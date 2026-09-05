"""The real APT path is accessible only after the explicit VM guard passes."""

from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tests/integration'))
import system_guest as guest
sys.path.pop(0)


@pytest.mark.parametrize('path,group', [
    ('/usr/share/applications/com.puffyslippers.OhNoParentControl.Parent.desktop', 'sudo'),
    ('/etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules', 'fapolicyd'),
    ('/etc/polkit-1/rules.d/00-oh-no-parent-control-session.rules', 'root'),
    ('/usr/libexec/oh-no-parent-control-broker', 'root'),
    ('/unrelated/com.puffyslippers.OhNoParentControl.Parent.desktop', 'root'),
])
def test_installed_groups_match_exact_maintainer_and_dependency_paths(monkeypatch, path, group):
    lookup = Mock(return_value=Mock(gr_gid=42))
    monkeypatch.setattr(guest.grp, 'getgrnam', lookup)
    assert guest.installed_group(Path(path)) == 42
    lookup.assert_called_once_with(group)


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
