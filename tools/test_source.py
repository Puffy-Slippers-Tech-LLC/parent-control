"""Finite checkout source leases for imports, transfers and guarded synchronization."""

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
MAX_RECORD_BYTES = 4 * 1024 * 1024
_local = threading.local()


class RestartExecution(Exception):
    """Control-only imports must unwind their owners before fresh execution."""


class SourceBusy(ValueError):
    """A source owner prevents immediate reader admission."""


def restart_execution():
    raise RestartExecution()


def source_directory(root, *, uid=None):
    from test_storage import directory, _directory
    uid = os.geteuid() if uid is None else uid
    if uid != os.geteuid() and os.geteuid() != 0:
        raise ValueError('source state requires its authenticated caller')
    state = (directory('state', root=root) if uid == os.geteuid() else
             _directory('state', root=root, create=False, owner='host', uid=uid))
    path = state / 'source-leases'
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



class SourceProtection:
    def __init__(self, directory, *, uid=None):
        self.directory = directory
        self.uid = os.geteuid() if uid is None else uid

    @contextmanager
    def state(self):
        with _lock(self.directory / 'state.lock', uid=self.uid) as gate:
            fcntl.flock(gate, fcntl.LOCK_EX)
            yield

    def validate(self, descriptor, *, held=False, writer=False):
        actual = os.fstat(descriptor)
        expected = (self.directory / 'source.lock').stat(follow_symlinks=False)
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

    def admit(self, descriptor):
        self.validate(descriptor)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True


def descriptors():
    leases = getattr(_local, 'leases', [])
    if leases:
        return tuple(dict.fromkeys(descriptor for descriptor, _ in leases))
    inherited = os.environ.get(VARIABLE)
    return (int(inherited),) if inherited is not None else ()


def environment():
    leases = getattr(_local, 'leases', [])
    if leases:
        return {VARIABLE: str(leases[-1][0])}
    return {VARIABLE: os.environ[VARIABLE]} if VARIABLE in os.environ else {}


def retain(descriptor):
    if not hasattr(_local, 'leases'):
        _local.leases = []
    lease = (descriptor, None)
    _local.leases.append(lease)
    return lease


def forget(descriptor):
    _local.leases = [lease for lease in getattr(_local, 'leases', []) if lease[0] != descriptor]
    if os.environ.get(VARIABLE) == str(descriptor):
        os.environ.pop(VARIABLE, None)
        os.environ.pop(WRITER, None)


def finish_imports(root=None, *, keep=(), directories=()):
    paths = (*((source_directory(root),) if root is not None else ()), *directories)
    inherited = {int(os.environ[name]) for name in (IMPORTS, STARTUP_READER) if name in os.environ}
    for fd in inherited:
        actual = os.fstat(fd)
        matching = None
        for path in paths:
            try:
                expected = (path / 'source.lock').stat(follow_symlinks=False)
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
def reader(root, *, stopped=lambda: False, wait=True):
    inherited = environment()
    uid = os.geteuid()
    if uid == 0 and VARIABLE in inherited:
        uid = os.fstat(int(inherited[VARIABLE])).st_uid
        if uid != 0 and uid != int(os.environ.get('PKEXEC_UID', '0')):
            raise ValueError('source lease does not belong to the authenticated caller')
    protection = SourceProtection(source_directory(root, **({'uid': uid} if uid != os.geteuid() else {})), uid=uid)
    if VARIABLE in inherited:
        fd = int(inherited[VARIABLE])
        protection.validate(fd, held=True)
        lease = retain(fd)
        try:
            yield fd
        finally:
            _local.leases = [item for item in _local.leases if item is not lease]
        return
    with _lock(protection.directory / 'source.lock', uid=uid) as fd:
        while not protection.admit(fd):
            if stopped():
                from detached_launcher import Stopped
                raise Stopped()
            if not wait:
                raise SourceBusy('checkout source is busy; retry after its current owner finishes')
            time.sleep(.1)
        retain(fd)
        try:
            yield fd
        finally:
            forget(fd)


def protected(function):
    from functools import wraps
    @wraps(function)
    def call(root, *args, **kwargs):
        with reader(root):
            return function(root, *args, **kwargs)
    return call


@contextmanager
def startup(root, argv, *, wait=True, stopped=lambda: False):
    controls = ('--help', '-h', '--list', '--stop', '--reset', '--reload')
    if any(flag in argv for flag in controls):
        yield
        return
    with reader(root, wait=wait, stopped=stopped):
        yield


@contextmanager
def admission(root, argv, *, wait=True, stopped=lambda: False):
    previous = getattr(_local, 'admission', None)
    if previous is not None:
        yield
        return
    with ExitStack() as context:
        _local.admission = (root, context)
        try:
            context.enter_context(startup(root, argv, wait=wait, stopped=stopped))
            yield
        finally:
            _local.admission = previous


def finish_admission():
    admitted = getattr(_local, 'admission', None)
    if admitted is not None:
        root, context = admitted
        context.close()
        _local.admission = None
        if IMPORTS in os.environ or STARTUP_READER in os.environ:
            finish_imports(root)


def leave_checkout():
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
    expected = (protection.directory / 'source.lock').stat(follow_symlinks=False)
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
            protection.validate(fd, held=True)
            break
        else:
            raise ValueError('source lease: authenticated preparation parent has no held source lease')
        lease = retain(fd)
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
