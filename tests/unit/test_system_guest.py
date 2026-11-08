"""Package mutations require an owned VM and the exact transferred artifact."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

import system_guest as guest
import guest_install_recipe


@pytest.fixture
def broker_fault_machine(monkeypatch, tmp_path):
    import system_graphical_expiry as expiry
    import system_kiosk_confinement as processes
    invocation = 'a' * 32
    before = f'MainPID=42\nInvocationID={invocation}\nActiveState=active'
    monkeypatch.setattr(guest, 'guard', Mock())
    run = Mock(return_value=before)
    monkeypatch.setattr(guest, 'run', run)
    monkeypatch.setattr(expiry.os, 'pidfd_open', Mock(return_value=91))
    close, send = Mock(), Mock()
    monkeypatch.setattr(expiry.os, 'close', close)
    monkeypatch.setattr(expiry.signal, 'pidfd_send_signal', send)
    monkeypatch.setattr(processes, 'process_identity', Mock(return_value=('123', 1, ('0',) * 4)))
    monkeypatch.setattr(processes, 'exited', Mock(return_value=False))
    monkeypatch.setattr(expiry, 'wait_for', Mock())
    (tmp_path / '42').mkdir()
    (tmp_path / '42/cgroup').write_text('0::/system.slice/' + guest.BROKER)
    monkeypatch.setattr(expiry, 'Path', lambda value: tmp_path if value == '/proc' else Path(value))
    return expiry, invocation, before, run, close, send


@pytest.mark.parametrize('replaced', [False, True])
@pytest.mark.parametrize('stop', [False, True])
def test_broker_fault_affects_only_the_recorded_live_invocation(broker_fault_machine, replaced, stop):
    expiry, invocation, before, run, close, send = broker_fault_machine
    after = before.replace(invocation, 'b' * 32) if replaced else before
    run.side_effect = [before, after, ''] if stop and not replaced else [before, after]
    record = Mock()
    if replaced:
        with pytest.raises(guest.GuestError, match='expiry:crash-broker-replaced'):
            expiry.fault_recorded_broker(invocation, record, stop=stop)
        send.assert_not_called()
        assert all(call.args[0][:2] != ['systemctl', 'stop'] for call in run.call_args_list)
    else:
        expiry.fault_recorded_broker(invocation, record, stop=stop)
        if stop:
            send.assert_not_called()
            assert run.call_args_list[-1].args[0] == ['systemctl', 'stop', guest.BROKER]
        else:
            send.assert_called_once_with(91, expiry.signal.SIGKILL)
    record.assert_called_once_with({'invocation': invocation, 'pid': 42, 'start': '123'})
    close.assert_called_once_with(91)


@pytest.mark.parametrize('resume', [False, True])
def test_broker_pause_and_resume_use_only_the_pinned_descriptor(broker_fault_machine, resume):
    expiry, invocation, before, run, close, send = broker_fault_machine
    identity = {'invocation': invocation, 'pid': 42, 'start': '123'}
    selected_signal = expiry.signal.SIGCONT if resume else expiry.signal.SIGSTOP
    expiry.fault_recorded_broker(invocation, Mock(), process_signal=selected_signal,
                                expected=identity if resume else None)
    send.assert_called_once_with(91, selected_signal)
    close.assert_called_once_with(91)


@pytest.mark.parametrize('original_start', ['122', None])
def test_broker_resume_requires_the_original_process_receipt(broker_fault_machine, original_start):
    expiry, invocation, before, run, close, send = broker_fault_machine
    expected = (None if original_start is None else
                {'invocation': invocation, 'pid': 42, 'start': original_start})
    with pytest.raises(guest.GuestError, match='expiry:broker-fault-(identity-changed|kind)'):
        expiry.fault_recorded_broker(invocation, Mock(), process_signal=expiry.signal.SIGCONT,
                                    expected=expected)
    send.assert_not_called()
    if expected is None:
        close.assert_not_called()
    else:
        close.assert_called_once_with(91)


def expected_install(package):
    return ['make', '--no-print-directory', '-C',
            str(Path(guest_install_recipe.__file__).resolve().parent / 'install-source'), 'install',
            'INSTALL_PACKAGE=' + str(package.resolve()),
            'APT=apt-get -o DPkg::Lock::Timeout=120 --no-install-recommends -y', 'DNF=dnf -y']


def test_fedora_installs_only_the_transferred_rpm_after_guard(tmp_path, monkeypatch):
    (tmp_path / 'package.rpm').write_bytes(b'package')
    monkeypatch.setattr(guest, 'PAYLOAD', tmp_path)
    for name in ('before_install', 'enable_diagnostics', 'guard'):
        monkeypatch.setattr(guest, name, Mock())
    # The installation helper now retains a transaction path and samples guest
    # diagnostics. Supply private command state without probing this host.
    monkeypatch.setattr(guest, 'commands', Mock(
        directory=tmp_path, sequence=1, last_returncode=1))
    for name in ('sample_install_trust', 'child_trust_inputs_diagnostic'):
        monkeypatch.setattr(guest, name, Mock())
    run = Mock()
    monkeypatch.setattr(guest, 'run', run)
    guest.install()
    guest.guard.assert_called_once()
    run.assert_called_once_with(expected_install(tmp_path / 'package.rpm'), timeout=2400)


def test_install_guard_failure_prevents_apt_and_diagnostic_writes(monkeypatch):
    monkeypatch.setattr(guest, 'before_install', Mock(side_effect=guest.GuestError('guard-refused')))
    run, enable = Mock(), Mock()
    monkeypatch.setattr(guest, 'run', run)
    monkeypatch.setattr(guest, 'enable_diagnostics', enable)
    with pytest.raises(guest.GuestError):
        guest.install()
    run.assert_not_called()
    enable.assert_not_called()


def test_guard_is_rechecked_before_make_package_install(monkeypatch):
    monkeypatch.setattr(guest, 'before_install', Mock())
    monkeypatch.setattr(guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(guest, 'guard', Mock(side_effect=guest.GuestError('identity-replaced')))
    monkeypatch.setattr(guest.os, 'environ', {})
    run = Mock()
    monkeypatch.setattr(guest, 'run', run)
    with pytest.raises(guest.GuestError):
        guest.install()
    run.assert_not_called()


def test_make_installs_only_the_exact_transferred_debian_artifact(monkeypatch, tmp_path):
    for name in ('before_install', 'enable_diagnostics', 'guard'):
        monkeypatch.setattr(guest, name, Mock())
    monkeypatch.setattr(guest.os, 'environ', {})
    monkeypatch.setattr(guest, 'commands', Mock(
        directory=tmp_path, sequence=1, last_returncode=1))
    for name in ('sample_install_trust', 'child_trust_inputs_diagnostic'):
        monkeypatch.setattr(guest, name, Mock())
    run = Mock()
    monkeypatch.setattr(guest, 'run', run)
    guest.install()
    run.assert_called_once_with(expected_install(guest.PAYLOAD / 'package.deb'), timeout=2400)
    assert guest.os.environ['DEBIAN_FRONTEND'] == 'noninteractive'


@pytest.mark.parametrize('operation', ['install_previous', 'upgrade'])
def test_update_guard_refusal_prevents_commands_and_writes(monkeypatch, operation):
    for name in ('before_install', 'guard'):
        monkeypatch.setattr(guest, name, Mock(side_effect=guest.GuestError('guard-refused')))
    run, diagnostics = Mock(), Mock()
    monkeypatch.setattr(guest, 'run', run)
    monkeypatch.setattr(guest, 'enable_diagnostics', diagnostics)
    with pytest.raises(guest.GuestError, match='guard-refused'):
        getattr(guest, operation)()
    run.assert_not_called()
    diagnostics.assert_not_called()


def test_previous_payload_digest_mismatch_prevents_apt(monkeypatch, tmp_path):
    monkeypatch.setattr(guest, 'PAYLOAD', tmp_path)
    (tmp_path / 'previous-package.deb').write_bytes(b'changed')
    (tmp_path / 'previous-inputs.json').write_text(json.dumps({'sha256': 'a' * 64}))
    for name in ('before_install', 'enable_diagnostics'):
        monkeypatch.setattr(guest, name, Mock())
    run = Mock()
    monkeypatch.setattr(guest, 'run', run)
    with pytest.raises(guest.GuestError, match='previous-package-digest'):
        guest.install_previous()
    run.assert_not_called()


def test_update_requires_old_package_reboot_before_apt(monkeypatch, tmp_path):
    monkeypatch.setattr(guest, 'PAYLOAD', tmp_path)
    (tmp_path / 'results').mkdir()
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    (tmp_path / 'results/previous-install.json').write_text(json.dumps({'boot': boot}))
    for name in ('guard', 'enable_diagnostics', 'wait_for_boot'):
        monkeypatch.setattr(guest, name, Mock())
    run = Mock()
    monkeypatch.setattr(guest, 'run', run)
    with pytest.raises(guest.GuestError, match='previous-package-reboot-not-observed'):
        guest.upgrade()
    run.assert_not_called()
    assert not (tmp_path / 'before.json').exists()


@pytest.mark.parametrize('session', ['greeter', 'ssh', 'personal', 'inactive', 'unknown'])
def test_activation_greeter_renewal_never_terminates_a_personal_session(monkeypatch, session):
    monkeypatch.setattr(guest, 'guard', Mock())
    properties = {'greeter': 'Class=greeter\nType=wayland',
                  'inactive': 'Class=greeter\nType=wayland',
                  'ssh': 'Class=user\nType=tty',
                  'personal': 'Class=user\nType=wayland'}
    calls = []
    def run(argv, **options):
        calls.append(argv)
        if argv[0] == 'loginctl':
            return '1 1000 fixture' if argv[1] == 'list-sessions' else properties.get(session, '')
        return 'inactive' if session == 'inactive' else 'active'
    monkeypatch.setattr(guest, 'run', run)
    if session in ('personal', 'inactive', 'unknown'):
        with pytest.raises(guest.GuestError):
            guest.prepare_activation_greeter()
    else:
        guest.prepare_activation_greeter()
    assert any(argv[:2] == ['systemctl', 'restart'] for argv in calls) == (session not in ('personal', 'unknown'))


@pytest.mark.parametrize('role', ['onpc-child-jordan', 'parent', 'approver', 'target'])
def test_spare_deletion_registry_refuses_protected_or_unregistered_names(monkeypatch, role):
    import system_accounts as accounts
    monkeypatch.setattr(guest, 'guard', Mock())
    run = Mock()
    monkeypatch.setattr(guest, 'run', run)
    with pytest.raises(guest.GuestError, match='deletion-fixture-scope'):
        accounts.delete_disposable_identity(1001, role, surface='spare-child')
    run.assert_not_called()


@pytest.mark.parametrize('refusal', ['replaced', 'administrator', 'active', 'unreadable-sessions'])
def test_spare_deletion_refuses_changed_identity_role_or_live_session(monkeypatch, refusal):
    from types import SimpleNamespace
    import system_accounts as accounts
    uid = 1200
    name = accounts.SPARE_CHILDREN['jordan'][0]
    monkeypatch.setattr(guest, 'guard', Mock())
    monkeypatch.setattr(accounts.pwd, 'getpwnam', lambda _: SimpleNamespace(
        pw_uid=uid + int(refusal == 'replaced')))
    monkeypatch.setattr(accounts.pwd, 'getpwuid', lambda _: SimpleNamespace(pw_name=name))
    monkeypatch.setattr(accounts, 'account_properties', lambda *_: {
        'Uid': uid, 'UserName': name, 'AccountType': int(refusal == 'administrator'),
        'LocalAccount': True, 'SystemAccount': False})
    run = Mock(return_value='3 1200 spare seat0 tty2' if refusal == 'active' else 'unreadable')
    monkeypatch.setattr(guest, 'run', run)
    redaction = Mock()
    monkeypatch.setattr(guest, 'retain_identity_for_redaction', redaction)
    with pytest.raises(guest.GuestError):
        accounts.delete_disposable_identity(uid, 'jordan', surface='spare-child')
    assert not any('DeleteUser' in call.args[0] for call in run.call_args_list)
    redaction.assert_not_called()


@pytest.mark.parametrize('refusal', ['collision', 'extra-child', 'active-baseline-child'])
def test_spare_profile_refuses_unsafe_start_before_any_account_mutation(monkeypatch, refusal):
    from types import SimpleNamespace
    import e2e_dynamic_account as fixture
    names = (*fixture.FIXED_CHILDREN, *fixture.FIXED_APPROVERS, fixture.KIOSK_USERNAME)
    if refusal == 'collision':
        names += (fixture.SPARE_CHILDREN['jordan'][0],)
    entries = [SimpleNamespace(pw_name=name, pw_uid=1200 + index) for index, name in enumerate(names)]
    monkeypatch.setattr(guest, 'guard', Mock())
    monkeypatch.setattr(fixture.pwd, 'getpwall', lambda: entries)
    monkeypatch.setattr(fixture.pwd, 'getpwnam', lambda name: next(
        entry for entry in entries if entry.pw_name == name))
    eligible = dict.fromkeys(fixture.FIXED_CHILDREN, 1200)
    if refusal == 'extra-child':
        eligible['unrelated-child'] = 1300
    monkeypatch.setattr(fixture, 'eligible_children', lambda: eligible)
    run = Mock(return_value='3 1200 child seat0 tty2')
    monkeypatch.setattr(guest, 'run', run)
    with pytest.raises(guest.GuestError):
        fixture.prepare_spare_children('two')
    assert not any('SetAccountType' in call.args[0] or 'CreateUser' in call.args[0]
                   for call in run.call_args_list)
