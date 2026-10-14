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
                                 'exercise_live_refusals',
                                 'verify_removed', 'password_login_health',
                                 'verify_active_kiosk_refusal'])
def test_guard_refusal_precedes_removal_actions(monkeypatch, entry):
    monkeypatch.setattr(removal.guest, 'guard', Mock(side_effect=removal.guest.GuestError('identity')))
    diagnostics = Mock()
    monkeypatch.setattr(removal.guest, 'enable_diagnostics', diagnostics)
    commands = Mock()
    monkeypatch.setattr(removal.guest, 'commands', commands)
    with pytest.raises(removal.guest.GuestError, match='identity'):
        getattr(removal, entry)(Mock(), {}) if entry == 'verify_active_kiosk_refusal' else getattr(removal, entry)(Mock())
    diagnostics.assert_not_called()
    commands.run.assert_not_called()


@pytest.mark.parametrize('arguments', [[], ['remove'], ['exercise-live-refusals', 'extra']])
def test_diagnostic_rejects_arguments_before_guest_actions(monkeypatch, arguments):
    exercise = Mock()
    monkeypatch.setattr(removal, 'exercise_live_refusals', exercise)
    with pytest.raises(removal.guest.GuestError, match='diagnostic-arguments'):
        removal.main(arguments)
    exercise.assert_not_called()


def test_diagnostic_route_guard_precedes_fixture_setup(monkeypatch):
    monkeypatch.setattr(removal.guest, 'guard', Mock(
        side_effect=removal.guest.GuestError('identity')))
    provision = Mock()
    monkeypatch.setattr(removal, 'provision_native', provision)
    with pytest.raises(removal.guest.GuestError, match='identity'):
        removal.main(['exercise-live-refusals'])
    provision.assert_not_called()


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_diagnostic_runs_only_finite_refusal_recovery(monkeypatch, capsys, package_format):
    accounts = {'parent': 1003, 'child': 1004, 'other': 1005}
    events = []
    monkeypatch.setattr(removal.guest, 'guard', Mock())
    monkeypatch.setattr(removal.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.' + package_format))
    monkeypatch.setattr(removal, 'provision_native', lambda: accounts)
    monkeypatch.setattr(removal, 'account_digest', lambda uid: str(uid))
    monkeypatch.setattr(removal, 'configure_restrictions',
                        lambda current: events.append(('configure', current)))
    def refuse(*args, record):
        assert callable(record)
        events.append(args)
    monkeypatch.setattr(removal, 'refuse_foreign_integration', refuse)
    commands, install, save = Mock(), Mock(), Mock()
    monkeypatch.setattr(removal.guest, 'commands', commands)
    monkeypatch.setattr(removal.guest, 'install_package', install)
    monkeypatch.setattr(removal, 'save_state', save)
    monkeypatch.setattr(removal.sys, 'argv', ['system_removal.py', 'exercise-live-refusals'])
    assert removal.main() == 0
    hook = '/etc/gdm/PreSession/Default' if package_format == 'rpm' else '/etc/gdm3/PreSession/Default'
    assert events == [('configure', accounts),
                      (accounts, '1004', '1005', 'hook', Path(hook)),
                      (accounts, '1004', '1005', 'pam', Path('/etc/pam.d/gdm-password'))]
    assert [json.loads(line) for line in capsys.readouterr().out.splitlines()] == [
        {'property': 'onpc.removal.' + category + '-refusal-retry',
         'value': 'foreign-edit-refused; payload-and-policy-preserved'}
        for category in ('hook', 'pam')]
    commands.run.assert_not_called()
    install.assert_not_called()
    save.assert_not_called()


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
    ('deb', 'oh-no-parent-control\tpn ', True),
    ('deb', 'oh-no-parent-control\tii ', False),
    ('deb', 'oh-no-parent-control\tiF ', False),
    ('deb', 'oh-no-parent-control\tiH ', False),
    ('deb', 'oh-no-parent-control\tiU ', False),
    ('deb', 'oh-no-parent-control\tiW ', False),
    ('deb', 'oh-no-parent-control\tit ', False),
    ('deb', 'oh-no-parent-control\tiiR', False),
    ('deb', 'oh-no-parent-control\t', False),
    ('deb', 'oh-no-parent-control', False),
    ('deb', 'oh-no-parent-control\ti?', False),
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
    monkeypatch.setattr(removal.guest, 'Path', path)
    path('/etc/pam.d').mkdir(parents=True)
    path('/usr/lib/pam.d').mkdir(parents=True)
    path('/etc/pam.d/gdm-password').write_bytes(b'auth required pam_unix.so\n')
    path('/usr/lib/pam.d/systemd-user').write_bytes(b'session required pam_systemd.so\n')
    for name in ('/etc/pam.d/gdm-password', '/usr/lib/pam.d/systemd-user'):
        path(name).chmod(0o644)
    fstat = os.fstat
    def root_info(descriptor):
        info = fstat(descriptor)
        return SimpleNamespace(st_uid=0, st_gid=0, st_mode=info.st_mode,
                               st_nlink=info.st_nlink, st_size=info.st_size)
    monkeypatch.setattr(removal.guest.os, 'fstat', root_info)
    path('/var/log/oh-no-parent-control').mkdir(parents=True)
    monkeypatch.setattr(removal.guest, 'guard', Mock())
    monkeypatch.setattr(removal, 'package_absent', lambda: True)
    monkeypatch.setattr(removal, 'preference_digest', lambda uid: 'preferences')
    monkeypatch.setattr(removal, 'account_state', lambda uid: (None, 0, 0, [0, 0], [False, []]))
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
             'preferences': 'preferences', 'other': removal.account_digest(1005),
             'other_policy': removal.account_digest(1005, include_preferences=False),
             'other_extensions': [[], []],
             'kiosk_name': removal.PRODUCT, 'kiosk_home': '/home/' + removal.PRODUCT,
             'hook': '/etc/gdm/PreSession/Default', 'authselect': 'local with-fingerprint',
             'pam_services': removal.guest.pam_service_state(),
             'payload': ['/usr/libexec/oh-no-parent-control-broker', removal.DEBIAN_NOTICE]}
    return state, properties, path, launch


@pytest.mark.parametrize('service', ['gdm-password', 'systemd-user'])
@pytest.mark.parametrize('fault', ['bytes', 'disposition', 'mode'])
@pytest.mark.parametrize('purged', [False, True])
def test_removed_pam_requires_original_bytes_mode_and_disposition(
        removed_machine, service, fault, purged):
    state, _, path, _ = removed_machine
    local = path('/etc/pam.d/' + service)
    vendor = path('/usr/lib/pam.d/' + service)
    active = local if local.exists() else vendor
    if purged:
        path('/var/log/oh-no-parent-control').rmdir()
    if fault == 'bytes':
        # No product reference remains, but the original bytes were changed.
        active.write_bytes(active.read_bytes() + b'# harmless-looking edit\n')
    elif fault == 'mode':
        active.chmod(0o600)
    elif local.exists():
        vendor.write_bytes(local.read_bytes())
        vendor.chmod(0o644)
        local.unlink()
    else:
        local.write_bytes(vendor.read_bytes())
        local.chmod(0o644)
    with pytest.raises(removal.guest.GuestError, match='pam-original-not-restored'):
        removal.verify_removed(state, purged=purged)


def test_removed_pam_retains_independent_restoration_evidence(removed_machine):
    state, _, _, _ = removed_machine
    record = Mock()
    removal.verify_removed(state, record=record)
    record.assert_called_once_with('onpc.removal.pam-restored',
                                   json.dumps(state['pam_services'], sort_keys=True))


@pytest.mark.parametrize('fault,category', [
    (None, None), ('DailyLimit', 'restrictions-remain'), ('ActiveExtension', 'restrictions-remain'),
    ('AppFilter', 'restrictions-remain'), ('payload', 'payload-remains'),
    ('hook', 'integration-remains'), ('baseline', 'integration-remains'),
    ('snapshot', 'integration-remains'), ('authselect-profile', 'integration-remains'),
    ('confinement-state', 'integration-remains'), ('confinement-policy', 'kiosk-policy-remains'),
    ('confinement-marker', 'integration-remains'), ('pam-barrier', 'pam-barrier-remains'),
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
             'confinement-state': '/var/lib/oh-no-parent-control/kiosk-confinement.json',
             'confinement-marker': '/var/lib/oh-no-parent-control/kiosk-confinement-removing',
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
    if fault == 'pam-barrier':
        path('/etc/pam.d/systemd-user').write_text(
            '# Oh No Parent Control removal admission barrier\n'
            'session requisite pam_succeed_if.so quiet user != oh-no-parent-control\n')
    if fault in ('extension', 'other-extension'):
        target_uid = state['accounts']['child' if fault == 'extension' else 'other']
        monkeypatch.setattr(removal, 'extension_lists', lambda uid: (
            [[], [removal.EXTENSION]] if uid == target_uid else [[], []]))
    if fault in ('authselect', 'selinux'):
        native_run = removal.guest.run
        monkeypatch.setattr(removal.guest, 'run', lambda argv: (
            'wrong' if argv[0] == ('authselect' if fault == 'authselect' else 'getenforce')
            else native_run(argv)))
    if fault == 'confinement-policy':
        native_run = removal.guest.run
        monkeypatch.setattr(removal.guest, 'run', lambda argv: (
            'onpc-kiosk 1.0\n' if argv[0] == 'semodule' else native_run(argv)))
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


@pytest.mark.parametrize('states,fault', [
    (['inactive'], None), (['failed'], None),
    (['active', 'deactivating', 'inactive'], None),
    (['active'], 'deadline'), (['unknown'], 'state'), (['inactive'], 'identity'),
])
def test_kiosk_logout_settles_read_only_before_owned_manager_start(monkeypatch, states, fault):
    account = SimpleNamespace(pw_uid=1007)
    guard, sleep = Mock(), Mock()
    monkeypatch.setattr(removal.guest, 'guard', guard)
    monkeypatch.setattr(removal.pwd, 'getpwnam', lambda name:
                        SimpleNamespace(pw_uid=9999) if fault == 'identity' else account)
    run = Mock(side_effect=states)
    monkeypatch.setattr(removal.guest, 'run', run)
    monkeypatch.setattr(removal.time, 'sleep', sleep)
    monkeypatch.setattr(removal.time, 'monotonic', Mock(side_effect=[0, 75] if fault else [0, 1, 2]))
    if fault:
        with pytest.raises(removal.guest.GuestError, match=(
                'kiosk-identity-changed' if fault == 'identity' else 'kiosk-manager-already-active')):
            removal.wait_kiosk_inactive(account)
    else:
        removal.wait_kiosk_inactive(account)
        assert run.call_count == len(states)
        assert sleep.call_count == len(states) - 1
    assert all(call.args == (['systemctl', 'show', '--value', '--property=ActiveState',
                             'user@1007.service'],) for call in run.call_args_list)
    if fault == 'identity':
        run.assert_not_called()
    if fault:
        sleep.assert_not_called()


@pytest.mark.parametrize('package_format,status,fault', [
    ('deb', 'install ok installed', None),
    ('deb', 'install ok half-configured', None),
    ('rpm', '', None),
    ('deb', 'install ok half-configured', 'payload'),
    ('deb', 'install ok half-configured', 'policy'),
    ('deb', 'install ok half-configured', 'accepted'),
    ('deb', 'unexpected', 'status'),
    ('deb', 'install ok half-configured', 'foreign-edit'),
    ('deb', 'install ok half-configured', 'retry-policy'),
    ('deb', 'install ok half-configured', 'guard'),
    ('deb', 'install ok half-configured', 'recovery-payload'),
    ('deb', 'install ok half-configured', 'unsafe-target'),
    ('deb', 'install ok half-configured', 'configure-failed'),
])
def test_foreign_refusal_checks_payload_before_resolution_and_public_retry(
        monkeypatch, package_format, status, fault):
    original = b'owned integration'
    modified = original + b'\n# onpc removal refusal fixture\n'
    contents, events = [original], []
    target = Mock()
    target.lstat.return_value = SimpleNamespace(
        st_mode=0o100644, st_uid=1004 if fault == 'unsafe-target' else 0, st_nlink=1)
    target.read_bytes.side_effect = lambda: contents[0]
    monkeypatch.setattr(removal.guest, 'guard', Mock(side_effect=(
        removal.guest.GuestError('guard') if fault == 'guard' else None)))
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.' + package_format))
    def write(path, info, expected, replacement):
        if contents[0] != expected:
            raise removal.guest.GuestError('hook-identity-changed')
        contents[0] = replacement
        events.append('resolved' if replacement == original else 'edited')
    monkeypatch.setattr(removal, 'write_hook', write)
    def native_remove(arguments, **options):
        assert arguments == removal.removal_command()
        events.append('remove')
        if fault == 'foreign-edit':
            contents[0] = b'foreign replacement'
    monkeypatch.setattr(removal.guest, 'commands', SimpleNamespace(
        run=native_remove, last_returncode=0 if fault == 'accepted' else 1))
    monkeypatch.setattr(removal, 'package_absent', lambda: False)
    def digest(uid):
        if ((fault == 'policy' and 'remove' in events) or
                (fault == 'retry-policy' and 'configure' in events)):
            return 'changed'
        return 'child' if uid == 1004 else 'other'
    monkeypatch.setattr(removal, 'account_digest', digest)
    def payload():
        assert contents[0] == modified and 'configure' not in events
        events.append('payload')
        if fault == 'payload':
            raise removal.guest.GuestError('package-file-digests')
    monkeypatch.setattr(removal.guest, 'verify_package_payload', payload)
    configured = [status == 'install ok installed' or package_format == 'rpm']
    configure_error = removal.guest.CommandError('configure-failed')
    def run(arguments):
        if arguments == ['dpkg-query', '-W', '-f=${Status}', removal.PRODUCT]:
            events.append('status')
            return status
        assert arguments == ['dpkg', '--configure', removal.PRODUCT]
        assert contents[0] == original and events.index('payload') < events.index('resolved')
        events.append('configure')
        if fault == 'configure-failed':
            raise configure_error
        configured[0] = True
    monkeypatch.setattr(removal.guest, 'run', lambda arguments, **options: run(arguments))
    install = Mock(side_effect=AssertionError('recovery must not replace live PAM payload'))
    monkeypatch.setattr(removal.guest, 'install_package', install)
    def files():
        assert configured[0] and contents[0] == original
        events.append('configured')
        if fault == 'recovery-payload':
            raise removal.guest.GuestError('package-file-digests')
    monkeypatch.setattr(removal.guest, 'verify_package_files', files)
    record = Mock()
    if fault:
        error_type = removal.guest.CommandError if fault == 'configure-failed' else removal.guest.GuestError
        with pytest.raises(error_type) as raised:
            removal.refuse_foreign_integration({'child': 1004, 'other': 1005},
                                               'child', 'other', 'pam', target, record=record)
        if fault == 'configure-failed':
            assert raised.value is configure_error
            assert events == ['edited', 'remove', 'payload', 'resolved', 'status', 'configure']
            assert not configured[0]
            record.assert_called_once_with('onpc.removal.pam-status-before-recovery', status)
    else:
        removal.refuse_foreign_integration({'child': 1004, 'other': 1005},
                                           'child', 'other', 'pam', target, record=record)
        assert events == (['edited', 'remove', 'payload', 'resolved'] +
                          (['status'] if package_format == 'deb' else []) +
                          (['configure'] if status == 'install ok half-configured' else []) +
                          ['configured'])
        assert [call.args for call in record.call_args_list] == ([
            ('onpc.removal.pam-status-before-recovery', status),
            ('onpc.removal.pam-status-after-recovery', 'install ok installed'),
        ] if package_format == 'deb' else [])
    assert contents[0] == (b'foreign replacement' if fault == 'foreign-edit' else original)
    if fault in ('payload', 'policy', 'accepted', 'status', 'foreign-edit', 'guard', 'unsafe-target'):
        assert 'configure' not in events and 'configured' not in events
    install.assert_not_called()


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
@pytest.mark.parametrize('fault', [None, 'accepted', 'erased', 'pam', 'marker', 'policy',
                                   'invocation', 'generation', 'namespace', 'uid'])
def test_active_kiosk_native_removal_preserves_policy_and_stops_only_owned_manager(
        tmp_path, monkeypatch, package_format, fault):
    import system_kiosk_confinement as confinement
    def path(value):
        return tmp_path / str(value).lstrip('/')
    monkeypatch.setattr(removal, 'Path', path)
    for name in ('/var/lib/oh-no-parent-control/kiosk-confinement.json',
                 '/etc/pam.d/gdm-password', '/etc/pam.d/systemd-user',
                 '/proc/234/root/usr/share/oh-no-parent-control/confinement/generation'):
        target = path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'owned')
    namespace = path('/proc/234/ns/mnt')
    namespace.parent.mkdir()
    namespace.symlink_to('owned-namespace')
    changed = False
    account = SimpleNamespace(pw_uid=1007)
    monkeypatch.setattr(removal.pwd, 'getpwnam', lambda name:
                        SimpleNamespace(pw_uid=9999) if changed and fault == 'uid' else account)
    monkeypatch.setattr(removal.guest, 'guard', Mock())
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.' + package_format))
    calls = []
    def run(arguments, **options):
        calls.append(arguments)
        if '--property=ActiveState' in arguments:
            return 'inactive'
        if '--property=InvocationID' in arguments:
            return 'foreign' if changed and fault == 'invocation' else 'owned'
        return ''
    monkeypatch.setattr(removal.guest, 'run', run)
    def native_remove(arguments, **options):
        nonlocal changed
        assert arguments == removal.removal_command()
        changed = True
        commands.last_returncode = 0 if fault == 'accepted' else 1
        if fault == 'pam':
            path('/etc/pam.d/gdm-password').write_bytes(b'changed')
        if fault == 'marker':
            path('/var/lib/oh-no-parent-control/kiosk-confinement-removing').write_text('removing')
        if fault == 'generation':
            path('/proc/234/root/usr/share/oh-no-parent-control/confinement/generation').write_bytes(b'foreign')
        if fault == 'namespace':
            namespace.unlink()
            namespace.symlink_to('foreign-namespace')
        return b'reason=kiosk-admissions-active'
    commands = SimpleNamespace(run=native_remove, last_returncode=1)
    monkeypatch.setattr(removal.guest, 'commands', commands)
    monkeypatch.setattr(removal, 'package_absent', lambda: fault == 'erased')
    monkeypatch.setattr(removal, 'account_digest', lambda uid:
                        'changed' if changed and fault == 'policy' else 'owned')
    verify = Mock()
    monkeypatch.setattr(removal.guest, 'verify_package_files', verify)
    monkeypatch.setattr(confinement, 'manager_pid', lambda unit: 234)
    monkeypatch.setattr(confinement, 'process_identity', lambda process: ('start', 1, ('1007',) * 4))
    monkeypatch.setattr(confinement, 'exited', lambda fd: False)
    census = Mock()
    monkeypatch.setattr(confinement, 'census', census)
    monkeypatch.setattr(confinement, 'user_command', lambda account, command: b'systemd 257')
    monkeypatch.setattr(removal.os, 'pidfd_open', lambda pid: 987)
    close = Mock()
    monkeypatch.setattr(removal.os, 'close', close)
    record = Mock()
    if fault:
        with pytest.raises(removal.guest.GuestError):
            removal.verify_active_kiosk_refusal(record, {'child': 1004, 'other': 1005})
    else:
        removal.verify_active_kiosk_refusal(record, {'child': 1004, 'other': 1005})
        verify.assert_called_once()
        assert census.call_args_list == [((), {'required_roles': ('manager',)})] * 2
        assert calls[-1][-1] == 'check-remove'
        assert [call.args[0] for call in record.call_args_list] == [
            'onpc.removal.kiosk-inactive-before-owned-start',
            'onpc.removal.active-kiosk-native-removal-refused',
            'onpc.removal.active-kiosk-drained',
        ]
    stopped = ['systemctl', 'stop', 'user@1007.service'] in calls
    assert stopped is (fault not in ('invocation', 'generation', 'namespace', 'uid'))
    close.assert_called_once_with(987)


@pytest.mark.parametrize('profile', ['other-profile (enforce)', 'onpc-kiosk-manager (enforce)'])
def test_debian_removal_requires_kiosk_profiles_unloaded(removed_machine, monkeypatch, profile):
    state, _, path, _ = removed_machine
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.deb'))
    profiles = path('/sys/kernel/security/apparmor/profiles')
    profiles.parent.mkdir(parents=True)
    profiles.write_text(profile + '\n')
    if profile.startswith('onpc-kiosk-'):
        with pytest.raises(removal.guest.GuestError, match='kiosk-policy-remains'):
            removal.verify_removed(state)
    else:
        removal.verify_removed(state)


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
             'defaults': defaults, 'other': 'other', 'other_policy': 'other',
             'purge_reinstall_boot': 'old'}
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
    monkeypatch.setattr(removal, 'account_digest', lambda uid, **options: 'other')
    monkeypatch.setattr(removal, 'Path', lambda name: tmp_path / str(name).lstrip('/'))
    monkeypatch.setattr(removal, 'account_property', lambda *args: [0, 0])
    if changed:
        with pytest.raises(removal.guest.GuestError, match='defaults-not-fresh'):
            removal.purge_reinstalled_rebooted(Mock())
    else:
        removal.purge_reinstalled_rebooted(Mock())


@pytest.fixture
def other_personal_preferences(removed_machine, monkeypatch):
    state, _, path, _ = removed_machine
    snapshot = [b'{"version":4,"personal":{"language":"fr"}}',
                1, 3600, [123, 456], [False, ['/bin/other-app']]]
    monkeypatch.setattr(removal, 'account_state', lambda uid: tuple(snapshot))
    state.update(other=removal.account_digest(state['accounts']['other']),
                 other_policy=removal.account_digest(
                     state['accounts']['other'], include_preferences=False),
                 defaults={'apps': {}, 'request': {}, 'parent_control_enabled': False},
                 removed_boot='old', purged_boot='old', purge_reinstall_boot='old')
    state_file = path('/private/removal-state.json')
    state_file.parent.mkdir()
    monkeypatch.setattr(removal, 'state_path', lambda: state_file)
    monkeypatch.setattr(removal, 'boot', lambda: 'new')
    monkeypatch.setattr(removal.guest, 'reboot_cleared', lambda: True)
    monkeypatch.setattr(removal.guest, 'reboot_requested', lambda: True)
    monkeypatch.setattr(removal.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(removal.guest, 'installed', Mock())
    monkeypatch.setattr(removal.guest, 'install_package', Mock())
    monkeypatch.setattr(removal, 'original_policy_diagnostics', Mock())
    monkeypatch.setattr(removal, 'desktop_health', Mock())
    monkeypatch.setattr(removal, 'password_login_health', Mock())
    monkeypatch.setattr(removal, 'call', Mock(return_value=[json.dumps(state['defaults'])]))
    monkeypatch.setattr(removal, 'accepted', lambda result: result)
    removal.save_state(state)
    return state, snapshot, path


@pytest.mark.parametrize('endpoint', ['removed', 'reinstalled'])
def test_ordinary_removal_and_retained_reinstall_reject_other_preferences_loss(
        other_personal_preferences, endpoint):
    state, snapshot, _ = other_personal_preferences
    snapshot[0] = None
    with pytest.raises(removal.guest.GuestError, match='other-account-changed'):
        if endpoint == 'removed':
            removal.verify_removed(state)
        else:
            removal.reinstalled_rebooted(Mock())


@pytest.mark.parametrize('endpoint', ['purged', 'purged-rebooted', 'fresh-reinstall'])
@pytest.mark.parametrize('changed', [None, 'LimitType', 'DailyLimit', 'ActiveExtension', 'AppFilter'])
def test_purge_allows_personal_preferences_deletion_but_preserves_every_native_property(
        other_personal_preferences, endpoint, changed):
    state, snapshot, path = other_personal_preferences
    # The real personal-only record participates in the original full witness.
    snapshot[0] = None
    assert removal.account_digest(state['accounts']['other']) != state['other']
    path('/var/log/oh-no-parent-control').rmdir()
    if changed:
        index, value = {'LimitType': (1, 0), 'DailyLimit': (2, 0),
                        'ActiveExtension': (3, [0, 0]), 'AppFilter': (4, [False, []])}[changed]
        snapshot[index] = value
    def verify():
        if endpoint == 'purged':
            removal.verify_removed(state, purged=True)
        elif endpoint == 'purged-rebooted':
            removal.purged_rebooted(Mock())
        else:
            removal.purge_reinstalled_rebooted(Mock())
    if changed:
        with pytest.raises(removal.guest.GuestError, match='other-account-changed'):
            verify()
    else:
        verify()


@pytest.mark.parametrize('symlink', [False, True])
def test_fresh_reinstall_rejects_replayed_other_preferences(
        other_personal_preferences, symlink):
    state, snapshot, path = other_personal_preferences
    preferences = path('/var/lib/oh-no-parent-control/preferences/1005.json')
    preferences.parent.mkdir(parents=True)
    if symlink:
        preferences.symlink_to(preferences.parent / 'missing')
        snapshot[0] = None
    else:
        preferences.write_bytes(snapshot[0])
    # Native policy remains unchanged even if old personal bytes return.
    assert removal.account_digest(1005, include_preferences=False) == state['other_policy']
    with pytest.raises(removal.guest.GuestError, match='other-preferences-remain'):
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
