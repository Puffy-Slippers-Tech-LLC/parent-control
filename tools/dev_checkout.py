"""Resolve the invoking repository before privileged checkout code is loaded.

The installer embeds this standard-library-only code in the root-owned helpers.
Polkit authorizes the caller; repository markers do not confer authorization.
"""
import os
from pathlib import Path
import grp
import pwd
import stat
import atexit
import ctypes
import fcntl
import json


_REMOTE_SCRATCH_FDS = []


def pin_remote_scratch(root, uid):
    """Keep transferred sources alive across pkexec's descriptor clearing.

    The already authenticated helper duplicates its caller's existing scratch
    open description. It does not open a pathname to manufacture ownership.
    The ordinary scratch allocator therefore sees the same lifetime lock even
    if an SSH receiver or its unprivileged worker exits unexpectedly.
    """
    if os.geteuid() != 0:
        return
    try:
        marker = os.open(root / '.onpc-remote-source.json',
                         os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return
    with os.fdopen(marker) as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o400 or info.st_size > 4096):
            raise ValueError('test-runner:unsafe-remote-source-receipt')
        origin = json.load(stream)
    anchor = Path(origin['storage_root'])
    scratch = anchor / 'output/test-runs/host/scratch'
    owners = [part for part in root.parents if part.parent == scratch
              and part.name.startswith('run-')]
    if len(owners) != 1:
        raise ValueError('test-runner:remote-source-outside-owned-scratch')
    expected = (owners[0] / 'owner').stat(follow_symlinks=False)
    if (not stat.S_ISREG(expected.st_mode) or expected.st_uid != uid
            or stat.S_IMODE(expected.st_mode) != 0o600 or expected.st_nlink != 1):
        raise ValueError('test-runner:unsafe-remote-scratch-owner')
    libc = ctypes.CDLL(None, use_errno=True)
    duplicate = getattr(libc, 'pidfd_getfd', None)
    if duplicate is None:
        raise ValueError('test-runner:remote-source-needs-pidfd-getfd')
    duplicate.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_uint)
    duplicate.restype = ctypes.c_int
    parent = os.getppid()
    process = os.pidfd_open(parent)
    proc = os.open('/proc/' + str(parent), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    descriptors = None
    try:
        def authenticate():
            status = os.open('status', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=proc)
            with os.fdopen(status) as stream:
                users = next((line.split()[1:] for line in stream if line.startswith('Uid:')), [])
            # A fixed dispatcher may spawn another privileged consumer. Its
            # root parent can forward the same caller-owned open description.
            if users not in ([str(uid)] * 4, ['0'] * 4):
                raise ValueError('test-runner:remote-source-parent-is-not-caller')
        authenticate()
        descriptors = os.open('fd', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=proc)
        names = os.listdir(descriptors)
        if len(names) > 4096:
            raise ValueError('test-runner:too-many-caller-descriptors')
        for name in names:
            if not name.isdecimal():
                continue
            try:
                actual = os.stat(name, dir_fd=descriptors)
            except FileNotFoundError:
                continue
            if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
                continue
            fd = duplicate(process, int(name), 0)
            if fd < 0:
                raise ValueError('test-runner:cannot-pin-remote-source: '
                                 + os.strerror(ctypes.get_errno()))
            try:
                authenticate()
                current = os.fstat(fd)
                if ((current.st_dev, current.st_ino) != (expected.st_dev, expected.st_ino)
                        or os.getppid() != parent):
                    raise ValueError('test-runner:remote-source-parent-changed')
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue
                _REMOTE_SCRATCH_FDS.append(fd)
                atexit.register(os.close, fd)
                fd = None
                return
            finally:
                if fd is not None:
                    os.close(fd)
        raise ValueError('test-runner:caller-has-no-remote-source-lease')
    finally:
        if descriptors is not None:
            os.close(descriptors)
        os.close(proc)
        os.close(process)


def checkout_root():
    root = Path.cwd()
    uid = int(os.environ.get('PKEXEC_UID', str(os.getuid())))
    try:
        allowed_users = {pwd.getpwuid(uid).pw_name, 'root'}
    except KeyError as error:
        raise ValueError('test-runner:unknown-repository-caller') from error
    groups = {}

    def safe(info):
        if info.st_uid not in (0, uid) or info.st_mode & 0o002:
            return False
        if info.st_mode & 0o020:
            if info.st_gid not in groups:
                # Ubuntu's private user groups commonly own mode-775 checkouts.
                # A writable group must not admit any unrelated account, through
                # either primary or supplementary membership.
                members = set(grp.getgrgid(info.st_gid).gr_mem)
                members.update(user.pw_name for user in pwd.getpwall()
                               if user.pw_gid == info.st_gid)
                groups[info.st_gid] = members <= allowed_users
            return groups[info.st_gid]
        return True
    markers = ('setup.sh', 'Makefile', 'tools/onpc-test-runner',
               'tools/install_test_runner.py', 'config/com.puffyslippers.onpc.development.policy')
    try:
        for relative in ('', *markers):
            path = root / relative
            for part in (path, *path.parents):
                if part.is_symlink():
                    raise ValueError('test-runner:unsafe-repository-path')
                info = part.stat()
                if not safe(info):
                    raise ValueError('test-runner:unsafe-repository-path')
                if part == root:
                    break
            info = path.stat()
            if not (stat.S_ISREG(info.st_mode) if relative else stat.S_ISDIR(info.st_mode)):
                raise ValueError('test-runner:unsafe-repository-path')
    except (OSError, KeyError) as error:
        raise ValueError('test-runner:invoke-from-repository-root-with-keep-cwd') from error
    pin_remote_scratch(root, uid)
    return root
