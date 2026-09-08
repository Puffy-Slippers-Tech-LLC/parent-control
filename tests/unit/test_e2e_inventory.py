"""Host-safe E2E selection/refusal regressions. No guest or worker imports."""

import copy
import importlib.util
import itertools
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('e2e_inventory', ROOT / 'tests/e2e/inventory.py')
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


@pytest.fixture
def document():
    return inventory.read_json(inventory.INVENTORY)[0]


def family(document, sid='E2E-012'):
    return next(item for item in document['scenarios'] if item['id'] == sid)


def test_starting_families_and_owners_match_required_coverage(document):
    inventory.validate_inventory(document)
    required = dict(re.findall(r'^\| (E2E-\d{3}) \| ([0-9A-Z/]+) \|',
                               (ROOT / 'docs/TestAutomation/E2E-Coverage.md').read_text(), re.M))
    actual = {item['id']: item for item in document['scenarios']}
    assert set(required) <= actual.keys()
    for sid, owners in required.items():
        assert actual[sid]['owners'] == owners.split('/')
    assert actual['E2E-001']['category'] == 'runner-smoke'
    assert actual['E2E-028']['category'] == actual['E2E-029']['category'] == 'fault-recovery'


def test_full_inventory_keeps_every_pending_case_and_evidence(document):
    plan = inventory.resolve_selection(document)
    expected = [item['id'] + '/' + variant['id'] for item in document['scenarios']
                for variant in item['variants']]
    assert [case['case_id'] for case in plan['cases']] == expected
    assert plan['pending_cases'] == [case['case_id'] for case in plan['cases']
                                     if case['status'] == 'pending']
    assert len(plan['pending_cases']) == 156
    assert plan['scope'] == 'full'
    assert [case['case_id'] for case in plan['cases'] if case['executable'] is not None] == [
        'E2E-001/gdm-observation']
    assert all(case['assertions'] and case['expected_evidence'] for case in plan['cases'])
    assert plan['evidence_contract']['outcomes'] == ['product', 'infrastructure', 'collection', 'cleanup']


@pytest.mark.parametrize('sid', ['E2E-013', 'E2E-014', 'E2E-015'])
def test_shared_form_family_selects_both_surfaces_and_all_variants(document, sid):
    plan = inventory.resolve_selection(document, sid)
    assert {case['parameters']['surface'] for case in plan['cases']} == {'child-overlay', 'kiosk'}
    assert len(plan['cases']) == len(family(document, sid)['variants'])
    assert plan['scope'] == 'partial'


def test_specific_variant_selects_once_and_keeps_pending_reason(document):
    plan = inventory.resolve_selection(document, 'E2E-023/fullscreen')
    assert len(plan['cases']) == 1
    assert plan['cases'][0]['parameters'] == {'gameplay': 'fullscreen'}
    assert plan['pending_cases'] == ['E2E-023/fullscreen']
    assert plan['cases'][0]['pending_reason']
    assert plan['scope'] == 'partial'
    assert [step['operation'] for step in plan['cases'][0]['phases']['steps']] == [
        'ui', 'ui', 'ui', 'ui', 'wait', 'ui']


@pytest.mark.parametrize('selector,category', [('', 'empty'), ('   ', 'empty'),
    ('E2E-000', 'unknown'), ('E2E-023/missing', 'unknown'), ('E2E-02', 'unknown'),
    ('E2E-023/*', 'unknown'), ('E2E-023,E2E-024', 'unknown'), ('E2E-023 ', 'unknown')])
def test_invalid_selection_fails_without_broadening(document, selector, category):
    with pytest.raises(inventory.InventoryError, match='selection:' + category):
        inventory.resolve_selection(document, selector)


@pytest.mark.parametrize('selector', [None, 'E2E-002', 'E2E-023/fullscreen',
    'E2E-028/startup-enforcement', 'E2E-028/startup-broker'])
def test_pending_selection_cannot_run(document, selector):
    with pytest.raises(inventory.InventoryError, match='selection:pending'):
        inventory.resolve_selection(document, selector, require_runnable=True)


def test_startup_selection_keeps_independent_failure_boundaries(document):
    clean = inventory.resolve_selection(document, 'E2E-002')['cases'][0]
    assert clean['requirement_gap'] is None
    assert set(clean['requirements']) == {'ONPC-CORE-INSTALL-001', 'ONPC-COMP-BROKER-010'}
    faults = inventory.resolve_selection(document, 'E2E-028')['cases']
    assert {case['case_id'] for case in faults if case['owner'] == '20'} == {
        'E2E-028/startup-enforcement', 'E2E-028/startup-broker'}
    # A recovered final state cannot substitute for observing the failed gate.
    for case in faults:
        for kind in ('visible', 'backend'):
            assert any(item['step_id'] == 'step-3' for item in case['assertions'][kind])
    # Dropping either startup boundary must fail declared matrix closure.
    chosen = family(document, 'E2E-028')
    chosen['variants'] = [v for v in chosen['variants'] if v['id'] != 'startup-broker']
    with pytest.raises(inventory.InventoryError, match='matrix:missing-value'):
        inventory.validate_inventory(document)


@pytest.mark.parametrize('scope', ['document', 'scenario', 'variant', 'step', 'evidence'])
def test_every_required_field_is_enforced(document, scope):
    def target(data):
        return {'document': data, 'scenario': data['scenarios'][0],
                'variant': data['scenarios'][0]['variants'][0],
                'step': data['scenarios'][0]['phases']['steps'][0],
                'evidence': data['evidence_contract']}[scope]
    for key in target(document):
        changed = copy.deepcopy(document)
        del target(changed)[key]
        with pytest.raises(inventory.InventoryError):
            inventory.validate_inventory(changed)


@pytest.mark.parametrize('value', [2, True, '1', None])
def test_unknown_schema_versions_fail(document, value):
    document['schema_version'] = value
    with pytest.raises(inventory.InventoryError, match='schema-version'):
        inventory.validate_inventory(document)


@pytest.mark.parametrize('value', [0, -1, True, '600', 86401, None])
def test_duration_is_a_bounded_positive_integer(document, value):
    document['scenarios'][0]['duration_seconds'] = value
    with pytest.raises(inventory.InventoryError, match='scenario:duration'):
        inventory.validate_inventory(document)


@pytest.mark.parametrize('location', ['scenarios', 'variants'])
def test_empty_or_duplicate_registry_refused(document, location):
    parent = document if location == 'scenarios' else family(document)
    original = parent[location]
    parent[location] = original + [copy.deepcopy(original[0])]
    with pytest.raises(inventory.InventoryError, match='duplicate-id'):
        inventory.validate_inventory(document)
    parent[location] = []
    with pytest.raises(inventory.InventoryError, match='empty'):
        inventory.validate_inventory(document)


def test_missing_interacting_combination_is_not_hidden_by_value_coverage(document):
    chosen = family(document)
    chosen['variants'].pop()
    assert all({case['parameters'][key] for case in chosen['variants']} == set(values)
               for key, values in chosen['matrix']['dimensions'].items())
    with pytest.raises(inventory.InventoryError, match='matrix:missing-combination'):
        inventory.validate_inventory(document)


def test_declared_dimension_value_cannot_disappear(document):
    chosen = family(document, 'E2E-023')
    chosen['variants'].pop()
    with pytest.raises(inventory.InventoryError, match='matrix:missing-value'):
        inventory.validate_inventory(document)


def test_same_combination_cannot_be_copied_under_new_id(document):
    chosen = family(document)
    duplicate = copy.deepcopy(chosen['variants'][0])
    duplicate['id'] = 'duplicate'
    chosen['variants'].append(duplicate)
    with pytest.raises(inventory.InventoryError, match='variant:duplicate-combination'):
        inventory.validate_inventory(document)


def test_unknown_requirement_and_unowned_variant_refused(document):
    chosen = family(document)
    chosen['requirements'].append('ONPC-NONEXISTENT-001')
    with pytest.raises(inventory.InventoryError, match='unknown-requirement'):
        inventory.validate_inventory(document)
    chosen['requirements'].pop()
    chosen['variants'][0]['owner'] = '28B'
    with pytest.raises(inventory.InventoryError, match='variant:owner'):
        inventory.validate_inventory(document)


@pytest.mark.parametrize('operation', ['outer-reset', 'snapshot', 'checkpoint', 'resume', 'provision', 'fault'])
def test_customer_steps_cannot_declare_reset_provision_or_undeclared_fault(document, operation):
    family(document)['phases']['steps'][0]['operation'] = operation
    with pytest.raises(inventory.InventoryError, match='step:(operation|category)'):
        inventory.validate_inventory(document)


def test_fault_intervention_requires_actor_step_and_evidence(document):
    chosen = family(document, 'E2E-028')
    chosen['interventions'].pop()
    with pytest.raises(inventory.InventoryError, match='intervention:declaration'):
        inventory.validate_inventory(document)


@pytest.mark.parametrize('kind', ['visible', 'backend', 'other_user'])
def test_three_sided_assertions_are_required(document, kind):
    family(document)['assertions'][kind] = []
    with pytest.raises(inventory.InventoryError, match='assertion:empty'):
        inventory.validate_inventory(document)


def test_assertions_must_reference_an_actual_journey_step(document):
    family(document)['assertions']['visible'][0]['step_id'] = 'cleanup'
    with pytest.raises(inventory.InventoryError, match='assertion:step'):
        inventory.validate_inventory(document)


@pytest.mark.parametrize('field', ['run_fields', 'step_fields', 'outcomes'])
def test_minimum_evidence_fields_cannot_be_dropped(document, field):
    document['evidence_contract'][field].pop()
    with pytest.raises(inventory.InventoryError, match='evidence:required-fields'):
        inventory.validate_inventory(document)


def test_expected_screen_evidence_cannot_be_replaced_by_backend_only(document):
    family(document)['expected_evidence'].remove('screen')
    with pytest.raises(inventory.InventoryError, match='evidence:expectations'):
        inventory.validate_inventory(document)


@pytest.fixture
def ready_document(document, tmp_path):
    """A declared executable is only inspected, never imported or executed."""
    document['scenarios'] = [family(document)]
    for relative in ['tests/requirements.json', 'docs/TestAutomation/E2E-Coverage.md']:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    executable = tmp_path / 'tests/e2e/tests/example.py'
    executable.parent.mkdir(parents=True)
    executable.write_text('raise RuntimeError("inventory must never execute this")\n')
    variant = document['scenarios'][0]['variants'][0]
    variant.update(status='ready', pending_reason=None,
                   executable={'path': 'tests/e2e/tests/example.py', 'test_id': 'test_example'})
    return document, tmp_path, variant


def test_ready_exact_case_resolves_but_family_does_not_drop_pending(ready_document):
    document, root, variant = ready_document
    exact = 'E2E-012/' + variant['id']
    plan = inventory.resolve_selection(document, exact, require_runnable=True, root=root)
    assert plan['pending_cases'] == []
    assert plan['cases'][0]['executable']['test_id'] == 'test_example'
    with pytest.raises(inventory.InventoryError, match='selection:pending'):
        inventory.resolve_selection(document, 'E2E-012', require_runnable=True, root=root)


@pytest.mark.parametrize('path', ['/tmp/example.py', 'tests/e2e/../../example.py',
                                 'tests/integration/system_runner.py', 'tests/e2e/tests/missing.py',
                                 'tests/e2e/scenarios.json'])
def test_ready_executable_must_exist_inside_e2e(ready_document, path):
    document, root, variant = ready_document
    variant['executable']['path'] = path
    with pytest.raises(inventory.InventoryError, match='executable:'):
        inventory.validate_inventory(document, root=root)


def test_ready_executable_symlink_cannot_escape_e2e(ready_document):
    document, root, variant = ready_document
    (root / 'outside.py').write_text('')
    (root / 'tests/e2e/escape.py').symlink_to(root / 'outside.py')
    variant['executable']['path'] = 'tests/e2e/escape.py'
    with pytest.raises(inventory.InventoryError, match='missing-or-escaping'):
        inventory.validate_inventory(document, root=root)


def test_duplicate_executable_identity_cannot_double_count_evidence(ready_document):
    document, root, variant = ready_document
    second = document['scenarios'][0]['variants'][1]
    second.update(status='ready', pending_reason=None, executable=variant['executable'])
    with pytest.raises(inventory.InventoryError, match='duplicate-test-id'):
        inventory.validate_inventory(document, root=root)


def test_requirement_gap_prevents_ready_status(ready_document):
    document, root, _ = ready_document
    document['scenarios'][0]['requirement_gap'] = 'Owning task must map an obligation.'
    with pytest.raises(inventory.InventoryError, match='unresolved-prerequisite'):
        inventory.validate_inventory(document, root=root)


@pytest.mark.parametrize('path', [(), ('scenarios',), ('scenarios', 0),
    ('scenarios', 0, 'variants', 0, 'parameters'), ('scenarios', 0, 'assertions'),
    ('scenarios', 0, 'phases'), ('scenarios', 0, 'matrix', 'dimensions')])
@pytest.mark.parametrize('value', [None, True, 5, 'private sentinel', []])
def test_malformed_nested_input_has_bounded_errors(document, path, value):
    if path:
        target = document
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
    else:
        document = value
    with pytest.raises(inventory.InventoryError) as caught:
        inventory.validate_inventory(document)
    assert 'private sentinel' not in str(caught.value)


def test_duplicate_json_keys_and_invalid_json_are_refused(tmp_path):
    path = tmp_path / 'bad.json'
    for content in ['{"schema_version": 1, "schema_version": 1}', '{', '\udcff']:
        path.write_bytes(content.encode('utf-8', errors='surrogatepass'))
        with pytest.raises(inventory.InventoryError):
            inventory.read_json(path)


def test_listing_is_cwd_independent_and_does_not_need_artifacts_or_vm(tmp_path):
    before = set(tmp_path.iterdir())
    command = [sys.executable, '-B', str(inventory.INVENTORY.with_name('inventory.py')),
               '--scenario', 'E2E-023']
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan['mode'] == 'list-only' and plan['vm_required_for_execution'] is True
    assert len(plan['inventory_sha256']) == 64
    assert {case['case_id'] for case in plan['cases']} == {'E2E-023/windowed', 'E2E-023/fullscreen'}
    assert set(tmp_path.iterdir()) == before
    result = subprocess.run(command + ['--require-runnable'], cwd=tmp_path,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 2
    assert result.stderr.strip() == 'selection:pending'
    assert not result.stdout


def test_every_declared_launch_route_policy_control_combination_remains_pending(document):
    chosen = family(document, 'E2E-019')
    expected = set(itertools.product(
        chosen['matrix']['dimensions']['route'], ['allowed', 'hard-blocked', 'soft-blocked'],
        ['enabled', 'disabled']))
    actual = {(v['parameters']['route'], v['parameters']['policy'], v['parameters']['control'])
              for v in chosen['variants']}
    assert actual == expected
    assert all(v['status'] == 'pending' for v in chosen['variants'])


def test_unmapped_surfaces_and_external_delivery_are_explicit_pending_work(document):
    for sid in ['E2E-030', 'E2E-031', 'E2E-032', 'E2E-033']:
        chosen = family(document, sid)
        assert chosen['requirement_gap']
        assert all(v['status'] == 'pending' for v in chosen['variants'])
    assert {'explicit-external-delivery-authorization', 'dedicated-test-recipient',
            'supported-real-feedback-service-profile'} <= set(family(document, 'E2E-032')['preconditions'])


def test_external_retry_is_declared_fault_recovery_and_requires_delivery_profile(document):
    chosen = family(document, 'E2E-033')
    assert chosen['category'] == 'fault-recovery'
    assert chosen['interventions']
    chosen['preconditions'].remove('explicit-external-delivery-authorization')
    with pytest.raises(inventory.InventoryError, match='delivery-prerequisites'):
        inventory.validate_inventory(document)
