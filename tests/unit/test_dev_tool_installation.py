"""Clean-machine rendering and root-owned installation boundaries."""
import ast
import json
import os
from pathlib import Path
import runpy
import shutil
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
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


def test_rules_render_for_a_checkout_with_spaces(tmp_path):
    root = tmp_path / 'checkout with spaces'
    (root / 'tools').mkdir(parents=True)
    (root / 'config').mkdir()
    for name in ('run-tests', 'run-unit-tests', 'run-ui-tests', 'diagnose', 'test-vm', 'cleanup-screenshots', 'read-only'):
        shutil.copy2(ROOT / 'tools' / name, root / 'tools' / name)
    shutil.copy2(ROOT / 'config/codex-tests.rules', root / 'config/codex-tests.rules')
    rendered = rules['render'](root)
    assert '@CHECKOUT@' not in rendered
    assert str(root / 'tools/run-tests') in rendered
    ast.parse(rendered)  # This declaration-only rules subset has valid string literals.
    (root / 'tools/test-vm').chmod(0o644)
    with pytest.raises(ValueError):
        rules['render'](root)


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
    execute = Mock()
    monkeypatch.setattr(installer['subprocess'], 'run', execute)
    installer['install_missing_dependencies']()
    if missing:
        command = execute.call_args.args[0]
        assert command[-3:] == ['ripgrep', 'curl', 'python3-pytest-cov']
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
