"""Public purge refuses unsafe input and erasure failures using private state."""
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.support.package_scripts import Machine, script_source
from tests.support.paths import ROOT


@pytest.fixture
def purge_module():
    spec = importlib.util.spec_from_file_location('onpc_package_purge', ROOT / 'packaging/purge.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('args', [['--yes', '--yes'], ['--path', '/'], ['remove'], ['--yes', 'extra']])
def test_public_purge_has_no_arbitrary_action_or_path(purge_module, monkeypatch, args):
    monkeypatch.setattr(purge_module.sys, 'argv', ['oh-no-parent-control-purge', *args])
    operation = Mock()
    monkeypatch.setattr(purge_module, 'purge', operation)
    with pytest.raises(ValueError, match='no-arguments-accepted'):
        purge_module.main()
    operation.assert_not_called()


def test_unprivileged_purge_refuses_before_reading_source_or_running_commands(purge_module, monkeypatch):
    monkeypatch.setattr(purge_module.os, 'geteuid', lambda: 1000)
    source, commands = Mock(), Mock()
    monkeypatch.setattr(purge_module, 'cleanup_source', source)
    monkeypatch.setattr(purge_module.subprocess, 'run', commands)
    with pytest.raises(ValueError, match='root-required'):
        purge_module.purge(yes=True)
    source.assert_not_called()
    commands.assert_not_called()


@pytest.mark.parametrize('fault', ['symlink', 'owner', 'writeable', 'hardlink', 'ancestor'])
def test_owned_source_and_state_guards_refuse_substitutions(purge_module, fault):
    info = SimpleNamespace(st_mode=stat.S_IFREG | (0o666 if fault == 'writeable' else 0o644),
                           st_uid=1000 if fault == 'owner' else 0,
                           st_nlink=2 if fault == 'hardlink' else 1)
    if fault == 'symlink':
        info.st_mode = stat.S_IFLNK | 0o777
    parent = Mock(lstat=Mock(return_value=SimpleNamespace(
        st_mode=stat.S_IFDIR | 0o755, st_uid=1000 if fault == 'ancestor' else 0)))
    target = Mock(parents=[parent], lstat=Mock(return_value=info))
    with pytest.raises(ValueError, match='unsafe-'):
        purge_module.secure(target, directory=False)


@pytest.mark.parametrize('fault', [None, 'erase', 'still-installed', 'pam', 'cleanup', 'interruption'])
def test_fedora_public_purge_runs_cleanup_only_in_native_callback_and_preserves_retry_data(
    purge_module, tmp_path, monkeypatch, capsys, fault,
):
    machine = Machine(tmp_path, 'fedora')
    machine.baseline(active=True, enabled=True, rules='original policy\n')
    preference = machine.write('var/lib/oh-no-parent-control/preferences/1004.json', 'saved preferences')
    log = machine.write('var/log/oh-no-parent-control/broker/day.log', 'retained log')
    source = machine.prepare_script(script_source('postrm', 'fedora')).read_text()
    monkeypatch.setattr(purge_module, 'Path', lambda value: tmp_path / str(value).lstrip('/'))
    monkeypatch.setattr(purge_module.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(purge_module.platform, 'freedesktop_os_release', lambda: {
        'ID': 'fedora', 'VERSION_ID': '44', 'VARIANT_ID': 'workstation'})
    events = []
    monkeypatch.setattr(purge_module, 'cleanup_source', lambda: (events.append('source') or source))
    monkeypatch.setattr(purge_module, 'secure', Mock())
    def pam():
        events.append('pam')
        if fault == 'pam':
            raise ValueError('purge:product-pam-reference-remains')
    monkeypatch.setattr(purge_module, 'verify_fedora_pam', pam)
    monkeypatch.setattr(purge_module, 'begin_intent', lambda: (events.append('intent') or (1, 2)))
    monkeypatch.setattr(purge_module, 'remove_intent', lambda identity: events.append('release'))
    queries = 0
    native_callback = False
    original_run = subprocess.run
    def run(argv, **kwargs):
        nonlocal queries, native_callback
        if native_callback and argv == ['/bin/sh', str(tmp_path / 'script'), '0']:
            return original_run(argv, **kwargs)
        if argv[0] == 'rpm':
            queries += 1
            events.append('query')
            return SimpleNamespace(stdout=purge_module.PRODUCT if queries == 1 or fault == 'still-installed' else '')
        if argv[0] == 'dnf':
            events.append('erase')
            assert argv == ['dnf', 'remove', '--no-autoremove', '-y', purge_module.PRODUCT]
            if fault == 'erase':
                raise subprocess.CalledProcessError(7, argv)
            if fault == 'interruption':
                raise KeyboardInterrupt
            if fault in ('still-installed', 'pam'):
                return SimpleNamespace(returncode=0)
            # The executable payload is gone before shared purge runs.
            for path in (tmp_path / 'usr/libexec').iterdir():
                path.unlink()
            events.append('cleanup')
            native_callback = True
            try:
                result = machine.run_rpm('postun', 0, RPM_REMOVAL_PHASE='purge', SERVICE_ACTIVE='1',
                                         TRUST_UPDATE_STATUS='9' if fault == 'cleanup' else '0')
            finally:
                native_callback = False
            if fault != 'cleanup':
                assert result.returncode == 0, result.stderr
                assert (tmp_path / 'run/oh-no-parent-control-reboot-required').read_text() == 'reboot\n'
                assert 'REBOOT REQUIRED: reboot to finish removing' in result.stderr
            # RPM postun failure can still accompany a successful DNF exit;
            # the public action must independently prove the postconditions.
            return SimpleNamespace(returncode=0)
        raise AssertionError('destructive work escaped the native transaction: ' + repr(argv))
    monkeypatch.setattr(purge_module.subprocess, 'run', run)
    if fault:
        with pytest.raises((ValueError, subprocess.CalledProcessError, KeyboardInterrupt)):
            purge_module.purge(yes=True)
        assert preference.read_text() == 'saved preferences' and log.read_text() == 'retained log'
        assert (tmp_path / 'var/lib/oh-no-parent-control/fapolicyd-before-install/complete').exists()
        if fault in ('erase', 'still-installed', 'pam', 'interruption'):
            assert 'cleanup' not in events
    else:
        purge_module.purge(yes=True)
        assert not (tmp_path / 'var/lib/oh-no-parent-control').exists()
        assert not (tmp_path / 'var/log/oh-no-parent-control').exists()
    output = capsys.readouterr()
    assert ('REBOOT REQUIRED: reboot to finish removing' in output.err) is (fault is None)
    assert events[0] == 'source'
    if 'erase' in events:
        assert events.index('source') < events.index('erase')
        assert 'release' in events


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
@pytest.mark.parametrize('pending_reboot', [False, True])
def test_standalone_saved_data_purge_preserves_but_does_not_recreate_reboot_request(
    tmp_path, distribution, pending_reboot,
):
    machine = Machine(tmp_path, distribution)
    marker_path = ('run/oh-no-parent-control-reboot-required' if distribution == 'fedora'
                   else 'run/reboot-required')
    marker = tmp_path / marker_path
    if pending_reboot:
        machine.write(marker_path, 'existing reboot request\n')
    machine.write('var/lib/oh-no-parent-control/preferences/1004.json', 'saved preference')
    machine.write('var/log/oh-no-parent-control/broker/day.log', 'saved log')

    result = machine.run('postrm', 'purge')

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / 'var/lib/oh-no-parent-control').exists()
    assert not (tmp_path / 'var/log/oh-no-parent-control').exists()
    assert marker.exists() is pending_reboot
    if pending_reboot:
        assert marker.read_text() == 'existing reboot request\n'
    assert 'REBOOT REQUIRED' not in result.stderr


@pytest.mark.parametrize('package_format', ['ubuntu', 'fedora'])
@pytest.mark.parametrize('yes', [False, True])
def test_native_confirmation_is_default_and_yes_is_explicit(purge_module, monkeypatch, package_format, yes):
    monkeypatch.setattr(purge_module.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(purge_module.platform, 'freedesktop_os_release', lambda: {
        'ID': package_format, 'VERSION_ID': '44', 'VARIANT_ID': 'workstation'})
    monkeypatch.setattr(purge_module, 'cleanup_source', lambda: 'fixed cleanup')
    monkeypatch.setattr(purge_module, 'secure', Mock())
    monkeypatch.setattr(purge_module, 'verify_fedora_pam', Mock())
    monkeypatch.setattr(purge_module, 'debian_purged', lambda: True)
    monkeypatch.setattr(purge_module, 'verify_purged_data', Mock())
    monkeypatch.setattr(purge_module, 'begin_intent', lambda: (1, 2))
    monkeypatch.setattr(purge_module, 'remove_intent', Mock())
    queries = iter([True, False])
    monkeypatch.setattr(purge_module, 'rpm_installed', lambda: next(queries))
    run = Mock(return_value=SimpleNamespace(stdout=purge_module.PRODUCT))
    monkeypatch.setattr(purge_module.subprocess, 'run', run)
    purge_module.purge(yes=yes)
    transactions = [call.args[0] for call in run.call_args_list if call.args[0][0] in ('apt-get', 'dnf')]
    assert len(transactions) == 1 and ('-y' in transactions[0]) == yes
    assert transactions[0][-1] == purge_module.PRODUCT


@pytest.mark.parametrize('reference', ['pam_oh_no_parent_control.so', '/usr/libexec/oh-no-parent-control-login-check'])
def test_retained_active_pam_reference_blocks_saved_data_deletion(purge_module, tmp_path, monkeypatch, reference):
    pam = tmp_path / 'pam.d'
    pam.mkdir()
    (pam / 'login').write_text('auth required ' + reference)
    native_path = Path
    monkeypatch.setattr(purge_module, 'Path', lambda value: pam if value == '/etc/pam.d' else native_path(tmp_path / 'missing-record'))
    run = Mock(return_value=SimpleNamespace(stdout='local'))
    monkeypatch.setattr(purge_module.subprocess, 'run', run)
    with pytest.raises(ValueError, match='product-pam-reference-remains'):
        purge_module.verify_fedora_pam()
    assert run.call_args_list[0].args[0] == ['authselect', 'check']
    assert run.call_args_list[0].kwargs['stdout'] == subprocess.PIPE


def test_bad_cleanup_source_fails_before_any_transaction(purge_module, monkeypatch):
    monkeypatch.setattr(purge_module.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(purge_module.platform, 'freedesktop_os_release', lambda: {'ID': 'ubuntu'})
    monkeypatch.setattr(purge_module, 'cleanup_source', Mock(side_effect=ValueError('purge:unsafe-cleanup-source')))
    run = Mock()
    monkeypatch.setattr(purge_module.subprocess, 'run', run)
    with pytest.raises(ValueError, match='unsafe-cleanup-source'):
        purge_module.purge()
    run.assert_not_called()


@pytest.mark.parametrize('rows, expected', [
    ('other-package\tii \n', True),
    ('oh-no-parent-control\tpn \n', True),
    ('oh-no-parent-control\tii \n', False),
    ('oh-no-parent-control\trc \n', False),
    ('oh-no-parent-control\n', False),
    ('oh-no-parent-control\t\n', False),
])
def test_debian_success_requires_absent_package_and_configuration(purge_module, monkeypatch, rows, expected):
    run = Mock(return_value=SimpleNamespace(stdout=rows))
    monkeypatch.setattr(purge_module.subprocess, 'run', run)
    assert purge_module.debian_purged() is expected
    assert run.call_args.kwargs['check'] is True


@pytest.mark.parametrize('fault', ['cancelled', 'retained-data'])
def test_apt_zero_exit_is_not_purge_success_without_postconditions(
    purge_module, monkeypatch, capsys, fault,
):
    monkeypatch.setattr(purge_module.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(purge_module.platform, 'freedesktop_os_release', lambda: {'ID': 'ubuntu'})
    monkeypatch.setattr(purge_module, 'cleanup_source', lambda: 'fixed cleanup')
    monkeypatch.setattr(purge_module, 'secure', Mock())
    monkeypatch.setattr(purge_module, 'debian_purged', lambda: fault != 'cancelled')
    saved_data = Mock(side_effect=ValueError('purge:saved-data-remains'))
    monkeypatch.setattr(purge_module, 'verify_purged_data', saved_data)
    monkeypatch.setattr(purge_module.subprocess, 'run', Mock(return_value=SimpleNamespace(
        stdout=purge_module.PRODUCT, returncode=0)))
    with pytest.raises(ValueError, match='package-not-purged|saved-data-remains'):
        purge_module.purge()
    assert 'outcome=accepted' not in capsys.readouterr().out
    if fault == 'cancelled':
        saved_data.assert_not_called()


@pytest.mark.parametrize('residue', ['directory', 'dangling-symlink'])
def test_purge_postcondition_rejects_saved_data_residue(purge_module, tmp_path, monkeypatch, residue):
    root = tmp_path / 'var/lib/oh-no-parent-control'
    root.parent.mkdir(parents=True)
    if residue == 'directory':
        root.mkdir()
    else:
        root.symlink_to(tmp_path / 'missing')
    monkeypatch.setattr(purge_module, 'Path', lambda value: tmp_path / str(value).lstrip('/'))
    with pytest.raises(ValueError, match='saved-data-remains'):
        purge_module.verify_purged_data()


def test_saved_root_preflight_refusal_precedes_package_erase(purge_module, monkeypatch):
    monkeypatch.setattr(purge_module.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(purge_module.platform, 'freedesktop_os_release', lambda: {'ID': 'ubuntu'})
    monkeypatch.setattr(purge_module, 'cleanup_source', lambda: 'fixed cleanup')
    monkeypatch.setattr(purge_module, 'secure', Mock(side_effect=ValueError('purge:unsafe-owned-path')))
    run = Mock()
    monkeypatch.setattr(purge_module.subprocess, 'run', run)
    with pytest.raises(ValueError, match='unsafe-owned-path'):
        purge_module.purge(yes=True)
    run.assert_not_called()


def intent_value():
    return {'purpose': 'onpc-native-rpm-purge-v1', 'owner_pid': 20,
            'owner_start': 70, 'boot_id': '12345678-1234-1234-1234-123456789012'}


@pytest.mark.parametrize('fault', [None, 'owner', 'short', 'oversize', 'numeric'])
def test_proc_identity_uses_root_owner_parent_and_kernel_start_time(purge_module, monkeypatch, fault):
    fields = ['S', '7', *(['0'] * 17), 'invalid' if fault == 'numeric' else '91']
    raw = '40 (name with ) separator) ' + ' '.join(fields)
    if fault == 'short': raw = '40 (name) S 7'
    if fault == 'oversize': raw += ' ' * 8192
    monkeypatch.setattr(purge_module.os, 'stat', lambda path: SimpleNamespace(st_uid=1000 if fault == 'owner' else 0))
    monkeypatch.setattr('builtins.open', lambda *args, **kwargs: io.StringIO(raw))
    if fault:
        with pytest.raises(ValueError):
            purge_module.process_identity(40)
    else:
        assert purge_module.process_identity(40) == (7, 91)


@pytest.mark.parametrize('fault', [None, 'boot', 'start', 'missing', 'reparented', 'depth', 'invalid', 'unprivileged'])
def test_native_callback_purge_requires_live_exact_root_ancestry(purge_module, monkeypatch, fault):
    value = intent_value()
    monkeypatch.setattr(purge_module.os, 'geteuid', lambda: 1000 if fault == 'unprivileged' else 0)
    monkeypatch.setattr(purge_module.os, 'getpid', lambda: 40)
    read = Mock(side_effect=ValueError('purge:invalid-intent')) if fault == 'invalid' else Mock(return_value=(value, (1, 2)))
    monkeypatch.setattr(purge_module, 'read_intent', read)
    monkeypatch.setattr(purge_module, 'current_boot', lambda: 'other' if fault == 'boot' else value['boot_id'])
    def process(pid):
        if fault == 'missing':
            raise FileNotFoundError
        if fault == 'reparented':
            return 1, 50
        if fault == 'depth':
            return pid + 1, 50
        return {40: (30, 50), 30: (20, 60), 20: (1, 71 if fault == 'start' else 70)}[pid]
    monkeypatch.setattr(purge_module, 'process_identity', process)
    pam, remove = Mock(), Mock()
    monkeypatch.setattr(purge_module, 'verify_fedora_pam', pam)
    monkeypatch.setattr(purge_module, 'remove_intent', remove)
    assert purge_module.rpm_removal_phase() == ('remove' if fault else 'purge')
    if fault:
        pam.assert_not_called()
        remove.assert_not_called()
    else:
        pam.assert_called_once_with()
        remove.assert_called_once_with((1, 2))


def test_matching_native_purge_pam_failure_keeps_retry_intent(purge_module, monkeypatch):
    value = intent_value()
    monkeypatch.setattr(purge_module.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(purge_module.os, 'getpid', lambda: 20)
    monkeypatch.setattr(purge_module, 'read_intent', lambda: (value, (1, 2)))
    monkeypatch.setattr(purge_module, 'current_boot', lambda: value['boot_id'])
    monkeypatch.setattr(purge_module, 'process_identity', lambda pid: (1, 70))
    monkeypatch.setattr(purge_module, 'verify_fedora_pam', Mock(side_effect=ValueError('purge:unsafe-pam')))
    removed = Mock()
    monkeypatch.setattr(purge_module, 'remove_intent', removed)
    with pytest.raises(ValueError, match='unsafe-pam'):
        purge_module.rpm_removal_phase()
    removed.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'owner', 'mode', 'hardlink', 'symlink', 'oversize',
                                  'json', 'purpose', 'pid', 'start', 'boot', 'extra'])
def test_native_intent_reads_require_secure_finite_records(purge_module, tmp_path, monkeypatch, fault):
    value = intent_value()
    if fault == 'purpose': value['purpose'] = 'unrelated'
    if fault == 'pid': value['owner_pid'] = True
    if fault == 'start': value['owner_start'] = -1
    if fault == 'boot': value['boot_id'] = 'short'
    if fault == 'extra': value['path'] = '/'
    path = tmp_path / 'intent.json'
    path.write_text('{' if fault == 'json' else 'x' * 1025 if fault == 'oversize' else json.dumps(value))
    path.chmod(0o644 if fault == 'mode' else 0o600)
    if fault == 'hardlink': os.link(path, tmp_path / 'link.json')
    if fault == 'symlink':
        target = tmp_path / 'target.json'
        path.rename(target)
        path.symlink_to(target)
    monkeypatch.setattr(purge_module, 'INTENT', path)
    monkeypatch.setattr(purge_module, 'secure', Mock())
    original_stat = os.fstat
    def file_stat(fd):
        info = original_stat(fd)
        return SimpleNamespace(st_mode=info.st_mode, st_uid=1000 if fault == 'owner' else 0,
                               st_nlink=info.st_nlink, st_size=info.st_size,
                               st_dev=info.st_dev, st_ino=info.st_ino)
    monkeypatch.setattr(purge_module.os, 'fstat', file_stat)
    if fault:
        with pytest.raises((OSError, ValueError)):
            purge_module.read_intent()
    else:
        assert purge_module.read_intent()[0] == value


@pytest.mark.parametrize('state', ['new', 'live', 'dead', 'prior-boot'])
def test_intent_creation_refuses_live_owner_and_retries_only_exact_stale_file(
    purge_module, tmp_path, monkeypatch, state,
):
    path = tmp_path / 'intent.json'
    value = intent_value()
    if state != 'new':
        path.write_text(json.dumps(value))
    identity = (path.stat().st_dev, path.stat().st_ino) if path.exists() else None
    monkeypatch.setattr(purge_module, 'INTENT', path)
    monkeypatch.setattr(purge_module, 'read_intent', lambda: (value, identity) if identity else None)
    monkeypatch.setattr(purge_module.os, 'getpid', lambda: 40)
    monkeypatch.setattr(purge_module, 'current_boot', lambda: '87654321-1234-1234-1234-123456789012' if state == 'prior-boot' else value['boot_id'])
    def process(pid):
        if state == 'dead' and pid == 20:
            raise FileNotFoundError
        return 1, 70
    monkeypatch.setattr(purge_module, 'process_identity', process)
    if state == 'live':
        with pytest.raises(ValueError, match='already-running'):
            purge_module.begin_intent()
        assert json.loads(path.read_text()) == value
    else:
        created = purge_module.begin_intent()
        assert json.loads(path.read_text())['owner_pid'] == 40
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        purge_module.remove_intent(created)
        assert not path.exists()


def test_intent_cleanup_preserves_replacement(purge_module, tmp_path, monkeypatch):
    path = tmp_path / 'intent.json'
    path.write_text('original')
    identity = path.stat().st_dev, path.stat().st_ino
    path.rename(tmp_path / 'previous.json')
    path.write_text('replacement')
    monkeypatch.setattr(purge_module, 'INTENT', path)
    with pytest.raises(ValueError, match='intent-replaced'):
        purge_module.remove_intent(identity)
    assert path.read_text() == 'replacement'


def test_post_transaction_reinstall_is_never_cleaned_up_by_the_purge_cli(purge_module, tmp_path, monkeypatch):
    saved = tmp_path / 'preferences.json'
    monkeypatch.setattr(purge_module.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(purge_module.platform, 'freedesktop_os_release', lambda: {
        'ID': 'fedora', 'VERSION_ID': '44', 'VARIANT_ID': 'workstation'})
    monkeypatch.setattr(purge_module, 'cleanup_source', lambda: 'fixed cleanup')
    monkeypatch.setattr(purge_module, 'secure', Mock())
    monkeypatch.setattr(purge_module, 'begin_intent', lambda: (1, 2))
    monkeypatch.setattr(purge_module, 'remove_intent', Mock())
    queries = iter([True, True])
    monkeypatch.setattr(purge_module, 'rpm_installed', lambda: next(queries))
    def native(argv, **kwargs):
        assert argv[0] == 'dnf'
        saved.write_text('new installation data')
    monkeypatch.setattr(purge_module.subprocess, 'run', native)
    with pytest.raises(ValueError, match='package-still-installed'):
        purge_module.purge(yes=True)
    assert saved.read_text() == 'new installation data'
