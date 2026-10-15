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
                                 'mounted_pam_fault',
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
            if entry == 'mounted_pam_fault':
                with removal.mounted_pam_fault(Mock()):
                    pass
            else:
                getattr(removal, entry)(Mock())
    diagnostics.assert_not_called()
    commands.run.assert_not_called()


@pytest.mark.parametrize('arguments', [[], ['remove'], ['exercise-live-refusals', 'extra'],
                                     ['exercise-live-finalization'],
                                     ['exercise-live-finalization', 'unknown'],
                                     ['exercise-live-finalization', 'mac-unload', 'extra']])
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


@pytest.mark.parametrize('fault', ['none', 'preexisting', 'remount', 'foreign-mount',
                                 'foreign-file', 'namespace', 'body'])
def test_pam_fault_unmounts_only_exact_owned_mount(monkeypatch, fault):
    path = Path('/etc/pam.d/systemd-user')
    identity = (1, 2, 0, 0, 0o100644, 1, b'unchanged')
    rows = {}
    namespace = 'mnt:[123]'
    row = lambda options: (('42', '1', '8:1', '/etc/pam.d/systemd-user', str(path), options),
                           ('ext4', '/dev/root', 'rw'))
    if fault == 'preexisting':
        rows['99'] = row('rw')
    monkeypatch.setattr(removal.guest, 'guard', Mock())
    monkeypatch.setattr(removal, 'fault_file_identity', lambda current: identity)
    monkeypatch.setattr(removal, 'mount_inventory', lambda: (namespace, dict(rows)))
    operations = []
    def run(argv, **kwargs):
        operations.append(argv)
        if argv[:2] == ['mount', '--bind']:
            rows['42'] = row('rw')
        elif argv[0] == 'mount':
            if fault == 'remount':
                raise removal.guest.CommandError('remount-failed')
            rows['42'] = row('ro')
        elif argv[0] == 'umount':
            rows.clear()
        else:
            pytest.fail('unexpected OS command')
    monkeypatch.setattr(removal.guest, 'run', run)
    def exercise():
        nonlocal namespace
        with removal.mounted_pam_fault(Mock()):
            if fault == 'foreign-mount':
                rows['99'] = rows.pop('42')
            elif fault == 'foreign-file':
                monkeypatch.setattr(removal, 'fault_file_identity', lambda current: (*identity[:-1], b'foreign'))
            elif fault == 'namespace':
                namespace = 'mnt:[456]'
            elif fault == 'body':
                raise RuntimeError('body-failed')
    if fault == 'none':
        exercise()
    else:
        with pytest.raises((removal.guest.GuestError, removal.guest.CommandError, RuntimeError)):
            exercise()
    unmounts = [argv for argv in operations if argv[0] == 'umount']
    assert unmounts == ([['umount', '--', str(path)]]
                        if fault in ('none', 'remount', 'body') else [])
    if fault == 'preexisting':
        assert operations == []
    else:
        assert operations[0] == ['mount', '--bind', str(path), str(path)]
        assert all('lazy' not in arg and arg != '-l' for argv in operations for arg in argv)


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


@pytest.mark.parametrize('fault', ['none', 'watcher', 'command', 'missed', 'snapshot', 'gdm'])
def test_aborted_watcher_has_private_commands_and_always_joins(tmp_path, monkeypatch, fault):
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
    gdm = tmp_path / 'gdm'
    gdm.write_bytes(b'foreign' if fault == 'gdm' else b'denial')
    real_path = Path
    monkeypatch.setattr(removal, 'Path', lambda value: gdm if value == '/etc/pam.d/gdm-password'
                        else real_path(value))
    def transition(uid):
        if fault == 'watcher':
            raise RuntimeError('watcher-failed')
        return {'snapshot': {'version': 1, 'accounts': [] if fault == 'snapshot' else [expected]},
                'native': [0, 0, [0, 0], [False, []]], 'extensions': [[], []],
                'policy_absent': list(removal.GENERATED_POLICY)}
    monkeypatch.setattr(removal, 'cleanup_transition', transition)
    record = Mock()
    if fault == 'none':
        assert removal.observe_aborted_transaction(1004, expected, b'denial', record) == (
            b'native callback failure', 7)
        assert (transaction.directory / 'observed-snapshot.txt').stat().st_mode & 0o777 == 0o600
    else:
        with pytest.raises((RuntimeError, removal.guest.GuestError, removal.guest.CommandError)):
            removal.observe_aborted_transaction(1004, expected, b'denial', record)
    assert events == ['native', 'joined']
    assert transaction.directory.parent == tmp_path.parent
    assert transaction.directory.name.startswith('rollback-')


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


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('fault', [None, 'product-domain', 'vendor-domain'])
def test_loaded_confinement_checks_installed_policy_and_vendor_domain(
        tmp_path, monkeypatch, backend, fault):
    config = {'backend': backend, 'domains': ['manager', 'gate']}
    config_path = tmp_path / 'config.json'
    config_path.write_text(json.dumps(config))
    monkeypatch.setattr(removal, 'Path', lambda name: config_path)
    monkeypatch.setattr(removal.guest, 'guard', Mock())
    enforcing = Mock(side_effect=ValueError('domain-not-enforcing')
                     if fault == 'product-domain' else None)
    preparation = Mock(return_value={'enforcing': enforcing})
    monkeypatch.setattr(removal.runpy, 'run_path', preparation)
    native = Mock(return_value='Builtin Permissive Types\n\nCustomized Permissive Types\n' +
                  ('xdm_t\n' if fault == 'vendor-domain' else 'other_xdm_t\n'))
    monkeypatch.setattr(removal.guest, 'run', native)
    if fault == 'product-domain' or (backend == 'selinux' and fault == 'vendor-domain'):
        with pytest.raises(removal.guest.GuestError, match=(
                'confinement-not-enforcing' if fault == 'product-domain'
                else 'vendor-domain-not-enforcing')):
            removal.verify_loaded_confinement()
    else:
        removal.verify_loaded_confinement()
    preparation.assert_called_once_with('/usr/libexec/oh-no-parent-control-kiosk-confinement')
    enforcing.assert_called_once_with(config)
    if backend == 'selinux' and fault != 'product-domain':
        native.assert_called_once_with(['/usr/sbin/semanage', 'permissive', '-l'], timeout=30)
    else:
        native.assert_not_called()


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
    ('enforcement-before', 'confinement-not-enforcing'),
    ('enforcement-after', 'confinement-not-enforcing'),
])
def test_inflight_removal_refusal_preserves_holder_and_enforcement(monkeypatch, fault, category):
    import system_kiosk_admission as admission
    import system_kiosk_confinement as confinement
    events = []
    removed = False
    held = False
    controlled = False
    account = SimpleNamespace(pw_uid=1007, pw_dir='/home/owned')
    monkeypatch.setattr(removal.guest, 'guard', Mock())
    monkeypatch.setattr(removal.pwd, 'getpwnam', lambda name:
                        SimpleNamespace(pw_uid=9999) if removed and fault == 'account' else account)
    def info(name):
        fields = dict(st_dev=1, st_ino=1, st_uid=1007, st_gid=1007, st_mode=0o40700)
        for field in fields:
            if removed and fault == name + '-' + field.removeprefix('st_'):
                fields[field] += 1
        return SimpleNamespace(**fields)
    monkeypatch.setattr(removal, 'Path', lambda value: (
        SimpleNamespace(lstat=lambda: info('home' if value == account.pw_dir else 'lease'))
        if value != '/proc' else Path(value)))
    monkeypatch.setattr(removal, 'wait_kiosk_inactive', lambda current: events.append('inactive'))
    monkeypatch.setattr(admission, 'verify_gates', lambda record: events.append('gates'))
    monkeypatch.setattr(removal, 'admission_removal_state', lambda:
                        'changed' if removed and fault == 'records' else 'owned')
    def enforcement():
        assert held
        events.append('enforcing')
        if fault == ('enforcement-after' if removed else 'enforcement-before'):
            raise removal.guest.GuestError('removal:confinement-not-enforcing')
    monkeypatch.setattr(removal, 'verify_loaded_confinement', enforcement)
    monkeypatch.setattr(removal, 'account_digest', lambda uid:
                        'changed' if removed and fault == {1004: 'child', 1005: 'other'}[uid] else 'owned')
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
        return b'unrelated failure' if fault == 'reason' else b'reason=kiosk-admissions-active'
    monkeypatch.setattr(removal, 'removal_command', lambda: ['native-remove'])
    monkeypatch.setattr(removal.guest, 'commands', SimpleNamespace(
        run=native_remove, last_returncode=0 if fault == 'accepted' else 1))
    monkeypatch.setattr(removal, 'package_absent', lambda: fault == 'erased')
    def payload():
        events.append('payload')
        if fault == 'payload':
            raise removal.guest.GuestError('removal:package-file-digests')
    monkeypatch.setattr(removal.guest, 'verify_package_files', payload)
    def launch(uid, allowed):
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
    def preflight(arguments, **options):
        assert not held
        assert arguments == ['/usr/libexec/oh-no-parent-control-kiosk-confinement-integration',
                             'check-remove']
        assert options == {'timeout': 30}
        events.append('preflight')
    monkeypatch.setattr(removal.guest, 'run', preflight)
    record = Mock()
    if fault:
        with pytest.raises(removal.guest.GuestError, match='^removal:' + category + '$'):
            removal.verify_inflight_admission_refusal(record, {'child': 1004, 'other': 1005})
        assert events[-2:] == ['close', 'failed-release']
        record.assert_not_called()
    else:
        removal.verify_inflight_admission_refusal(record, {'child': 1004, 'other': 1005})
        assert events == ['inactive', 'gates', ('launch', 1005, True), 'preflight',
                          'hold', 'inactive', 'enforcing', 'remove', 'enforcing', 'payload',
                          ('launch', 1005, True), ('launch', 1004, False), 'probe',
                          'close', 'normal-release', 'preflight', 'gates']
        assert [call.args[0] for call in record.call_args_list] == [
            'onpc.removal.inflight-admission-refused', 'onpc.removal.inflight-admission-drained']
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


@pytest.mark.parametrize('fault', [None, 'boot', 'policy', 'home', 'ordinary', 'preflight'])
def test_rollback_reboot_requires_preserved_state_before_native_finalization(tmp_path, monkeypatch, fault):
    import system_kiosk_admission as admission
    home = tmp_path / 'home'
    home.mkdir()
    info = home.lstat()
    kiosk = SimpleNamespace(pw_uid=info.st_uid, pw_gid=info.st_gid,
                            pw_dir='/home/oh-no-parent-control', pw_shell='/usr/sbin/nologin')
    parent = SimpleNamespace(pw_name='parent', pw_uid=41002, pw_gid=41002,
                             pw_dir='/home/parent', pw_shell='/bin/bash')
    state = {'accounts': {'child': 41001, 'parent': 41002}, 'kiosk_name': 'oh-no-parent-control',
             'rollback_rearm': {
                 'boot': 'old', 'policy': 'child-policy', 'extensions': ['child-extension'],
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
    monkeypatch.setattr(removal.guest, 'run', Mock(side_effect=(
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


def test_durable_denial_oracle_preserves_exact_original_local_or_vendor_bytes():
    saved = {'pam': {'gdm-password': {'before': '# local\naccount required pam_unix.so\n',
                                     'vendor': 'ignored vendor\n'},
                     'systemd-user': {'before': None, 'vendor': 'session required pam_systemd.so\n'},
                     'empty-local': {'before': '', 'vendor': 'must not substitute\n'}}}
    prefix = (b'# Oh No Parent Control removal admission barrier\n'
              b'account requisite pam_succeed_if.so quiet user != oh-no-parent-control\n'
              b'session requisite pam_succeed_if.so quiet user != oh-no-parent-control\n')
    assert removal.removal_denials(saved) == {
        'gdm-password': prefix + b'# local\naccount required pam_unix.so\n',
        'systemd-user': prefix + b'session required pam_systemd.so\n', 'empty-local': prefix}


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
             'kiosk_name': removal.PRODUCT, 'payload': [str(tmp_path / 'erased-broker')]}
    recovery = {'variant': 'mac-unload', 'boot': 'old', 'completed': False,
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
    saved = {'version': 1, 'pam': {
        'gdm-password': {'before': 'account required pam_unix.so\n', 'vendor': 'ignored\n'},
        'systemd-user': {'before': None, 'vendor': 'session required pam_systemd.so\n'}}}
    write('/var/lib/oh-no-parent-control/kiosk-confinement.json', json.dumps(dict(saved, removing=True)))
    write('/var/lib/oh-no-parent-control/kiosk-confinement-removing', 'removing\n')
    write('/var/lib/oh-no-parent-control/package-created-kiosk-uid', '41000\n')
    for service, contents in removal.removal_denials(saved).items():
        write('/etc/pam.d/' + service, contents.decode())
    write('/sys/kernel/security/apparmor/profiles', 'unrelated (enforce)\n')
    monkeypatch.setattr(removal, 'fault_file_identity', lambda target: (target.read_bytes(),))
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
def test_surviving_identity_requires_home_and_all_retained_account_state(finalization_machine, monkeypatch, fault):
    machine = finalization_machine
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
        assert machine.launch.call_args_list == [mock_call(41002, True), mock_call(41003, True)]


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
    assert machine.launch.call_args_list == [mock_call(41002, True), mock_call(41003, True)]


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
        expected.extend([mock_call(service, 'kiosk', callback, 7, service + '.kiosk.' + callback, record)
                         for callback in ('account', 'session')])
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


@pytest.mark.parametrize('fault', ['removing', 'extra-record', 'marker', 'uid', 'denial-bytes', 'erased-module'])
def test_durable_interval_refuses_changed_records_or_non_native_denial(finalization_machine, fault):
    machine = finalization_machine
    if fault in ('removing', 'extra-record'):
        current = dict(machine.saved, removing=True)
        current.update({'removing': 1} if fault == 'removing' else {'foreign': 'value'})
        machine.write('/var/lib/oh-no-parent-control/kiosk-confinement.json', json.dumps(current))
    elif fault in ('marker', 'uid'):
        machine.write('/var/lib/oh-no-parent-control/' + (
            'kiosk-confinement-removing' if fault == 'marker' else 'package-created-kiosk-uid'), 'changed\n')
    elif fault == 'denial-bytes':
        machine.write('/etc/pam.d/gdm-password', 'account required pam_permit.so\n')
    else:
        machine.saved['pam']['gdm-password']['before'] += 'session required pam_oh_no_parent_control.so\n'
        machine.write('/var/lib/oh-no-parent-control/kiosk-confinement.json',
                      json.dumps(dict(machine.saved, removing=True)))
        machine.write('/etc/pam.d/gdm-password', removal.removal_denials(machine.saved)['gdm-password'].decode())
    with pytest.raises(removal.guest.GuestError, match='recovery-records-changed|durable-denial-not-installed'):
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
    for owner, name in [(removal.guest, 'installed'), (removal, 'verify_loaded_confinement'),
                        (removal, 'wait_kiosk_inactive'), (admission, 'verify_gates')]:
        monkeypatch.setattr(owner, name, Mock())
    monkeypatch.setattr(removal, 'removal_command', lambda: ['native-remove'])
    verify = Mock()
    monkeypatch.setattr(removal, 'verify_removed', verify)
    machine.state_file, machine.verify = state_file, verify
    return machine


@pytest.mark.parametrize('completed', [False, True])
def test_finalization_reboot_finishes_only_pending_native_removal(finalization_reboot, completed):
    machine = finalization_reboot
    machine.state['finalization_retry']['completed'] = completed
    machine.state_file.write_text(json.dumps(machine.state))
    record = Mock()
    removal.finalization_retry_rebooted(record, 'mac-unload')
    if completed:
        machine.commands.run.assert_not_called()
        removal.guest.installed.assert_not_called()
    else:
        machine.commands.run.assert_called_once_with(['native-remove'], timeout=1800, merge_stderr=True)
        assert machine.run.call_args_list[-1] == mock_call([
            '/usr/libexec/oh-no-parent-control-kiosk-confinement-integration', 'check-remove'], timeout=30)
    machine.verify.assert_called_once_with(machine.state, record=record)
    assert machine.probe.call_args_list == [
        mock_call('login', role, 0, 'finalization.completed.' + role, record)
        for role in ('ordinary', 'other')]
    assert record.call_args.args[0] == 'onpc.finalization.retry-finalized'


@pytest.mark.parametrize('fault', ['missing-state', 'variant', 'boot', 'identity', 'policy',
                                 'extensions', 'preflight', 'native-removal', 'removed-check'])
def test_finalization_retry_stops_at_failed_identity_or_recovery_boundary(finalization_reboot, monkeypatch, fault):
    machine = finalization_reboot
    if fault == 'missing-state':
        machine.state.pop('finalization_retry')
    elif fault == 'variant':
        machine.recovery['variant'] = 'denial-publication'
    elif fault == 'boot':
        monkeypatch.setattr(removal, 'boot', lambda: 'old')
    elif fault == 'identity':
        machine.kiosk.pw_uid += 1
    elif fault == 'policy':
        machine.recovery['policy'] = 'changed'
    elif fault == 'extensions':
        machine.recovery['extensions'] = []
    elif fault == 'preflight':
        native_run = machine.run.side_effect
        def fail_preflight(argv, **kwargs):
            if argv[0] == 'findmnt':
                return native_run(argv, **kwargs)
            raise removal.guest.GuestError('fixture:preflight')
        machine.run.side_effect = fail_preflight
    elif fault == 'native-removal':
        machine.commands.run.side_effect = removal.guest.CommandError('fixture:native-removal')
    else:
        machine.verify.side_effect = removal.guest.GuestError('fixture:removed-check')
    machine.state_file.write_text(json.dumps(machine.state))
    record = Mock()
    with pytest.raises((KeyError, removal.guest.GuestError, removal.guest.CommandError)):
        removal.finalization_retry_rebooted(record, 'mac-unload')
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
    monkeypatch.setattr(removal, 'provision_native', lambda: machine.state['accounts'])
    monkeypatch.setattr(removal, 'call', Mock(return_value=[json.dumps({
        'parent_control_enabled': False, 'apps': {}})]))
    monkeypatch.setattr(removal, 'accepted', lambda result: result)
    monkeypatch.setattr(removal, 'account_state', lambda uid: (b'prefs', 1, 3600, [0, 0], [False, []]))
    monkeypatch.setattr(removal, 'boot', lambda: 'old')
    for owner, name in [(removal, 'configure_restrictions'), (removal, 'wait_kiosk_inactive'),
        (removal.guest, 'retain_identity_for_redaction'), (removal.guest, 'verify_package_payload'),
        (removal.guest, 'verify_package_files'), (removal.guest, 'install_package'),
        (removal, 'verify_loaded_confinement'), (admission, 'verify_gates')]:
        monkeypatch.setattr(owner, name, Mock())
    machine.write('/var/lib/oh-no-parent-control/kiosk-confinement.json', json.dumps(machine.saved))
    monkeypatch.setattr(removal, 'original_authselect', lambda: 'sssd')
    monkeypatch.setattr(removal, 'package_absent', lambda: False)
    monkeypatch.setattr(removal, 'removal_command', lambda: ['native-remove'])
    native_run = machine.run.side_effect
    machine.run.side_effect = lambda argv, **kwargs: (
        'install ok half-configured' if argv[0] == 'dpkg-query' else native_run(argv, **kwargs))
    # This fixture models only declared marker checks, never the host filesystem.
    monkeypatch.setattr(removal.os.path, 'lexists', lambda _: False)
    transaction = Mock(return_value=(b'kiosk confinement configuration failed', 1))
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
@pytest.mark.parametrize('variant', removal.FINALIZATION_VARIANTS)
def test_interrupted_finalization_selects_only_supported_native_recovery(interrupted_finalization, monkeypatch, package_format, variant):
    machine = interrupted_finalization
    monkeypatch.setattr(removal.guest, 'package_path', lambda: Path('package.' + package_format))
    if variant == 'account-finalization':
        machine.transaction.return_value = (b'refusing cleanup of a mounted directory', 1)
    record = Mock()
    removal.interrupted_finalization_retry(record, variant)
    machine.fault.verify_triggered.assert_called_once_with()
    assert machine.transaction.call_args.args[2] == removal.removal_denials(machine.saved)['gdm-password']
    state = machine.save.call_args.args[0]
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
        machine.transaction.return_value = (b'refusing cleanup of a mounted directory', 1)
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
        removal.interrupted_finalization_retry(Mock(), 'mac-unload')
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
            removal.interrupted_finalization_retry(Mock(), 'mac-unload')
    else:
        removal.interrupted_finalization_retry(Mock(), 'mac-unload')
    configurations = [item for item in machine.run.call_args_list
                      if item.args[0][:2] == ['dpkg', '--configure']]
    assert len(configurations) == (1 if status == 'install ok half-configured' else 0)
