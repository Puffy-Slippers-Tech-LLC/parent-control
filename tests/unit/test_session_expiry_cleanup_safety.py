"""No real guest or process operations: expiry fixtures must fail at their guard."""

from unittest.mock import Mock

import pytest

import system_session_expiry as expiry
import system_graphical_expiry as graphical


@pytest.mark.parametrize('entry,args', [
    ('identities', ()), ('grant', (1000, 1)), ('pam_probe', ('gdm-password',)),
    ('verify_pam_scope', ('gdm-password', Mock())),
    ('verify_offline_recovery', (Mock(),)), ('installed_manager', ()),
    ('verify_zero_time_pam', (Mock(),)), ('pam_password_status', (1000, Mock())),
    ('pam_password_in_process', (1000, b'fixture')),
    ('verify_request_extension', (Mock(),)), ('verify_runtime_rollback', (Mock(),)),
    ('verify_unavailable_enforcement', (Mock(),)),
])
def test_fixture_refuses_outside_guarded_guest(monkeypatch, entry, args):
    guard = Mock(side_effect=expiry.guest.GuestError('test:guest-refused'))
    run = Mock()
    account = Mock()
    load = Mock()
    create = Mock()
    monkeypatch.setattr(expiry.guest, 'guard', guard)
    monkeypatch.setattr(expiry.guest.commands, 'run', run)
    monkeypatch.setattr(expiry.pwd, 'getpwnam', account)
    monkeypatch.setattr(expiry.ctypes, 'CDLL', load)
    monkeypatch.setattr(expiry.tempfile, 'mkdtemp', create)
    with pytest.raises(expiry.guest.GuestError, match='test:guest-refused'):
        getattr(expiry, entry)(*args)
    run.assert_not_called()
    account.assert_not_called()
    load.assert_not_called()
    create.assert_not_called()


def test_pam_probe_refuses_unregistered_service_before_opening_pam(monkeypatch):
    load = Mock()
    monkeypatch.setattr(expiry.ctypes, 'CDLL', load)
    with pytest.raises(expiry.guest.GuestError, match='expiry:pam-service'):
        expiry.pam_probe('unregistered-service')
    load.assert_not_called()


@pytest.mark.parametrize('entry,args', [('prepare', ()), ('seed', ()), ('verify', (Mock(),)),
                                      ('screen_lock_observation', (1004, '4', Mock(), Mock())),
                                      ('verify_other_foreground', (1004, '4', Mock()))])
def test_graphical_fixture_requires_guest_guard_before_actions(monkeypatch, entry, args):
    monkeypatch.setattr(graphical.guest, 'guard',
                        Mock(side_effect=expiry.guest.GuestError('test:guest-refused')))
    run = Mock()
    monkeypatch.setattr(graphical.guest.commands, 'run', run)
    with pytest.raises(expiry.guest.GuestError, match='test:guest-refused'):
        getattr(graphical, entry)(*args)
    run.assert_not_called()
