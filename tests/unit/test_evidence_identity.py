"""Pure frozen-wire identity checks; no files, processes or shared resources."""
import copy
import hashlib
import stat

import pytest

import evidence_identity as identity


def context():
    repository = dict(root='/checkout', device=1, inode=2, uid=1000)
    owner = dict(repository_sha256=identity.digest(repository),
                 caller=dict(uid=1000, gid=1000), journal='/checkout/journal',
                 identity=dict(device=1, inode=3, mode=stat.S_IFDIR | 0o700,
                               uid=1000, gid=1000))
    return dict(repository=repository, workflow='docs/Plan.md', owner=owner,
                run='1' * 32, task='E02', check='check_exact', attempt='2' * 32,
                target='', inputs_sha256='3' * 64, sources_sha256='4' * 64)


def draft(**changes):
    value = context()
    value.update(changes)
    allocation = dict(path='/checkout/allocation', device=1, inode=4, mode=0o700,
                      journal='/checkout/journal', run='1' * 32)
    member = dict(role='result', original_path='/checkout/allocation/result.json',
                  source_allocation=allocation, bytes=4,
                  sha256=hashlib.sha256(b'pass').hexdigest(), required=True)
    return dict(schema=identity.SCHEMA, version=1, context=value,
                status='passed', completeness='complete', members=[member],
                dependencies=[], cleanup=dict(state='complete', record_members=[],
                                             scope=dict(owner=value['owner'], resources=[])))


def record(**changes):
    return identity.finalize_record(draft(**changes))


def inventory(records):
    files, mappings, physical_by_origin = [], [], {}
    for value in sorted(records, key=lambda item: item['record_id']):
        for member in value['members']:
            fingerprint = [1, 5, stat.S_IFREG | 0o600, 1000, 1000,
                           1, member['bytes'], 100, 100, 8]
            origin_key = member['original_path'], member['sha256']
            if origin_key not in physical_by_origin:
                physical = f'files/{len(files):08d}'
                files.append(dict(path=member['original_path'], bytes=member['bytes'],
                                  allocated_bytes=4096, sha256=member['sha256'],
                                  identity=fingerprint, allocation=member['source_allocation'],
                                  member=physical))
                physical_by_origin[origin_key] = physical
            physical = physical_by_origin[origin_key]
            mappings.append(dict(record_id=value['record_id'], member_id=member['member_id'],
                                 physical_member=physical,
                                 original_provenance=dict(original_path=member['original_path'],
                                                          source_allocation=member['source_allocation'],
                                                          identity=fingerprint)))
    mappings.sort(key=lambda item: (item['record_id'], item['member_id']))
    return mappings, files


def validate(records):
    mappings, files = inventory(records)
    return identity.validate_records(sorted(records, key=lambda item: item['record_id']),
                                     mappings, files)


def consumer(value):
    member = value['members'][0]
    return dict(schema='onpc-evidence-consumer', version=1,
                consumer_id='5' * 64, owner=copy.deepcopy(value['context']['owner']),
                revision_sha256='6' * 64, role='required_evidence',
                expected_context=copy.deepcopy(value['context']),
                references=[dict(kind='evidence', record_id=value['record_id'],
                                 member_id=member['member_id'],
                                 closure_sha256=value['closure_sha256'])], state='accepted')


def test_canonical_identity_and_no_input_mutation():
    source = draft()
    before = copy.deepcopy(source)
    value = identity.finalize_record(source)
    assert source == before
    assert identity.encoded({'z': 'é', 'a': 1}) == b'{"a":1,"z":"\\u00e9"}'
    assert identity.digest({'a': 1}) == hashlib.sha256(b'{"a":1}').hexdigest()
    assert value['record_id'] == identity.digest(dict(schema=identity.SCHEMA, version=1,
                                                     context=value['context']))
    assert identity.finalize_record(value) == value
    assert validate([value]) == {value['record_id']: value}
    assert identity.match_context(value, consumer(value)) == value
    assert identity.match_context(value, dict(consumer(value), state='suspended')) == value


@pytest.mark.parametrize('field,value', [
    ('attempt', '7' * 32), ('run', '8' * 32), ('inputs_sha256', '8' * 64),
    ('sources_sha256', '9' * 64), ('target', 'guest'), ('task', 'E03'),
    ('check', 'check_other'), ('workflow', 'docs/Other.md'),
])
def test_claim_dimensions_never_alias(field, value):
    original = record()
    changed = record(**{field: value})
    assert changed['record_id'] != original['record_id']
    with pytest.raises(identity.EvidenceContextError, match='context mismatch'):
        identity.match_context(changed, consumer(original))


def test_owner_and_checkout_are_part_of_identity():
    original = record()
    changed = draft()
    changed['context']['owner']['identity']['inode'] += 1
    changed['cleanup']['scope']['owner'] = changed['context']['owner']
    assert identity.finalize_record(changed)['record_id'] != original['record_id']
    changed = draft()
    changed['context']['repository']['inode'] += 1
    changed['context']['owner']['repository_sha256'] = identity.digest(changed['context']['repository'])
    assert identity.finalize_record(changed)['record_id'] != original['record_id']
    mappings, files = inventory([original])
    with pytest.raises(identity.EvidenceContextError, match='another checkout'):
        identity.validate_records([original], mappings, files,
                                  repository=changed['context']['repository'])


@pytest.mark.parametrize('value', [float('nan'), float('inf'), 1.0, (1,), {1: 'bad'},
                                 'a\x00b', '\ud800', 'é' * 2049])
def test_invalid_canonical_inputs_are_typed(value):
    with pytest.raises(identity.MalformedEvidence):
        identity.encoded(value)


@pytest.mark.parametrize('text', ['{"a":1,"a":2}', '{"x":NaN}', '{"x":Infinity}',
                                '{"x":1.0}', '{broken'])
def test_json_rejects_duplicates_and_nonfinite_numbers(text):
    with pytest.raises(identity.MalformedEvidence):
        identity.decoded(text)


@pytest.mark.parametrize('mutate', [
    lambda value: value.update(version=True),
    lambda value: value.update(version=2),
    lambda value: value.update(extra='unknown'),
    lambda value: value['context'].update(extra='unknown'),
    lambda value: value['context'].update(attempt='A' * 32),
    lambda value: value['context']['repository'].update(device=True),
    lambda value: value['members'][0].update(bytes=True),
    lambda value: value['members'][0].update(required=1),
    lambda value: value['members'][0]['source_allocation'].update(mode=True),
    lambda value: value['members'][0].update(original_path='/checkout/allocation/../secret'),
    lambda value: value['members'][0].update(original_path='/checkout/allocation/.ssh/key'),
    lambda value: value['cleanup']['scope']['resources'].append(
        dict(kind='vm', id='guest', disposition='off')),
])
def test_strict_record_shapes(mutate):
    value = draft()
    mutate(value)
    with pytest.raises(identity.MalformedEvidence):
        identity.finalize_record(value)


def test_status_changes_conflict_instead_of_superseding_same_record():
    passed = record()
    source = draft()
    source['status'] = 'failed'
    failed = identity.finalize_record(source)
    assert failed['record_id'] == passed['record_id']
    assert failed['closure_sha256'] != passed['closure_sha256']
    with pytest.raises(identity.EvidenceIntegrityError, match='conflicting record closures'):
        identity.validate_records([passed, failed], [], [])
    with pytest.raises(identity.MalformedEvidence, match='duplicate record ID'):
        identity.validate_records([passed, passed], [], [])


@pytest.mark.parametrize('field', ['record_id', 'closure_sha256'])
def test_generated_ids_cannot_overwrite_conflicting_supplied_values(field):
    value = record()
    value[field] = 'f' * 64
    with pytest.raises(identity.EvidenceIntegrityError):
        identity.finalize_record(value)


def test_member_identity_binds_role_original_and_bytes_not_basename():
    source = draft()
    first = source['members'][0]
    second = copy.deepcopy(first)
    second['original_path'] = '/checkout/allocation/subdir/result.json'
    source['members'].append(second)
    value = identity.finalize_record(source)
    assert len({item['member_id'] for item in value['members']}) == 2
    validate([value])
    original = value['members'][0]
    for changes in ({'role': 'input'}, {'sha256': 'f' * 64}):
        changed = dict(original, **changes)
        assert identity.member_id(value['record_id'], changed) != original['member_id']


@pytest.mark.parametrize('change', ['missing_mapping', 'orphan_mapping', 'wrong_member',
                                  'wrong_bytes', 'wrong_digest', 'wrong_origin',
                                  'wrong_identity', 'orphan_file', 'duplicate_mapping'])
def test_exact_mapping_and_inventory_refusal(change):
    value = record()
    mappings, files = inventory([value])
    if change == 'missing_mapping':
        mappings.clear()
    elif change == 'orphan_mapping':
        mappings[0]['record_id'] = 'f' * 64
    elif change == 'wrong_member':
        mappings[0]['physical_member'] = 'files/00000001'
    elif change == 'wrong_bytes':
        files[0]['bytes'] += 1
    elif change == 'wrong_digest':
        files[0]['sha256'] = 'f' * 64
    elif change == 'wrong_origin':
        mappings[0]['original_provenance']['original_path'] += '.other'
    elif change == 'wrong_identity':
        mappings[0]['original_provenance']['identity'] = list(files[0]['identity'])
        mappings[0]['original_provenance']['identity'][1] += 1
    elif change == 'orphan_file':
        files.append(dict(files[0], member='files/00000001', path=files[0]['path'] + '.other'))
    elif change == 'duplicate_mapping':
        mappings.append(copy.deepcopy(mappings[0]))
    with pytest.raises((identity.EvidenceIntegrityError, identity.MalformedEvidence)) as error:
        identity.validate_records([value], mappings, files)
    assert not isinstance(error.value, FileNotFoundError)


def test_equal_bytes_may_share_physical_storage_without_merging_origins():
    source = draft()
    second = copy.deepcopy(source['members'][0])
    second['original_path'] += '.second'
    source['members'].append(second)
    value = identity.finalize_record(source)
    mappings, files = inventory([value])
    mappings[1]['physical_member'] = files[0]['member']
    identity.validate_records([value], mappings, files[:1])
    assert mappings[0]['original_provenance'] != mappings[1]['original_provenance']


def test_dependencies_require_exact_transitive_closure():
    child = record(task='child')
    source = draft(task='parent')
    source['dependencies'] = [dict(record_id=child['record_id'], closure_sha256=child['closure_sha256'])]
    parent = identity.finalize_record(source)
    assert len(validate([child, parent])) == 2
    with pytest.raises(identity.EvidenceIntegrityError, match='dependency record missing'):
        validate([parent])
    source['dependencies'][0]['closure_sha256'] = 'f' * 64
    wrong = identity.finalize_record(source)
    with pytest.raises(identity.EvidenceIntegrityError, match='dependency closure mismatch'):
        validate([wrong, child])


def test_cycle_detection_is_independent_of_hash_validation(monkeypatch):
    # A genuine cyclic closure cannot self-hash. Exercise the graph guard after
    # bypassing only per-record hash validation, with internally exact edges.
    left, right = record(task='left'), record(task='right')
    left['dependencies'] = [dict(record_id=right['record_id'], closure_sha256=right['closure_sha256'])]
    right['dependencies'] = [dict(record_id=left['record_id'], closure_sha256=left['closure_sha256'])]
    monkeypatch.setattr(identity, '_record', lambda value: None)
    with pytest.raises(identity.EvidenceIntegrityError, match='dependency cycle'):
        validate([left, right])


@pytest.mark.parametrize('field,value', [('status', 'failed'), ('status', 'diagnostic'),
                                       ('completeness', 'partial')])
def test_required_evidence_cannot_use_nonpassing_or_partial_records(field, value):
    source = draft()
    source[field] = value
    value = identity.finalize_record(source)
    with pytest.raises(identity.EvidenceContextError, match='required proof'):
        identity.match_context(value, consumer(value))


@pytest.mark.parametrize('state', ['failed', 'pending', 'not_applicable'])
def test_cleanup_declaration_is_not_a_json_authorization_bypass(state):
    source = draft()
    source['cleanup']['state'] = state
    value = identity.finalize_record(source)
    with pytest.raises(identity.EvidenceContextError, match='required proof'):
        identity.match_context(value, consumer(value))


def test_cleanup_members_are_exact_and_have_cleanup_role():
    value = record()
    value['cleanup']['record_members'] = [value['members'][0]['member_id']]
    del value['closure_sha256']
    with pytest.raises(identity.EvidenceIntegrityError, match='cleanup member'):
        identity.finalize_record(value)


def test_reference_parser_preserves_specific_selector_and_relative_locator():
    selector = dict(record_id='1' * 64, member_id='2' * 64, closure_sha256='3' * 64)
    reference = '../proof/accepted.json#onpc-evidence-v1:' + ':'.join(selector.values())
    assert identity.parse_reference(reference) == ('../proof/accepted.json', selector)


@pytest.mark.parametrize('reference', ['accepted.json', 'accepted.json#heading',
    '/accepted.json#onpc-evidence-v1:' + ':'.join(['1' * 64] * 3),
    'accepted.json#onpc-evidence-v1:' + ':'.join(['A' * 64] * 3),
    'accepted.json#onpc-evidence-v1:' + ':'.join(['1' * 64] * 2),
    'https://example.org/accepted.json#onpc-evidence-v1:' + ':'.join(['1' * 64] * 3),
])
def test_generic_or_malformed_reference_never_supplies_exact_proof(reference):
    with pytest.raises(identity.MalformedEvidence):
        identity.parse_reference(reference)


def test_consumer_context_must_be_exact_and_document_context_is_not_invented():
    value = record()
    claim = consumer(value)
    del claim['expected_context']['attempt']
    with pytest.raises(identity.MalformedEvidence):
        identity.validate_consumer(claim)
    document = consumer(value)
    document.update(role='required_instruction', expected_context=None,
                    references=[dict(kind='document', destination='../Instructions.md', fragment='setup')])
    assert identity.validate_consumer(document) == document
    document['expected_context'] = value['context']
    with pytest.raises(identity.MalformedEvidence):
        identity.validate_consumer(document)
