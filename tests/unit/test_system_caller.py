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


def test_guard_failure_prevents_identity_drop_and_bus_connection(monkeypatch):
    monkeypatch.setattr(caller.guest, 'guard', Mock(side_effect=caller.guest.GuestError('guard-refused')))
    drop = Mock()
    monkeypatch.setattr(caller, 'drop_identity', drop)
    with pytest.raises(caller.guest.GuestError, match='guard-refused'):
        caller.main()
    drop.assert_not_called()


@pytest.mark.parametrize('target', ['../secret', True, -1, 0])
def test_private_read_cannot_select_arbitrary_paths(target):
    with pytest.raises(caller.guest.GuestError, match='caller:target'):
        caller.execute(None, {'kind': 'private-read', 'target': target}, None, None)
