"""Bounded native probes and restoration, without executing guest commands."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

import system_session_expiry as expiry
from system_caller import FixturePassword


@pytest.mark.parametrize('account_only', [False, True])
def test_password_probe_is_bounded_and_secret_is_stdin_only(monkeypatch, account_only):
    monkeypatch.setattr(expiry.guest, 'guard', Mock())
    monkeypatch.setattr(expiry, 'identities', lambda: {'child': 1004})
    invoke = Mock(return_value=b'13\n')
    monkeypatch.setattr(expiry.guest.commands, 'run', invoke)
    password = FixturePassword()
    assert expiry.pam_password_status(1004, password, account_only=account_only) == 13
    args, = invoke.call_args.args
    assert args[-2:] == ['--pam-password', 'account' if account_only else 'authenticate']
    assert password._value.decode() not in ' '.join(args)
    assert invoke.call_args.kwargs['timeout'] == 30
    assert invoke.call_args.kwargs['merge_stderr'] is False
    assert json.loads(invoke.call_args.kwargs['input']) == {
        'uid': 1004, 'password': password._value.decode()}


@pytest.mark.parametrize('raw', [b'32', b'-1', b'true', b'{}', b'private failure text'])
def test_password_probe_refuses_invalid_result_without_exposing_reply(monkeypatch, raw):
    monkeypatch.setattr(expiry.guest, 'guard', Mock())
    monkeypatch.setattr(expiry, 'identities', lambda: {'child': 1004})
    monkeypatch.setattr(expiry.guest.commands, 'run', Mock(return_value=raw))
    with pytest.raises(expiry.guest.GuestError, match='expiry:pam-password-') as caught:
        expiry.pam_password_status(1004, FixturePassword())
    assert 'private failure text' not in str(caught.value)


@pytest.mark.parametrize('approved', [False, True])
def test_unavailable_enforcement_restores_exact_file_even_on_bad_request_result(
        monkeypatch, tmp_path, approved):
    installation = tmp_path / 'extension'
    installation.mkdir()
    metadata = installation / 'metadata.json'
    metadata.write_bytes(b'original metadata')
    original = metadata.stat()
    fixture = tmp_path / 'failure'
    monkeypatch.setattr(expiry, 'Path', lambda value: fixture if
                        value == '/var/lib/onpc-test-extension-failure' else Path(value))
    monkeypatch.setattr(expiry, 'identities', lambda: {'child': 1004, 'parent': 1002})
    manager = Mock(installation=installation)
    manager._account.return_value = (Mock(), installation)
    manager._boolean.side_effect = [False] if approved else [True, False]
    monkeypatch.setattr(expiry, 'installed_manager', lambda: manager)
    monkeypatch.setattr(expiry, 'account_state', lambda uid: 'unchanged')
    def call(uid, method, *_args):
        if method == 'RevokeOneTimeGrant':
            return {'result': []}
        assert not metadata.exists()
        assert (fixture / 'metadata.json').stat().st_ino == original.st_ino
        return {'result': []} if approved else {'error': 'fixed-startup-failure'}
    monkeypatch.setattr(expiry, 'call', call)
    monkeypatch.setattr(expiry.guest, 'run', Mock(return_value='b false'))
    activate = Mock()
    monkeypatch.setattr(expiry.guest, 'activate_broker', activate)
    if approved:
        with pytest.raises(expiry.guest.GuestError, match='approval-without-enforcement'):
            expiry.verify_unavailable_enforcement(Mock())
    else:
        expiry.verify_unavailable_enforcement(Mock())
    assert metadata.stat().st_ino == original.st_ino
    assert metadata.read_bytes() == b'original metadata'
    assert not (fixture / 'metadata.json').exists()
    activate.assert_called_once()
