"""Read the finite native files already installed by prepare-baseline."""
from contextlib import ExitStack, contextmanager
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import sys

from guest_files import identity, read_regular, require
if __name__ == '__main__':
    from native_assets import ASSETS, GUI_FILES, PREFIX, desktop_entry, desktop_id, sources
else:
    from tests.fixtures.native_assets import ASSETS, GUI_FILES, PREFIX, desktop_entry, desktop_id, sources
import session_control

LIMIT = 2 * 1024 * 1024
ROOT_DIRECTORY = Path('/')


@contextmanager
def directory(path, child):
    """Pin every ancestor, refuse links/writable or foreign parents, preserve existing dirs."""
    require(path.is_absolute() and '..' not in path.parts and path.is_relative_to(ROOT_DIRECTORY))
    with ExitStack() as stack:
        fd = os.open(ROOT_DIRECTORY, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, fd)
        root_info = os.fstat(fd)
        require(root_info.st_uid in (0, child.pw_uid) and not root_info.st_mode & 0o022)
        chain = []
        for part in path.relative_to(ROOT_DIRECTORY).parts:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            stack.callback(os.close, next_fd)
            info = os.fstat(next_fd)
            require(stat.S_ISDIR(info.st_mode) and info.st_uid in (0, child.pw_uid)
                    and not info.st_mode & 0o022)
            chain.append((fd, part, next_fd, (info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode)))
            fd = next_fd
        def guard():
            current_root = ROOT_DIRECTORY.lstat()
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


def destinations(child):
    launchers = Path(child.pw_dir) / '.local/share/applications'
    return {source: (Path(PREFIX) / Path(source).name, 0o755 if Path(source).name
                    not in GUI_FILES else 0o644) for source in sources()[:6]} | {
        source: (launchers / Path(source).name, 0o644) for source in sources()[6:]}


def authority():
    require(os.geteuid() == 0)
    parent = pwd.getpwnam(session_control.ACCOUNTS['parent'])
    child = pwd.getpwnam(session_control.ACCOUNTS['standard'])
    require(parent.pw_uid >= 1000 and child.pw_uid >= 1000 and parent.pw_uid != child.pw_uid
            and grp.getgrnam('sudo').gr_gid in os.getgrouplist(parent.pw_name, parent.pw_gid))
    source = session_control.source_session(session_control.sessions(), parent.pw_uid)
    return child, parent, source


def readback(child, expected):
    require(type(expected) is dict and set(expected) == set(sources())
            and all(type(value) is str and len(value) == 64
                    and all(c in '0123456789abcdef' for c in value) for value in expected.values())
            and len({expected[source] for source in sources()[:4]}) == 4)
    result = {}
    for source, (target, mode) in destinations(child).items():
        with directory(target.parent, child) as (fd, guard):
            data, info = read_regular(fd, target.name, owner=child.pw_uid, mode=mode, limit=LIMIT)
            require(info.st_gid == child.pw_gid and hashlib.sha256(data).hexdigest() == expected[source])
            guard()
        result[source] = {'identity': identity(info), 'sha256': expected[source], 'mode': mode}
    return {'files': result, 'launchers': [desktop_id(asset[0]) for asset in ASSETS]}


def execute(action, expected):
    require(action in ('read', 'refuse'))
    if action == 'refuse':
        try:
            authority()
        except session_control.SessionError as error:
            require(str(error) == 'session:source-owner')
            return {'wrong_entry_refused': True}
        raise ValueError('files:wrong-entry-accepted')
    child, parent, entry = authority()
    result = readback(child, expected)
    require(session_control.source_session(session_control.sessions(), parent.pw_uid) == entry)
    return result


if __name__ == '__main__':
    require(len(sys.argv) == 2)
    request = sys.stdin.buffer.read(8193)
    require(len(request) <= 8192)
    print(json.dumps(execute(sys.argv[1], json.loads(request)), sort_keys=True))
