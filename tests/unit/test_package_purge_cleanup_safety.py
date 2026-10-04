"""Public purge refuses unsafe input and erasure failures using private state."""
import importlib.util
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
def test_fedora_public_purge_uses_frozen_cleanup_and_preserves_retry_data(
    purge_module, tmp_path, monkeypatch, fault,
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
    native_run = subprocess.run
    queries = 0
    def run(argv, **kwargs):
        nonlocal queries
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
            # The executable payload is gone before shared purge runs.
            for path in (tmp_path / 'usr/libexec').iterdir():
                path.unlink()
            return SimpleNamespace(returncode=0)
        assert argv == ['/bin/sh', '-s', '--', 'purge']
        events.append('cleanup')
        assert kwargs['input'] == source
        if fault == 'cleanup':
            raise subprocess.CalledProcessError(9, argv)
        return native_run(argv, **kwargs, env={**os.environ, 'AUDIT_ROOT': str(tmp_path),
                                              'PATH': str(tmp_path / 'test-bin') + os.pathsep + os.environ['PATH']},
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
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
    assert events[0] == 'source'
    if 'erase' in events:
        assert events.index('source') < events.index('erase')


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
    monkeypatch.setattr(purge_module.subprocess, 'run', lambda argv, **kwargs: SimpleNamespace(stdout='local'))
    with pytest.raises(ValueError, match='product-pam-reference-remains'):
        purge_module.verify_fedora_pam()


def test_bad_cleanup_source_fails_before_any_transaction(purge_module, monkeypatch):
    monkeypatch.setattr(purge_module.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(purge_module.platform, 'freedesktop_os_release', lambda: {'ID': 'ubuntu'})
    monkeypatch.setattr(purge_module, 'cleanup_source', Mock(side_effect=ValueError('purge:unsafe-cleanup-source')))
    run = Mock()
    monkeypatch.setattr(purge_module.subprocess, 'run', run)
    with pytest.raises(ValueError, match='unsafe-cleanup-source'):
        purge_module.purge()
    run.assert_not_called()
