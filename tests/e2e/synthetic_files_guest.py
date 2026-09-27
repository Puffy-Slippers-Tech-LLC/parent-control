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
BOUNDARY_PROFILES = {
    'count': {f'Count {index}.txt': b'C' for index in range(1, 6)},
    'sixth': {'Count 6.txt': b'C'},
    'maximum': {'Maximum.txt': b'M' * (5 * 1024 * 1024)},
    'oversized': {'Oversized.txt': b'O' * (5 * 1024 * 1024 + 1)},
    'total': {'Total.txt': b'T' * (3 * 1024 * 1024)},
    'overflow': {'Overflow.txt': b'X' * (3 * 1024 * 1024 + 1)},
}


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


def snapshot(root, contents=CONTENTS):
    info = directory(root)
    require(stat.S_IMODE(info.st_mode) == 0o700)
    names = []
    with os.scandir(root) as entries:
        for entry in entries:
            names.append(entry.name)
            require(len(names) <= len(contents))
    names.sort()
    require(len(names) <= len(contents) and set(names) <= set(contents))
    result = {'directory': identity(info), 'files': {}}
    for name in names:
        path = root / name
        before = path.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
                and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == 0o600
                and before.st_size == len(contents[name]))
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            require(identity(os.fstat(fd)) == identity(before))
            chunks = []
            remaining = len(contents[name])
            while remaining:
                chunk = os.read(fd, min(remaining, 65536))
                require(chunk)
                chunks.append(chunk)
                remaining -= len(chunk)
            content = b''.join(chunks)
            require(content == contents[name] and os.read(fd, 1) == b'')
        finally:
            os.close(fd)
        require(identity(path.lstat()) == identity(before))
        result['files'][name] = {'identity': identity(before),
                                 'sha256': hashlib.sha256(content).hexdigest(),
                                 'size': len(content)}
    require(identity(root.lstat()) == identity(info))
    return result


def operate(home, operation, previous, profile='standard'):
    """Validate everything before the first mutation; failures never clean up."""
    require(operation in ('stage', 'read', 'copy', 'rename', 'cleanup', 'absent'))
    require(profile == 'standard' or profile in BOUNDARY_PROFILES)
    require(profile == 'standard' or operation not in ('copy', 'rename'))
    directory(home)
    # All shared invocations lock the existing home inode; no lock-file cleanup
    # or second writer can race a receipt validation against a mutation.
    fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(identity(os.fstat(fd)) == identity(home.lstat()))
        return _operate(home, operation, previous, profile)
    finally:
        os.close(fd)


def _operate(home, operation, previous, profile):
    root = home / (DIRECTORY + ('' if profile == 'standard' else '-' + profile))
    files = FILES if profile == 'standard' else BOUNDARY_PROFILES[profile]
    contents = CONTENTS if profile == 'standard' else files
    if operation == 'absent':
        require(previous == {'absent': True} and not os.path.lexists(root))
        return {'absent': True}
    if operation == 'stage':
        require(previous is None and not os.path.lexists(root))
        root.mkdir(mode=0o700)
        for name, content in files.items():
            fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                require(os.write(fd, content) == len(content))
                os.fsync(fd)
            finally:
                os.close(fd)
        return snapshot(root, contents)
    current = snapshot(root, contents)
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
    return snapshot(root, contents)


def main():
    import pwd
    require(len(sys.argv) in (3, 4))
    account = pwd.getpwnam('onpc-parent-jamie')
    require(os.getuid() == account.pw_uid and account.pw_dir == '/home/onpc-parent-jamie')
    require(len(sys.argv[2]) <= 4096)
    previous = json.loads(sys.argv[2])
    try:
        result = operate(Path(account.pw_dir), sys.argv[1], previous,
                         sys.argv[3] if len(sys.argv) == 4 else 'standard')
    except (ValueError, OSError):
        result = {'refused': True}
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
