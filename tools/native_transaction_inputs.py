"""Finite, authenticated native inputs for core-installation task 004b.

This is a host bundle builder/verifier, never an installer or a dependency
resolver. The caller owns a registered allocation. Consumers only call verify.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tarfile
import tempfile
import uuid


MANIFEST_NAME = 'native-inputs.json'
INTENT_NAME = '.native-inputs-intent.json'
UBUNTU_KEYRING = Path('/usr/share/keyrings/ubuntu-archive-keyring.gpg')
FEDORA_KEY_URL = 'https://src.fedoraproject.org/rpms/fedora-repos/raw/f44/f/RPM-GPG-KEY-fedora-44-primary'
FEDORA_KEY_SHA256 = '93642aec521a1e5e96dd715f7ae0ec0850ebc9de09a94ce03cae5263f26cc18a'
FEDORA_FINGERPRINT = '36F612DCF27F7D1A48A835E4DBFCF71C6D9F90A6'
PAIRS = {
    'deb': {
        'pair_id': 'ubuntu26.04-bubblewrap', 'target': 'onpc-Ubuntu26.04',
        'package': 'bubblewrap', 'architecture': 'amd64', 'executable': '/usr/bin/bwrap',
        'old': {'version': '0.11.1-1', 'size': 50622,
                'build_id': '975168fbb14fa09c3dd20125151089641969f717',
                'sha256': '090bb705b6d49213b288f19d78be78a55a1b72843efb12eae73ab5cca0f54b8d',
                'pocket': 'resolute',
                'url': 'https://archive.ubuntu.com/ubuntu/pool/main/b/bubblewrap/bubblewrap_0.11.1-1_amd64.deb'},
        'new': {'version': '0.11.1-1ubuntu0.3', 'size': 51032,
                'build_id': '38527d4f72857f1f39e1d6af03851b9dd831febc',
                'sha256': 'd3a6c1b6b0e0474eaed6dbd055c0d601fd875af153976a0dc4aae75f4ea10868',
                'pocket': 'resolute-security',
                'url': 'https://archive.ubuntu.com/ubuntu/pool/main/b/bubblewrap/bubblewrap_0.11.1-1ubuntu0.3_amd64.deb'},
    },
    'rpm': {
        'pair_id': 'fedora44-xdg-dbus-proxy', 'target': 'onpc-Fedora44',
        'package': 'xdg-dbus-proxy', 'architecture': 'x86_64', 'executable': '/usr/bin/xdg-dbus-proxy',
        'old': {'version': '0:0.1.6-4.fc44',
                'sha256': '2197bd5a209e07c1a63bab22b0d1b262861186f850baa876a4bbcc3f916e9dbc',
                'executable_sha256': '1bfd8870b59939c54580bd7cb29ae7d2cffd8b348dbe9aeec7a3687e349e62c4',
                'executable_size': 61568,
                'url': 'https://dl.fedoraproject.org/pub/fedora/linux/releases/44/Everything/x86_64/os/Packages/x/xdg-dbus-proxy-0.1.6-4.fc44.x86_64.rpm'},
        'new': {'version': '0:0.1.9-1.fc44',
                'sha256': '14827cdd90771c751cb8cabff0764b26821dc0cb4a7b617f0e033eabcab63b81',
                'executable_sha256': '90d90a08aa46bc99b8fa226295be5869935e00a0f307f1dee4d78988e277d5af',
                'executable_size': 65728,
                'url': 'https://dl.fedoraproject.org/pub/fedora/linux/updates/44/Everything/x86_64/Packages/x/xdg-dbus-proxy-0.1.9-1.fc44.x86_64.rpm'},
    },
}


class NativeInputError(ValueError):
    """An exact native input is missing, incompatible or untrusted."""


def pair_for_format(package_format):
    if not isinstance(package_format, str):
        raise NativeInputError('unsupported native package format')
    try:
        return copy.deepcopy(PAIRS[package_format])
    except KeyError as error:
        raise NativeInputError('unsupported native package format') from error


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _run(command, *, binary=False):
    from tools.test_storage import scratch_descriptors
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=not binary,
                                env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C',
                                     'HOME': '/nonexistent'}, pass_fds=scratch_descriptors(), timeout=180)
    except (OSError, subprocess.SubprocessError) as error:
        detail = str(error)
        if isinstance(error, subprocess.CalledProcessError):
            detail = (error.stderr or error.stdout or b'' if binary else error.stderr or error.stdout or '')
            if isinstance(detail, bytes):
                detail = detail.decode('utf-8', errors='replace')
            detail = f'exit {error.returncode}: ' + detail.strip()[-1200:]
        raise NativeInputError('native verification command failed: ' + command[0] + ': ' + detail) from error
    return result.stdout


def _safe_tree(output):
    output = Path(output)
    if not output.is_absolute() or output.resolve() != output or not output.is_dir():
        raise NativeInputError('unsafe native input directory')
    owner = output.lstat().st_uid
    repository_owner = Path(__file__).resolve().parents[1].stat().st_uid
    if owner not in (os.geteuid(), repository_owner):
        raise NativeInputError('foreign native input owner')
    from tools import test_storage
    managed = test_storage.contains(output)
    for ancestor in output.parents:
        info = ancestor.lstat()
        # Shared sticky scratch parents are permitted by the storage owner.
        # They cannot replace a caller-owned child. Non-sticky writable parents
        # and ancestry controlled by another unprivileged owner are refused.
        if managed and not ancestor.is_relative_to(test_storage.BASE):
            # The shared storage implementation owns traversal above its root,
            # including developer-owned checkout ancestors and bind mounts.
            continue
        allowed_owners = (0, owner, Path('/').stat().st_uid)
        if managed and ancestor == test_storage.BASE:
            # This traversable boundary is shared by caller-owned inputs and
            # root-owned staging; only the boundary may use the checkout owner.
            allowed_owners += (repository_owner,)
        if (info.st_uid not in allowed_owners or not stat.S_ISDIR(info.st_mode)
                or (info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX)):
            raise NativeInputError('unsafe native input ancestor')
    for entry in (output, *output.rglob('*')):
        info = entry.lstat()
        if (info.st_uid != owner or info.st_mode & 0o022 or entry.resolve() != entry
                or not (stat.S_ISDIR(info.st_mode) or
                        (stat.S_ISREG(info.st_mode) and info.st_nlink == 1))):
            raise NativeInputError('unsafe native input tree: ' + entry.name)
    return output


def _trusted_ubuntu_keyring(path):
    path = Path(path)
    # The builder cannot promote a downloaded key to archive trust. An override
    # is useful for a distribution-managed local keyring, subject to this gate.
    if not path.is_absolute() or path.resolve() != path:
        raise NativeInputError('unsafe Ubuntu archive keyring')
    for entry in (path, *path.parents):
        info = entry.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode):
            raise NativeInputError('untrusted Ubuntu archive keyring ownership')
    if not path.is_file() or path.stat().st_nlink != 1:
        raise NativeInputError('invalid Ubuntu archive keyring')
    return path.read_bytes()


def _fetch(url):
    return _run(['curl', '-fsSL', '--max-time', '120', url], binary=True)


def _load(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value, dict):
            raise ValueError('record must be an object')
        return value
    except (OSError, ValueError) as error:
        raise NativeInputError('invalid native input record: ' + path.name) from error


def _atomic_json(path, value):
    # Shared scratch and managed allocations reside on the same disk. Keeping
    # unpublished records outside the bundle permits retry after process loss
    # without adopting an unrecorded speculative file. Cross-device publication
    # refuses rather than falling back to a non-atomic copy.
    from tools.test_storage import scratch_directory
    descriptor, name = tempfile.mkstemp(prefix='onpc-native-record-', dir=scratch_directory())
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(_canonical(value) + b'\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        _sync_directory(path.parent)
    finally:
        if os.path.lexists(name):
            os.unlink(name)


def _sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def publish_record(path, value):
    """Publish an owner's already validated binding record atomically."""
    _atomic_json(Path(path), value)


def _place(output, intent, name, data):
    expected = _hash(data)
    planned = intent['files'].get(name)
    if planned is not None and planned != expected:
        raise NativeInputError('native input source changed during interrupted preparation: ' + name)
    path = output / name
    if path.exists():
        if planned != expected or _digest(path) != expected:
            raise NativeInputError('native input placement collision: ' + name)
        if name in intent['pending']:
            pending = intent['pending'][name]
            if os.path.lexists(output / pending['temporary']):
                raise NativeInputError('native placement has competing pending file')
            del intent['pending'][name]
            _atomic_json(output / INTENT_NAME, intent)
        return
    intent['files'][name] = expected
    _atomic_json(output / INTENT_NAME, intent)
    pending = intent['pending'].get(name)
    if pending is None:
        from tools.test_storage import scratch_directory
        temporary = output / ('.partial-' + intent['token'] + '-' + name)
        descriptor, scratch_name = tempfile.mkstemp(prefix='onpc-native-placement-', dir=scratch_directory())
        info = os.fstat(descriptor)
        pending = {'temporary': temporary.name, 'identity': [info.st_dev, info.st_ino, info.st_uid]}
        intent['pending'][name] = pending
        try:
            _atomic_json(output / INTENT_NAME, intent)
            if os.path.lexists(temporary):
                raise NativeInputError('native pending placement collision')
            os.replace(scratch_name, temporary)
            _sync_directory(output)
        except BaseException:
            os.close(descriptor)
            raise
        finally:
            if os.path.lexists(scratch_name):
                os.unlink(scratch_name)
    else:
        temporary = output / pending['temporary']
        descriptor = os.open(temporary, os.O_WRONLY | os.O_NOFOLLOW)
        info = os.fstat(descriptor)
        if ([info.st_dev, info.st_ino, info.st_uid] != pending['identity']
                or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o022):
            os.close(descriptor)
            raise NativeInputError('interrupted native placement identity changed')
    with os.fdopen(descriptor, 'wb') as stream:
        stream.truncate(0)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if os.path.lexists(path):
        raise NativeInputError('native input placement collision: ' + name)
    os.replace(temporary, path)
    _sync_directory(output)
    del intent['pending'][name]
    _atomic_json(output / INTENT_NAME, intent)


def _deb_fields(text):
    result = {}
    key = None
    for line in text.splitlines():
        if line.startswith((' ', '\t')) and key is not None:
            result[key] += '\n' + line
        elif line:
            if ':' not in line:
                raise NativeInputError('invalid Debian metadata')
            key, value = line.split(':', 1)
            value = value.lstrip(' ')
            if key in result:
                raise NativeInputError('duplicate Debian metadata field')
            result[key] = value
    return result


def _release_content(raw):
    text = raw.decode('utf-8')
    if not text.startswith('-----BEGIN PGP SIGNED MESSAGE-----\n'):
        raise NativeInputError('missing signed Ubuntu Release metadata')
    try:
        body = text.split('\n\n', 1)[1].split('\n-----BEGIN PGP SIGNATURE-----', 1)[0]
    except IndexError as error:
        raise NativeInputError('invalid Ubuntu InRelease') from error
    return '\n'.join(line[2:] if line.startswith('- ') else line for line in body.splitlines())


def _verify_deb_chain(output, label, pair):
    spec = pair[label]
    release = output / (label + '.InRelease')
    receipt = _run(['gpgv', '--keyring', str(output / 'ubuntu-keyring.gpg'),
                    '--status-fd', '1', str(release)])
    if '[GNUPG:] VALIDSIG ' not in receipt:
        raise NativeInputError('Ubuntu Release signature not acknowledged')
    body = _release_content(release.read_bytes())
    fields = _deb_fields(body)
    if fields.get('Suite') != spec['pocket'] or fields.get('Origin') != 'Ubuntu':
        raise NativeInputError('wrong Ubuntu signed pocket')
    index = output / (label + '.Packages.gz')
    selected = [line.split() for line in fields.get('SHA256', '').splitlines()
                if line.split() and line.split()[-1] == 'main/binary-amd64/Packages.gz']
    if (len(selected) != 1 or len(selected[0]) != 3 or selected[0][0] != _digest(index)
            or selected[0][1] != str(index.stat().st_size)):
        raise NativeInputError('Ubuntu Packages index authentication failed')
    try:
        stanzas = [_deb_fields(value) for value in gzip.decompress(index.read_bytes()).decode().split('\n\n') if value.strip()]
    except (OSError, UnicodeError) as error:
        raise NativeInputError('invalid Ubuntu Packages index') from error
    matches = [entry for entry in stanzas if entry.get('Package') == pair['package']
               and entry.get('Version') == spec['version'] and entry.get('Architecture') == pair['architecture']]
    expected_filename = spec['url'].split('/ubuntu/', 1)[1]
    if (len(matches) != 1 or matches[0].get('SHA256') != spec['sha256']
            or matches[0].get('Size') != str(spec['size'])
            or matches[0].get('Filename') != expected_filename):
        raise NativeInputError('selected DEB is absent from authenticated Packages')
    # Retain stable signer identities rather than ephemeral tool paths/times.
    return {'valid_signatures': [line for line in receipt.splitlines() if line.startswith('[GNUPG:] VALIDSIG ')]}


def _tar_executable(raw, target):
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:*') as archive:
        matches = [entry for entry in archive.getmembers() if entry.name.removeprefix('./') == target.lstrip('/')]
        if len(matches) != 1 or not matches[0].isfile():
            raise NativeInputError('missing or linked measured DEB executable')
        entry = matches[0]
        data = archive.extractfile(entry).read()
        return data, entry.uid, entry.gid, entry.mode


def _cpio_executable(raw, target):
    """Read newc bytes without extracting package-controlled paths to the host."""
    offset = 0
    matches = []
    while offset < len(raw):
        header = raw[offset:offset + 110]
        if len(header) != 110 or header[:6] not in (b'070701', b'070702'):
            raise NativeInputError('invalid RPM cpio payload')
        try:
            fields = [int(header[6 + 8 * n:14 + 8 * n], 16) for n in range(13)]
        except ValueError as error:
            raise NativeInputError('invalid RPM cpio header') from error
        _, mode, uid, gid, links, _, size, _, _, _, _, namesize, _ = fields
        offset += 110
        namebytes = raw[offset:offset + namesize]
        if not namesize or not namebytes.endswith(b'\0'):
            raise NativeInputError('invalid RPM cpio filename')
        name = namebytes[:-1].decode('utf-8')
        offset = (offset + namesize + 3) & ~3
        data = raw[offset:offset + size]
        if len(data) != size:
            raise NativeInputError('truncated RPM cpio payload')
        offset = (offset + size + 3) & ~3
        if name == 'TRAILER!!!':
            break
        if name.removeprefix('./') == target.lstrip('/'):
            if not stat.S_ISREG(mode) or links != 1:
                raise NativeInputError('linked measured RPM executable')
            matches.append((data, uid, gid, stat.S_IMODE(mode)))
    if len(matches) != 1:
        raise NativeInputError('missing or duplicate measured RPM executable')
    return matches[0]


def _identity(output, label, package_format, pair):
    path = output / (label + '.' + package_format)
    spec = pair[label]
    if _digest(path) != spec['sha256'] or ('size' in spec and path.stat().st_size != spec['size']):
        raise NativeInputError('native package bytes mismatch: ' + label)
    if package_format == 'deb':
        fields = _deb_fields(_run(['dpkg-deb', '-f', str(path)]))
        name, version, architecture = (fields.get(key) for key in ('Package', 'Version', 'Architecture'))
        dependencies = {key: fields.get(key, '') for key in ('Depends', 'Pre-Depends', 'Recommends', 'Breaks', 'Conflicts', 'Replaces')}
        controls = _run(['dpkg-deb', '--ctrl-tarfile', str(path)], binary=True)
        with tarfile.open(fileobj=io.BytesIO(controls)) as archive:
            control_files = sorted(entry.name.removeprefix('./') for entry in archive.getmembers() if entry.isfile())
        if control_files != ['control', 'md5sums']:
            raise NativeInputError('unexpected DEB scripts or triggers')
        dependencies['control_files'] = control_files
        payload = _tar_executable(_run(['dpkg-deb', '--fsys-tarfile', str(path)], binary=True), pair['executable'])
    else:
        values = _run(['rpm', '-qp', '--queryformat', '%{NAME}\n%{EPOCHNUM}:%{VERSION}-%{RELEASE}\n%{ARCH}\n', str(path)]).splitlines()
        if len(values) != 3:
            raise NativeInputError('invalid RPM native identity')
        name, version, architecture = values
        dependencies = {}
        for option in ('--requires', '--conflicts', '--obsoletes', '--recommends', '--suggests', '--supplements', '--enhances', '--scripts', '--triggers', '--filetriggers'):
            dependencies[option.removeprefix('--')] = _run(['rpm', '-qp', option, str(path)]).strip().splitlines()
        if any(dependencies[key] for key in dependencies if key != 'requires'):
            raise NativeInputError('unexpected RPM scripts, triggers or companion relationships')
        payload = _cpio_executable(_run(['rpm2cpio', str(path)], binary=True), pair['executable'])
    if (name, version, architecture) != (pair['package'], spec['version'], pair['architecture']):
        raise NativeInputError('native package identity mismatch: ' + label)
    data, uid, gid, mode = payload
    digest = _hash(data)
    if ((uid, gid, mode) != (0, 0, 0o755) or not data.startswith(b'\x7fELF')
            or len(data) != spec.get('executable_size', 80424)
            or digest != spec.get('executable_sha256', digest)):
        raise NativeInputError('native executable identity mismatch: ' + label)
    executable = {'path': pair['executable'], 'sha256': digest, 'size': len(data),
                  'uid': uid, 'gid': gid, 'mode': mode}
    if package_format == 'deb':
        from tools.test_storage import scratch_directory
        with tempfile.TemporaryDirectory(prefix='onpc-native-elf-', dir=scratch_directory()) as temporary:
            measured = Path(temporary) / 'executable'
            measured.write_bytes(data)
            notes = _run(['readelf', '--notes', str(measured)])
            found = re.findall(r'Build ID: ([0-9a-f]+)', notes)
            if found != [spec['build_id']]:
                raise NativeInputError('native executable build ID mismatch: ' + label)
            executable['build_id'] = found[0]
    return {'path': path.name, 'name': name, 'version': version, 'architecture': architecture,
            'sha256': spec['sha256'], 'dependencies': dependencies,
            'executable': executable}


def _verify_rpm_trust(output):
    from tools.test_storage import scratch_directory
    key = output / 'fedora44-key.asc'
    if _digest(key) != FEDORA_KEY_SHA256:
        raise NativeInputError('Fedora signing key bytes mismatch')
    with tempfile.TemporaryDirectory(prefix='onpc-native-rpm-', dir=scratch_directory()) as temporary:
        home = Path(temporary)
        home.chmod(0o700)
        fingerprints = _run(['gpg', '--batch', '--homedir', str(home), '--with-colons', '--show-keys', str(key)])
        found = [row.split(':')[9] for row in fingerprints.splitlines() if row.startswith('fpr:')]
        if found != [FEDORA_FINGERPRINT]:
            raise NativeInputError('Fedora signing fingerprint mismatch')
        database = home / 'rpmdb'
        database.mkdir()
        _run(['rpm', '--dbpath', str(database), '--initdb'])
        _run(['rpm', '--dbpath', str(database), '--import', str(key)])
        receipts = {}
        for label in ('old', 'new'):
            result = _run(['rpmkeys', '--dbpath', str(database), '--checksig', '--verbose', str(output / (label + '.rpm'))])
            if ('NOT OK' in result or 'NOKEY' in result or 'NOTTRUSTED' in result
                    or not re.search(r'Signature.*(?:key ID (?:dbfcf71c)?6d9f90a6|key fingerprint: '
                                     + FEDORA_FINGERPRINT + r'): OK', result, re.IGNORECASE)
                    or not re.search(r'(Payload|payload).*digest: OK', result)):
                raise NativeInputError('Fedora RPM native signature/digest verification failed: ' +
                    label + ': ' + result.replace(str(output), '<bundle>').strip()[-1200:])
            receipts[label] = result.replace(str(output / (label + '.rpm')), label + '.rpm').strip().splitlines()
    return {'key_sha256': FEDORA_KEY_SHA256, 'fingerprint': FEDORA_FINGERPRINT,
            'native_signature_and_payload_digest': receipts,
            'key_source_url': FEDORA_KEY_URL}


def _measure(output, package_format, ubuntu_keyring):
    pair = pair_for_format(package_format)
    if package_format == 'deb':
        trusted = _trusted_ubuntu_keyring(ubuntu_keyring)
        if (output / 'ubuntu-keyring.gpg').read_bytes() != trusted:
            raise NativeInputError('retained Ubuntu keyring differs from local trust')
        trust = {'keyring_sha256': _hash(trusted), 'local_trust': str(ubuntu_keyring),
                 **{label: _verify_deb_chain(output, label, pair) for label in ('old', 'new')}}
        _run(['dpkg', '--compare-versions', pair['new']['version'], 'gt', pair['old']['version']])
    else:
        trust = _verify_rpm_trust(output)
        result = _run(['rpm', '--eval', '%{lua:print(rpm.vercmp("0.1.9","0.1.6"))}']).strip()
        if result != '1':
            raise NativeInputError('native RPM version ordering failed')
    packages = {label: _identity(output, label, package_format, pair) for label in ('old', 'new')}
    if (packages['old']['sha256'] == packages['new']['sha256']
            or packages['old']['executable']['sha256'] == packages['new']['executable']['sha256']):
        raise NativeInputError('native pair has identical package or executable bytes')
    return {'schema_version': 1, 'pair_id': pair['pair_id'], 'target': pair['target'],
            'package_format': package_format, 'selection': pair, 'packages': packages, 'verification': trust}


def _expected_files(package_format):
    files = {'old.' + package_format, 'new.' + package_format}
    return files | ({'ubuntu-keyring.gpg', 'old.InRelease', 'new.InRelease', 'old.Packages.gz', 'new.Packages.gz'}
                    if package_format == 'deb' else {'fedora44-key.asc'})


def _snapshot(output):
    _safe_tree(output)
    result = {}
    for path in (output, *output.rglob('*')):
        info = path.lstat()
        result[str(path.relative_to(output))] = [info.st_dev, info.st_ino, info.st_uid,
            info.st_gid, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
            _digest(path) if stat.S_ISREG(info.st_mode) else None]
    return result


def verify(output, *, package_format=None, ubuntu_keyring=UBUNTU_KEYRING):
    """Read-only verification; temporary native verifier state uses shared scratch."""
    output = _safe_tree(output)
    snapshot = _snapshot(output)
    manifest = _load(output / MANIFEST_NAME)
    package_format = package_format or manifest.get('package_format')
    pair_for_format(package_format)
    expected = _expected_files(package_format)
    if set(path.name for path in output.iterdir()) != expected | {MANIFEST_NAME, INTENT_NAME}:
        raise NativeInputError('native input layout mismatch')
    if (not isinstance(manifest.get('files'), dict) or set(manifest['files']) != expected
            or any(not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value)
                   for value in manifest['files'].values())):
        raise NativeInputError('native input file inventory mismatch')
    if any(_digest(output / name) != digest for name, digest in manifest['files'].items()):
        raise NativeInputError('native input retained file digest mismatch')
    measured = _measure(output, package_format, ubuntu_keyring)
    measured['files'] = manifest['files']
    measured['binding_sha256'] = _hash(_canonical(measured))
    if measured != manifest:
        raise NativeInputError('native input manifest does not match independent verification')
    intent = _load(output / INTENT_NAME)
    info = output.stat()
    if (intent.get('root') != [info.st_dev, info.st_ino, info.st_uid] or intent.get('pending') != {}
            or intent.get('selection') != measured['selection'] or intent.get('files') != measured['files']):
        raise NativeInputError('native input preparation ownership mismatch')
    if _snapshot(output) != snapshot:
        raise NativeInputError('native inputs changed during read-only verification')
    return manifest


def _begin(output, package_format):
    output = _safe_tree(output)
    if output.stat().st_uid != os.geteuid():
        raise NativeInputError('native input preparation requires caller ownership')
    pair = pair_for_format(package_format)
    info = output.stat()
    identity = [info.st_dev, info.st_ino, info.st_uid]
    if (output / INTENT_NAME).exists():
        intent = _load(output / INTENT_NAME)
        if (set(intent) != {'schema_version', 'root', 'selection', 'files', 'pending', 'token'}
                or intent['schema_version'] != 1 or intent['root'] != identity or intent['selection'] != pair
                or not isinstance(intent['token'], str) or not re.fullmatch('[0-9a-f]{32}', intent['token'])
                or not isinstance(intent['files'], dict)):
            raise NativeInputError('native preparation ownership mismatch')
        if not set(intent['files']).issubset(_expected_files(package_format)):
            raise NativeInputError('native preparation intent file mismatch')
        if any(not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value)
               for value in intent['files'].values()):
            raise NativeInputError('invalid native preparation file digest')
        if not isinstance(intent['pending'], dict) or not set(intent['pending']).issubset(intent['files']):
            raise NativeInputError('invalid native pending inventory')
        never_placed = []
        for name, pending in intent['pending'].items():
            if (not isinstance(pending, dict) or set(pending) != {'temporary', 'identity'}
                    or pending['temporary'] != '.partial-' + intent['token'] + '-' + name):
                raise NativeInputError('invalid native pending identity')
            temporary = output / pending['temporary']
            if temporary.exists():
                current = temporary.stat()
                if [current.st_dev, current.st_ino, current.st_uid] != pending['identity']:
                    raise NativeInputError('interrupted native placement identity changed')
            elif not (output / name).exists():
                # The empty inode was recorded in shared scratch, but process
                # loss preceded its atomic placement. No bundle file is adopted.
                never_placed.append(name)
        allowed = set(intent['files']) | {INTENT_NAME} | {value['temporary'] for value in intent['pending'].values()}
        if any(path.name not in allowed for path in output.iterdir()):
            raise NativeInputError('foreign native preparation entry')
        for name, digest in intent['files'].items():
            if (output / name).exists() and _digest(output / name) != digest:
                raise NativeInputError('interrupted native file differs from recorded identity: ' + name)
        renamed = [name for name, pending in intent['pending'].items()
                   if (output / name).exists() and not (output / pending['temporary']).exists()]
        for name in renamed + never_placed:
            del intent['pending'][name]
        if renamed or never_placed:
            _atomic_json(output / INTENT_NAME, intent)
    else:
        if any(output.iterdir()):
            raise NativeInputError('native preparation allocation must be empty')
        intent = {'schema_version': 1, 'root': identity, 'selection': pair, 'files': {}, 'pending': {}, 'token': uuid.uuid4().hex}
        _atomic_json(output / INTENT_NAME, intent)
    return output, intent


def prepare(output, *, package_format, ubuntu_keyring=UBUNTU_KEYRING):
    """Prepare exactly one finite pair in a caller-registered empty allocation.

    Published repeats verify without writes. Interrupted preparation reuses only
    already recorded exact files; changed downloads and foreign entries refuse.
    """
    output = _safe_tree(output)
    if (output / MANIFEST_NAME).exists():
        return verify(output, package_format=package_format, ubuntu_keyring=ubuntu_keyring)
    output, intent = _begin(output, package_format)
    pair = pair_for_format(package_format)
    if package_format == 'deb':
        _place(output, intent, 'ubuntu-keyring.gpg', _trusted_ubuntu_keyring(ubuntu_keyring))
        for label in ('old', 'new'):
            base = 'https://archive.ubuntu.com/ubuntu/dists/' + pair[label]['pocket'] + '/'
            for suffix, url in (('.InRelease', base + 'InRelease'),
                                ('.Packages.gz', base + 'main/binary-amd64/Packages.gz')):
                name = label + suffix
                if not (output / name).exists():
                    _place(output, intent, name, _fetch(url))
    else:
        if not (output / 'fedora44-key.asc').exists():
            _place(output, intent, 'fedora44-key.asc', _fetch(FEDORA_KEY_URL))
    for label in ('old', 'new'):
        name = label + '.' + package_format
        if not (output / name).exists():
            data = _fetch(pair[label]['url'])
            if _hash(data) != pair[label]['sha256']:
                raise NativeInputError('downloaded native package digest mismatch: ' + label)
            _place(output, intent, name, data)
    manifest = _measure(output, package_format, ubuntu_keyring)
    manifest['files'] = {name: _digest(output / name) for name in sorted(_expected_files(package_format))}
    manifest['binding_sha256'] = _hash(_canonical(manifest))
    _atomic_json(output / MANIFEST_NAME, manifest)
    return verify(output, package_format=package_format, ubuntu_keyring=ubuntu_keyring)


def stage(source, destination, *, package_format=None, ubuntu_keyring=UBUNTU_KEYRING):
    """Copy the exact verified input into a reserved staging child, with retry.

    The parent owns allocation/retention and selected-input/baseline binding.
    Source and destination must be disjoint. Staging never writes the source.
    """
    source = _safe_tree(source)
    destination = _safe_tree(destination)
    if source == destination or source in destination.parents or destination in source.parents:
        raise NativeInputError('native staging source and destination overlap')
    manifest = verify(source, package_format=package_format, ubuntu_keyring=ubuntu_keyring)
    package_format = manifest['package_format']
    snapshot = {path.name: (path.stat().st_dev, path.stat().st_ino, _digest(path))
                for path in source.iterdir()}
    if (destination / MANIFEST_NAME).exists():
        copied = verify(destination, package_format=package_format, ubuntu_keyring=ubuntu_keyring)
        if copied != manifest:
            raise NativeInputError('native staging published input mismatch')
    else:
        destination, intent = _begin(destination, package_format)
        for name in sorted(manifest['files']):
            data = (source / name).read_bytes()
            if _hash(data) != manifest['files'][name]:
                raise NativeInputError('native staging source bytes changed: ' + name)
            _place(destination, intent, name, data)
        copied = _measure(destination, package_format, ubuntu_keyring)
        copied['files'] = {name: _digest(destination / name) for name in sorted(manifest['files'])}
        copied['binding_sha256'] = _hash(_canonical(copied))
        if copied != manifest:
            raise NativeInputError('native staging copied input mismatch')
        _atomic_json(destination / MANIFEST_NAME, copied)
    _safe_tree(source)
    if (verify(source, package_format=package_format, ubuntu_keyring=ubuntu_keyring) != manifest
            or {path.name: (path.stat().st_dev, path.stat().st_ino, _digest(path))
                for path in source.iterdir()} != snapshot):
        raise NativeInputError('native staging source changed while copying')
    return verify(destination, package_format=package_format, ubuntu_keyring=ubuntu_keyring)
