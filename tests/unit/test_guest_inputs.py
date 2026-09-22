"""Automatic dependency discovery and immutable per-run guest payloads."""
import subprocess
import sys

import pytest

from guest_inputs import Bundle, InputError
from tests.support.paths import ROOT


def write(root, name, text):
    path = root / 'tests/integration' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def bundle(root):
    return Bundle(root, [('tests/integration/entry.py', 'entry.py')])


def test_new_transitive_and_function_local_imports_are_staged_automatically(tmp_path):
    write(tmp_path, 'entry.py', 'import helper\ndef later():\n import later_helper\n')
    write(tmp_path, 'helper.py', 'import nested\n')
    write(tmp_path, 'nested.py', 'import helper\n')
    write(tmp_path, 'later_helper.py', 'value = 1\n')
    frozen = bundle(tmp_path)
    assert set(frozen.files) == {'entry.py', 'helper.py', 'nested.py', 'later_helper.py'}
    frozen.stage(tmp_path / 'payload')
    result = subprocess.run([sys.executable, '-I', '-B', '-c',
        'import sys; sys.path.insert(0, sys.argv[1]); import entry; entry.later()',
        str(tmp_path / 'payload')], capture_output=True)
    assert result.returncode == 0, result.stderr


def test_changed_added_and_removed_dependencies_only_affect_next_bundle(tmp_path):
    write(tmp_path, 'entry.py', 'import old\n')
    write(tmp_path, 'old.py', 'value = 1\n')
    frozen = bundle(tmp_path)
    write(tmp_path, 'entry.py', 'import new\n')
    write(tmp_path, 'new.py', 'value = 2\n')
    (tmp_path / 'tests/integration/old.py').unlink()
    assert frozen.stage(tmp_path / 'attempt1') == frozen.stage(tmp_path / 'attempt2')
    assert (tmp_path / 'attempt2/entry.py').read_text() == 'import old\n'
    assert set(bundle(tmp_path).files) == {'entry.py', 'new.py'}


def test_relative_packages_and_from_submodule_imports(tmp_path):
    write(tmp_path, 'entry.py', 'from helpers import child\n')
    write(tmp_path, 'helpers/__init__.py', '')
    write(tmp_path, 'helpers/child.py', 'from . import sibling\n')
    write(tmp_path, 'helpers/sibling.py', 'answer = 42\n')
    assert set(bundle(tmp_path).files) == {'entry.py', 'helpers/__init__.py',
                                         'helpers/child.py', 'helpers/sibling.py'}


@pytest.mark.parametrize('fault', ['missing', 'ambiguous', 'symlink'])
def test_invalid_dependency_refuses_before_any_payload_is_written(tmp_path, fault):
    write(tmp_path, 'entry.py', 'import helper\n')
    if fault != 'missing':
        write(tmp_path, 'helper.py', '')
    if fault == 'ambiguous':
        path = tmp_path / 'tests/system/helper.py'
        path.parent.mkdir()
        path.write_text('')
    elif fault == 'symlink':
        path = tmp_path / 'tests/integration/helper.py'
        path.unlink()
        path.symlink_to('entry.py')
    with pytest.raises(InputError):
        bundle(tmp_path)
    assert not (tmp_path / 'payload').exists()


def test_real_setup_closure_imports_without_checkout_or_host_observer(tmp_path):
    import installed_setup
    frozen = installed_setup.inputs(ROOT)
    assert {'system_guest.py', 'e2e_dynamic_account.py', 'owned_commands.py',
            'guest_install_recipe.py', 'guest/redact.py'} <= frozen.files.keys()
    assert 'watch_activity.py' not in frozen.files
    frozen.stage(tmp_path)
    result = subprocess.run([sys.executable, '-I', '-B', '-c',
        'import sys; sys.path.insert(0, sys.argv[1]); '
        'import system_guest, e2e_dynamic_account, guest_install_recipe', str(tmp_path)],
        capture_output=True)
    assert result.returncode == 0, result.stderr


def test_recipe_digest_tracks_its_dependencies_but_ignores_unrelated_helpers(tmp_path):
    write(tmp_path, 'entry.py', 'import recipe\nimport helper\n')
    write(tmp_path, 'recipe.py', 'import installation\n')
    write(tmp_path, 'installation.py', 'value = 1\n')
    write(tmp_path, 'helper.py', 'value = 1\n')
    original = bundle(tmp_path).digest('recipe.py')
    write(tmp_path, 'helper.py', 'value = 2\n')
    assert bundle(tmp_path).digest('recipe.py') == original
    write(tmp_path, 'installation.py', 'value = 2\n')
    assert bundle(tmp_path).digest('recipe.py') != original


def test_system_setup_can_use_frozen_recipe_after_checkout_changes(tmp_path):
    import json
    write(tmp_path, 'entry.py', 'import recipe\n')
    write(tmp_path, 'recipe.py', 'value = 1\n')
    original = bundle(tmp_path)
    payload = tmp_path / 'payload'
    files = original.stage(payload)
    (payload / 'selected-inputs.json').write_text(json.dumps({'files': files}))
    write(tmp_path, 'recipe.py', 'import new_helper\n')
    write(tmp_path, 'new_helper.py', 'value = 2\n')
    frozen = Bundle.from_staged(tmp_path, payload)
    assert frozen.files == original.files
    assert frozen.digest('recipe.py') == original.digest('recipe.py')
    assert bundle(tmp_path).digest('recipe.py') != original.digest('recipe.py')


def test_staged_source_mutation_is_never_accepted_as_a_new_input(tmp_path):
    import json
    write(tmp_path, 'entry.py', 'value = 1\n')
    payload = tmp_path / 'payload'
    files = bundle(tmp_path).stage(payload)
    (payload / 'selected-inputs.json').write_text(json.dumps({'files': files}))
    (payload / 'entry.py').write_text('value = 2\n')
    with pytest.raises(InputError, match='staged-digest'):
        Bundle.from_staged(tmp_path, payload)
