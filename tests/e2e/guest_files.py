"""Descriptor-pinned bounded file primitives for finite guest fixture helpers.

Callers own finite paths, owner/mode expectations and lifetime receipts.
"""
from contextlib import ExitStack, contextmanager
import grp
import os
from pathlib import Path
import pwd
import stat


def require(value):
    if not value:
        raise ValueError('files:refused')


def identity(info):
    return [info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns]


@contextmanager
def directory(path, child, *, private_group=False):
    """Pin safe ancestors; optionally accept the child's exclusive writable group."""
    root = Path('/')
    require(path.is_absolute() and '..' not in path.parts and path.is_relative_to(root))
    if private_group:
        require(set(grp.getgrgid(child.pw_gid).gr_mem) <= {child.pw_name}
                and {p.pw_name for p in pwd.getpwall() if p.pw_gid == child.pw_gid}
                == {child.pw_name})

    def safe(info):
        return (stat.S_ISDIR(info.st_mode) and info.st_uid in (0, child.pw_uid)
                and not info.st_mode & 0o002
                and (not info.st_mode & 0o020 or private_group
                     and info.st_uid == child.pw_uid and info.st_gid == child.pw_gid))

    with ExitStack() as stack:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, fd)
        root_info = os.fstat(fd)
        require(safe(root_info))
        chain = []
        for part in path.relative_to(root).parts:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            stack.callback(os.close, next_fd)
            info = os.fstat(next_fd)
            require(safe(info))
            chain.append((fd, part, next_fd,
                          (info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode)))
            fd = next_fd

        def guard():
            current_root = root.lstat()
            require((current_root.st_dev, current_root.st_ino, current_root.st_mode,
                     current_root.st_uid, current_root.st_gid) ==
                    (root_info.st_dev, root_info.st_ino, root_info.st_mode,
                     root_info.st_uid, root_info.st_gid))
            for parent, name, pinned, expected in chain:
                for current in (os.fstat(pinned), os.stat(name, dir_fd=parent, follow_symlinks=False)):
                    require((current.st_dev, current.st_ino, current.st_uid, current.st_gid,
                             current.st_mode) == expected)
        guard()
        yield fd, guard
        guard()


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
