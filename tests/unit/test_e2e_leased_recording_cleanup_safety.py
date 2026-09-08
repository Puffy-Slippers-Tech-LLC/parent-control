"""Real recorder/collector/evidence gate and Lease exit; no VM or process actions."""

import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from test_e2e_evidence import attempt
from test_e2e_recording_cleanup_safety import session, execute_steps, reports

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/e2e'))
from leased_recording import LeasedScenario
from private_artifacts import EvidenceError
sys.path.pop(0)
sys.path.insert(0, str(ROOT / 'tests/integration'))
import system_runner
sys.path.pop(0)


@pytest.fixture
def held(session, monkeypatch):
    events = []
    ledger = system_runner.RunLedger()
    lease = system_runner.Lease(Mock(), Mock(), Mock(), ledger=ledger, graphics_type='vnc')
    lease.fd = 42
    lease.state = {'phase': 'isolated', 'domain_id': None, 'run': 'a' * 32,
                   'domain_uuid': 'recorded-domain'}
    def finish():
        events.append('restore')
        lease.state['phase'] = 'complete'
    def release():
        events.append('release')
        lease.fd = None
    lease.finish = Mock(side_effect=finish)
    lease.release = Mock(side_effect=release)
    lease.guard = Mock(side_effect=lambda **_: events.append('guard'))
    monkeypatch.setattr(system_runner.Lease, '__enter__', lambda self: self)
    session.verified.lease = lease
    session.verified.recheck_contract = Mock(side_effect=lambda _: events.append('inputs'))
    def validate(contract, records, collector):
        assert lease.fd == 42 and lease.state['phase'] == 'complete'
        events.append('validate')
        return contract.validate(records, collector)
    session.verified.validate = Mock(side_effect=validate)
    def cleanup(recorder, selected):
        assert selected is lease and selected.fd == 42
        assert selected.state['phase'] == 'complete'
        events.append('preservation')
        return copy.deepcopy(session.payload['cleanup'])
    close = Mock(side_effect=cleanup)
    bridge = LeasedScenario(session.recorder, session.verified, cleanup=close)
    return SimpleNamespace(session=session, lease=lease, events=events, bridge=bridge,
                           cleanup=close, ledger=ledger)


def execute(held):
    with held.lease:
        held.bridge.execute(lambda _: execute_steps(held.session))


def test_real_exit_restores_once_and_accepts_ordered_evidence_before_release(held):
    with held.lease:
        held.bridge.execute(lambda _: execute_steps(held.session))
        with pytest.raises(EvidenceError, match='lease-not-released'):
            held.bridge.result()
        checkpoint = reports(held.session)[-1]
        assert checkpoint['event'] == 'step-started'
        assert checkpoint['active_step'] == 'cleanup'
        assert checkpoint['record']['steps'][-1]['outcome'] == 'not-run'
        assert not (held.session.collector.path / 'acceptance.json').exists()
    assert held.events == ['inputs', 'inputs', 'restore', 'guard', 'inputs', 'preservation',
                           'validate', 'validate', 'release']
    assert held.bridge.result()['case_ids'] == ['E2E-001/gdm-observation']
    held.lease.finish.assert_called_once()
    held.lease.release.assert_called_once()
    held.lease.guard.assert_called_once_with(off=True)
    assert reports(held.session)[-1]['record']['cleanup'] == held.session.payload['cleanup']


@pytest.mark.parametrize('interrupt', [False, True])
@pytest.mark.parametrize('broken_cleanup', [False, True])
def test_original_action_failure_survives_restoration_and_finalization_errors(
        held, interrupt, broken_cleanup):
    original = KeyboardInterrupt('private-canary') if interrupt else RuntimeError('private-canary')
    before_restore = []
    finish = held.lease.finish.side_effect
    def restore():
        before_restore.extend(reports(held.session))
        if broken_cleanup:
            raise OSError('private-canary-cleanup')
        finish()
    held.lease.finish.side_effect = restore
    def fail(recorder):
        with recorder.step('setup'):
            raise original
    with pytest.raises(type(original)) as caught:
        with held.lease:
            held.bridge.execute(fail)
    assert caught.value is original
    assert before_restore[-1]['record']['first_failure']['code'] == (
        'scenario-step-interrupted' if interrupt else 'scenario-step-failed')
    result = reports(held.session)[-1]['record']
    assert result['first_failure'] == before_restore[-1]['record']['first_failure']
    assert [step['step_id'] for step in result['steps']] == ['setup', 'cleanup']
    assert result['cleanup']['lease_phase'] == ('incomplete' if broken_cleanup else 'complete')
    assert held.lease.fd is None
    held.lease.finish.assert_called_once()
    held.lease.release.assert_called_once()
    with pytest.raises(EvidenceError, match='attempt-failed'):
        held.bridge.result()
    assert 'private-canary' not in json.dumps(reports(held.session))


@pytest.mark.parametrize('boundary', ['restore', 'off-guard', 'inputs', 'preservation',
                                    'end-report', 'acceptance-copy', 'late-validation', 'release'])
def test_no_boundary_failure_can_return_an_acceptance(held, monkeypatch, boundary):
    original = OSError('private-canary')
    if boundary == 'restore':
        held.lease.finish.side_effect = original
    elif boundary == 'off-guard':
        held.lease.guard.side_effect = original
    elif boundary == 'inputs':
        held.session.verified.recheck_contract.side_effect = [None, original]
    elif boundary == 'preservation':
        held.cleanup.side_effect = original
    elif boundary in ('end-report', 'acceptance-copy'):
        save = held.session.collector.save_report
        def broken(name, value):
            if ((boundary == 'end-report' and value.get('event') == 'case-ended')
                    or (boundary == 'acceptance-copy' and name == 'acceptance')):
                raise original
            return save(name, value)
        monkeypatch.setattr(held.session.collector, 'save_report', broken)
    elif boundary == 'late-validation':
        validate = held.session.verified.validate.side_effect
        calls = []
        def changed(*args):
            calls.append(True)
            if len(calls) == 2:
                raise original
            return validate(*args)
        held.session.verified.validate.side_effect = changed
    elif boundary == 'release':
        release = held.lease.release.side_effect
        def broken_release():
            release()
            raise original
        held.lease.release.side_effect = broken_release
    with pytest.raises(BaseException) as caught:
        execute(held)
    assert caught.value is original
    held.lease.finish.assert_called_once()
    held.lease.release.assert_called_once()
    with pytest.raises(EvidenceError, match='attempt-failed'):
        held.bridge.result()
    assert 'private-canary' not in ''.join(
        path.read_text() for path in held.session.collector.path.glob('*.json'))


@pytest.mark.parametrize('replacement', ['fd', 'run', 'domain_uuid', 'lease-object'])
def test_replaced_lease_identity_refuses_evidence_without_extra_cleanup(held, replacement):
    finish = held.lease.finish.side_effect
    def replaced():
        finish()
        if replacement == 'fd':
            held.lease.fd = 43
        elif replacement == 'lease-object':
            selected = copy.copy(held.lease)
            selected.fd = held.lease.fd
            held.bridge._finalizer(selected)
        else:
            held.lease.state[replacement] = 'replaced'
    held.lease.finish.side_effect = replaced
    with pytest.raises(EvidenceError, match='lease-identity-changed'):
        execute(held)
    held.cleanup.assert_not_called()
    held.lease.release.assert_called_once()
    assert not (held.session.collector.path / 'acceptance.json').exists()


@pytest.mark.parametrize('event', ['case-started', 'before-cleanup', 'cleanup-start'])
def test_checkpoint_failure_still_uses_the_original_lease_cleanup(held, monkeypatch, event):
    original = OSError('private-canary')
    save = held.session.collector.save_report
    def broken(name, value):
        if (value.get('event') == event or
                (event == 'cleanup-start' and value.get('event') == 'step-started'
                 and value.get('active_step') == 'cleanup')):
            raise original
        return save(name, value)
    monkeypatch.setattr(held.session.collector, 'save_report', broken)
    with pytest.raises(OSError) as caught:
        execute(held)
    assert caught.value is original
    held.lease.finish.assert_called_once()
    held.lease.release.assert_called_once()
    with pytest.raises(EvidenceError, match='attempt-failed'):
        held.bridge.result()


def test_construction_refuses_another_finalizer_without_overwriting_it(held):
    callback = held.lease.finalize
    with pytest.raises(EvidenceError, match='finalizer-already-owned'):
        LeasedScenario(held.session.recorder, held.session.verified, cleanup=Mock())
    assert held.lease.finalize is callback


def test_worker_success_without_scenario_evidence_still_fails(held):
    with pytest.raises(EvidenceError):
        with held.lease:
            held.bridge.execute(lambda _: {'outcome': 'passed'})
    held.lease.finish.assert_called_once()
    held.lease.release.assert_called_once()
    with pytest.raises(EvidenceError, match='attempt-failed'):
        held.bridge.result()


@pytest.mark.parametrize('replacement', ['fd', 'run', 'domain_uuid', 'ledger'])
def test_changed_identity_before_execution_never_reaches_scenario(held, replacement):
    if replacement == 'fd': held.lease.fd = 43
    elif replacement == 'ledger': held.lease.ledger = system_runner.RunLedger()
    else: held.lease.state[replacement] = 'replaced'
    action = Mock()
    with pytest.raises(EvidenceError, match='lease-identity-changed'):
        with held.lease:
            held.bridge.execute(action)
    action.assert_not_called()
    held.lease.finish.assert_called_once()
    held.lease.release.assert_called_once()


@pytest.mark.parametrize('fault,code', [('released', 'prepared-lease-required'),
    ('running', 'prepared-lease-required'), ('phase', 'prepared-lease-required'),
    ('ledger', 'lease-ledger-required'), ('inputs', 'source-changed')])
def test_invalid_attachment_does_not_claim_the_finalizer(held, fault, code):
    held.lease.finalize = None
    if fault == 'released': held.lease.fd = None
    elif fault == 'running': held.lease.state['domain_id'] = 17
    elif fault == 'phase': held.lease.state['phase'] = 'running'
    elif fault == 'ledger': held.lease.ledger = None
    else: held.session.verified.recheck_contract.side_effect = EvidenceError('provenance:source-changed')
    with pytest.raises(EvidenceError, match=code):
        LeasedScenario(held.session.recorder, held.session.verified, cleanup=Mock())
    assert held.lease.finalize is None
    held.lease.finish.assert_not_called()
    held.lease.release.assert_not_called()
