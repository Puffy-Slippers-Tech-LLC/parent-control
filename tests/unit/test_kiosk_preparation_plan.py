"""Native preparation intent checks use independent real files and source inodes.

All storage is pytest-private; compiler/probe children have explicit deadlines
and are reaped. No mounts, service, system bus, policy or installation changes.
These component probes do not establish composed PAM admission.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

import pytest

from tests.unit.test_kiosk_material_authority import material_case
from tests.support.paths import ROOT
from tools import kiosk_view_receipt as receipt, test_storage


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def identity(path):
    s = path.lstat()
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns,
            s.st_mode, s.st_uid, s.st_gid]


@pytest.fixture(scope='module')
def plan_probe(tmp_path_factory):
    directory = tmp_path_factory.mktemp('native-preparation-plan')
    source, binary = directory / 'probe.c', directory / 'probe'
    source.write_text(r'''
#define _GNU_SOURCE
#define KIOSK_HOST_PROOF_OWNER getuid()
#define KIOSK_HOST_PROOF_GROUP getgid()
#include "kiosk_preparation_plan.h"
static void require(int ok) { if (!ok) { perror("plan-fixture"); exit(2); } }
static unsigned descriptors(void) {
    DIR *d=opendir("/proc/self/fd");require(d!=NULL);unsigned n=0;
    while(readdir(d))n++;
    require(!closedir(d));return n;
}
static char *read_bytes(const char *path,size_t *size) {
    FILE *f=fopen(path,"rb"); require(f!=NULL);
    require(!fseek(f,0,SEEK_END)); long n=ftell(f); require(n>=0 && n<=KIOSK_RECEIPT_BYTES);
    require(!fseek(f,0,SEEK_SET)); char *data=malloc((size_t)n+1); require(data!=NULL);
    require(fread(data,1,n,f)==(size_t)n && !fclose(f)); data[n]=0; *size=n; return data;
}
int main(int argc,char **argv) {
    require(argc==9); uint64_t now; require(!kiosk_host_now(&now)); uint64_t deadline=now+5000000;
    size_t ms,cs,ps; char *m=read_bytes(argv[2],&ms),*c=read_bytes(argv[3],&cs),*policy=read_bytes(argv[4],&ps);
    void *crypto=dlopen("libcrypto.so.3",RTLD_NOW|RTLD_LOCAL); require(crypto!=NULL);
    struct kiosk_material_authority a={0}; int result=kiosk_material_decode_until(&a,m,ms,c,cs,policy,ps,crypto,deadline);
    struct kiosk_host_proof proof={0}; proof.roots.root=proof.roots.usr=-1;
    int host=open(argv[5],O_PATH|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC); require(host>=0);
    int usr=openat(host,"usr",O_PATH|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC); require(usr>=0);
    struct kiosk_host_roots roots={host,usr};
    if(!result)result=kiosk_host_proof_capture_until(&proof,&roots,a.host_specs,a.host_count,deadline);
    int input=open(argv[6],O_RDONLY|O_CLOEXEC); require(input>=0);
    int copy=!strcmp(argv[7],"-")?-1:open(argv[7],O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    int clone=-1; struct kiosk_receipt v={0};
    if(!strcmp(argv[1],"gate") || !strcmp(argv[1],"view")) {
        size_t vs; char *vb=read_bytes(argv[8],&vs);
        if(!result)result=kiosk_receipt_parse(&v,vb,vs,crypto,deadline);
        free(vb);
        if(!result)result=kiosk_preparation_view_authority_until(&v,&a,deadline);
        clone=openat(host,"clone",O_PATH|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC); require(clone>=0);
    }
    if(!strcmp(argv[1],"renewed"))deadline++;
    if(!strcmp(argv[1],"expired"))deadline=1;
    struct kiosk_preparation_plan p={0};
    unsigned before=descriptors();
    if(!result && strcmp(argv[1],"view"))result=kiosk_preparation_plan_verify_until(&p,input,copy,&a,&proof,
        !strcmp(argv[1],"gate")?&v:NULL,clone,crypto,deadline);
    require(descriptors()==before);
    if(!result && strcmp(argv[1],"view")) {
        require(p.verified && p.deadline==deadline);
        if(copy>=0)for(unsigned i=0;i<p.ticket_members;i++) {
            const char *name;struct stat member;
            require(!kiosk_preparation_member_at_until(&p,copy,i,&name,&member));
            require(name!=NULL && S_ISREG(member.st_mode));
        }
        for(unsigned i=0;i<p.count;i++) {
            struct kiosk_preparation_row *r=p.rows+i;
            require(kiosk_preparation_plan_find(&p,r->path)==r);
            printf("%s\t%s\t%llu\t%d\t%s\t%llu\t%llu\n",r->path,r->kind,(unsigned long long)r->slot,r->required,r->source_class,
                (unsigned long long)r->origin[0],(unsigned long long)r->origin[1]);
        }
    }
    kiosk_preparation_plan_free(&p); kiosk_preparation_plan_free(&p); kiosk_receipt_free(&v);
    kiosk_host_proof_close(&proof); kiosk_material_free(&a);
    close(host);close(usr);close(input);if(copy>=0)close(copy);if(clone>=0)close(clone);
    free(m);free(c);free(policy);dlclose(crypto);return result?1:0;
}
''')
    result = subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                             '-I', str(ROOT / 'tools'), str(source), '-ldl', '-o', str(binary)],
                            capture_output=True, text=True, timeout=30,
                            pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == 0, result.stderr
    return binary


@pytest.fixture
def initial_case(material_case):
    case = material_case
    host = case['directory'] / 'host'
    host.mkdir(mode=0o755)
    for path, body in case['files'].items():
        target = host / path.lstrip('/')
        target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        for p in target.parents:
            if p == host:
                break
            p.chmod(0o755)
        target.write_bytes(body)
        target.chmod(0o755 if path in ('/usr/bin/tool', '/usr/bin/script') else 0o644)
    parent = case['directory'] / 'copies'
    parent.mkdir(mode=0o700)
    scratch = parent / ('.runtime-' + 'a' * 32)
    scratch.mkdir(mode=0o700)
    runtime = sorted([*deepcopy(case['record']['runtime']),
                      *(dict(row, kind='file', role='asset') for row in case['record']['payload'])],
                     key=lambda r: r['path'])
    native_copies, runtime_copies = [], []
    for group, records in ((native_copies, case['record']['native']), (runtime_copies, runtime)):
        for index, record in enumerate(records):
            name = ('native-' if group is native_copies else '') + str(index)
            target = scratch / name
            target.write_bytes(case['files'][record['path']])
            target.chmod(record['mode'])
            group.append(dict(index=index, name=name, identity=identity(target)))
    manifest = dict(format=1, backend='apparmor', records=runtime, copies=runtime_copies)
    manifest_bytes = encode(manifest)
    (scratch / 'runtime.json').write_bytes(manifest_bytes)
    (scratch / 'runtime.json').chmod(0o600)
    fd = os.open(scratch, os.O_RDONLY | os.O_DIRECTORY)
    try:
        mount = next(line.split()[1] for line in Path(f'/proc/self/fdinfo/{fd}').read_text().splitlines()
                     if line.startswith('mnt_id:'))
    finally:
        os.close(fd)
    runtime_receipt = dict(manifest, root=identity(scratch)[:2], mount=mount,
        manifest=hashlib.sha256(manifest_bytes).hexdigest(), manifest_identity=identity(scratch / 'runtime.json'))
    layout = [dict(path=path, kind='tree' if kind == 'directory' else kind)
              for kind, path, link in case['record']['proofs'] if path.startswith('/usr/')]
    native_map = {r['path']: (i, r, native_copies[i]) for i, r in enumerate(case['record']['native'])}
    runtime_map = {r['path']: (i, r, runtime_copies[i]) for i, r in enumerate(runtime)}
    sources = {}
    for slot, row in enumerate([dict(path='/usr', kind='tree'), *layout]):
        path = row['path']
        source = dict(kind=row['kind'], required=True, source_index=slot, source_class='skeleton')
        if row['kind'] == 'file':
            index, record, copied = (native_map if path in native_map else runtime_map)[path]
            source.update(source_class='native' if path in native_map else
                          'runtime' if path == '/usr/bin/script' else 'payload', index=index,
                          assertion=identity(host / path.lstrip('/')), record=deepcopy(record),
                          name=copied['name'], copy_identity=copied['identity'])
            if path in native_map:
                source['path'] = path
        sources[path] = source
    plan = dict(format=1, backend='apparmor', material=receipt.material_digest(case['record']),
                layout=layout, sources=sources, runtime=runtime_receipt, proofs=case['record']['proofs'],
                native=dict(records=case['record']['native'], copies=native_copies))
    ticket = dict(format=1, name=scratch.name, root=identity(scratch)[:2], parent=identity(parent)[:2],
                  members={p.name: identity(p)[:2] for p in scratch.iterdir()})
    case.update(host=host, scratch=scratch, result=dict(format=1, role='manager', backend='apparmor',
        material=plan['material'], source='-', plan=plan, ticket=ticket))
    return case


def run(probe, case, mode='initial', *, raw=None, view=None):
    directory = case['directory']
    paths = [directory / name for name in ('m.json', 'config.json', 'policy', 'result.json', 'view')]
    data = [receipt.material_canonical(case['record']), case['config_bytes'], case['policy_bytes'],
            encode(case['result']) if raw is None else raw,
            b'-' if view is None else receipt.encode_receipt(view)]
    for path, value in zip(paths, data):
        path.write_bytes(value)
    return subprocess.run([str(probe), mode, *(str(p) for p in paths[:3]), str(case['host']),
        str(paths[3]), '-' if mode in ('gate', 'view') else str(case['scratch']), str(paths[4])],
        capture_output=True, text=True, timeout=15, pass_fds=test_storage.scratch_descriptors())


def test_initial_plan_has_independent_native_and_supporting_copies(plan_probe, initial_case):
    result = run(plan_probe, initial_case)
    assert result.returncode == 0, result.stderr
    assert '/usr/bin/tool\tfile\t3\t1\tnative' in result.stdout
    assert (initial_case['scratch'] / 'native-0').stat().st_ino != (initial_case['host'] / 'usr/bin/tool').stat().st_ino


def add_initial_ambient(case, kind):
    target = case['host'] / 'usr/ambient'
    if kind == 'link': target.symlink_to('bin/script')
    elif kind == 'directory': target.mkdir(mode=0o755)
    else:
        target.write_bytes(b'ambient original')
        target.chmod(0o644)
    plan = case['result']['plan']
    row = dict(path='/usr/ambient', kind=kind)
    source = dict(kind=kind, required=False, source_class='ambient', path='/usr/ambient',
                  assertion=identity(target))
    if kind == 'link': row['link'] = source['link'] = 'bin/script'
    plan['layout'].append(row)
    plan['layout'].sort(key=lambda node: node['path'])
    plan['sources']['/usr/ambient'] = source
    for index, path in enumerate(sorted(plan['sources'])):
        plan['sources'][path]['source_index'] = index
        if path == '/usr/ambient': source['index'] = index
    return target, row, source


@pytest.mark.parametrize('kind', ['file', 'directory', 'link'])
@pytest.mark.parametrize('fault', [None, 'source-kind', 'source-link'])
def test_initial_ambient_intent_has_closed_kind_and_path_authority(plan_probe, initial_case, kind, fault):
    case = initial_case
    _target, row, source = add_initial_ambient(case, kind)
    if fault == 'source-kind':
        row['kind'] = source['kind'] = 'file' if kind != 'file' else 'directory'
        row.pop('link', None); source.pop('link', None)
    elif fault == 'source-link':
        if kind == 'link': source['link'] = 'bin/tool'
        else: source['assertion'][5] = stat.S_IFIFO | 0o600
    observed = run(plan_probe, case)
    assert observed.returncode == (0 if fault is None else 1), observed.stderr


@pytest.mark.parametrize('change', ['missing', 'same-byte-replacement', 'unsafe-mode', 'changed-type', 'changed-assertion'])
def test_initial_late_ambient_change_retains_only_frozen_intent(plan_probe, initial_case, change):
    case = initial_case
    target, _row, source = add_initial_ambient(case, 'file')
    original = source['assertion'][:2]
    if change == 'missing': target.unlink()
    elif change == 'same-byte-replacement':
        target.rename(target.with_name('old-ambient')); target.write_bytes(b'ambient original'); target.chmod(0o644)
    elif change == 'unsafe-mode': target.chmod(0o666)
    elif change == 'changed-type': target.unlink(); target.mkdir(mode=0o755)
    else:
        source['assertion'][1] += 1
        original = source['assertion'][:2]
    observed = run(plan_probe, case)
    assert observed.returncode == 0, observed.stderr
    assert f'\t0\tambient\t{original[0]}\t{original[1]}\n' in observed.stdout
    # Intent verification mounts nothing. Actual initial binding must turn each
    # changed source into absence/masking and must never adopt its replacement.


def test_initial_helper_cannot_invent_a_covered_tree_or_deep_source(plan_probe, initial_case):
    case = initial_case
    target, row, source = add_initial_ambient(case, 'directory')
    row['kind'] = source['kind'] = 'tree'
    source['source_class'] = 'skeleton'
    for key in ('path', 'index', 'assertion'): source.pop(key)
    child = target / 'deep'
    child.write_bytes(b'unselected deep source'); child.chmod(0o644)
    path = '/usr/ambient/deep'
    plan = case['result']['plan']
    plan['layout'].append(dict(path=path, kind='file')); plan['layout'].sort(key=lambda row: row['path'])
    plan['sources'][path] = dict(kind='file', required=False, source_class='ambient', path=path, assertion=identity(child))
    for slot, name in enumerate(sorted(plan['sources'])):
        plan['sources'][name]['source_index'] = slot
        if name == path: plan['sources'][name]['index'] = slot
    assert run(plan_probe, case).returncode == 1


@pytest.mark.parametrize('fault', ['role', 'material', 'source', 'extra-root', 'extra-plan', 'slot',
    'required', 'class', 'record-role', 'record-content', 'missing-required', 'copy-name', 'copy-inode',
    'ticket-inode', 'ticket-parent', 'ticket-extra', 'scratch-extra', 'copy-content', 'copy-hardlink',
    'source-inode', 'manifest-content', 'manifest-identity', 'runtime-member', 'native-member',
    'duplicate-key', 'noncanonical', 'expired', 'renewed'])
def test_initial_refuses_forged_claims_and_independent_inode_faults(plan_probe, initial_case, fault):
    case = initial_case
    result, plan = case['result'], case['result']['plan']
    native = plan['sources']['/usr/bin/tool']
    raw = None
    if fault in ('role', 'material', 'source'):
        result[fault] = 'wrong'
    elif fault == 'extra-root': result['unknown'] = 0
    elif fault == 'extra-plan': plan['unknown'] = 0
    elif fault == 'slot': native['source_index'] += 1
    elif fault == 'required': native['required'] = False
    elif fault == 'class': native['source_class'] = 'ambient'
    elif fault == 'record-role': native['record']['role'] = 'executor'
    elif fault == 'record-content': native['record']['sha256'] = 'f' * 64
    elif fault == 'missing-required':
        plan['layout'] = [row for row in plan['layout'] if row['path'] != '/usr/bin/tool']
        del plan['sources']['/usr/bin/tool']
    elif fault == 'copy-name': native['name'] = '0'
    elif fault == 'copy-inode': native['copy_identity'][1] += 1
    elif fault == 'ticket-inode': result['ticket']['members']['native-0'][1] += 1
    elif fault == 'ticket-parent': result['ticket']['parent'][1] += 1
    elif fault == 'ticket-extra': result['ticket']['members']['foreign'] = [1, 2]
    elif fault == 'scratch-extra': (case['scratch'] / 'foreign').touch()
    elif fault == 'copy-content': (case['scratch'] / 'native-0').write_bytes(b'wrong content')
    elif fault == 'copy-hardlink': os.link(case['scratch'] / 'native-0', case['directory'] / 'foreign-hardlink')
    elif fault == 'source-inode':
        source = case['host'] / 'usr/bin/tool'
        source.rename(source.with_name('old-tool'))
        source.write_bytes(case['files']['/usr/bin/tool']); source.chmod(0o755)
    elif fault == 'manifest-content': (case['scratch'] / 'runtime.json').write_bytes(b'{}')
    elif fault == 'manifest-identity': plan['runtime']['manifest_identity'][1] += 1
    elif fault == 'runtime-member': plan['runtime']['copies'].clear()
    elif fault == 'native-member': plan['native']['copies'].clear()
    elif fault == 'duplicate-key': raw = b'{"format":1,' + encode(result)[1:]
    elif fault == 'noncanonical': raw = b' ' + encode(result)
    observed = run(plan_probe, case, fault if fault in ('expired', 'renewed') else 'initial', raw=raw)
    assert observed.returncode == 1, observed.stderr


def gate_case(case):
    clone = case['host'] / 'clone'
    clone.mkdir(mode=0o755)
    for path, body in case['files'].items():
        target = clone / path.removeprefix('/usr/')
        target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        for parent in target.parents:
            if parent == clone: break
            parent.chmod(0o755)
        target.write_bytes(body)
        target.chmod((case['host'] / path.lstrip('/')).stat().st_mode & 0o7777)
    nodes = []
    for slot, (path, source) in enumerate(sorted(case['result']['plan']['sources'].items())):
        target = clone if path == '/usr' else clone / path.removeprefix('/usr/')
        info = identity(target)
        row = dict.fromkeys(receipt.NODE_FIELDS, 0)
        cls = source['source_class']
        record = source.get('record', {})
        row.update(path=path, kind=source['kind'], required=1, source_class=cls,
            acquisition='initial', role='manager' if cls == 'native' else 'skeleton' if cls == 'skeleton' else 'data',
            source_index=slot * 3, origin_device=info[0], origin_inode=info[1], device=info[0], inode=info[1],
            size=info[2], mtime_ns=info[3], ctime_ns=info[4], mode=info[5], uid=info[6], gid=info[7],
            nlink=target.stat().st_nlink, sha256=record.get('sha256', '-'), label='-', link='-', mountpoint=1)
        nodes.append(row)
    for path, kind in (('/usr/z-absent', 'absent'), ('/usr/z-masked', 'empty-directory')):
        row = dict.fromkeys(receipt.NODE_FIELDS, 0)
        row.update(path=path, kind=kind, source_index=len(nodes) * 3, source_class='ambient', role='ambient',
            acquisition='none', sha256='-', label='-', link='-')
        nodes.append(row)
    material = case['result']['material']
    view = dict(format=2, kind='V', backend='apparmor', role='manager', material=material,
        source='-', acquisition='a' * 64, nodes=nodes, coverage=[])
    digest = receipt.receipt_digest(view)
    layout = [dict(path=r['path'], kind=r['kind']) for r in nodes if r['path'] != '/usr']
    sources = {r['path']: dict(index=r['source_index'], assertion=identity(clone if r['path'] == '/usr'
                else clone / r['path'].removeprefix('/usr/'))) for r in nodes if r['required']}
    case['result'] = dict(format=1, role='gate', backend='apparmor', material=material, source=digest,
        ticket=None, plan=dict(material=material, layout=layout, sources=sources,
            source_slots={r['path']: r['source_index'] for r in nodes}, source_nodes=deepcopy(nodes), source_coverage=[]))
    return view


def test_gate_keeps_complete_original_mask_and_absence_slots(plan_probe, initial_case):
    view = gate_case(initial_case)
    result = run(plan_probe, initial_case, 'gate', view=view)
    assert result.returncode == 0, result.stderr
    assert '/usr/z-absent\tabsent\t' in result.stdout
    assert '/usr/z-masked\tempty-directory\t' in result.stdout


@pytest.mark.parametrize('fault', ['slot', 'missing-slot', 'added-source', 'assertion', 'clone-replacement',
    'foreign-content', 'required-omission', 'source-view-change', 'extra-source-field', 'ticket',
    'view-ambient-required', 'view-role', 'view-sha', 'view-class'])
def test_gate_cross_checks_original_view_and_independent_clone(plan_probe, initial_case, fault):
    case = initial_case
    view = gate_case(case)
    plan = case['result']['plan']
    if fault == 'slot': plan['source_slots']['/usr/bin/tool'] += 1
    elif fault == 'missing-slot': del plan['source_slots']['/usr/z-absent']
    elif fault == 'added-source': plan['sources']['/usr/z-absent'] = deepcopy(plan['sources']['/usr/bin/tool'])
    elif fault == 'assertion': plan['sources']['/usr/bin/tool']['assertion'][1] += 1
    elif fault == 'clone-replacement':
        target = case['host'] / 'clone/bin/tool'
        target.rename(target.with_name('old-tool')); target.write_bytes(case['files']['/usr/bin/tool']); target.chmod(0o755)
    elif fault == 'foreign-content': (case['host'] / 'clone/bin/tool').write_bytes(b'foreign')
    elif fault == 'required-omission': del plan['sources']['/usr/bin/tool']
    elif fault == 'source-view-change': plan['source_nodes'][0]['inode'] += 1
    elif fault == 'extra-source-field': plan['sources']['/usr/bin/tool']['foreign'] = True
    elif fault == 'ticket': case['result']['ticket'] = {}
    else:
        native = next(r for r in view['nodes'] if r['path'] == '/usr/bin/tool')
        if fault == 'view-ambient-required':
            native.update(required=0, source_class='ambient', role='ambient', sha256='-')
        elif fault == 'view-role': native['role'] = 'executor'
        elif fault == 'view-sha': native['sha256'] = 'f' * 64
        elif fault == 'view-class': native.update(source_class='runtime', role='data')
        plan['source_nodes'] = deepcopy(view['nodes'])
        case['result']['source'] = receipt.receipt_digest(view)
    observed = run(plan_probe, case, 'gate', view=view)
    assert observed.returncode == 1, observed.stderr


def add_gate_ambient(case, view, kind):
    path = '/usr/bin/ambient'
    target = case['host'] / 'clone/bin/ambient'
    if kind == 'link': target.symlink_to('script')
    elif kind == 'directory': target.mkdir(mode=0o755)
    else:
        target.write_bytes(b'ambient original source')
        target.chmod(0o644)
    info = identity(target)
    node = dict.fromkeys(receipt.NODE_FIELDS, 0)
    node.update(path=path, kind=kind, required=0, source_class='ambient', acquisition='initial',
        role='ambient', origin_device=info[0], origin_inode=info[1], device=info[0], inode=info[1],
        size=info[2], mtime_ns=info[3], ctime_ns=info[4], mode=info[5], uid=info[6], gid=info[7],
        nlink=target.lstat().st_nlink, sha256='-', label='-', link='script' if kind == 'link' else '-',
        mountpoint=0 if kind == 'link' else 1)
    view['nodes'].append(node)
    view['nodes'].sort(key=lambda row: row['path'])
    plan = case['result']['plan']
    for index, row in enumerate(view['nodes']):
        row['source_index'] = index * 3
        if row['path'] in plan['sources']:
            plan['sources'][row['path']]['index'] = index * 3
    plan['sources'][path] = dict(index=node['source_index'], assertion=info)
    # Inserting the independently observed ambient child changes its private
    # parent's metadata. Selection returns fresh source-local assertions, while
    # the completed V keeps its original inode/provenance and slot domain.
    for name, source in plan['sources'].items():
        current = case['host'] / 'clone' if name == '/usr' else case['host'] / 'clone' / name.removeprefix('/usr/')
        source['assertion'] = identity(current)
    plan['layout'].append(dict(path=path, kind=kind, **({'link': 'script'} if kind == 'link' else {})))
    plan['layout'].sort(key=lambda row: row['path'])
    plan['source_slots'] = {row['path']: row['source_index'] for row in view['nodes']}
    plan['source_nodes'] = deepcopy(view['nodes'])
    case['result']['source'] = receipt.receipt_digest(view)
    return path, target


def test_retained_view_cannot_invent_a_nonmaterial_tree(plan_probe, initial_case):
    case = initial_case
    view = gate_case(case)
    path, _target = add_gate_ambient(case, view, 'directory')
    row = next(node for node in view['nodes'] if node['path'] == path)
    row.update(kind='tree', source_class='skeleton', role='skeleton')
    plan = case['result']['plan']
    next(node for node in plan['layout'] if node['path'] == path)['kind'] = 'tree'
    plan['source_nodes'] = deepcopy(view['nodes'])
    case['result']['source'] = receipt.receipt_digest(view)
    assert run(plan_probe, case, 'gate', view=view).returncode == 1


@pytest.mark.parametrize('kind', ['file', 'directory', 'link'])
@pytest.mark.parametrize('decision', ['retain', 'omit', 'claim-without-source', 'wrong-inode', 'wrong-link'])
def test_gate_ambient_decisions_need_original_slot_and_actual_source(plan_probe, initial_case, kind, decision):
    case = initial_case
    view = gate_case(case)
    path, target = add_gate_ambient(case, view, kind)
    plan = case['result']['plan']
    if decision in ('omit', 'claim-without-source'):
        del plan['sources'][path]
        if decision == 'omit':
            plan['layout'] = [row for row in plan['layout'] if row['path'] != path]
            if kind == 'directory':
                plan['layout'].append(dict(path=path, kind='empty-directory'))
                plan['layout'].sort(key=lambda row: row['path'])
    elif decision == 'wrong-inode':
        plan['sources'][path]['assertion'][1] += 1
    elif decision == 'wrong-link':
        if kind == 'link':
            target.unlink(); target.symlink_to('tool')
        else:
            plan['sources'][path]['assertion'][0] += 1
    result = run(plan_probe, case, 'gate', view=view)
    assert result.returncode == (0 if decision in ('retain', 'omit') else 1), result.stderr
