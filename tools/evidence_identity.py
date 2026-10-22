"""Strict logical evidence metadata; JSON paths never grant filesystem authority.

The bundle reader separately pins owners, allocations and physical bytes. These
pure validators bind that verified inventory to exact immutable logical claims.
"""
import copy
import hashlib
import json
from pathlib import PurePosixPath
import re
import stat
import unicodedata

MAX_ENTRIES = 60000
MAX_METADATA = 64 * 1024 ** 2
MAX_BYTES = 1024 ** 3
SCHEMA = 'onpc-evidence-record'
VERSION = 1
CONTEXT_KEYS = {'repository', 'workflow', 'owner', 'run', 'task', 'check',
                'attempt', 'target', 'inputs_sha256', 'sources_sha256'}
RECORD_KEYS = {'schema', 'version', 'context', 'record_id', 'status',
               'completeness', 'members', 'dependencies', 'cleanup', 'closure_sha256'}
MEMBER_KEYS = {'member_id', 'role', 'original_path', 'source_allocation',
               'bytes', 'sha256', 'required'}


class MalformedEvidence(ValueError):
    """Unrecognized, ambiguous or noncanonical evidence metadata."""


class EvidenceIntegrityError(ValueError):
    """Recognized metadata disagrees with its hashes, inventory or closure."""


class EvidenceContextError(ValueError):
    """Verified evidence cannot establish the requested exact claim."""


def _text(value, *, empty=False):
    if not isinstance(value, str):
        raise MalformedEvidence('evidence: expected a string')
    try:
        length = len(value.encode('utf-8'))
    except UnicodeError as error:
        raise MalformedEvidence('evidence: invalid UTF-8 string') from error
    if ((not empty and not value) or length > 4096
            or any(unicodedata.category(char) == 'Cc' for char in value)):
        raise MalformedEvidence('evidence: invalid or oversized string')
    return value


def _json(value, depth=0):
    if depth > 64:
        raise MalformedEvidence('evidence: metadata nesting limit exceeded')
    if value is None or type(value) in (bool, int):
        return
    if isinstance(value, str):
        _text(value, empty=True)
    elif type(value) is list:
        if len(value) > MAX_ENTRIES:
            raise MalformedEvidence('evidence: metadata entry limit exceeded')
        for item in value:
            _json(item, depth + 1)
    elif type(value) is dict:
        if len(value) > MAX_ENTRIES:
            raise MalformedEvidence('evidence: metadata entry limit exceeded')
        for key, item in value.items():
            _text(key)
            _json(item, depth + 1)
    else:
        # Wire identities have no floating-point fields, including finite floats.
        raise MalformedEvidence('evidence: unsupported JSON value')


def encoded(value):
    """Canonical JSON matching evidence_bundle.encoded, with strict inputs."""
    _json(value)
    try:
        result = json.dumps(value, sort_keys=True, separators=(',', ':'),
                            ensure_ascii=True, allow_nan=False).encode('ascii')
    except (ValueError, OverflowError) as error:
        raise MalformedEvidence('evidence: unencodable JSON') from error
    if len(result) > MAX_METADATA:
        raise MalformedEvidence('evidence: metadata byte limit exceeded')
    return result


def decoded(value):
    """Decode JSON without silently collapsing duplicate object keys."""
    if not isinstance(value, (str, bytes)) or len(value) > MAX_METADATA:
        raise MalformedEvidence('evidence: invalid JSON input')
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise MalformedEvidence('evidence: duplicate JSON key')
            result[key] = item
        return result
    try:
        result = json.loads(value, object_pairs_hook=unique)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise MalformedEvidence('evidence: invalid JSON') from error
    encoded(result)
    return result


def digest(value):
    """SHA-256 of canonical JSON, never of implicit string or byte coercions."""
    return hashlib.sha256(encoded(value)).hexdigest()


def _object(value, keys, name):
    if type(value) is not dict or set(value) != keys:
        raise MalformedEvidence(f'evidence: invalid {name} fields')


def _integer(value, *, minimum=0, maximum=None):
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise MalformedEvidence('evidence: invalid integer')


def _hex(value, length=64):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{%d}' % length, value) is None:
        raise MalformedEvidence('evidence: invalid hash or token')


def _choice(value, choices):
    if not isinstance(value, str) or value not in choices:
        raise MalformedEvidence('evidence: invalid enum value')


def _path(value, *, relative=False):
    _text(value)
    parts = value.split('/')
    if (value.startswith('/') == relative or any(part in ('', '.', '..')
            for part in (parts if relative else parts[1:]))):
        raise MalformedEvidence('evidence: invalid provenance path')
    for part in parts:
        if (part in ('snapshot.json', '.ssh', 'ssh-key', 'ssh-key.pub', 'id_rsa',
                     'id_ed25519', 'id_ecdsa', 'credentials.json')
                or part.endswith(('.pem', '.key'))):
            raise MalformedEvidence('evidence: credentials are not evidence')
    return PurePosixPath(value)


def _destination(value):
    """A lexical document-relative locator; checkout containment is caller-owned."""
    _text(value)
    if (value.startswith('/') or any(part in ('', '.') for part in value.split('/'))
            or any(char in value for char in ('\\', '?', '#', ':', '%'))):
        raise MalformedEvidence('evidence: invalid relative locator')
    return value


def validate_repository(value):
    _object(value, {'root', 'device', 'inode', 'uid'}, 'repository')
    _path(value['root'])
    for key in ('device', 'inode'):
        _integer(value[key], minimum=1)
    _integer(value['uid'])


def validate_owner(value, *, repository=None):
    _object(value, {'repository_sha256', 'caller', 'journal', 'identity'}, 'owner')
    _hex(value['repository_sha256'])
    _object(value['caller'], {'uid', 'gid'}, 'caller')
    for item in value['caller'].values():
        _integer(item)
    _path(value['journal'])
    identity = value['identity']
    _object(identity, {'device', 'inode', 'mode', 'uid', 'gid'}, 'directory identity')
    for key in ('device', 'inode'):
        _integer(identity[key], minimum=1)
    for key in ('mode', 'uid', 'gid'):
        _integer(identity[key])
    if not stat.S_ISDIR(identity['mode']) or identity['mode'] & 0o077:
        raise MalformedEvidence('evidence: owner directory is not private')
    if repository is not None:
        validate_repository(repository)
        if (value['repository_sha256'] != digest(repository)
                or value['caller']['uid'] != repository['uid']):
            raise EvidenceContextError('evidence: owner belongs to another checkout or caller')


def validate_allocation(value):
    _object(value, {'path', 'device', 'inode', 'mode', 'journal', 'run'}, 'allocation')
    _path(value['path'])
    _path(value['journal'])
    for key in ('device', 'inode'):
        _integer(value[key], minimum=1)
    _integer(value['mode'])
    if value['mode'] != 0o700:
        raise MalformedEvidence('evidence: allocation mode must be 0700')
    _hex(value['run'], 32)


def _file_identity(value, allocation, size):
    if type(value) is not list or len(value) != 10:
        raise MalformedEvidence('evidence: invalid file identity')
    for item in value:
        _integer(item)
    if (not value[0] or not value[1] or not stat.S_ISREG(value[2])
            or value[2] & 0o002 or value[5] != 1):
        raise MalformedEvidence('evidence: unsafe file identity')
    if value[0] != allocation['device'] or value[6] != size:
        raise EvidenceIntegrityError('evidence: file identity disagrees with allocation or size')


def validate_context(value):
    _object(value, CONTEXT_KEYS, 'context')
    validate_repository(value['repository'])
    validate_owner(value['owner'], repository=value['repository'])
    for key in ('workflow', 'task', 'check'):
        _text(value[key])
    # A workflow is either a registered selector or a checkout-relative document.
    if '/' in value['workflow']:
        _path(value['workflow'], relative=True)
    _text(value['target'], empty=True)
    for key in ('run', 'attempt'):
        _hex(value[key], 32)
    for key in ('inputs_sha256', 'sources_sha256'):
        _hex(value[key])


def record_id(context):
    validate_context(context)
    return digest(dict(schema=SCHEMA, version=VERSION, context=context))


def member_id(record, member):
    _hex(record)
    if type(member) is not dict or not {'role', 'original_path', 'sha256'} <= set(member):
        raise MalformedEvidence('evidence: invalid member identity input')
    _choice(member['role'], {'result', 'input', 'command', 'junit', 'tap',
                             'cleanup', 'diagnostic', 'media'})
    _path(member['original_path'])
    _hex(member['sha256'])
    return digest(dict(record_id=record, role=member['role'],
                       original_path=member['original_path'], sha256=member['sha256']))


def _ordered(values, key, name):
    if type(values) is not list or len(values) > MAX_ENTRIES:
        raise MalformedEvidence(f'evidence: invalid {name} list')
    keys = [key(item) for item in values]
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise MalformedEvidence(f'evidence: unsorted or duplicate {name}')


def _references(values):
    if type(values) is not list:
        raise MalformedEvidence('evidence: invalid dependency list')
    for item in values:
        _object(item, {'record_id', 'closure_sha256'}, 'record reference')
        _hex(item['record_id'])
        _hex(item['closure_sha256'])
    _ordered(values, lambda item: item['record_id'], 'record references')


def _cleanup(value, owner, members):
    _object(value, {'state', 'record_members', 'scope'}, 'cleanup')
    _choice(value['state'], {'complete', 'failed', 'pending', 'not_applicable'})
    scope = value['scope']
    _object(scope, {'owner', 'resources'}, 'cleanup scope')
    validate_owner(scope['owner'])
    if scope['owner'] != owner:
        raise EvidenceContextError('evidence: cleanup belongs to another owner')
    resources = scope['resources']
    if type(resources) is not list:
        raise MalformedEvidence('evidence: invalid cleanup resources')
    for item in resources:
        _object(item, {'kind', 'id', 'disposition'}, 'cleanup resource')
        _text(item['kind'])
        _text(item['id'])
        _choice(item['disposition'], {'cleaned', 'preserved', 'not_owned'})
    _ordered(resources, lambda item: (item['kind'], item['id']), 'cleanup resources')
    refs = value['record_members']
    if type(refs) is not list:
        raise MalformedEvidence('evidence: invalid cleanup members')
    for item in refs:
        _hex(item)
    _ordered(refs, lambda item: item, 'cleanup members')
    available = {item['member_id'] for item in members if item['role'] == 'cleanup'}
    if not set(refs) <= available:
        raise EvidenceIntegrityError('evidence: cleanup member missing or has wrong role')
    if value['state'] == 'not_applicable' and (resources or refs):
        raise EvidenceIntegrityError('evidence: inapplicable cleanup declares resources or members')


def _record(record):
    _object(record, RECORD_KEYS, 'record')
    if record['schema'] != SCHEMA or type(record['version']) is not int or record['version'] != VERSION:
        raise MalformedEvidence('evidence: unsupported record schema/version')
    validate_context(record['context'])
    _hex(record['record_id'])
    _hex(record['closure_sha256'])
    if record['record_id'] != record_id(record['context']):
        raise EvidenceIntegrityError('evidence: record ID mismatch')
    _choice(record['status'], {'passed', 'failed', 'interrupted', 'not_run', 'diagnostic'})
    _choice(record['completeness'], {'complete', 'partial'})
    if type(record['members']) is not list:
        raise MalformedEvidence('evidence: invalid member list')
    for member in record['members']:
        _object(member, MEMBER_KEYS, 'member')
        _hex(member['member_id'])
        _integer(member['bytes'], maximum=MAX_BYTES)
        if type(member['required']) is not bool:
            raise MalformedEvidence('evidence: member required is not a boolean')
        validate_allocation(member['source_allocation'])
        path = _path(member['original_path'])
        allocation = _path(member['source_allocation']['path'])
        if not path.is_relative_to(allocation) or path == allocation:
            raise EvidenceIntegrityError('evidence: logical member is outside its allocation')
        if member['member_id'] != member_id(record['record_id'], member):
            raise EvidenceIntegrityError('evidence: member ID mismatch')
    _ordered(record['members'], lambda item: item['member_id'], 'members')
    _references(record['dependencies'])
    _cleanup(record['cleanup'], record['context']['owner'], record['members'])
    if record['closure_sha256'] != digest({key: item for key, item in record.items()
                                           if key != 'closure_sha256'}):
        raise EvidenceIntegrityError('evidence: closure digest mismatch')


def finalize_record(record):
    """Copy a producer draft, fill missing IDs/closure, reject supplied conflicts.

    Drafts omit record_id, member_id and closure_sha256. Set-valued member and
    dependency lists are sorted before hashing; caller input is never mutated.
    """
    encoded(record)
    result = copy.deepcopy(record)
    if type(result) is not dict or not (RECORD_KEYS - {'record_id', 'closure_sha256'}) <= set(result):
        raise MalformedEvidence('evidence: incomplete record draft')
    identity = record_id(result['context'])
    if 'record_id' in result and result['record_id'] != identity:
        raise EvidenceIntegrityError('evidence: draft record ID mismatch')
    result['record_id'] = identity
    if type(result['members']) is not list:
        raise MalformedEvidence('evidence: invalid member list')
    for item in result['members']:
        identity = member_id(result['record_id'], item)
        if 'member_id' in item and item['member_id'] != identity:
            raise EvidenceIntegrityError('evidence: draft member ID mismatch')
        item['member_id'] = identity
    result['members'].sort(key=lambda item: item['member_id'])
    if type(result['dependencies']) is not list:
        raise MalformedEvidence('evidence: invalid dependency list')
    for dependency in result['dependencies']:
        _object(dependency, {'record_id', 'closure_sha256'}, 'record reference')
        _hex(dependency['record_id'])
        _hex(dependency['closure_sha256'])
    result['dependencies'].sort(key=lambda item: item['record_id'])
    _references(result['dependencies'])
    closure = digest({key: item for key, item in result.items() if key != 'closure_sha256'})
    if 'closure_sha256' in result and result['closure_sha256'] != closure:
        raise EvidenceIntegrityError('evidence: draft closure mismatch')
    result['closure_sha256'] = closure
    _record(result)
    return result


def validate_records(records, member_map, files, *, repository=None):
    """Validate schema-2 logical inventory against already byte-verified files.

    All dependencies must be present; callers composing segments must supply
    their finite union. File bytes are verified by the archive reader, not by
    this metadata function. A missing dependency is integrity refusal, never an
    exact-reference absence notification.
    """
    encoded(dict(records=records, member_map=member_map, files=files))
    if repository is not None:
        validate_repository(repository)
    if type(records) is not list or type(member_map) is not list or type(files) is not list:
        raise MalformedEvidence('evidence: inventories must be lists')
    by_id = {}
    logical = {}
    for record in records:
        _record(record)
        key = record['record_id']
        if key in by_id:
            if by_id[key]['closure_sha256'] != record['closure_sha256']:
                raise EvidenceIntegrityError('evidence: conflicting record closures')
            raise MalformedEvidence('evidence: duplicate record ID')
        if repository is not None and record['context']['repository'] != repository:
            raise EvidenceContextError('evidence: record belongs to another checkout')
        by_id[key] = record
        for member in record['members']:
            logical[(key, member['member_id'])] = member
    _ordered(records, lambda item: item['record_id'], 'records')
    if len(logical) + len(records) + sum(len(item['dependencies']) for item in records) > MAX_ENTRIES:
        raise MalformedEvidence('evidence: logical metadata entry limit exceeded')
    physical = {}
    for index, item in enumerate(files):
        _object(item, {'path', 'bytes', 'allocated_bytes', 'sha256', 'identity',
                       'allocation', 'member'}, 'physical member')
        if item['member'] != f'files/{index:08d}':
            raise MalformedEvidence('evidence: invalid physical member name')
        _path(item['path'])
        validate_allocation(item['allocation'])
        path, allocation = _path(item['path']), _path(item['allocation']['path'])
        if path == allocation or not path.is_relative_to(allocation):
            raise EvidenceIntegrityError('evidence: physical member is outside its allocation')
        _integer(item['bytes'], maximum=MAX_BYTES)
        _hex(item['sha256'])
        _file_identity(item['identity'], item['allocation'], item['bytes'])
        _integer(item['allocated_bytes'])
        if item['allocated_bytes'] != item['identity'][9] * 512:
            raise EvidenceIntegrityError('evidence: allocated-byte mismatch')
        physical[item['member']] = item
    used, mapped, origins = set(), set(), {}
    for item in member_map:
        _object(item, {'record_id', 'member_id', 'physical_member', 'original_provenance'}, 'member mapping')
        _hex(item['record_id'])
        _hex(item['member_id'])
        _text(item['physical_member'])
        pair = item['record_id'], item['member_id']
        if pair not in logical or item['physical_member'] not in physical:
            raise EvidenceIntegrityError('evidence: orphan logical or physical mapping')
        if pair in mapped:
            raise MalformedEvidence('evidence: duplicate member mapping')
        mapped.add(pair)
        member, stored = logical[pair], physical[item['physical_member']]
        origin = item['original_provenance']
        _object(origin, {'original_path', 'source_allocation', 'identity'}, 'original provenance')
        _path(origin['original_path'])
        validate_allocation(origin['source_allocation'])
        _file_identity(origin['identity'], origin['source_allocation'], member['bytes'])
        if (origin['original_path'] != member['original_path']
                or origin['source_allocation'] != member['source_allocation']
                or stored['bytes'] != member['bytes'] or stored['sha256'] != member['sha256']):
            raise EvidenceIntegrityError('evidence: mapping bytes or original provenance disagree')
        origin_key = digest(dict(path=origin['original_path'], allocation=origin['source_allocation']))
        provenance = dict(identity=origin['identity'], sha256=member['sha256'])
        if origin_key in origins and origins[origin_key] != provenance:
            raise EvidenceIntegrityError('evidence: conflicting original provenance')
        origins[origin_key] = provenance
        if (stored['path'] == origin['original_path'] and stored['allocation'] == origin['source_allocation']
                and stored['identity'] != origin['identity']):
            raise EvidenceIntegrityError('evidence: conflicting physical provenance')
        used.add(item['physical_member'])
    _ordered(member_map, lambda item: (item['record_id'], item['member_id']), 'member mappings')
    if mapped != set(logical) or used != set(physical):
        raise EvidenceIntegrityError('evidence: incomplete logical or physical inventory')
    # Iterative DFS avoids Python recursion limits for a finite deep closure.
    done, active = set(), set()
    for root in by_id:
        stack = [(root, False)]
        while stack:
            key, leaving = stack.pop()
            if leaving:
                active.remove(key)
                done.add(key)
                continue
            if key in done:
                continue
            if key in active:
                raise EvidenceIntegrityError('evidence: dependency cycle')
            active.add(key)
            stack.append((key, True))
            for dependency in reversed(by_id[key]['dependencies']):
                target = dependency['record_id']
                if target not in by_id:
                    raise EvidenceIntegrityError('evidence: dependency record missing')
                if by_id[target]['closure_sha256'] != dependency['closure_sha256']:
                    raise EvidenceIntegrityError('evidence: dependency closure mismatch')
                stack.append((target, False))
    return by_id


def parse_reference(reference):
    """Parse an exact reserved selector while preserving its relative locator."""
    _text(reference)
    locator, separator, fragment = reference.partition('#')
    if not separator or '#' in fragment:
        raise MalformedEvidence('evidence: exact selector fragment required')
    _destination(locator)
    match = re.fullmatch(r'onpc-evidence-v1:([0-9a-f]{64}):([0-9a-f]{64}):([0-9a-f]{64})', fragment)
    if match is None:
        raise MalformedEvidence('evidence: malformed exact selector')
    return locator, dict(zip(('record_id', 'member_id', 'closure_sha256'), match.groups()))


def validate_consumer(consumer):
    encoded(consumer)
    _object(consumer, {'schema', 'version', 'consumer_id', 'owner', 'revision_sha256',
                       'role', 'expected_context', 'references', 'state'}, 'consumer')
    if (consumer['schema'] != 'onpc-evidence-consumer' or type(consumer['version']) is not int
            or consumer['version'] != 1):
        raise MalformedEvidence('evidence: unsupported consumer schema/version')
    _hex(consumer['consumer_id'])
    _hex(consumer['revision_sha256'])
    validate_owner(consumer['owner'])
    _choice(consumer['role'], {'required_evidence', 'required_instruction', 'optional_presentation',
                              'historical_information', 'example', 'operational_path'})
    _choice(consumer['state'], {'working', 'suspended', 'accepted', 'released'})
    refs = consumer['references']
    if type(refs) is not list or not refs:
        raise MalformedEvidence('evidence: consumer requires finite references')
    evidence = False
    for ref in refs:
        if type(ref) is not dict or 'kind' not in ref:
            raise MalformedEvidence('evidence: invalid consumer reference')
        if ref['kind'] == 'evidence':
            _object(ref, {'kind', 'record_id', 'member_id', 'closure_sha256'}, 'evidence reference')
            for key in ('record_id', 'member_id', 'closure_sha256'):
                _hex(ref[key])
            evidence = True
        elif ref['kind'] == 'document':
            _object(ref, {'kind', 'destination', 'fragment'}, 'document reference')
            _destination(ref['destination'])
            _text(ref['fragment'], empty=True)
        else:
            raise MalformedEvidence('evidence: invalid reference kind')
    _ordered(refs, lambda item: encoded(item), 'consumer references')
    if evidence or consumer['role'] == 'required_evidence':
        validate_context(consumer['expected_context'])
        if consumer['owner'] != consumer['expected_context']['owner']:
            raise EvidenceContextError('evidence: consumer context owner mismatch')
    elif consumer['expected_context'] is not None:
        raise MalformedEvidence('evidence: document consumer has no evidence context')
    if consumer['role'] == 'required_evidence' and not evidence:
        raise EvidenceContextError('evidence: required evidence has no evidence selector')
    return consumer


def match_context(record, consumer):
    _record(record)
    validate_consumer(consumer)
    if record['context'] != consumer['expected_context']:
        raise EvidenceContextError('evidence: exact expected context mismatch')
    if record['context']['owner'] != consumer['owner']:
        raise EvidenceContextError('evidence: consumer owner mismatch')
    if consumer['role'] == 'required_evidence':
        if (record['status'] != 'passed' or record['completeness'] != 'complete'
                or record['cleanup']['state'] != 'complete'):
            raise EvidenceContextError('evidence: required proof is not passed, complete and cleaned')
        if consumer['state'] == 'released':
            raise EvidenceContextError('evidence: consumer is not active')
    return record
