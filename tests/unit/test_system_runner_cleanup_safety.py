"""Run in isolation before any live system runner: all process/VM calls mocked."""
from tests.support.vm_registry import vm_name

import signal
import stat
import os
import json
import subprocess
import sys
from unittest.mock import Mock, patch

import pytest

import system_runner as runner
from tests.support.vm_baseline import local_preparation_source, rig
from tests.support.vm_runner import lease_rig


@pytest.fixture
def retained_history(monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    import kiosk_entry
    events = []
    owner = 'b' * 32
    handle = {'owner': owner, 'intent': [1, 42, 'digest']}
    proof = {'boot': 'original', 'unit': 'original', 'view': {'inode': 42}}
    state = SimpleNamespace(fail=None, changed=False, events=events, handle=handle, saved=[])
    state.checkpoint = lambda value: state.saved.append(value)
    lease = SimpleNamespace(state={'run': 'a' * 32}, guard=Mock())

    def call(argv, *, timeout):
        action = argv[6]
        assert state.saved[-1]['pending_action'] == action
        assert state.saved[-1]['owner'] == owner
        assert argv[:6] == ['env', 'ONPC_EXPECTED_RUN=' + 'a' * 32,
            'PYTHONDONTWRITEBYTECODE=1', '/usr/bin/python3', '-B',
            runner.PAYLOAD + '/system_kiosk_scope.py']
        assert argv[7] == owner
        assert timeout == (300 if action == 'start' else 180)
        if action != 'prepare': assert json.loads(argv[8]) == handle
        events.append(action)
        if state.fail == action: raise RuntimeError('failed-' + action)
        return json.dumps(({'boot': 'changed'} if state.changed else proof)
                          if action == 'check' else handle).encode()

    @contextmanager
    def station(vm, actual_lease, *, receipt):
        assert actual_lease is lease
        assert state.saved[-1]['entries'][-1] == {'attempted': True}
        events.append('public-enter')
        receipt['normal_exit'] = False
        if state.fail == 'enter': raise RuntimeError('uncertain-enter')
        try:
            yield receipt
        finally:
            events.append('public-exit')
            if state.fail == 'exit': raise RuntimeError('uncertain-exit')
            receipt['normal_exit'] = True

    monkeypatch.setattr(kiosk_entry, 'native_update_station', station)
    monkeypatch.setattr(runner.uuid, 'uuid4', lambda: SimpleNamespace(hex=owner))
    state.vm, state.lease = SimpleNamespace(call=Mock(side_effect=call)), lease
    return state


def test_retained_history_two_public_visits_keep_one_owner(retained_history):
    state = retained_history
    receipt = {}
    with runner.owned_retained_manager(state.vm, state.lease, receipt=receipt, checkpoint=state.checkpoint) as history:
        for name in ('first-mutation', 'second-mutation'):
            with history.station():
                state.events.append(name)
    assert state.events == ['prepare', 'start', 'check',
        'check', 'public-enter', 'check', 'first-mutation', 'public-exit', 'check',
        'check', 'public-enter', 'check', 'second-mutation', 'public-exit', 'check', 'cleanup']
    assert receipt['cleanup_complete'] and len(receipt['entries']) == 2
    assert all(entry['normal_exit'] for entry in receipt['entries'])
    assert 'first_failure' not in receipt
    assert receipt['cleanup_failures'] == []


@pytest.mark.parametrize('failure', ['start', 'enter', 'exit', 'body', 'interrupt'])
def test_retained_history_preserves_first_failure_and_always_attempts_owned_cleanup(retained_history, failure):
    state = retained_history
    receipt = {}
    state.fail = failure
    expected = KeyboardInterrupt if failure == 'interrupt' else RuntimeError
    with pytest.raises(expected):
        with runner.owned_retained_manager(state.vm, state.lease, receipt=receipt, checkpoint=state.checkpoint) as history:
            with history.station():
                if failure == 'body': raise RuntimeError('caller-first')
                if failure == 'interrupt': raise KeyboardInterrupt('caller-first')
    assert state.events[-1] == 'cleanup'
    assert receipt['cleanup_complete'] and receipt['first_failure'].startswith(expected.__name__)
    assert state.events.count('start') == 1
    assert state.events.count('public-enter') == (0 if failure == 'start' else 1)


def test_retained_history_cleanup_failure_does_not_replace_interruption(retained_history):
    state = retained_history
    receipt = {}
    with pytest.raises(KeyboardInterrupt, match='first') as caught:
        with runner.owned_retained_manager(state.vm, state.lease, receipt=receipt, checkpoint=state.checkpoint):
            state.fail = 'cleanup'
            raise KeyboardInterrupt('first')
    assert receipt['first_failure'] == 'KeyboardInterrupt: first'
    assert receipt['cleanup_failures'] == ['RuntimeError: failed-cleanup']
    assert 'cleanup_complete' not in receipt
    assert caught.value.__notes__ == ['retained-manager:cleanup-failed:RuntimeError']
    state.fail = None
    runner.RetainedManagerHistory(state.vm, state.lease, receipt=receipt, checkpoint=state.checkpoint).cleanup()
    assert receipt['cleanup_complete']
    assert state.events.count('start') == 1


@pytest.mark.parametrize('failure', ['enter', 'exit'])
def test_retained_history_never_replays_uncertain_public_input(retained_history, failure):
    state = retained_history
    state.fail = failure
    receipt = {}
    with runner.owned_retained_manager(state.vm, state.lease, receipt=receipt, checkpoint=state.checkpoint) as history:
        with pytest.raises(RuntimeError):
            with history.station(): pass
        state.fail = None
        with pytest.raises(runner.Error, match='uncertain-public-input'):
            with history.station(): pass
    assert state.events.count('public-enter') == 1


def test_retained_history_replacement_refuses_before_second_public_entry(retained_history):
    state = retained_history
    receipt = {}
    with pytest.raises(runner.Error, match='observation-changed'):
        with runner.owned_retained_manager(state.vm, state.lease, receipt=receipt, checkpoint=state.checkpoint) as history:
            with history.station(): pass
            state.changed = True
            with history.station(): pass
    assert state.events.count('public-enter') == 1
    assert state.events[-1] == 'cleanup'


def test_retained_history_will_not_start_without_durable_recovery_handle(retained_history):
    state = retained_history
    receipt = {}
    def checkpoint(value):
        state.saved.append(value)
        if value.get('pending_action') == 'start':
            raise OSError('save-failed')
    with pytest.raises(OSError, match='save-failed'):
        with runner.owned_retained_manager(state.vm, state.lease,
                receipt=receipt, checkpoint=checkpoint): pass
    assert state.events == ['prepare', 'cleanup']
    assert receipt['cleanup_complete']
    assert receipt['first_failure'] == 'OSError: save-failed'


@pytest.mark.parametrize('failure', [None, 'missing', 'parent', 'symlink', 'file',
                                   'owner', 'writable', 'archive', 'archive-link',
                                   'move', 'readback', 'run'])
def test_snapshot_payload_retirement_preserves_evidence_and_refuses_unsafe_paths(monkeypatch, failure):
    run = 'a' * 32
    payload = runner.PAYLOAD
    monkeypatch.setattr(runner.uuid, 'uuid4', Mock(return_value=Mock(hex='b' * 32)))
    archive = payload + '-snapshot-' + run + '-' + 'b' * 32
    files = {payload + '/removed-helper.py': b'old helper',
             payload + '/__pycache__/removed-helper.pyc': b'old cache',
             payload + '/private/install.log': b'prior evidence'}
    original = dict(files)
    directories = {payload}
    if failure == 'missing':
        directories.clear()
        files.clear()
        original.clear()
    if failure == 'archive':
        directories.add(archive)
    info = {'st_mode': stat.S_IFDIR | 0o700, 'st_uid': 0, 'st_gid': 0}
    if failure == 'file': info['st_mode'] = stat.S_IFREG | 0o600
    if failure == 'owner': info['st_uid'] = 1000
    if failure == 'writable': info['st_mode'] |= 0o020
    g = Mock()
    g.realpath.side_effect = lambda path: '/elsewhere' if failure == 'parent' else path
    g.exists.side_effect = lambda path: path in directories or path in files
    g.is_symlink.side_effect = lambda path: (
        failure == 'symlink' and path == payload or failure == 'archive-link' and path == archive)
    g.lstatns.return_value = info

    def move(source, destination):
        assert (source, destination) == (payload, archive)
        if failure == 'move':
            raise OSError('move refused')
        if failure == 'readback':
            return
        directories.remove(source)
        directories.add(destination)
        for path, content in list(files.items()):
            files[destination + path.removeprefix(source)] = content
            del files[path]

    g.mv.side_effect = move
    if failure not in (None, 'missing'):
        with pytest.raises((runner.Error, OSError)):
            runner.retire_snapshot_payload(g, '../invalid' if failure == 'run' else run)
        assert files == original
        if failure not in ('move', 'readback'):
            g.mv.assert_not_called()
    else:
        runner.retire_snapshot_payload(g, run)
        assert payload not in directories
        assert files == {archive + path.removeprefix(payload): content
                         for path, content in original.items()}
        if failure == 'missing':
            g.mv.assert_not_called()
    g.rm_rf.assert_not_called()


def test_terminal_spawn_failure_closes_both_owned_descriptors(monkeypatch):
    descriptors = []
    openpty = os.openpty
    def recorded():
        pair = openpty()
        descriptors.extend(pair)
        return pair
    monkeypatch.setattr(runner.os, 'openpty', recorded)
    monkeypatch.setattr(runner.subprocess, 'Popen', Mock(side_effect=OSError('spawn-refused')))
    with pytest.raises(OSError, match='spawn-refused'):
        runner.Commands().run(['apt-get', 'update'], terminal=True)
    assert len(descriptors) == 2
    for descriptor in descriptors:
        with pytest.raises(OSError):
            os.fstat(descriptor)


def test_outdated_preparation_refuses_before_disk_audit_or_vm_mutation(lease_rig):
    lease, current = lease_rig
    original = dict(current)
    state_path = lease.directory / 'phase.json'
    state = state_path.read_bytes()
    shutdowns = lease.source.shutdown_calls
    lease.capture.script_digest = '0' * 64
    lease.capture.verify_snapshot = Mock()
    lease.save = Mock()
    with pytest.raises(runner.Error, match='baseline:preparation-outdated'):
        lease.__enter__()
    lease.capture.verify_snapshot.assert_not_called()
    lease.save.assert_not_called()
    assert current == original and state_path.read_bytes() == state
    assert lease.source.shutdown_calls == shutdowns
    assert not lease.journal.exists()
    lease.source.domain.revertToSnapshot.assert_not_called()
    lease.source.domain.create.assert_not_called()
    assert lease.fd is None and lease.commands.lock_fd is None


def test_unprivileged_controller_refuses_before_any_host_or_guest_action():
    with patch.object(runner.os, 'geteuid', return_value=1000), \
            patch.object(runner.subprocess, 'Popen') as spawn, \
            patch.object(runner, 'Lease') as lease, \
            patch.object(runner.tempfile, 'mkdtemp') as mkdir:
        assert runner.main(['--vm', vm_name(), '--artifacts', '/tmp/unused']) == 1
    spawn.assert_not_called()
    lease.assert_not_called()
    mkdir.assert_not_called()


@pytest.mark.parametrize('failure', [KeyboardInterrupt(), subprocess.TimeoutExpired('ssh', 1)])
@pytest.mark.parametrize('timeouts', [0, 1, 2])
@pytest.mark.parametrize('inherited', [(), (43, 42, 43)])
def test_interrupted_command_signals_only_its_recorded_pidfd(failure, timeouts, inherited):
    child = Mock(pid=97531, returncode=0)
    child.communicate.side_effect = failure
    child.wait.side_effect = [subprocess.TimeoutExpired('ssh', 1)] * timeouts + [0]
    with patch.object(runner.subprocess, 'Popen', return_value=child) as spawn, \
            patch.object(runner.os, 'pidfd_open', return_value=41) as pin, \
            patch.object(runner.signal, 'pidfd_send_signal') as send, \
            patch.object(runner.os, 'close') as close, \
            patch.object(runner.os, 'kill') as raw_kill:
        commands = runner.Commands()
        commands.lock_fd = 42
        with pytest.raises(type(failure)):
            commands.run(['ssh'], pass_fds=inherited)
    pin.assert_called_once_with(child.pid)
    assert [call.args for call in send.call_args_list] == [
        (41, sig) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL)[:timeouts + 1]]
    assert spawn.call_args.kwargs['pass_fds'] == ((43, 42) if inherited else (42,))
    close.assert_called_once_with(41)
    raw_kill.assert_not_called()
    child.kill.assert_not_called()
    child.terminate.assert_not_called()


def test_dead_pidfd_never_falls_back_to_a_reused_pid():
    child = Mock(pid=97531, returncode=0)
    child.communicate.side_effect = KeyboardInterrupt
    with patch.object(runner.subprocess, 'Popen', return_value=child), \
            patch.object(runner.os, 'pidfd_open', return_value=41), \
            patch.object(runner.signal, 'pidfd_send_signal', side_effect=ProcessLookupError) as send, \
            patch.object(runner.os, 'close'), patch.object(runner.os, 'kill') as raw_kill:
        with pytest.raises(KeyboardInterrupt):
            runner.Commands().run(['ssh'])
    send.assert_called_once_with(41, signal.SIGINT)
    raw_kill.assert_not_called()


@pytest.mark.parametrize('cleanup', ['running', 'exited', 'signal-refused', 'wait-timeout'])
def test_pidfd_acquisition_failure_cleans_only_direct_child_and_preserves_error(cleanup):
    failure = OSError('private pidfd unavailable')
    child = Mock(pid=97531, returncode=None)
    if cleanup == 'exited':
        child.kill.side_effect = ProcessLookupError
    elif cleanup == 'signal-refused':
        child.kill.side_effect = PermissionError('private cleanup refusal')
    elif cleanup == 'wait-timeout':
        child.wait.side_effect = subprocess.TimeoutExpired('ssh', 10)
    with patch.object(runner.subprocess, 'Popen', return_value=child) as spawn, \
            patch.object(runner.os, 'pidfd_open', side_effect=failure), \
            patch.object(runner.signal, 'pidfd_send_signal') as send, \
            patch.object(runner.os, 'kill') as raw_kill:
        commands = runner.Commands()
        commands.lock_fd = 42
        with pytest.raises(OSError) as caught:
            commands.run(['ssh'], pass_fds=(43,))
    assert caught.value is failure
    assert spawn.call_args.kwargs['pass_fds'] == (43, 42)
    child.kill.assert_called_once_with()
    child.wait.assert_called_once_with(timeout=10)
    child.communicate.assert_not_called()
    send.assert_not_called()
    raw_kill.assert_not_called()
    assert getattr(failure, '__notes__', []) == (
        ['command:spawned-child-cleanup-failed'] if cleanup in ('signal-refused', 'wait-timeout') else [])


def test_pidfd_acquisition_failure_reaps_real_direct_child_and_retains_caller_fd(monkeypatch):
    # The child has its own finite lifetime even if the regression fails; the
    # finally block retains only this direct Popen identity for owned cleanup.
    children = []
    popen = subprocess.Popen
    def spawn(*args, **kwargs):
        child = popen(*args, **kwargs)
        children.append(child)
        return child
    failure = OSError('private pidfd unavailable')
    monkeypatch.setattr(runner.subprocess, 'Popen', spawn)
    monkeypatch.setattr(runner.os, 'pidfd_open', Mock(side_effect=failure))
    reader, writer = os.pipe()
    try:
        with pytest.raises(OSError) as caught:
            runner.Commands().run([sys.executable, '-I', '-c', 'import time; time.sleep(5)'],
                                  pass_fds=(writer,))
        assert caught.value is failure
        assert len(children) == 1 and children[0].returncode is not None
        with pytest.raises(ChildProcessError):
            os.waitpid(children[0].pid, os.WNOHANG)
        os.fstat(writer)
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)
        os.close(reader)
        os.close(writer)


@pytest.mark.parametrize('outcome', ['passed', 'failed', 'interrupted'])
@pytest.mark.parametrize('filtered', [False, True])
def test_command_diagnostic_filter_preserves_results_errors_and_owned_cleanup(
        monkeypatch, tmp_path, outcome, filtered):
    raw = b'unrelated database row\n' * 50000 + b'exact target row\n'
    errors = b'command stderr\n'
    child = Mock(pid=97531, returncode=1 if outcome == 'failed' else 0)

    def spawn(args, **options):
        options['stdout'].write(raw)
        options['stdout'].flush()
        options['stderr'].write(errors)
        options['stderr'].flush()
        return child

    if outcome == 'interrupted':
        child.communicate.side_effect = KeyboardInterrupt
    monkeypatch.setattr(runner.subprocess, 'Popen', spawn)
    monkeypatch.setattr(runner.os, 'pidfd_open', Mock(return_value=41))
    close = Mock()
    monkeypatch.setattr(runner.os, 'close', close)
    send = Mock()
    monkeypatch.setattr(runner.signal, 'pidfd_send_signal', send)
    commands = runner.Commands()
    commands.directory = tmp_path
    transform = Mock(return_value=b'exact target row\n')
    options = {'merge_stderr': False, **({'diagnostic_stdout': transform} if filtered else {})}
    if outcome == 'passed':
        assert commands.run(['probe'], **options) == raw
    else:
        with pytest.raises(KeyboardInterrupt if outcome == 'interrupted' else runner.CommandError):
            commands.run(['probe'], **options)
    assert (tmp_path / 'command-0001.txt').read_bytes() == (
        b'exact target row\n' if filtered else raw)
    assert (tmp_path / 'command-0001-stderr.txt').read_bytes() == errors
    if filtered:
        transform.assert_called_once_with(raw)
    else:
        transform.assert_not_called()
    assert commands.last_returncode == child.returncode
    close.assert_called_once_with(41)
    if outcome == 'interrupted':
        send.assert_called_once_with(41, signal.SIGINT)
        child.wait.assert_called_once_with(timeout=30)
    else:
        send.assert_not_called()


@pytest.mark.parametrize('category', ['guard:domain-replaced', 'guard:run-identity', 'guard:source-changed'])
def test_cleanup_refuses_replaced_domain_before_shutdown_or_destroy(category, local_preparation_source):
    lease = runner.Lease(Mock(), Mock(), Mock())
    lease.mutated = True
    lease.save = Mock()
    lease.guard = Mock(side_effect=runner.Error(category))
    with pytest.raises(runner.Error, match=category):
        lease.finish()
    lease.source.shutdown.assert_not_called()
    lease.source.domain.destroyFlags.assert_not_called()
    lease.source.domain.revertToSnapshot.assert_not_called()


def test_cleanup_cannot_destroy_a_domain_without_a_recorded_start_identity(local_preparation_source):
    lease = runner.Lease(Mock(), Mock(), Mock())
    lease.mutated = True
    lease.save = Mock()
    lease.guard = Mock()
    lease.view.snapshot = Mock(return_value=({}, False))
    with pytest.raises(runner.Error, match='cleanup:unowned-domain'):
        lease.finish()
    lease.source.shutdown.assert_not_called()
    lease.source.domain.destroyFlags.assert_not_called()


def test_domain_replacement_during_shutdown_timeout_prevents_force_stop(local_preparation_source):
    lease = runner.Lease(Mock(), Mock(), Mock())
    lease.mutated = True
    lease.save = Mock()
    lease.guard = Mock(side_effect=[None, runner.Error('guard:domain-replaced')])
    lease.view.domain_id = 17
    lease.view.snapshot = Mock(return_value=({}, False))
    lease.source.shutdown.side_effect = runner.Error('shutdown:timeout')
    with pytest.raises(runner.Error, match='guard:domain-replaced'):
        lease.finish()
    lease.source.domain.destroyFlags.assert_not_called()


def test_cleanup_failure_is_recorded_without_replacing_original_body_failure(local_preparation_source):
    clock = iter((4.0, 6.5))
    ledger = runner.RunLedger(monotonic=lambda: next(clock))
    lease = runner.Lease(Mock(), Mock(), Mock(), ledger=ledger)
    lease.finish = Mock(side_effect=runner.Error('cleanup:guest-changed'))
    lease.release = Mock()
    original = runner.Error('pytest:failed:installed')
    ledger.fail_outcome('product', 'pytest:failed:installed')

    with patch.object(runner.Lease, '__enter__', return_value=lease):
        with pytest.raises(runner.Error, match='pytest:failed:installed') as caught:
            with lease:
                raise original

    assert caught.value is original
    assert ledger.outcomes['cleanup'] == {
        'outcome': 'failed', 'category': 'cleanup:guest-changed'}
    assert ledger.durations['cleanup'] == 2.5
    lease.release.assert_called_once()


@pytest.mark.parametrize('body_error', [False, True])
@pytest.mark.parametrize('cleanup_error', [False, True])
@pytest.mark.parametrize('final_error', [False, True])
@pytest.mark.parametrize('release_error', [False, True])
def test_finalization_runs_once_while_held_and_preserves_first_error(
        body_error, cleanup_error, final_error, release_error, local_preparation_source):
    events = []
    errors = [RuntimeError('private body'), RuntimeError('private cleanup'),
              KeyboardInterrupt('private final'), RuntimeError('private release')]
    ledger = runner.RunLedger()
    lease = runner.Lease(Mock(), Mock(), Mock(), ledger=ledger)
    lease.fd = 42
    lease.state = {'phase': 'running'}

    def finish():
        assert lease.fd == 42
        events.append('finish')
        if cleanup_error:
            raise errors[1]
        lease.state['phase'] = 'complete'

    def finalize(held):
        assert held is lease and held.fd == 42
        assert held.state['phase'] == ('running' if cleanup_error else 'complete')
        events.append('finalize')
        if final_error:
            raise errors[2]

    def release():
        events.append('release')
        lease.fd = None
        if release_error:
            raise errors[3]

    lease.finish, lease.finalize, lease.release = finish, finalize, release
    expected = next((error for fault, error in zip(
        (body_error, cleanup_error, final_error, release_error), errors) if fault), None)
    with patch.object(runner.Lease, '__enter__', return_value=lease):
        try:
            with lease:
                events.append('body')
                if body_error:
                    raise errors[0]
        except BaseException as caught:
            assert caught is expected
        else:
            assert expected is None
    assert events == ['body', 'finish', 'finalize', 'release']
    assert lease.fd is None
    assert 'private' not in str(ledger.data())


def test_cleanup_failure_also_retains_an_unclassified_body_infrastructure_failure(local_preparation_source):
    ledger = runner.RunLedger()
    lease = runner.Lease(Mock(), Mock(), Mock(), ledger=ledger)
    lease.finish = Mock(side_effect=runner.Error('cleanup:guest-changed'))
    lease.release = Mock()
    original = runner.Error('transport:domain-replaced')

    with patch.object(runner.Lease, '__enter__', return_value=lease):
        with pytest.raises(runner.Error, match='transport:domain-replaced') as caught:
            with lease:
                raise original

    assert caught.value is original
    assert ledger.outcomes['infrastructure'] == {
        'outcome': 'failed', 'category': 'transport:domain-replaced'}
    assert ledger.outcomes['cleanup'] == {
        'outcome': 'failed', 'category': 'cleanup:guest-changed'}


def test_cleanup_failure_without_an_original_error_remains_terminal(local_preparation_source):
    ledger = runner.RunLedger()
    lease = runner.Lease(Mock(), Mock(), Mock(), ledger=ledger)
    lease.finish = Mock(side_effect=runner.Error('cleanup:guest-changed'))
    lease.release = Mock()

    with patch.object(runner.Lease, '__enter__', return_value=lease):
        with pytest.raises(runner.Error, match='cleanup:guest-changed'):
            with lease:
                pass

    assert ledger.outcomes['cleanup'] == {
        'outcome': 'failed', 'category': 'cleanup:guest-changed'}
    lease.release.assert_called_once()
