"""Private command/PAM doubles and bounded harmless wrapper shell children."""

from contextlib import contextmanager
import copy
import ctypes
import json
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

import system_first_configure as configure
import system_kiosk_admission as admission
from tests.support.package_scripts import package_machine
from tools.test_storage import scratch_descriptors


def test_reboot_history_keeps_native_execution_enforcing_without_policy_loss_faults(tmp_path, monkeypatch):
    import system_kiosk_confinement as confinement
    import system_kiosk_scope as scope
    saved = {'schema': 1, 'boot': 'previous-boot', 'identity': {}, 'ordinary': {}}
    state = tmp_path / 'state.json'
    state.write_text(json.dumps(saved))
    monkeypatch.setattr(configure, 'state_path', lambda: state)
    monkeypatch.setattr(configure, 'boot', lambda: 'new-boot')
    for name in ('verify_account_identity', 'verify_ordinary', 'verify_visibility',
                 'ordinary_controls', 'verify_gates', 'empty_authentication_probe',
                 'verify_loaded_confinement', 'verify_compatibility_profile'):
        monkeypatch.setattr(configure, name, Mock())
    for name in ('guard', 'enable_diagnostics', 'installed'):
        monkeypatch.setattr(configure.guest, name, Mock())
    monkeypatch.setattr(configure.guest, 'reboot_cleared', lambda: True)
    execution, collateral = Mock(), Mock()
    monkeypatch.setattr(confinement, 'verify_session_composition', execution)
    monkeypatch.setattr(scope, 'verify', collateral)
    record = Mock()
    configure.verify_reboot(record)
    execution.assert_called_once_with(record)
    collateral.assert_called_once_with(record)
    assert configure.verify_loaded_confinement.call_count == 2
    assert configure.guest.guard.call_count == 2
    configure.verify_compatibility_profile.assert_called_once_with(record, 'after-reboot')


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_installed_compatibility_witness_requires_active_profile_and_preserves_refusal(
        monkeypatch, package_format):
    import guest_test_dependencies
    monkeypatch.setattr(configure.guest, 'package_path', lambda: Path('package.' + package_format))
    receipt = {'profile': 'lxc-cgroups', 'stacks': ['common-session', 'common-session-noninteractive'],
               'module': 'pam_cgfs.so'}
    verify = Mock(return_value=receipt)
    monkeypatch.setattr(guest_test_dependencies, 'verify_pam_compatibility', verify)
    record = Mock()
    configure.verify_compatibility_profile(record, 'before-install')
    if package_format == 'rpm':
        verify.assert_not_called()
        record.assert_not_called()
        return
    verify.assert_called_once_with(Path('/'))
    assert record.call_args.args[0] == 'onpc.first-configure.pam-compatibility.before-install'
    assert json.loads(record.call_args.args[1]) == receipt
    verify.side_effect = ValueError('guest-tools:pam-compatibility-missing')
    record.reset_mock()
    with pytest.raises(ValueError, match='pam-compatibility-missing'):
        configure.verify_compatibility_profile(record, 'after-retry')
    record.assert_not_called()


@pytest.mark.parametrize('package_format,group,group_id', [('deb', 'sudo', 27), ('rpm', 'wheel', 10)])
@pytest.mark.parametrize('stage', ['after-retry', 'after-reboot'])
def test_identity_allows_only_native_private_state_group_normalization(
        monkeypatch, package_format, group, group_id, stage):
    expected = {'account': ['kiosk', 1005], 'marker': [123, 0, 0, stat.S_IFREG | 0o600, 1, 'digest'],
                'home': ['home-identity'], 'cache_metadata': [0, 0, 0o644, {}], 'cache_sha256': 'cache'}
    actual = copy.deepcopy(expected)
    actual['marker'][2] = group_id
    if stage == 'after-reboot':
        actual['cache_metadata'][2] = 0o600
    original = copy.deepcopy(expected)
    monkeypatch.setattr(configure, 'account_identity', lambda: actual)
    monkeypatch.setattr(configure.guest, 'package_path', lambda: Path('package.' + package_format))
    monkeypatch.setattr(configure.grp, 'getgrnam', lambda name:
                        SimpleNamespace(gr_gid=group_id) if name == group else None)
    run = Mock(return_value=group)
    monkeypatch.setattr(configure.guest, 'run', run)
    monkeypatch.setattr(configure, 'QUARANTINE', SimpleNamespace(parent=SimpleNamespace(
        lstat=lambda: SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=0, st_gid=group_id))))
    record = Mock()
    configure.verify_account_identity(expected, stage, record)
    assert expected == original
    assert run.call_args.args[0] == ['systemctl', 'show', '--property=Group', '--value',
                                     'oh-no-parent-control-broker.service']
    recorded = json.loads(record.call_args.args[1])
    assert recorded['changed'] == []
    assert recorded['actual'] == recorded['expected'] == actual


@pytest.mark.parametrize('failure', ['unit-group', 'directory-owner', 'directory-group',
    'directory-mode', 'directory-type', 'marker-group', 'marker-owner', 'marker-mode',
    'marker-inode', 'marker-bytes', 'account', 'home', 'cache'])
def test_identity_rejects_other_state_changes(tmp_path, monkeypatch, failure):
    expected = {'account': ['kiosk', 1005], 'marker': [123, 0, 0, stat.S_IFREG | 0o600, 1, 'digest'],
                'home': ['home-identity'], 'cache_metadata': [0, 0, 0o644, {}], 'cache_sha256': 'cache'}
    actual = copy.deepcopy(expected)
    actual['marker'][2] = 10
    directory = SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=0, st_gid=10)
    if failure.startswith('directory-'):
        setattr(directory, {'directory-owner': 'st_uid', 'directory-group': 'st_gid',
                            'directory-mode': 'st_mode', 'directory-type': 'st_mode'}[failure],
                {'directory-owner': 1000, 'directory-group': 11,
                 'directory-mode': stat.S_IFDIR | 0o750,
                 'directory-type': stat.S_IFLNK | 0o700}[failure])
    if failure.startswith('marker-'):
        index, value = {'marker-group': (2, 11), 'marker-owner': (1, 1),
                        'marker-mode': (3, stat.S_IFREG | 0o640), 'marker-inode': (0, 124),
                        'marker-bytes': (5, 'different')}[failure]
        actual['marker'][index] = value
    if failure in ('account', 'home'):
        actual[failure] = ['different']
    if failure == 'cache':
        actual['cache_sha256'] = 'different'
    monkeypatch.setattr(configure, 'account_identity', lambda: actual)
    monkeypatch.setattr(configure.guest, 'package_path', lambda: Path('package.rpm'))
    monkeypatch.setattr(configure.grp, 'getgrnam', lambda name: SimpleNamespace(gr_gid=10))
    monkeypatch.setattr(configure.guest, 'run', Mock(return_value='other' if failure == 'unit-group' else 'wheel'))
    monkeypatch.setattr(configure, 'QUARANTINE', SimpleNamespace(parent=SimpleNamespace(lstat=lambda: directory)))
    results = tmp_path / 'results'
    results.mkdir()
    cache = tmp_path / configure.PRODUCT
    cache.write_bytes(b'fixed-product-account-cache')
    monkeypatch.setattr(configure.guest, 'PAYLOAD', tmp_path)
    monkeypatch.setattr(configure, 'Path', lambda value: tmp_path)
    with pytest.raises(configure.guest.GuestError):
        configure.verify_account_identity(expected, 'after-retry', Mock())


@pytest.mark.parametrize('before_mode', [0o600, 0o644])
@pytest.mark.parametrize('change', ['none', 'owner', 'group', 'mode', 'attributes', 'bytes'])
def test_reboot_reuses_exact_native_cache_startup_comparison(monkeypatch, before_mode, change):
    expected = {'account': ['kiosk', 1005], 'marker': [123, 0, 0, stat.S_IFREG | 0o600, 1, 'digest'],
                'home': ['home-identity'], 'cache_metadata': [0, 0, before_mode, {'label': 'original'}],
                'cache_sha256': 'cache'}
    original = copy.deepcopy(expected)
    actual = copy.deepcopy(expected)
    actual['cache_metadata'][2] = 0o600
    if change == 'bytes':
        actual['cache_sha256'] = 'different'
    elif change != 'none':
        index, value = {'owner': (0, 1), 'group': (1, 1), 'mode': (2, 0o640),
                        'attributes': (3, {'label': 'different'})}[change]
        actual['cache_metadata'][index] = value
    monkeypatch.setattr(configure, 'account_identity', lambda: actual)
    if change == 'none':
        record = Mock()
        configure.verify_account_identity(expected, 'after-reboot', record)
        assert json.loads(record.call_args.args[1])['changed'] == []
    else:
        with pytest.raises(configure.guest.GuestError, match='fresh-restart-changed-record'):
            configure.verify_account_identity(expected, 'after-reboot', Mock())
    assert expected == original


@pytest.mark.parametrize('arguments', [
    ['--package'], [], ['--package', '--enable', 'oh-no-parent-control-kiosk-only'],
    ['--package', '--disable', 'malcontent', '--enable', 'oh-no-parent-control-session-limits',
     '--enable', 'oh-no-parent-control-kiosk-only'],
])
def test_default_pam_deferral_uses_public_disable_and_preserves_explicit_enables(tmp_path, arguments):
    original, wrapper, witness = (tmp_path / name for name in ('native', 'wrapper', 'witness'))
    original.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    original.chmod(0o700)
    wrapper.write_text(configure.deferred_pam_source(original, witness))
    wrapper.chmod(0o700)
    result = subprocess.run([str(wrapper), *arguments], capture_output=True, timeout=5)
    assert result.returncode == 0
    expected = (['--package', '--disable', 'oh-no-parent-control-kiosk-only',
                 '--disable', 'oh-no-parent-control-session-limits']
                if arguments == ['--package'] else arguments)
    assert result.stdout.decode().splitlines() == (expected or [''])
    assert witness.exists() == (arguments == ['--package'])
    if witness.exists():
        assert witness.read_bytes() == configure.PAM_DEFERRED
        assert stat.S_IMODE(witness.stat().st_mode) == 0o600


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
@pytest.mark.parametrize('stage', ['visibility', 'owned-passwordless', 'pam-ready'])
def test_quarantine_requires_exact_native_stack_statuses(monkeypatch, package_format, stage):
    monkeypatch.setattr(configure.guest, 'package_path', lambda: Path('package.' + package_format))
    statuses = configure.quarantine_statuses(stage)
    assert set(statuses) == {'gdm-password', 'login', 'sshd', 'systemd-user'}
    assert statuses == ({name: 7 for name in statuses} if package_format == 'deb' else
                        {'gdm-password': 13, 'login': None, 'sshd': None, 'systemd-user': 13}
                        if stage == 'pam-ready' else {name: 13 for name in statuses})


@pytest.mark.parametrize('invocation', ['exact', 'prefix', 'suffix', 'different', 'empty'])
def test_fault_wrapper_matches_only_exact_native_invocation(tmp_path, invocation):
    original, wrapper, witness = (tmp_path / name for name in (
        'original with spaces', 'wrapper', 'witness with spaces'))
    original.write_text('#!/bin/sh\nprintf "native:%s\\n" "$#"\n')
    original.chmod(0o700)
    arguments = ['-r', '/policy with spaces']
    wrapper.write_text(configure.wrapper_source(original, witness, arguments))
    wrapper.chmod(0o700)
    selected = {'exact': arguments, 'prefix': arguments[:1], 'suffix': [*arguments, 'extra'],
                'different': ['-i', arguments[1]], 'empty': []}[invocation]
    result = subprocess.run([str(wrapper), *selected], capture_output=True, timeout=5,
                            pass_fds=scratch_descriptors())
    assert result.returncode == (79 if invocation == 'exact' else 0)
    assert result.stdout == (b'' if invocation == 'exact' else
                             f'native:{len(selected)}\n'.encode())
    assert witness.exists() == (invocation == 'exact')
    if witness.exists():
        assert witness.read_bytes() == configure.WITNESS
        assert stat.S_IMODE(witness.stat().st_mode) == 0o600


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_faults_bind_exact_native_boundaries(monkeypatch, package_format):
    monkeypatch.setattr(configure.guest, 'package_path', lambda: Path('package.' + package_format))
    assert configure.fault_command('visibility') == (
        Path('/usr/bin/install'), (), ['-o', 'root', '-g', 'root', '-m', '0644',
            '/usr/share/oh-no-parent-control/99-oh-no-parent-control-allow.rules',
            '/etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules'], False)
    assert configure.fault_command('pam-ready') == (
        Path('/usr/bin/systemd-sysusers'), (), ['malcontent-timer-extension-agent.conf',
            'malcontent-timerd.conf', 'malcontent-webd.conf'], False)
    if package_format == 'deb':
        assert configure.fault_command('early-pam') == (
            Path('/usr/sbin/pam-auth-update'), (), ['--package'], False)
    else:
        with pytest.raises(configure.guest.GuestError, match='unexpected-default-pam-tool'):
            configure.fault_command('early-pam')
    with pytest.raises(configure.guest.GuestError, match='unknown-fault-stage'):
        configure.fault_command('confinement')


@pytest.mark.parametrize('package_machine,package_format', [('ubuntu', 'deb'), ('fedora', 'rpm')],
                         indirect=['package_machine'])
@pytest.mark.parametrize('stage', ['visibility', 'pam-ready'])
def test_exact_fault_interrupts_rendered_postinst_before_commit_and_allows_retry(
        package_machine, monkeypatch, package_format, stage):
    root, state, run = package_machine
    monkeypatch.setattr(configure.guest, 'package_path', lambda: Path('package.' + package_format))
    tool, aliases, arguments, after = configure.fault_command(stage)
    assert aliases == () and after is False
    arguments = [str(root / value.lstrip('/')) if value.startswith('/') else value
                 for value in arguments]
    target = root / 'bin' / tool.name
    delegated = root / 'delegated' / tool.name
    delegated.parent.mkdir()
    # Keep the native double's basename: it dispatches on argv[0].
    target.rename(delegated)
    witness = root / 'fault-witness'
    target.write_text(configure.wrapper_source(delegated, witness, arguments))
    target.chmod(0o700)
    marker = state / 'package-created-kiosk-uid'
    identity = (marker.stat().st_ino, marker.read_bytes())
    result = run(DPKG_FRONTEND_LOCKED='true')
    assert result.returncode == 79, result.stderr
    assert witness.read_bytes() == configure.WITNESS
    assert stat.S_IMODE(witness.stat().st_mode) == 0o600
    assert (marker.stat().st_ino, marker.read_bytes()) == identity
    commands = (root / 'commands').read_text().splitlines()
    lifecycle = 'oh-no-parent-control-kiosk-lifecycle --distribution '
    assert not any(line.startswith(lifecycle) and line.endswith((' commit', ' release'))
                   for line in commands)
    assert not any('oh-no-parent-control-broker.service' in line and
                   (' start ' in line or ' restart ' in line) for line in commands)
    assert (state / 'migration-in-progress').exists()
    assert (state / 'package-activation-pending').exists()
    complete = root / 'run/oh-no-parent-control-package-configuration-complete'
    assert not complete.exists()
    published = root / 'etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules'
    assert published.exists() == (stage == 'pam-ready')
    if stage == 'pam-ready':
        assert any(line.startswith('oh-no-parent-control-distro-pam ') and
                   line.endswith(' install') for line in commands)
    target.unlink()
    delegated.rename(target)
    result = run(DPKG_FRONTEND_LOCKED='true')
    assert result.returncode == 0, result.stderr
    assert (marker.stat().st_ino, marker.read_bytes()) == identity
    assert not (state / 'migration-in-progress').exists()
    assert not (state / 'package-activation-pending').exists()
    # Debian retains this marker for the package frontend's post-invoke hook.
    # RPM uses the successful script, commit/release and cleared guards.
    assert complete.exists() == (package_format == 'deb')
    assert published.read_bytes() == (root / 'usr/share/oh-no-parent-control' /
                                      published.name).read_bytes()
    commands = (root / 'commands').read_text().splitlines()
    prefix = lifecycle + ('fedora' if package_format == 'rpm' else 'ubuntu')
    assert commands.index(prefix + ' commit') < commands.index(prefix + ' release')
    assert any('oh-no-parent-control-broker.service' in line and
               (' start ' in line or ' restart ' in line) for line in commands)


@pytest.mark.parametrize('failure', ['none', 'wrapper', 'mode', 'witness', 'artifact'])
def test_fault_requires_exact_owned_witness(monkeypatch, failure):
    expected = (1, 2, 0, 0, stat.S_IFREG | 0o755, 1, b'wrapper')
    witness = (1, 3, 0, 0, stat.S_IFREG | (0o644 if failure == 'mode' else 0o600), 1,
               b'wrong' if failure == 'witness' else configure.WITNESS)
    fault = configure.ConfigureFault('visibility', Path('/native'), (),
        wrapper=expected, witness=Path('/witness'))
    fault.verify_artifacts = Mock(side_effect=ValueError('changed') if failure == 'artifact' else None)
    monkeypatch.setattr(configure, 'identity', lambda path:
        witness if path == Path('/witness') else (() if failure == 'wrapper' else expected))
    if failure == 'none':
        fault.verify_triggered()
    else:
        with pytest.raises((configure.guest.GuestError, ValueError)):
            fault.verify_triggered()
    fault.verify_artifacts.assert_called_once()


@pytest.mark.parametrize('expiry', [1, None, 0])
def test_quarantine_reads_installed_expiry_after_ordinary_controls_before_kiosk_probes(
        monkeypatch, expiry):
    events = []
    monkeypatch.setattr(configure.guest, 'guard', Mock())
    monkeypatch.setattr(configure.guest, 'package_path', lambda: Path('package.deb'))
    monkeypatch.setattr(configure.pwd, 'getpwnam', lambda name: SimpleNamespace(pw_uid=1006))
    saved = {'version': 1, 'uid': 1006, 'expires': None, 'phase': 'quarantined'}
    monkeypatch.setattr(configure, 'identity', lambda path:
                        (1, 2, 0, 0, stat.S_IFREG | 0o600, 1, json.dumps(saved).encode()))
    monkeypatch.setattr(configure, 'ordinary_controls', lambda record, stage, *, services:
                        events.append(('ordinary', stage)))
    def current_expiry():
        events.append(('expiry',))
        return expiry
    reader = Mock(return_value={'current_expiry': current_expiry})
    monkeypatch.setattr(configure.runpy, 'run_path', reader)
    monkeypatch.setattr(configure, 'passwordless', lambda: True)
    for name in ('probe', 'durable_probe', 'empty_authentication_probe'):
        monkeypatch.setattr(configure, name, lambda *args, _name=name:
                            events.append((_name, args)))
    monkeypatch.setattr(configure.guest, 'run', Mock(return_value='0'))
    monkeypatch.setattr(configure.guest.commands, 'run', Mock())
    monkeypatch.setattr(configure.guest.commands, 'last_returncode', 1)
    if expiry == 1:
        configure.verify_quarantine(Mock(), 'pam-ready')
        assert [event[0] for event in events] == [
            'ordinary', 'expiry', 'empty_authentication_probe', 'probe', 'probe',
            'probe', 'durable_probe']
        assert events[2][1][0] == 7
        assert [(event[1][0], event[1][2]) for event in events[3:6]] == [
            ('gdm-password', 7), ('login', 7), ('sshd', 7)]
        assert events[6][1][:4] == ('systemd-user', 'kiosk', 'account', 7)
    else:
        with pytest.raises(configure.guest.GuestError, match='native-expiry-not-retained'):
            configure.verify_quarantine(Mock(), 'pam-ready')
        assert events == [('ordinary', 'pam-ready'), ('expiry',)]
    reader.assert_called_once_with(
        '/usr/lib/oh-no-parent-control/lifecycle/lifecycle_migration.py')


def test_first_configuration_history_retains_two_faults_quarantine_and_retry_endpoint(
        tmp_path, monkeypatch):
    events = Mock()
    monkeypatch.setattr(configure.guest, 'PAYLOAD', tmp_path)
    cache = tmp_path / 'var/lib/AccountsService/users' / configure.PRODUCT
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b'owned account cache')
    monkeypatch.setattr(configure, 'Path', lambda path: tmp_path / str(path).lstrip('/'))
    monkeypatch.setattr(configure, 'boot', lambda: 'before-reboot')
    monkeypatch.setattr(configure, 'ordinary_state', lambda: {'ordinary': 'unchanged'})
    monkeypatch.setattr(configure, 'account_identity', lambda: {'uid': 1006})
    monkeypatch.setattr(configure, 'passwordless', lambda: True)
    monkeypatch.setattr(configure.pwd, 'getpwnam', lambda name: SimpleNamespace(pw_uid=1006))
    for name in ('verify_compatibility_profile', 'ordinary_controls', 'interrupted_install',
                 'verify_quarantine', 'verify_ordinary', 'verify_visibility',
                 'verify_account_identity', 'verify_loaded_confinement', 'verify_gates',
                 'empty_authentication_probe'):
        monkeypatch.setattr(configure, name, getattr(events, name))
    for name in ('guard', 'enable_diagnostics', 'before_install', 'installed'):
        monkeypatch.setattr(configure.guest, name, getattr(events, name))
    monkeypatch.setattr(configure.guest, 'reboot_requested', lambda: True)
    @contextmanager
    def deferred(record):
        events.defer()
        yield
    @contextmanager
    def fault(stage, record):
        events.fault_enter(stage)
        yield stage
        events.fault_exit(stage)
    monkeypatch.setattr(configure, 'deferred_default_pam', deferred)
    monkeypatch.setattr(configure, 'configure_fault', fault)
    retried = False
    def retry():
        nonlocal retried
        events.retry()
        retried = True
    monkeypatch.setattr(configure, 'retry_configuration', retry)
    manager = 'user@1006.service'
    def run(arguments):
        events.command(arguments)
        if arguments[1] == 'show':
            return 'inactive' if retried else 'failed'
        if arguments[1] == 'list-units':
            return '' if retried else manager
        return ''
    monkeypatch.setattr(configure.guest, 'run', run)
    record = Mock()
    configure.exercise(record)
    events.assert_has_calls([
        call.before_install(), call.ordinary_controls(record, 'baseline'), call.defer(),
        call.fault_enter('visibility'), call.interrupted_install('visibility', record, 'visibility'),
        call.verify_visibility(), call.verify_quarantine(record, 'visibility'),
        call.verify_ordinary({'ordinary': 'unchanged'}), call.fault_exit('visibility'),
        call.verify_account_identity({'uid': 1006}, 'before-passwordless-fixture', record),
        call.command(['passwd', '--delete', configure.PRODUCT]),
        call.verify_quarantine(record, 'owned-passwordless'), call.fault_enter('pam-ready'),
        call.interrupted_install('pam-ready', record, 'pam-ready'), call.verify_visibility(),
        call.verify_account_identity({'uid': 1006}, 'during-retry', record),
        call.verify_loaded_confinement(), call.verify_quarantine(record, 'pam-ready'),
        call.verify_ordinary({'ordinary': 'unchanged'}), call.fault_exit('pam-ready'),
    ])
    assert events.fault_enter.call_count == events.interrupted_install.call_count == 2
    events.verify_account_identity.assert_any_call({'uid': 1006}, 'after-retry', record)
    events.installed.assert_called_once_with(reboot_required=True)
    assert events.verify_loaded_confinement.call_count == 2
    assert events.verify_visibility.call_count == 3
    assert events.verify_ordinary.call_args_list == [call({'ordinary': 'unchanged'})] * 3
    events.verify_gates.assert_called_once_with(record)
    events.empty_authentication_probe.assert_called_once_with(
        0, 'first-configure.final.empty-authentication', record)
    assert events.mock_calls.index(call.retry()) < events.mock_calls.index(
        call.installed(reboot_required=True))
    assert json.loads(configure.state_path().read_text()) == {
        'schema': 1, 'boot': 'before-reboot', 'identity': {'uid': 1006},
        'ordinary': {'ordinary': 'unchanged'}}
    assert (tmp_path / 'results/first-configure-cache-before.txt').read_bytes() == cache.read_bytes()
    assert record.call_args.args[0] == 'onpc.first-configure.retry'


@pytest.mark.parametrize('status', ['install ok half-configured', 'install ok installed',
                                  'install reinstreq half-installed', 'unknown'])
def test_deb_configuration_retry_requires_retained_payload_and_exact_pending_state(monkeypatch, status):
    monkeypatch.setattr(configure.guest, 'package_path', lambda: Path('package.deb'))
    guard, payload, install = Mock(), Mock(), Mock()
    run = Mock(return_value=status)
    monkeypatch.setattr(configure.guest, 'guard', guard)
    monkeypatch.setattr(configure.guest, 'verify_package_payload', payload)
    monkeypatch.setattr(configure.guest, 'install_package', install)
    monkeypatch.setattr(configure.guest, 'run', run)
    if status == 'install ok half-configured':
        configure.retry_configuration()
        assert run.call_args_list == [call(['dpkg-query', '-W', '-f=${Status}', configure.PRODUCT]),
                                      call(['dpkg', '--configure', configure.PRODUCT], timeout=2400)]
    else:
        with pytest.raises(configure.guest.GuestError, match='unexpected-retry-package-status'):
            configure.retry_configuration()
        assert run.call_count == 1
    guard.assert_called_once()
    payload.assert_called_once()
    install.assert_not_called()


def test_deb_configuration_retry_preserves_payload_verification_failure(monkeypatch):
    monkeypatch.setattr(configure.guest, 'package_path', lambda: Path('package.deb'))
    monkeypatch.setattr(configure.guest, 'guard', Mock())
    monkeypatch.setattr(configure.guest, 'verify_package_payload',
                        Mock(side_effect=configure.guest.GuestError('payload-changed')))
    run = Mock()
    monkeypatch.setattr(configure.guest, 'run', run)
    with pytest.raises(configure.guest.GuestError, match='payload-changed'):
        configure.retry_configuration()
    run.assert_not_called()


def test_rpm_configuration_retry_uses_maintained_installation(monkeypatch):
    monkeypatch.setattr(configure.guest, 'package_path', lambda: Path('package.rpm'))
    install, run = Mock(), Mock()
    monkeypatch.setattr(configure.guest, 'install_package', install)
    monkeypatch.setattr(configure.guest, 'run', run)
    configure.retry_configuration()
    install.assert_called_once()
    run.assert_not_called()


@pytest.mark.parametrize('command_failed', [False, True])
@pytest.mark.parametrize('complete', [False, True])
def test_interruption_requires_boundary_witness_despite_rpm_success(
        tmp_path, monkeypatch, command_failed, complete):
    marker = tmp_path / 'complete'
    if complete:
        marker.write_text('complete')
    monkeypatch.setattr(configure, 'COMPLETE', marker)
    install = Mock(side_effect=configure.guest.CommandError('failed') if command_failed else None)
    monkeypatch.setattr(configure.guest, 'install_package', install)
    monkeypatch.setattr(configure.guest.commands, 'last_returncode', 79 if command_failed else 0)
    payload = Mock()
    monkeypatch.setattr(configure.guest, 'verify_package_payload', payload)
    fault, record = Mock(), Mock()
    if complete:
        with pytest.raises(configure.guest.GuestError, match='marked-complete'):
            configure.interrupted_install(fault, record, 'visibility')
        payload.assert_not_called()
    else:
        configure.interrupted_install(fault, record, 'visibility')
        payload.assert_called_once()
    fault.verify_triggered.assert_called_once()
    record.assert_called_once_with('onpc.first-configure.transaction-status.visibility',
                                   79 if command_failed else 0)


def test_unrelated_package_failure_cannot_count_as_interruption(tmp_path, monkeypatch):
    monkeypatch.setattr(configure, 'COMPLETE', tmp_path / 'absent')
    monkeypatch.setattr(configure.guest, 'install_package',
                        Mock(side_effect=configure.guest.CommandError('unrelated')))
    fault = Mock()
    fault.verify_triggered.side_effect = configure.guest.GuestError('fault-not-hit')
    payload = Mock()
    monkeypatch.setattr(configure.guest, 'verify_package_payload', payload)
    with pytest.raises(configure.guest.GuestError, match='fault-not-hit'):
        configure.interrupted_install(fault, Mock(), 'visibility')
    payload.assert_not_called()


@pytest.fixture
def native_pam(monkeypatch):
    monkeypatch.setattr(admission.guest, 'guard', Mock())
    monkeypatch.setattr(admission.guest, 'package_path', lambda: Path('package.deb'))
    service = Mock()
    service.exists.return_value = True
    service.lstat.return_value = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0)
    root = Mock()
    root.__truediv__ = Mock(return_value=service)
    monkeypatch.setattr(admission, 'Path', Mock(return_value=root))
    monkeypatch.setattr(admission.pwd, 'getpwnam', Mock(return_value=SimpleNamespace(
        pw_uid=1004, pw_name='oh-no-parent-control')))
    pam = Mock()
    for name in ('pam_start', 'pam_authenticate', 'pam_acct_mgmt', 'pam_end'):
        getattr(pam, name).return_value = 0
    libc = ctypes.CDLL('libc.so.6')
    monkeypatch.setattr(admission.ctypes, 'CDLL', lambda name: libc if name == 'libc.so.6' else pam)
    return pam


@pytest.mark.parametrize('authenticated,accounted', [(0, 13), (0, 0), (7, None), (4, None)])
def test_empty_token_worker_authenticates_before_independent_account_boundary(
        native_pam, authenticated, accounted):
    native_pam.pam_authenticate.return_value = authenticated
    native_pam.pam_acct_mgmt.return_value = accounted
    result = admission.pam_callback('gdm-password', 'kiosk', 'authentication-account', durable=True)
    assert result == {'authenticate': authenticated, 'account': accounted, 'end': 0}
    start = native_pam.pam_start.call_args.args
    assert start[:2] == (b'gdm-password', b'oh-no-parent-control')
    assert start[2]._obj.conv is not None
    handle = start[3]._obj
    expected = [call.pam_start(*start), call.pam_authenticate(handle, 0)]
    if authenticated == 0:
        expected.append(call.pam_acct_mgmt(handle, 0))
    else:
        native_pam.pam_acct_mgmt.assert_not_called()
    expected.append(call.pam_end(handle, authenticated if accounted is None else accounted))
    assert native_pam.mock_calls == expected
    native_pam.pam_open_session.assert_not_called()


@pytest.mark.parametrize('role,service,durable', [('ordinary', 'gdm-password', True),
    ('kiosk', 'systemd-user', True), ('kiosk', 'gdm-password', False)])
def test_empty_authentication_route_is_finite(native_pam, role, service, durable):
    with pytest.raises(admission.guest.GuestError, match='arguments'):
        admission.pam_callback(service, role, 'authentication-account', durable=durable)
    native_pam.pam_start.assert_not_called()


def test_empty_conversation_allocates_native_empty_token_and_name():
    reply = admission.empty_token_conversation('oh-no-parent-control')
    message_pointer = reply.argtypes[1]._type_
    message_type = message_pointer._type_
    response_pointer = reply.argtypes[2]._type_
    messages = [message_type(style, b'private prompt') for style in (1, 2, 3, 4)]
    pointers = (message_pointer * len(messages))(*(ctypes.pointer(item) for item in messages))
    responses = response_pointer()
    assert reply(4, pointers, ctypes.byref(responses), None) == 0
    libc = ctypes.CDLL('libc.so.6')
    libc.free.argtypes = [ctypes.c_void_p]
    try:
        assert ctypes.string_at(responses[0].response) == b''
        assert ctypes.string_at(responses[1].response) == b'oh-no-parent-control'
        assert responses[2].response is responses[3].response is None
        assert all(responses[index].code == 0 for index in range(4))
    finally:
        for index in range(4):
            libc.free(responses[index].response)
        libc.free(ctypes.cast(responses, ctypes.c_void_p))
    assert reply(0, pointers, ctypes.byref(responses), None) == 19
    assert reply(17, pointers, ctypes.byref(responses), None) == 19
    messages[0].style = 99
    assert reply(1, pointers, ctypes.byref(responses), None) == 19


@pytest.mark.parametrize('response', [
    {'authenticate': 0, 'account': 13, 'end': 0},
    {'authenticate': 7, 'account': None, 'end': 0},
    {'authenticate': 0, 'account': 0, 'end': 0},
    {'authenticate': False, 'account': 13, 'end': 0},
    {'authenticate': 0, 'account': 13, 'end': 4},
    {'account': 13, 'end': 0}, 'invalid',
])
def test_authentication_probe_requires_authentication_success_and_exact_admission(
        monkeypatch, response):
    monkeypatch.setattr(admission.guest, 'guard', Mock())
    monkeypatch.setattr(admission.guest, 'package_path', lambda: Path('package.deb'))
    run = Mock(return_value=json.dumps(response).encode())
    monkeypatch.setattr(admission.guest.commands, 'run', run)
    record = Mock()
    if response == {'authenticate': 0, 'account': 13, 'end': 0} and type(response['authenticate']) is int:
        admission.empty_authentication_probe(13, 'expired', record)
    else:
        with pytest.raises(admission.guest.GuestError):
            admission.empty_authentication_probe(13, 'expired', record)
    assert run.call_args.args[0][-1] == 'pam-authentication-account'
    assert run.call_args.kwargs == {'timeout': 45, 'merge_stderr': False}


def test_authentication_probe_uses_fedora_real_caller_context(monkeypatch):
    import system_kiosk_confinement
    monkeypatch.setattr(admission.guest, 'guard', Mock())
    monkeypatch.setattr(admission.guest, 'package_path', lambda: Path('package.rpm'))
    run = Mock(return_value=b'{"authenticate":0,"account":13,"end":0}')
    monkeypatch.setattr(admission.guest.commands, 'run', run)
    events = []
    @contextmanager
    def caller(directory, service):
        assert directory == admission.guest.PAYLOAD and service == 'gdm-password'
        events.append('enter')
        yield ['/native-xdm-interpreter', '-B']
        events.append('exit')
    monkeypatch.setattr(system_kiosk_confinement, 'pam_caller_command', caller)
    admission.empty_authentication_probe(13, 'expired', Mock())
    assert events == ['enter', 'exit']
    assert run.call_args.args[0][:2] == ['/native-xdm-interpreter', '-B']
