"""Private producer lifetime, descendant leases and identity-safe exact recovery.

Resource review: pytest-private roots and tiny payloads only. Builder wrappers
run bounded Python children; a separate harness subreaps its exact recorded
descendant. Every child is waited. No VM, bus, display, service, shared cache or
compiler is used.
"""
import errno
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import textwrap

import pytest

from tools import fixture_producer, test_retention as retention, test_storage as storage


OPTIONS = dict(transaction_id='1' * 32, compatibility_key='native-test',
               build_key='build-one')


@pytest.fixture
def private_store(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    root = tmp_path / 'output' / 'test-runs' / 'host' / 'fixtures'
    root.mkdir(mode=0o700, parents=True)
    # Root-run unit tests still exercise actual ownership instead of spoofing uid.
    monkeypatch.setattr(storage, 'fixture_directory', lambda: root)
    return fixture_producer.Store()


def slot(store):
    return store.snapshot()['slot']


def test_reservation_and_empty_allocation_are_durable_before_payload(private_store):
    store = private_store
    with store.producer(**OPTIONS) as producer:
        reserved = slot(store)
        assert reserved['transaction_id'] == producer.transaction_id == OPTIONS['transaction_id']
        assert reserved['slot_id'] == producer.slot_id
        assert reserved['allocations'] == []
        assert reserved['bundle_id'] is None
        assert reserved['completion_sha256'] is None
        path = producer.allocate('staging')
        assert path == producer.allocate('staging')
        assert not list(path.iterdir())
        recorded = slot(store)['allocations']
        assert len(recorded) == 1
        claim = recorded[0]
        info = path.stat()
        assert claim['name'] == 'staging' and claim['path'] == str(path)
        assert (claim['device'], claim['inode'], claim['uid'], claim['mode']) == (
            info.st_dev, info.st_ino, info.st_uid, 0o700)
        assert claim['locator'] and claim['mount']
        (path / 'payload').write_bytes(b'finite staging payload')
        environment = producer.environment({'PRESERVED': 'yes'})
        assert environment['PRESERVED'] == 'yes'
        assert {environment[name] for name in ('TMPDIR', 'TMP', 'TEMP')} == {
            str(producer.allocate('scratch'))}
        producer.verifying()
        assert slot(store)['state'] == 'verifying'
    assert store.snapshot() is None
    assert not path.exists()


@pytest.mark.parametrize('transaction_id', ['1' * 32, '2' * 32])
def test_independent_reservation_refuses_even_the_same_transaction(private_store, transaction_id):
    with private_store.producer(**OPTIONS):
        before = private_store.snapshot()
        with pytest.raises((ValueError, BlockingIOError)):
            with fixture_producer.Store().producer(**{**OPTIONS, 'transaction_id': transaction_id}):
                pytest.fail('a second producer was admitted')
        assert private_store.snapshot() == before


@pytest.mark.parametrize('name', ['', '.', '..', '../escape', '/absolute', 'nested/name'])
def test_allocation_names_cannot_escape_registered_root(private_store, name):
    with private_store.producer(**OPTIONS) as producer:
        with pytest.raises(ValueError):
            producer.allocate(name)
        assert slot(private_store)['allocations'] == []


@pytest.mark.parametrize('failure', [KeyboardInterrupt, OSError])
def test_staging_cancellation_and_disk_full_clean_only_owned_payload(
        private_store, tmp_path, monkeypatch, failure):
    committed = tmp_path / 'committed-input'
    committed.mkdir()
    (committed / 'artifact-manifest.json').write_text('unrelated committed-like input')
    with pytest.raises(failure):
        with private_store.producer(**OPTIONS) as producer:
            staging = producer.allocate('staging')
            if failure is OSError:
                write = Path.write_bytes
                def disk_full(path, data):
                    if path == staging / 'partial':
                        write(path, data[:3])
                        raise OSError(errno.ENOSPC, 'injected disk-full payload write')
                    return write(path, data)
                monkeypatch.setattr(Path, 'write_bytes', disk_full)
            (staging / 'partial').write_bytes(b'partial')
            raise KeyboardInterrupt
    assert private_store.snapshot() is None
    assert not staging.exists()
    assert (committed / 'artifact-manifest.json').read_text() == 'unrelated committed-like input'


@pytest.mark.parametrize('import_spelling', ['package', 'standalone'])
def test_real_builder_wrappers_forward_producer_lease_to_grandchild(
        private_store, tmp_path, monkeypatch, import_spelling):
    from tools import build_test_artifacts
    store = private_store
    if import_spelling == 'standalone':
        import fixture_producer as alternate
        import test_storage as alternate_storage
        monkeypatch.setattr(alternate_storage, 'ROOT', tmp_path)
        monkeypatch.setattr(alternate_storage, 'fixture_directory', lambda: private_store.path)
        store = alternate.Store()
    grandchild = (
        'import json,os; print(json.dumps([os.readlink("/proc/self/fd/"+n) '
        'for n in os.listdir("/proc/self/fd") if os.path.exists("/proc/self/fd/"+n)]))')
    child = (
        'import sys; from pathlib import Path; from tools import test_storage; '
        'from tests.fixtures import build_test_applications as fixtures; '
        'test_storage.ROOT=Path(sys.argv[1]); '
        'fixtures._run([sys.executable,"-B","-c",sys.argv[2]])')
    with store.producer(**OPTIONS):
        result = build_test_artifacts._run(
            [sys.executable, '-B', '-c', child, str(tmp_path), grandchild])
        descriptors = json.loads(result.stdout)
        assert str(tmp_path / 'output/test-runs/host/fixtures/producer.lock') in descriptors


def test_surviving_inherited_child_keeps_exact_slot_until_waited_exit(private_store):
    child = None
    try:
        with pytest.raises(ValueError):
            with private_store.producer(**OPTIONS) as producer:
                staging = producer.allocate('staging')
                (staging / 'payload').write_bytes(b'keep while child lives')
                original_slot = producer.slot_id
                child = subprocess.Popen(
                    [sys.executable, '-B', '-c',
                     'import select,sys; print("ready",flush=True); '
                     'ready=select.select([sys.stdin],[],[],5)[0]; '
                     'sys.stdin.buffer.read(1) if ready else sys.exit(3)'],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    pass_fds=storage.scratch_descriptors())
                assert select.select([child.stdout], [], [], 5)[0], 'child did not become ready'
                assert child.stdout.readline() == b'ready\n'
        pending = private_store.snapshot()
        assert pending['slot']['slot_id'] == original_slot
        assert pending['slot']['intent'] is not None
        for _ in range(2):
            with pytest.raises((ValueError, BlockingIOError)):
                private_store.recover(OPTIONS['transaction_id'])
            assert private_store.snapshot() == pending
            assert (staging / 'payload').read_bytes() == b'keep while child lives'
        child.communicate(b'x', timeout=5)
        assert child.returncode == 0
        private_store.recover(OPTIONS['transaction_id'])
        assert private_store.snapshot() is None
        assert not staging.exists()
    finally:
        if child is not None:
            if child.poll() is None:
                child.terminate()
            child.communicate(timeout=5)


def pending_cleanup(store, monkeypatch, *, allocations=('staging',)):
    """Interrupt owned deletion, leaving its durable intent for exact recovery."""
    paths = []
    with monkeypatch.context() as fault:
        def interrupted_delete(*args, **kwargs):
            raise KeyboardInterrupt
        fault.setattr(retention, 'clear_tree', interrupted_delete)
        with pytest.raises(KeyboardInterrupt):
            with store.producer(**OPTIONS) as producer:
                for name in allocations:
                    path = producer.allocate(name)
                    (path / 'payload').write_text(name)
                    paths.append(path)
    assert slot(store)['intent'] is not None
    return paths


def test_interrupted_deletion_retries_exact_intent_without_slot_growth(private_store, monkeypatch):
    paths = pending_cleanup(private_store, monkeypatch)
    pending = private_store.snapshot()
    with pytest.raises(ValueError):
        private_store.recover('2' * 32)
    assert private_store.snapshot() == pending
    for _ in range(2):
        with monkeypatch.context() as fault:
            def interrupted_delete(*args, **kwargs):
                raise KeyboardInterrupt
            fault.setattr(retention, 'clear_tree', interrupted_delete)
            with pytest.raises(KeyboardInterrupt):
                private_store.recover(OPTIONS['transaction_id'])
        assert private_store.snapshot() == pending
        with pytest.raises(ValueError):
            with private_store.producer(**OPTIONS):
                pytest.fail('pending cleanup admitted a new generation')
        assert private_store.snapshot() == pending
    private_store.recover(OPTIONS['transaction_id'])
    assert private_store.snapshot() is None
    assert all(not path.exists() for path in paths)


@pytest.mark.parametrize('replacement', ['directory', 'symlink'])
def test_all_claims_are_validated_before_deletion_and_replacements_preserved(
        private_store, monkeypatch, tmp_path, replacement):
    first, second = pending_cleanup(private_store, monkeypatch, allocations=('scratch', 'staging'))
    original = second.with_name(second.name + '-original')
    second.rename(original)
    outside = tmp_path / 'unrelated'
    outside.mkdir()
    (outside / 'keep').write_text('outside payload')
    if replacement == 'directory':
        second.mkdir(mode=0o700)
        (second / 'keep').write_text('replacement payload')
    else:
        second.symlink_to(outside, target_is_directory=True)
    pending = private_store.snapshot()
    try:
        with pytest.raises((ValueError, OSError)):
            private_store.recover(OPTIONS['transaction_id'])
        assert private_store.snapshot() == pending
        assert (first / 'payload').read_text() == 'scratch'
        assert (original / 'payload').read_text() == 'staging'
        assert (outside / 'keep').read_text() == 'outside payload'
        if replacement == 'directory':
            assert (second / 'keep').read_text() == 'replacement payload'
        else:
            assert second.is_symlink()
    finally:
        # Restore only these pytest-owned replacements; production recovery
        # must never adopt either identity or discover the renamed original.
        if second.is_symlink():
            second.unlink()
        else:
            (second / 'keep').unlink()
            second.rmdir()
        original.rename(second)
    private_store.recover(OPTIONS['transaction_id'])
    assert private_store.snapshot() is None


def test_unknown_sibling_is_preserved_during_owned_cleanup(private_store, tmp_path):
    root = tmp_path / 'output/test-runs/host/fixtures'
    unknown = root / 'unknown-staging'
    unknown.mkdir(mode=0o700)
    (unknown / 'keep').write_text('not registered')
    with private_store.producer(**OPTIONS) as producer:
        staging = producer.allocate('staging')
        (staging / 'payload').write_text('owned')
    assert not staging.exists()
    assert (unknown / 'keep').read_text() == 'not registered'


def test_producer_preserves_active_evidence_run_and_journal(private_store, tmp_path):
    evidence = retention.Store(tmp_path / 'evidence')
    with evidence.session():
        token = os.environ[retention.VARIABLE]
        before = (evidence.path / 'current.json').read_bytes()
        with private_store.producer(**OPTIONS) as producer:
            (producer.allocate('staging') / 'payload').write_text('small')
            assert os.environ[retention.VARIABLE] == token
            assert (evidence.path / 'current.json').read_bytes() == before
        assert os.environ[retention.VARIABLE] == token
        assert (evidence.path / 'current.json').read_bytes() == before


@pytest.mark.parametrize('durable', [False, True])
def test_reservation_interruption_recovers_exact_slot_without_payload(private_store, monkeypatch, durable):
    original_save = retention.Store.save
    with monkeypatch.context() as fault:
        def interrupted_save(self, fd, record, **kwargs):
            if kwargs.get('name') == 'producer.json':
                if durable:
                    original_save(self, fd, record, **kwargs)
                raise KeyboardInterrupt
            return original_save(self, fd, record, **kwargs)
        fault.setattr(retention.Store, 'save', interrupted_save)
        with pytest.raises(KeyboardInterrupt):
            with private_store.producer(**OPTIONS):
                pytest.fail('producer returned before durable reservation')
    assert not list(private_store.path.glob('producer-*'))
    if durable:
        pending = private_store.snapshot()
        assert pending['slot']['allocations'] == []
        with pytest.raises(ValueError):
            with private_store.producer(**OPTIONS):
                pytest.fail('interrupted reservation admitted another slot')
        assert private_store.snapshot() == pending
        private_store.recover(OPTIONS['transaction_id'])
    assert private_store.snapshot() is None
    with private_store.producer(**OPTIONS) as producer:
        producer.allocate('staging')
    assert private_store.snapshot() is None


@pytest.mark.parametrize('replace', [False, True])
def test_disk_full_registration_never_deletes_unknown_replacement(
        private_store, monkeypatch, replace):
    original_save = retention.Store.save
    unknown = None
    displaced = None
    with monkeypatch.context() as fault:
        def disk_full(self, fd, record, **kwargs):
            nonlocal unknown, displaced
            if (kwargs.get('name') == 'producer.json'
                    and record['slot']['state'] == 'producing'):
                unknown = Path(record['slot']['allocations'][0]['path'])
                if replace:
                    displaced = unknown.with_name(unknown.name + '-original')
                    unknown.rename(displaced)
                    unknown.mkdir(mode=0o700)
                    (unknown / 'keep').write_text('unknown identity')
                raise OSError(errno.ENOSPC, 'injected allocation receipt failure')
            return original_save(self, fd, record, **kwargs)
        fault.setattr(retention.Store, 'save', disk_full)
        with pytest.raises((OSError, ValueError)):
            with private_store.producer(**OPTIONS) as producer:
                producer.allocate('staging')
                pytest.fail('unregistered allocation returned to caller')
    assert unknown is not None
    if replace:
        pending = private_store.snapshot()
        assert pending['slot']['intent'] is not None
        with pytest.raises(ValueError):
            private_store.recover(OPTIONS['transaction_id'])
        assert private_store.snapshot() == pending
        assert (unknown / 'keep').read_text() == 'unknown identity'
        assert displaced.is_dir() and not list(displaced.iterdir())
        # Only the test owner restores these known fault-injection paths.
        (unknown / 'keep').unlink()
        unknown.rmdir()
        displaced.rmdir()
        private_store.recover(OPTIONS['transaction_id'])
        assert private_store.snapshot() is None
    else:
        assert private_store.snapshot() is None
        assert not unknown.exists()


def test_partial_deletion_recovery_keeps_same_receipt_until_all_removed(private_store, monkeypatch):
    first, second = pending_cleanup(private_store, monkeypatch, allocations=('scratch', 'staging'))
    pending = private_store.snapshot()
    clear = retention.clear_tree
    with monkeypatch.context() as fault:
        def interrupt_second(fd, device):
            if os.fstat(fd).st_ino == second.stat().st_ino:
                raise KeyboardInterrupt
            return clear(fd, device)
        fault.setattr(retention, 'clear_tree', interrupt_second)
        with pytest.raises(KeyboardInterrupt):
            private_store.recover(OPTIONS['transaction_id'])
    assert not first.exists() and second.is_dir()
    assert private_store.snapshot() == pending
    private_store.recover(OPTIONS['transaction_id'])
    assert private_store.snapshot() is None
    assert not second.exists()


def test_interruption_after_durable_staging_receipt_cleans_registered_identity(private_store, monkeypatch):
    save = retention.Store.save
    registered = None
    with monkeypatch.context() as fault:
        def interrupted_registration(self, fd, record, **kwargs):
            nonlocal registered
            result = save(self, fd, record, **kwargs)
            if (kwargs.get('name') == 'producer.json'
                    and record['slot']['state'] == 'producing'):
                registered = Path(record['slot']['allocations'][0]['path'])
                assert registered.is_dir() and not list(registered.iterdir())
                raise KeyboardInterrupt
            return result
        fault.setattr(retention.Store, 'save', interrupted_registration)
        with pytest.raises(KeyboardInterrupt):
            with private_store.producer(**OPTIONS) as producer:
                producer.allocate('staging')
                pytest.fail('interrupted registration returned an allocation')
    assert registered is not None and not registered.exists()
    assert private_store.snapshot() is None


@pytest.mark.parametrize('target', ['root', 'lock'])
def test_replaced_root_or_lock_refuses_before_deleting_allocations(
        private_store, monkeypatch, tmp_path, target):
    [staging] = pending_cleanup(private_store, monkeypatch)
    root = tmp_path / 'output/test-runs/host/fixtures'
    path = root if target == 'root' else root / 'producer.lock'
    original = path.with_name(path.name + '-original')
    path.rename(original)
    if target == 'root':
        path.mkdir(mode=0o700)
        witness = path / 'keep'
    else:
        witness = path
    witness.write_text('unknown replacement')
    witness.chmod(0o600)
    try:
        with pytest.raises((ValueError, OSError)):
            private_store.recover(OPTIONS['transaction_id'])
        assert witness.read_text() == 'unknown replacement'
        owned = original / staging.relative_to(root) if target == 'root' else staging
        assert (owned / 'payload').read_text() == 'staging'
    finally:
        witness.unlink()
        if target == 'root':
            path.rmdir()
        original.rename(path)
    private_store.recover(OPTIONS['transaction_id'])
    assert private_store.snapshot() is None


def test_abrupt_parent_exit_keeps_slot_until_adopted_descendant_is_reaped(private_store, tmp_path):
    # Subreaping belongs only to this isolated harness, never the pytest worker.
    # It waits the exact PID reported by its producer parent, including on failure.
    parent_script = textwrap.dedent('''
        import json, os, subprocess, sys
        from pathlib import Path
        from tools import fixture_producer, test_storage as storage
        storage.ROOT = Path(sys.argv[1])
        storage.fixture_directory = lambda: storage.ROOT / 'output/test-runs/host/fixtures'
        store = fixture_producer.Store()
        with store.producer(transaction_id='1'*32, compatibility_key='native-test', build_key='build-one') as producer:
            staging = producer.allocate('staging')
            (staging / 'payload').write_text('parent exited; child still owns this')
            release = int(sys.argv[2])
            child = subprocess.Popen([sys.executable, '-B', '-c',
                'import os,select,sys; fd=int(sys.argv[1]); '
                'assert select.select([fd],[],[],10)[0]; assert os.read(fd,1)==b"x"',
                str(release)], pass_fds=(*storage.scratch_descriptors(), release),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(json.dumps({'pid': child.pid, 'slot': producer.slot_id, 'path': str(staging)}), flush=True)
            os._exit(0)
    ''')
    harness = textwrap.dedent('''
        import ctypes, json, os, select, signal, subprocess, sys
        from pathlib import Path
        from tools import fixture_producer, test_storage as storage
        assert ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) == 0
        storage.ROOT = Path(sys.argv[1])
        storage.fixture_directory = lambda: storage.ROOT / 'output/test-runs/host/fixtures'
        store = fixture_producer.Store()
        release_read, release_write = os.pipe()
        child_pid = None
        child_fd = None
        parent = None
        try:
            parent = subprocess.Popen([sys.executable, '-B', '-c', sys.argv[2],
                sys.argv[1], str(release_read)], pass_fds=(release_read,),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            assert select.select([parent.stdout], [], [], 5)[0], 'parent did not report its child'
            claim = json.loads(parent.stdout.readline())
            child_pid = claim['pid']
            child_fd = os.pidfd_open(child_pid)
            output, errors = parent.communicate(timeout=5)
            assert parent.returncode == 0 and not output, errors
            assert not select.select([child_fd], [], [], 0)[0], 'descendant already exited'
            pending = store.snapshot()
            assert pending['slot']['slot_id'] == claim['slot']
            assert Path(claim['path'], 'payload').read_text() == 'parent exited; child still owns this'
            for _ in range(2):
                try:
                    store.recover('1'*32)
                except ValueError as error:
                    assert 'active' in str(error)
                else:
                    raise AssertionError('orphan descendant lost its producer lease')
                assert store.snapshot() == pending
            os.write(release_write, b'x')
            assert select.select([child_fd], [], [], 5)[0], 'descendant did not exit'
            waited, status = os.waitpid(child_pid, 0)
            assert waited == child_pid and os.waitstatus_to_exitcode(status) == 0
            child_pid = None
            assert store.recover('1'*32)
            assert store.snapshot() is None and not Path(claim['path']).exists()
            print('parent-exit lifetime and exact cleanup passed')
        finally:
            os.close(release_read)
            os.close(release_write)
            if parent is not None:
                if parent.poll() is None:
                    parent.terminate()
                parent.communicate(timeout=5)
            if child_pid is not None:
                if not select.select([child_fd], [], [], 5)[0]:
                    signal.pidfd_send_signal(child_fd, signal.SIGKILL)
                os.waitpid(child_pid, 0)
            if child_fd is not None:
                os.close(child_fd)
    ''')
    process = subprocess.Popen([sys.executable, '-B', '-c', harness, str(tmp_path), parent_script],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        output, errors = process.communicate(timeout=25)
        assert process.returncode == 0, errors
        assert output.strip() == 'parent-exit lifetime and exact cleanup passed'
        assert private_store.snapshot() is None
    finally:
        if process.poll() is None:
            process.terminate()
        process.communicate(timeout=5)


def test_runtime_dependency_command_forwards_producer_lease(private_store, monkeypatch):
    from tests.fixtures import gui_runtime
    run = subprocess.run
    observed = []

    def dependency(command, **kwargs):
        assert command[0] == '/usr/bin/ldd'
        probe = ('import os,json; print(json.dumps([os.readlink("/proc/self/fd/"+n) '
                 'for n in os.listdir("/proc/self/fd") if os.path.exists("/proc/self/fd/"+n)]))')
        result = run([sys.executable, '-B', '-c', probe], **kwargs, timeout=5)
        observed.append(json.loads(result.stdout))
        return subprocess.CompletedProcess(command, 0, '/lib64/ld-linux-x86-64.so.2 (0x1234)\n', '')

    # Enumerate only synthetic runtime inputs; the command probe still crosses
    # a real exec boundary and inspects the descriptors actually inherited.
    monkeypatch.setattr(gui_runtime, 'tree_sources', lambda path: [])
    monkeypatch.setattr(gui_runtime.Path, 'is_dir', lambda path: True)
    monkeypatch.setattr(gui_runtime.Path, 'rglob', lambda path, pattern: [])
    monkeypatch.setattr(gui_runtime.subprocess, 'run', dependency)
    with private_store.producer(**OPTIONS):
        gui_runtime.build_runtime(Path('/unused'), inputs={})
        lease = str(private_store.path / 'producer.lock')
        assert observed and all(lease in descriptors for descriptors in observed)


def test_unregistered_empty_staging_is_preserved_and_blocks_new_generations(private_store, monkeypatch):
    created = None
    mkdir = os.mkdir
    original_slot = None
    with monkeypatch.context() as fault:
        def interrupted_mkdir(name, *args, **kwargs):
            nonlocal created
            result = mkdir(name, *args, **kwargs)
            if str(name).startswith('producer-'):
                created = private_store.path / name
                raise KeyboardInterrupt
            return result
        fault.setattr(os, 'mkdir', interrupted_mkdir)
        with pytest.raises(ValueError, match='unregistered'):
            with private_store.producer(**OPTIONS) as producer:
                original_slot = producer.slot_id
                producer.allocate('staging')
    pending = private_store.snapshot()
    assert pending['slot']['slot_id'] == original_slot
    assert pending['slot']['allocations'] == []
    assert created.is_dir() and not list(created.iterdir())
    for _ in range(2):
        with pytest.raises(ValueError, match='unregistered'):
            private_store.recover(OPTIONS['transaction_id'])
        with pytest.raises(ValueError):
            with private_store.producer(**{**OPTIONS, 'transaction_id': '2' * 32}):
                pytest.fail('another generation replaced an unknown allocation')
        assert private_store.snapshot() == pending
        assert list(private_store.path.glob('producer-*')) == [created]
    # The test owns this exact injected empty directory; recovery did not adopt it.
    created.rmdir()
    private_store.recover(OPTIONS['transaction_id'])
    assert private_store.snapshot() is None

