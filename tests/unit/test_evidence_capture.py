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


@pytest.mark.parametrize('foreign', [False, True])
def test_checkout_private_writable_group_uses_shared_bundle_trust_policy(
        producer, monkeypatch, foreign):
    producer.checkout.chmod(0o775)
    user = bundle.pwd.getpwuid(os.geteuid()).pw_name
    monkeypatch.setattr(bundle.grp, 'getgrgid', lambda gid: SimpleNamespace(
        gr_mem=['another-account'] if foreign else [user]))
    monkeypatch.setattr(bundle.pwd, 'getpwall', lambda: [])
    if foreign:
        with pytest.raises(ValueError, match='unsafe writable group'):
            capture.session_context(producer.handle)
    else:
        assert capture.session_context(producer.handle) == producer.context


@pytest.mark.parametrize('intent', [None, [], 'recording_source'])
def test_malformed_optional_source_intent_refuses_as_invalid_metadata(producer, intent):
    producer.finalize()
    charge = json.loads((producer.store.path / 'current.json').read_bytes())['captures'][0]
    registration = capture._registration(charge)
    registration['intent'] = intent
    with pytest.raises(ValueError, match='invalid capture intent'):
        capture._checked_registration(registration)
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


def artifact_helper(producer, monkeypatch):
    script = runpy.run_path(str(ROOT / 'tools/onpc-test-artifacts'))
    main = script['main']
    monkeypatch.setitem(main.__globals__, 'CHECKOUT', str(producer.checkout))
    monkeypatch.setitem(main.__globals__, 'caller',
                        lambda: (os.geteuid(), os.getegid()))
    return main


@pytest.fixture
def helper(producer, monkeypatch):
    return artifact_helper(producer, monkeypatch)


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
     '--operation', 'acknowledge'],
    ['bundle-acknowledge', '--capture', 'short', '--expect', 'b' * 64],
    ['bundle-acknowledge', '--capture', 'a' * 64, '--expect', 'short'],
    ['bundle-acknowledge', '--capture', 'a' * 64, '--expect', 'b' * 64,
     '--destination', '/caller/receipt'],
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


def test_helper_publishes_real_capture_and_keeps_source_until_owner_acknowledges(
        producer, helper, capsys):
    identifier = producer.finalize()
    request = producer.inspect(identifier)
    assert helper(['bundle-plan', '--capture', identifier]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert helper(['bundle-export', '--capture', identifier,
                   '--expect', plan['selection_sha256']]) == 0
    receipt = json.loads(capsys.readouterr().out)
    verified = bundle.inspect(producer.checkout, os.geteuid(), os.getegid(), receipt['path'])
    assert verified['manifest']['records'] == [producer.record()]
    assert len(verified['manifest']['member_map']) == 1
    assert producer.result.read_bytes() == PAYLOAD
    before = (producer.store.path / 'current.json').read_bytes()
    # The authenticated helper cannot seize an active producer's owner lock.
    assert helper(['bundle-acknowledge', '--capture', identifier,
                   '--expect', request['request_sha256']]) == 2
    refused = capsys.readouterr()
    assert not refused.out and refused.err
    assert (producer.store.path / 'current.json').read_bytes() == before
    capture.acknowledge_capture(producer.checkout, os.geteuid(), os.getegid(), identifier,
                                expected=request['request_sha256'], session_handle=producer.handle)
    assert producer.result.read_bytes() == PAYLOAD


def test_helper_acknowledges_only_registered_delivery_of_finished_source(
        tmp_path, monkeypatch, capsys):
    with producer_session(tmp_path, monkeypatch) as value:
        identifier = value.finalize()
        request = value.inspect(identifier)
        receipt = publish_capture(value, identifier)
        helper_main = artifact_helper(value, monkeypatch)
    assert helper_main(['bundle-acknowledge', '--capture', identifier,
                        '--expect', request['request_sha256']]) == 0
    acknowledgement = json.loads(capsys.readouterr().out)
    assert acknowledgement['request'] == request
    state = json.loads((value.store.path / 'current.json').read_bytes())
    assert state['captures'][0]['acknowledgement'] == acknowledgement
    assert value.result.read_bytes() == PAYLOAD
    assert bundle.inspect(value.checkout, os.geteuid(), os.getegid(), receipt['path'])[
        'manifest']['records'] == [request['record']]


def publish_capture(producer, identifier=None, **kwargs):
    identifier = identifier or producer.finalize()
    with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                          [], [], [], captures=[identifier]) as selected:
        return bundle.export(selected, expected=selected.plan()['selection_sha256'], **kwargs)


def acknowledge(producer, identifier, expected=None):
    request = producer.inspect(identifier)
    return capture.acknowledge_capture(
        producer.checkout, os.geteuid(), os.getegid(), identifier,
        expected=expected or request['request_sha256'], session_handle=producer.handle)


def test_library_publication_and_acknowledgement_verify_complete_logical_closure(producer):
    identifier = producer.finalize()
    request = producer.inspect(identifier)
    receipt = publish_capture(producer, identifier)
    published = bundle.inspect(producer.checkout, os.geteuid(), os.getegid(), receipt['path'])
    manifest = published['manifest']
    assert manifest['records'] == [request['record']]
    assert len(manifest['member_map']) == len(request['sealed']['mappings']) == 1
    record = request['record']
    member = record['members'][0]
    assert bundle.inspect(producer.checkout, os.geteuid(), os.getegid(), receipt['path'],
                          record_id=record['record_id'], member_id=member['member_id'],
                          closure_sha256=record['closure_sha256']) == PAYLOAD
    before = json.loads((producer.store.path / 'current.json').read_bytes())
    assert not before['captures'][0].get('acknowledgement')
    assert producer.result.read_bytes() == PAYLOAD
    acknowledge(producer, identifier)
    after = json.loads((producer.store.path / 'current.json').read_bytes())
    acknowledgement = after['captures'][0]['acknowledgement']
    assert acknowledgement
    assert after['paths'] == before['paths'] and after['history'] == before['history']
    assert producer.result.read_bytes() == PAYLOAD
    assert producer.inspect(identifier) == request


def test_publication_preserves_complete_selected_dependency_closure(producer):
    first = producer.finalize()
    dependency = producer.record()
    handle = capture.issue_session(
        producer.store, repository=producer.checkout, workflow='capture-fixture',
        task='P03', check='dependent-capture', inputs_sha256='c' * 64,
        sources_sha256='d' * 64,
        consumers={CONSUMER: dict(consumer_id=CONSUMER, revision_sha256=REVISION)},
        dependencies=[dependency])
    record = producer.record(context=capture.session_context(handle),
        dependencies=[dict(record_id=dependency['record_id'],
                           closure_sha256=dependency['closure_sha256'])])
    second = capture.finalize_capture(handle, record=record, consumer_ids=[CONSUMER])
    with pytest.raises(ValueError, match='dependenc'):
        with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                              [], [], [], captures=[second]):
            pytest.fail('incomplete dependency publication was admitted')
    with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                          [], [], [], captures=sorted([first, second])) as selection:
        receipt = bundle.export(selection, expected=selection.selection_sha256)
    verified = bundle.inspect(producer.checkout, os.geteuid(), os.getegid(), receipt['path'])
    assert {item['record_id'] for item in verified['manifest']['records']} == {
        dependency['record_id'], record['record_id']}
    acknowledge(producer, first)
    request = producer.inspect(second)
    capture.acknowledge_capture(producer.checkout, os.geteuid(), os.getegid(), second,
        expected=request['request_sha256'], session_handle=handle)
    assert producer.result.read_bytes() == PAYLOAD


def test_cumulative_history_crosses_selection_limit_and_resumes_exact_publication(producer, monkeypatch):
    import capture_publication as publication

    identifiers, handles = [], []
    for number in range(capture.MAX_SELECTIONS):
        handle = capture.issue_session(
            producer.store, repository=producer.checkout, workflow='capture-fixture', task='P03',
            check='history-' + str(number), inputs_sha256='c' * 64, sources_sha256='d' * 64,
            consumers={CONSUMER: dict(consumer_id=CONSUMER, revision_sha256=REVISION)})
        record = producer.record(context=capture.session_context(handle))
        identifiers.append(capture.finalize_capture(handle, record=record, consumer_ids=[CONSUMER]))
        handles.append(handle)
    # Each batch also leaves room for the inherited publication's budget entry.
    batch = bundle.MAX_SOURCE_BUDGETS - 1
    for start in range(0, len(identifiers), batch):
        with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                              [], [], [], captures=identifiers[start:start + batch]) as selected:
            previous = bundle.export(selected, expected=selected.selection_sha256)
    old = producer.inspect(identifiers[0])
    # Another finished producer contributes one valid selection to the same
    # workflow; its history must not inherit the single-call selection limit.
    later = retention.Store(storage.directory('state') / 'retention-batch')
    with later.session() as run:
        source = Path(retention.allocate(tempfile.mkdtemp, prefix='onpc-later-proof-'))
        result = source / 'result.json'
        result.write_bytes(PAYLOAD)
        result.chmod(0o600)
        info = source.stat()
        allocation = dict(path=str(source), device=info.st_dev, inode=info.st_ino,
                          mode=0o700, journal=str(later.path), run=run)
        handle = capture.issue_session(
            later, repository=producer.checkout, workflow='capture-fixture', task='P03',
            check='next-producer', inputs_sha256='c' * 64, sources_sha256='d' * 64,
            consumers={CONSUMER: dict(consumer_id=CONSUMER, revision_sha256=REVISION)})
        member = dict(producer.record()['members'][0], original_path=str(result),
                      source_allocation=allocation)
        member.pop('member_id')
        context = capture.session_context(handle)
        record = producer.record(context=context, members=[member], cleanup=dict(
            state='complete', record_members=[], scope=dict(owner=context['owner'], resources=[])))
        identifier = capture.finalize_capture(handle, record=record, consumer_ids=[CONSUMER])
        with pytest.raises(ValueError, match='256 explicit sources'):
            with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                                  [], [], [], captures=[*identifiers, identifier]):
                pytest.fail('oversized individual selection accepted')
        def interrupt(stage):
            if stage == 'publication.committed':
                raise KeyboardInterrupt('private history-boundary interruption')
        with monkeypatch.context() as patch:
            patch.setattr(publication, 'checkpoint', interrupt)
            with pytest.raises(KeyboardInterrupt):
                publish_capture(producer, identifier)
        request = producer.inspect(identifier)
        parent = bundle.plan_parent(producer.checkout, publication._namespace(request))
        pending = json.loads((parent / 'retention' / publication.JOURNAL).read_bytes())['pending']
        assert len(pending['requests']) == capture.MAX_SELECTIONS + 1
        receipt = publish_capture(producer, identifier)
        assert str(Path(receipt['path']).parent) == pending['allocation']['path']
        assert receipt['path'] != previous['path'] and receipt['cleanup_complete']
        for item in (old, request):
            proof = item['record']
            assert bundle.inspect(producer.checkout, os.geteuid(), os.getegid(), receipt['path'],
                record_id=proof['record_id'], member_id=proof['members'][0]['member_id'],
                closure_sha256=proof['closure_sha256']) == PAYLOAD
        capture.acknowledge_capture(producer.checkout, os.geteuid(), os.getegid(), identifier,
            expected=request['request_sha256'], session_handle=handle)
    capture.acknowledge_capture(producer.checkout, os.geteuid(), os.getegid(), identifiers[0],
        expected=old['request_sha256'], session_handle=handles[0])
    assert producer.result.read_bytes() == PAYLOAD


@pytest.mark.parametrize('boundary', [
    'publication.registered', 'publication.copied', 'publication.committed',
    'publication.locator', 'publication.delivered',
])
@pytest.mark.parametrize('failure', [KeyboardInterrupt, RuntimeError])
def test_publication_interruption_recovers_same_registered_allocation(
        producer, monkeypatch, boundary, failure):
    import capture_publication as publication

    identifier = producer.finalize()
    source_state = (producer.store.path / 'current.json').read_bytes()

    def interrupt(stage):
        if stage == boundary:
            raise failure('private publication cancellation')

    with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                          [], [], [], captures=[identifier]) as selected:
        parent = selected.publication_parent(create=True)
        with monkeypatch.context() as local:
            local.setattr(publication, 'checkpoint', interrupt)
            with pytest.raises(failure):
                bundle.export(selected, expected=selected.selection_sha256)
    stages = {path: path.stat().st_ino for path in parent.iterdir()
              if path.name.startswith('onpc-evidence-bundle-')}
    assert len(stages) == 1
    assert (producer.store.path / 'current.json').read_bytes() == source_state
    assert producer.result.read_bytes() == PAYLOAD
    assert producer.previous_proof.read_bytes() == b'prior finished evidence\n'
    receipt = publish_capture(producer, identifier)
    assert Path(receipt['path']).parent in stages
    assert {path: path.stat().st_ino for path in stages} == stages
    assert {path for path in parent.iterdir()
            if path.name.startswith('onpc-evidence-bundle-')} == set(stages)
    assert receipt['cleanup_complete']
    assert not (parent / 'retention' / retention.PUBLICATION).exists()
    assert (producer.store.path / 'current.json').read_bytes() == source_state
    acknowledge(producer, identifier)


def test_lost_publication_and_ack_replies_retry_without_extra_allocations(producer):
    identifier = producer.finalize()
    first = publish_capture(producer, identifier)
    first_path = Path(first['path'])
    identity = (first_path.parent.stat().st_ino, first_path.stat().st_ino)
    second = publish_capture(producer, identifier)
    assert second == first
    assert (first_path.parent.stat().st_ino, first_path.stat().st_ino) == identity
    first_ack = acknowledge(producer, identifier)
    state = (producer.store.path / 'current.json').read_bytes()
    assert acknowledge(producer, identifier) == first_ack
    assert (producer.store.path / 'current.json').read_bytes() == state
    assert producer.result.read_bytes() == PAYLOAD


def test_lost_helper_export_reply_reuses_original_expected_selection(
        producer, helper, capsys):
    identifier = producer.finalize()
    assert helper(['bundle-plan', '--capture', identifier]) == 0
    expected = json.loads(capsys.readouterr().out)['selection_sha256']
    arguments = ['bundle-export', '--capture', identifier, '--expect', expected]
    assert helper(arguments) == 0
    receipt = json.loads(capsys.readouterr().out)
    archive = Path(receipt['path'])
    identity = (archive.parent.stat().st_ino, archive.stat().st_ino)
    assert helper(arguments) == 0
    assert json.loads(capsys.readouterr().out) == receipt
    assert (archive.parent.stat().st_ino, archive.stat().st_ino) == identity
    assert producer.result.read_bytes() == PAYLOAD


@pytest.mark.parametrize('replacement', [False, True])
def test_partial_copy_recovers_same_files_and_refuses_replacement(
        producer, monkeypatch, replacement):
    identifier = producer.finalize()
    real_stream = bundle.stream_bytes
    copied = False

    def partial_copy(stream, size, output=None):
        nonlocal copied
        if output is not None and not copied:
            copied = True
            output.write(stream.read(max(1, size // 2)))
            raise SimulatedInterrupt('private interruption in payload copy')
        return real_stream(stream, size, output)

    with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                          [], [], [], captures=[identifier]) as selected:
        expected = selected.selection_sha256
        parent = selected.publication_parent(create=True)
        with monkeypatch.context() as local:
            local.setattr(bundle, 'stream_bytes', partial_copy)
            with pytest.raises(SimulatedInterrupt):
                bundle.export(selected, expected=expected)
    stages = [path for path in parent.iterdir() if path.name.startswith('onpc-evidence-bundle-')]
    assert len(stages) == 1
    stage = stages[0]
    files = {path.name: path.stat().st_ino for path in stage.iterdir()}
    assert set(files) == {'evidence.zip', 'receipt.json'}
    assert (stage / 'evidence.zip').stat().st_size > 0
    if replacement:
        archive = stage / 'evidence.zip'
        saved = stage / 'evidence.owned-saved'
        archive.rename(saved)
        archive.write_bytes(saved.read_bytes())
        archive.chmod(0o600)
        # Keep only the expected names; the original remains privately owned.
        preserved = stage.with_name(stage.name + '-owned-file')
        saved.rename(preserved)
        try:
            with pytest.raises(ValueError, match='replaced|identity'):
                publish_capture(producer, identifier)
            assert archive.exists() and preserved.exists()
        finally:
            archive.unlink()
            preserved.rename(archive)
    with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                          [], [], [], captures=[identifier]) as selected:
        assert selected.selection_sha256 == expected
        receipt = bundle.export(selected, expected=expected)
    assert Path(receipt['path']).parent == stage
    assert {path.name: path.stat().st_ino for path in stage.iterdir()} == files
    assert producer.result.read_bytes() == PAYLOAD
    acknowledge(producer, identifier)


@pytest.mark.parametrize('failure', ['second-create', 'first-registration', 'registration-reply'])
def test_stage_initialization_failure_recovers_registered_allocation(
        producer, monkeypatch, failure):
    import capture_publication as publication

    identifier = producer.finalize()
    before = (producer.store.path / 'current.json').read_bytes()
    real_open = publication.os.open
    real_save = publication._save
    failed = False

    def failed_create(path, flags, *args, **kwargs):
        nonlocal failed
        if path == 'receipt.json' and flags & os.O_CREAT and not failed:
            failed = True
            raise OSError('private second stage file creation failure')
        return real_open(path, flags, *args, **kwargs)

    def failed_registration(store, fd, state, request, **kwargs):
        nonlocal failed
        pending = state.get('pending')
        if pending is not None and len(pending.get('files') or {}) == 1 and not failed:
            failed = True
            if failure == 'registration-reply':
                real_save(store, fd, state, request, **kwargs)
            raise OSError('private first stage file registration failure')
        return real_save(store, fd, state, request, **kwargs)

    with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                          [], [], [], captures=[identifier]) as selected:
        parent = selected.publication_parent(create=True)
        with monkeypatch.context() as local:
            if failure == 'second-create':
                local.setattr(publication.os, 'open', failed_create)
            else:
                local.setattr(publication, '_save', failed_registration)
            with pytest.raises(OSError, match='private .*stage file'):
                bundle.export(selected, expected=selected.selection_sha256)
    assert failed
    stages = [path for path in parent.iterdir() if path.name.startswith('onpc-evidence-bundle-')]
    assert len(stages) == 1
    stage = stages[0]
    stage_inode = stage.stat().st_ino
    files = {path.name: path.stat().st_ino for path in stage.iterdir()}
    assert set(files) <= {'evidence.zip', 'receipt.json'}
    assert (producer.store.path / 'current.json').read_bytes() == before
    assert producer.result.read_bytes() == PAYLOAD
    receipt = publish_capture(producer, identifier)
    assert Path(receipt['path']).parent == stage and stage.stat().st_ino == stage_inode
    assert all((stage / name).stat().st_ino == inode for name, inode in files.items())
    assert receipt['cleanup_complete']
    acknowledge(producer, identifier)


def test_pending_request_without_stage_rechecks_complete_budget_before_allocation(
        producer, monkeypatch):
    import capture_publication as publication

    identifier = producer.finalize()
    original = (producer.store.path / 'current.json').read_bytes()

    def failed_factory(**_kwargs):
        raise OSError('private allocation failure before stage registration')

    with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                          [], [], [], captures=[identifier]) as selected:
        parent = selected.publication_parent(create=True)
        with monkeypatch.context() as local:
            local.setattr(publication.tempfile, 'mkdtemp', failed_factory)
            with pytest.raises(OSError, match='private allocation'):
                bundle.export(selected, expected=selected.selection_sha256)
    assert not list(parent.glob('onpc-evidence-bundle-*'))
    journal = (parent / 'retention' / publication.JOURNAL).read_bytes()
    with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                          [], [], [], captures=[identifier]) as selected:
        with monkeypatch.context() as local:
            local.setattr(retention, 'MAX_RETAINED_BYTES', selected.projected_bytes)
            local.setattr(publication.tempfile, 'mkdtemp',
                          lambda **_kwargs: pytest.fail('capacity refusal allocated a stage'))
            with pytest.raises(ValueError, match='budget|capacity'):
                bundle.export(selected, expected=selected.selection_sha256)
    assert (parent / 'retention' / publication.JOURNAL).read_bytes() == journal
    assert (producer.store.path / 'current.json').read_bytes() == original
    assert producer.result.read_bytes() == PAYLOAD
    receipt = publish_capture(producer, identifier)
    with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                          [], [], [], captures=[identifier]) as selected:
        budget = selected.plan()['export_budget']
        assert budget['existing_allocated_bytes'] > 0
        assert budget['projected_bytes'] == 0
        assert budget['simultaneous_bytes'] == budget['existing_allocated_bytes']
    assert receipt['cleanup_complete']
    acknowledge(producer, identifier)


def test_partial_stage_retry_refuses_budget_that_cannot_finish_without_rewriting(
        producer, monkeypatch):
    identifier = producer.finalize()
    real_stream = bundle.stream_bytes
    interrupted = False

    def partial(stream, size, output=None):
        nonlocal interrupted
        if output is not None and not interrupted:
            interrupted = True
            output.write(stream.read(max(1, size // 2)))
            raise SimulatedInterrupt('private partial-stage capacity fixture')
        return real_stream(stream, size, output)

    with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                          [], [], [], captures=[identifier]) as selected:
        parent = selected.publication_parent(create=True)
        with monkeypatch.context() as local:
            local.setattr(bundle, 'stream_bytes', partial)
            with pytest.raises(SimulatedInterrupt):
                bundle.export(selected, expected=selected.selection_sha256)
    stage, = (path for path in parent.iterdir() if path.name.startswith('onpc-evidence-bundle-'))
    before = {path.name: (path.read_bytes(), bundle.fingerprint(path.stat()))
              for path in stage.iterdir()}
    source_state = (producer.store.path / 'current.json').read_bytes()
    with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                          [], [], [], captures=[identifier]) as selected:
        # The currently allocated partial tree fits this budget. Completion and
        # its control/recovery copies need more than the projected payload alone.
        limit = selected.projected_bytes
        used = sum(path.stat().st_blocks * 512 for path in parent.rglob('*'))
        assert used < limit
        with monkeypatch.context() as local:
            local.setattr(retention, 'MAX_RETAINED_BYTES', limit)
            with pytest.raises(ValueError, match='budget|capacity|limit'):
                bundle.export(selected, expected=selected.selection_sha256)
    assert {path.name: (path.read_bytes(), bundle.fingerprint(path.stat()))
            for path in stage.iterdir()} == before
    assert (producer.store.path / 'current.json').read_bytes() == source_state
    assert producer.result.read_bytes() == PAYLOAD
    receipt = publish_capture(producer, identifier)
    assert Path(receipt['path']).parent == stage
    assert all((stage / name).stat().st_ino == identity[1]
               for name, (_, identity) in before.items())
    acknowledge(producer, identifier)


def test_more_than_three_cumulative_generations_preserve_every_required_record(producer):
    import capture_publication as publication

    first = producer.finalize()
    request = producer.inspect(first)
    initial = publish_capture(producer, first)
    delivery = publication.read_delivery(producer.checkout, os.geteuid(), os.getegid(), first)
    required = {request['record']['record_id']}
    for number in range(4):
        handle = capture.issue_session(
            producer.store, repository=producer.checkout, workflow='capture-fixture', task='P12',
            check=f'cumulative-proof-{number}', target='', inputs_sha256='c' * 64,
            sources_sha256='d' * 64,
            consumers={CONSUMER: dict(consumer_id=CONSUMER, revision_sha256=REVISION)})
        record = producer.record(context=capture.session_context(handle))
        identifier = capture.finalize_capture(handle, record=record, consumer_ids=[CONSUMER])
        required.add(record['record_id'])
        receipt = publish_capture(producer, identifier)
        verified = bundle.inspect(producer.checkout, os.geteuid(), os.getegid(), receipt['path'])
        assert {item['record_id'] for item in verified['manifest']['records']} == required
    assert not Path(initial['path']).exists()
    with publication.verified_delivery(producer.checkout, os.geteuid(), os.getegid(),
                                       first, request, delivery) as verified:
        assert {item['record_id'] for item in verified['manifest']['records']} == required
    journal = Path(delivery['journal'])
    state = json.loads((journal / 'current.json').read_bytes())
    assert len([*state['history'], state]) <= retention.RUNS_TO_KEEP
    assert len(retention.latest_allocations([*state['history'], state])) <= retention.RUNS_TO_KEEP
    assert producer.result.read_bytes() == PAYLOAD
    acknowledge(producer, first)


@pytest.mark.parametrize('boundary', ['acknowledgement', 'acknowledged'])
@pytest.mark.parametrize('failure', [KeyboardInterrupt, RuntimeError])
def test_ack_interruption_preserves_source_and_retries_exact_receipt(
        producer, monkeypatch, boundary, failure):
    identifier = producer.finalize()
    receipt = publish_capture(producer, identifier)

    def interrupt(stage):
        if stage == boundary:
            raise failure('private owner acknowledgement cancellation')

    with monkeypatch.context() as local:
        local.setattr(capture, 'checkpoint', interrupt)
        with pytest.raises(failure):
            acknowledge(producer, identifier)
    state = json.loads((producer.store.path / 'current.json').read_bytes())
    assert bool(state['captures'][0].get('acknowledgement')) == (boundary == 'acknowledged')
    assert producer.result.read_bytes() == PAYLOAD
    assert producer.previous_proof.read_bytes() == b'prior finished evidence\n'
    acknowledgement = acknowledge(producer, identifier)
    assert acknowledgement['request'] == producer.inspect(identifier)
    assert publish_capture(producer, identifier) == receipt
    assert json.loads((producer.store.path / 'current.json').read_bytes())[
        'captures'][0]['acknowledgement'] == acknowledgement


@pytest.mark.parametrize('change', ['source-changed', 'source-missing',
                                    'destination-changed', 'destination-missing'])
def test_acknowledgement_reverifies_required_source_and_destination(producer, change):
    identifier = producer.finalize()
    receipt = publish_capture(producer, identifier)
    before = (producer.store.path / 'current.json').read_bytes()
    path = producer.result if change.startswith('source') else Path(receipt['path'])
    saved = path.with_name(path.name + '.owned-saved')
    path.rename(saved)
    try:
        if change.endswith('changed'):
            path.write_bytes(b'changed bytes cannot be acknowledged\n')
            path.chmod(0o600)
        with pytest.raises((ValueError, OSError)):
            acknowledge(producer, identifier)
        assert (producer.store.path / 'current.json').read_bytes() == before
        assert saved.exists()
        assert producer.previous_proof.read_bytes() == b'prior finished evidence\n'
    finally:
        if path.exists():
            path.unlink()
        saved.rename(path)


def test_stale_request_and_wrong_authenticated_caller_cannot_acknowledge(producer):
    identifier = producer.finalize()
    publish_capture(producer, identifier)
    before = (producer.store.path / 'current.json').read_bytes()
    with pytest.raises(ValueError):
        acknowledge(producer, identifier, expected='f' * 64)
    request = producer.inspect(identifier)
    with pytest.raises((ValueError, OSError)):
        capture.acknowledge_capture(producer.checkout, os.geteuid() + 1, os.getegid(), identifier,
                                    expected=request['request_sha256'], session_handle=producer.handle)
    assert (producer.store.path / 'current.json').read_bytes() == before
    assert producer.result.read_bytes() == PAYLOAD


@pytest.mark.parametrize('change', ['attempt', 'closure', 'request'])
def test_replayed_or_forged_registration_cannot_release_source(producer, change):
    identifier = producer.finalize()
    publish_capture(producer, identifier)
    registration = capture.capture_status(producer.handle, identifier)
    path = Path(registration['slot']['path']) / 'registration.json'
    saved = path.read_bytes()
    before = (producer.store.path / 'current.json').read_bytes()
    forged = copy.deepcopy(registration)
    if change == 'attempt':
        forged['request']['producer']['attempt'] = 'e' * 32
    elif change == 'closure':
        forged['request']['record']['closure_sha256'] = 'e' * 64
    else:
        forged['request']['request_sha256'] = 'e' * 64
    try:
        path.write_bytes(logical.encoded(forged))
        with pytest.raises(ValueError):
            acknowledge(producer, identifier)
        assert (producer.store.path / 'current.json').read_bytes() == before
        assert producer.result.read_bytes() == PAYLOAD
    finally:
        path.write_bytes(saved)


@pytest.mark.parametrize('boundary', ['preflight', 'actual'])
def test_publication_capacity_refusal_preserves_prior_proof_and_registered_retry(
        producer, monkeypatch, boundary):
    import capture_publication as publication

    identifier = producer.finalize()
    before = (producer.store.path / 'current.json').read_bytes()

    with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                          [], [], [], captures=[identifier]) as selected:
        with monkeypatch.context() as local:
            if boundary == 'preflight':
                local.setattr(retention, 'MAX_RETAINED_BYTES', 1)
            else:
                # Change the limit only after real bytes exist, past projection.
                def actual(stage):
                    if stage == 'publication.copied':
                        local.setattr(retention, 'MAX_RETAINED_BYTES', 1)
                local.setattr(publication, 'checkpoint', actual)
            with pytest.raises(ValueError, match='budget|capacity|limit'):
                bundle.export(selected, expected=selected.selection_sha256)
    assert (producer.store.path / 'current.json').read_bytes() == before
    assert producer.result.read_bytes() == PAYLOAD
    assert producer.previous_proof.read_bytes() == b'prior finished evidence\n'
    publish_capture(producer, identifier)
    acknowledge(producer, identifier)


def test_cumulative_capacity_refusal_keeps_previous_destination_and_new_required_source(
        producer, monkeypatch):
    first = producer.finalize()
    previous = publish_capture(producer, first)
    archive = Path(previous['path'])
    before_archive = (archive.read_bytes(), archive.stat().st_ino)
    handle = capture.issue_session(
        producer.store, repository=producer.checkout, workflow='capture-fixture', task='P12',
        check='next-cumulative-proof', target='', inputs_sha256='c' * 64,
        sources_sha256='d' * 64,
        consumers={CONSUMER: dict(consumer_id=CONSUMER, revision_sha256=REVISION)})
    record = producer.record(context=capture.session_context(handle))
    second = capture.finalize_capture(handle, record=record, consumer_ids=[CONSUMER])
    source_state = (producer.store.path / 'current.json').read_bytes()
    with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                          [], [], [], captures=[second]) as selected:
        parent = selected.publication_parent()
        journal = parent / 'retention/current.json'
        before_journal = journal.read_bytes()
        assert len(selected.manifest['records']) == 2
        with monkeypatch.context() as local:
            local.setattr(retention, 'MAX_RETAINED_BYTES', 1)
            with pytest.raises(ValueError, match='budget|capacity|limit'):
                bundle.export(selected, expected=selected.selection_sha256)
    assert (archive.read_bytes(), archive.stat().st_ino) == before_archive
    assert journal.read_bytes() == before_journal
    assert (producer.store.path / 'current.json').read_bytes() == source_state
    assert producer.result.read_bytes() == PAYLOAD
    replacement = publish_capture(producer, second)
    verified = bundle.inspect(producer.checkout, os.geteuid(), os.getegid(), replacement['path'])
    assert {item['record_id'] for item in verified['manifest']['records']} == {
        producer.record()['record_id'], record['record_id']}


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


def test_verified_ack_releases_exact_source_after_retained_session_rotation(
        tmp_path, monkeypatch):
    with producer_session(tmp_path, monkeypatch) as value:
        identifier = value.finalize()
        receipt = publish_capture(value, identifier)
        acknowledgement = acknowledge(value, identifier)
        slot = Path(acknowledgement['caller_slot']['path'])
    for _ in range(4):
        with value.store.session():
            pass
    assert not value.source.exists()
    assert not slot.exists()
    state = json.loads((value.store.path / 'current.json').read_bytes())
    assert not any(entry.get('captures') for entry in [*state['history'], state])
    verified = bundle.inspect(value.checkout, os.geteuid(), os.getegid(), receipt['path'])
    assert verified['manifest']['records'] == [acknowledgement['request']['record']]


@pytest.mark.parametrize('change', ['changed', 'missing'])
def test_acknowledged_destination_is_reverified_before_count_retirement(
        tmp_path, monkeypatch, change):
    with producer_session(tmp_path, monkeypatch) as value:
        identifier = value.finalize()
        receipt = publish_capture(value, identifier)
        acknowledgement = acknowledge(value, identifier)
    for _ in range(2):
        with value.store.session():
            pass
    before = (value.store.path / 'current.json').read_bytes()
    archive = Path(receipt['path'])
    saved = archive.with_name('evidence.owned-saved')
    archive.rename(saved)
    try:
        if change == 'changed':
            archive.write_bytes(b'changed acknowledged destination\n')
            archive.chmod(0o600)
        with pytest.raises(ValueError, match='capture|acknowledgement'):
            with value.store.session():
                pytest.fail('invalid replacement released a required source')
        assert (value.store.path / 'current.json').read_bytes() == before
        assert value.result.read_bytes() == PAYLOAD
        assert Path(acknowledgement['caller_slot']['path']).is_dir()
    finally:
        if archive.exists():
            archive.unlink()
        saved.rename(archive)
    # Restoring the same bytes after a rename does not restore the receipt's
    # exact file fingerprint. Prior acknowledgement remains insufficient.
    with pytest.raises(ValueError, match='capture|acknowledgement'):
        with value.store.session():
            pytest.fail('restored bytes bypassed exact destination identity')
    assert (value.store.path / 'current.json').read_bytes() == before
    assert value.result.read_bytes() == PAYLOAD


@pytest.mark.parametrize('removed', [False, True])
def test_interrupted_slot_cleanup_resumes_only_recorded_identity(
        tmp_path, monkeypatch, removed):
    with producer_session(tmp_path, monkeypatch) as value:
        identifier = value.finalize()
        publish_capture(value, identifier)
        acknowledgement = acknowledge(value, identifier)
    for _ in range(2):
        with value.store.session():
            pass
    slot = Path(acknowledgement['caller_slot']['path'])
    real_remove = retention.remove
    failed = False

    def interrupted(record, *args, **kwargs):
        nonlocal failed
        if record['path'] == str(slot) and not kwargs.get('validate_only') and not failed:
            failed = True
            if removed:
                real_remove(record, *args, **kwargs)
            raise SimulatedInterrupt('original retired; slot cleanup reply lost')
        return real_remove(record, *args, **kwargs)

    with monkeypatch.context() as local:
        local.setattr(retention, 'remove', interrupted)
        with pytest.raises(SimulatedInterrupt):
            with value.store.session():
                pytest.fail('slot cleanup failure admitted another owner')
    assert failed and not value.source.exists()
    before = (value.store.path / 'current.json').read_bytes()
    saved = slot.with_name(slot.name + '-owned-saved')
    if not removed:
        slot.rename(saved)
    slot.mkdir(mode=0o700)
    try:
        with pytest.raises(ValueError, match='replaced|identity'):
            with value.store.session():
                pytest.fail('cleanup adopted a replacement slot')
        assert slot.is_dir()
        assert (value.store.path / 'current.json').read_bytes() == before
    finally:
        slot.rmdir()
        if not removed:
            saved.rename(slot)
    with value.store.session():
        pass
    assert not slot.exists()
    after = json.loads((value.store.path / 'current.json').read_bytes())
    assert not any(entry.get('captures') for entry in [*after['history'], after])


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


def test_same_source_capture_survives_more_than_three_reopened_owners(
        tmp_path, monkeypatch):
    import capture_publication as publication

    with producer_session(tmp_path, monkeypatch) as value:
        identifier = value.finalize()
        request = value.inspect(identifier)
        context = copy.deepcopy(value.context)
        source_state = json.loads((value.store.path / 'current.json').read_bytes())
        charge = source_state['captures'][0]
        sealed = Path(request['sealed']['mappings'][0]['sealed_path'])
        originals = {path: (path.stat().st_dev, path.stat().st_ino, path.read_bytes())
                     for path in (value.result, sealed)}
        slot = Path(charge['path'])
        slot_identity = (slot.stat().st_dev, slot.stat().st_ino)

    stage = None
    stage_identity = None
    handles = [value.handle]
    for boundary in ('publication.registered', 'publication.copied',
                     'publication.committed', 'publication.locator'):
        with value.store.session(run=context['run']):
            resumed = capture.resume_session(value.store, identifier)
            assert all(resumed is not previous for previous in handles)
            handles.append(resumed)
            assert capture.session_context(resumed) == context
            assert capture.finalize_capture(resumed, record=request['record'],
                                            consumer_ids=[CONSUMER]) == identifier
            assert value.inspect(identifier) == request

            def interrupt(point):
                if point == boundary:
                    raise SimulatedInterrupt('reopen the same capture owner')

            with bundle.Selection(value.checkout, os.geteuid(), os.getegid(),
                                  [], [], [], captures=[identifier]) as selected:
                parent = selected.publication_parent(create=True)
                with monkeypatch.context() as local:
                    local.setattr(publication, 'checkpoint', interrupt)
                    with pytest.raises(SimulatedInterrupt):
                        bundle.export(selected, expected=selected.selection_sha256)
            stages = [path for path in parent.iterdir()
                      if path.name.startswith('onpc-evidence-bundle-')]
            assert len(stages) == 1
            if stage is None:
                stage = stages[0]
                stage_identity = (stage.stat().st_dev, stage.stat().st_ino)
            assert stages == [stage]
            assert (stage.stat().st_dev, stage.stat().st_ino) == stage_identity
        assert json.loads((value.store.path / 'current.json').read_bytes())['captures'] == [charge]
        assert (slot.stat().st_dev, slot.stat().st_ino) == slot_identity
        for path, original in originals.items():
            assert (path.stat().st_dev, path.stat().st_ino, path.read_bytes()) == original
        assert value.inspect(identifier) == request
        with pytest.raises(ValueError):
            capture.session_context(resumed)

    with value.store.session(run=context['run']):
        resumed = capture.resume_session(value.store, identifier)
        assert capture.session_context(resumed) == context
        receipt = publish_capture(value, identifier)
        assert Path(receipt['path']).parent == stage
        acknowledgement = capture.acknowledge_capture(
            value.checkout, os.geteuid(), os.getegid(), identifier,
            expected=request['request_sha256'], session_handle=resumed)
        assert acknowledgement['request'] == request
        verified = bundle.inspect(value.checkout, os.geteuid(), os.getegid(), receipt['path'])
        assert verified['manifest']['records'] == [request['record']]
        state = json.loads((value.store.path / 'current.json').read_bytes())
        assert state['paths'] == source_state['paths']
        assert state['history'] == source_state['history']
        assert len([*state['history'], state]) <= retention.RUNS_TO_KEEP
        assert len(state['captures']) == 1
        assert {key: item for key, item in state['captures'][0].items()
                if key != 'acknowledgement'} == charge


@pytest.mark.parametrize('failure', ['publication', 'acknowledgement-capacity'])
def test_failed_real_capture_blocks_oversized_startup_until_matching_acknowledgement(
        tmp_path, monkeypatch, failure):
    import capture_publication as publication

    allocation_bytes = retention.allocation_bytes

    def oversized_source(record, **kwargs):
        # Inject source usage only: shrinking the global limit also invalidates
        # the destination manifest's historical source-budget provenance.
        if Path(record['path']) == value.source:
            return retention.MAX_RETAINED_BYTES + 1
        return allocation_bytes(record, **kwargs)

    with producer_session(tmp_path, monkeypatch) as value:
        identifier = value.finalize()
        request = value.inspect(identifier)
        if failure == 'publication':
            def interrupt(point):
                if point == 'publication.copied':
                    raise SimulatedInterrupt('publication reply was interrupted')

            with monkeypatch.context() as local:
                local.setattr(publication, 'checkpoint', interrupt)
                with pytest.raises(SimulatedInterrupt):
                    publish_capture(value, identifier)
        else:
            publish_capture(value, identifier)
            with monkeypatch.context() as local:
                local.setattr(retention, 'allocation_bytes', oversized_source)
                with pytest.raises(ValueError, match='capacity|budget'):
                    acknowledge(value, identifier)

    before = (value.store.path / 'current.json').read_bytes()
    state = json.loads(before)
    charge = state['captures'][0]
    assert not charge.get('acknowledgement')
    sealed = Path(request['sealed']['mappings'][0]['sealed_path'])
    originals = {path: (path.stat().st_dev, path.stat().st_ino, path.read_bytes())
                 for path in (value.result, value.previous_proof, sealed)}
    audited = []
    with monkeypatch.context() as local:
        local.setattr(retention, 'allocation_bytes', oversized_source)
        with pytest.raises(ValueError, match='capture|acknowledgement'):
            value.store.reconcile(lambda: None, completed_guard=audited.append)
    assert not audited
    assert (value.store.path / 'current.json').read_bytes() == before
    for path, original in originals.items():
        assert (path.stat().st_dev, path.stat().st_ino, path.read_bytes()) == original
    assert value.inspect(identifier) == request

    receipt = publish_capture(value, identifier)
    acknowledgement = capture.acknowledge_capture(
        value.checkout, os.geteuid(), os.getegid(), identifier,
        expected=request['request_sha256'])
    assert acknowledgement['request'] == request
    acknowledged = json.loads((value.store.path / 'current.json').read_bytes())['captures'][0]
    assert {key: item for key, item in acknowledged.items()
            if key != 'acknowledgement'} == charge
    with monkeypatch.context() as local:
        local.setattr(retention, 'allocation_bytes', oversized_source)
        value.store.reconcile(lambda: None, completed_guard=audited.append)
    assert audited == [{str(value.source)}]
    assert not value.source.exists()
    assert not Path(charge['path']).exists()
    retired = json.loads((value.store.path / 'current.json').read_bytes())
    assert not retired['paths']
    assert not any(entry.get('captures') for entry in [*retired['history'], retired])
    verified = bundle.inspect(value.checkout, os.geteuid(), os.getegid(), receipt['path'])
    assert verified['manifest']['records'] == [request['record']]


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
    from contextlib import nullcontext
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
    record = producer.record(context=capture.session_context(handle))
    identifier = capture.finalize_capture(handle, record=record, consumer_ids=[CONSUMER])
    opened = retention.Store.opened

    def no_active_parent(store):
        assert store.path != producer.store.path, 'selection inspected active parent'
        return opened(store)

    with monkeypatch.context() as local:
        # Exercise the unprivileged Selection gate even on a root test host,
        # without changing credentials or replacing real capture/lock mechanics.
        local.setattr(bundle, 'os', SimpleNamespace(**(vars(os) | {
            'geteuid': lambda: os.geteuid() or 12345})))
        local.setattr(bundle, 'identity', lambda *_: nullcontext())
        local.setattr(retention.Store, 'opened', no_active_parent)
        with bundle.Selection(producer.checkout, os.geteuid(), os.getegid(),
                ['Fixture-Guest'], [], [], captures=[identifier]) as selected:
            assert selected.manifest['records'] == [record]
            assert selected.plan()['files'] == 1

