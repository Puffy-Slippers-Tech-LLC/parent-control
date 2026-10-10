"""Read the finite native files already installed by prepare-vm."""
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
            and grp.getgrnam(session_control.administrator_group()).gr_gid
            in os.getgrouplist(parent.pw_name, parent.pw_gid))
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


def product_tree(g, path, parent):
    """Bounded read-only preservation witness for installed product directories.

    Pin directories and regular files without following links. Contents stay
    private: only this in-memory witness is compared, never sent as evidence.
    """
    require(g.realpath(path) == path)
    before = g.lstatns(path)
    count, size = 0, 0

    def visit(parent, name, depth):
        nonlocal count, size
        count += 1
        require(count <= 256 and depth <= 8)
        info = os.stat(name, dir_fd=parent, follow_symlinks=False)
        require(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK |
                     (os.O_DIRECTORY if stat.S_ISDIR(info.st_mode) else 0), dir_fd=parent)
        with ExitStack() as stack:
            stack.callback(os.close, fd)
            require(os.fstat(fd) == info)
            if stat.S_ISDIR(info.st_mode):
                names = sorted(os.listdir(fd))
                require(len(names) <= 256)
                value = {name: visit(fd, name, depth + 1) for name in names}
                require(sorted(os.listdir(fd)) == names)
            else:
                require(info.st_nlink == 1 and info.st_size <= LIMIT - size)
                stream = stack.enter_context(os.fdopen(fd, 'rb', closefd=False))
                data = stream.read(LIMIT - size + 1)
                size += len(data)
                require(size <= LIMIT)
                value = hashlib.sha256(data).hexdigest()
            # Reading can change atime; all identity, content and write clocks
            # remain exact at both the descriptor and directory entry.
            signature = lambda item: (identity(item), item.st_nlink)
            require(signature(os.fstat(fd)) == signature(info)
                    and signature(os.stat(name, dir_fd=parent, follow_symlinks=False)) == signature(info))
            return signature(info), value

    with directory(g.path(path).parent, parent) as (fd, guard):
        result = visit(fd, g.path(path).name, 0)
        guard()
    require(g.lstatns(path) == before and g.realpath(path) == path)
    return result


def execute(action, expected, profile='native'):
    require(action in ('read', 'refuse'))
    require(profile in ('native', 'chinese'))
    if action == 'refuse':
        try:
            authority()
        except session_control.SessionError as error:
            require(str(error) == 'session:source-owner')
            return {'wrong_entry_refused': True}
        raise ValueError('files:wrong-entry-accepted')
    child, parent, entry = authority()
    if profile == 'chinese':
        require(expected == {})
        from chinese_language_assets import LocalFiles, read, verify
        g = LocalFiles()
        def state():
            # Engineering preservation proof only. No product probe supplies
            # a customer result; absent baseline and installed state both stay unchanged.
            paths = ['/var/lib/AccountsService/users/' + name for name in session_control.ACCOUNTS.values()]
            paths += ['/etc/default/locale', '/etc/locale.conf',
                      '/var/lib/oh-no-parent-control', '/etc/oh-no-parent-control']
            result = {}
            for path in paths:
                if not g.exists(path) and not g.is_symlink(path):
                    result[path] = None
                    continue
                before = g.lstatns(path)
                if path in ('/var/lib/oh-no-parent-control', '/etc/oh-no-parent-control'):
                    require(stat.S_ISDIR(before['st_mode']))
                    result[path] = product_tree(g, path, parent)
                    continue
                if path == '/etc/default/locale' and g.is_symlink(path):
                    # Ubuntu's compatibility link is preserved as a link. Read
                    # only its fixed canonical destination with the no-link
                    # reader; unexpected or dangling destinations still refuse.
                    require(before['st_uid'] == before['st_gid'] == 0
                            and g.realpath(path) == '/etc/locale.conf')
                    data = read(g, '/etc/locale.conf', 64 * 1024)
                    require(g.realpath(path) == '/etc/locale.conf')
                else:
                    data = g.read_file(path)
                require(g.lstatns(path) == before)
                result[path] = (before, hashlib.sha256(data).hexdigest())
            return result
        before = state()
        # The shared oracle pins the canonical release and platform-specific
        # package/file identity; /etc/os-release remains a compatibility link.
        result = verify(g)
        require(state() == before)
        result.update(unchanged_state=True)
    else:
        result = readback(child, expected)
    require(session_control.source_session(session_control.sessions(), parent.pw_uid) == entry)
    return result


if __name__ == '__main__':
    require(len(sys.argv) == 3)
    request = sys.stdin.buffer.read(8193)
    require(len(request) <= 8192)
    print(json.dumps(execute(sys.argv[1], json.loads(request), sys.argv[2]), sort_keys=True))
