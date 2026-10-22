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
import evidence_identity as identities
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


@pytest.mark.parametrize('status', ['continue', 'blocked', 'task_complete'])
def test_closed_turns_retain_exact_response_commands_and_scope_after_restarts(campaign, status):
    run, state, result, _ = campaign.accepted('consumer')
    from detached_launcher import finish_nested
    result['status'] = status
    result['checks'][0]['result'] = 'failed'
    (run / 'agent-result.json').write_bytes(bundle.encoded(result))
    finish_nested(campaign.plan.root, run)
    original = copy.deepcopy(state)
    first = proof.retain_turn(campaign.plan, run, state, result)
    expected = {name: (first / name).read_bytes() for name in proof.SOURCE_FILES}
    # A controller checkpoint update does not allocate a second terminal turn.
    (run / 'checkpoint.json').write_bytes(bundle.encoded(state))
    assert proof.retain_turn(campaign.plan, run, state, result) == first
    assert len(state['evidence_turns']) == 1
    for _ in range(5):
        run = campaign.namespace / uuid.uuid4().hex
        run.mkdir(mode=0o700)
        with campaign.runs.session():
            bundle.retention.retain(run)
        state = json.loads(json.dumps(state))
        proof.carry(campaign.plan, run, state)
        carried = Path(state['evidence_turns'][0])
        assert {name: (carried / name).read_bytes() for name in expected} == expected
        assert json.loads((carried / 'agent-result.json').read_bytes()) == result
        assert state['task'] == original['task']
        assert state['task_sessions'] == original['task_sessions']
    assert not first.exists()
    assert proof.recover(campaign.plan)['tasks'] == {}


@pytest.mark.parametrize('terminal', ['malformed', 'provider', 'missing'])
def test_rejected_and_missing_responses_preserve_truthful_terminal_bytes(campaign, terminal):
    run, state, _, _ = campaign.accepted('consumer')
    from detached_launcher import finish_nested
    (run / 'agent-result.json').unlink()
    if terminal == 'malformed':
        (run / 'agent-result.json').write_bytes(b'{not valid JSON')
    elif terminal == 'provider':
        (run / 'agent-error.json').write_bytes(b'{"kind":"capacity","retry":false}')
    finish_nested(campaign.plan.root, run)
    target = proof.retain_turn(campaign.plan, run, state)
    metadata, contents = proof._turn(target, 'consumer')
    if terminal == 'malformed':
        assert contents['agent-result.json'] == b'{not valid JSON'
    elif terminal == 'provider':
        assert contents['agent-error.json'] == b'{"kind":"capacity","retry":false}'
    else:
        assert metadata['result_sha256'] is None
        assert 'agent-result.json' not in contents
    assert proof.recover(campaign.plan)['tasks'] == {}


@pytest.mark.parametrize('rewrite_manifest', [False, True])
def test_turn_capture_refuses_unfinished_cleanup_and_changed_source(campaign, rewrite_manifest):
    run, state, result, _ = campaign.accepted('consumer')
    with pytest.raises(ValueError, match='cleanup has not finished'):
        proof.retain_turn(campaign.plan, run, state, result)
    assert 'evidence_turns' not in state
    from detached_launcher import finish_nested
    finish_nested(campaign.plan.root, run)
    target = proof.retain_turn(campaign.plan, run, state, result)
    (target / 'agent-commands.log').write_text('changed original command')
    if rewrite_manifest:
        # Coordinated edits must not rewrite history under its protected,
        # content-addressed checkpoint path, even with matching member hashes.
        manifest = json.loads((target / 'turn.json').read_bytes())
        manifest['files']['agent-commands.log'] = proof._digest((target / 'agent-commands.log').read_bytes())
        (target / 'turn.json').write_bytes(bundle.encoded(manifest))
    before = copy.deepcopy(state)
    with pytest.raises(ValueError, match='retained turn changed'):
        proof.carry(campaign.plan, run, state)
    assert state == before


def test_suspended_turn_is_published_with_later_accepted_proof(campaign):
    run, state, result, _ = campaign.accepted('consumer')
    from detached_launcher import finish_nested
    result['status'] = 'continue'
    result['checks'][0]['result'] = 'failed'
    (run / 'agent-result.json').write_bytes(bundle.encoded(result))
    finish_nested(campaign.plan.root, run)
    proof.retain_turn(campaign.plan, run, state, result)
    next_run, prerequisite, _, _ = campaign.accepted('prerequisite')
    prerequisite['suspended_tasks'] = {'consumer': state}
    proof.carry(campaign.plan, next_run, prerequisite)
    resumed = prerequisite['suspended_tasks']['consumer']
    captured = Path(resumed['evidence_turns'][0])
    proof.capture(campaign.plan, next_run, resumed)
    completed = dict(result, status='task_complete', checks=[dict(result['checks'][0], result='passed')])
    for name in proof.SOURCE_FILES:
        if name != 'agent-result.json':
            (next_run / name).write_bytes((run / name).read_bytes())
    (next_run / 'agent-result.json').write_bytes(bundle.encoded(completed))
    accepted = proof.preserve(campaign.plan, next_run, resumed, completed)
    raw = bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(), accepted['bundle'],
                         member=str(captured / 'agent-result.json'))
    assert json.loads(raw) == result
    assert json.loads(raw)['checks'][0]['result'] == 'failed'
    assert accepted['tasks']['consumer']['cleanup'] is True


@pytest.mark.parametrize('rejected', [False, True])
def test_working_reports_keep_original_provenance_without_completion_credit(campaign, rejected):
    run, state, result, report = campaign.accepted('consumer')
    from detached_launcher import finish_nested
    result['status'] = 'continue'
    (run / 'agent-result.json').write_bytes(bundle.encoded(result))
    finish_nested(campaign.plan.root, run)
    proof.retain_turn(campaign.plan, run, state, None if rejected else result)
    working = proof.recover(campaign.plan)
    assert working['tasks'] == {}
    original = bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(), working['bundle'])
    provenance = next(entry for entry in original['manifest']['files']
                      if entry['path'] == str(report / 'result.md'))
    for number in range(5):
        next_run, _, _, _ = campaign.accepted('later-' + str(number))
        proof.carry(campaign.plan, next_run, state)
    assert not report.exists() and not run.exists()
    result['status'] = 'task_complete'
    for name in proof.SOURCE_FILES:
        if name != 'agent-result.json':
            (next_run / name).write_bytes((Path(state['evidence_turns'][0]) / name).read_bytes())
    (next_run / 'agent-result.json').write_bytes(bundle.encoded(result))
    accepted = proof.preserve(campaign.plan, next_run, state, result)
    assert set(accepted['tasks']) == {'consumer'}
    retained = bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(), accepted['bundle'])
    actual = next(entry for entry in retained['manifest']['files']
                  if entry['path'] == provenance['path'])
    assert {key: value for key, value in actual.items() if key != 'member'} == {
        key: value for key, value in provenance.items() if key != 'member'}
    assert state['task_sessions'] == 1


def _runner_declaration(campaign, monkeypatch, *, status='passed', cleanup='complete',
                        workflow='regression', check='unit', target=''):
    import evidence_capture as capture
    import runner_evidence as runner
    monkeypatch.setattr(runner.regression_inputs, 'identity', lambda root: 'f' * 64)
    monkeypatch.setattr(capture, '_authenticated_caller',
                        lambda: dict(uid=os.geteuid(), gid=os.getegid()))
    import vm_config
    monkeypatch.setattr(vm_config, 'registry', lambda: {'guest': {}})
    store = bundle.retention.Store(bundle.storage.directory('state') / 'retention-host')
    with store.session():
        directory = Path(bundle.retention.allocate(tempfile.mkdtemp, prefix='onpc-plan-runner-'))
        evidence = runner.ReportEvidence(campaign.plan.root, directory, store=store, workflow=workflow)
        payload = directory / 'report.json'
        payload.write_bytes(bundle.encoded(dict(original_status=status, scope=['exact-case'])))
        payload.chmod(0o600)
        published = evidence.finalize(categories=[dict(name='unit', selected_ids=['exact-case'])],
            status=status, cleanup=cleanup, members=[dict(path=str(payload), role='result')],
            sources_sha256='f' * 64, inputs=dict(selector=['unit', 'exact-case']),
            check=check, target=target)
    record = published['records'][-1]
    member = next(item for item in record['members'] if item['original_path'] == str(payload))
    reference = next(item for item in published['references'] if item['member_id'] == member['member_id'])
    consumer = next(item for item in published['consumers'] if item['expected_context'] == record['context'])
    return dict(schema='onpc-plan-evidence', version=1, reference=reference,
                consumer=consumer, record=record), directory


def test_ordinary_consumer_authenticates_exact_runner_closure_after_source_rotation(campaign, monkeypatch):
    declaration, original = _runner_declaration(campaign, monkeypatch)
    run, state, result, _ = campaign.accepted('consumer')
    result['checks'][0]['evidence'] = bundle.encoded(declaration).decode()
    assert proof._references(campaign.plan, result, state) == []
    before = copy.deepcopy(state)
    expected = proof.consume(campaign.plan, state, result, register=False)
    assert state == before
    assert proof.consume(campaign.plan, state, result) == expected
    for _ in range(4):
        _runner_declaration(campaign, monkeypatch)
    assert not original.exists()
    assert proof.consume(campaign.plan, state, result) == expected
    (run / 'agent-result.json').write_bytes(bundle.encoded(result))
    accepted = proof.preserve(campaign.plan, run, state, result)
    saved = bundle.decoded(bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(),
        accepted['bundle'], member=accepted['tasks']['consumer']['result'], count=bundle.MAX_READ))
    assert saved == result
    assert state['task']['targets'] == [] and state['task_sessions'] == 1


@pytest.mark.parametrize('defect', ['target', 'member', 'closure', 'context', 'failed', 'partial', 'claim'])
def test_ordinary_structured_consumer_refuses_mismatched_or_nonpassing_proof(campaign, monkeypatch, defect):
    declaration, _ = _runner_declaration(campaign, monkeypatch,
        status='failed' if defect == 'failed' else 'passed',
        cleanup='pending' if defect == 'partial' else 'complete')
    _, state, result, _ = campaign.accepted('consumer')
    if defect == 'target':
        result['checks'][0]['target'] = 'another-target'
    elif defect == 'member':
        declaration['reference']['member_id'] = 'a' * 64
    elif defect == 'closure':
        declaration['reference']['closure_sha256'] = 'a' * 64
    elif defect == 'context':
        declaration['consumer']['expected_context']['sources_sha256'] = 'b' * 64
    result['checks'][0]['evidence'] = bundle.encoded(declaration).decode()
    if defect == 'claim':
        proof.consume(campaign.plan, state, result)
        result['checks'][0]['kind'] = 'review'
    before = copy.deepcopy(state)
    with pytest.raises(ValueError):
        proof.consume(campaign.plan, state, result)
    assert state == before


def test_structured_handoff_never_downgrades_to_legacy_prose(campaign):
    _, state, result, _ = campaign.accepted('consumer')
    result['checks'][0]['evidence'] = '{"schema":"onpc-plan-evidence","version":2}'
    with pytest.raises(ValueError, match='unsupported structured handoff'):
        proof._references(campaign.plan, result, state)


@pytest.mark.parametrize('workflow, selector, target, accepted', [
    ('regression', 'unit', '', False),
    ('regression', 'system', 'guest', False),
    ('system', 'system', '', False),
    ('system', 'unit', 'guest', False),
    ('system', 'system', 'guest', True),
    ('e2e', 'worker', 'guest', False),
    ('e2e', 'unit', 'guest', False),
    ('e2e', 'invocation', 'guest', True),
])
def test_installed_acceptance_requires_owning_installed_terminal_controller(
        campaign, monkeypatch, workflow, selector, target, accepted):
    declaration, _ = _runner_declaration(campaign, monkeypatch,
        workflow=workflow, check=selector, target=target)
    _, state, result, _ = campaign.accepted('consumer')
    state['task'].update(acceptance='installed', targets=['guest'])
    result['checks'][0].update(kind='installed', target=target,
                              evidence=bundle.encoded(declaration).decode())
    if accepted:
        assert proof.consume(campaign.plan, state, result)
    else:
        with pytest.raises(identities.EvidenceContextError, match='scope or verdict mismatch'):
            proof.consume(campaign.plan, state, result)
        assert 'evidence_consumers' not in state


def test_command_log_with_quoted_key_fixture_survives_preservation_and_recovery(campaign):
    run, state, result, _ = campaign.accepted('first')
    commands = (b"source read: b'-----BEGIN OPENSSH "
                + b"PRIVATE KEY-----\\nsecret'})\n")
    (run / 'agent-commands.log').write_bytes(commands)
    accepted = proof.preserve(campaign.plan, run, state, result)
    assert proof.recover(campaign.plan) == accepted
    capsule = Path(accepted['tasks']['first']['result']).parent
    assert bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(), accepted['bundle'],
        member=str(capsule / 'agent-commands.log')) == commands
    assert (run / 'agent-commands.log').read_bytes() == commands


def test_startup_verifies_cumulative_archive_once_per_recovery(campaign, monkeypatch):
    for task in ('first', 'second', 'third'):
        run, state, result, _ = campaign.accepted(task)
        retained = proof.preserve(campaign.plan, run, state, result)
    verify = bundle.verify_stream
    checksum = bundle.file_digest
    verifications, checksums = [], []

    def counted_verify(stream):
        verifications.append(stream)
        return verify(stream)

    def counted_checksum(fd, size):
        checksums.append(size)
        return checksum(fd, size)

    monkeypatch.setattr(bundle, 'verify_stream', counted_verify)
    monkeypatch.setattr(bundle, 'file_digest', counted_checksum)
    for attempt in (1, 2):
        assert proof.recover(campaign.plan) == retained
        assert len(verifications) == len(checksums) == attempt
        assert checksums[-1] == Path(retained['bundle']).stat().st_size


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


@pytest.mark.parametrize('binding, expected', [
    (None, ['required']),
    ('extra', ['required', 'extra']),
    (dict(concurrency=2, vms=['extra', 'required', 'third']),
     ['required', 'extra', 'third']),
])
def test_publication_targets_include_only_retained_selection(campaign, binding, expected):
    run, state, _, _ = campaign.accepted('first')
    state['task']['targets'] = ['required']
    assert proof._targets(run, state) == ['required']  # Older retained runs.
    (run / 'vm.json').write_bytes(bundle.encoded(dict(vm=binding)))
    assert proof._targets(run, state) == expected
    assert state['task']['targets'] == ['required']


@pytest.mark.parametrize('saved', [
    [], {}, dict(vm={}, extra=True), dict(vm=''), dict(vm=[]),
    dict(vm=dict(concurrency=True, vms=['extra'])),
    dict(vm=dict(concurrency=0, vms=['extra'])),
    dict(vm=dict(concurrency=2, vms=[])),
    dict(vm=dict(concurrency=2, vms=['extra', 'extra'])),
    dict(vm=dict(concurrency=2, vms=['extra', {}])),
])
def test_invalid_retained_selection_refuses_without_downgrading_scope(campaign, saved):
    run, state, _, _ = campaign.accepted('first')
    (run / 'vm.json').write_bytes(bundle.encoded(saved))
    with pytest.raises(ValueError, match='invalid retained VM selection'):
        proof._targets(run, state)


@pytest.mark.parametrize('task_targets', [[], ['linux-a']])
def test_selected_vm_supporting_proof_publishes_through_real_bundle_reader(
        campaign, monkeypatch, task_targets):
    from contextlib import nullcontext
    import vm_config

    run, state, result, _ = campaign.accepted('first')
    state['task']['targets'] = task_targets
    (run / 'vm.json').write_bytes(bundle.encoded(dict(vm=dict(
        concurrency=2, vms=['linux-b', 'linux-a', 'linux-c']))))
    uid, gid = os.geteuid(), os.getegid()
    monkeypatch.setattr(vm_config, 'registry', lambda: dict.fromkeys(
        ['linux-a', 'linux-b', 'linux-c', 'unselected']))
    # Exercise both target journal branches with real private files and locks,
    # while keeping the test unprivileged and entirely within its own checkout.
    target_sources = []
    for journal_name in ('retention-linux-b', f'retention-{uid}-linux-c'):
        store = bundle.retention.Store(bundle.storage.directory('state') / journal_name)
        with store.session():
            report = Path(bundle.retention.allocate(tempfile.mkdtemp,
                prefix='onpc-selected-vm-', dir=bundle.storage.directory('allocations')))
            (report / 'result.json').write_text(journal_name)
        target_sources.append(report / 'result.json')
    result['checks'][0]['evidence'] += ' ' + ' '.join(map(str, target_sources))
    (run / 'agent-result.json').write_bytes(bundle.encoded(result))
    monkeypatch.setattr(proof, 'os', SimpleNamespace(**(vars(os) | {'geteuid': lambda: uid or 1000})))
    monkeypatch.setattr(bundle, 'os', SimpleNamespace(**(vars(os) | {'geteuid': lambda: 0})))
    monkeypatch.setattr(bundle, 'identity', lambda *_: nullcontext())
    commands, published = [], []
    def invoke(command, **kwargs):
        commands.append(command)
        targets = [command[index + 1] for index, value in enumerate(command) if value == '--target']
        assert targets == list(dict.fromkeys([*task_targets, 'linux-b', 'linux-a', 'linux-c']))
        assert 'unselected' not in targets
        options = {flag: [command[index + 1] for index, value in enumerate(command) if value == flag]
                   for flag in ('--source', '--bundle', '--reference')}
        with bundle.Selection(campaign.plan.root, uid, gid, targets,
                options['--source'], options['--bundle'],
                plan_namespace=plan_namespace(campaign.plan.path),
                references=options['--reference']) as selected:
            assert all(str(path) in selected.files for path in target_sources)
            if command[3] == 'bundle-plan':
                value = dict(selection_sha256=selected.selection_sha256)
            else:
                value = bundle.export(selected, expected=command[command.index('--expect') + 1],
                                      defer_cleanup=True)
                published.append(value)
        return SimpleNamespace(returncode=0, stdout=json.dumps(value))
    monkeypatch.setattr(proof.subprocess, 'run', invoke)
    accepted = proof.preserve(campaign.plan, run, state, result)
    assert [command[3] for command in commands] == ['bundle-plan', 'bundle-export']
    assert len(published) == 1 and accepted == proof.recover(campaign.plan)
    assert state['task']['targets'] == task_targets
    for path in target_sources:
        assert bundle.inspect(campaign.plan.root, uid, gid, accepted['bundle'],
                              member=str(path)) == path.read_bytes()


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


@pytest.mark.parametrize('status,completeness,cleanup', [
    ('passed', 'complete', 'complete'),
    ('failed', 'complete', 'complete'),
    ('interrupted', 'partial', 'pending'),
])
def test_real_sealed_handoff_survives_suspension_restart_and_source_rotation(
        campaign, status, completeness, cleanup):
    import evidence_capture as capture
    import capture_publication as publication

    consumer_run, consumer, _, report = campaign.accepted('consumer')
    source_store = bundle.retention.Store(bundle.storage.directory('state') / 'retention-host')
    source_run = json.loads((source_store.path / 'current.json').read_bytes())['run']
    expected = {'result.md': (report / 'result.md').read_bytes(),
                'input.json': b'{"selection":"original inputs"}\n',
                'command.log': b'original command; exactly one invocation\n',
                'cleanup.json': json.dumps({'state': cleanup}).encode()}
    roles = dict(zip(expected, ('result', 'input', 'command', 'cleanup')))
    for name, data in expected.items():
        (report / name).write_bytes(data)
        (report / name).chmod(0o600)
    consumer_id = 'a' * 64
    with source_store.session(run=source_run):
        handle = capture.issue_session(source_store, repository=campaign.plan.root,
            workflow='suspended-plan-fixture', task='consumer', check='original-check',
            inputs_sha256=proof._digest(expected['input.json']),
            sources_sha256='d' * 64,
            consumers={consumer_id: dict(consumer_id=consumer_id, revision_sha256='b' * 64)})
        context = capture.session_context(handle)
        info = report.stat()
        allocation = dict(path=str(report), device=info.st_dev, inode=info.st_ino,
                          mode=0o700, journal=str(source_store.path), run=source_run)
        members = [dict(role=roles[name], original_path=str(report / name),
                        source_allocation=allocation, bytes=len(data),
                        sha256=proof._digest(data), required=True)
                   for name, data in expected.items()]
        cleanup_member = next(member for member in members if member['role'] == 'cleanup')
        record = identities.finalize_record(dict(schema=identities.SCHEMA, version=1,
            context=context, status=status, completeness=completeness,
            members=members, dependencies=[], cleanup=dict(state=cleanup,
                record_members=[identities.member_id(identities.record_id(context), cleanup_member)],
                scope=dict(owner=context['owner'], resources=[]))))
        identifier = capture.finalize_capture(handle, record=record, consumer_ids=[consumer_id])
        request = capture.inspect_capture(campaign.plan.root, os.geteuid(), os.getegid(), identifier)
        with bundle.Selection(campaign.plan.root, os.geteuid(), os.getegid(),
                              [], [], [], captures=[identifier]) as selected:
            receipt = bundle.export(selected, expected=selected.selection_sha256)
        acknowledgement = capture.acknowledge_capture(campaign.plan.root,
            os.geteuid(), os.getegid(), identifier, expected=request['request_sha256'],
            session_handle=handle)
    # The real task input carries the exact handoff, not a synthetic capture/carry
    # stub or a path that depends on the producer's disposable run lifetime.
    handoff = dict(request=request, delivery=acknowledgement['delivery'])
    brief = json.dumps(handoff, sort_keys=True).encode()
    (campaign.plan.root / 'docs/Brief.md').write_bytes(brief)
    proof.capture(campaign.plan, consumer_run, consumer)
    consumer.update(handoff='Resume original-check with its exact sealed attempt.',
                    commit_intent={'paths': ['owned.md'], 'commit': 'retained'},
                    protected_staged=['unrelated.md'])
    original = copy.deepcopy(consumer)
    active_run, state, _, _ = campaign.accepted('prerequisite')
    state['suspended_tasks'] = {'consumer': consumer}
    proof.carry(campaign.plan, active_run, state)
    exports = bundle.retention.Store(bundle.storage.directory('exports') / 'retention')
    for _ in range(5):
        run = campaign.namespace / uuid.uuid4().hex
        run.mkdir(mode=0o700)
        with campaign.runs.session():
            bundle.retention.retain(run)
        # Serialize and reload the checkpoint at every fresh-controller boundary.
        state = json.loads(json.dumps(state))
        proof.carry(campaign.plan, run, state)
        carried = state['suspended_tasks']['consumer']
        assert {key: value for key, value in carried.items() if key != 'evidence_inputs'} == {
            key: value for key, value in original.items() if key != 'evidence_inputs'}
        assert len(carried['evidence_inputs']) == len(original['evidence_inputs'])
        restored = (Path(carried['evidence_inputs'][-1]) / 'input-0002').read_bytes()
        assert restored == brief
        selected_handoff = json.loads(restored)
        with publication.verified_delivery(campaign.plan.root, os.geteuid(), os.getegid(),
                identifier, selected_handoff['request'], selected_handoff['delivery']) as verified:
            assert verified['manifest']['records'] == [record]
        for member in record['members']:
            assert bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(), receipt['path'],
                record_id=record['record_id'], member_id=member['member_id'],
                closure_sha256=record['closure_sha256']) == expected[Path(member['original_path']).name]
        with source_store.session():
            pass
        with exports.session():
            bundle.retention.allocate(tempfile.mkdtemp, prefix='onpc-unrelated-export-')
    assert not report.exists() and not consumer_run.exists() and not active_run.exists()
    for store in (campaign.runs, source_store, exports):
        retained = json.loads((store.path / 'current.json').read_bytes())
        assert len([*retained['history'], retained]) <= bundle.retention.RUNS_TO_KEEP


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


def test_compaction_cannot_publish_a_locator_that_drops_required_accepted_proof(campaign, monkeypatch):
    run, state, result, report = campaign.accepted('first')
    old = proof.preserve(campaign.plan, run, state, result)
    before = proof.locator(campaign.plan).read_bytes()
    run, state, result, _ = campaign.accepted('second')
    original_write, original_load = proof._write, bundle.Selection.load

    def incomplete_ledger(path, data):
        if Path(path).name == 'accepted-ledger.json':
            value = bundle.decoded(data)
            value['tasks'].pop('first')
            data = bundle.encoded(value)
        return original_write(path, data)

    def incomplete_compaction(selection):
        selection.bundles = []
        return original_load(selection)

    # Simulate a faulty compactor producing a valid new task/archive while
    # forgetting the predecessor's required closure. Verification of the new
    # archive alone is insufficient to authorize replacement of the locator.
    monkeypatch.setattr(proof, '_write', incomplete_ledger)
    monkeypatch.setattr(bundle.Selection, 'load', incomplete_compaction)
    with pytest.raises(ValueError, match='replacement omits or changes required proof'):
        proof.preserve(campaign.plan, run, state, result)
    assert proof.locator(campaign.plan).read_bytes() == before
    assert Path(old['bundle']).exists()
    assert (report / 'result.md').read_bytes() == b'Exact report for first'
    with pytest.raises(ValueError, match='replacement omits or changes required proof'):
        proof.recover(campaign.plan)
    assert proof.locator(campaign.plan).read_bytes() == before


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


def _structured_publication(campaign, *, media=None):
    """Explicit synthetic v2 records; the existing controller stays a v1 producer."""
    run, state, result, report = campaign.accepted('first')
    if media is not None:
        (report / 'required-media.bin').write_bytes(media)
    legacy = proof.preserve(campaign.plan, run, state, result)
    verified = bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(), legacy['bundle'])
    journal = campaign.namespace / 'retention'
    info, root_info = journal.stat(), campaign.plan.root.stat()
    repository = dict(root=str(campaign.plan.root), device=root_info.st_dev,
                      inode=root_info.st_ino, uid=os.geteuid())
    owner = dict(repository_sha256=identities.digest(repository),
        caller=dict(uid=os.geteuid(), gid=os.getegid()), journal=str(journal),
        identity=dict(device=info.st_dev, inode=info.st_ino, mode=info.st_mode,
                      uid=info.st_uid, gid=info.st_gid))
    context = dict(repository=repository, workflow=campaign.plan.path, owner=owner,
        run='1' * 32, task='first', check='unit', attempt='2' * 32, target='',
        inputs_sha256='3' * 64, sources_sha256='4' * 64)
    selected = legacy['tasks']['first']
    def logical(entries, context):
        members = []
        for entry in entries:
            role = ('result' if entry['path'] == selected['result'] else
                    'cleanup' if Path(entry['path']).name == 'cleanup.json' else
                    'media' if Path(entry['path']).name == 'required-media.bin' else 'input')
            members.append(dict(role=role, original_path=entry['path'],
                source_allocation=entry['allocation'], bytes=entry['bytes'],
                sha256=entry['sha256'], required=True))
        key = identities.record_id(context)
        cleanup = sorted(identities.member_id(key, member) for member in members
                         if member['role'] == 'cleanup')
        return identities.finalize_record(dict(schema='onpc-evidence-record', version=1,
            context=context, status='passed', completeness='complete', members=members,
            dependencies=[], cleanup=dict(state='complete', record_members=cleanup,
                scope=dict(owner=owner, resources=[]))))
    record = logical(verified['manifest']['files'], context)
    tasks = dict(first=dict(selected, record_refs=[dict(record_id=record['record_id'],
                                                      closure_sha256=record['closure_sha256'])]))
    ledger = dict(schema=2, plan=campaign.plan.path, generation=1,
        previous_index_sha256=proof._digest(proof.locator(campaign.plan).read_bytes()),
        tasks=tasks, records={record['record_id']: record},
        segments=[dict(id='00', record_ids=[record['record_id']])])
    source = run / 'structured'
    source.mkdir(mode=0o700)
    ledger_path = source / 'accepted-ledger.json'
    raw = bundle.encoded(ledger)
    ledger_path.write_bytes(raw)
    with campaign.runs.inspection() as retained:
        allocation = next(dict(item, journal=str(journal), run=entries['run'])
            for entries in [*retained['history'], retained]
            for item in entries['paths'] if item['path'] == str(run))
    metadata = logical([dict(path=str(ledger_path), allocation=allocation,
                            bytes=len(raw), sha256=bundle.digest(raw))],
                       dict(context, check='ledger-metadata'))
    with bundle.Selection(campaign.plan.root, os.geteuid(), os.getegid(), [], [str(source)],
            [legacy['bundle']], plan_namespace=plan_namespace(campaign.plan.path),
            logical_records=[record, metadata]) as selection:
        exported = bundle.export(selection, expected=selection.selection_sha256)
    index = dict(schema=2, plan=campaign.plan.path, generation=1,
        ledger=dict(segment_id='00', original_path=str(ledger_path)),
        ledger_sha256=bundle.digest(raw), segments=[_structured_segment(campaign, exported)], tasks=tasks)
    proof.locator(campaign.plan).write_bytes(bundle.encoded(index))
    member = next(item for item in record['members'] if item['original_path'] == selected['result'])
    selector = dict(record_id=record['record_id'], member_id=member['member_id'],
                    closure_sha256=record['closure_sha256'])
    consumer = dict(schema='onpc-evidence-consumer', version=1, consumer_id='5' * 64,
        owner=owner, revision_sha256='6' * 64, role='required_evidence', expected_context=context,
        references=[dict(kind='evidence', **selector)], state='accepted')
    reference = (os.path.relpath(proof.locator(campaign.plan),
                                (campaign.plan.root / campaign.plan.path).parent)
        + '#onpc-evidence-v1:' + ':'.join(selector[key]
            for key in ('record_id', 'member_id', 'closure_sha256')))
    return SimpleNamespace(index=index, record=record, consumer=consumer, reference=reference,
        scope=proof.reference_scope(campaign.plan, document=campaign.plan.path), result=result)


def _structured_segment(campaign, exported):
    parent = proof._parent(campaign.plan)
    with bundle.retention.Store(parent / 'retention').inspection() as state:
        entries = [*state['history'], state]
        number, allocation = next((number, allocation)
            for number, allocation in bundle.retention.latest_allocations(entries)
            if allocation['path'] == str(Path(exported['path']).parent))
        allocation = dict(allocation, journal=str(parent / 'retention'), run=entries[number]['run'])
    return dict(id='00', bundle=allocation['path'], sha256=exported['sha256'],
        selection_sha256=exported['selection_sha256'], allocation=allocation)


def test_schema2_exact_reference_survives_physical_generation_rotation(campaign):
    selected = _structured_publication(campaign)
    original = selected.index['segments'][0]['bundle']
    for _ in range(4):
        with bundle.Selection(campaign.plan.root, os.geteuid(), os.getegid(), [], [],
                [str(Path(selected.index['segments'][0]['bundle']) / 'evidence.zip')],
                plan_namespace=plan_namespace(campaign.plan.path)) as selection:
            exported = bundle.export(selection, expected=selection.selection_sha256)
        selected.index['segments'] = [_structured_segment(campaign, exported)]
        proof.locator(campaign.plan).write_bytes(bundle.encoded(selected.index))
        resolved = proof.resolve_reference(selected.reference, consumer=selected.consumer,
                                           read_scope=selected.scope)
        assert resolved['record'] == selected.record
        assert bundle.decoded(resolved['data']) == selected.result
    assert not Path(original).exists()
    assert proof.recover(campaign.plan) == selected.index


@pytest.mark.parametrize('defect', ['member', 'context', 'checkout', 'ledger', 'task', 'segment'])
def test_schema2_refuses_existing_wrong_member_context_or_changed_closure(campaign, defect):
    selected = _structured_publication(campaign)
    consumer = copy.deepcopy(selected.consumer)
    reference = selected.reference
    if defect == 'member':
        other = next(item for item in selected.record['members']
                     if item['member_id'] != consumer['references'][0]['member_id'])
        reference = reference.replace(consumer['references'][0]['member_id'], other['member_id'])
    elif defect == 'context':
        consumer['expected_context']['target'] = 'other-target'
    elif defect == 'checkout':
        # The archived owner is otherwise valid; only the live checkout inode changes.
        consumer['expected_context']['repository']['inode'] += 1
    elif defect == 'ledger':
        selected.index['ledger_sha256'] = 'a' * 64
    elif defect == 'task':
        selected.index['tasks']['first']['attempt'] = 'different-existing-attempt'
    else:
        selected.index['segments'][0]['selection_sha256'] = 'b' * 64
    proof.locator(campaign.plan).write_bytes(bundle.encoded(selected.index))
    with pytest.raises(ValueError):
        proof.resolve_reference(reference, consumer=consumer, read_scope=selected.scope)


def test_schema1_locator_stays_readable_but_refuses_exact_reference(campaign):
    run, state, result, _ = campaign.accepted('first')
    accepted = proof.preserve(campaign.plan, run, state, result)
    assert proof.recover(campaign.plan) == accepted
    scope = proof.reference_scope(campaign.plan, document=campaign.plan.path)
    with pytest.raises(ValueError, match='legacy locator'):
        with scope(proof.locator(campaign.plan), record_id='a' * 64):
            pytest.fail('legacy navigation supplied exact acceptance')


def test_exact_large_member_resolution_keeps_metadata_and_bounded_slice(campaign):
    media = b'm' * (bundle.MAX_READ + 1)
    selected = _structured_publication(campaign, media=media)
    member = next(item for item in selected.record['members'] if item['role'] == 'media')
    original = selected.consumer['references'][0]['member_id']
    selected.consumer['references'][0]['member_id'] = member['member_id']
    reference = selected.reference.replace(original, member['member_id'])
    result = proof.resolve_reference(reference, consumer=selected.consumer, read_scope=selected.scope)
    assert result['member'] == member
    assert result['data'] == media[:bundle.MAX_READ]
    assert result['data_complete'] is False
    assert result['closure'][selected.record['record_id']] == selected.record


def test_structured_helper_selection_refuses_unregistered_consumer(campaign):
    selected = _structured_publication(campaign)
    with pytest.raises(identities.EvidenceContextError, match='owner-registered consumer'):
        with bundle.Selection(campaign.plan.root, os.geteuid(), os.getegid(), [], [], [],
                plan_namespace=plan_namespace(campaign.plan.path),
                record_references=[selected.reference], consumer=selected.consumer):
            pytest.fail('caller JSON supplied consumer authority')
