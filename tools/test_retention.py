"""Last-three-run retention for explicitly registered aggregate allocations.

Never discover deletion targets by scanning temporary-directory prefixes. The
coordinator holds an exclusive storage lease until its children finish; writers
serialize the private journal. Unregistered replacements and unfinished owners
fail closed. A recreated path belongs to its latest recorded allocation.
"""

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import uuid
import tempfile

VARIABLE = 'ONPC_TEST_RETENTION'
RUNS_TO_KEEP = 3
MAX_RETAINED_BYTES = 4 * 1024 ** 3
_locks = set()


def latest_allocations(entries):
    """Return each path's last registered owner, in oldest-to-newest entries.

    Producers can remove an allocation and exclusively recreate the same named
    output in a later run. Keep the old journal records as evidence, but never
    validate or delete the new allocation using an expired owner's identity.
    The latest record still undergoes every identity and tree safety check.
    """
    latest = {}
    for index, entry in enumerate(entries):
        for record in entry['paths']:
            latest[record['path']] = (index, record)
    return list(latest.values())


def directory(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('retention: invalid directory')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def private(info, *, regular=False):
    kind = stat.S_ISREG if regular else stat.S_ISDIR
    if (not kind(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != (0o600 if regular else 0o700)
            or (regular and info.st_nlink != 1)):
        raise ValueError('retention: unsafe ownership or mode')


def ensure_directory(path):
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for name in Path(path).parts[1:]:
            try:
                os.mkdir(name, mode=0o700, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        private(os.fstat(fd))
    finally:
        os.close(fd)


class Store:
    def __init__(self, path):
        self.path = Path(path)

    def reconcile(self, guard):
        """Recover an idle owner, retaining its evidence in normal rotation.

        The caller holds checkout activity ownership; the privileged guard
        additionally reconciles the recorded VM under its independent lease.
        Never signal processes or discover disposable paths by name.
        """
        ensure_directory(self.path)
        with self.opened() as fd, self.locked(fd, 'owner.lock', blocking=False):
            guard()
            with self.locked(fd, 'writer.lock'):
                state = self.read(fd)
                marked = 'recovery-required' in os.listdir(fd)
                if state is None:
                    if marked:
                        raise ValueError('retention: recovery marker has no journal')
                    return False
                if state['finished'] and not marked:
                    return False
                for _, record in latest_allocations([*state['history'], state]):
                    remove(record, validate_only=True)
                run = uuid.UUID(hex=state['run']).hex
                archive = f'recovered-{run}.json'
                if archive not in os.listdir(fd):
                    self.save(fd, state, name=archive)
                if marked:
                    marker = os.stat('recovery-required', dir_fd=fd, follow_symlinks=False)
                    private(marker, regular=True)
                    os.rename('recovery-required', f'recovered-{run}.marker',
                              src_dir_fd=fd, dst_dir_fd=fd)
                    os.fsync(fd)
                state['finished'] = True
                self.save(fd, state)
                self.prune(fd, state)
                print('Recovered idle test retention; previous evidence retained.', flush=True)
                return True

    @contextmanager
    def opened(self):
        fd = directory(self.path)
        try:
            private(os.fstat(fd))
            yield fd
        finally:
            os.close(fd)

    @contextmanager
    def locked(self, fd, name, *, blocking=True):
        lock = os.open(name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
                       0o600, dir_fd=fd)
        try:
            private(os.fstat(lock), regular=True)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            except BlockingIOError as error:
                raise ValueError('retention: another owner is active') from error
            _locks.add(lock)
            yield
        finally:
            _locks.discard(lock)
            os.close(lock)

    def read(self, fd):
        try:
            source = os.open('current.json', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        except FileNotFoundError:
            return None
        with os.fdopen(source) as stream:
            private(os.fstat(stream.fileno()), regular=True)
            value = json.load(stream)
        if (not isinstance(value, dict)
                or set(value) not in ({'run', 'finished', 'paths'},
                                      {'run', 'finished', 'paths', 'history'})
                or not isinstance(value['paths'], list) or type(value['finished']) is not bool):
            raise ValueError('retention: invalid journal')
        uuid.UUID(hex=value['run'])
        # Upgrade the original single-run journal without losing its ownership
        # records. History is oldest first and contains only completed owners.
        history = value.setdefault('history', [])
        if not isinstance(history, list) or len(history) >= RUNS_TO_KEEP:
            raise ValueError('retention: invalid history')
        tokens = {value['run']}
        for entry in history:
            if (not isinstance(entry, dict) or set(entry) != {'run', 'paths'}
                    or not isinstance(entry['paths'], list) or entry['run'] in tokens):
                raise ValueError('retention: invalid history')
            uuid.UUID(hex=entry['run'])
            tokens.add(entry['run'])
        return value

    def save(self, fd, value, *, name='current.json'):
        out = os.open('current.tmp', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW,
                      0o600, dir_fd=fd)
        with os.fdopen(out, 'w') as stream:
            private(os.fstat(stream.fileno()), regular=True)
            os.ftruncate(stream.fileno(), 0)
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace('current.tmp', name, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)

    def prune(self, fd, state, *, keep=RUNS_TO_KEEP):
        """Bound completed evidence by count and allocated bytes, under ownership.

        Never evict the current run. A single oversized current run refuses new
        work until explicitly addressed, instead of silently losing evidence.
        """
        entries = [*state['history'], state]
        allocations = latest_allocations(entries)
        sizes = [0] * len(entries)
        for index, record in allocations:
            remove(record, validate_only=True)
            sizes[index] += allocation_bytes(record)
        expire = max(0, len(entries) - keep)
        while sum(sizes[expire:]) > MAX_RETAINED_BYTES and expire < len(entries) - 1:
            expire += 1
        for index, record in allocations:
            if index < expire:
                remove(record)
        state['history'] = state['history'][expire:]
        self.save(fd, state)
        # Archives are small recovery receipts, not a second retention queue.
        live = {entry['run'] for entry in [*state['history'], state]}
        for name in os.listdir(fd):
            import re
            match = re.fullmatch(r'(?:recovered|interrupted)-([0-9a-f]{32})\.(json|marker)', name)
            if match and match[1] not in live:
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                private(info, regular=True)
                os.unlink(name, dir_fd=fd)
        if sizes[-1] > MAX_RETAINED_BYTES:
            raise ValueError('retention: current run exceeds 4 GiB storage budget; '
                             'evidence preserved; cleanup required before new work')

    @contextmanager
    def session(self, *, run=None, guard=None, recover=None, preserve_completed=None):
        if not self.path.is_absolute() or '..' in self.path.parts:
            raise ValueError('retention: invalid storage path')
        ensure_directory(self.path)
        run = run or uuid.uuid4().hex
        if len(run) != 32 or uuid.UUID(hex=run).hex != run:
            raise ValueError('retention: invalid run token')
        previous = os.environ.get(VARIABLE)
        with self.opened() as fd, self.locked(fd, 'owner.lock', blocking=False):
            if guard is not None:
                guard()
            with self.locked(fd, 'writer.lock'):
                state = self.read(fd)
                if (state and state['finished'] and preserve_completed is not None
                        and 'recovery-required' not in os.listdir(fd)
                        and preserve_completed(state)):
                    raise ValueError('retention: legacy evidence requires explicit storage migration')
                if state and not state['finished']:
                    if ('recovery-required' in os.listdir(fd) or recover is None
                            or not recover(state)):
                        raise ValueError('retention: previous owner did not finish; preserve evidence for recovery')
                    # The caller qualified recovery. Keep its receipt and
                    # evidence in the same bounded rotation as completed runs.
                    self.save(fd, state, name=f'interrupted-{uuid.UUID(hex=state["run"]).hex}.json')
                    state['finished'] = True
                if state and state['run'] != run:
                    if any(entry['run'] == run for entry in state['history']):
                        raise ValueError('retention: an older run cannot resume after a newer owner')
                    # Check the previous current run before making it eligible
                    # for eviction. An oversized run must remain the owner until
                    # its evidence has been explicitly reduced or removed.
                    self.prune(fd, state)
                    history = state['history'] + [dict(run=state['run'], paths=state['paths'])]
                    # prune audited all identities before any eviction, including
                    # inaccessible sbuild trees and their earlier reports/logs.
                    allocations = latest_allocations(history)
                    for index, record in allocations:
                        if index < len(history) - (RUNS_TO_KEEP - 1):
                            remove(record)
                    state = dict(run=run, finished=False, paths=[],
                                 history=history[-(RUNS_TO_KEEP - 1):])
                if state is None:
                    state = dict(run=run, finished=False, paths=[], history=[])
                state['finished'] = False
                self.save(fd, state)
                self.prune(fd, state)
            os.environ[VARIABLE] = json.dumps([str(self.path), run])
            try:
                yield run
            finally:
                if previous is None:
                    os.environ.pop(VARIABLE, None)
                else:
                    os.environ[VARIABLE] = previous
                if guard is not None:
                    guard()
                with self.locked(fd, 'writer.lock'):
                    state = self.read(fd)
                    state['finished'] = 'recovery-required' not in os.listdir(fd)
                    self.save(fd, state)
                    if state['finished']:
                        self.prune(fd, state)


def environment():
    value = os.environ.get(VARIABLE)
    return {} if value is None else {VARIABLE: value}


def legacy_system_evidence(state):
    """Recognize the old system exporter changing a registered 0700 root to 0755.

    Only the privileged dispatcher uses this migration, under its recovery
    guard. Audit every allocation; archive the whole journal without deletion.
    """
    legacy = False
    for _, record in latest_allocations([*state['history'], state]):
        path = Path(record['path'])
        if (path.parent != Path('/tmp') or not path.name.startswith('onpc-system-')
                or record.get('mode', 0o700) != 0o700):
            remove(record, validate_only=True)
            continue
        try:
            target = directory(path)
        except FileNotFoundError:
            continue
        try:
            info = os.fstat(target)
            if stat.S_IMODE(info.st_mode) != 0o755:
                remove(record, validate_only=True)
                continue
            if (info.st_uid != os.geteuid() or
                    (info.st_dev, info.st_ino) != (record['device'], record['inode'])):
                raise ValueError('retention: legacy allocation identity changed')
            parent = directory(path.parent)
            try:
                if mount_id(target) != mount_id(parent):
                    raise ValueError('retention: mounted storage is not disposable')
            finally:
                os.close(parent)
            check_tree(target, info.st_dev)
            legacy = True
        finally:
            os.close(target)
    return legacy


def token():
    value = os.environ.get(VARIABLE)
    return None if value is None else json.loads(value)[1]


def allocate(factory, *, mode=0o700, runtime=False, **options):
    """Keep cooperative interruption outside allocation + registration.

    The factory is the producer's tempfile.mkdtemp, injectable by its tests.
    Nothing has populated the fresh directory yet if registration fails.
    """
    if mode not in (0o700, 0o711):
        raise ValueError('retention: invalid allocation mode')
    if runtime and (options.get('dir') != '/tmp' or mode != 0o700):
        raise ValueError('retention: runtime allocation requires private /tmp socket storage')
    parent = options.get('dir')
    if (not runtime and str(options.get('prefix', '')).startswith('onpc-')
            and (parent is None or os.fspath(parent) in ('/tmp', '/var/tmp'))):
        if __package__:
            from .test_storage import directory as storage_directory
        else:
            from test_storage import directory as storage_directory
        options['dir'] = str(storage_directory('sbuild' if mode == 0o711 else 'allocations'))
        if VARIABLE not in os.environ and mode == 0o700:
            if __package__:
                from .test_storage import scratch_directory
            else:
                from test_storage import scratch_directory
            options['dir'] = str(scratch_directory())
    if VARIABLE not in os.environ:
        path = factory(**options)
        if mode != 0o700:
            os.chmod(path, mode)
        return path
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
    try:
        path = factory(**options)
        try:
            if mode != 0o700:
                os.chmod(path, mode)
            retain(path, mode=mode)
        except BaseException:
            os.rmdir(path)
            raise
        return path
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def preserve_for_recovery():
    value = os.environ.get(VARIABLE)
    if value is None:
        return
    storage, run = json.loads(value)
    store = Store(storage)
    with store.opened() as fd, store.locked(fd, 'writer.lock'):
        state = store.read(fd)
        if state is None or state['run'] != run:
            raise ValueError('retention: recovery owner changed')
        marker = os.open('recovery-required', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW,
                         0o600, dir_fd=fd)
        try:
            private(os.fstat(marker), regular=True)
            os.fsync(marker)
            os.fsync(fd)
        finally:
            os.close(marker)


def retain(path, *, mode=0o700):
    """Register only an allocation just created by the calling producer."""
    value = os.environ.get(VARIABLE)
    if value is None:
        return path
    storage, run = json.loads(value)
    store = Store(storage)
    path = Path(path)
    target = directory(path)
    try:
        info = os.fstat(target)
        allocation_identity(info, mode)
        record = dict(path=str(path), device=info.st_dev, inode=info.st_ino, mode=mode)
        with store.opened() as fd, store.locked(fd, 'writer.lock'):
            state = store.read(fd)
            if state is None or state['run'] != run or state['finished']:
                raise ValueError('retention: allocation has no active owner')
            if record not in state['paths']:
                state['paths'].append(record)
                store.save(fd, state)
    finally:
        os.close(target)
    return path


def remove(record, *, validate_only=False):
    """Delete one recorded tree, without following links or crossing mounts."""
    path = Path(record['path'])
    try:
        parent = directory(path.parent)
    except FileNotFoundError:
        return
    try:
        try:
            target = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        except FileNotFoundError:
            return  # Passing render cleanup may already have removed it.
        try:
            info = os.fstat(target)
            allocation_identity(info, record.get('mode', 0o700))
            if (info.st_dev, info.st_ino) != (record['device'], record['inode']):
                raise ValueError('retention: recorded allocation was replaced')
            if mount_id(target) != mount_id(parent):
                raise ValueError('retention: mounted storage is not disposable')
            if os.geteuid() != 0 and sbuild_scratch(record):
                namespace_remove(record, validate_only=validate_only)
                return
            check_tree(target, info.st_dev)
            if validate_only:
                return
            current = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                raise ValueError('retention: allocation changed during cleanup')
            clear_tree(target, info.st_dev)
            current = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                raise ValueError('retention: allocation changed during cleanup')
            os.rmdir(path.name, dir_fd=parent)
        finally:
            os.close(target)
    except OSError as error:
        operation = 'inspect' if validate_only else 'clean'
        error.add_note(
            f'retention: cannot {operation} registered allocation {str(path)!r}; '
            'startup refused; preserve the journal and evidence until its cleanup is repaired')
        raise
    finally:
        os.close(parent)


def sbuild_scratch(record):
    path = Path(record['path'])
    return ((path.parent == Path('/var/tmp') or
             path.parent == Path(__file__).resolve().parents[1] / 'output/test-runs/host/sbuild')
            and path.name.startswith('onpc-sbuild-scratch-')
            and record.get('mode') == 0o711)


def allocation_bytes(record):
    """Allocated blocks, with the same pinned-directory/mount boundary as removal."""
    try:
        fd = directory(record['path'])
    except FileNotFoundError:
        return 0
    def size(parent):
        total = 0
        for name in os.listdir(parent):
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            total += info.st_blocks * 512
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                try:
                    if mount_id(child) != mount_id(parent):
                        raise ValueError('retention: mounted storage is not disposable')
                    total += size(child)
                finally:
                    os.close(child)
        return total
    try:
        return os.fstat(fd).st_blocks * 512 + size(fd)
    except PermissionError:
        if not sbuild_scratch(record):
            raise
        return namespace_remove(record, validate_only=True, measure=True)
    finally:
        os.close(fd)


def namespace_remove(record, *, validate_only, measure=False):
    # Map only the caller and its configured subordinate IDs, never host root.
    # Identity mapping keeps the complete subordinate range (map-auto plus
    # map-root-user drops one ID). No mount namespace: bind mounts remain visible
    # to the same descriptor-based audit used by ordinary retention.
    command = ['/usr/bin/unshare', '--user', '--map-users=subids',
               '--map-groups=subids', '--map-root-user', '--',
               '/usr/bin/python3', '-I', '-B', str(Path(__file__).resolve()),
               '--sbuild-retention', 'measure' if measure else 'inspect' if validate_only else 'remove']
    try:
        result = subprocess.run(command, input=json.dumps(record), text=True,
                                cwd='/', env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin',
                                              'LANG': 'C.UTF-8'},
                                pass_fds=tuple(_locks), timeout=300, check=False,
                                **({'capture_output': True} if measure else {}))
    except subprocess.TimeoutExpired as error:
        raise ValueError(f'retention: sbuild namespace operation timed out for {record["path"]!r}; '
                         'preserve the journal and evidence') from error
    if result.returncode:
        raise ValueError(f'retention: sbuild namespace operation failed for {record["path"]!r} '
                         f'(status={result.returncode}); preserve the journal and evidence')
    if measure:
        return int(result.stdout.strip())


def namespace_main(argv):
    if (argv not in (['--sbuild-retention', 'inspect'], ['--sbuild-retention', 'remove'],
                    ['--sbuild-retention', 'measure'])
            or os.geteuid() != 0):
        raise ValueError('retention: invalid sbuild namespace invocation')
    # Refuse invocation as real host root; this worker is only for caller-owned
    # scratch, with the caller mapped to namespace root by unshare.
    mapping = [line.split() for line in Path('/proc/self/uid_map').read_text().splitlines()]
    if not any(inner == '0' and outer != '0' and count == '1'
               for inner, outer, count in mapping):
        raise ValueError('retention: caller user namespace required')
    record = json.load(sys.stdin)
    if not sbuild_scratch(record):
        raise ValueError('retention: invalid sbuild scratch record')
    remove(record, validate_only=argv[1] != 'remove')
    if argv[1] == 'measure':
        print(allocation_bytes(record))


def check_tree(fd, device):
    for name in os.listdir(fd):
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if info.st_dev != device:
            raise ValueError('retention: mounted storage is not disposable')
        if stat.S_ISDIR(info.st_mode):
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                if os.fstat(child).st_dev != device or mount_id(child) != mount_id(fd):
                    raise ValueError('retention: mounted storage is not disposable')
                check_tree(child, device)
            finally:
                os.close(child)


def clear_tree(fd, device):
    """Operate on the pinned original tree even if its pathname is renamed."""
    for name in os.listdir(fd):
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if info.st_dev != device:
            raise ValueError('retention: mounted storage is not disposable')
        if stat.S_ISDIR(info.st_mode):
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                opened = os.fstat(child)
                if mount_id(child) != mount_id(fd):
                    raise ValueError('retention: mounted storage is not disposable')
                if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                    raise ValueError('retention: child directory was replaced')
                clear_tree(child, device)
                current = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                    raise ValueError('retention: child directory changed during cleanup')
                os.rmdir(name, dir_fd=fd)
            finally:
                os.close(child)
        else:
            os.unlink(name, dir_fd=fd)


def mount_id(fd):
    # Match the explicitly opened descriptor, as vm_ownership does.
    # st_dev alone cannot distinguish a bind mount on the same filesystem.
    values = [line.split()[1] for line in Path(f'/proc/self/fdinfo/{fd}').read_text().splitlines()
              if line.startswith('mnt_id:')]
    if len(values) != 1 or not values[0].isdecimal():
        raise ValueError('retention: mount identity is unavailable')
    return values[0]


def allocation_identity(info, mode):
    # sbuild's subordinate user needs traversal through its otherwise private
    # scratch parent. Registry directories always retain strict 0700 ownership.
    if (mode not in (0o700, 0o711) or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != mode):
        raise ValueError('retention: unsafe allocation ownership or mode')


if __name__ == '__main__':
    try:
        namespace_main(sys.argv[1:])
    except (ValueError, OSError) as error:
        sys.exit(str(error))
