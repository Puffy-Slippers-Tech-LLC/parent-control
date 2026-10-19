"""Completed-record selection against independent M and actual private inodes.

Pytest-private files and bounded, reaped compiler/probe children only. Each
probe uses its own user namespace to observe root ownership; no mounts, bus,
service or installed product is changed. Actual recursive coverage and live
manager identity remain the composed native/PAM fixture's responsibility.
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
from tests.unit.test_kiosk_preparation_plan import initial_case, identity
from tests.support.paths import ROOT
from tools import kiosk_confinement as preparation, kiosk_view_receipt as receipt, test_storage

BOOT = '01234567-89ab-cdef-0123-456789abcdef'
MARKER = '/usr/share/oh-no-parent-control/confinement/retained-view'


@pytest.fixture(scope='module')
def retained_probe(tmp_path_factory):
    directory = tmp_path_factory.mktemp('kiosk-retained-record')
    source, binary = directory / 'probe.c', directory / 'probe'
    header = (ROOT / 'tools/kiosk_confinement.h').read_text()
    paths = header[header.index('static int\nkiosk_trusted_stat('):header.index('/* Open parents separately.')]
    types = header[header.index('struct kiosk_pin_entry {'):header.index('static int\nkiosk_pin_reap_worker_until(')]
    mount_id = header[header.index('static int\nkiosk_pin_fd_mount('):header.index('static int\nkiosk_pin_attached_topology_until(')]
    same = header[header.index('static int\nkiosk_pin_same_stat('):header.index('static int\nkiosk_pin_open(')]
    source.write_text(r'''
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#include <limits.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/xattr.h>
#include <dirent.h>
#define KIOSK_VIEW_ROWS 32768U
#define KIOSK_VIEW_BYTES (64U * 1024U * 1024U)
static void require(int ok) {if(!ok){perror("retained-fixture");exit(2);}}
static void put(const char *path,const char *bytes) {
    int fd=open(path,O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC,0600);require(fd>=0);
    require(write(fd,bytes,strlen(bytes))==(ssize_t)strlen(bytes)&&close(fd)==0);
}
static void own_namespace(void) {
    uid_t uid=getuid();gid_t gid=getgid();char mapping[128];
    require(unshare(CLONE_NEWUSER)==0);put("/proc/self/setgroups","deny");
    snprintf(mapping,sizeof(mapping),"0 %lu 1\n",(unsigned long)uid);put("/proc/self/uid_map",mapping);
    snprintf(mapping,sizeof(mapping),"0 %lu 1\n",(unsigned long)gid);put("/proc/self/gid_map",mapping);
}
''' + paths + types + mount_id + same + r'''
#include "kiosk_retained_record.h"
static unsigned descriptors(void) {
    DIR *d=opendir("/proc/self/fd");require(d!=NULL);unsigned n=0;
    while(readdir(d))n++;
    require(!closedir(d));return n;
}
static char *read_bytes(const char *path,size_t *size) {
    FILE *f=fopen(path,"rb");require(f!=NULL);require(!fseek(f,0,SEEK_END));long n=ftell(f);
    require(n>0&&n<KIOSK_RECEIPT_BYTES&&!fseek(f,0,SEEK_SET));char *b=malloc((size_t)n+1);require(b!=NULL);
    require(fread(b,1,n,f)==(size_t)n&&!fclose(f));b[n]=0;*size=n;return b;
}
int main(int argc,char **argv) {
    require(argc==7);require(!chdir(argv[1]));own_namespace();
    uint64_t now;require(!kiosk_pin_now(&now));uint64_t deadline=now+5000000ULL;
    size_t ms,cs,ps;char *m=read_bytes("m.json",&ms),*c=read_bytes("config.json",&cs),*p=read_bytes("policy",&ps);
    void *crypto=dlopen("libcrypto.so.3",RTLD_NOW|RTLD_LOCAL);require(crypto!=NULL);
    struct kiosk_material_authority a={0};require(!kiosk_material_decode_until(&a,m,ms,c,cs,p,ps,crypto,deadline));
    int runtime=open("copies",O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    int usr=open("manager",O_PATH|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    int marker=kiosk_preparation_open(usr,KIOSK_RETAINED_MARKER,1,deadline);require(runtime>=0&&usr>=0&&marker>=0);
    struct kiosk_retained_record r;kiosk_retained_record_init(&r);unsigned before=descriptors();
    const char *mode=argv[2];uint64_t selected=!strcmp(mode,"expired")?1:!strcmp(mode,"renewed")?deadline+1:deadline;
    int result=kiosk_retained_record_open_until(&r,runtime,usr,marker,&a,argv[3],crypto,selected);
    if(!result) {
        require(r.verified&&r.manager_executable>=0&&r.receipt.nn>0);
        require((fcntl(r.view_fd,F_GETFL)&O_ACCMODE)==O_RDONLY&&(fcntl(r.slots_fd,F_GETFL)&O_ACCMODE)==O_RDONLY);
        int seals=fcntl(r.slots_fd,F_GET_SEALS);require(seals==(F_SEAL_WRITE|F_SEAL_GROW|F_SEAL_SHRINK|F_SEAL_SEAL));
        char *slots;size_t count;require(!kiosk_publication_read(r.slots_fd,&slots,&count,deadline));
        printf("slots %.*s\n",(int)count,slots);free(slots);
        for(unsigned i=0;i<r.inventory.count;i++)printf("ambient %s %u\n",r.inventory.entries[i].relative,r.ambient[i]);
        if(!strcmp(mode,"replace")) {
            require(!renameat(r.publication.root,argv[4],r.publication.root,"old-record"));
            int out=openat(r.publication.root,argv[4],O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);require(out>=0&&close(out)==0);
        } else if(!strcmp(mode,"bytes")) {
            int out=openat(r.publication.root,argv[4],O_WRONLY|O_APPEND|O_CLOEXEC);require(out>=0&&write(out,"X",1)==1&&!close(out));
        } else if(!strcmp(mode,"extra")) {
            int out=openat(r.publication.root,"foreign",O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);require(out>=0&&!close(out));
        } else if(!strcmp(mode,"root")) {
            require(!renameat(runtime,r.view,runtime,"old-root")&&!mkdirat(runtime,r.view,0700));
        } else if(!strcmp(mode,"marker")) {
            require(!fchmod(marker,0644));int out=kiosk_preparation_open(usr,KIOSK_RETAINED_MARKER,0,deadline);require(out>=0&&!close(out));
        }
        result=kiosk_retained_record_recheck_until(&r,usr,marker,&a,crypto,!strcmp(mode,"late-renewed")?deadline+1:deadline);
    }
    kiosk_retained_record_close(&r);kiosk_retained_record_close(&r);require(descriptors()==before);
    require(!close(marker)&&!close(usr)&&!close(runtime));kiosk_material_free(&a);free(m);free(c);free(p);dlclose(crypto);
    return result?1:0;
}
''')
    result = subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                             '-Wno-unused-function', '-I', str(ROOT / 'tools'), str(source),
                             '-ldl', '-o', str(binary)], capture_output=True, text=True,
                            timeout=30, pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == 0, result.stderr
    return binary


@pytest.fixture
def retained_case(initial_case):
    case = initial_case
    manager = case['directory'] / 'manager'
    manager.mkdir(mode=0o755)
    for kind, path, _link in case['record']['proofs']:
        if kind == 'directory' and path.startswith('/usr/'):
            target = manager / path.removeprefix('/usr/')
            target.mkdir(mode=0o755, parents=True, exist_ok=True)
            target.chmod(0o755)
    marker = manager / MARKER.removeprefix('/usr/')
    marker.touch(); marker.chmod(0o444)
    for name in ('ambient', 'z-masked'):
        (manager / name).mkdir(mode=0o755)
    sources = case['result']['plan']['sources']
    nodes = []
    for slot, (path, source) in enumerate(sorted(sources.items())):
        target = (case['scratch'] / source['name'] if 'name' in source else
                  manager if path == '/usr' else manager / path.removeprefix('/usr/'))
        info = identity(target)
        origin = identity(case['host'] / path.lstrip('/'))[:2]
        cls = source['source_class']
        row = dict.fromkeys(receipt.NODE_FIELDS, 0)
        row.update(path=path, kind=source['kind'], required=1, source_class=cls, acquisition='initial',
                   role='manager' if cls == 'native' else 'skeleton' if cls == 'skeleton' else 'data',
                   source_index=slot * 3, origin_device=origin[0], origin_inode=origin[1],
                   device=info[0], inode=info[1], size=info[2], mtime_ns=info[3], ctime_ns=info[4],
                   mode=info[5], uid=0, gid=0, nlink=target.stat().st_nlink,
                   sha256=source.get('record', {}).get('sha256', '-'), label='-', link='-',
                   mountpoint=int(path == '/usr' or source['kind'] == 'file'))
        nodes.append(row)
    info = identity(manager / 'ambient')
    ambient = dict.fromkeys(receipt.NODE_FIELDS, 0)
    ambient.update(path='/usr/ambient', kind='directory', required=0, source_class='ambient',
                   role='ambient', acquisition='initial', source_index=1, origin_device=info[0],
                   origin_inode=info[1], device=info[0], inode=info[1], size=info[2], mtime_ns=info[3],
                   ctime_ns=info[4], mode=info[5], uid=0, gid=0, nlink=2,
                   sha256='-', label='-', link='-', mountpoint=1)
    nodes.append(ambient)
    for path, kind in (('/usr/z-absent', 'absent'), ('/usr/z-masked', 'empty-directory')):
        row = dict.fromkeys(receipt.NODE_FIELDS, 0)
        row.update(path=path, kind=kind, source_index=100 + len(nodes), source_class='ambient', role='ambient',
                   acquisition='none', sha256='-', label='-', link='-')
        nodes.append(row)
    nodes.sort(key=lambda node: node['path'])
    view = dict(format=2, kind='V', backend='apparmor', role='manager', material=case['result']['material'],
                source='-', acquisition='a' * 64, nodes=nodes, coverage=[])
    case.update(manager=manager, marker=marker, view=view)
    publish(case)
    return case


def publish(case):
    view = case['view']
    digest = receipt.receipt_digest(view)
    scratch = case['scratch']
    if scratch.name != digest:
        scratch = scratch.rename(scratch.parent / digest)
        case['scratch'] = scratch
    marker_bytes = f'ONPC-KIOSK-VIEW\t1\tapparmor\t{view["material"]}\t{digest}\n'.encode()
    case['marker'].chmod(0o644); case['marker'].write_bytes(marker_bytes); case['marker'].chmod(0o444)
    # V does not include marker metadata, so writing it cannot make a recursive
    # hash input. Directory inode/mode assertions remain independent.
    inventory = []
    for row in view['nodes']:
        if row['kind'] in ('absent', 'link'):
            continue
        path = row['path']
        values = ([row['device'], row['inode'], row['mode'], 0, 0] if row['kind'] != 'empty-directory'
                  else [*(identity(case['manager'] / path.removeprefix('/usr/'))[:2]), stat.S_IFDIR | 0o755, 0, 0])
        inventory.append([path.removeprefix('/usr').lstrip('/'), *values, row['mountpoint']])
    marker_info = identity(case['marker'])
    inventory.append([MARKER.removeprefix('/usr/'), marker_info[0], marker_info[1], marker_info[5], 0, 0, 0])
    inventory.sort()
    pins = 'ONPC-KIOSK-PINS\t1\n'
    for index, (relative, dev, ino, mode, uid, gid, mountpoint) in enumerate(inventory):
        parent = str(Path(relative).parent)
        parent = '' if parent == '.' else parent
        parent_index = next((i for i, row in enumerate(inventory[:index]) if row[0] == parent), 0)
        pins += f'P\t{relative or "-"}\t{dev}\t{ino}\t{mode}\t{uid}\t{gid}\t{parent_index}\t{mountpoint}\n'
    case['pins'] = pins.encode()
    root_info = scratch.stat()
    source_info = case['manager'].stat()
    source_fd = os.open(case['manager'], os.O_PATH | os.O_DIRECTORY)
    try:
        source_mount = next(line.split()[1] for line in Path(f'/proc/self/fdinfo/{source_fd}').read_text().splitlines()
                            if line.startswith('mnt_id:'))
    finally:
        os.close(source_fd)
    ready = (f'ONPC-KIOSK-READY\t2\t{view["material"]}\t{digest}\t{hashlib.sha256(case["pins"]).hexdigest()}\t{BOOT}'
             f'\t{root_info.st_dev}\t{root_info.st_ino}\t{source_info.st_dev}\t{source_info.st_ino}'
             f'\t{marker_info[0]}\t{marker_info[1]}\t{source_mount}\t123\n').encode()
    for name, data in [('material.json', receipt.material_canonical(case['record'])),
                       ('view', receipt.encode_receipt(view)), ('pins', case['pins']), ('ready', ready)]:
        (scratch / name).write_bytes(data); (scratch / name).chmod(0o600)
    # Python's host UID is observed as root in the probe's private namespace.
    manifest_path = scratch / 'runtime.json'
    manifest = case['result']['plan']['runtime']
    disk = {key: deepcopy(manifest[key]) for key in ('format', 'backend', 'records', 'copies')}
    for row in disk['copies']:
        row['identity'][6:8] = [0, 0]
    manifest_path.write_bytes(preparation.runtime_canonical(disk)); manifest_path.chmod(0o600)


def run(probe, case, mode='healthy', member='ready', boot=BOOT):
    directory = case['directory']
    for name, data in [('m.json', receipt.material_canonical(case['record'])),
                       ('config.json', case['config_bytes']), ('policy', case['policy_bytes'])]:
        (directory / name).write_bytes(data)
    return subprocess.run([str(probe), str(directory), mode, boot, member, '-', '-'],
                          capture_output=True, text=True, timeout=15,
                          pass_fds=test_storage.scratch_descriptors())


def test_retained_selection_keeps_native_manager_and_all_source_slots(retained_probe, retained_case):
    case = retained_case
    before = {p.name: (p.stat().st_ino, p.read_bytes()) for p in case['scratch'].iterdir()}
    observed = run(retained_probe, case)
    assert observed.returncode == 0, observed.stderr
    slots = json.loads(observed.stdout.splitlines()[0].removeprefix('slots '))
    assert slots == dict(format=1, material=case['view']['material'], source=receipt.receipt_digest(case['view']),
                         slots={n['path']: n['source_index'] for n in case['view']['nodes']})
    assert 'ambient ambient 1\n' in observed.stdout
    assert 'ambient bin/tool 0\n' in observed.stdout
    assert 'ambient z-masked 1\n' in observed.stdout
    assert before == {p.name: (p.stat().st_ino, p.read_bytes()) for p in case['scratch'].iterdir()}


@pytest.mark.parametrize('name', ['quote-"', 'backslash-\\', 'é', '😀'])
def test_retained_slots_preserve_valid_names_with_canonical_ascii_json(retained_probe, retained_case, name):
    case = retained_case
    path = '/usr/a-' + name
    (case['manager'] / 'ambient').rename(case['manager'] / path.removeprefix('/usr/'))
    row = next(node for node in case['view']['nodes'] if node['path'] == '/usr/ambient')
    row['path'] = path
    publish(case)
    observed = run(retained_probe, case)
    assert observed.returncode == 0, observed.stderr
    expected = dict(format=1, material=case['view']['material'], source=receipt.receipt_digest(case['view']),
                    slots={node['path']: node['source_index'] for node in case['view']['nodes']})
    raw = observed.stdout.splitlines()[0].removeprefix('slots ').encode('utf-8')
    assert raw == json.dumps(expected, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


@pytest.mark.parametrize('fault', ['expired', 'renewed', 'late-renewed', 'extra', 'root', 'marker'])
def test_retained_selection_refuses_identity_or_deadline_changes(retained_probe, retained_case, fault):
    observed = run(retained_probe, retained_case, fault)
    assert observed.returncode == 1, observed.stderr


@pytest.mark.parametrize('mode', ['bytes', 'replace'])
@pytest.mark.parametrize('member', ['ready', 'view', 'material.json', 'pins', 'runtime.json', 'native-0', '0'])
def test_retained_final_check_repeats_every_named_identity_and_hash(retained_probe, retained_case, mode, member):
    observed = run(retained_probe, retained_case, mode, member)
    assert observed.returncode == 1, observed.stderr


@pytest.mark.parametrize('fault', ['absent-ready', 'boot', 'ready-root', 'ready-source', 'ready-marker',
    'ready-inventory', 'ready-attachment', 'view-class', 'view-copy', 'native-content', 'native-hardlink', 'supporting-content',
    'supporting-identity', 'supporting-record', 'manifest-format', 'foreign-member', 'inventory-extra',
    'inventory-required-ambient', 'missing-copy', 'marker-material'])
def test_retained_rejects_forged_completion_and_copy_authority(retained_probe, retained_case, fault):
    case = retained_case
    root = case['scratch']
    boot = BOOT
    if fault == 'absent-ready': (root / 'ready').unlink()
    elif fault == 'boot': boot = '11234567-89ab-cdef-0123-456789abcdef'
    elif fault.startswith('ready-'):
        fields = (root / 'ready').read_text().rstrip('\n').split('\t')
        field = {'ready-root': 7, 'ready-source': 9, 'ready-marker': 11, 'ready-inventory': 4, 'ready-attachment': 12}[fault]
        fields[field] = 'f' * 64 if field == 4 else str(int(fields[field]) + 1)
        (root / 'ready').write_text('\t'.join(fields) + '\n')
    elif fault in ('view-class', 'view-copy'):
        row = next(n for n in case['view']['nodes'] if n['path'] == '/usr/bin/tool')
        if fault == 'view-class': row.update(source_class='runtime', role='data')
        else: row['inode'] += 1
        publish(case)
    elif fault == 'native-content': (root / 'native-0').write_bytes(b'foreign ELF bytes')
    elif fault == 'native-hardlink': os.link(root / 'native-0', case['directory'] / 'foreign-link')
    elif fault == 'supporting-content': (root / '0').write_bytes(b'foreign supporting bytes')
    elif fault in ('supporting-identity', 'supporting-record', 'manifest-format'):
        path = root / 'runtime.json'
        data = path.read_bytes(); prefix = len(b'ONPC-KIOSK-RUNTIME\0') + 8
        disk = json.loads(data[prefix:])
        if fault == 'supporting-identity': disk['copies'][0]['identity'][1] += 1
        elif fault == 'supporting-record': disk['records'][0]['sha256'] = 'f' * 64
        else: disk['format'] = 2
        path.write_bytes(preparation.runtime_canonical(disk))
    elif fault == 'foreign-member': (root / 'foreign').write_bytes(b'unknown')
    elif fault.startswith('inventory-'):
        pins = case['pins']
        if fault == 'inventory-extra':
            pins += f'P\tzz-extra\t1\t123\t{stat.S_IFDIR | 0o755}\t0\t0\t0\t0\n'.encode()
        else:
            lines = pins.decode().splitlines()
            row = next(i for i, line in enumerate(lines) if line.startswith('P\tbin/tool\t'))
            fields = lines[row].split('\t'); fields[3] = str(int(fields[3]) + 1)
            lines[row] = '\t'.join(fields); pins = ('\n'.join(lines) + '\n').encode()
        (root / 'pins').write_bytes(pins)
        fields = (root / 'ready').read_text().rstrip('\n').split('\t')
        fields[4] = hashlib.sha256(pins).hexdigest(); (root / 'ready').write_text('\t'.join(fields) + '\n')
    elif fault == 'missing-copy': (root / 'native-0').unlink()
    else:
        case['marker'].chmod(0o644)
        case['marker'].write_text(case['marker'].read_text().replace(case['view']['material'], 'f' * 64))
        case['marker'].chmod(0o444)
    observed = run(retained_probe, case, boot=boot)
    assert observed.returncode == 1, observed.stderr
