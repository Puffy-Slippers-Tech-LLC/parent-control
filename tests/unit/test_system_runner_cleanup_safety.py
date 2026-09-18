"""Run in isolation before any live system runner: all process/VM calls mocked."""

import signal
import stat
import os
import subprocess
from unittest.mock import Mock, patch

import pytest

import system_runner as runner
from tests.support.vm_baseline import local_preparation_source, rig
from tests.support.vm_runner import lease_rig


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
        assert runner.main(['--artifacts', '/tmp/unused']) == 1
    spawn.assert_not_called()
    lease.assert_not_called()
    mkdir.assert_not_called()


@pytest.mark.parametrize('failure', [KeyboardInterrupt(), subprocess.TimeoutExpired('ssh', 1)])
@pytest.mark.parametrize('timeouts', [0, 1, 2])
def test_interrupted_command_signals_only_its_recorded_pidfd(failure, timeouts):
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
            commands.run(['ssh'])
    pin.assert_called_once_with(child.pid)
    assert [call.args for call in send.call_args_list] == [
        (41, sig) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL)[:timeouts + 1]]
    assert spawn.call_args.kwargs['pass_fds'] == (42,)
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
