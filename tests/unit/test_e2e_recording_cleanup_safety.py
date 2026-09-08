"""Host-only real recording/collector checks; no guest or host process cleanup."""

import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from test_e2e_evidence import attempt
from test_e2e_provenance import source, lease

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/e2e'))
import recording
import provenance
import e2e_worker
from private_artifacts import PrivateCollector, EvidenceError
sys.path.pop(0)


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


def test_actual_callbacks_build_gate_accepted_records_and_private_checkpoints(session):
    result = complete(session)
    assert session.recorder.validate(session.verified)['outcome'] == 'passed'
    events = reports(session)
    assert events[0]['event'] == 'case-started'
    assert events[-1]['event'] == 'case-ended'
    start = next(e for e in events if e['event'] == 'step-started')
    assert start['record']['steps'][0]['outcome'] == 'not-run'
    assert events[-2]['record']['cleanup']['lease_phase'] is None
    assert all(s['outcome'] == 'passed' for s in result['steps'])
    assert 'private-canary' not in ''.join(p.read_text() for p in session.collector.path.iterdir())
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in session.collector.path.iterdir())
    result['steps'].clear()
    session.contract.plan['cases'].clear()
    assert session.recorder.records[0]['steps'] and session.contract.plan['cases']


@pytest.mark.parametrize('interrupt', [False, True])
@pytest.mark.parametrize('cleanup_fails', [False, True])
def test_original_failure_is_durable_before_cleanup_and_survives_combined_errors(
        session, interrupt, cleanup_fails):
    original = KeyboardInterrupt('private-canary') if interrupt else RuntimeError('private-canary')
    observed = []
    def execute(r):
        with r.step('setup'):
            raise original
    def close(r):
        observed.extend(reports(session))
        with r.step('cleanup'):
            if cleanup_fails:
                raise RuntimeError('private-canary-cleanup')
        return session.payload['cleanup']
    with pytest.raises(type(original)) as caught:
        session.recorder.run_case('E2E-001/gdm-observation', execute=execute, cleanup=close)
    assert caught.value is original
    first = observed[-1]['record']['first_failure']
    result = session.recorder.records[0]
    assert observed[-1]['event'] == 'before-cleanup'
    assert result['first_failure'] == first
    assert result['steps'][0]['outcome'] == ('interrupted' if interrupt else 'failed')
    assert [s['step_id'] for s in result['steps']] == ['setup', 'cleanup']
    assert result['outcomes']['cleanup'] == ('failed' if cleanup_fails else 'passed')
    with pytest.raises(EvidenceError):
        session.recorder.validate(session.verified)
    assert 'private-canary' not in json.dumps(reports(session))


@pytest.mark.parametrize('boundary', ['case-started', 'step-started', 'before-cleanup', 'case-ended'])
def test_report_failure_still_runs_cleanup_and_cannot_be_cleared(session, monkeypatch, boundary):
    save = session.collector.save_report
    original = OSError('private-canary')
    def broken(name, value):
        if value.get('event') == boundary:
            raise original
        return save(name, value)
    monkeypatch.setattr(session.collector, 'save_report', broken)
    close = Mock(return_value=session.payload['cleanup'])
    with pytest.raises(OSError) as caught:
        session.recorder.run_case('E2E-001/gdm-observation',
            execute=lambda _: execute_steps(session), cleanup=close)
    assert caught.value is original
    close.assert_called_once()
    assert session.recorder.records[0]['outcomes']['collection'] == 'failed'


@pytest.mark.parametrize('invalid', ['step-2', 'setup'])
def test_suppressed_duplicate_or_reordered_action_still_prevents_acceptance(session, invalid):
    r = session.recorder
    r.begin_case('E2E-001/gdm-observation')
    with r.step('setup'):
        pass
    with pytest.raises(EvidenceError, match='step-order'):
        with r.step(invalid):
            pytest.fail('An out-of-order action must never execute')
    assert r.records[0]['first_failure']['code'] == 'scenario-step-order'


def test_worker_exit_zero_without_actions_or_assertions_is_never_a_scenario_pass(session):
    session.recorder.run_case('E2E-001/gdm-observation', execute=lambda _: {'outcome': 'passed'},
                             cleanup=lambda _: session.payload['cleanup'])
    with pytest.raises(EvidenceError):
        session.recorder.validate(session.verified)
    assert session.recorder.records[0]['steps'] == []
    assert session.recorder.records[0]['first_failure']['code'] == 'scenario-steps-missing'


def test_missing_assertions_are_reported_when_the_real_step_finishes(session):
    r = session.recorder
    def execute(_):
        for item in session.payload['steps']:
            if item['phase'] == 'cleanup':
                break
            with r.step(item['step_id']):
                r.continuity(boot='boot-private')
    with pytest.raises(EvidenceError, match='missing-assertions'):
        r.run_case('E2E-001/gdm-observation', execute=execute, cleanup=lambda _: cleanup(session))
    assert r.records[0]['steps'][-2]['step_id'] == 'step-3'
    assert r.records[0]['steps'][-2]['outcome'] == 'failed'


@pytest.mark.parametrize('change', ['release', 'incomplete', 'input', 'report'])
def test_final_gate_failure_is_retained_with_original_failure_and_no_acceptance(session, change, monkeypatch):
    complete(session)
    if change == 'release':
        session.verified.lease.fd = None
    elif change == 'incomplete':
        session.verified.lease.state['phase'] = 'running'
    elif change == 'input':
        session.verified.validate = Mock(side_effect=EvidenceError('provenance:source-changed'))
    else:
        (session.collector.path / 'event-000001.json').write_text('tampered')
    with pytest.raises(EvidenceError):
        session.recorder.validate(session.verified)
    report = json.loads((session.collector.path / 'acceptance-rejected.json').read_text())
    assert report['outcome'] == 'failed'
    assert report['records'][0]['first_failure'] is not None
    assert not (session.collector.path / 'acceptance.json').exists()


def test_reboot_aliases_do_not_confuse_reused_session_identifiers(session):
    r = session.recorder
    r.begin_case('E2E-001/gdm-observation')
    for name, boot in [('setup', 'first-private-boot'), ('start', 'second-private-boot')]:
        with r.step(name):
            r.continuity(boot=boot, sessions=['same-private-session'])
    steps = r.records[0]['steps']
    assert [s['boot_id'] for s in steps] == ['boot-1', 'boot-2']
    assert [s['session_ids'] for s in steps] == [['session-1'], ['session-2']]


def test_real_provenance_change_after_execution_is_persisted(source, lease, session):
    document = json.loads((source / 'tests/e2e/scenarios.json').read_text())
    document['scenarios'] = document['scenarios'][:1]
    variant = document['scenarios'][0]['variants'][0]
    variant.update(status='ready', pending_reason=None,
                   executable={'path': 'tests/e2e/runner.py', 'test_id': 'synthetic-smoke'})
    (source / 'tests/e2e/scenarios.json').write_text(json.dumps(document))
    lease.state['phase'] = 'complete'
    verified = provenance.VerifiedInputs(root=source, lease=lease)
    contract = verified.contract(run_id='run-one', selector='E2E-001')
    session.recorder = recording.ScenarioRecorder(contract, session.collector)
    complete(session)
    (source / 'local-change.py').write_text('changed after execution')
    with pytest.raises(EvidenceError, match='source-changed'):
        session.recorder.validate(verified)
    report = json.loads((session.collector.path / 'acceptance-rejected.json').read_text())
    assert report['code'] == 'provenance:source-changed'
    assert report['records'][0]['first_failure']['code'] == 'input-preservation-failed'


@pytest.mark.parametrize('changed', [False, True])
def test_worker_bridge_rechecks_inputs_before_start_and_does_not_invent_steps(session, monkeypatch, changed):
    import e2e_worker
    verified = session.verified
    verified.source_files = {'distribution-input': 'digest'}
    verified.recheck_contract = Mock(side_effect=EvidenceError('provenance:source-changed') if changed else None)
    worker = Mock(return_value={'outcome': 'passed'})
    monkeypatch.setattr(e2e_worker, 'run_distribution', worker)
    r = session.recorder
    r.begin_case('E2E-001/gdm-observation')
    def run():
        return r.run_worker(verified, Path('/tmp'), verified.lease, Mock(),
                            observe=Mock(), validate=Mock())
    if changed:
        with pytest.raises(EvidenceError, match='source-changed'):
            run()
        worker.assert_not_called()
        assert r.records[0]['first_failure']['code'] == 'input-preservation-failed'
    else:
        assert run()['outcome'] == 'passed'
        assert r.records[0]['steps'] == [] and r.records[0]['assertions'] == []
        assert worker.call_args.kwargs['expected_inputs'] == verified.source_files
        worker.call_args.kwargs['on_failure']('infrastructure', 'worker-interrupted')
        assert reports(session)[-1]['record']['first_failure']['code'] == 'worker-interrupted'
    verified.recheck_contract.assert_called_once_with(session.contract)


def test_report_failure_during_rejection_preserves_the_gate_exception(session, monkeypatch):
    complete(session)
    original = EvidenceError('provenance:source-changed')
    session.verified.validate = Mock(side_effect=original)
    monkeypatch.setattr(session.collector, 'save_report', Mock(side_effect=OSError('private-canary')))
    with pytest.raises(EvidenceError) as caught:
        session.recorder.validate(session.verified)
    assert caught.value is original
    assert reports(session)[-1]['event'] == 'case-ended'


def test_late_input_change_refuses_even_after_initial_gate_pass(session):
    complete(session)
    session.verified.validate = Mock(side_effect=[{'outcome': 'passed'},
                                                  EvidenceError('provenance:source-changed')])
    with pytest.raises(EvidenceError, match='source-changed'):
        session.recorder.validate(session.verified)
    rejected = json.loads((session.collector.path / 'acceptance-rejected.json').read_text())
    assert rejected['outcome'] == 'failed'
    assert rejected['records'][0]['first_failure']['code'] == 'input-preservation-failed'


def test_worker_guard_refusal_is_recorded_even_before_its_failure_hook(session, monkeypatch):
    import e2e_worker
    r = session.recorder
    verified = session.verified
    verified.source_files = {}
    verified.recheck_contract = Mock()
    original = RuntimeError('private-canary')
    monkeypatch.setattr(e2e_worker, 'run_distribution', Mock(side_effect=original))
    r.begin_case('E2E-001/gdm-observation')
    with pytest.raises(RuntimeError) as caught:
        r.run_worker(verified, Path('/tmp'), verified.lease, Mock(), observe=Mock(), validate=Mock())
    assert caught.value is original
    assert reports(session)[-1]['record']['first_failure']['code'] == 'worker-execution-failed'


def test_expired_action_deadline_does_not_prevent_outer_cleanup(session, monkeypatch):
    r = session.recorder
    now = [0.0]
    monkeypatch.setattr(recording.time, 'monotonic', lambda: now[0])
    closed = []
    def execute(_):
        with r.step('setup'):
            now[0] = 601.0
    def close(_):
        with r.step('cleanup'):
            closed.append(True)
        return session.payload['cleanup']
    with pytest.raises(EvidenceError, match='deadline'):
        r.run_case('E2E-001/gdm-observation', execute=execute, cleanup=close)
    assert closed == [True]
    assert r.records[0]['outcomes']['cleanup'] == 'passed'


def test_failed_assertion_and_secret_artifact_errors_remain_latched(session):
    r = session.recorder
    def execute(_):
        for item in session.payload['steps']:
            if item['phase'] == 'cleanup':
                break
            with r.step(item['step_id']):
                r.continuity(boot='private-boot')
                if item['step_id'] == 'step-3':
                    with pytest.raises(EvidenceError, match='secret-detected'):
                        r.artifact('unsafe-screen', 'screen', b'private-canary', reviewed=True)
                    for kind in r.contract.plan['cases'][0]['expected_evidence']:
                        r.artifact(kind, kind, ('reviewed ' + kind).encode(), reviewed=True)
                    for a in session.payload['assertions']:
                        r.assertion(a['assertion_id'], artifact_ids=a['artifact_ids'], outcome='failed')
    with pytest.raises(EvidenceError, match='step-failed'):
        r.run_case('E2E-001/gdm-observation', execute=execute, cleanup=lambda _: cleanup(session))
    record = r.records[0]
    assert record['first_failure']['code'] == 'scenario-artifact-failed'
    assert record['outcomes']['collection'] == 'failed'
    assert record['outcomes']['infrastructure'] == 'failed'
    assert record['outcomes']['product'] == 'not-run'
    assert 'private-canary' not in json.dumps(reports(session))


def test_invalid_cleanup_report_is_retained_without_exporting_its_values(session):
    with pytest.raises(EvidenceError, match='cleanup-fields'):
        session.recorder.run_case('E2E-001/gdm-observation', execute=lambda _: execute_steps(session),
                                 cleanup=lambda _: {'private-canary': 'private-canary'})
    final = reports(session)[-1]
    assert final['record']['first_failure']['code'] == 'scenario-finalization-failed'
    assert final['record']['outcomes']['cleanup'] == 'failed'
    assert 'private-canary' not in json.dumps(final)
