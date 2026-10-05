"""Removal assertions fail closed with private files and OS-command doubles."""

import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import system_removal as removal


@pytest.mark.parametrize('entry', ['remove', 'removed_rebooted', 'reinstalled_rebooted',
                                 'purged_rebooted', 'purge_reinstalled_rebooted',
                                 'verify_removed', 'password_login_health'])
def test_guard_refusal_precedes_removal_actions(monkeypatch, entry):
    monkeypatch.setattr(removal.guest, 'guard', Mock(side_effect=removal.guest.GuestError('identity')))
    diagnostics = Mock()
    monkeypatch.setattr(removal.guest, 'enable_diagnostics', diagnostics)
    commands = Mock()
    monkeypatch.setattr(removal.guest, 'commands', commands)
    with pytest.raises(removal.guest.GuestError, match='identity'):
        getattr(removal, entry)(Mock())
    diagnostics.assert_not_called()
    commands.run.assert_not_called()


@pytest.mark.parametrize('statuses', [(0, 0), (7, 0), (0, 7)])
def test_removed_password_login_requires_authentication_and_account_acceptance(monkeypatch, statuses):
    import system_caller
    import system_session_expiry
    monkeypatch.setattr(removal.guest, 'guard', Mock())
    password = Mock()
    monkeypatch.setattr(system_caller, 'FixturePassword', Mock(return_value=password))
    probe = Mock(side_effect=statuses)
    monkeypatch.setattr(system_session_expiry, 'pam_password_status', probe)
    if statuses == (0, 0):
        removal.password_login_health(1004)
        assert probe.call_count == 2
        assert probe.call_args.kwargs == {'account_only': True}
    else:
        with pytest.raises(removal.guest.GuestError, match='password-login-unhealthy'):
            removal.password_login_health(1004)
    password.install.assert_called_once_with(1004)


@pytest.mark.parametrize('package_format,expected', [
    ('rpm', ['dnf', 'remove', '--no-autoremove', '-y', removal.PRODUCT]),
    ('deb', ['apt-get', '-o', 'DPkg::Lock::Timeout=120', 'remove', '-y', removal.PRODUCT]),
])
def test_removal_uses_native_manager_and_retains_dependencies(monkeypatch, package_format, expected):
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.' + package_format))
    assert removal.removal_command() == expected


@pytest.mark.parametrize('package_format,output,absent', [
    ('rpm', 'other\noh-no-parent-control-helper', True),
    ('rpm', 'other\noh-no-parent-control', False),
    ('deb', 'oh-no-parent-control\trc ', True),
    ('deb', 'oh-no-parent-control\tii ', False),
    ('deb', 'oh-no-parent-control-helper\tii ', True),
])
def test_package_absence_uses_exact_identity_and_debian_install_status(
    monkeypatch, package_format, output, absent,
):
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.' + package_format))
    monkeypatch.setattr(removal.guest, 'run', Mock(return_value=output))
    assert removal.package_absent() == absent


@pytest.mark.parametrize('substituted', [False, True])
def test_removal_state_stays_private_and_refuses_symlink(tmp_path, monkeypatch, substituted):
    monkeypatch.setattr(removal.guest, 'PAYLOAD', tmp_path)
    (tmp_path / 'private').mkdir(mode=0o700)
    protected = tmp_path / 'protected'
    protected.write_text('keep')
    if substituted:
        removal.state_path().symlink_to(protected)
        with pytest.raises(removal.guest.GuestError, match='state-substituted'):
            removal.save_state({'accounts': [1004]})
        assert protected.read_text() == 'keep'
    else:
        removal.save_state({'accounts': [1004]})
        assert removal.state_path() == tmp_path / 'private/removal-state.json'
        assert removal.state_path().stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('replacement', ['content', 'inode', 'symlink'])
def test_refusal_hook_restoration_never_overwrites_replacement(tmp_path, monkeypatch, replacement):
    hook = tmp_path / 'hook'
    hook.write_bytes(b'original')
    identity = hook.stat()
    # The guest guard requires root; model only file ownership in this host test.
    native_fstat = os.fstat
    monkeypatch.setattr(removal.os, 'fstat', lambda fd: SimpleNamespace(
        st_mode=native_fstat(fd).st_mode, st_uid=0, st_nlink=native_fstat(fd).st_nlink,
        st_dev=native_fstat(fd).st_dev, st_ino=native_fstat(fd).st_ino))
    removal.write_hook(hook, identity, b'original', b'modified')
    if replacement == 'content':
        hook.write_bytes(b'foreign')
    else:
        hook.rename(tmp_path / 'old-hook')
        foreign = tmp_path / 'foreign'
        foreign.write_bytes(b'foreign')
        if replacement == 'symlink':
            hook.symlink_to(foreign)
        else:
            foreign.rename(hook)
    with pytest.raises(removal.guest.GuestError, match='hook-identity-changed'):
        removal.write_hook(hook, identity, b'modified', b'original')
    assert hook.read_bytes() == b'foreign'


@pytest.mark.parametrize('raw,accepted', [
    ('@as []', True), ("['other-extension']", True), ('true', False),
    ('[42]', False), ('invalid', False),
])
def test_native_extension_reader_validates_public_list_and_user_home(monkeypatch, raw, accepted):
    monkeypatch.setattr(removal.pwd, 'getpwuid', lambda uid: SimpleNamespace(
        pw_dir='/home/fixture', pw_name='fixture'))
    monkeypatch.setattr(removal, 'Path', lambda path: Mock(
        is_symlink=Mock(return_value=False), is_dir=Mock(return_value=True),
        stat=Mock(return_value=SimpleNamespace(st_uid=1004))))
    run = Mock(return_value=raw)
    monkeypatch.setattr(removal.guest, 'run', run)
    if accepted:
        assert len(removal.extension_lists(1004)) == 2
        assert {args[0][-1] for args, _ in run.call_args_list} == {
            'enabled-extensions', 'disabled-extensions'}
        assert all(args[0][:6] == ['runuser', '-u', 'fixture', '--', 'env', '-i']
                   for args, _ in run.call_args_list)
    else:
        with pytest.raises(removal.guest.GuestError, match='extension-list-invalid'):
            removal.extension_lists(1004)


@pytest.fixture
def removed_machine(tmp_path, monkeypatch):
    def path(value):
        return tmp_path / str(value).lstrip('/')
    monkeypatch.setattr(removal, 'Path', path)
    path('/etc/pam.d').mkdir(parents=True)
    path('/var/log/oh-no-parent-control').mkdir(parents=True)
    monkeypatch.setattr(removal.guest, 'guard', Mock())
    monkeypatch.setattr(removal, 'package_absent', lambda: True)
    monkeypatch.setattr(removal, 'preference_digest', lambda uid: 'preferences')
    monkeypatch.setattr(removal, 'account_digest', lambda uid: 'other')
    monkeypatch.setattr(removal, 'extension_lists', lambda uid: [[], []])
    def missing(name):
        raise KeyError(name)
    monkeypatch.setattr(removal.pwd, 'getpwnam', missing)
    properties = {'LimitType': 0, 'DailyLimit': 0, 'ActiveExtension': [0, 0], 'AppFilter': [False, []]}
    monkeypatch.setattr(removal, 'account_property', lambda uid, interface, prop: properties[prop])
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.rpm'))
    monkeypatch.setattr(removal.guest, 'run', lambda argv: (
        'local with-fingerprint' if argv[0] == 'authselect' else
        'Enforcing' if argv[0] == 'getenforce' else 'b false'))
    launch = Mock()
    monkeypatch.setattr(removal, 'observe_launch', launch)
    state = {'accounts': {'child': 1004, 'other': 1005, 'parent': 1003},
             'preferences': 'preferences', 'other': 'other', 'other_extensions': [[], []],
             'kiosk_name': removal.PRODUCT, 'kiosk_home': '/home/' + removal.PRODUCT,
             'hook': '/etc/gdm/PreSession/Default', 'authselect': 'local with-fingerprint',
             'payload': ['/usr/libexec/oh-no-parent-control-broker', removal.DEBIAN_NOTICE]}
    return state, properties, path, launch


@pytest.mark.parametrize('fault,category', [
    (None, None), ('DailyLimit', 'restrictions-remain'), ('ActiveExtension', 'restrictions-remain'),
    ('AppFilter', 'restrictions-remain'), ('payload', 'payload-remains'),
    ('hook', 'integration-remains'), ('baseline', 'integration-remains'),
    ('snapshot', 'integration-remains'), ('authselect-profile', 'integration-remains'),
    ('dangling-trust', 'integration-remains'), ('dangling-home', 'kiosk-home-remains'),
    ('pam-module', 'pam-reference-remains'), ('pam-helper', 'pam-reference-remains'),
    ('extension', 'extension-entry-remains'), ('other-extension', 'other-extension-settings-changed'),
    ('authselect', 'authselect-not-restored'), ('selinux', 'selinux-not-enforcing'),
])
def test_removed_machine_rejects_residue_and_health_mismatches(removed_machine, monkeypatch, fault, category):
    state, properties, path, launch = removed_machine
    if fault in properties:
        properties[fault] = {'DailyLimit': 60, 'ActiveExtension': [100, 600],
                             'AppFilter': [False, ['/bin/app']]}[fault]
    files = {'payload': state['payload'][0], 'hook': state['hook'],
             'baseline': '/var/lib/oh-no-parent-control/fapolicyd-before-install/complete',
             'snapshot': '/var/lib/oh-no-parent-control/uninstall-enforcement.json',
             'authselect-profile': '/etc/authselect/custom/oh-no-parent-control/system-auth'}
    if fault in files:
        target = path(files[fault])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('residue')
    if fault in ('dangling-trust', 'dangling-home'):
        target = path('/etc/fapolicyd/trust.d/oh-no-parent-control.trust'
                      if fault == 'dangling-trust' else state['kiosk_home'])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(tmp_missing := target.parent / 'missing')
        assert not tmp_missing.exists()
    if fault in ('pam-module', 'pam-helper'):
        path('/etc/pam.d/login').write_text('auth required ' + (
            'pam_oh_no_parent_control.so' if fault == 'pam-module' else
            'pam_exec.so /usr/libexec/oh-no-parent-control-login-check'))
    if fault in ('extension', 'other-extension'):
        target_uid = state['accounts']['child' if fault == 'extension' else 'other']
        monkeypatch.setattr(removal, 'extension_lists', lambda uid: (
            [[], [removal.EXTENSION]] if uid == target_uid else [[], []]))
    if fault in ('authselect', 'selinux'):
        native_run = removal.guest.run
        monkeypatch.setattr(removal.guest, 'run', lambda argv: (
            'wrong' if argv[0] == ('authselect' if fault == 'authselect' else 'getenforce')
            else native_run(argv)))
    if category:
        with pytest.raises(removal.guest.GuestError, match=category):
            removal.verify_removed(state)
    else:
        # The retained Debian conffile is deliberately exempted from payload
        # erasure, while executable payload never receives that exception.
        notice = path(removal.DEBIAN_NOTICE)
        notice.parent.mkdir(parents=True)
        notice.write_text('retained conffile')
        removal.verify_removed(state)
        assert launch.call_args_list == [((1004, True), {}), ((1005, True), {})]


def test_pam_comments_and_inactive_backups_are_preserved(removed_machine):
    _, _, path, _ = removed_machine
    path('/etc/pam.d/login').write_text('# auth required pam_oh_no_parent_control.so\nauth required pam_unix.so\n')
    path('/etc/pam.d/login.pam-old').write_text('auth required pam_oh_no_parent_control.so\n')
    removal.verify_pam_removed()


@pytest.mark.parametrize('residue', [None, 'state', 'logs', 'symlink', 'notice'])
def test_purge_requires_all_saved_data_and_notice_payload_removed(removed_machine, residue):
    state, _, path, launch = removed_machine
    path('/var/log/oh-no-parent-control').rmdir()
    roots = {'state': '/var/lib/oh-no-parent-control', 'logs': '/var/log/oh-no-parent-control',
             'symlink': '/var/lib/oh-no-parent-control', 'notice': removal.DEBIAN_NOTICE}
    if residue:
        target = path(roots[residue])
        target.parent.mkdir(parents=True, exist_ok=True)
        if residue == 'symlink':
            target.symlink_to(target.parent / 'missing')
        elif residue == 'notice':
            target.write_text('retained conffile')
        else:
            target.mkdir()
        with pytest.raises(removal.guest.GuestError, match=(
                'payload-remains' if residue == 'notice' else 'saved-data-remains')):
            removal.verify_removed(state, purged=True)
    else:
        removal.verify_removed(state, purged=True)
        assert launch.call_count == 2


@pytest.mark.parametrize('changed', [None, 'apps', 'request', 'parent_control_enabled'])
def test_purge_reinstall_checks_fresh_defaults_and_zero_grant(monkeypatch, tmp_path, changed):
    defaults = {'apps': {}, 'request': {'kiosk_muted': True}, 'parent_control_enabled': False}
    state = {'accounts': {'child': 1004, 'other': 1005, 'parent': 1003},
             'defaults': defaults, 'other': 'other', 'purge_reinstall_boot': 'old'}
    path = tmp_path / 'state.json'
    path.write_text(json.dumps(state))
    monkeypatch.setattr(removal, 'state_path', lambda: path)
    monkeypatch.setattr(removal.guest, 'guard', Mock())
    monkeypatch.setattr(removal.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(removal.guest, 'installed', Mock())
    monkeypatch.setattr(removal.guest, 'reboot_cleared', lambda: True)
    monkeypatch.setattr(removal, 'boot', lambda: 'new')
    current = dict(defaults)
    if changed:
        current[changed] = {'apps': {'app.desktop': {}}, 'request': {'kiosk_muted': False},
                            'parent_control_enabled': True}[changed]
    monkeypatch.setattr(removal, 'call', Mock(return_value=[json.dumps(current)]))
    monkeypatch.setattr(removal, 'accepted', lambda result: result)
    monkeypatch.setattr(removal, 'account_digest', lambda uid: 'other')
    monkeypatch.setattr(removal, 'account_property', lambda *args: [0, 0])
    if changed:
        with pytest.raises(removal.guest.GuestError, match='defaults-not-fresh'):
            removal.purge_reinstalled_rebooted(Mock())
    else:
        removal.purge_reinstalled_rebooted(Mock())


def test_original_authselect_uses_recorded_profile_and_features(removed_machine):
    _, _, path, _ = removed_machine
    record = path('/var/lib/oh-no-parent-control/fedora-authselect.json')
    record.parent.mkdir(parents=True)
    record.write_text(json.dumps({'version': 1, 'original': ['sssd', 'with-fingerprint']}))
    assert removal.original_authselect() == 'sssd with-fingerprint'
    record.write_text(json.dumps({'profile': 'wrong', 'features': []}))
    with pytest.raises(removal.guest.GuestError, match='authselect-record-invalid'):
        removal.original_authselect()


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_policy_diagnostics_use_bounded_native_reads_and_keep_probe_failures(monkeypatch, package_format):
    monkeypatch.setattr(removal.guest, 'guard', Mock())
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.' + package_format))
    commands = Mock(last_returncode=1)
    monkeypatch.setattr(removal.guest, 'commands', commands)
    record = Mock()
    removal.original_policy_diagnostics(record, 'removed')
    if package_format == 'deb':
        commands.run.assert_not_called()
        record.assert_not_called()
    else:
        assert commands.run.call_count == record.call_count == 6
        assert all(call.kwargs == {'check': False, 'timeout': 30, 'merge_stderr': True}
                   for call in commands.run.call_args_list)
        assert all(call.args[1] == '1' for call in record.call_args_list)
        commands.run.reset_mock()
        with pytest.raises(removal.guest.GuestError, match='diagnostic-stage'):
            removal.original_policy_diagnostics(record, 'unknown')
        commands.run.assert_not_called()
        monkeypatch.setattr(removal.guest, 'guard', Mock(side_effect=removal.guest.GuestError('identity')))
        with pytest.raises(removal.guest.GuestError, match='identity'):
            removal.original_policy_diagnostics(record, 'removed')
        commands.run.assert_not_called()
