"""Bounded repetition and refusal of foreign, active or recovery-owned storage."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import stat
import tempfile
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest

from tools import test_retention as retention


class SimulatedFailure(ValueError):
    """Distinguish the fixture's failure from a retention error."""


class SimulatedInterrupt(KeyboardInterrupt):
    """Distinguish the fixture's interrupt from a real test-run interruption."""


def test_inherited_retention_capability_is_the_existing_exclusive_owner(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        owner = retention.owner_descriptor()
        assert retention.descriptors() == (owner,)
        assert retention.environment()[retention.OWNER_VARIABLE] == str(owner)
        false_owner = os.open(store.path / 'owner.lock', os.O_RDONLY)
        try:
            with monkeypatch.context() as patch:
                patch.setenv(retention.OWNER_VARIABLE, str(false_owner))
                with pytest.raises(ValueError, match='does not own'):
                    retention.owner_descriptor()
            assert retention.owner_descriptor() == owner
        finally:
            os.close(false_owner)
        with monkeypatch.context() as patch:
            patch.delenv(retention.OWNER_VARIABLE)
            with pytest.raises(ValueError, match='descriptor required'):
                retention.owner_descriptor()


def test_inherited_retention_capability_refuses_replaced_lock(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        owner = retention.owner_descriptor()
        lock = store.path / 'owner.lock'
        original = store.path / 'original.lock'
        lock.rename(original)
        lock.touch(mode=0o600)
        try:
            with pytest.raises(ValueError, match='replaced|ownership'):
                retention.owner_descriptor()
            assert os.fstat(owner).st_ino == original.stat().st_ino
        finally:
            lock.unlink()
            original.rename(lock)


def allocated(parent, name):
    path = parent / name
    path.mkdir(mode=0o700)
    (path / 'test.log').write_bytes(b'evidence' * 128)
    retention.retain(path)
    return path


def advance_to_expiry(store):
    for _ in range(2):
        with store.session():
            pass


def export_fixture(tmp_path):
    store = retention.Store(tmp_path / 'exports-state')
    paths = []
    for index in range(3):
        with store.session():
            paths.append(allocated(tmp_path, f'export-{index}'))
    return store, paths


def publication_allocation(transaction, tmp_path):
    path = transaction.allocate(tempfile.mkdtemp, prefix='export-', dir=str(tmp_path))
    (path / 'bundle.zip').write_bytes(b'verified bundle bytes')
    return path


def test_verified_publication_reuse_keeps_journal_and_refuses_allocation(tmp_path, monkeypatch):
    store, paths = export_fixture(tmp_path)
    before = (store.path / 'current.json').read_bytes()
    seen = []

    def reuse(state):
        seen.append(state['run'])
        with pytest.raises(ValueError, match='another owner'):
            with retention.Store(store.path).inspection():
                pytest.fail('reuse released its owner lock')
        return {'path': str(paths[0])}

    # Reuse needs no projected staging capacity, while existing usage stays strict.
    with store.publication(projected_bytes=retention.MAX_RETAINED_BYTES,
                           reuse=reuse, wait=True) as transaction:
        assert transaction.reused == {'path': str(paths[0])}
        with pytest.raises(ValueError, match='reused publication'):
            transaction.allocate(tempfile.mkdtemp, dir=tmp_path)
        with pytest.raises(ValueError, match='no uncommitted'):
            transaction.commit()
    assert len(seen) == 1
    assert (store.path / 'current.json').read_bytes() == before
    assert all(path.exists() for path in paths)


def test_publication_reuse_cannot_bypass_replaced_owner_audit(tmp_path):
    store, paths = export_fixture(tmp_path)
    paths[0].rename(tmp_path / 'original')
    paths[0].mkdir(mode=0o700)
    before = (store.path / 'current.json').read_bytes()
    with pytest.raises(ValueError, match='replaced'):
        with store.publication(projected_bytes=0,
                reuse=lambda _: pytest.fail('reuse ran before identity audit')):
            pytest.fail('replaced export was adopted')
    assert (store.path / 'current.json').read_bytes() == before


def pending_capture(store, tmp_path, *, oldest=False):
    """A valid parent charge remains required even if its controls are absent."""
    slot = tmp_path / 'capture-slot'
    slot.mkdir(mode=0o700)
    info = slot.stat()
    charge = dict(capture_id='a' * 64, path=str(slot), device=info.st_dev,
                  inode=info.st_ino, mode=0o700, reserved_bytes=0, intent={})
    with store.opened() as fd, store.locked(fd, 'writer.lock'):
        state = store.read(fd)
        entry = state['history'][0] if oldest else state
        entry['captures'] = [charge]
        store.save(fd, state)
    return slot, charge


def required_report_history(tmp_path, monkeypatch, phase):
    """Real multi-member capture with unpublished and suspended consumers.

    Only the allocator root and process authentication are private fixture
    inputs. Sealing, publication, acknowledgement and retirement locks stay real.
    """
    import evidence_bundle as bundle
    import evidence_capture as capture
    import evidence_identity as logical
    import test_retention as live_retention
    import test_storage as storage
    import capture_publication as publication

    checkout = tmp_path / 'checkout'
    checkout.mkdir(mode=0o700)
    monkeypatch.setattr(storage, 'ROOT', checkout)
    monkeypatch.setattr(storage, 'BASE', checkout / 'output/test-runs')
    monkeypatch.delenv(live_retention.VARIABLE, raising=False)
    store = live_retention.Store(storage.directory('state') / 'retention-host')
    consumers = {identifier: dict(consumer_id=identifier, revision_sha256='c' * 64)
                 for identifier in ('a' * 64, 'b' * 64)}
    payloads = {
        'result': b'{"verdict":"passed","invocations":1}\n',
        'input': b'exact original selected inputs\n',
        'command': b'one recorded command, no rerun\n',
        'cleanup': b'{"state":"complete","resources":[]}\n',
    }
    with store.session() as run:
        source = Path(live_retention.allocate(tempfile.mkdtemp,
                                             prefix='onpc-report-history-'))
        for role, payload in payloads.items():
            path = source / f'{role}.json'
            path.write_bytes(payload)
            path.chmod(0o600)
        handle = capture.issue_session(
            store, repository=checkout, workflow='retirement-history', task='E04',
            check='complete-report', inputs_sha256='d' * 64, sources_sha256='e' * 64,
            consumers=consumers)
        context = capture.session_context(handle)
        info = source.stat()
        allocation = dict(path=str(source), device=info.st_dev, inode=info.st_ino,
                          mode=0o700, journal=str(store.path), run=run)
        record = logical.finalize_record(dict(
            schema=logical.SCHEMA, version=1, context=context,
            status='passed', completeness='complete', dependencies=[],
            members=[dict(role=role, original_path=str(source / f'{role}.json'),
                          source_allocation=allocation, bytes=len(payload),
                          sha256=hashlib.sha256(payload).hexdigest(), required=True)
                     for role, payload in payloads.items()],
            cleanup=dict(state='complete', record_members=[],
                         scope=dict(owner=context['owner'], resources=[]))))
        identifier = capture.finalize_capture(handle, record=record,
                                              consumer_ids=sorted(consumers))
        request = capture.inspect_capture(checkout, os.geteuid(), os.getegid(), identifier)

        def publish():
            with bundle.Selection(checkout, os.geteuid(), os.getegid(), [], [], [],
                                  captures=[identifier]) as selected:
                return bundle.export(selected, expected=selected.selection_sha256)

        receipt = None
        if phase == 'failed':
            def interrupted(point):
                if point == 'publication.copied':
                    raise SimulatedInterrupt('fixture interrupted publication')
            with monkeypatch.context() as local:
                local.setattr(publication, 'checkpoint', interrupted)
                with pytest.raises(SimulatedInterrupt):
                    publish()
        elif phase == 'capacity':
            # Use the real projected-size refusal before allocating a destination.
            with bundle.Selection(checkout, os.geteuid(), os.getegid(), [], [], [],
                                  captures=[identifier]) as selected:
                with monkeypatch.context() as local:
                    local.setattr(live_retention, 'MAX_RETAINED_BYTES', 1)
                    with pytest.raises(ValueError, match='budget|capacity'):
                        bundle.export(selected, expected=selected.selection_sha256)
        else:
            receipt = publish()
        if phase == 'acknowledged':
            capture.acknowledge_capture(
                checkout, os.geteuid(), os.getegid(), identifier,
                expected=request['request_sha256'], session_handle=handle)
    return SimpleNamespace(store=store, source=source, record=record, request=request,
                           consumers=consumers, payloads=payloads, publish=publish,
                           receipt=receipt, capture=capture, bundle=bundle,
                           retention=live_retention, checkout=checkout,
                           allocation_bytes=live_retention.allocation_bytes)


def retirement_history_route(history, monkeypatch, route):
    """Exercise actual startup dispatch; simulate only its privilege/VM boundary."""
    store = history.store
    if route == 'ordinary':
        for _ in range(2):
            with store.session():
                pass
        def rotate():
            with store.session():
                pass
        return rotate

    allocation_bytes = history.retention.allocation_bytes
    def oversized_source(record, **kwargs):
        # Keep historical bundle provenance valid; only the owned original is large.
        if Path(record['path']) == history.source:
            return history.retention.MAX_RETAINED_BYTES + 1
        return allocation_bytes(record, **kwargs)
    monkeypatch.setattr(history.retention, 'allocation_bytes', oversized_source)
    if route == 'host':
        import test_recovery
        monkeypatch.setattr(test_recovery.test_activity, 'activity',
                            lambda *args, **kwargs: nullcontext())
        monkeypatch.setattr(test_recovery.test_activity, 'retention_path',
                            lambda root: store.path)
        return lambda: test_recovery.cleanup_host(history.checkout)

    import check_test_recovery as recovery
    from contextlib import contextmanager
    import test_storage
    monkeypatch.setattr(recovery, 'ROOT', Path.cwd())
    monkeypatch.setattr(recovery, 'os', SimpleNamespace(
        geteuid=lambda: 0, environ={'PKEXEC_UID': str(os.geteuid() or 1000)}))
    monkeypatch.setattr(recovery.sys, 'argv', ['check_test_recovery'])
    monkeypatch.setattr(test_storage, 'privileged_state', lambda uid: store.path)
    monkeypatch.setattr(recovery, 'reconcile_vm', lambda root: None)
    held = False
    @contextmanager
    def lease(root):
        nonlocal held
        assert not held
        held = True
        try:
            yield
        finally:
            held = False
    monkeypatch.setattr(recovery.runpy, 'run_path', lambda path: {'retention_lease': lease})
    def unused(paths):
        assert held and paths == {str(history.source)}
    monkeypatch.setattr(recovery, 'unused', unused)
    remove = history.retention.remove
    def pinned_remove(record, *, validate_only=False):
        if record['path'] == str(history.source) and not validate_only:
            assert held
        return remove(record, validate_only=validate_only)
    monkeypatch.setattr(history.retention, 'remove', pinned_remove)
    return recovery.main


def assert_complete_report(history, receipt):
    verified = history.bundle.inspect(history.checkout, os.geteuid(), os.getegid(),
                                      receipt['path'])
    assert verified['manifest']['records'] == [history.record]
    assert history.request['consumers'] == history.consumers
    for member in history.record['members']:
        content = history.bundle.inspect(
            history.checkout, os.geteuid(), os.getegid(), receipt['path'],
            record_id=history.record['record_id'], member_id=member['member_id'],
            closure_sha256=history.record['closure_sha256'])
        assert content == history.payloads[member['role']]
        assert hashlib.sha256(content).hexdigest() == member['sha256']


@pytest.mark.parametrize('route', ['ordinary', 'host', 'privileged'])
@pytest.mark.parametrize('phase', ['failed', 'published', 'capacity', 'suspended'])
def test_report_rotation_preserves_required_original_until_durable_acknowledgement(
        tmp_path, monkeypatch, route, phase):
    history = required_report_history(tmp_path, monkeypatch, phase)
    rotate = retirement_history_route(history, monkeypatch, route)
    before = (history.store.path / 'current.json').read_bytes()
    charge = next(item for entry in [*json.loads(before)['history'], json.loads(before)]
                  for item in entry.get('captures', []))
    assert 'acknowledgement' not in charge
    originals = {path: (path.stat().st_dev, path.stat().st_ino, path.read_bytes())
                 for path in history.source.iterdir()}
    with pytest.raises(ValueError, match='capture|acknowledgement'):
        rotate()
    assert (history.store.path / 'current.json').read_bytes() == before
    for path, original in originals.items():
        assert (path.stat().st_dev, path.stat().st_ino, path.read_bytes()) == original

    # Simulated capacity is only a retirement input; finish the exact recorded
    # publication and owner acknowledgement using the original source usage.
    with monkeypatch.context() as local:
        if route != 'ordinary':
            local.setattr(history.retention, 'allocation_bytes', history.allocation_bytes)
        receipt = history.publish()
        history.capture.acknowledge_capture(
            history.checkout, os.geteuid(), os.getegid(), charge['capture_id'],
            expected=history.request['request_sha256'])
    rotate()
    assert not history.source.exists()
    assert not Path(charge['path']).exists()
    for _ in range(4):
        with history.store.session():
            pass
    assert_complete_report(history, receipt)
    state = json.loads((history.store.path / 'current.json').read_bytes())
    assert not any(entry.get('captures') for entry in [*state['history'], state])


@pytest.mark.parametrize('route', ['ordinary', 'host', 'privileged'])
@pytest.mark.parametrize('change', ['missing-destination', 'replaced-destination',
                                    'wrong-attempt', 'wrong-closure'])
def test_stale_owner_acknowledgement_cannot_release_required_report(
        tmp_path, monkeypatch, route, change):
    history = required_report_history(tmp_path, monkeypatch, 'acknowledged')
    if change.endswith('destination'):
        archive = Path(history.receipt['path'])
        archive.rename(archive.with_name('original-evidence.zip'))
        if change == 'replaced-destination':
            archive.write_bytes(b'foreign replacement must survive\n')
            archive.chmod(0o600)
    else:
        with history.store.opened() as fd, history.store.locked(fd, 'writer.lock'):
            state = history.store.read(fd)
            acknowledgement = state['captures'][0]['acknowledgement']
            if change == 'wrong-attempt':
                acknowledgement['request']['record']['context']['attempt'] = 'f' * 32
            else:
                acknowledgement['request']['record']['members'].pop()
            history.store.save(fd, state)
    rotate = retirement_history_route(history, monkeypatch, route)
    before = (history.store.path / 'current.json').read_bytes()
    with pytest.raises(ValueError, match='capture|acknowledgement'):
        rotate()
    assert (history.store.path / 'current.json').read_bytes() == before
    for role, payload in history.payloads.items():
        assert (history.source / f'{role}.json').read_bytes() == payload
    if change == 'replaced-destination':
        assert archive.read_bytes() == b'foreign replacement must survive\n'


@pytest.mark.parametrize('route', ['ordinary', 'host', 'privileged'])
@pytest.mark.parametrize('replace_remaining', [False, True])
def test_required_report_partial_retirement_keeps_exact_remaining_identity(
        tmp_path, monkeypatch, route, replace_remaining):
    history = required_report_history(tmp_path, monkeypatch, 'acknowledged')
    rotate = retirement_history_route(history, monkeypatch, route)
    before = (history.store.path / 'current.json').read_bytes()
    original_record = next(record for _, record in history.retention.latest_allocations(
        [*json.loads(before)['history'], json.loads(before)])
        if record['path'] == str(history.source))
    remove = history.retention.remove
    failed = False
    def interrupted(record, *, validate_only=False):
        nonlocal failed
        if record == original_record and not validate_only and not failed:
            failed = True
            (history.source / 'command.json').unlink()
            raise SimulatedInterrupt('fixture partially retired one original allocation')
        return remove(record, validate_only=validate_only)
    with monkeypatch.context() as local:
        local.setattr(history.retention, 'remove', interrupted)
        with pytest.raises(SimulatedInterrupt):
            rotate()
    assert failed and history.source.is_dir()
    assert (history.store.path / 'current.json').read_bytes() == before
    assert (history.source / 'result.json').read_bytes() == history.payloads['result']
    if replace_remaining:
        saved = history.source.with_name('owned-remaining-original')
        history.source.rename(saved)
        history.source.mkdir(mode=0o700)
        (history.source / 'foreign').write_bytes(b'foreign bytes\n')
        with pytest.raises(ValueError, match='replaced|capture|acknowledgement'):
            rotate()
        assert (history.source / 'foreign').read_bytes() == b'foreign bytes\n'
        assert (history.store.path / 'current.json').read_bytes() == before
        # Restore only the fixture-owned exact remaining allocation for recovery.
        (history.source / 'foreign').unlink()
        history.source.rmdir()
        saved.rename(history.source)
    rotate()
    assert not history.source.exists()
    assert_complete_report(history, history.receipt)


@pytest.mark.parametrize('operation', ['count', 'prune', 'reconcile', 'privileged-prune',
                                        'discard', 'unpublished'])
def test_pending_capture_refuses_each_source_retirement_route(tmp_path, monkeypatch, operation):
    store, paths = export_fixture(tmp_path)
    slot, _ = pending_capture(store, tmp_path, oldest=operation in ('count', 'prune', 'privileged-prune'))
    if operation == 'reconcile':
        monkeypatch.setattr(retention, 'MAX_RETAINED_BYTES', 1)
    before = (store.path / 'current.json').read_bytes()
    with pytest.raises(ValueError, match='capture'):
        if operation == 'count':
            with store.session():
                pytest.fail('count admission retired a required capture')
        elif operation in ('prune', 'privileged-prune'):
            with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False):
                # The privileged startup has this separate prune after reconcile.
                with store.retirement(fd) as authorize, store.locked(fd, 'writer.lock'):
                    store.prune(fd, store.read(fd), keep=2, authorize=authorize)
        elif operation == 'reconcile':
            store.reconcile(lambda: None, completed_guard=lambda _paths: None)
        elif operation == 'discard':
            store.discard_completed(lambda _paths: pytest.fail('capture refusal reached discard guard'))
        else:
            store.discard_unpublished_input(paths[-1])
    assert (store.path / 'current.json').read_bytes() == before
    assert all(path.is_dir() for path in paths) and slot.is_dir()


@pytest.mark.parametrize('resume', ['finish', 'publication', 'direct'])
def test_committed_recovery_checks_original_capture_before_any_retirement(tmp_path, resume):
    store, paths = export_fixture(tmp_path)
    with store.publication(projected_bytes=16384) as transaction:
        stage = publication_allocation(transaction, tmp_path)
        transaction.commit(defer_cleanup=True)
    with store.opened() as fd, store.locked(fd, 'writer.lock', publication=True):
        intent = retention.read_publication(store, fd)
        slot = tmp_path / 'capture-slot'
        slot.mkdir(mode=0o700)
        info = slot.stat()
        intent['original']['history'][0]['captures'] = [dict(
            capture_id='a' * 64, path=str(slot), device=info.st_dev,
            inode=info.st_ino, mode=0o700, reserved_bytes=0, intent={})]
        store.save(fd, intent, name=retention.PUBLICATION)
        replacement, _ = retention.publication_states(intent)
        store.save(fd, replacement)
    before = (store.path / 'current.json').read_bytes()
    with pytest.raises(ValueError, match='capture'):
        if resume == 'finish':
            store.finish_publication()
        elif resume == 'publication':
            with store.publication(projected_bytes=0):
                pytest.fail('recovery retired a pending source')
        else:
            with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False):
                with store.locked(fd, 'writer.lock', publication=True):
                    retention.recover_publication(store, fd)
    assert all(path.is_dir() for path in paths) and stage.is_dir() and slot.is_dir()
    assert (store.path / 'current.json').read_bytes() == before
    assert (store.path / retention.PUBLICATION).is_file()


def test_publication_history_preserves_unretired_capture_charge(tmp_path):
    store, _ = export_fixture(tmp_path)
    _, charge = pending_capture(store, tmp_path)
    with store.publication(projected_bytes=16384) as transaction:
        publication_allocation(transaction, tmp_path)
        transaction.commit(defer_cleanup=True)
    state = json.loads((store.path / 'current.json').read_text())
    assert state['history'][-1]['captures'] == [charge]
    assert store.finish_publication()
    assert json.loads((store.path / 'current.json').read_text())['history'][-1]['captures'] == [charge]


def test_acknowledged_retirement_keeps_proof_pinned_until_exact_cleanup_and_save(
        tmp_path, monkeypatch):
    from contextlib import contextmanager
    store, paths = export_fixture(tmp_path)
    slot, charge = pending_capture(store, tmp_path, oldest=True)
    held = False
    selected = []
    @contextmanager
    def retirement_scope(fd):
        nonlocal held
        # A destination verification scope must start before the source writer.
        with store.locked(fd, 'writer.lock', blocking=False):
            pass
        held = True
        def authorize(entries, *, cleanup=False):
            assert held
            charges = [item for entry in entries for item in entry.get('captures', [])]
            assert charges == [charge]
            selected.append(cleanup)
            if cleanup:
                assert not paths[0].exists()
                # The old journal keeps the claim until cleanup has succeeded.
                assert json.loads((store.path / 'current.json').read_text())['history'][0]['captures'] == [charge]
                retention.remove(charge)
        try:
            yield authorize
        finally:
            held = False
    monkeypatch.setattr(store, 'retirement', retirement_scope)
    remove = retention.remove
    def pinned_remove(record, *, validate_only=False):
        if not validate_only:
            assert held
        return remove(record, validate_only=validate_only)
    monkeypatch.setattr(retention, 'remove', pinned_remove)
    with store.session():
        assert not paths[0].exists() and not slot.exists()
        assert all(path.exists() for path in paths[1:])
    assert selected == [False, True]
    assert not held


@pytest.mark.parametrize('phase', ['staging', 'committed'])
def test_resumable_publication_reuses_stage_and_defers_exact_retirement(tmp_path, phase):
    store, paths = export_fixture(tmp_path)
    with pytest.raises(SimulatedFailure):
        with store.publication(projected_bytes=16384, resumable=True) as transaction:
            stage = publication_allocation(transaction, tmp_path)
            if phase == 'committed':
                transaction.commit(defer_cleanup=True)
            recorded = json.loads((store.path / retention.PUBLICATION).read_text())
            raise SimulatedFailure('lost publication reply')
    assert all(path.exists() for path in paths) and stage.is_dir()
    factory = Mock(side_effect=AssertionError('retry allocated another stage'))
    with store.publication(projected_bytes=16384, resumable=True) as retried:
        assert retried.intent == recorded
        assert retried.original == recorded['original']
        if phase == 'staging':
            assert retried.allocate(factory) == stage
        else:
            assert retried.committing
        retried.commit(defer_cleanup=True)
        factory.assert_not_called()
        assert all(path.exists() for path in paths)
    assert (store.path / retention.PUBLICATION).is_file()
    assert store.finish_publication()
    assert not paths[0].exists() and all(path.exists() for path in paths[1:])
    assert stage.is_dir()


def test_resumable_publication_retry_counts_its_stage_once(tmp_path, monkeypatch):
    store, paths = export_fixture(tmp_path)
    with store.publication(projected_bytes=16384, resumable=True) as transaction:
        stage = publication_allocation(transaction, tmp_path)
    with store.opened() as fd:
        intent = retention.read_publication(store, fd)
    records = [record for _, record in retention.latest_allocations(
        [*intent['original']['history'], intent['original']])]
    usage = retention.publication_usage([*records, intent['staging']])
    monkeypatch.setattr(retention, 'MAX_RETAINED_BYTES', usage)
    with store.publication(projected_bytes=usage, resumable=True) as retried:
        assert retried.allocate(Mock()) == stage
        retried.commit(defer_cleanup=True)
    assert all(path.exists() for path in paths) and stage.is_dir()


@pytest.mark.parametrize('include_committed', [False, True])
def test_inspections_overlap_but_exclude_writers_until_last_reader_exits(
        tmp_path, include_committed):
    store, originals = export_fixture(tmp_path)
    journal = (store.path / 'current.json').read_bytes()
    peer = retention.Store(store.path)
    with store.inspection(include_committed=include_committed) as first:
        with peer.inspection(include_committed=include_committed) as second:
            assert first == second
            # Independent descriptors exercise the same flock conflicts as
            # separate artifact-reader processes, without timing or sleeps.
            for name in ('owner.lock', 'writer.lock'):
                with store.opened() as fd, pytest.raises(ValueError, match='another owner'):
                    with peer.locked(fd, name, blocking=False):
                        pytest.fail('writer admitted during overlapping inspection')
        with pytest.raises(ValueError, match='another owner'):
            with peer.publication(projected_bytes=0):
                pytest.fail('publication admitted before the last reader exited')
        assert all(path.exists() for path in originals)
        assert (store.path / 'current.json').read_bytes() == journal
    with peer.publication(projected_bytes=16384) as transaction:
        published = publication_allocation(transaction, tmp_path)
        transaction.commit()
    assert not originals[0].exists()
    assert published.exists() and all(path.exists() for path in originals[1:])


def test_publication_failure_preserves_three_exports_then_commit_rotates(tmp_path):
    store, originals = export_fixture(tmp_path)
    original = (store.path / 'current.json').read_bytes()
    with pytest.raises(SimulatedFailure):
        with store.publication(projected_bytes=16384) as transaction:
            staging = publication_allocation(transaction, tmp_path)
            assert (store.path / retention.PUBLICATION).is_file()
            assert (store.path / 'current.json').read_bytes() == original
            assert all(path.exists() for path in originals)
            raise SimulatedFailure
    assert not staging.exists()
    assert (store.path / 'current.json').read_bytes() == original
    assert all((path / 'test.log').read_bytes() == b'evidence' * 128 for path in originals)
    with store.publication(projected_bytes=16384) as transaction:
        published = publication_allocation(transaction, tmp_path)
        transaction.commit()
    assert not originals[0].exists()
    assert all(path.exists() for path in originals[1:])
    assert (published / 'bundle.zip').read_bytes() == b'verified bundle bytes'
    assert not (store.path / retention.PUBLICATION).exists()
    with store.inspection() as state:
        assert len(state['history']) == 2 and state['paths'][0]['path'] == str(published)


@pytest.mark.parametrize('boundary', ['precommit', 'journal', 'retirement'])
def test_publication_recovers_durable_intent_without_losing_exports(tmp_path, monkeypatch, boundary):
    store, originals = export_fixture(tmp_path)
    journal = (store.path / 'current.json').read_bytes()
    save, remove = store.save, retention.remove
    interrupted = False
    def save_fault(fd, value, *, name='current.json'):
        nonlocal interrupted
        if boundary == 'journal' and name == 'current.json' and not interrupted:
            interrupted = True
            raise SimulatedInterrupt
        return save(fd, value, name=name)
    def remove_fault(record, *, validate_only=False):
        nonlocal interrupted
        should_fail = (boundary == 'precommit' and record['path'] not in {str(p) for p in originals}
                       or boundary == 'retirement' and record['path'] == str(originals[0]))
        if not validate_only and should_fail and not interrupted:
            interrupted = True
            raise SimulatedInterrupt
        return remove(record, validate_only=validate_only)
    monkeypatch.setattr(store, 'save', save_fault)
    monkeypatch.setattr(retention, 'remove', remove_fault)
    with pytest.raises(SimulatedInterrupt):
        with store.publication(projected_bytes=16384) as transaction:
            staging = publication_allocation(transaction, tmp_path)
            if boundary != 'precommit':
                transaction.commit()
    assert (store.path / retention.PUBLICATION).exists()
    if boundary in ('precommit', 'journal'):
        assert (store.path / 'current.json').read_bytes() == journal
        assert all(path.exists() for path in originals)
    with pytest.raises(ValueError, match='publication pending'):
        with store.session():
            pytest.fail('ordinary session accepted pending publication')
    with pytest.raises(ValueError, match='publication pending'):
        with store.inspection():
            pytest.fail('inspection accepted pending publication')
    with store.publication(projected_bytes=0):
        pass
    assert not (store.path / retention.PUBLICATION).exists()
    assert staging.exists() == (boundary != 'precommit')
    assert originals[0].exists() == (boundary == 'precommit')
    assert all(path.exists() for path in originals[1:])


@pytest.mark.parametrize('fault', ['replacement', 'owner', 'symlink', 'hardlink', 'mount', 'nested-mount', 'file-mount'])
def test_publication_audits_all_existing_exports_before_allocation(tmp_path, monkeypatch, fault):
    store, originals = export_fixture(tmp_path)
    journal = (store.path / 'current.json').read_bytes()
    victim = originals[0]
    if fault == 'replacement':
        victim.rename(tmp_path / 'original-export')
        victim.mkdir(mode=0o700)
    elif fault == 'owner':
        os.chmod(victim, 0o755)
    elif fault == 'symlink':
        (victim / 'link').symlink_to(originals[1] / 'test.log')
    elif fault == 'hardlink':
        os.link(victim / 'test.log', victim / 'second-link')
    else:
        mounted = (victim if fault == 'mount' else victim / 'test.log'
                   if fault == 'file-mount' else victim / 'nested')
        if fault == 'nested-mount':
            mounted.mkdir(mode=0o700)
        mount_id = retention.mount_id
        def fake_mount(fd):
            return 'fixture-mount' if Path(os.readlink(f'/proc/self/fd/{fd}')) == mounted else mount_id(fd)
        monkeypatch.setattr(retention, 'mount_id', fake_mount)
    with pytest.raises((ValueError, OSError)):
        with store.publication(projected_bytes=0):
            pytest.fail('unsafe existing export accepted')
    assert (store.path / 'current.json').read_bytes() == journal
    assert all(path.exists() for path in originals)


@pytest.mark.parametrize('when', ['entry', 'commit'])
def test_publication_budget_preserves_original_journal_and_all_exports(tmp_path, monkeypatch, when):
    store, originals = export_fixture(tmp_path)
    journal = (store.path / 'current.json').read_bytes()
    original_size = sum(retention.allocation_bytes(record) for _, record in
                        retention.latest_allocations([*json.loads(journal)['history'], json.loads(journal)]))
    monkeypatch.setattr(retention, 'MAX_RETAINED_BYTES', original_size + 8192)
    with pytest.raises(ValueError, match='publication exceeds'):
        with store.publication(projected_bytes=16384 if when == 'entry' else 0) as transaction:
            staging = publication_allocation(transaction, tmp_path)
            (staging / 'bundle.zip').write_bytes(b'x' * 32768)
            transaction.commit()
    assert (store.path / 'current.json').read_bytes() == journal
    assert all(path.exists() for path in originals)
    assert not (store.path / retention.PUBLICATION).exists()


def test_publication_registers_empty_allocation_before_return_and_holds_locks(tmp_path):
    store, originals = export_fixture(tmp_path)
    with store.publication(projected_bytes=16384) as transaction:
        staging = transaction.allocate(tempfile.mkdtemp, prefix='export-', dir=str(tmp_path))
        intent = json.loads((store.path / retention.PUBLICATION).read_text())
        assert intent['staging']['path'] == str(staging)
        assert intent['staging']['inode'] == staging.stat().st_ino
        assert list(staging.iterdir()) == []
        with pytest.raises(ValueError, match='another owner'):
            with store.inspection():
                pass
        with pytest.raises(ValueError, match='one allocation'):
            transaction.allocate(tempfile.mkdtemp, dir=str(tmp_path))
    assert not staging.exists() and all(path.exists() for path in originals)
    with pytest.raises(ValueError, match='no uncommitted'):
        transaction.commit()


def test_publication_refuses_an_inherited_execution_token(tmp_path, monkeypatch):
    store, originals = export_fixture(tmp_path)
    journal = (store.path / 'current.json').read_bytes()
    monkeypatch.setenv(retention.VARIABLE, json.dumps([str(store.path), 'a' * 32]))
    with pytest.raises(ValueError, match='independent owner'):
        with store.publication(projected_bytes=0):
            pytest.fail('publication accepted an execution owner')
    assert (store.path / 'current.json').read_bytes() == journal
    assert all(path.exists() for path in originals)


@pytest.mark.parametrize('replace', ['staging', 'retirement'])
def test_publication_recovery_refuses_replaced_staging_and_retirement(tmp_path, monkeypatch, replace):
    store, originals = export_fixture(tmp_path)
    remove = retention.remove
    def interrupt(record, *, validate_only=False):
        if not validate_only:
            raise SimulatedInterrupt
        return remove(record, validate_only=validate_only)
    monkeypatch.setattr(retention, 'remove', interrupt)
    with pytest.raises(SimulatedInterrupt):
        with store.publication(projected_bytes=16384) as transaction:
            staging = publication_allocation(transaction, tmp_path)
            transaction.commit()
    monkeypatch.setattr(retention, 'remove', remove)
    journal = (store.path / 'current.json').read_bytes()
    victim = staging if replace == 'staging' else originals[0]
    victim.rename(tmp_path / 'displaced-export')
    victim.mkdir(mode=0o700)
    (victim / 'keep').write_text('replacement')
    with pytest.raises(ValueError, match='replaced'):
        with store.publication(projected_bytes=0):
            pass
    assert (store.path / 'current.json').read_bytes() == journal
    assert (victim / 'keep').read_text() == 'replacement'
    assert staging.exists() and (store.path / retention.PUBLICATION).exists()


def test_deferred_publication_is_durable_inspectable_and_finishes_exact_retirement(tmp_path):
    store, originals = export_fixture(tmp_path)
    with store.publication(projected_bytes=16384) as transaction:
        staging = publication_allocation(transaction, tmp_path)
        transaction.commit(defer_cleanup=True)
    assert all(path.exists() for path in originals)
    assert staging.exists() and (store.path / retention.PUBLICATION).is_file()
    with pytest.raises(ValueError, match='publication pending'):
        with store.inspection():
            pass
    with store.inspection(include_committed=True) as state:
        assert state['paths'][0]['path'] == str(staging)
        assert all(path.exists() for path in originals)
    assert store.finish_publication()
    assert not store.finish_publication()
    assert not originals[0].exists()
    assert all(path.exists() for path in originals[1:]) and staging.exists()
    assert not (store.path / retention.PUBLICATION).exists()


def test_deferred_finish_and_inspection_refuse_uncommitted_staging(tmp_path, monkeypatch):
    store, originals = export_fixture(tmp_path)
    remove = retention.remove
    def interrupted(record, *, validate_only=False):
        if not validate_only:
            raise SimulatedInterrupt
        return remove(record, validate_only=validate_only)
    monkeypatch.setattr(retention, 'remove', interrupted)
    with pytest.raises(SimulatedInterrupt):
        with store.publication(projected_bytes=16384) as transaction:
            staging = publication_allocation(transaction, tmp_path)
    with pytest.raises(ValueError, match='not committed'):
        store.finish_publication()
    with pytest.raises(ValueError, match='not durably committed'):
        with store.inspection(include_committed=True):
            pass
    assert staging.exists() and all(path.exists() for path in originals)


@pytest.mark.parametrize('resume', ['finish', 'publication'])
@pytest.mark.parametrize('corruption', ['changed', 'missing'])
def test_committed_publication_verifies_payload_before_retirement_and_retries(
        tmp_path, resume, corruption):
    store, originals = export_fixture(tmp_path)
    expected = b'verified bundle bytes'
    calls = []
    def verify(record):
        calls.append(record['path'])
        assert (Path(record['path']) / 'bundle.zip').read_bytes() == expected, 'corrupt bundle'
    with store.publication(projected_bytes=16384, verify=verify) as transaction:
        stage = publication_allocation(transaction, tmp_path)
        transaction.commit(defer_cleanup=True)
    assert calls and set(calls) == {str(stage)}
    original = (store.path / 'current.json').read_bytes()
    payload = stage / 'bundle.zip'
    if corruption == 'changed':
        payload.write_bytes(b'corrupted payload')
    else:
        payload.unlink()
    def recover():
        if resume == 'finish':
            store.finish_publication(verify=verify)
        else:
            with store.publication(projected_bytes=0, verify=verify):
                pass
    with pytest.raises((AssertionError, FileNotFoundError)):
        recover()
    assert (store.path / 'current.json').read_bytes() == original
    assert all(path.exists() for path in originals)
    assert (store.path / retention.PUBLICATION).is_file()
    payload.write_bytes(expected)
    recover()
    assert not originals[0].exists()
    assert all(path.exists() for path in originals[1:]) and payload.read_bytes() == expected
    assert not (store.path / retention.PUBLICATION).exists()


def test_initial_publication_verification_refusal_preserves_journal_and_exports(tmp_path):
    store, originals = export_fixture(tmp_path)
    original = (store.path / 'current.json').read_bytes()
    expected = b'required verified payload'
    def refuse(record):
        if (Path(record['path']) / 'bundle.zip').read_bytes() != expected:
            raise SimulatedFailure('bundle verification refused')
    with pytest.raises(SimulatedFailure, match='verification refused'):
        with store.publication(projected_bytes=16384, verify=refuse) as transaction:
            stage = publication_allocation(transaction, tmp_path)
            transaction.commit()
    assert not stage.exists() and all(path.exists() for path in originals)
    assert (store.path / 'current.json').read_bytes() == original
    assert not (store.path / retention.PUBLICATION).exists()
    with store.publication(projected_bytes=16384, verify=refuse) as transaction:
        retried = publication_allocation(transaction, tmp_path)
        (retried / 'bundle.zip').write_bytes(expected)
        transaction.commit()
    assert not originals[0].exists() and retried.exists()


@pytest.mark.parametrize('resume', ['finish', 'publication'])
def test_committed_publication_recovery_refuses_grown_aggregate_before_retirement(
        tmp_path, monkeypatch, resume):
    store, originals = export_fixture(tmp_path)
    with store.publication(projected_bytes=16384) as transaction:
        stage = publication_allocation(transaction, tmp_path)
        transaction.commit(defer_cleanup=True)
    original = (store.path / 'current.json').read_bytes()
    intent = json.loads((store.path / retention.PUBLICATION).read_text())
    records = [record for _, record in retention.latest_allocations(
        [*intent['original']['history'], intent['original']])]
    usage = retention.publication_usage([*records, intent['staging']])
    with monkeypatch.context() as limited:
        limited.setattr(retention, 'MAX_RETAINED_BYTES', usage - 1)
        with pytest.raises(ValueError, match='publication exceeds'):
            if resume == 'finish':
                store.finish_publication()
            else:
                with store.publication(projected_bytes=0):
                    pass
    assert (store.path / 'current.json').read_bytes() == original
    assert all(path.exists() for path in originals) and stage.exists()
    assert (store.path / retention.PUBLICATION).is_file()
    assert store.finish_publication()
    assert not originals[0].exists() and stage.exists()


def test_preparing_publication_recovery_can_remove_only_its_oversized_staging(tmp_path, monkeypatch):
    store, originals = export_fixture(tmp_path)
    original = (store.path / 'current.json').read_bytes()
    state = json.loads(original)
    records = [record for _, record in retention.latest_allocations([*state['history'], state])]
    original_size = retention.publication_usage(records)
    remove = retention.remove
    def interrupt(record, *, validate_only=False):
        if not validate_only:
            raise SimulatedInterrupt
        return remove(record, validate_only=validate_only)
    with monkeypatch.context() as interrupted:
        interrupted.setattr(retention, 'remove', interrupt)
        with pytest.raises(SimulatedInterrupt):
            with store.publication(projected_bytes=16384) as transaction:
                stage = publication_allocation(transaction, tmp_path)
    (stage / 'bundle.zip').write_bytes(b'x' * 32768)
    monkeypatch.setattr(retention, 'MAX_RETAINED_BYTES', original_size + 8192)
    with store.publication(projected_bytes=0):
        pass
    assert not stage.exists() and all(path.exists() for path in originals)
    assert (store.path / 'current.json').read_bytes() == original
    assert not (store.path / retention.PUBLICATION).exists()


@pytest.mark.parametrize('fault', [None, 'active', 'guard', 'replaced', 'marker-link'])
def test_idle_reconciliation_preserves_evidence_and_refuses_unsafe_recovery(tmp_path, fault):
    store = retention.Store(tmp_path / 'state')
    with store.session() as run:
        evidence = allocated(tmp_path, 'evidence')
        retention.preserve_for_recovery()
    original = (store.path / 'current.json').read_bytes()
    marker = store.path / 'recovery-required'
    if fault == 'replaced':
        evidence.rename(tmp_path / 'original')
        evidence.mkdir(mode=0o700)
    if fault == 'marker-link':
        marker.rename(tmp_path / 'marker')
        marker.symlink_to(tmp_path / 'marker')
    def guard():
        if fault == 'guard':
            raise ValueError('VM recovery refused')
    if fault == 'active':
        with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False):
            with pytest.raises(ValueError, match='another owner'):
                store.reconcile(guard)
    elif fault:
        with pytest.raises(ValueError):
            store.reconcile(guard)
    else:
        assert store.reconcile(guard)
        assert not store.reconcile(guard)
        assert (store.path / f'recovered-{run}.json').read_bytes() == original
        assert not marker.exists()
        assert json.loads((store.path / 'current.json').read_text())['finished']
        assert (evidence / 'test.log').exists()
        # Recovered allocations still participate in bounded normal retention.
        advance_to_expiry(store)
        with store.session():
            pass
        assert not evidence.exists()
    if fault:
        assert (store.path / 'current.json').read_bytes() == original
        assert marker.exists()
        assert evidence.exists()


@pytest.fixture
def dispatcher_vm(monkeypatch):
    """Keep VM selection process-local while exercising real argument parsing."""
    import vm_config
    name = 'fixture-vm'
    def select(selected, path):
        assert selected == name
        return SimpleNamespace(name=name)
    monkeypatch.setattr(vm_config, 'select', select)
    return name


@pytest.fixture
def retention_vm(tmp_path, monkeypatch):
    """Keep controller checkout locks away from the host VM coordinator."""
    import vm_pool
    monkeypatch.setattr(vm_pool, 'RUNTIME', tmp_path / 'pool')
    monkeypatch.delenv(vm_pool.VARIABLE, raising=False)
    return 'f95890e1-88e7-4779-8ae3-53fdcc34330a'


@pytest.mark.parametrize('status', [0, 1])
@pytest.mark.parametrize('selected', ['check_test_recovery', 'check_retained_runs_cleanup'])
def test_unattended_recovery_does_not_launch_tests(tmp_path, monkeypatch, capsys, status, dispatcher_vm, selected):
    import test_storage
    monkeypatch.setattr(test_storage, 'privileged_state', lambda uid: tmp_path / 'privileged-state')
    dispatcher = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'tools/onpc-test-runner'))
    dispatcher['run'].__globals__['selection'] = lambda *args: ['recovery']
    commands = []
    def execute(command, **kwargs):
        output = capsys.readouterr().out
        assert 'cleanup prerequisites' not in output
        assert command == ['recovery']
        assert kwargs['env']['ONPC_TEST_VM'] == dispatcher_vm
        commands.append(command)
        return status
    control = SimpleNamespace(run=execute, installed=lambda **kw: nullcontext(control))
    monkeypatch.setattr(dispatcher['runpy'], 'run_path', lambda path: {
        'Control': lambda: control, 'safety_command': lambda root: ['safety']})
    dispatcher['run'].__globals__['confined_file'] = lambda *args: tmp_path / 'control'
    monkeypatch.setattr(dispatcher['os'], 'getgrouplist', lambda *args: [])
    caller = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name='fixture',
                             pw_dir=str(tmp_path))
    assert dispatcher['run'](tmp_path, [
        '--unattended', 'integration', selected, '--vm', dispatcher_vm,
    ], caller) == status
    assert commands == [['recovery']]


def test_direct_discard_dispatch_does_not_enter_retention(tmp_path, monkeypatch, dispatcher_vm):
    import test_storage
    import test_retention
    dispatcher = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'tools/onpc-test-runner'))
    dispatcher['run'].__globals__['selection'] = lambda *args: ['discard']
    monkeypatch.setattr(test_storage, 'privileged_state', lambda uid: tmp_path / 'state')
    monkeypatch.setattr(test_retention.Store, 'session',
                        lambda *args, **kwargs: pytest.fail('cleanup entered retention rotation'))
    calls = []
    def execute(command, **kwargs):
        calls.append(command)
        assert kwargs['env']['ONPC_TEST_VM'] == dispatcher_vm
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(dispatcher['subprocess'], 'run', execute)
    caller = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name='fixture', pw_dir=str(tmp_path))
    assert dispatcher['run'](tmp_path, ['integration', 'check_retained_runs_cleanup',
                                      '--vm', dispatcher_vm], caller) == 0
    assert calls == [['discard']]


@pytest.mark.parametrize('pending', [False, True])
@pytest.mark.parametrize('fault', [None, 'guard', 'active', 'replaced', 'live', 'interrupted'])
def test_execution_recovery_retires_only_verified_oversized_evidence(
        tmp_path, monkeypatch, capsys, pending, fault):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        first = allocated(tmp_path, 'first')
        second = allocated(tmp_path, 'second')
        if pending:
            retention.preserve_for_recovery()
    unknown = tmp_path / 'unknown'
    unknown.mkdir()
    (unknown / 'keep').write_text('unregistered')
    original = (store.path / 'current.json').read_bytes()
    monkeypatch.setattr(retention, 'MAX_RETAINED_BYTES', 1)
    if fault == 'replaced':
        second.rename(tmp_path / 'original')
        second.mkdir(mode=0o700)
        (second / 'keep').write_text('replacement')
    calls = []
    held = False
    from contextlib import contextmanager
    @contextmanager
    def lease():
        nonlocal held
        held = True
        try:
            yield
        finally:
            held = False
    def guard():
        calls.append('recover')
        if fault == 'guard':
            raise ValueError('recovery failed')
    def unused(paths):
        assert held and paths == {str(first), str(second)}
        calls.append('audit')
        if fault == 'live':
            raise ValueError('live reference')
    remove = retention.remove
    interrupted = False
    def retire(record, *, validate_only=False):
        nonlocal interrupted
        if not validate_only:
            assert held
            if fault == 'interrupted' and record['path'] == str(second) and not interrupted:
                interrupted = True
                raise KeyboardInterrupt
        return remove(record, validate_only=validate_only)
    monkeypatch.setattr(retention, 'remove', retire)
    def recover():
        return store.reconcile(guard, completed_guard=unused, lease=lease)
    if fault == 'active':
        with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False):
            with pytest.raises(ValueError, match='another owner'):
                recover()
        assert calls == []
    elif fault:
        with pytest.raises(KeyboardInterrupt if fault == 'interrupted' else ValueError):
            recover()
    else:
        assert recover() == pending
    assert not held
    if fault in ('active', 'guard', 'replaced'):
        assert first.exists() and second.exists()
        assert (store.path / 'current.json').read_bytes() == original
    elif fault == 'live':
        assert first.exists() and second.exists()
    if fault == 'interrupted':
        assert not first.exists() and second.exists()
        # Records survive partial removal; retry validates the original second
        # allocation and completes without adopting unrelated storage.
        assert len(json.loads((store.path / 'current.json').read_text())['paths']) == 2
        recover()
    if fault in (None, 'interrupted'):
        assert not first.exists() and not second.exists()
        assert json.loads((store.path / 'current.json').read_text())['paths'] == []
        assert 'Retired oversized completed test evidence' in capsys.readouterr().out
        with store.session():
            pass
    assert (unknown / 'keep').read_text() == 'unregistered'


def test_execution_recovery_keeps_completed_evidence_within_budget(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        evidence = allocated(tmp_path, 'evidence')
    audit = Mock()
    assert not store.reconcile(lambda: None, completed_guard=audit)
    audit.assert_not_called()
    assert (evidence / 'test.log').is_file()


def test_host_preflight_automatically_retires_oversized_completed_evidence(tmp_path, monkeypatch):
    import test_recovery
    import test_retention as live_retention
    import regression_process
    store = live_retention.Store(tmp_path / 'state')
    with store.session():
        path = tmp_path / 'evidence'
        path.mkdir(mode=0o700)
        (path / 'result').write_text('saved failure')
        live_retention.retain(path)
    monkeypatch.setattr(live_retention, 'MAX_RETAINED_BYTES', 1)
    monkeypatch.setattr(test_recovery.test_activity, 'activity', lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(test_recovery.test_activity, 'retention_path', lambda root: store.path)
    monkeypatch.setattr(regression_process, 'category_run',
                        lambda *args, **kwargs: pytest.fail('host recovery touched the VM'))
    assert test_recovery.cleanup_host(tmp_path) == 0
    assert not path.exists()
    with store.session():
        pass


@pytest.mark.parametrize('fault', [None, 'busy', 'recovery', 'live'])
def test_privileged_preflight_retires_oversized_run_under_vm_leases(tmp_path, monkeypatch, fault):
    import check_test_recovery as recovery
    from contextlib import contextmanager
    store = recovery.test_retention.Store(tmp_path / 'state')
    with store.session():
        path = tmp_path / 'evidence'
        path.mkdir(mode=0o700)
        (path / 'result').write_text('saved failure')
        recovery.test_retention.retain(path)
    monkeypatch.setattr(recovery.test_retention, 'MAX_RETAINED_BYTES', 1)
    monkeypatch.setattr(recovery, 'ROOT', Path.cwd())
    monkeypatch.setattr(recovery, 'os', SimpleNamespace(geteuid=lambda: 0,
                                                      environ={'PKEXEC_UID': '1000'}))
    monkeypatch.setattr(recovery.sys, 'argv', ['check_test_recovery'])
    import test_storage
    monkeypatch.setattr(test_storage, 'privileged_state', lambda uid: store.path)
    held = False
    def reconcile(root):
        if fault == 'recovery':
            raise ValueError('VM recovery failed')
    monkeypatch.setattr(recovery, 'reconcile_vm', reconcile)
    @contextmanager
    def lease(root):
        nonlocal held
        if fault == 'busy':
            raise BlockingIOError('VM busy')
        held = True
        try:
            yield
        finally:
            held = False
    monkeypatch.setattr(recovery.runpy, 'run_path', lambda path: {'retention_lease': lease})
    def unused(paths):
        assert held and paths == {str(path)}
        if fault == 'live':
            raise ValueError('live reference')
    monkeypatch.setattr(recovery, 'unused', unused)
    remove = recovery.test_retention.remove
    def retire(record, *, validate_only=False):
        assert held
        return remove(record, validate_only=validate_only)
    monkeypatch.setattr(recovery.test_retention, 'remove', retire)
    if fault:
        with pytest.raises((ValueError, BlockingIOError)):
            recovery.main()
        assert (path / 'result').read_text() == 'saved failure'
    else:
        assert recovery.main() == 0
        assert not path.exists()
    assert not held


def test_explicit_discard_reclaims_oversized_finished_run_and_history(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        old = allocated(tmp_path, 'old')
    with store.session():
        current = allocated(tmp_path, 'current')
    unknown = tmp_path / 'unknown'
    unknown.mkdir()
    (unknown / 'keep').write_text('unregistered')
    original = (store.path / 'current.json').read_bytes()
    monkeypatch.setattr(retention, 'MAX_RETAINED_BYTES', 1)
    with pytest.raises(ValueError, match='exceeds 4 GiB'):
        with store.session():
            pytest.fail('oversized result accepted')
    # Normal pruning may retire history before reporting the current refusal.
    journal = (store.path / 'current.json').read_bytes()
    guards = []
    assert store.discard_completed(lambda paths: guards.append(paths)) == 1
    assert guards == [{str(current)}]
    assert not current.exists() and not old.exists()
    assert (store.path / 'current.json').read_bytes() == journal
    assert (unknown / 'keep').read_text() == 'unregistered'
    assert store.discard_completed(lambda paths: None) == 1
    with store.session():
        pass
    assert original != journal


@pytest.mark.parametrize('fault', ['unfinished', 'marked', 'active', 'replaced', 'symlink', 'mount', 'live'])
def test_explicit_discard_audits_every_allocation_before_deletion(tmp_path, monkeypatch, fault):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        first = allocated(tmp_path, 'first')
        second = allocated(tmp_path, 'second')
        if fault == 'unfinished':
            retention.preserve_for_recovery()
    if fault == 'unfinished':
        (store.path / 'recovery-required').unlink()
    if fault == 'marked':
        (store.path / 'recovery-required').touch(mode=0o600)
    if fault in ('replaced', 'symlink'):
        second.rename(tmp_path / 'original')
        if fault == 'symlink':
            second.symlink_to(tmp_path / 'original', target_is_directory=True)
        else:
            second.mkdir(mode=0o700)
            (second / 'keep').write_text('foreign')
    if fault == 'mount':
        original_mount = retention.mount_id
        monkeypatch.setattr(retention, 'mount_id', lambda fd:
                            'foreign' if Path(os.readlink(f'/proc/self/fd/{fd}')) == second else original_mount(fd))
    journal = (store.path / 'current.json').read_bytes()
    def guard(paths):
        if fault == 'live':
            raise ValueError('live reference')
    if fault == 'active':
        with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False):
            with pytest.raises(ValueError, match='another owner'):
                store.discard_completed(guard)
    else:
        with pytest.raises((ValueError, OSError)):
            store.discard_completed(guard)
    assert (first / 'test.log').exists()
    assert second.exists()
    assert (store.path / 'current.json').read_bytes() == journal


def test_explicit_discard_retries_partial_deletion_and_uses_latest_registration(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        recreated = allocated(tmp_path, 'recreated')
        first = allocated(tmp_path, 'first')
    recreated.rename(tmp_path / 'original')
    with store.session():
        recreated = allocated(tmp_path, 'recreated')
        last = allocated(tmp_path, 'last')
    journal = (store.path / 'current.json').read_bytes()
    remove = retention.remove
    def interrupted(record, *, validate_only=False):
        if record['path'] == str(last) and not validate_only:
            raise OSError('interrupted deletion')
        return remove(record, validate_only=validate_only)
    monkeypatch.setattr(retention, 'remove', interrupted)
    with pytest.raises(OSError, match='interrupted deletion'):
        store.discard_completed(lambda paths: None)
    assert not recreated.exists() and not first.exists()
    assert last.exists() and (tmp_path / 'original/test.log').exists()
    assert (store.path / 'current.json').read_bytes() == journal
    monkeypatch.setattr(retention, 'remove', remove)
    assert store.discard_completed(lambda paths: None) == 3
    assert not last.exists()
    assert (store.path / 'current.json').read_bytes() == journal


@pytest.mark.parametrize('failed', [False, True])
def test_discard_keeps_vm_and_compatibility_leases_through_removal(tmp_path, monkeypatch, failed, retention_vm):
    import prepare_baseline as baseline
    import vm_pool
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    directory = tmp_path / 'named-vm'
    directory.mkdir(mode=0o700)
    monkeypatch.setattr(baseline, 'BASELINES', directory)
    monkeypatch.setattr(baseline.guest_contract.vm_config, 'STATE_ROOT', tmp_path)
    (directory / 'phase.json').write_text(json.dumps(
        dict(phase='finalized', source=dict(layout=dict(uuid=retention_vm)))))
    (directory / 'phase.json').chmod(0o600)
    store = retention.Store(tmp_path / 'state')
    with store.session():
        evidence = allocated(tmp_path, 'evidence')
    locks = (directory / '.lock', tmp_path / '.lock', vm_pool.RUNTIME / (retention_vm + '.lock'))
    def guarded(paths):
        for path in locks:
            with path.open('rb') as lock:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if failed:
            raise ValueError('guard refused')
    try:
        with dispatcher['retention_lease'](root):
            store.discard_completed(guarded)
    except ValueError as error:
        assert failed and str(error) == 'guard refused'
    assert evidence.exists() == failed
    for path in locks:
        with path.open('rb') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


@pytest.mark.parametrize('failed', [False, True])
def test_privileged_discard_preserves_evidence_when_recovery_fails(tmp_path, monkeypatch, failed):
    import check_retained_runs_cleanup as cleanup
    calls = []
    def recover(root):
        calls.append('recover')
        if failed:
            raise ValueError('recovery failed')
    monkeypatch.setattr(cleanup.check_test_recovery, 'reconcile_vm', recover)
    lease = Mock(return_value=nullcontext())
    monkeypatch.setattr(cleanup.runpy, 'run_path', lambda path: {'retention_lease': lease})
    monkeypatch.setattr(cleanup.os, 'geteuid', lambda: 0)
    monkeypatch.setenv('PKEXEC_UID', '1000')
    monkeypatch.setattr(cleanup.sys, 'argv', ['check_retained_runs_cleanup'])
    monkeypatch.setattr(cleanup, 'ROOT', Path.cwd())
    monkeypatch.setattr(cleanup, 'privileged_state', lambda uid: tmp_path / 'selected-state')
    discard = Mock()
    monkeypatch.setattr(cleanup.test_retention, 'Store', lambda path: SimpleNamespace(discard_completed=discard))
    if failed:
        with pytest.raises(ValueError, match='recovery failed'):
            cleanup.main()
        lease.assert_not_called()
        discard.assert_not_called()
    else:
        assert cleanup.main() == 0
        lease.assert_called_once_with(Path.cwd())
        discard.assert_called_once_with(cleanup.unused)
    assert calls == ['recover']


def test_host_discard_leaves_vm_and_workflow_stores_untouched(tmp_path, monkeypatch):
    import cleanup_e2e
    import test_retention
    from contextlib import contextmanager
    host = test_retention.Store(tmp_path / 'host')
    workflow = test_retention.Store(tmp_path / 'workflow')
    vm = test_retention.Store(tmp_path / 'vm')
    for store in (host, workflow, vm):
        with store.session():
            allocated(tmp_path, store.path.name + '-result')
    @contextmanager
    def activity(root, **kwargs):
        assert kwargs == {'host_only': True}
        yield
    monkeypatch.setattr(cleanup_e2e.test_activity, 'activity', activity)
    monkeypatch.setattr(cleanup_e2e.test_activity, 'retention_path', lambda root: host.path)
    monkeypatch.setattr(cleanup_e2e, 'cleanup_host', lambda root: 0)
    monkeypatch.setattr(cleanup_e2e, 'cleanup', lambda root: pytest.fail('host touched VM'))
    assert cleanup_e2e.main(['--host-only', '--discard-completed']) == 0
    assert not (tmp_path / 'host-result').exists()
    assert (tmp_path / 'workflow-result').exists() and (tmp_path / 'vm-result').exists()


@pytest.mark.parametrize('manifest', ['artifact-manifest.json', 'native-inputs.json'])
def test_unpublished_input_recovery_keeps_reports_and_reuses_the_named_path(tmp_path, manifest):
    from tools import test_storage
    store = retention.Store(tmp_path / 'state')
    with store.session():
        partial = allocated(tmp_path, 'partial')
        report = allocated(tmp_path, 'report')
    unknown = tmp_path / 'unknown'
    unknown.mkdir()
    (unknown / 'keep').write_text('unregistered')
    journal = (store.path / 'current.json').read_bytes()
    assert store.discard_unpublished_input(partial)
    assert not partial.exists() and (report / 'test.log').exists()
    assert (unknown / 'keep').read_text() == 'unregistered'
    assert (store.path / 'current.json').read_bytes() == journal
    assert not store.discard_unpublished_input(partial)
    assert test_storage.named_input_slot(partial) == partial
    with store.session():
        new = allocated(tmp_path, 'partial')
        (new / manifest).write_text('completed bundle')
    assert test_storage.named_input_slot(partial) == new
    with pytest.raises(ValueError, match='published artifact'):
        store.discard_unpublished_input(partial)
    assert (new / manifest).read_text() == 'completed bundle'


@pytest.mark.parametrize('fault', ['active', 'unfinished', 'marked', 'unknown',
                                  'replaced', 'symlink', 'mount', 'manifest',
                                  'corrupt-manifest', 'linked-manifest', 'child-link'])
def test_unpublished_input_recovery_refuses_unsafe_or_published_inputs(tmp_path, monkeypatch, fault):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        partial = allocated(tmp_path, 'partial')
        report = allocated(tmp_path, 'report')
        if fault == 'unfinished':
            retention.preserve_for_recovery()
    if fault == 'unfinished':
        (store.path / 'recovery-required').unlink()
    if fault == 'marked':
        (store.path / 'recovery-required').touch(mode=0o600)
    if fault == 'unknown':
        partial = tmp_path / 'unknown'
        partial.mkdir(mode=0o700)
        (partial / 'test.log').write_text('unknown')
    if fault in ('replaced', 'symlink'):
        partial.rename(tmp_path / 'original')
        if fault == 'symlink':
            partial.symlink_to(tmp_path / 'original', target_is_directory=True)
        else:
            partial.mkdir(mode=0o700)
            (partial / 'test.log').write_text('replacement')
    if fault == 'mount':
        mount = retention.mount_id
        monkeypatch.setattr(retention, 'mount_id', lambda fd:
            'foreign' if Path(os.readlink(f'/proc/self/fd/{fd}')) == partial else mount(fd))
    if fault in ('manifest', 'corrupt-manifest'):
        (partial / 'artifact-manifest.json').write_text('{}' if fault == 'manifest' else 'invalid')
    if fault == 'linked-manifest':
        (partial / 'artifact-manifest.json').symlink_to(tmp_path / 'missing')
    if fault == 'child-link':
        (partial / 'child').symlink_to(report)
    journal = (store.path / 'current.json').read_bytes()
    if fault == 'active':
        with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False):
            with pytest.raises(ValueError, match='another owner'):
                store.discard_unpublished_input(partial)
    else:
        with pytest.raises((ValueError, OSError)):
            store.discard_unpublished_input(partial)
    assert (partial / 'test.log').exists() and (report / 'test.log').exists()
    assert (store.path / 'current.json').read_bytes() == journal


def test_unpublished_input_recovery_retries_partial_deletion_and_latest_identity(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        original = allocated(tmp_path, 'partial')
    original.rename(tmp_path / 'preserved')
    with store.session():
        partial = allocated(tmp_path, 'partial')
    journal = (store.path / 'current.json').read_bytes()
    remove = retention.remove
    def interrupted(record, *, validate_only=False):
        if not validate_only:
            (partial / 'test.log').unlink()
            raise OSError('interrupted deletion')
        return remove(record, validate_only=True)
    monkeypatch.setattr(retention, 'remove', interrupted)
    with pytest.raises(OSError, match='interrupted deletion'):
        store.discard_unpublished_input(partial)
    monkeypatch.setattr(retention, 'remove', remove)
    assert store.discard_unpublished_input(partial)
    assert (tmp_path / 'preserved/test.log').exists()
    assert (store.path / 'current.json').read_bytes() == journal


def test_unpublished_input_cli_derives_exact_selection_under_checkout_ownership(tmp_path, monkeypatch):
    import cleanup_e2e
    import test_commands
    import test_storage
    from contextlib import contextmanager
    calls = []
    partial = tmp_path / 'partial'
    @contextmanager
    def activity(root, **kwargs):
        assert kwargs == {'includes_host': True}
        calls.append('owned')
        yield
        calls.append('released')
    monkeypatch.setattr(cleanup_e2e.os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(cleanup_e2e.vm_config, 'execution',
                        lambda selection: (1, [SimpleNamespace(name='selected')]))
    monkeypatch.setattr(cleanup_e2e, 'select', lambda name: calls.append(name))
    monkeypatch.setattr(test_commands, 'qualification_input_options',
                        lambda root, selector: {} if selector == 'check_e2e_countdown' else None)
    monkeypatch.setattr(test_storage, 'named_input', lambda **options: partial)
    monkeypatch.setattr(cleanup_e2e.test_activity, 'activity', activity)
    monkeypatch.setattr(cleanup_e2e.test_activity, 'retention_path', lambda root: tmp_path / 'state')
    monkeypatch.setattr(cleanup_e2e.test_retention, 'Store', lambda path:
        SimpleNamespace(discard_unpublished_input=lambda selected: calls.append(selected) or True))
    monkeypatch.setattr(cleanup_e2e, 'cleanup', lambda root: pytest.fail('input recovery touched VM'))
    assert cleanup_e2e.main(['--vm', 'selected', '--discard-unpublished-input', 'check_e2e_countdown']) == 0
    assert calls == ['selected', 'owned', partial, 'released']
    for args in (['--discard-unpublished-input', 'check_e2e_countdown'],
                 ['--vm', 'all', '--discard-unpublished-input', 'check_e2e_countdown'],
                 ['--vm', 'selected', '--discard-completed', '--discard-unpublished-input', 'check_e2e_countdown'],
                 ['--vm', 'selected', '--discard-unpublished-input', '../check_e2e_countdown'],
                 ['--vm', 'selected', '--discard-unpublished-input', 'check_unavailable']):
        assert cleanup_e2e.main(args) == 2
    assert calls == ['selected', 'owned', partial, 'released']


def test_recovery_safety_uses_shared_parallel_cleanup_coordinator():
    import regression_process
    root = Path(__file__).resolve().parents[2]
    command = regression_process.safety_command(root)
    assert command == ['/usr/bin/python3', '-IB', str(root / 'tools/regression_process.py'),
                       '--cleanup-prerequisites']


def input_transfer_scene(tmp_path):
    from tools import test_input_transfer
    source = retention.Store(tmp_path / 'retention-batch')
    destination = retention.Store(tmp_path / 'retention-selected')
    with destination.session():
        path = allocated(tmp_path, 'input')
        destination_report = allocated(tmp_path, 'destination-report')
    # Keep the unlinked inode pinned so the new allocation has a distinct
    # identity even on filesystems which aggressively reuse directory inodes.
    old = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        destination.discard_unpublished_input(path)
        with source.session():
            path = allocated(tmp_path, 'input')
            (path / 'artifact-manifest.json').write_text('published')
            source_report = allocated(tmp_path, 'source-report')
    finally:
        os.close(old)
    def perform(verify=lambda path: 0):
        return test_input_transfer.transfer(source, destination, path,
            selector='check_e2e_countdown', vm='selected', verify=verify)
    return source, destination, path, source_report, destination_report, perform


def test_input_transfer_preserves_evidence_and_changes_only_cleanup_owner(tmp_path):
    source, destination, path, sr, dr, perform = input_transfer_scene(tmp_path)
    original = [json.loads((store.path / 'current.json').read_text()) for store in (source, destination)]
    calls = []
    assert perform(lambda candidate: calls.append(candidate) or 0)
    assert calls == [path] and not perform()
    current = [json.loads((store.path / 'current.json').read_text()) for store in (source, destination)]
    assert [state['run'] for state in current] == [state['run'] for state in original]
    assert current[1]['paths'][:-1] == original[1]['paths']
    assert current[0]['paths'][1:] == original[0]['paths'][1:]
    assert current[0]['paths'][0]['retired']['destination'] == str(destination.path)
    assert not any(record['path'] == str(path) for _, record in
                   retention.latest_allocations([*current[0]['history'], current[0]]))
    assert sr.exists() and dr.exists() and (path / 'artifact-manifest.json').exists()
    for _ in range(3):
        with source.session():
            pass
    assert path.exists()  # The former owner cannot evict the transferred input.
    for _ in range(3):
        with destination.session():
            pass
    assert not path.exists()  # Its recipient owns normal eventual expiration.


@pytest.mark.parametrize('step', range(1, 9))
def test_input_transfer_recovers_each_durable_boundary(tmp_path, monkeypatch, step):
    from tools import test_input_transfer
    source, destination, path, sr, dr, perform = input_transfer_scene(tmp_path)
    save, unlink = retention.Store.save, test_input_transfer.os.unlink
    writes = 0
    def boundary():
        nonlocal writes
        writes += 1
        if writes == step:
            raise OSError('interrupted durable transfer')
    def interrupted_save(store, fd, value, *, name='current.json'):
        save(store, fd, value, name=name)
        boundary()
    def interrupted_unlink(name, **kwargs):
        unlink(name, **kwargs)
        if name == test_input_transfer.MARKER:
            boundary()
    monkeypatch.setattr(retention.Store, 'save', interrupted_save)
    monkeypatch.setattr(test_input_transfer.os, 'unlink', interrupted_unlink)
    with pytest.raises(OSError, match='interrupted durable transfer'):
        perform()
    monkeypatch.setattr(retention.Store, 'save', save)
    monkeypatch.setattr(test_input_transfer.os, 'unlink', unlink)
    if step <= 5:
        for store in (source, destination):
            with pytest.raises(ValueError):
                with store.session():
                    pytest.fail('incomplete transfer allowed execution')
    perform()
    assert not perform()
    assert sr.exists() and dr.exists() and path.exists()
    assert not (source.path / test_input_transfer.MARKER).exists()
    assert not (destination.path / test_input_transfer.MARKER).exists()
    with source.session(), destination.session():
        pass


@pytest.mark.parametrize('fault', ['active-source', 'active-destination', 'unfinished', 'marked',
                                  'unregistered', 'replacement', 'symlink', 'mount',
                                  'bad-bundle', 'budget', 'other-replacement'])
def test_input_transfer_refuses_without_mutation(tmp_path, monkeypatch, fault):
    from tools import test_input_transfer
    source, destination, path, sr, dr, perform = input_transfer_scene(tmp_path)
    if fault == 'unfinished':
        state = json.loads((source.path / 'current.json').read_text())
        state['finished'] = False
        with source.opened() as fd:
            source.save(fd, state)
    if fault == 'marked':
        (destination.path / 'recovery-required').touch(mode=0o600)
    if fault == 'unregistered':
        state = json.loads((source.path / 'current.json').read_text())
        state['paths'] = state['paths'][1:]
        with source.opened() as fd:
            source.save(fd, state)
    if fault in ('replacement', 'symlink'):
        path.rename(tmp_path / 'kept-original')
        if fault == 'symlink':
            path.symlink_to(tmp_path / 'kept-original', target_is_directory=True)
        else:
            path.mkdir(mode=0o700)
    if fault == 'other-replacement':
        dr.rename(tmp_path / 'kept-report')
        dr.mkdir(mode=0o700)
    if fault == 'mount':
        mount = retention.mount_id
        monkeypatch.setattr(retention, 'mount_id', lambda fd:
            'foreign' if Path(os.readlink(f'/proc/self/fd/{fd}')) == path else mount(fd))
    if fault == 'budget':
        monkeypatch.setattr(retention, 'MAX_RETAINED_BYTES', 1)
    before = [(store.path / 'current.json').read_bytes() for store in (source, destination)]
    active = source if fault == 'active-source' else destination
    owner = active.opened() if fault.startswith('active-') else nullcontext(None)
    with owner as fd:
        lock = active.locked(fd, 'owner.lock', blocking=False) if fd is not None else nullcontext()
        with lock, pytest.raises((ValueError, OSError)):
            perform(lambda path: 2 if fault == 'bad-bundle' else 0)
    assert before == [(store.path / 'current.json').read_bytes() for store in (source, destination)]
    assert sr.exists() and dr.exists()
    assert not (source.path / test_input_transfer.MARKER).exists()
    assert not (destination.path / test_input_transfer.MARKER).exists()


def test_retirement_never_resurrects_an_older_claim_and_invalid_receipts_refuse(tmp_path):
    source, destination, path, sr, dr, perform = input_transfer_scene(tmp_path)
    assert perform()
    state = json.loads((source.path / 'current.json').read_text())
    live = dict(state['paths'][0])
    del live['retired']
    state['history'].append(dict(run=uuid.uuid4().hex, paths=[live]))
    assert not any(record['path'] == str(path) for _, record in retention.latest_allocations(
        [*state['history'], state]))
    state['paths'][0]['retired']['transaction'] = 'invalid'
    with pytest.raises(ValueError, match='retirement'):
        retention.latest_allocations([*state['history'], state])


def test_pending_transfer_refuses_changed_identity_and_competing_selector(tmp_path, monkeypatch):
    from tools import test_input_transfer
    source, destination, path, sr, dr, perform = input_transfer_scene(tmp_path)
    save = destination.save
    monkeypatch.setattr(destination, 'save', lambda *args, **kwargs: (_ for _ in ()).throw(
        OSError('second intent interrupted')))
    with pytest.raises(OSError):
        perform()
    monkeypatch.setattr(destination, 'save', save)
    before = (source.path / test_input_transfer.MARKER).read_bytes()
    with pytest.raises(ValueError, match='intent changed'):
        test_input_transfer.transfer(source, destination, path,
            selector='check_other', vm='selected', verify=lambda path: 0)
    path.rename(tmp_path / 'kept-original')
    path.mkdir(mode=0o700)
    with pytest.raises(ValueError, match='replaced'):
        perform()
    assert (source.path / test_input_transfer.MARKER).read_bytes() == before
    assert (tmp_path / 'kept-original/artifact-manifest.json').exists()


@pytest.mark.parametrize('operation', ['session', 'discard', 'unpublished', 'reconcile', 'retain', 'mark'])
def test_pending_transfer_blocks_all_ordinary_retention_writers(tmp_path, monkeypatch, operation):
    source, destination, path, sr, dr, perform = input_transfer_scene(tmp_path)
    save = destination.save
    monkeypatch.setattr(destination, 'save', lambda *args, **kwargs: (_ for _ in ()).throw(OSError('interrupted')))
    with pytest.raises(OSError):
        perform()
    monkeypatch.setattr(destination, 'save', save)
    state = json.loads((source.path / 'current.json').read_text())
    monkeypatch.setenv(retention.VARIABLE, json.dumps([str(source.path), state['run']]))
    with pytest.raises(ValueError, match='transfer pending'):
        if operation == 'session':
            with source.session():
                pass
        elif operation == 'discard':
            source.discard_completed(lambda paths: None)
        elif operation == 'unpublished':
            source.discard_unpublished_input(path)
        elif operation == 'reconcile':
            source.reconcile(lambda: None)
        elif operation == 'retain':
            retention.retain(sr)
        else:
            retention.preserve_for_recovery()
    assert path.exists() and sr.exists() and dr.exists()
    assert not (source.path / 'recovery-required').exists()


def test_batch_input_cli_derives_journals_and_runs_normal_verification_under_ownership(tmp_path, monkeypatch):
    import cleanup_e2e
    monkeypatch.setattr(cleanup_e2e, 'reservation', lambda *a, **kw: nullcontext())
    import test_commands
    import test_storage
    import test_input_transfer
    import vm_artifacts
    import regression_process
    from contextlib import contextmanager
    calls = []
    path = tmp_path / 'input'
    @contextmanager
    def activity(root, **kwargs):
        assert kwargs == {'includes_host': True}
        calls.append('owned')
        yield
        calls.append('released')
    monkeypatch.setattr(cleanup_e2e.os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(cleanup_e2e.vm_config, 'execution', lambda selection:
        (1, [SimpleNamespace(name='selected')]))
    monkeypatch.setattr(cleanup_e2e, 'select', lambda name: calls.append(name))
    monkeypatch.setattr(test_commands, 'qualification_input_options', lambda root, selector: {})
    monkeypatch.setattr(test_storage, 'named_input', lambda **kwargs: path)
    monkeypatch.setattr(cleanup_e2e.test_activity, 'activity', activity)
    monkeypatch.setattr(cleanup_e2e.test_activity, 'retention_path', lambda root: tmp_path / 'retention-selected')
    monkeypatch.setattr(regression_process.Control, 'installed', lambda self, **kwargs: nullcontext(self))
    def verify(root, control, environment, **kwargs):
        assert calls[-1] == 'owned'
        assert kwargs == {'candidate': path, 'output': path}
        calls.append('verified')
        return 0
    monkeypatch.setattr(vm_artifacts, 'prepare', verify)
    def transfer(source, destination, selected, **kwargs):
        assert selected == path and source.path == tmp_path / 'retention-batch'
        assert destination.path == tmp_path / 'retention-selected'
        assert kwargs['vm'] == 'selected' and kwargs['selector'] == 'check_e2e_countdown'
        assert kwargs['verify'](selected) == 0
        return True
    monkeypatch.setattr(test_input_transfer, 'transfer', transfer)
    monkeypatch.setattr(cleanup_e2e, 'cleanup', lambda root: pytest.fail('transfer started ordinary VM cleanup'))
    assert cleanup_e2e.main(['--vm', 'selected', '--transfer-batch-input', 'check_e2e_countdown']) == 0
    assert calls == ['selected', 'owned', 'verified', 'released']
    for args in (['--transfer-batch-input', 'check_e2e_countdown'],
                 ['--vm', 'all-enabled', '--transfer-batch-input', 'check_e2e_countdown'],
                 ['--vm', 'selected', '--discard-completed', '--transfer-batch-input', 'check_e2e_countdown'],
                 ['--vm', 'selected', '--transfer-batch-input', '../check_e2e_countdown']):
        assert cleanup_e2e.main(args) == 2
    assert calls == ['selected', 'owned', 'verified', 'released']


def test_idle_reconciliation_retries_after_marker_archive_and_failed_commit(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    with store.session() as run:
        evidence = allocated(tmp_path, 'evidence')
        retention.preserve_for_recovery()
    save = store.save
    def failed_commit(fd, value, *, name='current.json'):
        if name == 'current.json':
            raise OSError('simulated commit failure')
        save(fd, value, name=name)
    monkeypatch.setattr(store, 'save', failed_commit)
    with pytest.raises(OSError, match='commit failure'):
        store.reconcile(lambda: None)
    archived = (store.path / f'recovered-{run}.json').read_bytes()
    assert not json.loads((store.path / 'current.json').read_text())['finished']
    monkeypatch.setattr(store, 'save', save)
    assert store.reconcile(lambda: None)
    assert (store.path / f'recovered-{run}.json').read_bytes() == archived
    assert (evidence / 'test.log').exists()


@pytest.mark.parametrize('failed', [False, True])
def test_launcher_reconciles_only_idle_pending_storage(tmp_path, monkeypatch, failed):
    import test_recovery
    import test_retention as live_retention
    import regression_process
    import vm_config
    import vm_selection
    # Model one selected VM, independent of the enclosing launcher's selection
    # and host/batch activity. Keep all journals in this test's private root.
    vm = SimpleNamespace(name='fixture-vm')
    def load(name):
        assert name == vm.name
        return vm
    monkeypatch.setattr(vm_config, 'load', load)
    monkeypatch.setenv(vm_config.VARIABLE, vm.name)
    monkeypatch.delenv(vm_selection.BATCH, raising=False)
    monkeypatch.setattr(test_recovery.test_activity, '_host_only', False)
    monkeypatch.setattr(test_recovery.test_activity, 'descriptors', lambda: (123,))
    store = live_retention.Store(test_recovery.test_activity.retention_path(tmp_path))
    with store.session():
        live_retention.preserve_for_recovery()
    original = (store.path / 'current.json').read_bytes()
    calls = []
    def recover(root, category, args, **kwargs):
        calls.append((category, args))
        return int(failed)
    monkeypatch.setattr(regression_process, 'category_run', recover)
    if failed:
        with pytest.raises(ValueError, match='automatic recovery failed'):
            test_recovery.before_run(tmp_path, ['integration', 'check_test_recovery'])
        assert (store.path / 'recovery-required').exists()
        assert (store.path / 'current.json').read_bytes() == original
    else:
        test_recovery.before_run(tmp_path, ['integration', 'check_test_recovery'])
        test_recovery.before_run(tmp_path, ['unit', 'selected'])
        assert not (store.path / 'recovery-required').exists()
        assert json.loads((store.path / 'current.json').read_text())['finished']
    assert calls == [('integration', ['check_test_recovery', '--vm', vm.name])]


def test_execution_option_does_not_bypass_required_recovery(tmp_path, monkeypatch):
    import test_recovery
    monkeypatch.setattr(test_recovery.test_activity, 'descriptors', lambda: (123,))
    cleanup = Mock(return_value=0)
    monkeypatch.setattr(test_recovery, 'cleanup', cleanup)
    assert test_recovery.before_run(
        tmp_path, ['--stop-on-error', 'integration', 'check_test_recovery'],
        categories=['integration']) == 0
    cleanup.assert_called_once_with(tmp_path)


@pytest.mark.parametrize('fault', [None, 'busy', 'recovery-failed'])
def test_automatic_vm_recovery_keeps_guard_refusals(tmp_path, monkeypatch, fault):
    import check_test_recovery as recovery
    calls = []
    def guard(root):
        calls.append('guard')
        if fault == 'busy':
            raise BlockingIOError('lease is held')
        if calls == ['guard']:
            raise ValueError('retention: VM recovery is unfinished; preserve evidence')
    monkeypatch.setattr(recovery.runpy, 'run_path', lambda path: {'retention_guard': guard})
    def finish(**kwargs):
        assert kwargs == {'graphics_type': None, 'maintenance': True}
        calls.append('recover')
        return int(fault == 'recovery-failed')
    monkeypatch.setattr(recovery.check_graphical_recovery, 'main', finish)
    if fault:
        with pytest.raises((ValueError, BlockingIOError)):
            recovery.reconcile_vm(tmp_path)
    else:
        recovery.reconcile_vm(tmp_path)
    assert calls == (['guard'] if fault == 'busy' else
                     ['guard', 'recover'] if fault else ['guard', 'recover', 'guard'])


@pytest.mark.parametrize('argv', [[], ['--help'], ['system', '--list'], ['unit', 'selected'],
                                  ['host'], ['host-builds']])
def test_clean_host_or_listing_does_not_request_recovery(tmp_path, monkeypatch, argv):
    import test_recovery
    import regression_process
    monkeypatch.setattr(test_recovery.test_activity, 'descriptors', lambda: (123,))
    monkeypatch.setattr(regression_process, 'category_run',
                        lambda *args, **kwargs: pytest.fail('unnecessary recovery'))
    assert test_recovery.before_run(tmp_path, argv) == 0


@pytest.mark.parametrize('category', ['unit', 'ui', 'host', 'host-builds'])
def test_host_leaves_pending_vm_recovery_untouched(tmp_path, monkeypatch, category):
    import test_recovery
    import test_retention as live_retention
    monkeypatch.setattr(test_recovery.test_activity, 'descriptors', lambda: (123,))
    store = live_retention.Store(tmp_path / 'output/test-runs/host/state/retention')
    with store.session():
        live_retention.preserve_for_recovery()
    original = (store.path / 'current.json').read_bytes()
    monkeypatch.setattr(test_recovery, 'cleanup',
                        lambda *_: pytest.fail('host attempted VM recovery'))
    assert test_recovery.before_run(tmp_path, [category]) == 0
    assert (store.path / 'current.json').read_bytes() == original
    assert (store.path / 'recovery-required').exists()


@pytest.mark.parametrize('fault', [None, 'active', 'replaced', 'activity'])
def test_host_startup_recovers_only_idle_verified_evidence(tmp_path, monkeypatch, fault):
    import test_activity
    import test_recovery
    import test_retention as live_retention
    import test_storage
    import regression_process
    monkeypatch.delenv(test_activity.VARIABLE, raising=False)
    monkeypatch.setattr(test_activity, '_descriptor', None)
    monkeypatch.setattr(regression_process, 'category_run',
                        lambda *_args, **_kwargs: pytest.fail('host accessed VM recovery'))
    store = live_retention.Store(test_storage.directory('state', root=tmp_path) / 'retention-host')
    with store.session() as run:
        evidence = tmp_path / 'evidence'
        evidence.mkdir(mode=0o700)
        live_retention.retain(evidence)
        (evidence / 'test.log').write_text('interrupted evidence')
        live_retention.preserve_for_recovery()
    original = (store.path / 'current.json').read_bytes()
    if fault == 'replaced':
        evidence.rename(tmp_path / 'original')
        evidence.mkdir(mode=0o700)
    with test_activity.activity(tmp_path, host_only=True):
        def start():
            return test_recovery.before_run(tmp_path, ['--stop-on-error', 'unit'], categories=['unit'])
        if fault == 'active':
            with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False):
                with pytest.raises(ValueError, match='another owner'):
                    start()
        elif fault == 'activity':
            descriptor = test_activity._descriptor
            monkeypatch.setattr(test_activity, '_descriptor', None)
            with pytest.raises(ValueError, match='another test launcher'):
                test_recovery.cleanup_host(tmp_path)
            monkeypatch.setattr(test_activity, '_descriptor', descriptor)
        elif fault:
            with pytest.raises(ValueError, match='replaced'):
                start()
        else:
            assert start() == 0
            assert start() == 0
            assert (store.path / f'recovered-{run}.json').read_bytes() == original
            assert (evidence / 'test.log').read_text() == 'interrupted evidence'
            with store.session():
                pass
    if fault:
        assert (store.path / 'current.json').read_bytes() == original
        assert (store.path / 'recovery-required').exists()
        assert evidence.exists()


@pytest.fixture
def repetition_tree():
    # Only the bounded repetition workload uses /tmp (tmpfs on the host).
    # Keep real filesystem calls; disk-backed sync/error checks use tmp_path.
    with tempfile.TemporaryDirectory(prefix='onpc-retention-stress-', dir='/tmp') as root:
        yield Path(root)


@pytest.mark.parametrize('outcome', ['pass', 'failure', 'interrupt'])
def test_one_hundred_runs_have_constant_retained_size(repetition_tree, outcome):
    store = retention.Store(repetition_tree / 'state')
    foreign = repetition_tree / 'onpc-unregistered'
    foreign.mkdir()
    (foreign / 'keep').write_text('not owned by this runner')
    sizes = []
    previous = []
    for number in range(100):
        try:
            with store.session():
                if len(previous) == 3:
                    assert all(not path.exists() for path in previous.pop(0))
                assert all(path.exists() for group in previous for path in group)
                previous.append([allocated(repetition_tree, f'run-{number}-{kind}')
                                 for kind in ('report', 'build-a', 'build-b', 'ui', 'vm')])
                # Producers may independently discard passing render output.
                disposable = allocated(repetition_tree, f'render-{number}')
                # Fail before another iteration if a regression grows this
                # shared-filesystem footprint. Includes journals and sentinels.
                entries = list(repetition_tree.rglob('*'))
                assert len(entries) < 64
                assert sum(p.stat().st_size for p in entries if p.is_file()) < 256 * 1024
                shutil.rmtree(disposable)
                if outcome == 'failure':
                    raise SimulatedFailure('assertion failed')
                if outcome == 'interrupt':
                    raise SimulatedInterrupt
        except (SimulatedFailure, SimulatedInterrupt):
            if outcome == 'pass':
                raise
        sizes.append(sum(p.stat().st_size for group in previous for path in group for p in path.iterdir()))
        assert len(list(repetition_tree.glob('run-*'))) == 5 * min(number + 1, 3)
        assert (foreign / 'keep').read_text() == 'not owned by this runner'
    assert len(set(sizes[2:])) == 1
    state = json.loads((store.path / 'current.json').read_text())
    assert len(state['paths']) == 6
    assert len(state['history']) == 2
    assert all(len(entry['paths']) == 6 for entry in state['history'])


def test_same_run_keeps_all_vm_categories_until_fourth_run(tmp_path):
    store = retention.Store(tmp_path / 'state')
    run = uuid.uuid4().hex
    for index in range(4):
        with store.session(run=run):
            allocated(tmp_path, f'category-{index}')
            assert len(list(tmp_path.glob('category-*'))) == index + 1
    advance_to_expiry(store)
    assert len(list(tmp_path.glob('category-*'))) == 4
    with store.session():
        assert not list(tmp_path.glob('category-*'))


def test_active_owner_is_not_rotated(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'active')
        with pytest.raises(ValueError, match='another owner'):
            with retention.Store(store.path).session():
                pytest.fail('competing owner admitted')
        assert path.exists()


def test_parallel_writers_do_not_lose_allocations(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        with ThreadPoolExecutor(max_workers=4) as pool:
            paths = list(pool.map(lambda number: allocated(tmp_path, f'worker-{number}'), range(30)))
    advance_to_expiry(store)
    with store.session():
        assert all(not path.exists() for path in paths)


@pytest.mark.parametrize('kind', ['symlink', 'directory'])
def test_replaced_allocation_is_preserved_and_refused(tmp_path, kind):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'owned')
    path.rename(tmp_path / 'original')
    if kind == 'symlink':
        path.symlink_to(tmp_path / 'original', target_is_directory=True)
    else:
        path.mkdir(mode=0o700)
        (path / 'keep').write_text('replacement')
    with pytest.raises((ValueError, OSError)):
        with store.session():
            pytest.fail('replaced allocation accepted')
    assert (tmp_path / 'original/test.log').exists()
    assert path.exists()


@pytest.mark.parametrize('same_run', [False, True])
def test_recreated_registered_output_expires_with_its_latest_owner(tmp_path, same_run):
    store = retention.Store(tmp_path / 'state')
    with store.session() as first:
        path = allocated(tmp_path, 'named-output')
    # Keep the old inode allocated so the fixture cannot accidentally reuse it.
    original = tmp_path / 'original'
    path.rename(original)
    with store.session(run=first if same_run else None):
        retention.allocate(lambda: path.mkdir(mode=0o700) or str(path))
        (path / 'test.log').write_text('new output')
    journal = json.loads((store.path / 'current.json').read_text())
    records = [record for entry in [*journal['history'], journal]
               for record in entry['paths'] if record['path'] == str(path)]
    assert len(records) == 2
    assert records[0]['inode'] != records[1]['inode']
    assert not retention.legacy_system_evidence(journal)
    # Expiring the old owner must neither reject nor delete the new allocation.
    advance_to_expiry(store)
    assert (path / 'test.log').read_text() == 'new output'
    with store.session():
        assert not path.exists()
    assert (original / 'test.log').exists()


@pytest.mark.parametrize('fault', [None, 'unregistered', 'old-identity', 'symlink', 'mode'])
def test_recreated_output_recovery_still_checks_latest_identity(tmp_path, fault):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'named-output')
    original = tmp_path / 'original'
    path.rename(original)
    with store.session():
        retention.allocate(lambda: path.mkdir(mode=0o700) or str(path))
        (path / 'test.log').write_text('new output')
        retention.preserve_for_recovery()
    journal = store.path / 'current.json'
    before = journal.read_bytes()
    if fault in ('unregistered', 'old-identity', 'symlink'):
        path.rename(tmp_path / 'new-output')
        if fault == 'unregistered':
            path.mkdir(mode=0o700)
        elif fault == 'old-identity':
            original.rename(path)
        else:
            path.symlink_to(tmp_path / 'new-output', target_is_directory=True)
    elif fault == 'mode':
        path.chmod(0o755)
    if fault:
        with pytest.raises((ValueError, OSError)):
            store.reconcile(lambda: None)
        assert journal.read_bytes() == before
        assert (store.path / 'recovery-required').exists()
    else:
        assert store.reconcile(lambda: None)
        assert (path / 'test.log').read_text() == 'new output'
        advance_to_expiry(store)
        assert path.exists()
        with store.session():
            assert not path.exists()


def test_nested_symlink_never_deletes_its_target(tmp_path):
    store = retention.Store(tmp_path / 'state')
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'keep').write_text('foreign')
    with store.session():
        path = allocated(tmp_path, 'owned')
        (path / 'link').symlink_to(outside, target_is_directory=True)
        os.link(outside / 'keep', path / 'hardlink')
    advance_to_expiry(store)
    with store.session():
        assert not path.exists()
        assert (outside / 'keep').read_text() == 'foreign'


def test_unfinished_journal_stops_repetition_before_allocating(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'recovery')
    journal = store.path / 'current.json'
    state = json.loads(journal.read_text())
    state['finished'] = False
    journal.write_text(json.dumps(state))
    for _ in range(5):
        with pytest.raises(ValueError, match='previous owner did not finish'):
            with store.session():
                pytest.fail('unfinished owner bypassed')
        assert path.exists()
    assert len(list(tmp_path.iterdir())) == 2


def test_successful_recovery_returns_entire_journal_to_bounded_rotation(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        older = allocated(tmp_path, 'older')
    with store.session():
        interrupted = allocated(tmp_path, 'interrupted')
    journal = store.path / 'current.json'
    state = json.loads(journal.read_text())
    state['finished'] = False
    journal.write_text(json.dumps(state))
    for _ in range(5):
        with store.session(recover=lambda candidate: candidate == state):
            pass
    archived = store.path / f'interrupted-{state["run"]}.json'
    assert not archived.exists()
    assert not older.exists() and not interrupted.exists()


def test_recovery_callback_cannot_override_cleanup_failure(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'unsafe')
        retention.preserve_for_recovery()
    with pytest.raises(ValueError, match='previous owner did not finish'):
        with store.session(recover=lambda _: pytest.fail('cleanup marker bypassed')):
            pass
    assert path.exists()
    assert not list(store.path.glob('interrupted-*.json'))


def test_failed_recovery_guard_never_rotates_or_marks_finished(tmp_path):
    store = retention.Store(tmp_path / 'state')
    def refuse():
        raise ValueError('recovery unfinished')
    with store.session():
        path = allocated(tmp_path, 'old')
    with pytest.raises(ValueError, match='recovery unfinished'):
        with store.session(guard=refuse):
            pytest.fail('recovery guard bypassed')
    assert path.exists()
    calls = []
    def fail_on_exit():
        calls.append(1)
        if len(calls) == 2:
            refuse()
    with pytest.raises(ValueError, match='recovery unfinished'):
        with store.session(guard=fail_on_exit):
            allocated(tmp_path, 'new')
    assert not json.loads((store.path / 'current.json').read_text())['finished']


def test_fixture_cleanup_failure_pins_evidence_after_controller_exit(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'unsafe-fixture')
        retention.preserve_for_recovery()
    with pytest.raises(ValueError, match='previous owner did not finish'):
        with store.session():
            pytest.fail('unproven fixture cleanup bypassed')
    assert path.exists()


def test_allocation_registers_before_unmasking_interrupts(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    calls = []
    original = retention.retain
    def registered(path, **options):
        calls.append('register')
        return original(path, **options)
    def mask(action, signals):
        calls.append('block' if action == retention.signal.SIG_BLOCK else 'restore')
        return set()
    monkeypatch.setattr(retention, 'retain', registered)
    monkeypatch.setattr(retention.signal, 'pthread_sigmask', mask)
    with store.session():
        result = retention.allocate(tempfile.mkdtemp, prefix='allocation-', dir=tmp_path)
        assert calls == ['block', 'register', 'restore']
    advance_to_expiry(store)
    with store.session():
        assert not Path(result).exists()


def test_registration_failure_removes_only_the_new_empty_allocation(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    def broken(path, **options):
        raise OSError('journal unavailable')
    with store.session():
        monkeypatch.setattr(retention, 'retain', broken)
        with pytest.raises(OSError, match='journal unavailable'):
            retention.allocate(tempfile.mkdtemp, prefix='allocation-', dir=tmp_path)
        assert not list(tmp_path.glob('allocation-*'))


def test_unchanged_pruning_audits_allocations_without_repeating_journal_syncs(tmp_path,
                                                                          monkeypatch):
    store = retention.Store(tmp_path / 'state')
    calls = []
    real_sync = os.fsync

    def sync(fd):
        calls.append('directory' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'file')
        real_sync(fd)

    monkeypatch.setattr(os, 'fsync', sync)
    with store.session() as run:
        evidence = allocated(tmp_path, 'evidence')
        assert calls == ['file', 'directory'] * 2
        before = (store.path / 'current.json').stat()
        with store.opened() as fd, store.locked(fd, 'writer.lock'):
            store.prune(fd, store.read(fd))
            after = (store.path / 'current.json').stat()
            assert (after.st_ino, after.st_mtime_ns, after.st_ctime_ns) == (
                before.st_ino, before.st_mtime_ns, before.st_ctime_ns)
            # Skipping a journal write must not skip the allocation audit.
            evidence.chmod(0o777)
            try:
                with pytest.raises(ValueError, match='ownership|mode'):
                    store.prune(fd, store.read(fd))
            finally:
                evidence.chmod(0o700)
        assert calls == ['file', 'directory'] * 2
    assert calls == ['file', 'directory'] * 3
    assert json.loads((store.path / 'current.json').read_bytes())['finished']

    # Reopening the same owner still commits both lifecycle transitions.
    calls.clear()
    with store.session(run=run):
        assert not json.loads((store.path / 'current.json').read_bytes())['finished']
    assert calls == ['file', 'directory'] * 2
    assert (evidence / 'test.log').read_bytes() == b'evidence' * 128


@pytest.mark.parametrize('fault', [None, 'file-sync', 'replace', 'directory-sync'])
def test_registration_syncs_before_return_and_preserves_evidence_on_io_failure(tmp_path, monkeypatch,
                                                                             fault):
    # Use the launcher's ordinary disk-backed tmp_path for the durability
    # protocol. All operations remain real except the one injected I/O failure.
    store = retention.Store(tmp_path / 'state')
    calls, created = [], []
    real_sync, real_replace = os.fsync, os.replace

    def factory(**options):
        path = tempfile.mkdtemp(**options)
        created.append(path)
        return path

    def sync(fd):
        stage = 'directory-sync' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'file-sync'
        calls.append(stage)
        if stage == 'file-sync':
            # The bytes must already have left Python's buffer before fsync.
            pending = json.loads((store.path / 'current.tmp').read_text())
            assert {record['path'] for record in pending['paths']} == {str(existing), created[0]}
        if fault == stage:
            raise OSError('injected ' + stage)
        real_sync(fd)

    def replace(*args, **options):
        calls.append('replace')
        if fault == 'replace':
            raise OSError('injected replace')
        real_replace(*args, **options)

    with store.session():
        existing = allocated(tmp_path, 'existing-evidence')
        original = json.loads((store.path / 'current.json').read_text())
        with monkeypatch.context() as patch:
            patch.setattr(os, 'fsync', sync)
            patch.setattr(os, 'replace', replace)
            expectation = pytest.raises(OSError, match='injected ' + fault) if fault else nullcontext()
            with expectation:
                result = retention.allocate(factory, prefix='allocation-', dir=tmp_path)
                calls.append('returned')
        order = ['file-sync', 'replace', 'directory-sync', 'returned']
        assert calls == (order[:order.index(fault) + 1] if fault else order)
        assert len(created) == 1
        assert Path(created[0]).exists() is (fault is None)
        if fault is None:
            assert result == created[0]
        saved = json.loads((store.path / 'current.json').read_text())
        assert saved['paths'][0] == original['paths'][0]
        assert (existing / 'test.log').read_bytes() == b'evidence' * 128
        if fault in ('file-sync', 'replace'):
            assert saved == original
        else:
            # Directory-sync failure can expose the replaced journal; it must
            # still raise, remove only the fresh empty tree and retain evidence.
            assert {record['path'] for record in saved['paths']} == {str(existing), created[0]}


def test_sbuild_traversable_scratch_is_registered_and_rotated(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = Path(retention.allocate(tempfile.mkdtemp, dir=tmp_path, mode=0o711))
        assert path.stat().st_mode & 0o777 == 0o711
        (path / 'early-failure').mkdir()
    advance_to_expiry(store)
    with store.session():
        assert not path.exists()


@pytest.mark.parametrize('fault', [None, 'identity', 'mode', 'mount', 'namespace'])
def test_sbuild_namespace_requires_valid_record_and_preserves_failed_rotation(
        tmp_path, monkeypatch, fault):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = Path(retention.allocate(tempfile.mkdtemp, dir=tmp_path, mode=0o711))
        (path / 'evidence').write_text('keep')
    advance_to_expiry(store)
    journal = store.path / 'current.json'
    original = journal.read_bytes()
    if fault == 'identity':
        path.rename(tmp_path / 'original')
        path.mkdir(mode=0o711)
    elif fault == 'mode':
        path.chmod(0o700)
    elif fault == 'mount':
        mount_id = retention.mount_id
        monkeypatch.setattr(retention, 'mount_id', lambda fd:
                            'mounted' if os.fstat(fd).st_ino == path.stat().st_ino else mount_id(fd))
    monkeypatch.setattr(retention, 'sbuild_scratch', lambda record: True)
    calls = []
    def namespace(record, *, validate_only):
        calls.append(validate_only)
        assert record['path'] == str(path)
        assert len(retention._locks) == 2
        if fault == 'namespace':
            raise ValueError('namespace failed')
        # Emulate only the namespace boundary; keep real identity/tree checks.
        with monkeypatch.context() as patch:
            patch.setattr(retention, 'sbuild_scratch', lambda record: False)
            retention.remove(record, validate_only=validate_only)
    monkeypatch.setattr(retention, 'namespace_remove', namespace)
    if fault:
        with pytest.raises(ValueError):
            with store.session():
                pytest.fail('unsafe scratch accepted')
        assert journal.read_bytes() == original
        assert path.exists()
        assert calls == ([True] if fault == 'namespace' else [])
    else:
        with store.session():
            assert not path.exists()
        assert calls == [True, False]


@pytest.mark.parametrize('path,mode,expected', [
    ('/var/tmp/onpc-sbuild-scratch-example', 0o711, True),
    ('/var/tmp/onpc-sbuild-scratch-example', 0o700, False),
    ('/tmp/onpc-sbuild-scratch-example', 0o711, False),
    ('/var/tmp/other', 0o711, False),
    ('/var/tmp/onpc-sbuild-scratch-example/child', 0o711, False),
])
def test_only_registered_sbuild_parent_uses_namespace(path, mode, expected):
    assert retention.sbuild_scratch(dict(path=path, mode=mode)) is expected


@pytest.mark.parametrize('inspect,status', [(True, 0), (False, 0), (True, 1), (False, 'timeout')])
def test_namespace_command_inherits_leases_without_host_privilege(
        tmp_path, monkeypatch, inspect, status):
    record = dict(path='/var/tmp/onpc-sbuild-scratch-test', mode=0o711, device=1, inode=2)
    store = retention.Store(tmp_path / 'state')
    def execute(command, **kwargs):
        assert command[:7] == ['/usr/bin/unshare', '--user', '--map-users=subids',
                               '--map-groups=subids', '--map-root-user', '--', '/usr/bin/python3']
        assert command[7:9] == ['-I', '-B']
        assert command[-2:] == ['--sbuild-retention', 'inspect' if inspect else 'remove']
        assert json.loads(kwargs['input']) == record
        assert kwargs['cwd'] == '/'
        assert kwargs['env'] == {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'}
        assert set(kwargs['pass_fds']) == retention._locks
        assert retention._locks
        for fd in kwargs['pass_fds']:
            os.fstat(fd)
        if status == 'timeout':
            raise retention.subprocess.TimeoutExpired(command, 300)
        return SimpleNamespace(returncode=status)
    monkeypatch.setattr(retention.subprocess, 'run', execute)
    with store.session():
        with pytest.raises(ValueError, match='namespace operation') if status else nullcontext():
            retention.namespace_remove(record, validate_only=inspect)
    assert not retention._locks


@pytest.mark.parametrize('fault', [None, 'host-root', 'ordinary-user', 'path', 'operation'])
@pytest.mark.parametrize('operation', ['inspect', 'remove'])
def test_namespace_worker_refuses_unmapped_root_and_out_of_scope_records(
        monkeypatch, fault, operation):
    record = dict(path='/var/tmp/onpc-sbuild-scratch-example', mode=0o711, device=1, inode=2)
    if fault == 'path':
        record['path'] = '/var/tmp/unregistered'
    args = ['--sbuild-retention', operation if fault != 'operation' else 'chmod']
    monkeypatch.setattr(retention.os, 'geteuid', lambda: 1000 if fault == 'ordinary-user' else 0)
    read = Path.read_text
    monkeypatch.setattr(Path, 'read_text', lambda path, *a, **kw:
                        ('0 0 4294967295\n' if fault == 'host-root' else
                         '0 1000 1\n100000 100000 65536\n')
                        if str(path) == '/proc/self/uid_map' else read(path, *a, **kw))
    monkeypatch.setattr(retention.sys, 'stdin', io.StringIO(json.dumps(record)))
    calls = []
    monkeypatch.setattr(retention, 'remove', lambda value, **kw: calls.append((value, kw)))
    if fault:
        with pytest.raises(ValueError):
            retention.namespace_main(args)
        assert not calls
    else:
        retention.namespace_main(args)
        assert calls == [(record, {'validate_only': operation == 'inspect'})]


def test_inaccessible_sbuild_scratch_stops_growth(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with pytest.raises(PermissionError):
        with store.session():
            evidence = allocated(tmp_path, 'build-evidence')
            path = Path(retention.allocate(tempfile.mkdtemp, dir=tmp_path, mode=0o711))
            child = path / 'unproven-chroot-cleanup'
            child.mkdir(mode=0)
    try:
        for _ in range(3):
            with pytest.raises(PermissionError):
                with store.session():
                    pytest.fail('unproven chroot cleanup admitted another run')
            assert child.exists()
            assert (evidence / 'test.log').exists()
    finally:
        child.chmod(0o700)


def test_journal_hardlink_is_rejected_before_truncation(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        pass
    outside = tmp_path / 'keep'
    outside.write_text('original data')
    outside.chmod(0o600)
    os.link(outside, store.path / 'current.tmp')
    with pytest.raises(ValueError, match='unsafe ownership'):
        with store.session():
            pytest.fail('hardlinked journal accepted')
    assert outside.read_text() == 'original data'


def test_symlink_storage_parent_does_not_create_external_directories(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    (tmp_path / 'link').symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        with retention.Store(tmp_path / 'link/new').session():
            pytest.fail('symlink storage accepted')
    assert not list(outside.iterdir())


def test_mount_boundary_is_refused(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'owned')
    original = os.stat
    def changed(name, *args, **kwargs):
        value = original(name, *args, **kwargs)
        if name == 'test.log':
            return SimpleNamespace(st_dev=value.st_dev + 1)
        return value
    monkeypatch.setattr(retention.os, 'stat', changed)
    with pytest.raises(ValueError, match='mounted storage'):
        with store.session():
            pytest.fail('mount accepted')
    assert (path / 'test.log').exists()


@pytest.mark.parametrize('nested', [False, True])
def test_same_device_bind_mount_is_refused(tmp_path, monkeypatch, nested):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'owned')
        mounted = path / 'mounted' if nested else path
        mounted.mkdir(exist_ok=True)
        (mounted / 'keep').write_text('mounted data')
    original = retention.mount_id
    def changed(fd):
        return 'foreign-mount' if Path(os.readlink(f'/proc/self/fd/{fd}')) == mounted else original(fd)
    monkeypatch.setattr(retention, 'mount_id', changed)
    with pytest.raises(ValueError, match='mounted storage'):
        with store.session():
            pytest.fail('bind mount accepted')
    assert (mounted / 'keep').read_text() == 'mounted data'


def test_root_replacement_during_deletion_never_erases_replacement(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'owned')
    advance_to_expiry(store)
    clear = retention.clear_tree
    def replaced(fd, device):
        path.rename(tmp_path / 'original')
        path.mkdir(mode=0o700)
        (path / 'keep').write_text('replacement')
        clear(fd, device)
    monkeypatch.setattr(retention, 'clear_tree', replaced)
    with pytest.raises(ValueError, match='changed during cleanup'):
        with store.session():
            pytest.fail('replacement accepted')
    assert (path / 'keep').read_text() == 'replacement'


def test_dispatcher_groups_privileged_categories_by_aggregate(tmp_path, monkeypatch, dispatcher_vm):
    import test_storage
    monkeypatch.setattr(test_storage, 'privileged_state', lambda uid: tmp_path / 'root-state')
    # Keep dispatcher scratch private without replacing the Store used by both
    # scratch allocation and the real aggregate retention journal.
    monkeypatch.setattr(test_storage, 'scratch_directory', lambda: tmp_path)
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    run = dispatcher['run']
    run.__globals__['retention_guard'] = lambda root: None
    run.__globals__['selection'] = lambda root, argv: ['selected-controller']
    caller = SimpleNamespace(pw_uid=os.geteuid(), pw_gid=os.getegid(),
                             pw_name='fixture', pw_dir=str(tmp_path))
    monkeypatch.setattr(dispatcher['os'], 'getgrouplist', lambda *args: [])
    owned = []
    def execute(command, **kwargs):
        if command == ['selected-controller']:
            assert kwargs['env']['TMPDIR'] == str(tmp_path)
            assert kwargs['env']['ONPC_TEST_VM'] == dispatcher_vm
            assert retention.VARIABLE not in kwargs['env']
            assert retention.OWNER_VARIABLE not in kwargs['env']
            # The selected child opens its own producer session; the dispatcher
            # forwards only the validated run used to group aggregate evidence.
            store = retention.Store(test_storage.privileged_state(caller.pw_uid))
            with store.session(run=kwargs['env']['ONPC_QUALIFICATION_RETENTION_RUN']):
                owned.append(allocated(tmp_path, f'vm-{len(owned)}'))
        return 0
    control = SimpleNamespace(run=execute, installed=lambda **kw: nullcontext(control))
    monkeypatch.setattr(dispatcher['runpy'], 'run_path', lambda path: {
        'Control': lambda: control, 'safety_command': lambda root: ['safety']})
    first = uuid.uuid4().hex
    for category in ('system', 'e2e'):
        assert run(root, [f'--retention-run={first}', '--unattended', category,
                          '--vm', dispatcher_vm], caller) == 0
    assert all(path.exists() for path in owned)
    for _ in range(2):
        assert run(root, [f'--retention-run={uuid.uuid4().hex}', '--unattended', 'system',
                          '--vm', dispatcher_vm], caller) == 0
        assert all(path.exists() for path in owned)
    assert run(root, [f'--retention-run={uuid.uuid4().hex}', '--unattended', 'system',
                      '--vm', dispatcher_vm], caller) == 0
    assert not any(path.exists() for path in owned[:2])
    assert all(path.exists() for path in owned[2:])


def test_original_single_run_journal_upgrades_without_losing_evidence(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'original')
    journal = store.path / 'current.json'
    state = json.loads(journal.read_text())
    del state['history']
    journal.write_text(json.dumps(state))
    advance_to_expiry(store)
    assert path.exists()
    with store.session():
        assert not path.exists()


@pytest.mark.parametrize('fault', [None, 'identity', 'mode', 'unfinished', 'foreign'])
def test_legacy_system_export_is_preserved_only_after_identity_audit(tmp_path, fault):
    store = retention.Store(tmp_path / 'state')
    with tempfile.TemporaryDirectory(prefix='onpc-system-', dir='/tmp') as name:
        path = Path(name)
        with store.session() as old_run:
            retention.retain(path)
            (path / 'result.log').write_text('retained evidence')
            if fault == 'foreign':
                foreign = allocated(tmp_path, 'foreign')
        journal = store.path / 'current.json'
        old = json.loads(journal.read_text())
        path.chmod(0o755)
        if fault == 'identity':
            old['paths'][0]['inode'] += 1
        elif fault == 'mode':
            path.chmod(0o777)
        elif fault == 'unfinished':
            old['finished'] = False
        elif fault == 'foreign':
            foreign.chmod(0o755)
        journal.write_text(json.dumps(old))
        if fault:
            with pytest.raises(ValueError):
                with store.session(preserve_completed=retention.legacy_system_evidence):
                    pytest.fail('unsafe legacy journal accepted')
            assert json.loads(journal.read_text()) == old
        else:
            for _ in range(4):
                with pytest.raises(ValueError, match='explicit storage migration'):
                    with store.session(preserve_completed=retention.legacy_system_evidence):
                        pytest.fail('unbounded legacy archive accepted')
                assert json.loads(journal.read_text()) == old
                assert not list(store.path.glob('preserved-*.json'))
        assert (path / 'result.log').read_text() == 'retained evidence'


def test_older_vm_token_cannot_resume_after_a_newer_run(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session() as run:
        path = allocated(tmp_path, 'old-vm')
    with store.session():
        current = allocated(tmp_path, 'current-vm')
    with pytest.raises(ValueError, match='older run cannot resume'):
        with store.session(run=run):
            pytest.fail('older run resumed')
    assert path.exists() and current.exists()


def test_shell_review_copies_rotate_with_their_aggregate(tmp_path):
    namespace = runpy.run_path(str(Path(__file__).resolve().parents[2] /
                                  'tests/ui/test_child_shell_lifecycle.py'))
    preserve = namespace['_preserve_attempt_artifacts']
    preserve.__globals__['ARTIFACTS'] = tmp_path / 'review'
    source = tmp_path / 'shell-runtime'
    source.mkdir()
    log = source / 'lifecycle-events.log'
    store = retention.Store(tmp_path / 'state')
    copies = []
    for index in range(4):
        log.write_text(f'run {index}')
        with store.session():
            # The real producer allocates a unique runtime for each attempt.
            current = tmp_path / f'onpc-child-lifecycle-{index}'
            shutil.copytree(source, current)
            copies.append(preserve(current, 'lifecycle'))
        assert all(path.exists() for path in copies[-3:])
    assert not copies[0].exists()
    assert [(path / log.name).read_text() for path in copies[1:]] == ['run 1', 'run 2', 'run 3']


@pytest.mark.parametrize('phase', ['complete', 'running', 'cleanup-requested'])
def test_privileged_guard_reads_the_shared_recovery_journal(tmp_path, monkeypatch, phase, retention_vm):
    import prepare_baseline as baseline
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    monkeypatch.setattr(baseline, 'BASELINES', tmp_path)
    finalized = json.dumps(dict(phase='finalized', source=dict(layout=dict(uuid=retention_vm))))
    for name, content in (('.lock', ''), ('phase.json', finalized),
                          ('system-run.json', json.dumps({'phase': phase}))):
        path = tmp_path / name
        path.write_text(content)
        path.chmod(0o600)
    if phase == 'complete':
        dispatcher['retention_guard'](root)
    else:
        with pytest.raises(ValueError, match='recovery is unfinished'):
            dispatcher['retention_guard'](root)


def test_privileged_guard_uses_shared_named_baseline_lease(tmp_path, monkeypatch, retention_vm):
    import prepare_baseline as baseline
    import vm_pool
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    directory = tmp_path / 'named-vm'
    directory.mkdir(mode=0o700)
    monkeypatch.setattr(baseline, 'BASELINES', directory)
    monkeypatch.setattr(baseline.guest_contract.vm_config, 'STATE_ROOT', tmp_path)
    finalized = json.dumps(dict(phase='finalized', source=dict(layout=dict(uuid=retention_vm))))
    for name, content in (('phase.json', finalized),
                          ('system-run.json', '{"phase":"complete"}')):
        path = directory / name
        path.write_text(content)
        path.chmod(0o600)
    lock_path = tmp_path / '.lock'
    lock_path.touch(mode=0o600)
    # Completed journals do not authorize retention while this VM is leased
    # or an older controller holds the legacy root lease exclusively.
    dispatcher['retention_guard'](root)
    vm_lock_path = directory / '.lock'
    assert vm_lock_path.is_file()
    pool_lock_path = vm_pool.RUNTIME / (retention_vm + '.lock')
    with ThreadPoolExecutor(max_workers=1) as worker:
        for busy_path in (vm_lock_path, lock_path, pool_lock_path):
            reached = Event()
            name = 'compatibility_lock' if busy_path == lock_path else 'open_controller_lock'
            acquire = getattr(baseline, name)
            def observed(*args, **kwargs):
                reached.set()
                return acquire(*args, **kwargs)
            with monkeypatch.context() as patch:
                patch.setattr(baseline, name, observed)
                with busy_path.open('rb') as lock:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    pending = worker.submit(dispatcher['retention_guard'], root)
                    assert reached.wait(5)
                    # The maintained lease queues until its owner checks in.
                    with pytest.raises(TimeoutError):
                        pending.result(timeout=0.1)
                pending.result(timeout=5)
            dispatcher['retention_guard'](root)

    # A newer controller for another VM shares the compatibility lease and
    # owns only its own exclusive lease, so it must not block this VM.
    other_directory = tmp_path / 'other-vm'
    other_directory.mkdir(mode=0o700)
    other_lock_path = other_directory / '.lock'
    other_lock_path.touch(mode=0o600)
    with lock_path.open('rb') as legacy, other_lock_path.open('rb') as other:
        fcntl.flock(legacy.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        fcntl.flock(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        dispatcher['retention_guard'](root)

    # Success and refusal must both release every descriptor they acquired.
    for released_path in (vm_lock_path, lock_path, pool_lock_path):
        with released_path.open('rb') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    dispatcher['retention_guard'](root)


@pytest.mark.parametrize('value', ['../outside', '', 'a' * 31, 'g' * 32])
def test_privileged_run_token_cannot_supply_paths(value):
    dispatcher = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'tools/onpc-test-runner'))
    with pytest.raises(ValueError, match='invalid-retention-run'):
        dispatcher['run'](Path('/missing'), ['--retention-run=' + value, '--unattended'], None)
