"""Host-only runtime evidence acceptance/refusal; no worker or VM operations."""

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/e2e'))
import evidence
import inventory
import private_artifacts
sys.path.pop(0)

EvidenceError = private_artifacts.EvidenceError
SECRET = 'fixture-only-password-9!'


@pytest.fixture
def attempt(tmp_path):
    """A synthetic recorder contract with no guest credential provisioning."""
    document, _ = inventory.read_json(inventory.INVENTORY)
    document['scenarios'] = document['scenarios'][:1]
    document['scenarios'][0]['duration_seconds'] = 600
    document['scenarios'][0]['preconditions'].remove('fixture-credentials-via-secret-api')
    for relative in ('tests/requirements.json', 'docs/TestAutomation/E2E-Coverage.md'):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    executable = tmp_path / 'tests/e2e/synthetic.py'
    executable.parent.mkdir(parents=True)
    executable.write_text('raise RuntimeError("must never execute")\n')
    variant = document['scenarios'][0]['variants'][0]
    variant.update(status='ready', pending_reason=None,
                   executable={'path': 'tests/e2e/synthetic.py', 'test_id': 'synthetic-smoke'})
    path = tmp_path / 'inventory.json'
    path.write_text(json.dumps(document))
    inputs = {key: hashlib.sha256(key.encode()).hexdigest() for key in evidence.INPUT_FIELDS}
    inputs.update(inventory_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  environment_id='ubuntu26-04-pinned', package_sha256=None)
    contract = evidence.EvidenceContract(inventory_path=path, inputs=inputs,
                                         selector='E2E-001', run_id='run-one', root=tmp_path)
    case = inventory.resolve_selection(document, 'E2E-001', root=tmp_path)['cases'][0]
    with private_artifacts.PrivateCollector(run_id='run-one', secrets=[SECRET], parent=tmp_path) as collector:
        artifacts = [collector.add(kind, kind, ('reviewed ' + kind).encode(), reviewed=True)
                     for kind in case['expected_evidence']]
        assertions = []
        for kind, items in case['assertions'].items():
            for item in items:
                assertions.append({'assertion_id': item['id'], 'kind': kind,
                                   'step_id': item['step_id'], 'outcome': 'passed',
                                   'artifact_ids': [{'visible': 'screen', 'backend': 'backend',
                                                     'other_user': 'other-user'}[kind]]})
        steps = []
        for phase in inventory.PHASES:
            for step in case['phases'][phase]:
                checks = [a['assertion_id'] for a in assertions if a['step_id'] == step['id']]
                steps.append({'step_id': step['id'], 'phase': phase, 'operation': step['operation'],
                              'outcome': 'passed', 'monotonic_seconds': len(steps),
                              'boot_id': 'boot-1', 'session_ids': ['session-1'],
                              'assertion_ids': checks,
                              'artifact_ids': [a['artifact_id'] for a in artifacts] if checks else []})
        result = {'schema_version': 1, 'run_id': 'run-one', 'scenario_id': 'E2E-001',
                  'variant_id': 'gdm-observation', **inputs, 'executable': case['executable'],
                  'started_at': '2026-09-07T12:00:00Z', 'ended_at': '2026-09-07T12:00:10Z',
                  'steps': steps, 'artifacts': artifacts, 'assertions': assertions,
                  'outcomes': dict.fromkeys(inventory.OUTCOMES, 'passed'),
                  'first_failure': None, 'failures': [],
                  'cleanup': {key: 'complete' if key == 'lease_phase' else True
                              for key in evidence.CLEANUP_FIELDS}}
        yield contract, collector, result, path, inputs


def test_valid_synthetic_attempt_passes_with_partial_scope_and_private_copies(attempt):
    contract, collector, result, _, _ = attempt
    summary = contract.validate([result], collector)
    assert summary['outcome'] == 'passed' and summary['scope'] == 'partial'
    assert summary['case_ids'] == ['E2E-001/gdm-observation']
    assert stat.S_IMODE(collector.path.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in collector.path.iterdir())
    collector.save_report('result', {'summary': summary, 'cases': [result]})
    assert contract.validate([result], collector) == summary


def test_pending_repository_inventory_cannot_be_runtime_accepted(attempt):
    _, _, _, _, inputs = attempt
    with pytest.raises(inventory.InventoryError, match='selection:pending'):
        evidence.EvidenceContract(inputs=inputs, run_id='run-one')


@pytest.mark.parametrize('mutation', ['missing', 'extra', 'wrong-case', 'wrong-variant', 'old-run'])
def test_exact_case_selection_refuses_missing_extra_wrong_and_stale_results(attempt, mutation):
    contract, collector, result, _, _ = attempt
    records = [result]
    if mutation == 'missing':
        records = []
    elif mutation == 'extra':
        records.append(copy.deepcopy(result))
    else:
        key = {'wrong-case': 'scenario_id', 'wrong-variant': 'variant_id', 'old-run': 'run_id'}[mutation]
        result[key] = 'wrong'
    with pytest.raises(EvidenceError, match='result:(case-count|identity)'):
        contract.validate(records, collector)


@pytest.mark.parametrize('field', evidence.INPUT_FIELDS)
def test_every_provenance_identity_must_match_frozen_inputs(attempt, field):
    contract, collector, result, _, _ = attempt
    result[field] = 'stale'
    with pytest.raises(EvidenceError, match='stale-inputs'):
        contract.validate([result], collector)


def test_inventory_bytes_and_caller_inputs_are_frozen_before_execution(attempt):
    contract, collector, result, path, inputs = attempt
    inputs['source_sha256'] = '0' * 64
    assert contract.validate([result], collector)['outcome'] == 'passed'
    path.write_text(path.read_text() + '\n')
    with pytest.raises(EvidenceError, match='inventory-digest'):
        evidence.EvidenceContract(inventory_path=path, selector='E2E-001', inputs=inputs,
                                  run_id='run-two', root=path.parent)


@pytest.mark.parametrize('status', ['failed', 'skipped', 'interrupted', 'xfail', 'flaky', 'not-run'])
@pytest.mark.parametrize('location', ['step', 'assertion', 'product', 'infrastructure', 'collection', 'cleanup'])
def test_any_nonpassing_required_result_prevents_acceptance(attempt, status, location):
    contract, collector, result, _, _ = attempt
    if location == 'step':
        result['steps'][2]['outcome'] = status
    elif location == 'assertion':
        result['assertions'][0]['outcome'] = status
    else:
        result['outcomes'][location] = status
    with pytest.raises(EvidenceError, match='not-passed'):
        contract.validate([result], collector)


@pytest.mark.parametrize('mutation', ['missing', 'extra', 'duplicate', 'reorder', 'checkpoint', 'phase'])
def test_ordered_step_execution_cannot_be_partial_or_replaced(attempt, mutation):
    contract, collector, result, _, _ = attempt
    steps = result['steps']
    if mutation == 'missing':
        steps.pop()
    elif mutation == 'extra':
        steps.append(copy.deepcopy(steps[2]))
    elif mutation == 'duplicate':
        steps[3] = copy.deepcopy(steps[2])
    elif mutation == 'reorder':
        steps[2], steps[3] = steps[3], steps[2]
    elif mutation == 'checkpoint':
        steps[3]['operation'] = 'checkpoint'
    else:
        steps[3]['phase'] = 'setup'
    with pytest.raises(EvidenceError, match='step-(count|identity)'):
        contract.validate([result], collector)


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'wrong-step', 'wrong-kind', 'no-artifact',
                                     'unknown-artifact', 'wrong-evidence-kind', 'unlinked'])
def test_executed_assertions_require_identity_and_their_actual_step_evidence(attempt, mutation):
    contract, collector, result, _, _ = attempt
    item = result['assertions'][0]
    if mutation == 'missing':
        result['assertions'].pop()
    elif mutation == 'duplicate':
        result['assertions'][1] = copy.deepcopy(item)
    elif mutation == 'wrong-step':
        item['step_id'] = 'step-1'
    elif mutation == 'wrong-kind':
        item['kind'] = 'backend'
    elif mutation == 'no-artifact':
        item['artifact_ids'] = []
    elif mutation == 'unknown-artifact':
        item['artifact_ids'] = ['missing']
    elif mutation == 'wrong-evidence-kind':
        item['artifact_ids'] = ['backend']
    else:
        result['steps'][4]['artifact_ids'].remove('screen')
    with pytest.raises(EvidenceError, match='assertion'):
        contract.validate([result], collector)


@pytest.mark.parametrize('key', evidence.CLEANUP_FIELDS)
def test_every_cleanup_guarantee_is_required(attempt, key):
    contract, collector, result, _, _ = attempt
    result['cleanup'][key] = 'incomplete' if key == 'lease_phase' else False
    with pytest.raises(EvidenceError, match='cleanup-incomplete'):
        contract.validate([result], collector)


@pytest.mark.parametrize('value', [-1, True, float('nan'), float('inf'), 601, '1'])
def test_step_times_are_finite_bounded_monotonic_measurements(attempt, value):
    contract, collector, result, _, _ = attempt
    result['steps'][3]['monotonic_seconds'] = value
    with pytest.raises(EvidenceError, match='step-time'):
        contract.validate([result], collector)


@pytest.mark.parametrize('value', ['2026-09-07T12:00:00', '2026-02-30T12:00:00Z',
                                 '2026-09-07T11:59:59Z', '2026-09-07T12:11:00Z', None])
def test_actual_attempt_boundaries_cannot_be_missing_reversed_or_over_budget(attempt, value):
    contract, collector, result, _, _ = attempt
    result['ended_at'] = value
    with pytest.raises(EvidenceError, match='(timestamp|duration)'):
        contract.validate([result], collector)


def test_first_failure_survives_cleanup_and_cannot_be_replaced_by_retry(attempt):
    contract, collector, result, _, _ = attempt
    ledger = evidence.FailureLedger()
    ledger.record('product', 'assertion-failed', step_id='step-2', monotonic_seconds=3)
    first = ledger.first_failure
    ledger.record('collection', 'copy-failed', step_id='end', monotonic_seconds=5)
    ledger.record('cleanup', 'restore-failed', step_id='cleanup', monotonic_seconds=6)
    snapshot = ledger.snapshot()
    snapshot[0]['code'] = 'changed'
    assert ledger.first_failure == first
    for event in ledger.snapshot():
        contract.record_failure('E2E-001/gdm-observation', event['category'], event['code'],
                                step_id=event['step_id'], monotonic_seconds=event['monotonic_seconds'])
    result.update(failures=ledger.snapshot(), first_failure=ledger.first_failure)
    result['outcomes'].update(product='failed', collection='failed', cleanup='failed')
    report = collector.save_report('attempt', result)
    original = report.read_bytes()
    with pytest.raises(EvidenceError, match='attempt-not-passed'):
        contract.validate([result], collector)
    result['outcomes'] = dict.fromkeys(inventory.OUTCOMES, 'passed')
    with pytest.raises(EvidenceError, match='attempt-not-passed'):
        contract.validate([result], collector)
    with pytest.raises(EvidenceError, match='write-failed'):
        collector.save_report('attempt', result)
    assert report.read_bytes() == original
    result['first_failure'] = ledger.snapshot()[-1]
    with pytest.raises(EvidenceError, match='first-failure'):
        contract.validate([result], collector)
    result.update(first_failure=None, failures=[])
    with pytest.raises(EvidenceError, match='failure-history'):
        contract.validate([result], collector)
    assert contract.failure_state('E2E-001/gdm-observation')['first_failure'] == first


@pytest.mark.parametrize('location', ['steps', 'assertions', 'artifacts', 'outcomes', 'cleanup', 'failures'])
@pytest.mark.parametrize('value', [None, 7, 'private-sentinel', {}])
def test_malformed_nested_results_have_bounded_secret_free_errors(attempt, location, value):
    contract, collector, result, _, _ = attempt
    result[location] = value
    with pytest.raises(EvidenceError) as caught:
        contract.validate([result], collector)
    assert 'private-sentinel' not in str(caught.value)


@pytest.mark.parametrize('mutation', ['digest', 'path', 'redaction', 'old-run', 'duplicate', 'missing'])
def test_manifest_cannot_claim_uncollected_or_stale_artifacts(attempt, mutation):
    contract, collector, result, _, _ = attempt
    item = result['artifacts'][0]
    if mutation == 'duplicate':
        result['artifacts'].append(copy.deepcopy(item))
    elif mutation == 'missing':
        result['artifacts'].pop()
    else:
        key = {'digest': 'sha256', 'path': 'path', 'redaction': 'redaction', 'old-run': 'run_id'}[mutation]
        item[key] = '../../private-sentinel'
    with pytest.raises(EvidenceError):
        contract.validate([result], collector)


@pytest.fixture
def collector(tmp_path):
    with private_artifacts.PrivateCollector(run_id='run-one', secrets=[SECRET], parent=tmp_path) as value:
        yield value


@pytest.mark.parametrize('data', [SECRET.encode(), base64.b64encode(SECRET.encode()),
                                 SECRET.replace('!', '%21').encode(), SECRET.encode('utf-16-le')])
def test_secret_data_is_rejected_before_any_copy_is_created(collector, data):
    with pytest.raises(EvidenceError, match='secret-detected') as caught:
        collector.add('backend', 'backend', b'prefix ' + data, reviewed=True)
    assert SECRET not in str(caught.value)
    assert list(collector.path.iterdir()) == []


def test_unreviewed_captures_and_reports_with_credentials_are_never_written(collector):
    with pytest.raises(EvidenceError, match='review-required'):
        collector.add('screen', 'screen', b'opaque capture')
    with pytest.raises(EvidenceError, match='secret-detected'):
        collector.save_report('result', {'unexpected': SECRET})
    assert list(collector.path.iterdir()) == []


def test_copy_is_private_and_independent_of_source_changes(collector, tmp_path):
    source = tmp_path / 'source'
    source.mkdir(mode=0o700)
    path = source / 'reviewed.txt'
    path.write_bytes(b'reviewed observation')
    path.chmod(0o600)
    record = collector.copy(source, path.name, 'backend', 'backend', reviewed=True)
    path.write_bytes(b'changed source')
    collector.verify([record])
    assert (collector.path / record['path']).read_bytes() == b'reviewed observation'


@pytest.mark.parametrize('unsafe', ['symlink', 'hardlink', 'fifo', 'directory', 'public-file',
                                   'public-directory', 'parent-symlink', 'traversal', 'absolute', 'large'])
def test_unsafe_sources_are_refused_without_opening_arbitrary_data(collector, tmp_path, unsafe):
    source = tmp_path / 'source'
    source.mkdir(mode=0o700)
    path = source / 'reviewed.txt'
    path.write_bytes(b'safe')
    path.chmod(0o600)
    name = path.name
    if unsafe == 'symlink':
        link = source / 'link.txt'
        link.symlink_to(path)
        name = link.name
    elif unsafe == 'hardlink':
        os.link(path, source / 'hardlink.txt')
    elif unsafe == 'fifo':
        os.mkfifo(source / 'pipe', 0o600)
        name = 'pipe'
    elif unsafe == 'directory':
        (source / 'nested').mkdir(mode=0o700)
        name = 'nested'
    elif unsafe == 'public-file':
        path.chmod(0o644)
    elif unsafe == 'public-directory':
        source.chmod(0o755)
    elif unsafe == 'parent-symlink':
        link = tmp_path / 'alias'
        link.symlink_to(source, target_is_directory=True)
        source = link
    elif unsafe == 'traversal':
        name = '../reviewed.txt'
    elif unsafe == 'absolute':
        name = str(path)
    elif unsafe == 'large':
        with path.open('wb') as stream:
            stream.truncate(private_artifacts.MAX_BYTES + 1)
    with pytest.raises(EvidenceError):
        collector.copy(source, name, 'backend', 'backend', reviewed=True)
    assert list(collector.path.iterdir()) == []


@pytest.mark.parametrize('mutation', ['bytes', 'symlink', 'hardlink', 'public', 'unregistered'])
def test_final_gate_rechecks_copies_and_rejects_unregistered_worker_files(attempt, mutation):
    contract, collector, result, _, _ = attempt
    path = collector.path / result['artifacts'][0]['path']
    if mutation == 'bytes':
        path.write_bytes(b'changed')
    elif mutation == 'symlink':
        path.unlink()
        path.symlink_to('/etc/passwd')
    elif mutation == 'hardlink':
        os.link(path, collector.path / 'second-link')
    elif mutation == 'public':
        path.chmod(0o644)
    else:
        (collector.path / 'vars.json').write_text('{}')
    with pytest.raises(EvidenceError, match='artifact:'):
        contract.validate([result], collector)


def test_failed_write_never_registers_an_artifact(collector):
    with patch.object(private_artifacts.os, 'fsync', side_effect=OSError('private-sentinel')):
        with pytest.raises(EvidenceError, match='write-failed') as caught:
            collector.add('backend', 'backend', b'reviewed', reviewed=True)
    assert 'private-sentinel' not in str(caught.value)
    with pytest.raises(EvidenceError, match='unregistered-file'):
        collector.verify([])


@pytest.mark.parametrize('mutation', ['renamed', 'symlink', 'public'])
def test_collector_directory_identity_and_privacy_are_revalidated(collector, mutation):
    record = collector.add('backend', 'backend', b'reviewed', reviewed=True)
    if mutation == 'public':
        collector.path.chmod(0o755)
    else:
        previous = collector.path.with_name(collector.path.name + '-previous')
        collector.path.rename(previous)
        if mutation == 'renamed':
            collector.path.mkdir(mode=0o700)
        else:
            collector.path.symlink_to(previous, target_is_directory=True)
    with pytest.raises(EvidenceError, match='artifact:'):
        collector.verify([record])
    with pytest.raises(EvidenceError, match='artifact:'):
        collector.save_report('result', {'outcome': 'passed'})


def test_retained_failure_report_tampering_prevents_later_acceptance(attempt):
    contract, collector, result, _, _ = attempt
    report = collector.save_report('diagnostic', {'code': 'original-failure'})
    report.write_text('{"code": "changed"}')
    with pytest.raises(EvidenceError, match='report-digest'):
        contract.validate([result], collector)


def test_secrets_cannot_be_used_as_artifact_or_report_filenames(tmp_path):
    secret = 'credential-sentinel'
    with private_artifacts.PrivateCollector(run_id='run-one', secrets=[secret], parent=tmp_path) as collector:
        with pytest.raises(EvidenceError, match='secret-detected'):
            collector.add(secret, 'backend', b'reviewed', reviewed=True)
        with pytest.raises(EvidenceError, match='secret-detected'):
            collector.save_report(secret, {'outcome': 'failed'})
        assert list(collector.path.iterdir()) == []
    with pytest.raises(EvidenceError, match='secret-detected'):
        private_artifacts.PrivateCollector(run_id=secret, secrets=[secret], parent=tmp_path)


def test_step_measurement_cannot_outlive_recorded_attempt(attempt):
    contract, collector, result, _, _ = attempt
    result['ended_at'] = result['started_at']
    with pytest.raises(EvidenceError, match='step-time'):
        contract.validate([result], collector)


def test_source_changed_during_read_is_refused(collector, tmp_path):
    source = tmp_path / 'source'
    source.mkdir(mode=0o700)
    path = source / 'reviewed.txt'
    path.write_bytes(b'reviewed')
    path.chmod(0o600)
    original_read = private_artifacts.os.read

    def changing_read(fd, size):
        data = original_read(fd, size)
        if data:
            path.write_bytes(b'changed-length')
        return data

    with patch.object(private_artifacts.os, 'read', side_effect=changing_read):
        with pytest.raises(EvidenceError, match='changed-during-copy'):
            collector.copy(source, path.name, 'backend', 'backend', reviewed=True)
    assert list(collector.path.iterdir()) == []


def test_full_selection_executes_each_variant_once_and_cannot_reuse_another_case(attempt):
    _, collector, result, path, inputs = attempt
    document = json.loads(path.read_text())
    family = document['scenarios'][0]
    family['matrix']['dimensions']['transport'].append('second-transport')
    variant = copy.deepcopy(family['variants'][0])
    variant.update(id='second-transport', parameters={'transport': 'second-transport'},
                   executable={'path': 'tests/e2e/synthetic.py', 'test_id': 'synthetic-second'})
    family['variants'].append(variant)
    path.write_text(json.dumps(document))
    inputs['inventory_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    result['inventory_sha256'] = inputs['inventory_sha256']
    contract = evidence.EvidenceContract(inventory_path=path, inputs=inputs,
                                         run_id='run-one', root=path.parent)
    second = copy.deepcopy(result)
    second.update(variant_id=variant['id'], executable=variant['executable'])
    second['artifacts'] = [collector.add('second-' + a['artifact_id'], a['kind'], b'reviewed-second',
                                          reviewed=True) for a in result['artifacts']]
    for item in second['steps'] + second['assertions']:
        item['artifact_ids'] = ['second-' + aid for aid in item['artifact_ids']]
    assert contract.validate([result, second], collector)['scope'] == 'full'
    for records in ([result, result], [second, result], [result], [result, second, second]):
        with pytest.raises(EvidenceError, match='result:(identity|case-count)'):
            contract.validate(records, collector)
