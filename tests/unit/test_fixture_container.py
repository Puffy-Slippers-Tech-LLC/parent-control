"""Private descriptors and bounded waited Python children; no container work.

Each destructive descriptor-compaction check runs in a fresh child. The pytest
worker never changes its descriptor table beyond opening/closing its own files.
There are no VMs, services, displays, shared stores or external resources.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tools import fixture_container as container
from tools import fixture_producer, test_storage as storage


@pytest.fixture
def allocations(tmp_path):
    source, workspace = tmp_path / 'sources', tmp_path / 'build'
    source.mkdir()
    workspace.mkdir()
    (workspace / 'compiled').mkdir()
    (workspace / 'scratch').mkdir()
    return source, workspace


@pytest.mark.parametrize('target', ['ubuntu', 'fedora'])
@pytest.mark.parametrize('leases', [(), (3,), (3, 4, 5)])
def test_command_is_fixed_offline_target_build(allocations, target, leases):
    source, workspace = allocations
    invocation = container.command(source, workspace, target, 'a' * 64, leases)
    assert invocation[:8] == ['podman', 'run', '--rm', '--pull=never', '--network=none',
                              '--userns=keep-id', '--cap-drop=all',
                              '--preserve-fds=' + str(len(leases))]
    assert invocation[8:16] == ['--env', 'TMPDIR=/work/scratch', '--env',
        'PYTHONDONTWRITEBYTECODE=1', '--volume', f'{source}:/source:ro,Z',
        '--volume', f'{workspace}:/work:rw,Z']
    assert invocation[16:] == ['a' * 64, '/usr/bin/python3', '-I', '-S', '-B',
        '/source/tools/fixture_target_build.py', '--source', '/source', '--output',
        '/work/compiled', '--target', target,
        *[value for fd in leases for value in ('--lease-fd', str(fd))]]
    assert not any('runtime=' in argument for argument in invocation)


@pytest.mark.parametrize('fault', ['target', 'tag', 'prefix', 'sparse', 'bool', 'output',
                                  'same', 'relative', 'symlink', 'nonsibling'])
def test_command_rejects_unsafe_or_unbounded_inputs(allocations, tmp_path, fault):
    source, workspace = allocations
    target, image, leases = 'ubuntu', 'a' * 64, (3,)
    if fault == 'target': target = 'other'
    if fault == 'tag': image = 'fedora:44'
    if fault == 'prefix': image = 'sha256:' + image
    if fault == 'sparse': leases = (5,)
    if fault == 'bool': leases = (True,)
    if fault == 'output': (workspace / 'compiled/foreign').write_bytes(b'foreign')
    if fault == 'same': source = workspace
    if fault == 'relative': source = Path('sources')
    if fault == 'symlink':
        alias = tmp_path / 'source-alias'
        alias.symlink_to(source, target_is_directory=True)
        source = alias
    if fault == 'nonsibling':
        source = tmp_path / 'elsewhere/sources'
        source.mkdir(parents=True)
    with pytest.raises(ValueError):
        container.command(source, workspace, target, image, leases)


def _child(source, *arguments, pass_fds=()):
    return subprocess.run([sys.executable, '-I', '-S', '-B', '-c', source,
                           str(Path(container.__file__).resolve()), *map(str, arguments)],
                          pass_fds=pass_fds, check=True, capture_output=True,
                          text=True, timeout=15)


def test_compaction_handles_sparse_permuted_overlapping_fds_without_parent_changes(tmp_path):
    first, second = tmp_path / 'first', tmp_path / 'second'
    first.write_bytes(b'first')
    second.write_bytes(b'second')
    source = '''import importlib.util,json,os,sys
spec=importlib.util.spec_from_file_location('fixture_container',sys.argv[1])
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
first=os.open(sys.argv[2],os.O_RDONLY); second=os.open(sys.argv[3],os.O_RDONLY)
os.dup2(first,41); os.dup2(second,3)
before=[os.fstat(fd).st_ino for fd in (41,3)]
mapped=module.compact((41,3))
assert mapped==(3,4)
assert [os.fstat(fd).st_ino for fd in mapped]==before
assert all(os.get_inheritable(fd) for fd in mapped)
try: os.fstat(41)
except OSError: pass
else: raise AssertionError('sparse original survived')
print(json.dumps([os.read(fd,32).decode() for fd in mapped]))
'''
    with first.open('rb') as parent_file:
        before = os.fstat(parent_file.fileno())
        result = _child(source, first, second)
        assert os.fstat(parent_file.fileno()).st_ino == before.st_ino
        assert parent_file.read() == b'first'
    assert json.loads(result.stdout) == ['first', 'second']


@pytest.mark.parametrize('fault', ['duplicate', 'standard', 'pipe'])
def test_invalid_compaction_refuses_before_descriptor_mutation(tmp_path, fault):
    source = '''import importlib.util,os,sys
spec=importlib.util.spec_from_file_location('fixture_container',sys.argv[1])
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
fd=os.open(sys.argv[2],os.O_RDONLY); before=os.fstat(fd)
values=(fd,fd) if sys.argv[3]=='duplicate' else (0,) if sys.argv[3]=='standard' else (os.pipe()[0],)
try: module.compact(values)
except ValueError: pass
else: raise AssertionError('invalid descriptors accepted')
assert os.fstat(fd).st_ino==before.st_ino
print('refused')
'''
    path = tmp_path / 'lease'
    path.write_bytes(b'lease')
    assert _child(source, path, fault).stdout.strip() == 'refused'


def test_compacted_producer_lease_survives_exec_in_owned_child(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    root = tmp_path / 'output/test-runs/host/fixtures'
    root.mkdir(parents=True, mode=0o700)
    monkeypatch.setattr(storage, 'fixture_directory', lambda: root)
    store = fixture_producer.Store()
    source = '''import importlib.util,os,sys
spec=importlib.util.spec_from_file_location('fixture_container',sys.argv[1])
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
mapped=module.compact(tuple(map(int,sys.argv[2:])))
code='import os; print(chr(10).join(os.readlink("/proc/self/fd/"+str(fd)) for fd in '+repr(mapped)+'))'
os.execv(sys.executable,[sys.executable,'-I','-S','-B','-c',code])
'''
    with store.producer(transaction_id='b' * 32, compatibility_key='container-test',
                        build_key='private-lease'):
        leases = storage.scratch_descriptors()
        result = _child(source, *leases, pass_fds=leases)
        assert str(root / 'producer.lock') in result.stdout.splitlines()
    assert store.snapshot() is None
