"""Accepted proof survives ordinary bounded rotation without a new archive format."""
import copy
import json
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import uuid
import zipfile
from contextlib import contextmanager

import pytest

import evidence_bundle as bundle
import plan_evidence as proof
from execution_plan import plan_namespace


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    import vm_config
    monkeypatch.delenv(bundle.retention.VARIABLE, raising=False)
    monkeypatch.setattr(bundle.storage, 'ROOT', tmp_path)
    monkeypatch.setattr(bundle.storage, 'BASE', tmp_path / 'output/test-runs')
    monkeypatch.setattr(vm_config, 'registry', lambda: {})
    docs = tmp_path / 'docs'
    docs.mkdir()
    plan = SimpleNamespace(root=tmp_path, path='docs/Plan.md', queue='docs/Queue.md')
    (docs / 'Plan.md').write_text('Task queue: [Queue](Queue.md).\n')
    namespace = bundle.storage.directory('plans', root=tmp_path) / plan_namespace(plan.path)
    bundle.retention.ensure_directory(namespace)
    runs = bundle.retention.Store(namespace / 'retention')
    reports = bundle.retention.Store(bundle.storage.directory('state') / 'retention-host')

    def accepted(task):
        run = namespace / uuid.uuid4().hex
        run.mkdir(mode=0o700)
        with runs.session():
            bundle.retention.retain(run)
        with reports.session():
            report = Path(bundle.retention.allocate(tempfile.mkdtemp,
                prefix='onpc-report-', dir=bundle.storage.directory('reports')))
            (report / 'result.md').write_text('Exact report for ' + task)
        (docs / 'Queue.md').write_text('| [x] | ' + task + ' | task | Baseline | scope | 1 min |\n')
        (docs / 'Brief.md').write_text('Exact selected brief for ' + task)
        state = dict(task_id=task, task=dict(brief='docs/Brief.md', targets=[], acceptance='host'),
                     task_sessions=1)
        proof.capture(plan, run, state)
        result = dict(task_id=task, status='task_complete', cleanup_complete=True,
            checks=[dict(kind='host', target='', result='passed', evidence=str(report / 'result.md'))],
            summary='accepted ' + task, handoff='done', stage_paths=[], blocker=None)
        for name, data in {
            'agent-result.json': json.dumps(result), 'checkpoint.json': json.dumps(state),
            'nested.json': '[]', 'prompt.txt': 'Exact prompt for ' + task,
            'agent-commands.log': 'Exact commands for ' + task,
        }.items():
            (run / name).write_text(data)
        return run, state, result, report

    return SimpleNamespace(plan=plan, accepted=accepted, namespace=namespace, runs=runs)


def test_exact_proof_survives_more_than_three_later_sessions_and_independent_exports(campaign):
    first = None
    for index in range(6):
        run, state, result, report = campaign.accepted(str(index))
        accepted = proof.preserve(campaign.plan, run, state, result)
        assert Path(accepted['ledger']).name == 'accepted-ledger.json'
        if first is None:
            first = (run, report, dict(accepted['tasks']['0']))
        # An unrelated export journal rotates independently and cannot retire
        # the plan's accepted proof or consume its three publication slots.
        exports = bundle.retention.Store(bundle.storage.directory('exports') / 'retention')
        with exports.session():
            allocation = Path(bundle.retention.allocate(tempfile.mkdtemp,
                prefix='onpc-independent-', dir=bundle.storage.directory('exports')))
            (allocation / 'unrelated.txt').write_text(str(index))
    old_run, old_report, original = first
    assert not old_run.exists() and not old_report.exists()
    current = proof.recover(campaign.plan)
    assert set(current['tasks']) == set(map(str, range(6)))
    assert current['tasks']['0'] == original
    def read(path):
        return bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(), current['bundle'],
                              member=str(path), count=bundle.MAX_READ)
    assert json.loads(read(original['result']))['cleanup_complete'] is True
    capsule = Path(original['result']).parent
    assert read(capsule / 'prompt.txt') == b'Exact prompt for 0'
    assert read(capsule / 'agent-commands.log') == b'Exact commands for 0'
    assert read(capsule / 'nested.json') == b'[]'
    assert json.loads(read(capsule / 'cleanup.json'))['cleanup_complete'] is True
    assert read(old_report / 'result.md') == b'Exact report for 0'
    inputs = json.loads(read(original['inputs'][0]))
    brief = next(item for item in inputs['files'] if item['path'].endswith('Brief.md'))
    assert read(Path(original['inputs'][0]).parent / brief['member']) == b'Exact selected brief for 0'


def test_git_retry_reuses_only_the_exact_verified_result(campaign):
    run, state, result, _ = campaign.accepted('first')
    retained = proof.preserve(campaign.plan, run, state, result)
    assert proof.preserve(campaign.plan, run, state, result) == retained
    with pytest.raises(ValueError, match='accepted result changed'):
        proof.preserve(campaign.plan, run, state, dict(result, summary='changed'))


@pytest.mark.parametrize('reference', [
    '{path}. Controller source is unchanged.',
    '{path}: passed!',
    '"{path}".',
    '{path}#checks; owned cleanup complete.',
    '[report]({path}).',
    '`{path}`.',
])
def test_prose_report_references_publish_exact_evidence(campaign, reference):
    run, state, result, report = campaign.accepted('first')
    source = report / 'result.md'
    result['checks'][0]['evidence'] = reference.format(path=source)
    (run / 'agent-result.json').write_text(json.dumps(result))
    assert proof._references(campaign.plan, result, state) == [str(source)]
    accepted = proof.preserve(campaign.plan, run, state, result)
    assert bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(),
        accepted['bundle'], member=str(source)) == b'Exact report for first'


@pytest.mark.parametrize('reference', ['[report]({path}).', '`{path}`.'])
@pytest.mark.parametrize('filename', ['result.md.', 'result.md,', 'result, exact.md'])
def test_delimited_report_paths_preserve_literal_punctuation(campaign, reference, filename):
    run, state, result, report = campaign.accepted('first')
    source = report / filename
    (report / 'result.md').rename(source)
    result['checks'][0]['evidence'] = reference.format(path=source)
    (run / 'agent-result.json').write_text(json.dumps(result))
    assert proof._references(campaign.plan, result, state) == [str(source)]
    accepted = proof.preserve(campaign.plan, run, state, result)
    assert bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(),
        accepted['bundle'], member=str(source)) == b'Exact report for first'


def test_link_labels_are_not_evidence_sources(campaign):
    _, state, result, report = campaign.accepted('first')
    source = report / 'result.md'
    result['checks'][0]['evidence'] = f'[{report / "label-only.md"}]({source}).'
    assert proof._references(campaign.plan, result, state) == [str(source)]


def test_queue_prose_and_relative_links_preserve_one_exact_source(campaign):
    _, state, result, report = campaign.accepted('first')
    source = report / 'result.md'
    queue = campaign.plan.root / campaign.plan.queue
    relative = os.path.relpath(source, queue.parent)
    queue.write_text('| [x] | first | task | Baseline | scope | '
                     f'Passed: {source}. [report]({relative}). |\n')
    result['checks'][0]['evidence'] = 'See queue for retained evidence.'
    assert proof._references(campaign.plan, result, state) == [str(source)]


def test_missing_prose_report_still_refuses_publication(campaign):
    run, state, result, report = campaign.accepted('first')
    result['checks'][0]['evidence'] = f'Missing report: {report / "missing.md"}.'
    (run / 'agent-result.json').write_text(json.dumps(result))
    with pytest.raises(FileNotFoundError, match='missing.md'):
        proof.preserve(campaign.plan, run, state, result)
    assert not proof.locator(campaign.plan).exists()


@pytest.mark.parametrize('defect', ['none', 'missing-member', 'corrupt', 'live-replacement'])
def test_rotated_reference_uses_only_exact_verified_selected_bundle(campaign, defect):
    run, state, result, report = campaign.accepted('first')
    original = report / 'result.md'
    with bundle.Selection(campaign.plan.root, os.geteuid(), os.getegid(), [],
                          [str(report)], []) as selection:
        archived = bundle.export(selection, expected=selection.selection_sha256)['path']
    reports = bundle.retention.Store(bundle.storage.directory('state') / 'retention-host')
    for _ in range(3):
        with reports.session():
            bundle.retention.allocate(tempfile.mkdtemp, prefix='onpc-later-',
                                      dir=bundle.storage.directory('reports'))
    assert not original.exists()
    referenced = original if defect != 'missing-member' else report / 'unknown.md'
    result['checks'][0]['evidence'] = f'Exact report: `{referenced}`. Archive: `{archived}`.'
    (run / 'agent-result.json').write_text(json.dumps(result))
    if defect == 'corrupt':
        with open(archived, 'ab') as stream:
            stream.write(b'changed archive')
    elif defect == 'live-replacement':
        report.mkdir(mode=0o700)
        original.write_text('unregistered replacement')
    if defect == 'none':
        accepted = proof.preserve(campaign.plan, run, state, result)
        assert bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(),
            accepted['bundle'], member=str(original)) == b'Exact report for first'
    else:
        expected = proof.EvidenceUnavailable if defect == 'missing-member' else ValueError
        with pytest.raises(expected):
            proof.preserve(campaign.plan, run, state, result)
        assert not proof.locator(campaign.plan).exists()


def test_expired_references_name_every_missing_path_without_acceptance(campaign):
    run, state, result, report = campaign.accepted('first')
    missing = [report / 'missing.md', bundle.storage.directory('exports') /
               'onpc-evidence-bundle-missing/evidence.zip']
    result['checks'][0]['evidence'] = ' '.join(f'`{path}`' for path in missing)
    (run / 'agent-result.json').write_text(json.dumps(result))
    with pytest.raises(proof.EvidenceUnavailable) as failure:
        proof.preserve(campaign.plan, run, state, result)
    assert all(str(path) in str(failure.value) for path in missing)
    assert not proof.locator(campaign.plan).exists()


@pytest.mark.parametrize('targets', [[], ['guest']])
def test_private_reference_access_is_deferred_only_to_authenticated_target_reader(
        campaign, monkeypatch, targets):
    run, state, result, report = campaign.accepted('first')
    state['task']['targets'] = targets
    source = str(report / 'result.md')
    original_present = bundle.Selection.reference_present
    def present(selection, path):
        if str(path) == source:
            raise PermissionError('private target allocation')
        return original_present(selection, path)
    monkeypatch.setattr(bundle.Selection, 'reference_present', present)
    monkeypatch.setattr(proof, 'os', SimpleNamespace(**(vars(os) | {'geteuid': lambda: 1000})))
    monkeypatch.setattr(proof, 'recover', lambda _: None)
    commands = []
    def invoke(command, **kwargs):
        commands.append(command)
        assert command[:3] == ['pkexec', '--keep-cwd', '/usr/local/libexec/onpc-test-artifacts']
        assert ['--target', 'guest'] == command[command.index('--target'):command.index('--target') + 2]
        assert source in [command[index + 1] for index, value in enumerate(command) if value == '--reference']
        assert kwargs['cwd'] == campaign.plan.root
        return SimpleNamespace(returncode=0, stdout=json.dumps({'selection_sha256': 'exact'}))
    monkeypatch.setattr(proof.subprocess, 'run', invoke)
    if targets:
        assert proof.preserve(campaign.plan, run, state, result) is None
        assert [command[3] for command in commands] == ['bundle-plan', 'bundle-export']
    else:
        with pytest.raises(PermissionError, match='private target allocation'):
            proof.preserve(campaign.plan, run, state, result)
        assert not commands


@pytest.mark.parametrize('failure', ['expired', 'permission', 'bad-json', 'foreign', 'duplicate', 'wrong-code'])
def test_target_helper_only_renews_explicit_structured_missing_references(campaign, monkeypatch, failure):
    run, state, result, report = campaign.accepted('first')
    state['task']['targets'] = ['guest']
    source = str(report / 'result.md')
    monkeypatch.setattr(proof, 'os', SimpleNamespace(**(vars(os) | {'geteuid': lambda: 1000})))
    monkeypatch.setattr(proof, 'recover', lambda _: None)
    def invoke(command, **_):
        assert '--reference' in command and source in command
        paths = [source, source] if failure == 'duplicate' else [source]
        if failure == 'foreign':
            paths = [str(run / 'unselected.json')]
        payload = bundle.encoded(dict(error='evidence_unavailable', paths=paths)).decode()
        if failure in ('permission', 'bad-json'):
            payload = 'test-artifacts: PermissionError' if failure == 'permission' else 'invalid JSON'
        return SimpleNamespace(returncode=2 if failure in ('permission', 'wrong-code') else 3,
                               stderr=payload, stdout='')
    monkeypatch.setattr(proof.subprocess, 'run', invoke)
    expected = proof.EvidenceUnavailable if failure == 'expired' else ValueError
    with pytest.raises(expected):
        proof.preserve(campaign.plan, run, state, result)
    assert not proof.locator(campaign.plan).exists()


def test_evidence_renewal_keeps_exact_rejected_source_across_bounded_rotation(campaign):
    original_run, state, result, _ = campaign.accepted('first')
    proof._source(campaign.plan, original_run, state, result)
    renewal = dict(reason='proof expired', result=result,
                   evidence_source=state.pop('evidence_source'))
    state['evidence_renewal'] = renewal
    for _ in range(5):
        run = campaign.namespace / uuid.uuid4().hex
        run.mkdir(mode=0o700)
        with campaign.runs.session():
            bundle.retention.retain(run)
        proof.carry(campaign.plan, run, state)
        source = Path(renewal['evidence_source']['path'])
        assert source.parent.parent == run
        assert json.loads((source / 'agent-result.json').read_bytes()) == result
        assert (source / 'agent-commands.log').read_text() == 'Exact commands for first'
    assert not original_run.exists()
    (source / 'agent-commands.log').write_text('changed')
    with pytest.raises(ValueError, match='retained session source changed'):
        proof.carry(campaign.plan, run, state)


def test_renewed_acceptance_retains_both_exact_attempts(campaign):
    run, state, result, _ = campaign.accepted('first')
    old = proof.preserve(campaign.plan, run, state, result)
    state['task_sessions'] += 1
    proof.capture(campaign.plan, run, state)
    renewed = dict(result, summary='renewed acceptance after Git reconciliation')
    (run / 'agent-result.json').write_text(json.dumps(renewed))
    (run / 'checkpoint.json').write_text(json.dumps(state))
    current = proof.preserve(campaign.plan, run, state, renewed)
    assert current['tasks']['first']['attempt'] != old['tasks']['first']['attempt']
    assert bundle.decoded(bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(),
        current['bundle'], member=old['tasks']['first']['result'])) == result
    assert bundle.decoded(bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(),
        current['bundle'], member=current['tasks']['first']['result'])) == renewed


def test_unfinished_inputs_survive_more_than_three_restarts(campaign):
    original_run, state, _, _ = campaign.accepted('unfinished')
    original_metadata = (Path(state['evidence_inputs'][0]) / 'inputs.json').read_bytes()
    for number in range(5):
        run = campaign.namespace / uuid.uuid4().hex
        run.mkdir(mode=0o700)
        with campaign.runs.session():
            bundle.retention.retain(run)
        (campaign.plan.root / 'docs/Brief.md').write_text('continued brief ' + str(number))
        state['task_sessions'] += 1
        proof.capture(campaign.plan, run, state)
        assert all(Path(path).parent.parent == run for path in state['evidence_inputs'])
    assert not original_run.exists()
    assert len(state['evidence_inputs']) == 6
    assert (Path(state['evidence_inputs'][0]) / 'inputs.json').read_bytes() == original_metadata
    assert (Path(state['evidence_inputs'][0]) / 'input-0002').read_bytes() == b'Exact selected brief for unfinished'


def test_suspended_inputs_survive_prerequisite_rotations_without_sessions_or_git_changes(campaign):
    consumer_run, consumer, consumer_result, _ = campaign.accepted('consumer')
    nested_run, nested, _, _ = campaign.accepted('nested-consumer')
    initial_run, state, active_result, _ = campaign.accepted('prerequisite')
    consumer.update(phase='recover', pending_completion=consumer_result,
                    recovery_run=str(consumer_run),
                    commit_intent=dict(paths=['owned.md'], commit='retained'),
                    stage_baseline={'foreign.md': 'preserve'}, protected_staged=['foreign.md'],
                    suspended_tasks={'nested-consumer': nested})
    state.update(suspended_tasks={'consumer': consumer}, total_sessions=4,
                 phase='recover', pending_completion=active_result,
                 commit_intent=dict(paths=['active.md'], commit='active-retained'),
                 stage_baseline={'active.md': 'original'}, protected_staged=['staged.md'])
    def states(value):
        yield value
        for child in value.get('suspended_tasks', {}).values():
            yield from states(child)
    def without_inputs(value):
        copied = copy.deepcopy(value)
        for record in states(copied):
            record.pop('evidence_inputs', None)
            record.pop('evidence_source', None)
        return copied
    unchanged = without_inputs(state)
    originals = {record['task_id']: (Path(record['evidence_inputs'][0]) / 'input-0002').read_bytes()
                 for record in states(state)}
    proof.carry(campaign.plan, initial_run, state)
    for _ in range(5):
        run = campaign.namespace / uuid.uuid4().hex
        run.mkdir(mode=0o700)
        with campaign.runs.session():
            bundle.retention.retain(run)
        proof.carry(campaign.plan, run, state)
        assert without_inputs(state) == unchanged
        for record in states(state):
            assert len(record['evidence_inputs']) == 1
            source = Path(record['evidence_inputs'][0])
            assert source.parent.parent == run
            assert (source / 'input-0002').read_bytes() == originals[record['task_id']]
    assert not consumer_run.exists() and not nested_run.exists() and not initial_run.exists()


def test_carry_without_legacy_inputs_is_noop_and_missing_originals_refuse(campaign):
    run, state, _, _ = campaign.accepted('first')
    legacy = dict(phase='recover', task_id='legacy', task_sessions=3,
                  stage_baseline={'foreign': 'contents'}, protected_staged=['foreign'])
    before = copy.deepcopy(legacy)
    assert proof.carry(campaign.plan, run, legacy) == before
    source = Path(state['evidence_inputs'][0])
    (source / 'input-0002').unlink()
    with pytest.raises(FileNotFoundError):
        proof.carry(campaign.plan, run, state)


def test_missing_recovery_brief_retains_exact_original_snapshot(campaign):
    run, state, result, _ = campaign.accepted('first')
    original = Path(state['evidence_inputs'][0])
    brief = campaign.plan.root / 'docs/Brief.md'
    brief.unlink()
    state.update(phase='recover', task_sessions=2)
    latest = proof.capture(campaign.plan, run, state)
    metadata = bundle.decoded((latest / 'inputs.json').read_bytes())
    assert metadata['missing'] == [dict(path=str(brief), reason='missing during retained task recovery')]
    assert not any(entry['path'] == str(brief) for entry in metadata['files'])
    assert (original / 'input-0002').read_bytes() == b'Exact selected brief for first'
    assert 'evidence_capture_requires_brief' not in state
    (run / 'checkpoint.json').write_text(json.dumps(state))
    accepted = proof.preserve(campaign.plan, run, state, result)
    assert bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(), accepted['bundle'],
        member=str(original / 'input-0002')) == b'Exact selected brief for first'


def test_legacy_missing_brief_requires_restore_then_later_capture(campaign):
    run, state, result, _ = campaign.accepted('first')
    state.pop('evidence_inputs')
    state.pop('evidence_attempt')
    brief = campaign.plan.root / 'docs/Brief.md'
    brief.unlink()
    state.update(phase='recover', task_sessions=2)
    proof.capture(campaign.plan, run, state)
    assert state['evidence_capture_requires_brief'] is True
    with pytest.raises(ValueError, match='later session must capture'):
        proof.preserve(campaign.plan, run, state, result)
    brief.write_text('exact restored brief')
    with pytest.raises(ValueError, match='later session must capture'):
        proof.preserve(campaign.plan, run, state, result)
    state['task_sessions'] += 1
    latest = proof.capture(campaign.plan, run, state)
    assert 'evidence_capture_requires_brief' not in state
    (run / 'checkpoint.json').write_text(json.dumps(state))
    accepted = proof.preserve(campaign.plan, run, state, result)
    assert bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(), accepted['bundle'],
        member=str(latest / 'input-0002')) == b'exact restored brief'


def test_missing_first_execution_brief_remains_a_refusal(campaign):
    run, state, _, _ = campaign.accepted('first')
    (campaign.plan.root / 'docs/Brief.md').unlink()
    state.update(phase='implement', in_flight=True)
    with pytest.raises(FileNotFoundError):
        proof.capture(campaign.plan, run, state)


@pytest.mark.parametrize('defect', ['input', 'result', 'report', 'bundle'])
def test_missing_or_changed_proof_refuses_without_replacing_valid_index(campaign, defect):
    run, state, result, report = campaign.accepted('first')
    if defect == 'bundle':
        old = proof.preserve(campaign.plan, run, state, result)
        before = proof.locator(campaign.plan).read_bytes()
        Path(old['bundle']).write_bytes(b'changed')
    elif defect == 'input':
        (Path(state['evidence_inputs'][0]) / 'input-0000').write_text('changed')
    elif defect == 'result':
        (run / 'agent-result.json').write_text('{}')
    else:
        (report / 'result.md').unlink()
    with pytest.raises((ValueError, OSError)):
        proof.preserve(campaign.plan, run, state, result)
    if defect == 'bundle':
        assert proof.locator(campaign.plan).read_bytes() == before
    else:
        assert not proof.locator(campaign.plan).exists()


def test_committed_interruption_recovers_index_before_retiring_old_proof(campaign, monkeypatch):
    for task in ('first', 'second', 'third'):
        run, state, result, _ = campaign.accepted(task)
        old = proof.preserve(campaign.plan, run, state, result)
    first_bundle = Path(old['bundle'])
    before = proof.locator(campaign.plan).read_bytes()
    run, state, result, _ = campaign.accepted('fourth')
    original = proof._atomic
    monkeypatch.setattr(proof, '_atomic', lambda *_: (_ for _ in ()).throw(OSError('interrupted index')))
    with pytest.raises(OSError, match='interrupted index'):
        proof.preserve(campaign.plan, run, state, result)
    assert proof.locator(campaign.plan).read_bytes() == before
    assert first_bundle.exists()
    monkeypatch.setattr(proof, '_atomic', original)
    recovered = proof.recover(campaign.plan)
    assert set(recovered['tasks']) == {'first', 'second', 'third', 'fourth'}
    assert proof.recover(campaign.plan) == recovered


def test_interrupted_precommit_preserves_previous_publication(campaign, monkeypatch):
    run, state, result, _ = campaign.accepted('first')
    old = proof.preserve(campaign.plan, run, state, result)
    before = proof.locator(campaign.plan).read_bytes()
    run, state, result, _ = campaign.accepted('second')
    monkeypatch.setattr(bundle.Selection, 'write', lambda *_: (_ for _ in ()).throw(OSError('interrupted copy')))
    with pytest.raises(OSError, match='interrupted copy'):
        proof.preserve(campaign.plan, run, state, result)
    assert proof.locator(campaign.plan).read_bytes() == before
    assert proof.recover(campaign.plan) == old


def test_failed_publication_pending_source_survives_more_than_three_new_runs(campaign, monkeypatch):
    original_run, state, result, _ = campaign.accepted('first')
    state['pending_completion'] = result
    original_write = bundle.Selection.write
    monkeypatch.setattr(bundle.Selection, 'write', lambda *_: (_ for _ in ()).throw(OSError('failed copy')))
    with pytest.raises(OSError, match='failed copy'):
        proof.preserve(campaign.plan, original_run, state, result)
    original_commands = (Path(state['evidence_source']['path']) / 'agent-commands.log').read_bytes()
    previous = original_run
    for _ in range(5):
        run = campaign.namespace / uuid.uuid4().hex
        run.mkdir(mode=0o700)
        with campaign.runs.session():
            bundle.retention.retain(run)
        state['recovery_run'] = str(previous)
        proof.carry(campaign.plan, run, state)
        assert Path(state['evidence_source']['path']).parent.parent == run
        assert not (run / 'agent-result.json').exists()
        previous = run
    assert not original_run.exists()
    monkeypatch.setattr(bundle.Selection, 'write', original_write)
    accepted = proof.preserve(campaign.plan, run, state, result)
    capsule = Path(accepted['tasks']['first']['result']).parent
    assert bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(), accepted['bundle'],
        member=str(capsule / 'agent-commands.log')) == original_commands


def test_changed_pending_source_refuses_during_fresh_run_carry(campaign, monkeypatch):
    original_run, state, result, _ = campaign.accepted('first')
    state['pending_completion'] = result
    monkeypatch.setattr(bundle.Selection, 'write', lambda *_: (_ for _ in ()).throw(OSError('failed copy')))
    with pytest.raises(OSError):
        proof.preserve(campaign.plan, original_run, state, result)
    (Path(state['evidence_source']['path']) / 'agent-commands.log').write_text('changed source')
    run = campaign.namespace / uuid.uuid4().hex
    run.mkdir(mode=0o700)
    with campaign.runs.session():
        bundle.retention.retain(run)
    state['recovery_run'] = str(original_run)
    with pytest.raises(ValueError, match='retained session source changed'):
        proof.carry(campaign.plan, run, state)
    assert not proof.locator(campaign.plan).exists()


def test_verified_published_git_retry_needs_no_raw_source_copy(campaign):
    original_run, state, result, _ = campaign.accepted('first')
    accepted = proof.preserve(campaign.plan, original_run, state, result)
    state['pending_completion'] = result
    for _ in range(5):
        run = campaign.namespace / uuid.uuid4().hex
        run.mkdir(mode=0o700)
        with campaign.runs.session():
            bundle.retention.retain(run)
        proof.carry(campaign.plan, run, state)
        assert not (run / 'accepted-source').exists()
    assert not original_run.exists()
    assert proof.preserve(campaign.plan, run, state, result) == accepted


def test_foreign_index_change_blocks_committed_recovery_and_preserves_payloads(campaign, monkeypatch):
    run, state, result, _ = campaign.accepted('first')
    old = proof.preserve(campaign.plan, run, state, result)
    run, state, result, _ = campaign.accepted('second')
    original = proof._atomic
    monkeypatch.setattr(proof, '_atomic', lambda *_: (_ for _ in ()).throw(OSError('interrupted')))
    with pytest.raises(OSError):
        proof.preserve(campaign.plan, run, state, result)
    monkeypatch.setattr(proof, '_atomic', original)
    path = proof.locator(campaign.plan)
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(ValueError, match='index changed during publication'):
        proof.recover(campaign.plan)
    assert Path(old['bundle']).exists()


def test_changed_publication_owner_refuses_before_index_replacement(campaign, monkeypatch):
    run, state, result, _ = campaign.accepted('first')
    old = proof.preserve(campaign.plan, run, state, result)
    before = proof.locator(campaign.plan).read_bytes()
    run, state, result, _ = campaign.accepted('second')
    original = proof._atomic
    monkeypatch.setattr(proof, '_atomic', lambda *_: (_ for _ in ()).throw(OSError('interrupted')))
    with pytest.raises(OSError):
        proof.preserve(campaign.plan, run, state, result)
    monkeypatch.setattr(proof, '_atomic', original)
    journal = Path(old['bundle']).parent.parent / 'retention/current.json'
    substituted = json.loads(journal.read_bytes())
    substituted['run'] = uuid.uuid4().hex
    journal.write_text(json.dumps(substituted))
    with pytest.raises(ValueError, match='publication owner changed'):
        proof.recover(campaign.plan)
    assert proof.locator(campaign.plan).read_bytes() == before
    assert Path(old['bundle']).exists()


def test_queue_rewrite_changes_only_proven_selected_estimate_destinations(campaign):
    run, state, result, report = campaign.accepted('first')
    queue = campaign.plan.root / campaign.plan.queue
    relative = os.path.relpath(report / 'result.md', queue.parent)
    before = ('| [x] | earlier | unchanged | Baseline | old scope | [old](missing.md) |\n'
              '| [x] | first | selected task | earlier | exact scope | 3 min; [passed](' + relative + ') |\n')
    queue.write_text(before)
    accepted = proof.preserve(campaign.plan, run, state, result)
    assert proof.rewrite_references(campaign.plan, state, accepted)
    expected = before.replace(relative, os.path.relpath(proof.locator(campaign.plan), queue.parent))
    assert queue.read_text() == expected
    assert not proof.rewrite_references(campaign.plan, state, accepted)
    queue.write_text(before.replace(relative, relative + '.missing'))
    with pytest.raises(ValueError, match='no exact preserved proof'):
        proof.rewrite_references(campaign.plan, state, accepted)


def test_queue_rewrite_retains_verified_completed_proof_and_leaves_unfinished_or_unproven_links(campaign):
    run, state, result, report = campaign.accepted('first')
    queue = campaign.plan.root / campaign.plan.queue
    relative = os.path.relpath(report / 'result.md', queue.parent)
    directory = os.path.relpath(report, queue.parent)
    missing = '../output/test-runs/host/reports/expired/report.md'
    before = ('| [x] | earlier | old task | Baseline | old scope | [retained](' + relative + ') |\n'
              '| [x] | directory | old report tree | earlier | whole historical report | [directory](' + directory + ') |\n'
              '| [x] | lost | lost task | earlier | fixed scope | [unavailable](' + missing + ') |\n'
              '| [x] | first | selected task | earlier | exact scope | [passed](' + relative + ') |\n'
              '| [ ] | suspended | unfinished task | first | suspended scope | [own proof](' + relative + ') |\n')
    queue.write_text(before)
    state['queue_before'] = {'earlier': True, 'directory': True, 'lost': True,
                             'first': False, 'suspended': False}
    accepted = proof.preserve(campaign.plan, run, state, result)
    assert proof.rewrite_references(campaign.plan, state, accepted)
    destination = os.path.relpath(proof.locator(campaign.plan), queue.parent)
    expected = before.replace('[retained](' + relative + ')', '[retained](' + destination + ')')
    expected = expected.replace('[passed](' + relative + ')', '[passed](' + destination + ')')
    assert queue.read_text() == expected
    assert '[unavailable](' + missing + ')' in expected
    assert '[own proof](' + relative + ')' in expected
    assert '[directory](' + directory + ')' in expected


def test_selected_report_preserves_input_command_and_cleanup_siblings(campaign):
    run, state, result, report = campaign.accepted('first')
    for name in ('selected-inputs.json', 'commands.log', 'cleanup.json'):
        (report / name).write_text('exact ' + name)
    accepted = proof.preserve(campaign.plan, run, state, result)
    for name in ('selected-inputs.json', 'commands.log', 'cleanup.json'):
        assert bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(), accepted['bundle'],
            member=str(report / name)) == ('exact ' + name).encode()


def test_scoped_archive_refuses_foreign_plan_journal(campaign):
    run, state, result, _ = campaign.accepted('first')
    accepted = proof.preserve(campaign.plan, run, state, result)
    payload = io.BytesIO()
    with zipfile.ZipFile(accepted['bundle']) as source:
        manifest = bundle.decoded(source.read('manifest.json'))
        entry = next(item for item in manifest['files']
                     if Path(item['allocation']['path']).parent == campaign.namespace)
        entry['allocation']['journal'] = str(campaign.namespace.parent / ('f' * 64) / 'retention')
        with zipfile.ZipFile(payload, 'w', compression=zipfile.ZIP_STORED) as target:
            for item in manifest['files']:
                target.writestr(item['member'], source.read(item['member']))
            data = bundle.encoded(manifest)
            target.writestr('manifest.json', data)
            target.writestr('manifest.sha256', bundle.digest(data))
    with pytest.raises(ValueError, match='inconsistent storage provenance'):
        bundle.verify_stream(payload)


@pytest.mark.parametrize('failure', [FileNotFoundError, PermissionError])
def test_plan_catalogue_allows_absent_host_state_but_preserves_permission_refusal(campaign, monkeypatch, failure):
    campaign.accepted('first')
    proof._parent(campaign.plan, create=True)
    original = bundle.storage.directory
    def directory(kind, **kwargs):
        if kind == 'state':
            raise failure('host state unavailable')
        return original(kind, **kwargs)
    monkeypatch.setattr(bundle.storage, 'directory', directory)
    selected = bundle.Selection(campaign.plan.root, os.geteuid(), os.getegid(), [], [], [],
                                plan_namespace=plan_namespace(campaign.plan.path))
    if failure is PermissionError:
        with pytest.raises(PermissionError):
            selected.catalogue()
    else:
        assert (campaign.namespace / 'retention', os.geteuid(), os.getegid()) in selected.catalogue()


@pytest.mark.parametrize('namespace', [None, 'a' * 64])
def test_privileged_reader_resolves_publication_as_authenticated_caller(tmp_path, monkeypatch, namespace):
    # Simulate root/caller transitions without changing real process credentials.
    current = [0, 0]
    caller = (1234, 1234)
    @contextmanager
    def identity(uid, gid):
        previous = current[:]
        current[:] = [uid, gid]
        try:
            yield
        finally:
            current[:] = previous
    monkeypatch.setattr(bundle, 'identity', identity)
    monkeypatch.setattr(bundle, 'os', SimpleNamespace(**(vars(os) | {
        'geteuid': lambda: current[0], 'getegid': lambda: current[1]})))
    def directory(kind, **kwargs):
        assert tuple(current) == caller
        return tmp_path / 'host' / kind
    monkeypatch.setattr(bundle.storage, 'directory', directory)
    selected = bundle.Selection(tmp_path, *caller, [], [], [], plan_namespace=namespace)
    expected = (tmp_path / 'host' / 'exports' if namespace is None else
                tmp_path / 'host' / 'plans' / namespace / 'evidence')
    assert selected.publication_parent() == expected
    assert current == [0, 0]
    with identity(*caller):
        assert selected.publication_parent() == expected
        assert tuple(current) == caller
    assert current == [0, 0]
