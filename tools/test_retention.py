"""Last-three-run retention for explicitly registered aggregate allocations.

Never discover deletion targets by scanning temporary-directory prefixes. The
coordinator holds an exclusive storage lease until its children finish; writers
serialize the private journal. Replaced paths and unfinished owners fail closed.
"""

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import signal
import stat
import uuid

VARIABLE = 'ONPC_TEST_RETENTION'
RUNS_TO_KEEP = 3


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
                for entry in [state, *state['history']]:
                    for record in entry['paths']:
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
            yield
        finally:
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
                    # Preserve legacy evidence outside rotation. Never rewrite
                    # its ownership records or delete a mismatched allocation.
                    self.save(fd, state, name=f'preserved-{uuid.UUID(hex=state["run"]).hex}.json')
                    state = None
                if state and not state['finished']:
                    if ('recovery-required' in os.listdir(fd) or recover is None
                            or not recover(state)):
                        raise ValueError('retention: previous owner did not finish; preserve evidence for recovery')
                    # Recovery never calls deletion or labels the old owner
                    # finished. Pin its entire journal, including older evidence,
                    # outside normal rotation before committing a fresh owner.
                    self.save(fd, state, name=f'interrupted-{uuid.UUID(hex=state["run"]).hex}.json')
                    state = None
                if state and state['run'] != run:
                    if any(entry['run'] == run for entry in state['history']):
                        raise ValueError('retention: an older run cannot resume after a newer owner')
                    history = state['history'] + [dict(run=state['run'], paths=state['paths'])]
                    # A late refusal (for example an inaccessible sbuild
                    # chroot) must preserve its earlier report and build log.
                    for entry in history:
                        for record in entry['paths']:
                            remove(record, validate_only=True)
                    for entry in history[:-(RUNS_TO_KEEP - 1)]:
                        for record in entry['paths']:
                            remove(record)
                    state = dict(run=run, finished=False, paths=[],
                                 history=history[-(RUNS_TO_KEEP - 1):])
                if state is None:
                    state = dict(run=run, finished=False, paths=[], history=[])
                state['finished'] = False
                self.save(fd, state)
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


def environment():
    value = os.environ.get(VARIABLE)
    return {} if value is None else {VARIABLE: value}


def legacy_system_evidence(state):
    """Recognize the old system exporter changing a registered 0700 root to 0755.

    Only the privileged dispatcher uses this migration, under its recovery
    guard. Audit every allocation; archive the whole journal without deletion.
    """
    legacy = False
    for entry in [state, *state['history']]:
        for record in entry['paths']:
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


def allocate(factory, *, mode=0o700, **options):
    """Keep cooperative interruption outside allocation + registration.

    The factory is the producer's tempfile.mkdtemp, injectable by its tests.
    Nothing has populated the fresh directory yet if registration fails.
    """
    if mode not in (0o700, 0o711):
        raise ValueError('retention: invalid allocation mode')
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
    finally:
        os.close(parent)


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
    # Match the explicitly opened descriptor, as backing_verification does.
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
