"""P03 sealed handoff authority with private files and real retention locks.

Every allocation belongs to this module's pytest tree. There are no processes,
VMs, displays, sockets, external services or shared mutable caches.
"""

import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace

import pytest

import evidence_bundle as bundle
import evidence_capture as capture
import evidence_identity as logical
import test_retention as retention
import test_storage as storage
import test_input_transfer as input_transfer
from tests.support.paths import ROOT


CONSUMER = 'a' * 64
REVISION = 'b' * 64
PAYLOAD = b'{"result":"passed","cleanup":"complete"}\n'


@contextmanager
def producer_session(tmp_path, monkeypatch, *, journal_name='retention-host'):
    """Inject the shared allocator's checkout; keep its filesystem guards real."""
    checkout = tmp_path / 'checkout'
    checkout.mkdir(mode=0o700)
    monkeypatch.setattr(storage, 'ROOT', checkout)
    monkeypatch.setattr(storage, 'BASE', checkout / 'output/test-runs')
    monkeypatch.delenv(retention.VARIABLE, raising=False)
    store = retention.Store(storage.directory('state') / journal_name)
    with store.session():
        previous = Path(retention.allocate(tempfile.mkdtemp,
                                          prefix='onpc-prior-proof-fixture-'))
        previous_proof = previous / 'previous-result.json'
        previous_proof.write_bytes(b'prior finished evidence\n')
        previous_proof.chmod(0o600)
    with store.session() as run:
        source = Path(retention.allocate(tempfile.mkdtemp,
                                        prefix='onpc-capture-fixture-'))
        result = source / 'result.json'
        result.write_bytes(PAYLOAD)
        result.chmod(0o600)
        sibling = source / 'mutable-sibling.log'
        sibling.write_bytes(b'producer still running\n')
        sibling.chmod(0o600)
        handle = capture.issue_session(
            store, repository=checkout, workflow='capture-fixture', task='P03',
            check='sealed-producer', target='', inputs_sha256='c' * 64,
            sources_sha256='d' * 64,
            consumers={CONSUMER: dict(consumer_id=CONSUMER,
                                      revision_sha256=REVISION)})
        context = capture.session_context(handle)
        info = source.stat()
        allocation = dict(path=str(source), device=info.st_dev, inode=info.st_ino,
                          mode=0o700, journal=str(store.path), run=run)

        def record(**changes):
            draft = dict(
                schema=logical.SCHEMA, version=1, context=copy.deepcopy(context),
                status='passed', completeness='complete',
                members=[dict(role='result', original_path=str(result),
                              source_allocation=copy.deepcopy(allocation),
                              bytes=len(PAYLOAD),
                              sha256=hashlib.sha256(PAYLOAD).hexdigest(),
                              required=True)], dependencies=[],
                cleanup=dict(state='complete', record_members=[],
                             scope=dict(owner=copy.deepcopy(context['owner']),
                                        resources=[])))
            draft.update(changes)
            return logical.finalize_record(draft)

        def finalize(value=None):
            return capture.finalize_capture(handle, record=value or record(),
                                            consumer_ids=[CONSUMER])

        def inspect(identifier, **kwargs):
            return capture.inspect_capture(checkout, os.geteuid(), os.getegid(),
                                           identifier, **kwargs)

        yield SimpleNamespace(checkout=checkout, store=store, source=source,
                              result=result, sibling=sibling, handle=handle,
                              previous_proof=previous_proof,
                              context=context, allocation=allocation,
                              record=record, finalize=finalize, inspect=inspect)


@pytest.fixture
def producer(tmp_path, monkeypatch):
    with producer_session(tmp_path, monkeypatch) as value:
        yield value


def test_finished_seal_is_readable_while_parent_and_unselected_sibling_are_active(
        producer, monkeypatch):
    identifier = producer.finalize()
    before = (producer.store.path / 'current.json').read_bytes()
    assert json.loads(before)['finished'] is False
    producer.sibling.write_bytes(b'late write outside the finalized allowlist\n')
    opened = retention.Store.opened

    def no_active_parent(self):
        assert self.path != producer.store.path, 'collector inspected active parent'
        return opened(self)

    with monkeypatch.context() as local:
        local.setattr(retention.Store, 'opened', no_active_parent)
        request = producer.inspect(identifier)
    assert request['capture_id'] == identifier
    assert request['record'] == producer.record()
    assert (producer.store.path / 'current.json').read_bytes() == before
    assert producer.result.read_bytes() == PAYLOAD
    assert len(request['sealed']['mappings']) == 1
    mapping = request['sealed']['mappings'][0]
    assert mapping['original_path'] == str(producer.result)
    assert mapping['source_allocation'] == producer.allocation
    assert mapping['sealed_path'] != str(producer.result)
    sealed = Path(mapping['sealed_path'])
    assert sealed.read_bytes() == PAYLOAD
    assert sealed.stat().st_ino != producer.result.stat().st_ino
    assert sealed.stat().st_nlink == producer.result.stat().st_nlink == 1
    assert not producer.source.is_relative_to(sealed.parent)
    assert not sealed.is_relative_to(producer.source)
    assert request['request_sha256'] == logical.digest(
        {key: value for key, value in request.items() if key != 'request_sha256'})


@pytest.mark.parametrize('handle', [None, {}, object(), '/forged/journal'])
def test_paths_environment_and_plain_objects_cannot_mint_authority(producer, handle):
    before = (producer.store.path / 'current.json').read_bytes()
    with pytest.raises((ValueError, TypeError)):
        capture.finalize_capture(handle, record=producer.record(), consumer_ids=[CONSUMER])
    assert (producer.store.path / 'current.json').read_bytes() == before
    assert producer.result.read_bytes() == PAYLOAD


def test_environment_run_without_held_store_owner_cannot_issue_a_handle(producer):
    unowned = retention.Store(producer.store.path.with_name('retention-unowned'))
    with pytest.raises(ValueError):
        capture.issue_session(
            unowned, repository=producer.checkout, workflow='capture-fixture',
            task='P03', check='unowned', target='', inputs_sha256='c' * 64,
            sources_sha256='d' * 64,
            consumers={CONSUMER: dict(consumer_id=CONSUMER,
                                      revision_sha256=REVISION)})
    assert producer.result.read_bytes() == PAYLOAD


def test_replaced_owner_lock_cannot_reuse_the_issued_descriptor(producer):
    path = producer.store.path / 'owner.lock'
    original = path.with_name('owner.lock.saved')
    path.rename(original)
    path.write_bytes(b'')
    path.chmod(0o600)
    try:
        with pytest.raises(ValueError):
            producer.finalize()
        assert producer.result.read_bytes() == PAYLOAD
        state = json.loads((producer.store.path / 'current.json').read_bytes())
        assert not state.get('captures')
    finally:
        path.unlink()
        original.rename(path)


def test_handle_is_bound_to_its_issuing_process(producer, monkeypatch):
    issued = os.getpid()
    with monkeypatch.context() as local:
        local.setattr(capture.os, 'getpid', lambda: issued + 1)
        with pytest.raises(ValueError):
            producer.finalize()
    state = json.loads((producer.store.path / 'current.json').read_bytes())
    assert not state.get('captures')
    assert producer.result.read_bytes() == PAYLOAD


@pytest.mark.parametrize('field,value', [
    ('attempt', 'e' * 32), ('run', 'e' * 32), ('target', 'foreign-guest'),
    ('task', 'other-task'), ('check', 'other-check'),
    ('inputs_sha256', 'e' * 64), ('sources_sha256', 'e' * 64),
])
def test_record_must_match_issued_attempt_target_and_context(producer, field, value):
    context = copy.deepcopy(producer.context)
    context[field] = value
    with pytest.raises(ValueError):
        producer.finalize(producer.record(context=context))
    assert producer.result.read_bytes() == PAYLOAD


def test_missing_dependency_refuses_before_sealing_or_source_release(producer):
    record = producer.record(dependencies=[dict(record_id='e' * 64,
                                              closure_sha256='f' * 64)])
    before = (producer.store.path / 'current.json').read_bytes()
    with pytest.raises(ValueError, match='dependenc'):
        producer.finalize(record)
    assert (producer.store.path / 'current.json').read_bytes() == before
    assert producer.result.read_bytes() == PAYLOAD


def test_unknown_consumer_cannot_relax_the_issued_dependency(producer):
    with pytest.raises(ValueError):
        capture.finalize_capture(producer.handle, record=producer.record(),
                                 consumer_ids=['f' * 64])
    assert producer.result.read_bytes() == PAYLOAD


def test_exact_retry_is_idempotent_and_changed_request_cannot_replay(producer):
    identifier = producer.finalize()
    request = producer.inspect(identifier)
    before = (producer.store.path / 'current.json').read_bytes()
    assert producer.finalize() == identifier
    assert producer.inspect(identifier) == request
    assert (producer.store.path / 'current.json').read_bytes() == before
    with pytest.raises(ValueError):
        producer.finalize(producer.record(status='failed'))
    with pytest.raises(ValueError):
        producer.inspect(identifier, expected='f' * 64)
    with pytest.raises(ValueError):
        producer.inspect(identifier, target='foreign-guest')
    assert producer.inspect(identifier) == request
    assert producer.result.read_bytes() == PAYLOAD


def test_producer_retry_refuses_mutated_original_and_preserves_the_seal(producer):
    identifier = producer.finalize()
    request = producer.inspect(identifier)
    producer.result.write_bytes(b'changed original after sealing\n')
    with pytest.raises(ValueError):
        producer.finalize()
    assert producer.result.exists()
    sealed = Path(request['sealed']['mappings'][0]['sealed_path'])
    assert sealed.read_bytes() == PAYLOAD


def test_collector_refuses_mutated_seal_without_releasing_original(producer):
    identifier = producer.finalize()
    request = producer.inspect(identifier)
    sealed = Path(request['sealed']['mappings'][0]['sealed_path'])
    sealed.write_bytes(b'changed immutable seal\n')
    with pytest.raises(ValueError):
        producer.inspect(identifier)
    assert producer.result.read_bytes() == PAYLOAD
    assert sealed.exists()


def test_collector_never_reopens_original_payload_for_a_finished_seal(producer):
    identifier = producer.finalize()
    request = producer.inspect(identifier)
    saved = producer.result.with_name('producer-private-result.saved')
    producer.result.rename(saved)
    try:
        assert producer.inspect(identifier) == request
    finally:
        saved.rename(producer.result)


def test_source_mutation_during_real_copy_retains_required_stage(producer, monkeypatch):
    real_hash = capture._hash
    changed = False

    def race(fd, size, output=None):
        nonlocal changed
        checksum = real_hash(fd, size, output)
        if output is not None and not changed:
            changed = True
            producer.result.write_bytes(b'changed during sealed copy\n')
        return checksum

    with monkeypatch.context() as local:
        local.setattr(capture, '_hash', race)
        with pytest.raises(ValueError, match='changed'):
            producer.finalize()
    parent = json.loads((producer.store.path / 'current.json').read_bytes())
    assert len(parent['captures']) == 1
    identifier = parent['captures'][0]['capture_id']
    status = capture.capture_status(producer.handle, identifier)
    assert status['state'] == 'sealing' and status['request'] is None
    assert status['intent']['record'] == producer.record()
    assert producer.result.read_bytes() == b'changed during sealed copy\n'
    assert producer.previous_proof.read_bytes() == b'prior finished evidence\n'
    with pytest.raises(ValueError):
        producer.inspect(identifier)


def test_capture_selection_uses_finished_snapshot_without_parent_catalogue(
        producer, monkeypatch):
    identifier = producer.finalize()
    request = producer.inspect(identifier)
    opened = retention.Store.opened

    def no_active_parent(self):
        assert self.path != producer.store.path, 'selection inspected active parent'
        return opened(self)

    with monkeypatch.context() as local:
        local.setattr(retention.Store, 'opened', no_active_parent)
        with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                              [], [], [], captures=[identifier]) as selected:
            assert selected.manifest['schema'] == 2
            assert selected.manifest['records'] == [producer.record()]
            assert len(selected.manifest['files']) == 1
            origin = selected.manifest['member_map'][0]['original_provenance']
            assert origin['original_path'] == str(producer.result)
            assert origin['source_allocation'] == producer.allocation
            assert selected.manifest['files'][0]['path'] == (
                request['sealed']['mappings'][0]['sealed_path'])
            assert selected.plan()['selection_sha256'] == logical.digest(selected.manifest)


def test_selection_pins_original_provenance_for_its_entire_read_scope(producer):
    identifier = producer.finalize()
    registration = capture.capture_status(producer.handle, identifier)
    path = Path(registration['slot']['path']) / 'registration.json'
    original_bytes = path.read_bytes()
    original_identity = copy.deepcopy(registration['intent']['originals'][0]['identity'])
    try:
        with pytest.raises(ValueError, match='control record changed'):
            with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                                  [], [], [], captures=[identifier]) as selected:
                origin = selected.manifest['member_map'][0]['original_provenance']
                assert origin['identity'] == original_identity
                changed = json.loads(original_bytes)
                changed['intent']['originals'][0]['identity'][7] += 1
                path.write_bytes(logical.encoded(changed))
                assert origin['identity'] == original_identity
    finally:
        path.write_bytes(original_bytes)
    assert producer.inspect(identifier)['capture_id'] == identifier
    assert producer.result.read_bytes() == PAYLOAD


@pytest.fixture
def helper(producer, monkeypatch):
    script = runpy.run_path(str(ROOT / 'tools/onpc-test-artifacts'))
    main = script['main']
    monkeypatch.setitem(main.__globals__, 'CHECKOUT', str(producer.checkout))
    monkeypatch.setitem(main.__globals__, 'caller',
                        lambda: (os.geteuid(), os.getegid()))
    return main


def test_helper_capture_plan_and_custody_inspect_use_authenticated_registration(
        producer, helper, capsys):
    identifier = producer.finalize()
    request = producer.inspect(identifier)
    assert helper(['bundle-plan', '--capture', identifier]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan['selection_sha256']
    assert helper(['bundle-custody', '--transaction', identifier,
                   '--expect', request['request_sha256'], '--operation', 'inspect']) == 0
    assert json.loads(capsys.readouterr().out) == request
    assert helper(['bundle-custody', '--transaction', identifier,
                   '--expect', 'f' * 64, '--operation', 'inspect']) == 2
    failed = capsys.readouterr()
    assert not failed.out
    assert failed.err
    assert producer.inspect(identifier) == request


@pytest.mark.parametrize('arguments', [
    ['bundle-plan', '--capture', 'short'],
    ['bundle-plan', '--capture', 'A' * 64],
    ['bundle-custody', '--transaction', 'a' * 64, '--operation', 'inspect'],
    ['bundle-custody', '--transaction', 'a' * 64, '--expect', 'short',
     '--operation', 'inspect'],
    ['bundle-custody', '--transaction', 'a' * 64, '--expect', 'b' * 64,
     '--operation', 'retire-finish'],
    ['bundle-custody', '--transaction', 'a' * 64, '--expect', 'b' * 64,
     '--operation', 'inspect', '--uid', '1000'],
    ['bundle-custody', '--transaction', 'a' * 64, '--expect', 'b' * 64,
     '--operation', 'inspect', '--source', '/caller/journal'],
])
def test_helper_rejects_unregistered_capabilities_and_malformed_ids_before_identity(
        helper, monkeypatch, arguments):
    monkeypatch.setitem(helper.__globals__, 'caller',
                        lambda: pytest.fail('malformed selection reached caller authentication'))
    with pytest.raises(SystemExit) as failure:
        helper(arguments)
    assert failure.value.code == 2


def test_capture_export_remains_explicitly_unregistered_until_publication_task(
        producer, helper, capsys):
    identifier = producer.finalize()
    with pytest.raises(SystemExit) as failure:
        helper(['bundle-export', '--capture', identifier, '--expect', 'f' * 64])
    assert failure.value.code == 2
    result = capsys.readouterr()
    assert not result.out
    assert result.err
    assert producer.result.read_bytes() == PAYLOAD
    assert producer.inspect(identifier)['capture_id'] == identifier


def test_library_export_cannot_bypass_the_pending_capture_publication_gate(producer):
    identifier = producer.finalize()
    with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                          [], [], [], captures=[identifier]) as selected:
        with pytest.raises(ValueError, match='capture|publication|pending'):
            bundle.export(selected, expected=selected.plan()['selection_sha256'])
    assert producer.result.read_bytes() == PAYLOAD
    assert producer.inspect(identifier)['capture_id'] == identifier


def test_capacity_refusal_preserves_source_and_prior_proof_without_extra_slots(
        producer, monkeypatch):
    original = json.loads((producer.store.path / 'current.json').read_bytes())
    previous = producer.previous_proof.read_bytes()
    refused = []
    with monkeypatch.context() as local:
        local.setattr(retention, 'MAX_RETAINED_BYTES', 1)
        for _ in range(2):
            with pytest.raises(ValueError, match='budget|capacity|limit'):
                producer.finalize()
            state = json.loads((producer.store.path / 'current.json').read_bytes())
            refused.append(copy.deepcopy(state.get('captures', [])))
            assert state['paths'] == original['paths']
            assert state['history'] == original['history']
            assert len(state.get('captures', [])) <= 1
            assert producer.result.read_bytes() == PAYLOAD
            assert producer.previous_proof.read_bytes() == previous
    assert refused[0] == refused[1]
    identifier = producer.finalize()
    assert producer.inspect(identifier)['capture_id'] == identifier
    state = json.loads((producer.store.path / 'current.json').read_bytes())
    assert len(state['captures']) == 1
    assert producer.previous_proof.read_bytes() == previous


def test_projected_entry_limit_refuses_before_creating_a_capture_slot(producer, monkeypatch):
    for _ in range(14):
        retention.allocate(tempfile.mkdtemp, prefix='onpc-entry-budget-fixture-')
    before = (producer.store.path / 'current.json').read_bytes()
    record = producer.record()
    # Each finite wire object still fits. The simultaneous parent allocations
    # plus the proposed capture/member would exceed the collection entry bound.
    with monkeypatch.context() as local:
        local.setattr(logical, 'MAX_ENTRIES', 16)
        with pytest.raises(ValueError, match='entry|capacity|limit'):
            producer.finalize(record)
    assert (producer.store.path / 'current.json').read_bytes() == before
    assert producer.result.read_bytes() == PAYLOAD
    assert producer.previous_proof.read_bytes() == b'prior finished evidence\n'
    parent = storage.directory('captures', root=producer.checkout)
    assert not list(parent.iterdir())


def test_parent_commit_then_interruption_preserves_the_registered_slot(producer, monkeypatch):
    real_save = producer.store.save
    interrupted = False

    def commit_then_interrupt(fd, state, *, name='current.json'):
        nonlocal interrupted
        real_save(fd, state, name=name)
        if name == 'current.json' and state.get('captures') and not interrupted:
            interrupted = True
            raise SimulatedInterrupt('parent intent durable before interrupted reply')

    with monkeypatch.context() as local:
        local.setattr(producer.store, 'save', commit_then_interrupt)
        with pytest.raises(SimulatedInterrupt):
            producer.finalize()
    state = json.loads((producer.store.path / 'current.json').read_bytes())
    assert len(state['captures']) == 1
    charge = copy.deepcopy(state['captures'][0])
    slot = Path(charge['path'])
    slot_info = slot.stat()
    assert (slot_info.st_dev, slot_info.st_ino) == (charge['device'], charge['inode'])
    assert producer.result.read_bytes() == PAYLOAD
    assert producer.previous_proof.read_bytes() == b'prior finished evidence\n'
    assert producer.finalize() == charge['capture_id']
    after = json.loads((producer.store.path / 'current.json').read_bytes())
    assert after['captures'] == [charge]
    assert slot.stat().st_ino == slot_info.st_ino
    assert producer.inspect(charge['capture_id'])['record'] == producer.record()


@pytest.mark.parametrize('operation', ['prune', 'discard'])
def test_finished_required_capture_blocks_retirement_and_completed_discard(
        tmp_path, monkeypatch, operation):
    with producer_session(tmp_path, monkeypatch) as value:
        identifier = value.finalize()
        request = value.inspect(identifier)
    before = (value.store.path / 'current.json').read_bytes()
    state = json.loads(before)
    slot = state['captures'][0]
    slot_identity = Path(slot['path']).stat()
    sealed = Path(request['sealed']['mappings'][0]['sealed_path'])
    with pytest.raises(ValueError, match='capture'):
        if operation == 'discard':
            value.store.discard_completed(
                lambda _paths: pytest.fail('dependency refusal reached destructive audit'))
        else:
            with value.store.opened() as fd:
                with value.store.locked(fd, 'owner.lock', blocking=False):
                    with value.store.locked(fd, 'writer.lock'):
                        value.store.prune(fd, copy.deepcopy(state), keep=0)
    assert (value.store.path / 'current.json').read_bytes() == before
    assert value.result.read_bytes() == sealed.read_bytes() == PAYLOAD
    assert value.previous_proof.read_bytes() == b'prior finished evidence\n'
    assert Path(slot['path']).stat().st_ino == slot_identity.st_ino
    assert value.inspect(identifier) == request


def test_direct_fourth_session_cannot_rotate_a_required_capture_away(
        tmp_path, monkeypatch):
    with producer_session(tmp_path, monkeypatch) as value:
        identifier = value.finalize()
        request = value.inspect(identifier)
    with pytest.raises(ValueError):
        value.finalize()
    for _ in range(2):
        with value.store.session():
            pass
    before = (value.store.path / 'current.json').read_bytes()
    with pytest.raises(ValueError, match='capture'):
        with value.store.session():
            pytest.fail('fourth run retired a required capture')
    assert (value.store.path / 'current.json').read_bytes() == before
    assert value.result.read_bytes() == PAYLOAD
    assert value.inspect(identifier) == request
    entries = [*json.loads(before)['history'], json.loads(before)]
    charges = [charge for entry in entries for charge in entry.get('captures', [])]
    assert len(charges) == 1 and charges[0]['capture_id'] == identifier


class SimulatedInterrupt(KeyboardInterrupt):
    """A fixture-owned cooperative interruption, never a host signal."""


class SimulatedCancellation(RuntimeError):
    """Cancellation cannot discard required source or invent acceptance."""


@pytest.mark.parametrize('boundary,state', [
    ('required', 'required'), ('sealing', 'sealing'),
    ('finished', 'sealing'), ('sealed', 'sealed'),
])
@pytest.mark.parametrize('failure', [SimulatedInterrupt, SimulatedCancellation])
def test_interruption_reuses_exact_intent_slot_and_resumable_stage(
        producer, monkeypatch, boundary, state, failure):
    def interrupt(stage):
        if stage == boundary:
            raise failure('owned fixture cancellation')

    with monkeypatch.context() as local:
        local.setattr(capture, 'checkpoint', interrupt)
        with pytest.raises(failure):
            producer.finalize()
    parent = json.loads((producer.store.path / 'current.json').read_bytes())
    assert len(parent['captures']) == 1
    charge = copy.deepcopy(parent['captures'][0])
    identifier = charge['capture_id']
    registration = capture.capture_status(producer.handle, identifier)
    assert registration['state'] == state
    assert registration['intent'] == charge['intent']
    assert registration['intent']['record'] == producer.record()
    assert registration['intent']['record']['context']['attempt'] == producer.context['attempt']
    if state != 'sealed':
        with pytest.raises(ValueError, match='pending|sealed'):
            producer.inspect(identifier)
        assert registration['request'] is None
    slot = Path(charge['path'])
    slot_inode = slot.stat().st_ino
    snapshot = slot / 'snapshot'
    snapshot_inode = snapshot.stat().st_ino if snapshot.exists() else None
    assert producer.result.read_bytes() == PAYLOAD
    assert producer.previous_proof.read_bytes() == b'prior finished evidence\n'
    assert producer.finalize() == identifier
    after = json.loads((producer.store.path / 'current.json').read_bytes())
    assert after['captures'] == [charge]
    assert slot.stat().st_ino == slot_inode
    if snapshot_inode is not None:
        assert snapshot.stat().st_ino == snapshot_inode
    request = producer.inspect(identifier)
    assert request['record'] == producer.record()
    if state == 'sealed':
        assert request == registration['request']


def test_reopened_owner_resumes_exact_registered_attempt_with_a_fresh_handle(
        tmp_path, monkeypatch):
    with producer_session(tmp_path, monkeypatch) as value:
        def interrupt(stage):
            if stage == 'sealing':
                raise SimulatedInterrupt('reopen exact producer run')

        with monkeypatch.context() as local:
            local.setattr(capture, 'checkpoint', interrupt)
            with pytest.raises(SimulatedInterrupt):
                value.finalize()
        before = json.loads((value.store.path / 'current.json').read_bytes())
        charge = copy.deepcopy(before['captures'][0])
        identifier = charge['capture_id']
        original_record = value.record()
        original_context = copy.deepcopy(value.context)
        slot_inode = Path(charge['path']).stat().st_ino
    with pytest.raises(ValueError):
        value.finalize()
    with value.store.session(run=original_context['run']):
        resumed = capture.resume_session(value.store, identifier)
        assert resumed is not value.handle
        assert capture.session_context(resumed) == original_context
        assert capture.capture_status(resumed, identifier)['state'] == 'sealing'
        with pytest.raises(ValueError):
            capture.finalize_capture(value.handle, record=original_record,
                                     consumer_ids=[CONSUMER])
        assert capture.finalize_capture(resumed, record=original_record,
                                        consumer_ids=[CONSUMER]) == identifier
        after = json.loads((value.store.path / 'current.json').read_bytes())
        assert after['captures'] == [charge]
        assert Path(charge['path']).stat().st_ino == slot_inode
        assert value.inspect(identifier)['record'] == original_record
    with pytest.raises(ValueError):
        capture.session_context(resumed)


def test_partial_interrupted_record_is_preserved_without_diagnostic_promotion(producer):
    cleanup = copy.deepcopy(producer.record()['cleanup'])
    cleanup['state'] = 'pending'
    record = producer.record(status='interrupted', completeness='partial', cleanup=cleanup)
    identifier = producer.finalize(record)
    request = producer.inspect(identifier)
    assert request['record'] == record
    assert request['record']['status'] == 'interrupted'
    assert request['record']['completeness'] == 'partial'
    assert request['record']['cleanup']['state'] == 'pending'


def test_missing_registration_refuses_instead_of_reading_parent(producer):
    identifier = producer.finalize()
    registration = capture.capture_status(producer.handle, identifier)
    path = Path(registration['slot']['path']) / 'registration.json'
    saved = path.with_name('registration.saved')
    path.rename(saved)
    try:
        with pytest.raises((ValueError, OSError)):
            producer.inspect(identifier)
        assert producer.result.read_bytes() == PAYLOAD
    finally:
        saved.rename(path)


@pytest.mark.parametrize('change', ['pending', 'foreign', 'replaced', 'active'])
def test_pending_foreign_replaced_or_active_registration_refuses(producer, change):
    identifier = producer.finalize()
    request = producer.inspect(identifier)
    registration = capture.capture_status(producer.handle, identifier)
    slot = Path(registration['slot']['path'])
    path = slot / 'registration.json'
    before = path.read_bytes()
    try:
        if change in ('pending', 'foreign'):
            changed = copy.deepcopy(registration)
            if change == 'pending':
                changed['state'] = 'sealing'
            else:
                changed['intent']['producer']['caller']['uid'] += 1
            path.write_bytes(logical.encoded(changed))
            with pytest.raises(ValueError):
                producer.inspect(identifier)
        elif change == 'replaced':
            saved = slot.with_name(slot.name + '-saved')
            slot.rename(saved)
            slot.mkdir(mode=0o700)
            try:
                (slot / 'registration.json').write_bytes(before)
                (slot / 'registration.json').chmod(0o600)
                with pytest.raises(ValueError, match='replaced'):
                    producer.inspect(identifier)
            finally:
                (slot / 'registration.json').unlink()
                slot.rmdir()
                saved.rename(slot)
        else:
            sealed_store = retention.Store(request['sealed']['owner']['journal'])
            with sealed_store.session(run=request['sealed']['allocation']['run']):
                with pytest.raises(ValueError, match='active|owner|finished'):
                    producer.inspect(identifier)
    finally:
        path.write_bytes(before)
    assert producer.result.read_bytes() == PAYLOAD
    assert producer.inspect(identifier) == request


@pytest.mark.parametrize('change', [
    'version-bool', 'unknown-request', 'unknown-producer', 'unknown-sealed',
    'unknown-mapping', 'allocation-bool', 'identity-bool', 'duplicate-mapping',
    'wrong-origin', 'consumer-extra', 'producer-attempt',
])
def test_strict_capture_request_wire_shapes(producer, change):
    request = producer.inspect(producer.finalize())
    changed = copy.deepcopy(request)
    if change == 'version-bool':
        changed['version'] = True
    elif change == 'unknown-request':
        changed['extra'] = None
    elif change == 'unknown-producer':
        changed['producer']['extra'] = None
    elif change == 'unknown-sealed':
        changed['sealed']['extra'] = None
    elif change == 'unknown-mapping':
        changed['sealed']['mappings'][0]['extra'] = None
    elif change == 'allocation-bool':
        changed['sealed']['allocation']['device'] = True
    elif change == 'identity-bool':
        changed['sealed']['mappings'][0]['identity'][1] = True
    elif change == 'duplicate-mapping':
        changed['sealed']['mappings'].append(copy.deepcopy(changed['sealed']['mappings'][0]))
    elif change == 'wrong-origin':
        changed['sealed']['mappings'][0]['original_path'] += '.foreign'
    elif change == 'consumer-extra':
        changed['consumers'][CONSUMER]['extra'] = None
    else:
        changed['producer']['attempt'] = 'e' * 32
        changed['capture_id'] = logical.digest(changed['producer'])
    changed['request_sha256'] = logical.digest(
        {key: value for key, value in changed.items() if key != 'request_sha256'})
    with pytest.raises(ValueError):
        capture._validate_request(changed)
    assert producer.inspect(request['capture_id']) == request


@pytest.mark.parametrize('change', [
    'original-extra', 'original-identity-bool', 'missing-original',
    'duplicate-original', 'foreign-original-member', 'file-progress-bool',
    'file-progress-extra',
])
def test_registration_validates_finite_original_and_partial_file_identities(
        producer, change):
    identifier = producer.finalize()
    registration = capture.capture_status(producer.handle, identifier)
    changed = copy.deepcopy(registration)
    original = changed['intent']['originals'][0]
    member = producer.record()['members'][0]['member_id']
    if change == 'original-extra':
        original['extra'] = None
    elif change == 'original-identity-bool':
        original['identity'][1] = True
    elif change == 'missing-original':
        changed['intent']['originals'] = []
    elif change == 'duplicate-original':
        changed['intent']['originals'].append(copy.deepcopy(original))
    elif change == 'foreign-original-member':
        original['member_id'] = 'f' * 64
    elif change == 'file-progress-bool':
        changed['files'][member][1] = True
    else:
        changed['files']['f' * 64] = [1, 2]
    with pytest.raises(ValueError):
        capture._checked_registration(changed)
    assert producer.inspect(identifier)['capture_id'] == identifier


def test_root_safety_witness_precedes_caller_catalogue_even_on_interruption(
        producer, tmp_path, monkeypatch):
    identifier = producer.finalize()
    registration = capture.capture_status(producer.handle, identifier)
    caller_path = Path(registration['slot']['path']) / 'registration.json'
    original_catalogue = caller_path.read_bytes()
    # Exercise the real privileged writer with identity-only host doubles.
    # Its private root descriptor and caller catalogue remain separate real files.
    privileged = copy.deepcopy(registration)
    privileged['intent']['producer']['owner']['identity']['uid'] = 0
    root_slot = tmp_path / 'private-root-witness'
    root_slot.mkdir(mode=0o700)
    root_os = SimpleNamespace(**vars(os))
    root_os.geteuid = lambda: 0

    @contextmanager
    def authenticated_identity(uid, gid):
        assert dict(uid=uid, gid=gid) == registration['intent']['producer']['caller']
        yield

    def interrupt_after_witness(stage):
        assert stage == 'witness'
        assert (root_slot / 'witness.json').read_bytes() == logical.encoded(privileged)
        assert caller_path.read_bytes() == original_catalogue
        raise SimulatedInterrupt('root witness committed; catalogue not exposed')

    try:
        with retention.directory_descriptor(root_slot) as fd:
            with monkeypatch.context() as local:
                local.setattr(capture, 'os', root_os)
                local.setattr(capture, '_identity', authenticated_identity)
                local.setattr(capture, 'checkpoint', interrupt_after_witness)
                with pytest.raises(SimulatedInterrupt):
                    capture._publish_registration(fd, privileged)
            assert caller_path.read_bytes() == original_catalogue
            assert not (root_slot / 'registration.json').exists()
            with monkeypatch.context() as local:
                local.setattr(capture, 'os', root_os)
                local.setattr(capture, '_identity', authenticated_identity)
                capture._publish_registration(fd, privileged)
        pointer = json.loads(caller_path.read_bytes())
        assert pointer == dict(schema='onpc-sealed-witness', version=1,
                               capture_id=identifier,
                               request_sha256=registration['request']['request_sha256'],
                               witness_sha256=logical.digest(privileged), state='sealed')
        assert (root_slot / 'registration.json').read_bytes() == logical.encoded(privileged)
    finally:
        caller_path.write_bytes(original_catalogue)


def test_captured_unpublished_input_cannot_be_discarded(tmp_path, monkeypatch):
    with producer_session(tmp_path, monkeypatch) as value:
        identifier = value.finalize()
        request = value.inspect(identifier)
    before = (value.store.path / 'current.json').read_bytes()
    with pytest.raises(ValueError, match='capture'):
        value.store.discard_unpublished_input(value.source)
    assert (value.store.path / 'current.json').read_bytes() == before
    assert value.result.read_bytes() == PAYLOAD
    assert value.inspect(identifier) == request


@pytest.mark.parametrize('captured_owner', ['source', 'destination'])
def test_input_claim_transfer_refuses_either_captures_bearing_owner(
        tmp_path, monkeypatch, captured_owner):
    journal = 'retention-batch' if captured_owner == 'source' else 'retention-fixture'
    with producer_session(tmp_path, monkeypatch, journal_name=journal) as value:
        identifier = value.finalize()
        request = value.inspect(identifier)
    source = (value.store if captured_owner == 'source' else
              retention.Store(value.store.path.with_name('retention-batch')))
    destination = (value.store if captured_owner == 'destination' else
                   retention.Store(value.store.path.with_name('retention-fixture')))
    peer = destination if captured_owner == 'source' else source
    with peer.session():
        pass
    before = {store.path: (store.path / 'current.json').read_bytes()
              for store in (source, destination)}
    with pytest.raises(ValueError, match='capture'):
        input_transfer.transfer(
            source, destination, value.source, selector='check_capture_fixture',
            vm='fixture', verify=lambda _path: pytest.fail('capture barrier reached input verifier'))
    for store in (source, destination):
        assert (store.path / 'current.json').read_bytes() == before[store.path]
        assert not (store.path / input_transfer.MARKER).exists()
    assert value.result.read_bytes() == PAYLOAD
    assert value.inspect(identifier) == request


@pytest.mark.parametrize('boundary', ['copy', 'finished'])
@pytest.mark.parametrize('replacement', ['file', 'allocation', 'nested-directory'])
def test_replaced_source_path_refuses_before_readable_seal(
        producer, monkeypatch, boundary, replacement):
    record = producer.record()
    original_file = producer.result
    if replacement == 'nested-directory':
        directory = producer.source / 'nested'
        directory.mkdir(mode=0o700)
        original_file = directory / producer.result.name
        producer.result.rename(original_file)
        record.pop('closure_sha256')
        record['members'][0].pop('member_id')
        record['members'][0]['original_path'] = str(original_file)
        record = logical.finalize_record(record)
    target = (producer.source if replacement == 'allocation' else
              original_file.parent if replacement == 'nested-directory' else original_file)
    saved = target.with_name(target.name + '-owned-original')
    replaced = False

    def replace():
        nonlocal replaced
        if replaced:
            return
        replaced = True
        target.rename(saved)
        if replacement == 'file':
            target.write_bytes(PAYLOAD)
            target.chmod(0o600)
        else:
            target.mkdir(mode=0o700)
            (target / original_file.name).write_bytes(PAYLOAD)
            (target / original_file.name).chmod(0o600)

    real_hash = capture._hash

    def copy_and_replace(fd, size, output=None):
        result = real_hash(fd, size, output)
        if output is not None:
            replace()
        return result

    def finished_and_replace(stage):
        if stage == 'finished':
            replace()

    try:
        with monkeypatch.context() as local:
            if boundary == 'copy':
                local.setattr(capture, '_hash', copy_and_replace)
            else:
                local.setattr(capture, 'checkpoint', finished_and_replace)
            with pytest.raises(ValueError, match='replaced|changed|identity'):
                producer.finalize(record)
        state = json.loads((producer.store.path / 'current.json').read_bytes())
        assert len(state['captures']) == 1
        identifier = state['captures'][0]['capture_id']
        registration = capture.capture_status(producer.handle, identifier)
        assert registration['state'] == 'sealing' and registration['request'] is None
        assert Path(state['captures'][0]['path']).is_dir()
        with pytest.raises(ValueError, match='pending|sealed'):
            producer.inspect(identifier)
        assert (saved if replacement == 'file' else saved / original_file.name).read_bytes() == PAYLOAD
    finally:
        if replaced:
            if replacement == 'file':
                target.unlink()
            else:
                (target / original_file.name).unlink()
                target.rmdir()
            saved.rename(target)
        if replacement == 'nested-directory':
            original_file.rename(producer.result)
            original_file.parent.rmdir()


@pytest.mark.parametrize('commit', [False, True])
@pytest.mark.parametrize('operation', ['snapshot-retain', 'file-registration'])
def test_registration_failure_resumes_same_slot_without_unregistered_payload(
        producer, monkeypatch, operation, commit):
    interrupted = False
    real_retain = retention.retain
    real_publish = capture._publish_registration

    def retain_failure(path, **kwargs):
        nonlocal interrupted
        if Path(path).name == 'snapshot' and not interrupted:
            interrupted = True
            if commit:
                real_retain(path, **kwargs)
            raise SimulatedInterrupt('snapshot registration boundary')
        return real_retain(path, **kwargs)

    def publish_failure(fd, registration):
        nonlocal interrupted
        if (registration['state'] == 'sealing' and registration['files']
                and not interrupted):
            interrupted = True
            if commit:
                real_publish(fd, registration)
            raise SimulatedInterrupt('per-file registration boundary')
        return real_publish(fd, registration)

    with monkeypatch.context() as local:
        if operation == 'snapshot-retain':
            local.setattr(retention, 'retain', retain_failure)
        else:
            local.setattr(capture, '_publish_registration', publish_failure)
        with pytest.raises(SimulatedInterrupt):
            producer.finalize()
    state = json.loads((producer.store.path / 'current.json').read_bytes())
    assert len(state['captures']) == 1
    charge = copy.deepcopy(state['captures'][0])
    identifier = charge['capture_id']
    slot = Path(charge['path'])
    slot_inode = slot.stat().st_ino
    status = capture.capture_status(producer.handle, identifier)
    assert status['state'] == 'sealing' and status['request'] is None
    snapshot = slot / 'snapshot'
    sealed_state = json.loads((slot / 'retention-sealed/current.json').read_bytes())
    if snapshot.exists():
        info = snapshot.stat()
        assert sealed_state['paths'] == [dict(path=str(snapshot), device=info.st_dev,
                                            inode=info.st_ino, mode=0o700)]
        assert set(path.name for path in snapshot.iterdir()) == set(status['files'])
    else:
        assert sealed_state['paths'] == []
    identities = {name: (snapshot / name).stat().st_ino for name in status['files']}
    assert producer.result.read_bytes() == PAYLOAD
    assert producer.finalize() == identifier
    after = json.loads((producer.store.path / 'current.json').read_bytes())
    assert after['captures'] == [charge]
    assert slot.stat().st_ino == slot_inode
    assert producer.inspect(identifier)['record'] == producer.record()
    for name, inode in identities.items():
        assert (snapshot / name).stat().st_ino == inode


def test_unmask_interruption_closes_the_just_registered_output_descriptor(
        producer, monkeypatch):
    real_open = os.open
    output = []
    member_id = producer.record()['members'][0]['member_id']
    interrupted = False

    def track_open(path, flags, *args, **kwargs):
        fd = real_open(path, flags, *args, **kwargs)
        if path == member_id and flags & os.O_WRONLY:
            output.append(fd)
        return fd

    def interrupted_unmask(how, _mask):
        nonlocal interrupted
        if how == capture.signal.SIG_SETMASK and output and not interrupted:
            interrupted = True
            raise SimulatedInterrupt('mask restoration before output fdopen')
        return set()

    with monkeypatch.context() as local:
        local.setattr(capture.os, 'open', track_open)
        local.setattr(capture.signal, 'pthread_sigmask', interrupted_unmask)
        with pytest.raises(SimulatedInterrupt):
            producer.finalize()
    assert len(output) == 1
    with pytest.raises(OSError):
        os.fstat(output[0])
    state = json.loads((producer.store.path / 'current.json').read_bytes())
    assert len(state['captures']) == 1
    identifier = state['captures'][0]['capture_id']
    assert producer.result.read_bytes() == PAYLOAD
    assert producer.finalize() == identifier
    assert producer.inspect(identifier)['record'] == producer.record()


def test_capture_selection_enforces_combined_source_budget_limit(producer, monkeypatch):
    identifiers = [producer.finalize()]
    for number in range(2):
        handle = capture.issue_session(
            producer.store, repository=producer.checkout, workflow='capture-fixture',
            task='P03', check=f'budget-source-{number}', target='',
            inputs_sha256='c' * 64, sources_sha256='d' * 64,
            consumers={CONSUMER: dict(consumer_id=CONSUMER, revision_sha256=REVISION)})
        context = capture.session_context(handle)
        identifiers.append(capture.finalize_capture(
            handle, record=producer.record(context=context), consumer_ids=[CONSUMER]))
    assert bundle.MAX_SOURCE_BUDGETS == 64
    with monkeypatch.context() as local:
        local.setattr(bundle, 'MAX_SOURCE_BUDGETS', 2)
        with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                              [], [], [], captures=identifiers[:2]) as selected:
            assert len(selected.manifest['source_budgets']) == 2
            assert len(selected.manifest['records']) == 2
        with pytest.raises(ValueError, match='source.*budget|budget.*source'):
            with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                                  [], [], [], captures=identifiers):
                pytest.fail('capture selection exceeded its finite source-budget bound')
    assert producer.result.read_bytes() == PAYLOAD
    assert all(producer.inspect(identifier)['capture_id'] == identifier
               for identifier in identifiers)


def test_named_capture_targets_require_canonical_registry_names(
        producer, tmp_path, monkeypatch):
    from tests.integration import vm_config

    config = tmp_path / 'fixture-vms.json'
    config.write_text(json.dumps(dict(vms=[dict(name='Fixture-Guest', id='7',
                                               disk_anchor='/fixture/guest.qcow2',
                                               enabled='false', package_format='deb')])))
    monkeypatch.setattr(vm_config, 'CONFIG', config)
    monkeypatch.setitem(sys.modules, 'vm_config', vm_config)
    options = dict(repository=producer.checkout, workflow='capture-fixture',
                   task='P03', check='canonical-target', inputs_sha256='c' * 64,
                   sources_sha256='d' * 64,
                   consumers={CONSUMER: dict(consumer_id=CONSUMER,
                                             revision_sha256=REVISION)})
    handle = capture.issue_session(producer.store, target='Fixture-Guest', **options)
    assert capture.session_context(handle)['target'] == 'Fixture-Guest'
    before = (producer.store.path / 'current.json').read_bytes()
    for target in ('7', 'Unknown-Guest', 'fixture-guest'):
        with pytest.raises(ValueError, match='canonical|registered'):
            capture.issue_session(producer.store, target=target, **options)
    assert (producer.store.path / 'current.json').read_bytes() == before

