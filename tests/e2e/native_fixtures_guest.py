"""One finite native payload placement; only the disposable VM owns cleanup."""
from contextlib import ExitStack, contextmanager
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import sys

from guest_files import identity, read_regular, require, write_exclusive
if __name__ == '__main__':
    from native_assets import ASSETS, GUI_FILES, PREFIX, desktop_entry, desktop_id, sources
else:
    from tests.fixtures.native_assets import ASSETS, GUI_FILES, PREFIX, desktop_entry, desktop_id, sources
import session_control

SOURCE = Path('/var/lib/onpc-e2e-assets')
MARKER = Path('/var/lib/onpc-e2e-native-fixtures-used')
LIMIT = 2 * 1024 * 1024
ROOT_DIRECTORY = Path('/')


@contextmanager
def directory(path, child, *, create=False):
    """Pin every ancestor, refuse links/writable or foreign parents, preserve existing dirs."""
    require(path.is_absolute() and '..' not in path.parts and path.is_relative_to(ROOT_DIRECTORY))
    with ExitStack() as stack:
        fd = os.open(ROOT_DIRECTORY, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, fd)
        root_info = os.fstat(fd)
        require(root_info.st_uid in (0, child.pw_uid) and not root_info.st_mode & 0o022)
        chain = []
        for part in path.relative_to(ROOT_DIRECTORY).parts:
            try:
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, 0o755, dir_fd=fd)
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.fchown(next_fd, child.pw_uid, child.pw_gid)
                os.fchmod(next_fd, 0o755)
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


def read_payload(child, expected):
    require(type(expected) is dict and set(expected) == set(sources())
            and all(type(value) is str and len(value) == 64
                    and all(c in '0123456789abcdef' for c in value) for value in expected.values()))
    content = {}
    for source in sources():
        path = SOURCE / source
        with directory(path.parent, child) as (fd, guard):
            data, info = read_regular(fd, path.name, owner=0, mode=0o644, limit=LIMIT)
            guard()
        require(hashlib.sha256(data).hexdigest() == expected[source])
        content[source] = data
    require(len({expected[source] for source in sources()[:4]}) == 4)
    for asset in ASSETS:
        require(content['fixtures/native-launchers/' + desktop_id(asset[0])] ==
                desktop_entry(asset).encode())
    return content


def preflight(child, mapping):
    require(not os.path.lexists(Path(PREFIX).parent) and not os.path.lexists(MARKER))
    for target, mode in mapping.values():
        require(not os.path.lexists(target))
        # Validate every existing ancestor before creating anything.
        ancestor = target.parent
        while not os.path.lexists(ancestor):
            ancestor = ancestor.parent
        with directory(ancestor, child):
            pass
    with directory(Path(child.pw_dir), child) as (fd, guard):
        require(os.fstat(fd).st_uid == child.pw_uid)
    with marker_directory(child):
        pass


@contextmanager
def marker_directory(child):
    with directory(MARKER.parent, child) as (fd, guard):
        require(os.fstat(fd).st_uid == 0)
        yield fd, guard


def readback(child, expected):
    result = {}
    for source, (target, mode) in destinations(child).items():
        with directory(target.parent, child) as (fd, guard):
            data, info = read_regular(fd, target.name, owner=child.pw_uid, mode=mode, limit=LIMIT)
            require(info.st_gid == child.pw_gid and hashlib.sha256(data).hexdigest() == expected[source])
            guard()
        result[source] = {'identity': identity(info), 'sha256': expected[source], 'mode': mode}
    return {'files': result, 'launchers': [desktop_id(asset[0]) for asset in ASSETS]}


def execute(action, expected):
    require(action in ('prepare', 'read', 'refuse'))
    if action == 'refuse':
        try:
            authority()
        except session_control.SessionError as error:
            require(str(error) == 'session:source-owner')
            require(not os.path.lexists(MARKER) and not os.path.lexists(Path(PREFIX).parent))
            return {'wrong_entry_refused': True}
        raise ValueError('files:wrong-entry-accepted')
    child, parent, entry = authority()
    payload = read_payload(child, expected)
    if action == 'prepare':
        mapping = destinations(child)
        preflight(child, mapping)
        # Only check installed Python/GTK dependencies, never install or launch a GUI.
        import gi
        gi.require_version('Gtk', '4.0')
        from gi.repository import Gtk
        require(Gtk.MAJOR_VERSION == 4)
        require(session_control.source_session(session_control.sessions(), parent.pw_uid) == entry)
        with marker_directory(child) as (fd, guard):
            write_exclusive(fd, MARKER.name, b'consumed\n', owner=0, group=0, mode=0o600)
        for source, (target, mode) in mapping.items():
            with directory(target.parent, child, create=True) as (fd, guard):
                guard()
                write_exclusive(fd, target.name, payload[source], owner=child.pw_uid,
                                group=child.pw_gid, mode=mode)
                guard()
    else:
        with marker_directory(child) as (fd, guard):
            marker, info = read_regular(fd, MARKER.name, owner=0, mode=0o600, limit=32)
            require(marker == b'consumed\n')
    result = readback(child, expected)
    require(session_control.source_session(session_control.sessions(), parent.pw_uid) == entry)
    return result


if __name__ == '__main__':
    require(len(sys.argv) == 2)
    request = sys.stdin.buffer.read(8193)
    require(len(request) <= 8192)
    print(json.dumps(execute(sys.argv[1], json.loads(request)), sort_keys=True))
