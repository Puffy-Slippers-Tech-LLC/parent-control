"""Finite synthetic attachment fixture operations; executed as the fixture user.

No caller-supplied paths or bytes. The controller carries the previous exact
directory/file identity receipt. Unknown or replaced objects refuse all writes,
including cleanup. Guest storage belongs to the disposable fixture home.
"""
import hashlib
import io
import fcntl
import json
import os
from pathlib import Path
import platform
import stat
import sys
import tempfile
import time
import zipfile
import zlib
from contextlib import ExitStack
from datetime import date
from download_destination import DIRECTORY as SAVE_DIRECTORY, download_directory
from guest_files import identity, read_regular, require, write_exclusive

ZIP_NAME = 'Synthetic archive.zip'
ZIP_ARTIFACT = 'synthetic-archive'
ZIP_LIMIT = 65536
ZIP_MEMBERS = 16
ZIP_MEMBER_LIMIT = 4096
ZIP_EXPANDED_LIMIT = 8192
ZIP_SECONDS = 5
ZIP_CONTENTS = {'empty/': b'', 'note.txt': b'Independent synthetic archive note\n',
                'metadata.json': b'{"kind":"synthetic","version":1}\n'}


def make_zip(entries=None):
    """Deterministic fixture bytes, separate from the archive observation."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        for name, content in (ZIP_CONTENTS.items() if entries is None else entries):
            archive.writestr(zipfile.ZipInfo(name), content)
    return output.getvalue()


ZIP_FILES = {ZIP_NAME: make_zip()}

DIRECTORY = '.onpc-e2e-synthetic-files'
FILES = {'Synthetic note.txt': b'ONPC synthetic attachment\n',
         'Second note.txt': b'ONPC second synthetic attachment\n'}
COPY = 'Synthetic copy.txt'
RENAMED = 'Renamed synthetic note.txt'
CONTENTS = {**FILES, COPY: FILES['Synthetic note.txt'],
            RENAMED: FILES['Synthetic note.txt']}
TEXT_ARTIFACT = 'synthetic-note'
TEXT_NAME = 'Synthetic note.txt'
TEXT_LIMIT = 1024
CHANGED_TEXT = b'ONPC changed synthetic attachment\n'
BOUNDARY_PROFILES = {
    'single': {'Synthetic note.txt': FILES['Synthetic note.txt']},
    'count': {f'Count {index}.txt': b'C' for index in range(1, 6)},
    'sixth': {'Count 6.txt': b'C'},
    'maximum': {'Maximum.txt': b'M' * (5 * 1024 * 1024)},
    'oversized': {'Oversized.txt': b'O' * (5 * 1024 * 1024 + 1)},
    'total': {'Total.txt': b'T' * (3 * 1024 * 1024)},
    'overflow': {'Overflow.txt': b'X' * (3 * 1024 * 1024 + 1)},
    'name180': {'N' * 176 + '.txt': b'N'},
    'name181': {'N' * 177 + '.txt': b'N'},
    'hidden': {'Hidden\u200b.txt': b'H'},
    'mixed': {'Accepted.txt': b'A', 'Oversized.txt': b'O' * (5 * 1024 * 1024 + 1)},
}

NATIVE_SPACE_PARENT = Path('/opt/onpc-test-fixtures/Applications/Whitespace')
NATIVE_SPACE_SOURCE = 'Path With Spaces.AppImage'
NATIVE_SPACE_COPY = 'Copied Path With Spaces.AppImage'
NATIVE_COMMA_PARENT = Path('/opt/onpc-test-fixtures/Applications/Comma')
NATIVE_COMMA_SOURCE = 'Path,With,Commas.AppImage'
NATIVE_COMMA_COPY = 'Copied,Path,With,Commas.AppImage'


def native_space_operate(home, operation, request, profile='native-space'):
    """FILE05: one Jordan-owned executable copy, never arbitrary file input."""
    import pwd
    require(profile in ('native-space', 'native-comma'))
    parent_path, source_name, copy_name = (
        (NATIVE_SPACE_PARENT, NATIVE_SPACE_SOURCE, NATIVE_SPACE_COPY) if profile == 'native-space'
        else (NATIVE_COMMA_PARENT, NATIVE_COMMA_SOURCE, NATIVE_COMMA_COPY))
    child = pwd.getpwnam('onpc-child-jordan')
    require(os.getuid() == os.geteuid() == child.pw_uid
            and home == Path(child.pw_dir) == Path('/home/onpc-child-jordan'))
    require(operation in ('stage', 'copy', 'read', 'cleanup', 'absent')
            and type(request) is dict and set(request) == {'expected', 'previous'})
    expected, previous = request['expected'], request['previous']
    require(type(expected) is dict and set(expected) == {'source', 'nonmatching'}
            and all(type(value) is str and len(value) == 64
                    and all(c in '0123456789abcdef' for c in value)
                    for value in expected.values())
            and expected['source'] != expected['nonmatching'])
    with ExitStack() as stack:
        # Pin each ancestor and the destination directory before inspecting or
        # writing. Directory timestamps may change; identity/owner/mode may not.
        parent = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, parent)
        chain = []
        for name in parent_path.parts[1:]:
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            stack.callback(os.close, fd)
            info = os.fstat(fd)
            require(info.st_uid in (0, child.pw_uid) and not info.st_mode & 0o022)
            chain.append((parent, name, fd, identity(info)[:5]))
            parent = fd
        require(info.st_uid == child.pw_uid and info.st_gid == child.pw_gid
                and stat.S_IMODE(info.st_mode) == 0o755)
        fcntl.flock(parent, fcntl.LOCK_EX | fcntl.LOCK_NB)

        def guard():
            for ancestor, name, pinned, receipt in chain:
                require(identity(os.fstat(pinned))[:5] == receipt
                        == identity(os.stat(name, dir_fd=ancestor, follow_symlinks=False))[:5])

        def readback():
            guard()
            names = set(os.listdir(parent))
            base = {source_name, 'onpc-test-gui.py', 'gtk_automation.py'}
            require(names in (base, base | {copy_name}))
            result = {'directory': chain[-1][3], 'destination': str(parent_path / copy_name),
                      'files': {}}
            for name in (source_name, copy_name):
                if name not in names:
                    continue
                data, entry = read_regular(parent, name, owner=child.pw_uid,
                                            mode=0o755, limit=2 * 1024 * 1024)
                digest = hashlib.sha256(data).hexdigest()
                require(entry.st_gid == child.pw_gid and digest == expected['source'])
                result['files'][name] = {'identity': identity(entry), 'sha256': digest,
                                         'size': len(data)}
            guard()
            return result

        current = readback()
        if operation == 'stage':
            require(previous is None and set(current['files']) == {source_name})
        elif operation == 'absent':
            require(previous == {'absent': True}
                    and set(current['files']) == {source_name})
            return {'absent': True}
        else:
            require(current == previous)
            if operation == 'copy':
                require(set(current['files']) == {source_name})
                data, entry = read_regular(parent, source_name, owner=child.pw_uid,
                                          mode=0o755, limit=2 * 1024 * 1024)
                require(identity(entry) == current['files'][source_name]['identity'])
                guard()
                write_exclusive(parent, copy_name, data, owner=child.pw_uid,
                                group=child.pw_gid, mode=0o755)
            elif operation == 'cleanup':
                require(set(current['files']) == {source_name, copy_name})
                guard()
                require(identity(os.stat(copy_name, dir_fd=parent, follow_symlinks=False))
                        == current['files'][copy_name]['identity'])
                os.unlink(copy_name, dir_fd=parent)
                require(set(readback()['files']) == {source_name})
                return {'absent': True}
        return readback()


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
    parent = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        require(identity(os.fstat(parent)) == identity(info))
        for name in names:
            content, before = read_regular(parent, name, owner=os.getuid(), mode=0o600,
                                           limit=len(contents[name]))
            require(content == contents[name])
            result['files'][name] = {'identity': identity(before),
                                     'sha256': hashlib.sha256(content).hexdigest(),
                                     'size': len(content)}
        require(identity(os.fstat(parent)) == identity(info))
    finally:
        os.close(parent)
    require(identity(root.lstat()) == identity(info))
    return result


def read_text(home, request):
    """Read one declared text artifact against its preparation receipt.

    All path components are fixed here. Open descriptors pin the directory and
    file while comparing the receipt, reading bytes and checking replacement.
    """
    require(type(request) is dict and set(request) == {'receipt', 'artifact'}
            and request['artifact'] == TEXT_ARTIFACT)
    receipt = request['receipt']
    require(type(receipt) is dict and set(receipt) == {'directory', 'files'}
            and type(receipt['files']) is dict and TEXT_NAME in receipt['files'])
    expected = receipt['files'][TEXT_NAME]
    require(type(expected) is dict and set(expected) == {'identity', 'sha256', 'size'})
    root = home / DIRECTORY
    home_fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        require(identity(os.fstat(home_fd)) == identity(home.lstat()))
        root_fd = os.open(DIRECTORY, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                          dir_fd=home_fd)
        try:
            return _read_text_open(root_fd, home, receipt, expected)
        finally:
            os.close(root_fd)
    finally:
        os.close(home_fd)


def _read_text_open(root_fd, home, receipt, expected):
    content = read_pinned(root_fd, home / DIRECTORY, receipt, expected, TEXT_NAME, TEXT_LIMIT)
    require(content == FILES[TEXT_NAME])
    content.decode('utf-8', errors='strict')
    return {'artifact': TEXT_ARTIFACT, 'matched': True,
            'size': len(content), 'sha256': hashlib.sha256(content).hexdigest()}


def read_pinned(root_fd, root, receipt, expected, name, limit, *, diagnostic=False):
    """Bounded bytes from the exact owned inode; no caller-controlled paths."""
    root_info = os.fstat(root_fd)
    require(identity(root_info) == receipt['directory'] and stat.S_ISDIR(root_info.st_mode)
            and root_info.st_uid == os.getuid()
            and (not root_info.st_mode & 0o022 if diagnostic
                 else stat.S_IMODE(root_info.st_mode) == 0o700))
    before = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
    require(identity(before) == expected['identity'] and stat.S_ISREG(before.st_mode)
            and before.st_uid == os.getuid() and before.st_nlink == 1
            and stat.S_IMODE(before.st_mode) == 0o600 and 0 < before.st_size <= limit)
    content, pinned = read_regular(root_fd, name, owner=os.getuid(), mode=0o600, limit=limit)
    require(identity(pinned) == identity(before)
            and len(content) == expected['size']
            and hashlib.sha256(content).hexdigest() == expected['sha256'])
    require(identity(os.fstat(root_fd)) == receipt['directory']
            and identity(root.lstat()) == receipt['directory'])
    return content


def inspect_zip(content, *, diagnostic=False):
    """Observe actual member bytes using zipfile, without extraction."""
    archive_limit, count_limit, member_limit, expanded_limit = (
        (2 * 1024 * 1024, 17, 16 * 1024 * 1024, 16 * 1024 * 1024)
        if diagnostic else (ZIP_LIMIT, ZIP_MEMBERS, ZIP_MEMBER_LIMIT, ZIP_EXPANDED_LIMIT))
    require(0 < len(content) <= archive_limit)
    deadline = time.monotonic() + ZIP_SECONDS
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            require(0 < len(entries) <= count_limit)
            names = [entry.filename for entry in entries]
            require(len(set(names)) == len(names))
            for entry in entries:
                name = entry.filename
                parts = name.rstrip('/').split('/')
                require(entry.orig_filename == name and name and not name.startswith('/')
                        and '\\' not in name and ':' not in name
                        and all(part not in ('', '.', '..') for part in parts)
                        and not any(ord(char) < 32 for char in name)
                        and not entry.flag_bits & 1
                        and stat.S_IFMT(entry.external_attr >> 16) in (0, stat.S_IFREG, stat.S_IFDIR)
                        and entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                        and 0 <= entry.file_size <= member_limit)
            require(sum(entry.file_size for entry in entries) <= expanded_limit)
            if not diagnostic:
                require(set(names) == set(ZIP_CONTENTS))
            result, contents = {}, {}
            for entry in entries:
                require(time.monotonic() < deadline)
                with archive.open(entry) as member:
                    actual = member.read(member_limit + 1)
                    require(len(actual) <= member_limit and member.read(1) == b'')
                require(len(actual) == entry.file_size)
                if diagnostic:
                    contents[entry.filename] = actual
                else:
                    require(actual == ZIP_CONTENTS[entry.filename])
                actual.decode('utf-8', errors='strict')
                if not diagnostic and entry.filename.endswith('.json'):
                    require(json.loads(actual) == {'kind': 'synthetic', 'version': 1})
                result[entry.filename] = {'size': len(actual),
                                          'sha256': hashlib.sha256(actual).hexdigest()}
            require(time.monotonic() < deadline)
            if diagnostic:
                checks = compare_diagnostic_contents(archive, contents)
                require(time.monotonic() < deadline)
                return {'artifact': 'diagnostic-export', 'members': result,
                        'matched': True, 'checks': checks}
            return {'artifact': ZIP_ARTIFACT, 'members': result, 'matched': True}
    except (zipfile.BadZipFile, zlib.error, RuntimeError, NotImplementedError, EOFError,
            KeyError, TypeError) as error:
        raise ValueError('files:zip-refused') from error


def compare_diagnostic_contents(archive, contents):
    """Independent public inventory/header/system assertions, then closed grammar.

    The installed format validator is supplemental: no collector or source log
    is opened. Only the customer-selected exported archive is inspected.
    """
    if '/usr/lib/oh-no-parent-control/common' not in sys.path:
        sys.path.append('/usr/lib/oh-no-parent-control/common')
    from oh_no_parent_control_ui.diagnostic_report import read_report
    # Review the actual exported bytes for this attempt's declared synthetic
    # personal values as well as validating the closed diagnostic grammar.
    require(all(marker not in content for content in contents.values() for marker in (
        b'onpc-parent-', b'onpc-child-', b'first@example.invalid',
        b'Synthetic feedback first', b'ONPC synthetic attachment')))
    info = json.loads(contents['system-info.json'])
    # The documented summary may include saved languages under report-local
    # role labels. read_report below validates their closed grammar and bounds.
    keys = {'schema', 'system', 'health', 'counts', 'logs'}
    require(type(info) is dict and set(info) in (keys, keys | {'user_languages'})
            and type(info['schema']) is int and info['schema'] == 3
            and type(info['logs']) is dict and len(info['logs']) <= 12)
    folders = {'broker/', 'child/', 'kiosk/', 'parent/'}
    require(set(contents) == {'system-info.json', *folders, *info['logs']}
            and all(contents[name] == b'' for name in folders))
    header = (b'ONPC component log (schema 3)\n'
        b'Offsets are elapsed time within a broker diagnostic segment, not clock times.\n'
        b'Dates name retained source files; incident context can include earlier observations.\n'
        b'Frontend events are observations; broker events describe broker decisions.\n'
        b'Missing observations do not establish that an operation did not occur.\n\n')
    totals = dict.fromkeys(('broker', 'child', 'kiosk', 'parent'), 0)
    records = 0
    for name, count in info['logs'].items():
        component, filename = name.split('/')
        require(component in totals and len(filename) == 14 and filename.endswith('.log')
                and date.fromisoformat(filename[:10]).isoformat() == filename[:10])
        totals[component] += 1
        require(totals[component] <= 3 and type(count) is int and 0 <= count <= 12000)
        records += count
        actual = contents[name]
        require(actual.startswith(header)
                and len(actual[len(header):].decode('ascii').splitlines()) == count)
    require(records <= 12000)
    system = info['system']
    # Compare against the guest OS independently of the exported report.
    # The shared reader runs on both registered packaging targets.
    os_id = platform.freedesktop_os_release().get('ID')
    require(os_id in ('ubuntu', 'fedora'))
    # Fresh frontend collections always include the reviewed display section.
    # read_report below validates its closed fields and bounds; legacy reports
    # without displays remain readable by the product parser, outside this case.
    require(type(system) is dict and set(system) == {'schema', 'app_version', 'os', 'kernel',
        'architecture', 'timezone', 'session_type', 'accounts', 'dependencies', 'displays'}
        and type(system['schema']) is int and system['schema'] == 1
        and system['os']['id'] == os_id and system['session_type'] == 'wayland'
        and system['app_version'] != 'unknown')
    require(set(info['health']) == {'accounts', 'timer', 'polkit', 'systemd', 'migration', 'storage'}
            and all(value in ('available', 'inactive', 'unavailable', 'incomplete', 'unknown')
                    for value in info['health'].values()))
    require(set(info['counts']) == {'suppressed', 'rotations', 'incidents', 'invalid',
        'truncated', 'missing', 'write_failures'} and all(type(value) is int
        and 0 <= value <= 2**53 - 1 for value in info['counts'].values()))
    read_report(archive)  # Validates system categories and every closed log field/prose.
    return {'inventory': True, 'headers': True, 'system': True, 'contents': True,
            'records': records}


def read_zip(home, request):
    require(type(request) is dict and set(request) == {'receipt', 'artifact'}
            and request['artifact'] == ZIP_ARTIFACT)
    receipt = request['receipt']
    require(type(receipt) is dict and set(receipt) == {'directory', 'files'}
            and type(receipt['files']) is dict and set(receipt['files']) == {ZIP_NAME})
    expected = receipt['files'][ZIP_NAME]
    require(type(expected) is dict and set(expected) == {'identity', 'sha256', 'size'})
    root = home / (DIRECTORY + '-zip')
    home_fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        require(identity(os.fstat(home_fd)) == identity(home.lstat()))
        root_fd = os.open(root.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=home_fd)
        try:
            content = read_pinned(root_fd, root, receipt, expected, ZIP_NAME, ZIP_LIMIT)
            return inspect_zip(content)
        finally:
            os.close(root_fd)
    finally:
        os.close(home_fd)


def probe_zip_refusals(home):
    """Fault receipts describe actual bytes so archive guards are exercised."""
    faults = ('missing', 'symlink', 'replaced', 'owner', 'malformed', 'duplicate',
              'unsafe', 'wrong-entry', 'different', 'archive-limit', 'member-limit',
              'expanded-limit', 'count-limit')
    for fault in faults:
        with tempfile.TemporaryDirectory(prefix='.onpc-e2e-zip-probe-', dir=home) as temporary:
            probe_home = Path(temporary)
            root = probe_home / (DIRECTORY + '-zip')
            root.mkdir(mode=0o700)
            content = ZIP_FILES[ZIP_NAME]
            if fault == 'malformed': content = b'not a ZIP'
            if fault == 'duplicate':
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', UserWarning)
                    content = make_zip([*ZIP_CONTENTS.items(), ('note.txt', b'duplicate')])
            if fault == 'unsafe': content = make_zip([('../note.txt', b'unsafe')])
            if fault == 'wrong-entry': content = make_zip([('other.txt', b'unrelated')])
            if fault == 'different': content = make_zip({**ZIP_CONTENTS, 'note.txt': b'changed'}.items())
            if fault == 'archive-limit': content = b'x' * (ZIP_LIMIT + 1)
            if fault == 'member-limit': content = make_zip([('note.txt', b'x' * (ZIP_MEMBER_LIMIT + 1))])
            if fault == 'expanded-limit':
                content = make_zip([(name, b'x' * ZIP_MEMBER_LIMIT) for name in ZIP_CONTENTS])
            if fault == 'count-limit': content = make_zip([(str(i), b'') for i in range(ZIP_MEMBERS + 1)])
            target = root / ZIP_NAME
            target.write_bytes(content)
            target.chmod(0o600)
            receipt = snapshot(root, {ZIP_NAME: content})
            if fault == 'missing': target.unlink()
            if fault in ('symlink', 'replaced'):
                target.rename(root / 'preserved')
                if fault == 'symlink': target.symlink_to(root / 'preserved')
                else:
                    target.write_bytes(content)
                    target.chmod(0o600)
            if fault == 'owner': receipt['files'][ZIP_NAME]['identity'][2] += 1
            try:
                read_zip(probe_home, {'receipt': receipt, 'artifact': ZIP_ARTIFACT})
            except (ValueError, OSError):
                continue
            raise ValueError('files:zip-probe-accepted-' + fault)
    return {'refused': list(faults), 'owned_cleanup': True}


def probe_text_refusals(home):
    """Finite disposable fault fixtures; never mutate the owned staged file."""
    faults = ('missing', 'symlink', 'replaced', 'empty', 'different', 'oversized')
    for fault in faults:
        with tempfile.TemporaryDirectory(prefix='.onpc-e2e-text-probe-', dir=home) as temporary:
            probe_home = Path(temporary)
            probe_root = probe_home / DIRECTORY
            probe_root.mkdir(mode=0o700)
            target = probe_root / TEXT_NAME
            target.write_bytes(FILES[TEXT_NAME])
            target.chmod(0o600)
            receipt = snapshot(probe_root)
            if fault == 'missing':
                target.unlink()
            elif fault == 'symlink':
                target.rename(probe_root / 'preserved')
                target.symlink_to(probe_root / 'preserved')
            elif fault == 'replaced':
                target.rename(probe_root / 'preserved')
                target.write_bytes(FILES[TEXT_NAME])
                target.chmod(0o600)
            elif fault == 'empty':
                target.write_bytes(b'')
            elif fault == 'different':
                target.write_bytes(b'unrelated')
            elif fault == 'oversized':
                target.write_bytes(b'x' * (TEXT_LIMIT + 1))
            try:
                read_text(probe_home, {'receipt': receipt, 'artifact': TEXT_ARTIFACT})
            except (ValueError, OSError):
                continue
            raise ValueError('files:probe-accepted-' + fault)
    return {'refused': list(faults), 'owned_cleanup': True}


def change_source(root, receipt, contents):
    """One fixed write, after pinning and validating the original owned bytes."""
    require(snapshot(root, contents) == receipt and TEXT_NAME in receipt['files'])
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        expected = receipt['files'][TEXT_NAME]
        require(read_pinned(root_fd, root, receipt, expected, TEXT_NAME, TEXT_LIMIT)
                == FILES[TEXT_NAME])
        fd = os.open(TEXT_NAME, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root_fd)
        try:
            require(identity(os.fstat(fd)) == expected['identity'])
            require(os.read(fd, TEXT_LIMIT + 1) == FILES[TEXT_NAME])
            require(identity(os.stat(TEXT_NAME, dir_fd=root_fd, follow_symlinks=False))
                    == expected['identity'] and identity(root.lstat()) == receipt['directory'])
            os.lseek(fd, 0, os.SEEK_SET)
            require(os.write(fd, CHANGED_TEXT) == len(CHANGED_TEXT))
            os.ftruncate(fd, len(CHANGED_TEXT))
            os.fsync(fd)
            require(identity(os.stat(TEXT_NAME, dir_fd=root_fd, follow_symlinks=False))
                    == identity(os.fstat(fd)))
        finally:
            os.close(fd)
        require(identity(root.lstat()) == receipt['directory'])
    finally:
        os.close(root_fd)
    return snapshot(root, {**contents, TEXT_NAME: CHANGED_TEXT})


def probe_source_refusals(home):
    faults = ('path', 'owner', 'symlink', 'replaced', 'different', 'hardlink')
    for fault in faults:
        with tempfile.TemporaryDirectory(prefix='.onpc-e2e-source-probe-', dir=home) as temporary:
            probe_home = Path(temporary)
            receipt = operate(probe_home, 'stage', None)
            root = probe_home / DIRECTORY
            target = root / TEXT_NAME
            if fault == 'path':
                receipt['files']['../Synthetic note.txt'] = receipt['files'].pop(TEXT_NAME)
            if fault == 'owner': receipt['files'][TEXT_NAME]['identity'][2] += 1
            if fault in ('symlink', 'replaced'):
                target.rename(probe_home / 'preserved')
                if fault == 'symlink': target.symlink_to(probe_home / 'preserved')
                else:
                    target.write_bytes(FILES[TEXT_NAME])
                    target.chmod(0o600)
            if fault == 'different': target.write_bytes(b'preserve this unrelated content')
            if fault == 'hardlink': os.link(target, probe_home / 'preserved')
            before = target.read_bytes()
            identities = {p.name: p.lstat() for p in root.iterdir()}
            try:
                operate(probe_home, 'change-source', receipt)
            except (ValueError, OSError):
                require(target.read_bytes() == before
                        and {p.name: p.lstat() for p in root.iterdir()} == identities)
            else:
                raise ValueError('files:source-probe-accepted-' + fault)
    return {'refused': list(faults), 'owned_cleanup': True}


SAVE_NAME = 'Selected diagnostics.zip'
SAVE_CANCEL_NAME = 'Cancelled diagnostics.zip'
SAVE_LIMIT = 16 * 1024 * 1024


def save_snapshot(root, previous, *, saved=False):
    """FILE05 exact newly exported file; archive contents belong to FILE08."""
    info = directory(root)
    require(type(previous) is dict)
    require(identity(info)[:5] == previous['directory'][:5])
    require(set(os.listdir(root)) == set(previous['baseline'])
            | ({'Unwritable', SAVE_NAME} if saved else {'Unwritable'}))
    require({name: identity((root / name).lstat()) for name in previous['baseline']}
            == previous['baseline'])
    denied = root / 'Unwritable'
    require(identity(directory(denied)) == previous['unwritable']
            and stat.S_IMODE(denied.stat().st_mode) == 0o500
            and not os.access(denied, os.W_OK) and not os.listdir(denied))
    result = {'directory': identity(info), 'unwritable': previous['unwritable'],
              'baseline': previous['baseline'], 'created': previous['created'], 'files': {}}
    if saved:
        path = root / SAVE_NAME
        before = path.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
                and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == 0o600
                and 0 < before.st_size <= SAVE_LIMIT)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            require(identity(os.fstat(fd)) == identity(before))
            digest = hashlib.sha256()
            count = 0
            while count < before.st_size:
                chunk = os.read(fd, min(65536, before.st_size - count))
                require(chunk)
                count += len(chunk)
                digest.update(chunk)
            require(os.read(fd, 1) == b'' and identity(os.fstat(fd)) == identity(before))
        finally:
            os.close(fd)
        require(identity(path.lstat()) == identity(before))
        result['files'][SAVE_NAME] = {'identity': identity(before), 'size': count,
                                     'sha256': digest.hexdigest()}
    require(identity(root.lstat()) == identity(info))
    return result


def read_saved_zip(home, request):
    require(type(request) is dict and set(request) == {'receipt', 'artifact'}
            and request['artifact'] == 'diagnostic-export')
    receipt = request['receipt']
    require(type(receipt) is dict and set(receipt) == {
        'directory', 'unwritable', 'baseline', 'created', 'files'}
        and type(receipt['files']) is dict and set(receipt['files']) == {SAVE_NAME})
    root = download_directory(home)
    require(save_snapshot(root, receipt, saved=True) == receipt)
    home_fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        require(identity(os.fstat(home_fd)) == identity(home.lstat()))
        root_fd = os.open(root.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=home_fd)
        try:
            content = read_pinned(root_fd, root, receipt, receipt['files'][SAVE_NAME],
                                  SAVE_NAME, 2 * 1024 * 1024, diagnostic=True)
            result = inspect_zip(content, diagnostic=True)
            require(save_snapshot(root, receipt, saved=True) == receipt)
            return result
        finally:
            os.close(root_fd)
    finally:
        os.close(home_fd)


def save_operate(home, operation, previous):
    root = download_directory(home)
    require(operation in ('stage', 'read', 'saved', 'cleanup', 'absent', 'open-zip'))
    if operation == 'open-zip':
        return read_saved_zip(home, previous)
    if operation == 'absent':
        require(previous == {'absent': True})
        if os.path.lexists(root):
            directory(root)
            require(not any(os.path.lexists(root / name) for name in
                            ('Unwritable', SAVE_NAME, SAVE_CANCEL_NAME)))
        return previous
    if operation == 'stage':
        require(previous is None)
        created = not os.path.lexists(root)
        if created:
            root.mkdir(mode=0o700)
        directory(root)
        require(not any(os.path.lexists(root / name) for name in
                        ('Unwritable', SAVE_NAME, SAVE_CANCEL_NAME)))
        baseline = {path.name: identity(path.lstat()) for path in root.iterdir()}
        (root / 'Unwritable').mkdir(mode=0o500)
        receipt = {'directory': identity(root.lstat()),
                   'unwritable': identity((root / 'Unwritable').lstat()),
                   'baseline': baseline, 'created': created, 'files': {}}
        return save_snapshot(root, receipt)
    require(type(previous) is dict and set(previous) == {
                'directory', 'unwritable', 'baseline', 'created', 'files'}
            and type(previous['files']) is dict and type(previous['baseline']) is dict
            and type(previous['created']) is bool)
    if operation == 'saved':
        require(previous['files'] == {})
        return save_snapshot(root, previous, saved=True)
    current = save_snapshot(root, previous, saved=bool(previous['files']))
    require(current == previous)
    if operation == 'cleanup':
        # Validation of the complete set precedes every removal. Unknown,
        # replaced, changed and cancelled-name files are never reclaimed.
        if current['files']:
            (root / SAVE_NAME).unlink()
        (root / 'Unwritable').rmdir()
        if previous['created']:
            root.rmdir()
        return save_operate(home, 'absent', {'absent': True})
    return current


def operate(home, operation, previous, profile='standard'):
    """Validate everything before the first mutation; failures never clean up."""
    if profile in ('native-space', 'native-comma'):
        return native_space_operate(home, operation, previous, profile)
    require(operation in ('stage', 'read', 'copy', 'rename', 'cleanup', 'absent', 'open-text', 'probe-text', 'open-zip', 'probe-zip', 'change-source', 'probe-source', 'saved'))
    require(profile in ('standard', 'zip', 'save') or profile in BOUNDARY_PROFILES)
    require(operation != 'saved' or profile == 'save')
    require(profile == 'standard' or operation not in ('copy', 'rename'))
    directory(home)
    # All shared invocations lock the existing home inode; no lock-file cleanup
    # or second writer can race a receipt validation against a mutation.
    fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(identity(os.fstat(fd)) == identity(home.lstat()))
        return (save_operate(home, operation, previous) if profile == 'save'
                else _operate(home, operation, previous, profile))
    finally:
        os.close(fd)


def _operate(home, operation, previous, profile):
    root = home / (DIRECTORY + ('' if profile == 'standard' else '-' + profile))
    files = FILES if profile == 'standard' else ZIP_FILES if profile == 'zip' else BOUNDARY_PROFILES[profile]
    contents = CONTENTS if profile == 'standard' else files
    if operation in ('change-source', 'probe-source'):
        require(profile in ('standard', 'single'))
        if operation == 'change-source':
            require(type(previous) is dict and set(previous.get('files', {})) == set(files))
            return change_source(root, previous, contents)
        require(snapshot(root, contents) == previous)
        return probe_source_refusals(home)
    # The carried exact receipt selects the sole declared changed state. Other
    # commands still require original bytes; no copy/rename of changed sources.
    if (operation in ('read', 'cleanup') and profile in ('standard', 'single')
            and type(previous) is dict
            and previous.get('files', {}).get(TEXT_NAME, {}).get('sha256')
            == hashlib.sha256(CHANGED_TEXT).hexdigest()):
        contents = {**contents, TEXT_NAME: CHANGED_TEXT}
    if operation == 'open-zip':
        require(profile == 'zip')
        return read_zip(home, previous)
    if operation == 'probe-zip':
        require(profile == 'zip' and snapshot(root, contents) == previous)
        return probe_zip_refusals(home)
    if operation == 'open-text':
        require(profile == 'standard')
        return read_text(home, previous)
    if operation == 'probe-text':
        require(profile == 'standard' and snapshot(root) == previous)
        return probe_text_refusals(home)
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


def diagnostic_zip_refusal(error):
    """Locate a refused export read without exposing exceptions or artifact data.

    Function-relative offsets survive the controller's in-memory module prefix.
    Only reviewed function names and bounded integers leave the guest; never
    traceback filenames, source lines, locals or exception messages.
    """
    scopes = {'operate', 'save_operate', 'read_saved_zip', 'save_snapshot',
              'directory', 'read_pinned', 'read_regular', 'inspect_zip',
              'compare_diagnostic_contents', 'read_report', '_component',
              'contents', '_manifest', 'validate_record', 'validate_system_info'}
    frames = []
    trace = error.__traceback__
    while trace is not None:
        code = trace.tb_frame.f_code
        offset = trace.tb_lineno - code.co_firstlineno
        if code.co_name in scopes and 0 <= offset <= 4096:
            frames.append({'function': code.co_name, 'offset': offset})
            frames = frames[-8:]
        trace = trace.tb_next
    print('diagnostic-zip:refusal ' + json.dumps({
        'category': 'filesystem' if isinstance(error, OSError) else 'validation',
        'frames': frames,
    }, sort_keys=True), file=sys.stderr, flush=True)


def main():
    import pwd
    require(len(sys.argv) in (3, 4))
    user = ('onpc-child-jordan' if len(sys.argv) == 4 and sys.argv[3] in ('native-space', 'native-comma')
            else 'onpc-parent-jamie')
    account = pwd.getpwnam(user)
    require(os.getuid() == os.geteuid() == account.pw_uid and account.pw_dir == '/home/' + user)
    require(len(sys.argv[2]) <= 4096)
    previous = json.loads(sys.argv[2])
    try:
        result = operate(Path(account.pw_dir), sys.argv[1], previous,
                         sys.argv[3] if len(sys.argv) == 4 else 'standard')
    except (ValueError, OSError) as error:
        if (sys.argv[1] == 'open-zip' and len(sys.argv) == 4 and sys.argv[3] == 'save'
                and type(previous) is dict and previous.get('artifact') == 'diagnostic-export'):
            diagnostic_zip_refusal(error)
        result = {'refused': True}
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
