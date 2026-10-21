"""Removal assertions fail closed with private files and OS-command doubles."""

import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call as mock_call

import pytest

import system_removal as removal


@pytest.mark.parametrize('entry', ['remove', 'removed_rebooted', 'reinstalled_rebooted',
                                 'purged_rebooted', 'purge_reinstalled_rebooted',
                                 'exercise_live_refusals',
                                 'aborted_cleanup_rollback_retry', 'rollback_rearmed_rebooted',
                                 'rpm_posterase_recovery', 'rpm_posterase_reinstalled_rebooted',
                                 'verify_removed', 'password_login_health',
                                 'verify_active_kiosk_refusal', 'verify_inflight_admission_refusal'])
def test_guard_refusal_precedes_removal_actions(monkeypatch, entry):
    monkeypatch.setattr(removal.guest, 'guard', Mock(side_effect=removal.guest.GuestError('identity')))
    diagnostics = Mock()
    monkeypatch.setattr(removal.guest, 'enable_diagnostics', diagnostics)
    commands = Mock()
    monkeypatch.setattr(removal.guest, 'commands', commands)
    with pytest.raises(removal.guest.GuestError, match='identity'):
        if entry in ('verify_active_kiosk_refusal', 'verify_inflight_admission_refusal'):
            getattr(removal, entry)(Mock(), {})
        else:
            getattr(removal, entry)(Mock())
    diagnostics.assert_not_called()
    commands.run.assert_not_called()


@pytest.mark.parametrize('arguments', [[], ['remove'], ['exercise-live-refusals', 'extra'],
                                     ['exercise-live-finalization'],
                                     ['exercise-live-finalization', 'unknown'],
                                     ['exercise-live-finalization', 'mac-unload', 'extra'],
                                     ['exercise-live-rpm-posterase', 'extra']])
def test_diagnostic_rejects_arguments_before_guest_actions(monkeypatch, arguments):
    exercise = Mock()
    monkeypatch.setattr(removal, 'exercise_live_refusals', exercise)
    with pytest.raises(removal.guest.GuestError, match='diagnostic-arguments'):
        removal.main(arguments)
    exercise.assert_not_called()


@pytest.mark.parametrize('variant', removal.FINALIZATION_VARIANTS)
def test_live_finalization_dispatches_only_selected_shared_history(monkeypatch, capsys, variant):
    def exercise(record, selected):
        assert selected == variant
        record('selected-history', selected)
    monkeypatch.setattr(removal, 'interrupted_finalization_retry', exercise)
    unrelated = Mock()
    monkeypatch.setattr(removal, 'exercise_live_refusals', unrelated)
    assert removal.main(['exercise-live-finalization', variant]) == 0
    assert json.loads(capsys.readouterr().out) == {
        'property': 'selected-history', 'value': variant}
    unrelated.assert_not_called()


def test_live_rpm_posterase_dispatches_the_same_first_history_phase(monkeypatch, capsys):
    def exercise(record):
        record('selected-history', 'rpm-posterase')
    monkeypatch.setattr(removal, 'rpm_posterase_recovery', exercise)
    unrelated = Mock()
    monkeypatch.setattr(removal, 'exercise_live_refusals', unrelated)
    assert removal.main(['exercise-live-rpm-posterase']) == 0
    assert json.loads(capsys.readouterr().out) == {
        'property': 'selected-history', 'value': 'rpm-posterase'}
    unrelated.assert_not_called()


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
    provision = Mock(return_value=accounts)
    monkeypatch.setattr(removal, 'provision_native', provision)
    monkeypatch.setattr(removal, 'account_digest', lambda uid: str(uid))
    monkeypatch.setattr(removal, 'configure_restrictions',
                        lambda current, *, variant: events.append(('configure', current, variant)))
    def refuse(*args, record, reason):
        assert callable(record)
        events.append((*args, reason))
    monkeypatch.setattr(removal, 'refuse_foreign_integration', refuse)
    commands, install, save = Mock(), Mock(), Mock()
    monkeypatch.setattr(removal.guest, 'commands', commands)
    monkeypatch.setattr(removal.guest, 'install_package', install)
    monkeypatch.setattr(removal, 'save_state', save)
    monkeypatch.setattr(removal.sys, 'argv', ['system_removal.py', 'exercise-live-refusals'])
    assert removal.main() == 0
    native_variant = 'trusted-hard' if package_format == 'rpm' else 'command'
    provision.assert_called_once_with(native_variant)
    hook = '/etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules'
    pam = '/var/lib/oh-no-parent-control/' + (
        'fedora-authselect.json' if package_format == 'rpm' else 'malcontent-pam-before-install')
    assert events == [('configure', accounts, native_variant),
                      (accounts, '1004', '1005', 'hook', Path(hook),
                       b'system integration was modified; preserving it and refusing removal'),
                      (accounts, '1004', '1005', 'pam', Path(pam),
                       b'invalid original authselect selection' if package_format == 'rpm'
                       else b'invalid original PAM selection')]
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


@pytest.mark.parametrize('fault', ['none', 'limit', 'grant', 'filter', 'extension', 'rules', 'snapshot'])
def test_cleanup_transition_requires_positive_complete_native_clearing(tmp_path, monkeypatch, fault):
    snapshot = tmp_path / 'snapshot'
    snapshot.write_text(json.dumps({'version': 1, 'accounts': []}))
    snapshot.chmod(0o600)
    native = [0, 0, [0, 0], [False, []]]
    if fault == 'limit':
        native[0] = 1
    elif fault == 'grant':
        native[2] = [10, 600]
    elif fault == 'filter':
        native[3] = [False, ['blocked']]
    monkeypatch.setattr(removal, 'account_state', lambda uid: (b'preferences', *native))
    monkeypatch.setattr(removal, 'extension_lists', lambda uid:
                        [[removal.EXTENSION], []] if fault == 'extension' else [[], []])
    monkeypatch.setattr(removal.os.path, 'lexists', lambda path: fault == 'rules')
    native_stat = snapshot.lstat()
    wrapped = Mock(lstat=Mock(return_value=SimpleNamespace(
        st_mode=native_stat.st_mode, st_uid=0)), read_text=snapshot.read_text)
    if fault == 'snapshot':
        wrapped.lstat.side_effect = FileNotFoundError
    monkeypatch.setattr(removal, 'Path', lambda value: wrapped)
    result = removal.cleanup_transition(1004)
    assert result == ({'snapshot': {'version': 1, 'accounts': []},
                       'native': (0, 0, [0, 0], [False, []]), 'extensions': [[], []],
                       'policy_absent': list(removal.GENERATED_POLICY)} if fault == 'none' else None)


@pytest.mark.parametrize('quarantine', [False, True])
@pytest.mark.parametrize('fault', ['none', 'watcher', 'command', 'missed', 'snapshot', 'quarantine'])
def test_aborted_watcher_has_private_commands_and_always_joins(tmp_path, monkeypatch, fault, quarantine):
    events = []
    expected = {'uid': 1004}
    transaction = SimpleNamespace(directory=None, last_returncode=7)
    def run(argv, **kwargs):
        events.append('native')
        assert kwargs == {'check': False, 'timeout': 1800, 'merge_stderr': True}
        if fault == 'command':
            raise removal.guest.CommandError('native-failed')
        return b'native callback failure'
    transaction.run = run
    monkeypatch.setattr(removal.guest, 'Commands', lambda: transaction)
    monkeypatch.setattr(removal.guest, 'commands', SimpleNamespace(directory=tmp_path))
    monkeypatch.setattr(removal, 'removal_command', lambda: ['native-remove'])
    class Worker:
        def __init__(self, *, target, name):
            self.target = target
        def start(self):
            self.target()
        def is_alive(self):
            return fault != 'missed'
        def join(self):
            events.append('joined')
    monkeypatch.setattr(removal.threading, 'Thread', Worker)
    ticks = iter([0, 1, 1801])
    monkeypatch.setattr(removal.time, 'monotonic', lambda: next(ticks))
    monkeypatch.setattr(removal.time, 'sleep', lambda value: None)
    saved = {'uid': 1007, 'expires': None} if quarantine else None
    verify_quarantine = Mock(side_effect=(removal.guest.GuestError('changed-quarantine')
                                         if fault == 'quarantine' else None))
    monkeypatch.setattr(removal, 'verify_quarantine', verify_quarantine)
    def transition(uid):
        if fault == 'watcher':
            raise RuntimeError('watcher-failed')
        return {'snapshot': {'version': 1, 'accounts': [] if fault == 'snapshot' else [expected]},
                'native': [0, 0, [0, 0], [False, []]], 'extensions': [[], []],
                'policy_absent': list(removal.GENERATED_POLICY)}
    monkeypatch.setattr(removal, 'cleanup_transition', transition)
    record = Mock()
    if fault == 'none' or (fault == 'quarantine' and not quarantine):
        assert removal.observe_aborted_transaction(1004, expected, saved, record) == (
            b'native callback failure', 7)
        assert (transaction.directory / 'observed-snapshot.txt').stat().st_mode & 0o777 == 0o600
    else:
        with pytest.raises((RuntimeError, removal.guest.GuestError, removal.guest.CommandError)):
            removal.observe_aborted_transaction(1004, expected, saved, record)
    assert events == ['native', 'joined']
    assert transaction.directory.parent == tmp_path.parent
    assert transaction.directory.name.startswith('rollback-')
    if not quarantine:
        verify_quarantine.assert_not_called()


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


@pytest.mark.parametrize('variant', ['command', 'trusted-hard'])
def test_removed_pam_retains_independent_restoration_evidence(removed_machine, variant):
    state, _, _, launch = removed_machine
    state['native_variant'] = variant
    record = Mock()
    removal.verify_removed(state, record=record)
    record.assert_called_once_with('onpc.removal.pam-restored',
                                   json.dumps(state['pam_services'], sort_keys=True))
    assert launch.call_args_list == [mock_call(1004, True, variant=variant),
                                    mock_call(1005, True, variant=variant)]


@pytest.mark.parametrize('fault,category', [
    (None, None), ('DailyLimit', 'restrictions-remain'), ('ActiveExtension', 'restrictions-remain'),
    ('AppFilter', 'restrictions-remain'), ('payload', 'payload-remains'),
    ('hook', 'integration-remains'), ('baseline', 'integration-remains'),
    ('snapshot', 'integration-remains'), ('authselect-profile', 'integration-remains'),
    ('confinement-state', 'integration-remains'), ('confinement-policy', 'kiosk-policy-remains'),
    ('confinement-marker', 'integration-remains'), ('pam-barrier', 'pam-barrier-remains'),
    ('expiry-record', 'integration-remains'), ('capture-record', 'integration-remains'),
    ('capture-directory', 'integration-remains'),
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
             'expiry-record': '/var/lib/oh-no-parent-control/kiosk-configuration-account.json',
             'capture-record': '/var/lib/oh-no-parent-control/legacy-kiosk-policy.json',
             'capture-directory': '/var/lib/oh-no-parent-control/legacy-kiosk-policy/config.json',
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
        assert launch.call_args_list == [mock_call(1004, True, variant='command'),
                                        mock_call(1005, True, variant='command')]


def test_pam_comments_and_inactive_backups_are_preserved(removed_machine):
    _, _, path, _ = removed_machine
    path('/etc/pam.d/login').write_text('# auth required pam_oh_no_parent_control.so\nauth required pam_unix.so\n')
    path('/etc/pam.d/login.pam-old').write_text('auth required pam_oh_no_parent_control.so\n')
    removal.verify_pam_removed()


@pytest.mark.parametrize('states,fault', [
    (['inactive'], None), (['failed'], None),
    (['active', 'activating', 'deactivating', 'inactive'], None),
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
    monkeypatch.setattr(removal.time, 'monotonic', Mock(
        side_effect=[0, 75] if fault else [0] + [1] * len(states)))
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


def test_removal_handoff_wait_reuses_native_helper_with_existing_categories(monkeypatch):
    import system_kiosk_confinement as confinement

    wait = Mock()
    monkeypatch.setattr(confinement, 'wait_kiosk_inactive', wait)
    account = SimpleNamespace(pw_uid=1007)
    removal.wait_kiosk_inactive(account)
    wait.assert_called_once_with(account, identity_category='removal:kiosk-identity-changed',
                                active_category='removal:kiosk-manager-already-active')


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
        assert options == {'check': False, 'timeout': 1800, 'merge_stderr': True}
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
    install = Mock(side_effect=lambda: events.append('reinstall'))
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
                          (['reinstall'] if package_format == 'rpm' else []) +
                          ['configured'])
        assert [call.args for call in record.call_args_list] == ([
            ('onpc.removal.pam-status-before-recovery', status),
            ('onpc.removal.pam-status-after-recovery', 'install ok installed'),
        ] if package_format == 'deb' else [])
    assert contents[0] == (b'foreign replacement' if fault == 'foreign-edit' else original)
    if fault in ('payload', 'policy', 'accepted', 'status', 'foreign-edit', 'guard', 'unsafe-target'):
        assert 'configure' not in events and 'configured' not in events
    if package_format == 'rpm' and (fault is None or fault in ('retry-policy', 'recovery-payload')):
        install.assert_called_once_with()
    else:
        install.assert_not_called()


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
@pytest.mark.parametrize('fault', [None, 'accepted', 'erased', 'pam', 'marker', 'policy',
                                   'invocation', 'identity', 'dead', 'pid', 'uid',
                                   'record-group', 'record-bytes'])
def test_active_kiosk_native_removal_preserves_policy_and_stops_only_owned_manager(
        tmp_path, monkeypatch, package_format, fault):
    import system_kiosk_confinement as confinement
    def path(value):
        return tmp_path / str(value).lstrip('/')
    monkeypatch.setattr(removal, 'Path', path)
    for name in ('/etc/pam.d/gdm-password', '/etc/pam.d/systemd-user'):
        target = path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'owned')
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
            marker = path('/var/lib/oh-no-parent-control/kiosk-configuration-account.json')
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text('unexpected quarantine')
        return b'oh-no-parent-control: log out of the kiosk session before removal'
    commands = SimpleNamespace(run=native_remove, last_returncode=1)
    monkeypatch.setattr(removal.guest, 'commands', commands)
    monkeypatch.setattr(removal, 'package_absent', lambda: fault == 'erased')
    monkeypatch.setattr(removal, 'account_digest', lambda uid:
                        'changed' if changed and fault == 'policy' else 'owned')
    verify = Mock()
    monkeypatch.setattr(removal.guest, 'verify_package_files', verify)
    monkeypatch.setattr(confinement, 'manager_pid', lambda unit:
                        999 if changed and fault == 'pid' else 234)
    monkeypatch.setattr(confinement, 'process_identity', lambda process:
                        ('foreign' if changed and fault == 'identity' else 'start', 1, ('1007',) * 4))
    monkeypatch.setattr(confinement, 'exited', lambda fd: changed and fault == 'dead')
    preflight = Mock()
    monkeypatch.setattr(removal, 'check_remove_preflight', preflight)
    authselect = '/var/lib/oh-no-parent-control/fedora-authselect.json'
    monkeypatch.setattr(removal.grp, 'getgrnam', lambda _: SimpleNamespace(gr_gid=10))
    def records():
        return {'pam': 'changed' if changed and fault == 'pam' else 'owned',
                authselect: (0o600, 0,
                    1000 if changed and fault == 'record-group' else
                    0 if changed and package_format == 'rpm' else 10,
                    'changed' if changed and fault == 'record-bytes' else 'original')}
    monkeypatch.setattr(removal, 'admission_removal_state', records)
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
        preflight.assert_called_once_with()
        assert [call.args[0] for call in record.call_args_list] == [
            'onpc.removal.kiosk-inactive-before-owned-start',
            'onpc.removal.active-kiosk-native-removal-refused',
            'onpc.removal.active-kiosk-drained',
        ]
    stopped = ['systemctl', 'stop', 'user@1007.service'] in calls
    assert stopped is (fault not in ('invocation', 'identity', 'dead', 'pid', 'uid'))
    close.assert_called_once_with(987)


@pytest.fixture
def admission_records(tmp_path, monkeypatch):
    def path(value):
        return tmp_path / str(value).lstrip('/')
    monkeypatch.setattr(removal, 'Path', path)
    native_lstat = Path.lstat
    ownership = [0, 0]
    def lstat(target):
        fields = list(native_lstat(target))
        fields[4:6] = ownership
        return os.stat_result(fields)
    monkeypatch.setattr(Path, 'lstat', lstat)
    target = path('/var/lib/oh-no-parent-control/fapolicyd-before-install/policy')
    target.parent.mkdir(parents=True, mode=0o700)
    target.write_bytes(b'original policy')
    target.chmod(0o600)
    return path, target, ownership


@pytest.mark.parametrize('changed', ['bytes', 'mode', 'uid', 'gid', 'absent'])
def test_admission_snapshot_preserves_bytes_modes_ownership_and_absence(admission_records, changed):
    path, target, ownership = admission_records
    before = removal.admission_removal_state()
    absent = path('/var/lib/oh-no-parent-control/kiosk-confinement-removing')
    assert before[str(absent)] is None
    assert before[str(target)][:3] == (0o600, 0, 0)
    # Debian may atomically republish identical records during abort-remove.
    replacement = target.with_name('replacement')
    replacement.write_bytes(target.read_bytes())
    replacement.chmod(0o600)
    replacement.replace(target)
    assert removal.admission_removal_state() == before
    if changed == 'bytes':
        target.write_bytes(b'changed policy')
    elif changed == 'mode':
        target.chmod(0o400)
    elif changed in ('uid', 'gid'):
        ownership[changed == 'gid'] = 1
    else:
        absent.write_bytes(b'removal barrier')
        absent.chmod(0o600)
    if changed == 'uid':
        with pytest.raises(removal.guest.GuestError, match='^removal:unsafe-admission-record$'):
            removal.admission_removal_state()
    else:
        assert removal.admission_removal_state() != before


@pytest.mark.parametrize('unsafe', ['symlink', 'writable', 'fifo', 'too-many'])
def test_admission_snapshot_rejects_unsafe_or_unbounded_records(admission_records, unsafe):
    _, target, _ = admission_records
    if unsafe == 'too-many':
        for index in range(129):
            target.with_name(str(index)).write_bytes(b'owned')
    elif unsafe == 'writable':
        target.chmod(0o622)
    else:
        target.unlink()
        if unsafe == 'symlink':
            target.symlink_to('missing')
        else:
            os.mkfifo(target, 0o600)
    category = 'admission-record-bound' if unsafe == 'too-many' else 'unsafe-admission-record'
    with pytest.raises(removal.guest.GuestError, match='^removal:' + category + '$'):
        removal.admission_removal_state()


@pytest.mark.parametrize('name', [
    *['/etc/pam.d/common-' + part for part in (
        'auth', 'account', 'password', 'session', 'session-noninteractive')],
    *['/etc/pam.d/' + part for part in (
        'system-auth', 'password-auth', 'fingerprint-auth', 'smartcard-auth')],
    '/etc/authselect/authselect.conf',
    '/etc/authselect/custom/oh-no-parent-control/system-auth',
])
@pytest.mark.parametrize('changed', ['bytes', 'mode', 'uid', 'gid', 'absent'])
def test_admission_snapshot_preserves_shared_pam_and_authselect(admission_records, name, changed):
    path, _, ownership = admission_records
    target = path(name)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.write_bytes(b'installed stack or profile selection')
    target.chmod(0o644)
    before = removal.admission_removal_state()
    if changed == 'bytes':
        target.write_bytes(b'restored original stack or selection')
    elif changed == 'mode':
        target.chmod(0o600)
    elif changed in ('uid', 'gid'):
        ownership[changed == 'gid'] = 1
    else:
        target.unlink()
    if changed == 'uid':
        with pytest.raises(removal.guest.GuestError, match='unsafe-admission-record'):
            removal.admission_removal_state()
    else:
        assert removal.admission_removal_state() != before


@pytest.mark.parametrize('name', ['system-auth', 'password-auth', 'fingerprint-auth', 'smartcard-auth'])
@pytest.mark.parametrize('changed', ['link', 'bytes', 'mode', 'gid', 'absent', 'unsafe'])
def test_admission_snapshot_witnesses_fedora_link_and_effective_target(
        admission_records, name, changed):
    path, _, ownership = admission_records
    link, target = path('/etc/pam.d/' + name), path('/etc/authselect/' + name)
    link.parent.mkdir(parents=True)
    target.parent.mkdir(parents=True)
    target.write_bytes(b'generated managed PAM')
    target.chmod(0o644)
    link.symlink_to('../authselect/' + name)
    before = removal.admission_removal_state()
    assert before[str(link)][3] == '../authselect/' + name
    assert before[str(target)][:3] == (0o644, 0, 0)
    if changed in ('link', 'unsafe'):
        link.unlink()
        link.symlink_to('/etc/authselect/' + name if changed == 'link' else '/etc/shadow')
    elif changed == 'bytes':
        target.write_bytes(b'original PAM')
    elif changed == 'mode':
        target.chmod(0o600)
    elif changed == 'gid':
        ownership[1] = 1
    else:
        target.unlink()
    if changed == 'unsafe':
        with pytest.raises(removal.guest.GuestError, match='unsafe-admission-record'):
            removal.admission_removal_state()
    else:
        assert removal.admission_removal_state() != before


@pytest.mark.parametrize('suffix,distribution', [('.deb', 'ubuntu'), ('.rpm', 'fedora')])
@pytest.mark.parametrize('fault', [False, True])
def test_kiosk_readiness_uses_current_distro_pam_owner(monkeypatch, suffix, distribution, fault):
    monkeypatch.setattr(removal.guest, 'guard', Mock())
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package' + suffix))
    ready = Mock(side_effect=ValueError('owned-policy-changed') if fault else None)
    load = Mock(return_value={'runtime_ready': ready})
    monkeypatch.setattr(removal.runpy, 'run_path', load)
    if fault:
        with pytest.raises(removal.guest.GuestError, match='kiosk-pam-not-ready'):
            removal.verify_loaded_confinement()
    else:
        removal.verify_loaded_confinement()
    load.assert_called_once_with('/usr/lib/oh-no-parent-control/lifecycle/distro_pam.py')
    ready.assert_called_once_with(distribution)


@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('fault', [None, 'identity', 'marker', 'idle', 'quarantine', 'prepared'])
def test_current_removal_preflight_uses_owned_readers_without_quarantine(monkeypatch, legacy, fault):
    events = []
    marker = object()
    saved = {'kiosk_uid': 999 if fault == 'identity' else 1007} if legacy else None

    @contextmanager
    def barriers():
        events.append('lock')
        try:
            yield
        finally:
            events.append('unlock')

    def idle(value, identity):
        assert value is saved and identity == 1007
        events.append('idle')
        if fault == 'idle':
            raise ValueError('kiosk-processes-active')

    lifecycle = dict(barriers=barriers, uid=lambda: 1007,
        account=Mock(), state=lambda: saved, marker=Mock(), DISABLED=marker,
        read=Mock(return_value=b'removing' if fault == 'marker' else None),
        verify_pam=Mock(), policy_material=Mock(), idle=idle,
        expiry_record=Mock(return_value={'uid': 1007} if fault in ('quarantine', 'prepared') else None),
        quarantined=Mock(side_effect=ValueError('changed-quarantine') if fault == 'quarantine' else None))
    mutations = {name: Mock(side_effect=AssertionError('preflight must remain read-only'))
                 for name in ('prepare_remove', 'prepare', 'quarantine', 'save', 'write',
                              'erase', 'set_expiry', 'release_account')}
    lifecycle.update(mutations)
    load = Mock(return_value=lifecycle)
    monkeypatch.setattr(removal.guest, 'guard', Mock())
    monkeypatch.setattr(removal.runpy, 'run_path', load)
    refused = fault in ('idle', 'quarantine') or (legacy and fault == 'identity') or (not legacy and fault == 'marker')
    if refused:
        with pytest.raises((ValueError, removal.guest.GuestError)):
            removal.check_remove_preflight()
    else:
        removal.check_remove_preflight()
    load.assert_called_once_with('/usr/lib/oh-no-parent-control/lifecycle/lifecycle_migration.py')
    lifecycle['account'].assert_called_once_with(1007)
    lifecycle['expiry_record'].assert_called_once_with(1007)
    if fault in ('quarantine', 'prepared'):
        lifecycle['quarantined'].assert_called_once_with(1007)
    else:
        lifecycle['quarantined'].assert_not_called()
    assert events[0] == 'lock' and events[-1] == 'unlock'
    assert ('idle' in events) is (not refused or fault == 'idle')
    if fault == 'quarantine':
        lifecycle['read'].assert_not_called()
        lifecycle['verify_pam'].assert_not_called()
        lifecycle['policy_material'].assert_not_called()
    elif legacy:
        lifecycle['read'].assert_not_called()
        if fault != 'identity':
            lifecycle['verify_pam'].assert_called_once_with(saved)
            lifecycle['policy_material'].assert_called_once_with(saved)
    else:
        lifecycle['read'].assert_called_once_with(marker, private=True, optional=True)
        lifecycle['verify_pam'].assert_not_called()
        lifecycle['policy_material'].assert_not_called()
    for mutation in mutations.values():
        mutation.assert_not_called()


def test_current_lifecycle_readers_refuse_before_loading_installed_code(monkeypatch):
    guard = Mock(side_effect=removal.guest.GuestError('wrong-guest'))
    load = Mock()
    monkeypatch.setattr(removal.guest, 'guard', guard)
    monkeypatch.setattr(removal.runpy, 'run_path', load)
    for action in (removal.check_remove_preflight, removal.verify_loaded_confinement):
        with pytest.raises(removal.guest.GuestError, match='wrong-guest'):
            action()
    load.assert_not_called()


@pytest.mark.parametrize('fault,category', [
    (None, None), ('accepted', 'inflight-admission-not-refused'),
    ('erased', 'inflight-admission-not-refused'), ('reason', 'inflight-admission-not-refused'),
    ('root', 'admission-holder-not-root'), ('dead-before', 'admission-holder-not-root'),
    ('dead-after', 'admission-holder-changed'), ('identity', 'admission-holder-changed'),
    ('dead-control', 'admission-holder-changed'), ('records', 'inflight-refusal-changed-records'),
    ('account', 'inflight-refusal-changed-ownership'),
    *[(target + '-' + field, 'inflight-refusal-changed-ownership')
      for target in ('home', 'lease') for field in ('dev', 'ino', 'uid', 'gid', 'mode')],
    ('child', 'inflight-refusal-changed-policy'),
    ('other', 'inflight-refusal-changed-policy'), ('payload', 'package-file-digests'),
    *[(name, 'inflight-refusal-guards-not-retained') for name in
      ('mask-content', 'mask-owner', 'mask-type', 'mask-target', 'expiry', 'expiry-record')],
    ('preexisting-mask', 'inflight-refusal-changed-records'),
    ('recovery-status', 'inflight-unexpected-recovery-package-status'),
    ('recovery-command', 'fixture-recovery'), ('recovery-payload', 'package-file-digests'),
    ('recovery-records', 'inflight-recovery-changed-state'),
    ('recovery-mask', 'inflight-recovery-changed-state'),
    ('recovery-expiry', 'inflight-recovery-changed-state'),
    ('recovery-policy', 'inflight-recovery-changed-state'),
    ('recovery-readiness', 'kiosk-pam-not-ready'),
    ('enforcement-before', 'kiosk-pam-not-ready'),
    ('enforcement-after', 'kiosk-pam-not-ready'),
])
@pytest.mark.parametrize('variant', ['command', 'trusted-hard'])
@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_inflight_removal_refusal_preserves_holder_and_enforcement(monkeypatch, fault, category, variant, package_format):
    import system_kiosk_admission as admission
    import system_kiosk_confinement as confinement
    events = []
    removed = False
    held = False
    controlled = False
    recovered = False
    account = SimpleNamespace(pw_uid=1007, pw_dir='/home/owned')
    monkeypatch.setattr(removal.guest, 'guard', Mock())
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.' + package_format))
    monkeypatch.setattr(removal.pwd, 'getpwnam', lambda name:
                        SimpleNamespace(pw_uid=9999) if removed and fault == 'account' else account)
    def info(name):
        fields = dict(st_dev=1, st_ino=1, st_uid=1007, st_gid=1007, st_mode=0o40700)
        for field in fields:
            if removed and fault == name + '-' + field.removeprefix('st_'):
                fields[field] += 1
        return SimpleNamespace(**fields)
    runtime_mask = '/run/systemd/system/oh-no-parent-control-broker.service'
    mask_record = '/var/lib/oh-no-parent-control/uninstall-broker-mask'
    def path(value):
        if value == '/proc':
            return Path(value)
        if value == runtime_mask:
            return SimpleNamespace(lstat=lambda: SimpleNamespace(
                st_mode=0o100600 if fault == 'mask-type' else 0o120777,
                st_uid=1000 if fault == 'mask-owner' else 0))
        return SimpleNamespace(lstat=lambda: info('home' if value == account.pw_dir else 'lease'))
    monkeypatch.setattr(removal, 'Path', path)
    monkeypatch.setattr(removal, 'fault_file_identity', lambda target:
                        (b'foreign' if fault == 'mask-content' else b'',))
    monkeypatch.setattr(removal.os, 'readlink', lambda target:
                        '/foreign' if fault == 'mask-target' else '/dev/null')
    monkeypatch.setattr(removal.os.path, 'lexists', lambda target:
        (str(target).endswith('kiosk-configuration-account.json') and removed and fault == 'expiry-record') or
        (str(target) == runtime_mask and recovered and fault == 'recovery-mask'))
    monkeypatch.setattr(removal, 'current_expiry', lambda:
                        1 if (removed and fault == 'expiry') or (recovered and fault == 'recovery-expiry') else 23000)
    monkeypatch.setattr(removal, 'wait_kiosk_inactive', lambda current: events.append('inactive'))
    monkeypatch.setattr(admission, 'verify_gates', lambda record: events.append('gates'))
    def records():
        return {mask_record: ((0o600, 0, 0, 'empty') if
                    (fault == 'preexisting-mask' or (removed and not recovered)) else None),
                'pam': 'changed' if (removed and fault == 'records') or
                       (recovered and fault == 'recovery-records') else 'owned'}
    monkeypatch.setattr(removal, 'admission_removal_state', records)
    def enforcement():
        assert held or recovered
        events.append('enforcing')
        if (fault == ('enforcement-after' if removed else 'enforcement-before') or
                (recovered and fault == 'recovery-readiness')):
            raise removal.guest.GuestError('removal:kiosk-pam-not-ready')
    monkeypatch.setattr(removal, 'verify_loaded_confinement', enforcement)
    monkeypatch.setattr(removal, 'account_digest', lambda uid:
                        'changed' if (removed and fault == {1004: 'child', 1005: 'other'}[uid]) or
                        (recovered and fault == 'recovery-policy') else 'owned')
    @contextmanager
    def holder(record):
        nonlocal held
        events.append('hold')
        held = True
        try:
            yield 234
        except BaseException:
            events.append('failed-release')
            raise
        else:
            events.append('normal-release')
        finally:
            held = False
    monkeypatch.setattr(admission, 'held_account', holder)
    monkeypatch.setattr(removal.os, 'pidfd_open', lambda pid: 987)
    close = Mock(side_effect=lambda fd: events.append('close'))
    monkeypatch.setattr(removal.os, 'close', close)
    monkeypatch.setattr(confinement, 'process_identity', lambda process:
                        ('changed' if removed and fault == 'identity' else 'start', 1,
                         ('1007',) * 4 if fault == 'root' else ('0',) * 4))
    monkeypatch.setattr(confinement, 'exited', lambda fd:
                        fault == 'dead-before' or (removed and fault == 'dead-after') or
                        (controlled and fault == 'dead-control'))
    def native_remove(arguments, **options):
        nonlocal removed
        assert held and arguments == ['native-remove']
        assert options == {'check': False, 'timeout': 120, 'merge_stderr': True}
        removed = True
        events.append('remove')
        return (b'unrelated failure' if fault == 'reason' else
                b'kiosk-lifecycle: [Errno 11] Resource temporarily unavailable')
    monkeypatch.setattr(removal, 'removal_command', lambda: ['native-remove'])
    monkeypatch.setattr(removal.guest, 'commands', SimpleNamespace(
        run=native_remove, last_returncode=0 if fault == 'accepted' else 1))
    monkeypatch.setattr(removal, 'package_absent', lambda: fault == 'erased')
    def payload():
        events.append('payload')
        if fault == 'payload':
            raise removal.guest.GuestError('removal:package-file-digests')
    monkeypatch.setattr(removal.guest, 'verify_package_payload', payload)
    def recovery_files():
        assert not held and recovered
        events.append('files')
        if fault == 'recovery-payload':
            raise removal.guest.GuestError('removal:package-file-digests')
    monkeypatch.setattr(removal.guest, 'verify_package_files', recovery_files)
    def recover():
        nonlocal recovered
        assert not held and removed
        if fault == 'recovery-command':
            raise removal.guest.GuestError('removal:fixture-recovery')
        recovered = True
        events.append('rearm')
    monkeypatch.setattr(removal.guest, 'install_package', recover)
    def run(arguments, **options):
        assert not held and removed
        if arguments == ['dpkg-query', '-W', '-f=${Status}', removal.PRODUCT]:
            assert options == {}
            return 'unexpected' if fault == 'recovery-status' else 'install ok half-configured'
        assert arguments == ['dpkg', '--configure', removal.PRODUCT] and options == {'timeout': 1800}
        recover()
    monkeypatch.setattr(removal.guest, 'run', run)
    def launch(uid, allowed, **options):
        assert options == {'variant': variant}
        assert (uid, allowed) in ((1005, True), (1004, False))
        assert held is removed
        events.append(('launch', uid, allowed))
    monkeypatch.setattr(removal, 'observe_launch', launch)
    def probe(*args):
        nonlocal controlled
        assert held and removed
        assert args[:-1] == ('login', 'ordinary', 0, 'held-removal.ordinary-after')
        controlled = True
        events.append('probe')
    monkeypatch.setattr(admission, 'probe', probe)
    def preflight():
        assert not held
        events.append('preflight')
    monkeypatch.setattr(removal, 'check_remove_preflight', preflight)
    record = Mock()
    effective_fault = fault is not None and not (fault == 'recovery-status' and package_format == 'rpm')
    if effective_fault:
        with pytest.raises(removal.guest.GuestError, match='^removal:' + category + '$'):
            removal.verify_inflight_admission_refusal(record, {'child': 1004, 'other': 1005},
                                                     variant=variant)
        if fault.startswith('recovery-'):
            assert 'normal-release' in events and 'failed-release' not in events
            assert [item.args[0] for item in record.call_args_list] == [
                'onpc.removal.inflight-admission-refused', 'onpc.removal.inflight-admission-drained']
        else:
            assert events[-2:] == ['close', 'failed-release']
            record.assert_not_called()
    else:
        removal.verify_inflight_admission_refusal(record, {'child': 1004, 'other': 1005},
                                                 variant=variant)
        assert events == ['inactive', 'gates', ('launch', 1005, True), 'preflight',
                          'hold', 'inactive', 'enforcing', 'remove', 'enforcing', 'payload',
                          ('launch', 1005, True), ('launch', 1004, False), 'probe',
                          'close', 'normal-release', 'preflight', 'rearm', 'files', 'enforcing', 'gates']
        assert [call.args[0] for call in record.call_args_list] == [
            'onpc.removal.inflight-admission-refused', 'onpc.removal.inflight-admission-drained',
            'onpc.removal.inflight-admission-restored']
    assert not held
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


@pytest.mark.parametrize('changed', [None, 'mode', 'uid', 'group', 'bytes', 'absent', 'other-record'])
def test_rollback_allows_only_private_authselect_native_group_republication(monkeypatch, changed):
    monkeypatch.setattr(removal.grp, 'getgrnam', lambda _: SimpleNamespace(gr_gid=10))
    name = '/var/lib/oh-no-parent-control/fedora-authselect.json'
    before = (0o600, 0, 10, 'original-digest')
    after = [0o600, 0, 0, 'original-digest']
    if changed in ('mode', 'uid', 'group', 'bytes'):
        index, value = {'mode': (0, 0o640), 'uid': (1, 1000),
                        'group': (2, 1000), 'bytes': (3, 'changed-digest')}[changed]
        after[index] = value
    if changed == 'other-record':
        name = '/var/lib/oh-no-parent-control/package-created-kiosk-uid'
    assert removal.rollback_record_matches(
        name, before, None if changed == 'absent' else tuple(after)) is (changed is None)


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


@pytest.mark.parametrize('fault', [None, 'boot', 'policy', 'home', 'ordinary', 'preflight', 'expiry'])
@pytest.mark.parametrize('variant', ['command', 'trusted-hard'])
def test_rollback_reboot_requires_preserved_state_before_native_finalization(
        tmp_path, monkeypatch, fault, variant):
    import system_kiosk_admission as admission
    home = tmp_path / 'home'
    home.mkdir()
    info = home.lstat()
    kiosk = SimpleNamespace(pw_uid=info.st_uid, pw_gid=info.st_gid,
                            pw_dir='/home/oh-no-parent-control', pw_shell='/usr/sbin/nologin')
    parent = SimpleNamespace(pw_name='parent', pw_uid=41002, pw_gid=41002,
                             pw_dir='/home/parent', pw_shell='/bin/bash')
    state = {'accounts': {'child': 41001, 'parent': 41002}, 'kiosk_name': 'oh-no-parent-control',
             'native_variant': variant,
             'rollback_rearm': {
                 'boot': 'old', 'policy': 'child-policy', 'extensions': ['child-extension'], 'expires': None,
                 'kiosk_identity': [kiosk.pw_uid, kiosk.pw_gid, kiosk.pw_dir, kiosk.pw_shell],
                 'kiosk_home': [info.st_ino, info.st_uid, info.st_gid, info.st_mode],
                 'ordinary': {'parent': {'uid': 41002, 'policy': 'parent-policy',
                     'extensions': ['parent-extension'],
                     'identity': [parent.pw_name, parent.pw_uid, parent.pw_gid,
                                  parent.pw_dir, parent.pw_shell]}},
             }}
    path = tmp_path / 'state.json'
    path.write_text(json.dumps(state))
    monkeypatch.setattr(removal, 'state_path', lambda: path)
    monkeypatch.setattr(removal, 'Path', lambda _: home)
    monkeypatch.setattr(removal, 'boot', lambda: 'old' if fault == 'boot' else 'new')
    monkeypatch.setattr(removal, 'current_expiry', lambda: 1 if fault == 'expiry' else None)
    monkeypatch.setattr(removal.guest, 'guard', Mock())
    monkeypatch.setattr(removal.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(removal.guest, 'reboot_cleared', lambda: True)
    monkeypatch.setattr(removal.guest, 'installed', Mock())
    monkeypatch.setattr(removal.pwd, 'getpwnam', lambda _: kiosk)
    monkeypatch.setattr(removal.pwd, 'getpwuid', lambda _: parent)
    monkeypatch.setattr(removal, 'account_digest', lambda uid: (
        'changed' if fault == 'policy' and uid == 41001 else
        'child-policy' if uid == 41001 else 'parent-policy'))
    monkeypatch.setattr(removal, 'extension_lists', lambda uid: (
        ['changed'] if fault == 'ordinary' and uid == 41002 else
        ['child-extension'] if uid == 41001 else ['parent-extension']))
    if fault == 'home':
        home.chmod(0o700 if stat.S_IMODE(info.st_mode) != 0o700 else 0o755)
    for name in ('observe_launch', 'verify_loaded_confinement', 'wait_kiosk_inactive'):
        monkeypatch.setattr(removal, name, Mock())
    monkeypatch.setattr(admission, 'verify_gates', Mock())
    monkeypatch.setattr(admission, 'probe', Mock())
    monkeypatch.setattr(removal, 'check_remove_preflight', Mock(side_effect=(
        removal.guest.GuestError('preflight') if fault == 'preflight' else None)))
    commands, verify = Mock(), Mock()
    monkeypatch.setattr(removal.guest, 'commands', commands)
    monkeypatch.setattr(removal, 'verify_removed', verify)
    monkeypatch.setattr(removal, 'removal_command', lambda: ['native-remove'])
    if fault:
        with pytest.raises(removal.guest.GuestError):
            removal.rollback_rearmed_rebooted(Mock())
        commands.run.assert_not_called()
        verify.assert_not_called()
    else:
        record = Mock()
        removal.rollback_rearmed_rebooted(record)
        commands.run.assert_called_once_with(['native-remove'], timeout=1800, merge_stderr=True)
        verify.assert_called_once_with(state, record=record)
        assert removal.observe_launch.call_args_list == [
            mock_call(41001, False, variant=variant),
            mock_call(41002, True, variant=variant),
            mock_call(41002, True, variant=variant)]
        assert [call.args[0] for call in record.call_args_list] == [
            'onpc.rollback.rearm-reboot', 'onpc.rollback.retry-finalized']


@pytest.mark.parametrize('entry', ['interrupted_finalization_retry', 'finalization_retry_rebooted'])
@pytest.mark.parametrize('fault', ['guard', 'variant'])
def test_finalization_entry_refuses_before_setup(monkeypatch, entry, fault):
    guard = Mock(side_effect=removal.guest.GuestError('fixture:guard') if fault == 'guard' else None)
    monkeypatch.setattr(removal.guest, 'guard', guard)
    diagnostics, provision, state = Mock(), Mock(), Mock()
    monkeypatch.setattr(removal.guest, 'enable_diagnostics', diagnostics)
    monkeypatch.setattr(removal, 'provision_native', provision)
    monkeypatch.setattr(removal, 'state_path', state)
    with pytest.raises(removal.guest.GuestError, match='fixture:guard' if fault == 'guard' else 'variant'):
        getattr(removal, entry)(Mock(), 'unknown')
    diagnostics.assert_not_called()
    provision.assert_not_called()
    state.assert_not_called()


@pytest.mark.parametrize('raw,expected', [('', None), ('0', 0), ('20000', 20000)])
def test_native_expiry_reader_preserves_original_empty_or_numeric_value(monkeypatch, raw, expected):
    run = Mock(return_value=removal.PRODUCT + ':!:1:0:99999:7::' + raw + ':')
    monkeypatch.setattr(removal.guest, 'run', run)
    assert removal.current_expiry() == expected
    assert run.call_args.args == (['getent', 'shadow', removal.PRODUCT],)
    redactor = run.call_args.kwargs['diagnostic_stdout']
    assert redactor(b'arbitrary private shadow fields') == b'kiosk-expiry-read\n'
    assert set(run.call_args.kwargs) == {'diagnostic_stdout'}


@pytest.mark.parametrize('suffix,expected', [('.deb', 7), ('.rpm', 13)])
@pytest.mark.parametrize('service', ['gdm-password', 'systemd-user'])
def test_native_expiry_oracle_uses_distribution_account_status(monkeypatch, suffix, expected, service):
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package' + suffix))
    assert removal.expiry_status(service) == expected


@pytest.mark.parametrize('suffix,service', [('.deb', 'login'), ('.unknown', 'gdm-password')])
def test_native_expiry_oracle_refuses_unknown_service_or_package(monkeypatch, suffix, service):
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package' + suffix))
    with pytest.raises(removal.guest.GuestError, match='expiry-service|package-format'):
        removal.expiry_status(service)


@pytest.mark.parametrize('raw', ['other:!:1:0:99999:7:::','invalid',
    removal.PRODUCT + ':!:1:0:99999:7::-1:',
    removal.PRODUCT + ':!:1:0:99999:7::١:',
    removal.PRODUCT + ':!:1:0:99999:7::tomorrow:',
    removal.PRODUCT + ':!:1:0:99999:7::1:extra:extra'])
def test_native_expiry_reader_refuses_unowned_or_malformed_shadow_output(monkeypatch, raw):
    monkeypatch.setattr(removal.guest, 'run', Mock(return_value=raw))
    with pytest.raises(removal.guest.GuestError, match='invalid-kiosk-expiry'):
        removal.current_expiry()


@pytest.mark.parametrize('fault', [None, 'uid', 'legacy', 'legacy-marker', 'expiry', 'capture', 'capture-directory'])
def test_fresh_recovery_snapshot_owns_current_identity_and_exact_pam_metadata(monkeypatch, fault):
    monkeypatch.setattr(removal.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=41000))
    marker = Mock(return_value=SimpleNamespace(contents=(b'41001\n' if fault == 'uid' else b'41000\n')))
    monkeypatch.setattr(removal, 'private_recovery_record', marker)
    names = {'legacy': 'kiosk-confinement.json', 'legacy-marker': 'kiosk-confinement-removing',
             'expiry': 'kiosk-configuration-account.json', 'capture': 'legacy-kiosk-policy.json',
             'capture-directory': 'legacy-kiosk-policy'}
    monkeypatch.setattr(removal.os.path, 'lexists', lambda path: Path(path).name == names.get(fault))
    monkeypatch.setattr(removal, 'current_expiry', lambda: 23000)
    identities = {name: (1, index, 0, 0, 0o100644, 1, name.encode())
                  for index, name in enumerate(('gdm-password', 'systemd-user'))}
    monkeypatch.setattr(removal, 'fault_file_identity', lambda path: identities[path.name])
    if fault:
        with pytest.raises(removal.guest.GuestError, match='changed-kiosk-identity|nonfresh-lifecycle-records'):
            removal.removal_recovery_state()
    else:
        assert removal.removal_recovery_state() == {'uid': 41000, 'expires': 23000,
            'pam': {name: identity[2:] for name, identity in identities.items()}}
        marker.assert_called_once_with(Path('/var/lib/oh-no-parent-control/package-created-kiosk-uid'))


@pytest.mark.parametrize('fault', [None, 'version', 'bool-version', 'uid', 'expires', 'bool-expires', 'phase', 'extra',
                                  'json', 'non-object',
                                  'actual-expiry', 'marker', 'legacy', 'legacy-marker'])
@pytest.mark.parametrize('marker_uid', [None, 41003])
@pytest.mark.parametrize('expires', [None, 0, 23000])
def test_quarantine_oracle_requires_exact_uid_expiry_phase_and_known_records(monkeypatch, fault, marker_uid, expires):
    saved = {'uid': 41000, 'expires': expires}
    current = {'version': 1, 'uid': 41000, 'expires': expires, 'phase': 'quarantined'}
    if fault == 'bool-version':
        current['version'] = True
    elif fault == 'bool-expires':
        current['expires'] = False
    elif fault in ('version', 'uid', 'expires', 'phase', 'extra'):
        current[fault] = {'version': 2, 'uid': 41001, 'expires': 2,
                          'phase': 'releasing', 'extra': True}[fault]
    def read(path):
        contents = (json.dumps(current).encode() if path.name == 'kiosk-configuration-account.json'
                    else (str(999 if fault == 'marker' else marker_uid or saved['uid']) + '\n').encode())
        if path.name == 'kiosk-configuration-account.json' and fault in ('json', 'non-object'):
            contents = b'invalid json' if fault == 'json' else b'[]'
        return SimpleNamespace(contents=contents)
    monkeypatch.setattr(removal, 'private_recovery_record', read)
    monkeypatch.setattr(removal, 'current_expiry', lambda: None if fault == 'actual-expiry' else 1)
    monkeypatch.setattr(removal.os.path, 'lexists', lambda path: Path(path).name == {
        'legacy': 'kiosk-confinement.json', 'legacy-marker': 'kiosk-confinement-removing'}.get(fault))
    if fault:
        with pytest.raises(removal.guest.GuestError, match='quarantine-record-changed|recovery-records-changed'):
            removal.verify_quarantine(saved, marker_uid=marker_uid)
    else:
        removal.verify_quarantine(saved, marker_uid=marker_uid)


@pytest.mark.parametrize('residue', [None, 'executable', 'dangling'])
def test_finalization_erasure_exempts_only_exact_notice(tmp_path, residue):
    executable = tmp_path / 'broker'
    if residue == 'executable':
        executable.write_bytes(b'payload')
    elif residue == 'dangling':
        executable.symlink_to(tmp_path / 'absent')
    state = {'payload': [removal.DEBIAN_NOTICE, str(executable)]}
    if residue:
        with pytest.raises(removal.guest.GuestError, match='payload-not-erased'):
            removal.verify_payload_erased(state)
    else:
        removal.verify_payload_erased(state)


@pytest.fixture
def finalization_machine(tmp_path, monkeypatch):
    import system_kiosk_admission as admission
    def path(value):
        return tmp_path / str(value).lstrip('/')
    def write(name, value):
        target = path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value)
        return target
    monkeypatch.setattr(removal, 'Path', path)
    native_lexists = os.path.lexists
    monkeypatch.setattr(removal.os.path, 'lexists', lambda target: native_lexists(
        path(target) if str(target).startswith(('/etc/', '/var/', '/run/')) else target))
    home = path('/home/kiosk')
    home.mkdir(parents=True)
    info = home.lstat()
    kiosk = SimpleNamespace(pw_name=removal.PRODUCT, pw_uid=41000, pw_gid=41000,
                            pw_dir='/home/kiosk', pw_shell='/usr/sbin/nologin')
    ordinary = {uid: SimpleNamespace(pw_name=role, pw_uid=uid, pw_gid=uid,
                                    pw_dir='/home/' + role, pw_shell='/bin/bash')
                for role, uid in [('parent', 41002), ('other', 41003)]}
    monkeypatch.setattr(removal.pwd, 'getpwnam', lambda _: kiosk)
    monkeypatch.setattr(removal.pwd, 'getpwuid', ordinary.__getitem__)
    monkeypatch.setattr(removal, 'account_digest', lambda uid, **kwargs: 'policy-' + str(uid))
    monkeypatch.setattr(removal, 'extension_lists', lambda uid: ['extensions-' + str(uid)])
    monkeypatch.setattr(removal, 'preference_digest', lambda uid: 'preferences')
    state = {'accounts': {'child': 41001, 'parent': 41002, 'other': 41003},
             'preferences': 'preferences', 'other': 'policy-41003',
             'pam_services': {'original': 'bytes'},
             'kiosk_name': removal.PRODUCT, 'payload': [str(tmp_path / 'erased-broker')]}
    recovery = {'variant': 'denial-publication', 'boot': 'old', 'completed': False, 'expires': None,
                'policy': 'policy-41001', 'extensions': ['extensions-41001'],
                'kiosk_identity': [kiosk.pw_uid, kiosk.pw_gid, kiosk.pw_dir, kiosk.pw_shell],
                'kiosk_home': ['btrfs', '98a66632-e833-4d5b-9539-84d88ac96e90', '257',
                               info.st_ino, info.st_uid, info.st_gid, info.st_mode],
                'home_device': info.st_dev,
                'ordinary': {}}
    for role, uid in [('parent', 41002), ('other', 41003)]:
        account = ordinary[uid]
        recovery['ordinary'][role] = {
            'uid': uid, 'policy': 'policy-' + str(uid), 'extensions': ['extensions-' + str(uid)],
            'identity': [account.pw_name, uid, uid, account.pw_dir, account.pw_shell]}
    state['finalization_retry'] = recovery
    saved = {'uid': 41000, 'expires': None, 'pam': {}}
    write('/var/lib/oh-no-parent-control/kiosk-configuration-account.json', json.dumps({
        'version': 1, 'uid': 41000, 'expires': None, 'phase': 'quarantined'}))
    write('/var/lib/oh-no-parent-control/package-created-kiosk-uid', '41000\n')
    for service, contents in {'gdm-password': 'account required pam_unix.so\n',
                               'systemd-user': 'session required pam_systemd.so\n'}.items():
        write('/etc/pam.d/' + service, contents)
    write('/sys/kernel/security/apparmor/profiles', 'unrelated (enforce)\n')
    def file_identity(target):
        info = target.lstat()
        return (info.st_dev, info.st_ino, 0, 0, info.st_mode, info.st_nlink, target.read_bytes())
    monkeypatch.setattr(removal, 'fault_file_identity', file_identity)
    saved['pam'] = {service: file_identity(path('/etc/pam.d/' + service))[2:]
                    for service in ('gdm-password', 'systemd-user')}
    monkeypatch.setattr(removal, 'current_expiry', lambda: 1)
    monkeypatch.setattr(removal.guest, 'pam_service_state', lambda: {'original': 'bytes'})
    monkeypatch.setattr(removal, 'private_recovery_record', lambda target:
                        SimpleNamespace(contents=target.read_bytes()))
    monkeypatch.setattr(removal.guest, 'guard', Mock())
    monkeypatch.setattr(removal.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.deb'))
    filesystem = {'uuid': '98a66632-e833-4d5b-9539-84d88ac96e90', 'fstype': 'btrfs',
                  'fs-options': 'rw,relatime,subvolid=257,subvol=/home'}
    run = Mock(side_effect=lambda argv, **kwargs: (
        json.dumps({'filesystems': [filesystem]}) if argv[0] == 'findmnt' else
        {'getenforce': 'Enforcing', '/usr/sbin/semanage': 'unrelated_t\n',
         '/usr/sbin/semodule': 'unrelated 1.0\n'}.get(argv[0], '')))
    monkeypatch.setattr(removal.guest, 'run', run)
    commands = Mock()
    monkeypatch.setattr(removal.guest, 'commands', commands)
    launch, durable, probe = Mock(), Mock(), Mock()
    monkeypatch.setattr(removal, 'observe_launch', launch)
    monkeypatch.setattr(admission, 'durable_probe', durable)
    monkeypatch.setattr(admission, 'probe', probe)
    return SimpleNamespace(state=state, recovery=recovery, saved=saved, write=write, path=path,
        kiosk=kiosk, ordinary=ordinary, launch=launch, durable=durable, probe=probe,
        run=run, commands=commands, filesystem=filesystem, home=home)


@pytest.mark.parametrize('fault', [None, 'kiosk-uid', 'home-inode', 'ordinary-identity',
                                 'ordinary-policy', 'ordinary-extension', 'other-policy', 'preferences'])
@pytest.mark.parametrize('native_variant', ['command', 'trusted-hard'])
def test_surviving_identity_requires_home_and_all_retained_account_state(
        finalization_machine, monkeypatch, fault, native_variant):
    machine = finalization_machine
    machine.state['native_variant'] = native_variant
    if fault == 'kiosk-uid':
        machine.kiosk.pw_uid += 1
    elif fault == 'home-inode':
        machine.recovery['kiosk_home'][3] += 1
    elif fault == 'ordinary-identity':
        machine.ordinary[41002].pw_shell = '/bin/false'
    elif fault == 'ordinary-policy':
        machine.recovery['ordinary']['parent']['policy'] = 'changed'
    elif fault == 'ordinary-extension':
        machine.recovery['ordinary']['parent']['extensions'] = []
    elif fault == 'other-policy':
        machine.state['other'] = 'changed'
    elif fault == 'preferences':
        machine.state['preferences'] = 'changed'
    if fault:
        with pytest.raises(removal.guest.GuestError, match='finalization:|other-account-changed'):
            removal.verify_surviving_identity(machine.state, machine.recovery)
    else:
        removal.verify_surviving_identity(machine.state, machine.recovery)
        assert machine.launch.call_args_list == [
            mock_call(41002, True, variant=native_variant),
            mock_call(41003, True, variant=native_variant)]


def test_identity_mismatch_retains_only_field_comparisons_and_device_numbers(finalization_machine):
    machine = finalization_machine
    machine.recovery['kiosk_home'][3] += 1
    machine.recovery['home_device'] += 1
    record = Mock()
    with pytest.raises(removal.guest.GuestError, match='kiosk-identity-changed'):
        removal.verify_surviving_identity(machine.state, machine.recovery, record)
    name, encoded = record.call_args.args
    assert name == 'onpc.finalization.identity-comparison'
    result = json.loads(encoded)
    assert result['account_fields'] == dict.fromkeys(('uid', 'gid', 'home', 'shell'), True)
    assert result['home_fields'] == {'filesystem': True, 'uuid': True, 'subvolume': True,
                                     'inode': False, 'uid': True, 'gid': True, 'mode': True}
    assert result['saved_home_device'] == result['home_device'] + 1
    assert machine.kiosk.pw_dir not in encoded and machine.kiosk.pw_shell not in encoded
    assert machine.filesystem['uuid'] not in encoded


def test_surviving_home_accepts_reboot_device_renumbering(finalization_machine):
    machine = finalization_machine
    machine.recovery['home_device'] = machine.home.lstat().st_dev + 1
    record = Mock()
    removal.verify_surviving_identity(machine.state, machine.recovery, record)
    comparison = json.loads(record.call_args.args[1])
    assert comparison['saved_home_device'] != comparison['home_device']
    assert comparison['home_fields'] == dict.fromkeys(
        ('filesystem', 'uuid', 'subvolume', 'inode', 'uid', 'gid', 'mode'), True)
    assert machine.launch.call_args_list == [mock_call(41002, True, variant='command'),
                                            mock_call(41003, True, variant='command')]


@pytest.mark.parametrize('field,replacement', [
    (0, 'ext4'), (1, 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'), (2, '258'),
    (3, -1), (4, -1), (5, -1), (6, 0o40000),
])
def test_surviving_home_refuses_every_changed_persistent_field(finalization_machine, field, replacement):
    machine = finalization_machine
    assert machine.recovery['kiosk_home'][field] != replacement
    machine.recovery['kiosk_home'][field] = replacement
    with pytest.raises(removal.guest.GuestError, match='finalization:kiosk-identity-changed'):
        removal.verify_surviving_identity(machine.state, machine.recovery)
    machine.launch.assert_not_called()


@pytest.mark.parametrize('fstype,options,subvolume', [
    ('btrfs', 'rw,relatime,subvolid=257,subvol=/home', '257'),
    ('btrfs', 'ro,noatime,subvol=/home,subvolid=000257', '257'),
    ('ext4', 'rw,relatime', None), ('xfs', 'ro,noatime', None),
])
def test_persistent_home_identity_uses_filesystem_not_mount_flags(
    tmp_path, monkeypatch, fstype, options, subvolume,
):
    home = tmp_path / 'home'
    home.mkdir(mode=0o700)
    info = home.lstat()
    uuid = '98A66632-E833-4D5B-9539-84D88AC96E90'
    run = Mock(return_value=json.dumps({'filesystems': [
        {'uuid': uuid, 'fstype': fstype, 'fs-options': options}]}))
    monkeypatch.setattr(removal.guest, 'run', run)
    assert removal.persistent_home_identity(home, info) == [
        fstype, uuid.lower(), subvolume, info.st_ino, info.st_uid, info.st_gid, info.st_mode]
    run.assert_called_once_with(['findmnt', '--json', '--target', str(home),
                                 '--output', 'UUID,FSTYPE,FS-OPTIONS'], timeout=15)


def test_surviving_home_accepts_equivalent_self_bind_mount(finalization_machine):
    machine = finalization_machine
    machine.filesystem['fs-options'] = 'ro,noatime,subvol=/home,subvolid=000257'
    removal.verify_surviving_identity(machine.state, machine.recovery)
    assert machine.launch.call_count == 2


@pytest.mark.parametrize('output', [
    'not json', 'null', '[]', '{}', '{"filesystems": null}', '{"filesystems": {}}',
    '{"filesystems": []}', '{"filesystems": [null]}',
    '{"filesystems": [], "extra": 1}',
    '{"filesystems": [], "filesystems": []}',
    *[json.dumps({'filesystems': rows}) for rows in [
        [{}, {}],
        [{'uuid': '98a66632-e833-4d5b-9539-84d88ac96e90', 'fstype': 'ext4',
          'fs-options': 'rw'}] * 2,
        [{'uuid': '98a66632-e833-4d5b-9539-84d88ac96e90', 'fstype': 'btrfs'}],
        *[[{'uuid': uuid, 'fstype': fstype, 'fs-options': options}]
          for uuid, fstype, options in [
              (None, 'btrfs', 'subvolid=257'), ('', 'btrfs', 'subvolid=257'),
              ('invalid', 'btrfs', 'subvolid=257'),
              ('98a66632-e833-4d5b-9539-84d88ac96e90', None, 'subvolid=257'),
              ('98a66632-e833-4d5b-9539-84d88ac96e90', 'BTRFS', 'subvolid=257'),
              ('98a66632-e833-4d5b-9539-84d88ac96e90', 'bad/type', 'subvolid=257'),
              ('98a66632-e833-4d5b-9539-84d88ac96e90', 'btrfs', None),
              ('98a66632-e833-4d5b-9539-84d88ac96e90', 'btrfs', ''),
              ('98a66632-e833-4d5b-9539-84d88ac96e90', 'btrfs', 'rw'),
              ('98a66632-e833-4d5b-9539-84d88ac96e90', 'btrfs', 'subvolid=-1'),
              ('98a66632-e833-4d5b-9539-84d88ac96e90', 'btrfs', 'subvolid=abc'),
              ('98a66632-e833-4d5b-9539-84d88ac96e90', 'btrfs', 'subvolid=257,subvolid=257'),
          ]],
    ]],
    '{"filesystems": [{"uuid": "98a66632-e833-4d5b-9539-84d88ac96e90", '
    '"fstype": "ext4", "fs-options": "rw", "source": "/dev/foreign"}]}',
    '{"filesystems": [{"uuid": "98a66632-e833-4d5b-9539-84d88ac96e90", '
    '"fstype": "ext4", "fstype": "ext4", "fs-options": "rw"}]}',
])
def test_persistent_home_identity_refuses_malformed_or_ambiguous_mount_query(tmp_path, monkeypatch, output):
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setattr(removal.guest, 'run', Mock(return_value=output))
    with pytest.raises(removal.guest.GuestError, match='finalization:home-filesystem-identity'):
        removal.persistent_home_identity(home)


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_durable_interval_uses_installed_native_boundaries_and_exact_recovery(finalization_machine, monkeypatch, package_format):
    machine = finalization_machine
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.' + package_format))
    record = Mock()
    removal.verify_durable_interval(machine.state, machine.recovery, machine.saved, record)
    expected = []
    for service in ('gdm-password', 'systemd-user'):
        expected.extend([mock_call(service, role, 'account', 0, service + '.' + role, record)
                         for role in ('ordinary', 'other')])
        expected.append(mock_call(service, 'kiosk', 'account',
                                  13 if package_format == 'rpm' else 7,
                                  service + '.kiosk.account', record))
    assert machine.durable.call_args_list == expected
    assert machine.probe.call_args_list == [
        mock_call('login', role, 0, 'finalization.payload-erased.' + role, record)
        for role in ('ordinary', 'other')]
    assert record.call_args_list[-1].args[0] == 'onpc.finalization.payload-erased-interval'
    expected_commands = [mock_call(['findmnt', '--json', '--target', str(machine.home),
                                    '--output', 'UUID,FSTYPE,FS-OPTIONS'], timeout=15)]
    if package_format == 'rpm':
        expected_commands.extend([mock_call(['getenforce']),
            mock_call(['/usr/sbin/semanage', 'permissive', '-l']), mock_call(['/usr/sbin/semodule', '-l'])])
    assert machine.run.call_args_list == expected_commands
    machine.commands.run.assert_not_called()


@pytest.mark.parametrize('fault', ['phase', 'extra-record', 'legacy', 'uid', 'pam-bytes',
                                 'pam-mode', 'erased-module', 'ordinary-pam', 'expiry'])
def test_durable_interval_refuses_changed_records_or_non_native_denial(finalization_machine, fault):
    machine = finalization_machine
    if fault in ('phase', 'extra-record', 'expiry'):
        current = {'version': 1, 'uid': 41000, 'expires': None, 'phase': 'quarantined'}
        current.update({'phase': 'releasing'} if fault == 'phase' else
                       {'expires': 123} if fault == 'expiry' else {'foreign': 'value'})
        machine.write('/var/lib/oh-no-parent-control/kiosk-configuration-account.json', json.dumps(current))
    elif fault == 'legacy':
        machine.write('/var/lib/oh-no-parent-control/kiosk-confinement-removing', 'removing\n')
    elif fault == 'uid':
        machine.write('/var/lib/oh-no-parent-control/package-created-kiosk-uid', '41003\n')
    elif fault == 'pam-bytes':
        machine.write('/etc/pam.d/gdm-password', 'account required pam_permit.so\n')
    elif fault == 'pam-mode':
        machine.path('/etc/pam.d/gdm-password').chmod(0o600)
    elif fault == 'ordinary-pam':
        machine.state['pam_services'] = {'changed': 'PAM baseline'}
    else:
        machine.write('/etc/pam.d/gdm-password', 'account required pam_oh_no_parent_control.so\n')
    with pytest.raises(removal.guest.GuestError, match=(
            'recovery-records-changed|quarantine-record-changed|vendor-service-changed|'
            'original-pam-not-restored|pam-reference-remains')):
        removal.verify_durable_interval(machine.state, machine.recovery, machine.saved, Mock())
    machine.durable.assert_not_called()


@pytest.mark.parametrize('fault', ['global', 'xdm_t', 'init_t', 'onpc_kiosk_t', 'selinux-module', 'apparmor'])
def test_durable_interval_requires_unloaded_mac_and_enforcing_native_domains(finalization_machine, monkeypatch, fault):
    machine = finalization_machine
    if fault == 'apparmor':
        machine.write('/sys/kernel/security/apparmor/profiles', 'onpc-kiosk-manager (enforce)\n')
    else:
        monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.rpm'))
        native_run = machine.run.side_effect
        machine.run.side_effect = lambda argv, **kwargs: (
            native_run(argv, **kwargs) if argv[0] == 'findmnt' else
            'Permissive' if fault == 'global' and argv == ['getenforce'] else
            fault if fault.endswith('_t') and argv[0] == '/usr/sbin/semanage' else
            'onpc-kiosk 1.0\n' if fault == 'selinux-module' and argv[0] == '/usr/sbin/semodule' else
            'Enforcing' if argv == ['getenforce'] else '')
    record = Mock()
    with pytest.raises(removal.guest.GuestError, match='selinux-not-enforcing|domain-not-enforcing|mac-not-unloaded'):
        removal.verify_durable_interval(machine.state, machine.recovery, machine.saved, record)
    assert all(item.args[0] != 'onpc.finalization.payload-erased-interval'
               for item in record.call_args_list)


@pytest.fixture
def finalization_reboot(finalization_machine, monkeypatch):
    import system_kiosk_admission as admission
    machine = finalization_machine
    state_file = machine.write('/private/finalization-state.json', json.dumps(machine.state))
    monkeypatch.setattr(removal, 'state_path', lambda: state_file)
    monkeypatch.setattr(removal, 'boot', lambda: 'new')
    monkeypatch.setattr(removal, 'current_expiry', lambda: machine.recovery['expires'])
    for owner, name in [(removal.guest, 'installed'), (removal, 'verify_loaded_confinement'),
                        (removal, 'wait_kiosk_inactive'), (removal, 'check_remove_preflight'),
                        (admission, 'verify_gates')]:
        monkeypatch.setattr(owner, name, Mock())
    monkeypatch.setattr(removal, 'removal_command', lambda: ['native-remove'])
    verify = Mock()
    monkeypatch.setattr(removal, 'verify_removed', verify)
    machine.state_file, machine.verify = state_file, verify
    return machine


@pytest.mark.parametrize('completed', [False, True])
@pytest.mark.parametrize('native_variant', ['command', 'trusted-hard'])
def test_finalization_reboot_finishes_only_pending_native_removal(
        finalization_reboot, completed, native_variant):
    machine = finalization_reboot
    machine.state['native_variant'] = native_variant
    machine.state['finalization_retry']['completed'] = completed
    machine.state_file.write_text(json.dumps(machine.state))
    record = Mock()
    removal.finalization_retry_rebooted(record, 'denial-publication')
    if completed:
        machine.commands.run.assert_not_called()
        removal.guest.installed.assert_not_called()
    else:
        machine.commands.run.assert_called_once_with(['native-remove'], timeout=1800, merge_stderr=True)
        removal.check_remove_preflight.assert_called_once_with()
    machine.verify.assert_called_once_with(machine.state, record=record)
    assert machine.probe.call_args_list == [
        mock_call('login', role, 0, 'finalization.completed.' + role, record)
        for role in ('ordinary', 'other')]
    expected_launches = [] if completed else [
        mock_call(41002, True, variant=native_variant),
        mock_call(41003, True, variant=native_variant),
        mock_call(41001, False, variant=native_variant)]
    assert machine.launch.call_args_list == [
        *expected_launches, mock_call(41002, True, variant=native_variant)]
    assert record.call_args.args[0] == 'onpc.finalization.retry-finalized'


@pytest.mark.parametrize('fault', ['missing-state', 'variant', 'boot', 'identity', 'policy',
                                 'extensions', 'expiry', 'preflight', 'native-removal', 'removed-check'])
def test_finalization_retry_stops_at_failed_identity_or_recovery_boundary(finalization_reboot, monkeypatch, fault):
    machine = finalization_reboot
    if fault == 'missing-state':
        machine.state.pop('finalization_retry')
    elif fault == 'variant':
        machine.recovery['variant'] = 'account-finalization'
    elif fault == 'boot':
        monkeypatch.setattr(removal, 'boot', lambda: 'old')
    elif fault == 'identity':
        machine.kiosk.pw_uid += 1
    elif fault == 'policy':
        machine.recovery['policy'] = 'changed'
    elif fault == 'extensions':
        machine.recovery['extensions'] = []
    elif fault == 'expiry':
        monkeypatch.setattr(removal, 'current_expiry', lambda: 1)
    elif fault == 'preflight':
        removal.check_remove_preflight.side_effect = removal.guest.GuestError('fixture:preflight')
    elif fault == 'native-removal':
        machine.commands.run.side_effect = removal.guest.CommandError('fixture:native-removal')
    else:
        machine.verify.side_effect = removal.guest.GuestError('fixture:removed-check')
    machine.state_file.write_text(json.dumps(machine.state))
    record = Mock()
    with pytest.raises((KeyError, removal.guest.GuestError, removal.guest.CommandError)):
        removal.finalization_retry_rebooted(record, 'denial-publication')
    if fault not in ('native-removal', 'removed-check'):
        machine.commands.run.assert_not_called()
    else:
        assert machine.commands.run.call_count == 1
    if fault != 'removed-check':
        machine.verify.assert_not_called()
    machine.probe.assert_not_called()
    if fault in ('missing-state', 'variant', 'boot'):
        record.assert_not_called()
    else:
        assert [item.args[0] for item in record.call_args_list] == [
            'onpc.finalization.identity-comparison']
        comparison = json.loads(record.call_args.args[1])
        assert comparison['account_fields']['uid'] == (fault != 'identity')


@pytest.fixture
def interrupted_finalization(finalization_machine, monkeypatch, tmp_path):
    import system_kiosk_admission as admission
    import system_removal_faults as faults
    machine = finalization_machine
    payload = tmp_path / 'payload'
    payload.mkdir()
    (payload / 'before.json').write_text(json.dumps({'pam_services': {'original': 'bytes'}}))
    (payload / 'installed-files.json').write_text(json.dumps([{'path': machine.state['payload'][0]}]))
    monkeypatch.setattr(removal.guest, 'PAYLOAD', payload)
    machine.provision = Mock(return_value=machine.state['accounts'])
    monkeypatch.setattr(removal, 'provision_native', machine.provision)
    monkeypatch.setattr(removal, 'call', Mock(return_value=[json.dumps({
        'parent_control_enabled': False, 'apps': {}})]))
    monkeypatch.setattr(removal, 'accepted', lambda result: result)
    monkeypatch.setattr(removal, 'account_state', lambda uid: (b'prefs', 1, 3600, [0, 0], [False, []]))
    monkeypatch.setattr(removal, 'boot', lambda: 'old')
    for owner, name in [(removal, 'configure_restrictions'), (removal, 'wait_kiosk_inactive'),
        (removal.guest, 'retain_identity_for_redaction'), (removal.guest, 'verify_package_payload'),
        (removal.guest, 'verify_package_files'), (removal.guest, 'install_package'),
        (removal, 'verify_loaded_confinement'), (removal, 'check_remove_preflight'),
        (admission, 'verify_gates')]:
        monkeypatch.setattr(owner, name, Mock())
    monkeypatch.setattr(removal, 'removal_recovery_state', lambda: machine.saved)
    monkeypatch.setattr(removal, 'current_expiry', lambda: machine.saved['expires'])
    monkeypatch.setattr(removal, 'original_authselect', lambda: 'sssd')
    monkeypatch.setattr(removal, 'package_absent', lambda: False)
    monkeypatch.setattr(removal, 'removal_command', lambda: ['native-remove'])
    native_run = machine.run.side_effect
    machine.run.side_effect = lambda argv, **kwargs: (
        'install ok half-configured' if argv[0] == 'dpkg-query' else native_run(argv, **kwargs))
    # This fixture models only declared marker checks, never the host filesystem.
    monkeypatch.setattr(removal.os.path, 'lexists', lambda _: False)
    transaction = Mock(return_value=(b'onpc-removal-fault: selected finite interruption', 1))
    monkeypatch.setattr(removal, 'observe_aborted_transaction', transaction)
    fault = Mock()
    @contextmanager
    def interruption(variant, record):
        yield fault
    monkeypatch.setattr(faults, 'interruption_fault', interruption)
    interval, verify, save = Mock(), Mock(), Mock()
    monkeypatch.setattr(removal, 'verify_durable_interval', interval)
    monkeypatch.setattr(removal, 'verify_removed', verify)
    monkeypatch.setattr(removal, 'save_state', save)
    machine.transaction, machine.fault = transaction, fault
    machine.interval, machine.verify, machine.save = interval, verify, save
    return machine


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_finalization_initial_launch_failure_collects_policy_without_starting_removal(
        interrupted_finalization, monkeypatch, package_format):
    machine = interrupted_finalization
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.' + package_format))
    failure = removal.guest.GuestError('enforcement:expected-allow')
    machine.launch.side_effect = failure
    diagnostics = Mock()
    monkeypatch.setattr(removal, 'restriction_failure_diagnostics', diagnostics)
    with pytest.raises(removal.guest.GuestError) as caught:
        removal.interrupted_finalization_retry(Mock(), 'denial-publication')
    assert caught.value is failure
    assert diagnostics.call_count == (1 if package_format == 'rpm' else 0)
    native_variant = 'trusted-hard' if package_format == 'rpm' else 'command'
    machine.provision.assert_called_once_with(native_variant)
    machine.launch.assert_called_once_with(machine.state['accounts']['child'], True,
                                           variant=native_variant)
    removal.configure_restrictions.assert_not_called()
    machine.transaction.assert_not_called()
    machine.fault.verify_triggered.assert_not_called()
    machine.save.assert_not_called()
    removal.guest.install_package.assert_not_called()


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
@pytest.mark.parametrize('variant', removal.FINALIZATION_VARIANTS)
def test_interrupted_finalization_selects_only_supported_native_recovery(interrupted_finalization, monkeypatch, package_format, variant):
    machine = interrupted_finalization
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.' + package_format))
    if variant == 'account-finalization':
        machine.transaction.return_value = (b'onpc-removal-fault: account-finalization', 1)
    record = Mock()
    removal.interrupted_finalization_retry(record, variant)
    machine.fault.verify_triggered.assert_called_once_with()
    assert machine.transaction.call_args.args[2] is None
    state = machine.save.call_args.args[0]
    native_variant = 'trusted-hard' if package_format == 'rpm' else 'command'
    machine.provision.assert_called_once_with(native_variant)
    removal.configure_restrictions.assert_called_once_with(state['accounts'], variant=native_variant)
    assert state['native_variant'] == native_variant
    assert machine.launch.call_args_list[:3] == [
        mock_call(state['accounts'][role], True, variant=native_variant)
        for role in ('child', 'parent', 'other')]
    assert all(item.kwargs == {'variant': native_variant}
               for item in machine.launch.call_args_list)
    if variant != 'account-finalization':
        assert mock_call(state['accounts']['child'], False, variant=native_variant) in (
            machine.launch.call_args_list)
    assert state['finalization_retry']['variant'] == variant
    assert state['finalization_retry']['boot'] == 'old'
    assert state['finalization_retry']['kiosk_home'] == machine.recovery['kiosk_home']
    assert state['finalization_retry']['home_device'] == machine.home.lstat().st_dev
    if variant == 'account-finalization':
        machine.interval.assert_called_once()
    else:
        machine.interval.assert_not_called()
    if variant == 'account-finalization' and package_format == 'deb':
        machine.commands.run.assert_called_once_with(['native-remove'], timeout=1800, merge_stderr=True)
        machine.verify.assert_called_once_with(state, record=record)
        assert state['finalization_retry']['completed'] is True
    else:
        machine.commands.run.assert_not_called()
        machine.verify.assert_not_called()
        assert state['finalization_retry']['completed'] is False
        if package_format == 'rpm':
            removal.guest.install_package.assert_called_once_with()
        else:
            assert mock_call(['dpkg', '--configure', removal.PRODUCT], timeout=1800) in machine.run.call_args_list
    assert machine.save.call_count == 2


@pytest.mark.parametrize('fault', ['freshness', 'not-triggered', 'wrong-output', 'interval', 'retry'])
def test_interrupted_finalization_never_retries_after_failed_proof(interrupted_finalization, monkeypatch, fault):
    machine = interrupted_finalization
    if fault == 'freshness':
        monkeypatch.setattr(removal, 'call', Mock(return_value=[json.dumps({
            'parent_control_enabled': True, 'apps': {}})]))
    elif fault == 'not-triggered':
        machine.fault.verify_triggered.side_effect = removal.guest.GuestError('fixture:not-triggered')
    elif fault == 'wrong-output':
        machine.transaction.return_value = (b'unrelated callback failure', 1)
    elif fault == 'interval':
        machine.interval.side_effect = removal.guest.GuestError('fixture:interval')
    else:
        machine.commands.run.side_effect = removal.guest.CommandError('fixture:retry')
    if fault != 'wrong-output':
        machine.transaction.return_value = (b'onpc-removal-fault: account-finalization', 1)
    record = Mock()
    with pytest.raises((removal.guest.GuestError, removal.guest.CommandError)):
        removal.interrupted_finalization_retry(record, 'account-finalization')
    if fault == 'retry':
        assert machine.commands.run.call_count == 1
    else:
        machine.commands.run.assert_not_called()
    machine.verify.assert_not_called()
    removal.guest.install_package.assert_not_called()
    assert all(item.args[0] != 'onpc.finalization.owned-recovery' for item in record.call_args_list)


def test_interrupted_finalization_preserves_foreign_recovery_records(interrupted_finalization, monkeypatch):
    machine = interrupted_finalization
    monkeypatch.setattr(removal, 'admission_removal_state', Mock(side_effect=[
        {'ordinary-pam': None}, {'ordinary-pam': 'foreign-change'}]))
    with pytest.raises(removal.guest.GuestError, match='foreign-or-ownership-state-changed'):
        removal.interrupted_finalization_retry(Mock(), 'denial-publication')
    machine.commands.run.assert_not_called()
    removal.guest.install_package.assert_not_called()


@pytest.mark.parametrize('status', ['install ok installed', 'install ok half-configured', 'unexpected'])
def test_deb_finalization_rearm_uses_actual_native_configuration_state(interrupted_finalization, status):
    machine = interrupted_finalization
    native_run = machine.run.side_effect
    machine.run.side_effect = lambda argv, **kwargs: (
        status if argv[0] == 'dpkg-query' else native_run(argv, **kwargs))
    if status == 'unexpected':
        with pytest.raises(removal.guest.GuestError, match='unexpected-rearm-package-status'):
            removal.interrupted_finalization_retry(Mock(), 'denial-publication')
    else:
        removal.interrupted_finalization_retry(Mock(), 'denial-publication')
    configurations = [item for item in machine.run.call_args_list
                      if item.args[0][:2] == ['dpkg', '--configure']]
    assert len(configurations) == (1 if status == 'install ok half-configured' else 0)


@pytest.mark.parametrize('entry', ['ownership_refusal_retry', 'ownership_retry_rebooted'])
def test_ownership_entry_guard_precedes_setup(monkeypatch, entry):
    monkeypatch.setattr(removal.guest, 'guard', Mock(side_effect=removal.guest.GuestError('identity')))
    start, commands = Mock(), Mock()
    monkeypatch.setattr(removal, 'focused_recovery_start', start)
    monkeypatch.setattr(removal.guest, 'commands', commands)
    with pytest.raises(removal.guest.GuestError, match='identity'):
        getattr(removal, entry)(Mock(), 'systemd-user-edit')
    start.assert_not_called()
    commands.run.assert_not_called()


@pytest.fixture
def ownership_machine(finalization_machine, monkeypatch):
    import system_kiosk_admission as admission
    import system_removal_ownership as ownership
    machine = finalization_machine
    machine.state['hook'] = '/etc/gdm3/PreSession/Default'
    machine.state['ownership_retry'] = machine.recovery
    before = {'recovery': (0o600, 0, 0, 'original')}
    start = Mock(return_value=(machine.state, machine.recovery, machine.saved, before, {}))
    monkeypatch.setattr(removal, 'focused_recovery_start', start)
    monkeypatch.setattr(removal, 'admission_removal_state', Mock(return_value=dict(before)))
    monkeypatch.setattr(removal.os.path, 'lexists', lambda _: False)
    for owner, name in [(removal, 'verify_surviving_identity'), (removal, 'verify_loaded_confinement'),
                        (removal, 'wait_kiosk_inactive'), (removal.guest, 'verify_package_payload'),
                        (removal.guest, 'verify_package_files'), (removal, 'check_remove_preflight'),
                        (admission, 'verify_gates')]:
        monkeypatch.setattr(owner, name, Mock())
    monkeypatch.setattr(removal, 'package_absent', lambda: False)
    monkeypatch.setattr(removal, 'removal_command', lambda: ['native-remove'])
    monkeypatch.setattr(removal, 'boot', lambda: 'old')
    machine.commands.last_returncode = 1
    machine.commands.run.return_value = b'invalid original PAM selection'
    machine.run.return_value = 'install ok half-configured'
    machine.run.side_effect = None
    monkeypatch.setattr(removal.guest, 'install_package', Mock())
    expiry = [1]
    monkeypatch.setattr(removal, 'current_expiry', lambda: expiry[0])
    def rearmed():
        expiry[0] = machine.saved['expires']
        journal = machine.path('/var/lib/oh-no-parent-control/kiosk-configuration-account.json')
        if journal.exists():
            journal.unlink()
    removal.guest.verify_package_files.side_effect = rearmed
    machine.write('/var/lib/oh-no-parent-control/uninstall-broker-mask', '')
    mask = machine.path('/run/systemd/system/oh-no-parent-control-broker.service')
    mask.parent.mkdir(parents=True, exist_ok=True)
    mask.symlink_to('/dev/null')
    native_readlink = os.readlink
    monkeypatch.setattr(removal.os, 'readlink', lambda target: native_readlink(
        machine.path(target) if str(target).startswith('/run/') else target))
    conflict = Mock()
    events = []
    @contextmanager
    def fixture(variant, target, foreign_uid, record):
        events.append(('start', variant, str(target), foreign_uid))
        try:
            yield conflict
        finally:
            events.append(('resolved', variant))
    monkeypatch.setattr(ownership, 'ownership_conflict', fixture)
    save = Mock()
    monkeypatch.setattr(removal, 'save_state', save)
    machine.start, machine.conflict, machine.events, machine.save = start, conflict, events, save
    return machine


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
@pytest.mark.parametrize('variant', ['systemd-user-edit', 'gdm-password-link', 'systemd-user-link',
    'gdm-hook-link', 'confinement-record-owner', 'confinement-record-link', 'confinement-record-uid'])
def test_ownership_refusal_preserves_proofs_before_owned_resolution(ownership_machine, monkeypatch,
                                                                 package_format, variant):
    machine = ownership_machine
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.' + package_format))
    machine.recovery['variant'] = variant
    reasons = {
        'systemd-user-edit': (b'invalid original authselect selection' if package_format == 'rpm'
                              else b'invalid original PAM selection'),
        'gdm-password-link': (b'unsafe authselect ownership or substituted path' if package_format == 'rpm'
                              else b'unsafe original PAM selection'),
        'systemd-user-link': b'refusing substituted child trust integration',
        'gdm-hook-link': b'system integration was modified; preserving it and refusing removal',
        'confinement-record-owner': b'unsafe-migration-file',
        'confinement-record-link': b'[Errno 40]',
        'confinement-record-uid': b'changed-kiosk-expiry-record',
    }
    machine.commands.run.return_value = reasons[variant]
    record = Mock()
    removal.ownership_refusal_retry(record, variant)
    machine.commands.run.assert_called_once_with(['native-remove'], check=False, timeout=1800,
                                                 merge_stderr=True)
    assert machine.events[0][1] == variant
    baseline = ('fedora-authselect.json' if package_format == 'rpm'
                else 'malcontent-pam-before-install')
    expected_target = {
        'systemd-user-edit': '/var/lib/oh-no-parent-control/' + baseline,
        'gdm-password-link': '/var/lib/oh-no-parent-control/' + baseline,
        'systemd-user-link': '/var/lib/oh-no-parent-control/installed-child-extension-trust',
        'gdm-hook-link': '/etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules',
    }.get(variant, '/var/lib/oh-no-parent-control/kiosk-configuration-account.json')
    assert machine.events[0][2] == expected_target
    assert machine.events[0][3] == machine.state['accounts']['other']
    assert machine.events[1] == ('resolved', variant)
    assert machine.conflict.verify.call_count == 2
    removal.guest.verify_package_payload.assert_called_once_with()
    removal.guest.verify_package_files.assert_called_once_with()
    assert machine.save.call_args.args[0]['ownership_retry']['boot'] == 'old'
    names = [item.args[0] for item in record.call_args_list]
    assert names == ['onpc.ownership.target', 'onpc.ownership.native-status',
                     'onpc.ownership.refused', 'onpc.ownership.resolved']
    configurations = [item for item in machine.run.call_args_list
                      if item.args[0][:2] == ['dpkg', '--configure']]
    assert len(configurations) == (package_format == 'deb')


@pytest.mark.parametrize('fault', ['status', 'reason', 'payload', 'conflict', 'identity',
                                  'records', 'policy', 'MAC', 'ordinary'])
def test_ownership_failed_proof_never_rearms_or_claims_resolution(ownership_machine, monkeypatch, fault):
    machine = ownership_machine
    error = removal.guest.GuestError('fixture:' + fault)
    if fault == 'status':
        machine.commands.last_returncode = 0
    elif fault == 'reason':
        machine.commands.run.return_value = b'unrelated failure'
    elif fault == 'payload':
        removal.guest.verify_package_payload.side_effect = error
    elif fault == 'conflict':
        machine.conflict.verify.side_effect = error
    elif fault == 'identity':
        removal.verify_surviving_identity.side_effect = error
    elif fault == 'records':
        removal.admission_removal_state.return_value = {'recovery': 'changed'}
    elif fault == 'policy':
        machine.recovery['policy'] = 'changed'
    elif fault == 'MAC':
        removal.verify_loaded_confinement.side_effect = error
    else:
        machine.probe.side_effect = [None, None, error]
    record = Mock()
    with pytest.raises(removal.guest.GuestError):
        removal.ownership_refusal_retry(record, 'systemd-user-edit')
    removal.guest.verify_package_files.assert_not_called()
    machine.save.assert_not_called()
    assert all(item.args[0] != 'onpc.ownership.resolved' for item in record.call_args_list)


def test_admission_snapshot_excludes_only_conflict_under_separate_identity_guard(admission_records):
    path, _, _ = admission_records
    target = path('/var/lib/oh-no-parent-control/kiosk-configuration-account.json')
    target.symlink_to('foreign')
    result = removal.admission_removal_state(exclude=(str(target),))
    assert str(target) not in result
    assert str(path('/var/lib/oh-no-parent-control/package-created-kiosk-uid')) in result
    with pytest.raises(removal.guest.GuestError, match='unsafe-admission-record'):
        removal.admission_removal_state()


@pytest.mark.parametrize('entry', ['identity_filesystem_refusal_retry',
                                 'identity_filesystem_retry_rebooted'])
def test_identity_filesystem_guard_precedes_setup(monkeypatch, entry):
    monkeypatch.setattr(removal.guest, 'guard', Mock(side_effect=removal.guest.GuestError('identity')))
    start = Mock()
    monkeypatch.setattr(removal, 'focused_recovery_start', start)
    with pytest.raises(removal.guest.GuestError, match='identity'):
        getattr(removal, entry)(Mock(), 'home-owner')
    start.assert_not_called()


@pytest.fixture
def identity_filesystem_machine(ownership_machine, monkeypatch):
    import system_removal_identity as identity
    machine = ownership_machine
    machine.state['identity_filesystem_retry'] = machine.recovery
    conflict = machine.conflict
    conflict.variant = 'state-owner'
    conflict.preflight = True
    conflict.expected_marker_uid = None
    conflict.reason = b'exact-ownership-refusal'
    machine.commands.run.return_value = conflict.reason
    durable, removed = Mock(), Mock()
    monkeypatch.setattr(removal, 'verify_durable_interval', durable)
    monkeypatch.setattr(removal, 'verify_removed', removed)
    def private_record(target):
        removal.guest.require(stat.S_IMODE(target.lstat().st_mode) == 0o600,
                              'fixture:unsafe-private-record')
        return SimpleNamespace(contents=target.read_bytes())
    monkeypatch.setattr(removal, 'private_recovery_record', private_record)
    monkeypatch.setattr(removal.guest, 'install_package', Mock())
    monkeypatch.setattr(removal, 'account_state', lambda _: (
        b'preferences', 1, 3600, [0, 0], [False, []]))
    snapshot_path = machine.write('/var/lib/oh-no-parent-control/uninstall-enforcement.json',
        json.dumps({'version': 1, 'accounts': [{'uid': machine.state['accounts']['child'],
            'limit_type': 1, 'daily_limit': 3600, 'active_extension': [0, 0],
            'app_filter': [False, []], 'extension_enabled': True}]}))
    snapshot_path.chmod(0o600)
    machine.write('/var/lib/oh-no-parent-control/uninstall-broker-mask', '')
    mask = machine.path('/run/systemd/system/oh-no-parent-control-broker.service')
    lstat = Path.lstat
    def root_mask_info(path):
        info = lstat(path)
        if path == mask:
            fields = list(info)
            fields[4] = 0
            return os.stat_result(fields)
        return info
    monkeypatch.setattr(Path, 'lstat', root_mask_info)
    machine.write('/var/lib/oh-no-parent-control/fedora-authselect.json',
                  json.dumps({'version': 1, 'phase': 'installed', 'original': ['sssd']})).chmod(0o600)
    machine.write('/var/lib/oh-no-parent-control/fedora-execution-policy.json', 'execution-provenance').chmod(0o600)
    @contextmanager
    def fixture(variant, foreign_uid, record):
        conflict.variant = variant
        conflict.preflight = variant in ('kiosk-marker-uid', 'home-owner', 'home-link',
                                         'state-owner', 'state-link')
        machine.events.append(('start', variant))
        try:
            if not conflict.preflight:
                machine.write('/var/lib/oh-no-parent-control/fedora-authselect.json',
                              json.dumps({'version': 1, 'phase': 'restored', 'original': ['sssd']}))
            yield conflict
        finally:
            machine.events.append(('resolved', variant))
    monkeypatch.setattr(identity, 'identity_filesystem_conflict', fixture)
    machine.durable_interval, machine.removed = durable, removed
    return machine


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
@pytest.mark.parametrize('variant', ['kiosk-marker-uid', 'home-owner', 'home-link',
                                  'home-mount', 'state-owner', 'state-link', 'state-mount'])
def test_identity_filesystem_refusal_keeps_native_stage_and_owned_retry(
    identity_filesystem_machine, monkeypatch, package_format, variant,
):
    machine = identity_filesystem_machine
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.' + package_format))
    machine.recovery['variant'] = variant
    record = Mock()
    removal.identity_filesystem_refusal_retry(record, variant)
    preflight = variant in ('kiosk-marker-uid', 'home-owner', 'home-link',
                           'state-owner', 'state-link')
    completed = not preflight and package_format == 'deb'
    assert machine.commands.run.call_args_list[0] == mock_call(
        ['native-remove'], check=False, timeout=1800, merge_stderr=True)
    assert machine.commands.run.call_count == 1 + completed
    assert machine.events == [('start', variant), ('resolved', variant)]
    assert machine.conflict.verify.call_count == 2
    assert machine.durable_interval.call_count == (not preflight)
    if not preflight:
        assert machine.durable_interval.call_args.kwargs == {'conflict': machine.conflict}
    assert machine.removed.call_count == completed
    assert removal.guest.install_package.call_count == (package_format == 'rpm')
    assert machine.recovery['completed'] == completed
    assert machine.save.call_args.args[0]['identity_filesystem_retry']['boot'] == 'old'
    assert record.call_args.args[0] == 'onpc.identity-filesystem.resolved'


@pytest.mark.parametrize('fault', ['reason', 'status', 'foreign-state', 'durable', 'identity',
                                  'snapshot', 'mask', 'retry', 'final-state'])
def test_identity_filesystem_failed_proof_never_claims_resolution(
    identity_filesystem_machine, monkeypatch, fault,
):
    machine = identity_filesystem_machine
    error = removal.guest.GuestError('fixture:' + fault)
    if fault == 'reason':
        machine.commands.run.return_value = b'unrelated failure'
    elif fault == 'status':
        machine.commands.last_returncode = 0
    elif fault == 'foreign-state':
        machine.conflict.verify.side_effect = error
    elif fault == 'durable':
        machine.durable_interval.side_effect = error
    elif fault == 'identity':
        removal.verify_surviving_identity.side_effect = error
    elif fault == 'snapshot':
        machine.write('/var/lib/oh-no-parent-control/uninstall-enforcement.json',
                      json.dumps({'version': 1, 'accounts': []})).chmod(0o600)
    elif fault == 'mask':
        machine.path('/run/systemd/system/oh-no-parent-control-broker.service').unlink()
        machine.path('/run/systemd/system/oh-no-parent-control-broker.service').symlink_to('/foreign')
    elif fault == 'retry':
        machine.commands.run.side_effect = [machine.conflict.reason, error]
    else:
        machine.removed.side_effect = error
    record = Mock()
    with pytest.raises(removal.guest.GuestError):
        removal.identity_filesystem_refusal_retry(record, 'home-mount')
    machine.save.assert_not_called()
    assert all(item.args[0] != 'onpc.identity-filesystem.resolved' for item in record.call_args_list)


@pytest.mark.parametrize('variant', ['home-owner', 'home-link', 'kiosk-marker-uid', 'state-mount'])
def test_durable_ownership_interval_keeps_identity_and_foreign_state_guards(
    finalization_machine, variant,
):
    machine = finalization_machine
    conflict = SimpleNamespace(variant=variant, expected_marker_uid=None, verify=Mock())
    if variant.startswith('home-'):
        # The foreign home has its own exact descriptor-bound fixture witness.
        machine.recovery['kiosk_home'][3] += 1
    elif variant == 'kiosk-marker-uid':
        conflict.expected_marker_uid = 41003
        machine.write('/var/lib/oh-no-parent-control/package-created-kiosk-uid', '41003\n')
    removal.verify_durable_interval(machine.state, machine.recovery, machine.saved, Mock(),
                                    conflict=conflict)
    conflict.verify.assert_called_once_with()
    assert machine.durable.call_count == 6
    machine.kiosk.pw_uid += 1
    with pytest.raises(removal.guest.GuestError, match='kiosk-identity-changed'):
        removal.verify_durable_interval(machine.state, machine.recovery, machine.saved, Mock(),
                                        conflict=conflict)


@pytest.mark.parametrize('gid', [0, 10, 27])
@pytest.mark.parametrize('fault', [None, 'owner', 'mode', 'link', 'type'])
def test_private_recovery_record_accepts_only_root_private_single_regular_file(monkeypatch, gid, fault):
    import system_removal_ownership as ownership
    info = [1, 2, 0, gid, stat.S_IFREG | 0o600, 1]
    if fault == 'owner':
        info[2] = 1000
    elif fault == 'mode':
        info[4] |= 0o040
    elif fault == 'link':
        info[5] = 2
    elif fault == 'type':
        info[4] = stat.S_IFLNK | 0o600
    value = ownership.Witness(tuple(info), 0, (), b'provenance')
    monkeypatch.setattr(ownership, 'witness', Mock(return_value=value))
    if fault:
        with pytest.raises(removal.guest.GuestError, match='unsafe-recovery-record'):
            removal.private_recovery_record(Path('/fixed-record'))
    else:
        assert removal.private_recovery_record(Path('/fixed-record')) == value


@pytest.mark.parametrize('completed', [False, True])
@pytest.mark.parametrize('fault', [None, 'variant', 'boot', 'request', 'native-removal', 'removed-check'])
def test_identity_filesystem_retry_requires_its_complete_history(
    finalization_reboot, monkeypatch, completed, fault,
):
    machine = finalization_reboot
    machine.recovery.update(variant='home-owner', completed=completed)
    machine.state['identity_filesystem_retry'] = machine.recovery
    if fault == 'variant':
        machine.recovery['variant'] = 'home-link'
    if fault == 'boot':
        monkeypatch.setattr(removal, 'boot', lambda: 'old')
    monkeypatch.setattr(removal.guest, 'reboot_cleared', lambda: fault != 'request')
    if fault == 'native-removal':
        machine.commands.run.side_effect = removal.guest.GuestError('native-removal')
    elif fault == 'removed-check':
        machine.verify.side_effect = removal.guest.GuestError('removed-check')
    machine.state_file.write_text(json.dumps(machine.state))
    record = Mock()
    fails = fault is not None and not (completed and fault == 'native-removal')
    if fails:
        with pytest.raises(removal.guest.GuestError):
            removal.identity_filesystem_retry_rebooted(record, 'home-owner')
        assert all(item.args[0] != 'onpc.identity-filesystem.retry-finalized'
                   for item in record.call_args_list)
    else:
        removal.identity_filesystem_retry_rebooted(record, 'home-owner')
        assert record.call_args.args[0] == 'onpc.identity-filesystem.retry-finalized'
    assert machine.commands.run.call_count == (not completed and fault not in ('variant', 'boot', 'request'))


@pytest.mark.parametrize('fault', [None, 'variant', 'boot', 'request', 'identity',
                                  'preflight', 'native-removal', 'removed-check'])
def test_ownership_reboot_requires_continuous_proof_before_finalization(finalization_reboot,
                                                                     monkeypatch, fault):
    machine = finalization_reboot
    machine.recovery['variant'] = 'systemd-user-edit'
    machine.state['ownership_retry'] = machine.recovery
    machine.state_file.write_text(json.dumps(machine.state))
    monkeypatch.setattr(removal.guest, 'reboot_cleared', lambda: fault != 'request')
    identity = Mock()
    monkeypatch.setattr(removal, 'verify_surviving_identity', identity)
    if fault == 'variant':
        machine.recovery['variant'] = 'gdm-hook-link'
        machine.state_file.write_text(json.dumps(machine.state))
    elif fault == 'boot':
        monkeypatch.setattr(removal, 'boot', lambda: 'old')
    elif fault == 'identity':
        identity.side_effect = removal.guest.GuestError('identity')
    elif fault == 'preflight':
        removal.check_remove_preflight.side_effect = removal.guest.CommandError('preflight')
    elif fault == 'native-removal':
        machine.commands.run.side_effect = removal.guest.CommandError('native-removal')
    elif fault == 'removed-check':
        machine.verify.side_effect = removal.guest.GuestError('removed-check')
    record = Mock()
    if fault:
        with pytest.raises((removal.guest.GuestError, removal.guest.CommandError)):
            removal.ownership_retry_rebooted(record, 'systemd-user-edit')
        assert all(item.args[0] != 'onpc.ownership.retry-finalized'
                   for item in record.call_args_list)
        if fault not in ('native-removal', 'removed-check'):
            machine.commands.run.assert_not_called()
        if fault != 'removed-check':
            machine.verify.assert_not_called()
    else:
        removal.ownership_retry_rebooted(record, 'systemd-user-edit')
        machine.commands.run.assert_called_once_with(['native-remove'], timeout=1800,
                                                     merge_stderr=True)
        machine.verify.assert_called_once_with(machine.state, record=record)
        assert record.call_args.args[0] == 'onpc.ownership.retry-finalized'


@pytest.fixture
def rpm_posterase_machine(identity_filesystem_machine, monkeypatch):
    machine = identity_filesystem_machine
    machine.recovery['variant'] = 'rpm-posterase'
    machine.state['rpm_posterase'] = machine.recovery
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.rpm'))
    monkeypatch.setattr(removal, 'package_absent', Mock(return_value=True))
    # DNF can itself fail after erasure; the CLI then never reaches its later
    # saved-data check. Exact callback diagnostics and actual state own proof.
    machine.commands.run.return_value = b'postun exact-ownership-refusal native-transaction-failed'
    machine.path('/var/log/oh-no-parent-control').mkdir(parents=True)
    def reinstall(*args):
        assert machine.events == [('start', 'home-mount')]
        machine.events.append(('restored', 'before-conflict-release'))
    machine.reinstall = Mock(side_effect=reinstall)
    monkeypatch.setattr(removal, 'observe_rpm_reinstall', machine.reinstall)
    return machine


def test_rpm_posterase_keeps_retained_proofs_and_rearms_before_conflict_release(rpm_posterase_machine):
    machine = rpm_posterase_machine
    record = Mock()
    removal.rpm_posterase_recovery(record)
    machine.start.assert_called_once_with(record, 'rpm-posterase', 'rpm_posterase')
    machine.commands.run.assert_called_once_with(
        ['/usr/bin/oh-no-parent-control-purge', '--yes'], check=False, timeout=1800,
        merge_stderr=True)
    machine.durable_interval.assert_called_once_with(
        machine.state, machine.recovery, machine.saved, record, conflict=machine.conflict)
    assert machine.conflict.verify.call_count == 2
    assert machine.events == [('start', 'home-mount'), ('restored', 'before-conflict-release'),
                              ('resolved', 'home-mount')]
    assert machine.save.call_args.args[0]['rpm_posterase']['boot'] == 'old'
    assert machine.recovery['ordinary_native'] == {
        'parent': 'policy-41002', 'other': 'policy-41003'}
    assert [item.args[0] for item in record.call_args_list] == [
        'onpc.rpm-posterase.failed-purge-status', 'onpc.rpm-posterase.retained',
        'onpc.rpm-posterase.reinstalled', 'onpc.rpm-posterase.resolved']


@pytest.mark.parametrize('fault', ['platform', 'status', 'present', 'postun', 'reason',
    'accepted', 'durable', 'snapshot', 'mask', 'authselect', 'provenance',
    'logs', 'intent', 'reinstall', 'payload', 'conflict', 'identity', 'policy',
    'extensions', 'MAC', 'gates', 'guards'])
def test_rpm_posterase_failed_proof_never_claims_resolution(rpm_posterase_machine, monkeypatch, fault):
    import system_kiosk_admission as admission
    machine = rpm_posterase_machine
    error = removal.guest.GuestError('fixture:' + fault)
    if fault == 'platform':
        monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.deb'))
    elif fault == 'status':
        machine.commands.last_returncode = 0
    elif fault == 'present':
        removal.package_absent.return_value = False
    elif fault in ('postun', 'reason', 'accepted'):
        output = machine.commands.run.return_value
        token = {'postun': b'postun', 'reason': machine.conflict.reason}.get(fault)
        machine.commands.run.return_value = (output.replace(token, b'') if token else
            output + b' saved-state purge outcome=accepted')
    elif fault == 'snapshot':
        machine.write('/var/lib/oh-no-parent-control/uninstall-enforcement.json',
                      json.dumps({'version': 1, 'accounts': []}))
    elif fault == 'mask':
        machine.path('/run/systemd/system/oh-no-parent-control-broker.service').unlink()
        machine.path('/run/systemd/system/oh-no-parent-control-broker.service').symlink_to('/foreign')
    elif fault in ('authselect', 'provenance'):
        original = removal.private_recovery_record
        reads = {}
        def altered(path):
            value = original(path)
            reads[path.name] = reads.get(path.name, 0) + 1
            target = 'fedora-authselect.json' if fault == 'authselect' else 'fedora-execution-policy.json'
            if path.name == target and reads[path.name] > 1:
                return SimpleNamespace(contents=b'{}')
            return value
        monkeypatch.setattr(removal, 'private_recovery_record', altered)
    elif fault == 'logs':
        machine.path('/var/log/oh-no-parent-control').rmdir()
    elif fault in ('intent', 'guards'):
        suffix = ('/run/oh-no-parent-control-purge-intent.json' if fault == 'intent'
                  else '/var/lib/oh-no-parent-control/migration-in-progress')
        monkeypatch.setattr(removal.os.path, 'lexists', lambda value: str(value).endswith(suffix))
    elif fault in ('policy', 'extensions'):
        machine.reinstall.side_effect = lambda *args: machine.recovery.update(
            {fault: 'changed'})
    else:
        target = {'durable': machine.durable_interval, 'reinstall': machine.reinstall,
            'payload': removal.guest.verify_package_files, 'conflict': machine.conflict.verify,
            'identity': removal.verify_surviving_identity, 'MAC': removal.verify_loaded_confinement,
            'gates': admission.verify_gates}[fault]
        target.side_effect = error
    record = Mock()
    with pytest.raises(removal.guest.GuestError):
        removal.rpm_posterase_recovery(record)
    machine.save.assert_not_called()
    assert not {'onpc.rpm-posterase.reinstalled', 'onpc.rpm-posterase.resolved'} & {
        item.args[0] for item in record.call_args_list}
    if fault in ('platform', 'status', 'present', 'postun', 'reason', 'accepted',
                 'durable', 'snapshot', 'mask', 'authselect', 'provenance', 'logs', 'intent'):
        machine.reinstall.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'platform', 'variant', 'boot', 'request', 'identity',
    'policy', 'extensions', 'MAC', 'gates', 'preflight', 'purge', 'removed', 'accepted',
    'notice', 'reboot', 'intent', 'ordinary-identity', 'ordinary-native',
    'ordinary-extensions', 'login', 'password'])
def test_rpm_posterase_reboot_requires_complete_history_before_completion(
    finalization_reboot, monkeypatch, fault,
):
    import system_kiosk_admission as admission
    machine = finalization_reboot
    machine.recovery.update(variant='rpm-posterase', ordinary_native={
        role: value['policy'] for role, value in machine.recovery['ordinary'].items()})
    machine.state['rpm_posterase'] = machine.recovery
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path(
        'package.deb' if fault == 'platform' else 'package.rpm'))
    monkeypatch.setattr(removal.guest, 'reboot_cleared', lambda: fault != 'request')
    monkeypatch.setattr(removal.guest, 'reboot_requested', lambda: fault != 'reboot')
    monkeypatch.setattr(removal.os.path, 'lexists', lambda value: fault == 'intent')
    identity, password = Mock(), Mock()
    monkeypatch.setattr(removal, 'verify_surviving_identity', identity)
    monkeypatch.setattr(removal, 'password_login_health', password)
    output = b'saved-state purge outcome=accepted ' + removal.REMOVAL_NOTICE.encode()
    machine.commands.run.return_value = output
    error = removal.guest.GuestError('fixture:' + str(fault))
    if fault == 'variant':
        machine.recovery['variant'] = 'other-phase'
    elif fault == 'boot':
        monkeypatch.setattr(removal, 'boot', lambda: 'old')
    elif fault in ('policy', 'extensions'):
        machine.recovery[fault] = 'changed'
    elif fault in ('accepted', 'notice'):
        machine.commands.run.return_value = (removal.REMOVAL_NOTICE.encode() if fault == 'accepted'
                                            else b'saved-state purge outcome=accepted')
    elif fault == 'ordinary-identity':
        machine.ordinary[41002].pw_shell = '/bin/false'
    elif fault == 'ordinary-native':
        machine.recovery['ordinary_native']['parent'] = 'changed'
    elif fault == 'ordinary-extensions':
        machine.recovery['ordinary']['parent']['extensions'] = []
    elif fault in ('identity', 'MAC', 'gates', 'preflight', 'purge', 'removed', 'login', 'password'):
        target = {'identity': identity, 'MAC': removal.verify_loaded_confinement,
            'gates': admission.verify_gates, 'preflight': removal.check_remove_preflight,
            'purge': machine.commands.run, 'removed': machine.verify,
            'login': machine.probe, 'password': password}[fault]
        target.side_effect = error
    machine.state_file.write_text(json.dumps(machine.state))
    record = Mock()
    if fault:
        with pytest.raises(removal.guest.GuestError):
            removal.rpm_posterase_reinstalled_rebooted(record)
        assert all(item.args[0] != 'onpc.rpm-posterase.completed'
                   for item in record.call_args_list)
    else:
        removal.rpm_posterase_reinstalled_rebooted(record)
        machine.verify.assert_called_once_with(machine.state, purged=True, record=record)
        password.assert_called_once_with(machine.state['accounts']['child'])
        assert record.call_args.args[0] == 'onpc.rpm-posterase.completed'
    if fault in ('platform', 'variant', 'boot', 'request', 'identity', 'policy', 'extensions',
                 'MAC', 'gates', 'preflight'):
        machine.commands.run.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'guard', 'command', 'cancel', 'watcher', 'snapshot',
                                 'marker', 'marker-bytes', 'marker-uid', 'marker-phase',
                                 'marker-expiry', 'native-expiry', 'policy', 'extensions', 'rules',
                                 'execution', 'release-during-execution',
                                 'release-during-read', 'finished-before-observation'])
def test_rpm_reinstall_observer_requires_bracketed_restoration_and_joins_worker(
    tmp_path, monkeypatch, fault,
):
    import guest_install_recipe
    def path(value):
        if str(value).startswith(str(tmp_path)):
            return Path(value)
        return tmp_path / str(value).lstrip('/')
    marker = path('/var/lib/oh-no-parent-control/kiosk-configuration-account.json')
    marker.parent.mkdir(parents=True)
    quarantine = {'version': 1, 'uid': 41000, 'expires': None, 'phase': 'quarantined'}
    current = dict(quarantine)
    if fault and fault.startswith('marker-'):
        field = fault.removeprefix('marker-')
        if field in ('uid', 'phase', 'expiry'):
            current[{'expiry': 'expires'}.get(field, field)] = {
                'uid': 41003, 'phase': 'releasing', 'expiry': 123}[field]
    if fault != 'marker':
        marker.write_bytes(b'foreign' if fault == 'marker-bytes' else json.dumps(current).encode())
    marker.with_name('package-created-kiosk-uid').write_bytes(b'41000\n')
    snapshot = marker.with_name('uninstall-enforcement.json')
    if fault == 'snapshot':
        snapshot.write_bytes(b'retained')
    rules = path('/etc/fapolicyd/rules.d/owned.rules')
    rules.parent.mkdir(parents=True)
    rules.write_bytes(b'changed' if fault == 'rules' else b'restored')
    events = []
    transaction = SimpleNamespace(directory=None)
    failure = (KeyboardInterrupt() if fault == 'cancel' else
               removal.guest.CommandError('native-install-failed'))
    def run(arguments, **kwargs):
        events.append('install')
        assert arguments == ['make', 'install']
        assert kwargs == {'timeout': 1800, 'merge_stderr': True}
        if fault in ('command', 'cancel'):
            raise failure
        return b' installed\n'
    transaction.run = run
    def install(run, guard, package):
        guard()
        assert package == Path('package.rpm')
        assert run(['make', 'install'], timeout=1800) == 'installed'
    monkeypatch.setattr(guest_install_recipe, 'install', install)
    monkeypatch.setattr(removal, 'Path', path)
    native_lexists = os.path.lexists
    monkeypatch.setattr(removal.os.path, 'lexists', lambda value: native_lexists(path(value)))
    monkeypatch.setattr(removal.guest, 'Commands', lambda: transaction)
    monkeypatch.setattr(removal.guest, 'commands', SimpleNamespace(directory=tmp_path / 'commands'))
    monkeypatch.setattr(removal.guest, 'guard', Mock(side_effect=(
        removal.guest.GuestError('identity') if fault == 'guard' else None)))
    monkeypatch.setattr(removal.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.rpm'))
    monkeypatch.setattr(removal, 'current_expiry', lambda: None if fault == 'native-expiry' else 1)
    monkeypatch.setattr(removal, 'private_recovery_record', lambda target:
                        SimpleNamespace(contents=target.read_bytes()))
    class Worker:
        def __init__(self, *, target, name):
            assert name == 'onpc-rpm-reinstall'
            self.target = target
            self.alive = iter([fault != 'finished-before-observation', False])
        def start(self):
            self.target()
        def is_alive(self):
            return next(self.alive)
        def join(self):
            events.append('joined')
    monkeypatch.setattr(removal.threading, 'Thread', Worker)
    monkeypatch.setattr(removal.time, 'sleep', lambda _: None)
    def digest(uid):
        assert uid == 41001
        if fault == 'watcher':
            raise RuntimeError('read-failed')
        return 'changed' if fault == 'policy' else 'policy'
    monkeypatch.setattr(removal, 'account_digest', digest)
    def launch(uid, allowed, **options):
        assert uid == 41001 and allowed is False
        assert options == {'variant': 'command'}
        if fault != 'release-during-read':
            assert json.loads(marker.read_bytes()) == quarantine
        if fault == 'execution':
            raise removal.guest.GuestError('fixture:execution-not-denied')
        if fault == 'release-during-execution':
            marker.unlink()
    monkeypatch.setattr(removal, 'observe_launch', launch)
    def extensions(uid):
        if fault == 'release-during-read':
            marker.unlink()
        return [] if fault == 'extensions' else ['extension']
    monkeypatch.setattr(removal, 'extension_lists', extensions)
    record = Mock()
    def observe():
        removal.observe_rpm_reinstall({'accounts': {'child': 41001}},
            {'policy': 'policy', 'extensions': ['extension'], 'kiosk_identity': [41000], 'expires': None},
            {'/etc/fapolicyd/rules.d/owned.rules': b'restored'}, record)
    if fault:
        with pytest.raises((removal.guest.GuestError, RuntimeError, KeyboardInterrupt)) as caught:
            observe()
        if fault in ('command', 'cancel'):
            assert caught.value is failure
        record.assert_not_called()
    else:
        observe()
        assert record.call_args.args[0] == 'onpc.rpm-posterase.restored-before-release'
    assert events == ([] if fault == 'guard' else ['install', 'joined'])
    if fault != 'guard':
        assert transaction.directory.parent == tmp_path
        assert transaction.directory.name.startswith('rpm-reinstall-')
