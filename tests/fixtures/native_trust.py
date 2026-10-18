"""Finite trusted-native fixture schema, shared by offline and live readers."""
import hashlib
import json
import re
import stat

try:
    from baseline_assets import TRUSTED_NATIVE, MECHANICAL, trusted_file_modes
except ImportError:
    from tests.fixtures.baseline_assets import TRUSTED_NATIVE, MECHANICAL, trusted_file_modes

TRUST_RECORD = '/var/lib/onpc-baseline-native-trust.json'
TRUST_FILE = '/etc/fapolicyd/trust.d/onpc-baseline-native.trust'
TRUST_PENDING = TRUST_FILE + '.onpc-baseline-new'
TRUST_PURPOSE = 'onpc-trusted-native-fixtures-v1'
FIXTURE_RECORD = '/var/lib/onpc-baseline-fixtures.json'
BACKEND_CONFIG = '/etc/fapolicyd/fapolicyd.conf'
BACKEND_RECORD = '/var/lib/onpc-baseline-native-backend.json'
BACKEND_PENDING = BACKEND_CONFIG + '.onpc-baseline-new'
BACKEND_PURPOSE = 'onpc-native-file-backend-v1'


def _metadata_diagnostic(category, sourcekind, metadata, canonical, native_gid=None):
    fields = {
        'sourcekind': sourcekind,
        'root_owner': int(metadata['st_uid'] == 0),
        'root_group': int(metadata['st_gid'] == 0),
        'canonical': int(bool(canonical)),
        'regular': int(stat.S_ISREG(metadata['st_mode'])),
        'singlylinked': int(metadata['st_nlink'] == 1),
        'mode': f"{stat.S_IMODE(metadata['st_mode']):04o}",
    }
    if native_gid is not None:
        fields['native_group'] = int(metadata['st_gid'] == native_gid)
    return ('baseline:fixtures-' + category + ';'
            + ';'.join(f'{key}={value}' for key, value in fields.items()))


class ForeignTrustMetadataError(ValueError):
    """Safe fixed metadata predicates; never retain a foreign path or account."""
    def __init__(self, *, legacy, metadata, canonical):
        super().__init__(_metadata_diagnostic('foreign-trust-metadata',
                         'legacy' if legacy else 'fragment', metadata, canonical))


class OwnedTrustMetadataError(ForeignTrustMetadataError):
    """Diagnose the fixed owned fragment while preserving every identity guard."""
    def __init__(self, *, metadata, canonical, native_gid=None):
        ValueError.__init__(self, _metadata_diagnostic('owned-trust-metadata',
                            'owned-fragment', metadata, canonical, native_gid))


def require(value):
    if not value:
        raise ValueError('baseline:fixtures-unsafe-or-stale; run tools/prepare-vm')


def native_tool_paths(os_id):
    """Closed canonical package locations, including Fedora's bin/sbin merge."""
    require(os_id in ('ubuntu', 'fedora'))
    root = '/usr/sbin' if os_id == 'ubuntu' else '/usr/bin'
    return {'daemon': root + '/fapolicyd', 'cli': root + '/fapolicyd-cli'}


def _backend_line(contents, os_id):
    require(os_id in ('ubuntu', 'fedora') and isinstance(contents, bytes)
            and 0 < len(contents) <= 65536)
    matches = list(re.finditer(rb'(?m)^([ \t]*trust[ \t]*=[ \t]*)([^\r\n#]*)(.*)$', contents))
    require(len(matches) == 1)
    match = matches[0]
    sources = [value.strip() for value in match[2].split(b',')]
    native = b'debdb' if os_id == 'ubuntu' else b'rpmdb'
    require(sources in ([native, b'file'], [b'file', native]) or
            (os_id == 'ubuntu' and sources == [b'debdb']))
    return match, sources


def file_backend_sources(contents, os_id):
    return [value.decode('ascii') for value in _backend_line(contents, os_id)[1]]


def file_backend_config(contents, os_id):
    """Enable only the recognized native file backend, preserving other bytes."""
    match, sources = _backend_line(contents, os_id)
    if b'file' in sources:
        return contents
    return (contents[:match.start(2)] + match[2].replace(b'debdb', b'debdb,file', 1)
            + contents[match.end(2):])


def validate_backend_record(record):
    require(isinstance(record, dict) and set(record) == {
        'purpose', 'os_id', 'before_hex', 'after_hex', 'metadata', 'complete'}
        and record['purpose'] == BACKEND_PURPOSE and record['os_id'] in ('ubuntu', 'fedora')
        and type(record['complete']) is bool)
    for key in ('before_hex', 'after_hex'):
        require(isinstance(record[key], str) and len(record[key]) <= 131072
                and re.fullmatch(r'(?:[0-9a-f]{2})+', record[key]) is not None)
    require(file_backend_config(bytes.fromhex(record['before_hex']), record['os_id'])
            == bytes.fromhex(record['after_hex']))
    metadata = record['metadata']
    require(isinstance(metadata, dict) and set(metadata) == {'mode', 'uid', 'gid'}
            and type(metadata['mode']) is int and metadata['mode'] in (0o600, 0o640, 0o644)
            and type(metadata['uid']) is int and metadata['uid'] == 0
            and type(metadata['gid']) is int and 0 <= metadata['gid'] < 2 ** 32)
    return record


def validate_backend_shape(backend, os_id):
    require(os_id in ('ubuntu', 'fedora'))
    require(isinstance(backend, dict) and set(backend) == {
        'config_sha256', 'record_sha256', 'mode', 'uid', 'gid', 'sources'})
    require(all(isinstance(backend[key], str) and re.fullmatch('[0-9a-f]{64}', backend[key]) is not None
                for key in ('config_sha256', 'record_sha256')))
    native = 'debdb' if os_id == 'ubuntu' else 'rpmdb'
    require(type(backend['mode']) is int and backend['mode'] in (0o600, 0o640, 0o644)
            and type(backend['uid']) is int and backend['uid'] == 0
            and type(backend['gid']) is int and 0 <= backend['gid'] < 2 ** 32
            and isinstance(backend['sources'], list)
            and backend['sources'] in ([native, 'file'], ['file', native]))
    return backend


def validate_backend_provenance(backend, config_contents, record_contents, os_id):
    """Pure verification of enabled bytes, exact receipt and preserved metadata."""
    validate_backend_shape(backend, os_id)
    require(hashlib.sha256(config_contents).hexdigest() == backend['config_sha256']
            and hashlib.sha256(record_contents).hexdigest() == backend['record_sha256']
            and file_backend_config(config_contents, os_id) == config_contents
            and file_backend_sources(config_contents, os_id) == backend['sources'])
    record = validate_backend_record(json.loads(record_contents))
    require(record['complete'] and record['os_id'] == os_id
            and bytes.fromhex(record['after_hex']) == config_contents
            and record['metadata'] == {key: backend[key] for key in ('mode', 'uid', 'gid')})
    return backend


def trust_entries(content):
    """Read the public SHA256 format, refusing extra and duplicate paths."""
    require(isinstance(content, bytes) and len(content) <= 16384)
    entries = {}
    for line in content.decode('ascii').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        fields = line.split()
        require(len(fields) == 3 and fields[0] in trusted_file_modes()
                and fields[0] not in entries and fields[1].isdigit()
                and re.fullmatch('[0-9a-f]{64}', fields[2]) is not None)
        entries[fields[0]] = {'size': int(fields[1]), 'sha256': fields[2]}
    return entries


def database_row(line):
    """Native dumps preserve spaces in paths; size/hash are the last fields."""
    source = line.split(None, 1)
    if len(source) != 2:
        return None
    fields = source[1].rsplit(None, 2)
    return [source[0], *fields] if len(fields) == 3 else None


def validate_trusted_shape(record, *, pending=False, allow_legacy=False):
    """Validate durable completed or interrupted intent without adopting paths."""
    keys = {
        'purpose', 'preparation_script_sha256', 'fixture_record_sha256', 'files',
        'native', 'trust_file_sha256'}
    require(isinstance(record, dict) and (set(record) == keys | {'backend', 'trust_file_metadata'} or
            (allow_legacy and set(record) in (keys, keys | {'backend'})))
            and record['purpose'] == TRUST_PURPOSE)
    for key in ('preparation_script_sha256', 'fixture_record_sha256', 'trust_file_sha256'):
        if key == 'trust_file_sha256' and pending and record[key] is None:
            continue
        require(isinstance(record[key], str) and re.fullmatch('[0-9a-f]{64}', record[key]) is not None)
    modes = trusted_file_modes()
    legacy_paths = {p for p, _ in TRUSTED_NATIVE.values()}
    require(isinstance(record['files'], dict) and (set(record['files']) == set(modes)
            or (allow_legacy and set(record['files']) == legacy_paths)))
    for path, spec in record['files'].items():
        require(isinstance(spec, dict) and set(spec) == {'sha256', 'size', 'mode', 'uid', 'gid'}
                and type(spec['size']) is int and spec['size'] > 0
                and type(spec['mode']) is int and spec['mode'] == modes[path]
                and type(spec['uid']) is int and type(spec['gid']) is int and spec['uid'] == spec['gid'] == 0
                and isinstance(spec['sha256'], str) and re.fullmatch('[0-9a-f]{64}', spec['sha256']) is not None)
    require(len({spec['sha256'] for path, spec in record['files'].items()
                 if modes[path] == 0o755}) == sum(modes[path] == 0o755 for path in record['files']))
    native = record['native']
    native_keys = {'os_id', 'package', 'version', 'daemon_sha256', 'cli_sha256'}
    require(isinstance(native, dict) and set(native) == (
        native_keys | {'service_gid'} if 'trust_file_metadata' in record else native_keys)
        and native['os_id'] in ('ubuntu', 'fedora') and native['package'] == 'fapolicyd'
        and isinstance(native['version'], str) and re.fullmatch('[A-Za-z0-9.+:~_-]+', native['version']) is not None)
    require(all(isinstance(native[key], str) and re.fullmatch('[0-9a-f]{64}', native[key]) is not None
                for key in ('daemon_sha256', 'cli_sha256')))
    if 'trust_file_metadata' in record:
        require(type(native['service_gid']) is int and 0 < native['service_gid'] < 2 ** 32)
        metadata = record['trust_file_metadata']
        require(isinstance(metadata, dict) and set(metadata) == {'mode', 'uid', 'gid'}
                and type(metadata['mode']) is int and metadata['mode'] == 0o600
                and type(metadata['uid']) is int and metadata['uid'] == 0
                and type(metadata['gid']) is int and metadata['gid'] == native['service_gid'])
    if 'backend' in record:
        validate_backend_shape(record['backend'], native['os_id'])
    return record


def validate_trusted_record(record, fixture_record, preparation_script_sha256):
    """Pure validator binding native provenance to the exact baseline inputs."""
    validate_trusted_shape(record)
    require(record['preparation_script_sha256'] == preparation_script_sha256)
    require(record['fixture_record_sha256'] == hashlib.sha256(fixture_record).hexdigest())
    fixture = json.loads(fixture_record)
    require(fixture.get('purpose') == 'onpc-reusable-fixtures-v1' and fixture.get('pending') is None)
    for path, spec in record['files'].items():
        require({k: v for k, v in spec.items() if k != 'size'} == fixture['files'].get(path))
        require(spec['sha256'] != fixture['files'][MECHANICAL]['sha256'])
    return record
