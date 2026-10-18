"""Native bundle contracts with isolated byte fixtures and native-tool doubles."""
import copy
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile

import pytest

from tools import native_transaction_inputs as native


def _tar(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        for name, data in entries.items():
            entry = tarfile.TarInfo('./' + name)
            entry.size = len(data)
            entry.mode = 0o755
            archive.addfile(entry, io.BytesIO(data))
    return stream.getvalue()


def _cpio(name, data):
    def entry(path, contents):
        fields = [1, 0o100755, 0, 0, 1, 0, len(contents), 0, 0, 0, 0, len(path) + 1, 0]
        raw = b'070701' + b''.join(f'{value:08x}'.encode() for value in fields) + path.encode() + b'\0'
        raw += b'\0' * (-len(raw) % 4)
        raw += contents
        return raw + b'\0' * (-len(raw) % 4)
    return entry('./' + name, data) + entry('TRAILER!!!', b'')


@pytest.fixture(params=['deb', 'rpm'])
def inputs(request, tmp_path, monkeypatch):
    package_format = request.param
    pair = copy.deepcopy(native.PAIRS[package_format])
    payloads = {label: b'\x7fELF' + label.encode() + b'x' * (80424 - 4 - len(label))
                for label in ('old', 'new')}
    packages = {label: (label + ' native package').encode() for label in ('old', 'new')}
    downloads = {}
    for label in ('old', 'new'):
        spec = pair[label]
        spec['sha256'] = native._hash(packages[label])
        if package_format == 'deb':
            spec['size'] = len(packages[label])
        else:
            spec['executable_size'] = len(payloads[label])
            spec['executable_sha256'] = native._hash(payloads[label])
        downloads[spec['url']] = packages[label]
    monkeypatch.setitem(native.PAIRS, package_format, pair)
    key = b'fixture trusted key'
    monkeypatch.setattr(native, '_trusted_ubuntu_keyring', lambda path: key)
    monkeypatch.setattr(native, 'FEDORA_KEY_SHA256', native._hash(key))
    downloads[native.FEDORA_KEY_URL] = key
    if package_format == 'deb':
        for label in ('old', 'new'):
            spec = pair[label]
            index = gzip.compress((f"Package: {pair['package']}\nVersion: {spec['version']}\n"
                                   f"Architecture: {pair['architecture']}\nSHA256: {spec['sha256']}\n"
                                   f"Size: {spec['size']}\nFilename: {spec['url'].split('/ubuntu/', 1)[1]}\n").encode())
            base = 'https://archive.ubuntu.com/ubuntu/dists/' + spec['pocket'] + '/'
            downloads[base + 'main/binary-amd64/Packages.gz'] = index
            downloads[base + 'InRelease'] = ("-----BEGIN PGP SIGNED MESSAGE-----\nHash: SHA256\n\n"
                f"Origin: Ubuntu\nSuite: {spec['pocket']}\nSHA256:\n {native._hash(index)} {len(index)} main/binary-amd64/Packages.gz\n"
                "-----BEGIN PGP SIGNATURE-----\nfixture\n").encode()
    state = {'calls': [], 'wrong_version': False, 'wrong_arch': False, 'bad_signature': False,
             'same_payload': False, 'failed_fetch': None, 'changed_file': None, 'signer': 'short'}

    def fetch(url):
        if url == state['failed_fetch']:
            raise native.NativeInputError('interrupted download')
        return downloads[url]

    def run(command, *, binary=False):
        state['calls'].append(command)
        tool = command[0]
        label = 'new' if any(Path(str(value)).name.startswith('new.') for value in command) else 'old'
        if tool == 'gpgv':
            if state['bad_signature']:
                raise native.NativeInputError('native verification command failed: gpgv')
            return '[GNUPG:] VALIDSIG 1234567890 2026-10-18 1 0 4 0 1 10 01 1234567890\n'
        if tool == 'dpkg':
            assert command[1:3] == ['--compare-versions', pair['new']['version']]
            return ''
        if tool == 'dpkg-deb':
            if command[1] == '-f':
                version = '999' if state['wrong_version'] else pair[label]['version']
                arch = 'arm64' if state['wrong_arch'] else pair['architecture']
                return f"Package: {pair['package']}\nVersion: {version}\nArchitecture: {arch}\nDepends: libc6 (>= 2.38), libcap2 (>= 1:2.10), libselinux1 (>= 3.1~)\n"
            if command[1] == '--ctrl-tarfile':
                return _tar({'control': b'control', 'md5sums': b'hashes'})
            data = payloads['old' if state['same_payload'] else label]
            return _tar({pair['executable'].lstrip('/'): data})
        if tool == 'readelf':
            data = Path(command[-1]).read_bytes()
            selected = 'old' if data == payloads['old'] else 'new'
            return ' Build ID: ' + pair[selected]['build_id'] + '\n'
        if tool == 'gpg':
            return 'fpr:::::::::' + native.FEDORA_FINGERPRINT + ':\n'
        if tool == 'rpmkeys':
            if state['bad_signature']:
                return 'Header V4 RSA/SHA256 Signature, key ID 6d9f90a6: NOKEY\nPayload SHA256 digest: OK\n'
            signer = ('key fingerprint: ' + native.FEDORA_FINGERPRINT.lower()
                      if state['signer'] == 'fingerprint' else
                      'key ID ' + ('dbfcf71c6d9f90a6' if state['signer'] == 'long' else '6d9f90a6'))
            return 'Header OpenPGP V4 RSA/SHA256 signature, ' + signer + ': OK\nPayload SHA256 digest: OK\n'
        if tool == 'rpm':
            if '--eval' in command:
                return '1\n'
            if '--queryformat' in command:
                version = '0:999-1.fc44' if state['wrong_version'] else pair[label]['version']
                arch = 'aarch64' if state['wrong_arch'] else pair['architecture']
                return f"{pair['package']}\n{version}\n{arch}\n"
            if '--requires' in command:
                return 'dbus\nlibc.so.6(GLIBC_2.38)(64bit)\n'
            return ''
        if tool == 'rpm2cpio':
            return _cpio(pair['executable'].lstrip('/'), payloads['old' if state['same_payload'] else label])
        raise AssertionError(command)

    monkeypatch.setattr(native, '_fetch', fetch)
    monkeypatch.setattr(native, '_run', run)
    output = tmp_path / 'bundle'
    output.mkdir(mode=0o700)
    return package_format, pair, output, state, downloads


def test_prepare_repeat_and_read_only_verify(inputs):
    package_format, pair, output, state, _ = inputs
    manifest = native.prepare(output, package_format=package_format)
    before = {path.name: (path.stat().st_ino, path.stat().st_mtime_ns, path.read_bytes()) for path in output.iterdir()}
    assert native.prepare(output, package_format=package_format) == manifest
    assert native.verify(output) == manifest
    assert before == {path.name: (path.stat().st_ino, path.stat().st_mtime_ns, path.read_bytes()) for path in output.iterdir()}
    assert manifest['selection'] == pair
    assert manifest['packages']['old']['executable']['sha256'] != manifest['packages']['new']['executable']['sha256']
    tools = {command[0] for command in state['calls']}
    assert {'gpgv', 'dpkg', 'dpkg-deb', 'readelf'} <= tools if package_format == 'deb' else {'gpg', 'rpm', 'rpmkeys', 'rpm2cpio'} <= tools


def test_controller_stages_actual_verified_schema_and_preflight_consumes_it(inputs, tmp_path):
    import system_runner
    from tests.integration import native_transaction

    package_format, _, output, _, _ = inputs
    manifest = native.prepare(output, package_format=package_format)
    destination = tmp_path / 'attempt-input'
    destination.mkdir(mode=0o700)
    selected = destination / 'selected-inputs.json'
    selected.write_bytes(b'{"files":{"helper.py":{"sha256":"selected"}}}')
    selected.chmod(0o600)
    options = {'package_format': package_format, 'baseline_provenance_sha256': 'a' * 64,
               'selected_inputs_sha256': native._digest(selected)}
    binding = system_runner.stage_native_assets(output, destination, **options)
    copied = destination / 'native-transaction'
    assert binding['native_manifest_sha256'] == native._digest(copied / native.MANIFEST_NAME)
    assert native.verify(copied) == manifest
    selection, packages, paths = native_transaction.validate_manifest(manifest, copied)
    assert selection == manifest['selection'] and packages == manifest['packages']
    assert set(paths) == {'old', 'new'}
    assert system_runner.stage_native_assets(output, destination, **options) == binding
    assert system_runner.verify_native_assets(destination, **options) == binding


@pytest.mark.parametrize('fault', ['wrong_version', 'wrong_arch', 'bad_signature', 'same_payload'])
def test_native_identity_and_signature_refusals(inputs, fault):
    package_format, _, output, state, _ = inputs
    state[fault] = True
    with pytest.raises(native.NativeInputError):
        native.prepare(output, package_format=package_format)
    assert not (output / native.MANIFEST_NAME).exists()


@pytest.mark.parametrize('fault', ['tampered', 'missing', 'extra', 'symlink', 'hardlink', 'unsafe_mode'])
def test_read_only_verifier_refuses_tree_and_bytes(inputs, fault):
    package_format, _, output, _, _ = inputs
    native.prepare(output, package_format=package_format)
    package = output / ('old.' + package_format)
    if fault == 'tampered':
        package.write_bytes(b'tampered')
    elif fault == 'missing':
        package.unlink()
    elif fault == 'extra':
        (output / 'foreign').write_bytes(b'foreign')
    elif fault == 'symlink':
        package.unlink()
        package.symlink_to(output / ('new.' + package_format))
    elif fault == 'hardlink':
        os.link(package, output / 'foreign')
    else:
        package.chmod(0o666)
    before = sorted(path.name for path in output.iterdir())
    with pytest.raises((native.NativeInputError, FileNotFoundError)):
        native.verify(output)
    assert before == sorted(path.name for path in output.iterdir())


def test_interrupted_download_retry_and_changed_selection_refusal(inputs):
    package_format, pair, output, state, _ = inputs
    state['failed_fetch'] = pair['new']['url']
    with pytest.raises(native.NativeInputError, match='interrupted download'):
        native.prepare(output, package_format=package_format)
    old_inode = (output / ('old.' + package_format)).stat().st_ino
    state['failed_fetch'] = None
    native.prepare(output, package_format=package_format)
    assert (output / ('old.' + package_format)).stat().st_ino == old_inode
    pair['new']['version'] = 'substituted'
    with pytest.raises(native.NativeInputError):
        native.verify(output)


def test_mid_write_retry_uses_recorded_inode(inputs, monkeypatch):
    package_format, _, output, _, _ = inputs
    output, intent = native._begin(output, package_format)
    name = 'old.' + package_format
    data = b'complete package bytes'
    original_replace = native.os.replace

    def interrupted_replace(source, destination):
        if Path(destination).name == name:
            # Model a crash after some bytes reached the registered temp inode.
            Path(source).write_bytes(b'partial')
            raise OSError('interrupted placement')
        return original_replace(source, destination)

    monkeypatch.setattr(native.os, 'replace', interrupted_replace)
    with pytest.raises(OSError, match='interrupted placement'):
        native._place(output, intent, name, data)
    pending = json.loads((output / native.INTENT_NAME).read_text())['pending'][name]
    partial = output / pending['temporary']
    inode = partial.stat().st_ino
    monkeypatch.setattr(native.os, 'replace', original_replace)
    output, intent = native._begin(output, package_format)
    native._place(output, intent, name, data)
    assert (output / name).read_bytes() == data
    assert (output / name).stat().st_ino == inode


def test_mid_write_replaced_inode_refuses(inputs, monkeypatch):
    package_format, _, output, _, _ = inputs
    output, intent = native._begin(output, package_format)
    name = 'old.' + package_format
    original_replace = native.os.replace

    def interrupted_replace(source, destination):
        if Path(destination).name == name:
            raise OSError('interrupted placement')
        return original_replace(source, destination)

    monkeypatch.setattr(native.os, 'replace', interrupted_replace)
    with pytest.raises(OSError):
        native._place(output, intent, name, b'package')
    partial = output / intent['pending'][name]['temporary']
    replacement = output / 'replacement'
    replacement.write_bytes(b'foreign')
    replacement.chmod(0o600)
    original_replace(replacement, partial)
    monkeypatch.setattr(native.os, 'replace', original_replace)
    with pytest.raises(native.NativeInputError, match='identity changed'):
        native._begin(output, package_format)


def test_stage_repeat_collision_and_binding(inputs, tmp_path):
    package_format, _, source, _, _ = inputs
    manifest = native.prepare(source, package_format=package_format)
    destination = tmp_path / 'stage'
    destination.mkdir(mode=0o700)
    assert native.stage(source, destination) == manifest
    assert native.stage(source, destination) == manifest
    source_intent = json.loads((source / native.INTENT_NAME).read_text())
    stage_intent = json.loads((destination / native.INTENT_NAME).read_text())
    assert source_intent['root'] != stage_intent['root']
    assert native.verify(destination)['binding_sha256'] == manifest['binding_sha256']
    collision = tmp_path / 'collision'
    collision.mkdir(mode=0o700)
    (collision / 'foreign').write_bytes(b'foreign')
    (collision / 'foreign').chmod(0o600)
    with pytest.raises(native.NativeInputError, match='must be empty'):
        native.stage(source, collision)
    with pytest.raises(native.NativeInputError, match='overlap'):
        native.stage(source, source)


def test_stage_interrupted_retry_preserves_verified_files(inputs, tmp_path, monkeypatch):
    package_format, _, source, _, _ = inputs
    manifest = native.prepare(source, package_format=package_format)
    destination = tmp_path / 'stage'
    destination.mkdir(mode=0o700)
    original_place = native._place

    def interrupted_place(output, intent, name, data):
        if name == 'old.' + package_format:
            raise OSError('interrupted staging')
        return original_place(output, intent, name, data)

    monkeypatch.setattr(native, '_place', interrupted_place)
    with pytest.raises(OSError, match='interrupted staging'):
        native.stage(source, destination)
    identities = {path.name: path.stat().st_ino for path in destination.iterdir() if path.name != native.INTENT_NAME}
    monkeypatch.setattr(native, '_place', original_place)
    assert native.stage(source, destination) == manifest
    assert all((destination / name).stat().st_ino == inode for name, inode in identities.items())


@pytest.mark.parametrize('inputs', ['deb'], indirect=True)
def test_deb_signed_index_tamper_is_not_native_signature_success(inputs):
    package_format, pair, output, _, downloads = inputs
    url = 'https://archive.ubuntu.com/ubuntu/dists/' + pair['old']['pocket'] + '/main/binary-amd64/Packages.gz'
    downloads[url] += b'tamper'
    with pytest.raises(native.NativeInputError, match='index authentication'):
        native.prepare(output, package_format=package_format)


@pytest.mark.parametrize('inputs', ['rpm'], indirect=True)
def test_rpm_pinned_key_refuses_download_substitution(inputs):
    package_format, _, output, _, downloads = inputs
    downloads[native.FEDORA_KEY_URL] = b'foreign key'
    with pytest.raises(native.NativeInputError, match='signing key bytes'):
        native.prepare(output, package_format=package_format)


@pytest.mark.parametrize('inputs', ['rpm'], indirect=True)
@pytest.mark.parametrize('signer', ['long', 'fingerprint'])
def test_rpm_native_signer_formats_identify_the_same_pinned_key(inputs, signer):
    package_format, _, output, state, _ = inputs
    state['signer'] = signer
    manifest = native.prepare(output, package_format=package_format)
    assert manifest['verification']['fingerprint'] == native.FEDORA_FINGERPRINT
    assert native.verify(output) == manifest


def test_subprocess_failure_is_refusal(monkeypatch):
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0], stderr='invalid signature')
    monkeypatch.setattr(native.subprocess, 'run', fail)
    with pytest.raises(native.NativeInputError, match='gpgv'):
        native._run(['gpgv', 'untrusted.InRelease'])


def test_foreign_owner_refusal(inputs, monkeypatch):
    _, _, output, _, _ = inputs
    original = Path.lstat

    def foreign(path):
        info = original(path)
        if path == output:
            values = list(info)
            values[4] = 987654
            return os.stat_result(values)
        return info

    monkeypatch.setattr(Path, 'lstat', foreign)
    with pytest.raises(native.NativeInputError, match='foreign native input owner'):
        native._safe_tree(output)


def test_read_only_verification_detects_native_tool_side_mutation(inputs, monkeypatch):
    package_format, _, output, _, _ = inputs
    native.prepare(output, package_format=package_format)
    original = native._measure

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        path = output / ('old.' + package_format)
        path.write_bytes(path.read_bytes())
        return result

    monkeypatch.setattr(native, '_measure', changed)
    with pytest.raises(native.NativeInputError, match='changed during read-only'):
        native.verify(output)


@pytest.mark.parametrize('record', [[], {'package_format': []}, {'package_format': 'deb', 'files': []}])
def test_malformed_manifest_is_controlled_refusal(inputs, record):
    _, _, output, _, _ = inputs
    (output / native.MANIFEST_NAME).write_text(json.dumps(record))
    (output / native.MANIFEST_NAME).chmod(0o600)
    with pytest.raises(native.NativeInputError):
        native.verify(output)
