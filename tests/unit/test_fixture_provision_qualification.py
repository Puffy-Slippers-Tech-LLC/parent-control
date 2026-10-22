"""Independent qualification assertions with private records and local doubles.

No guest, subprocess, fixture producer, shared journal, service or cache is used.
Only bounded in-memory data and pytest-private result files are owned here.
"""
from copy import deepcopy
from contextlib import contextmanager, nullcontext
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, call

import pytest

import fixture_provision_qualification as qualification
from tools import fixture_execution, fixture_manifest


@pytest.fixture
def selection(request):
    target = getattr(request, 'param', 'ubuntu')
    return fixture_execution.Selection(target, 'a' * 64,
        '/tmp/onpc-native-runtime-' + target + '-' + 'a' * 64 + '-private',
        1, 2, '/tmp/retention-private', 3, 4, 'b' * 32, 'c' * 64)


@pytest.fixture(autouse=True)
def configured_target(monkeypatch):
    monkeypatch.setattr(qualification.prepare_vm.vm_config, 'selected',
                        lambda: SimpleNamespace(name='onpc-Ubuntu26.04'))


@pytest.fixture
def audit_case():
    members, payloads = {}, {}
    for key, declaration in fixture_manifest.declarations().items():
        source = declaration['source']
        payloads[key] = b'private inert payload ' + (source if isinstance(source, bytes) else source.encode())
        members[key] = {name: value for name, value in declaration.items() if name != 'source'}
        members[key].update(length=len(payloads[key]),
                            sha256=hashlib.sha256(payloads[key]).hexdigest())
    manifest = {'members': members, 'absences': deepcopy(fixture_manifest.ABSENCES),
                'inputs': {'target': {'os': 'ubuntu', 'release': '26.04', 'architecture': 'x86_64'}}}
    accounts = {role: {'uid': 1100 + index, 'gid': 2100 + index, 'home': '/home/' + role}
                for index, role in enumerate(('parent', 'child', 'other'))}
    accounts['system'] = {'uid': 0, 'gid': 0, 'home': '/root'}
    subsets = ['trusted-hard', 'riley-grid']
    keys = {key for key, member in members.items() if set(member['subsets']) & set(subsets)}
    files, rows = {}, {}
    for key in keys:
        member = members[key]
        owner = accounts[member['owner']]
        path = member['destination']
        for role, account in accounts.items():
            path = path.replace('@' + role + '@', account['home'])
        files[key] = {name: member[name] for name in ('sha256', 'length', 'mode')}
        files[key].update(uid=owner['uid'], gid=owner['gid'], nlink=1, regular=True,
                          device=5, inode=6, mtime_ns=7, ctime_ns=8)
        rows[key] = ([['filedb', path, str(member['length']), member['sha256']]]
                     if member['native_action'] == 'trust' else [])
    binding = {'boot_sha256': 'd' * 64, 'vm_uuid': 'private-vm', 'run': 'e' * 32}
    observed = dict(accounts=accounts, files=files, native_rows=rows, **binding,
        unselected_present=[], staging=[], installed=False,
        native_gid=975, native_active=True,
        platform=deepcopy(manifest['inputs']['target']), selinux_enforcing=None, labels={},
        admissions={}, rule_sources={}, compiled=None, compiled_previous=None,
        public_rules=None, rules_check=None,
        trust_entries={row[0][1]: {'length': int(row[0][2]), 'sha256': row[0][3]}
                       for row in rows.values() if row},
        preserved={'/etc/fapolicyd/private.rules': {'sha256': 'f' * 64},
                   '@attempt-trust': {'uid': 0, 'gid': 975, 'mode': 0o600,
                                      'regular': True, 'nlink': 1}},
        vendor_database_sha256='0' * 64)
    return SimpleNamespace(manifest=manifest, payloads=payloads, subsets=subsets,
                           keys=keys, observed=observed, binding=binding)


def test_readback_accepts_exact_independent_members_and_account_destinations(audit_case):
    case = audit_case
    before = deepcopy(case.manifest)
    expected = qualification.validate_readback(case.observed, case.manifest,
        case.subsets, case.binding, installed=False)
    assert set(expected) == case.keys
    for key, member in expected.items():
        owner = case.observed['accounts'][member['owner']]
        assert (member['uid'], member['gid']) == (owner['uid'], owner['gid'])
        assert '@' not in member['destination']
    assert case.manifest == before


@pytest.mark.parametrize(('field', 'value'), [
    ('sha256', '0' * 64), ('length', -1), ('mode', 0o777),
    ('uid', 9999), ('gid', 9999), ('nlink', 2), ('regular', False),
])
def test_readback_rejects_payload_or_ownership_drift(audit_case, field, value):
    case = audit_case
    case.observed['files'][next(iter(case.keys))][field] = value
    with pytest.raises(qualification.system.Error, match='independent-readback'):
        qualification.validate_readback(case.observed, case.manifest,
            case.subsets, case.binding, installed=False)


@pytest.mark.parametrize('change', ['duplicate', 'wrong-source', 'missing', 'unselected'])
def test_readback_requires_exact_native_database_rows(audit_case, change):
    case = audit_case
    rows = case.observed['native_rows']
    key = next(key for key, value in rows.items() if value)
    if change == 'duplicate':
        rows[key] *= 2
    elif change == 'wrong-source':
        rows[key][0][0] = 'rpmdb'
    elif change == 'missing':
        rows[key] = []
    else:
        rows['unselected'] = []
    with pytest.raises(qualification.system.Error, match='exact-native-trust|native-inventory'):
        qualification.validate_readback(case.observed, case.manifest,
            case.subsets, case.binding, installed=False)


@pytest.mark.parametrize('field', ['boot_sha256', 'vm_uuid', 'run'])
def test_readback_binds_actual_attempt_identity(audit_case, field):
    case = audit_case
    case.observed[field] = 'foreign'
    with pytest.raises(qualification.system.Error, match='actual-attempt'):
        qualification.validate_readback(case.observed, case.manifest,
            case.subsets, case.binding, installed=False)


@pytest.mark.parametrize('change', ['inactive', 'extra-entry', 'missing-entry',
    'trust-owner', 'trust-group', 'trust-mode', 'trust-hardlink'])
def test_readback_requires_active_exact_trust_and_safe_metadata(audit_case, change):
    case = audit_case
    if change == 'inactive':
        case.observed['native_active'] = False
    elif change == 'extra-entry':
        case.observed['trust_entries']['/foreign'] = {'length': 1, 'sha256': 'a' * 64}
    elif change == 'missing-entry':
        case.observed['trust_entries'].pop(next(iter(case.observed['trust_entries'])))
    else:
        field, value = {'trust-owner': ('uid', 1000), 'trust-group': ('gid', 9999),
                        'trust-mode': ('mode', 0o644), 'trust-hardlink': ('nlink', 2)}[change]
        case.observed['preserved']['@attempt-trust'][field] = value
    with pytest.raises(qualification.system.Error, match='native-activation|trust-metadata'):
        qualification.validate_readback(case.observed, case.manifest,
            case.subsets, case.binding, installed=False)


@pytest.mark.parametrize('change', ['missing', 'extra', 'unselected', 'staging', 'installed'])
def test_readback_refuses_nonminimal_runtime(audit_case, change):
    case = audit_case
    if change == 'missing':
        case.observed['files'].pop(next(iter(case.keys)))
    elif change == 'extra':
        case.observed['files']['unselected'] = {}
    elif change == 'unselected':
        case.observed['unselected_present'] = ['unselected']
    elif change == 'staging':
        case.observed['staging'] = ['onpc-fixture-private']
    else:
        case.observed['installed'] = True
    with pytest.raises(qualification.system.Error, match='minimal-runtime'):
        qualification.validate_readback(case.observed, case.manifest,
            case.subsets, case.binding, installed=False)


@pytest.mark.parametrize('field', ['inode', 'mtime_ns', 'sha256', 'mode'])
def test_repeat_detects_identity_time_content_or_mode_changes(audit_case, field):
    before = audit_case.observed
    qualification.verify_repeat(before, deepcopy(before))
    after = deepcopy(before)
    after['files'][next(iter(audit_case.keys))][field] = 'changed'
    with pytest.raises(qualification.system.Error, match='repeat-wrote-state'):
        qualification.verify_repeat(before, after)


@pytest.mark.parametrize('change', ['policy', 'vendor-database'])
def test_unrelated_policy_must_survive_provisioning(audit_case, change):
    before = audit_case.observed
    after = deepcopy(before)
    after['preserved']['@attempt-trust'] = {'sha256': 'owned-change'}
    qualification.unchanged_policy(before, after)
    if change == 'policy':
        after['preserved']['/etc/fapolicyd/private.rules']['sha256'] = 'changed'
    else:
        after['vendor_database_sha256'] = 'changed'
    with pytest.raises(qualification.system.Error, match='unrelated-native-or-product-state-changed'):
        qualification.unchanged_policy(before, after)


def test_recording_boundary_delegates_exact_objects_and_records_only_sent_payloads(monkeypatch, audit_case):
    transport, request, reply = object(), {'attempt': 'private'}, object()
    delegate = Mock()
    delegate.call.return_value = reply
    constructor = Mock(return_value=delegate)
    monkeypatch.setattr(qualification.fixture_provision, 'SSHBoundary', constructor)
    boundary = qualification.RecordingBoundary(transport)
    payloads = {key: audit_case.payloads[key] for key in audit_case.keys}
    assert boundary.call('inspect', request) is reply
    assert boundary.call('stage', request, payloads) is reply
    constructor.assert_called_once_with(transport)
    assert delegate.call.call_args_list == [call('inspect', request, None), call('stage', request, payloads)]
    assert delegate.call.call_args.args[1] is request
    assert delegate.call.call_args.args[2] is payloads
    assert boundary.actions == ['inspect', 'stage']
    assert boundary.transfers == [{key: {'length': len(value),
        'sha256': hashlib.sha256(value).hexdigest()} for key, value in payloads.items()}]
    assert set(boundary.transfers[0]) == audit_case.keys


@pytest.mark.parametrize('failure', ['missing', 'authentication', 'corrupt', 'incompatible', 'target'])
def test_invalid_selection_refuses_before_suite_or_acquire(monkeypatch, tmp_path, selection, failure):
    suite = Mock(side_effect=AssertionError('must not construct a VM suite'))
    monkeypatch.setattr(qualification, 'Suite', suite)
    pin = Mock(return_value=nullcontext())
    monkeypatch.setattr(qualification, 'authenticated_input', pin)
    verify = Mock(return_value={})
    authenticate = Mock(return_value={})
    monkeypatch.setattr(fixture_execution, 'verify', verify)
    monkeypatch.setattr(qualification.fixture_provision, 'authenticated_bundle', authenticate)
    record = selection.record()
    if failure == 'missing':
        record = None
    elif failure == 'authentication':
        pin.side_effect = ValueError('untrusted input')
    elif failure == 'target':
        record['target'] = 'fedora'
        record['allocation'] = record['allocation'].replace('ubuntu', 'fedora')
    elif failure == 'corrupt':
        verify.side_effect = ValueError('corrupt input')
    else:
        authenticate.side_effect = ValueError('incompatible input')
    with pytest.raises((ValueError, qualification.system.Error)):
        qualification.qualify(tmp_path, tmp_path / 'unused-assets', record)
    suite.assert_not_called()
    if failure in ('missing', 'authentication', 'target'):
        verify.assert_not_called()
    if failure != 'incompatible':
        authenticate.assert_not_called()


@pytest.mark.parametrize('selection', ['ubuntu', 'fedora'], indirect=True)
@pytest.mark.parametrize('failure', [None, 'foreign', 'interrupted', 'fresh-minimal', 'installed-union'])
def test_qualification_closes_suite_and_exits_lease_after_attempts(monkeypatch, tmp_path, selection, failure):
    events = []
    pinned = False

    @contextmanager
    def pin(record):
        nonlocal pinned
        assert record == selection.record()
        pinned = True
        events.append('pin-enter')
        try:
            yield
        finally:
            events.append('pin-exit')
            pinned = False

    monkeypatch.setattr(qualification, 'authenticated_input', pin)

    def cleanup(name):
        assert pinned, 'input pin released before VM recovery and suite cleanup'
        events.append(name)

    lease = MagicMock()
    guest = ({'ubuntu_version': '26.04'} if selection.target == 'ubuntu' else {'os_id': 'fedora', 'version': '44'})
    lease.capture.state = None

    def enter():
        cleanup('enter')
        lease.capture.state = {'guest': {**guest, 'fixture_boundary': 'clean'}}

    lease.__enter__.side_effect = enter
    lease.__exit__.side_effect = lambda *args: cleanup('exit') or False
    name = next(name for name, os_id in qualification.TARGETS.items() if os_id == selection.target)
    monkeypatch.setattr(qualification.prepare_vm.vm_config, 'selected', lambda: SimpleNamespace(name=name))
    source = SimpleNamespace(domain=SimpleNamespace(name=lambda: name))
    suite = Mock()
    suite.acquire.return_value = (source, None, lease)
    suite.close.side_effect = lambda: cleanup('close')
    monkeypatch.setattr(qualification, 'Suite', Mock(return_value=suite))
    monkeypatch.setattr(fixture_execution, 'verify', Mock(return_value={'private': 'manifest'}))
    monkeypatch.setattr(qualification.fixture_provision, 'authenticated_bundle', Mock())
    monkeypatch.setattr(qualification.fixture_provision, 'reset_after_restore', Mock())
    monkeypatch.setattr(qualification.system, 'artifact_source', Mock(return_value='private-assets'))
    monkeypatch.setattr(qualification.system, 'stage_assets', Mock())
    monkeypatch.setattr(qualification, 'preflight_source', Mock())

    def attempt(actual_suite, directory, frozen, manifest, *args, **kwargs):
        assert actual_suite is suite and frozen == selection and pinned
        events.append(directory.name)
        if directory.name == failure:
            raise ValueError('private attempt failure')
        return {'actual_boot_sha256': directory.name,
                'binding': {'boot_sha256': directory.name, 'attempt_id': directory.name}}

    monkeypatch.setattr(qualification, 'foreign_attempt', attempt)
    monkeypatch.setattr(qualification, 'interrupted_attempt', attempt)
    monkeypatch.setattr(qualification, 'successful_attempt', attempt)
    if failure:
        with pytest.raises(ValueError, match='private attempt failure'):
            qualification.qualify(tmp_path, tmp_path / 'unused-assets', selection.record())
        assert (tmp_path / 'private/controller-error.txt').is_file()
    else:
        result = qualification.qualify(tmp_path, tmp_path / 'unused-assets', selection.record())
        assert result['owned_baseline_restoration_verified'] is True
        assert set(result['attempts']) == {'foreign', 'interrupted', 'fresh-minimal', 'installed-union'}
        assert result['attempts']['interrupted']['owned_restoration_verified_before_fresh_attempt'] is True
        assert lease.prepare.call_count == 4 and lease.stop.call_count == 3
    assert events[:2] == ['pin-enter', 'enter']
    assert events[-3:] == ['exit', 'close', 'pin-exit']
    assert not pinned
    suite.acquire.assert_called_once()
    suite.close.assert_called_once()
    lease.__exit__.assert_called_once()


def test_missing_installed_helper_closure_refuses_before_vm_acquisition(monkeypatch, tmp_path, selection):
    suite = Mock()
    suite.input_bundle.side_effect = ValueError('missing installed helper')
    monkeypatch.setattr(qualification, 'Suite', Mock(return_value=suite))
    monkeypatch.setattr(qualification, 'authenticated_input', lambda _: nullcontext())
    monkeypatch.setattr(fixture_execution, 'verify', Mock(return_value={}))
    monkeypatch.setattr(qualification.fixture_provision, 'authenticated_bundle', Mock())
    monkeypatch.setattr(qualification.system, 'artifact_source', Mock())
    monkeypatch.setattr(qualification.system, 'stage_assets', Mock())
    monkeypatch.setattr(qualification, 'preflight_source', Mock())
    with pytest.raises(ValueError, match='missing installed helper'):
        qualification.qualify(tmp_path, tmp_path / 'assets', selection.record())
    suite.acquire.assert_not_called()
    suite.close.assert_called_once()


@pytest.mark.parametrize('diagnostic_failure', [False, True])
def test_failed_provision_retains_independent_audit_without_retry(monkeypatch, tmp_path, diagnostic_failure):
    transport = object()
    monkeypatch.setattr(qualification, 'baseline_transport', Mock(return_value=transport))
    before = {'files': {}, 'unselected_present': [], 'staging': [],
              'preserved': {'@attempt-trust': None}}
    observation = {'private': 'independent observation'}
    audit = Mock(side_effect=[before, ValueError('diagnostic failed') if diagnostic_failure else observation])
    monkeypatch.setattr(qualification, 'audit', audit)
    failure = ValueError('original provisioning failure')
    controller = Mock()
    controller.provision.side_effect = failure
    monkeypatch.setattr(qualification.fixture_provision, 'Provisioner', Mock(return_value=controller))
    monkeypatch.setattr(qualification, 'RecordingBoundary', Mock())
    with pytest.raises(ValueError) as caught:
        qualification.successful_attempt(Mock(), tmp_path, object(), {}, ['trusted-hard'], installed=False)
    assert caught.value is failure
    controller.provision.assert_called_once()
    assert audit.call_args_list == [call(transport, {}, ['trusted-hard'])] * 2
    if diagnostic_failure:
        assert 'diagnostic failed' in (tmp_path / 'failure-audit-error.txt').read_text()
    else:
        assert json.loads((tmp_path / 'failure-audit.json').read_bytes()) == observation


def test_main_retains_input_preflight_error_before_suite_exists(monkeypatch, tmp_path):
    monkeypatch.setattr(qualification.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(qualification.os, 'umask', Mock())
    monkeypatch.setattr(qualification.prepare_vm.vm_config, 'selected',
                        lambda: SimpleNamespace(name='onpc-Ubuntu26.04'))
    monkeypatch.setattr(qualification, 'session', nullcontext)
    monkeypatch.setattr(qualification, 'allocate', lambda *args, **kwargs: str(tmp_path))
    monkeypatch.setattr(qualification, 'qualify', Mock(side_effect=ValueError('input preflight detail')))
    assert qualification.main(assets='unused', selection={}) == 1
    assert 'input preflight detail' in (tmp_path / 'controller-error.txt').read_text()
    assert not (tmp_path / 'result.json').exists()


def fedora_case(case):
    """Private independently declared native source and package-policy records."""
    case.manifest['inputs']['target'] = {'os': 'fedora', 'release': '44', 'architecture': 'x86_64'}
    observed = case.observed
    observed['platform'] = deepcopy(case.manifest['inputs']['target'])
    observed['selinux_enforcing'] = True
    members = qualification.selected_members(case.manifest, case.subsets, observed['accounts'])
    by_path = {member['destination']: member for member in members.values()}
    hashes = {source: by_path[path]['sha256'] for source, (path, _) in
              qualification.native_assets.source_destinations('@other@').items()
              if source in qualification.native_assets.runtime_sources()}
    texts = qualification.native_assets.native_policy_files(hashes,
        tuple(observed['accounts'][role]['uid'] for role in ('child', 'other')))
    def metadata(text):
        return {'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest(),
                'length': len(text.encode()), 'uid': 0, 'gid': observed['native_gid'],
                'mode': 0o644, 'regular': True, 'nlink': 1}
    observed['admissions'] = {path: metadata(text.decode()) for path, text in texts.items()}
    sources = {'/etc/fapolicyd/rules.d/90-deny-execute.rules': 'deny_audit perm=execute all : all\n'}
    sources.update({path: text.decode() for path, text in texts.items()})
    observed['rule_sources'] = sources
    compiled = '## This file is automatically generated from /etc/fapolicyd/rules.d\n' + ''.join(
        line + '\n' for path in sorted(sources) for line in sources[path].splitlines()
        if line and not line.startswith('#'))
    observed['compiled'] = metadata(compiled)
    observed['compiled_previous'] = metadata('private previous compilation\n')
    observed['public_rules'] = '\n'.join(f'{index}. {line}' for index, line in enumerate(
        qualification.policy_rules(compiled.encode()), 1)) + '\n'
    observed['rules_check'] = '/usr/sbin/fagenrules: No change\n'
    paths = {m['destination'] for m in members.values()} | set(texts) | {qualification.TRUST}
    observed['labels'] = {path: {'actual': 'system_u:object_r:usr_t:s0',
                               'expected': 'system_u:object_r:usr_t:s0'} for path in paths}
    return case


def test_fedora_readback_independently_accepts_exact_untrusted_admissions(audit_case):
    case = fedora_case(audit_case)
    qualification.validate_readback(case.observed, case.manifest, case.subsets, case.binding, installed=False)
    untrusted = [key for key in case.keys if case.manifest['members'][key]['native_action'] == 'native-execute']
    assert len(untrusted) == 4 and all(case.observed['native_rows'][key] == [] for key in untrusted)


@pytest.mark.parametrize('change', ['missing', 'extra', 'broad', 'subject', 'trust', 'owner', 'mode', 'hash'])
def test_fedora_readback_refuses_nonexact_admissions(audit_case, change):
    case = fedora_case(audit_case)
    rows = case.observed['admissions']
    row = rows[next(iter(rows))]
    if change == 'missing':
        rows.pop(next(iter(rows)))
    elif change == 'extra':
        rows['/etc/fapolicyd/rules.d/68-extra-fixture.rules'] = deepcopy(row)
    elif change == 'broad':
        row['text'] = 'allow perm=any all : dir=/opt/\n'
    elif change == 'subject':
        row['text'] = row['text'].replace('uid=1101,1102', 'all')
    elif change == 'trust':
        row['text'] = row['text'].replace('trust=0', 'trust=1')
    else:
        row[{'owner': 'uid', 'mode': 'mode', 'hash': 'sha256'}[change]] = {'owner': 1000, 'mode': 0o666, 'hash': '0' * 64}[change]
    with pytest.raises(qualification.system.Error, match='admission-inventory|exact-native-admission'):
        qualification.validate_readback(case.observed, case.manifest, case.subsets, case.binding, installed=False)


@pytest.mark.parametrize('change', ['permissive', 'disabled', 'wrong-label', 'missing-label', 'extra-label'])
def test_fedora_readback_requires_enforcement_and_exact_label_inventory(audit_case, change):
    case = fedora_case(audit_case)
    observed = case.observed
    if change in ('permissive', 'disabled'):
        observed['selinux_enforcing'] = False if change == 'permissive' else None
    elif change == 'wrong-label':
        observed['labels'][next(iter(observed['labels']))]['actual'] = 'system_u:object_r:unlabeled_t:s0'
    elif change == 'missing-label':
        observed['labels'].pop(next(iter(observed['labels'])))
    else:
        observed['labels']['/foreign'] = {'actual': 'x:y:z:s0', 'expected': 'x:y:z:s0'}
    with pytest.raises(qualification.system.Error, match='selinux-not-enforcing|selinux-labels'):
        qualification.validate_readback(observed, case.manifest, case.subsets, case.binding, installed=False)


@pytest.mark.parametrize('change', ['compiled', 'source', 'public', 'not-loaded', 'compiled-owner'])
def test_fedora_readback_requires_exact_compilation_and_public_activation(audit_case, change):
    case = fedora_case(audit_case)
    observed = case.observed
    if change == 'compiled':
        observed['compiled']['text'] += 'allow perm=any all : all\n'
    elif change == 'source':
        observed['rule_sources'].pop(next(iter(observed['admissions'])))
    elif change == 'public':
        observed['public_rules'] += '999. allow perm=any all : all\n'
    elif change == 'not-loaded':
        observed['rules_check'] = '/usr/sbin/fagenrules: Rules have changed and should be updated\n'
    else:
        observed['compiled']['uid'] = 1000
    with pytest.raises(qualification.system.Error, match='admission-source|compiled-native-policy'):
        qualification.validate_readback(observed, case.manifest, case.subsets, case.binding, installed=False)


@pytest.mark.parametrize('change', ['os', 'release', 'architecture'])
def test_readback_refuses_wrong_observed_platform(audit_case, change):
    audit_case.observed['platform'][change] = 'foreign'
    with pytest.raises(qualification.system.Error, match='platform-identity'):
        qualification.validate_readback(audit_case.observed, audit_case.manifest,
            audit_case.subsets, audit_case.binding, installed=False)


def test_lost_reply_occurs_after_real_delegate_action_and_captures_no_payload_bytes(monkeypatch):
    delegate = Mock()
    request = {'stage_identity': [1, 2], 'binding': {'attempt_id': 'interrupted'}}
    reply = {'ok': True, 'identities': {'private': [3, 4]}}
    delegate.call.return_value = reply
    monkeypatch.setattr(qualification.fixture_provision, 'SSHBoundary', Mock(return_value=delegate))
    boundary = qualification.InterruptedBoundary(object())
    payloads = {'private': b'inert selected bytes'}
    with pytest.raises(qualification.LostReply, match='deliberate-lost-stage-reply'):
        boundary.call('stage', request, payloads)
    delegate.call.assert_called_once_with('stage', request, payloads)
    assert boundary.interrupted_request == request and boundary.interrupted_request is not request
    assert boundary.stage_reply == reply and boundary.stage_reply is not reply
    assert boundary.transfers == [{'private': {'length': len(payloads['private']),
        'sha256': hashlib.sha256(payloads['private']).hexdigest()}}]


@pytest.mark.parametrize('change', ['neighbor', 'product', 'vendor', 'previous'])
def test_fedora_preservation_excludes_only_proved_exact_outputs(audit_case, change):
    case = fedora_case(audit_case)
    after = deepcopy(case.observed)
    before = deepcopy(after)
    before['admissions'] = {}
    before['compiled'] = deepcopy(after['compiled_previous'])
    for path in after['admissions']:
        after['preserved'][path] = deepcopy(after['admissions'][path])
    after['preserved'][qualification.COMPILED] = deepcopy(after['compiled'])
    after['preserved'][qualification.COMPILED + '.prev'] = deepcopy(after['compiled_previous'])
    before['preserved'][qualification.COMPILED] = deepcopy(before['compiled'])
    qualification.unchanged_policy(before, after)
    if change == 'previous':
        after['compiled_previous']['sha256'] = 'foreign'
    elif change == 'vendor':
        after['vendor_database_sha256'] = 'foreign'
    else:
        path = ('/etc/fapolicyd/rules.d/68-onpc-baseline-runtime.rules' if change == 'neighbor'
                else '/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules')
        after['preserved'][path] = {'sha256': 'foreign'}
    with pytest.raises(qualification.system.Error, match='unrelated-native-or-product-state-changed|compiled-previous-preservation'):
        qualification.unchanged_policy(before, after)


@pytest.mark.parametrize(('guest', 'suffix'), [({'ubuntu_version': '26.04'}, 'deb'),
    ({'os_id': 'fedora', 'version': '44'}, 'rpm')])
def test_installed_transport_uses_verified_platform_package(monkeypatch, tmp_path, guest, suffix):
    assets = tmp_path / 'assets'
    assets.mkdir()
    package = assets / ('package.' + suffix)
    package.write_bytes(b'private package double')
    attempt = tmp_path / 'attempt'
    attempt.mkdir()
    lease = Mock()
    lease.capture.state = {'guest': guest}
    lease.state = {'run': 'a' * 32}
    lease.view.domain_id = 7
    domain = Mock()
    domain.snapshotListNames.return_value = ['onpc-v1']
    domain.snapshotLookupByName.return_value.getXMLDesc.return_value = 'private xml'
    suite = SimpleNamespace(lease=lease, source=SimpleNamespace(domain=domain, uuid='private-vm'),
                            commands=object(), input_bundle=Mock(return_value=object()))
    version = Mock(return_value='1')
    monkeypatch.setattr(qualification.system, 'package_version', version)
    monkeypatch.setattr(qualification.app_snapshot, 'snapshot_name', lambda _: 'onpc-v1')
    monkeypatch.setattr(qualification.app_snapshot, 'input_identity', Mock())
    monkeypatch.setattr(qualification.app_snapshot, 'matches', Mock(return_value=True))
    monkeypatch.setattr(qualification.app_snapshot, 'mode_mismatch', Mock(return_value=None))
    monkeypatch.setattr(qualification.online_snapshot, 'load', Mock(return_value={}))
    monkeypatch.setattr(qualification.online_snapshot, 'stage', Mock(return_value='private host key'))
    monkeypatch.setattr(qualification.system, 'address', Mock(return_value='private-address'))
    transport = Mock()
    monkeypatch.setattr(qualification, 'Transport', Mock(return_value=transport))
    assert qualification.installed_transport(suite, attempt, assets) is transport
    version.assert_called_once_with(suite.commands, package)
    assert (attempt / 'input' / package.name).read_bytes() == package.read_bytes()
    assert not (attempt / 'input' / ('package.deb' if suffix == 'rpm' else 'package.rpm')).exists()
    transport.probe_ready.assert_called_once_with()


def test_interrupted_attempt_poisoned_real_provisioner_leaves_stage_for_owner(monkeypatch, tmp_path, audit_case, selection):
    case = audit_case
    lease = SimpleNamespace(fd=1, state={'phase': 'running', 'domain_uuid': case.binding['vm_uuid'],
        'domain_id': 7, 'run': case.binding['run']}, guard=Mock())
    before = deepcopy(case.observed)
    before.update(files={}, staging=[], trust_entries={}, labels={})
    before['native_rows'] = {key: [] for key in fixture_manifest.select(['trusted-hard'])}
    before['preserved']['@attempt-trust'] = None
    requests = []

    def delegate_call(action, request, payloads):
        requests.append((action, deepcopy(request)))
        if action == 'inspect':
            return {'accounts': before['accounts'], 'target': case.manifest['inputs']['target']}
        if action == 'reserve':
            return {'ok': True, 'identity': [3, 4]}
        if action == 'stage':
            return {'ok': True, 'identities': {key: [5, 6] for key in payloads}}
        assert action == 'preflight', 'uncertain attempt reached placement, activation or cleanup'
        return {'ok': True}

    delegate = Mock()
    delegate.call.side_effect = delegate_call
    monkeypatch.setattr(qualification.fixture_provision, 'SSHBoundary', Mock(return_value=delegate))
    transport = Mock(config={key: lease.state[key] for key in ('domain_uuid', 'domain_id', 'run')})

    def transport_call(argv, **kwargs):
        if argv[-1] == qualification.STAGING_AUDIT:
            data = json.loads(kwargs['input'])
            assert data['stage_identity'] == [3, 4] and set(data['stage_files']) == set(data['members'])
            return json.dumps({'staging': data['staging'], 'selected': sorted(data['members']), 'retained': True}).encode()
        assert argv[-1] == qualification.fixture_provision.BOOT_SHA256_PROBE
        return (case.binding['boot_sha256'] + '\n').encode()

    transport.call.side_effect = transport_call
    monkeypatch.setattr(qualification, 'baseline_transport', Mock(return_value=transport))
    constructor = qualification.fixture_provision.Provisioner
    loaded = {'manifest': case.manifest, 'payloads': case.payloads, 'content_identity': 'c' * 64}
    monkeypatch.setattr(qualification.fixture_provision, 'Provisioner',
        lambda *args, **kwargs: constructor(*args, input_reader=lambda _: loaded, **kwargs))

    def audit(*args):
        observed = deepcopy(before)
        if requests and requests[-1][0] == 'stage':
            observed['staging'] = [qualification.Path(requests[-1][1]['staging']).name]
        return observed

    monkeypatch.setattr(qualification, 'audit', audit)
    result = qualification.interrupted_attempt(SimpleNamespace(lease=lease), tmp_path, selection, case.manifest)
    assert result['terminal_attempt'] is True and result['scenario_input_released'] is False
    assert result['staging_retained_for_vm_recovery']['retained'] is True
    assert [action for action, _ in requests] == ['inspect', 'inspect', 'preflight', 'reserve', 'stage']
    assert lease._fixture_provision_state['failed'] is True and lease._fixture_provision_state['receipt'] is None
    intent = json.loads((tmp_path / 'fixture-staging-intent.json').read_bytes())
    assert intent['staging'] == requests[-1][1]['staging'] and intent['vm_uuid'] == lease.state['domain_uuid']


@pytest.mark.parametrize('target', ['onpc-Unknown', 'onpc-Ubuntu24.04', 'onpc-Fedora43'])
def test_other_target_profiles_stay_gated_before_suite(monkeypatch, tmp_path, selection, target):
    monkeypatch.setattr(qualification.prepare_vm.vm_config, 'selected', lambda: SimpleNamespace(name=target))
    monkeypatch.setattr(qualification, 'authenticated_input', lambda _: nullcontext())
    suite = Mock()
    monkeypatch.setattr(qualification, 'Suite', suite)
    with pytest.raises(qualification.system.Error, match='target-not-qualified'):
        qualification.qualify(tmp_path, tmp_path / 'unused-assets', selection.record())
    suite.assert_not_called()
