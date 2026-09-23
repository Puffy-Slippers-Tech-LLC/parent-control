"""Metadata-only VM lifecycles with real ownership locks and simulated disks."""

import fcntl
import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

import vm_ownership
import prepare_baseline as baseline
import provenance
from vt6_authentication import Authentication
from tests.support.e2e_provenance import source
from tests.support.vm_baseline import rig
from tests.support.vm_runner import lease_rig


@pytest.fixture(autouse=True)
def forbid_image_scans(rig, monkeypatch):
    original = baseline.digest

    def digest(path, **kwargs):
        assert Path(path) not in (rig.top, rig.anchor), 'VM image hash attempted'
        return original(path, **kwargs)

    monkeypatch.setattr(baseline, 'digest', digest)
    monkeypatch.setattr(rig.commands, 'check',
                        Mock(side_effect=AssertionError('image structural scan attempted')))


def test_every_lifecycle_boundary_uses_metadata_only(lease_rig, capsys):
    lease, current = lease_rig
    # Contents deliberately differ from any previously accepted byte digest.
    lease.capture.anchor.write_bytes(b'x' * lease.capture.anchor.stat().st_size)
    with lease:
        lease.prepare()
        lease.start()
        for boundary in ('acquisition', 'checkpoint', 'restoration', 'recovery'):
            assert lease.capture.verify_snapshot(boundary=boundary) == lease.capture.state['proof']
        lease.stop()
        assert lease.capture.verify_snapshot() == lease.capture.state['proof']
    assert lease.state['phase'] == 'complete' and lease.fd is None
    assert lease.source.off and current['id'] == -1
    assert lease.source.domain.revertToSnapshot.call_count == 2
    assert lease.capture.verification_totals['bytes_read'] == 0
    assert lease.capture.verification_totals['policy'] == 'metadata-only'
    events = [json.loads(line.removeprefix('baseline:verification '))
              for line in capsys.readouterr().err.splitlines()
              if line.startswith('baseline:verification ')]
    assert events and all(event['mode'] == 'metadata-only' and event['bytes_read'] == 0
                          for event in events)
    assert events[0]['boundary'] == 'acquisition' and events[-1]['boundary'] == 'restoration'


def test_interrupted_metadata_check_releases_lock_before_vm_mutation(lease_rig, monkeypatch):
    lease, _ = lease_rig
    monkeypatch.setattr(vm_ownership.VMOwnership, 'check', Mock(side_effect=KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        lease.__enter__()
    assert lease.fd is None
    lease.source.domain.create.assert_not_called()
    lease.source.domain.revertToSnapshot.assert_not_called()


def test_closed_guard_cannot_be_reused(lease_rig):
    lease, _ = lease_rig
    with lease:
        guard = lease.capture.vm_ownership
    assert guard.closed
    with pytest.raises(baseline.CaptureError, match='backing-owner-changed'):
        guard.check()


def test_file_changes_refuse_and_stay_failed_after_identity_is_restored(lease_rig):
    lease, _ = lease_rig
    with pytest.raises(baseline.CaptureError), lease:
        lease.prepare()
        path = lease.capture.anchor
        saved = path.with_suffix('.saved')
        path.rename(saved)
        path.write_bytes(b'replacement')
        with pytest.raises(baseline.CaptureError):
            lease.capture.verify_snapshot()
        path.unlink()
        saved.rename(path)
        with pytest.raises(baseline.CaptureError):
            lease.capture.verify_snapshot()


@pytest.mark.parametrize('fault', ['snapshot', 'guest', 'test-failure'])
def test_metadata_policy_preserves_refusals_and_owned_cleanup(lease_rig, fault):
    lease, current = lease_rig
    if fault == 'snapshot':
        lease.source.baseline_xml = lease.source.baseline_xml.replace(
            '<creationTime>100', '<creationTime>200')
        with pytest.raises(baseline.CaptureError):
            lease.__enter__()
        lease.source.domain.create.assert_not_called()
        lease.source.domain.revertToSnapshot.assert_not_called()
    elif fault == 'guest':
        with pytest.raises(Exception, match='cleanup:guest-changed'), lease:
            lease.prepare()
            lease.start()
            lease.inspect = Mock(return_value={'changed': True})
        assert lease.state['phase'] == 'cleanup-requested'
        assert lease.source.domain.revertToSnapshot.call_count == 2
    else:
        with pytest.raises(RuntimeError, match='test-failed'), lease:
            lease.prepare()
            lease.start()
            raise RuntimeError('test-failed')
        assert lease.state['phase'] == 'complete'
        assert lease.source.domain.revertToSnapshot.call_count == 2
    assert lease.fd is None and lease.source.off and current['id'] == -1


@pytest.mark.parametrize('change', ['replace', 'symlink', 'hardlink', 'chain', 'snapshot'])
def test_identity_and_snapshot_changes_refuse(lease_rig, change):
    lease, _ = lease_rig
    with pytest.raises(baseline.CaptureError), lease:
        path = lease.capture.anchor
        if change in ('replace', 'symlink'):
            saved = path.with_suffix('.saved')
            path.rename(saved)
            if change == 'replace':
                path.write_bytes(saved.read_bytes())
            else:
                path.symlink_to(saved)
        elif change == 'hardlink':
            os.link(path, path.with_suffix('.alias'))
        elif change == 'chain':
            lease.capture.state['source']['chain'][1]['virtual_size'] += 1
        else:
            lease.source.baseline_xml = lease.source.baseline_xml.replace(
                '<creationTime>100', '<creationTime>200')
        lease.capture.verify_snapshot()
    assert lease.fd is None


@pytest.mark.parametrize('change', ['unlock', 'descriptor', 'path', 'attempt', 'process'])
def test_lost_or_replaced_vm_ownership_refuses(lease_rig, monkeypatch, change):
    lease, _ = lease_rig
    extra_fd = None
    try:
        with pytest.raises(baseline.CaptureError, match='backing-owner-changed'), lease:
            proof = lease.capture.vm_ownership
            if change == 'unlock':
                fcntl.flock(lease.fd, fcntl.LOCK_UN)
            elif change == 'descriptor':
                # The same inode opened separately has no owned flock.
                extra_fd = os.open(lease.directory / '.lock', os.O_RDWR)
                os.dup2(extra_fd, lease.fd)
            elif change == 'path':
                lock = lease.directory / '.lock'
                lock.rename(lock.with_suffix('.saved'))
                lock.touch(mode=0o600)
            elif change == 'attempt':
                lease.state['run'] = 'another-attempt'
            else:
                proof.pid += 1
            lease.capture.verify_snapshot()
    finally:
        if extra_fd is not None:
            os.close(extra_fd)
    assert lease.fd is None


@pytest.mark.parametrize('action', ['prepare', 'restore'])
def test_ownership_loss_refuses_before_journal_or_vm_mutation(lease_rig, action):
    lease, _ = lease_rig
    with pytest.raises(baseline.CaptureError, match='backing-owner-changed'), lease:
        if action == 'restore':
            lease.prepare()
        journal = lease.journal.read_bytes()
        shutdowns = lease.source.shutdown_calls
        restores = lease.source.domain.revertToSnapshot.call_count
        fcntl.flock(lease.fd, fcntl.LOCK_UN)
        with pytest.raises(baseline.CaptureError, match='backing-owner-changed'):
            getattr(lease, action)()
        assert lease.journal.read_bytes() == journal
        assert lease.source.shutdown_calls == shutdowns
        assert lease.source.domain.revertToSnapshot.call_count == restores


def test_release_error_preserves_original_failure_and_still_releases_vm_lock(lease_rig, monkeypatch):
    lease, _ = lease_rig
    with pytest.raises(RuntimeError, match='first-failure'), lease:
        proof = lease.capture.vm_ownership
        real_close = proof.close
        def close_then_fail():
            real_close()
            raise OSError('private-canary')
        monkeypatch.setattr(proof, 'close', close_then_fail)
        raise RuntimeError('first-failure')
    assert lease.fd is None and proof.closed


def test_real_provenance_revokes_vt6_authorization_after_ownership_loss(lease_rig, source):
    lease, _ = lease_rig
    with pytest.raises(baseline.CaptureError, match='backing-owner-changed'), lease:
        lease.prepare()
        verified = provenance.VerifiedInputs(root=source, lease=lease)
        observer = Mock()
        auth = Authentication(source, observer, verified)
        proof = lease.capture.vm_ownership
        fcntl.flock(lease.fd, fcntl.LOCK_UN)
        with pytest.raises(provenance.EvidenceError, match='vt6-auth:inputs-before-refused'):
            auth.observe('vt6-login-ready', None, Mock())
        observer.read.assert_not_called()
        with pytest.raises(provenance.EvidenceError, match='vt6-auth:previous-failure'):
            auth.observe('vt6-login-ready', None, Mock())
        assert verified._failure == 'provenance:recheck-failed'


def test_durable_baseline_reconciliation_is_not_cached(lease_rig, source):
    lease, _ = lease_rig
    with lease:
        lease.prepare()
        verified = provenance.VerifiedInputs(root=source, lease=lease)
        path = lease.capture.directory / 'phase.json'
        original = path.read_bytes()
        changed = json.loads(original)
        changed['phase'] = 'source-off'
        path.write_bytes(baseline.encode(changed))
        with pytest.raises(provenance.EvidenceError, match='baseline-state-changed'):
            verified.recheck()
        path.write_bytes(original)
        with pytest.raises(provenance.EvidenceError, match='baseline-state-changed'):
            verified.recheck()


def test_metadata_failure_still_stops_and_restores_only_the_owned_guest(lease_rig):
    lease, current = lease_rig
    with pytest.raises(baseline.CaptureError, match='backing-file-changed'), lease:
        lease.prepare()
        lease.start()
        proof = lease.capture.vm_ownership
        proof.remember(baseline.CaptureError('guard:backing-file-changed'))
    assert lease.fd is None and current['id'] == -1
    assert lease.source.off
    assert lease.source.domain.revertToSnapshot.call_count == 2
    assert lease.capture.verification_failure is not None
    assert lease.state['phase'] == 'cleanup-requested'


def test_ownership_refusal_stays_latched_after_the_lock_is_reacquired(lease_rig):
    lease, _ = lease_rig
    with pytest.raises(baseline.CaptureError, match='backing-owner-changed'), lease:
        lease.prepare()
        fcntl.flock(lease.fd, fcntl.LOCK_UN)
        with pytest.raises(baseline.CaptureError, match='backing-owner-changed'):
            lease.guard()
        fcntl.flock(lease.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(baseline.CaptureError, match='backing-owner-changed'):
            lease.start()
        lease.source.domain.create.assert_not_called()


def test_retirement_cannot_clear_a_failed_metadata_guard_or_allow_startup(lease_rig):
    lease, _ = lease_rig
    with pytest.raises(baseline.CaptureError, match='backing-file-changed'), lease:
        lease.prepare()
        proof = lease.capture.vm_ownership
        proof.remember(baseline.CaptureError('guard:backing-file-changed'))
        with pytest.raises(baseline.CaptureError, match='backing-file-changed'):
            lease.start()
        assert proof.closed
        with pytest.raises(baseline.CaptureError, match='backing-file-changed'):
            lease.capture.begin_vm_ownership(lease)
        lease.source.domain.create.assert_not_called()


@pytest.mark.parametrize('fault', ['none', 'xml', 'active', 'backing', 'snapshot', 'guest'])
def test_off_recovery_audits_exact_restoration_without_vm_mutations(lease_rig, fault):
    import system_runner as runner
    lease, current = lease_rig
    lease.__enter__()
    lease.prepare()
    lease.start()
    lease.save('cleanup-requested')
    lease.capture.retire_vm_ownership()
    lease.source.domain.revertToSnapshot(None, 0)
    lease.release()
    recovery = runner.Lease(lease.source, lease.commands, lease.inspect,
                            directory=lease.directory, anchor=lease.capture.anchor,
                            graphics_type='vnc')
    journal = lease.journal.read_bytes()
    if fault == 'xml':
        current['xml'] = current['xml'].replace('</domain>', '<description>changed</description></domain>')
    elif fault == 'active':
        current['id'] = 72
        lease.source.off = False
    elif fault == 'backing':
        path = lease.capture.anchor
        path.rename(path.with_suffix('.saved'))
        path.write_bytes(b'replaced backing')
    elif fault == 'snapshot':
        lease.source.baseline_xml = lease.source.baseline_xml.replace(
            '<creationTime>100', '<creationTime>200')
    elif fault == 'guest':
        recovery.inspect = Mock(return_value={'changed': True})
    lease.source.domain.reset_mock()
    lease.source.connection.reset_mock()
    shutdowns = lease.source.shutdown_calls
    if fault == 'none':
        recovery.recover_graphical_cleanup()
        assert recovery.state['phase'] == 'complete'
        assert recovery.capture.verification_totals['bytes_read'] == 0
    else:
        with pytest.raises((runner.Error, baseline.CaptureError)):
            recovery.recover_graphical_cleanup()
        assert lease.journal.read_bytes() == journal
    assert recovery.fd is None
    assert lease.source.shutdown_calls == shutdowns
    lease.source.domain.create.assert_not_called()
    lease.source.domain.destroyFlags.assert_not_called()
    lease.source.domain.revertToSnapshot.assert_not_called()
    lease.source.connection.defineXML.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'phase', 'run', 'snapshot'])
def test_off_isolated_recovery_restores_only_recorded_cleanup(lease_rig, fault):
    import system_runner as runner
    lease, current = lease_rig
    lease.view.graphics_type = 'vnc'
    lease.__enter__()
    lease.prepare()
    lease.start()
    lease.save('cleanup-requested')
    lease.capture.retire_vm_ownership()
    lease.source.off, current['id'] = True, -1
    lease.release()
    recovery = runner.Lease(lease.source, lease.commands, lease.inspect,
                            directory=lease.directory, anchor=lease.capture.anchor,
                            graphics_type='vnc')
    if fault == 'phase':
        state = json.loads(lease.journal.read_bytes())
        state['phase'] = 'running'
        lease.journal.write_bytes(baseline.encode(state))
    elif fault == 'run':
        current['xml'] = current['xml'].replace(lease.state['run'], 'b' * 32)
    elif fault == 'snapshot':
        lease.source.baseline_xml = lease.source.baseline_xml.replace(
            '<creationTime>100', '<creationTime>200')
    lease.source.domain.reset_mock()
    lease.source.connection.reset_mock()
    if fault is None:
        recovery.recover_graphical_cleanup()
        assert recovery.state['phase'] == 'complete'
        lease.source.domain.revertToSnapshot.assert_called_once()
        lease.source.connection.defineXML.assert_called_once_with(lease.original_xml)
        assert lease.source.off and current['id'] == -1
    else:
        with pytest.raises((runner.Error, baseline.CaptureError)):
            recovery.recover_graphical_cleanup()
        lease.source.domain.revertToSnapshot.assert_not_called()
        lease.source.connection.defineXML.assert_not_called()
        assert json.loads(lease.journal.read_bytes())['phase'] != 'complete'
    assert recovery.fd is None
    lease.source.domain.create.assert_not_called()
    lease.source.domain.destroyFlags.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'instance', 'run', 'busy', 'maintenance'])
@pytest.mark.parametrize('graphics_type', ['vnc', 'spice'])
def test_dead_running_owner_recovery_requires_its_vm_identity_and_lease(lease_rig, fault, graphics_type):
    import system_runner as runner
    lease, current = lease_rig
    lease.view.graphics_type = graphics_type
    lease.__enter__()
    lease.prepare()
    lease.start()
    lease.release()
    recovery = runner.Lease(lease.source, lease.commands, lease.inspect,
                            directory=lease.directory, anchor=lease.capture.anchor,
                            graphics_type=graphics_type)
    recover = (recovery.recover_graphical_cleanup if graphics_type == 'vnc'
               else recovery.recover_system_cleanup)
    journal = lease.journal.read_bytes()
    if fault == 'instance':
        current['id'] = 72
    if fault == 'run':
        current['xml'] = current['xml'].replace(lease.state['run'], 'b' * 32)
    if fault == 'maintenance':
        path = lease.directory / 'vm-control.json'
        path.write_text(json.dumps({'run': lease.state['run']}))
        path.chmod(0o600)
    lease.source.domain.reset_mock()
    lease.source.connection.reset_mock()
    if fault == 'busy':
        import fcntl
        with lease.capture.lock_path.open('rb') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with pytest.raises(runner.Error, match='busy-controller'):
                recover()
    elif fault:
        with pytest.raises((runner.Error, baseline.CaptureError)):
            recover()
    else:
        recover()
        assert recovery.state['phase'] == 'complete'
        assert current['xml'] == lease.original_xml
        lease.source.domain.revertToSnapshot.assert_called_once()
    if fault:
        assert lease.journal.read_bytes() == journal
        lease.source.domain.revertToSnapshot.assert_not_called()
        lease.source.domain.destroyFlags.assert_not_called()
    assert recovery.fd is None


@pytest.mark.parametrize('fault', ['none', 'active', 'run', 'sharing', 'backing', 'instance'])
@pytest.mark.parametrize('graphics_type', ['vnc', 'spice'])
def test_prestart_recovery_restores_only_recorded_off_isolation(lease_rig, fault, graphics_type):
    import system_runner as runner
    lease, current = lease_rig
    lease.view.graphics_type = graphics_type
    lease.__enter__()
    lease.prepare()
    lease.release()  # Simulate interruption after isolation, before guest start.
    recovery = runner.Lease(lease.source, lease.commands, lease.inspect,
                            directory=lease.directory, anchor=lease.capture.anchor,
                            graphics_type=graphics_type)
    recover = (recovery.recover_graphical_cleanup if graphics_type == 'vnc'
               else recovery.recover_system_cleanup)
    if fault == 'active':
        current['id'] = 72
        lease.source.off = False
    elif fault == 'run':
        current['xml'] = current['xml'].replace(lease.state['run'], 'b' * 32)
    elif fault == 'sharing':
        current['xml'] = current['xml'].replace('</devices>', '<channel/></devices>')
    elif fault == 'backing':
        path = lease.capture.anchor
        path.rename(path.with_suffix('.saved'))
        path.write_bytes(b'replaced backing')
    elif fault == 'instance':
        state = json.loads(lease.journal.read_bytes())
        state['domain_id'] = 17
        lease.journal.write_bytes(runner.baseline.encode(state))
    journal = lease.journal.read_bytes()
    lease.source.domain.reset_mock()
    lease.source.connection.reset_mock()
    shutdowns = lease.source.shutdown_calls
    if fault == 'none':
        recover()
        assert recovery.state['phase'] == 'complete'
        assert current['xml'] == lease.original_xml
        lease.source.domain.revertToSnapshot.assert_called_once()
        lease.source.connection.defineXML.assert_called_once_with(lease.original_xml)
    else:
        with pytest.raises((runner.Error, baseline.CaptureError)):
            recover()
        assert lease.journal.read_bytes() == journal
        lease.source.domain.revertToSnapshot.assert_not_called()
        lease.source.connection.defineXML.assert_not_called()
    assert recovery.fd is None
    assert lease.source.shutdown_calls == shutdowns
    lease.source.domain.create.assert_not_called()
    lease.source.domain.destroyFlags.assert_not_called()
