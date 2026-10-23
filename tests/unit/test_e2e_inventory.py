"""Host-safe E2E selection/refusal regressions. No guest or worker imports."""

import copy
from tests.support.modules import load_module

import pytest


from tests.support.paths import ROOT
inventory = load_module('onpc_test_e2e_inventory', ROOT / 'tests/e2e/inventory.py')


@pytest.fixture
def document():
    return inventory.read_json(inventory.INVENTORY)[0]


def family(document, sid='E2E-012'):
    return next(item for item in document['scenarios'] if item['id'] == sid)


def test_full_inventory_keeps_every_pending_case_and_evidence(document):
    plan = inventory.resolve_selection(document)
    expected = [item['id'] + '/' + variant['id'] for item in document['scenarios']
                for variant in item['variants']]
    assert [case['case_id'] for case in plan['cases']] == expected
    assert plan['pending_cases'] == [case['case_id'] for case in plan['cases']
                                     if case['status'] == 'pending']
    assert plan['scope'] == 'full'
    assert all(case['assertions'] and case['expected_evidence'] for case in plan['cases'])
    assert plan['evidence_contract']['outcomes'] == ['product', 'infrastructure', 'collection', 'cleanup']


def test_ready_selection_explicitly_accounts_for_every_pending_case(document):
    full = inventory.resolve_selection(document)
    plan = inventory.resolve_selection(document, ready_only=True, require_runnable=True)
    assert plan['scope'] == 'partial' and plan['ready_only'] is True
    assert plan['pending_cases'] == []
    assert plan['excluded_pending_cases'] == full['pending_cases']
    assert plan['cases'] == [c for c in full['cases'] if c['status'] == 'ready']
    assert len(plan['cases']) + len(plan['excluded_pending_cases']) == len(full['cases'])
    with pytest.raises(inventory.InventoryError, match='conflicting-selectors'):
        inventory.resolve_selection(document, 'E2E-030', ready_only=True)


def test_no_ready_cases_refuses_instead_of_passing_an_empty_suite(document):
    for item in document['scenarios']:
        for variant in item['variants']:
            variant.update(status='pending', executable=None, pending_reason='Unimplemented fixture')
    with pytest.raises(inventory.InventoryError, match='selection:no-ready-cases'):
        inventory.resolve_selection(document, ready_only=True, require_runnable=True)


@pytest.mark.parametrize('selector,category', [('', 'empty'), ('   ', 'empty'),
    ('E2E-000', 'unknown'), ('E2E-023/missing', 'unknown'), ('E2E-02', 'unknown'),
    ('E2E-023/*', 'unknown'), ('E2E-023,E2E-024', 'unknown'), ('E2E-023 ', 'unknown')])
def test_invalid_selection_fails_without_broadening(document, selector, category):
    with pytest.raises(inventory.InventoryError, match='selection:' + category):
        inventory.resolve_selection(document, selector)


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


@pytest.mark.parametrize('field', ['run_fields', 'step_fields', 'outcomes'])
def test_minimum_evidence_fields_cannot_be_dropped(document, field):
    document['evidence_contract'][field].pop()
    with pytest.raises(inventory.InventoryError, match='evidence:required-fields'):
        inventory.validate_inventory(document)


@pytest.fixture
def ready_document(document, tmp_path):
    """A declared executable is only inspected, never imported or executed."""
    document['scenarios'] = [family(document)]
    for relative in ['tests/requirements.json', *document['scenarios'][0]['contract_refs']]:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    executable = tmp_path / 'tests/e2e/tests/example.py'
    executable.parent.mkdir(parents=True)
    executable.write_text('raise RuntimeError("inventory must never execute this")\n')
    variant = document['scenarios'][0]['variants'][0]
    assert document['scenarios'][0]['assertions']['backend'] == []
    assert 'backend' not in document['scenarios'][0]['expected_evidence']
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


def test_duplicate_json_keys_and_invalid_json_are_refused(tmp_path):
    path = tmp_path / 'bad.json'
    for content in ['{"schema_version": 1, "schema_version": 1}', '{', '\udcff']:
        path.write_bytes(content.encode('utf-8', errors='surrogatepass'))
        with pytest.raises(inventory.InventoryError):
            inventory.read_json(path)
