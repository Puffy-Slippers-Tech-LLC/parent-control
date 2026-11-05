"""Baseline-owned installation and read-only installed Snap fixture readback.

Local fixtures are deliberately unasserted, strict, system-wide packages. Only
baseline preparation calls reconcile; workers call verify and never repair.
"""
import configparser
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shlex
import socket
import stat
import struct
import subprocess
import sys

from tests.fixtures import snap_assets as assets

RECORD = Path('/var/lib/onpc-baseline-snaps.json')
INPUT = Path('/var/lib/onpc-baseline-preparation/snap-inputs')
PURPOSE = 'onpc-baseline-snaps-v1'


def require(value, detail):
    if not value:
        raise ValueError('snap-fixtures:' + detail + '; refresh with tools/prepare-vm')


def base_cache_peer(info):
    """Recognize Snap's one root-owned, content-addressed base-cache link."""
    cache = os.open('/var/lib/snapd/cache', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        parent = os.fstat(cache)
        require(parent.st_uid == parent.st_gid == 0 and not parent.st_mode & 0o022,
                'base-cache-owner')
        names = os.listdir(cache)
        require(len(names) <= 4096, 'base-cache-bound')
        matches = []
        for name in names:
            item = os.stat(name, dir_fd=cache, follow_symlinks=False)
            if (item.st_dev, item.st_ino) == (info.st_dev, info.st_ino):
                require(re.fullmatch('[0-9a-f]{96}', name)
                        and stat.S_ISREG(item.st_mode) and item.st_uid == item.st_gid == 0
                        and item.st_nlink == 2 and not item.st_mode & 0o022, 'base-cache-peer')
                matches.append(name)
        require(len(matches) == 1, 'base-cache-peer')
        return matches[0]
    finally:
        os.close(cache)


def read(path, *, limit=1024 * 1024, base_cache=False):
    """Read root-owned regular bytes through pinned, non-writable ancestors."""
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'path')
    require(not base_cache or re.fullmatch(
        r'/var/lib/snapd/snaps/core26_[1-9][0-9]*[.]snap', str(path)), 'base-cache-scope')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            require(info.st_uid == 0 and not info.st_mode & 0o022, 'ancestor-owner')
        child = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        with os.fdopen(child, 'rb') as stream:
            info = os.fstat(stream.fileno())
            require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0
                    and not info.st_mode & 0o022
                    and info.st_size <= limit, 'file-owner-or-size')
            cached = base_cache_peer(info) if base_cache and info.st_nlink == 2 else None
            require(info.st_nlink == 1 or cached is not None, 'file-links')
            data = stream.read(limit + 1)
            require(len(data) == info.st_size, 'file-changed')
            require(cached is None or hashlib.sha3_384(data).hexdigest() == cached, 'base-cache-digest')
            return data
    finally:
        os.close(fd)


def validate_hashes(expected):
    require(type(expected) is dict and set(expected) == set(assets.packages())
            and all(type(value) is str and re.fullmatch('[0-9a-f]{64}', value)
                    for value in expected.values()) and len(set(expected.values())) == 3,
            'manifest')


def run(argv):
    return subprocess.run(argv, check=True, capture_output=True, text=True,
        timeout=600, env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'})


def installed():
    result = run(['/usr/bin/snap', 'list', '--all', '--unicode=never'])
    if (result.stdout == '' and result.stderr ==
            "No snaps are installed yet. Try 'snap install hello-world'.\n"):
        return {}
    lines = result.stdout.splitlines()
    require(bool(lines) and lines[0].split() ==
            ['Name', 'Version', 'Rev', 'Tracking', 'Publisher', 'Notes'], 'package-list')
    rows = [line.split() for line in lines[1:]]
    require(all(len(row) == 6 for row in rows), 'package-list')
    names = {name for _, name, _ in assets.ASSETS} | {assets.BASE}
    result = {}
    for name in names:
        active = [row for row in rows if row[0] == name and 'disabled' not in row[5].split(',')]
        require(len(active) <= 1, 'ambiguous-package')
        if active:
            result[name] = active[0]
    return result


def daemon_snap(name):
    """One bounded public installed-state GET; never contact the Snap Store."""
    require(name in {item[1] for item in assets.ASSETS}, 'daemon-recipient')

    class LocalConnection(http.client.HTTPConnection):
        def connect(self):
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect('/run/snapd.socket')
            _, uid, _ = struct.unpack('3i', self.sock.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i')))
            require(uid == 0, 'daemon-owner')

    connection = LocalConnection('localhost', timeout=15)
    try:
        connection.request('GET', '/v2/snaps/' + name, headers={'Connection': 'close'})
        response = connection.getresponse()
        raw = response.read(65537)
        require(response.status == 200 and 0 < len(raw) <= 65536, 'daemon-response')
        value = json.loads(raw)
        require(type(value) is dict and value.get('type') == 'sync'
                and value.get('status-code') == 200 and type(value.get('result')) is dict,
                'daemon-response')
        return value['result']
    finally:
        connection.close()


def package_readback(name, row, *, expected=None, title=None):
    require((name == assets.BASE and title is None)
            or any(name == item and title == label for _, item, label in assets.ASSETS),
            'package-recipient')
    require(row[0] == name and re.fullmatch(r'(?:x)?[1-9][0-9]*', row[2]), 'revision')
    revision = row[2]
    blob = Path('/var/lib/snapd/snaps') / (name + '_' + revision + '.snap')
    digest = hashlib.sha256(read(blob, limit=1024 * 1024 * 1024,
                                base_cache=title is None)).hexdigest()
    require(expected is None or digest == expected, 'installed-digest')
    if title is None:
        require('dangerous' not in row[5].split(',') and row[4] != '-', 'base-trust')
        return {'sha256': digest, 'revision': revision}
    local_strict = (row[1] == assets.VERSION and row[4] == '-'
                    and revision.startswith('x') and row[5] in ('-', 'dangerous'))
    if not local_strict:
        # Closed nonsecret state from a declared fixture, retained when an
        # installed boundary refuses. Never print arbitrary publisher/version.
        known = {'dangerous', 'devmode', 'classic', 'jailmode', 'disabled', 'broken', 'held', '-'}
        print('snap-fixtures: installed-state=' + json.dumps({
            'version_matches': row[1] == assets.VERSION, 'publisher_unset': row[4] == '-',
            'notes': sorted(set(row[5].split(',')) & known),
            'unknown_notes': bool(set(row[5].split(',')) - known)}, sort_keys=True),
            file=sys.stderr, flush=True)
    # Snap versions differ in whether unasserted local packages display the
    # "dangerous" note. The xN revision and absent publisher bind local trust;
    # neither spelling admits devmode/classic or bypasses strict readback below.
    require(local_strict, 'trust-or-confinement')
    mount_root = (Path('/var/lib/snapd/snap') if Path('/var/lib/snapd/snap').is_dir()
                  else Path('/snap'))
    mount = mount_root / name / revision
    architecture = {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(os.uname().machine)
    require(read(mount / 'meta/snap.yaml').decode() == assets.metadata(name, architecture),
            'installed-metadata')
    role, = (role for role, item, _ in assets.ASSETS if item == name)
    require(read(mount / 'fixture-role') == (role + '\n').encode(), 'role')
    desktop = Path('/var/lib/snapd/desktop/applications') / assets.desktop_id(name)
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.read_string(read(desktop).decode())
    entry = parser['Desktop Entry']
    command = shlex.split(entry['Exec'])
    command_paths = {'/snap/bin/' + name, '/var/lib/snapd/snap/bin/' + name}
    require(entry['Type'] == 'Application' and entry['Name'] == title
            and entry.get('X-SnapInstanceName') == name
            and entry.get('X-SnapAppName') == name
            and sum(command.count(path) for path in command_paths) == 1
            and not entry.getboolean('Hidden', fallback=False)
            and not entry.getboolean('NoDisplay', fallback=False), 'launcher')
    active = daemon_snap(name)
    require(all(active.get(key) == value for key, value in {
        'name': name, 'version': assets.VERSION, 'revision': revision, 'status': 'active',
        'type': 'app', 'base': assets.BASE, 'confinement': 'strict', 'id': ''}.items())
        and active.get('publisher') is None and active.get('devmode') is False
        and active.get('jailmode') is False and active.get('trymode', False) is False
        and active.get('broken', '') == '', 'installed-confinement')
    # This is a system-wide capability diagnostic, not the package's mode.
    support = run(['/usr/bin/snap', 'debug', 'confinement']).stdout.strip()
    require(support in ('strict', 'partial'), 'system-support-response')
    return {'sha256': digest, 'revision': revision, 'confinement': active['confinement'],
            'devmode': active['devmode'], 'jailmode': active['jailmode'], 'system_support': support,
            'trust': 'unasserted-local', 'scope': 'system', 'desktop_id': desktop.name}


def record():
    value = json.loads(read(RECORD))
    require(type(value) is dict and set(value) == {'purpose', 'source', 'files', 'pending'}
            and value['purpose'] == PURPOSE
            and type(value['source']) is str and re.fullmatch('[0-9a-f]{64}', value['source'])
            and (value['pending'] is None or type(value['pending']) is dict), 'record')
    validate_hashes(value['files'])
    if value['pending'] is not None:
        validate_hashes(value['pending'])
    return value


def verify(expected, *, source=None):
    validate_hashes(expected)
    saved = record()
    require(saved['files'] == expected and saved['pending'] is None
            and (source is None or saved['source'] == source), 'stale-baseline')
    rows = installed()
    require(set(rows) == {assets.BASE, *(name for _, name, _ in assets.ASSETS)}, 'missing-package')
    result = {name: package_readback(name, rows[name], expected=expected[name + '.snap'], title=title)
              for _, name, title in assets.ASSETS}
    result[assets.BASE] = package_readback(assets.BASE, rows[assets.BASE])
    require(record() == saved, 'record-changed')
    return result


def publish(value):
    # The fixed record is private baseline state, never a caller-selected path.
    temporary = RECORD.with_suffix('.new')
    if os.path.lexists(temporary):
        # A complete interrupted publication is reusable only for this exact
        # intent. Unknown, partial or substituted bytes remain a refusal.
        require(read(temporary) == (json.dumps(value, sort_keys=True) + '\n').encode(),
                'publication-collision')
        os.replace(temporary, RECORD)
        return
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(json.dumps(value, sort_keys=True) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, RECORD)


def reconcile(source, *, runner):
    expected = json.loads(read(INPUT / 'SHA256SUMS.json'))
    validate_hashes(expected)
    for name, digest in expected.items():
        require(hashlib.sha256(read(INPUT / name, limit=1024 * 1024 * 1024)).hexdigest() == digest,
                'input-digest')
    saved = record() if os.path.lexists(RECORD) else None
    runner.run(['systemctl', 'enable', '--now', 'snapd.socket'], timeout=180)
    runner.run(['/usr/bin/snap', 'wait', 'system', 'seed.loaded'], timeout=600)
    rows = installed()
    # Inspect every collision before the first package write. A pending receipt
    # authorizes only its exact intended bytes after an interrupted install.
    for _, name, title in assets.ASSETS:
        if name in rows:
            require(saved is not None, 'foreign-package')
            observed = package_readback(name, rows[name], title=title)
            require(observed['sha256'] in {saved['files'][name + '.snap'],
                (saved['pending'] or saved['files'])[name + '.snap']}, 'foreign-package-digest')
    if assets.BASE not in rows:
        runner.run(['/usr/bin/snap', 'install', assets.BASE], timeout=1200)
    else:
        package_readback(assets.BASE, rows[assets.BASE])
    desired = {'purpose': PURPOSE, 'source': source, 'files': expected, 'pending': None}
    if saved == desired:
        return verify(expected, source=source)
    previous = (saved['pending'] or saved['files']) if saved else expected
    require(saved is None or saved['pending'] is None or saved['files'] == expected,
            'unfinished-other-update')
    publish({**desired, 'pending': previous})
    for _, name, title in assets.ASSETS:
        if name in rows and package_readback(name, rows[name], title=title)['sha256'] == expected[name + '.snap']:
            continue
        runner.run(['/usr/bin/snap', 'install', '--dangerous', str(INPUT / (name + '.snap'))],
                   timeout=1200)
    # Prove every active installed identity before publishing completion.
    current = installed()
    for _, name, title in assets.ASSETS:
        require(name in current, 'installation-failed')
        package_readback(name, current[name], expected=expected[name + '.snap'], title=title)
    publish(desired)
    return verify(expected, source=source)
