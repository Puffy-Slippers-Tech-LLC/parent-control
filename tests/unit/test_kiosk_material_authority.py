"""Semantic material authority with independent host bytes and link witnesses.

Compiled probes and all fixture data use launcher-owned private disk scratch.
Children have explicit timeouts and are reaped; no bus, mount, UI or shared
service is used. These tests establish finite material contracts, not composed
retained-view/PAM admission. The coordinator owns the unit resource inventory.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from tools import kiosk_view_receipt
from tools import kiosk_confinement
from tools import test_storage


ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = '/usr/share/oh-no-parent-control/confinement'


@pytest.fixture(scope='module')
def material_probe(tmp_path_factory):
    directory = tmp_path_factory.mktemp('kiosk-material-authority')
    source, binary = directory / 'probe.c', directory / 'probe'
    source.write_text(r'''
#define _GNU_SOURCE
#define KIOSK_HOST_PROOF_OWNER getuid()
#define KIOSK_HOST_PROOF_GROUP getgid()
#include "kiosk_material_authority.h"
static void require(int ok) { if(!ok) { perror("material-fixture"); exit(2); } }
static char *read_bytes(const char *path,size_t *size) {
    FILE *stream=fopen(path,"rb"); require(stream!=NULL);
    require(fseek(stream,0,SEEK_END)==0); long length=ftell(stream);
    require(length>=0 && length<=KIOSK_RECEIPT_BYTES && fseek(stream,0,SEEK_SET)==0);
    char *data=malloc((size_t)length+1); require(data!=NULL);
    require(fread(data,1,(size_t)length,stream)==(size_t)length && fclose(stream)==0);
    data[length]=0; *size=(size_t)length; return data;
}
int main(int argc,char **argv) {
    require(argc>=5); uint64_t now; require(kiosk_host_now(&now)==0);
    uint64_t deadline=!strcmp(argv[1],"expired")?1:now+5000000ULL;
    size_t ms,cs,ps; char *m=read_bytes(argv[2],&ms),*c=read_bytes(argv[3],&cs),*p=read_bytes(argv[4],&ps);
    void *crypto=dlopen("libcrypto.so.3",RTLD_NOW|RTLD_LOCAL); require(crypto!=NULL);
    struct kiosk_material_authority authority={0};
    int result=kiosk_material_decode_until(&authority,m,ms,c,cs,p,ps,crypto,deadline);
    if(!result && !strncmp(argv[1],"host",4)) {
        require(argc==6); int root=open(argv[5],O_PATH|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC); require(root>=0);
        int usr=openat(root,"usr",O_PATH|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC); require(usr>=0);
        struct kiosk_host_roots roots={.root=root,.usr=usr}; struct kiosk_host_proof proof={0};
        result=kiosk_host_proof_capture_until(&proof,&roots,authority.host_specs,authority.host_count,deadline);
        if(!result)result=kiosk_material_verify_host_until(&authority,&proof);
        if(!result)result=kiosk_material_verify_routes_until(&authority,&proof);
        if(!result && !strcmp(argv[1],"host-late-optional")) {
            int added=openat(usr,"bin/optional",O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0755); require(added>=0);
            require(write(added,"\177ELF optional",13)==13 && close(added)==0);
            result=kiosk_material_verify_routes_until(&authority,&proof);
        }
        if(!result && !strcmp(argv[1],"host-late-library")) {
            require(symlinkat("libsystemd-shared-260.so",usr,"lib/systemd/libsystemd-late.so")==0);
            result=kiosk_material_verify_routes_until(&authority,&proof);
        }
        if(!result && !strcmp(argv[1],"host-renewed-deadline")) {
            proof.deadline++;
            result=kiosk_material_verify_routes_until(&authority,&proof);
        }
        if(!result && !strcmp(argv[1],"host-pinned-usr")) {
            require(renameat(root,"usr",root,"original-usr")==0 && mkdirat(root,"usr",0755)==0);
            /* Simulate the caller's replacement /usr after attachment. */
            result=kiosk_material_verify_routes_until(&authority,&proof);
        }
        kiosk_host_proof_close(&proof); require(close(root)==0 && close(usr)==0);
    }
    if(!result) {
        puts(authority.digest);
        for(unsigned i=0;i<authority.count;i++) {
            const struct kiosk_material_spec *s=authority.specs+i;
            require(kiosk_material_find(&authority,s->path)==s);
            printf("%s\t%s\t%s\t%s\t%s\t%s\t%s\n",s->path,s->kind,s->source_class,s->role,s->source,s->sha256,s->link);
        }
        for(unsigned i=0;i<authority.route_count;i++) {
            const struct kiosk_material_route *r=authority.routes+i;
            printf("route\t%s\t%d\n",r->path?r->path:r->library_directory,r->selected);
        }
    }
    kiosk_material_free(&authority); kiosk_material_free(&authority);
    free(m); free(c); free(p); require(dlclose(crypto)==0); return result?1:0;
}
''')
    result = subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-O2',
                             '-I', str(ROOT / 'tools'), str(source), '-ldl', '-o', str(binary)],
                            capture_output=True, text=True, timeout=30,
                            pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == 0, result.stderr
    return binary


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def _proofs(files, links=()):
    members = {'/': ('directory', '-')}
    for path in files:
        for parent in Path(path).parents:
            members[str(parent)] = ('directory', '-')
        members[path] = ('file', '-')
    for path, target in links:
        for parent in Path(path).parents:
            members[str(parent)] = ('directory', '-')
        members[path] = ('link', target)
    return [[kind, path, target] for path, (kind, target) in sorted(members.items())]


@pytest.fixture
def material_case(tmp_path):
    config = dict(backend='apparmor', domains=['manager'],
                  executables=[dict(role='manager', paths=['/usr/bin/tool'], optional=False)],
                  preserved_executables=[], reserved_directories=[],
                  runtime_inputs={'/usr/bin/script': dict(kind='file', role='script')})
    config_bytes = json.dumps(config, indent=2).encode() + b'\n'
    policy_bytes, native_bytes, script_bytes = b'trusted policy\n', b'\x7fELF independent native\n', b'#!/usr/bin/python3\n'
    record = dict(format=1, backend='apparmor', config=_hash(config_bytes), policy=_hash(policy_bytes),
                  native=[dict(role='manager', path='/usr/bin/tool', sha256=_hash(native_bytes),
                               size=len(native_bytes), source_label=None, mode=0o755, label=None)],
                  preserved=[], runtime=[dict(path='/usr/bin/script', kind='file', role='script',
                       sha256=_hash(script_bytes), size=len(script_bytes), mode=0o755, label=None)],
                  payload=[dict(path=PAYLOAD + '/config.json', sha256=_hash(config_bytes),
                                size=len(config_bytes), mode=0o644, label=None),
                           dict(path=PAYLOAD + '/onpc-kiosk.apparmor', sha256=_hash(policy_bytes),
                                size=len(policy_bytes), mode=0o644, label=None)])
    files = {'/usr/bin/tool': native_bytes, '/usr/bin/script': script_bytes,
             PAYLOAD + '/config.json': config_bytes, PAYLOAD + '/onpc-kiosk.apparmor': policy_bytes}
    record['proofs'] = _proofs(files)
    return dict(record=record, config=config, config_bytes=config_bytes, policy_bytes=policy_bytes,
                files=files, directory=tmp_path)


def _rebind_config(case):
    case['config_bytes'] = json.dumps(case['config'], indent=2).encode() + b'\n'
    case['record']['config'] = _hash(case['config_bytes'])
    case['record']['payload'][0].update(sha256=_hash(case['config_bytes']), size=len(case['config_bytes']))
    case['files'][PAYLOAD + '/config.json'] = case['config_bytes']


def _run(probe, case, mode='decode', *, material=None, config=None, policy=None, host=None):
    directory = case['directory']
    paths = [directory / name for name in ('m.json', 'config.json', 'policy')]
    values = [material if material is not None else _encode(case['record']),
              config if config is not None else case['config_bytes'],
              policy if policy is not None else case['policy_bytes']]
    for path, value in zip(paths, values):
        path.write_bytes(value)
    return subprocess.run([str(probe), mode, *map(str, paths), *([str(host)] if host else [])],
                          capture_output=True, text=True, timeout=10,
                          pass_fds=test_storage.scratch_descriptors())


def _original_host(case):
    host = case['directory'] / 'original-host'
    host.mkdir(mode=0o755)
    linked = {path for kind, path, _ in case['record']['proofs'] if kind == 'link'}
    for kind, path, _ in case['record']['proofs']:
        if kind == 'directory' and not any(str(parent) in linked for parent in Path(path).parents):
            target = host / path.lstrip('/')
            target.mkdir(mode=0o755, parents=True, exist_ok=True)
            target.chmod(0o755)
    modes = {row.get('source', row['path']): 0o755 for row in case['record']['native']}
    modes.update({row['path']: row['mode'] for group in ('runtime', 'preserved', 'payload')
                  for row in case['record'][group] if 'mode' in row})
    for path, data in case['files'].items():
        target = host / path.lstrip('/')
        target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        for parent in target.parents:
            if parent == host:
                break
            parent.chmod(0o755)
        target.write_bytes(data)
        target.chmod(modes.get(path, 0o644))
    for kind, path, link in case['record']['proofs']:
        if kind == 'link':
            target = host / path.lstrip('/')
            target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            if target.is_symlink():
                assert target.readlink() == Path(link)
            else:
                target.symlink_to(link)
    return host


def test_semantic_authority_closes_destinations_and_original_host(material_probe, material_case):
    case = material_case
    host = _original_host(case)
    result = _run(material_probe, case, 'host', host=host)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0] == kiosk_view_receipt.material_digest(case['record'])
    assert '/usr/bin/tool\tfile\tnative\tmanager\t/usr/bin/tool\t' in result.stdout
    assert '/usr/bin/script\tfile\truntime\tdata\t' in result.stdout
    assert '/usr/bin\ttree\tskeleton\tskeleton\t' in result.stdout
    # A mutually consistent M is insufficient when independently opened bytes disagree.
    (host / 'usr/bin/tool').write_bytes(b'changed original-host bytes\n')
    assert _run(material_probe, case, 'host', host=host).returncode == 1


def test_alias_closure_has_independent_target_and_selected_route(material_probe, material_case):
    case = material_case
    case['config']['executables'][0]['paths'] = ['/bin/tool']
    case['record']['native'][0]['aliases'] = ['/bin/tool']
    case['record']['proofs'] = _proofs(case['files'], [('/bin', 'usr/bin')])
    case['record']['proofs'].append(['file', '/bin/tool', '-'])
    case['record']['proofs'].sort(key=lambda row: row[1])
    _rebind_config(case)
    host = _original_host(case)
    result = _run(material_probe, case, 'host', host=host)
    assert result.returncode == 0, result.stderr
    assert 'route\t/bin/tool\t1' in result.stdout
    case['record']['proofs'] = [row for row in case['record']['proofs'] if row[1] != '/bin']
    assert _run(material_probe, case).returncode == 1


def test_unselected_optional_route_is_exposed_for_native_host_check(material_probe, material_case):
    case = material_case
    case['config']['executables'].append(dict(role='service', paths=['/usr/bin/optional'], optional=True))
    _rebind_config(case)
    result = _run(material_probe, case)
    assert result.returncode == 0, result.stderr
    assert 'route\t/usr/bin/optional\t0' in result.stdout


@pytest.mark.parametrize('candidate', ['absent', 'dangling', 'non-directory', 'present', 'alias',
    'untrusted-parent', 'dangling-untrusted', 'present-untrusted-parent', 'untrusted-link-text',
    'non-utf8-link-text', 'loop', 'late', 'renewed-deadline'])
def test_current_host_optional_route_absence(material_probe, material_case, candidate):
    case = material_case
    path = '/usr/bin/optional'
    if candidate in ('non-directory', 'untrusted-parent', 'present-untrusted-parent'):
        path = '/usr/private/optional'
    case['config']['executables'].append(dict(role='audio', paths=[path], optional=True))
    _rebind_config(case)
    host = _original_host(case)
    mode = 'host'
    if candidate == 'present':
        (host / path.lstrip('/')).write_bytes(b'\x7fELF unreported native')
    elif candidate == 'alias':
        (host / path.lstrip('/')).symlink_to('tool')
    elif candidate == 'dangling':
        (host / path.lstrip('/')).symlink_to('missing')
    elif candidate == 'loop':
        (host / path.lstrip('/')).symlink_to('optional')
    elif candidate in ('untrusted-link-text', 'non-utf8-link-text'):
        (host / path.lstrip('/')).symlink_to('missing\tname' if candidate == 'untrusted-link-text' else 'missing-\udcff')
    elif candidate == 'non-directory':
        (host / 'usr/private').write_bytes(b'not a directory')
        (host / 'usr/private').chmod(0o644)
    elif candidate in ('untrusted-parent', 'dangling-untrusted', 'present-untrusted-parent'):
        (host / 'usr/private').mkdir(mode=0o777)
        (host / 'usr/private').chmod(0o777)
        if candidate == 'dangling-untrusted':
            (host / path.lstrip('/')).symlink_to('../private/missing')
        elif candidate == 'present-untrusted-parent':
            (host / path.lstrip('/')).write_bytes(b'\x7fELF unreported untrusted native')
    elif candidate == 'late':
        mode = 'host-late-optional'
    elif candidate == 'renewed-deadline':
        mode = 'host-renewed-deadline'
    assert _run(material_probe, case).returncode == 0
    result = _run(material_probe, case, mode, host=host)
    absent = ('absent', 'dangling', 'non-directory', 'untrusted-parent', 'dangling-untrusted',
              'untrusted-link-text', 'non-utf8-link-text', 'loop')
    if candidate in absent:
        assert not (host / path.lstrip('/')).exists()
    assert result.returncode == (0 if candidate in absent else 1), result.stderr


def _library_case(case, *, directory_alias=False, optional=False):
    directory = '/usr/lib/systemd'
    path = '/usr/lib/private/shared-260.bin'
    alias = directory + '/libsystemd-shared-260.so'
    body = b'\x7fELF independently observed library'
    case['config']['executables'].append(dict(role='library', paths=[], library_directory=directory,
                                            optional=optional))
    case['record']['native'].append(dict(role='library', path=path, aliases=[alias],
        sha256=_hash(body), size=len(body), mode=0o644, label=None, source_label=None))
    case['files'][path] = body
    links = [(alias, path)]
    if directory_alias:
        # The glob's concrete directory has a different canonical name. The
        # lexical child is still mandatory proof text, not another dentry.
        links += [(directory, 'actual'), ('/usr/lib/actual/libsystemd-shared-260.so', path)]
    case['record']['proofs'] = _proofs(case['files'], links)
    if directory_alias:
        next(row for row in case['record']['proofs'] if row[1] == directory)[:] = ['link', directory, 'actual']
    _rebind_config(case)
    return directory, path, alias


@pytest.mark.parametrize('candidate', ['healthy', 'extra-file', 'extra-alias', 'extra-directory',
    'extra-dangling', 'extra-substituted-source', 'late-alias', 'ambient-siblings', 'changed-target'])
def test_current_host_library_membership(material_probe, material_case, candidate):
    case = material_case
    directory, path, alias = _library_case(case)
    host = _original_host(case)
    (host / path.lstrip('/')).chmod(0o644)
    extra = host / (directory + '/libsystemd-extra.so').lstrip('/')
    mode = 'host'
    if candidate == 'extra-file':
        extra.write_bytes(b'\x7fELF omitted library')
    elif candidate == 'extra-alias':
        extra.symlink_to(Path(alias).name)
    elif candidate == 'extra-directory':
        extra.mkdir(mode=0o755)
    elif candidate == 'extra-dangling':
        extra.symlink_to('missing')
    elif candidate == 'extra-substituted-source':
        extra.symlink_to('/usr/bin/tool')
    elif candidate == 'late-alias':
        mode = 'host-late-library'
    elif candidate == 'changed-target':
        (host / alias.lstrip('/')).unlink()
        (host / alias.lstrip('/')).symlink_to('/usr/bin/tool')
    elif candidate == 'ambient-siblings':
        for name in ('ambient', 'libsystemd-extra.so.1', 'libother-260.so', 'invalid\tname'):
            (host / directory.lstrip('/') / name).write_bytes(b'ambient unrelated bytes')
        (host / directory.lstrip('/') / 'writable').mkdir(mode=0o777)
    # The material and its closed host proof cannot see additional glob inputs.
    assert _run(material_probe, case).returncode == 0
    result = _run(material_probe, case, mode, host=host)
    assert result.returncode == (0 if candidate in ('healthy', 'ambient-siblings') else 1), result.stderr


def test_library_directory_alias_is_enumerated_from_original_host(material_probe, material_case):
    case = material_case
    directory, path, _ = _library_case(case, directory_alias=True)
    host = _original_host(case)
    (host / path.lstrip('/')).chmod(0o644)
    assert _run(material_probe, case, 'host', host=host).returncode == 0
    (host / 'usr/lib/actual/libsystemd-extra.so').symlink_to('libsystemd-shared-260.so')
    assert _run(material_probe, case, 'host', host=host).returncode == 1


def test_unselected_optional_library_still_requires_existing_trusted_directory(material_probe, material_case):
    case = material_case
    directory = '/usr/lib/systemd'
    case['config']['executables'].append(dict(role='library', paths=[], library_directory=directory,
                                            optional=True))
    case['record']['proofs'] += [['directory', '/usr/lib', '-'], ['directory', directory, '-']]
    case['record']['proofs'].sort(key=lambda row: row[1])
    _rebind_config(case)
    host = _original_host(case)
    assert _run(material_probe, case, 'host', host=host).returncode == 0
    (host / directory.lstrip('/')).rmdir()
    assert _run(material_probe, case, 'host', host=host).returncode == 1
    (host / directory.lstrip('/')).mkdir(mode=0o755, parents=True)
    assert _run(material_probe, case, 'host', host=host).returncode == 0
    (host / directory.lstrip('/') / 'libsystemd-omitted.so').write_bytes(b'\x7fELF omitted')
    assert _run(material_probe, case, 'host', host=host).returncode == 1


def test_optional_empty_library_requires_declared_directory_proof(material_probe, material_case):
    case = material_case
    case['config']['executables'].append(dict(role='library', paths=[],
                                            library_directory='/usr/lib/systemd', optional=True))
    _rebind_config(case)
    # No native member happens to retain this directory; attested config still
    # requires its trusted ancestry even for an empty optional glob.
    assert _run(material_probe, case).returncode == 1


def test_routes_use_separately_pinned_original_usr(material_probe, material_case):
    case = material_case
    case['config']['executables'].append(dict(role='audio', paths=['/usr/bin/optional'], optional=True))
    _library_case(case)
    host = _original_host(case)
    assert _run(material_probe, case, 'host-pinned-usr', host=host).returncode == 0
    assert not (host / 'usr/bin/tool').exists()
    assert (host / 'original-usr/bin/tool').read_bytes() == case['files']['/usr/bin/tool']


def test_library_scan_limit_is_aggregate_across_declared_directories(material_probe, material_case):
    case = material_case
    directory, _, _ = _library_case(case)
    # Repeated declared scans still consume bounded work; sibling metadata and
    # contents are irrelevant. Empty private files keep this disk fixture small.
    host = _original_host(case)
    parent = host / directory.lstrip('/')
    for index in range(16384):
        (parent / f'ambient-{index}').touch()
    assert _run(material_probe, case, 'host', host=host).returncode == 0
    case['config']['executables'].append(deepcopy(case['config']['executables'][-1]))
    _rebind_config(case)
    (host / (PAYLOAD + '/config.json').lstrip('/')).write_bytes(case['config_bytes'])
    result = _run(material_probe, case, 'host', host=host)
    assert result.returncode == 1, result.stderr


def test_substitution_keeps_destination_and_original_source_authority_separate(material_probe, material_case):
    case = material_case
    paths = ['/usr/bin/bwrap', '/usr/libexec/private-bwrap']
    bodies = [b'\x7fELF vendor bwrap', b'\x7fELF fixed wrapper']
    for i, role in enumerate(('bwrap', 'bwrap-native')):
        case['config']['executables'].append(dict(role=role, paths=[paths[i]], source=paths[1 - i]))
        case['record']['native'].append(dict(role=role, path=paths[i], source=paths[1 - i],
            sha256=_hash(bodies[1 - i]), size=len(bodies[1 - i]), mode=0o755, label=None, source_label=None))
        case['files'][paths[i]] = bodies[i]
    case['record']['proofs'] = _proofs(case['files'])
    _rebind_config(case)
    host = _original_host(case)
    result = _run(material_probe, case, 'host', host=host)
    assert result.returncode == 0, result.stderr
    assert '/usr/bin/bwrap\tfile\tnative\tbwrap\t/usr/libexec/private-bwrap\t' in result.stdout
    # The finite production swap also consumes this destination as bwrap-native
    # source. Its original setid mode cannot be treated as a destination waiver.
    (host / 'usr/bin/bwrap').chmod(0o4755)
    assert _run(material_probe, case, 'host', host=host).returncode == 1
    (host / 'usr/bin/bwrap').chmod(0o755)
    case['record']['native'][1]['sha256'] = _hash(bodies[0])
    # A changed M digest cannot replace the independently measured source bytes.
    assert _run(material_probe, case, 'host', host=host).returncode == 1


@pytest.mark.parametrize('mutation', ['not-elf', 'not-executable', 'wrong-size'])
def test_independent_native_host_semantics(material_probe, material_case, mutation):
    case = material_case
    native = case['record']['native'][0]
    if mutation == 'not-elf':
        case['files'][native['path']] = b'plain text matching a forged material record\n'
        native.update(sha256=_hash(case['files'][native['path']]), size=len(case['files'][native['path']]))
    elif mutation == 'wrong-size':
        native['size'] += 1
    host = _original_host(case)
    if mutation == 'not-executable':
        (host / 'usr/bin/tool').chmod(0o644)
    # Hash/proof parsing alone succeeds; independent native source semantics deny.
    assert _run(material_probe, case).returncode == 0
    assert _run(material_probe, case, 'host', host=host).returncode == 1


def test_reserved_directory_alias_cannot_escape_usr(material_probe, material_case):
    case = material_case
    case['config']['reserved_directories'] = ['/usr/reserved']
    case['record']['proofs'] += [['directory', '/etc', '-'], ['link', '/usr/reserved', '/etc']]
    case['record']['proofs'].sort(key=lambda row: row[1])
    _rebind_config(case)
    assert _run(material_probe, case).returncode == 1


@pytest.mark.parametrize('fault', ['healthy', 'changed-target', 'outside-directory', 'missing-proof', 'missing-alias'])
def test_library_glob_lexical_alias_keeps_canonical_host_source(material_probe, material_case, fault):
    case = material_case
    directory = '/usr/lib/systemd'
    path = '/usr/lib/private/shared-260.bin'
    alias = directory + '/libsystemd-shared-260.so'
    body = b'\x7fELF independently observed library'
    case['config']['executables'].append(dict(role='library', paths=[], library_directory=directory))
    case['record']['native'].append(dict(role='library', path=path, aliases=[alias],
        sha256=_hash(body), size=len(body), mode=0o644, label=None, source_label=None))
    case['files'][path] = body
    case['record']['proofs'] = _proofs(case['files'], [(alias, path)])
    _rebind_config(case)
    if fault == 'changed-target':
        next(row for row in case['record']['proofs'] if row[1] == alias)[2] = '/usr/bin/tool'
    elif fault == 'outside-directory':
        outside = '/usr/lib/private/libsystemd-shared-260.so'
        case['record']['native'][-1]['aliases'] = [outside]
        case['record']['proofs'] = _proofs(case['files'], [(outside, path)])
    elif fault == 'missing-proof':
        case['record']['proofs'] = [row for row in case['record']['proofs'] if row[1] != alias]
    elif fault == 'missing-alias':
        del case['record']['native'][-1]['aliases']
    if fault == 'healthy':
        host = _original_host(case)
        # Libraries need ELF content, but source_record permits non-executable mode.
        (host / path.lstrip('/')).chmod(0o644)
        result = _run(material_probe, case, 'host', host=host)
        assert result.returncode == 0, result.stderr
        assert path + '\tfile\tnative\tlibrary\t' in result.stdout
        assert alias + '\tlink\talias\tdata\t' in result.stdout
        assert 'route\t' + directory + '\t1' in result.stdout
    else:
        assert _run(material_probe, case).returncode == 1


def test_library_alias_cannot_cross_substitution_source(material_probe, material_case, monkeypatch):
    case = material_case
    directory, first = '/usr/lib/systemd', '/usr/lib/systemd/libsystemd-first.so'
    foo, bar = '/usr/lib/foo', '/usr/lib/bar'
    bodies = {first: b'\x7fELF first library', foo: b'\x7fELF original foo', bar: b'\x7fELF replacement bar'}
    case['config']['executables'] += [dict(role='library', paths=[], library_directory=directory),
        dict(role='library', paths=[foo], source=bar), dict(role='library', paths=[bar], source=foo)]
    for path, source in ((first, None), (foo, bar), (bar, foo)):
        body = bodies[source or path]
        record = dict(role='library', path=path, sha256=_hash(body), size=len(body),
                      mode=0o644, label=None, source_label=None)
        if source:
            record['source'] = source
        case['record']['native'].append(record)
    case['files'].update(bodies)
    case['record']['proofs'] = _proofs(case['files'])
    _rebind_config(case)
    assert _run(material_probe, case).returncode == 0
    host = _original_host(case)
    # Exercise inventory() independently with real paths, preserving its source
    # predicates while replacing only the fixture's root ownership walk.
    configured = deepcopy(case['config'])
    for entry in configured['executables']:
        entry['paths'] = [str(host / path.lstrip('/')) for path in entry['paths']]
        for key in ('source', 'library_directory'):
            if key in entry:
                entry[key] = str(host / entry[key].lstrip('/'))
    monkeypatch.setattr(kiosk_confinement, 'trusted', lambda path, **kwargs: Path(path).resolve(strict=True))
    assert len(kiosk_confinement.inventory(configured)) == 4
    alias = directory + '/libsystemd-foo.so'
    (host / alias.lstrip('/')).symlink_to('../foo')
    with pytest.raises(ValueError, match='conflicting-executable-roles'):
        kiosk_confinement.inventory(configured)
    case['record']['native'][2]['aliases'] = [alias]
    case['record']['proofs'] = _proofs(case['files'], [(alias, '../foo')])
    # A globally selected unsubstituted library route cannot authorize an alias
    # for the separate substituted source, even though its target path matches.
    assert _run(material_probe, case).returncode == 1


def test_vendor_privilege_is_limited_to_exact_attested_member(material_probe, material_case):
    case = material_case
    path, data = '/usr/lib/polkit-1/helper', b'\x7fELF vendor helper'
    case['config']['preserved_executables'] = [dict(path=path, mode=0o4755, label=None)]
    case['record']['preserved'] = [dict(path=path, mode=0o4755, label=None, uid=0, gid=0,
                                      sha256=_hash(data), size=len(data))]
    case['files'][path] = data
    case['record']['proofs'] = _proofs(case['files'])
    _rebind_config(case)
    result = _run(material_probe, case)
    assert result.returncode == 0, result.stderr
    assert path + '\tfile\tvendor\tvendor\t' in result.stdout
    case['record']['preserved'][0]['mode'] = 0o755
    assert _run(material_probe, case).returncode == 1


def test_runtime_mask_is_terminal_without_granting_dev_null_source(material_probe, material_case):
    case = material_case
    path = PAYLOAD + '/user-units/masked.service'
    case['config']['runtime_inputs'][path] = dict(kind='link', role='unit', link='/dev/null')
    case['record']['runtime'].append(dict(path=path, kind='link', role='unit', link='/dev/null'))
    case['record']['runtime'].sort(key=lambda row: row['path'])
    case['record']['proofs'] = _proofs(case['files'], [(path, '/dev/null')])
    _rebind_config(case)
    result = _run(material_probe, case)
    assert result.returncode == 0, result.stderr
    assert path + '\tlink\truntime\tdata\t' in result.stdout
    assert '/dev/null' not in [row[1] for row in case['record']['proofs']]
    case['record']['runtime'][-1]['link'] = '/etc/passwd'
    assert _run(material_probe, case).returncode == 1


def test_selinux_copy_labels_derive_from_closed_native_role(material_probe, material_case):
    case = material_case
    case['config']['backend'] = case['record']['backend'] = 'selinux'
    native = case['record']['native'][0]
    native.update(source_label='system_u:object_r:bin_t:s0',
                  label='system_u:object_r:onpc_kiosk_manager_exec_t:s0')
    case['record']['runtime'][0]['label'] = 'system_u:object_r:bin_t:s0'
    for row in case['record']['payload']:
        row['label'] = 'system_u:object_r:usr_t:s0'
    case['record']['payload'][1]['path'] = PAYLOAD + '/onpc-kiosk.cil'
    case['files'][PAYLOAD + '/onpc-kiosk.cil'] = case['files'].pop(PAYLOAD + '/onpc-kiosk.apparmor')
    case['record']['proofs'] = _proofs(case['files'])
    _rebind_config(case)
    result = _run(material_probe, case)
    assert result.returncode == 0, result.stderr
    native['label'] = 'system_u:object_r:onpc_kiosk_executor_exec_t:s0'
    assert _run(material_probe, case).returncode == 1


@pytest.mark.parametrize('mutation', [
    'unknown-root', 'unknown-native', 'unknown-runtime', 'unknown-proof-kind',
    'duplicate-native', 'duplicate-runtime', 'duplicate-proof', 'missing-parent',
    'missing-native', 'missing-runtime', 'missing-payload', 'wrong-policy-hash',
    'wrong-config-hash', 'wrong-payload-size', 'wrong-runtime-role', 'wrong-runtime-mode',
    'wrong-native-role', 'wrong-native-mode', 'forged-substitution', 'forged-alias',
    'extra-proof', 'conflicting-proof', 'noncanonical-path', 'invalid-label',
    'oversize', 'wrong-format', 'wrong-type', 'lone-surrogate',
])
def test_semantic_refusals(material_probe, material_case, mutation):
    case, m = material_case, material_case['record']
    if mutation == 'unknown-root':
        m['ambient'] = []
    elif mutation == 'unknown-native':
        m['native'][0]['required'] = False
    elif mutation == 'unknown-runtime':
        m['runtime'][0]['ambient'] = True
    elif mutation == 'unknown-proof-kind':
        m['proofs'][0][0] = 'other'
    elif mutation.startswith('duplicate-'):
        group = mutation.removeprefix('duplicate-')
        group = 'proofs' if group == 'proof' else group
        m[group].append(deepcopy(m[group][0]))
    elif mutation == 'missing-parent':
        m['proofs'] = [row for row in m['proofs'] if row[1] != '/usr/bin']
    elif mutation.startswith('missing-'):
        m[mutation.removeprefix('missing-')].clear()
    elif mutation == 'wrong-policy-hash':
        m['policy'] = '0' * 64
    elif mutation == 'wrong-config-hash':
        m['config'] = '0' * 64
    elif mutation == 'wrong-payload-size':
        m['payload'][0]['size'] += 1
    elif mutation == 'wrong-runtime-role':
        m['runtime'][0]['role'] = 'asset'
    elif mutation == 'wrong-runtime-mode':
        m['runtime'][0]['mode'] = 0o644
    elif mutation == 'wrong-native-role':
        m['native'][0]['role'] = 'executor'
    elif mutation == 'wrong-native-mode':
        m['native'][0]['mode'] = 0o4755
    elif mutation == 'forged-substitution':
        m['native'][0]['source'] = '/usr/bin/script'
    elif mutation == 'forged-alias':
        m['native'][0]['aliases'] = ['/usr/bin/script']
    elif mutation == 'extra-proof':
        m['proofs'].append(['directory', '/usr/unused', '-'])
        m['proofs'].sort(key=lambda row: row[1])
    elif mutation == 'conflicting-proof':
        next(row for row in m['proofs'] if row[1] == '/usr/bin/tool')[0] = 'directory'
    elif mutation == 'noncanonical-path':
        m['native'][0]['path'] = '/usr/bin/../bin/tool'
    elif mutation == 'invalid-label':
        m['native'][0]['source_label'] = 'forged'
    elif mutation == 'oversize':
        m['native'][0]['size'] = 512 * 1024 * 1024 + 1
    elif mutation == 'wrong-format':
        m['format'] = 2
    elif mutation == 'wrong-type':
        m['format'] = True
    elif mutation == 'lone-surrogate':
        m['native'][0]['path'] = '/usr/bin/\ud800'
    assert _run(material_probe, case).returncode == 1


@pytest.mark.parametrize('which', ['config', 'policy'])
def test_exact_attested_bytes_are_checked(material_probe, material_case, which):
    case = material_case
    assert _run(material_probe, case, **{which: case[which + '_bytes'] + b' '}).returncode == 1


@pytest.mark.parametrize('encoding', ['duplicate-material-key', 'duplicate-config-key', 'whitespace', 'trailing', 'nul', 'expired'])
def test_encoding_and_deadline_refusals(material_probe, material_case, encoding):
    case = material_case
    data = _encode(case['record'])
    kwargs = {}
    if encoding == 'duplicate-material-key':
        data = b'{"backend":"apparmor",' + data[1:]
    elif encoding == 'duplicate-config-key':
        case['config_bytes'] = b'{"backend":"apparmor",' + case['config_bytes'][1:]
        case['record']['config'] = _hash(case['config_bytes'])
        case['record']['payload'][0].update(sha256=_hash(case['config_bytes']), size=len(case['config_bytes']))
        data = _encode(case['record'])
    elif encoding == 'whitespace':
        data = b' ' + data
    elif encoding == 'trailing':
        data += b'{}'
    elif encoding == 'nul':
        data += b'\0'
    result = _run(material_probe, case, 'expired' if encoding == 'expired' else 'decode', material=data, **kwargs)
    assert result.returncode == 1
