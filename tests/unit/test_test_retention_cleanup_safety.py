"""Bounded repetition and refusal of foreign, active or recovery-owned storage."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import fcntl
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import stat
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest

from tools import test_retention as retention


class SimulatedFailure(ValueError):
    """Distinguish the fixture's failure from a retention error."""


class SimulatedInterrupt(KeyboardInterrupt):
    """Distinguish the fixture's interrupt from a real test-run interruption."""


def allocated(parent, name):
    path = parent / name
    path.mkdir(mode=0o700)
    (path / 'test.log').write_bytes(b'evidence' * 128)
    retention.retain(path)
    return path


def advance_to_expiry(store):
    for _ in range(2):
        with store.session():
            pass


@pytest.mark.parametrize('fault', [None, 'active', 'guard', 'replaced', 'marker-link'])
def test_idle_reconciliation_preserves_evidence_and_refuses_unsafe_recovery(tmp_path, fault):
    store = retention.Store(tmp_path / 'state')
    with store.session() as run:
        evidence = allocated(tmp_path, 'evidence')
        retention.preserve_for_recovery()
    original = (store.path / 'current.json').read_bytes()
    marker = store.path / 'recovery-required'
    if fault == 'replaced':
        evidence.rename(tmp_path / 'original')
        evidence.mkdir(mode=0o700)
    if fault == 'marker-link':
        marker.rename(tmp_path / 'marker')
        marker.symlink_to(tmp_path / 'marker')
    def guard():
        if fault == 'guard':
            raise ValueError('VM recovery refused')
    if fault == 'active':
        with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False):
            with pytest.raises(ValueError, match='another owner'):
                store.reconcile(guard)
    elif fault:
        with pytest.raises(ValueError):
            store.reconcile(guard)
    else:
        assert store.reconcile(guard)
        assert not store.reconcile(guard)
        assert (store.path / f'recovered-{run}.json').read_bytes() == original
        assert not marker.exists()
        assert json.loads((store.path / 'current.json').read_text())['finished']
        assert (evidence / 'test.log').exists()
        # Recovered allocations still participate in bounded normal retention.
        advance_to_expiry(store)
        with store.session():
            pass
        assert not evidence.exists()
    if fault:
        assert (store.path / 'current.json').read_bytes() == original
        assert marker.exists()
        assert evidence.exists()


@pytest.fixture
def dispatcher_vm(monkeypatch):
    """Keep VM selection process-local while exercising real argument parsing."""
    import vm_config
    name = 'fixture-vm'
    def select(selected, path):
        assert selected == name
        return SimpleNamespace(name=name)
    monkeypatch.setattr(vm_config, 'select', select)
    return name


@pytest.mark.parametrize('status', [0, 1])
@pytest.mark.parametrize('selected', ['check_test_recovery', 'check_retained_runs_cleanup'])
def test_unattended_recovery_does_not_launch_tests(tmp_path, monkeypatch, capsys, status, dispatcher_vm, selected):
    import test_storage
    monkeypatch.setattr(test_storage, 'privileged_state', lambda uid: tmp_path / 'privileged-state')
    dispatcher = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'tools/onpc-test-runner'))
    dispatcher['run'].__globals__['selection'] = lambda *args: ['recovery']
    commands = []
    def execute(command, **kwargs):
        output = capsys.readouterr().out
        assert 'cleanup prerequisites' not in output
        assert command == ['recovery']
        assert kwargs['env']['ONPC_TEST_VM'] == dispatcher_vm
        commands.append(command)
        return status
    control = SimpleNamespace(run=execute, installed=lambda **kw: nullcontext(control))
    monkeypatch.setattr(dispatcher['runpy'], 'run_path', lambda path: {
        'Control': lambda: control, 'safety_command': lambda root: ['safety']})
    dispatcher['run'].__globals__['confined_file'] = lambda *args: tmp_path / 'control'
    monkeypatch.setattr(dispatcher['os'], 'getgrouplist', lambda *args: [])
    caller = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name='fixture',
                             pw_dir=str(tmp_path))
    assert dispatcher['run'](tmp_path, [
        '--unattended', 'integration', selected, '--vm', dispatcher_vm,
    ], caller) == status
    assert commands == [['recovery']]


def test_direct_discard_dispatch_does_not_enter_retention(tmp_path, monkeypatch, dispatcher_vm):
    import test_storage
    import test_retention
    dispatcher = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'tools/onpc-test-runner'))
    dispatcher['run'].__globals__['selection'] = lambda *args: ['discard']
    monkeypatch.setattr(test_storage, 'privileged_state', lambda uid: tmp_path / 'state')
    monkeypatch.setattr(test_retention.Store, 'session',
                        lambda *args, **kwargs: pytest.fail('cleanup entered retention rotation'))
    calls = []
    def execute(command, **kwargs):
        calls.append(command)
        assert kwargs['env']['ONPC_TEST_VM'] == dispatcher_vm
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(dispatcher['subprocess'], 'run', execute)
    caller = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name='fixture', pw_dir=str(tmp_path))
    assert dispatcher['run'](tmp_path, ['integration', 'check_retained_runs_cleanup',
                                      '--vm', dispatcher_vm], caller) == 0
    assert calls == [['discard']]


def test_explicit_discard_reclaims_oversized_finished_run_and_history(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        old = allocated(tmp_path, 'old')
    with store.session():
        current = allocated(tmp_path, 'current')
    unknown = tmp_path / 'unknown'
    unknown.mkdir()
    (unknown / 'keep').write_text('unregistered')
    original = (store.path / 'current.json').read_bytes()
    monkeypatch.setattr(retention, 'MAX_RETAINED_BYTES', 1)
    with pytest.raises(ValueError, match='exceeds 4 GiB'):
        with store.session():
            pytest.fail('oversized result accepted')
    # Normal pruning may retire history before reporting the current refusal.
    journal = (store.path / 'current.json').read_bytes()
    guards = []
    assert store.discard_completed(lambda paths: guards.append(paths)) == 1
    assert guards == [{str(current)}]
    assert not current.exists() and not old.exists()
    assert (store.path / 'current.json').read_bytes() == journal
    assert (unknown / 'keep').read_text() == 'unregistered'
    assert store.discard_completed(lambda paths: None) == 1
    with store.session():
        pass
    assert original != journal


@pytest.mark.parametrize('fault', ['unfinished', 'marked', 'active', 'replaced', 'symlink', 'mount', 'live'])
def test_explicit_discard_audits_every_allocation_before_deletion(tmp_path, monkeypatch, fault):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        first = allocated(tmp_path, 'first')
        second = allocated(tmp_path, 'second')
        if fault == 'unfinished':
            retention.preserve_for_recovery()
    if fault == 'unfinished':
        (store.path / 'recovery-required').unlink()
    if fault == 'marked':
        (store.path / 'recovery-required').touch(mode=0o600)
    if fault in ('replaced', 'symlink'):
        second.rename(tmp_path / 'original')
        if fault == 'symlink':
            second.symlink_to(tmp_path / 'original', target_is_directory=True)
        else:
            second.mkdir(mode=0o700)
            (second / 'keep').write_text('foreign')
    if fault == 'mount':
        original_mount = retention.mount_id
        monkeypatch.setattr(retention, 'mount_id', lambda fd:
                            'foreign' if Path(os.readlink(f'/proc/self/fd/{fd}')) == second else original_mount(fd))
    journal = (store.path / 'current.json').read_bytes()
    def guard(paths):
        if fault == 'live':
            raise ValueError('live reference')
    if fault == 'active':
        with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False):
            with pytest.raises(ValueError, match='another owner'):
                store.discard_completed(guard)
    else:
        with pytest.raises((ValueError, OSError)):
            store.discard_completed(guard)
    assert (first / 'test.log').exists()
    assert second.exists()
    assert (store.path / 'current.json').read_bytes() == journal


def test_explicit_discard_retries_partial_deletion_and_uses_latest_registration(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        recreated = allocated(tmp_path, 'recreated')
        first = allocated(tmp_path, 'first')
    recreated.rename(tmp_path / 'original')
    with store.session():
        recreated = allocated(tmp_path, 'recreated')
        last = allocated(tmp_path, 'last')
    journal = (store.path / 'current.json').read_bytes()
    remove = retention.remove
    def interrupted(record, *, validate_only=False):
        if record['path'] == str(last) and not validate_only:
            raise OSError('interrupted deletion')
        return remove(record, validate_only=validate_only)
    monkeypatch.setattr(retention, 'remove', interrupted)
    with pytest.raises(OSError, match='interrupted deletion'):
        store.discard_completed(lambda paths: None)
    assert not recreated.exists() and not first.exists()
    assert last.exists() and (tmp_path / 'original/test.log').exists()
    assert (store.path / 'current.json').read_bytes() == journal
    monkeypatch.setattr(retention, 'remove', remove)
    assert store.discard_completed(lambda paths: None) == 3
    assert not last.exists()
    assert (store.path / 'current.json').read_bytes() == journal


@pytest.mark.parametrize('failed', [False, True])
def test_discard_keeps_vm_and_compatibility_leases_through_removal(tmp_path, monkeypatch, failed):
    import prepare_baseline as baseline
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    directory = tmp_path / 'named-vm'
    directory.mkdir(mode=0o700)
    monkeypatch.setattr(baseline, 'BASELINES', directory)
    monkeypatch.setattr(baseline.guest_contract.vm_config, 'STATE_ROOT', tmp_path)
    (directory / 'phase.json').write_text('{"phase":"finalized"}')
    (directory / 'phase.json').chmod(0o600)
    store = retention.Store(tmp_path / 'state')
    with store.session():
        evidence = allocated(tmp_path, 'evidence')
    def guarded(paths):
        for path in (directory / '.lock', tmp_path / '.lock'):
            with path.open('rb') as lock:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if failed:
            raise ValueError('guard refused')
    try:
        with dispatcher['retention_lease'](root):
            store.discard_completed(guarded)
    except ValueError as error:
        assert failed and str(error) == 'guard refused'
    assert evidence.exists() == failed
    for path in (directory / '.lock', tmp_path / '.lock'):
        with path.open('rb') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


@pytest.mark.parametrize('failed', [False, True])
def test_privileged_discard_preserves_evidence_when_recovery_fails(tmp_path, monkeypatch, failed):
    import check_retained_runs_cleanup as cleanup
    calls = []
    def recover(root):
        calls.append('recover')
        if failed:
            raise ValueError('recovery failed')
    monkeypatch.setattr(cleanup.check_test_recovery, 'reconcile_vm', recover)
    lease = Mock(return_value=nullcontext())
    monkeypatch.setattr(cleanup.runpy, 'run_path', lambda path: {'retention_lease': lease})
    monkeypatch.setattr(cleanup.os, 'geteuid', lambda: 0)
    monkeypatch.setenv('PKEXEC_UID', '1000')
    monkeypatch.setattr(cleanup.sys, 'argv', ['check_retained_runs_cleanup'])
    monkeypatch.setattr(cleanup, 'ROOT', Path.cwd())
    monkeypatch.setattr(cleanup, 'privileged_state', lambda uid: tmp_path / 'selected-state')
    discard = Mock()
    monkeypatch.setattr(cleanup.test_retention, 'Store', lambda path: SimpleNamespace(discard_completed=discard))
    if failed:
        with pytest.raises(ValueError, match='recovery failed'):
            cleanup.main()
        lease.assert_not_called()
        discard.assert_not_called()
    else:
        assert cleanup.main() == 0
        lease.assert_called_once_with(Path.cwd())
        discard.assert_called_once_with(cleanup.unused)
    assert calls == ['recover']


def test_host_discard_leaves_vm_and_workflow_stores_untouched(tmp_path, monkeypatch):
    import cleanup_e2e
    import test_retention
    from contextlib import contextmanager
    host = test_retention.Store(tmp_path / 'host')
    workflow = test_retention.Store(tmp_path / 'workflow')
    vm = test_retention.Store(tmp_path / 'vm')
    for store in (host, workflow, vm):
        with store.session():
            allocated(tmp_path, store.path.name + '-result')
    @contextmanager
    def activity(root, **kwargs):
        assert kwargs == {'host_only': True}
        yield
    monkeypatch.setattr(cleanup_e2e.test_activity, 'activity', activity)
    monkeypatch.setattr(cleanup_e2e.test_activity, 'retention_path', lambda root: host.path)
    monkeypatch.setattr(cleanup_e2e, 'cleanup_host', lambda root: 0)
    monkeypatch.setattr(cleanup_e2e, 'cleanup', lambda root: pytest.fail('host touched VM'))
    assert cleanup_e2e.main(['--host-only', '--discard-completed']) == 0
    assert not (tmp_path / 'host-result').exists()
    assert (tmp_path / 'workflow-result').exists() and (tmp_path / 'vm-result').exists()


def test_recovery_safety_uses_shared_parallel_cleanup_coordinator():
    import regression_process
    root = Path(__file__).resolve().parents[2]
    command = regression_process.safety_command(root)
    assert command == ['/usr/bin/python3', '-IB', str(root / 'tools/regression_process.py'),
                       '--cleanup-prerequisites']


def test_idle_reconciliation_retries_after_marker_archive_and_failed_commit(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    with store.session() as run:
        evidence = allocated(tmp_path, 'evidence')
        retention.preserve_for_recovery()
    save = store.save
    def failed_commit(fd, value, *, name='current.json'):
        if name == 'current.json':
            raise OSError('simulated commit failure')
        save(fd, value, name=name)
    monkeypatch.setattr(store, 'save', failed_commit)
    with pytest.raises(OSError, match='commit failure'):
        store.reconcile(lambda: None)
    archived = (store.path / f'recovered-{run}.json').read_bytes()
    assert not json.loads((store.path / 'current.json').read_text())['finished']
    monkeypatch.setattr(store, 'save', save)
    assert store.reconcile(lambda: None)
    assert (store.path / f'recovered-{run}.json').read_bytes() == archived
    assert (evidence / 'test.log').exists()


@pytest.mark.parametrize('failed', [False, True])
def test_launcher_reconciles_only_idle_pending_storage(tmp_path, monkeypatch, failed):
    import test_recovery
    import test_retention as live_retention
    import regression_process
    import vm_config
    import vm_selection
    # Model one selected VM, independent of the enclosing launcher's selection
    # and host/batch activity. Keep all journals in this test's private root.
    vm = SimpleNamespace(name='fixture-vm')
    def load(name):
        assert name == vm.name
        return vm
    monkeypatch.setattr(vm_config, 'load', load)
    monkeypatch.setenv(vm_config.VARIABLE, vm.name)
    monkeypatch.delenv(vm_selection.BATCH, raising=False)
    monkeypatch.setattr(test_recovery.test_activity, '_host_only', False)
    monkeypatch.setattr(test_recovery.test_activity, 'descriptors', lambda: (123,))
    store = live_retention.Store(test_recovery.test_activity.retention_path(tmp_path))
    with store.session():
        live_retention.preserve_for_recovery()
    original = (store.path / 'current.json').read_bytes()
    calls = []
    def recover(root, category, args, **kwargs):
        calls.append((category, args))
        return int(failed)
    monkeypatch.setattr(regression_process, 'category_run', recover)
    if failed:
        with pytest.raises(ValueError, match='automatic recovery failed'):
            test_recovery.before_run(tmp_path, ['integration', 'check_test_recovery'])
        assert (store.path / 'recovery-required').exists()
        assert (store.path / 'current.json').read_bytes() == original
    else:
        test_recovery.before_run(tmp_path, ['integration', 'check_test_recovery'])
        test_recovery.before_run(tmp_path, ['unit', 'selected'])
        assert not (store.path / 'recovery-required').exists()
        assert json.loads((store.path / 'current.json').read_text())['finished']
    assert calls == [('integration', ['check_test_recovery', '--vm', vm.name])]


def test_execution_option_does_not_bypass_required_recovery(tmp_path, monkeypatch):
    import test_recovery
    monkeypatch.setattr(test_recovery.test_activity, 'descriptors', lambda: (123,))
    cleanup = Mock(return_value=0)
    monkeypatch.setattr(test_recovery, 'cleanup', cleanup)
    assert test_recovery.before_run(
        tmp_path, ['--stop-on-error', 'integration', 'check_test_recovery'],
        categories=['integration']) == 0
    cleanup.assert_called_once_with(tmp_path)


@pytest.mark.parametrize('fault', [None, 'busy', 'recovery-failed'])
def test_automatic_vm_recovery_keeps_guard_refusals(tmp_path, monkeypatch, fault):
    import check_test_recovery as recovery
    calls = []
    def guard(root):
        calls.append('guard')
        if fault == 'busy':
            raise BlockingIOError('lease is held')
        if calls == ['guard']:
            raise ValueError('retention: VM recovery is unfinished; preserve evidence')
    monkeypatch.setattr(recovery.runpy, 'run_path', lambda path: {'retention_guard': guard})
    def finish(**kwargs):
        assert kwargs == {'graphics_type': None, 'maintenance': True}
        calls.append('recover')
        return int(fault == 'recovery-failed')
    monkeypatch.setattr(recovery.check_graphical_recovery, 'main', finish)
    if fault:
        with pytest.raises((ValueError, BlockingIOError)):
            recovery.reconcile_vm(tmp_path)
    else:
        recovery.reconcile_vm(tmp_path)
    assert calls == (['guard'] if fault == 'busy' else
                     ['guard', 'recover'] if fault else ['guard', 'recover', 'guard'])


@pytest.mark.parametrize('argv', [[], ['--help'], ['system', '--list'], ['unit', 'selected'],
                                  ['host'], ['host-builds']])
def test_clean_host_or_listing_does_not_request_recovery(tmp_path, monkeypatch, argv):
    import test_recovery
    import regression_process
    monkeypatch.setattr(test_recovery.test_activity, 'descriptors', lambda: (123,))
    monkeypatch.setattr(regression_process, 'category_run',
                        lambda *args, **kwargs: pytest.fail('unnecessary recovery'))
    assert test_recovery.before_run(tmp_path, argv) == 0


@pytest.mark.parametrize('category', ['unit', 'ui', 'host', 'host-builds'])
def test_host_leaves_pending_vm_recovery_untouched(tmp_path, monkeypatch, category):
    import test_recovery
    import test_retention as live_retention
    monkeypatch.setattr(test_recovery.test_activity, 'descriptors', lambda: (123,))
    store = live_retention.Store(tmp_path / 'output/test-runs/host/state/retention')
    with store.session():
        live_retention.preserve_for_recovery()
    original = (store.path / 'current.json').read_bytes()
    monkeypatch.setattr(test_recovery, 'cleanup',
                        lambda *_: pytest.fail('host attempted VM recovery'))
    assert test_recovery.before_run(tmp_path, [category]) == 0
    assert (store.path / 'current.json').read_bytes() == original
    assert (store.path / 'recovery-required').exists()


@pytest.mark.parametrize('fault', [None, 'active', 'replaced', 'activity'])
def test_host_startup_recovers_only_idle_verified_evidence(tmp_path, monkeypatch, fault):
    import test_activity
    import test_recovery
    import test_retention as live_retention
    import test_storage
    import regression_process
    monkeypatch.delenv(test_activity.VARIABLE, raising=False)
    monkeypatch.setattr(test_activity, '_descriptor', None)
    monkeypatch.setattr(regression_process, 'category_run',
                        lambda *_args, **_kwargs: pytest.fail('host accessed VM recovery'))
    store = live_retention.Store(test_storage.directory('state', root=tmp_path) / 'retention-host')
    with store.session() as run:
        evidence = tmp_path / 'evidence'
        evidence.mkdir(mode=0o700)
        live_retention.retain(evidence)
        (evidence / 'test.log').write_text('interrupted evidence')
        live_retention.preserve_for_recovery()
    original = (store.path / 'current.json').read_bytes()
    if fault == 'replaced':
        evidence.rename(tmp_path / 'original')
        evidence.mkdir(mode=0o700)
    with test_activity.activity(tmp_path, host_only=True):
        def start():
            return test_recovery.before_run(tmp_path, ['--stop-on-error', 'unit'], categories=['unit'])
        if fault == 'active':
            with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False):
                with pytest.raises(ValueError, match='another owner'):
                    start()
        elif fault == 'activity':
            descriptor = test_activity._descriptor
            monkeypatch.setattr(test_activity, '_descriptor', None)
            with pytest.raises(ValueError, match='another test launcher'):
                test_recovery.cleanup_host(tmp_path)
            monkeypatch.setattr(test_activity, '_descriptor', descriptor)
        elif fault:
            with pytest.raises(ValueError, match='replaced'):
                start()
        else:
            assert start() == 0
            assert start() == 0
            assert (store.path / f'recovered-{run}.json').read_bytes() == original
            assert (evidence / 'test.log').read_text() == 'interrupted evidence'
            with store.session():
                pass
    if fault:
        assert (store.path / 'current.json').read_bytes() == original
        assert (store.path / 'recovery-required').exists()
        assert evidence.exists()


@pytest.fixture
def repetition_tree():
    # Only the bounded repetition workload uses /tmp (tmpfs on the host).
    # Keep real filesystem calls; disk-backed sync/error checks use tmp_path.
    with tempfile.TemporaryDirectory(prefix='onpc-retention-stress-', dir='/tmp') as root:
        yield Path(root)


@pytest.mark.parametrize('outcome', ['pass', 'failure', 'interrupt'])
def test_one_hundred_runs_have_constant_retained_size(repetition_tree, outcome):
    store = retention.Store(repetition_tree / 'state')
    foreign = repetition_tree / 'onpc-unregistered'
    foreign.mkdir()
    (foreign / 'keep').write_text('not owned by this runner')
    sizes = []
    previous = []
    for number in range(100):
        try:
            with store.session():
                if len(previous) == 3:
                    assert all(not path.exists() for path in previous.pop(0))
                assert all(path.exists() for group in previous for path in group)
                previous.append([allocated(repetition_tree, f'run-{number}-{kind}')
                                 for kind in ('report', 'build-a', 'build-b', 'ui', 'vm')])
                # Producers may independently discard passing render output.
                disposable = allocated(repetition_tree, f'render-{number}')
                # Fail before another iteration if a regression grows this
                # shared-filesystem footprint. Includes journals and sentinels.
                entries = list(repetition_tree.rglob('*'))
                assert len(entries) < 64
                assert sum(p.stat().st_size for p in entries if p.is_file()) < 256 * 1024
                shutil.rmtree(disposable)
                if outcome == 'failure':
                    raise SimulatedFailure('assertion failed')
                if outcome == 'interrupt':
                    raise SimulatedInterrupt
        except (SimulatedFailure, SimulatedInterrupt):
            if outcome == 'pass':
                raise
        sizes.append(sum(p.stat().st_size for group in previous for path in group for p in path.iterdir()))
        assert len(list(repetition_tree.glob('run-*'))) == 5 * min(number + 1, 3)
        assert (foreign / 'keep').read_text() == 'not owned by this runner'
    assert len(set(sizes[2:])) == 1
    state = json.loads((store.path / 'current.json').read_text())
    assert len(state['paths']) == 6
    assert len(state['history']) == 2
    assert all(len(entry['paths']) == 6 for entry in state['history'])


def test_same_run_keeps_all_vm_categories_until_fourth_run(tmp_path):
    store = retention.Store(tmp_path / 'state')
    run = uuid.uuid4().hex
    for index in range(4):
        with store.session(run=run):
            allocated(tmp_path, f'category-{index}')
            assert len(list(tmp_path.glob('category-*'))) == index + 1
    advance_to_expiry(store)
    assert len(list(tmp_path.glob('category-*'))) == 4
    with store.session():
        assert not list(tmp_path.glob('category-*'))


def test_active_owner_is_not_rotated(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'active')
        with pytest.raises(ValueError, match='another owner'):
            with retention.Store(store.path).session():
                pytest.fail('competing owner admitted')
        assert path.exists()


def test_parallel_writers_do_not_lose_allocations(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        with ThreadPoolExecutor(max_workers=4) as pool:
            paths = list(pool.map(lambda number: allocated(tmp_path, f'worker-{number}'), range(30)))
    advance_to_expiry(store)
    with store.session():
        assert all(not path.exists() for path in paths)


@pytest.mark.parametrize('kind', ['symlink', 'directory'])
def test_replaced_allocation_is_preserved_and_refused(tmp_path, kind):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'owned')
    path.rename(tmp_path / 'original')
    if kind == 'symlink':
        path.symlink_to(tmp_path / 'original', target_is_directory=True)
    else:
        path.mkdir(mode=0o700)
        (path / 'keep').write_text('replacement')
    with pytest.raises((ValueError, OSError)):
        with store.session():
            pytest.fail('replaced allocation accepted')
    assert (tmp_path / 'original/test.log').exists()
    assert path.exists()


@pytest.mark.parametrize('same_run', [False, True])
def test_recreated_registered_output_expires_with_its_latest_owner(tmp_path, same_run):
    store = retention.Store(tmp_path / 'state')
    with store.session() as first:
        path = allocated(tmp_path, 'named-output')
    # Keep the old inode allocated so the fixture cannot accidentally reuse it.
    original = tmp_path / 'original'
    path.rename(original)
    with store.session(run=first if same_run else None):
        retention.allocate(lambda: path.mkdir(mode=0o700) or str(path))
        (path / 'test.log').write_text('new output')
    journal = json.loads((store.path / 'current.json').read_text())
    records = [record for entry in [*journal['history'], journal]
               for record in entry['paths'] if record['path'] == str(path)]
    assert len(records) == 2
    assert records[0]['inode'] != records[1]['inode']
    assert not retention.legacy_system_evidence(journal)
    # Expiring the old owner must neither reject nor delete the new allocation.
    advance_to_expiry(store)
    assert (path / 'test.log').read_text() == 'new output'
    with store.session():
        assert not path.exists()
    assert (original / 'test.log').exists()


@pytest.mark.parametrize('fault', [None, 'unregistered', 'old-identity', 'symlink', 'mode'])
def test_recreated_output_recovery_still_checks_latest_identity(tmp_path, fault):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'named-output')
    original = tmp_path / 'original'
    path.rename(original)
    with store.session():
        retention.allocate(lambda: path.mkdir(mode=0o700) or str(path))
        (path / 'test.log').write_text('new output')
        retention.preserve_for_recovery()
    journal = store.path / 'current.json'
    before = journal.read_bytes()
    if fault in ('unregistered', 'old-identity', 'symlink'):
        path.rename(tmp_path / 'new-output')
        if fault == 'unregistered':
            path.mkdir(mode=0o700)
        elif fault == 'old-identity':
            original.rename(path)
        else:
            path.symlink_to(tmp_path / 'new-output', target_is_directory=True)
    elif fault == 'mode':
        path.chmod(0o755)
    if fault:
        with pytest.raises((ValueError, OSError)):
            store.reconcile(lambda: None)
        assert journal.read_bytes() == before
        assert (store.path / 'recovery-required').exists()
    else:
        assert store.reconcile(lambda: None)
        assert (path / 'test.log').read_text() == 'new output'
        advance_to_expiry(store)
        assert path.exists()
        with store.session():
            assert not path.exists()


def test_nested_symlink_never_deletes_its_target(tmp_path):
    store = retention.Store(tmp_path / 'state')
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'keep').write_text('foreign')
    with store.session():
        path = allocated(tmp_path, 'owned')
        (path / 'link').symlink_to(outside, target_is_directory=True)
        os.link(outside / 'keep', path / 'hardlink')
    advance_to_expiry(store)
    with store.session():
        assert not path.exists()
        assert (outside / 'keep').read_text() == 'foreign'


def test_unfinished_journal_stops_repetition_before_allocating(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'recovery')
    journal = store.path / 'current.json'
    state = json.loads(journal.read_text())
    state['finished'] = False
    journal.write_text(json.dumps(state))
    for _ in range(5):
        with pytest.raises(ValueError, match='previous owner did not finish'):
            with store.session():
                pytest.fail('unfinished owner bypassed')
        assert path.exists()
    assert len(list(tmp_path.iterdir())) == 2


def test_successful_recovery_returns_entire_journal_to_bounded_rotation(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        older = allocated(tmp_path, 'older')
    with store.session():
        interrupted = allocated(tmp_path, 'interrupted')
    journal = store.path / 'current.json'
    state = json.loads(journal.read_text())
    state['finished'] = False
    journal.write_text(json.dumps(state))
    for _ in range(5):
        with store.session(recover=lambda candidate: candidate == state):
            pass
    archived = store.path / f'interrupted-{state["run"]}.json'
    assert not archived.exists()
    assert not older.exists() and not interrupted.exists()


def test_recovery_callback_cannot_override_cleanup_failure(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'unsafe')
        retention.preserve_for_recovery()
    with pytest.raises(ValueError, match='previous owner did not finish'):
        with store.session(recover=lambda _: pytest.fail('cleanup marker bypassed')):
            pass
    assert path.exists()
    assert not list(store.path.glob('interrupted-*.json'))


def test_failed_recovery_guard_never_rotates_or_marks_finished(tmp_path):
    store = retention.Store(tmp_path / 'state')
    def refuse():
        raise ValueError('recovery unfinished')
    with store.session():
        path = allocated(tmp_path, 'old')
    with pytest.raises(ValueError, match='recovery unfinished'):
        with store.session(guard=refuse):
            pytest.fail('recovery guard bypassed')
    assert path.exists()
    calls = []
    def fail_on_exit():
        calls.append(1)
        if len(calls) == 2:
            refuse()
    with pytest.raises(ValueError, match='recovery unfinished'):
        with store.session(guard=fail_on_exit):
            allocated(tmp_path, 'new')
    assert not json.loads((store.path / 'current.json').read_text())['finished']


def test_fixture_cleanup_failure_pins_evidence_after_controller_exit(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'unsafe-fixture')
        retention.preserve_for_recovery()
    with pytest.raises(ValueError, match='previous owner did not finish'):
        with store.session():
            pytest.fail('unproven fixture cleanup bypassed')
    assert path.exists()


def test_allocation_registers_before_unmasking_interrupts(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    calls = []
    original = retention.retain
    def registered(path, **options):
        calls.append('register')
        return original(path, **options)
    def mask(action, signals):
        calls.append('block' if action == retention.signal.SIG_BLOCK else 'restore')
        return set()
    monkeypatch.setattr(retention, 'retain', registered)
    monkeypatch.setattr(retention.signal, 'pthread_sigmask', mask)
    with store.session():
        result = retention.allocate(tempfile.mkdtemp, prefix='allocation-', dir=tmp_path)
        assert calls == ['block', 'register', 'restore']
    advance_to_expiry(store)
    with store.session():
        assert not Path(result).exists()


def test_registration_failure_removes_only_the_new_empty_allocation(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    def broken(path, **options):
        raise OSError('journal unavailable')
    with store.session():
        monkeypatch.setattr(retention, 'retain', broken)
        with pytest.raises(OSError, match='journal unavailable'):
            retention.allocate(tempfile.mkdtemp, prefix='allocation-', dir=tmp_path)
        assert not list(tmp_path.glob('allocation-*'))


@pytest.mark.parametrize('fault', [None, 'file-sync', 'replace', 'directory-sync'])
def test_registration_syncs_before_return_and_preserves_evidence_on_io_failure(tmp_path, monkeypatch,
                                                                             fault):
    # Use the launcher's ordinary disk-backed tmp_path for the durability
    # protocol. All operations remain real except the one injected I/O failure.
    store = retention.Store(tmp_path / 'state')
    calls, created = [], []
    real_sync, real_replace = os.fsync, os.replace

    def factory(**options):
        path = tempfile.mkdtemp(**options)
        created.append(path)
        return path

    def sync(fd):
        stage = 'directory-sync' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'file-sync'
        calls.append(stage)
        if stage == 'file-sync':
            # The bytes must already have left Python's buffer before fsync.
            pending = json.loads((store.path / 'current.tmp').read_text())
            assert {record['path'] for record in pending['paths']} == {str(existing), created[0]}
        if fault == stage:
            raise OSError('injected ' + stage)
        real_sync(fd)

    def replace(*args, **options):
        calls.append('replace')
        if fault == 'replace':
            raise OSError('injected replace')
        real_replace(*args, **options)

    with store.session():
        existing = allocated(tmp_path, 'existing-evidence')
        original = json.loads((store.path / 'current.json').read_text())
        with monkeypatch.context() as patch:
            patch.setattr(os, 'fsync', sync)
            patch.setattr(os, 'replace', replace)
            expectation = pytest.raises(OSError, match='injected ' + fault) if fault else nullcontext()
            with expectation:
                result = retention.allocate(factory, prefix='allocation-', dir=tmp_path)
                calls.append('returned')
        order = ['file-sync', 'replace', 'directory-sync', 'returned']
        assert calls == (order[:order.index(fault) + 1] if fault else order)
        assert len(created) == 1
        assert Path(created[0]).exists() is (fault is None)
        if fault is None:
            assert result == created[0]
        saved = json.loads((store.path / 'current.json').read_text())
        assert saved['paths'][0] == original['paths'][0]
        assert (existing / 'test.log').read_bytes() == b'evidence' * 128
        if fault in ('file-sync', 'replace'):
            assert saved == original
        else:
            # Directory-sync failure can expose the replaced journal; it must
            # still raise, remove only the fresh empty tree and retain evidence.
            assert {record['path'] for record in saved['paths']} == {str(existing), created[0]}


def test_sbuild_traversable_scratch_is_registered_and_rotated(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = Path(retention.allocate(tempfile.mkdtemp, dir=tmp_path, mode=0o711))
        assert path.stat().st_mode & 0o777 == 0o711
        (path / 'early-failure').mkdir()
    advance_to_expiry(store)
    with store.session():
        assert not path.exists()


@pytest.mark.parametrize('fault', [None, 'identity', 'mode', 'mount', 'namespace'])
def test_sbuild_namespace_requires_valid_record_and_preserves_failed_rotation(
        tmp_path, monkeypatch, fault):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = Path(retention.allocate(tempfile.mkdtemp, dir=tmp_path, mode=0o711))
        (path / 'evidence').write_text('keep')
    advance_to_expiry(store)
    journal = store.path / 'current.json'
    original = journal.read_bytes()
    if fault == 'identity':
        path.rename(tmp_path / 'original')
        path.mkdir(mode=0o711)
    elif fault == 'mode':
        path.chmod(0o700)
    elif fault == 'mount':
        mount_id = retention.mount_id
        monkeypatch.setattr(retention, 'mount_id', lambda fd:
                            'mounted' if os.fstat(fd).st_ino == path.stat().st_ino else mount_id(fd))
    monkeypatch.setattr(retention, 'sbuild_scratch', lambda record: True)
    calls = []
    def namespace(record, *, validate_only):
        calls.append(validate_only)
        assert record['path'] == str(path)
        assert len(retention._locks) == 2
        if fault == 'namespace':
            raise ValueError('namespace failed')
        # Emulate only the namespace boundary; keep real identity/tree checks.
        with monkeypatch.context() as patch:
            patch.setattr(retention, 'sbuild_scratch', lambda record: False)
            retention.remove(record, validate_only=validate_only)
    monkeypatch.setattr(retention, 'namespace_remove', namespace)
    if fault:
        with pytest.raises(ValueError):
            with store.session():
                pytest.fail('unsafe scratch accepted')
        assert journal.read_bytes() == original
        assert path.exists()
        assert calls == ([True] if fault == 'namespace' else [])
    else:
        with store.session():
            assert not path.exists()
        assert calls == [True, False]


@pytest.mark.parametrize('path,mode,expected', [
    ('/var/tmp/onpc-sbuild-scratch-example', 0o711, True),
    ('/var/tmp/onpc-sbuild-scratch-example', 0o700, False),
    ('/tmp/onpc-sbuild-scratch-example', 0o711, False),
    ('/var/tmp/other', 0o711, False),
    ('/var/tmp/onpc-sbuild-scratch-example/child', 0o711, False),
])
def test_only_registered_sbuild_parent_uses_namespace(path, mode, expected):
    assert retention.sbuild_scratch(dict(path=path, mode=mode)) is expected


@pytest.mark.parametrize('inspect,status', [(True, 0), (False, 0), (True, 1), (False, 'timeout')])
def test_namespace_command_inherits_leases_without_host_privilege(
        tmp_path, monkeypatch, inspect, status):
    record = dict(path='/var/tmp/onpc-sbuild-scratch-test', mode=0o711, device=1, inode=2)
    store = retention.Store(tmp_path / 'state')
    def execute(command, **kwargs):
        assert command[:7] == ['/usr/bin/unshare', '--user', '--map-users=subids',
                               '--map-groups=subids', '--map-root-user', '--', '/usr/bin/python3']
        assert command[7:9] == ['-I', '-B']
        assert command[-2:] == ['--sbuild-retention', 'inspect' if inspect else 'remove']
        assert json.loads(kwargs['input']) == record
        assert kwargs['cwd'] == '/'
        assert kwargs['env'] == {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'}
        assert set(kwargs['pass_fds']) == retention._locks
        assert retention._locks
        for fd in kwargs['pass_fds']:
            os.fstat(fd)
        if status == 'timeout':
            raise retention.subprocess.TimeoutExpired(command, 300)
        return SimpleNamespace(returncode=status)
    monkeypatch.setattr(retention.subprocess, 'run', execute)
    with store.session():
        with pytest.raises(ValueError, match='namespace operation') if status else nullcontext():
            retention.namespace_remove(record, validate_only=inspect)
    assert not retention._locks


@pytest.mark.parametrize('fault', [None, 'host-root', 'ordinary-user', 'path', 'operation'])
@pytest.mark.parametrize('operation', ['inspect', 'remove'])
def test_namespace_worker_refuses_unmapped_root_and_out_of_scope_records(
        monkeypatch, fault, operation):
    record = dict(path='/var/tmp/onpc-sbuild-scratch-example', mode=0o711, device=1, inode=2)
    if fault == 'path':
        record['path'] = '/var/tmp/unregistered'
    args = ['--sbuild-retention', operation if fault != 'operation' else 'chmod']
    monkeypatch.setattr(retention.os, 'geteuid', lambda: 1000 if fault == 'ordinary-user' else 0)
    read = Path.read_text
    monkeypatch.setattr(Path, 'read_text', lambda path, *a, **kw:
                        ('0 0 4294967295\n' if fault == 'host-root' else
                         '0 1000 1\n100000 100000 65536\n')
                        if str(path) == '/proc/self/uid_map' else read(path, *a, **kw))
    monkeypatch.setattr(retention.sys, 'stdin', io.StringIO(json.dumps(record)))
    calls = []
    monkeypatch.setattr(retention, 'remove', lambda value, **kw: calls.append((value, kw)))
    if fault:
        with pytest.raises(ValueError):
            retention.namespace_main(args)
        assert not calls
    else:
        retention.namespace_main(args)
        assert calls == [(record, {'validate_only': operation == 'inspect'})]


def test_inaccessible_sbuild_scratch_stops_growth(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with pytest.raises(PermissionError):
        with store.session():
            evidence = allocated(tmp_path, 'build-evidence')
            path = Path(retention.allocate(tempfile.mkdtemp, dir=tmp_path, mode=0o711))
            child = path / 'unproven-chroot-cleanup'
            child.mkdir(mode=0)
    try:
        for _ in range(3):
            with pytest.raises(PermissionError):
                with store.session():
                    pytest.fail('unproven chroot cleanup admitted another run')
            assert child.exists()
            assert (evidence / 'test.log').exists()
    finally:
        child.chmod(0o700)


def test_journal_hardlink_is_rejected_before_truncation(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        pass
    outside = tmp_path / 'keep'
    outside.write_text('original data')
    outside.chmod(0o600)
    os.link(outside, store.path / 'current.tmp')
    with pytest.raises(ValueError, match='unsafe ownership'):
        with store.session():
            pytest.fail('hardlinked journal accepted')
    assert outside.read_text() == 'original data'


def test_symlink_storage_parent_does_not_create_external_directories(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    (tmp_path / 'link').symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        with retention.Store(tmp_path / 'link/new').session():
            pytest.fail('symlink storage accepted')
    assert not list(outside.iterdir())


def test_mount_boundary_is_refused(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'owned')
    original = os.stat
    def changed(name, *args, **kwargs):
        value = original(name, *args, **kwargs)
        if name == 'test.log':
            return SimpleNamespace(st_dev=value.st_dev + 1)
        return value
    monkeypatch.setattr(retention.os, 'stat', changed)
    with pytest.raises(ValueError, match='mounted storage'):
        with store.session():
            pytest.fail('mount accepted')
    assert (path / 'test.log').exists()


@pytest.mark.parametrize('nested', [False, True])
def test_same_device_bind_mount_is_refused(tmp_path, monkeypatch, nested):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'owned')
        mounted = path / 'mounted' if nested else path
        mounted.mkdir(exist_ok=True)
        (mounted / 'keep').write_text('mounted data')
    original = retention.mount_id
    def changed(fd):
        return 'foreign-mount' if Path(os.readlink(f'/proc/self/fd/{fd}')) == mounted else original(fd)
    monkeypatch.setattr(retention, 'mount_id', changed)
    with pytest.raises(ValueError, match='mounted storage'):
        with store.session():
            pytest.fail('bind mount accepted')
    assert (mounted / 'keep').read_text() == 'mounted data'


def test_root_replacement_during_deletion_never_erases_replacement(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'owned')
    advance_to_expiry(store)
    clear = retention.clear_tree
    def replaced(fd, device):
        path.rename(tmp_path / 'original')
        path.mkdir(mode=0o700)
        (path / 'keep').write_text('replacement')
        clear(fd, device)
    monkeypatch.setattr(retention, 'clear_tree', replaced)
    with pytest.raises(ValueError, match='changed during cleanup'):
        with store.session():
            pytest.fail('replacement accepted')
    assert (path / 'keep').read_text() == 'replacement'


def test_dispatcher_groups_privileged_categories_by_aggregate(tmp_path, monkeypatch, dispatcher_vm):
    import test_storage
    monkeypatch.setattr(test_storage, 'privileged_state', lambda uid: tmp_path / 'root-state')
    import test_retention as dispatcher_retention
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    run = dispatcher['run']
    run.__globals__['retention_guard'] = lambda root: None
    run.__globals__['selection'] = lambda root, argv: ['selected-controller']
    caller = SimpleNamespace(pw_uid=os.geteuid(), pw_gid=os.getegid(),
                             pw_name='fixture', pw_dir=str(tmp_path))
    monkeypatch.setattr(dispatcher['os'], 'getgrouplist', lambda *args: [])
    store = dispatcher_retention.Store(tmp_path / 'root-state')
    monkeypatch.setattr(dispatcher_retention, 'Store', lambda path: store)
    owned = []
    def execute(command, **kwargs):
        if command == ['selected-controller']:
            assert kwargs['env']['ONPC_TEST_VM'] == dispatcher_vm
            assert kwargs['env'][retention.VARIABLE] == os.environ[retention.VARIABLE]
            owned.append(allocated(tmp_path, f'vm-{len(owned)}'))
        return 0
    control = SimpleNamespace(run=execute, installed=lambda **kw: nullcontext(control))
    monkeypatch.setattr(dispatcher['runpy'], 'run_path', lambda path: {
        'Control': lambda: control, 'safety_command': lambda root: ['safety']})
    first = uuid.uuid4().hex
    for category in ('system', 'e2e'):
        assert run(root, [f'--retention-run={first}', '--unattended', category,
                          '--vm', dispatcher_vm], caller) == 0
    assert all(path.exists() for path in owned)
    for _ in range(2):
        assert run(root, [f'--retention-run={uuid.uuid4().hex}', '--unattended', 'system',
                          '--vm', dispatcher_vm], caller) == 0
        assert all(path.exists() for path in owned)
    assert run(root, [f'--retention-run={uuid.uuid4().hex}', '--unattended', 'system',
                      '--vm', dispatcher_vm], caller) == 0
    assert not any(path.exists() for path in owned[:2])
    assert all(path.exists() for path in owned[2:])


def test_original_single_run_journal_upgrades_without_losing_evidence(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'original')
    journal = store.path / 'current.json'
    state = json.loads(journal.read_text())
    del state['history']
    journal.write_text(json.dumps(state))
    advance_to_expiry(store)
    assert path.exists()
    with store.session():
        assert not path.exists()


@pytest.mark.parametrize('fault', [None, 'identity', 'mode', 'unfinished', 'foreign'])
def test_legacy_system_export_is_preserved_only_after_identity_audit(tmp_path, fault):
    store = retention.Store(tmp_path / 'state')
    with tempfile.TemporaryDirectory(prefix='onpc-system-', dir='/tmp') as name:
        path = Path(name)
        with store.session() as old_run:
            retention.retain(path)
            (path / 'result.log').write_text('retained evidence')
            if fault == 'foreign':
                foreign = allocated(tmp_path, 'foreign')
        journal = store.path / 'current.json'
        old = json.loads(journal.read_text())
        path.chmod(0o755)
        if fault == 'identity':
            old['paths'][0]['inode'] += 1
        elif fault == 'mode':
            path.chmod(0o777)
        elif fault == 'unfinished':
            old['finished'] = False
        elif fault == 'foreign':
            foreign.chmod(0o755)
        journal.write_text(json.dumps(old))
        if fault:
            with pytest.raises(ValueError):
                with store.session(preserve_completed=retention.legacy_system_evidence):
                    pytest.fail('unsafe legacy journal accepted')
            assert json.loads(journal.read_text()) == old
        else:
            for _ in range(4):
                with pytest.raises(ValueError, match='explicit storage migration'):
                    with store.session(preserve_completed=retention.legacy_system_evidence):
                        pytest.fail('unbounded legacy archive accepted')
                assert json.loads(journal.read_text()) == old
                assert not list(store.path.glob('preserved-*.json'))
        assert (path / 'result.log').read_text() == 'retained evidence'


def test_older_vm_token_cannot_resume_after_a_newer_run(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session() as run:
        path = allocated(tmp_path, 'old-vm')
    with store.session():
        current = allocated(tmp_path, 'current-vm')
    with pytest.raises(ValueError, match='older run cannot resume'):
        with store.session(run=run):
            pytest.fail('older run resumed')
    assert path.exists() and current.exists()


def test_shell_review_copies_rotate_with_their_aggregate(tmp_path):
    namespace = runpy.run_path(str(Path(__file__).resolve().parents[2] /
                                  'tests/ui/test_child_shell_lifecycle.py'))
    preserve = namespace['_preserve_attempt_artifacts']
    preserve.__globals__['ARTIFACTS'] = tmp_path / 'review'
    source = tmp_path / 'shell-runtime'
    source.mkdir()
    log = source / 'lifecycle-events.log'
    store = retention.Store(tmp_path / 'state')
    copies = []
    for index in range(4):
        log.write_text(f'run {index}')
        with store.session():
            # The real producer allocates a unique runtime for each attempt.
            current = tmp_path / f'onpc-child-lifecycle-{index}'
            shutil.copytree(source, current)
            copies.append(preserve(current, 'lifecycle'))
        assert all(path.exists() for path in copies[-3:])
    assert not copies[0].exists()
    assert [(path / log.name).read_text() for path in copies[1:]] == ['run 1', 'run 2', 'run 3']


@pytest.mark.parametrize('phase', ['complete', 'running', 'cleanup-requested'])
def test_privileged_guard_reads_the_shared_recovery_journal(tmp_path, monkeypatch, phase):
    import prepare_baseline as baseline
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    monkeypatch.setattr(baseline, 'BASELINES', tmp_path)
    for name, content in (('.lock', ''), ('phase.json', '{"phase":"finalized"}'),
                          ('system-run.json', json.dumps({'phase': phase}))):
        path = tmp_path / name
        path.write_text(content)
        path.chmod(0o600)
    if phase == 'complete':
        dispatcher['retention_guard'](root)
    else:
        with pytest.raises(ValueError, match='recovery is unfinished'):
            dispatcher['retention_guard'](root)


def test_privileged_guard_uses_shared_named_baseline_lease(tmp_path, monkeypatch):
    import prepare_baseline as baseline
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    directory = tmp_path / 'named-vm'
    directory.mkdir(mode=0o700)
    monkeypatch.setattr(baseline, 'BASELINES', directory)
    monkeypatch.setattr(baseline.guest_contract.vm_config, 'STATE_ROOT', tmp_path)
    for name, content in (('phase.json', '{"phase":"finalized"}'),
                          ('system-run.json', '{"phase":"complete"}')):
        path = directory / name
        path.write_text(content)
        path.chmod(0o600)
    lock_path = tmp_path / '.lock'
    lock_path.touch(mode=0o600)
    # Completed journals do not authorize retention while this VM is leased
    # or an older controller holds the legacy root lease exclusively.
    dispatcher['retention_guard'](root)
    vm_lock_path = directory / '.lock'
    assert vm_lock_path.is_file()
    for busy_path in (vm_lock_path, lock_path):
        with busy_path.open('rb') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with pytest.raises(BlockingIOError):
                dispatcher['retention_guard'](root)
        dispatcher['retention_guard'](root)

    # A newer controller for another VM shares the compatibility lease and
    # owns only its own exclusive lease, so it must not block this VM.
    other_directory = tmp_path / 'other-vm'
    other_directory.mkdir(mode=0o700)
    other_lock_path = other_directory / '.lock'
    other_lock_path.touch(mode=0o600)
    with lock_path.open('rb') as legacy, other_lock_path.open('rb') as other:
        fcntl.flock(legacy.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        fcntl.flock(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        dispatcher['retention_guard'](root)

    # Success and refusal must both release every descriptor they acquired.
    for released_path in (vm_lock_path, lock_path):
        with released_path.open('rb') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    dispatcher['retention_guard'](root)


@pytest.mark.parametrize('value', ['../outside', '', 'a' * 31, 'g' * 32])
def test_privileged_run_token_cannot_supply_paths(value):
    dispatcher = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'tools/onpc-test-runner'))
    with pytest.raises(ValueError, match='invalid-retention-run'):
        dispatcher['run'](Path('/missing'), ['--retention-run=' + value, '--unattended'], None)
