"""Run in isolation before any live system runner: all process/VM calls mocked."""

import signal
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tests/integration'))
import system_runner as runner
sys.path.pop(0)


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
def test_cleanup_refuses_replaced_domain_before_shutdown_or_destroy(category):
    lease = runner.Lease(Mock(), Mock(), Mock())
    lease.mutated = True
    lease.save = Mock()
    lease.guard = Mock(side_effect=runner.Error(category))
    with pytest.raises(runner.Error, match=category):
        lease.finish()
    lease.source.shutdown.assert_not_called()
    lease.source.domain.destroyFlags.assert_not_called()
    lease.source.domain.revertToSnapshot.assert_not_called()


def test_cleanup_cannot_destroy_a_domain_without_a_recorded_start_identity():
    lease = runner.Lease(Mock(), Mock(), Mock())
    lease.mutated = True
    lease.save = Mock()
    lease.guard = Mock()
    lease.view.snapshot = Mock(return_value=({}, False))
    with pytest.raises(runner.Error, match='cleanup:unowned-domain'):
        lease.finish()
    lease.source.shutdown.assert_not_called()
    lease.source.domain.destroyFlags.assert_not_called()


def test_domain_replacement_during_shutdown_timeout_prevents_force_stop():
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
