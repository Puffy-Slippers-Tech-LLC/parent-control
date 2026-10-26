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
import sys
from contextlib import contextmanager, ExitStack
import tempfile
import re

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


def directory(kind='allocations', *, root=None, create=True):
    if kind not in ('allocations', 'scratch', 'sessions', 'sessions-host', 'fix-tests', 'fix-tests-host', 'write-e2e', 'sync-whatsnew', 'plans',
                    'reports', 'state', 'exports', 'cache', 'sbuild', 'recordings', 'captures'):
        raise ValueError('invalid test storage kind')
    if kind == 'recordings':
        return recordings_directory(root=root, create=create)
    owner = 'privileged' if os.geteuid() == 0 else 'host'
    return _directory(kind, root=root, create=create, owner=owner, uid=os.geteuid())


def fixture_directory():
    """One host fixture authority, separate from disposable execution caches.

    Producers are caller-owned. Authenticated privileged read-only lookup is a
    later cache/session boundary; root must never build a second fixture cache.
    """
    if os.geteuid() == 0:
        raise ValueError('fixture production requires an unprivileged owner')
    return _directory('fixtures', root=None, create=True, owner='host', uid=os.geteuid())


def recordings_directory(*, root=None, caller_uid=None, create=True):
    """Recording owner root, or root's read-only authenticated caller lookup.

    The privileged dispatcher must authenticate caller_uid before passing it.
    This lookup never creates, adopts, or modifies the caller's directory.
    Recordings are owner-private directly below output/test-runs; root may
    inspect an authenticated caller's directory, but cannot create its own.
    """
    if caller_uid is None:
        if os.geteuid() == 0:
            raise ValueError('recordings require an unprivileged owner')
        if create:
            if __package__:
                from .recording_control import relocate_legacy
            else:
                from recording_control import relocate_legacy
            relocate_legacy(root)
        return _directory('recordings', root=root, create=create, owner=None, uid=os.geteuid())
    if os.geteuid() != 0 or type(caller_uid) is not int or caller_uid <= 0 or create:
        raise ValueError('recordings caller lookup requires root, a positive UID and create=False')
    return _directory('recordings', root=root, create=False, owner=None, uid=caller_uid)


def _directory(kind, *, root, create, owner, uid):
    # Shared ancestors are traversable; payload roots stay owner-private.
    base = (Path(root) if root is not None else ROOT) / 'output/test-runs'
    path = base / owner / kind if owner is not None else base / kind
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        candidate = Path('/')
        for part in path.parts[1:]:
            candidate = candidate / part
            mode = (0o755 if candidate in (base.parent, base, *((base / owner,) if owner is not None else ()))
                    else 0o711 if candidate == path and kind == 'sbuild' else 0o700)
            if create:
                try:
                    os.mkdir(part, mode=mode, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            if create and owner == 'host' and uid == os.geteuid() and uid > 0 and candidate == base.parent:
                try:
                    _prepare_output_ancestor(fd, part, child, uid)
                except BaseException:
                    os.close(child)
                    raise
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if info.st_uid != uid or stat.S_IMODE(info.st_mode) != (0o711 if kind == 'sbuild' else 0o700):
            raise ValueError('unsafe test storage ownership or mode')
        disk_backed(fd)
    finally:
        os.close(fd)
    return path


def _prepare_output_ancestor(parent, name, descriptor, uid):
    """Tighten only the caller's ordinary group-writable output directory.

    Old build output may predate private test storage. Reconcile this one shared
    ancestor through its pinned parent; never rewrite payloads or relax the
    authenticated input reader. Root and read-only allocation skip this route.
    """
    if __package__:
        from .test_retention import mount_id
    else:
        from test_retention import mount_id
    before = os.fstat(descriptor)
    mode = stat.S_IMODE(before.st_mode)
    if before.st_uid != uid or mode & 0o022 and not (
            mode == 0o775 and before.st_gid == os.getegid()):
        raise ValueError('unsafe test output ancestor ownership or mode')
    if mode != 0o775:
        return
    if mount_id(parent) != mount_id(descriptor):
        raise ValueError('mounted test output ancestor refused')
    identity = lambda info: (info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode),
                             info.st_uid, info.st_gid)
    current = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if identity(current) != identity(before) or stat.S_IMODE(current.st_mode) not in (0o755, 0o775):
        raise ValueError('test output ancestor replaced')
    # Another identical allocator may already have completed the same repair.
    if stat.S_IMODE(current.st_mode) == 0o775:
        os.fchmod(descriptor, 0o755)
        os.fsync(descriptor)
    after = os.fstat(descriptor)
    current = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if (identity(after) != identity(before) or identity(current) != identity(after)
            or stat.S_IMODE(after.st_mode) != 0o755 or stat.S_IMODE(current.st_mode) != 0o755):
        raise ValueError('test output ancestor changed during preparation')


def contains(path):
    path = Path(path)
    return path.is_absolute() and '..' not in path.parts and path.is_relative_to(BASE)


def allocation_parent():
    return directory()


def named_input(*, package_source=False, fixture_source=False, upgrade_source=False,
                vm_source=False):
    # Privileged qualifiers consume the caller's already frozen host bundle.
    # Every qualification must select current sources, including default callers.
    # package_source remains accepted for existing explicit callers.
    # Keep each source identity immutable under the normal allocation journal.
    if __package__:
        from . import package_inputs
    else:
        import package_inputs
    paths = package_inputs.paths(ROOT)
    if fixture_source or upgrade_source:
        paths = sorted(set(paths) | {Path(name) for name in (
            'tests/fixtures/build_test_applications.py', 'tests/fixtures/native_assets.py',
            'tests/fixtures/onpc_test_application.c', 'tests/fixtures/gui_application.py',
            'common/oh_no_parent_control_ui/gtk_automation.py')})
    identity = package_inputs.digest(ROOT, paths)
    prefix = ('onpc-upgrade-v1.2-' if upgrade_source else
              'onpc-native-fixtures-' if fixture_source else 'onpc-parent-setup-')
    # Platform binding is infrastructure policy, never an opt-in per scenario.
    # Retain vm_source for existing callers, including its required-VM guard.
    if __package__:
        from .vm_selection import selected
    else:
        from vm_selection import selected
    vm = selected(required=vm_source)
    if vm is not None:
        prefix += vm.name + '-'
    return named_input_slot(BASE / ('host/allocations/' + prefix + identity))


def named_input_slot(path):
    """Preserve empty reservations; select a fresh, independently registered slot.

    The execution activity lock serializes producers and consumers. Never adopt
    or delete an existing directory: even an empty one can be unregistered.
    Nonempty inputs still undergo the consumer's complete manifest/tree checks.
    """
    if __package__:
        from .test_retention import directory as open_directory
    else:
        from test_retention import directory as open_directory
    for generation in range(32):
        candidate = path if generation == 0 else path.with_name(path.name + f'-{generation}')
        try:
            fd = open_directory(candidate)
        except FileNotFoundError:
            return candidate
        try:
            if os.listdir(fd):
                return candidate
        finally:
            os.close(fd)
    raise ValueError('named input has too many empty reservations')


def _input_caller(caller_uid):
    """Authenticate an input reader; a supplied UID never grants authority."""
    uid = os.geteuid()
    if uid == 0:
        value = os.environ.get('PKEXEC_UID', '')
        if not value.isascii() or not value.isdecimal() or int(value) <= 0:
            raise ValueError('input: authenticated caller required')
        uid = int(value)
    if caller_uid is not None and (type(caller_uid) is not int or caller_uid != uid):
        raise ValueError('input: foreign caller')
    return uid


def _input_identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid,
            info.st_gid, None if stat.S_ISDIR(info.st_mode) else info.st_nlink)


@contextmanager
def authenticated_input(selection, *, caller_uid=None, root=ROOT):
    """Pin one execution's registered caller-owned input without writing it.

    The authenticated dispatcher supplies the caller identity. The live owner
    and shared writer lock protect this read from retention rotation; neither
    a path nor a serialized selection creates ownership. Bundle verification
    must use the yielded allocation descriptor, including child opens.
    """
    if __package__:
        from . import test_retention as retention
    else:
        import test_retention as retention
    uid = _input_caller(caller_uid)
    fields = {'schema', 'target', 'key', 'allocation', 'device', 'inode', 'journal',
              'journal_device', 'journal_inode', 'run', 'build_identity'}
    if (type(selection) is not dict or set(selection) != fields
            or selection['schema'] != 'onpc-execution-fixture-v1'
            or type(selection['target']) is not str or selection['target'] not in ('ubuntu', 'fedora')
            or any(type(selection[key]) is not str for key in ('journal', 'allocation'))
            or any(type(selection[key]) is not str or
                   re.fullmatch(r'[0-9a-f]{64}', selection[key]) is None
                   for key in ('key', 'build_identity'))
            or not retention.valid_token(selection['run'])
            or any(type(selection[key]) is not int or selection[key] <= 0
                   for key in ('device', 'inode', 'journal_device', 'journal_inode'))):
        raise ValueError('input: invalid selection')
    root = Path(root)
    base = root / 'output/test-runs/host'
    journal = Path(selection['journal'])
    allocation = Path(selection['allocation'])
    if (not root.is_absolute() or '..' in root.parts
            or journal.parent != base / 'state'
            or not retention.journal_path(str(journal))
            or allocation.parent != base / 'allocations'
            or re.fullmatch(r'onpc-[A-Za-z0-9_.-]+', allocation.name) is None):
        raise ValueError('input: unconfined selection')

    with ExitStack() as stack:
        witnesses = []
        def opened(name, flags, parent=None):
            fd = os.open(name, flags | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
            stack.callback(os.close, fd)
            return fd

        def chain(path):
            parent = opened('/', os.O_RDONLY | os.O_DIRECTORY)
            current = Path('/')
            for name in path.parts[1:]:
                current /= name
                child = opened(name, os.O_RDONLY | os.O_DIRECTORY, parent)
                info = os.fstat(child)
                if current.is_relative_to(root) and current != root:
                    if info.st_uid != uid or info.st_mode & 0o022:
                        raise ValueError('input: unsafe storage owner or mode')
                    if retention.mount_id(child) != retention.mount_id(parent):
                        raise ValueError('input: mounted storage')
                witnesses.append((parent, name, child, _input_identity(info), retention.mount_id(child)))
                parent = child
            return parent

        def private(fd, *, regular=False):
            info = os.fstat(fd)
            if (info.st_uid != uid or stat.S_IMODE(info.st_mode) != (0o600 if regular else 0o700)
                    or not (stat.S_ISREG(info.st_mode) if regular else stat.S_ISDIR(info.st_mode))
                    or regular and info.st_nlink != 1):
                raise ValueError('input: unsafe owner or mode')
            return info

        journal_fd = chain(journal)
        info = private(journal_fd)
        if (info.st_dev, info.st_ino) != (selection['journal_device'], selection['journal_inode']):
            raise ValueError('input: journal replaced')
        disk_backed(journal_fd)
        owner = opened('owner.lock', os.O_RDONLY | os.O_NONBLOCK, journal_fd)
        owner_info = private(owner, regular=True)
        writer = opened('writer.lock', os.O_RDONLY | os.O_NONBLOCK, journal_fd)
        writer_info = private(writer, regular=True)
        for descriptor in (owner, writer):
            if retention.mount_id(descriptor) != retention.mount_id(journal_fd):
                raise ValueError('input: mounted journal entry')

        def live_owner():
            try:
                fcntl.flock(owner, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            else:
                fcntl.flock(owner, fcntl.LOCK_UN)
                raise ValueError('input: execution owner is not active')

        live_owner()
        # Existing locks only: a privileged reader must not create caller files.
        fcntl.flock(writer, fcntl.LOCK_SH | fcntl.LOCK_NB)
        source = opened('current.json', os.O_RDONLY | os.O_NONBLOCK, journal_fd)
        before = private(source, regular=True)
        if retention.mount_id(source) != retention.mount_id(journal_fd):
            raise ValueError('input: mounted journal entry')
        if before.st_size > 8 * 1024 ** 2:
            raise ValueError('input: journal too large')
        with os.fdopen(os.dup(source), 'rb') as stream:
            raw = stream.read(8 * 1024 ** 2 + 1)
        after = os.fstat(source)
        if (len(raw) != before.st_size or _input_identity(before) != _input_identity(after)
                or (before.st_mtime_ns, before.st_ctime_ns) != (after.st_mtime_ns, after.st_ctime_ns)):
            raise ValueError('input: journal changed')
        def unique(pairs):
            result = {}
            for name, value in pairs:
                if name in result:
                    raise ValueError('input: duplicate journal field')
                result[name] = value
            return result
        try:
            state = retention.validate_state(json.loads(raw, object_pairs_hook=unique))
            records = {record['path']: record for _, record in
                       retention.latest_allocations([*state['history'], state])}
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise ValueError('input: invalid journal') from error
        if state['run'] != selection['run']:
            raise ValueError('input: execution run changed')
        expected = dict(path=str(allocation), device=selection['device'],
                        inode=selection['inode'], mode=0o700)
        if records.get(str(allocation)) != expected or expected not in state['paths']:
            raise ValueError('input: allocation is not registered to this owner')
        allocation_fd = chain(allocation)
        info = private(allocation_fd)
        if (info.st_dev, info.st_ino) != (selection['device'], selection['inode']):
            raise ValueError('input: allocation replaced')
        disk_backed(allocation_fd)

        def recheck():
            for parent, name, original, saved, mount in witnesses:
                current = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                  dir_fd=parent)
                try:
                    if (_input_identity(os.fstat(current)) != saved
                            or retention.mount_id(current) != mount
                            or retention.mount_id(original) != mount):
                        raise ValueError('input: path replaced or mounted')
                finally:
                    os.close(current)
            for name, saved in (('owner.lock', owner_info), ('writer.lock', writer_info),
                                ('current.json', before)):
                current = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW,
                                  dir_fd=journal_fd)
                try:
                    if (_input_identity(os.fstat(current)) != _input_identity(saved)
                            or retention.mount_id(current) != retention.mount_id(journal_fd)):
                        raise ValueError('input: journal entry replaced or mounted')
                finally:
                    os.close(current)
            current = os.fstat(source)
            if (current.st_size, current.st_mtime_ns, current.st_ctime_ns) != (
                    before.st_size, before.st_mtime_ns, before.st_ctime_ns):
                raise ValueError('input: journal changed')
            live_owner()

        recheck()
        try:
            yield allocation_fd
        finally:
            recheck()


def privileged_state(uid):
    if type(uid) is not int or uid <= 0 or os.geteuid() != 0:
        raise ValueError('privileged storage requires an authenticated caller')
    from vm_selection import selected
    vm = selected(required=False)
    legacy = directory('state') / f'retention-{uid}'
    if vm:
        legacy_retention_guard(legacy)
    return legacy.with_name(legacy.name + ('-' + vm.name if vm else ''))


def legacy_retention_guard(path):
    """Preserve old journals and refuse to forget an unfinished or live owner."""
    if not path.exists():
        return
    if __package__:
        from .test_retention import Store, private
    else:
        from test_retention import Store, private
    store = Store(path)
    with store.opened() as fd:
        owner = os.open('owner.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        try:
            private(os.fstat(owner), regular=True)
            fcntl.flock(owner, fcntl.LOCK_SH | fcntl.LOCK_NB)
            with store.locked(fd, 'writer.lock'):
                state = store.read(fd)
                if state and not state['finished']:
                    raise ValueError('retention: legacy VM journal is unfinished; preserve evidence and recover it before parallel execution')
        finally:
            os.close(owner)


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
        # Block-device numbers can change after reboot. Record the filesystem
        # identity while this new allocation is pinned; never infer it later
        # from a legacy receipt whose device no longer matches.
        filesystem = os.fstatvfs(child).f_fsid
        if filesystem:
            record['filesystem'] = filesystem
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
    allocation identity before it is handed out. Incomplete entries are preserved
    without preventing an independent allocation; unsafe identities still refuse.
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
                try:
                    owner = os.open('owner', os.O_RDWR | os.O_NOFOLLOW, dir_fd=child)
                except FileNotFoundError:
                    print(
                        f'scratch allocation {str(parent / name)!r} is missing its owner file; '
                        'preserving it and allocating independent scratch', file=sys.stderr)
                    continue
                try:
                    retention.private(os.fstat(owner), regular=True)
                    try:
                        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        continue
                    try:
                        receipt = os.open('identity.json', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=child)
                    except FileNotFoundError:
                        print(
                            f'scratch allocation {str(parent / name)!r} is missing its identity receipt; '
                            'preserving it and allocating independent scratch', file=sys.stderr)
                        continue
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
    producer = ROOT / 'output/test-runs/host/fixtures/producer.lock'
    descriptors = set(() if _scratch_fd is None else (_scratch_fd,))
    for name in os.listdir('/proc/self/fd'):
        descriptor = int(name)
        try:
            path = Path(os.readlink(f'/proc/self/fd/{descriptor}'))
            if str(path) == str(producer) + ' (deleted)':
                raise ValueError('fixture producer lease was removed')
            scratch_owner = (path.name == 'owner' and path.parent.parent == parent
                             and path.parent.name.startswith('run-'))
            if not scratch_owner and path != producer:
                continue
            info = os.fstat(descriptor)
            if (stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
                    and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1):
                if path == producer:
                    current = os.stat(path, follow_symlinks=False)
                    if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                        raise ValueError('fixture producer lease was replaced')
                descriptors.add(descriptor)
        except OSError as error:
            if error.errno not in (errno.ENOENT, errno.EBADF):
                raise
            # listdir's own fd or a concurrent worker's descriptor has closed.
    if __package__:
        from . import test_retention
    else:
        import test_retention
    descriptors.update(test_retention.descriptors())
    return tuple(sorted(descriptors))
