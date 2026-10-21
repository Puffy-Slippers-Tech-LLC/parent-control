"""Host-only fixtures for installed durable PAM boundary observations."""

from contextlib import contextmanager
import ctypes
import json
from pathlib import Path
import stat
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

import system_kiosk_admission as admission
import system_kiosk_confinement as confinement


@pytest.fixture
def worker(monkeypatch):
    monkeypatch.setattr(admission.guest, 'guard', Mock())
    monkeypatch.setattr(admission.guest, 'package_path', lambda: Path('package.deb'))
    service = Mock()
    service.exists.return_value = True
    service.lstat.return_value = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0)
    root = Mock()
    root.__truediv__ = Mock(return_value=service)
    monkeypatch.setattr(admission, 'Path', Mock(return_value=root))
    account = SimpleNamespace(pw_uid=1004, pw_name='oh-no-parent-control')
    monkeypatch.setattr(admission.pwd, 'getpwnam', Mock(return_value=account))
    pam = Mock()
    for name in ('pam_start', 'pam_acct_mgmt', 'pam_open_session', 'pam_close_session', 'pam_end'):
        getattr(pam, name).return_value = 0
    load = Mock(return_value=pam)
    monkeypatch.setattr(admission.ctypes, 'CDLL', load)
    return SimpleNamespace(service=service, root=root, pam=pam, load=load, account=account)


@pytest.mark.parametrize('callback', ['account', 'session'])
@pytest.mark.parametrize('status', [0, 7, 4])
def test_worker_invokes_one_native_callback_and_cleans_up(worker, callback, status):
    operation = worker.pam.pam_acct_mgmt if callback == 'account' else worker.pam.pam_open_session
    operation.return_value = status
    result = admission.pam_callback('systemd-user', 'kiosk', callback, durable=True)
    assert result == {'callback': callback, 'status': status,
                      'close': 0 if callback == 'session' and status == 0 else None, 'end': 0}
    worker.load.assert_called_once_with('libpam.so.0')
    start = worker.pam.pam_start.call_args.args
    assert start[:2] == (b'systemd-user', b'oh-no-parent-control')
    assert isinstance(start[3]._obj, ctypes.c_void_p)
    handle = start[3]._obj
    operation.assert_called_once_with(handle, 0)
    other = worker.pam.pam_open_session if callback == 'account' else worker.pam.pam_acct_mgmt
    other.assert_not_called()
    expected = [call.pam_start(*start),
                call.pam_acct_mgmt(handle, 0) if callback == 'account'
                else call.pam_open_session(handle, 0)]
    if callback == 'session' and status == 0:
        expected.append(call.pam_close_session(handle, 0))
    else:
        worker.pam.pam_close_session.assert_not_called()
    expected.append(call.pam_end(handle, status))
    assert worker.pam.mock_calls == expected


@pytest.mark.parametrize('failure', ['open', 'close', 'hold'])
def test_worker_always_ends_started_handle(worker, failure):
    error = RuntimeError('fixture:failure')
    if failure == 'open':
        worker.pam.pam_open_session.side_effect = error
    elif failure == 'close':
        worker.pam.pam_close_session.side_effect = error
    hold = Mock(side_effect=error) if failure == 'hold' else None
    with pytest.raises(RuntimeError, match='fixture:failure'):
        admission.pam_callback('gdm-password', 'ordinary', 'session', durable=True, hold=hold)
    handle = worker.pam.pam_start.call_args.args[3]._obj
    worker.pam.pam_end.assert_called_once_with(handle, 4 if failure == 'open' else 0)
    if failure != 'open':
        worker.pam.pam_close_session.assert_called_once_with(handle, 0)


def test_start_failure_has_no_handle_cleanup(worker):
    worker.pam.pam_start.return_value = 4
    with pytest.raises(admission.guest.GuestError, match='pam-start'):
        admission.pam_callback('gdm-password', 'kiosk', 'session', durable=True)
    worker.pam.pam_open_session.assert_not_called()
    worker.pam.pam_end.assert_not_called()


def test_worker_preserves_close_and_end_failure_statuses(worker):
    worker.pam.pam_close_session.return_value = 4
    worker.pam.pam_end.return_value = 6
    assert admission.pam_callback('systemd-user', 'ordinary', 'session', durable=True) == {
        'callback': 'session', 'status': 0, 'close': 4, 'end': 6}


def test_worker_refuses_root_target_identity(worker):
    worker.account.pw_uid = 0
    with pytest.raises(admission.guest.GuestError, match='identity'):
        admission.pam_callback('systemd-user', 'ordinary', 'session', durable=True)
    worker.load.assert_not_called()


def test_existing_account_only_interface_and_services_are_preserved(worker):
    assert admission.pam_account('sshd', 'ordinary') == {'account': 0, 'end': 0}
    worker.pam.pam_open_session.assert_not_called()
    with pytest.raises(admission.guest.GuestError, match='arguments'):
        admission.pam_callback('systemd-user', 'ordinary', 'account')


@pytest.mark.parametrize('mode,uid', [(stat.S_IFLNK | 0o777, 0),
                                   (stat.S_IFDIR | 0o755, 0),
                                   (stat.S_IFREG | 0o666, 0),
                                   (stat.S_IFREG | 0o644, 1000)])
def test_worker_refuses_unsafe_service_before_loading_pam(worker, mode, uid):
    worker.service.lstat.return_value = SimpleNamespace(st_mode=mode, st_uid=uid)
    with pytest.raises(admission.guest.GuestError, match='unsafe-service'):
        admission.pam_callback('gdm-password', 'kiosk', 'account', durable=True)
    worker.load.assert_not_called()


def test_missing_service_cannot_fall_back_to_other(worker):
    worker.service.exists.return_value = False
    worker.service.is_symlink.return_value = False
    with pytest.raises(admission.guest.GuestError, match='missing-service'):
        admission.pam_callback('gdm-password', 'kiosk', 'session', durable=True)
    worker.load.assert_not_called()


def test_dangling_service_link_is_unsafe_instead_of_vendor_fallback(worker):
    worker.service.exists.return_value = False
    worker.service.is_symlink.return_value = True
    worker.service.lstat.return_value = SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_uid=0)
    with pytest.raises(admission.guest.GuestError, match='unsafe-service'):
        admission.pam_callback('gdm-password', 'ordinary', 'session', durable=True)
    worker.load.assert_not_called()


@pytest.mark.parametrize('service,role,callback', [('sshd', 'kiosk', 'account'),
                                                 ('gdm-password', 'root', 'account'),
                                                 ('gdm-password', 'kiosk', 'authenticate')])
def test_worker_refuses_unsupported_arguments(worker, service, role, callback):
    with pytest.raises(admission.guest.GuestError, match='arguments'):
        admission.pam_callback(service, role, callback, durable=True)
    worker.load.assert_not_called()


@pytest.mark.parametrize('entry,args', [
    ('pam_callback', ('gdm-password', 'kiosk', 'account')),
    ('pam_account', ('gdm-password', 'kiosk')),
    ('probe', ('gdm-password', 'kiosk', 0, 'fixture', Mock())),
    ('durable_probe', ('gdm-password', 'kiosk', 'session', 7, 'fixture', Mock())),
    ('empty_authentication_probe', (0, 'fixture', Mock())),
])
def test_guest_guard_precedes_native_or_command_operations(monkeypatch, entry, args):
    monkeypatch.setattr(admission.guest, 'guard',
                        Mock(side_effect=admission.guest.GuestError('fixture:guard')))
    load, run, lookup = Mock(), Mock(), Mock()
    monkeypatch.setattr(admission.ctypes, 'CDLL', load)
    monkeypatch.setattr(admission.guest.commands, 'run', run)
    monkeypatch.setattr(admission.pwd, 'getpwnam', lookup)
    with pytest.raises(admission.guest.GuestError, match='fixture:guard'):
        getattr(admission, entry)(*args)
    load.assert_not_called()
    run.assert_not_called()
    lookup.assert_not_called()


@pytest.fixture
def controller(monkeypatch):
    monkeypatch.setattr(admission.guest, 'guard', Mock())
    monkeypatch.setattr(admission.guest, 'package_path', lambda: Path('package.deb'))
    run = Mock()
    monkeypatch.setattr(admission.guest.commands, 'run', run)
    return run


@pytest.mark.parametrize('service,role,expected', [
    ('unregistered', 'ordinary', 0), ('sshd', 'root', 0), ('sshd', 'kiosk', True),
])
def test_account_probe_refuses_invalid_arguments_before_command(controller, service, role, expected):
    with pytest.raises(admission.guest.GuestError, match='arguments'):
        admission.probe(service, role, expected, 'fixture', Mock())
    controller.assert_not_called()


@pytest.mark.parametrize('service', admission.DURABLE_SERVICES)
@pytest.mark.parametrize('role', admission.USERS)
@pytest.mark.parametrize('callback', ['account', 'session'])
def test_probe_exact_invocation_and_typed_result(controller, service, role, callback):
    status = admission.PAM_AUTH_ERR if role == 'kiosk' else 0
    result = {'callback': callback, 'status': status,
              'close': 0 if callback == 'session' and status == 0 else None, 'end': 0}
    controller.return_value = json.dumps(result).encode()
    record = Mock()
    admission.durable_probe(service, role, callback, status, 'fixture', record)
    controller.assert_called_once_with([
        '/usr/bin/python3', '-B', str(Path(admission.__file__).resolve()),
        'pam-durable', service, role, callback], timeout=45, merge_stderr=False)
    record.assert_called_once_with('onpc.kiosk.admission.fixture', json.dumps(result, sort_keys=True))


@pytest.mark.parametrize('change', [{'status': 0}, {'callback': 'session'}, {'close': 4}, {'end': 4}])
def test_probe_records_native_failure_before_asserting(controller, change):
    result = dict({'callback': 'account', 'status': 7, 'close': None, 'end': 0}, **change)
    controller.return_value = json.dumps(result)
    record = Mock()
    with pytest.raises(admission.guest.GuestError, match='unexpected-status:fixture'):
        admission.durable_probe('gdm-password', 'kiosk', 'account', 7, 'fixture', record)
    record.assert_called_once_with('onpc.kiosk.admission.fixture', json.dumps(result, sort_keys=True))


@pytest.mark.parametrize('result', [None, {}, {'callback': 'account', 'status': True, 'close': None, 'end': 0},
    {'callback': 'account', 'status': 7, 'close': False, 'end': 0},
    {'callback': 'account', 'status': 7, 'close': None, 'end': False},
    {'callback': 1, 'status': 7, 'close': None, 'end': 0}])
def test_probe_refuses_inexact_result_types(controller, result):
    controller.return_value = json.dumps(result)
    with pytest.raises(admission.guest.GuestError, match='worker-result'):
        admission.durable_probe('gdm-password', 'kiosk', 'account', 7, 'fixture', Mock())


def test_probe_refuses_malformed_json(controller):
    controller.return_value = b'not-json'
    with pytest.raises(admission.guest.GuestError, match='worker-result'):
        admission.durable_probe('gdm-password', 'kiosk', 'account', 7, 'fixture', Mock())


def test_rpm_kiosk_probe_uses_native_caller_after_payload_erasure(controller, monkeypatch):
    monkeypatch.setattr(admission.guest, 'package_path', lambda: Path('package.rpm'))
    entered = Mock()

    @contextmanager
    def caller(directory, service):
        entered(directory, service)
        yield ['/usr/bin/runcon', 'system_u:system_r:xdm_t:s0', '/baseline/caller', '-B']

    monkeypatch.setattr(confinement, 'pam_caller_command', caller)
    controller.return_value = json.dumps({'callback': 'session', 'status': 7, 'close': None, 'end': 0})
    admission.durable_probe('gdm-password', 'kiosk', 'session', 7, 'fixture', Mock())
    entered.assert_called_once_with(admission.guest.PAYLOAD, 'gdm-password')
    assert controller.call_args.args[0][:4] == [
        '/usr/bin/runcon', 'system_u:system_r:xdm_t:s0', '/baseline/caller', '-B']


def test_rpm_worker_refuses_wrong_native_caller_context(worker, monkeypatch):
    monkeypatch.setattr(admission.guest, 'package_path', lambda: Path('package.rpm'))
    worker.root.read_text.return_value = 'unconfined_u:unconfined_r:unconfined_t:s0'
    with pytest.raises(admission.guest.GuestError, match='caller-context'):
        admission.pam_callback('gdm-password', 'kiosk', 'session', durable=True)
    worker.load.assert_not_called()


@pytest.mark.parametrize('authenticated,accounted', [(0, 0), (0, 6), (7, None)])
def test_empty_token_worker_preserves_authentication_and_account_denial(
        worker, authenticated, accounted):
    worker.pam.pam_authenticate.return_value = authenticated
    worker.pam.pam_acct_mgmt.return_value = accounted
    result = admission.pam_callback('gdm-password', 'kiosk', 'authentication-account', durable=True)
    assert result == {'authenticate': authenticated, 'account': accounted, 'end': 0}
    handle = worker.pam.pam_start.call_args.args[3]._obj
    worker.pam.pam_authenticate.assert_called_once_with(handle, 0)
    if authenticated == 0:
        worker.pam.pam_acct_mgmt.assert_called_once_with(handle, 0)
    else:
        worker.pam.pam_acct_mgmt.assert_not_called()
    worker.pam.pam_open_session.assert_not_called()
    worker.pam.pam_end.assert_called_once_with(handle, authenticated or accounted)


@pytest.mark.parametrize('package', ['deb', 'rpm'])
@pytest.mark.parametrize('authenticated,accounted', [(0, 0), (0, 6), (7, None)])
def test_empty_token_probe_observes_exact_native_authority(
        controller, monkeypatch, package, authenticated, accounted):
    monkeypatch.setattr(admission.guest, 'package_path', lambda: Path('package.' + package))
    entered = Mock()

    @contextmanager
    def caller(directory, service):
        entered(directory, service)
        yield ['native-caller', '-B']

    monkeypatch.setattr(confinement, 'pam_caller_command', caller)
    result = {'authenticate': authenticated, 'account': accounted, 'end': 0}
    controller.return_value = json.dumps(result).encode()
    record = Mock()
    admission.empty_authentication_probe(accounted, 'authority', record,
                                         expected_authenticate=authenticated)
    prefix = ['native-caller', '-B'] if package == 'rpm' else ['/usr/bin/python3', '-B']
    controller.assert_called_once_with([
        *prefix, str(Path(admission.__file__).resolve()), 'pam-authentication-account'],
        timeout=45, merge_stderr=False)
    if package == 'rpm':
        entered.assert_called_once_with(admission.guest.PAYLOAD, 'gdm-password')
    else:
        entered.assert_not_called()
    record.assert_called_once_with('onpc.kiosk.admission.authority', json.dumps(result, sort_keys=True))


@pytest.mark.parametrize('result', [
    {'authenticate': 0, 'account': 0, 'end': 0},
    {'authenticate': 7, 'account': 6, 'end': 0},
    {'authenticate': 7, 'account': None, 'end': 4},
    {'authenticate': True, 'account': None, 'end': 0},
    {'authenticate': 7, 'account': None, 'end': False},
])
def test_empty_token_probe_never_accepts_wrong_authority_or_teardown(controller, result):
    controller.return_value = json.dumps(result)
    with pytest.raises(admission.guest.GuestError, match='(unexpected-status|worker-result)'):
        admission.empty_authentication_probe(None, 'denied', Mock(), expected_authenticate=7)


@pytest.mark.parametrize('authenticated,accounted', [(True, None), (0, None), (7, 0), (0, False)])
def test_empty_token_probe_rejects_invalid_expectations_before_command(
        controller, authenticated, accounted):
    with pytest.raises(admission.guest.GuestError, match='arguments'):
        admission.empty_authentication_probe(accounted, 'invalid', Mock(),
                                             expected_authenticate=authenticated)
    controller.assert_not_called()
