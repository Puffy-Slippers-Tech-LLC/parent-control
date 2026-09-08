"""Real qualification callback/recorder; worker and guest operations substituted."""

import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/e2e'))
import controller_qualification as qualification
from evidence import EvidenceContract, CLEANUP_FIELDS, INPUT_FIELDS
import inventory
from private_artifacts import PrivateCollector, EvidenceError
from recording import ScenarioRecorder
sys.path.pop(0)


@pytest.fixture
def harness(tmp_path, monkeypatch):
    inputs = {key: hashlib.sha256(key.encode()).hexdigest() for key in INPUT_FIELDS}
    inputs.update(inventory_sha256=hashlib.sha256(inventory.INVENTORY.read_bytes()).hexdigest(),
                  environment_id='ubuntu26-04-pinned', package_sha256=None)
    contract = EvidenceContract(inventory_path=inventory.INVENTORY, root=ROOT,
        selector='E2E-034', run_id='qualification-test', inputs=inputs)
    collector = PrivateCollector(run_id='qualification-test', secrets=['private-canary'], parent=tmp_path)
    recorder = ScenarioRecorder(contract, collector)
    recorder.begin_case('E2E-034/serial-controller')
    context = SimpleNamespace(lease=Mock(), verified=Mock(inputs=inputs), directory=tmp_path,
        guestfs=Mock(), commands=Mock(), host_key='private-canary',
        credentials=Mock(provision=Mock(return_value={'verified': True})))
    monkeypatch.setattr(qualification, 'AssetTransfer', Mock(return_value=Mock(
        provision=Mock(return_value={'files': 3, 'sha256': 'a' * 64}))))
    monkeypatch.setattr(qualification, 'provision_getty', Mock())
    monkeypatch.setattr(qualification, 'module_result', Mock())
    observer = Mock(read=Mock(return_value={'boot_sha256': 'b' * 64}))
    settings = SimpleNamespace(failure=None, omit=None)
    class Smoke:
        def __init__(self, *args, progress, **kwargs):
            self.vm, self.steps = observer, []
            self.progress = progress
        def step(self):
            for stage in qualification.SERIAL_STAGES:
                if stage == settings.omit:
                    break
                self.progress(stage, None)
                if stage == settings.failure:
                    raise RuntimeError('private-canary')
                item = {'stage': stage, 'command_marker_verified': True,
                        'unexpected_user_session': False}
                self.steps.append(item)
                self.progress(stage, item)
    monkeypatch.setattr(qualification, 'Smoke', Smoke)
    worker = {'outcome': 'passed', 'worker_stopped': True,
              'callback_closed': True, 'shutdown_verified': True}
    def run_worker(*, observe, validate, **kwargs):
        assert kwargs == {'authenticate': True, 'serial': True, 'timeout': 600}
        observe()
        validate()
        return worker
    context.run_worker = Mock(side_effect=run_worker)
    yield SimpleNamespace(recorder=recorder, collector=collector, context=context,
        observer=observer, settings=settings, worker=worker, contract=contract)
    collector.close()


def finish(harness):
    with harness.recorder.step('cleanup'):
        pass
    harness.recorder.end_case({key: 'complete' if key == 'lease_phase' else True
                              for key in CLEANUP_FIELDS})


def test_actual_callback_evidence_passes_exact_contract(harness):
    qualification.execute(harness.recorder, harness.context)
    finish(harness)
    result = harness.contract.validate(harness.recorder.records, harness.collector)
    assert result['case_ids'] == ['E2E-034/serial-controller']
    record = harness.recorder.records[0]
    assert [s['step_id'] for s in record['steps']] == [
        'setup', 'start', *qualification.SERIAL_STAGES[1:], 'end', 'cleanup']
    assert {s['boot_id'] for s in record['steps'][1:-1]} == {'boot-1'}
    assert all(s['session_ids'] == [] for s in record['steps'])
    assert 'private-canary' not in json.dumps(record)
    harness.context.lease.finish.assert_not_called()
    harness.context.lease.release.assert_not_called()


@pytest.mark.parametrize('boundary', ['boot-change', 'boot-read', 'missing-stage',
                                      'observation', 'shutdown', 'collection', 'provision'])
def test_incomplete_or_changed_attempt_cannot_create_passing_evidence(harness, boundary):
    if boundary == 'boot-change':
        harness.observer.read.side_effect = [{'boot_sha256': 'b' * 64}, {'boot_sha256': 'c' * 64}]
    elif boundary == 'boot-read':
        harness.observer.read.side_effect = KeyboardInterrupt('private-canary')
    elif boundary == 'missing-stage':
        harness.settings.omit = 'serial-command'
    elif boundary == 'observation':
        harness.settings.failure = 'serial-password'
    elif boundary == 'shutdown':
        harness.worker['shutdown_verified'] = False
    elif boundary == 'collection':
        harness.collector.add = Mock(side_effect=OSError('private-canary'))
    else:
        harness.context.credentials.provision.side_effect = RuntimeError('private-canary')
    with pytest.raises((Exception, KeyboardInterrupt)):
        qualification.execute(harness.recorder, harness.context)
    finish(harness)
    with pytest.raises(EvidenceError):
        harness.contract.validate(harness.recorder.records, harness.collector)
    assert harness.recorder.records[0]['failures']
    assert 'private-canary' not in json.dumps(harness.recorder.records)
    harness.context.lease.finish.assert_not_called()
    harness.context.lease.release.assert_not_called()
