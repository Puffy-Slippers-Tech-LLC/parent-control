"""Bounded workflow-local publication of authenticated finished captures.

The retention publication intent owns the single staging allocation. This small
workflow journal supplies exact request bindings and the cumulative locator; it
is neither a catalogue nor authority derived from caller JSON.
"""
from contextlib import contextmanager, ExitStack
import copy
import os
from pathlib import Path
import signal
import tempfile

import evidence_bundle as bundle
import evidence_capture as capture
import evidence_identity as logical
import test_retention as retention

JOURNAL = 'capture-publication.json'


def checkpoint(stage):
    """Finite interruption points used by private-store recovery regressions."""


def _namespace(request):
    context = request['record']['context']
    return bundle.digest(bundle.encoded(dict(kind='capture-working',
        repository=context['repository'], workflow=context['workflow'])))


def _read(fd):
    try:
        return capture._read(fd, JOURNAL)
    except FileNotFoundError:
        return None


def _validate(state, request):
    logical._object(state, {'schema', 'namespace', 'repository', 'workflow', 'published', 'pending'},
                    'capture publication journal')
    context = request['record']['context']
    if (type(state['schema']) is not int or state['schema'] != 1
            or state['namespace'] != _namespace(request)
            or state['repository'] != context['repository']
            or state['workflow'] != context['workflow']):
        raise ValueError('capture publication: foreign workflow journal')
    for generation in (state['published'], state['pending']):
        if generation is None:
            continue
        logical._object(generation, {'requests', 'selection_sha256', 'allocation', 'receipt', 'files'},
                        'capture publication generation')
        logical._hex(generation['selection_sha256'])
        requests = generation['requests']
        if not isinstance(requests, list) or not 0 < len(requests) <= 256:
            raise ValueError('capture publication: invalid request closure')
        ids = []
        for item in requests:
            capture._validate_request(item)
            if _namespace(item) != state['namespace']:
                raise ValueError('capture publication: mixed workflows')
            ids.append(item['capture_id'])
        if ids != sorted(set(ids)):
            raise ValueError('capture publication: ambiguous request closure')
        if generation['allocation'] is not None:
            retention.publication_record(generation['allocation'])
        if generation['files'] is not None:
            if (not isinstance(generation['files'], dict)
                    or not set(generation['files']) <= {'evidence.zip', 'receipt.json'}):
                raise ValueError('capture publication: invalid publication files')
            for identity in generation['files'].values():
                if (not isinstance(identity, list) or len(identity) != 6
                        or any(type(item) is not int or item < 0 for item in identity)):
                    raise ValueError('capture publication: invalid stage file identity')
        receipt = generation['receipt']
        if receipt is not None:
            logical._object(receipt, {'schema', 'sha256', 'bytes', 'identity', 'selection_sha256',
                                     'path', 'files'}, 'capture publication receipt')
            if (type(receipt['schema']) is not int or receipt['schema'] != 2
                    or type(receipt['files']) is not int or not 0 < receipt['files'] <= bundle.MAX_FILES
                    or receipt['selection_sha256'] != generation['selection_sha256']):
                raise ValueError('capture publication: receipt selection mismatch')
            allocation = generation['allocation']
            if allocation is None or receipt['path'] != str(Path(allocation['path']) / 'evidence.zip'):
                raise ValueError('capture publication: receipt allocation mismatch')
    if state['published'] is not None and state['published']['receipt'] is None:
        raise ValueError('capture publication: incomplete published locator')
    if state['published'] is not None and set(state['published']['files'] or {}) != {'evidence.zip', 'receipt.json'}:
        raise ValueError('capture publication: incomplete published file identities')
    if len(bundle.encoded(state)) > logical.MAX_METADATA:
        raise ValueError('capture publication: metadata limit exceeded')


def _save(store, fd, state, request, *, reserved=0):
    _validate(state, request)
    # Metadata and recovery scratch are physical copies within the same budget.
    records = []
    current = store.read(fd)
    if current is not None:
        records.extend(record for _, record in retention.latest_allocations([*current['history'], current]))
    intent = retention.read_publication(store, fd)
    if intent is not None and intent['staging'] not in records:
        records.append(intent['staging'])
    controls = sum(os.stat(name, dir_fd=fd, follow_symlinks=False).st_blocks * 512
                   for name in os.listdir(fd) if name not in ('owner.lock', 'writer.lock'))
    metadata = ((len(bundle.encoded(state)) + 4095) // 4096) * 4096
    if retention.publication_usage(records) + controls + 2 * metadata + reserved > retention.MAX_RETAINED_BYTES:
        raise ValueError('capture publication: workflow metadata exceeds storage budget; evidence preserved')
    capture._write(fd, JOURNAL, state)


@contextmanager
def _selection_owner(store):
    """Inspect prior proof even while this workflow has a resumable stage."""
    with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False, shared=True):
        with store.locked(fd, 'writer.lock', publication=True, shared=True):
            owner_identity = capture._directory_identity(os.fstat(fd))
            current = store.read(fd)
            retention.finished_owner(fd, current)
            intent = retention.read_publication(store, fd)
            if intent is not None:
                replacement, _ = retention.publication_states(intent)
                if current != intent['original'] and not (intent['phase'] == 'committed' and current == replacement):
                    raise ValueError('capture publication: destination owner changed')
            yield fd, current, intent
            with retention.directory_descriptor(store.path) as owner:
                if capture._directory_identity(os.fstat(owner)) != owner_identity:
                    raise ValueError('capture publication: workflow owner replaced during read')


def prepare_selection(selection):
    """Carry the prior cumulative archive before the selection is planned."""
    request = selection.capture_requests[0]
    namespace = _namespace(request)
    if any(_namespace(item) != namespace for item in selection.capture_requests):
        raise ValueError('capture publication: select one authenticated workflow')
    if selection.plan_namespace is not None:
        from execution_plan import plan_namespace
        if selection.plan_namespace != plan_namespace(request['record']['context']['workflow']):
            raise ValueError('capture publication: explicit plan does not match authenticated workflow')
    selection.capture_namespace = namespace
    with bundle.identity(selection.uid, selection.gid):
        try:
            parent = selection.publication_parent()
        except FileNotFoundError:
            selection.capture_previous = None
            return
        if not (parent / 'retention').exists():
            selection.capture_previous = None
            return
        store = retention.Store(parent / 'retention')
        fd, current, intent = selection.export_stack.enter_context(_selection_owner(store))
        state = _read(fd)
        if state is None:
            if current is None and intent is None and set(os.listdir(fd)) <= {'owner.lock', 'writer.lock'}:
                selection.capture_previous = None
                return
            raise ValueError('capture publication: missing workflow journal')
        _validate(state, request)
        selection.capture_previous = copy.deepcopy(state)
        published = state['published']
        if published is None:
            return
        record = published['allocation']
        verified = bundle.inspect_record(record, selection.uid, checkout=selection.checkout)
        _verify_generation(published, verified)
        allocation = dict(record, journal=str(store.path))
        # The archive's journal/run provenance is authenticated by retention.
        entries = [] if current is None else [*current['history'], current]
        if intent is not None:
            entries += ([] if intent['original'] is None else [*intent['original']['history'], intent['original']])
        runs = [entry['run'] for entry in entries if record in entry['paths']]
        if not runs:
            raise ValueError('capture publication: locator allocation is not retained')
        allocation['run'] = runs[0]
        path = published['receipt']['path']
        if path in selection.bundles:
            raise ValueError('capture publication: cumulative bundle was selected twice')
        selection.records[record['path']] = allocation
        selection.bundles = [*selection.bundles, path]
        selection.source_budgets.append(dict(journal=str(store.path),
            allocated_bytes=retention.publication_usage([record])))
        known = {item['capture_id']: item for item in published['requests']}
        if (not selection.sources and not selection.references and len(selection.bundles) == 1
                and all(known.get(item['capture_id']) == item for item in selection.capture_requests)):
            selection.capture_reuse = verified


def _verify_generation(generation, verified):
    receipt = generation['receipt']
    if receipt is None or {key: verified[key] for key in receipt if key != 'path'} != {
            key: value for key, value in receipt.items() if key != 'path'}:
        raise ValueError('capture publication: destination receipt changed')
    manifest = verified['manifest']
    if manifest.get('schema') != 2:
        raise ValueError('capture publication: destination has no complete logical closure')
    records = {item['record_id']: item for item in manifest['records']}
    physical = {item['member']: item for item in manifest['files']}
    mappings = {(item['record_id'], item['member_id']): item for item in manifest['member_map']}
    for request in generation['requests']:
        record = request['record']
        if records.get(record['record_id']) != record:
            raise ValueError('capture publication: request record or attempt changed')
        for member in record['members']:
            mapping = mappings.get((record['record_id'], member['member_id']))
            if mapping is None:
                raise ValueError('capture publication: incomplete destination closure')
            origin = mapping['original_provenance']
            item = physical[mapping['physical_member']]
            if (origin['original_path'] != member['original_path']
                    or origin['source_allocation'] != member['source_allocation']
                    or item['sha256'] != member['sha256'] or item['bytes'] != member['bytes']):
                raise ValueError('capture publication: original member provenance changed')


def _delivery(request, journal):
    return dict(schema=1, capture_id=request['capture_id'],
                request_sha256=request['request_sha256'], journal=str(journal))


def _deliver(selection, store):
    deliveries = []
    for request in selection.capture_requests:
        delivery = _delivery(request, store.path)
        with bundle.identity(selection.uid, selection.gid):
            repository = capture._repository(selection.checkout, dict(uid=selection.uid, gid=selection.gid))
            with retention.directory_descriptor(capture._slot_path(repository, request['capture_id'])) as fd:
                retention.private(os.fstat(fd))
                capture._write(fd, 'publication.json', delivery)
        deliveries.append(delivery)
    checkpoint('publication.delivered')
    return deliveries


def _write_archive(selection, directory, store, state, request, owner_fd):
    pending = state['pending']
    with retention.directory_descriptor(directory) as fd:
        retention.check_tree(fd, os.fstat(fd).st_dev, regular_only=True)
        known = pending['files'] or {}
        if set(os.listdir(fd)) != set(known):
            raise ValueError('capture publication: unregistered staging files')
        for name, identity in known.items():
            if bundle.fingerprint(os.stat(name, dir_fd=fd, follow_symlinks=False))[:6] != identity:
                raise ValueError('capture publication: registered stage file replaced')
        for name in ('evidence.zip', 'receipt.json'):
            if name in known:
                continue
            before = copy.deepcopy(state)
            previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
            descriptor, created = None, None
            try:
                descriptor = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
                info = os.fstat(descriptor)
                created = info.st_dev, info.st_ino
                os.fsync(descriptor)
                os.fsync(fd)
                pending['files'] = dict(known, **{name: bundle.fingerprint(info)[:6]})
                _save(store, owner_fd, state, request)
                known = pending['files']
            except BaseException:
                # A failed atomic control write may already be committed. Only
                # a verified unchanged old journal permits exact empty rollback.
                try:
                    durable = _read(owner_fd)
                    if durable is not None:
                        _validate(durable, request)
                except BaseException:
                    durable = None
                if created is not None and durable == before:
                    capture._rollback_empty_file(fd, name, descriptor, created)
                    pending['files'] = before['pending']['files']
                raise
            finally:
                if descriptor is not None:
                    os.close(descriptor)
                signal.pthread_sigmask(signal.SIG_SETMASK, previous)
        if set(os.listdir(fd)) != set(pending['files']):
            raise ValueError('capture publication: stage file closure changed')
        for name, identity in pending['files'].items():
            if bundle.fingerprint(os.stat(name, dir_fd=fd, follow_symlinks=False))[:6] != identity:
                raise ValueError('capture publication: registered stage file replaced')
        descriptor = os.open('evidence.zip', os.O_RDWR | os.O_NOFOLLOW, dir_fd=fd)
        with os.fdopen(descriptor, 'w+b') as destination:
            if bundle.fingerprint(os.fstat(destination.fileno()))[:6] != pending['files']['evidence.zip']:
                raise ValueError('capture publication: registered archive replaced')
            os.ftruncate(destination.fileno(), 0)
            with bundle.identity(selection.reader_uid, selection.reader_gid):
                selection.write(destination)
            size = os.fstat(destination.fileno()).st_size
            receipt = dict(schema=2, sha256=bundle.file_digest(destination.fileno(), size),
                bytes=size, identity=bundle.fingerprint(os.fstat(destination.fileno())),
                selection_sha256=selection.selection_sha256)
        descriptor = os.open('receipt.json', os.O_WRONLY | os.O_NOFOLLOW, dir_fd=fd)
        with os.fdopen(descriptor, 'wb') as output:
            if bundle.fingerprint(os.fstat(output.fileno()))[:6] != pending['files']['receipt.json']:
                raise ValueError('capture publication: registered receipt replaced')
            os.ftruncate(output.fileno(), 0)
            output.write(bundle.encoded(receipt))
            output.flush()
            os.fsync(output.fileno())
        os.fsync(fd)
    return dict(receipt, path=str(directory / 'evidence.zip'), files=len(selection.manifest['files']))


@contextmanager
def _independent_owner():
    # A live producer can publish its independently finished subset in-process.
    # Its inherited allocation token must never select the destination owner.
    previous = os.environ.pop(retention.VARIABLE, None)
    try:
        yield
    finally:
        if previous is not None:
            os.environ[retention.VARIABLE] = previous


def publish(selection, *, expected, defer_cleanup=False):
    if type(defer_cleanup) is not bool or expected != selection.selection_sha256:
        raise ValueError('capture publication: selection changed; inspect a fresh plan')
    request = selection.capture_requests[0]
    selection.export_stack.close()
    with bundle.identity(selection.uid, selection.gid):
        parent = selection.publication_parent(create=True)
        store = retention.Store(parent / 'retention')
        verify = lambda record: bundle.inspect_record(record, selection.uid, checkout=selection.checkout)
        projected = 0 if getattr(selection, 'capture_reuse', None) is not None else selection.projected_bytes
        with _independent_owner(), store.publication(projected_bytes=projected, verify=verify, resumable=True) as transaction:
            state = _read(transaction.fd)
            if state is None:
                state = dict(schema=1, namespace=selection.capture_namespace,
                    repository=request['record']['context']['repository'],
                    workflow=request['record']['context']['workflow'], published=None, pending=None)
            _validate(state, request)
            published = state['published']
            matching = (published is not None and published['selection_sha256'] == expected
                        and all(item in published['requests'] for item in selection.capture_requests))
            if getattr(selection, 'capture_reuse', None) is not None or matching:
                if transaction.intent is not None and (
                        transaction.intent['phase'] != 'committed'
                        or transaction.intent['staging'] != published['allocation']):
                    raise ValueError('capture publication: finish the recorded pending selection before reuse')
                _verify_generation(published, verify(published['allocation']))
                deliveries = _deliver(selection, store)
                if not defer_cleanup and transaction.intent is not None:
                    retention.recover_publication(store, transaction.fd, verify=verify,
                                                 authorize=transaction.authorize)
                return dict(published['receipt'], cleanup_complete=not defer_cleanup,
                            deliveries=deliveries)
            if state != getattr(selection, 'capture_previous', None) and getattr(selection, 'capture_previous', None) is not None:
                raise ValueError('capture publication: workflow changed after selection')
            if published is not None and getattr(selection, 'capture_previous', None) is None:
                raise ValueError('capture publication: workflow changed after selection')
            requests = {item['capture_id']: item for item in (published['requests'] if published else [])}
            for item in selection.capture_requests:
                if item['capture_id'] in requests and requests[item['capture_id']] != item:
                    raise ValueError('capture publication: changed registered request')
                requests[item['capture_id']] = item
            wanted = dict(requests=[requests[key] for key in sorted(requests)],
                          selection_sha256=selection.selection_sha256, allocation=None, receipt=None, files=None)
            pending = state['pending']
            if pending is None:
                if transaction.intent is not None:
                    raise ValueError('capture publication: unbound retention transaction')
                state['pending'] = wanted
                _save(store, transaction.fd, state, request, reserved=selection.projected_bytes)
            elif pending['requests'] != wanted['requests'] or pending['selection_sha256'] != expected:
                raise ValueError('capture publication: retry the exact pending selection')
            pending = state['pending']
            if transaction.intent is None:
                # A prior attempt may have saved its workflow request before
                # allocation failed. Reforecast the same completion before any
                # resumed allocation, even though the request already exists.
                _save(store, transaction.fd, state, request,
                      reserved=selection.projected_bytes)
            directory = (Path(transaction.intent['staging']['path']) if transaction.committing else
                         transaction.allocate(tempfile.mkdtemp, prefix='onpc-evidence-bundle-', dir=parent))
            if pending['allocation'] is not None and pending['allocation'] != transaction.intent['staging']:
                raise ValueError('capture publication: registered stage changed')
            pending['allocation'] = transaction.intent['staging']
            remaining = (max(0, selection.projected_bytes
                             - retention.publication_usage([pending['allocation']]))
                         if transaction.intent['phase'] == 'staging' else 0)
            _save(store, transaction.fd, state, request, reserved=remaining)
            checkpoint('publication.registered')
            if transaction.intent['phase'] == 'staging':
                pending['receipt'] = _write_archive(selection, directory, store, state, request, transaction.fd)
                _save(store, transaction.fd, state, request)
                checkpoint('publication.copied')
                _verify_generation(pending, verify(pending['allocation']))
                _save(store, transaction.fd, state, request)
                transaction.commit(defer_cleanup=True)
            elif pending['receipt'] is None:
                raise ValueError('capture publication: missing committed receipt')
            _verify_generation(pending, verify(pending['allocation']))
            checkpoint('publication.committed')
            state['published'], state['pending'] = pending, None
            _save(store, transaction.fd, state, request)
            checkpoint('publication.locator')
            deliveries = _deliver(selection, store)
            if not defer_cleanup:
                retention.recover_publication(store, transaction.fd, verify=verify,
                                             authorize=transaction.authorize)
            return dict(pending['receipt'], cleanup_complete=not defer_cleanup, deliveries=deliveries)


def read_delivery(checkout, uid, gid, capture_id):
    logical._hex(capture_id)
    with bundle.identity(uid, gid):
        repository = capture._repository(checkout, dict(uid=uid, gid=gid))
        with retention.directory_descriptor(capture._slot_path(repository, capture_id)) as fd:
            retention.private(os.fstat(fd))
            return capture._read(fd, 'publication.json')


@contextmanager
def verified_delivery(checkout, uid, gid, capture_id, request, delivery):
    """Pin current cumulative proof independently through acknowledgement/deletion."""
    capture._validate_request(request)
    logical._object(delivery, {'schema', 'capture_id', 'request_sha256', 'journal'}, 'capture delivery')
    stack = ExitStack()
    try:
        with bundle.identity(uid, gid):
            repository = capture._repository(checkout, dict(uid=uid, gid=gid))
            parent = bundle.plan_parent(checkout, _namespace(request))
            store = retention.Store(parent / 'retention')
            if (type(delivery['schema']) is not int or delivery != _delivery(request, store.path)
                    or capture_id != request['capture_id'] or request['producer']['repository'] != repository
                    or request['producer']['caller'] != dict(uid=uid, gid=gid)):
                raise ValueError('capture publication: foreign delivery')
            fd, current, intent = stack.enter_context(_selection_owner(store))
            pins = []
            state = capture._pin_record(fd, JOURNAL, stack, pins)
            _validate(state, request)
            generation = state['published']
            if generation is None or request not in generation['requests']:
                raise ValueError('capture publication: request is not published')
            allocation = generation['allocation']
            entries = [] if current is None else [*current['history'], current]
            if not any(allocation == item for _, item in retention.latest_allocations(entries)):
                raise ValueError('capture publication: destination allocation is not retained')
            verified, read = stack.enter_context(bundle.verified_record(allocation, uid, checkout=checkout))
            _verify_generation(generation, verified)
            result = dict(receipt=copy.deepcopy(generation['receipt']), manifest=verified['manifest'],
                          allocation=copy.deepcopy(allocation), delivery=copy.deepcopy(delivery))
        # Preserve the authenticated helper's entry identity while source-owner
        # acknowledgement/deletion runs; only destination reads drop identity.
        yield result
        with bundle.identity(uid, gid):
            if _read(fd) != state:
                raise ValueError('capture publication: workflow journal changed during verification')
            for parent_fd, name, descriptor, identity, data, _, _ in pins:
                if (bundle.fingerprint(os.fstat(descriptor)) != identity
                        or bundle.fingerprint(os.stat(name, dir_fd=parent_fd, follow_symlinks=False)) != identity
                        or os.pread(descriptor, logical.MAX_METADATA + 1, 0) != data):
                    raise ValueError('capture publication: workflow control identity changed during verification')
    finally:
        with bundle.identity(uid, gid):
            stack.close()
