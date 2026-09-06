"""Isolated ownership checks. No processes, namespaces, or VM controls run."""

import signal
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tests/integration'))
import graphical_worker as worker
sys.path.pop(0)


def handle():
    item = worker.Worker.__new__(worker.Worker)
    item.control = Mock()
    item.child = Mock(pid=12345)
    item.pidfd = 42
    return item


@pytest.mark.parametrize('expired', [False, True])
def test_timeout_signals_only_pinned_supervisor(expired):
    item = handle()
    child = item.child
    item.child.wait.side_effect = [subprocess.TimeoutExpired('worker', 7), 0]
    with patch.object(worker.signal, 'pidfd_send_signal',
                      side_effect=ProcessLookupError if expired else None) as send, \
            patch.object(worker.os, 'kill') as raw, patch.object(worker.os, 'close') as close:
        item.close()
    send.assert_called_once_with(42, signal.SIGKILL)
    close.assert_called_once_with(42)
    raw.assert_not_called()
    child.kill.assert_not_called()
    child.terminate.assert_not_called()


def test_control_closes_before_wait_and_normal_exit_needs_no_signal():
    item = handle()
    events = []
    item.control.close.side_effect = lambda: events.append('eof')
    item.child.wait.side_effect = lambda **kwargs: events.append('wait')
    with patch.object(worker.signal, 'pidfd_send_signal') as send, \
            patch.object(worker.os, 'close'):
        item.close()
    assert events == ['eof', 'wait']
    send.assert_not_called()


def test_cleanup_failure_retains_pidfd_for_owned_recovery():
    item = handle()
    item.child.wait.side_effect = subprocess.TimeoutExpired('worker', 7)
    with patch.object(worker.signal, 'pidfd_send_signal'), patch.object(worker.os, 'close') as close:
        with pytest.raises(subprocess.TimeoutExpired):
            item.close()
    assert item.pidfd == 42
    close.assert_not_called()


def test_failed_identity_recording_never_falls_back_to_numeric_pid():
    item = handle()
    item.pidfd = None
    item.child.wait.side_effect = subprocess.TimeoutExpired('worker', 7)
    with patch.object(worker.signal, 'pidfd_send_signal') as send, \
            patch.object(worker.os, 'kill') as raw:
        with pytest.raises(RuntimeError, match='unrecorded-supervisor'):
            item.close()
    send.assert_not_called()
    raw.assert_not_called()


def test_non_root_refuses_before_socket_files_or_spawn(tmp_path):
    with patch.object(worker.os, 'geteuid', return_value=1000), \
            patch.object(worker.socket, 'socketpair') as pair, \
            patch.object(worker.subprocess, 'Popen') as spawn:
        with pytest.raises(RuntimeError, match='root-required'):
            worker.Worker(tmp_path, '/tmp/callback', 'a' * 32, ['/bin/true'])
    pair.assert_not_called()
    spawn.assert_not_called()


@pytest.mark.parametrize('pid,original,current', [
    (27, (1, 2, 3), (4, 5, 6)),
    (1, (1, 2, 3), (1, 5, 6)),
    (1, (1, 2, 3), (4, 2, 6)),
    (1, (1, 2, 3), (4, 5, 3)),
])
def test_bridge_refuses_host_namespace_before_creating_listener(pid, original, current):
    with patch.object(worker.os, 'geteuid', return_value=0), \
            patch.object(worker.os, 'getpid', return_value=pid), \
            patch.object(worker, 'namespace_ids', return_value=current), \
            patch.object(worker.socket, 'socket') as socket_factory:
        with pytest.raises(RuntimeError, match='namespace'):
            worker.Bridge(original, '/tmp/unused', 'a' * 32)
    socket_factory.assert_not_called()


def test_spawn_pins_identity_before_releasing_start_gate(tmp_path):
    tmp_path.chmod(0o700)
    metadata = tmp_path.stat()
    fake_metadata = Mock(st_mode=metadata.st_mode, st_uid=0)
    parent, remote = Mock(), Mock()
    remote.fileno.return_value = 19
    child = Mock(pid=12345)
    events = []
    with patch.object(worker.os, 'geteuid', return_value=0), \
            patch.object(worker.Path, 'lstat', return_value=fake_metadata), \
            patch.object(worker, 'namespace_ids', return_value=(1, 2, 3)), \
            patch.object(worker.socket, 'socketpair', return_value=(parent, remote)), \
            patch.object(worker.subprocess, 'Popen', return_value=child) as spawn, \
            patch.object(worker.os, 'pidfd_open', side_effect=lambda pid: events.append(('pin', pid)) or 42), \
            patch.object(worker.os, 'close'):
        parent.sendall.side_effect = lambda packet: events.append(('send', packet))
        item = worker.Worker(tmp_path, '/tmp/callback', 'a' * 32, ['/bin/true'])
        item.close()
    assert events == [('pin', 12345), ('send', b'start\n')]
    args = spawn.call_args.args[0]
    for flag in ('--net', '--pid', '--mount-proc', '--kill-child=KILL'):
        assert flag in args
    assert spawn.call_args.kwargs['pass_fds'] == (19,)
    assert spawn.call_args.kwargs['env'].keys() == {'PATH', 'HOME', 'LANG'}


def test_failed_pin_closes_gate_without_authorizing_backend(tmp_path):
    tmp_path.chmod(0o700)
    metadata = Mock(st_mode=tmp_path.stat().st_mode, st_uid=0)
    parent, remote = Mock(), Mock()
    remote.fileno.return_value = 19
    with patch.object(worker.os, 'geteuid', return_value=0), \
            patch.object(worker.Path, 'lstat', return_value=metadata), \
            patch.object(worker, 'namespace_ids', return_value=(1, 2, 3)), \
            patch.object(worker.socket, 'socketpair', return_value=(parent, remote)), \
            patch.object(worker.subprocess, 'Popen') as spawn, \
            patch.object(worker.os, 'pidfd_open', side_effect=OSError), \
            patch.object(worker.signal, 'pidfd_send_signal') as send:
        with pytest.raises(OSError):
            worker.Worker(tmp_path, '/tmp/callback', 'a' * 32, ['/bin/true'])
    parent.sendall.assert_not_called()
    parent.close.assert_called_once()
    spawn.return_value.wait.assert_called_once_with(timeout=7)
    send.assert_not_called()
