"""Synthetic E2E evidence contracts; these fixtures never provision a guest."""

import hashlib
import json

import pytest
import evidence
import inventory
import private_artifacts
from tests.support.paths import ROOT

SECRET = 'fixture-only-password-9!'


@pytest.fixture
def attempt(tmp_path):
    """A synthetic recorder contract with no guest credential provisioning."""
    document, _ = inventory.read_json(inventory.INVENTORY)
    document['scenarios'] = document['scenarios'][:1]
    document['scenarios'][0]['duration_seconds'] = 600
    document['scenarios'][0]['preconditions'].remove('fixture-credentials-via-secret-api')
    for relative in ('tests/requirements.json', 'docs/TestAutomation/E2E-Coverage.md'):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    executable = tmp_path / 'tests/e2e/synthetic.py'
    executable.parent.mkdir(parents=True)
    executable.write_text('raise RuntimeError("must never execute")\n')
    variant = document['scenarios'][0]['variants'][0]
    variant.update(status='ready', pending_reason=None,
                   executable={'path': 'tests/e2e/synthetic.py', 'test_id': 'synthetic-smoke'})
    path = tmp_path / 'inventory.json'
    path.write_text(json.dumps(document))
    inputs = {key: hashlib.sha256(key.encode()).hexdigest() for key in evidence.INPUT_FIELDS}
    inputs.update(inventory_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  environment_id='ubuntu26-04-pinned', package_sha256=None)
    contract = evidence.EvidenceContract(inventory_path=path, inputs=inputs,
                                         selector='E2E-001', run_id='run-one', root=tmp_path)
    case = inventory.resolve_selection(document, 'E2E-001', root=tmp_path)['cases'][0]
    with private_artifacts.PrivateCollector(run_id='run-one', secrets=[SECRET], parent=tmp_path) as collector:
        artifacts = [collector.add(kind, kind, ('reviewed ' + kind).encode(), reviewed=True)
                     for kind in case['expected_evidence']]
        assertions = []
        for kind, items in case['assertions'].items():
            for item in items:
                assertions.append({'assertion_id': item['id'], 'kind': kind,
                                   'step_id': item['step_id'], 'outcome': 'passed',
                                   'artifact_ids': [{'visible': 'screen', 'backend': 'backend',
                                                     'other_user': 'other-user'}[kind]]})
        steps = []
        for phase in inventory.PHASES:
            for step in case['phases'][phase]:
                checks = [a['assertion_id'] for a in assertions if a['step_id'] == step['id']]
                steps.append({'step_id': step['id'], 'phase': phase, 'operation': step['operation'],
                              'outcome': 'passed', 'monotonic_seconds': len(steps),
                              'boot_id': 'boot-1', 'session_ids': ['session-1'],
                              'assertion_ids': checks,
                              'artifact_ids': [a['artifact_id'] for a in artifacts] if checks else []})
        result = {'schema_version': 1, 'run_id': 'run-one', 'scenario_id': 'E2E-001',
                  'variant_id': 'gdm-observation', **inputs, 'executable': case['executable'],
                  'started_at': '2026-09-07T12:00:00Z', 'ended_at': '2026-09-07T12:00:10Z',
                  'steps': steps, 'artifacts': artifacts, 'assertions': assertions,
                  'outcomes': dict.fromkeys(inventory.OUTCOMES, 'passed'),
                  'first_failure': None, 'failures': [],
                  'cleanup': {key: 'complete' if key == 'lease_phase' else True
                              for key in evidence.CLEANUP_FIELDS}}
        yield contract, collector, result, path, inputs
