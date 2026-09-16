"""Real kernel lease refusals and simulated VM boundaries; no live VM writes."""

import errno
import fcntl
import json
import mmap
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

import backing_verification as backing
import prepare_host as baseline
import provenance
from vt6_authentication import Authentication
from tests.support.e2e_provenance import source
from tests.support.vm_baseline import rig
from tests.support.vm_runner import lease_rig


def require_leases(lease):
    if not lease.capture.backing_verification.enabled:
        pytest.skip('kernel read leases unavailable; full verification remains enabled')


@pytest.mark.parametrize('lease_rig', [False], indirect=True)
@pytest.mark.parametrize('fallback', [False, True])
def test_fast_attempt_skips_every_byte_scan_but_restores_and_reports_policy(
        lease_rig, monkeypatch, capsys, fallback):
    lease, current = lease_rig
    if fallback:
        monkeypatch.setattr(backing, 'supported_filesystem', lambda _: False)
    # A pre-existing same-size content change is deliberately outside fast
    # mode's assurance. Neither the leased nor fallback route may hash it.
    lease.capture.anchor.write_bytes(b'x' * lease.capture.anchor.stat().st_size)
    monkeypatch.setattr(baseline, 'digest', Mock(side_effect=AssertionError('unexpected full scan')))
    monkeypatch.setattr(backing.os, 'read', Mock(side_effect=AssertionError('unexpected leased scan')))
    with lease:
        lease.prepare()
        assert lease.capture.verify_snapshot() == lease.capture.state['proof']
        lease.start()
        assert lease.capture.verify_snapshot(force_bytes=True) == lease.capture.state['proof']
        assert not lease.capture.backing_verification.verified
    assert lease.state['phase'] == 'complete' and lease.fd is None
    assert lease.source.off and current['id'] == -1
    assert lease.source.domain.revertToSnapshot.call_count == 2
    assert lease.capture.verification_totals['bytes_read'] == 0
    assert lease.capture.verification_totals['policy'] == 'metadata-only'
    events = [json.loads(line.removeprefix('baseline:verification '))
              for line in capsys.readouterr().err.splitlines()
              if line.startswith('baseline:verification ')]
    assert events and all(event['mode'] == 'metadata-only' for event in events)
    assert events[0]['boundary'] == 'acquisition' and events[-1]['boundary'] == 'restoration'


@pytest.mark.parametrize('lease_rig', [True, False], indirect=True)
@pytest.mark.parametrize('fault', ['snapshot', 'guest', 'test-failure'])
def test_both_policies_preserve_refusals_and_owned_cleanup(lease_rig, fault):
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


def test_backing_open_refuses_symlinked_parent_without_following_it(tmp_path):
    directory = tmp_path / 'actual'
    directory.mkdir()
    (directory / 'file').write_bytes(b'unchanged')
    alias = tmp_path / 'alias'
    alias.symlink_to(directory, target_is_directory=True)
    with pytest.raises(OSError):
        backing.open_backing(alias / 'file')
    assert (directory / 'file').read_bytes() == b'unchanged'


def test_same_attempt_reuses_only_leased_bytes_and_rehashes_restoration(lease_rig, capsys):
    lease, _ = lease_rig
    size = Path(lease.capture.anchor).stat().st_size
    with lease:
        require_leases(lease)
        proof = lease.capture.backing_verification
        lease.prepare()
        initial = lease.capture.verification_totals['bytes_read']
        for _ in range(3):
            assert lease.capture.verify_snapshot() == lease.capture.state['proof']
        assert lease.capture.verification_totals['bytes_read'] == initial == size
        top = Path(lease.capture.state['source']['chain'][0]['path'])
        top.write_bytes(b'ordinary active image writes are allowed')
        assert lease.capture.verify_snapshot() == lease.capture.state['proof']
        assert all(not os.get_inheritable(fd) for _, fd, _ in proof.files)
    assert proof.closed and not proof.files
    assert lease.fd is None and lease.state['phase'] == 'complete'
    assert lease.capture.verification_totals['bytes_read'] == 2 * size
    events = [json.loads(line.removeprefix('baseline:verification '))
              for line in capsys.readouterr().err.splitlines()
              if line.startswith('baseline:verification ')]
    assert events[-1]['boundary'] == 'restoration'
    assert events[-1]['mode'] == 'full' and events[-1]['bytes_read'] == size
    assert sum(event['mode'] == 'leased-proof' for event in events) == 4


@pytest.mark.parametrize('flags', [os.O_WRONLY, os.O_RDWR, os.O_WRONLY | os.O_TRUNC])
def test_conflicting_writer_is_refused_synchronously_without_signal_timing(lease_rig, flags):
    lease, _ = lease_rig
    with pytest.raises(baseline.CaptureError, match='backing-lease-broken'), lease:
        require_leases(lease)
        original = lease.capture.anchor.read_bytes()
        with pytest.raises(BlockingIOError) as failure:
            os.open(lease.capture.anchor, flags | os.O_NONBLOCK)
        assert failure.value.errno in (errno.EAGAIN, errno.EWOULDBLOCK)
        assert lease.capture.anchor.read_bytes() == original
        # Even a cancelled nonblocking writer leaves the kernel break latched.
        lease.capture.verify_snapshot()
    assert lease.fd is None
    assert not lease.capture.backing_verification.files


def test_revoked_lease_cannot_pass_after_same_size_write_and_restored_bytes(lease_rig):
    lease, _ = lease_rig
    with pytest.raises(baseline.CaptureError, match='backing-lease-broken'), lease:
        require_leases(lease)
        proof = lease.capture.backing_verification
        path, fd, _ = proof.files[0]
        original = path.read_bytes()
        before = path.stat()
        fcntl.fcntl(fd, fcntl.F_SETLEASE, fcntl.F_UNLCK)
        path.write_bytes(b'x' * len(original))
        path.write_bytes(original)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        for _ in range(2):
            with pytest.raises(baseline.CaptureError, match='backing-lease-broken'):
                lease.capture.verify_snapshot()
    assert lease.fd is None


@pytest.mark.parametrize('mapping', [False, True])
def test_existing_writable_fd_or_mapping_forces_full_reads(lease_rig, mapping):
    lease, _ = lease_rig
    path = lease.capture.anchor
    stream = path.open('r+b')
    view = None
    try:
        if mapping:
            view = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_WRITE)
            stream.close()
        with pytest.raises(baseline.CaptureError, match='backing-digest-changed'), lease:
            assert not lease.capture.backing_verification.enabled
            initial = lease.capture.verification_totals['bytes_read']
            lease.capture.verify_snapshot()
            assert lease.capture.verification_totals['bytes_read'] == 2 * initial
            if mapping:
                view[0:1] = b'x'
                view.flush()
            else:
                os.pwrite(stream.fileno(), b'x', 0)
            lease.capture.verify_snapshot()
    finally:
        if view is not None:
            view.close()
        stream.close()
    assert lease.fd is None


@pytest.mark.parametrize('reason', ['filesystem', 'permission', 'signal'])
def test_unavailable_optimization_keeps_full_hashes_and_failure_latching(lease_rig, monkeypatch, reason):
    lease, _ = lease_rig
    if reason == 'filesystem':
        monkeypatch.setattr(backing, 'supported_filesystem', lambda _fd: False)
    elif reason == 'signal':
        monkeypatch.setattr(backing.signal, 'getsignal', lambda _sig: lambda *_: None)
    else:
        real_fcntl = fcntl.fcntl
        def unavailable(fd, command, *args):
            if command == fcntl.F_SETLEASE:
                raise PermissionError(errno.EPERM, 'private-canary')
            return real_fcntl(fd, command, *args)
        monkeypatch.setattr(backing.fcntl, 'fcntl', unavailable)
    with lease:
        proof = lease.capture.backing_verification
        assert not proof.enabled and not proof.files
        original = lease.capture.anchor.read_bytes()
        size = len(original)
        lease.capture.verify_snapshot()
        assert lease.capture.verification_totals['bytes_read'] == 2 * size
        lease.capture.anchor.write_bytes(b'x' * size)
        with pytest.raises(baseline.CaptureError, match='backing-digest-changed'):
            lease.capture.verify_snapshot()
        lease.capture.anchor.write_bytes(original)
        with pytest.raises(baseline.CaptureError, match='backing-digest-changed'):
            lease.capture.verify_snapshot()


@pytest.mark.parametrize('change', ['replace', 'symlink', 'hardlink', 'chain', 'snapshot'])
def test_identity_and_snapshot_changes_refuse_even_with_leased_bytes(lease_rig, change):
    lease, _ = lease_rig
    with pytest.raises(baseline.CaptureError), lease:
        require_leases(lease)
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
def test_lost_or_replaced_vm_ownership_cannot_reuse_proof(lease_rig, monkeypatch, change):
    lease, _ = lease_rig
    extra_fd = None
    try:
        with pytest.raises(baseline.CaptureError, match='backing-owner-changed'), lease:
            require_leases(lease)
            proof = lease.capture.backing_verification
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


def test_closed_or_foreign_capture_proofs_cannot_be_transferred(lease_rig):
    lease, _ = lease_rig
    with lease:
        require_leases(lease)
        proof = lease.capture.backing_verification
        foreign = Mock()
        with pytest.raises(baseline.CaptureError, match='backing-owner-changed'):
            proof.verify(foreign, lambda _: None)
    with pytest.raises(baseline.CaptureError, match='backing-owner-changed'):
        proof.verify(lease.capture, lambda _: None)


@pytest.mark.parametrize('action', ['prepare', 'restore'])
def test_ownership_loss_refuses_before_journal_or_vm_mutation(lease_rig, action):
    lease, _ = lease_rig
    with pytest.raises(baseline.CaptureError, match='backing-owner-changed'), lease:
        require_leases(lease)
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


def test_interrupt_during_initial_hash_releases_all_owned_descriptors(lease_rig, monkeypatch):
    lease, _ = lease_rig
    real_read = backing.os.read
    def interrupt(fd, count):
        proof = lease.capture.backing_verification
        if proof and any(fd == item[1] for item in proof.files):
            raise KeyboardInterrupt
        return real_read(fd, count)
    monkeypatch.setattr(backing.os, 'read', interrupt)
    try:
        try:
            lease.__enter__()
        except KeyboardInterrupt:
            pass
        else:
            require_leases(lease)
            pytest.fail('initial protected read did not run')
    finally:
        if lease.fd is not None:
            lease.release()
    assert lease.fd is None and not lease.capture.backing_verification.files
    lease.source.domain.create.assert_not_called()
    lease.source.domain.revertToSnapshot.assert_not_called()


def test_release_error_preserves_original_failure_and_still_releases_vm_lock(lease_rig, monkeypatch):
    lease, _ = lease_rig
    with pytest.raises(RuntimeError, match='first-failure'), lease:
        require_leases(lease)
        proof = lease.capture.backing_verification
        real_close = proof.close
        def close_then_fail():
            real_close()
            raise OSError('private-canary')
        monkeypatch.setattr(proof, 'close', close_then_fail)
        raise RuntimeError('first-failure')
    assert lease.fd is None and proof.closed and not proof.files


@pytest.mark.parametrize('fault', ['unsupported', 'interrupted', 'broken-before-fallback'])
def test_partial_acquisition_releases_files_and_never_downgrades_a_broken_proof(
        lease_rig, monkeypatch, fault):
    lease, _ = lease_rig
    # Exercise a second backing member without creating any VM image. The
    # synthetic inventory accepts this chain only inside this disposable rig.
    real_begin = lease.capture.begin_backing_verification
    def begin(owner):
        state = lease.capture.state
        second = lease.capture.anchor.with_suffix('.second')
        second.write_bytes(b'second backing')
        state['source']['chain'].append({**baseline.identity(second), 'virtual_size': 4096})
        state['source_digests'].append(baseline.digest(second))
        real_begin(owner)
    monkeypatch.setattr(lease.capture, 'begin_backing_verification', begin)
    real_support = backing.supported_filesystem
    count = 0
    def supported(fd):
        nonlocal count
        count += 1
        if count == 1:
            if not real_support(fd):
                pytest.skip('local filesystem cannot qualify partial kernel leases')
            return True
        if fault == 'interrupted':
            raise KeyboardInterrupt
        if fault == 'broken-before-fallback':
            first = lease.capture.backing_verification.files[0][1]
            fcntl.fcntl(first, fcntl.F_SETLEASE, fcntl.F_UNLCK)
        return False
    monkeypatch.setattr(backing, 'supported_filesystem', supported)
    expected = KeyboardInterrupt if fault == 'interrupted' else baseline.CaptureError
    # For ordinary fallback, synthetic inventory divergence refuses the later
    # full verification; acquisition itself must have released its first lease.
    with pytest.raises(expected):
        lease.__enter__()
    assert lease.fd is None
    proof = lease.capture.backing_verification
    assert proof.closed and not proof.files
    if fault == 'unsupported':
        assert proof.fallback == 'filesystem' and not proof.enabled
    elif fault == 'broken-before-fallback':
        assert str(proof.failure) == 'guard:backing-lease-broken'


def test_close_attempts_every_descriptor_after_one_close_error(lease_rig, monkeypatch):
    lease, _ = lease_rig
    with pytest.raises(OSError, match='private-canary'), lease:
        require_leases(lease)
        proof = lease.capture.backing_verification
        path, fd, pinned = proof.files[0]
        duplicate = os.dup(fd)
        proof.files.append((path, duplicate, pinned))
        real_close = backing.os.close
        closed = []
        def close(fd_to_close):
            real_close(fd_to_close)
            closed.append(fd_to_close)
            if fd_to_close == duplicate:
                raise OSError('private-canary')
        monkeypatch.setattr(backing.os, 'close', close)
    assert fd in closed and duplicate in closed
    assert lease.fd is None and not proof.files


def test_real_provenance_revokes_vt6_authorization_after_backing_lease_loss(lease_rig, source):
    lease, _ = lease_rig
    with pytest.raises(baseline.CaptureError, match='backing-lease-broken'), lease:
        require_leases(lease)
        lease.prepare()
        verified = provenance.VerifiedInputs(root=source, lease=lease)
        observer = Mock()
        auth = Authentication(source, observer, verified)
        proof = lease.capture.backing_verification
        fcntl.fcntl(proof.files[0][1], fcntl.F_SETLEASE, fcntl.F_UNLCK)
        with pytest.raises(provenance.EvidenceError, match='vt6-auth:inputs-before-refused'):
            auth.observe('vt6-login-ready', None, Mock())
        observer.read.assert_not_called()
        with pytest.raises(provenance.EvidenceError, match='vt6-auth:previous-failure'):
            auth.observe('vt6-login-ready', None, Mock())
        assert verified._failure == 'provenance:recheck-failed'


def test_durable_baseline_reconciliation_is_not_cached(lease_rig, source):
    lease, _ = lease_rig
    with lease:
        require_leases(lease)
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


def test_vm_transitions_retire_proof_and_first_existing_gate_must_rehash(lease_rig, monkeypatch):
    lease, _ = lease_rig
    original_start = lease.source.domain.create.side_effect
    original_shutdown = lease.source.shutdown
    proofs = []

    def transition(action):
        proof = lease.capture.backing_verification
        assert proof.closed and not proof.files
        proofs.append(proof)
        # Model QEMU's supported transient writable open, without a blocking
        # writer or a lease-break deadline. This must succeed on every run.
        fd = os.open(lease.capture.anchor, os.O_RDWR | os.O_NONBLOCK)
        os.close(fd)
        return action()

    with lease:
        require_leases(lease)
        lease.prepare()
        monkeypatch.setattr(lease.source.domain.create, 'side_effect',
                            lambda: transition(original_start))
        monkeypatch.setattr(lease.source, 'shutdown',
                            lambda guard, requested: transition(
                                lambda: original_shutdown(guard, requested=requested)))
        size = lease.capture.anchor.stat().st_size
        lease.start()
        assert lease.capture.verification_totals['bytes_read'] == size
        active = lease.capture.backing_verification
        assert active is not proofs[0] and not active.verified
        lease.capture.verify_snapshot()
        assert active.verified
        assert lease.capture.verification_totals['bytes_read'] == 2 * size
        lease.stop()
        assert active.closed
        lease.capture.verify_snapshot()
        assert lease.capture.verification_totals['bytes_read'] == 3 * size
    assert lease.capture.verification_totals['bytes_read'] == 4 * size
    assert len(proofs) == 2


def test_transition_mutation_is_rejected_by_fresh_full_hash(lease_rig):
    lease, _ = lease_rig
    start = lease.source.domain.create.side_effect
    with pytest.raises(baseline.CaptureError, match='backing-digest-changed'), lease:
        require_leases(lease)
        lease.prepare()
        def corrupt_start():
            lease.capture.anchor.write_bytes(b'x' * lease.capture.anchor.stat().st_size)
            start()
        lease.source.domain.create.side_effect = corrupt_start
        lease.start()
        assert not lease.capture.backing_verification.verified
        lease.capture.verify_snapshot()
    assert lease.fd is None
    assert str(lease.capture.verification_failure) == 'guard:backing-digest-changed'
    assert lease.source.off
    assert lease.source.domain.revertToSnapshot.call_count == 2


def test_byte_proof_failure_still_stops_and_restores_only_the_owned_guest(lease_rig):
    lease, current = lease_rig
    with pytest.raises(baseline.CaptureError, match='backing-lease-broken'), lease:
        require_leases(lease)
        lease.prepare()
        lease.start()
        proof = lease.capture.backing_verification
        fcntl.fcntl(proof.files[0][1], fcntl.F_SETLEASE, fcntl.F_UNLCK)
    assert lease.fd is None and current['id'] == -1
    assert lease.source.off
    assert lease.source.domain.revertToSnapshot.call_count == 2
    assert lease.capture.verification_failure is not None
    assert lease.state['phase'] == 'cleanup-requested'


@pytest.mark.parametrize('lease_rig', [True, False], indirect=True)
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


@pytest.mark.parametrize('lease_rig', [True, False], indirect=True)
def test_retirement_cannot_clear_a_broken_proof_or_allow_startup(lease_rig):
    lease, _ = lease_rig
    with pytest.raises(baseline.CaptureError, match='backing-lease-broken'), lease:
        require_leases(lease)
        lease.prepare()
        proof = lease.capture.backing_verification
        fcntl.fcntl(proof.files[0][1], fcntl.F_SETLEASE, fcntl.F_UNLCK)
        with pytest.raises(baseline.CaptureError, match='backing-lease-broken'):
            lease.start()
        assert proof.closed
        with pytest.raises(baseline.CaptureError, match='backing-lease-broken'):
            lease.capture.begin_backing_verification(lease)
        lease.source.domain.create.assert_not_called()


@pytest.mark.parametrize('fault', ['none', 'xml', 'active', 'backing', 'snapshot', 'guest'])
def test_off_recovery_audits_exact_restoration_without_vm_mutations(lease_rig, fault):
    import system_runner as runner
    lease, current = lease_rig
    lease.__enter__()
    lease.prepare()
    lease.start()
    lease.save('cleanup-requested')
    lease.capture.retire_backing_verification()
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
        lease.capture.anchor.write_bytes(b'x' * lease.capture.anchor.stat().st_size)
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
        assert recovery.capture.verification_totals['bytes_read'] == lease.capture.anchor.stat().st_size
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
        lease.capture.anchor.write_bytes(b'x' * lease.capture.anchor.stat().st_size)
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
