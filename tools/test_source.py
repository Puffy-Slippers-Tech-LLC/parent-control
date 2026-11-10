"""Checkout leases and durable source fences, independent of repair policy.

The historical paths are retained so an interrupted writer still has the same
identity after an upgrade. Queue ordering and validation of a finished repair
belong to callers; this module never owns cases, tickets or execution progress.
"""

from contextlib import contextmanager, ExitStack
import ctypes
import fcntl
import json
import os
from pathlib import Path
import stat
import threading
import time

VARIABLE = 'ONPC_TEST_SOURCE_FD'
WRITER = 'ONPC_TEST_SOURCE_WRITER'
IMPORTS = 'ONPC_TEST_SOURCE_IMPORT_FD'
STARTUP_READER = 'ONPC_REPAIR_STARTUP_FD'
STARTUP_WRITER = 'ONPC_REPAIR_WRITER_FD'
IMPACT_MAX_BYTES = 4 * 1024 * 1024
_local = threading.local()
_generations = {}


class RestartExecution(Exception):
    """Control-only imports must unwind their owners before fresh execution."""


class SourceBusy(ValueError):
    """A live source owner prevents immediate reader admission."""


def restart_execution():
    raise RestartExecution()


def source_directory(root, *, uid=None):
    from test_storage import directory, _directory
    uid = os.geteuid() if uid is None else uid
    if uid != os.geteuid() and os.geteuid() != 0:
        raise ValueError('source state requires its authenticated caller')
    state = (directory('state', root=root) if uid == os.geteuid() else
             _directory('state', root=root, create=False, owner='host', uid=uid))
    path = state / 'fix-tests-source'
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError('source state path contains a symlink')
    if uid == os.geteuid():
        path.mkdir(mode=0o700, exist_ok=True)
    info = path.stat()
    if info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('source state directory must be caller-owned and private')
    return path


@contextmanager
def _lock(path, *, uid=None):
    uid = os.geteuid() if uid is None else uid
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
                 | (os.O_CREAT if uid == os.geteuid() else 0), 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise ValueError('unsafe checkout source lock')
        yield fd
    finally:
        os.close(fd)


def _read(path, default=None, *, uid=None, max_bytes=65536):
    uid = os.geteuid() if uid is None else uid
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return default
    with os.fdopen(fd, encoding='utf-8') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid
                or info.st_nlink != 1 or info.st_size > max_bytes):
            raise ValueError('unsafe checkout source metadata')
        return json.load(stream)


def _sync(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write(path, value, *, max_bytes=65536):
    """Commit the fence before permitting any source modification."""
    encoded = json.dumps(value)
    if len(encoded.encode('utf-8')) > max_bytes:
        raise ValueError('oversized checkout source metadata')
    temporary = path.with_suffix('.tmp')
    _read(path, max_bytes=max_bytes)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_nlink != 1):
            raise ValueError('unsafe checkout source metadata')
        stream.truncate(0)
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    _sync(path.parent)


class SourceProtection:
    def __init__(self, directory, *, uid=None):
        self.directory = directory
        self.uid = os.geteuid() if uid is None else uid

    @contextmanager
    def state(self):
        with _lock(self.directory / 'repair-queue-gate', uid=self.uid) as gate:
            fcntl.flock(gate, fcntl.LOCK_EX)
            yield

    def owner(self):
        value = _read(self.directory / 'repair-source-pending.json', uid=self.uid)
        if value is None:
            return None
        if (not isinstance(value, dict) or set(value) != {'run'}
                or not isinstance(value['run'], str) or not Path(value['run']).is_absolute()):
            raise ValueError('invalid checkout source owner')
        return value['run']

    def _impact_records(self):
        value = _read(self.directory / 'repair-impact-holds.json', {}, uid=self.uid,
                      max_bytes=IMPACT_MAX_BYTES)
        if (not isinstance(value, dict)
                or any(not isinstance(ticket, str) or not Path(ticket).is_absolute()
                       or not isinstance(record, dict)
                       or set(record) != {'hold', 'generation'}
                       or record['hold'] not in ('untriaged', 'yes', 'unsure', None)
                       or type(record['generation']) is not int or record['generation'] < 0
                       for ticket, record in value.items())):
            raise ValueError('invalid checkout impact holds')
        return value

    def impact_holds(self):
        """Return effective holds; another writer invalidates an inactive hold."""
        generation = self.generation()
        return {ticket: record['hold'] or 'unsure'
                for ticket, record in self._impact_records().items()
                if record['hold'] is not None or record['generation'] != generation}

    def set_impact(self, ticket, decision):
        """Change only this ticket's normal admission hold under state()."""
        if (not isinstance(ticket, str) or not Path(ticket).is_absolute()
                or decision not in ('untriaged', 'yes', 'unsure', 'no')):
            raise ValueError('invalid checkout impact decision')
        records = self._impact_records()
        records[ticket] = {'hold': None if decision == 'no' else decision,
                           'generation': self.generation()}
        _write(self.directory / 'repair-impact-holds.json', records, max_bytes=IMPACT_MAX_BYTES)

    def release_impact(self, ticket):
        """Release a settled ticket without changing any other hold under state()."""
        if not isinstance(ticket, str) or not Path(ticket).is_absolute():
            raise ValueError('invalid checkout impact ticket')
        records = self._impact_records()
        records.pop(ticket, None)
        _write(self.directory / 'repair-impact-holds.json', records, max_bytes=IMPACT_MAX_BYTES)

    def generation(self):
        value = _read(self.directory / 'repair-generation.json', 0, uid=self.uid)
        if type(value) is not int or value < 0:
            raise ValueError('invalid checkout source generation')
        return value

    def check_generation(self, *, fresh=False):
        """Check imported code while its source lease is held.

        Only interpreter replacement may borrow newer bytes with ``fresh``;
        that does not make this interpreter's previous imports current.
        """
        generation = self.generation()
        previous = _generations.setdefault(self.directory, generation)
        if previous != generation and not fresh:
            from launcher_reload import ReloadRequested, current, request
            if current is None:
                raise ValueError('checkout source changed after startup; restart this command before continuing')
            request(current.run)
            raise ReloadRequested()

    def validate(self, descriptor, *, held=False, writer=False):
        actual = os.fstat(descriptor)
        expected = (self.directory / 'repair-owner').stat(follow_symlinks=False)
        if ((actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino)
                or not stat.S_ISREG(actual.st_mode) or actual.st_uid != self.uid
                or actual.st_nlink != 1 or stat.S_IMODE(actual.st_mode) != 0o600):
            raise ValueError('inherited source lease identity changed')
        if held:
            # Linux reports flock ownership for this exact open description,
            # including inherited descriptors. A matching inode alone is not a
            # lease, and probing with flock would downgrade a retained writer.
            locks = Path('/proc/self/fdinfo', str(descriptor)).read_text().splitlines()
            modes = [parts[4] for line in locks if line.startswith('lock:')
                     for parts in [line.split()] if len(parts) >= 5
                     and parts[2:4] == ['FLOCK', 'ADVISORY']]
            if ('WRITE' if writer else 'READ') not in modes and not (not writer and 'WRITE' in modes):
                raise ValueError('inherited source descriptor has no held lease')
            return 'writer' if 'WRITE' in modes else 'reader'

    def admit(self, descriptor, *, owner=None, resumed=None, prepare=None,
              impact_ticket=None, ready=None):
        """Try a lease under state(); publish writer recovery only after admission.

        ``ready`` checks the caller's finite-work boundary while its coordinator
        lock and this gate are held. Failure publishes no writer intent. Only a
        named pending ticket's read-only triage may bypass impact holds; source
        writers and retained unverified edits still fence that reader.
        """
        self.validate(descriptor)
        if impact_ticket is not None and (owner is not None
                or not isinstance(impact_ticket, str)
                or impact_ticket not in self._impact_records()):
            raise ValueError('impact triage requires a held ticket and a reader lease')
        if ready is not None and not ready():
            return False
        if owner is None and impact_ticket is None and self.impact_holds():
            return False
        try:
            fcntl.flock(descriptor, (fcntl.LOCK_EX if owner else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        try:
            pending = self.owner()
            if pending is not None and (owner is None or pending != owner and resumed != {'run': pending}):
                raise ValueError('another unfinished repair retains unverified checkout edits; resume that repair first '
                                 'or use --reset to abandon saved progress and verify from scratch')
            if owner is not None:
                if prepare is not None:
                    prepare()
                _write(self.directory / 'repair-source-pending.json', {'run': owner})
            return True
        except BaseException:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            raise

    def finish(self, owner, *, changed=False, unfinished=False):
        """Release only the caller's validated outcome under state()."""
        pending = self.owner()
        if pending is not None and pending != owner:
            raise ValueError('checkout repair ownership changed before release')
        if changed:
            if pending != owner:
                raise ValueError('checkout source change has no retained writer')
            _write(self.directory / 'repair-generation.json', self.generation() + 1)
        if not unfinished:
            (self.directory / 'repair-source-pending.json').unlink(missing_ok=True)
            _sync(self.directory)

    def reset(self, remove):
        """Called only after authorized reset drained every checkout owner."""
        # Keep generations monotonic across independent runs and explicit reset.
        _write(self.directory / 'repair-generation.json', self.generation() + 1)
        remove(self.directory / 'repair-source-pending.json')
        remove(self.directory / 'repair-impact-holds.json')
        _sync(self.directory)


class RepairGate:
    """Own a worker's source lease; callers own repair order and admission policy."""
    def __init__(self, run, *, root=None, stopped=lambda: False):
        self.run = run
        self.root = root
        self.owner = str(run.resolve())
        self.protection = SourceProtection(source_directory(root))
        self.fd = None
        self.stopped = stopped
        inherited = os.environ.pop(STARTUP_WRITER, None)
        saved = ({'pid': os.getpid(), 'fds': [int(inherited)]} if inherited is not None
                 else _read(run / 'repair-lease.json'))
        if saved is not None:
            if (not isinstance(saved, dict) or set(saved) != {'pid', 'fds'}
                    or type(saved['pid']) is not int or saved['pid'] <= 0
                    or not isinstance(saved['fds'], list) or len(saved['fds']) != 1
                    or type(saved['fds'][0]) is not int or saved['fds'][0] < 0):
                raise ValueError('invalid retained repair lease')
            if saved['pid'] == os.getpid():
                fd, = saved['fds']
                with self.protection.state():
                    self.protection.validate(fd, held=True, writer=True)
                    if self.protection.owner() is None:
                        raise ValueError('inherited repair writer has no retained source owner')
                    if not self.protection.admit(fd, owner=self.owner, resumed=self._resumed()):
                        raise ValueError('inherited repair writer lost its source lease')
                os.set_inheritable(fd, False)
                self.fd = fd
                retain(fd, self.owner)

    def _resumed(self):
        return _read(self.run / 'repair-source-resume.json')

    def _check_stop(self):
        if self.stopped() or (self.run / 'cancel').exists():
            from detached_launcher import Stopped
            raise Stopped()
        import launcher_reload
        if launcher_reload.pending():
            getattr(self, 'on_reload', launcher_reload.check)()

    def _check_source(self, *, reloading=False):
        import launcher_reload
        try:
            self.protection.check_generation(fresh=reloading)
        except launcher_reload.ReloadRequested:
            # Let the controller save its continuation before replacing code.
            self._check_stop()
            raise

    def generation(self):
        return self.protection.generation()

    def try_acquire(self, *, reloading=False, ready=None):
        """Claim a drained source boundary without publishing waiting intent.

        A coordinator may hold its own lock while calling this method. ``ready``
        runs under the source gate, so it must not invert that lock order.
        """
        if self.fd is not None:
            return False
        with _lock(self.protection.directory / 'repair-owner') as opened:
            fd = os.dup(opened)
        try:
            with self.protection.state():
                if not self.protection.admit(fd, owner=self.owner,
                        resumed=self._resumed(), ready=ready):
                    return False
            self.fd = fd
            retain(fd, self.owner)
            self._check_source(reloading=reloading)
            return True
        finally:
            # An admitted writer survives exceptions until its owner detaches
            # or explicitly records the repair outcome.
            if self.fd is None:
                os.close(fd)

    def acquire(self, *, reloading=False, ready=None):
        """Wait for admission without fencing readers before the writer exists."""
        if self.fd is not None:
            return False
        while True:
            self._check_stop()
            if self.try_acquire(reloading=reloading, ready=ready):
                return True
            time.sleep(.1)

    @contextmanager
    def source(self, *, reloading=False):
        """Protect finite work, borrowing this worker's writer when present."""
        if self.fd is None:
            import launcher_reload
            try:
                with reader(self.root, stopped=self._check_stop, fresh=reloading) as source:
                    yield source
            except launcher_reload.ReloadRequested:
                self._check_stop()
                raise
            return
        with self.protection.state():
            self.protection.validate(self.fd, held=True, writer=True)
            if self.protection.owner() != self.owner:
                raise ValueError('inherited source writer ownership changed')
        self._check_source(reloading=reloading)
        lease = retain(self.fd, self.owner)
        try:
            yield None
        finally:
            _local.leases = [item for item in _local.leases if item is not lease]

    @contextmanager
    def reload_source(self, *, root=None):
        """Retain the same source identity while replacing the interpreter."""
        with self.source(reloading=True) as source:
            yield self.fd if self.fd is not None else source

    def release(self, *, changed=False, unfinished=False):
        if self.fd is not None:
            with self.protection.state():
                self.protection.validate(self.fd, held=True, writer=True)
                self.protection.finish(self.owner, changed=changed, unfinished=unfinished)
            (self.run / 'repair-lease.json').unlink(missing_ok=True)
            self.detach()

    def detach(self):
        """Drop this process's descriptor while preserving any durable fence."""
        if self.fd is not None:
            forget(self.fd)
            os.close(self.fd)
            self.fd = None


@contextmanager
def borrowed(root, environment):
    """Borrow a validated writer on this thread without changing process aliases."""
    protection = SourceProtection(source_directory(root))
    try:
        descriptor = int(environment[VARIABLE])
        owner = environment[WRITER]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('bounded repair requires its owning source writer') from error
    with protection.state():
        protection.validate(descriptor, held=True, writer=True)
        if not isinstance(owner, str) or protection.owner() != owner:
            raise ValueError('borrowed source writer ownership changed')
    previous = getattr(_local, 'leases', [])
    _local.leases = [*previous, (descriptor, owner)]
    try:
        yield
    finally:
        _local.leases = previous


def descriptors():
    # A child must not inherit another worker thread's reader: that hidden
    # lease could prevent the child from ever acquiring its own repair writer.
    leases = getattr(_local, 'leases', [])
    if leases:
        return tuple(dict.fromkeys(descriptor for descriptor, _ in leases))
    inherited = os.environ.get(VARIABLE)
    return (int(inherited),) if inherited is not None else ()


def environment():
    leases = getattr(_local, 'leases', [])
    if leases:
        descriptor, owner = leases[-1]
        return {VARIABLE: str(descriptor), **({WRITER: owner} if owner else {})}
    return {key: os.environ[key] for key in (VARIABLE, WRITER) if key in os.environ}


def retain(descriptor, owner=None):
    """Register an owned writer or startup reader for nested commands."""
    if not hasattr(_local, 'leases'):
        _local.leases = []
    lease = (descriptor, owner)
    _local.leases.append(lease)
    return lease


def forget(descriptor):
    _local.leases = [lease for lease in getattr(_local, 'leases', []) if lease[0] != descriptor]
    if os.environ.get(VARIABLE) == str(descriptor):
        os.environ.pop(VARIABLE, None)
        os.environ.pop(WRITER, None)


def finish_imports(root=None, *, keep=(), directories=()):
    """Release verified bootstrap leases and every alias of a closed FD.

    A repair may have adopted the same FD as its retained writer. Its owner,
    rather than startup cleanup, remains responsible for that descriptor.
    """
    paths = (*((source_directory(root),) if root is not None else ()), *directories)
    inherited = {int(os.environ[name]) for name in (IMPORTS, STARTUP_READER) if name in os.environ}
    for fd in inherited:
        actual = os.fstat(fd)
        matching = None
        for path in paths:
            try:
                expected = (path / 'repair-owner').stat(follow_symlinks=False)
            except FileNotFoundError:
                continue
            if (actual.st_dev, actual.st_ino) == (expected.st_dev, expected.st_ino):
                matching = path
                break
        if matching is None:
            raise ValueError('inherited source lease identity changed')
        SourceProtection(matching).validate(fd, held=True)
        for name in (IMPORTS, STARTUP_READER):
            if os.environ.get(name) == str(fd):
                os.environ.pop(name)
        if fd not in keep:
            forget(fd)
            os.close(fd)


@contextmanager
def reader(root, *, stopped=lambda: False, fresh=False, wait=True, impact_ticket=None):
    """Protect finite work; only a held ticket grants read-only impact triage."""
    inherited = environment()
    uid = os.geteuid()
    if uid == 0 and VARIABLE in inherited:
        uid = os.fstat(int(inherited[VARIABLE])).st_uid
        if uid != 0 and uid != int(os.environ.get('PKEXEC_UID', '0')):
            raise ValueError('source lease does not belong to the authenticated caller')
    protection = SourceProtection(source_directory(root, **({'uid': uid} if uid != os.geteuid() else {})), uid=uid)
    if VARIABLE in inherited:
        if impact_ticket is not None:
            with protection.state():
                if (not isinstance(impact_ticket, str)
                        or impact_ticket not in protection._impact_records()):
                    raise ValueError('impact triage requires a held ticket and a reader lease')
        fd = int(inherited[VARIABLE])
        owner = inherited.get(WRITER)
        mode = protection.validate(fd, held=True, writer=owner is not None)
        if impact_ticket is not None and mode == 'writer':
            raise SourceBusy('checkout source is busy; impact triage cannot borrow a writer')
        if owner is not None and protection.owner() != owner:
            raise ValueError('inherited source writer ownership changed')
        protection.check_generation(fresh=fresh)
        lease = retain(fd, owner)
        try:
            yield fd
        finally:
            # Restore the enclosing registration, including nested same-FD use.
            _local.leases = [item for item in _local.leases if item is not lease]
        return
    with _lock(protection.directory / 'repair-owner') as fd:
        while True:
            if stopped():
                from detached_launcher import Stopped
                raise Stopped()
            with protection.state():
                if protection.admit(fd, impact_ticket=impact_ticket):
                    protection.check_generation(fresh=fresh)
                    break
            if not wait:
                raise SourceBusy('checkout source is busy; retry after its current owner finishes')
            time.sleep(.1)
        retain(fd)
        try:
            yield fd
        finally:
            forget(fd)


def protected(function):
    """Keep one finite source-consuming operation and its cleanup admitted."""
    from functools import wraps
    @wraps(function)
    def call(root, *args, **kwargs):
        with reader(root):
            return function(root, *args, **kwargs)
    return call


@contextmanager
def startup(root, argv, *, repair=False, wait=True, fresh=False):
    """Control/recovery stays available while fresh execution imports fence."""
    controls = ('--help', '-h', '--list', '--stop', '--reset', '--reload')
    if any(flag in argv for flag in controls):
        yield
        return
    # Existing repair supervisors used separate startup descriptor names.
    inherited = os.environ.get(STARTUP_READER) or os.environ.get(STARTUP_WRITER)
    previous = {key: os.environ.get(key) for key in (VARIABLE, WRITER)}
    try:
        if inherited is not None and VARIABLE not in os.environ:
            os.environ[VARIABLE] = inherited
            owner = SourceProtection(source_directory(root)).owner()
            if owner is not None:
                os.environ[WRITER] = owner
            elif STARTUP_WRITER in os.environ:
                raise ValueError('inherited repair writer has no retained source owner')
        if repair and '--resume' in argv and VARIABLE not in environment():
            protection = SourceProtection(source_directory(root))
            # Bootstrap only borrows existing bytes. Recheck the owner each
            # time the lease is attempted, and never publish a writer fence:
            # the previous writer may finish while this process waits.
            with _lock(protection.directory / 'repair-owner') as fd:
                while True:
                    with protection.state():
                        owner = protection.owner()
                        try:
                            fcntl.flock(fd, (fcntl.LOCK_EX if owner else fcntl.LOCK_SH) | fcntl.LOCK_NB)
                        except BlockingIOError:
                            pass
                        else:
                            break
                    if not wait:
                        raise ValueError('checkout source is busy; retry after its current owner finishes')
                    time.sleep(.1)
                protection.check_generation(fresh=fresh)
                retain(fd, owner)
                try:
                    yield
                finally:
                    forget(fd)
            return
        with reader(root, wait=wait, fresh=fresh):
            yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@contextmanager
def admission(root, argv, *, repair=False, wait=True):
    """Keep public controller imports/admission finite, with an explicit handoff."""
    previous = getattr(_local, 'admission', None)
    if previous is not None:
        yield
        return
    with ExitStack() as context:
        _local.admission = (root, context)
        try:
            context.enter_context(startup(root, argv, repair=repair, wait=wait))
            yield
        finally:
            _local.admission = previous


def finish_admission():
    """Release before controller/resource waits or observation, never a writer."""
    admitted = getattr(_local, 'admission', None)
    if admitted is not None:
        root, context = admitted
        context.close()
        _local.admission = None
        if IMPORTS in os.environ or STARTUP_READER in os.environ:
            keep = tuple(fd for fd, owner in getattr(_local, 'leases', []) if owner is not None)
            finish_imports(root, keep=keep)


def leave_checkout():
    """A destination checkout must obtain its own source identity."""
    finish_admission()
    for descriptor in descriptors():
        os.set_inheritable(descriptor, False)
    for name in (VARIABLE, WRITER, IMPORTS, STARTUP_READER, STARTUP_WRITER):
        os.environ.pop(name, None)


@contextmanager
def _borrow_process(root, uid, pid):
    """Duplicate a proven caller lease, retaining its exact open description.

    The privileged entry point supplies its kernel-derived parent and pkexec's
    authenticated UID. Pinning the pidfd and /proc directory prevents PID reuse
    from turning a dead caller into another process's authority.
    """
    protection = SourceProtection(source_directory(root, uid=uid), uid=uid)
    expected = (protection.directory / 'repair-owner').stat(follow_symlinks=False)
    libc = ctypes.CDLL(None, use_errno=True)
    duplicate = getattr(libc, 'pidfd_getfd', None)
    if duplicate is None or not hasattr(os, 'pidfd_open'):
        raise ValueError('source lease: this host lacks the required pidfd_getfd API; preparation refused')
    duplicate.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_uint)
    duplicate.restype = ctypes.c_int
    fd = None
    with ExitStack() as resources:
        process = os.pidfd_open(pid)
        resources.callback(os.close, process)
        proc = os.open('/proc/' + str(pid), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        resources.callback(os.close, proc)
        def authenticate():
            status = os.open('status', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=proc)
            with os.fdopen(status) as stream:
                identities = next((line.split()[1:] for line in stream if line.startswith('Uid:')), [])
            if identities != [str(uid)] * 4:
                raise ValueError('source lease: preparation parent is not the authenticated caller')
        authenticate()
        parent_fds = os.open('fd', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=proc)
        resources.callback(os.close, parent_fds)
        names = os.listdir(parent_fds)
        if len(names) > 4096:
            raise ValueError('source lease: preparation parent has too many descriptors')
        for name in names:
            if not name.isdecimal():
                continue
            try:
                actual = os.stat(name, dir_fd=parent_fds)
            except FileNotFoundError:
                continue
            if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
                continue
            fd = duplicate(process, int(name), 0)
            if fd < 0:
                raise ValueError('source lease: cannot duplicate the authenticated parent lease: '
                                 + os.strerror(ctypes.get_errno()) + '; preparation refused')
            resources.callback(os.close, fd)
            authenticate()
            with protection.state():
                mode = protection.validate(fd, held=True)
                owner = protection.owner()
                if (mode == 'writer') != (owner is not None):
                    raise ValueError('source lease: held mode and retained writer ownership disagree')
                protection.check_generation()
            break
        else:
            raise ValueError('source lease: authenticated preparation parent has no held source lease')
        lease = retain(fd, owner)
        try:
            yield
        finally:
            _local.leases = [item for item in _local.leases if item is not lease]


@contextmanager
def privileged(root, uid):
    """Only authenticated fixed dispatchers may borrow their caller's source."""
    if os.geteuid() != 0 or type(uid) is not int or uid <= 0:
        raise ValueError('source lease: authenticated privileged preparation required')
    parent = os.getppid()
    with ExitStack() as lease:
        try:
            lease.enter_context(_borrow_process(root, uid, parent))
        except OSError as error:
            raise ValueError('source lease: cannot authenticate the preparation parent: '
                             + str(error) + '; preparation refused') from error
        if os.getppid() != parent:
            raise ValueError('source lease: preparation parent exited before admission')
        yield
