"""Closed native-runtime bundle codec. Reads and checks bytes; never extracts.

The caller owns allocation, freezing build inputs and atomic publication. Guest
paths and native actions come only from the maintained finite declarations.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import struct
import tarfile
from types import SimpleNamespace

from tests.fixtures import baseline_assets, native_assets
from tools import fixture_provenance

SCHEMA = 1
MAX_MEMBER = 8 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
MAX_MANIFEST = 1024 * 1024
SUBSETS = ('native', 'riley-grid', 'baseline-child', 'activity', 'mechanical', 'trusted-hard',
           'trusted-soft', 'trusted-hard-launcher', 'trusted-soft-launcher',
           'command', 'whitespace', 'pattern', 'retention',
           'catalogue', 'controls', 'compatibility', 'legacy')
DEPENDENCIES = {
    'elf': {'class': 64, 'machine': 'x86_64',
            'interpreter': '/lib64/ld-linux-x86-64.so.2',
            'needed': ['libc.so.6'], 'glibc_max': '2.43'},
    'gui': {'interpreter': '/usr/bin/python3', 'modules': ['gi', 'cairo'],
            'gtk_min': '4.22'},
}
ABSENCES = [{'destination': '/usr/local/bin/onpc-test-catalog-fallback',
             'subsets': ['catalogue', 'legacy']}]
_HEX = re.compile('[0-9a-f]{64}')


def _fail(reason):
    raise ValueError('fixture:' + reason)


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def declarations():
    """Return ID -> descriptor, including source keys or literal desktop bytes."""
    accounts = {role: SimpleNamespace(pw_dir='@' + role + '@')
                for role in ('child', 'other', 'parent')}
    native = baseline_assets.native_files(accounts)
    catalogue = baseline_assets.catalogue_files(accounts)
    runtime = {destination for destination, _ in
               native_assets.source_destinations('@other@').values()}
    grid = {destination for destination, _ in
            native_assets.source_destinations('@child@').values()
            if destination.startswith(native_assets.PREFIX + '/')}
    grid.add('@child@/.local/share/applications/' + native_assets.desktop_id('A'))
    baseline_child = {destination for destination, _ in
                      native_assets.source_destinations('@child@').values()
                      if destination.startswith('@child@/.local/share/applications/')}
    trusted = native_assets.trusted_file_modes()
    result = {}
    for destination, (source, mode, owner) in (native | catalogue).items():
        subsets = {'legacy'}
        if destination in runtime:
            subsets.add('native')
        if destination in grid:
            subsets.add('riley-grid')
        if destination in baseline_child:
            subsets.add('baseline-child')
        if destination.startswith(native_assets.ACTIVITY_PREFIX + '/'):
            subsets.add('activity')
        if destination == baseline_assets.MECHANICAL:
            subsets.add('mechanical')
        if destination in catalogue:
            subsets.add('catalogue')
        if (destination in native_assets.legacy_executable_paths()
                or destination in {native_assets.PREFIX + '/' + filename
                                   for filename in native_assets.GUI_FILES}):
            subsets.add('compatibility')
        if destination in native and destination not in runtime | grid:
            if source in ('trusted-hard', 'trusted-soft'):
                subsets.add(source)
            elif destination.startswith('/usr/share/applications/'):
                for identity, (_, suffix) in native_assets.TRUSTED_NATIVE.items():
                    if destination.endswith('.' + suffix + '.desktop'):
                        subsets.add(identity + '-launcher')
            for identity, (target, suffix) in baseline_assets.NATIVE.items():
                if (destination == target or destination ==
                        '/usr/share/applications/com.puffyslippers.ONPCTest.' + suffix + '.desktop'
                        or identity == 'pattern' and destination ==
                        str(Path(target).with_name('Unrelated.AppImage'))):
                    subsets.add(identity)
            if (destination != baseline_assets.MECHANICAL
                    and 'activity' not in subsets
                    and not subsets & {'trusted-hard', 'trusted-soft',
                                       'trusted-hard-launcher', 'trusted-soft-launcher'}):
                subsets.add('controls')
        action = ('trust' if destination in trusted else
                  'native-execute' if mode == 0o755 and
                  (destination in runtime or source == 'mechanical') else
                  'native-open' if destination in runtime and mode == 0o644
                  and destination.startswith(native_assets.PREFIX + '/') else 'none')
        result[_digest(destination.encode())] = {
            'destination': destination, 'mode': mode, 'owner': owner,
            'source': source, 'subsets': sorted(subsets), 'native_action': action}
    return dict(sorted(result.items()))


def select(subsets):
    """Return the exact union of finite requested subsets (empty is allowed)."""
    if (type(subsets) not in (tuple, list) or
            any(type(name) is not str or name not in SUBSETS for name in subsets)
            or len(set(subsets)) != len(subsets)):
        _fail('subsets')
    return {key: value for key, value in declarations().items()
            if set(subsets).intersection(value['subsets'])}


def _json_value(value, depth=0):
    if depth > 16:
        _fail('json-depth')
    if value is None or type(value) is bool:
        return
    if type(value) is int and abs(value) <= 2 ** 63 - 1:
        return
    if type(value) is str and len(value) <= 16384:
        return
    if type(value) is list and len(value) <= 4096:
        for item in value:
            _json_value(item, depth + 1)
        return
    if type(value) is dict and len(value) <= 4096:
        for key, item in value.items():
            if type(key) is not str or not key or len(key) > 4096:
                _fail('json-key')
            _json_value(item, depth + 1)
        return
    _fail('json-value')


def _canonical(value):
    _json_value(value)
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')


def _decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _fail('duplicate-json-field')
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs,
                           parse_constant=lambda _: _fail('json-constant'))
        if _canonical(value) != raw:
            _fail('noncanonical-json')
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError('fixture:json') from error


def _inputs(value):
    from tools.artifact_inputs import NATIVE_RUNTIME_SOURCES
    if (type(value) is not dict or
            set(value) != {'source', 'toolchain', 'target', 'dependencies'}
            or any(type(value[key]) is not dict or not value[key]
                   for key in ('source', 'toolchain', 'dependencies'))):
        _fail('inputs')
    target = value['target']
    if (type(target) is not dict or
            set(target) != {'os', 'release', 'architecture'}
            or target['architecture'] != 'x86_64'
            or (target['os'], target['release']) not in
            (('ubuntu', '26.04'), ('fedora', '44'))
            or value['dependencies'] != DEPENDENCIES):
        _fail('target-or-dependencies')
    if len(_canonical(value)) > MAX_MANIFEST // 2:
        _fail('inputs-size')
    fixture_provenance.validate(value['toolchain'], target)
    if set(value['source']) != set(NATIVE_RUNTIME_SOURCES):
        _fail('source-inventory')
    for record in value['source'].values():
        if (type(record) is not dict or set(record) != {'sha256', 'length', 'mode'}
                or type(record['sha256']) is not str or _HEX.fullmatch(record['sha256']) is None
                or type(record['length']) is not int or not 0 <= record['length'] <= MAX_MEMBER
                or type(record['mode']) is not int or not 0 <= record['mode'] <= 0o777
                or not record['mode'] & 0o400 or record['mode'] & 0o002):
            _fail('source-record')


def verify_elf(data):
    """Independently bound ELF64 segments, loader, libraries and GLIBC needs."""
    def unpack(fmt, offset):
        size = struct.calcsize(fmt)
        if type(offset) is not int or offset < 0 or offset + size > len(data):
            _fail('elf-bounds')
        return struct.unpack_from(fmt, data, offset)
    if type(data) is not bytes or not 64 <= len(data) <= MAX_MEMBER:
        _fail('elf-length')
    header = unpack('<16sHHIQQQIHHHHHH', 0)
    ident, kind, machine, version, entry, phoff, _, flags, ehsize, phsize, phnum, _, _, _ = header
    if (ident[:7] != b'\x7fELF\x02\x01\x01' or ident[7] not in (0, 3)
            or ident[8:] != bytes(8) or kind not in (2, 3) or machine != 62
            or version != 1 or flags != 0 or ehsize != 64 or phsize != 56
            or not 1 <= phnum <= 128 or phoff < 64
            or phoff + phnum * phsize > len(data)):
        _fail('elf-header')
    segments, interpreters, dynamic = [], [], []
    for index in range(phnum):
        segment = unpack('<IIQQQQQQ', phoff + index * phsize)
        tag, perms, offset, address, _, length, memory, alignment = segment
        if (offset + length > len(data) or length > memory
                or alignment not in (0, 1) and
                (alignment & (alignment - 1) or address % alignment != offset % alignment)):
            _fail('elf-segment')
        segments.append(segment)
        if tag == 3:
            interpreters.append(data[offset:offset + length])
        if tag == 2:
            dynamic.append((offset, length, address))
    if interpreters != [DEPENDENCIES['elf']['interpreter'].encode() + b'\0'] or len(dynamic) != 1:
        _fail('elf-runtime')
    if not any(tag == 1 and perms & 1 and address <= entry < address + length
               for tag, perms, _, address, _, length, _, _ in segments):
        _fail('elf-entry')
    def locate(address, length):
        matches = [offset + address - base for tag, _, offset, base, _, size, _, _
                   in segments if tag == 1 and base <= address
                   and address + length <= base + size]
        if len(matches) != 1:
            _fail('elf-address')
        return matches[0]
    offset, length, address = dynamic[0]
    if locate(address, length) != offset:
        _fail('elf-dynamic-address')
    if length % 16 or not 16 <= length <= 65536:
        _fail('elf-dynamic')
    entries = {}
    ended = False
    for at in range(offset, offset + length, 16):
        tag, value = unpack('<qQ', at)
        if ended:
            if tag or value:
                _fail('elf-dynamic-tail')
        elif tag == 0:
            ended = True
        else:
            entries.setdefault(tag, []).append(value)
    if not ended or any(tag in entries for tag in
                        (15, 29, 0x6ffffefb, 0x6ffffefc, 0x7ffffffd, 0x7fffffff)):
        _fail('elf-dynamic-contract')
    def single(tag):
        values = entries.get(tag, [])
        if len(values) != 1:
            _fail('elf-dynamic-field')
        return values[0]
    strsize = single(10)
    if not 1 <= strsize <= MAX_MEMBER:
        _fail('elf-strings')
    strings = locate(single(5), strsize)
    def string(index):
        if not 0 <= index < strsize:
            _fail('elf-string-offset')
        end = data.find(b'\0', strings + index, strings + strsize)
        if end < 0:
            _fail('elf-string-termination')
        try:
            return data[strings + index:end].decode('ascii')
        except UnicodeError as error:
            raise ValueError('fixture:elf-string') from error
    if [string(index) for index in entries.get(1, [])] != ['libc.so.6']:
        _fail('elf-needed')
    if single(0x6fffffff) != 1:
        _fail('elf-version-count')
    need_address = single(0x6ffffffe)
    need = locate(need_address, 16)
    version, count, filename, auxiliary, following = unpack('<HHIII', need)
    if version != 1 or not 1 <= count <= 128 or string(filename) != 'libc.so.6' or following or auxiliary < 16:
        _fail('elf-version-need')
    address = need_address + auxiliary
    seen = set()
    required_versions = []
    for index in range(count):
        at = locate(address, 16)
        if at in seen:
            _fail('elf-version-cycle')
        seen.add(at)
        _, _, _, name, following = unpack('<IHHII', at)
        name = string(name)
        match = re.fullmatch(r'GLIBC_([0-9]+)\.([0-9]+)(?:\.([0-9]+))?', name)
        if (match is None or tuple(int(part or 0) for part in match.groups()) > (2, 43, 0)):
            _fail('elf-glibc-version')
        required_versions.append(name)
        if (index == count - 1 and following != 0) or (index < count - 1 and following < 16):
            _fail('elf-version-chain')
        address += following
    return {'class': 'ELF64', 'machine': 'x86_64',
            'interpreter': DEPENDENCIES['elf']['interpreter'], 'needed': ['libc.so.6'],
            'glibc_versions': sorted(set(required_versions)), 'sha256': _digest(data)}


def _header(key, size, mode):
    item = tarfile.TarInfo(key)
    item.size, item.mode = size, mode
    return item.tobuf(format=tarfile.USTAR_FORMAT)


def _tar(payloads, declared):
    out = io.BytesIO()
    for key in sorted(payloads):
        data = payloads[key]
        out.write(_header(key, len(data), declared[key]['mode']))
        out.write(data)
        out.write(bytes((-len(data)) % 512))
    out.write(bytes(1024))
    out.write(bytes((-out.tell()) % 10240))
    return out.getvalue()


def _read(directory, name, limit):
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=directory)
    try:
        before = os.fstat(descriptor)
        parent = os.fstat(directory)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit
                or before.st_mode & 0o022 or before.st_uid != parent.st_uid):
            _fail('file-type-or-size')
        with os.fdopen(descriptor, 'rb', closefd=False) as stream:
            data = stream.read(limit + 1)
        after = os.fstat(descriptor)
        identity = lambda info: (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
                                 info.st_uid, info.st_gid, info.st_size,
                                 info.st_mtime_ns, info.st_ctime_ns)
        if len(data) != before.st_size or identity(before) != identity(after):
            _fail('file-changed')
        return data
    finally:
        os.close(descriptor)


def _directory(output):
    path = Path(output).absolute()
    if path.resolve() != path:
        _fail('directory-symlink')
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    info = os.fstat(descriptor)
    if info.st_mode & 0o022:
        os.close(descriptor)
        _fail('directory-permissions')
    return descriptor


def _check_payloads(payloads, declared, inputs):
    if type(payloads) is not dict or set(payloads) != set(declared):
        _fail('payload-inventory')
    total, sources = 0, {}
    for key, descriptor in declared.items():
        data = payloads[key]
        if type(data) is not bytes or not 0 < len(data) <= MAX_MEMBER:
            _fail('member-length')
        total += len(data)
        source = descriptor['source']
        if type(source) is bytes:
            if data != source:
                _fail('literal-bytes')
        else:
            if source in sources and sources[source] != data:
                _fail('source-alias-bytes')
            sources[source] = data
        if descriptor['mode'] == 0o755:
            verify_elf(data)
    if total > MAX_TOTAL:
        _fail('total-length')
    executables = ('mechanical', 'A', 'H', 'S', 'N', 'trusted-hard',
                   'trusted-soft', 'trusted-activity')
    if len({_digest(sources[key]) for key in executables}) != len(executables):
        _fail('identity-collision')
    if sources['onpc-test-gui.py'] == sources['gtk_automation.py']:
        _fail('runtime-collision')
    for key, path in (('onpc-test-gui.py', 'tests/fixtures/gui_application.py'),
                      ('gtk_automation.py', 'common/oh_no_parent_control_ui/gtk_automation.py')):
        record = inputs['source'][path]
        if record['sha256'] != _digest(sources[key]) or record['length'] != len(sources[key]):
            _fail('source-payload-binding')
    return {key: verify_elf(sources[key]) for key in fixture_provenance.IDENTITIES}


def _verify(directory, target, complete):
    expected_files = {'fixture-manifest.json', 'payload.tar'} | ({'complete.json'} if complete else set())
    if set(os.listdir(directory)) != expected_files:
        _fail('bundle-inventory')
    raw = _read(directory, 'fixture-manifest.json', MAX_MANIFEST)
    manifest = _decode(raw)
    if (type(manifest) is not dict or set(manifest) !=
            {'schema', 'build_identity', 'inputs', 'members', 'absences', 'abi'}
            or type(manifest['schema']) is not int or manifest['schema'] != SCHEMA):
        _fail('manifest-schema')
    _inputs(manifest['inputs'])
    if manifest['build_identity'] != _digest(_canonical(manifest['inputs'])):
        _fail('build-identity')
    if target is not None and target != manifest['inputs']['target']['os']:
        _fail('target-mismatch')
    if _canonical(manifest['absences']) != _canonical(ABSENCES):
        _fail('absence-inventory')
    declared = declarations()
    members = manifest['members']
    if type(members) is not dict or set(members) != set(declared):
        _fail('member-inventory')
    for key, declaration in declared.items():
        member = members[key]
        fields = {name: value for name, value in declaration.items() if name != 'source'}
        if (type(member) is not dict or set(member) != set(fields) | {'length', 'sha256'}
                or _canonical({name: member[name] for name in fields}) != _canonical(fields)
                or type(member['length']) is not int or not 0 < member['length'] <= MAX_MEMBER
                or type(member['sha256']) is not str or _HEX.fullmatch(member['sha256']) is None):
            _fail('member-fields')
    if sum(member['length'] for member in members.values()) > MAX_TOTAL:
        _fail('total-length')
    archive = _read(directory, 'payload.tar', MAX_TOTAL + len(declared) * 1024 + 10240)
    payloads, offset = {}, 0
    for key in sorted(declared):
        member = members[key]
        size = member['length']
        if archive[offset:offset + 512] != _header(key, size, member['mode']):
            _fail('archive-header')
        offset += 512
        data = archive[offset:offset + size]
        if len(data) != size or _digest(data) != member['sha256']:
            _fail('member-checksum')
        payloads[key] = data
        offset += size
        padding = (-size) % 512
        if archive[offset:offset + padding] != bytes(padding):
            _fail('archive-padding')
        offset += padding
    final = offset + 1024
    final += (-final) % 10240
    if len(archive) != final or archive[offset:] != bytes(final - offset):
        _fail('archive-trailer')
    abi = _check_payloads(payloads, declared, manifest['inputs'])
    if _canonical(manifest['abi']) != _canonical(abi):
        _fail('abi-proof')
    if complete:
        marker = _decode(_read(directory, 'complete.json', 1024))
        if marker != {'schema': SCHEMA, 'content_identity': _digest(raw + archive)} or type(marker['schema']) is not int:
            _fail('completion')
    return manifest


def verify(output, target=None):
    """Verify a complete bundle without extraction; return its manifest."""
    if target is not None and (type(target) is not str or target not in ('ubuntu', 'fedora')):
        _fail('target')
    directory = _directory(output)
    try:
        return _verify(directory, target, True)
    except (OSError, OverflowError, struct.error) as error:
        raise ValueError('fixture:bundle-read') from error
    finally:
        os.close(directory)


def write(output, inputs, payloads):
    """Write into the caller's empty allocation; independently check then mark."""
    _inputs(inputs)
    declared = declarations()
    abi = _check_payloads(payloads, declared, inputs)
    manifest = {'schema': SCHEMA, 'inputs': inputs, 'abi': abi,
                'build_identity': _digest(_canonical(inputs)), 'absences': ABSENCES,
                'members': {key: {**{name: value for name, value in item.items() if name != 'source'},
                                  'length': len(payloads[key]), 'sha256': _digest(payloads[key])}
                            for key, item in declared.items()}}
    raw = _canonical(manifest)
    if len(raw) > MAX_MANIFEST:
        _fail('manifest-size')
    archive = _tar(payloads, declared)
    directory = _directory(output)
    try:
        if os.listdir(directory):
            _fail('output-not-empty')
        def put(name, data):
            descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=directory)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        put('fixture-manifest.json', raw)
        put('payload.tar', archive)
        _verify(directory, None, False)
        put('complete.json', _canonical({'schema': SCHEMA, 'content_identity': _digest(raw + archive)}))
        os.fsync(directory)
        return _verify(directory, None, True)
    finally:
        os.close(directory)
