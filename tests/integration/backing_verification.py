"""Attempt-local backing byte proofs protected by Linux read leases.

Only ext4 and tmpfs are admitted. Other filesystems retain full byte reads.
No proof survives release, failure, or a conflicting writer. Snapshot metadata,
the writable top image and durable baseline state remain Capture's responsibility.
"""

import copy
import errno
import fcntl
import os
from pathlib import Path
import signal
import stat

from prepare_host import CaptureError, canonical, identity, require


def metadata(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_uid, info.st_gid, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def open_backing(path):
    """Pin every parent; a path swap cannot introduce symlink traversal."""
    parent = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in path.parent.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                            | os.O_CLOEXEC, dir_fd=parent)
            os.close(parent)
            parent = child
        return os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                       | os.O_CLOEXEC, dir_fd=parent)
    finally:
        os.close(parent)


def fdinfo(fd):
    # Inspect only this controller's explicitly retained descriptor.
    return Path(f'/proc/self/fdinfo/{fd}').read_text().splitlines()


def supported_filesystem(fd):
    """Match the opened file's mount ID, never a path-prefix guess."""
    mounts = [line.split()[1] for line in fdinfo(fd) if line.startswith('mnt_id:')]
    if len(mounts) != 1:
        return False
    info = os.fstat(fd)
    device = f'{os.major(info.st_dev)}:{os.minor(info.st_dev)}'
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        before, separator, after = line.partition(' - ')
        fields = before.split()
        if separator and len(fields) >= 6 and fields[0] == mounts[0]:
            return fields[2] == device and after.split()[0] in ('ext4', 'tmpfs')
    return False


class BackingVerification:
    """A one-shot byte proof; F_GETLEASE is authoritative, never signal timing.

    F_SETLEASE rejects existing writable opens (including retained writable
    mappings). A new conflicting open/truncate marks the read lease breaking
    before allowing writes. F_GETLEASE then reports F_UNLCK, even if the writer
    cancels or the break deadline expires. We never renew a lease.

    SIGURG's default disposition is ignore. Request it instead of fatal SIGIO;
    install no handler, change no disposition and depend on no delivery race.
    An application using SIGURG retains full verification instead.
    """

    def __init__(self, capture, owner):
        self.capture, self.owner = capture, owner
        self.state = copy.deepcopy(capture.state)
        self.pid, self.lock_fd = os.getpid(), owner.fd
        self.run = owner.backing_run
        self.lock_identity = identity(capture.lock_path, private=True, mode=0o600)
        self.files = []
        self.enabled = False
        self.verified = False
        self.closed = False
        self.failure = None
        self.ownership_failure = None
        self.fallback = None

    def check_owner(self):
        if self.ownership_failure is not None:
            raise self.ownership_failure
        try:
            self._check_owner()
        except BaseException as error:
            self.ownership_failure = error
            self.remember(error)
            raise

    def _check_owner(self):
        require(os.getpid() == self.pid
                and self.owner.capture is self.capture
                and self.capture.backing_verification is self
                and self.owner.fd == self.lock_fd
                and self.owner.commands.lock_fd == self.lock_fd
                and self.owner.backing_run == self.run
                and (self.owner.state is None or self.owner.state['run'] == self.run),
                'guard:backing-owner-changed')
        require(self.capture.state == self.state, 'guard:backing-state-changed')
        lock = self.capture.lock_path
        require(identity(lock, private=True, mode=0o600) == self.lock_identity,
                'guard:backing-owner-changed')
        info = os.fstat(self.lock_fd)
        require((info.st_dev, info.st_ino) ==
                (self.lock_identity['device'], self.lock_identity['inode']),
                'guard:backing-owner-changed')
        expected = ['FLOCK', 'ADVISORY', 'WRITE', str(self.pid),
                    f'{os.major(info.st_dev):02x}:{os.minor(info.st_dev):02x}:{info.st_ino}',
                    '0', 'EOF']
        # fdinfo reports locks belonging to this open file description. A
        # different controller locking the same inode cannot satisfy this.
        require(any(line.split()[2:] == expected for line in fdinfo(self.lock_fd)
                    if line.startswith('lock:')), 'guard:backing-owner-changed')

    def remember(self, error):
        if self.failure is None:
            self.failure = error if isinstance(error, (CaptureError, KeyboardInterrupt)) else (
                CaptureError('guard:backing-verification-failed'))

    def check(self):
        if self.failure is not None:
            raise self.failure
        try:
            require(not self.closed, 'guard:backing-owner-changed')
            self.check_owner()
            for path, fd, pinned in self.files:
                require(fcntl.fcntl(fd, fcntl.F_GETLEASE) == fcntl.F_RDLCK,
                        'guard:backing-lease-broken')
                require(metadata(os.fstat(fd)) == pinned and
                        metadata(canonical(path).lstat()) == pinned,
                        'guard:backing-file-changed')
                require(fcntl.fcntl(fd, fcntl.F_GETLEASE) == fcntl.F_RDLCK,
                        'guard:backing-lease-broken')
        except BaseException as error:
            self.remember(error)
            raise

    def acquire(self):
        """Try once before hashing. Unsupported/conflicting opens use full reads."""
        self.check()
        if signal.getsignal(signal.SIGURG) not in (signal.SIG_DFL, signal.SIG_IGN):
            self.fallback = 'signal-in-use'
            return
        try:
            for item in self.state['source']['chain'][1:]:
                path = canonical(item['path'])
                info = path.lstat()
                require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                        and (info.st_dev, info.st_ino) == (item['device'], item['inode']),
                        'guard:backing-file-changed')
                fd = open_backing(path)
                retained = False
                try:
                    require(metadata(os.fstat(fd)) == metadata(info), 'guard:backing-file-changed')
                    if not supported_filesystem(fd):
                        self.fallback = 'filesystem'
                        break
                    try:
                        fcntl.fcntl(fd, fcntl.F_SETSIG, signal.SIGURG)
                        fcntl.fcntl(fd, fcntl.F_SETLEASE, fcntl.F_RDLCK)
                    except OSError as error:
                        if error.errno not in (errno.EAGAIN, errno.EACCES, errno.EPERM,
                                               errno.EINVAL, errno.ENOSYS, errno.EOPNOTSUPP):
                            raise
                        self.fallback = 'lease-unavailable'
                        break
                    self.files.append((path, fd, metadata(info)))
                    retained = True
                finally:
                    if not retained:
                        os.close(fd)
            self.check()
            if self.fallback is not None:
                self._close_files()
                return
            self.enabled = True
        except BaseException as error:
            self.remember(error)
            raise

    def verify(self, capture, count_bytes, *, force_bytes=False):
        require(capture is self.capture, 'guard:backing-owner-changed')
        self.check()
        if not self.enabled:
            return False
        try:
            if force_bytes or not self.verified:
                import hashlib
                for index, (_path, fd, _pinned) in enumerate(self.files, start=1):
                    content = hashlib.sha256()
                    os.lseek(fd, 0, os.SEEK_SET)
                    while block := os.read(fd, 1024 * 1024):
                        count_bytes(len(block))
                        content.update(block)
                    require(content.hexdigest() == self.state['source_digests'][index],
                            'guard:backing-digest-changed')
                self.check()
                self.verified = True
            return True
        except BaseException as error:
            self.remember(error)
            raise

    def _close_files(self):
        pending = None
        files, self.files = self.files, []
        for _path, fd, _pinned in reversed(files):
            try:
                # Descriptors are CLOEXEC and are never passed to children.
                # Closing releases the lease; never retry close on a reused fd.
                os.close(fd)
            except BaseException as error:
                pending = pending if pending is not None else error
        if pending is not None:
            raise pending

    def close(self):
        if self.closed:
            return
        pending = None
        try:
            self.check()
        except BaseException as error:
            pending = error
        finally:
            self.closed = True
            try:
                self._close_files()
            except BaseException as error:
                self.remember(error)
                pending = pending if pending is not None else error
        if pending is not None:
            raise pending
