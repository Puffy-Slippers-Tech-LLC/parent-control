"""Package mutations require an owned VM and the exact transferred artifact."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

import system_guest as guest
import guest_install_recipe


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
