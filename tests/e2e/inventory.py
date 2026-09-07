"""Host-only E2E inventory validation and exact selection; no VM imports/actions."""

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / 'tests/e2e/scenarios.json'
CATEGORIES = {'customer-journey', 'runner-smoke', 'fault-recovery', 'environment-boundary'}
PHASES = ('setup', 'start', 'steps', 'end', 'cleanup')
EVIDENCE = {'action-trace', 'screen', 'backend', 'other-user', 'continuity',
            'input-provenance', 'outcomes', 'cleanup', 'intervention', 'delivery'}
RUN_FIELDS = ('run_id', 'scenario_id', 'variant_id', 'source_sha256',
              'inventory_sha256', 'package_sha256', 'assets_sha256',
              'environment_id', 'baseline_sha256', 'started_at', 'ended_at',
              'steps', 'artifacts', 'outcomes', 'first_failure', 'cleanup')
STEP_FIELDS = ('step_id', 'phase', 'operation', 'outcome', 'monotonic_seconds',
               'boot_id', 'session_ids', 'assertion_ids', 'artifact_ids')
OUTCOMES = ('product', 'infrastructure', 'collection', 'cleanup')


class InventoryError(ValueError):
    """A stable error category, never raw inventory/credential contents."""


def require(condition, category):
    if not condition:
        raise InventoryError(category)


def fields(value, names, category):
    require(isinstance(value, dict) and set(value) == set(names), category)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value, category, *, empty=False):
    require(isinstance(value, list) and (empty or bool(value)), category)
    require(all(nonempty(item) for item in value), category)
    require(len(value) == len(set(value)), category)


def token(value):
    return isinstance(value, str) and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value)


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'inventory:duplicate-json-key')
        result[key] = value
    return result


def read_json(path):
    try:
        raw = path.read_bytes()
        return json.loads(raw, object_pairs_hook=no_duplicate_keys), hashlib.sha256(raw).hexdigest()
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InventoryError('inventory:unreadable-json') from error


def validate_inventory(document, *, root=ROOT):
    """Validate declarations, matrix closure and references without executing them.

    Pending entries are valid inventory, but never runnable. This is structural
    validation, not proof that prose describes complete or safe customer actions.
    """
    try:
        _validate_inventory(document, root=root)
    except (TypeError, KeyError) as error:
        # Malformed nested JSON must produce the same bounded refusal as an
        # invalid field, not a traceback containing raw input values.
        raise InventoryError('inventory:invalid-shape') from error


def _validate_inventory(document, *, root):
    fields(document, ('schema_version', 'evidence_contract', 'scenarios'), 'inventory:fields')
    require(type(document['schema_version']) is int and document['schema_version'] == 1,
            'inventory:schema-version')
    contract = document['evidence_contract']
    fields(contract, ('schema_version', 'run_fields', 'step_fields', 'outcomes'), 'evidence:fields')
    require(type(contract['schema_version']) is int and contract['schema_version'] == 1,
            'evidence:schema-version')
    for key, expected in (('run_fields', RUN_FIELDS), ('step_fields', STEP_FIELDS),
                          ('outcomes', OUTCOMES)):
        require(contract[key] == list(expected), 'evidence:required-fields')
    registry, _ = read_json(root / 'tests/requirements.json')
    known_requirements = {entry['id'] for entry in registry['requirements']}
    scenarios = document['scenarios']
    require(isinstance(scenarios, list) and scenarios, 'inventory:empty')
    scenario_ids, case_ids, test_ids = set(), set(), set()
    for scenario in scenarios:
        fields(scenario, ('id', 'title', 'category', 'owners', 'requirements', 'requirement_gap',
                          'contract_refs', 'components', 'environment', 'preconditions',
                          'phases', 'interventions', 'assertions', 'expected_evidence',
                          'duration_seconds', 'matrix', 'variants'), 'scenario:fields')
        sid = scenario['id']
        require(isinstance(sid, str) and re.fullmatch(r'E2E-[0-9]{3}', sid), 'scenario:id')
        require(sid not in scenario_ids, 'scenario:duplicate-id')
        scenario_ids.add(sid)
        require(nonempty(scenario['title']), 'scenario:title')
        require(isinstance(scenario['category'], str) and scenario['category'] in CATEGORIES,
                'scenario:category')
        for key in ('owners', 'contract_refs', 'components', 'preconditions', 'expected_evidence'):
            strings(scenario[key], 'scenario:' + key)
        require(all(re.fullmatch(r'[0-9]{2}[ABC]?', owner) for owner in scenario['owners']),
                'scenario:owner')
        strings(scenario['requirements'], 'scenario:requirements', empty=True)
        require(set(scenario['requirements']) <= known_requirements, 'scenario:unknown-requirement')
        gap = scenario['requirement_gap']
        require(gap is None or nonempty(gap), 'scenario:requirement-gap')
        require(scenario['requirements'] or gap or scenario['category'] == 'runner-smoke',
                'scenario:missing-requirement')
        for ref in scenario['contract_refs']:
            path = Path(ref.split('#', 1)[0])
            require(not path.is_absolute() and '..' not in path.parts
                    and path.parts[:1] == ('docs',), 'scenario:contract-path')
            require((root / path).is_file(), 'scenario:missing-contract')
        require(scenario['environment'] == 'ubuntu26.04', 'scenario:environment')
        require(type(scenario['duration_seconds']) is int
                and 0 < scenario['duration_seconds'] <= 86400, 'scenario:duration')
        phases = scenario['phases']
        fields(phases, PHASES, 'scenario:phases')
        step_ids = set()
        for phase in PHASES:
            require(isinstance(phases[phase], list) and phases[phase], 'scenario:empty-phase')
            for step in phases[phase]:
                fields(step, ('id', 'operation', 'description'), 'step:fields')
                require(token(step['id']) and step['id'] not in step_ids, 'step:id')
                step_ids.add(step['id'])
                require(nonempty(step['description']), 'step:description')
                allowed = {'setup': {'provision'}, 'start': {'begin'},
                           'steps': {'ui', 'observe', 'wait', 'fault', 'environment'},
                           'end': {'collect'}, 'cleanup': {'outer-reset'}}[phase]
                require(isinstance(step['operation'], str) and step['operation'] in allowed,
                        'step:operation')
                if step['operation'] in ('fault', 'environment'):
                    required = {'fault': 'fault-recovery', 'environment': 'environment-boundary'}
                    require(scenario['category'] == required[step['operation']], 'step:category')
        interventions = scenario['interventions']
        require(isinstance(interventions, list), 'intervention:list')
        intervention_ids = set()
        for item in interventions:
            fields(item, ('step_id', 'actor', 'evidence'), 'intervention:fields')
            require(item['step_id'] in step_ids and item['step_id'] not in intervention_ids,
                    'intervention:step')
            intervention_ids.add(item['step_id'])
            require(nonempty(item['actor']) and nonempty(item['evidence']), 'intervention:evidence')
        fault_steps = {step['id'] for step in phases['steps']
                       if step['operation'] in ('fault', 'environment')}
        require(intervention_ids == fault_steps, 'intervention:declaration')
        if scenario['category'] in ('fault-recovery', 'environment-boundary'):
            require(bool(fault_steps), 'intervention:missing')
        assertions = scenario['assertions']
        fields(assertions, ('visible', 'backend', 'other_user'), 'assertion:fields')
        assertion_ids = set()
        for kind, items in assertions.items():
            require(isinstance(items, list) and items, 'assertion:empty')
            for item in items:
                fields(item, ('id', 'step_id', 'description'), 'assertion:fields')
                require(token(item['id']) and item['id'] not in assertion_ids, 'assertion:id')
                assertion_ids.add(item['id'])
                require(item['step_id'] in {step['id'] for step in phases['steps']},
                        'assertion:step')
                require(nonempty(item['description']), 'assertion:description')
        evidence = set(scenario['expected_evidence'])
        require(evidence <= EVIDENCE and EVIDENCE - {'intervention', 'delivery'} <= evidence,
                'evidence:expectations')
        require(not interventions or 'intervention' in evidence, 'evidence:intervention')
        if 'delivery' in evidence:
            require({'explicit-external-delivery-authorization', 'dedicated-test-recipient',
                     'supported-real-feedback-service-profile'} <= set(scenario['preconditions']),
                    'evidence:delivery-prerequisites')
        matrix = scenario['matrix']
        fields(matrix, ('dimensions', 'full_combinations', 'rationale'), 'matrix:fields')
        require(nonempty(matrix['rationale']), 'matrix:rationale')
        dimensions = matrix['dimensions']
        require(isinstance(dimensions, dict) and dimensions, 'matrix:dimensions')
        for key, values in dimensions.items():
            require(token(key), 'matrix:dimension-name')
            strings(values, 'matrix:values')
            require(all(token(value) for value in values), 'matrix:value-name')
        groups = matrix['full_combinations']
        require(isinstance(groups, list), 'matrix:groups')
        seen_groups = set()
        for group in groups:
            strings(group, 'matrix:group')
            require(set(group) <= set(dimensions) and len(group) >= 2, 'matrix:group')
            require(frozenset(group) not in seen_groups, 'matrix:duplicate-group')
            seen_groups.add(frozenset(group))
        variants = scenario['variants']
        require(isinstance(variants, list) and variants, 'scenario:empty-variants')
        combinations = set()
        for variant in variants:
            fields(variant, ('id', 'owner', 'parameters', 'status', 'pending_reason', 'executable'),
                   'variant:fields')
            require(token(variant['id']), 'variant:id')
            cid = sid + '/' + variant['id']
            require(cid not in case_ids, 'variant:duplicate-id')
            case_ids.add(cid)
            require(variant['owner'] in scenario['owners'], 'variant:owner')
            params = variant['parameters']
            fields(params, dimensions, 'variant:dimensions')
            require(all(isinstance(value, str) and value in dimensions[key]
                        for key, value in params.items()), 'variant:unknown-value')
            combination = tuple(params[key] for key in dimensions)
            require(combination not in combinations, 'variant:duplicate-combination')
            combinations.add(combination)
            require(variant['status'] in ('pending', 'ready'), 'variant:status')
            if variant['status'] == 'pending':
                require(nonempty(variant['pending_reason']) and variant['executable'] is None,
                        'variant:pending-contract')
            else:
                require(variant['pending_reason'] is None and gap is None,
                        'variant:unresolved-prerequisite')
                executable = variant['executable']
                fields(executable, ('path', 'test_id'), 'executable:fields')
                require(nonempty(executable['path']), 'executable:path')
                path = Path(executable['path'])
                require(not path.is_absolute() and '..' not in path.parts
                        and path.parts[:2] == ('tests', 'e2e') and path.suffix in ('.pm', '.py'),
                        'executable:path')
                resolved = (root / path).resolve()
                require(resolved.is_relative_to((root / 'tests/e2e').resolve())
                        and resolved.is_file(), 'executable:missing-or-escaping')
                require(nonempty(executable['test_id']), 'executable:test-id')
                identity = (str(path), executable['test_id'])
                require(identity not in test_ids, 'executable:duplicate-test-id')
                test_ids.add(identity)
        # Every declared value and interacting combination must have a case,
        # including pending cases; selection must never shrink the matrix.
        for key, values in dimensions.items():
            require({variant['parameters'][key] for variant in variants} == set(values),
                    'matrix:missing-value')
        for group in groups:
            expected = set(itertools.product(*(dimensions[key] for key in group)))
            actual = {tuple(variant['parameters'][key] for key in group) for variant in variants}
            require(actual == expected, 'matrix:missing-combination')


def resolve_selection(document, scenario=None, *, require_runnable=False, root=ROOT):
    """A family expands all variants; an explicit case remains a partial result."""
    validate_inventory(document, root=root)
    require(scenario is None or nonempty(scenario), 'selection:empty')
    selected = []
    for family in document['scenarios']:
        for variant in family['variants']:
            cid = family['id'] + '/' + variant['id']
            if scenario is None or scenario in (family['id'], cid):
                selected.append({'case_id': cid, 'scenario_id': family['id'],
                                 'category': family['category'], 'owner': variant['owner'],
                                 'environment': family['environment'],
                                 'preconditions': family['preconditions'],
                                 'parameters': variant['parameters'], 'status': variant['status'],
                                 'pending_reason': variant['pending_reason'],
                                 'executable': variant['executable'],
                                 'duration_seconds': family['duration_seconds'],
                                 'requirements': family['requirements'],
                                 'requirement_gap': family['requirement_gap'],
                                 'phases': family['phases'], 'interventions': family['interventions'],
                                 'assertions': family['assertions'],
                                 'expected_evidence': family['expected_evidence']})
    require(bool(selected), 'selection:unknown')
    pending = [case['case_id'] for case in selected if case['status'] == 'pending']
    require(not require_runnable or not pending, 'selection:pending')
    return {'schema_version': 1, 'scope': 'full' if scenario is None else 'partial',
            'selector': scenario, 'vm_required_for_execution': True,
            'pending_cases': pending, 'cases': selected,
            'evidence_contract': document['evidence_contract']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', help='exact E2E-NNN family or E2E-NNN/variant')
    parser.add_argument('--require-runnable', action='store_true',
                        help='refuse pending cases; this command still never executes tests')
    args = parser.parse_args(argv)
    try:
        document, digest = read_json(INVENTORY)
        selection = resolve_selection(document, args.scenario, require_runnable=args.require_runnable)
        selection['inventory_sha256'] = digest
        selection['mode'] = 'list-only'
        print(json.dumps(selection, indent=2))
    except InventoryError as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
