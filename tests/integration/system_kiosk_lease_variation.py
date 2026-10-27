"""Installed lease engineering controls; no public-entry acceptance claim."""
from contextlib import ExitStack, contextmanager
import ctypes
import errno
import fcntl
import importlib
import json
import os
from pathlib import Path
import pwd
import select
import signal
import stat
import subprocess
import sys

import system_guest as guest
from system_kiosk_admission import held_account, probe, root_uids
from system_kiosk_confinement import (caller_identity, lifecycle_event,
    pam_caller_command, wait_kiosk_inactive)


LOCK = Path('/run/oh-no-parent-control-kiosk-admission.lock')
DISABLED = Path('/var/lib/oh-no-parent-control/kiosk-confinement-removing')
SERVICES = ('gdm-password', 'systemd-user')


def session_lease(service):
    # Fedora's vendor account stack can return at sufficient pam_unix before
    # including system-auth. Its session stack always reaches the owned module.
    return service == 'systemd-user' and guest.package_path().suffix == '.rpm'


def require(value, code):
    guest.require(value, 'kiosk-lease:' + code)


def lifecycle():
    # Load the actual package owner, never a copied locking implementation.
    directory = Path('/usr/lib/oh-no-parent-control/lifecycle')
    path = directory / 'lifecycle_migration.py'
    for item in (*reversed(directory.parents), directory, path):
        info = item.lstat()
        require(info.st_uid == 0 and not info.st_mode & 0o022 and
                (stat.S_ISREG(info.st_mode) if item == path else stat.S_ISDIR(info.st_mode)),
                'unsafe-installed-lifecycle')
    sys.path.insert(0, str(directory))
    module = importlib.import_module('lifecycle_migration')
    require(Path(module.__file__) == path, 'installed-lifecycle-path')
    return module


def identity(info):
    return (info.st_dev, info.st_ino, info.st_uid, info.st_gid,
            info.st_nlink, info.st_mode, info.st_size)


def current(fd, expected):
    require(identity(os.fstat(fd)) == expected == identity(LOCK.lstat()),
            'lease-changed')


@contextmanager
def stale_mode(fd, *, repaired=False):
    """Restore only this exact inode and this attempt's exact mode change."""
    before = identity(os.fstat(fd))
    current(fd, before)
    require(stat.S_IMODE(before[5]) == 0o600, 'healthy-mode')
    os.fchmod(fd, 0o640)
    injected = (*before[:5], stat.S_IFREG | 0o640, before[6])
    try:
        current(fd, injected)
        yield injected
    finally:
        # A writer repair is allowed only in the explicitly selected recovery
        # history. Both permitted modes still require the same owned inode.
        observed = identity(os.fstat(fd))
        require(observed in ((before, injected) if repaired else (injected,)),
                'restoration-state-changed')
        current(fd, observed)
        os.fchmod(fd, stat.S_IMODE(before[5]))
        current(fd, before)


def writer(expected, record, stage):
    """Observe the maintained configuration writer's real exclusive barrier."""
    owner = lifecycle()
    try:
        with owner.barriers():
            result = 'acquired'
    except BlockingIOError as error:
        require(error.errno in (errno.EAGAIN, errno.EACCES), 'writer-error')
        result = 'busy'
    except ValueError as error:
        require(str(error) == 'unsafe-migration-file', 'writer-error')
        result = 'stale-mode-refused'
    record(stage, {'writer': result})
    require(result == expected, 'writer-outcome:' + stage)


def held_readonly():
    """Inspect this worker's actual native lease descriptor, not a probe open."""
    named = LOCK.lstat()
    descriptors = []
    for entry in Path('/proc/self/fd').iterdir():
        try:
            descriptor = int(entry.name)
            opened = os.fstat(descriptor)
        except OSError:
            continue
        if (opened.st_dev, opened.st_ino) == (named.st_dev, named.st_ino):
            descriptors.append(descriptor)
    require(len(descriptors) == 1, 'held-descriptor')
    require(fcntl.fcntl(descriptors[0], fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY,
            'held-readonly')
    return {'device': named.st_dev, 'inode': named.st_ino, 'readonly': True}


def event(value):
    print(json.dumps(value, sort_keys=True), flush=True)


def retained_worker(service):
    """A real installed PAM transaction under the distro caller identity."""
    guest.guard()
    require(service in SERVICES, 'worker-service')
    root_uids(os.getpid())
    context = Path('/proc/self/attr/current').read_text().strip().rstrip('\0')
    if guest.package_path().suffix == '.rpm':
        require(context == caller_identity(service)[0], 'worker-context')
    pam = ctypes.CDLL('libpam.so.0')

    class Conversation(ctypes.Structure):
        _fields_ = [('conv', ctypes.c_void_p), ('data', ctypes.c_void_p)]

    pam.pam_start.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
                             ctypes.POINTER(Conversation), ctypes.POINTER(ctypes.c_void_p)]
    for name in ('pam_acct_mgmt', 'pam_open_session', 'pam_close_session', 'pam_end'):
        getattr(pam, name).argtypes = [ctypes.c_void_p, ctypes.c_int]
        getattr(pam, name).restype = ctypes.c_int
    handle, conversation = ctypes.c_void_p(), Conversation()
    require(pam.pam_start(service.encode(), b'oh-no-parent-control',
                         ctypes.byref(conversation), ctypes.byref(handle)) == 0, 'pam-start')
    opened = False
    try:
        require(pam.pam_acct_mgmt(handle, 0) == 0, 'retained-account')
        at_session = session_lease(service)
        if at_session:
            require(pam.pam_open_session(handle, 0) == 0, 'retained-session')
            opened = True
        event({'ready': True, 'pid': os.getpid(), 'service': service,
               'context': context, 'boundary': 'session' if at_session else 'account',
               **held_readonly()})
        operations = {'recheck': pam.pam_open_session if at_session else pam.pam_acct_mgmt,
                      'open': pam.pam_open_session,
                      'close': pam.pam_close_session}
        # Finite controller protocol, bounded even if the controller disappears.
        for _ in range(5):
            poll = select.poll()
            poll.register(0, select.POLLIN | select.POLLHUP)
            require(bool(poll.poll(120000)), 'worker-expired')
            command = sys.stdin.buffer.readline(32)
            if command == b'':
                break
            require(command.endswith(b'\n'), 'worker-command')
            command = command.decode().strip()
            require(command in operations, 'worker-command')
            status = operations[command](handle, 0)
            if command == 'open' and status == 0:
                opened = True
            if command == 'close' and status == 0:
                opened = False
            event({'operation': command, 'status': status, **held_readonly()})
        else:
            raise guest.GuestError('kiosk-lease:worker-command-bound')
    finally:
        try:
            if opened:
                require(pam.pam_close_session(handle, 0) == 0, 'cleanup-close')
        finally:
            ended = pam.pam_end(handle, 0)
    require(ended == 0, 'pam-end')
    event({'end': ended})


@contextmanager
def retained(service, record):
    with ExitStack() as stack:
        command = ['/usr/bin/python3', '-B']
        if guest.package_path().suffix == '.rpm':
            command = stack.enter_context(pam_caller_command(guest.PAYLOAD, service))
        child = subprocess.Popen([*command, str(Path(__file__).resolve()), 'retained', service],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, close_fds=True)
        pidfd = None
        try:
            pidfd = os.pidfd_open(child.pid)
            ready = lifecycle_event(child.stdout.fileno())
            require(ready.get('ready') is True and ready.get('pid') == child.pid
                    and ready.get('service') == service and ready.get('readonly') is True,
                    'worker-ready')
            require(ready.get('boundary') == ('session' if session_lease(service) else 'account'),
                    'worker-boundary')
            root_uids(child.pid)
            record(service + '.retained', ready)

            def operation(name, expected):
                child.stdin.write((name + '\n').encode())
                child.stdin.flush()
                result = lifecycle_event(child.stdout.fileno())
                record(service + '.' + name, result)
                require(result.get('operation') == name and result.get('status') == expected
                        and result.get('readonly') is True and
                        (result.get('device'), result.get('inode')) ==
                        (ready['device'], ready['inode']), 'retained-outcome')

            yield operation
            child.stdin.close()
            require(lifecycle_event(child.stdout.fileno()) == {'end': 0}, 'worker-end')
            require(child.wait(timeout=15) == 0, 'worker-exit')
        finally:
            try:
                child.stdin.close()
            except BrokenPipeError:
                pass
            try:
                try:
                    child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    if pidfd is None:
                        child.kill()  # Direct, unreaped child only.
                    else:
                        try:
                            signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    child.wait(timeout=15)
            finally:
                try:
                    child.stdout.close()
                finally:
                    if pidfd is not None:
                        os.close(pidfd)


def engineering(expectation):
    guest.guard()
    require(expectation in ('refusal', 'recovery'), 'expectation')
    guest.enable_diagnostics()
    account = pwd.getpwnam('oh-no-parent-control')
    wait_kiosk_inactive(account)
    owner = lifecycle()
    owner.account(owner.uid())
    require(not os.path.lexists(DISABLED), 'existing-removal-marker')
    # /run is cleared by the maintained prepared boot. Existing inodes cannot
    # be deleted to manufacture this control, even in an idle graphical seat.
    require(not os.path.lexists(LOCK), 'absent-precondition')
    results = []

    def record(stage, value):
        item = {'stage': stage, 'value': value}
        results.append(item)
        # Retain the actual boundary result even if the next assertion fails.
        print(json.dumps(item, sort_keys=True), file=sys.stderr, flush=True)

    probe('gdm-password', 'kiosk', 0, 'absent-new', record)
    fd = os.open(LOCK, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        baseline = identity(os.fstat(fd))
        require(stat.S_ISREG(baseline[5]) and baseline[2:5] == (0, 0, 1)
                and stat.S_IMODE(baseline[5]) == 0o600, 'lease-identity')
        current(fd, baseline)
        probe('gdm-password', 'kiosk', 0, 'healthy-existing', record)
        with held_account(record):
            writer('busy', record, 'account-excludes-writer')
        writer('acquired', record, 'account-released')
        with stale_mode(fd, repaired=expectation == 'recovery'):
            probe('gdm-password', 'kiosk', 6, 'stale-mode', record)
            writer('stale-mode-refused' if expectation == 'refusal' else 'acquired',
                   record, 'stale-writer')
            if expectation == 'recovery':
                current(fd, baseline)
                probe('gdm-password', 'kiosk', 0, 'writer-repaired', record)
        current(fd, baseline)
        for service in SERVICES:
            at_session = session_lease(service)
            with retained(service, record) as operation:
                writer('busy', record, service + '.admission-excludes-writer')
                with stale_mode(fd):
                    operation('recheck', 14 if at_session else 6)
                operation('recheck', 0)
                if not at_session:
                    operation('open', 0)
                operation('close', 0)
                writer('busy', record, service + '.close-excludes-writer')
            writer('acquired', record, service + '.end-released')
            current(fd, baseline)
        with owner.barriers():
            current(fd, baseline)
            probe('gdm-password', 'kiosk', 6, 'active-writer', record)
            # Non-kiosk accounts retain their actual installed account gate.
            probe('gdm-password', 'ordinary', 0, 'active-writer.ordinary', record)
        probe('gdm-password', 'kiosk', 0, 'writer-finished-fresh', record)
        current(fd, baseline)
        require(not os.path.lexists(DISABLED), 'unexpected-removal-marker')
    finally:
        os.close(fd)
    wait_kiosk_inactive(account)
    return {'qualified': True, 'expectation': expectation, 'restored': True,
            'controls': results, 'public_acceptance': False,
            'recovery_qualified': expectation == 'recovery'}


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'retained':
        retained_worker(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == 'engineering':
        event(engineering(sys.argv[2]))
    else:
        raise SystemExit('kiosk-lease:arguments')
