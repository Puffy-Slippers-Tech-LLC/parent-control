"""Provisioning and recorder credential bridge with real private evidence storage."""

import base64
import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

from test_e2e_evidence import attempt
from test_e2e_fixture_credentials_cleanup_safety import attempt as credential_attempt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/e2e'))
import e2e_worker
from private_artifacts import PrivateCollector, EvidenceError
from recording import ScenarioRecorder
sys.path.pop(0)


@pytest.mark.parametrize('serial', [False, True])
def test_same_provisioned_credentials_and_serial_transport_reach_worker(
        attempt, credential_attempt, tmp_path, monkeypatch, serial):
    credential_attempt.run()
    credentials = credential_attempt.fixture
    secrets = credentials.variables.registered_secrets
    contract = attempt[0]
    worker = Mock(return_value={'outcome': 'passed'})
    monkeypatch.setattr(e2e_worker, 'run_distribution', worker)
    with PrivateCollector(run_id=contract.run_id, secrets=secrets, parent=tmp_path) as collector:
        recorder = ScenarioRecorder(contract, collector)
        recorder.begin_case('E2E-001/gdm-observation')
        observer, validate, ledger = Mock(), Mock(), Mock()
        verified = credential_attempt.verified
        result = recorder.run_worker(verified, tmp_path, credential_attempt.lease, ledger,
            observe=observer, validate=validate, credentials=credentials, serial=serial, timeout=120)
        assert result == {'outcome': 'passed'}
        worker.assert_called_once_with(tmp_path, credential_attempt.lease, ledger,
            expected_inputs=verified.source_files, observe=observer, validate=validate,
            timeout=120, on_failure=recorder.failure, credentials=credentials, serial=serial)
        assert recorder.records[0]['steps'] == [] and recorder.records[0]['assertions'] == []
        for value in (secrets[0].encode(), base64.b64encode(secrets[0].encode())):
            with pytest.raises(EvidenceError, match='secret-detected'):
                collector.add('credential-leak', 'backend', value, reviewed=True)
        collector.verify([])
        assert secrets[0] not in ''.join(path.read_text() for path in collector.path.iterdir())


@pytest.mark.parametrize('fault,code', [
    ('not-provisioned', 'provisioning-required'),
    ('foreign-credentials', 'provisioning-required'),
    ('released', 'provisioning-required'),
    ('running', 'provisioning-required'),
    ('unregistered', 'unregistered-secret'),
    ('wrong-type', 'fixture-credentials'),
    ('missing-credentials', 'serial-credentials'),
    ('invalid-serial', 'serial-credentials'),
    ('closed-collector', 'collector-closed'),
])
def test_invalid_credentials_never_start_worker_and_latch_fixed_failure(
        attempt, credential_attempt, tmp_path, monkeypatch, fault, code):
    if fault != 'not-provisioned':
        credential_attempt.run()
    credentials = credential_attempt.fixture
    secrets = credentials.variables.registered_secrets
    verified = credential_attempt.verified
    lease = credential_attempt.lease
    serial = True
    registered = secrets
    if fault == 'foreign-credentials':
        lease = Mock(fd=42, state={'phase': 'isolated', 'domain_id': None})
        verified.lease = lease
    elif fault == 'released': lease.fd = None
    elif fault == 'running': lease.state['domain_id'] = 17
    elif fault == 'unregistered': registered = []
    elif fault == 'wrong-type': credentials = Mock()
    elif fault == 'missing-credentials': credentials = None
    elif fault == 'invalid-serial': serial = 'yes'
    worker = Mock()
    monkeypatch.setattr(e2e_worker, 'run_distribution', worker)
    with PrivateCollector(run_id=attempt[0].run_id, secrets=registered, parent=tmp_path) as collector:
        recorder = ScenarioRecorder(attempt[0], collector)
        recorder.begin_case('E2E-001/gdm-observation')
        if fault == 'closed-collector': collector.close()
        with pytest.raises(EvidenceError, match=code):
            recorder.run_worker(verified, tmp_path, lease, Mock(), observe=Mock(), validate=Mock(),
                                credentials=credentials, serial=serial)
        worker.assert_not_called()
        record = recorder.records[0]
        assert record['first_failure']['code'] == 'worker-execution-failed'
        assert record['outcomes']['infrastructure'] == 'failed'
        assert not record['steps'] and not record['assertions']
        assert secrets[0] not in json.dumps(record)


def test_collector_registry_is_frozen_and_does_not_accept_an_encoded_value_as_registration(tmp_path):
    secret = 'a-secret-with-a-distinct-encoded-value'
    values = [base64.b64encode(secret.encode()).decode()]
    with PrivateCollector(run_id='frozen-registry', secrets=values, parent=tmp_path) as collector:
        collector.save_report('earlier', {'outcome': 'not-run'})
        values.append(secret)
        with pytest.raises(EvidenceError, match='unregistered-secret'):
            collector.require_secrets([secret])
        collector.require_secrets(values[:1])
        collector.verify([])
