"""Filesystem-backed selected-account catalog precedence regressions.

These host checks never install or launch applications. Installed discovery and
enforcement qualification remains in Task 15A's guarded system selection.
"""

from types import SimpleNamespace

import pytest

from oh_no_parent_control import catalog
from oh_no_parent_control.core import UserAccount


@pytest.fixture
def catalog_tree(tmp_path, monkeypatch):
    homes = {role: tmp_path / role for role in ('child', 'other-child', 'admin')}
    accounts = {
        role: SimpleNamespace(pw_uid=uid, pw_dir=str(homes[role]))
        for uid, role in enumerate(homes, start=1001)
    }
    system = tuple(tmp_path / path for path in (
        'usr/local/share/applications', 'usr/share/applications',
        'var/lib/flatpak/exports/share/applications',
    ))
    system_bins = tuple(tmp_path / path for path in (
        'usr/local/bin', 'usr/bin', 'bin',
    ))
    monkeypatch.setattr(catalog.pwd, 'getpwnam', accounts.__getitem__)
    monkeypatch.setattr(catalog, 'SYSTEM_APPLICATION_DIRS', system)
    monkeypatch.setattr(catalog, 'SYSTEM_EXECUTABLE_DIRS', system_bins)
    # The broker's inherited administrator environment must not select the
    # administrator's launchers when the requested child changes.
    monkeypatch.setenv('HOME', str(homes['admin']))
    monkeypatch.setenv('XDG_DATA_HOME', str(homes['admin'] / '.local/share'))
    monkeypatch.setenv('XDG_DATA_DIRS', str(homes['admin'] / '.local/share'))

    def discover(role='child'):
        user = UserAccount(accounts[role].pw_uid, role, role, False, False, True)
        return {app['id']: app for app in catalog.list_apps(user)}

    def binary(directory, name):
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
        target.chmod(0o755)
        return target

    def launcher(directory, desktop_id, label, extra='', command=None):
        target = tmp_path / 'targets' / label
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
        target.chmod(0o755)
        filename = directory / desktop_id
        filename.parent.mkdir(parents=True, exist_ok=True)
        exec_line = command if command is not None else f'"{target}"'
        filename.write_text(
            '[Desktop Entry]\nType=Application\n'
            f'Name={label}\nExec={exec_line}\n{extra}',
            encoding='utf-8',
        )
        return target

    return SimpleNamespace(
        homes=homes, accounts=accounts, system=system, system_bins=system_bins,
        discover=discover, launcher=launcher, binary=binary,
        local=homes['child'] / '.local/share/applications',
        flatpak=homes['child'] / '.local/share/flatpak/exports/share/applications',
    )


def test_selected_child_precedence_and_administrator_exclusion(catalog_tree):
    tree = catalog_tree
    desktop_id = 'org.example.Shared.desktop'
    for index, directory in enumerate(tree.system):
        tree.launcher(directory, desktop_id, f'system-{index}')
    tree.launcher(tree.flatpak, desktop_id, 'child-export')
    target = tree.launcher(tree.local, desktop_id, 'child override with spaces')
    admin = tree.homes['admin'] / '.local/share/applications'
    tree.launcher(admin, desktop_id, 'admin-substitution')
    tree.launcher(admin, 'org.example.AdminOnly.desktop', 'admin-only')
    system_only = tree.launcher(
        tree.system[1], 'org.example.SystemOnly.desktop', 'system-only',
    )
    child_only = tree.launcher(tree.local, 'org.example.ChildOnly.desktop', 'child-only')

    apps = tree.discover()

    assert set(apps) == {
        desktop_id, 'org.example.SystemOnly.desktop', 'org.example.ChildOnly.desktop',
    }
    assert apps[desktop_id]['targets'] == (str(target),)
    assert apps[desktop_id]['name'] == 'child override with spaces'
    assert apps['org.example.SystemOnly.desktop']['targets'] == (str(system_only),)
    assert apps['org.example.ChildOnly.desktop']['targets'] == (str(child_only),)


def test_switching_selected_child_does_not_reuse_another_childs_launchers(catalog_tree):
    tree = catalog_tree
    desktop_id = 'org.example.Shared.desktop'
    system_target = tree.launcher(tree.system[0], desktop_id, 'system')
    child_target = tree.launcher(tree.local, desktop_id, 'child')
    tree.launcher(tree.local, 'org.example.ChildOnly.desktop', 'child-only')
    other = tree.homes['other-child'] / '.local/share/applications'
    tree.launcher(other, 'org.example.OtherOnly.desktop', 'other-only')

    child_apps = tree.discover('child')
    other_apps = tree.discover('other-child')
    child_again = tree.discover('child')

    assert child_apps[desktop_id]['targets'] == (str(child_target),)
    assert other_apps[desktop_id]['targets'] == (str(system_target),)
    assert set(other_apps) == {desktop_id, 'org.example.OtherOnly.desktop'}
    assert set(child_apps) == {desktop_id, 'org.example.ChildOnly.desktop'}
    assert child_again == child_apps


def test_child_flatpak_export_precedes_system_launcher(catalog_tree):
    tree = catalog_tree
    desktop_id = 'org.example.Flatpak.desktop'
    tree.launcher(tree.system[0], desktop_id, 'system-substitution')
    deployment = tree.homes['child'] / '.local/share/flatpak/app/export'
    deployment.mkdir(parents=True)
    source = deployment / desktop_id
    source.write_text(
        '[Desktop Entry]\nType=Application\nName=Child Flatpak\n'
        'X-Flatpak=org.example.Flatpak\n'
        'Exec=/usr/bin/flatpak run --arch=x86_64 --branch=stable org.example.Flatpak\n',
        encoding='utf-8',
    )
    tree.flatpak.mkdir(parents=True)
    (tree.flatpak / desktop_id).symlink_to(source)

    assert tree.discover()[desktop_id]['targets'] == (
        'app/org.example.Flatpak/x86_64/stable',
    )


@pytest.mark.parametrize('nested', [False, True], ids=['flat-id', 'nested-id'])
@pytest.mark.parametrize('visibility', ['Hidden=true', 'NoDisplay=true'])
def test_child_visibility_override_masks_lower_priority_launchers(
        catalog_tree, nested, visibility):
    tree = catalog_tree
    desktop_id = 'vendor-org.example.Masked.desktop'
    child_filename = 'vendor/org.example.Masked.desktop' if nested else desktop_id
    tree.launcher(tree.system[0], desktop_id, 'system-masked')
    tree.launcher(tree.flatpak, desktop_id, 'export-masked')
    tree.launcher(tree.local, child_filename, 'child-masked', visibility + '\n')
    visible = tree.launcher(tree.system[1], 'org.example.Visible.desktop', 'visible')

    apps = tree.discover()

    assert set(apps) == {'org.example.Visible.desktop'}
    assert apps['org.example.Visible.desktop']['targets'] == (str(visible),)


def test_system_directory_precedence_is_preserved(catalog_tree):
    tree = catalog_tree
    desktop_id = 'org.example.System.desktop'
    target = tree.launcher(tree.system[0], desktop_id, 'local-system')
    tree.launcher(tree.system[1], desktop_id, 'distribution-system')
    tree.launcher(tree.system[2], desktop_id, 'system-export')

    assert tree.discover()[desktop_id]['targets'] == (str(target),)


@pytest.mark.parametrize('entry', [
    '[Desktop Entry]\nHidden=true\n',
    '[Desktop Entry]\nType=Application\nName=Unavailable\n',
    'invalid desktop entry\n',
], ids=['minimal-hidden', 'missing-exec', 'malformed-entry'])
def test_unlistable_child_override_does_not_substitute_system_target(catalog_tree, entry):
    tree = catalog_tree
    desktop_id = 'org.example.Unlistable.desktop'
    tree.launcher(tree.system[0], desktop_id, 'system-substitution')
    tree.local.mkdir(parents=True)
    (tree.local / desktop_id).write_text(entry, encoding='utf-8')

    assert tree.discover() == {}


@pytest.mark.parametrize('identity', ['missing-account', 'replaced-uid'])
def test_unavailable_or_replaced_account_does_not_fall_back_to_system_catalog(
        catalog_tree, identity, caplog):
    tree = catalog_tree
    tree.launcher(tree.system[0], 'org.example.System.desktop', 'system')
    user = UserAccount(1001, 'child', 'child', False, False, True)
    if identity == 'missing-account':
        del tree.accounts['child']
        reason = 'account-unavailable'
    else:
        tree.accounts['child'].pw_uid = 2001
        reason = 'identity-mismatch'

    assert catalog.list_apps(user) == ()
    assert [record.getMessage() for record in caplog.records] == [
        f'catalog discovery outcome={reason}',
    ]


@pytest.mark.parametrize('child_bin', ['.local/bin', 'bin'])
def test_relative_exec_prefers_selected_child_binary(catalog_tree, monkeypatch, child_bin):
    tree = catalog_tree
    command = 'onpc-catalog-game'
    target = tree.binary(tree.homes['child'] / child_bin, command)
    if child_bin == '.local/bin':
        tree.binary(tree.homes['child'] / 'bin', command)
    tree.binary(tree.system_bins[0], command)
    admin = tree.binary(tree.homes['admin'] / 'bin', command)
    monkeypatch.setenv('PATH', str(admin.parent))
    tree.launcher(tree.system[0], 'game.desktop', 'Game', command=command + ' %u')

    assert tree.discover()['game.desktop']['targets'] == (str(target),)


def test_relative_exec_switches_child_without_reusing_binary(catalog_tree, monkeypatch):
    tree = catalog_tree
    command = 'onpc-catalog-game'
    child = tree.binary(tree.homes['child'] / '.local/bin', command)
    other = tree.binary(tree.homes['other-child'] / 'bin', command)
    admin = tree.binary(tree.homes['admin'] / 'bin', command)
    monkeypatch.setenv('PATH', str(admin.parent))
    tree.launcher(tree.system[0], 'game.desktop', 'Game', command=command)

    assert tree.discover('child')['game.desktop']['targets'] == (str(child),)
    assert tree.discover('other-child')['game.desktop']['targets'] == (str(other),)
    assert tree.discover('child')['game.desktop']['targets'] == (str(child),)


@pytest.mark.parametrize('system_index', [0, 1, 2])
def test_relative_exec_system_fallback_ignores_admin_path(
        catalog_tree, monkeypatch, system_index):
    tree = catalog_tree
    command = 'onpc-catalog-game'
    for directory in tree.system_bins[system_index:]:
        tree.binary(directory, command)
    target = tree.system_bins[system_index] / command
    admin = tree.binary(tree.homes['admin'] / 'bin', command)
    monkeypatch.setenv('PATH', str(admin.parent))
    tree.launcher(tree.local, 'game.desktop', 'Game', command=command)

    assert tree.discover()['game.desktop']['targets'] == (str(target),)


@pytest.mark.parametrize('inherited_path', ['admin', 'empty', 'relative', 'unset'])
@pytest.mark.parametrize('command_prefix', ['', './'], ids=['bare', 'relative-path'])
def test_relative_exec_never_uses_admin_or_working_directory_fallback(
        catalog_tree, monkeypatch, inherited_path, command_prefix):
    tree = catalog_tree
    command = 'onpc-catalog-admin-only'
    admin = tree.binary(tree.homes['admin'] / 'bin', command)
    monkeypatch.chdir(admin.parent)
    if inherited_path == 'unset':
        monkeypatch.delenv('PATH', raising=False)
    else:
        monkeypatch.setenv('PATH', {
            'admin': str(admin.parent), 'empty': '', 'relative': '.',
        }[inherited_path])
    tree.launcher(tree.local, 'game.desktop', 'Game', command=command_prefix + command)

    assert tree.discover() == {}


def test_relative_exec_system_symlink_uses_canonical_native_target(catalog_tree, monkeypatch):
    tree = catalog_tree
    target = tree.binary(tree.homes['child'] / 'Applications', 'Game with spaces')
    command = tree.system_bins[0] / 'onpc-catalog-game'
    command.parent.mkdir(parents=True)
    command.symlink_to(target)
    monkeypatch.setenv('PATH', str(command.parent))
    tree.launcher(tree.local, 'game.desktop', 'Game', command=command.name)

    assert tree.discover()['game.desktop']['targets'] == (str(target),)


def test_relative_exec_system_alias_cannot_select_generic_launcher(catalog_tree, monkeypatch):
    tree = catalog_tree
    wrapper = tree.binary(tree.system_bins[1], 'shared-wrapper')
    command = tree.system_bins[0] / 'onpc-catalog-game'
    command.parent.mkdir(parents=True)
    command.symlink_to(wrapper)
    monkeypatch.setattr(catalog, 'GENERIC_LAUNCHERS', {str(wrapper)})
    monkeypatch.setenv('PATH', str(command.parent))
    tree.launcher(tree.local, 'game.desktop', 'Game', command=command.name)

    assert tree.discover() == {}
