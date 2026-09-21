"""Clean-machine rendering and root-owned installation boundaries."""
import ast
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
from unittest.mock import Mock

import pytest

from tests.support.paths import ROOT
installer = runpy.run_path(str(ROOT / 'tools/install_test_runner.py'))
rules = runpy.run_path(str(ROOT / 'tools/install_codex_rules.py'))
UUID = 'f95890e1-88e7-4779-8ae3-53fdcc34330a'


@pytest.fixture
def baseline(tmp_path):
    directory = tmp_path / 'baseline'
    directory.mkdir(mode=0o700)
    state = directory / 'phase.json'
    state.write_text(json.dumps({'phase': 'finalized', 'source': {'layout': {'uuid': UUID}}}))
    state.chmod(0o600)
    return directory


def test_pin_from_finalized_provenance_only(baseline):
    assert installer['pinned_vm_uuid'](baseline, owner=os.getuid()) == UUID
    (baseline / 'phase.json').write_text('{"phase":"source-off"}')
    assert installer['pinned_vm_uuid'](baseline, owner=os.getuid()) is None
    assert installer['pinned_vm_uuid'](baseline / 'missing') is None


def test_default_pin_uses_configured_vm_state_and_never_legacy_record(baseline, monkeypatch):
    import vm_config
    monkeypatch.setattr(vm_config, 'STATE_ROOT', baseline)
    monkeypatch.setattr(vm_config, 'load', lambda: vm_config.VMConfig('another-vm', Path('/disk')))
    assert installer['pinned_vm_uuid'](owner=os.getuid()) is None
    selected = baseline / 'another-vm'
    selected.mkdir(mode=0o700)
    (selected / 'phase.json').write_bytes((baseline / 'phase.json').read_bytes())
    (selected / 'phase.json').chmod(0o600)
    assert installer['pinned_vm_uuid'](owner=os.getuid()) == UUID


@pytest.mark.parametrize('kind', ['file-mode', 'directory-mode', 'symlink', 'hardlink', 'uuid'])
def test_unsafe_baseline_cannot_pin_vm(baseline, kind):
    path = baseline / 'phase.json'
    if kind == 'file-mode':
        path.chmod(0o644)
    elif kind == 'directory-mode':
        baseline.chmod(0o755)
    elif kind == 'symlink':
        path.rename(baseline / 'other')
        path.symlink_to('other')
    elif kind == 'hardlink':
        os.link(path, baseline / 'other')
    else:
        path.write_text('{"phase":"finalized","source":{"layout":{"uuid":"other"}}}')
    with pytest.raises(ValueError):
        installer['pinned_vm_uuid'](baseline, owner=os.getuid())


def test_rendered_dispatcher_pins_checkout_and_uuid():
    source = installer['render_helper'](ROOT, 'onpc-test-runner', UUID)
    namespace = {}
    exec(compile(source, '<installed-dispatcher-fixture>', 'exec'), namespace)
    assert namespace['CHECKOUT'] == str(ROOT)
    assert namespace['VM_UUID'] == UUID
    assert namespace['selection'](ROOT, ['vm', 'reboot'])[-3:] == ['--expected-uuid', UUID, 'reboot']


def test_atomic_helper_install_and_symlink_refusal(tmp_path, monkeypatch):
    chown = Mock()
    monkeypatch.setattr(installer['os'], 'fchown', chown)
    target = tmp_path / 'libexec/helper'
    installer['install_file'](target, b'validated-helper', 0o755)
    assert target.read_bytes() == b'validated-helper'
    assert target.stat().st_mode & 0o777 == 0o755
    chown.assert_called_once()
    other = tmp_path / 'libexec/link'
    other.symlink_to(target)
    with pytest.raises(ValueError):
        installer['install_file'](other, b'overwrite', 0o755)
    assert target.read_bytes() == b'validated-helper'


@pytest.mark.parametrize('existing_cache', [False, True])
@pytest.mark.parametrize('ui_watch', [False, True])
def test_viewer_icon_resolves_after_fresh_and_repeated_setup(tmp_path, monkeypatch, existing_cache, ui_watch):
    import gi
    gi.require_version('Gtk', '4.0')
    from gi.repository import Gio, GLib, Gtk

    data_root = tmp_path / 'share'
    theme = data_root / 'icons/hicolor'
    icons = theme / '48x48/apps'
    icons.mkdir(parents=True)
    unrelated = icons / 'unrelated.png'
    logo = (ROOT / 'data/app_logo_titlebar.png').read_bytes()
    unrelated.write_bytes(logo)
    if existing_cache:
        subprocess.run(['/usr/bin/gtk-update-icon-cache', '--ignore-theme-index', str(theme)],
                       check=True)
    monkeypatch.setattr(os, 'fchown', Mock())
    for _ in range(2):
        options = dict(application_id='org.onpc.UIWatch', launcher='watch-ui',
                       title='UI tests — View only') if ui_watch else {}
        installer['install_watch_desktop'](ROOT, data_root=data_root, **options)
        app_id = 'org.onpc.UIWatch' if ui_watch else 'org.onpc.E2EWatch'
        entry = Gio.DesktopAppInfo.new_from_filename(
            str(data_root / 'applications' / (app_id + '.desktop')))
        assert entry is not None
        parsed, command = GLib.shell_parse_argv(entry.get_commandline())
        assert parsed and command == [str(ROOT / 'tools' / ('watch-ui' if ui_watch else 'watch-e2e'))]
        icon_name = entry.get_icon().to_string()
        lookup = Gtk.IconTheme.new()
        lookup.set_search_path([str(data_root / 'icons'), '/usr/share/icons'])
        lookup.set_theme_name('hicolor')
        assert lookup.has_icon(icon_name)
        assert (icons / (icon_name + '.png')).read_bytes() == logo
        assert lookup.has_icon('unrelated')
        assert unrelated.read_bytes() == logo


def test_tools_refresh_repairs_only_root_owned_cache_directory(tmp_path, monkeypatch):
    tools = tmp_path / 'tools'
    cache = tools / '__pycache__'
    cache.mkdir(parents=True)
    bytecode = cache / 'test_launcher.cpython-314.pyc'
    bytecode.write_bytes(b'preserved cache contents')
    original = cache.stat()
    real_fstat = os.fstat

    def root_owned_cache(descriptor):
        info = real_fstat(descriptor)
        if info.st_ino == original.st_ino and info.st_dev == original.st_dev:
            values = list(info)
            values[4] = values[5] = 0
            return os.stat_result(values)
        return info

    changed = []

    def chown(descriptor, uid, gid):
        info = real_fstat(descriptor)
        changed.append((info.st_dev, info.st_ino, uid, gid))

    with monkeypatch.context() as patch:
        patch.setattr(os, 'fstat', root_owned_cache)
        patch.setattr(os, 'fchown', chown)
        installer['repair_checkout_bytecode'](tmp_path)
    assert changed == [(original.st_dev, original.st_ino,
                        tools.stat().st_uid, tools.stat().st_gid)]
    assert bytecode.read_bytes() == b'preserved cache contents'
    assert bytecode.stat().st_uid == os.getuid()
    assert cache.stat().st_mode == original.st_mode

    # An already caller-owned cache and an absent cache are repeatable no-ops.
    untouched = Mock(side_effect=AssertionError('must not change caller-owned cache'))
    monkeypatch.setattr(os, 'fchown', untouched)
    installer['repair_checkout_bytecode'](tmp_path)
    bytecode.unlink()
    cache.rmdir()
    installer['repair_checkout_bytecode'](tmp_path)
    untouched.assert_not_called()


@pytest.mark.parametrize('kind', ['tools-symlink', 'cache-symlink', 'cache-file'])
def test_tools_refresh_refuses_unsafe_cache_path(tmp_path, monkeypatch, kind):
    tools = tmp_path / 'tools'
    outside = tmp_path / 'outside'
    outside.mkdir()
    if kind == 'tools-symlink':
        tools.symlink_to(outside, target_is_directory=True)
    else:
        tools.mkdir()
        cache = tools / '__pycache__'
        if kind == 'cache-symlink':
            cache.symlink_to(outside, target_is_directory=True)
        else:
            cache.write_bytes(b'preserve non-directory')
    chown = Mock(side_effect=AssertionError('unsafe path must not change ownership'))
    monkeypatch.setattr(os, 'fchown', chown)
    with pytest.raises((OSError, ValueError)):
        installer['repair_checkout_bytecode'](tmp_path)
    chown.assert_not_called()


def test_tools_refresh_installs_fixed_helper_before_cache_repair_and_can_retry(monkeypatch):
    main = installer['main']
    installed = Mock(side_effect=OSError('installation failed'))
    repaired = Mock()
    monkeypatch.setattr(os, 'geteuid', lambda: 0)
    monkeypatch.setattr(installer['sys'], 'argv', ['install_test_runner.py'])
    monkeypatch.setitem(main.__globals__, 'pinned_vm_uuid', lambda: None)
    monkeypatch.setitem(main.__globals__, 'install_missing_dependencies', Mock())
    monkeypatch.setitem(main.__globals__, 'install_file', installed)
    monkeypatch.setattr(installer['subprocess'], 'run', Mock())
    monkeypatch.setitem(main.__globals__, 'repair_checkout_bytecode', repaired)
    with pytest.raises(OSError, match='installation failed'):
        main()
    repaired.assert_not_called()
    installed.side_effect = None
    for _ in range(2):
        main()
    assert repaired.call_count == 2
    repaired.assert_called_with(ROOT)


def test_rules_render_for_a_checkout_with_spaces(tmp_path):
    root = tmp_path / 'checkout with spaces'
    (root / 'tools').mkdir(parents=True)
    (root / 'config').mkdir()
    for name in ('run-tests', 'run-unit-tests', 'run-ui-tests', 'diagnose', 'test-vm',
                 'cleanup-screenshots', 'read-only'):
        shutil.copy2(ROOT / 'tools' / name, root / 'tools' / name)
    shutil.copy2(ROOT / 'config/codex-tests.rules', root / 'config/codex-tests.rules')
    rendered = rules['render'](root)
    assert '@CHECKOUT@' not in rendered
    assert str(root / 'tools/run-tests') in rendered
    ast.parse(rendered)  # This declaration-only rules subset has valid string literals.
    (root / 'tools/test-vm').chmod(0o644)
    with pytest.raises(ValueError):
        rules['render'](root)


def test_project_tool_allow_covers_new_nested_executables_without_manual_inventory(tmp_path):
    root = tmp_path / 'checkout with spaces'
    nested = root / 'tools/future'
    nested.mkdir(parents=True)
    executable = nested / 'new-tool'
    executable.write_text('#!/usr/bin/python3\n')
    executable.chmod(0o755)
    (nested / 'support.py').write_text('# import-only module\n')
    assert rules['project_tool_paths'](root) == [
        'tools/future/new-tool', './tools/future/new-tool', str(executable)]
    executable.chmod(0o644)
    with pytest.raises(ValueError, match='no executable project tools'):
        rules['project_tool_paths'](root)


@pytest.mark.parametrize('replacement', [
    ('<allow_active>no</allow_active>', '<allow_active>auth_admin</allow_active>'),
    ('/usr/local/libexec/onpc-test-runner', '/usr/bin/python3'),
    ('org.freedesktop.policykit.exec.path', 'org.freedesktop.policykit.exec.argv1'),
])
def test_action_policy_refuses_prompts_or_generic_programs(tmp_path, replacement):
    installer['validated_policy'](ROOT)
    (tmp_path / 'config').mkdir()
    name = 'com.puffyslippers.onpc.development.policy'
    (tmp_path / 'config' / name).write_text((ROOT / 'config' / name).read_text().replace(*replacement))
    with pytest.raises(ValueError):
        installer['validated_policy'](tmp_path)


@pytest.mark.parametrize('missing', [False, True])
def test_only_missing_fixed_dependencies_are_installed_without_upgrades(monkeypatch, missing):
    monkeypatch.setattr(installer['os'], 'access', lambda *args: not missing)
    monkeypatch.setattr(installer['importlib'].util, 'find_spec', lambda *args: None if missing else object())
    monkeypatch.setitem(installer['install_missing_dependencies'].__globals__,
                        'watch_terminal_available', lambda: not missing)
    execute = Mock()
    monkeypatch.setattr(installer['subprocess'], 'run', execute)
    installer['install_missing_dependencies']()
    if missing:
        command = execute.call_args.args[0]
        assert command[-5:] == ['ripgrep', 'curl', 'gtk-update-icon-cache',
                               'python3-pytest-cov', 'gir1.2-vte-3.91']
        assert '--no-upgrade' in command
        assert '--no-remove' in command
        assert '--no-install-recommends' in command
        assert execute.call_args.kwargs['check'] is True
    else:
        execute.assert_not_called()


def test_system_rules_install_is_atomic_idempotent_and_preserves_other_rules(tmp_path, monkeypatch):
    target = tmp_path / 'etc/codex/rules/onpc-read-only.rules'
    target.parent.mkdir(parents=True)
    target.parent.parent.chmod(0o775)
    unrelated = target.with_name('organization.rules')
    unrelated.write_text('# preserved organization policy\n')
    real_stat = Path.stat

    def root_owned(path, *args, **kwargs):
        # Model /etc ownership in a user-owned fixture, without privilege.
        values = list(real_stat(path, *args, **kwargs))
        if path not in (target.parent, target.parent.parent):
            values[0] &= ~0o022
        values[4] = values[5] = 0
        return os.stat_result(values)

    monkeypatch.setattr(Path, 'stat', root_owned)
    monkeypatch.setattr(os, 'fchown', Mock())
    rules['install_system_rules'](ROOT, target)
    assert real_stat(target.parent.parent).st_mode & 0o777 == 0o755
    assert target.read_bytes() == (ROOT / 'config/codex-read-only.rules').read_bytes()
    assert target.stat().st_mode & 0o777 == 0o644
    with monkeypatch.context() as patch:
        replace = Mock(side_effect=AssertionError('unchanged rules must not be rewritten'))
        patch.setattr(os, 'replace', replace)
        rules['install_system_rules'](ROOT, target)
    assert unrelated.read_text() == '# preserved organization policy\n'
    target.unlink()
    target.symlink_to(unrelated)
    with pytest.raises(ValueError, match='symlink'):
        rules['install_system_rules'](ROOT, target)
    assert unrelated.read_text() == '# preserved organization policy\n'
