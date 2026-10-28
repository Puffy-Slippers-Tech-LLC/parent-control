"""FIFO admission for expensive disk work on the VM/build host.

The root-owned VM pool runtime is shared by users and checkouts. Each admitted
request has a kernel-locked ticket. Only the oldest live ticket may execute;
unlocked tickets are abandoned requests, never expired or stolen owners.
Durable workflow journals remain their existing owners' responsibility.
"""
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
import fcntl
import json
import os
from pathlib import Path
import re
import select
import signal
import stat
import subprocess
import sys
import time
import uuid

try:
    import vm_pool
except ModuleNotFoundError:
    from . import vm_pool

# Script and package launchers must share nesting state in the same process.
sys.modules.setdefault('host_disk', sys.modules[__name__])
sys.modules.setdefault('tools.host_disk', sys.modules[__name__])

_local = ContextVar('host_disk_operation', default=None)
_ticket = re.compile(r'([0-9]+)-[0-9a-f]{32}')
VARIABLE = 'ONPC_HOST_DISK_FD'


def _inherited():
    value = os.environ.get(VARIABLE)
    if value is None:
        return ()
    try:
        fd, device, inode = json.loads(value)
        if any(type(item) is not int for item in (fd, device, inode)) or fd < 3:
            raise ValueError
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) != (device, inode):
            raise ValueError
        if stat.S_ISREG(info.st_mode):
            path = Path(os.readlink('/proc/self/fd/' + str(fd)))
            if (path.parent != vm_pool.RUNTIME / 'disk' or not _ticket.fullmatch(path.name)
                    or info.st_uid not in (0, os.geteuid())
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                raise ValueError
        elif not (stat.S_ISFIFO(info.st_mode)
                  and fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE == os.O_WRONLY):
            raise ValueError
        return (fd,)
    except (TypeError, ValueError, OSError) as error:
        raise ValueError('host-disk: invalid inherited slot descriptor') from error


def descriptors():
    """Owned commands inherit the slot, including after their controller exits."""
    held = _local.get()
    return (held[1],) if held is not None and held[0] == os.getpid() else _inherited()


def environment(base=None):
    """Propagate only an inherited descriptor, never an unverified receipt.

    Pair with descriptors() in pass_fds. Wrapped child builders borrow that
    lifetime instead of queuing behind their own parent.
    """
    result = dict(os.environ if base is None else base)
    result.pop(VARIABLE, None)
    held = descriptors()
    if held:
        info = os.fstat(held[0])
        result[VARIABLE] = json.dumps([held[0], info.st_dev, info.st_ino])
    return result


def _open(directory, name):
    fd = os.open(directory / name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise ValueError('host-disk: unsafe queue file')
        return fd
    except BaseException:
        os.close(fd)
        raise


def _cancelled(stopped=None, incoming=None):
    if stopped is not None and (stopped() if callable(stopped) else stopped.is_set()):
        raise KeyboardInterrupt
    if incoming is not None and select.select([incoming], [], [], 0)[0]:
        if not os.read(incoming, 1):
            raise KeyboardInterrupt


@contextmanager
def _host(*, stopped=None, incoming=None):
    """Short gate orders admission; waiting never holds the admission gate."""
    directory = vm_pool.RUNTIME / 'disk'
    vm_pool.RUNTIME.mkdir(mode=0o700, exist_ok=True)
    info = vm_pool.RUNTIME.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise ValueError('host-disk: unsafe pool runtime')
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise ValueError('host-disk: unsafe queue directory')
    gate = _open(directory, 'gate')
    fd = None
    name = None
    try:
        _cancelled(stopped, incoming)
        fcntl.flock(gate, fcntl.LOCK_EX)
        try:
            numbers = [int(match[1]) for path in directory.iterdir()
                       if (match := _ticket.fullmatch(path.name))]
            name = str(max(numbers, default=0) + 1) + '-' + uuid.uuid4().hex
            fd = _open(directory, name)
            fcntl.flock(fd, fcntl.LOCK_EX)
        finally:
            fcntl.flock(gate, fcntl.LOCK_UN)
        announced = False
        while True:
            _cancelled(stopped, incoming)
            fcntl.flock(gate, fcntl.LOCK_EX)
            try:
                first = None
                for path in sorted((p for p in directory.iterdir() if _ticket.fullmatch(p.name)),
                                   key=lambda p: int(p.name.partition('-')[0])):
                    if path.name == name:
                        first = name
                        break
                    prior = _open(directory, path.name)
                    try:
                        try:
                            fcntl.flock(prior, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        except BlockingIOError:
                            first = path.name
                            break
                        # No process retains this ticket. Its operation has
                        # finished or crashed; there is no PID-based stealing.
                        path.unlink()
                    finally:
                        os.close(prior)
            finally:
                fcntl.flock(gate, fcntl.LOCK_UN)
            if first == name:
                _cancelled(stopped, incoming)
                yield fd
                break
            if not announced:
                print('host-disk: queued for host disk slot', file=sys.stderr, flush=True)
                announced = True
            if incoming is not None:
                select.select([incoming], [], [], 0.1)
            else:
                time.sleep(0.1)
    finally:
        # Do not unlink our ticket: inherited command descriptors can still
        # own it after this context exits. The next admission retires it safely.
        if fd is not None:
            os.close(fd)
        os.close(gate)


@contextmanager
def _remote(*, stopped=None):
    """The existing privileged dispatcher owns the one host queue."""
    if __package__:
        from .dev_privileges import check
    else:
        from dev_privileges import check
    helper = '/usr/local/libexec/onpc-test-runner'
    check(helper)
    child = subprocess.Popen(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
                              helper, 'disk'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             start_new_session=True,
                             env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'})
    try:
        while not select.select([child.stdout], [], [], 0.1)[0]:
            _cancelled(stopped)
        if child.stdout.readline(64) != b'host-disk: acquired\n':
            raise ValueError('host-disk: admission failed; refresh ./setup.sh --test-tools-only')
        _cancelled(stopped)
        yield child.stdin.fileno()
    finally:
        child.stdin.close()
        child.stdout.close()
        status = child.wait()
        if status and sys.exc_info()[0] is None:
            raise ValueError('host-disk: keeper failed (status ' + str(status) + ')')


def _reserve(*, stopped=None):
    return _host(stopped=stopped) if os.geteuid() == 0 else _remote(stopped=stopped)


@contextmanager
def operation(label, *, stopped=None):
    """Borrow in-process nesting; never acquire a VM or child controller here.

    Queue time is outside the operation's existing command timeout. Callers keep
    their identity guards and revalidate after admission before mutating state.
    """
    _cancelled(stopped)
    if descriptors():
        yield
        return
    try:
        from watch_activity import operation as observed
    except ModuleNotFoundError:
        observed = lambda _label: nullcontext()
    with observed('Waiting for host disk slot: ' + label):
        with _reserve(stopped=stopped) as fd:
            token = _local.set((os.getpid(), fd))
            try:
                with observed(label):
                    yield
            finally:
                _local.reset(token)


def keep():
    with _host(incoming=0):
        print('host-disk: acquired', flush=True)
        while os.read(0, 1):
            pass


if __name__ == '__main__':
    def interrupted(_signal, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    try:
        if len(sys.argv) != 1 or os.geteuid() != 0:
            raise ValueError('host-disk: invoke through the test dispatcher')
        keep()
    except KeyboardInterrupt:
        sys.exit(130)
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
