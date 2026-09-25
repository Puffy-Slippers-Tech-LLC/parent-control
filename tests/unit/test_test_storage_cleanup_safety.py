"""Storage relocation, bounded repetition, and owner-safe scratch recovery."""
import fcntl
import json
import os
from pathlib import Path
import tempfile
import sys
from types import SimpleNamespace

import pytest

from tools import test_retention as retention, test_storage as storage


def test_current_named_input_changes_with_product_bytes_without_overwriting(tmp_path, monkeypatch):
    from tools import package_inputs
    # Only private files and read-only hashing; no subprocess, allocation or cleanup.
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setattr(storage, 'BASE', tmp_path / 'outputs')
    monkeypatch.setattr(package_inputs, 'paths', lambda _: [Path('product.py')])
    source = tmp_path / 'product.py'
    source.write_text('first')
    first = storage.named_input(package_source=True)
    assert storage.named_input(package_source=True) == first
    assert not first.exists()
    source.write_text('second')
    assert storage.named_input(package_source=True) != first
    assert storage.named_input().name == 'onpc-parent-setup-input'
    source.unlink()
    source.symlink_to(tmp_path / 'missing')
    with pytest.raises(ValueError, match='regular file'):
        storage.named_input(package_source=True)


def test_storage_refuses_linked_parent_before_creating_outside(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    root = tmp_path / 'repo'
    root.mkdir()
    (root / 'output').symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        storage.directory(root=root)
    assert not list(outside.iterdir())


def test_repeated_failures_and_recovery_are_byte_and_count_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(retention, 'MAX_RETAINED_BYTES', 24 * 1024)
    store = retention.Store(tmp_path / 'state')
    for index in range(100):
        with store.session():
            path = Path(retention.allocate(tempfile.mkdtemp, dir=tmp_path))
            (path / 'evidence').write_bytes(b'x' * 8192)
            if index % 3 == 0:
                retention.preserve_for_recovery()
        if index % 3 == 0:
            store.reconcile(lambda: None)
        state = json.loads((store.path / 'current.json').read_text())
        entries = [*state['history'], state]
        assert len(entries) <= 3
        assert sum(retention.allocation_bytes(r) for _, r in
                   retention.latest_allocations(entries)) <= 24 * 1024
        assert len(list(tmp_path.iterdir())) <= 4
        assert len(list(store.path.glob('recovered-*.json'))) <= 3


def test_current_oversized_evidence_is_preserved_and_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(retention, 'MAX_RETAINED_BYTES', 4096)
    store = retention.Store(tmp_path / 'state')
    with pytest.raises(ValueError, match='storage budget'):
        with store.session():
            path = Path(retention.allocate(tempfile.mkdtemp, dir=tmp_path))
            (path / 'failure').write_bytes(b'x' * 8192)
    assert (path / 'failure').stat().st_size == 8192
    journal = (store.path / 'current.json').read_bytes()
    for _ in range(2):
        with pytest.raises(ValueError, match='storage budget'):
            with store.session():
                pytest.fail('oversized evidence did not block new work')
        assert (path / 'failure').stat().st_size == 8192
        assert (store.path / 'current.json').read_bytes() == journal
    # An explicit evidence cleanup releases the refusal without changing limits.
    (path / 'failure').unlink()
    with store.session():
        pass


def test_scratch_recovery_preserves_locked_owner_and_reclaims_idle(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setattr(storage, '_scratch', None)
    monkeypatch.setattr(storage, '_scratch_fd', None)
    first = storage.scratch_directory()
    first_fd = storage._scratch_fd
    (first / 'keep').write_text('active')
    monkeypatch.setattr(storage, '_scratch', None)
    monkeypatch.setattr(storage, '_scratch_fd', None)
    second = storage.scratch_directory()
    assert (first / 'keep').read_text() == 'active'
    fcntl.flock(first_fd, fcntl.LOCK_UN)
    monkeypatch.setattr(storage, '_scratch', None)
    monkeypatch.setattr(storage, '_scratch_fd', None)
    third = storage.scratch_directory()
    assert not first.exists()
    assert second.is_dir() and third.is_dir()


@pytest.mark.parametrize('boundary', ['directory', 'staging-receipt', 'owner',
                                     'identity', 'payload', 'publication'])
def test_scratch_initialization_interruption_is_retryable(tmp_path, monkeypatch, boundary):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setattr(storage, '_scratch', None)
    monkeypatch.setattr(storage, '_scratch_fd', None)
    with monkeypatch.context() as fault:
        mkdir, open_fd, rename, dump = os.mkdir, os.open, os.rename, json.dump

        def interrupted_mkdir(name, *args, **kwargs):
            result = mkdir(name, *args, **kwargs)
            if (boundary, name) in (('directory', 'initializing'), ('payload', 'tmp')):
                raise KeyboardInterrupt
            return result

        def interrupted_open(name, *args, **kwargs):
            if boundary == 'owner' and name == 'owner':
                raise KeyboardInterrupt
            return open_fd(name, *args, **kwargs)

        def interrupted_dump(record, stream, **kwargs):
            if ((boundary == 'staging-receipt' and record['path'].endswith('/initializing'))
                    or (boundary == 'identity' and '/run-' in record['path'])):
                stream.write('{"path":')
                raise KeyboardInterrupt
            return dump(record, stream, **kwargs)

        def interrupted_rename(source, *args, **kwargs):
            result = rename(source, *args, **kwargs)
            if boundary == 'publication' and source == 'initializing':
                raise KeyboardInterrupt
            return result

        fault.setattr(os, 'mkdir', interrupted_mkdir)
        fault.setattr(os, 'open', interrupted_open)
        fault.setattr(os, 'rename', interrupted_rename)
        fault.setattr(json, 'dump', interrupted_dump)
        with pytest.raises(KeyboardInterrupt):
            storage.scratch_directory()
    recovered = storage.scratch_directory()
    assert recovered.is_dir()
    assert sorted(p.name for p in recovered.parent.parent.iterdir()) == ['gate', recovered.parent.name]


@pytest.mark.parametrize('fault', ['unrecorded', 'replacement', 'symlink'])
def test_scratch_staging_never_adopts_unknown_payload(tmp_path, monkeypatch, fault):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setattr(storage, '_scratch', None)
    monkeypatch.setattr(storage, '_scratch_fd', None)
    parent = storage.directory('scratch')
    staging = parent / 'initializing'
    staging.mkdir(mode=0o700)
    (staging / 'keep').write_text('unrelated')
    if fault == 'replacement':
        info = staging.stat()
        record = dict(path=str(staging), device=info.st_dev, inode=info.st_ino + 1, mode=0o700)
        with retention.Store(parent).opened() as fd:
            retention.Store(parent).save(fd, record, name='initializing.json')
    elif fault == 'symlink':
        staging.rename(parent / 'outside')
        staging.symlink_to(parent / 'outside', target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        storage.scratch_directory()
    assert (staging / 'keep').read_text() == 'unrelated'


def test_interrupted_scratch_reclamation_keeps_external_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setattr(storage, '_scratch', None)
    monkeypatch.setattr(storage, '_scratch_fd', None)
    first = storage.scratch_directory()
    fcntl.flock(storage._scratch_fd, fcntl.LOCK_UN)
    monkeypatch.setattr(storage, '_scratch', None)
    monkeypatch.setattr(storage, '_scratch_fd', None)
    with monkeypatch.context() as fault:
        def partial_delete(fd, device):
            os.unlink('owner', dir_fd=fd)
            raise KeyboardInterrupt
        fault.setattr(retention, 'clear_tree', partial_delete)
        with pytest.raises(KeyboardInterrupt):
            storage.scratch_directory()
    second = storage.scratch_directory()
    assert second.is_dir() and not first.exists()
    assert not (second.parent.parent / 'reclaiming.json').exists()


def test_build_children_forward_inherited_scratch_leases(tmp_path, monkeypatch):
    from tools import build_test_artifacts
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setattr(storage, '_scratch', None)
    monkeypatch.setattr(storage, '_scratch_fd', None)
    scratch = storage.scratch_directory()
    # The fixture builder starts in a fresh interpreter, with no cached scratch
    # globals. Both subprocess wrappers must forward the original owner lock.
    grandchild = ('import json, os; print(json.dumps(['
                 'os.readlink("/proc/self/fd/" + n) for n in os.listdir("/proc/self/fd") '
                 'if os.path.exists("/proc/self/fd/" + n)]))')
    child = ('import sys; from pathlib import Path; '
             'from tools import test_storage; '
             'from tests.fixtures import build_test_applications as fixtures; '
             'test_storage.ROOT = Path(sys.argv[1]); '
             'assert test_storage._scratch_fd is None; '
             'fixtures._run([sys.executable, "-B", "-c", sys.argv[2]])')
    result = build_test_artifacts._run([sys.executable, '-B', '-c', child,
                                       str(tmp_path), grandchild])
    assert str(scratch.parent / 'owner') in json.loads(result.stdout)


@pytest.mark.parametrize('module_name', ['check_graphical_transport',
                                       'check_graphical_attachment', 'check_graphical_worker'])
def test_diagnostic_failure_evidence_outlives_dispatcher_scratch(tmp_path, monkeypatch, module_name):
    import importlib
    from unittest.mock import Mock
    diagnostic = importlib.import_module(module_name)
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setattr(storage, '_scratch', None)
    monkeypatch.setattr(storage, '_scratch_fd', None)
    scratch = storage.scratch_directory()
    monkeypatch.setattr(tempfile, 'tempdir', str(scratch))
    monkeypatch.setattr(diagnostic, 'os', SimpleNamespace(
        geteuid=lambda: 0, getegid=lambda: 0, umask=lambda _: None))
    monkeypatch.setattr(sys, 'argv', ['check'])
    if module_name == 'check_graphical_transport':
        monkeypatch.setattr(diagnostic, 'probe', lambda _: {'outcome': 'failed'})
        monkeypatch.setattr(diagnostic, 'receive_probe', lambda *_: {'outcome': 'failed'})
        monkeypatch.setattr(diagnostic, 'importlib', SimpleNamespace(import_module=lambda _: None))
    elif module_name == 'check_graphical_attachment':
        monkeypatch.setattr(diagnostic.runner, 'host_fingerprint',
                            Mock(side_effect=RuntimeError('injected preparation failure')))
        monkeypatch.setattr(diagnostic.signal, 'signal', Mock())
    else:
        monkeypatch.setattr(diagnostic, 'attempt', Mock(side_effect=RuntimeError('injected failure')))
    store = retention.Store(tmp_path / 'journal')
    with store.session():
        assert diagnostic.main() == 1
    state = json.loads((store.path / 'current.json').read_text())
    record, = state['paths']
    evidence = Path(record['path']) / 'result.json'
    assert evidence.is_file()
    fcntl.flock(storage._scratch_fd, fcntl.LOCK_UN)
    monkeypatch.setattr(storage, '_scratch', None)
    monkeypatch.setattr(storage, '_scratch_fd', None)
    storage.scratch_directory()
    assert evidence.is_file() and not scratch.exists()
    for _ in range(2):
        with store.session():
            pass
        assert evidence.is_file()
    with store.session():
        pass
    assert not evidence.exists()


@pytest.mark.parametrize('parent', [None, '/tmp', Path('/tmp'), '/var/tmp', Path('/var/tmp')])
def test_allocator_redirects_bulk_tmp_outputs(tmp_path, monkeypatch, parent):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    with retention.Store(tmp_path / 'state').session():
        path = Path(retention.allocate(tempfile.mkdtemp, prefix='onpc-test-artifacts-', dir=parent))
        assert path.parent == tmp_path / 'output/test-runs/host/allocations'
        assert path.stat().st_mode & 0o777 == 0o700


def test_repair_transcript_compaction_keeps_tail_and_writer_position(tmp_path, monkeypatch):
    import detached_launcher
    monkeypatch.setattr(detached_launcher, 'MAX_LOG_BYTES', 512)
    path = tmp_path / 'output'
    with path.open('wb') as writer:
        writer.write(b'old line\n' * 100 + b'latest result\n')
        writer.flush()
        detached_launcher.compact_log(path, writer_fd=writer.fileno())
        writer.write(b'next result\n')
    assert path.stat().st_size < 512
    assert path.read_bytes().endswith(b'latest result\nnext result\n')
    assert b'Earlier transcript expired' in path.read_bytes()
