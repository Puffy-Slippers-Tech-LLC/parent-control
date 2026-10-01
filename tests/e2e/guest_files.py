"""Descriptor-pinned bounded file primitives for finite guest fixture helpers.

Callers own finite paths, owner/mode expectations and lifetime receipts.
"""
import os
import stat


def require(value):
    if not value:
        raise ValueError('files:refused')


def identity(info):
    return [info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def read_regular(parent, name, *, owner, mode, limit):
    before = os.stat(name, dir_fd=parent, follow_symlinks=False)
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
            and before.st_uid == owner and stat.S_IMODE(before.st_mode) == mode
            and 0 < before.st_size <= limit)
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    try:
        require(identity(os.fstat(fd)) == identity(before))
        chunks, remaining = [], before.st_size
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            require(chunk)
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(fd, 1) == b'' and identity(os.fstat(fd)) == identity(before)
                and identity(os.stat(name, dir_fd=parent, follow_symlinks=False)) == identity(before))
        return b''.join(chunks), before
    finally:
        os.close(fd)


def write_exclusive(parent, name, content, *, owner, group, mode):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode,
                 dir_fd=parent)
    try:
        os.fchown(fd, owner, group)
        os.fchmod(fd, mode)
        view = memoryview(content)
        while view:
            written = os.write(fd, view)
            require(written > 0)
            view = view[written:]
        os.fsync(fd)
        require(identity(os.fstat(fd)) == identity(
            os.stat(name, dir_fd=parent, follow_symlinks=False)))
    finally:
        os.close(fd)
