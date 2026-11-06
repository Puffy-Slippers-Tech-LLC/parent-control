"""One baseline-owned, offline, system-wide Flatpak installation scope.

Preparation alone installs bundles. Restored attempts only read public Flatpak
state, exact deployment metadata and exported launchers.
"""
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess

from tests.fixtures import flatpak_assets as assets
from baseline_snaps import read

RECORD = Path('/var/lib/onpc-baseline-flatpaks.json')
INPUT = Path('/var/lib/onpc-baseline-preparation/flatpak-inputs')
ROOT = Path('/var/lib/flatpak')
PURPOSE = 'onpc-baseline-flatpaks-v1'


def require(value, detail):
    if not value:
        raise ValueError('flatpak-fixtures:' + detail + '; refresh with tools/prepare-vm')


def validate_manifest(value, *, current=False):
    require(type(value) is dict and set(value) == set(assets.declarations()), 'manifest')
    for ref, bundle in assets.declarations().items():
        item = value[ref]
        require(type(item) is dict and set(item) == {'bundle', 'commit', 'metadata'}
                and item['bundle'] == bundle
                and all(type(item[key]) is str and re.fullmatch('[0-9a-f]{64}', item[key])
                        for key in ('commit', 'metadata')), 'manifest')
        require(not current or item['metadata'] == hashlib.sha256(
            assets.metadata(ref.split('/')[1]).encode()).hexdigest(), 'manifest')
    require(len({item['commit'] for item in value.values()}) == 4, 'manifest')


def record():
    saved = json.loads(read(RECORD))
    require(type(saved) is dict and set(saved) == {'purpose', 'source', 'manifest', 'pending'}
            and saved['purpose'] == PURPOSE and type(saved['source']) is str
            and re.fullmatch('[0-9a-f]{64}', saved['source']), 'record')
    validate_manifest(saved['manifest'])
    if saved['pending'] is not None:
        validate_manifest(saved['pending'])
    return saved


def publish(value):
    data = (json.dumps(value, sort_keys=True) + '\n').encode()
    pending = RECORD.with_suffix('.new')
    if os.path.lexists(pending):
        require(read(pending) == data, 'publication-collision')
    else:
        fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    os.replace(pending, RECORD)
    fd = os.open(RECORD.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def run(arguments):
    return subprocess.run(['/usr/bin/flatpak', *arguments], check=True,
        capture_output=True, text=True, timeout=180,
        env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'})


def installed():
    rows = run(['list', '--system', '--all', '--columns=application,arch,branch']).stdout.splitlines()
    require(all(len(row.split('\t')) == 3 for row in rows), 'installed-list')
    names = {ref.split('/')[1]: ref for ref in assets.declarations()}
    found = set()
    for row in rows:
        name, arch, branch = row.split('\t')
        if name in names:
            ref = names[name]
            require(arch == assets.ARCH and branch == assets.BRANCH and ref not in found,
                    'installed-scope')
            found.add(ref)
    return found


def read_deployed(path):
    """OSTree deployments use root-owned hardlinks; never traverse symlinks."""
    require(path.is_relative_to(ROOT) and '..' not in path.parts, 'deployment-scope')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            require(info.st_uid == 0 and not info.st_mode & 0o022, 'deployment-owner')
        child = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        with os.fdopen(child, 'rb') as stream:
            info = os.fstat(stream.fileno())
            require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0
                    and not info.st_mode & 0o022 and info.st_size <= 65536, 'deployment-file')
            data = stream.read(65537)
            require(len(data) == info.st_size, 'deployment-changed')
            return data
    finally:
        os.close(fd)


def readback(ref, expected):
    require(ref in assets.declarations(), 'recipient')
    require(run(['info', '--system', '--show-ref', ref]).stdout.strip() == ref, 'installed-ref')
    commit = run(['info', '--system', '--show-commit', ref]).stdout.strip()
    require(commit == expected['commit'], 'installed-digest')
    location = ROOT / ref / commit
    require(run(['info', '--system', '--show-location', ref]).stdout.strip() == str(location),
            'installed-scope')
    require(hashlib.sha256(read_deployed(location / 'metadata')).hexdigest()
            == expected['metadata'], 'installed-metadata')
    kind, name, _, _ = ref.split('/')
    result = {'commit': commit, 'scope': 'system', 'metadata': expected['metadata']}
    if kind == 'app':
        require(not os.path.lexists(ROOT / 'overrides/global')
                and not os.path.lexists(ROOT / 'overrides' / name), 'confinement-override')
        # Public deployment metadata must retain the exact finite context. No
        # host filesystems, device access, network or sandbox bypass is declared.
        permissions = configparser.ConfigParser(interpolation=None, strict=True)
        permissions.read_string(run(['info', '--system', '--show-permissions', ref]).stdout)
        require(dict(permissions['Context']) == {
            'shared': 'ipc;', 'sockets': 'wayland;fallback-x11;'}, 'confinement')
        parser = configparser.ConfigParser(interpolation=None, strict=True)
        parser.read_string(read_deployed(location / f'export/share/applications/{name}.desktop').decode())
        entry = parser['Desktop Entry']
        title, = (title for _, app, title in assets.ASSETS if app == name)
        command = shlex.split(entry['Exec'])
        require(entry['Type'] == 'Application' and entry['Name'] == title
                and entry.get('X-Flatpak') == name and command[0] == '/usr/bin/flatpak'
                and command.count(name) == 1 and 'run' in command
                and '--command=onpc-test-application' in command
                and not entry.getboolean('Hidden', fallback=False)
                and not entry.getboolean('NoDisplay', fallback=False), 'launcher')
        exported = ROOT / f'exports/share/applications/{name}.desktop'
        require(exported.is_symlink() and exported.resolve(strict=True) ==
                location / f'export/share/applications/{name}.desktop', 'launcher-export')
        result.update(desktop_id=name + '.desktop', confinement='flatpak')
    return result


def verify(manifest, *, source):
    validate_manifest(manifest, current=True)
    saved = record()
    require(saved['manifest'] == manifest and saved['source'] == source
            and saved['pending'] is None, 'stale-baseline')
    require(installed() == set(manifest), 'missing-package')
    result = {ref: readback(ref, expected) for ref, expected in manifest.items()}
    require(record() == saved, 'record-changed')
    return result


def reconcile(source, *, runner):
    manifest = json.loads(read(INPUT / assets.MANIFEST))
    validate_manifest(manifest, current=True)
    hashes = json.loads(read(INPUT / 'SHA256SUMS.json'))
    require(type(hashes) is dict and set(hashes) == set(assets.declarations().values()), 'input-manifest')
    for name, digest in hashes.items():
        require(hashlib.sha256(read(INPUT / name, limit=1024 * 1024 * 1024)).hexdigest()
                == digest, 'input-digest')
    saved = record() if os.path.lexists(RECORD) else None
    found = installed()
    require(not any(os.path.lexists(ROOT / 'overrides' / name)
                    for name in ('global', *(item[1] for item in assets.ASSETS))),
            'confinement-override')
    # Refuse every unowned collision before the first package mutation.
    for ref in found:
        require(saved is not None, 'foreign-package')
        commit = run(['info', '--system', '--show-commit', ref]).stdout.strip()
        candidates = [saved['manifest'], saved['pending'] or saved['manifest']]
        matches = [value[ref] for value in candidates if value[ref]['commit'] == commit]
        require(bool(matches), 'foreign-package-digest')
        readback(ref, matches[0])
    desired = {'purpose': PURPOSE, 'source': source, 'manifest': manifest, 'pending': None}
    if saved == desired:
        return verify(manifest, source=source)
    require(saved is None or saved['pending'] is None or saved['manifest'] == manifest,
            'unfinished-other-update')
    publish({**desired, 'pending': (saved['pending'] or saved['manifest']) if saved else manifest})
    # Dict order is explicit: the declared runtime precedes its three apps.
    for ref, name in assets.declarations().items():
        if ref in found and run(['info', '--system', '--show-commit', ref]).stdout.strip() == manifest[ref]['commit']:
            continue
        runner.run(['/usr/bin/flatpak', 'install', '--system', '--noninteractive', '--assumeyes',
                    '--no-deps', '--no-related', '--or-update', '--bundle', str(INPUT / name)], timeout=1200)
        readback(ref, manifest[ref])
    publish(desired)
    return verify(manifest, source=source)
