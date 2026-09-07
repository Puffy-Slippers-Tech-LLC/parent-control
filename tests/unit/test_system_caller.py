"""Credential-drop regressions use mocks; no host account or bus is changed."""

from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tests/integration'))
import system_caller as caller
sys.path.pop(0)


def identity_rig(monkeypatch):
    account = SimpleNamespace(pw_name='fixture', pw_gid=1234, pw_dir='/home/fixture')
    monkeypatch.setattr(caller.pwd, 'getpwuid', Mock(return_value=account))
    calls = Mock()
    for name in ('initgroups', 'setresgid', 'setresuid', 'chdir'):
        monkeypatch.setattr(caller.os, name, getattr(calls, name))
    monkeypatch.setattr(caller.os, 'getresuid', lambda: (2345,) * 3)
    monkeypatch.setattr(caller.os, 'getresgid', lambda: (1234,) * 3)
    monkeypatch.setattr(caller.os, 'environ', {'DBUS_SYSTEM_BUS_ADDRESS': 'untrusted', 'SECRET': 'hidden'})
    return calls


def test_all_saved_credentials_are_dropped_before_bus_use(monkeypatch):
    calls = identity_rig(monkeypatch)
    caller.drop_identity(2345)
    assert [(c[0], c.args) for c in calls.mock_calls] == [
        ('initgroups', ('fixture', 1234)), ('setresgid', (1234, 1234, 1234)),
        ('setresuid', (2345, 2345, 2345)), ('chdir', ('/',))]
    assert caller.os.environ == {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': '/home/fixture'}


@pytest.mark.parametrize('uid', [0, -1, True, '2345'])
def test_invalid_identity_refuses_before_any_credential_change(monkeypatch, uid):
    calls = identity_rig(monkeypatch)
    with pytest.raises(caller.guest.GuestError, match='caller:uid'):
        caller.drop_identity(uid)
    assert not calls.mock_calls


def test_retained_root_saved_uid_is_refused(monkeypatch):
    identity_rig(monkeypatch)
    monkeypatch.setattr(caller.os, 'getresuid', lambda: (2345, 2345, 0))
    with pytest.raises(caller.guest.GuestError, match='caller:credentials'):
        caller.drop_identity(2345)


def test_explicit_root_caller_sets_and_verifies_all_credentials(monkeypatch):
    calls = identity_rig(monkeypatch)
    monkeypatch.setattr(caller.os, 'getresuid', lambda: (0, 0, 0))
    caller.drop_identity(0, allow_root=True)
    calls.setresuid.assert_called_once_with(0, 0, 0)
    calls.initgroups.assert_called_once_with('fixture', 1234)
    calls.setresgid.assert_called_once_with(1234, 1234, 1234)
    assert caller.os.environ == {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': '/home/fixture'}


@pytest.mark.parametrize('allow_root', [False, None, 1, 'true'])
def test_root_requires_literal_opt_in(monkeypatch, allow_root):
    calls = identity_rig(monkeypatch)
    with pytest.raises(caller.guest.GuestError, match='caller:uid'):
        caller.drop_identity(0, allow_root=allow_root)
    assert not calls.mock_calls


def test_root_opt_in_still_verifies_kernel_credentials(monkeypatch):
    identity_rig(monkeypatch)
    with pytest.raises(caller.guest.GuestError, match='caller:credentials'):
        caller.drop_identity(0, allow_root=True)


def test_authentication_agent_cannot_opt_in_to_root(monkeypatch, capsys):
    calls = identity_rig(monkeypatch)
    monkeypatch.setattr(caller.guest, 'guard', Mock())
    monkeypatch.setattr(caller.os, 'setsid', Mock())
    monkeypatch.setattr(caller.fcntl, 'ioctl', Mock())
    execute = Mock()
    monkeypatch.setattr(caller.os, 'execv', execute)
    with pytest.raises(SystemExit):
        caller.run_agent('12345,67890', '13', '0')
    assert not calls.mock_calls
    execute.assert_not_called()
    assert capsys.readouterr() == ('', 'agent-wrapper:identity\n')


def test_guard_failure_prevents_identity_drop_and_bus_connection(monkeypatch):
    monkeypatch.setattr(caller.guest, 'guard', Mock(side_effect=caller.guest.GuestError('guard-refused')))
    drop = Mock()
    monkeypatch.setattr(caller, 'drop_identity', drop)
    with pytest.raises(caller.guest.GuestError, match='guard-refused'):
        caller.main()
    drop.assert_not_called()


@pytest.mark.parametrize('failure', [None, 'guard', 'identity'])
def test_agent_drops_all_credentials_before_exec_and_fails_closed(monkeypatch, capsys, failure):
    calls = Mock()
    identity = identity_rig(monkeypatch)
    calls.attach_mock(identity, 'identity')
    monkeypatch.setattr(caller.guest, 'guard', calls.guard)
    monkeypatch.setattr(caller.os, 'setsid', calls.setsid)
    monkeypatch.setattr(caller.fcntl, 'ioctl', calls.ioctl)
    monkeypatch.setattr(caller.os, 'execv', calls.execv)
    if failure == 'guard':
        calls.guard.side_effect = RuntimeError('private-guard-detail')
    elif failure == 'identity':
        identity.setresuid.side_effect = RuntimeError('private-identity-detail')
    if failure:
        with pytest.raises(SystemExit):
            caller.run_agent('12345,67890', '13', '2345')
        calls.execv.assert_not_called()
        assert capsys.readouterr() == ('', f'agent-wrapper:{failure}\n')
        if failure == 'guard':
            assert not identity.mock_calls
    else:
        caller.run_agent('12345,67890', '13', '2345')
        assert [entry[0] for entry in calls.mock_calls] == [
            'guard', 'setsid', 'ioctl', 'identity.initgroups',
            'identity.setresgid', 'identity.setresuid', 'identity.chdir', 'execv']
        calls.execv.assert_called_once_with('/usr/bin/pkttyagent', [
            'pkttyagent', '--process', '12345,67890', '--notify-fd', '13'])
        assert caller.os.environ == {
            'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C', 'HOME': '/home/fixture'}


@pytest.mark.parametrize('target', ['../secret', True, -1, 0])
def test_private_read_cannot_select_arbitrary_paths(target):
    with pytest.raises(caller.guest.GuestError, match='caller:target'):
        caller.execute(None, {'kind': 'private-read', 'target': target}, None, None)


def stream_rig(monkeypatch, chunks):
    instance = caller.PersistentCaller.__new__(caller.PersistentCaller)
    instance.child = SimpleNamespace(stdout=Mock())
    instance.pending = b''
    monkeypatch.setattr(caller.select, 'select', Mock(return_value=([instance.child.stdout], [], [])))
    monkeypatch.setattr(caller.os, 'read', Mock(side_effect=chunks))
    return instance


def test_stream_frames_fragmented_and_combined_replies(monkeypatch):
    instance = stream_rig(monkeypatch, [b'{"result":', b'[1]}\n{"error":"denied"}\n'])
    assert instance.receive() == {'result': [1]}
    assert instance.receive() == {'error': 'denied'}
    assert caller.os.read.call_count == 2


def test_stream_eof_is_a_failure(monkeypatch):
    instance = stream_rig(monkeypatch, [b''])
    with pytest.raises(caller.guest.GuestError, match='stream-disconnected'):
        instance.receive()


def test_stream_wait_has_a_bounded_deadline(monkeypatch):
    instance = stream_rig(monkeypatch, [])
    caller.select.select.return_value = ([], [], [])
    with pytest.raises(caller.guest.GuestError, match='stream-timeout'):
        instance.receive(timeout=0.1)
    assert 0 < caller.select.select.call_args.args[3] <= 0.1


def test_stream_rejects_unbounded_replies(monkeypatch):
    instance = stream_rig(monkeypatch, [b'x' * 1048577])
    with pytest.raises(caller.guest.GuestError, match='stream-reply-size'):
        instance.receive()
