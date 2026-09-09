"""Real temporary catalog trees with mocked installed caller boundaries."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import system_enforcement as enforcement

@pytest.fixture
def installed_catalog_tree(monkeypatch, tmp_path):
    # The privileged dispatcher's unprivileged safety phase clears PYTHONPATH.
    # Resolve this fixture's source dependency without relying on host setup.
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'broker'))
    from oh_no_parent_control import catalog
    from oh_no_parent_control.core import UserAccount

    accounts = {'child': 1001, 'other': 1002, 'parent': 1003}
    identities = {}
    for role, uid in accounts.items():
        home = tmp_path / role
        home.mkdir(mode=0o700)
        identities[uid] = SimpleNamespace(pw_uid=uid, pw_gid=uid, pw_dir=str(home))
    target = tmp_path / 'native/fixture'
    target.parent.mkdir()
    target.write_bytes(b'fixture')
    target.chmod(0o755)
    system = tmp_path / 'system'
    system.mkdir()
    desktop = system / enforcement.DESKTOP_ID
    desktop.write_text(f'[Desktop Entry]\nType=Application\nName=System\nExec="{target}"\n')
    monkeypatch.setattr(enforcement, 'TARGET', target)
    monkeypatch.setattr(enforcement, 'DESKTOP', desktop)
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    monkeypatch.setattr(enforcement.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(enforcement.pwd, 'getpwuid', identities.__getitem__)
    monkeypatch.setattr(enforcement.pwd, 'getpwnam', lambda role: identities[accounts[role]])
    chown = Mock()
    monkeypatch.setattr(enforcement.os, 'chown', chown)
    monkeypatch.setattr(catalog, 'SYSTEM_APPLICATION_DIRS', (system,))
    monkeypatch.setenv('HOME', identities[1003].pw_dir)
    monkeypatch.setenv('XDG_DATA_HOME', str(Path(identities[1003].pw_dir) / '.local/share'))
    monkeypatch.setenv('PATH', str(Path(identities[1003].pw_dir) / '.local/bin'))
    local_bin, system_bin = tmp_path / 'local-bin', tmp_path / 'system-bin'
    monkeypatch.setattr(enforcement, 'CATALOG_LOCAL_BIN', local_bin)
    monkeypatch.setattr(enforcement, 'CATALOG_SYSTEM_BIN', system_bin)
    monkeypatch.setattr(catalog, 'SYSTEM_EXECUTABLE_DIRS', (local_bin, system_bin))
    calls = []

    def call(uid, method, signature='()', args=()):
        assert (uid, method, signature) == (1003, 'ListApplications', '(u)')
        calls.append(args[0])
        role = next(role for role, value in accounts.items() if value == args[0])
        user = UserAccount(args[0], role, role, False, False, True)
        return [[[app['id'], app['name'], '', '', list(app['targets']), []]
                 for app in catalog.list_apps(user)]]

    monkeypatch.setattr(enforcement, 'call', call)
    return SimpleNamespace(accounts=accounts, identities=identities, target=target,
                           system=system, local_bin=local_bin, system_bin=system_bin,
                           call=call, calls=calls, chown=chown)
