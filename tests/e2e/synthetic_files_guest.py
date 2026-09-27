"""Finite synthetic attachment fixture operations; executed as the fixture user.

No caller-supplied paths or bytes. The controller carries the previous exact
directory/file identity receipt. Unknown or replaced objects refuse all writes,
including cleanup. Guest storage belongs to the disposable fixture home.
"""
import hashlib
import fcntl
import json
import os
from pathlib import Path
import stat
import sys

DIRECTORY = '.onpc-e2e-synthetic-files'
FILES = {'Synthetic note.txt': b'ONPC synthetic attachment\n',
         'Second note.txt': b'ONPC second synthetic attachment\n'}
COPY = 'Synthetic copy.txt'
RENAMED = 'Renamed synthetic note.txt'
CONTENTS = {**FILES, COPY: FILES['Synthetic note.txt'],
            RENAMED: FILES['Synthetic note.txt']}


def require(value):
    if not value:
        raise ValueError('files:refused')


def identity(info):
    return [info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def directory(path):
    require(path.is_absolute() and path.resolve() == path)
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
            and not info.st_mode & 0o022)
    return info


def snapshot(root):
    info = directory(root)
    require(stat.S_IMODE(info.st_mode) == 0o700)
    names = []
    with os.scandir(root) as entries:
        for entry in entries:
            names.append(entry.name)
            require(len(names) <= len(CONTENTS))
    names.sort()
    require(len(names) <= len(CONTENTS) and set(names) <= set(CONTENTS))
    result = {'directory': identity(info), 'files': {}}
    for name in names:
        path = root / name
        before = path.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
                and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == 0o600
                and before.st_size == len(CONTENTS[name]))
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            require(identity(os.fstat(fd)) == identity(before))
            content = os.read(fd, 1024)
            require(content == CONTENTS[name] and os.read(fd, 1) == b'')
        finally:
            os.close(fd)
        require(identity(path.lstat()) == identity(before))
        result['files'][name] = {'identity': identity(before),
                                 'sha256': hashlib.sha256(content).hexdigest(),
                                 'size': len(content)}
    require(identity(root.lstat()) == identity(info))
    return result


def operate(home, operation, previous):
    """Validate everything before the first mutation; failures never clean up."""
    require(operation in ('stage', 'read', 'copy', 'rename', 'cleanup', 'absent'))
    directory(home)
    # All shared invocations lock the existing home inode; no lock-file cleanup
    # or second writer can race a receipt validation against a mutation.
    fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(identity(os.fstat(fd)) == identity(home.lstat()))
        return _operate(home, operation, previous)
    finally:
        os.close(fd)


def _operate(home, operation, previous):
    root = home / DIRECTORY
    if operation == 'absent':
        require(previous == {'absent': True} and not os.path.lexists(root))
        return {'absent': True}
    if operation == 'stage':
        require(previous is None and not os.path.lexists(root))
        root.mkdir(mode=0o700)
        for name, content in FILES.items():
            fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                require(os.write(fd, content) == len(content))
                os.fsync(fd)
            finally:
                os.close(fd)
        return snapshot(root)
    current = snapshot(root)
    require(type(previous) is dict and current == previous)
    names = set(current['files'])
    if operation == 'copy':
        require(names == set(FILES))
        source = os.open(root / 'Synthetic note.txt', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            require(identity(os.fstat(source)) == current['files']['Synthetic note.txt']['identity'])
            content = os.read(source, 1024)
            require(content == CONTENTS[COPY])
        finally:
            os.close(source)
        # O_EXCL forbids clobbering even if a destination appears after validation.
        fd = os.open(root / COPY, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            require(os.write(fd, content) == len(content))
            os.fsync(fd)
        finally:
            os.close(fd)
    elif operation == 'rename':
        require(names == {*FILES, COPY})
        # Hard-link + unlink is a no-clobber rename on this single filesystem.
        os.link(root / COPY, root / RENAMED, follow_symlinks=False)
        os.unlink(root / COPY)
    elif operation == 'cleanup':
        for name in names:
            os.unlink(root / name)
        root.rmdir()
        return {'absent': not os.path.lexists(root)}
    return snapshot(root)


def main():
    import pwd
    require(len(sys.argv) == 3)
    account = pwd.getpwnam('onpc-parent-jamie')
    require(os.getuid() == account.pw_uid and account.pw_dir == '/home/onpc-parent-jamie')
    require(len(sys.argv[2]) <= 4096)
    previous = json.loads(sys.argv[2])
    try:
        result = operate(Path(account.pw_dir), sys.argv[1], previous)
    except (ValueError, OSError):
        result = {'refused': True}
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
