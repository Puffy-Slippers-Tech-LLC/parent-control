"""Producer-owned finite seals and verified source-owner acknowledgements.

Only a capability minted from a live in-process retention owner can finalize a
record. Readers resolve an exact registered ID and hold the independent finished
snapshot owner. They never inspect the active producer journal.
"""
from contextlib import contextmanager, ExitStack
import copy
import hashlib
import os
from pathlib import Path
import pwd
import stat
import uuid
import weakref
import signal
import sys

if __package__:
    from . import evidence_identity as logical, test_retention as retention, test_storage as storage
else:
    import evidence_identity as logical
    import test_retention as retention
    import test_storage as storage

_handles = weakref.WeakKeyDictionary()
_MINT = object()
MAX_SELECTIONS = 256


class _SessionHandle:
    __slots__ = ('__weakref__',)

    def __new__(cls, authority=None):
        if authority is not _MINT:
            raise ValueError('capture: session handles are producer-issued')
        return object.__new__(cls)


def checkpoint(stage):
    """Durable boundary for cancellation/fault-injection by private tests."""


@contextmanager
def _registration_window():
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
    try:
        yield
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def _authenticated_caller():
    if os.geteuid() != 0:
        return dict(uid=os.geteuid(), gid=os.getegid())
    value = os.environ.get('PKEXEC_UID', '')
    if not value.isascii() or not value.isdecimal() or int(value) <= 0:
        raise ValueError('capture: privileged producer needs an authenticated caller')
    account = pwd.getpwuid(int(value))
    return dict(uid=account.pw_uid, gid=account.pw_gid)


def validate_targets(checkout, targets):
    """Registry metadata only; this does not inspect or operate any VM."""
    if not targets:
        return
    if len(targets) > MAX_SELECTIONS or len(set(targets)) != len(targets):
        raise ValueError('capture: expected unique registered canonical targets')
    sys.path.insert(0, str(Path(checkout) / 'tests/integration'))
    try:
        import vm_config
    finally:
        sys.path.pop(0)
    configured = vm_config.registry()
    if any(target not in configured for target in targets):
        raise ValueError('capture: expected registered canonical targets')


@contextmanager
def _identity(uid, gid):
    old_uid, old_gid = os.geteuid(), os.getegid()
    def switch(next_uid, next_gid):
        if (os.geteuid(), os.getegid()) == (next_uid, next_gid):
            return
        if os.geteuid() != 0:
            os.seteuid(0)
        os.setegid(next_gid)
        os.seteuid(next_uid)
    try:
        switch(uid, gid)
        yield
    finally:
        switch(old_uid, old_gid)


def _directory_identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, mode=info.st_mode,
                uid=info.st_uid, gid=info.st_gid)


def _repository(path, caller):
    path = Path(path)
    logical._path(str(path))
    with retention.directory_descriptor(path) as fd:
        info = os.fstat(fd)
        if info.st_uid != caller['uid']:
            raise ValueError('capture: unsafe checkout identity')
        # Use the bundle reader's existing private-user-group policy. Ordinary
        # Ubuntu checkouts can be 0775 without admitting another account.
        if __package__:
            from .evidence_bundle import safe
        else:
            from evidence_bundle import safe
        safe(info, caller['uid'], directory=True)
        return dict(root=str(path), device=info.st_dev, inode=info.st_ino, uid=caller['uid'])


def _owner(path, fd, repository, caller):
    return dict(repository_sha256=logical.digest(repository), caller=copy.deepcopy(caller),
                journal=str(path), identity=_directory_identity(os.fstat(fd)))


def _consumers(values):
    if type(values) is not dict or not 0 < len(values) <= MAX_SELECTIONS:
        raise ValueError('capture: expected finite owner-issued consumers')
    for key, value in values.items():
        logical._hex(key)
        logical._object(value, {'consumer_id', 'revision_sha256'}, 'consumer revision')
        if value['consumer_id'] != key:
            raise ValueError('capture: consumer ID mismatch')
        logical._hex(value['revision_sha256'])
    return copy.deepcopy(values)


def _dependency_records(record, records):
    by_id = {}
    for item in records:
        logical._record(item)
        key = item['record_id']
        if key in by_id:
            raise ValueError('capture: duplicate dependency record')
        if item['context']['repository'] != record['context']['repository']:
            raise ValueError('capture: foreign dependency record')
        by_id[key] = item
    by_id[record['record_id']] = record
    if sum(1 + len(item['members']) + len(item['dependencies']) for item in by_id.values()) > logical.MAX_ENTRIES:
        raise ValueError('capture: dependency closure entry limit exceeded')
    visiting, visited = set(), set()
    pending = [(record, False)]
    while pending:
        item, leaving = pending.pop()
        key = item['record_id']
        if leaving:
            visiting.remove(key)
            visited.add(key)
            continue
        if key in visiting:
            raise ValueError('capture: cyclic dependency closure')
        if key in visited:
            continue
        visiting.add(key)
        pending.append((item, True))
        for reference in reversed(item['dependencies']):
            child = by_id.get(reference['record_id'])
            if child is None or child['closure_sha256'] != reference['closure_sha256']:
                raise ValueError('capture: missing or changed dependency closure')
            pending.append((child, False))
    if visited != set(by_id):
        raise ValueError('capture: unreferenced dependency record')


def issue_session(store, *, repository, workflow, task, check, target='',
                  inputs_sha256, sources_sha256, consumers, dependencies=()):
    """Issue one attempt under an existing, descriptor-held producer session.

    The environment and advisory activity FDs are deliberately not consulted.
    Use resume_session for a recorded interrupted attempt; new issues are fresh.
    """
    binding = store.producer_binding()
    caller = _authenticated_caller()
    repository = _repository(repository, caller)
    root = Path(repository['root']) / 'output/test-runs'
    if not store.path.is_relative_to(root):
        raise ValueError('capture: producer journal is outside shared checkout storage')
    fd, run = binding[1], binding[3]
    owner = _owner(store.path, fd, repository, caller)
    context = dict(repository=repository, workflow=workflow, owner=owner, run=run,
                   task=task, check=check, attempt=uuid.uuid4().hex, target=target,
                   inputs_sha256=inputs_sha256, sources_sha256=sources_sha256)
    logical.validate_context(context)
    validate_targets(repository['root'], [target] if target else [])
    consumers = _consumers(consumers)
    dependencies = copy.deepcopy(list(dependencies))
    for record in dependencies:
        logical._record(record)
    handle = _SessionHandle(_MINT)
    _handles[handle] = dict(store=store, binding=binding, context=context,
                            consumers=consumers, dependencies=dependencies)
    return handle


def _session(handle):
    if type(handle) is not _SessionHandle or handle not in _handles:
        raise ValueError('capture: a producer-issued session handle is required')
    value = _handles[handle]
    if value['store'].producer_binding() is not value['binding']:
        raise ValueError('capture: session handle is stale')
    if _authenticated_caller() != value['context']['owner']['caller']:
        raise ValueError('capture: session caller changed')
    if _repository(value['context']['repository']['root'], value['context']['owner']['caller']) != value['context']['repository']:
        raise ValueError('capture: checkout changed')
    return value


def session_context(handle):
    return copy.deepcopy(_session(handle)['context'])


def resume_session(store, capture_id):
    """Reissue only an exact registered attempt under a newly held live owner."""
    logical._hex(capture_id)
    binding = store.producer_binding()
    with store.locked(binding[1], 'writer.lock'):
        state = store.read(binding[1])
        matches = [item for item in state.get('captures', []) if item['capture_id'] == capture_id]
    if len(matches) != 1:
        raise ValueError('capture: missing same-run resume intent')
    intent = matches[0]['intent']
    context = intent['record']['context']
    if context['run'] != binding[3]:
        raise ValueError('capture: resume requires the original producer run')
    handle = issue_session(store, repository=context['repository']['root'],
        workflow=context['workflow'], task=context['task'], check=context['check'], target=context['target'],
        inputs_sha256=context['inputs_sha256'], sources_sha256=context['sources_sha256'],
        consumers=intent['consumers'], dependencies=intent['dependencies'])
    if {key: value for key, value in _handles[handle]['context'].items() if key != 'attempt'} != {key: value for key, value in context.items() if key != 'attempt'}:
        raise ValueError('capture: resumed producer binding changed')
    _handles[handle]['context']['attempt'] = context['attempt']
    return handle


def _fingerprint(info):
    return [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_blocks]


def _write(fd, name, value):
    payload = logical.encoded(value)
    temporary = name + '.tmp'
    # Like Store.save, this fixed private journal scratch is retriable after a
    # short write. It is never a payload or caller-selected deletion target.
    out = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=fd)
    try:
        with os.fdopen(out, 'wb') as stream:
            retention.private(os.fstat(stream.fileno()), regular=True)
            os.ftruncate(stream.fileno(), 0)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, name, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    except BaseException:
        # Preserve an interrupted temporary record; never adopt unknown bytes.
        raise


def _read(fd, name):
    source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(source, 'rb') as stream:
        retention.private(os.fstat(stream.fileno()), regular=True)
        data = stream.read(logical.MAX_METADATA + 1)
        result = logical.decoded(data)
        if data != logical.encoded(result):
            raise ValueError('capture: noncanonical registration')
        return result


def _pin_record(parent, name, stack, pins):
    source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    stack.callback(os.close, source)
    info = os.fstat(source)
    retention.private(info, regular=True)
    data = os.pread(source, logical.MAX_METADATA + 1, 0)
    result = logical.decoded(data)
    if data != logical.encoded(result):
        raise ValueError('capture: noncanonical registration')
    pins.append((parent, name, source, _fingerprint(info), data, os.geteuid(), os.getegid()))
    return result


@contextmanager
def _source(member, state, store, run, *, guards=None, recording_owner=None,
            recording_source=None):
    if recording_source is not None:
        if recording_owner is None:
            raise ValueError('capture: a held recording source owner is required')
        allocation = member['source_allocation']
        if (allocation['journal'] != str(store.path) or allocation['run'] != run
                or allocation['path'] != recording_source['path']):
            raise ValueError('capture: recording belongs to a foreign workflow')
        with recording_owner._capture_source(member, recording_source, guards=guards) as value:
            yield value
        return
    allocation = member['source_allocation']
    if allocation['journal'] != str(store.path) or allocation['run'] != run:
        raise ValueError('capture: member belongs to a foreign producer')
    selected = [item for item in state['paths'] if item == {
        key: allocation[key] for key in ('path', 'device', 'inode', 'mode')}]
    if len(selected) != 1:
        raise ValueError('capture: finalized source is not registered to this run')
    with ExitStack() as stack:
        root = stack.enter_context(retention.directory_descriptor(allocation['path']))
        info = os.fstat(root)
        retention.allocation_identity(info, 0o700)
        if (info.st_dev, info.st_ino) != (allocation['device'], allocation['inode']):
            raise ValueError('capture: source allocation was replaced')
        parent = stack.enter_context(retention.directory_descriptor(Path(allocation['path']).parent))
        if retention.mount_id(root) != retention.mount_id(parent):
            raise ValueError('capture: mounted source allocation')
        parts = Path(member['original_path']).relative_to(allocation['path']).parts
        parent = root
        directories = []
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            stack.callback(os.close, child)
            child_info = os.fstat(child)
            if child_info.st_uid != os.geteuid() or child_info.st_mode & 0o022 or retention.mount_id(child) != retention.mount_id(root):
                raise ValueError('capture: unsafe source parent')
            directories.append((parent, part, child, _directory_identity(child_info)))
            parent = child
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        stack.callback(os.close, fd)
        info = os.fstat(fd)
        logical._file_identity(_fingerprint(info), allocation, member['bytes'])
        if info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise ValueError('capture: unsafe finalized source')
        original = _fingerprint(info)
        root_identity = _directory_identity(os.fstat(root))

        def validate():
            # Rewalk the recorded absolute allocation as well as every held
            # nested edge. A held obsolete parent alone cannot prove its path.
            with retention.directory_descriptor(allocation['path']) as current_root:
                if _directory_identity(os.fstat(current_root)) != root_identity:
                    raise ValueError('capture: source allocation path was replaced')
            for directory, name, child, identity in directories:
                if (_directory_identity(os.fstat(child)) != identity
                        or _directory_identity(os.stat(name, dir_fd=directory, follow_symlinks=False)) != identity):
                    raise ValueError('capture: finalized source directory was replaced')
            current = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
            if _fingerprint(current) != original or _fingerprint(os.fstat(fd)) != original:
                raise ValueError('capture: finalized source path changed or was replaced')

        if guards is not None:
            guards.append(validate)
        try:
            yield fd, info
        finally:
            validate()


def _hash(fd, size, output=None):
    # Use the established bounded copy and private-key content guard.
    if __package__:
        from .evidence_bundle import stream_bytes
    else:
        from evidence_bundle import stream_bytes
    os.lseek(fd, 0, os.SEEK_SET)
    with os.fdopen(os.dup(fd), 'rb') as stream:
        return stream_bytes(stream, size, output)


def _slot_path(repository, capture_id, *, create=False):
    logical._hex(capture_id)
    return storage.directory('captures', root=repository['root'], create=create) / capture_id


def _registration(charge, state='required'):
    return dict(schema='onpc-sealed-registration', version=1,
                capture_id=charge['capture_id'], state=state, intent=charge['intent'],
                slot={key: charge[key] for key in ('path', 'device', 'inode', 'mode')},
                reserved_bytes=charge['reserved_bytes'], files={}, request=None)


def _checked_registration(value, charge=None):
    logical._object(value, {'schema', 'version', 'capture_id', 'state', 'intent', 'slot',
                            'reserved_bytes', 'files', 'request'}, 'sealed registration')
    if value['schema'] != 'onpc-sealed-registration' or type(value['version']) is not int or value['version'] != 1:
        raise ValueError('capture: unsupported registration')
    logical._hex(value['capture_id'])
    logical._choice(value['state'], {'required', 'sealing', 'sealed'})
    retention.publication_record(value['slot'])
    logical._integer(value['reserved_bytes'])
    intent_fields = {'producer', 'record', 'consumers', 'dependencies', 'originals'}
    if type(value['intent']) is not dict:
        raise ValueError('capture: invalid capture intent')
    logical._object(value['intent'], intent_fields | ({'recording_source'}
                    if 'recording_source' in value['intent'] else set()), 'capture intent')
    intent = value['intent']
    _validate_producer(intent['producer'])
    logical._record(intent['record'])
    _dependency_records(intent['record'], intent['dependencies'])
    _consumers(intent['consumers'])
    if 'recording_source' in intent:
        _validate_recording_source(intent['recording_source'], intent['record'])
    logical._ordered(intent['originals'], lambda item: item['member_id'], 'original identities')
    members = {item['member_id']: item for item in intent['record']['members']}
    if {item['member_id'] for item in intent['originals']} != set(members):
        raise ValueError('capture: original identity allowlist changed')
    for item in intent['originals']:
        logical._object(item, {'member_id', 'identity'}, 'original identity')
        member = members[item['member_id']]
        logical._file_identity(item['identity'], member['source_allocation'], member['bytes'])
    if value['capture_id'] != logical.digest(intent['producer']):
        raise ValueError('capture: capture ID mismatch')
    if intent['record']['context'] != _producer_context(intent):
        raise ValueError('capture: producer context mismatch')
    if type(value['files']) is not dict or len(value['files']) > logical.MAX_ENTRIES:
        raise ValueError('capture: invalid sealed file progress')
    for key, identity in value['files'].items():
        if key not in members or type(identity) is not list or len(identity) != 2:
            raise ValueError('capture: unregistered sealed file progress')
        for number in identity:
            logical._integer(number, minimum=1)
    if value['state'] == 'required' and (value['files'] or value['request'] is not None):
        raise ValueError('capture: required registration contains payload progress')
    if value['state'] == 'sealing' and value['request'] is not None:
        raise ValueError('capture: unfinished registration contains sealed request')
    if value['state'] == 'sealed':
        if set(value['files']) != set(members):
            raise ValueError('capture: sealed file progress is incomplete')
        _validate_request(value['request'])
    if charge is not None and (charge['reserved_bytes'] != value['reserved_bytes'] or _registration(charge)['intent'] != intent):
        raise ValueError('capture: parent intent changed')
    if charge is not None and value['slot'] != {key: charge[key] for key in ('path', 'device', 'inode', 'mode')}:
        raise ValueError('capture: slot registration changed')
    return value


def _producer_context(intent):
    context = intent['record']['context']
    producer = intent['producer']
    return dict(context, repository=producer['repository'], owner=producer['owner'],
                run=producer['run'], attempt=producer['attempt'])


def _validate_producer(value):
    logical._object(value, {'repository', 'caller', 'owner', 'run', 'attempt', 'nonce'}, 'capture producer')
    logical.validate_repository(value['repository'])
    logical.validate_owner(value['owner'], repository=value['repository'])
    if value['caller'] != value['owner']['caller']:
        raise ValueError('capture: caller and owner disagree')
    for key in ('run', 'attempt', 'nonce'):
        logical._hex(value[key], 32)


def _publish_registration(fd, registration):
    """Root safety witness is durable before exposing a caller catalogue row."""
    producer = registration['intent']['producer']
    caller = producer['caller']
    if producer['owner']['identity']['uid'] == 0:
        if os.geteuid() != 0:
            raise ValueError('capture: privileged safety witness requires root')
        _write(fd, 'witness.json', registration)
        witness_sha256 = logical.digest(registration)
        checkpoint('witness')
        with _identity(caller['uid'], caller['gid']):
            path = _slot_path(producer['repository'], registration['capture_id'], create=True)
            retention.ensure_directory(path)
            with retention.directory_descriptor(path) as caller_fd:
                _write(caller_fd, 'registration.json', dict(schema='onpc-sealed-witness', version=1,
                    capture_id=registration['capture_id'], request_sha256=(None if registration['request'] is None else registration['request']['request_sha256']),
                    witness_sha256=witness_sha256, state=registration['state']))
    _write(fd, 'registration.json', registration)


def _resume_registration(fd, charge):
    # The private witness wins after interruption between its durable write and
    # the caller catalogue update. Republish that same stage before resuming.
    name = 'witness.json' if charge['intent']['producer']['owner']['identity']['uid'] == 0 else 'registration.json'
    try:
        registration = _checked_registration(_read(fd, name), charge)
    except FileNotFoundError:
        registration = _registration(charge)
    _publish_registration(fd, registration)
    return registration


def _rollback_empty_directory(parent, name, identity):
    """Undo only a newly created, unregistered and still empty exact inode."""
    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    try:
        info = os.fstat(child)
        retention.private(info)
        if ((info.st_dev, info.st_ino) != identity or os.listdir(child)
                or retention.mount_id(child) != retention.mount_id(parent)):
            raise ValueError('capture: unregistered snapshot changed; preserve its identity')
        current = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != identity:
            raise ValueError('capture: unregistered snapshot was replaced')
        os.rmdir(name, dir_fd=parent)
        os.fsync(parent)
    finally:
        os.close(child)


def _rollback_empty_file(parent, name, descriptor, identity):
    info = os.fstat(descriptor)
    retention.private(info, regular=True)
    current = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if ((info.st_dev, info.st_ino) != identity or info.st_size != 0
            or (current.st_dev, current.st_ino) != identity):
        raise ValueError('capture: unregistered sealed file changed; preserve its identity')
    os.unlink(name, dir_fd=parent)
    os.fsync(parent)


def _registered_progress(fd, charge):
    """None means uncertainty; only a verified old stage can permit rollback."""
    name = 'witness.json' if charge['intent']['producer']['owner']['identity']['uid'] == 0 else 'registration.json'
    try:
        return _checked_registration(_read(fd, name), charge)
    except BaseException:
        return None


def _intent_entries(intent):
    records = [intent['record'], *intent['dependencies']]
    return (len(intent['consumers']) + len(intent['originals'])
            + 3 * len(intent['record']['members'])
            + sum(1 + len(item['members']) + len(item['dependencies'])
                  + len(item['cleanup']['record_members'])
                  + len(item['cleanup']['scope']['resources']) for item in records))


def _projected_registration(intent, path):
    """Conservative exact-shape wire forecast before allocating a stage."""
    large = 2 ** 64 - 1
    producer, record = intent['producer'], intent['record']
    allocation = dict(path=str(path / 'snapshot'), device=large, inode=large,
                      mode=0o700, journal=str(path / 'retention-sealed'), run=producer['nonce'])
    owner = dict(producer['owner'], journal=allocation['journal'], identity=dict(
        device=large, inode=large, mode=stat.S_IFDIR | 0o700, uid=os.geteuid(), gid=os.getegid()))
    mappings = [dict(member_id=member['member_id'], original_path=member['original_path'],
        source_allocation=member['source_allocation'], sealed_path=str(path / 'snapshot' / member['member_id']),
        sealed_allocation=allocation, identity=[large, large, stat.S_IFREG | 0o600,
            os.geteuid(), os.getegid(), 1, member['bytes'], large, large, large], sha256=member['sha256'])
        for member in record['members']]
    request = dict(schema='onpc-finalized-capture', version=1, capture_id=logical.digest(producer),
        producer=producer, record=record, consumers=intent['consumers'],
        sealed=dict(owner=owner, allocation=allocation, mappings=mappings), request_sha256='f' * 64)
    registration = dict(schema='onpc-sealed-registration', version=1,
        capture_id=request['capture_id'], state='sealed', intent=intent,
        slot=dict(path=str(path), device=large, inode=large, mode=0o700),
        reserved_bytes=large, files={member['member_id']: [large, large] for member in record['members']}, request=request)
    return len(logical.encoded(registration))


def _capacity(state, proposed, intent):
    records = [record for _, record in retention.latest_allocations([*state['history'], state])]
    current = sum(retention.allocation_bytes(record) for record in records)
    current += sum(retention.capture_bytes(entry) for entry in [*state['history'], state])
    entries = _intent_entries(intent) + sum(len(entry['paths']) + sum(_intent_entries(item['intent'])
                    for item in entry.get('captures', []))
                  for entry in [*state['history'], state])
    if entries > logical.MAX_ENTRIES:
        raise ValueError('capture: parent collection entry capacity exhausted')
    if current + proposed > retention.MAX_RETAINED_BYTES:
        raise ValueError('capture: capacity refusal; current=%d projected=%d limit=%d; finish the recorded capture or select a smaller independent closure' %
                         (current, current + proposed, retention.MAX_RETAINED_BYTES))


def _check_recording_owner(owner):
    if __package__:
        from .recording_storage import Recording
    else:
        from recording_storage import Recording
    if type(owner) is not Recording or owner.fd is None or owner.lock is None:
        raise ValueError('capture: a live recording case owner is required')
    owner._root_guard()


def _validate_recording_source(value, record):
    logical._object(value, {'category', 'case_id', 'required_id', 'path', 'root', 'lock'},
                    'recording source authority')
    import re
    if (not isinstance(value['category'], str)
            or re.fullmatch(r'[a-z][a-z0-9]*', value['category']) is None
            or type(value['case_id']) is not int or value['case_id'] <= 0):
        raise ValueError('capture: invalid recording case')
    logical._hex(value['required_id'])
    repository = record['context']['repository']
    # Derive the only admissible source root, without accepting a caller path
    # or giving retention any cleanup claim over this shared directory.
    root = storage.recordings_directory(root=repository['root'], create=False,
        **({'caller_uid': repository['uid']} if os.geteuid() == 0 else {}))
    if value['path'] != str(root):
        raise ValueError('capture: recording source is outside shared recordings')
    logical._object(value['root'], {'device', 'inode', 'mode', 'uid', 'gid'}, 'recording root identity')
    logical._object(value['lock'], {'name', 'device', 'inode'}, 'recording case lease identity')
    for key in ('device', 'inode'):
        logical._integer(value['root'][key], minimum=1)
        logical._integer(value['lock'][key], minimum=1)
    key = '%s-%d' % (value['category'], value['case_id'])
    if value['lock']['name'] != '.' + key + '.lock':
        raise ValueError('capture: recording case lease changed')
    if (record['status'] != 'diagnostic' or record['completeness'] != 'complete'
            or len(record['members']) != 2):
        raise ValueError('capture: required recording must be complete diagnostic media and origin')
    if not all(item['required'] for item in record['members']) or {
            item['role'] for item in record['members']} != {'media', 'diagnostic'}:
        raise ValueError('capture: incomplete recording origin closure')
    for member in record['members']:
        if Path(member['original_path']).parent != root or member['source_allocation']['path'] != str(root):
            raise ValueError('capture: recording member outside exact case root')


def resume_recording_session(store, recording_owner):
    """Resume even when interruption preceded the parent's capture registration.

    The case's private required declaration supplies the attempt. A held case
    and the exact original live workflow owner jointly authorize reissuance;
    caller JSON and a path cannot mint a handle.
    """
    _check_recording_owner(recording_owner)
    required = recording_owner.state['required']
    if required is None or required['retired']:
        raise ValueError('capture: no pending required recording to resume')
    recording_owner._validate_required(required)
    recording_owner._check_source_binding(recording_owner._source_binding(required))
    recording_owner._verify(required['original'])
    context = required['context']
    binding = store.producer_binding()
    if (str(store.path) != context['owner']['journal'] or binding[3] != context['run']
            or _directory_identity(os.fstat(binding[1])) != context['owner']['identity']):
        raise ValueError('capture: recording resume requires the original live workflow run')
    handle = issue_session(store, repository=context['repository']['root'],
        workflow=context['workflow'], task=context['task'], check=context['check'], target=context['target'],
        inputs_sha256=context['inputs_sha256'], sources_sha256=context['sources_sha256'],
        consumers=required['consumers'], dependencies=required['dependencies'])
    if ({key: value for key, value in _handles[handle]['context'].items() if key != 'attempt'} !=
            {key: value for key, value in context.items() if key != 'attempt'}):
        raise ValueError('capture: resumed recording producer binding changed')
    _handles[handle]['context']['attempt'] = context['attempt']
    return handle


def finalize_recording_capture(session_handle, recording_owner, *, consumer_ids):
    """Adapt one case-owned recording without adopting its shared directory.

    The existing case journal owns the pending requirement and source witness;
    the existing workflow journal owns and budgets the ordinary sealed capture.
    """
    _check_recording_owner(recording_owner)
    session = _session(session_handle)
    owner = recording_owner
    context = session['context']
    if (owner.store.path != storage.recordings_directory(root=context['repository']['root'], create=False)
            or context['owner']['caller'] != _authenticated_caller()
            or os.geteuid() != context['owner']['caller']['uid']):
        raise ValueError('capture: recording belongs to another checkout or caller')
    if (type(consumer_ids) not in (tuple, list) or not consumer_ids
            or list(consumer_ids) != sorted(set(consumer_ids))
            or any(item not in session['consumers'] for item in consumer_ids)):
        raise ValueError('capture: expected finite owner-issued recording consumers')
    consumers = {key: session['consumers'][key] for key in consumer_ids}
    required = owner.state['required']
    if required is not None and required['retired']:
        # A new immutable requirement may replace the prior one only after its
        # recorded parent charge has actually completed normal cleanup.
        prior = retention.Store(required['context']['owner']['journal'])
        with prior.opened() as prior_fd, prior.locked(prior_fd, 'writer.lock', shared=True):
            if _directory_identity(os.fstat(prior_fd)) != required['context']['owner']['identity']:
                raise ValueError('capture: prior recording workflow owner changed')
            state = prior.read(prior_fd)
            if state is None or any(charge['capture_id'] == required['capture_id']
                    for entry in [*state['history'], state] for charge in entry.get('captures', [])):
                raise ValueError('capture: finish prior recording source cleanup before another requirement')
        owner._remove(required['origin']['file'])
        owner.state['required'] = required = None
        owner._save()
    if required is None:
        original = owner.state['current']
        if original is None or owner.state['pending'] is not None:
            raise ValueError('capture: select an existing finalized recording before replacement')
        owner._verify(original)
        source = owner._open(original)
        try:
            origin = dict(schema='onpc-recording-origin-v1', category=owner.category,
                case_id=owner.case_id, path=str(owner.store.path / original['name']),
                identity=_fingerprint(os.fstat(source)), sha256=original['sha256'],
                provenance=copy.deepcopy(owner.state['provenance']), context=copy.deepcopy(context),
                root=_directory_identity(os.fstat(owner.fd)), lock=copy.deepcopy(owner.lock_identity))
        finally:
            os.close(source)
        payload = logical.encoded(origin)
        # Register the empty witness in the case owner before writing bytes.
        name = '.' + owner.key + '-origin-' + uuid.uuid4().hex + '.json'
        with _registration_window():
            witness = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                              0o600, dir_fd=owner.fd)
            try:
                info = os.fstat(witness)
                required = dict(id=logical.digest(dict(context=context, consumers=consumers,
                    dependencies=session['dependencies'], origin=origin)),
                    original=copy.deepcopy(original), origin=dict(file=dict(name=name,
                    device=info.st_dev, inode=info.st_ino), payload=origin), context=copy.deepcopy(context),
                    consumers=copy.deepcopy(consumers), dependencies=copy.deepcopy(session['dependencies']),
                    record=None, capture_id=None,
                    acknowledgement=None, parent_acknowledged=False, retired=False)
                owner.state['required'] = required
                owner.state['version'] = 2
                owner._save()
            finally:
                os.close(witness)
        checkpoint('recording.required')
    if (required['context'] != context or required['consumers'] != consumers
            or required['dependencies'] != session['dependencies'] or required['retired']):
        raise ValueError('capture: resume the exact required recording attempt and consumers')
    owner._check_source_binding(owner._source_binding(required))
    owner._verify(required['original'])
    source = owner._open(required['original'])
    try:
        if _fingerprint(os.fstat(source)) != required['origin']['payload']['identity']:
            raise ValueError('capture: required recording original identity changed')
    finally:
        os.close(source)
    payload = logical.encoded(required['origin']['payload'])
    witness_record = required['origin']['file']
    witness = owner._open(witness_record)
    try:
        existing = os.pread(witness, len(payload) + 1, 0)
    finally:
        os.close(witness)
    if existing != payload:
        if required['record'] is not None or required['capture_id'] is not None:
            raise ValueError('capture: finalized recording witness changed')
        witness = os.open(witness_record['name'], os.O_WRONLY | os.O_NOFOLLOW, dir_fd=owner.fd)
        with os.fdopen(witness, 'wb') as stream:
            if (os.fstat(stream.fileno()).st_dev, os.fstat(stream.fileno()).st_ino) != (
                    witness_record['device'], witness_record['inode']):
                raise ValueError('capture: recording witness was replaced')
            os.ftruncate(stream.fileno(), 0)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(owner.fd)
    allocation = dict(path=str(owner.store.path), device=required['origin']['payload']['root']['device'],
        inode=required['origin']['payload']['root']['inode'], mode=0o700,
        journal=str(session['store'].path), run=context['run'])
    draft = dict(schema=logical.SCHEMA, version=1, context=copy.deepcopy(context),
        status='diagnostic', completeness='complete', members=[
            dict(role='media', original_path=str(owner.store.path / required['original']['name']),
                source_allocation=allocation, bytes=required['original']['size'],
                sha256=required['original']['sha256'], required=True),
            dict(role='diagnostic', original_path=str(owner.store.path / witness_record['name']),
                source_allocation=allocation, bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest(), required=True)],
        dependencies=sorted([dict(record_id=item['record_id'], closure_sha256=item['closure_sha256'])
            for item in session['dependencies']], key=lambda item: item['record_id']),
        cleanup=dict(state='not_applicable', record_members=[],
                     scope=dict(owner=copy.deepcopy(context['owner']), resources=[])))
    record = logical.finalize_record(draft)
    if required['record'] is not None and required['record'] != record:
        raise ValueError('capture: required recording closure changed')
    required['record'] = record
    owner._save()
    identifier = finalize_capture(session_handle, record=record, consumer_ids=consumer_ids,
                                  _recording_owner=owner)
    required['capture_id'] = identifier
    owner._save()
    return identifier


def finalize_capture(session_handle, *, record, consumer_ids, _recording_owner=None):
    """Seal exactly one immutable record; retry the same durable intent/slot."""
    session = _session(session_handle)
    record = copy.deepcopy(record)
    logical._record(record)
    if record['context'] != session['context']:
        raise ValueError('capture: record has wrong issued attempt, target or request context')
    _dependency_records(record, session['dependencies'])
    if type(consumer_ids) not in (list, tuple) or not consumer_ids or len(consumer_ids) > MAX_SELECTIONS:
        raise ValueError('capture: expected finite consumer IDs')
    if list(consumer_ids) != sorted(set(consumer_ids)) or any(key not in session['consumers'] for key in consumer_ids):
        raise ValueError('capture: consumers are not owner-issued revisions')
    consumers = {key: session['consumers'][key] for key in consumer_ids}
    if not record['members'] or len(record['members']) + len(session['dependencies']) > logical.MAX_ENTRIES:
        raise ValueError('capture: invalid finite finalized allowlist')
    if sum(item['bytes'] for item in record['members']) > logical.MAX_BYTES:
        raise ValueError('capture: sealed source exceeds 1 GiB limit')
    store, fd, run = session['store'], session['binding'][1], session['binding'][3]
    recording_source = None
    if _recording_owner is not None:
        _check_recording_owner(_recording_owner)
        required = _recording_owner.state['required']
        if (required is None or required['record'] != record
                or required['context'] != session['context']
                or required['consumers'] != consumers):
            raise ValueError('capture: required recording context changed')
        recording_source = _recording_owner._source_binding(required)
        _validate_recording_source(recording_source, record)
        _recording_owner._check_source_binding(recording_source)
    with store.locked(fd, 'writer.lock'):
        state = store.read(fd)
        matches = [item for item in state.get('captures', [])
                   if item['intent']['producer']['attempt'] == record['context']['attempt']]
        if len(matches) > 1:
            raise ValueError('capture: ambiguous capture attempt')
        charge = copy.deepcopy(matches[0]) if matches else None
    with ExitStack() as sources:
        originals, opened, source_guards = [], {}, []
        for member in record['members']:
            source, info = sources.enter_context(_source(member, state, store, run, guards=source_guards,
                recording_owner=_recording_owner, recording_source=recording_source))
            before = _fingerprint(info)
            if _hash(source, member['bytes']) != member['sha256'] or _fingerprint(os.fstat(source)) != before:
                raise ValueError('capture: finalized source changed')
            originals.append(dict(member_id=member['member_id'], identity=before))
            opened[member['member_id']] = source
        if charge is None:
            producer = dict(repository=record['context']['repository'], caller=record['context']['owner']['caller'],
                            owner=record['context']['owner'], run=run, attempt=record['context']['attempt'], nonce=uuid.uuid4().hex)
            intent = dict(producer=producer, record=record, consumers=consumers,
                          dependencies=session['dependencies'], originals=originals)
            if recording_source is not None:
                intent['recording_source'] = recording_source
            capture_id = logical.digest(producer)
            with _registration_window(), store.locked(fd, 'writer.lock'):
                state = store.read(fd)
                if len(state.get('captures', [])) >= MAX_SELECTIONS:
                    raise ValueError('capture: capture slot capacity exhausted')
                path = _slot_path(producer['repository'], capture_id, create=True)
                control_bytes = _projected_registration(intent, path)
                reserved = (sum((member['bytes'] + 4095) // 4096 * 4096 for member in record['members'])
                            + ((control_bytes + 4095) // 4096 * 4096) * 4
                            + len(logical.encoded(intent)) * 2 + len(record['members']) * 512 + 131072)
                _capacity(state, reserved, intent)
                projected = copy.deepcopy(state)
                projected.setdefault('captures', []).append(dict(capture_id=capture_id,
                    path=str(path), device=2 ** 64 - 1, inode=2 ** 64 - 1, mode=0o700,
                    reserved_bytes=reserved, intent=intent))
                retention.validate_captures(projected['captures'])
                logical.encoded(projected)
                os.mkdir(path, 0o700)
                with retention.directory_descriptor(path) as slot:
                    info = os.fstat(slot)
                    charge = dict(capture_id=capture_id, path=str(path), device=info.st_dev,
                                  inode=info.st_ino, mode=0o700, reserved_bytes=reserved, intent=intent)
                    state.setdefault('captures', []).append(charge)
                    try:
                        retention.validate_captures(state['captures'])
                        logical.encoded(state)
                        store.save(fd, state)
                    except BaseException:
                        # A save can raise after its atomic replace committed.
                        # Preserve uncertainty and every identity-recorded stage.
                        try:
                            committed = store.read(fd)
                        except BaseException:
                            committed = None
                        if committed is not None and charge not in committed.get('captures', []):
                            os.rmdir(path)
                        raise
                    registration = _registration(charge)
                    _publish_registration(slot, registration)
            checkpoint('required')
        else:
            capture_id = charge['capture_id']
            if charge['intent']['record'] != record or charge['intent']['consumers'] != consumers or charge['intent']['originals'] != originals:
                raise ValueError('capture: resumed finalized allowlist or source identity changed')
            if charge['intent'].get('recording_source') != recording_source:
                raise ValueError('capture: resumed recording authority changed')
        with retention.directory_descriptor(charge['path']) as slot:
            info = os.fstat(slot)
            if (info.st_dev, info.st_ino) != (charge['device'], charge['inode']):
                raise ValueError('capture: sealed slot was replaced')
            registration = _resume_registration(slot, charge)
            if registration['state'] == 'sealed':
                with capture_scope(record['context']['repository']['root'],
                                   charge['intent']['producer']['caller']['uid'], charge['intent']['producer']['caller']['gid'], capture_id) as request:
                    if request != registration['request']:
                        raise ValueError('capture: sealed request changed')
                return capture_id
            registration['state'] = 'sealing'
            _publish_registration(slot, registration)
            checkpoint('sealing')
            sealed_store = retention.Store(Path(charge['path']) / 'retention-sealed')
            snapshot = Path(charge['path']) / 'snapshot'
            nonce = charge['intent']['producer']['nonce']
            with sealed_store.session(run=nonce, recover=lambda _state: True):
                with sealed_store.opened() as sealed_fd:
                    sealed_state = sealed_store.read(sealed_fd)
                    if not sealed_state['paths']:
                        with _registration_window():
                            os.mkdir(snapshot, 0o700)
                            snapshot_info = os.stat('snapshot', dir_fd=slot, follow_symlinks=False)
                            snapshot_identity = snapshot_info.st_dev, snapshot_info.st_ino
                            snapshot_record = dict(path=str(snapshot), device=snapshot_info.st_dev,
                                                   inode=snapshot_info.st_ino, mode=0o700)
                            try:
                                retention.retain(snapshot)
                            except BaseException:
                                try:
                                    committed = sealed_store.read(sealed_fd)
                                except BaseException:
                                    committed = None
                                if (committed is not None and committed['run'] == nonce
                                        and not any(item['path'] == str(snapshot) for item in committed['paths'])):
                                    _rollback_empty_directory(slot, 'snapshot', snapshot_identity)
                                raise
                        sealed_state = sealed_store.read(sealed_fd)
                    if len(sealed_state['paths']) != 1 or sealed_state['paths'][0]['path'] != str(snapshot):
                        raise ValueError('capture: unexpected sealed allocation')
                    sealed_record = sealed_state['paths'][0]
                    sealed_allocation = dict(sealed_record, journal=str(sealed_store.path), run=nonce)
                    sealed_owner = _owner(sealed_store.path, sealed_fd, record['context']['repository'], charge['intent']['producer']['caller'])
                with retention.directory_descriptor(snapshot) as destination:
                    mappings = []
                    for member in record['members']:
                        name = member['member_id']
                        prior = registration['files'].get(name)
                        flags = os.O_WRONLY | os.O_NOFOLLOW | (os.O_CREAT | os.O_EXCL if prior is None else 0)
                        with ExitStack() as output_owner:
                            with _registration_window():
                                output = os.open(name, flags, 0o600, dir_fd=destination)
                                try:
                                    stream = os.fdopen(output, 'wb')
                                except BaseException:
                                    os.close(output)
                                    raise
                                # Own the descriptor before unmasking can raise.
                                output_owner.enter_context(stream)
                                info = os.fstat(stream.fileno())
                                try:
                                    retention.private(info, regular=True)
                                    if prior is not None and [info.st_dev, info.st_ino] != prior:
                                        raise ValueError('capture: partial sealed file was replaced')
                                    registration['files'][name] = [info.st_dev, info.st_ino]
                                    _publish_registration(slot, registration)
                                except BaseException:
                                    durable = _registered_progress(slot, charge)
                                    if prior is None and durable is not None and name not in durable['files']:
                                        _rollback_empty_file(destination, name, stream.fileno(),
                                                             (info.st_dev, info.st_ino))
                                    raise
                            os.ftruncate(stream.fileno(), 0)
                            if _hash(opened[name], member['bytes'], stream) != member['sha256']:
                                raise ValueError('capture: source digest changed while sealing')
                            stream.flush()
                            os.fsync(stream.fileno())
                            sealed_identity = _fingerprint(os.fstat(stream.fileno()))
                        original = next(item['identity'] for item in originals if item['member_id'] == name)
                        if _fingerprint(os.fstat(opened[name])) != original or _hash(opened[name], member['bytes']) != member['sha256']:
                            raise ValueError('capture: finalized source changed while sealing')
                        mappings.append(dict(member_id=name, original_path=member['original_path'],
                            source_allocation=member['source_allocation'], sealed_path=str(snapshot / name),
                            sealed_allocation=sealed_allocation, identity=sealed_identity, sha256=member['sha256']))
                    if sorted(os.listdir(destination)) != sorted(registration['files']):
                        raise ValueError('capture: unregistered sealed payload')
                    os.fsync(destination)
                request = dict(schema='onpc-finalized-capture', version=1, capture_id=capture_id,
                    producer=charge['intent']['producer'], record=record, consumers=consumers,
                    sealed=dict(owner=sealed_owner, allocation=sealed_allocation, mappings=mappings))
                request['request_sha256'] = logical.digest(request)
                _validate_request(request)
            checkpoint('finished')
            _session(session_handle)
            with store.locked(fd, 'writer.lock'):
                current = store.read(fd)
                if charge not in current.get('captures', []):
                    raise ValueError('capture: parent intent changed before seal commit')
                if retention.capture_bytes(dict(captures=[charge])) > charge['reserved_bytes']:
                    raise ValueError('capture: sealed slot exceeded its reserved capacity')
            for validate in source_guards:
                validate()
            registration.update(state='sealed', request=request)
            _publish_registration(slot, registration)
            checkpoint('sealed')
            return capture_id


def _validate_request(value):
    logical._object(value, {'schema', 'version', 'capture_id', 'producer', 'record', 'consumers', 'sealed', 'request_sha256'}, 'capture request')
    if value['schema'] != 'onpc-finalized-capture' or type(value['version']) is not int or value['version'] != 1:
        raise ValueError('capture: unsupported request')
    _validate_producer(value['producer'])
    logical._record(value['record'])
    context = value['record']['context']
    producer = value['producer']
    if (context['repository'] != producer['repository'] or context['owner'] != producer['owner']
            or context['run'] != producer['run'] or context['attempt'] != producer['attempt']):
        raise ValueError('capture: request context differs from producer')
    _consumers(value['consumers'])
    if value['capture_id'] != logical.digest(value['producer']):
        raise ValueError('capture: request producer ID mismatch')
    logical._hex(value['request_sha256'])
    if value['request_sha256'] != logical.digest({key: item for key, item in value.items() if key != 'request_sha256'}):
        raise ValueError('capture: request digest mismatch')
    sealed = value['sealed']
    logical._object(sealed, {'owner', 'allocation', 'mappings'}, 'sealed request')
    logical.validate_owner(sealed['owner'], repository=value['producer']['repository'])
    logical.validate_allocation(sealed['allocation'])
    if sealed['owner']['journal'] != sealed['allocation']['journal']:
        raise ValueError('capture: sealed journal mismatch')
    members = {item['member_id']: item for item in value['record']['members']}
    logical._ordered(sealed['mappings'], lambda item: item['member_id'], 'sealed mappings')
    if {item['member_id'] for item in sealed['mappings']} != set(members):
        raise ValueError('capture: incomplete finalized allowlist')
    for mapping in sealed['mappings']:
        logical._object(mapping, {'member_id', 'original_path', 'source_allocation', 'sealed_path', 'sealed_allocation', 'identity', 'sha256'}, 'sealed mapping')
        member = members[mapping['member_id']]
        if (mapping['original_path'] != member['original_path'] or mapping['source_allocation'] != member['source_allocation']
                or mapping['sha256'] != member['sha256'] or mapping['sealed_allocation'] != sealed['allocation']
                or mapping['sealed_path'] != str(Path(sealed['allocation']['path']) / mapping['member_id'])):
            raise ValueError('capture: sealed mapping provenance mismatch')
        logical._file_identity(mapping['identity'], sealed['allocation'], member['bytes'])


def capture_status(handle, capture_id):
    session = _session(handle)
    logical._hex(capture_id)
    store, fd = session['store'], session['binding'][1]
    with store.locked(fd, 'writer.lock'):
        state = store.read(fd)
        matches = [item for item in state.get('captures', []) if item['capture_id'] == capture_id]
    if len(matches) != 1:
        raise ValueError('capture: missing producer registration')
    with retention.directory_descriptor(matches[0]['path']) as slot:
        name = 'witness.json' if matches[0]['intent']['producer']['owner']['identity']['uid'] == 0 else 'registration.json'
        return copy.deepcopy(_checked_registration(_read(slot, name), matches[0]))


@contextmanager
def capture_scope(checkout, uid, gid, capture_id, *, expected=None, target=None, metadata=None):
    """Pin only one registered finished subowner, without opening its parent."""
    logical._hex(capture_id)
    if expected is not None:
        logical._hex(expected)
    for item in (uid, gid):
        logical._integer(item)
    caller = dict(uid=uid, gid=gid)
    repository = _repository(checkout, caller)
    reader_uid, reader_gid = os.geteuid(), os.getegid()
    with ExitStack() as stack:
        control_pins = []
        with _identity(uid, gid):
            caller_path = _slot_path(repository, capture_id)
            caller_fd = stack.enter_context(retention.directory_descriptor(caller_path))
            retention.private(os.fstat(caller_fd))
            registration = _pin_record(caller_fd, 'registration.json', stack, control_pins)
        privileged = registration.get('schema') == 'onpc-sealed-witness'
        if privileged:
            if reader_uid != 0:
                raise ValueError('capture: privileged snapshot requires authenticated helper')
            logical._object(registration, {'schema', 'version', 'capture_id', 'request_sha256', 'witness_sha256', 'state'}, 'witness registration')
            if type(registration['version']) is not int or registration['version'] != 1 or registration['capture_id'] != capture_id:
                raise ValueError('capture: invalid witness registration')
            path = _slot_path(repository, capture_id)
            slot = stack.enter_context(retention.directory_descriptor(path))
            retention.private(os.fstat(slot))
            witness = _checked_registration(_pin_record(slot, 'witness.json', stack, control_pins))
            if logical.digest(witness) != registration['witness_sha256'] or witness['state'] != registration['state']:
                raise ValueError('capture: private safety witness mismatch')
            if witness['request'] is not None and witness['request']['request_sha256'] != registration['request_sha256']:
                raise ValueError('capture: witness request digest mismatch')
            registration = witness
        else:
            path, slot = caller_path, caller_fd
            registration = _checked_registration(registration)
        if registration['state'] != 'sealed' or registration['request'] is None:
            raise ValueError('capture: registration is pending, not sealed')
        request = registration['request']
        _validate_request(request)
        producer = request['producer']
        if (producer['repository'] != repository or producer['caller'] != caller
                or producer['owner']['identity']['uid'] != (0 if privileged else uid)
                or request['capture_id'] != capture_id or registration['capture_id'] != capture_id
                or request['producer'] != registration['intent']['producer']
                or request['record'] != registration['intent']['record']
                or request['consumers'] != registration['intent']['consumers']):
            raise ValueError('capture: foreign registered producer')
        if expected is not None and request['request_sha256'] != expected:
            raise ValueError('capture: wrong expected request digest')
        if target is not None and request['record']['context']['target'] != target:
            raise ValueError('capture: wrong registered target')
        info = os.fstat(slot)
        if registration['slot'] != dict(path=str(path), device=info.st_dev, inode=info.st_ino, mode=0o700):
            raise ValueError('capture: registered slot was replaced')
        sealed = request['sealed']
        if (sealed['owner']['journal'] != str(path / 'retention-sealed')
                or sealed['allocation']['path'] != str(path / 'snapshot')):
            raise ValueError('capture: sealed owner is outside registered slot')
        owner_uid = 0 if privileged else uid
        with _identity(owner_uid, 0 if privileged else gid):
            store = retention.Store(sealed['owner']['journal'])
            state = stack.enter_context(store.inspection())
            owner_fd = stack.enter_context(store.opened())
            if _directory_identity(os.fstat(owner_fd)) != sealed['owner']['identity']:
                raise ValueError('capture: sealed owner was replaced')
            allocation = sealed['allocation']
            record = {key: allocation[key] for key in ('path', 'device', 'inode', 'mode')}
            if (state is None or state['run'] != allocation['run'] or state['history'] or state['paths'] != [record]):
                raise ValueError('capture: sealed allocation registration changed')
            snapshot = stack.enter_context(retention.directory_descriptor(allocation['path']))
            snapshot_info = os.fstat(snapshot)
            retention.allocation_identity(snapshot_info, 0o700)
            if (snapshot_info.st_dev, snapshot_info.st_ino) != (allocation['device'], allocation['inode']):
                raise ValueError('capture: sealed allocation was replaced')
            if sorted(os.listdir(snapshot)) != sorted(item['member_id'] for item in sealed['mappings']):
                raise ValueError('capture: sealed snapshot allowlist changed')
            before = {}
            for mapping in sealed['mappings']:
                member = next(item for item in request['record']['members'] if item['member_id'] == mapping['member_id'])
                file_fd = os.open(mapping['member_id'], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=snapshot)
                stack.callback(os.close, file_fd)
                info = os.fstat(file_fd)
                retention.private(info, regular=True)
                if _fingerprint(info) != mapping['identity'] or _hash(file_fd, member['bytes']) != mapping['sha256']:
                    raise ValueError('capture: sealed file changed')
                before[file_fd] = mapping['identity']
        if metadata is not None:
            if type(metadata) is not dict or metadata:
                raise ValueError('capture: scope metadata output must be an empty dictionary')
            metadata['originals'] = copy.deepcopy(registration['intent']['originals'])
        yield copy.deepcopy(request)
        for parent, name, descriptor, identity, data, pin_uid, pin_gid in control_pins:
            with _identity(pin_uid, pin_gid):
                if (_fingerprint(os.fstat(descriptor)) != identity
                        or _fingerprint(os.stat(name, dir_fd=parent, follow_symlinks=False)) != identity
                        or os.pread(descriptor, logical.MAX_METADATA + 1, 0) != data):
                    raise ValueError('capture: registered control record changed during read')
        with _identity(owner_uid, 0 if privileged else gid):
            with retention.directory_descriptor(path) as current_slot:
                if _directory_identity(os.fstat(current_slot)) != _directory_identity(os.fstat(slot)):
                    raise ValueError('capture: sealed slot was replaced during read')
            for file_fd, identity in before.items():
                if _fingerprint(os.fstat(file_fd)) != identity:
                    raise ValueError('capture: sealed file changed during read')
            for mapping in sealed['mappings']:
                if _fingerprint(os.stat(mapping['member_id'], dir_fd=snapshot, follow_symlinks=False)) != mapping['identity']:
                    raise ValueError('capture: sealed file path changed during read')


def inspect_capture(checkout, uid, gid, capture_id, *, expected=None, target=None):
    with capture_scope(checkout, uid, gid, capture_id, expected=expected, target=target) as request:
        return request


def _publication_module():
    if __package__:
        from . import capture_publication
    else:
        import capture_publication
    return capture_publication


def _acknowledgement(charge, value):
    logical._object(value, {'schema', 'version', 'request', 'delivery', 'caller_slot'},
                    'capture acknowledgement')
    if (value['schema'] != 'onpc-capture-acknowledgement'
            or type(value['version']) is not int or value['version'] != 1):
        raise ValueError('capture: unsupported acknowledgement')
    request = value['request']
    _validate_request(request)
    if (request['capture_id'] != charge['capture_id']
            or request['producer'] != charge['intent']['producer']
            or request['record'] != charge['intent']['record']
            or request['consumers'] != charge['intent']['consumers']):
        raise ValueError('capture: acknowledgement request or closure changed')
    retention.publication_record(value['caller_slot'])
    caller = request['producer']['caller']
    with _identity(caller['uid'], caller['gid']):
        expected_slot = _slot_path(request['producer']['repository'], charge['capture_id'])
    if value['caller_slot']['path'] != str(expected_slot):
        raise ValueError('capture: acknowledgement caller slot changed')
    logical.encoded(value)
    return value


def _charge_owner(store, fd, entry, charge):
    """Validate the private parent claim, never a caller-supplied receipt."""
    _checked_registration(_registration(charge), charge)
    producer = charge['intent']['producer']
    _validate_producer(producer)
    logical._record(charge['intent']['record'])
    if (producer['owner']['journal'] != str(store.path)
            or producer['owner']['identity'] != _directory_identity(os.fstat(fd))
            or producer['run'] != entry['run']
            or charge['capture_id'] != logical.digest(producer)
            or charge['path'] != str(_slot_path(producer['repository'], charge['capture_id']))):
        raise ValueError('capture: required source owner changed')


def _destination_originals(charge, verified):
    """Bind archived provenance to the producer's private before-copy witness."""
    record = charge['intent']['record']
    context = record['context']
    if context['task'] == 'runner-start' and context['check'] == 'report-start':
        # A lifecycle seal protects later producer bytes during preparation.
        # Publishing that seal alone must never authorize whole-run retirement,
        # including via the finished-owner helper after a lost process.
        reference = dict(record_id=record['record_id'], closure_sha256=record['closure_sha256'])
        terminals = [candidate for candidate in verified['manifest']['records']
            if candidate['context']['task'] == 'runner-terminal'
            and candidate['context']['check'] == 'report'
            and all(candidate['context'][key] == context[key]
                    for key in ('repository', 'workflow', 'owner', 'run'))
            and reference in candidate['dependencies']]
        if len(terminals) != 1:
            raise ValueError('capture: runner startup requires its exact terminal closure')
    originals = {item['member_id']: item['identity'] for item in charge['intent']['originals']}
    mappings = {(item['record_id'], item['member_id']): item
                for item in verified['manifest']['member_map']}
    for member in record['members']:
        mapping = mappings.get((record['record_id'], member['member_id']))
        if mapping is None or mapping['original_provenance'] != dict(
                original_path=member['original_path'],
                source_allocation=member['source_allocation'],
                identity=originals[member['member_id']]):
            raise ValueError('capture: destination original identity changed')


@contextmanager
def _recording_scope(charge, owner=None):
    binding = charge['intent'].get('recording_source')
    if binding is None:
        if owner is not None:
            raise ValueError('capture: unexpected recording owner')
        yield None
        return
    if __package__:
        from .recording_storage import Store
    else:
        from recording_storage import Store
    producer = charge['intent']['producer']
    caller = producer['caller']
    with ExitStack() as stack:
        stack.enter_context(_identity(caller['uid'], caller['gid']))
        if owner is None:
            owner = stack.enter_context(Store(root=producer['repository']['root'], create=False).owner(
                binding['category'], binding['case_id']))
        _check_recording_owner(owner)
        required = owner._check_source_binding(binding)
        if (required['record'] != charge['intent']['record']
                or required['context'] != charge['intent']['record']['context']
                or required['consumers'] != charge['intent']['consumers']):
            raise ValueError('capture: required recording closure changed')
        yield owner


@contextmanager
def _original_scope(store, entry, charge, *, missing=False, recording_owner=None):
    """Keep present original descriptors pinned; only retirement retries omit bytes."""
    intent = charge['intent']
    originals = {item['member_id']: item['identity'] for item in intent['originals']}
    if set(originals) != {item['member_id'] for item in intent['record']['members']}:
        raise ValueError('capture: original closure changed')
    with ExitStack() as stack:
        for member in intent['record']['members']:
            try:
                source, info = stack.enter_context(_source(member, entry, store, entry['run'],
                    recording_owner=recording_owner,
                    recording_source=intent.get('recording_source')))
            except FileNotFoundError:
                if missing:
                    continue
                raise
            if (_fingerprint(info) != originals[member['member_id']]
                    or _hash(source, member['bytes']) != member['sha256']):
                raise ValueError('capture: acknowledged original changed')
        yield


def acknowledge_capture(checkout, uid, gid, capture_id, *, expected, session_handle=None,
                        _recording_owner=None):
    """Record custody only under the exact live or finished source owner.

    Destination ownership is acquired before the source writer. The public helper
    can acknowledge a finished owner; a live producer must supply its unforgeable
    in-process session handle. Neither a receipt nor a path is source authority.
    """
    publication = _publication_module()
    with ExitStack() as stack:
        request = stack.enter_context(capture_scope(checkout, uid, gid, capture_id,
                                                    expected=expected))
        producer = request['producer']
        caller = producer['caller']
        if session_handle is not None:
            session = _session(session_handle)
            if session['context'] != request['record']['context']:
                raise ValueError('capture: acknowledgement belongs to another issued attempt')
            store, fd = session['store'], session['binding'][1]
        else:
            owner_uid = producer['owner']['identity']['uid']
            stack.enter_context(_identity(owner_uid, 0 if owner_uid == 0 else gid))
            store = retention.Store(producer['owner']['journal'])
            fd = stack.enter_context(store.opened())
            stack.enter_context(store.locked(fd, 'owner.lock', blocking=False))
            with store.locked(fd, 'writer.lock'):
                retention.finished_owner(fd, store.read(fd))
        delivery = publication.read_delivery(checkout, uid, gid, capture_id)
        verified = stack.enter_context(publication.verified_delivery(
            checkout, uid, gid, capture_id, request, delivery))
        # Inspect the immutable private charge to acquire the case lease before
        # the source writer; never upgrade ownership while holding that writer.
        with store.locked(fd, 'writer.lock', shared=True):
            before = store.read(fd)
            selected = [charge for entry in [*before['history'], before]
                        for charge in entry.get('captures', []) if charge['capture_id'] == capture_id]
        if len(selected) != 1:
            raise ValueError('capture: missing exact source intent for acknowledgement')
        recording_owner = stack.enter_context(_recording_scope(selected[0], _recording_owner))
        # The independent destination lease remains held through durable save.
        with store.locked(fd, 'writer.lock'):
            state = store.read(fd)
            entries = [*state['history'], state]
            matches = [(entry, charge) for entry in entries for charge in entry.get('captures', [])
                       if charge['capture_id'] == capture_id]
            if len(matches) != 1:
                raise ValueError('capture: missing exact source intent for acknowledgement')
            entry, charge = matches[0]
            if charge != selected[0]:
                raise ValueError('capture: source intent changed while acquiring recording ownership')
            _charge_owner(store, fd, entry, charge)
            _destination_originals(charge, verified)
            with _original_scope(store, entry, charge, recording_owner=recording_owner):
                with _identity(uid, gid):
                    caller_path = _slot_path(producer['repository'], capture_id)
                    with retention.directory_descriptor(caller_path) as caller_fd:
                        info = os.fstat(caller_fd)
                        retention.private(info)
                        caller_slot = dict(path=str(caller_path), device=info.st_dev,
                                           inode=info.st_ino, mode=0o700)
                acknowledgement = dict(schema='onpc-capture-acknowledgement', version=1,
                    request=request, delivery=delivery, caller_slot=caller_slot)
                _acknowledgement(charge, acknowledgement)
                if recording_owner is not None:
                    required = recording_owner.state['required']
                    if required['acknowledgement'] not in (None, acknowledgement):
                        raise ValueError('capture: recording acknowledgement changed')
                    required['capture_id'] = capture_id
                    required['acknowledgement'] = copy.deepcopy(acknowledgement)
                    recording_owner._save()
                    checkpoint('recording.receipt')
                previous = charge.get('acknowledgement')
                if previous is not None and previous != acknowledgement:
                    raise ValueError('capture: source acknowledgement changed')
                if previous is None:
                    # Account parent control/recovery growth before the write.
                    proposed = copy.deepcopy(state)
                    selected = next(item for owner in [*proposed['history'], proposed]
                                    for item in owner.get('captures', [])
                                    if item['capture_id'] == capture_id)
                    selected['acknowledgement'] = acknowledgement
                    logical.encoded(proposed)
                    _capacity(state, len(logical.encoded(acknowledgement)) * 2 + 8192,
                              charge['intent'])
                    checkpoint('acknowledgement')
                    charge['acknowledgement'] = acknowledgement
                    store.save(fd, state)
                if recording_owner is not None:
                    recording_owner.state['required']['parent_acknowledged'] = True
                    recording_owner._save()
                    checkpoint('recording.acknowledged')
                checkpoint('acknowledged')
                return copy.deepcopy(acknowledgement)


@contextmanager
def retirement_scope(store, fd):
    """Pin replacement custody outside the source writer, then audit deletions.

    Pending or invalid claims are remembered and refuse only when selected for
    retirement. A parent acknowledgement survives partial source/slot deletion,
    so recovery never needs to adopt a missing or caller-replaced seal control.
    """
    with store.locked(fd, 'writer.lock', publication=True, shared=True):
        state = store.read(fd)
        intent = retention.read_publication(store, fd)
        states = [state]
        if intent is not None:
            states.append(intent['original'])
        entries = [entry for owner in states if owner is not None
                   for entry in [*owner['history'], owner]]
        charges = {}
        for entry in entries:
            for charge in entry.get('captures', []):
                previous = charges.setdefault(charge['capture_id'], (entry, copy.deepcopy(charge)))
                if previous[1] != charge:
                    raise ValueError('capture: conflicting required source claims')
    with ExitStack() as destinations:
        publication = _publication_module() if charges else None
        verified, failures, recording_owners = {}, {}, {}
        # Deterministic trusted journal ordering; no source writer is held here.
        ordered = sorted(charges.items(), key=lambda pair: (
            pair[1][1].get('acknowledgement', {}).get('delivery', {}).get('journal', ''), pair[0]))
        for identifier, (entry, charge) in ordered:
            try:
                _charge_owner(store, fd, entry, charge)
                acknowledgement = _acknowledgement(charge, charge['acknowledgement'])
                producer = acknowledgement['request']['producer']
                caller = producer['caller']
                replacement = destinations.enter_context(publication.verified_delivery(
                    producer['repository']['root'], caller['uid'], caller['gid'], identifier,
                    acknowledgement['request'], acknowledgement['delivery']))
                _destination_originals(charge, replacement)
                recording_owner = destinations.enter_context(_recording_scope(charge))
                if recording_owner is not None:
                    required = recording_owner.state['required']
                    if (not required['parent_acknowledged']
                            or required['acknowledgement'] != acknowledgement):
                        raise ValueError('capture: recording owner has not durably retained this acknowledgement')
                    recording_owners[identifier] = recording_owner
                verified[identifier] = charge
            except (KeyError, ValueError, OSError) as error:
                failures[identifier] = error

        def authorize(selected_entries, *, cleanup=False):
            selected = [(entry, charge) for entry in selected_entries
                        for charge in entry.get('captures', [])]
            # Audit the entire selection before deleting any original or seal.
            for entry, charge in selected:
                identifier = charge['capture_id']
                if identifier not in verified or verified[identifier] != charge:
                    raise ValueError('capture: required source has no verified acknowledgement; '
                                     'finish its recorded publication') from failures.get(identifier)
                _charge_owner(store, fd, entry, charge)
                if not cleanup:
                    with _original_scope(store, entry, charge, missing=True,
                            recording_owner=recording_owners.get(identifier)):
                        pass
                retention.remove({key: charge[key] for key in ('path', 'device', 'inode', 'mode')},
                                 validate_only=True)
                acknowledgement = charge['acknowledgement']
                caller = acknowledgement['request']['producer']['caller']
                with _identity(caller['uid'], caller['gid']):
                    retention.remove(acknowledgement['caller_slot'], validate_only=True)
            if cleanup:
                for _, charge in selected:
                    acknowledgement = charge['acknowledgement']
                    private_slot = {key: charge[key] for key in ('path', 'device', 'inode', 'mode')}
                    retention.remove(private_slot)
                    if acknowledgement['caller_slot'] != private_slot:
                        caller = acknowledgement['request']['producer']['caller']
                        with _identity(caller['uid'], caller['gid']):
                            retention.remove(acknowledgement['caller_slot'])

        yield authorize
