"""Identity-bound discovery and lifetime of the shared recording controller.

The controller lease is inherited by rendering children. An idle successor may
replace only a complete self-identifying journal, never an unknown stale name.
Privileged readers discover only their authenticated caller's private endpoint.
"""
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import uuid

if __package__:
    from . import test_retention, test_storage
else:
    import test_retention
    import test_storage

MANIFEST = 'control.json'
LOCK = '.controller.lock'


def _identity(info):
    return dict(device=info.st_dev, inode=info.st_ino)


def _private(info, uid, *, directory=False):
    if ((stat.S_ISDIR if directory else stat.S_ISREG)(info.st_mode) is False
            or info.st_uid != uid or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600)
            or (not directory and info.st_nlink != 1)):
        raise ValueError('recording control: unsafe ownership, type or mode')


def _process(pid):
    """Kernel process identity, excluding a dead unreaped zombie."""
    try:
        path = Path(f'/proc/{pid}/stat')
        info = path.stat()
        value = path.read_text()
    except FileNotFoundError:
        return None
    fields = value[value.rfind(')') + 2:].split()
    if len(fields) < 20:
        raise ValueError('recording control: process identity unavailable')
    if fields[0] in ('Z', 'X'):
        return None
    return dict(pid=pid, start_ticks=int(fields[19]), uid=info.st_uid)


def _alive(owner):
    return _process(owner['pid']) == owner


def _endpoint_path(endpoint):
    if (not isinstance(endpoint, dict) or set(endpoint) != {'socket', 'nonce'}
            or not isinstance(endpoint['socket'], str) or not isinstance(endpoint['nonce'], str)
            or re.fullmatch(r'[a-f0-9]{48}', endpoint['nonce']) is None):
        raise ValueError('recording control: invalid endpoint')
    path = Path(endpoint['socket'])
    if (not path.is_absolute() or '..' in path.parts or path.name != 'control'
            or path.parent.parent != Path('/tmp')
            or re.fullmatch(r'onpc-record-control-[A-Za-z0-9_-]+', path.parent.name) is None):
        raise ValueError('recording control: endpoint outside managed runtime')
    return path


def _socket(endpoint, uid, expected=None):
    path = _endpoint_path(endpoint)
    fd = test_retention.directory(path.parent)
    try:
        _private(os.fstat(fd), uid, directory=True)
        info = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != uid or info.st_nlink != 1:
            raise ValueError('recording control: unsafe runtime socket')
        identity = dict(directory=_identity(os.fstat(fd)), socket=_identity(info))
        if expected is not None and expected != identity:
            raise ValueError('recording control: runtime identity changed')
        return identity
    finally:
        os.close(fd)


def _identity_record(value):
    return (isinstance(value, dict) and set(value) == {'device', 'inode'}
            and all(type(value[key]) is int and value[key] >= 0 for key in value))


def _load(fd, uid):
    try:
        source = os.open(MANIFEST, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    except FileNotFoundError:
        return None
    with os.fdopen(source) as stream:
        info = os.fstat(stream.fileno())
        _private(info, uid)
        if info.st_size > 8192 or test_retention.mount_id(stream.fileno()) != test_retention.mount_id(fd):
            raise ValueError('recording control: oversized or mounted journal')
        value = json.load(stream)
    required = {'version', 'active', 'run_id', 'owner', 'root', 'lock', 'file', 'endpoint', 'runtime'}
    if (not isinstance(value, dict) or set(value) != required or type(value['version']) is not int
            or value['version'] != 1 or type(value['active']) is not bool
            or not isinstance(value['run_id'], str) or re.fullmatch(r'[a-f0-9]{32}', value['run_id']) is None
            or not all(_identity_record(value[key]) for key in ('root', 'lock', 'file'))
            or value['file'] != _identity(info) or value['root'] != _identity(os.fstat(fd))
            or not isinstance(value['owner'], dict) or set(value['owner']) != {'pid', 'start_ticks', 'uid'}
            or any(type(value['owner'][key]) is not int or value['owner'][key] < (0 if key == 'uid' else 1)
                   for key in ('pid', 'start_ticks', 'uid')) or value['owner']['uid'] != uid):
        raise ValueError('recording control: invalid or replaced journal')
    if value['active']:
        if (not isinstance(value['runtime'], dict) or set(value['runtime']) != {'directory', 'socket'}
                or not all(_identity_record(item) for item in value['runtime'].values())):
            raise ValueError('recording control: incomplete active journal')
        # Validate syntax even when stale runtime has already been reclaimed.
        _endpoint_path(value['endpoint'])
    elif value['endpoint'] is not None or value['runtime'] is not None:
        raise ValueError('recording control: invalid inactive journal')
    return value


class Publication:
    def __init__(self, root=None):
        self.directory = test_storage.recordings_directory(root=root)
        self.fd = self.lock = None
        self.state = None
        self.identity = None
        try:
            self.fd = test_retention.directory(self.directory)
            _private(os.fstat(self.fd), os.geteuid(), directory=True)
            self.root_identity = _identity(os.fstat(self.fd))
            self.lock = os.open(LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                                0o600, dir_fd=self.fd)
            _private(os.fstat(self.lock), os.geteuid())
            if test_retention.mount_id(self.lock) != test_retention.mount_id(self.fd):
                raise ValueError('recording control: mounted lock refused')
            self.lock_identity = _identity(os.fstat(self.lock))
            try:
                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError('recording control: another controller is active') from error
            previous = _load(self.fd, os.geteuid())
            if previous is not None:
                if previous['lock'] != self.lock_identity:
                    raise ValueError('recording control: controller lock replaced')
                if previous['active'] and _alive(previous['owner']):
                    raise ValueError('recording control: active journal has a live owner')
                self.identity = previous['file']
            owner = _process(os.getpid())
            if owner is None or owner['uid'] != os.geteuid():
                raise ValueError('recording control: controller identity unavailable')
            self.state = dict(version=1, active=False, run_id=uuid.uuid4().hex,
                              owner=owner, root=self.root_identity, lock=self.lock_identity,
                              file=None, endpoint=None, runtime=None)
            self._save()
        except BaseException:
            self._release()
            raise

    def descriptors(self):
        return () if self.lock is None else (self.lock,)

    def _guard(self):
        check = test_retention.directory(self.directory)
        try:
            _private(os.fstat(check), os.geteuid(), directory=True)
            if (_identity(os.fstat(check)) != self.root_identity
                    or test_retention.mount_id(check) != test_retention.mount_id(self.fd)):
                raise ValueError('recording control: directory changed')
        finally:
            os.close(check)
        info = os.stat(LOCK, dir_fd=self.fd, follow_symlinks=False)
        _private(info, os.geteuid())
        if _identity(info) != self.lock_identity:
            raise ValueError('recording control: controller lock replaced')
        if self.identity is not None:
            current = _load(self.fd, os.geteuid())
            if current is None:
                raise ValueError('recording control: controller journal replaced')
            if current['file'] != self.identity:
                # A signal may arrive after rename completed but before Python
                # updated identity. The prepared, identity-known receipt from
                # this exact owner/run is sufficient to finish safe shutdown.
                if (current['file'] != self.state['file']
                        or current['run_id'] != self.state['run_id']
                        or current['owner'] != self.state['owner']):
                    raise ValueError('recording control: controller journal replaced')
                self.identity = current['file']
        else:
            try:
                os.stat(MANIFEST, dir_fd=self.fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ValueError('recording control: unowned journal exists')

    def _save(self):
        self._guard()
        name = '.control-' + uuid.uuid4().hex + '.tmp'
        out = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                      0o600, dir_fd=self.fd)
        with os.fdopen(out, 'w') as stream:
            self.state['file'] = _identity(os.fstat(stream.fileno()))
            json.dump(self.state, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        # The stable lease serializes trusted publishers. Preserve unknown
        # replacements appearing while the temporary receipt was written.
        self._guard()
        os.replace(name, MANIFEST, src_dir_fd=self.fd, dst_dir_fd=self.fd)
        self.identity = self.state['file']
        os.fsync(self.fd)

    def publish(self, endpoint):
        if self.fd is None:
            raise ValueError('recording control: publisher is closed')
        identity = _socket(endpoint, os.geteuid())
        self.state.update(active=True, endpoint=dict(endpoint), runtime=identity)
        self._save()

    def _release(self):
        if self.lock is not None:
            os.close(self.lock)
            self.lock = None
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def close(self):
        try:
            if self.fd is not None:
                self.state.update(active=False, endpoint=None, runtime=None)
                self._save()
        finally:
            self._release()


def endpoint(root=None):
    """Read only a live owner endpoint; stale active records fail closed.

    PKEXEC_UID is meaningful only in a root dispatcher, which authenticates it.
    Ordinary owner processes inspect their own storage branch.
    """
    caller = os.environ.get('PKEXEC_UID') if os.geteuid() == 0 else None
    arguments = dict(root=root, create=False)
    if caller is not None:
        if not caller.isdecimal() or int(caller) <= 0:
            raise ValueError('recording control: invalid authenticated caller')
        uid = int(caller)
        arguments['caller_uid'] = uid
    else:
        uid = os.geteuid()
    try:
        directory = test_storage.recordings_directory(**arguments)
    except FileNotFoundError:
        return None
    fd = test_retention.directory(directory)
    lock = None
    try:
        _private(os.fstat(fd), uid, directory=True)
        state = _load(fd, uid)
        if state is None:
            return None
        lock = os.open(LOCK, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        _private(os.fstat(lock), uid)
        if (_identity(os.fstat(lock)) != state['lock']
                or test_retention.mount_id(lock) != test_retention.mount_id(fd)):
            raise ValueError('recording control: controller lock replaced')
        if not state['active']:
            return None
        if not _alive(state['owner']):
            raise ValueError('recording control: stale active owner')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            raise ValueError('recording control: active controller lease is absent')
        _socket(state['endpoint'], uid, state['runtime'])
        return dict(state['endpoint'])
    finally:
        if lock is not None:
            os.close(lock)
        os.close(fd)
