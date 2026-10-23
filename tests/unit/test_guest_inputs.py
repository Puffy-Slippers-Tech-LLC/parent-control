"""Automatic dependency discovery and immutable per-run guest payloads."""
import subprocess
import sys

import pytest

from guest_inputs import Bundle, InputError
from tests.support.paths import ROOT
from tools.test_storage import scratch_descriptors


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


def test_repository_fixture_packages_import_from_frozen_payload(tmp_path):
    write(tmp_path, 'entry.py', 'from tests.fixtures import asset\n')
    for name, content in (
            ('tests/__init__.py', ''), ('tests/fixtures/__init__.py', ''),
            ('tests/fixtures/asset.py', 'from . import native\n'),
            ('tests/fixtures/native.py', 'answer = 42\n')):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    payload = tmp_path / 'payload'
    original = bundle(tmp_path)
    files = original.stage(payload)
    import json
    (payload / 'selected-inputs.json').write_text(json.dumps({'files': files}))
    assert Bundle.from_staged(tmp_path, payload).files == original.files
    result = subprocess.run([sys.executable, '-I', '-B', '-c',
        'import sys; sys.path.insert(0, sys.argv[1]); import entry; '
        'assert entry.asset.native.answer == 42', str(payload)], capture_output=True)
    assert result.returncode == 0, result.stderr


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
            'guest_install_recipe.py', 'guest/redact.py', 'system_kiosk_confinement.py',
            'system_kiosk_admission.py', 'system_kiosk_feedback.py',
            'baseline_environment.py', 'baseline_assets.py', 'native_assets.py'} <= frozen.files.keys()
    assert 'system_removal.py' not in frozen.files
    assert 'watch_activity.py' not in frozen.files
    frozen.stage(tmp_path)
    result = subprocess.run([sys.executable, '-I', '-B', '-c',
        'import sys; sys.path.insert(0, sys.argv[1]); '
        'import system_guest, e2e_dynamic_account, guest_install_recipe, '
        'system_kiosk_confinement, system_kiosk_admission, system_kiosk_feedback; '
        'assert callable(system_kiosk_confinement.census)', str(tmp_path)],
        capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_first_configuration_frozen_closure_imports_without_retired_helpers(tmp_path):
    import system_runner as runner
    from tests.support.vm_runner import INVENTORIES
    selection = runner.resolve_selection('package', runner.FIRST_CONFIGURE_CASE,
        inventories={**INVENTORIES,
                     'package': (*INVENTORIES['package'], runner.FIRST_CONFIGURE_CASE)})
    runner.stage_selected_inputs(selection, tmp_path)
    # Use the real consumer's explicit fixture inputs, including flat aliases
    # for baseline/native assets, before following its immutable import closure.
    frozen = Bundle.from_staged(ROOT, tmp_path)
    assert {'system_first_configure.py', 'system_removal.py', 'system_removal_faults.py',
            'system_kiosk_admission.py', 'system_kiosk_confinement.py',
            'system_kiosk_scope.py'} <= frozen.files.keys()
    assert not {'system_kiosk_platform.py', 'system_native_update.py',
                'system_kiosk_required_history.py', 'system_kiosk_ambient_history.py'} & frozen.files.keys()
    assert frozen.files['system_first_configure.py'] == (
        ROOT / 'tests/integration/system_first_configure.py').read_bytes()
    result = subprocess.run([sys.executable, '-I', '-B', '-c',
        'import sys; sys.path.insert(0, sys.argv[1]); import system_first_configure; '
        'assert callable(system_first_configure.exercise); '
        'assert callable(system_first_configure.verify_reboot); '
        'assert callable(system_first_configure.configure_fault)',
        str(tmp_path)], capture_output=True, timeout=10,
        pass_fds=scratch_descriptors())
    assert result.returncode == 0, result.stderr


def test_pam_variation_histories_freeze_and_import_current_helpers(tmp_path):
    import system_runner as runner
    from tests.support.vm_runner import INVENTORIES

    selection = runner.resolve_selection('package', runner.PAM_CASE, inventories={
        **INVENTORIES,
        'package': (*INVENTORIES['package'], *(history.case_id for history in runner.PAM_HISTORIES)),
    })
    runner.stage_selected_inputs(selection, tmp_path)
    frozen = Bundle.from_staged(ROOT, tmp_path)
    helpers = ('system_pam_variants.py', 'system_first_configure.py',
               'system_removal.py', 'system_removal_faults.py',
               'system_kiosk_admission.py', 'system_kiosk_confinement.py')
    for name in helpers:
        assert frozen.files[name] == (ROOT / 'tests/integration' / name).read_bytes()
    assert not {'system_kiosk_platform.py', 'system_native_update.py',
                'system_kiosk_required_history.py', 'system_kiosk_ambient_history.py'} & frozen.files.keys()
    result = subprocess.run([sys.executable, '-I', '-B', '-c',
        'import sys; sys.path.insert(0, sys.argv[1]); import system_pam_variants as variants; '
        'assert all(callable(getattr(variants, name)) for name in '
        '("exercise", "verify_reboot", "remove", "verify_removed_reboot"))',
        str(tmp_path)], capture_output=True, timeout=10,
        pass_fds=scratch_descriptors())
    assert result.returncode == 0, result.stderr


def test_native_preflight_freezes_without_copying_distribution_rpm_bindings(tmp_path):
    frozen = Bundle(ROOT, [('tests/integration/native_transaction.py', 'native_transaction.py')])
    assert set(frozen.files) == {'native_transaction.py'}
    frozen.stage(tmp_path)
    result = subprocess.run([sys.executable, '-I', '-B', '-c',
        'import sys; sys.path.insert(0, sys.argv[1]); import native_transaction; '
        'assert native_transaction.SCHEMA == 1', str(tmp_path)],
        capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_removal_histories_freeze_and_import_the_current_recovery_helpers(tmp_path):
    import system_runner as runner
    from tests.support.vm_runner import RECOVERY_INVENTORIES

    selection = runner.resolve_selection('removal', inventories=RECOVERY_INVENTORIES)
    runner.stage_selected_inputs(selection, tmp_path)
    frozen = Bundle.from_staged(ROOT, tmp_path)
    helpers = ('system_removal.py', 'system_removal_faults.py',
               'system_removal_ownership.py', 'system_removal_identity.py')
    assert set(helpers) <= frozen.files.keys()
    for name in helpers:
        assert frozen.files[name] == (ROOT / 'tests/integration' / name).read_bytes()
    assert not {'system_kiosk_platform.py', 'system_native_update.py',
                'system_kiosk_required_history.py', 'system_kiosk_ambient_history.py'} & frozen.files.keys()
    assert all('mac-unload' not in execution.case_id for execution in selection.executions)
    result = subprocess.run([sys.executable, '-I', '-B', '-c',
        'import sys; sys.path.insert(0, sys.argv[1]); '
        'import system_removal, system_removal_faults, system_removal_ownership, '
        'system_removal_identity; '
        'assert callable(system_removal.aborted_cleanup_rollback_retry); '
        'assert callable(system_removal.interrupted_finalization_retry); '
        'assert callable(system_removal.rpm_posterase_recovery); '
        'assert callable(system_removal.check_remove_preflight)',
        str(tmp_path)], capture_output=True, timeout=10,
        pass_fds=scratch_descriptors())
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
