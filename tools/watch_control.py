"""Small live Watch policy shared by a launcher's owned processes."""

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile
import time


VARIABLE = 'ONPC_WATCH_CONTROL'
FRAME = b'WATCH '
_cached = None


def validate(value, *, partial=False):
    if (not isinstance(value, dict) or set(value) - {'ssh', 'view'}
            or not partial and set(value) != {'ssh', 'view'}
            or any(type(item) is not bool for item in value.values())):
        raise ValueError('watch: invalid settings')
    return dict(value)


def _read(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts or path.resolve(strict=True) != path:
        raise ValueError('watch: invalid settings path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        owners = {os.geteuid(), int(os.environ.get('PKEXEC_UID', os.geteuid()))}
        if (not stat.S_ISREG(info.st_mode) or info.st_size > 1024
                or info.st_uid not in owners or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_nlink != 1):
            raise ValueError('watch: invalid settings file')
        return validate(json.loads(stream.read(1025)))


def settings():
    global _cached
    path = os.environ.get(VARIABLE)
    if not path:
        return dict(ssh=True, view=True)
    now = time.monotonic()
    cached = _cached
    if cached is None or cached[0] != path or now >= cached[2]:
        value = _read(path)
        _cached = (path, value, now + .25)
    else:
        value = cached[1]
    return dict(value)


def read(run):
    return _read(target(run))


def target(run):
    run = Path(run)
    try:
        fd = os.open(run / 'watch-parent.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return run / 'watch.json'
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1
                or info.st_size > 4096):
            raise ValueError('watch: invalid parent settings')
        value = json.loads(stream.read(4097))
    if not isinstance(value, str):
        raise ValueError('watch: invalid parent settings')
    path = Path(value)
    if (not path.is_absolute() or '..' in path.parts or path.name != 'watch.json'
            or path.resolve(strict=True) != path):
        raise ValueError('watch: invalid parent settings')
    _read(path)
    return path


def enabled(kind):
    return settings()[kind]


def environment():
    path = os.environ.get(VARIABLE)
    return {VARIABLE: path} if path else {}


def _write(run, updates, *, initialize=False, record=False):
    global _cached
    updates = validate(updates, partial=True)
    run = target(run).parent
    gate = os.open(run / 'watch-gate', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(gate)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise ValueError('watch: invalid settings gate')
        fcntl.flock(gate, fcntl.LOCK_EX)
        path = run / 'watch.json'
        try:
            value = _read(path)
        except FileNotFoundError:
            if not initialize:
                raise
            value = dict(ssh=False, view=False)
        value.update(updates)
        if (record or (run / 'watch-recording').exists()) and not all(value.values()):
            raise ValueError('--record requires --watch-ssh on and --watch-view on')
        if record:
            marker = os.open(run / 'watch-recording', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
            try:
                info = os.fstat(marker)
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                        or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                    raise ValueError('watch: invalid recording guard')
            finally:
                os.close(marker)
        with tempfile.NamedTemporaryFile(mode='w', prefix='watch-', dir=run, delete=False) as stream:
            temporary = Path(stream.name)
            try:
                json.dump(value, stream)
                stream.close()
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        _cached = None
        return value
    finally:
        os.close(gate)


def initialize(run, updates=None, *, inherit=False, record=False):
    """Create an off policy, preserving saved choices on a resumed run."""
    if inherit and VARIABLE in os.environ:
        path = Path(os.environ[VARIABLE])
        if (not path.is_absolute() or '..' in path.parts or path.name != 'watch.json'
                or path.resolve(strict=True) != path):
            raise ValueError('watch: invalid inherited settings')
        _read(path)
        pointer = Path(run) / 'watch-parent.json'
        try:
            fd = os.open(pointer, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            if target(run) != path:
                raise ValueError('watch: inherited settings changed')
        else:
            with os.fdopen(fd, 'w') as stream:
                json.dump(str(path), stream)
    return _write(run, updates or {}, initialize=True, record=record)


def update(run, updates):
    return _write(run, updates)


@contextmanager
def binding(run):
    previous = os.environ.get(VARIABLE)
    os.environ[VARIABLE] = str(target(run))
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(VARIABLE, None)
        else:
            os.environ[VARIABLE] = previous


@contextmanager
def receiving(initial=None, *, active=None):
    """Rebind portable bool settings to this host's existing scratch lifetime."""
    if __package__:
        from .test_storage import scratch_directory
    else:
        from test_storage import scratch_directory
    temporary = tempfile.TemporaryDirectory(prefix='watch-control-', dir=scratch_directory())
    try:
        run = Path(temporary.name)
        initialize(run, initial or {})
        with binding(run):
            yield run
    finally:
        if active is not None and active():
            # A blocked listener still owns its files; the shared scratch lease
            # preserves them until this process and its descendants finish.
            temporary._finalizer.detach()
        else:
            temporary.cleanup()


def parse(argv):
    remaining, updates = [], {}
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument == '--':
            remaining.extend(argv[index:])
            break
        option, separator, value = argument.partition('=')
        if option in ('--watch-ssh', '--watch-view'):
            kind = option.removeprefix('--watch-')
            if kind in updates:
                raise ValueError(f'{option} may be supplied only once')
            if not separator:
                index += 1
                value = argv[index] if index < len(argv) else ''
            if value not in ('on', 'off'):
                raise ValueError(f'{option} requires on or off')
            updates[kind] = value == 'on'
        else:
            remaining.append(argument)
        index += 1
    return remaining, updates
