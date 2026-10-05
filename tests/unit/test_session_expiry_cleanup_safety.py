"""No real guest or process operations: expiry fixtures must fail at their guard."""

import json
from pathlib import Path
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


@pytest.mark.parametrize('runtime', [0, 3000000, 2 ** 64 - 1, -1, 2 ** 64, True, 'infinity'])
def test_pam_scope_observer_reads_typed_native_properties_without_commands(runtime, monkeypatch):
    observer = expiry.PamScopeObserver.__new__(expiry.PamScopeObserver)
    observer.call = Mock(side_effect=['/login/session', 'session-42.scope', '/system/unit', runtime, 'active'])
    command = Mock(side_effect=AssertionError('post-PAM command forbidden'))
    monkeypatch.setattr(expiry.guest, 'run', command)
    if type(runtime) is int and 0 <= runtime < 2 ** 64:
        scope, path, value = observer.scope('42')
        assert (scope, path, value) == ('session-42.scope', '/system/unit',
            'infinity' if runtime == 2 ** 64 - 1 else str(runtime) + 'us')
        assert observer.active(path)
    else:
        with pytest.raises(expiry.guest.GuestError, match='expiry:scope-runtime-response'):
            observer.scope('42')
    assert observer.call.call_args_list[0].args == (
        'org.freedesktop.login1', '/org/freedesktop/login1',
        'org.freedesktop.login1.Manager', 'GetSession', '(s)', ('42',), '(o)')
    assert observer.call.call_args_list[3].args == (
        'org.freedesktop.systemd1', '/system/unit', 'org.freedesktop.DBus.Properties',
        'Get', '(ss)', ('org.freedesktop.systemd1.Scope', 'RuntimeMaxUSec'), '(v)')
    command.assert_not_called()


@pytest.mark.parametrize('active', [False, True])
def test_pam_probe_observes_open_session_without_executing_diagnostic_children(monkeypatch, capsys, active):
    from types import SimpleNamespace
    monkeypatch.setattr(expiry, 'identities', lambda: {'child': 1004})
    monkeypatch.setattr(expiry.pwd, 'getpwuid', lambda _uid: SimpleNamespace(pw_name='fixture'))
    monkeypatch.setattr(expiry, 'grant', lambda *_: 101)
    monkeypatch.setattr(expiry.time, 'time', lambda: 100.25)
    monkeypatch.setattr(expiry.time, 'sleep', Mock())
    observer = Mock(scope=Mock(return_value=('session-42.scope', '/system/unit', 'infinity')),
                    active=Mock(return_value=active))
    monkeypatch.setattr(expiry, 'PamScopeObserver', Mock(return_value=observer))
    pam = Mock()
    for operation in ('pam_start', 'pam_putenv', 'pam_acct_mgmt', 'pam_open_session',
                      'pam_close_session', 'pam_end'):
        getattr(pam, operation).return_value = 0
    pam.pam_getenv.return_value = b'42'
    monkeypatch.setattr(expiry.ctypes, 'CDLL', Mock(return_value=pam))
    command = Mock(side_effect=AssertionError('post-PAM command forbidden'))
    monkeypatch.setattr(expiry.guest, 'run', command)
    if active:
        expiry.pam_probe('gdm-password')
    else:
        with pytest.raises(expiry.guest.GuestError, match='expiry:scope-ended-at-old-deadline'):
            expiry.pam_probe('gdm-password')
    observations = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert observations[:2] == [
        {'stage': 'account', 'status': 0, 'remaining_seconds': 0.75},
        {'stage': 'scope-created', 'runtime_max': 'infinity', 'scope': 'session-42.scope'}]
    assert (observations[-1].get('scope_active') is True) == active
    pam.pam_close_session.assert_called_once()
    pam.pam_end.assert_called_once()
    observer.scope.assert_called_once_with('42')
    observer.active.assert_called_once_with('/system/unit')
    command.assert_not_called()


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
@pytest.mark.parametrize('service', expiry.SERVICES)
@pytest.mark.parametrize('witnesses', [True, False])
def test_pam_scope_uses_supported_capture_and_requires_native_witnesses(
        monkeypatch, package_format, service, witnesses):
    accounts = {'parent': 1003, 'child': 1004, 'other': 1005}
    monkeypatch.setattr(expiry, 'identities', lambda: accounts)
    monkeypatch.setattr(expiry, 'account_state', lambda _uid: ('unchanged',))
    change = Mock(return_value={})
    monkeypatch.setattr(expiry, 'call', change)
    monkeypatch.setattr(expiry, 'accepted', lambda value: value)
    monkeypatch.setattr(expiry.guest, 'guard', lambda: {'run': 'a' * 32})
    monkeypatch.setattr(expiry.guest, 'package_path', lambda: Path('package.' + package_format))
    gdm = service.startswith('gdm-')
    observations = [
        {'stage': 'account', 'status': 0, 'remaining_seconds': 0.9 if gdm else 2.9},
        {'stage': 'scope-created', 'runtime_max': 'infinity' if gdm else '3s',
         'scope': 'session-42.scope'},
    ]
    if gdm:
        observations.append({'stage': 'past-deadline', 'scope_active': True})
    raw = ''.join(json.dumps(item) + '\r\n' for item in observations).encode() if witnesses else b''
    commands = Mock(last_returncode=0)
    commands.run.return_value = raw
    monkeypatch.setattr(expiry.guest, 'commands', commands)
    monkeypatch.setattr(expiry.guest, 'run', Mock(
        return_value='Scope reached runtime time limit. Stopping.'))
    if witnesses:
        expiry.verify_pam_scope(service, Mock())
    else:
        with pytest.raises(expiry.guest.GuestError, match='expiry:pam-witnesses'):
            expiry.verify_pam_scope(service, Mock())
    args, options = commands.run.call_args
    assert '--pipe' in args[0] and '--wait' in args[0] and '--collect' in args[0]
    assert args[0][-2:] == ['--pam', service]
    assert options == {'timeout': 60, 'check': False, 'merge_stderr': False,
                       'terminal': package_format == 'rpm'}
    assert commands.run.call_count == 1
    assert change.call_args.args == (1003, 'SetParentControl', '(ubu)', (1004, False, 60))


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
