"""Spectator ownership, bounded cleanup and refusal to adopt unrelated objects."""

import os
import socket
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.support.ui_watch import Observer, start, stop_child
from ui_watch_transport import Publication, private_directory


@pytest.mark.parametrize('exited', [False, True])
def test_only_owned_unreaped_child_can_be_signalled(exited):
    child = Mock()
    child.poll.return_value = 0 if exited else None
    child.wait.side_effect = [subprocess.TimeoutExpired('owned-child', 5), 0]
    stop_child(child)
    assert child.terminate.call_count == int(not exited)
    assert child.kill.call_count == int(not exited)


def test_observer_closes_lifetime_channel_before_wait_or_signal():
    observer = Observer.__new__(Observer)
    observer.control, observer.child, observer.log = Mock(), Mock(), Mock()
    observer.services = []
    control, child, log = observer.control, observer.child, observer.log
    child.wait.side_effect = lambda **_kw: control.close.assert_called_once()
    observer.close()
    child.terminate.assert_not_called()
    child.kill.assert_not_called()
    log.close.assert_called_once()
    observer.close()
    child.wait.assert_called_once()


def test_fixture_cleanup_signals_its_recorded_services_in_reverse_order():
    observer = Observer.__new__(Observer)
    observer.control = observer.child = observer.log = None
    first, second, exited = Mock(), Mock(), Mock()
    first.poll.return_value = second.poll.return_value = None
    exited.poll.return_value = 0
    second.wait.side_effect = [subprocess.TimeoutExpired('wireplumber', 2), 0]
    order = []
    first.terminate.side_effect = lambda: order.append('first')
    second.terminate.side_effect = lambda: order.append('second')
    observer.services = [first, second, exited]
    observer.close()
    assert order == ['second', 'first']
    second.kill.assert_called_once()
    first.kill.assert_not_called()
    exited.terminate.assert_not_called()
    observer.close()
    first.terminate.assert_called_once()


def test_publication_cleanup_preserves_replacement_socket_and_other_worker():
    temporary = tempfile.TemporaryDirectory(prefix='onpc-ui-watch-test-', dir='/tmp')
    directory = Path(temporary.name)
    first, second = Publication(directory), Publication(directory)
    replacement = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    try:
        first.path.unlink()
        replacement.bind(str(first.path))
        first.close()
        assert first.path.is_socket() and second.path.is_socket()
        second.frames.publish(test='still running')
    finally:
        replacement.close()
        first.path.unlink()
        second.close()
        temporary.cleanup()


@pytest.mark.parametrize('unsafe', ['symlink', 'public', 'owner'])
def test_registry_rejects_unsafe_directory(tmp_path, monkeypatch, unsafe):
    directory = tmp_path / 'registry'
    directory.mkdir(mode=0o700)
    if unsafe == 'symlink':
        link = tmp_path / 'link'
        link.symlink_to(directory)
        directory = link
    elif unsafe == 'public':
        directory.chmod(0o777)
    else:
        monkeypatch.setattr(os, 'getuid', lambda: directory.stat().st_uid + 1)
    with pytest.raises(ValueError, match='ui-registry-owner'):
        private_directory(directory)


def test_refuses_host_compositor_before_spawning(monkeypatch):
    spawn = Mock(side_effect=AssertionError('must refuse before spawning'))
    monkeypatch.setattr(subprocess, 'Popen', spawn)
    session = SimpleNamespace(temporary_root='/tmp/unrelated', bus_address='unix:path=/run/user/1000/bus',
                              environment={'XDG_RUNTIME_DIR': '/run/user/1000',
                                           'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/run/user/1000/bus'})
    assert start(session) is None
    spawn.assert_not_called()
