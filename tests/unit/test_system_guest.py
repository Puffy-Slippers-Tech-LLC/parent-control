"""The real APT path is accessible only after the explicit VM guard passes."""

import json
from pathlib import Path
from unittest.mock import Mock, MagicMock

import pytest

import system_guest as guest


def test_probe_diagnostic_filter_does_not_change_returned_database(monkeypatch):
    commands = Mock()
    commands.run.return_value = b' full independent database\n'
    monkeypatch.setattr(guest, 'commands', commands)
    transform = Mock(return_value=b'only relevant diagnostics')
    assert guest.run(['fapolicyd-cli', '--dump-db'], diagnostic_stdout=transform) == (
        'full independent database')
    commands.run.assert_called_once_with(['fapolicyd-cli', '--dump-db'], timeout=120,
                                         merge_stderr=False, diagnostic_stdout=transform)
    transform.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'version', 'files', 'selinux', 'configuration', 'broker', 'boot-gate'])
def test_fedora_snapshot_requires_exact_rpm_and_completed_configuration(tmp_path, monkeypatch, fault):
    (tmp_path / 'package.rpm').write_bytes(b'package')
    monkeypatch.setattr(guest, 'PAYLOAD', tmp_path)
    original_path = guest.Path
    config = Mock(st_uid=0, st_mode=0o644 if fault == 'configuration' else 0o600)
    monkeypatch.setattr(guest, 'Path', lambda value: Mock(stat=Mock(return_value=config))
                        if value == '/etc/oh-no-parent-control/config.json' else original_path(value))
    guard, boot = Mock(), Mock()
    monkeypatch.setattr(guest, 'guard', guard)
    monkeypatch.setattr(guest, 'wait_for_boot', boot)
    calls = []
    def run(command):
        calls.append(command)
        if command[:2] == ['rpm', '-q']:
            return 'old' if fault == 'version' else 'oh-no-parent-control-1.2-0.1.dev.fc44.x86_64'
        if command[:2] == ['rpm', '-qp']:
            assert command[-1] == str(tmp_path / 'package.rpm')
            return 'oh-no-parent-control-1.2-0.1.dev.fc44.x86_64'
        if command[:2] == ['rpm', '--verify']:
            return 'changed packaged file' if fault == 'files' else ''
        if command == ['getenforce']:
            return 'Permissive' if fault == 'selinux' else 'Enforcing'
        if command[0] == 'busctl':
            assert command[-1] == 'ListManagedUsers'
            return ''
        assert command[:2] == ['systemctl', 'is-active']
        failed = guest.BROKER if fault == 'broker' else 'oh-no-parent-control-execution-policy-ready.service'
        return 'failed' if fault in ('broker', 'boot-gate') and command[-1] == failed else 'active'
    monkeypatch.setattr(guest, 'run', run)
    if fault:
        with pytest.raises(guest.GuestError):
            guest.verify_snapshot()
    else:
        guest.verify_snapshot()
    guard.assert_called_once()
    boot.assert_called_once()
    assert not any(command[0] in ('dnf', 'apt-get', 'dpkg', 'dpkg-query') for command in calls)


def test_fedora_installs_only_the_transferred_rpm_after_guard(tmp_path, monkeypatch):
    (tmp_path / 'package.rpm').write_bytes(b'package')
    monkeypatch.setattr(guest, 'PAYLOAD', tmp_path)
    for name in ('before_install', 'enable_diagnostics', 'guard'):
        monkeypatch.setattr(guest, name, Mock())
    run = Mock()
    monkeypatch.setattr(guest, 'run', run)
    guest.install()
    guest.guard.assert_called_once()
    run.assert_called_once_with(['dnf', 'install', '-y', str(tmp_path / 'package.rpm')], timeout=1800)


def test_fedora_guard_refusal_prevents_dnf(tmp_path, monkeypatch):
    (tmp_path / 'package.rpm').write_bytes(b'package')
    monkeypatch.setattr(guest, 'PAYLOAD', tmp_path)
    monkeypatch.setattr(guest, 'before_install', Mock())
    monkeypatch.setattr(guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(guest, 'guard', Mock(side_effect=guest.GuestError('identity-replaced')))
    run = Mock()
    monkeypatch.setattr(guest, 'run', run)
    with pytest.raises(guest.GuestError, match='identity-replaced'):
        guest.install()
    run.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'guard', 'boot', 'status', 'version', 'files'])
def test_snapshot_publication_requires_verified_installation(monkeypatch, fault):
    guard = Mock(side_effect=guest.GuestError('guard') if fault == 'guard' else None)
    boot = Mock(side_effect=guest.GuestError('boot') if fault == 'boot' else None)
    calls = []
    def run(command):
        calls.append(command)
        if command[0] == 'dpkg-deb':
            return '1.1'
        if command[0] == 'dpkg':
            return 'changed packaged file' if fault == 'files' else ''
        if '-f=${Status}' in command:
            return 'unpacked' if fault == 'status' else 'install ok installed'
        assert '-f=${Version}' in command
        return 'old version' if fault == 'version' else '1.1'
    monkeypatch.setattr(guest, 'guard', guard)
    monkeypatch.setattr(guest, 'wait_for_boot', boot)
    monkeypatch.setattr(guest, 'run', run)
    if fault:
        with pytest.raises(guest.GuestError):
            guest.verify_snapshot()
    else:
        guest.verify_snapshot()
    guard.assert_called_once()
    if fault == 'guard':
        boot.assert_not_called()
    else:
        boot.assert_called_once()
    if fault in ('guard', 'boot'):
        assert calls == []
    assert all(command[0] != 'apt-get' for command in calls)


@pytest.mark.parametrize('fault', [None, 'hostname', 'record'])
def test_hostname_comes_from_verified_preparation_record(tmp_path, monkeypatch, fault):
    baseline = tmp_path / 'prepared.json'
    baseline.write_text(json.dumps({'guest': {'hostname': 'custom-test-vm'}}))
    monkeypatch.setattr(guest, 'BASELINE', baseline)
    expected = guest.sha(baseline)
    if fault == 'record':
        baseline.write_text(json.dumps({'guest': {'hostname': 'changed-vm'}}))
    hostname = 'old-vm' if fault == 'hostname' else 'custom-test-vm'
    if fault:
        category = 'hostname' if fault == 'hostname' else 'preparation-digest'
        with pytest.raises(guest.GuestError, match=category):
            guest.check_prepared_hostname(expected, hostname)
    else:
        guest.check_prepared_hostname(expected, hostname)


@pytest.mark.parametrize('path,group', [
    ('/usr/share/applications/com.puffyslippers.OhNoParentControl.Parent.desktop', 'sudo'),
    ('/usr/share/oh-no-parent-control/99-oh-no-parent-control-allow.rules', 'root'),
    ('/usr/share/polkit-1/rules.d/00-oh-no-parent-control-session.rules', 'root'),
    ('/usr/libexec/oh-no-parent-control-broker', 'root'),
    ('/unrelated/com.puffyslippers.OhNoParentControl.Parent.desktop', 'root'),
])
@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_installed_groups_match_exact_maintainer_and_dependency_paths(monkeypatch, path, group, package_format):
    monkeypatch.setattr(guest, 'package_path', lambda: Path('package.' + package_format))
    lookup = Mock(return_value=Mock(gr_gid=42))
    monkeypatch.setattr(guest.grp, 'getgrnam', lookup)
    assert guest.installed_group(Path(path)) == 42
    lookup.assert_called_once_with('wheel' if group == 'sudo' and package_format == 'rpm' else group)


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
@pytest.mark.parametrize('fault', [None, 'auth', 'account', 'order', 'obsolete', 'profile'])
def test_installed_pam_checks_each_platform_stack(tmp_path, monkeypatch, package_format, fault):
    monkeypatch.setattr(guest, 'package_path', lambda: Path('package.' + package_format))
    monkeypatch.setattr(guest, 'Path', lambda *parts: tmp_path / Path(*parts).relative_to('/'))
    pam = tmp_path / 'etc/pam.d'
    pam.mkdir(parents=True)
    auth = '' if fault == 'auth' else 'auth required pam_oh_no_parent_control.so\n'
    account = ('account required pam_malcontent.so\n' if fault != 'account' else '')
    cap = 'account required pam_oh_no_parent_control.so\n'
    account = cap + account if fault == 'order' else account + cap
    session = 'session optional oh-no-parent-control-clear-session-runtime-max\n' if fault == 'obsolete' else ''
    if package_format == 'rpm':
        for name in ('system-auth', 'password-auth', 'fingerprint-auth', 'smartcard-auth'):
            (pam / name).write_text(auth + account + session)
    else:
        for name, contents in (('common-auth', auth), ('common-account', account), ('common-session', session)):
            (pam / name).write_text(contents)
    run = Mock(side_effect=['', '' if fault == 'profile' else 'custom/oh-no-parent-control with-faillock'])
    monkeypatch.setattr(guest, 'run', run)
    if fault and not (fault == 'profile' and package_format == 'deb'):
        with pytest.raises(guest.GuestError):
            guest.verify_pam()
    else:
        guest.verify_pam()
    assert run.call_count == (2 if package_format == 'rpm' else 0)


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
@pytest.mark.parametrize('state', ['absent', 'requested', 'malformed'])
def test_reboot_marker_requires_platform_request_and_removal(tmp_path, monkeypatch, package_format, state):
    monkeypatch.setattr(guest, 'package_path', lambda: Path('package.' + package_format))
    monkeypatch.setattr(guest, 'Path', lambda value: tmp_path / Path(value).name)
    if state != 'absent':
        if package_format == 'rpm':
            (tmp_path / 'oh-no-parent-control-reboot-required').write_text(
                'reboot\n' if state == 'requested' else 'invalid\n')
        else:
            (tmp_path / 'reboot-required').touch()
            (tmp_path / 'reboot-required.pkgs').write_text(
                'oh-no-parent-control\n' if state == 'requested' else 'another-package\n')
    assert guest.reboot_requested() == (state == 'requested')
    assert guest.reboot_cleared() == (state == 'absent' or package_format == 'deb' and state == 'malformed')


def test_activation_uses_allowed_public_method_without_logging_account_reply(monkeypatch):
    run = Mock(side_effect=['', 'u 1', 'active', ''])
    monkeypatch.setattr(guest, 'run', run)
    guest.activate_broker()
    assert run.call_args_list[0].args[0] == ['systemctl', 'stop', guest.BROKER]
    assert 'StartServiceByName' in run.call_args_list[1].args[0]
    assert run.call_args.args[0] == [
        'busctl', '--system', '--quiet', 'call', guest.BUS,
        '/com/puffyslippers/OhNoParentControl1', guest.BUS, 'ListManagedUsers']


def test_failed_broker_activation_is_not_retried(monkeypatch):
    run = Mock(side_effect=['', guest.CommandError('activation-failed')])
    monkeypatch.setattr(guest, 'run', run)
    with pytest.raises(guest.CommandError, match='activation-failed'):
        guest.activate_broker()
    assert run.call_count == 2


def test_before_reboot_activation_checks_gate_without_policy_success(monkeypatch):
    run = Mock(side_effect=['', 'u 1', 'active'])
    gate = Mock()
    monkeypatch.setattr(guest, 'run', run)
    monkeypatch.setattr(guest, 'verify_reboot_gate', gate)
    guest.activate_broker(reboot_required=True)
    assert run.call_count == 3
    gate.assert_called_once_with()


@pytest.mark.parametrize('reboot_required,fault', [(True, None), (True, 'created'),
    (True, 'modified'), (True, 'deleted'), (False, None), (False, 'missing')])
def test_installed_policy_checks_follow_explicit_reboot_phase(
        tmp_path, monkeypatch, reboot_required, fault):
    monkeypatch.setattr(guest, 'PAYLOAD', tmp_path)
    (tmp_path / 'installed-files.json').write_text('[]')
    monkeypatch.setattr(guest, 'wait_for_boot', Mock())
    monkeypatch.setattr(guest, 'verify_package_files', Mock())
    monkeypatch.setattr(guest, 'package_path', lambda: Path('package.deb'))
    monkeypatch.setattr(guest, 'verify_pam', Mock())
    path = MagicMock()
    path.stat.return_value = Mock(st_uid=0, st_mode=0o600)
    path.is_file.return_value = True
    rules = Mock()
    rules.stat.return_value = Mock(st_uid=0)
    rules.is_file.return_value = fault != 'missing'
    monkeypatch.setattr(guest, 'Path', lambda value: rules if value.endswith(
        '/89-oh-no-parent-control.rules') else path)
    monkeypatch.setattr(guest.ET, 'parse', Mock())
    monkeypatch.setattr(guest, 'run', Mock(return_value='active'))
    activation = Mock()
    monkeypatch.setattr(guest, 'activate_broker', activation)
    before = None if fault == 'created' else 'original-policy'
    after = {'created': 'new-policy', 'modified': 'changed-policy', 'deleted': None}.get(fault, before)
    state = Mock(side_effect=[before, after])
    monkeypatch.setattr(guest, 'execution_rule_state', state)
    if fault:
        with pytest.raises(guest.GuestError, match=(
                'policy-changed-before-reboot' if reboot_required else 'generated-execution-rules')):
            guest.installed(reboot_required=reboot_required)
    else:
        guest.installed(reboot_required=reboot_required)
    activation.assert_called_once_with(reboot_required=reboot_required)
    assert state.call_count == (2 if reboot_required else 0)


@pytest.mark.parametrize('reply', ['reboot', 'other-error', 'transport-error', 'success'])
def test_reboot_gate_requires_exact_dbus_error(monkeypatch, reply):
    from gi.repository import Gio, GLib
    connection = Mock()
    connection.call_sync.side_effect = None if reply == 'success' else GLib.Error('failure')
    monkeypatch.setattr(Gio, 'bus_get_sync', Mock(return_value=connection))
    error_name = {'reboot': guest.BUS + '.Error.RebootRequired',
                  'other-error': guest.BUS + '.Error.NotAuthorized'}.get(reply)
    monkeypatch.setattr(Gio.DBusError, 'get_remote_error', Mock(return_value=error_name))
    if reply == 'reboot':
        guest.verify_reboot_gate()
    else:
        with pytest.raises(guest.GuestError, match='broker-'):
            guest.verify_reboot_gate()
    Gio.bus_get_sync.assert_called_once_with(Gio.BusType.SYSTEM, None)
    connection.call_sync.assert_called_once()
    call = connection.call_sync.call_args.args
    assert call[:5] == (guest.BUS, '/com/puffyslippers/OhNoParentControl1', guest.BUS,
                       'ListManagedUsers', None)
    assert call[5].dup_string() == '(a(uss))'
    assert call[6:] == (Gio.DBusCallFlags.NONE, 30000, None)


@pytest.mark.parametrize('status,state', [(0, b'running\n'), (1, b'degraded\n')])
def test_boot_wait_accepts_terminal_states_before_service_assertions(monkeypatch, status, state):
    commands = Mock(last_returncode=status)
    commands.run.return_value = state
    monkeypatch.setattr(guest, 'commands', commands)
    guest.wait_for_boot()
    commands.run.assert_called_once_with(
        ['systemctl', 'is-system-running', '--wait'], timeout=600,
        check=False, merge_stderr=False)


@pytest.mark.parametrize('status,state', [(1, b'starting'), (1, b'maintenance'),
                                         (1, b'stopping'), (2, b'degraded'), (1, b'running')])
def test_incomplete_or_failed_boot_prevents_installed_assertions(monkeypatch, status, state):
    commands = Mock(last_returncode=status)
    commands.run.return_value = state
    monkeypatch.setattr(guest, 'commands', commands)
    run = Mock()
    monkeypatch.setattr(guest, 'run', run)
    with pytest.raises(guest.GuestError, match='boot-not-complete'):
        guest.installed()
    commands.run.assert_called_once()
    run.assert_not_called()


def test_boot_wait_timeout_is_terminal_without_assertion_retry(monkeypatch):
    commands = Mock()
    commands.run.side_effect = guest.CommandError('command:timeout:systemctl')
    monkeypatch.setattr(guest, 'commands', commands)
    run = Mock()
    monkeypatch.setattr(guest, 'run', run)
    with pytest.raises(guest.CommandError, match='command:timeout:systemctl'):
        guest.installed()
    commands.run.assert_called_once()
    run.assert_not_called()


def test_install_guard_failure_prevents_apt_and_diagnostic_writes(monkeypatch):
    monkeypatch.setattr(guest, 'before_install', Mock(side_effect=guest.GuestError('guard-refused')))
    run, enable = Mock(), Mock()
    monkeypatch.setattr(guest, 'run', run)
    monkeypatch.setattr(guest, 'enable_diagnostics', enable)
    with pytest.raises(guest.GuestError):
        guest.install()
    run.assert_not_called()
    enable.assert_not_called()


def test_guard_is_rechecked_after_dependency_refresh_before_package_install(monkeypatch):
    monkeypatch.setattr(guest, 'before_install', Mock())
    monkeypatch.setattr(guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(guest, 'guard', Mock(side_effect=guest.GuestError('identity-replaced')))
    monkeypatch.setattr(guest.os, 'environ', {})
    run = Mock()
    monkeypatch.setattr(guest, 'run', run)
    with pytest.raises(guest.GuestError):
        guest.install()
    assert run.call_count == 1
    assert run.call_args.args[0] == ['apt-get', 'update']


def test_apt_installs_only_the_exact_transferred_debian_artifact(monkeypatch):
    for name in ('before_install', 'enable_diagnostics', 'guard'):
        monkeypatch.setattr(guest, name, Mock())
    monkeypatch.setattr(guest.os, 'environ', {})
    run = Mock()
    monkeypatch.setattr(guest, 'run', run)
    guest.install()
    assert run.call_args.args[0] == [
        'apt-get', '-o', 'DPkg::Lock::Timeout=120', 'install', '--no-install-recommends',
        '-y', str(guest.PAYLOAD / 'package.deb')]
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


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
@pytest.mark.parametrize('fault', [None, 'digest', 'version', 'files'])
def test_previous_install_verifies_exact_platform_artifact(tmp_path, monkeypatch, package_format, fault):
    package = tmp_path / ('package.' + package_format)
    package.write_bytes(b'current')
    previous = tmp_path / ('previous-package.' + package_format)
    previous.write_bytes(b'previous')
    digest = guest.sha(previous)
    (tmp_path / 'previous-inputs.json').write_text(json.dumps({
        'sha256': 'a' * 64 if fault == 'digest' else digest}))
    monkeypatch.setattr(guest, 'PAYLOAD', tmp_path)
    monkeypatch.setattr(guest, 'before_install', Mock())
    monkeypatch.setattr(guest, 'enable_diagnostics', Mock())
    guard = Mock()
    monkeypatch.setattr(guest, 'guard', guard)
    calls = []
    def run(command, **options):
        calls.append(command)
        if command[0] in ('apt-get', 'dnf'):
            return ''
        if command == ['getenforce']:
            return 'Enforcing'
        if '--verify' in command:
            return 'changed-file' if fault == 'files' else ''
        if '-f=${Status}' in command:
            return 'install ok installed'
        if command[0] == 'dpkg-deb' or command[-1] == str(previous):
            return 'old-identity'
        return 'wrong-identity' if fault == 'version' else 'old-identity'
    monkeypatch.setattr(guest, 'run', run)
    if fault:
        with pytest.raises(guest.GuestError, match='previous-package-'):
            guest.install_previous()
        assert not (tmp_path / 'results/previous-install.json').exists()
    else:
        guest.install_previous()
        receipt = json.loads((tmp_path / 'results/previous-install.json').read_text())
        assert receipt['previous_package_sha256'] == digest and receipt['payload_verified']
    if fault == 'digest':
        assert calls == []
        guard.assert_not_called()
    else:
        guard.assert_called_once_with()
        transactions = [c for c in calls if c[0] in ('apt-get', 'dnf') and str(previous) in c]
        assert len(transactions) == 1
        assert transactions[0][0] == ('dnf' if package_format == 'rpm' else 'apt-get')


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
@pytest.mark.parametrize('same_version', [False, True])
@pytest.mark.parametrize('fault', [None, 'old-marker', 'old-files', 'old-version', 'digest',
                                   'guard', 'new-files', 'new-version', 'new-marker'])
def test_upgrade_preserves_reboot_and_payload_guards_on_both_platforms(
        tmp_path, monkeypatch, package_format, same_version, fault):
    package = tmp_path / ('package.' + package_format)
    package.write_bytes(b'current')
    previous = tmp_path / ('previous-package.' + package_format)
    previous.write_bytes(b'previous')
    digest = guest.sha(previous)
    marker = {'package_sha256': guest.sha(package), 'baseline_sha256': 'b' * 64}
    (tmp_path / 'results').mkdir()
    (tmp_path / 'results/previous-install.json').write_text(json.dumps({
        'boot': 'previous-boot', 'previous_package_sha256': 'a' * 64 if fault == 'digest' else digest}))
    monkeypatch.setattr(guest, 'PAYLOAD', tmp_path)
    monkeypatch.setattr(guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(guest, 'wait_for_boot', Mock())
    monkeypatch.setattr(guest, 'guard', Mock(side_effect=[marker,
        guest.GuestError('guard-replaced') if fault == 'guard' else marker]))
    monkeypatch.setattr(guest, 'reboot_cleared', lambda: fault != 'old-marker')
    monkeypatch.setattr(guest, 'reboot_requested', lambda: fault != 'new-marker')
    new_identity = 'old-identity' if same_version else 'new-identity'
    calls, installed = [], False
    def run(command, **options):
        nonlocal installed
        calls.append(command)
        if command[0] in ('apt-get', 'dnf'):
            installed = True
            return ''
        if command == ['getenforce']:
            return 'Enforcing'
        if '--verify' in command:
            return 'changed-file' if fault == ('new-files' if installed else 'old-files') else ''
        if '-f=${Status}' in command:
            return 'install ok installed'
        artifact = command[2] if command[0] == 'dpkg-deb' else command[-1]
        if artifact == str(previous):
            return 'old-identity'
        if artifact == str(package):
            return new_identity
        if fault == ('new-version' if installed else 'old-version'):
            return 'wrong-identity'
        return new_identity if installed else 'old-identity'
    monkeypatch.setattr(guest, 'run', run)
    if fault:
        with pytest.raises(guest.GuestError):
            guest.upgrade()
        assert not (tmp_path / 'results/update-activation.json').exists()
    else:
        guest.upgrade()
        receipt = json.loads((tmp_path / 'results/update-activation.json').read_text())
        assert receipt['same_version_reinstall'] == same_version
        assert receipt['previous_package_sha256'] == digest
        assert receipt['package_sha256'] == marker['package_sha256']
        assert receipt['old_package_reboot_observed'] and receipt['update_requested_reboot']
    transactions = [c for c in calls if c[0] in ('apt-get', 'dnf')]
    if fault in ('old-marker', 'old-files', 'old-version', 'digest', 'guard'):
        assert transactions == []
    else:
        assert len(transactions) == 1
        assert transactions[0][-1] == str(package)
        if package_format == 'rpm':
            assert transactions[0] == ['dnf', 'reinstall' if same_version else 'install', '-y', str(package)]
            assert all(c[0] not in ('dpkg', 'dpkg-query', 'dpkg-deb', 'apt-get') for c in calls)
        else:
            assert '--reinstall' in transactions[0]
        assert guest.guard.call_count == 2


def test_rpm_package_identity_includes_epoch_release_and_architecture(monkeypatch):
    run = Mock(return_value='oh-no-parent-control-2:1.2-0.1.dev.fc44.x86_64')
    monkeypatch.setattr(guest, 'run', run)
    package = Path('previous-package.rpm')
    assert guest.package_identity(package) == run.return_value
    assert run.call_args.args[0] == ['rpm', '-qp', '--queryformat',
        '%{NAME}-%{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}', str(package)]
