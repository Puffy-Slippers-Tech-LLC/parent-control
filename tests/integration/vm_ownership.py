"""Attempt-local VM ownership and disk identity checks; never read image contents."""

import copy
import os
from pathlib import Path

from prepare_baseline import CaptureError, identity, require


def fdinfo(fd):
    # Inspect only this controller's explicitly retained descriptor.
    return Path(f'/proc/self/fdinfo/{fd}').read_text().splitlines()


class VMOwnership:
    """Attest the exact held controller lock, run, state and disk identities."""

    def __init__(self, capture, owner):
        self.capture, self.owner = capture, owner
        self.state = copy.deepcopy(capture.state)
        self.pid, self.lock_fd = os.getpid(), owner.fd
        self.run = owner.ownership_run
        self.lock_identity = identity(capture.lock_path, private=True, mode=0o600)
        self.closed = False
        self.failure = None
        self.ownership_failure = None

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
                and self.capture.vm_ownership is self
                and self.owner.fd == self.lock_fd
                and self.owner.commands.lock_fd == self.lock_fd
                and self.owner.ownership_run == self.run
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
            for item in self.state['source']['chain']:
                require(identity(item['path']) ==
                        {key: item[key] for key in ('path', 'device', 'inode')},
                        'guard:backing-file-changed')
        except BaseException as error:
            self.remember(error)
            raise

    def close(self):
        if self.closed:
            return
        try:
            self.check()
        finally:
            self.closed = True
