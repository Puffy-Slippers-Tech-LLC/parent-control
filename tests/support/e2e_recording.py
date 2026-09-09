"""Compose the real recorder with synthetic steps and explicit cleanup results."""

import copy
import json
from types import SimpleNamespace

import pytest
import recording
from private_artifacts import PrivateCollector

@pytest.fixture
def session(attempt, tmp_path):
    contract, _, payload, _, _ = attempt
    with PrivateCollector(run_id=contract.run_id, secrets=['private-canary'], parent=tmp_path) as collector:
        recorder = recording.ScenarioRecorder(contract, collector)
        verified = SimpleNamespace(lease=SimpleNamespace(fd=42, state={'phase': 'complete'}),
            validate=lambda contract, records, collector: contract.validate(records, collector))
        yield SimpleNamespace(recorder=recorder, contract=contract, collector=collector,
                              payload=payload, verified=verified)


def reports(session):
    return [json.loads(p.read_text()) for p in sorted(session.collector.path.glob('event-*.json'))]


def execute_steps(session, *, omit=None):
    r = session.recorder
    for item in session.payload['steps']:
        if item['phase'] == 'cleanup' or item['step_id'] == omit:
            continue
        with r.step(item['step_id']):
            r.continuity(boot='private-canary-boot', sessions=['private-canary-session'])
            if item['step_id'] == 'step-3':
                for kind in r.contract.plan['cases'][0]['expected_evidence']:
                    r.artifact(kind, kind, ('reviewed ' + kind).encode(), reviewed=True)
                for assertion in session.payload['assertions']:
                    r.assertion(assertion['assertion_id'], artifact_ids=assertion['artifact_ids'])


def cleanup(session):
    with session.recorder.step('cleanup'):
        pass
    return copy.deepcopy(session.payload['cleanup'])


def complete(session):
    return session.recorder.run_case('E2E-001/gdm-observation',
        execute=lambda _: execute_steps(session), cleanup=lambda _: cleanup(session))
