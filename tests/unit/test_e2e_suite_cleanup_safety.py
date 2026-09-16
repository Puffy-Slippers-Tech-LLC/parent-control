"""Suite transitions with real ownership locks and mocked libvirt only."""

import fcntl
import os
from contextlib import nullcontext
from unittest.mock import Mock

import pytest

import graphical_lease
import suite_lease
import system_runner as system
from tests.support.vm_baseline import rig
from tests.support.vm_runner import lease_rig


@pytest.fixture
def suite(lease_rig):
    original, current = lease_rig
    lease = suite_lease.SuiteLease(original.source, original.commands, Mock(wraps=original.inspect),
        directory=original.directory, anchor=original.capture.anchor,
        graphics_type='vnc', ledger=system.RunLedger())
    lease.source.api.VIR_DOMAIN_SNAPSHOT_REVERT_FORCE = 4
    try:
        yield lease, current
    finally:
        if lease.fd is not None:
            # Host-safe fixture: do not mask a failed test with another audit.
            system.Lease.release(lease)


def run_case(lease):
    lease.ledger = system.RunLedger()
    with lease:
        lease.prepare()
        adapter = graphical_lease.Adapter(lease)
        adapter.request('off', adapter.run)
        adapter.request('on', adapter.run)
        adapter.request('off', adapter.run)
        assert adapter.request('status', adapter.run) == 'off'
    assert lease.attempt_released and lease.fd is not None
    assert lease.state['phase'] == 'complete'


def test_three_cases_restore_once_per_boundary_and_audit_only_at_suite_ends(suite):
    lease, _ = suite
    shutdowns = lease.source.shutdown_calls
    for _ in range(3):
        run_case(lease)
        assert lease.capture.verification_totals['calls'] == 1
        assert lease.inspect.call_count == 1
        # The shared lock remains exclusive even while a case is reported.
        other = os.open(lease.capture.lock_path, os.O_RDWR)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(other)
    calls = lease.source.domain.revertToSnapshot.call_args_list
    assert [call.args[1] for call in calls] == [0, 4, 4, 4]
    assert lease.source.shutdown_calls == shutdowns + 1  # Initial preflight only.
    lease.source.domain.destroyFlags.assert_not_called()
    lease.audit()
    assert lease.fd is None
    assert lease.capture.verification_totals['calls'] == 2
    assert lease.inspect.call_count == 2
    assert lease.source.domain.revertToSnapshot.call_count == 4


def test_checkpoint_provenance_does_not_hash_backings_or_launch_qemu_img(suite, monkeypatch):
    lease, _ = suite
    with lease:
        lease.prepare()
        with monkeypatch.context() as patch:
            info = Mock(side_effect=AssertionError('unexpected qemu-img'))
            audit = Mock(side_effect=AssertionError('unexpected full audit'))
            patch.setattr(lease.commands, 'info', info)
            patch.setattr(lease.capture, 'verify_snapshot', audit)
            for _ in range(3):
                assert lease.verify_baseline() == lease.capture.state['proof']
    lease.audit()


@pytest.mark.parametrize('fault', ['instance', 'tag', 'snapshot', 'lock', 'disk'])
def test_changed_ownership_refuses_force_restore(suite, fault):
    lease, current = suite
    with pytest.raises(RuntimeError) if fault == 'lock' else nullcontext(), lease:
        lease.prepare()
        lease.start()
        saved = dict(current)
        metadata = lease.source.baseline_xml
        disk = lease.source.layout['disk']
        if fault == 'instance':
            current['id'] += 1
        elif fault == 'tag':
            current['xml'] = current['xml'].replace(lease.state['run'], 'b' * 32)
        elif fault == 'snapshot':
            lease.source.baseline_xml += ' '
        elif fault == 'lock':
            fcntl.flock(lease.fd, fcntl.LOCK_UN)
        else:
            lease.source.layout['disk'] += '-replacement'
        before = lease.source.domain.revertToSnapshot.call_count
        try:
            with pytest.raises(RuntimeError):
                lease.stop()
            assert lease.source.domain.revertToSnapshot.call_count == before
        finally:
            current.update(saved)
            lease.source.baseline_xml = metadata
            lease.source.layout['disk'] = disk
    if fault != 'lock':
        lease.audit()
    else:
        with pytest.raises(RuntimeError, match='backing-owner-changed'):
            system.Lease.release(lease)
        assert lease.fd is None


def test_failed_case_is_restored_but_cannot_start_another_case(suite):
    lease, _ = suite
    with pytest.raises(ValueError, match='case failed'):
        with lease:
            lease.prepare()
            lease.start()
            raise ValueError('case failed')
    assert lease.state['phase'] == 'complete'
    before = lease.source.domain.create.call_count
    with pytest.raises(RuntimeError, match='previous-case-incomplete'):
        lease.__enter__()
    assert lease.source.domain.create.call_count == before
    lease.audit()
    assert lease.fd is None


@pytest.mark.parametrize('worker_stops', [False, True])
def test_restore_failure_is_not_retried_by_cleanup_or_final_audit(suite, worker_stops):
    lease, _ = suite
    with pytest.raises(RuntimeError, match='restore failed'):
        with lease:
            lease.prepare()
            lease.start()
            lease.source.domain.revertToSnapshot.side_effect = RuntimeError('restore failed')
            if worker_stops:
                lease.stop()
    before = lease.source.domain.revertToSnapshot.call_count
    assert before == 2  # Initial baseline and exactly one failed final revert.
    with pytest.raises(RuntimeError, match='cleanup-incomplete'):
        lease.audit()
    assert lease.source.domain.revertToSnapshot.call_count == before
    assert lease.fd is None


@pytest.mark.parametrize('fault', ['backing', 'guest', 'state'])
def test_final_audit_refuses_mutation_and_releases_lock(suite, fault):
    lease, _ = suite
    run_case(lease)
    if fault == 'backing':
        lease.capture.anchor.write_bytes(b'changed backing bytes')
    elif fault == 'guest':
        lease.inspect.return_value = {'changed': True}
    else:
        lease.capture.read_state = Mock(return_value={'changed': True})
    with pytest.raises(RuntimeError):
        lease.audit()
    assert lease.fd is None


def test_source_validation_runs_after_audit_before_release_and_failure_is_terminal(suite):
    lease, _ = suite
    run_case(lease)
    def validate():
        assert lease.fd is not None
        assert lease.capture.verification_totals['calls'] == 2
        assert lease.verify_baseline() == lease.capture.state['proof']
        raise ValueError('source changed during audit')
    with pytest.raises(ValueError, match='source changed'):
        lease.audit(validate=validate)
    assert lease.fd is None


@pytest.mark.parametrize('failure', [None, 'audit', 'host', 'close'])
def test_suite_closes_connection_even_after_audit_or_host_failure(monkeypatch, failure):
    suite = suite_lease.Suite(Mock())
    suite.source = Mock()
    suite.lease = Mock()
    suite.host_before = 'original'
    fingerprint = Mock(return_value='changed' if failure == 'host' else 'original')
    monkeypatch.setattr(system, 'host_fingerprint', fingerprint)
    if failure == 'audit':
        suite.lease.audit.side_effect = RuntimeError('audit failed')
    elif failure == 'close':
        suite.source.close.side_effect = RuntimeError('close failed')
    with pytest.raises(RuntimeError) if failure else nullcontext():
        suite.close()
    suite.lease.audit.assert_called_once()
    suite.source.close.assert_called_once()
