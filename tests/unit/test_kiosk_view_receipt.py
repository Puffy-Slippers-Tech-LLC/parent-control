"""Bounded compiled receipt witnesses, with independently opened source inodes.

Private files/links test source replacement and link provenance. C witnesses
test the closed coverage encoding and independent comparison, not actual mount
topology or PAM admission. The native pin suite owns real private mount tests.
Compiler/probe children are bounded and synchronously reaped; all fixture state
uses launcher-provided disk scratch. No bus, display, service or shared writes.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat
import subprocess

import pytest

from tools import kiosk_view_receipt as receipt
from tools import test_storage


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def receipt_probe(tmp_path_factory):
    directory = tmp_path_factory.mktemp('kiosk-view-receipt')
    source, binary = directory / 'receipt.c', directory / 'receipt'
    source.write_text(r'''
#define _GNU_SOURCE
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include "kiosk_view_receipt.h"
static void require(int ok) { if (!ok) { fprintf(stderr,"receipt-fixture:%s\n",strerror(errno)); exit(2); } }
static char *read_bytes(const char *path, size_t *size) {
    FILE *stream=fopen(path,"rb"); require(stream!=NULL);
    require(fseek(stream,0,SEEK_END)==0); long length=ftell(stream);
    require(length>=0 && length<=KIOSK_RECEIPT_BYTES && fseek(stream,0,SEEK_SET)==0);
    char *data=malloc((size_t)length+1); require(data!=NULL);
    require(fread(data,1,(size_t)length,stream)==(size_t)length && fclose(stream)==0);
    data[length]=0; *size=(size_t)length; return data;
}
static int inode(const struct kiosk_receipt_row *row, const char *path, int coverage) {
    struct stat info; int fd=open(path,O_PATH|O_NOFOLLOW|O_CLOEXEC);
    if(fd<0)return -1;
    int result=fstat(fd,&info); require(close(fd)==0); if(result)return -1;
    uint64_t values[]={info.st_dev,info.st_ino,info.st_size,
        (uint64_t)info.st_mtim.tv_sec*1000000000ULL+info.st_mtim.tv_nsec,
        (uint64_t)info.st_ctim.tv_sec*1000000000ULL+info.st_ctim.tv_nsec,
        info.st_mode,info.st_uid,info.st_gid};
    unsigned first=coverage?KC_DEV:KR_DEV;
    for(unsigned i=0;i<8;i++)if(row->number[first+i]!=values[i])return -1;
    if(!coverage && row->number[KR_NLINK]!=(uint64_t)info.st_nlink)return -1;
    return 0;
}
int main(int argc,char **argv) {
    require(argc>=3); uint64_t deadline; struct timespec now;
    require(clock_gettime(CLOCK_MONOTONIC,&now)==0);
    deadline=(uint64_t)now.tv_sec*1000000ULL+now.tv_nsec/1000ULL+5000000ULL;
    if(!strcmp(argv[1],"expired"))deadline=1;
    void *crypto=dlopen("libcrypto.so.3",RTLD_NOW|RTLD_LOCAL); require(crypto!=NULL);
    size_t size; char *data=read_bytes(argv[2],&size), hash[65];
    int result=-1;
    if(!strcmp(argv[1],"material")) {
        result=kiosk_receipt_material_hash(data,size,crypto,deadline,hash);
        if(!result)puts(hash);
    } else {
        struct kiosk_receipt parsed={0},expected={0};
        result=kiosk_receipt_parse(&parsed,data,size,crypto,deadline);
        if(!result && (!strcmp(argv[1],"match") || !strcmp(argv[1],"derive"))) {
            require(argc==4); size_t other_size; char *other=read_bytes(argv[3],&other_size);
            result=kiosk_receipt_parse(&expected,other,other_size,crypto,deadline);
            if(!result)result=!strcmp(argv[1],"match")?
                kiosk_receipt_match(&parsed,&expected,deadline):kiosk_receipt_derivation(&expected,&parsed,deadline);
            free(other);
        }
        if(!result && !strcmp(argv[1],"observe")) {
            require(argc==6);
            const struct kiosk_receipt_row *file=kiosk_receipt_find(&parsed,"/usr/bin/tool");
            const struct kiosk_receipt_row *link=kiosk_receipt_find(&parsed,"/usr/z-link");
            result=!file || !link || parsed.nc!=1?-1:inode(file,argv[3],0);
            if(!result)result=inode(link,argv[4],0);
            if(!result)result=inode(&parsed.coverage[0],argv[5],1);
            if(!result) {
                char text[4096]; ssize_t n=readlink(argv[4],text,sizeof(text)-1);
                if(n<0)result=-1;
                else { text[n]=0; if(strcmp(text,link->v[KR_LINK]))result=-1; }
            }
            if(!result) {
                int fd=open(argv[3],O_RDONLY|O_NOFOLLOW|O_CLOEXEC); char bytes[32]={0};
                if(fd<0 || read(fd,bytes,sizeof(bytes))!=14 || strcmp(bytes,"original-token"))result=-1;
                if(fd>=0)require(close(fd)==0);
            }
        }
        if(!result)puts(parsed.digest);
        kiosk_receipt_free(&expected); kiosk_receipt_free(&parsed);
    }
    free(data); require(dlclose(crypto)==0); return result?1:0;
}
''')
    result = subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-O2',
                             '-I', str(ROOT / 'tools'), str(source), '-ldl', '-o', str(binary)],
                            text=True, capture_output=True, timeout=30,
                            pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == 0, result.stderr
    return binary


def _identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, size=info.st_size,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
                mode=info.st_mode, uid=info.st_uid, gid=info.st_gid)


def _node(path, kind, index, *, required=0, source_class='ambient', role='ambient', info=None, link='-'):
    fields = dict(device=1, inode=index + 100, size=0, mtime_ns=1, ctime_ns=1,
                  mode=(stat.S_IFREG if kind == 'file' else stat.S_IFLNK if kind == 'link' else stat.S_IFDIR) | 0o755,
                  uid=0, gid=0)
    if info is not None:
        fields = _identity(info)
    return dict(path=path, kind=kind, required=required, source_class=source_class,
                acquisition='initial', role=role, source_index=index,
                origin_device=fields['device'], origin_inode=fields['inode'], **fields,
                nlink=info.st_nlink if info is not None else 1,
                sha256=hashlib.sha256(b'original-token').hexdigest() if kind == 'file' and required else '-',
                label='-', link=link, mountpoint=int(kind in ('file', 'directory') or path == '/usr'))


@pytest.fixture
def source_view(tmp_path):
    tool = tmp_path / 'tool'
    tool.write_bytes(b'original-token')
    tool.chmod(0o755)
    link = tmp_path / 'link'
    link.symlink_to('share/ambient')
    nested = tmp_path / 'nested'
    nested.mkdir()
    nodes = [
        _node('/usr', 'tree', 0, required=1, source_class='skeleton', role='skeleton'),
        _node('/usr/bin', 'tree', 1, required=1, source_class='skeleton', role='skeleton'),
        _node('/usr/bin/tool', 'file', 2, required=1, source_class='native', role='manager', info=tool.stat()),
        _node('/usr/share', 'tree', 3, source_class='skeleton', role='skeleton'),
        _node('/usr/share/ambient', 'directory', 4),
        _node('/usr/z-link', 'link', 5, info=link.lstat(), link='share/ambient'),
    ]
    fields = _identity(nested.stat())
    witness = dict(owner=4, path='/usr/share/ambient/nested',
                   origin_device=fields['device'], origin_inode=fields['inode'], **fields)
    return (dict(format=2, kind='V', backend='apparmor', role='manager', material='1' * 64,
                 source='-', acquisition='2' * 64, nodes=nodes, coverage=[witness]), tool, link, nested)


def _run(probe, tmp_path, data, mode='parse', others=()):
    source = tmp_path / 'record'
    source.write_bytes(data)
    result = subprocess.run([str(probe), mode, str(source), *(str(path) for path in others)],
                            text=True, capture_output=True, timeout=10,
                            pass_fds=test_storage.scratch_descriptors())
    return result


def test_material_hash_preserves_existing_encoding(receipt_probe, tmp_path):
    from tools.kiosk_confinement import material_digest
    record = dict(format=1, backend='apparmor', config='1' * 64, policy='2' * 64,
                  native=[dict(path='/usr/bin/t\u00e9st', role='manager', size=1)], runtime=[],
                  preserved=[], proofs=[['directory', '/usr', None]], payload=[])
    data = json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')
    expected = hashlib.sha256(b'ONPC-KIOSK-MATERIAL\0' + len(data).to_bytes(8, 'big') + data).hexdigest()
    assert receipt.material_canonical(record) == data
    assert receipt.material_digest(record) == material_digest(record) == expected
    result = _run(receipt_probe, tmp_path, data, 'material')
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


@pytest.mark.parametrize('data', [
    b'{"b":1,"a":2}', b'{"a":1,"a":2}', b'{ "a":1}', b'{"a":01}',
    b'{"a":-0}', b'{"a":1.0}', b'{"a":1e0}', b'{"a":"\\/"}',
    b'{"a":"\\u0041"}', b'{"a":"\\u00EF"}', b'{"a":NaN}', b'{}\n',
    b'{"a":' + b'[' * 65 + b'0' + b']' * 65 + b'}', b'{"a":"x\x00y"}',
])
def test_native_material_refuses_noncanonical(receipt_probe, tmp_path, data):
    assert _run(receipt_probe, tmp_path, data, 'material').returncode == 1


def test_native_material_sorts_prefix_keys_by_content(receipt_probe, tmp_path):
    record = {'a!': 2, 'a': 1, 'a ': 3, 'a_': 4}
    result = _run(receipt_probe, tmp_path, receipt.material_canonical(record), 'material')
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == receipt.material_digest(record)


def test_native_receipt_hash_and_independent_sources(receipt_probe, source_view, tmp_path):
    view, tool, link, nested = source_view
    data = receipt.encode_receipt(view)
    expected = hashlib.sha256(b'ONPC-KIOSK-VIEW\0' + len(data).to_bytes(8, 'big') + data).hexdigest()
    result = _run(receipt_probe, tmp_path, data, 'observe', (tool, link, nested))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == receipt.receipt_digest(view) == expected


@pytest.mark.parametrize('target', ['tool', 'link', 'nested', 'bytes'])
def test_independent_replacement_or_source_drift_refuses(receipt_probe, source_view, tmp_path, target):
    view, tool, link, nested = source_view
    data = receipt.encode_receipt(view)
    if target == 'tool':
        tool.rename(tmp_path / 'old-tool')
        tool.write_bytes(b'original-token')
        tool.chmod(0o755)
    elif target == 'link':
        link.unlink()
        link.symlink_to('foreign')
    elif target == 'nested':
        nested.rename(tmp_path / 'old-nested')
        nested.mkdir()
    else:
        tool.write_bytes(b'changed--token')
    result = _run(receipt_probe, tmp_path, data, 'observe', (tool, link, nested))
    assert result.returncode == 1, result.stderr


@pytest.mark.parametrize('fault', ['version', 'backend', 'role', 'self', 'unknown', 'class',
                                  'acquisition', 'required', 'index', 'order', 'extra',
                                  'nul', 'newline', 'coverage-owner', 'coverage-path'])
def test_closed_native_grammar(receipt_probe, source_view, tmp_path, fault):
    view = source_view[0]
    lines = receipt.encode_receipt(view).decode().splitlines()
    header, tool, ambient, coverage = lines[0].split('\t'), lines[3].split('\t'), lines[5].split('\t'), lines[-1].split('\t')
    if fault == 'version': header[1] = '1'
    elif fault == 'backend': header[3] = 'foreign'
    elif fault == 'role': header[4] = 'gate'
    elif fault == 'self': header[6] = '3' * 64
    elif fault == 'class': tool[1 + receipt.NODE_FIELDS.index('source_class')] = 'host-path'
    elif fault == 'acquisition': tool[1 + receipt.NODE_FIELDS.index('acquisition')] = 'retained'
    elif fault == 'required': ambient[1 + receipt.NODE_FIELDS.index('required')] = '1'
    elif fault == 'index': tool[1 + receipt.NODE_FIELDS.index('source_index')] = '1'
    elif fault == 'coverage-owner': coverage[1] = '2'
    elif fault == 'coverage-path': coverage[2] = '/usr/share/../foreign'
    lines[0], lines[3], lines[5], lines[-1] = '\t'.join(header), '\t'.join(tool), '\t'.join(ambient), '\t'.join(coverage)
    if fault == 'unknown': lines.append('X\tforeign')
    elif fault == 'order': lines[2], lines[3] = lines[3], lines[2]
    elif fault == 'extra': lines[3] += '\textra'
    data = ('\n'.join(lines) + '\n').encode()
    if fault == 'nul': data = data.replace(b'tool', b'to\x00l')
    elif fault == 'newline': data = data[:-1]
    assert _run(receipt_probe, tmp_path, data).returncode == 1


@pytest.mark.parametrize('fault', ['missing-required', 'missing-coverage', 'role', 'index', 'provenance', 'label', 'link', 'material', 'acquisition'])
def test_native_expected_closure_is_independent(receipt_probe, source_view, tmp_path, fault):
    expected = source_view[0]
    actual = deepcopy(expected)
    if fault == 'missing-required': del actual['nodes'][2]
    elif fault == 'missing-coverage': actual['coverage'] = []
    elif fault == 'role': actual['nodes'][2]['role'] = 'gate'
    elif fault == 'index': actual['nodes'][-1]['source_index'] += 1
    elif fault == 'provenance': actual['nodes'][2]['origin_inode'] += 1
    elif fault == 'label': actual['nodes'][2]['label'] = 'foreign_t'
    elif fault == 'link': actual['nodes'][-1]['link'] = 'foreign'
    elif fault == 'material': actual['material'] = '3' * 64
    else: actual['acquisition'] = '4' * 64
    if fault == 'missing-required':
        actual['coverage'][0]['owner'] -= 1
    expected_path = tmp_path / 'expected'
    expected_path.write_bytes(receipt.encode_receipt(expected))
    assert _run(receipt_probe, tmp_path, receipt.encode_receipt(actual), 'match', (expected_path,)).returncode == 1


def _invocation(view):
    result = deepcopy(view)
    result.update(kind='I', role='gate', source=receipt.receipt_digest(view), acquisition='3' * 64)
    for node in result['nodes']:
        node['acquisition'] = 'retained'
        if node['kind'] in ('tree', 'link'): node['inode'] += 1000
    return result


def _omit(node):
    node['kind'] = 'empty-directory' if node['kind'] == 'directory' else 'absent'
    node.update(acquisition='none', sha256='-', label='-', link='-', mountpoint=0)
    for key in receipt.NODE_FIELDS[9:18]: node[key] = 0


@pytest.mark.parametrize('narrow', [False, True])
def test_invocation_keeps_original_sources_and_can_narrow(receipt_probe, source_view, tmp_path, narrow):
    view = source_view[0]
    # Only the retained vendor-helper class permits an original unlinked file.
    view['nodes'][2].update(source_class='vendor', role='vendor')
    invocation = _invocation(view)
    if narrow:
        _omit(invocation['nodes'][4])
        _omit(invocation['nodes'][5])
        invocation['coverage'] = []
    # Source-local ctime/link count can be freshly measured after host unlink;
    # source original inode, content and role remain invariant.
    invocation['nodes'][2]['ctime_ns'] += 1
    invocation['nodes'][2]['nlink'] = 0
    assert receipt.check_derivation(view, invocation) is invocation
    source = tmp_path / 'source'
    source.write_bytes(receipt.encode_receipt(view))
    result = _run(receipt_probe, tmp_path, receipt.encode_receipt(invocation), 'derive', (source,))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == receipt.receipt_digest(invocation)
    assert receipt.receipt_digest(invocation) != receipt.receipt_digest(view)


@pytest.mark.parametrize('field,value', [('size', 99), ('mode', stat.S_IFREG | 0o777),
                                        ('uid', 1), ('gid', 1), ('nlink', 0)])
def test_required_receipt_cannot_relax_copy_metadata(receipt_probe, source_view, tmp_path, field, value):
    view = source_view[0]
    invocation = _invocation(view)
    source = tmp_path / 'source'
    source.write_bytes(receipt.encode_receipt(view))
    invocation['nodes'][2][field] = value
    # Construct the negative wire independently of producer validation so both
    # native grammar and native derivation are reached for their owned checks.
    lines = receipt.encode_receipt(_invocation(view)).decode().splitlines()
    fields = lines[3].split('\t')
    fields[1 + receipt.NODE_FIELDS.index(field)] = str(value)
    lines[3] = '\t'.join(fields)
    with pytest.raises(ValueError):
        receipt.check_derivation(view, invocation)
    assert _run(receipt_probe, tmp_path, ('\n'.join(lines) + '\n').encode(),
                'derive', (source,)).returncode == 1


@pytest.mark.parametrize('required_alias', [False, True])
def test_recreated_link_has_fresh_independent_inode_and_original_text(
        receipt_probe, source_view, tmp_path, required_alias):
    view, tool, link, nested = source_view
    if required_alias:
        view['nodes'][-1].update(required=1, source_class='alias', role='data')
    original = link.lstat()
    invocation = _invocation(view)
    link.rename(tmp_path / 'original-link')
    link.symlink_to('share/ambient')
    replacement = link.lstat()
    assert replacement.st_ino != original.st_ino
    invocation['nodes'][-1].update(**_identity(replacement), nlink=replacement.st_nlink)
    assert invocation['nodes'][-1]['origin_inode'] == original.st_ino
    receipt.check_derivation(view, invocation)
    source = tmp_path / 'source'
    source.write_bytes(receipt.encode_receipt(view))
    data = receipt.encode_receipt(invocation)
    assert _run(receipt_probe, tmp_path, data, 'derive', (source,)).returncode == 0
    assert _run(receipt_probe, tmp_path, data, 'observe', (tool, link, nested)).returncode == 0


@pytest.mark.parametrize('fault', ['source', 'material', 'backend', 'index', 'class', 'origin', 'inode', 'role', 'link', 'coverage', 'revive'])
def test_invocation_cannot_mix_or_expand(receipt_probe, source_view, tmp_path, fault):
    view = source_view[0]
    invocation = _invocation(view)
    if fault == 'source': invocation['source'] = '4' * 64
    elif fault == 'material': invocation['material'] = '4' * 64
    elif fault == 'backend': invocation['backend'] = 'selinux'
    elif fault == 'index': invocation['nodes'][-1]['source_index'] += 1
    elif fault == 'class': invocation['nodes'][2].update(source_class='runtime', role='data')
    elif fault == 'origin': invocation['nodes'][2]['origin_inode'] += 1
    elif fault == 'inode': invocation['nodes'][2]['inode'] += 1
    elif fault == 'role': invocation['nodes'][2]['role'] = 'gate'
    elif fault == 'link': invocation['nodes'][-1]['link'] = 'foreign'
    elif fault == 'coverage': invocation['coverage'] = []
    else:
        _omit(view['nodes'][-1])
        invocation['source'] = receipt.receipt_digest(view)
    with pytest.raises(ValueError, match='receipt-derivation'):
        receipt.check_derivation(view, invocation)
    source = tmp_path / 'source'
    source.write_bytes(receipt.encode_receipt(view))
    assert _run(receipt_probe, tmp_path, receipt.encode_receipt(invocation), 'derive', (source,)).returncode == 1


def test_expired_shared_deadline_refuses(receipt_probe, source_view, tmp_path):
    assert _run(receipt_probe, tmp_path, receipt.encode_receipt(source_view[0]), 'expired').returncode == 1


@pytest.mark.parametrize('fault', ['extra-field', 'unknown-version', 'source-index', 'required-mask', 'unbounded-number', 'control'])
def test_producer_fails_closed(source_view, fault):
    view = source_view[0]
    if fault == 'extra-field': view['unexpected'] = 1
    elif fault == 'unknown-version': view['format'] = 3
    elif fault == 'source-index': view['nodes'][2]['source_index'] = 1
    elif fault == 'required-mask': _omit(view['nodes'][2])
    elif fault == 'unbounded-number': view['nodes'][2]['inode'] = 1 << 63
    else: view['nodes'][-1]['link'] = 'a\tb'
    with pytest.raises(ValueError): receipt.encode_receipt(view)
