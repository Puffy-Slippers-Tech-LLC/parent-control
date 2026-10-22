"""One durable fixture producer, independent of execution-result retention.

This is the unfinished-slot lifetime only. Bundle construction, publication,
catalogue admission and version retirement belong to their later owners.
"""

from contextlib import contextmanager
import copy
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import stat
import uuid

if __package__:
    from . import test_retention as retention, test_storage as storage
else:
    import test_retention as retention
    import test_storage as storage


SCHEMA = 'onpc-fixture-producer-v1'
RECORD = 'producer.json'
LOCK = 'producer.lock'
_IDENTITY = {'path', 'device', 'inode', 'mode', 'uid', 'mount'}
_SLOT = {'slot_id', 'transaction_id', 'compatibility_key', 'build_key', 'state',
         'owner', 'allocations', 'bundle_id', 'completion_sha256',
         'publication_sequence', 'intent'}
_INTENT = {'transaction_id', 'operation', 'phase', 'expected_generation',
           'resources', 'before', 'after', 'owner', 'cleanup'}


def _require(condition, message):
    if not condition:
        raise ValueError('fixture producer: ' + message)


def _keys(value, expected):
    return isinstance(value, dict) and set(value) == expected


def _token(value):
    return retention.valid_token(value)


def _name(value):
    return isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9-]{0,31}', value) is not None


def _key(value):
    return isinstance(value, str) and 0 < len(value) <= 512 and not any(ord(c) < 32 for c in value)


def _identity(fd, path):
    info = os.fstat(fd)
    return dict(path=str(path), device=info.st_dev, inode=info.st_ino,
                mode=stat.S_IMODE(info.st_mode), uid=info.st_uid,
                mount=retention.mount_id(fd))


def _identity_shape(value, path, *, mode=None):
    _require(_keys(value, _IDENTITY), 'invalid identity fields')
    _require(value['path'] == str(path), 'identity locator changed')
    _require(all(type(value[key]) is int and value[key] >= 0
                 for key in ('device', 'inode', 'mode', 'uid')), 'invalid identity values')
    _require(value['inode'] > 0 and value['uid'] == os.geteuid(), 'identity owner changed')
    _require(isinstance(value['mount'], str) and value['mount'].isdecimal(), 'invalid mount identity')
    _require(mode is None or value['mode'] == mode, 'identity mode changed')


def _check(fd, claim, path, *, private=False, regular=False):
    if private:
        retention.private(os.fstat(fd), regular=regular)
    _require(_identity(fd, path) == claim, 'recorded identity was replaced')


def _owner(lock, root):
    # /proc starttime is stable across PID reuse, unlike a PID alone.
    process = Path('/proc/self/stat').read_text()
    return dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                pid=os.getpid(), start=process.rsplit(')', 1)[1].split()[19],
                lock=_identity(lock, root / LOCK))


@contextmanager
def _registration_signals():
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
    try:
        yield
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def _json_pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, 'duplicate durable field')
        result[key] = value
    return result


class Store:
    """Shared host authority for one unfinished fixture slot.

    There is deliberately no caller-selected storage path and no implicit
    recovery. A failed transaction must be retried by its exact transaction ID.
    """

    def __init__(self):
        self.path = Path(storage.fixture_directory())
        self.checkout = Path(storage.ROOT)
        self._store = retention.Store(self.path)
        with self._store.opened() as fd:
            self._root_identity = _identity(fd, self.path)
        checkout_fd = retention.directory(self.checkout)
        try:
            self._checkout_identity = _identity(checkout_fd, self.checkout)
        finally:
            os.close(checkout_fd)

    def _root(self, fd, state=None):
        retention.private(os.fstat(fd))
        storage.disk_backed(fd)
        _check(fd, self._root_identity, self.path, private=True)
        with self._store.opened() as current:
            _require(_identity(current, self.path) == _identity(fd, self.path),
                     'fixture root was replaced')
        checkout_fd = retention.directory(self.checkout)
        try:
            _check(checkout_fd, self._checkout_identity, self.checkout)
            checkout = dict(root_identity=_identity(checkout_fd, self.checkout),
                            owner_uid=os.geteuid())
            _require(checkout['root_identity']['uid'] == os.geteuid(), 'checkout owner changed')
        finally:
            os.close(checkout_fd)
        if state is not None:
            _require(state['checkout'] == checkout, 'checkout identity changed')
            _check(fd, state['root_identity'], self.path, private=True)
        return checkout

    def _lease(self, fd):
        lock = os.open(LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
                       0o600, dir_fd=fd)
        try:
            retention.private(os.fstat(lock), regular=True)
            _require(retention.mount_id(lock) == retention.mount_id(fd), 'producer lock is mounted')
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError('fixture producer: owner or descendant is active; cleanup pending') from error
            os.fsync(fd)
            return lock
        except BaseException:
            os.close(lock)
            raise

    def _lock_identity(self, fd, state, lock=None):
        opened = os.open(LOCK, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
        try:
            claim = state['slot']['owner']['lock']
            _check(opened, claim, self.path / LOCK, private=True, regular=True)
            if lock is not None:
                _check(lock, claim, self.path / LOCK, private=True, regular=True)
        finally:
            os.close(opened)

    def _validate(self, value):
        _require(_keys(value, {'schema', 'checkout', 'root_identity', 'slot'})
                 and value['schema'] == SCHEMA, 'invalid producer schema')
        checkout = value['checkout']
        _require(_keys(checkout, {'root_identity', 'owner_uid'})
                 and type(checkout['owner_uid']) is int
                 and checkout['owner_uid'] == os.geteuid(), 'invalid checkout owner')
        _identity_shape(checkout['root_identity'], self.checkout)
        _identity_shape(value['root_identity'], self.path, mode=0o700)
        slot = value['slot']
        _require(_keys(slot, _SLOT), 'invalid slot fields')
        _require(_token(slot['slot_id']) and _token(slot['transaction_id']), 'invalid slot identity')
        _require(_key(slot['compatibility_key']) and _key(slot['build_key']), 'invalid build keys')
        _require(slot['state'] in ('reserved', 'producing', 'verifying', 'recovery-pending'),
                 'invalid unfinished phase')
        _require(all(slot[key] is None for key in ('bundle_id', 'completion_sha256', 'publication_sequence')),
                 'unfinished producer has completion fields')
        owner = slot['owner']
        _require(_keys(owner, {'boot_id', 'pid', 'start', 'lock'}), 'invalid owner fields')
        _require(isinstance(owner['boot_id'], str)
                 and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', owner['boot_id']) is not None
                 and type(owner['pid']) is int and owner['pid'] > 0
                 and isinstance(owner['start'], str) and owner['start'].isdecimal(), 'invalid owner identity')
        _identity_shape(owner['lock'], self.path / LOCK, mode=0o600)
        allocations = slot['allocations']
        _require(isinstance(allocations, list) and len(allocations) <= 32, 'invalid allocations')
        names = set()
        for allocation in allocations:
            _require(_keys(allocation, _IDENTITY | {'locator', 'name'}), 'invalid allocation fields')
            name = allocation['name']
            _require(_name(name) and name not in names, 'invalid or duplicate allocation name')
            names.add(name)
            locator = self._locator(slot['transaction_id'], name)
            _require(allocation['locator'] == locator, 'allocation locator changed')
            claim = {key: allocation[key] for key in _IDENTITY}
            _identity_shape(claim, self.path / locator, mode=0o700)
            _require(claim['mount'] == value['root_identity']['mount']
                     and claim['device'] == value['root_identity']['device'], 'allocation filesystem changed')
        intent = slot['intent']
        if slot['state'] != 'recovery-pending':
            _require(intent is None, 'unexpected producer intent')
        else:
            _require(_keys(intent, _INTENT), 'invalid cleanup intent')
            _require(intent['transaction_id'] == slot['transaction_id']
                     and intent['operation'] == 'delete' and intent['phase'] == 'delete'
                     and intent['expected_generation'] is None
                     and intent['resources'] == allocations and intent['owner'] == owner
                     and intent['before'] in ('reserved', 'producing', 'verifying')
                     and intent['after'] is None
                     and intent['cleanup'] == [a['name'] for a in allocations], 'cleanup intent changed')
        return value

    def _read(self, fd):
        try:
            source = os.open(RECORD, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
        except FileNotFoundError:
            return None
        with os.fdopen(source) as stream:
            retention.private(os.fstat(stream.fileno()), regular=True)
            _require(os.fstat(stream.fileno()).st_size <= 1024 * 1024, 'producer record too large')
            value = self._validate(json.load(stream, object_pairs_hook=_json_pairs))
        self._root(fd, value)
        self._lock_identity(fd, value)
        return value

    def _save(self, fd, state):
        self._validate(state)
        self._root(fd, state)
        self._lock_identity(fd, state)
        self._store.save(fd, state, name=RECORD)

    @staticmethod
    def _locator(transaction, name):
        return 'producer-' + transaction + '-' + name

    def _unknown(self, fd, state=None):
        # Inspection is a refusal guard, never a source of deletion authority.
        # An interrupted mkdir with no receipt cannot become a fresh generation.
        registered = set() if state is None else {
            allocation['locator'] for allocation in state['slot']['allocations']}
        _require(not any(name.startswith('producer-') and name not in registered
                         for name in os.listdir(fd)),
                 'unregistered producer allocation preserved; recovery remains pending')

    def snapshot(self):
        """Read the durable unfinished slot under only the short state gate."""
        with self._store.opened() as fd:
            self._root(fd)
            with self._store.locked(fd, 'gate.lock', shared=True):
                return self._read(fd)

    @contextmanager
    def producer(self, *, transaction_id, compatibility_key, build_key):
        _require(_token(transaction_id), 'transaction ID must be UUID32')
        _require(_key(compatibility_key) and _key(build_key), 'invalid build keys')
        with self._store.opened() as fd:
            checkout = self._root(fd)
            lock = self._lease(fd)
            producer = None
            try:
                with self._store.locked(fd, 'gate.lock'):
                    existing = self._read(fd)
                    _require(existing is None, 'unfinished slot exists; exact recover(transaction_id) required')
                    self._unknown(fd)
                    state = dict(schema=SCHEMA, checkout=checkout, root_identity=_identity(fd, self.path),
                                 slot=dict(slot_id=uuid.uuid4().hex, transaction_id=transaction_id,
                                           compatibility_key=compatibility_key, build_key=build_key,
                                           state='reserved', owner=_owner(lock, self.path), allocations=[],
                                           bundle_id=None, completion_sha256=None,
                                           publication_sequence=None, intent=None))
                    self._save(fd, state)
                producer = Producer(self, fd, lock, state)
                try:
                    yield producer
                finally:
                    producer._active = False
                    # Save failure also closes the lease. No removal may follow
                    # until a fresh acquisition proves all inherited references gone.
                    try:
                        self._pending(fd, transaction_id, lock)
                    finally:
                        os.close(lock)
                        lock = None
                    self.recover(transaction_id)
            finally:
                # Never LOCK_UN: a child can hold this same open description.
                if lock is not None:
                    os.close(lock)

    def _pending(self, fd, transaction, lock):
        with self._store.locked(fd, 'gate.lock'):
            state = self._read(fd)
            _require(state is not None and state['slot']['transaction_id'] == transaction,
                     'producer transaction changed')
            self._lock_identity(fd, state, lock)
            slot = state['slot']
            if slot['state'] != 'recovery-pending':
                before = slot['state']
                slot['state'] = 'recovery-pending'
                slot['intent'] = dict(transaction_id=transaction, operation='delete', phase='delete',
                                      expected_generation=None, resources=copy.deepcopy(slot['allocations']),
                                      before=before, after=None, owner=copy.deepcopy(slot['owner']),
                                      cleanup=[a['name'] for a in slot['allocations']])
                self._save(fd, state)
            return state

    def _allocation(self, fd, state, allocation, *, missing=False):
        self._root(fd, state)
        try:
            child = os.open(allocation['locator'], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=fd)
        except FileNotFoundError:
            _require(missing, 'registered allocation is missing')
            return False
        try:
            retention.allocation_identity(os.fstat(child), 0o700)
            claim = {key: allocation[key] for key in _IDENTITY}
            _check(child, claim, self.path / allocation['locator'])
        finally:
            os.close(child)
        return True

    def recover(self, transaction_id):
        """Retry only this recorded transaction; preserve unknown/replaced trees."""
        _require(_token(transaction_id), 'transaction ID must be UUID32')
        with self._store.opened() as fd:
            self._root(fd)
            lock = self._lease(fd)
            try:
                with self._store.locked(fd, 'gate.lock'):
                    state = self._read(fd)
                    if state is None:
                        return False
                    _require(state['slot']['transaction_id'] == transaction_id,
                             'different transaction owns the unfinished slot')
                    self._lock_identity(fd, state, lock)
                state = self._pending(fd, transaction_id, lock)
                self._unknown(fd, state)
                # Whole-selection audit precedes the first destructive operation.
                for allocation in state['slot']['allocations']:
                    if self._allocation(fd, state, allocation, missing=True):
                        retention.remove(allocation, validate_only=True)
                for allocation in state['slot']['allocations']:
                    if self._allocation(fd, state, allocation, missing=True):
                        retention.remove(allocation)
                        os.fsync(fd)
                with self._store.locked(fd, 'gate.lock'):
                    current = self._read(fd)
                    _require(current == state, 'producer record changed during cleanup')
                    self._lock_identity(fd, state, lock)
                    os.unlink(RECORD, dir_fd=fd)
                    os.fsync(fd)
                return True
            finally:
                os.close(lock)


class Producer:
    """One lease-bound producer. Allocation registration always precedes return."""

    def __init__(self, store, fd, lock, state):
        self._store, self._fd, self._lock = store, fd, lock
        self._state, self._active = state, True

    @property
    def slot_id(self):
        return self._state['slot']['slot_id']

    @property
    def transaction_id(self):
        return self._state['slot']['transaction_id']

    def _current(self):
        _require(self._active, 'producer is closed')
        state = self._store._read(self._fd)
        _require(state == self._state and state['slot']['state'] != 'recovery-pending',
                 'producer state changed')
        self._store._lock_identity(self._fd, state, self._lock)
        return state

    def allocate(self, name):
        _require(_name(name), 'allocation name must be one bounded safe component')
        with self._store._store.locked(self._fd, 'gate.lock'):
            state = self._current()
            for allocation in state['slot']['allocations']:
                if allocation['name'] == name:
                    self._store._allocation(self._fd, state, allocation)
                    return Path(allocation['path'])
            _require(len(state['slot']['allocations']) < 32, 'too many producer allocations')
            _require(state['slot']['state'] in ('reserved', 'producing'), 'cannot allocate during verification')
            locator = self._store._locator(self.transaction_id, name)
            path = self._store.path / locator
            with _registration_signals():
                # An existing empty path is unknown, never a reusable generation.
                os.mkdir(locator, mode=0o700, dir_fd=self._fd)
                child = os.open(locator, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self._fd)
                try:
                    retention.private(os.fstat(child))
                    allocation = dict(_identity(child, path), locator=locator, name=name)
                    _require(allocation['mount'] == state['root_identity']['mount'], 'allocation is mounted')
                    os.fsync(child)
                    os.fsync(self._fd)
                    updated = copy.deepcopy(state)
                    updated['slot']['allocations'].append(allocation)
                    updated['slot']['state'] = 'producing'
                    try:
                        self._store._save(self._fd, updated)
                    except BaseException:
                        # replace/fsync can fail after durable registration. Read
                        # back before deciding whether this exact empty child is
                        # still ours to undo; uncertainty preserves it.
                        current = self._store._read(self._fd)
                        if current == updated:
                            self._state = updated
                        elif current == state:
                            self._store._root(self._fd, state)
                            _check(child, {key: allocation[key] for key in _IDENTITY}, path, private=True)
                            _require(not os.listdir(child), 'unregistered allocation gained contents')
                            info = os.stat(locator, dir_fd=self._fd, follow_symlinks=False)
                            _require((info.st_dev, info.st_ino) == (allocation['device'], allocation['inode']),
                                     'unregistered allocation was replaced')
                            os.rmdir(locator, dir_fd=self._fd)
                            os.fsync(self._fd)
                        raise
                    self._state = updated
                finally:
                    os.close(child)
            return path

    def environment(self, base=None):
        result = dict(os.environ if base is None else base)
        scratch = str(self.allocate('scratch'))
        result.update(TMPDIR=scratch, TMP=scratch, TEMP=scratch)
        return result

    def verifying(self):
        with self._store._store.locked(self._fd, 'gate.lock'):
            state = self._current()
            updated = copy.deepcopy(state)
            updated['slot']['state'] = 'verifying'
            self._store._save(self._fd, updated)
            self._state = updated
