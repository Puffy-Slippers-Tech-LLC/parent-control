"""Disk-backed test storage. Paths are fixed by the trusted checkout, not TMPDIR.

Allocation identities and deletion belong to test_retention. This module
validates storage and manages scratch leases, reclaiming only recorded identities.
"""
import ctypes
import os
from pathlib import Path
import stat
import fcntl
import json
import atexit
import uuid
import errno
from contextlib import contextmanager
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/test-runs'
_scratch = None
_scratch_fd = None


def disk_backed(fd):
    # Linux statfs: f_type is the first native long; reserve enough space for
    # the complete structure without depending on libc's architecture layout.
    buffer = ctypes.create_string_buffer(256)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.fstatfs(fd, ctypes.byref(buffer)):
        raise OSError(ctypes.get_errno(), 'storage filesystem inspection failed')
    if ctypes.c_long.from_buffer(buffer).value in (0x01021994, 0x858458f6):
        raise ValueError('test storage must be disk-backed; tmpfs/ramfs refused')


def directory(kind='allocations', *, root=None):
    base = (Path(root) if root is not None else ROOT) / 'output/test-runs'
    if kind not in ('allocations', 'scratch', 'sessions', 'sessions-host', 'fix-tests', 'write-e2e',
                    'reports', 'state', 'exports', 'cache', 'sbuild'):
        raise ValueError('invalid test storage kind')
    # Shared ancestors are traversable; payload roots stay owner-private.
    owner = 'privileged' if os.geteuid() == 0 else 'host'
    path = base / owner / kind
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        candidate = Path('/')
        for part in path.parts[1:]:
            candidate = candidate / part
            mode = (0o755 if candidate in (base.parent, base, base / owner)
                    else 0o711 if candidate == path and kind == 'sbuild' else 0o700)
            try:
                os.mkdir(part, mode=mode, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != (0o711 if kind == 'sbuild' else 0o700):
            raise ValueError('unsafe test storage ownership or mode')
        disk_backed(fd)
    finally:
        os.close(fd)
    return path


def contains(path):
    path = Path(path)
    return path.is_absolute() and '..' not in path.parts and path.is_relative_to(BASE)


def allocation_parent():
    return directory()


def named_input():
    # Privileged qualifiers consume the caller's already frozen host bundle.
    return BASE / 'host/allocations/onpc-parent-setup-input'


def privileged_state(uid):
    if type(uid) is not int or uid <= 0 or os.geteuid() != 0:
        raise ValueError('privileged storage requires an authenticated caller')
    return directory('state') / f'retention-{uid}'


def runtime_allocation(factory, *, prefix='onpc-runtime-'):
    """Short AF_UNIX runtime only; callers own prompt identity-based cleanup.

    Bulk payloads and retained evidence must use disk storage instead. This is
    the single location policy for socket fixtures that cannot fit below ROOT.
    """
    if __package__:
        from .test_retention import allocate
    else:
        from test_retention import allocate
    return allocate(factory, prefix=prefix, dir='/tmp', runtime=True)


@contextmanager
def runtime_directory(*, prefix='onpc-runtime-'):
    """Scoped short socket runtime, removed by its exact allocation identity."""
    if __package__:
        from .test_retention import remove
    else:
        from test_retention import remove
    path = Path(runtime_allocation(tempfile.mkdtemp, prefix=prefix))
    info = path.stat()
    record = dict(path=str(path), device=info.st_dev, inode=info.st_ino, mode=0o700)
    try:
        yield path
    finally:
        remove(record)


def initialize_scratch(parent, fd, retention):
    """Publish a complete scratch owner from an identity-recorded staging slot.

    No payload is written until the staging identity is durably recorded. An
    interruption before that receipt can leave only an empty slot, which can be
    initialized without deleting or adopting any unrecorded contents.
    """
    staging = parent / 'initializing'
    try:
        receipt = os.open('initializing.json', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
    except FileNotFoundError:
        pass
    else:
        with os.fdopen(receipt) as stream:
            retention.private(os.fstat(stream.fileno()), regular=True)
            record = json.load(stream)
        if record['path'] != str(staging):
            raise ValueError('scratch staging identity path changed')
        retention.remove(record)
        os.unlink('initializing.json', dir_fd=fd)
        os.fsync(fd)
    try:
        os.mkdir('initializing', mode=0o700, dir_fd=fd)
    except FileExistsError:
        pass
    child = retention.directory(staging)
    try:
        info = os.fstat(child)
        retention.private(info)
        if retention.mount_id(child) != retention.mount_id(fd) or os.listdir(child):
            raise ValueError('scratch staging has unrecorded contents or a mount')
        record = dict(path=str(staging), device=info.st_dev, inode=info.st_ino, mode=0o700)
        retention.Store(parent).save(fd, record, name='initializing.json')
        path = parent / ('run-' + uuid.uuid4().hex)
        owner = os.open('owner', os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=child)
        try:
            fcntl.flock(owner, fcntl.LOCK_EX)
            receipt = os.open('identity.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                              0o600, dir_fd=child)
            with os.fdopen(receipt, 'w') as stream:
                json.dump(dict(record, path=str(path)), stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.mkdir('tmp', mode=0o700, dir_fd=child)
            os.fsync(child)
            os.rename('initializing', path.name, src_dir_fd=fd, dst_dir_fd=fd)
            os.fsync(fd)
            os.unlink('initializing.json', dir_fd=fd)
            os.fsync(fd)
            return path / 'tmp', owner
        except BaseException:
            os.close(owner)
            raise
    finally:
        os.close(child)


def reclaim_scratch(parent, fd, retention, record=None):
    # Keep the identity outside the tree being removed. A crash after deleting
    # its owner/receipt files must still leave enough proof to finish cleanup.
    if record is None:
        try:
            receipt = os.open('reclaiming.json', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        except FileNotFoundError:
            return
        with os.fdopen(receipt) as stream:
            retention.private(os.fstat(stream.fileno()), regular=True)
            record = json.load(stream)
        path = Path(record['path'])
        if path.parent != parent or not path.name.startswith('run-'):
            raise ValueError('scratch reclamation identity path changed')
    else:
        retention.Store(parent).save(fd, record, name='reclaiming.json')
    retention.remove(record)
    os.unlink('reclaiming.json', dir_fd=fd)
    os.fsync(fd)


def scratch_directory():
    """Process-owned disk scratch, also reclaimed after an abrupt owner exit.

    The locked owner descriptor is inherited by children. Receipts record the
    allocation identity before it is handed out. Unknown/replaced entries refuse.
    """
    global _scratch, _scratch_fd
    if _scratch is not None:
        return _scratch
    if __package__:
        from . import test_retention as retention
    else:
        import test_retention as retention
    parent = directory('scratch')
    with retention.Store(parent).opened() as fd, retention.Store(parent).locked(fd, 'gate'):
        if _scratch is not None:
            return _scratch
        reclaim_scratch(parent, fd, retention)
        for name in os.listdir(fd):
            if name in ('gate', 'initializing', 'initializing.json', 'current.tmp'):
                continue
            child = retention.directory(parent / name)
            try:
                retention.private(os.fstat(child))
                owner = os.open('owner', os.O_RDWR | os.O_NOFOLLOW, dir_fd=child)
                try:
                    retention.private(os.fstat(owner), regular=True)
                    try:
                        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        continue
                    receipt = os.open('identity.json', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=child)
                    with os.fdopen(receipt) as stream:
                        retention.private(os.fstat(stream.fileno()), regular=True)
                        record = json.load(stream)
                    if record['path'] != str(parent / name):
                        raise ValueError('scratch identity path changed')
                    reclaim_scratch(parent, fd, retention, record)
                finally:
                    os.close(owner)
            finally:
                os.close(child)
        _scratch, _scratch_fd = initialize_scratch(parent, fd, retention)
        # Descendants are launched with scratch_descriptors(), so an abruptly
        # terminated coordinator cannot make a still-running child's tree idle.
        atexit.register(os.close, _scratch_fd)
        return _scratch


def scratch_descriptors():
    # A fresh Python child has no module globals for its inherited leases.
    # Forward only its already-open private scratch owner descriptors, including
    # leases created through either import spelling of this module. No pathname
    # is opened to acquire another process's ownership.
    parent = ROOT / 'output/test-runs' / ('privileged' if os.geteuid() == 0 else 'host') / 'scratch'
    descriptors = set(() if _scratch_fd is None else (_scratch_fd,))
    for name in os.listdir('/proc/self/fd'):
        descriptor = int(name)
        try:
            path = Path(os.readlink(f'/proc/self/fd/{descriptor}'))
            if (path.name != 'owner' or path.parent.parent != parent
                    or not path.parent.name.startswith('run-')):
                continue
            info = os.fstat(descriptor)
            if (stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
                    and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1):
                descriptors.add(descriptor)
        except OSError as error:
            if error.errno not in (errno.ENOENT, errno.EBADF):
                raise
            # listdir's own fd or a concurrent worker's descriptor has closed.
    return tuple(sorted(descriptors))
