"""One account-bound synthetic work document; shared by fixture and FILE08/09.

Receipts pin the directory and inode. Each distinct save changes that inode;
reopening requires the independently collected, updated receipt.
"""
import fcntl
import hashlib
import os
from pathlib import Path
import pwd
import stat

from guest_files import identity, read_regular, require, write_exclusive

DIRECTORY = 'ONPC synthetic work'
NAME = 'Work.txt'
USERS = ('onpc-child-jordan', 'onpc-child-riley')
INITIAL = {user: user.rsplit('-', 1)[1].title() + ' original synthetic work' for user in USERS}
SAVED = {user: user.rsplit('-', 1)[1].title() + ' saved synthetic work' for user in USERS}
JORDAN_TEXTS = ('homework cycle 1', 'work again cycle 1',
                'homework cycle 2', 'work again cycle 2')


def saved_texts(user):
    return (SAVED[user], *(JORDAN_TEXTS if user == USERS[0] else ()))


def account_home(user):
    require(user in USERS)
    account = pwd.getpwnam(user)
    require(os.getuid() == os.geteuid() == account.pw_uid
            and account.pw_dir == '/home/' + user)
    return Path(account.pw_dir)


class Document:
    def __init__(self, user, receipt):
        home = account_home(user)  # Reject another account before opening files.
        require(type(receipt) is dict and set(receipt) == {'user', 'directory', 'file', 'sha256', 'size'}
                and receipt['user'] == user)
        self.user, self.receipt = user, receipt
        self.attempted, self.failed = set(), False
        self.home_fd = self.root_fd = None
        try:
            self.home_fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            require(identity(os.fstat(self.home_fd)) == identity(home.lstat())
                    and os.fstat(self.home_fd).st_uid == os.getuid()
                    and not os.fstat(self.home_fd).st_mode & 0o022)
            self.root_fd = os.open(DIRECTORY, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                   dir_fd=self.home_fd)
            self.read()
        except BaseException:
            self.close()
            raise

    def read(self, *, changed=False):
        root = os.fstat(self.root_fd)
        require(identity(root)[:5] == self.receipt['directory']
                and root.st_uid == os.getuid() and stat.S_IMODE(root.st_mode) == 0o700
                and identity(os.stat(DIRECTORY, dir_fd=self.home_fd, follow_symlinks=False))[:5]
                    == self.receipt['directory']
                and os.listdir(self.root_fd) == [NAME])
        data, info = read_regular(self.root_fd, NAME, owner=os.getuid(), mode=0o600, limit=256)
        require(identity(info)[:5] == self.receipt['file'][:5])
        text = data.decode('utf-8')
        require(text in (INITIAL[self.user], *saved_texts(self.user)))
        result = {'user': self.user, 'directory': identity(root)[:5], 'file': identity(info),
                  'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}
        require(changed or result == self.receipt)
        return text, result

    def save(self, text):
        require(not self.failed and text in saved_texts(self.user) and text not in self.attempted)
        self.attempted.add(text)
        self.failed = True  # An interrupted or uncertain write cannot be replayed.
        fcntl.flock(self.root_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            previous, _receipt = self.read()
            require(text != previous)
            fd = os.open(NAME, os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.root_fd)
            try:
                require(identity(os.fstat(fd)) == self.receipt['file'])
                data = text.encode('utf-8')
                require(os.write(fd, data) == len(data))
                os.ftruncate(fd, len(data))
                os.fsync(fd)
            finally:
                os.close(fd)
            actual, receipt = self.read(changed=True)
            require(actual == text)
            self.receipt = receipt
            self.failed = False
        finally:
            fcntl.flock(self.root_fd, fcntl.LOCK_UN)

    def close(self):
        for name in ('root_fd', 'home_fd'):
            fd = getattr(self, name, None)
            if fd is not None:
                os.close(fd)
                setattr(self, name, None)


def operate(user, operation, receipt):
    home = account_home(user)
    require(operation in ('stage', 'read', 'saved', 'cleanup', 'absent'))
    root = home / DIRECTORY
    if operation == 'absent':
        require(receipt == {'absent': True} and not os.path.lexists(root))
        return receipt
    if operation == 'stage':
        require(receipt is None and not os.path.lexists(root))
        parent = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            require(os.fstat(parent).st_uid == os.getuid()
                    and not os.fstat(parent).st_mode & 0o022)
            os.mkdir(DIRECTORY, mode=0o700, dir_fd=parent)
            fd = os.open(DIRECTORY, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            try:
                write_exclusive(fd, NAME, INITIAL[user].encode(), owner=os.getuid(),
                                group=os.getgid(), mode=0o600)
                data, info = read_regular(fd, NAME, owner=os.getuid(), mode=0o600, limit=256)
                return {'user': user, 'directory': identity(os.fstat(fd))[:5], 'file': identity(info),
                        'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}
            finally:
                os.close(fd)
        finally:
            os.close(parent)
    # Saved readback permits changed bytes, never a replaced inode or directory.
    if operation == 'saved':
        text = SAVED[user]
        if type(receipt) is dict and set(receipt) == {'previous', 'text'}:
            text, receipt = receipt['text'], receipt['previous']
        require(text in saved_texts(user))
        require(type(receipt) is dict and receipt.get('user') == user)
        digest = hashlib.sha256(text.encode()).hexdigest()
        require(receipt['sha256'] != digest)
        expected = {**receipt, 'sha256': digest, 'size': len(text.encode())}
        # Recover the current timestamps only after checking the original inode.
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            require(identity(os.fstat(fd))[:5] == receipt['directory'])
            _data, info = read_regular(fd, NAME, owner=os.getuid(), mode=0o600, limit=256)
            require(identity(info)[:5] == receipt['file'][:5])
            expected['file'] = identity(info)
        finally:
            os.close(fd)
        receipt = expected
    document = Document(user, receipt)
    try:
        _text, current = document.read()
        if operation == 'cleanup':
            os.unlink(NAME, dir_fd=document.root_fd)
            os.rmdir(DIRECTORY, dir_fd=document.home_fd)
            return {'absent': True}
        return current
    finally:
        document.close()
