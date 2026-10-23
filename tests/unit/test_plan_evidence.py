"""Accepted proof survives ordinary bounded rotation without a new archive format."""
import copy
import fcntl
import json
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from urllib.parse import quote
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

    def accepted(task, *, earlier_rows='', later_rows='', queue_text=None):
        run = namespace / uuid.uuid4().hex
        run.mkdir(mode=0o700)
        with runs.session():
            bundle.retention.retain(run)
        with reports.session():
            report = Path(bundle.retention.allocate(tempfile.mkdtemp,
                prefix='onpc-report-', dir=bundle.storage.directory('reports')))
            (report / 'result.md').write_text('Exact report for ' + task)
        (docs / 'Queue.md').write_text(queue_text(report) if queue_text else
            earlier_rows + '| [x] | ' + task + ' | task | Baseline | scope | 1 min |\n' + later_rows)
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


def test_publication_survives_worktree_propagation_and_live_control_writes(
        campaign, tmp_path_factory, monkeypatch):
    import subprocess
    import launcher_worktrees
    from detached_launcher import atomic

    root = campaign.plan.root
    private = tmp_path_factory.mktemp('publication-worktrees')
    def git(checkout, *args, check=True):
        return subprocess.run(['git', *args], cwd=checkout, capture_output=True,
            text=True, check=check, timeout=10, env=dict(os.environ, LC_ALL='C'))

    (root / '.gitignore').write_text('output/\n')
    (root / 'config').mkdir()
    (root / 'config/worktree.json').write_text(json.dumps(dict(worktrees=['main', 'worktree'])))
    (root / 'shared.py').write_text('before merge\n')
    (root / 'active.py').write_text('before task\n')
    git(root, 'init', '-qb', 'main')
    git(root, 'config', 'user.name', 'Publication test')
    git(root, 'config', 'user.email', 'publication@example.invalid')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'baseline')
    remote, other = private / 'remote.git', private / 'worktree'
    git(root, 'init', '--bare', '-q', str(remote))
    git(root, 'remote', 'add', 'origin', str(remote))
    git(root, 'push', '-qu', 'origin', 'main')
    git(root, 'worktree', 'add', '-qb', 'worktree', str(other))
    (other / 'shared.py').write_text('merged from other launcher\n')
    git(other, 'add', 'shared.py')
    git(other, 'commit', '-qm', 'other task')
    git(other, 'push', '-qu', 'origin', 'worktree')
    commit = git(other, 'rev-parse', 'HEAD').stdout.strip()
    propagation_run = private / 'propagation'
    propagation_run.mkdir(mode=0o700)

    run, state, result, report = campaign.accepted('current')
    (root / 'active.py').write_text('current launcher active work\n')
    write = bundle.Selection.write
    propagated = {}
    def merge_during_copy(selection, destination):
        # Reproduce an observer's atomic control update after inventory while
        # another launcher's real stash/merge/restore/push reaches this checkout.
        atomic(run / 'chat-inbox.json', {'messages': ['continue']})
        launcher_worktrees.propagate(other, propagation_run, propagated, commit,
            git=git, resolve=lambda *_: pytest.fail('nonconflicting merge needed resolution'))
        return write(selection, destination)

    monkeypatch.setattr(bundle.Selection, 'write', merge_during_copy)
    accepted = proof.preserve(campaign.plan, run, state, result)
    assert git(root, 'rev-parse', 'HEAD').stdout.strip() == commit
    assert (root / 'shared.py').read_text() == 'merged from other launcher\n'
    assert (root / 'active.py').read_text() == 'current launcher active work\n'
    assert not git(root, 'stash', 'list').stdout
    assert propagated['worktree_propagation']['targets'][0]['phase'] == 'done'
    def read(path):
        return bundle.inspect(root, os.geteuid(), os.getegid(), accepted['bundle'], member=str(path))
    assert json.loads(read(accepted['tasks']['current']['result'])) == result
    assert read(report / 'result.md') == b'Exact report for current'
    assert read(Path(accepted['tasks']['current']['result']).parent / 'prompt.txt') == b'Exact prompt for current'


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


@pytest.mark.parametrize('scope', ['sessions-host', 'sessions'])
def test_prerequisite_turn_preserves_finished_runner_output_after_rotation(campaign, scope):
    from detached_launcher import finish_nested

    run, state, result, _ = campaign.accepted('consumer')
    parent = bundle.storage.directory(scope)
    sessions = bundle.retention.Store(parent / 'retention')
    session = parent / uuid.uuid4().hex
    with sessions.session():
        session.mkdir(mode=0o700)
        bundle.retention.retain(session)
        (session / 'owner').touch(mode=0o600)
        (session / 'output').write_bytes(b'publication failed; no acceptance\n')
    result.update(status='prerequisite_required')
    result['checks'] = [dict(kind='host', target='', result='not_run',
                            evidence=str(session / 'output'))]
    (run / 'agent-result.json').write_bytes(bundle.encoded(result))
    finish_nested(campaign.plan.root, run)
    proof.retain_turn(campaign.plan, run, state, result)
    for _ in range(4):
        with sessions.session():
            pass
    assert not session.exists()
    # Re-publish the original reference from verified archived proof only.
    later, _, _, _ = campaign.accepted('later')
    proof.carry(campaign.plan, later, state)
    for name in proof.SOURCE_FILES:
        (later / name).write_bytes((run / name).read_bytes())
    (later / 'agent-commands.log').write_text('later continuation')
    proof.retain_turn(campaign.plan, later, state, result)
    saved = proof.recover(campaign.plan)
    assert saved['tasks'] == {}
    assert bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(), saved['bundle'],
                          member=str(session / 'output')) == b'publication failed; no acceptance\n'


@pytest.mark.parametrize('defect', ['active', 'unregistered', 'owner-link', 'owner-replaced'])
def test_runner_output_requires_registered_idle_unchanged_owner(campaign, defect):
    parent = bundle.storage.directory('sessions-host')
    sessions = bundle.retention.Store(parent / 'retention')
    session = parent / uuid.uuid4().hex
    with sessions.session():
        session.mkdir(mode=0o700)
        if defect != 'unregistered':
            bundle.retention.retain(session)
        (session / 'owner').touch(mode=0o600)
        (session / 'output').write_bytes(b'exact terminal output')
    if defect == 'owner-link':
        (session / 'owner').unlink()
        (session / 'owner').symlink_to(session / 'output')
    with (session / 'owner').open('rb') as owner:
        if defect == 'active':
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        selection = bundle.Selection(campaign.plan.root, os.geteuid(), os.getegid(), [],
                                     [str(session / 'output')], [])
        expected = {'active': 'session is active', 'unregistered': 'one recorded allocation',
                    'owner-replaced': 'changed'}
        with pytest.raises((ValueError, OSError)) as failure:
            with selection:
                assert defect == 'owner-replaced'
                (session / 'owner').rename(session / 'old-owner')
                (session / 'owner').touch(mode=0o600)
                bundle.export(selection, expected=selection.selection_sha256)
        assert not isinstance(failure.value, proof.EvidenceUnavailable)
        if defect in expected:
            assert expected[defect] in str(failure.value)
    assert (session / 'output').read_bytes() == b'exact terminal output'


def test_target_session_output_keeps_target_scope_live_and_archived(campaign, monkeypatch):
    # Registry/privilege checks have their own coverage. This host-safe history
    # exercises real journal discovery and provenance without a VM or helper.
    monkeypatch.setattr(bundle.Selection, 'validate_targets', lambda self: None)
    parent = bundle.storage.directory('sessions') / 'vm-guest'
    bundle.retention.ensure_directory(parent)
    sessions = bundle.retention.Store(parent / 'retention')
    with sessions.session():
        session = parent / uuid.uuid4().hex
        session.mkdir(mode=0o700)
        bundle.retention.retain(session)
        (session / 'owner').touch(mode=0o600)
        (session / 'output').write_bytes(b'exact target failure')
    source = str(session / 'output')
    with bundle.Selection(campaign.plan.root, os.geteuid(), os.getegid(), ['guest'],
                          [source], []) as selected:
        archive = bundle.export(selected, expected=selected.selection_sha256)['path']
    with pytest.raises(ValueError, match='one recorded allocation'):
        with bundle.Selection(campaign.plan.root, os.geteuid(), os.getegid(), [], [source], []):
            pytest.fail('unselected live target accepted')
    for _ in range(4):
        with sessions.session():
            pass
    assert not Path(source).exists()
    namespace = plan_namespace(campaign.plan.path)
    with bundle.Selection(campaign.plan.root, os.geteuid(), os.getegid(), ['guest'], [],
                          [archive], references=[source], plan_namespace=namespace) as selected:
        assert selected.files[source][0]['sha256'] == bundle.digest(b'exact target failure')
    with pytest.raises(identities.EvidenceContextError, match='target does not match'):
        with bundle.Selection(campaign.plan.root, os.geteuid(), os.getegid(), [], [],
                              [archive], references=[source], plan_namespace=namespace):
            pytest.fail('unselected archived target accepted')


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


@pytest.mark.parametrize('mode', ['accepted', 'rejected', 'export', 'unregistered', 'receipt', 'raw'])
def test_legacy_runner_archive_citation_authenticates_its_publication_owner(campaign, monkeypatch, mode):
    import capture_publication
    declaration, _ = _runner_declaration(campaign, monkeypatch)
    namespace = capture_publication._namespace(dict(record=declaration['record']))
    parent = bundle.plan_parent(campaign.plan.root, namespace)
    with bundle.retention.Store(parent / 'retention').inspection() as owner:
        records = bundle.retention.latest_allocations([*owner['history'], owner])
        archive = Path(records[-1][1]['path']) / 'evidence.zip'
    if mode == 'export':
        with bundle.Selection(campaign.plan.root, os.geteuid(), os.getegid(), [], [],
                              [str(archive)]) as selected:
            archive = Path(bundle.export(selected, expected=selected.selection_sha256)['path'])
    expected = archive.read_bytes()
    receipt = (archive.parent / 'receipt.json').read_bytes()
    run, state, result, _ = campaign.accepted('consumer')
    assert namespace != plan_namespace(campaign.plan.path)
    result['checks'][0]['evidence'] += f' Supporting runner archive: `{archive}`.'
    (run / 'agent-result.json').write_bytes(bundle.encoded(result))
    from detached_launcher import finish_nested
    finish_nested(campaign.plan.root, run)
    before = copy.deepcopy(state)
    if mode == 'unregistered':
        # A correctly named copy is still not an authenticated publication.
        replacement = archive.parent.with_name('onpc-evidence-bundle-unregistered')
        archive.parent.rename(replacement)
        archive = replacement / archive.name
        result['checks'][0]['evidence'] = str(archive)
        (run / 'agent-result.json').write_bytes(bundle.encoded(result))
    elif mode == 'receipt':
        (archive.parent / 'receipt.json').write_bytes(b'{}')
    elif mode == 'raw':
        # An archive citation grants no access to raw allocations of that plan.
        raw = parent.parent / ('b' * 32)
        raw.mkdir(mode=0o700)
        with bundle.retention.Store(parent.parent / 'retention').session():
            bundle.retention.retain(raw)
        (raw / 'private.json').write_bytes(b'not selected proof')
        result['checks'][0]['evidence'] += f' `{raw / "private.json"}`'
        (run / 'agent-result.json').write_bytes(bundle.encoded(result))
    if mode in ('unregistered', 'receipt', 'raw'):
        with pytest.raises(ValueError):
            proof.retain_turn(campaign.plan, run, state)
        assert not proof.locator(campaign.plan).exists()
        return
    # Cover archive-only discovery as well as publication mixed with live proof.
    with bundle.Selection(campaign.plan.root, os.geteuid(), os.getegid(), [], [], [],
                          plan_namespace=plan_namespace(campaign.plan.path),
                          references=[str(archive)]) as selected:
        assert selected.manifest['schema'] == 1
        assert selected.files[str(archive)][0]['sha256'] == bundle.digest(expected)
    turn = proof.retain_turn(campaign.plan, run, state,
                             None if mode == 'rejected' else result)
    retained = proof.recover(campaign.plan)
    assert retained['tasks'] == {}
    assert bundle.decoded(bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(),
        retained['bundle'], member=str(turn / 'agent-result.json'))) == result
    if mode == 'accepted':
        for _ in range(3):
            with bundle.retention.Store(parent / 'retention').session():
                pass
        assert not archive.exists()
        retained = proof.preserve(campaign.plan, run, state, result)
        assert set(retained['tasks']) == {'consumer'}
    assert bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(),
        retained['bundle'], member=str(archive), count=bundle.MAX_READ) == expected
    assert bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(),
        retained['bundle'], member=str(archive.parent / 'receipt.json')) == receipt
    assert state['task'] == before['task'] and state['task_sessions'] == before['task_sessions']
    assert 'evidence_consumers' not in state  # Legacy prose registers no structured claim.


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

    # Restart carry-over, accepted Git retries and queue rewriting must use the
    # same pinned read scope as ledger verification, rather than rescan the
    # entire cumulative archive for each result or manifest lookup.
    state['pending_completion'] = result
    for attempt, operation in enumerate((
            lambda: proof.carry(campaign.plan, run, state),
            lambda: proof.preserve(campaign.plan, run, state, result),
            lambda: proof.rewrite_references(campaign.plan, state, retained)), start=3):
        operation()
        assert len(verifications) == len(checksums) == attempt


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


@pytest.mark.parametrize('reference', ['[report](<{path}>).', '`{path}`.'])
@pytest.mark.parametrize('filename', ['result.md.', 'result.md,', 'result, exact.md',
                                      'result.md?', 'result%20.md'])
def test_delimited_report_paths_preserve_literal_punctuation(campaign, reference, filename):
    run, state, result, report = campaign.accepted('first')
    source = report / filename
    (report / 'result.md').rename(source)
    result['checks'][0]['evidence'] = reference.format(
        path=quote(str(source), safe='/') if reference.startswith('[') else source)
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


@pytest.mark.parametrize('status', ['continue', 'task_complete'])
def test_control_journal_citations_do_not_become_payload_or_queue_proof(campaign, status):
    run, state, result, report = campaign.accepted('first')
    journal = bundle.plan_parent(campaign.plan.root, 'a' * 64) / 'retention' / 'capture-publication.json'
    # The journal need not exist: a navigation citation grants no read authority
    # and must not become a renewable reference or a replacement proof link.
    result['status'] = status
    result['checks'][0]['evidence'] += f' Recovery inspected `{journal}`: no pending generation.'
    queue = campaign.plan.root / campaign.plan.queue
    relative = os.path.relpath(journal, queue.parent)
    queue.write_text('| [x] | first | task | Baseline | scope | '
                     f'[report]({report / "result.md"}); [control journal]({relative}) |\n')
    (run / 'agent-result.json').write_bytes(bundle.encoded(result))
    assert proof._references(campaign.plan, result, state) == [str(report / 'result.md')]
    from detached_launcher import finish_nested
    finish_nested(campaign.plan.root, run)
    turn = proof.retain_turn(campaign.plan, run, state, result)
    retained = proof.recover(campaign.plan)
    assert set(retained['tasks']) == set()
    assert bundle.decoded(bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(),
        retained['bundle'], member=str(turn / 'agent-result.json'))) == result
    if status == 'task_complete':
        retained = proof.preserve(campaign.plan, run, state, result)
        assert proof.rewrite_references(campaign.plan, state, retained)
        assert f'[control journal]({relative})' in queue.read_text()
        assert '[report](' + os.path.relpath(proof.locator(campaign.plan), queue.parent) + ')' in queue.read_text()
    files = bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(),
                           retained['bundle'])['manifest']['files']
    assert str(journal) not in {entry['path'] for entry in files}
    assert str(report / 'result.md') in {entry['path'] for entry in files}


def test_control_journal_filename_inside_allocation_remains_exact_evidence(campaign):
    run, state, result, report = campaign.accepted('first')
    source = report / 'capture-publication.json'
    (report / 'result.md').rename(source)
    result['checks'][0]['evidence'] = str(source)
    (run / 'agent-result.json').write_bytes(bundle.encoded(result))
    assert proof._references(campaign.plan, result, state) == [str(source)]
    retained = proof.preserve(campaign.plan, run, state, result)
    assert bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(),
        retained['bundle'], member=str(source)) == b'Exact report for first'


@pytest.mark.parametrize('suffix', ['evidence/retention/capture-publication.json.extra',
                                   'evidence/other/capture-publication.json'])
def test_control_journal_lookalikes_still_refuse_unregistered_storage(campaign, suffix):
    run, state, result, _ = campaign.accepted('first')
    source = campaign.namespace / suffix
    result['checks'][0]['evidence'] = str(source)
    (run / 'agent-result.json').write_bytes(bundle.encoded(result))
    assert proof._references(campaign.plan, result, state) == [str(source)]
    with pytest.raises(ValueError, match='reference is outside checkout evidence storage'):
        proof.preserve(campaign.plan, run, state, result)
    assert not proof.locator(campaign.plan).exists()


def test_queue_prose_and_relative_links_preserve_one_exact_source(campaign):
    _, state, result, report = campaign.accepted('first')
    source = report / 'result.md'
    queue = campaign.plan.root / campaign.plan.queue
    relative = os.path.relpath(source, queue.parent)
    queue.write_text('| [x] | first | task | Baseline | scope | '
                     f'Passed: {source}. [report]({relative}). |\n')
    result['checks'][0]['evidence'] = 'See queue for retained evidence.'
    assert proof._references(campaign.plan, result, state) == [str(source)]


def test_reference_style_queue_proof_uses_selected_row_and_document_base(campaign):
    run, state, result, report = campaign.accepted('first', later_rows=
        '| [ ] | later | task | first | scope | [missing][other] |\n'
        '\n[other]: ../output/test-runs/missing.md\n')
    source = report / 'result (exact)#1.md.'
    (report / 'result.md').rename(source)
    queue = campaign.plan.root / campaign.plan.queue
    relative = os.path.relpath(source, queue.parent).replace('#', '%23')
    label = report / 'label-only.md'
    queue.write_text(f'| [x] | first | task | Baseline | scope | [{label}][proof] |\n'
                     '| [ ] | later | task | first | scope | [missing][other] |\n'
                     f'\n[proof]: <{relative}> "exact original proof"\n'
                     '[other]: ../output/test-runs/missing.md\n')
    result['checks'][0]['evidence'] = 'See the selected queue row.\n```md\n' + str(label) + '\n```'
    assert proof._references(campaign.plan, result, state) == [str(source)]
    (run / 'agent-result.json').write_text(json.dumps(result))
    accepted = proof.preserve(campaign.plan, run, state, result)
    assert bundle.inspect(campaign.plan.root, os.geteuid(), os.getegid(),
                          accepted['bundle'], member=str(source)) == b'Exact report for first'


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
    run, state, result, report = campaign.accepted('first',
        earlier_rows='| [x] | earlier | unchanged | Baseline | old scope | [old](missing.md) |\n')
    queue = campaign.plan.root / campaign.plan.queue
    relative = os.path.relpath(report / 'result.md', queue.parent)
    before = ('| [x] | earlier | unchanged | Baseline | old scope | [old](missing.md) |\n'
              '| [x] | first | selected task | earlier | exact scope | 3 min; [passed](' + relative + ') '
              '`[example](' + relative + ')` ![image](' + relative + ') '
              '[angle](<' + relative + '>) [title](' + relative + ' "title") [reference][proof] |\n'
              '\n[proof]: ' + relative + '\n')
    queue.write_text(before)
    accepted = proof.preserve(campaign.plan, run, state, result)
    assert proof.rewrite_references(campaign.plan, state, accepted)
    expected = before.replace('[passed](' + relative + ')',
                              '[passed](' + os.path.relpath(proof.locator(campaign.plan), queue.parent) + ')')
    assert queue.read_text() == expected
    assert not proof.rewrite_references(campaign.plan, state, accepted)
    queue.write_text(before.replace(relative, relative + '.missing'))
    with pytest.raises(ValueError, match='no exact preserved proof'):
        proof.rewrite_references(campaign.plan, state, accepted)


def test_queue_rewrite_retains_verified_completed_proof_and_leaves_unfinished_or_unproven_links(campaign):
    queue = campaign.plan.root / campaign.plan.queue
    missing = '../output/test-runs/host/reports/expired/report.md'
    def original_queue(report):
        relative = os.path.relpath(report / 'result.md', queue.parent)
        directory = os.path.relpath(report, queue.parent)
        return ('| [x] | earlier | old task | Baseline | old scope | [retained](' + relative + ') |\n'
                '| [x] | directory | old report tree | earlier | whole historical report | [directory](' + directory + ') |\n'
                '| [x] | lost | lost task | earlier | fixed scope | [unavailable](' + missing + ') |\n'
                '| [x] | first | selected task | earlier | exact scope | [passed](' + relative + ') |\n'
                '| [ ] | suspended | unfinished task | first | suspended scope | [own proof](' + relative + ') |\n')
    run, state, result, report = campaign.accepted('first', queue_text=original_queue)
    relative = os.path.relpath(report / 'result.md', queue.parent)
    directory = os.path.relpath(report, queue.parent)
    before = queue.read_text()
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


def _declared_document(campaign, selected, text, *, document='docs/nested/Evidence.md'):
    path = campaign.plan.root / document
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    declaration = dict(document=document, sha256=bundle.digest(path.read_bytes()),
        references=[dict(start=link.start, consumer=copy.deepcopy(selected.consumer),
            selector=copy.deepcopy(selected.consumer['references'][0]), workflow=None)
            for link in proof.references(text)])
    return path, declaration


def test_declared_nested_prose_rewrites_only_destinations_and_shared_definition(campaign):
    selected = _structured_publication(campaign)
    original = Path(next(item['original_path'] for item in selected.record['members']
                         if item['member_id'] == selected.consumer['references'][0]['member_id']))
    document = campaign.plan.root / 'docs/nested/Evidence.md'
    relative = os.path.relpath(original, document.parent)
    before = ('# Résultat\n\nAccepted **claim** [exact](<' + relative + '> "kept title").\n'
              'The [first][proof] and [second][proof] share proof.\n\n'
              '[proof]: <' + relative + '> "kept definition title"\n'
              '`$(touch sentinel)` stays authored text.\n')
    path, declaration = _declared_document(campaign, selected, before)
    # Retained proof must work after the disposable original has gone away.
    original.unlink()
    collected_path, text, claims = proof.collect_document_references(campaign.plan, declaration)
    assert collected_path == path and text == before and len(claims) == 3
    scope = proof.reference_scope(campaign.plan, document=declaration['document'])
    destination = proof.generate_reference(consumer=selected.consumer,
        selector=selected.consumer['references'][0], read_scope=scope)
    assert destination == os.path.relpath(proof.locator(campaign.plan), path.parent) + selected.reference[
        selected.reference.index('#'):]
    preview = proof.preview_document_links(campaign.plan, declaration)
    assert path.read_text() == before
    assert len(preview['edits']) == 2
    assert proof.apply_document_links(campaign.plan, preview)
    assert path.read_text() == before.replace(relative, destination)
    assert not original.exists()
    assert not (campaign.plan.root / 'sentinel').exists()


def test_declared_shared_definition_requires_every_use(campaign):
    selected = _structured_publication(campaign)
    path, declaration = _declared_document(campaign, selected,
        '[first][proof] and [second][proof].\n\n[proof]: ' + selected.reference + '\n')
    declaration['references'].pop()
    before = path.read_bytes()
    with pytest.raises(ValueError, match='shared definition has undeclared uses'):
        proof.collect_document_references(campaign.plan, declaration)
    assert path.read_bytes() == before


@pytest.mark.parametrize('changed', ['document', 'preview', 'declaration'])
def test_declared_apply_refuses_changed_document_or_preview_without_writing(campaign, changed):
    selected = _structured_publication(campaign)
    path, declaration = _declared_document(campaign, selected,
        '[proof](' + selected.reference + ')\n', document=campaign.plan.path)
    preview = proof.preview_document_links(campaign.plan, declaration)
    if changed == 'document':
        path.write_text(path.read_text() + 'Unrelated concurrent edit.\n')
    elif changed == 'preview':
        preview['edits'][0]['after'] = 'wrong-existing.md'
    else:
        preview['declaration']['references'][0]['consumer']['revision_sha256'] = 'a' * 64
    before = path.read_bytes()
    with pytest.raises(ValueError, match='document changed|preview or exact proof changed'):
        proof.apply_document_links(campaign.plan, preview)
    assert path.read_bytes() == before


@pytest.mark.parametrize('field,value', [
    ('attempt', '7' * 32), ('target', 'other-target'), ('inputs_sha256', '8' * 64),
])
def test_declared_context_refuses_same_archived_bytes_for_other_claim(campaign, field, value):
    selected = _structured_publication(campaign)
    path, declaration = _declared_document(campaign, selected, '[proof](' + selected.reference + ')\n',
                                          document=campaign.plan.path)
    before = path.read_bytes()
    # Only the consuming claim changes; the selected archive/member bytes do not.
    declaration['references'][0]['consumer']['expected_context'][field] = value
    with pytest.raises(identities.EvidenceContextError) as error:
        proof.preview_document_links(campaign.plan, declaration)
    diagnostic = error.value.reference_diagnostic
    assert diagnostic['condition'] == 'identity'
    assert diagnostic['document'] == campaign.plan.path and diagnostic['line'] == 1
    assert diagnostic['expected'] != diagnostic['actual'] and diagnostic['recovery']
    assert path.read_bytes() == before


@pytest.mark.parametrize('wrong', ['existing-member', 'generic-locator'])
def test_declared_destination_must_already_identify_selected_member(campaign, wrong):
    selected = _structured_publication(campaign)
    if wrong == 'existing-member':
        member = next(item for item in selected.record['members']
            if item['member_id'] != selected.consumer['references'][0]['member_id']
            and Path(item['original_path']).is_file())
        destination = os.path.relpath(member['original_path'],
                                      (campaign.plan.root / campaign.plan.path).parent)
    else:
        destination = selected.reference.partition('#')[0]
        assert proof.locator(campaign.plan).is_file()
    path, declaration = _declared_document(campaign, selected, '[proof](' + destination + ')\n',
                                          document=campaign.plan.path)
    before = path.read_bytes()
    with pytest.raises(ValueError, match='destination is not the selected original member'):
        proof.preview_document_links(campaign.plan, declaration)
    assert path.read_bytes() == before


def test_declared_queue_rewrite_keeps_task_state_and_protected_claims(campaign):
    selected = _structured_publication(campaign)
    member = next(item for item in selected.record['members']
                  if item['member_id'] == selected.consumer['references'][0]['member_id'])
    queue = campaign.plan.root / campaign.plan.queue
    original = os.path.relpath(member['original_path'], queue.parent)
    state = dict(task_id='first', queue_before={'earlier': True, 'suspended': False})
    frozen = copy.deepcopy(state)
    for task, completion, column, authorized in [
            ('first', '[x]', 'estimate', True), ('earlier', '[x]', 'estimate', True),
            ('suspended', '[ ]', 'estimate', False), ('first', '[x]', 'scope', False)]:
        link = '[exact](' + original + ')'
        scope, estimate = (link, '1 min') if column == 'scope' else ('fixed scope', '1 min; ' + link)
        before = f'| {completion} | {task} | fixed label | Baseline | {scope} | {estimate} |\n'
        path, declaration = _declared_document(campaign, selected, before, document=campaign.plan.queue)
        if authorized:
            preview = proof.preview_document_links(campaign.plan, declaration, state=state)
            assert proof.apply_document_links(campaign.plan, preview, state=state)
            assert path.read_text() == before.replace(original, selected.reference)
        else:
            with pytest.raises(ValueError, match='protected queue destination'):
                proof.preview_document_links(campaign.plan, declaration, state=state)
            assert path.read_text() == before
        assert state == frozen
    before = '| [x] | first | task | Baseline | scope | [exact](' + original + ') |\n'
    path, declaration = _declared_document(campaign, selected, before, document=campaign.plan.queue)
    with pytest.raises(ValueError, match='protected queue destination'):
        proof.preview_document_links(campaign.plan, declaration)
    assert path.read_text() == before
    before = ('| [x] | first | task | Baseline | scope | [exact][proof] |\n\n'
              '[proof]: ' + original + '\n')
    path, declaration = _declared_document(campaign, selected, before, document=campaign.plan.queue)
    with pytest.raises(ValueError, match='protected queue destination'):
        proof.preview_document_links(campaign.plan, declaration, state=state)
    assert path.read_text() == before
    assert state == frozen


@pytest.mark.parametrize('spelling', ['original', 'exact'])
def test_declared_original_reappearance_cannot_bypass_live_source_guards(campaign, spelling):
    selected = _structured_publication(campaign)
    original = Path(next(item['original_path'] for item in selected.record['members']
                         if item['member_id'] == selected.consumer['references'][0]['member_id']))
    destination = (selected.reference if spelling == 'exact' else
                   os.path.relpath(original, (campaign.plan.root / campaign.plan.path).parent))
    path, declaration = _declared_document(campaign, selected,
        '[proof](' + destination + ')\n', document=campaign.plan.path)
    original.unlink()
    preview = proof.preview_document_links(campaign.plan, declaration)
    original.symlink_to(proof.locator(campaign.plan))
    before = path.read_bytes()
    with pytest.raises((ValueError, OSError)):
        proof.apply_document_links(campaign.plan, preview)
    assert path.read_bytes() == before
    assert original.is_symlink()


def _policy_document(campaign, selected, text, *, role='required_evidence', document='docs/Claim.md'):
    path, declaration = _declared_document(campaign, selected, text, document=document)
    contracts = {}
    for link, claim in zip(proof.references(text), declaration['references']):
        consumer = claim['consumer']
        consumer['consumer_id'] = identities.digest(dict(document=document, start=link.start))
        consumer['revision_sha256'] = bundle.digest(proof._claim_bytes(text, link))
        consumer['role'] = role
        if role != 'required_evidence':
            target = proof.local_destination(link.destination)
            consumer['expected_context'] = None
            consumer['references'] = [dict(kind='document', destination=os.path.normpath(target.path),
                                           fragment=target.fragment or '')]
            claim['selector'] = None
        contracts[consumer['consumer_id']] = copy.deepcopy(consumer)
    return path, declaration, contracts


def _refresh_policy_document(path, declaration):
    declaration['sha256'] = bundle.digest(path.read_bytes())
    for link, claim in zip(proof.references(path.read_text()), declaration['references']):
        claim['start'] = link.start


def test_policy_binds_claim_wording_and_owner_role_even_at_unchanged_destination(campaign):
    selected = _structured_publication(campaign)
    before = '# Presentation\nUbuntu passed [proof](' + selected.reference + ').\n'
    path, declaration, contracts = _policy_document(campaign, selected, before)
    assert not any(item.blocked for item in proof.check_document_references(
        campaign.plan, declaration, contracts=contracts))
    path.write_text(before.replace('# Presentation', '# **Presentation**'))
    _refresh_policy_document(path, declaration)
    assert not any(item.blocked for item in proof.check_document_references(
        campaign.plan, declaration, contracts=contracts))
    path.write_text(before.replace('Ubuntu passed', 'Both targets passed'))
    _refresh_policy_document(path, declaration)
    decision, = proof.check_document_references(campaign.plan, declaration, contracts=contracts)
    assert decision.blocked and decision.diagnostic.condition == 'stale'
    declaration['references'][0]['consumer']['role'] = 'optional_presentation'
    decision, = proof.check_document_references(campaign.plan, declaration, contracts=contracts)
    assert decision.blocked and decision.diagnostic.condition == 'conflict'


def test_policy_historical_loss_is_nonpassing_and_exactly_revision_bound(campaign):
    selected = _structured_publication(campaign)
    target = campaign.plan.root / 'docs/Old.md'
    target.write_text('# Old\n')
    path, declaration, contracts = _policy_document(campaign, selected,
        'Historical result [record](Old.md).\n', role='historical_information')
    original, = proof.check_document_references(campaign.plan, declaration, contracts=contracts)
    target.unlink()
    decision, = proof.check_document_references(campaign.plan, declaration,
        contracts=contracts, retained=[original.binding])
    assert decision.advisory and decision.diagnostic.condition == 'missing'
    assert not hasattr(decision, 'passed')
    required, = proof.check_document_references(campaign.plan, declaration,
        contracts=contracts, retained=[original.binding], active=True)
    assert required.blocked
    path.write_text('Changed historical result [record](Old.md).\n')
    _refresh_policy_document(path, declaration)
    claim = declaration['references'][0]
    claim['consumer']['revision_sha256'] = bundle.digest(proof._claim_bytes(path.read_text(),
        next(proof.references(path.read_text()))))
    contracts[claim['consumer']['consumer_id']] = copy.deepcopy(claim['consumer'])
    changed, = proof.check_document_references(campaign.plan, declaration,
        contracts=contracts, retained=[original.binding])
    assert changed.blocked and changed.diagnostic.condition == 'missing'


def test_policy_new_optional_anchor_cannot_downgrade_required_contract(campaign):
    selected = _structured_publication(campaign)
    (campaign.plan.root / 'docs/Guide.md').write_text('# Present\n')
    path, declaration, contracts = _policy_document(campaign, selected,
        'Decoration [section](Guide.md#missing).\n', role='optional_presentation')
    optional, = proof.check_document_references(campaign.plan, declaration, contracts=contracts)
    assert optional.advisory and optional.diagnostic.condition == 'fragment'
    absent, = proof.check_document_references(campaign.plan, declaration, contracts={})
    assert absent.blocked and absent.diagnostic.condition == 'conflict'
    claim = declaration['references'][0]['consumer']
    contracts[claim['consumer_id']]['role'] = 'required_instruction'
    conflict, = proof.check_document_references(campaign.plan, declaration, contracts=contracts)
    assert conflict.blocked and conflict.diagnostic.condition == 'conflict'
    claim['role'] = 'required_instruction'
    required, = proof.check_document_references(campaign.plan, declaration, contracts=contracts)
    assert required.blocked and required.diagnostic.condition == 'fragment'


def test_equivalent_instruction_spelling_retains_claim_but_not_historical_exception(campaign):
    selected = _structured_publication(campaign)
    (campaign.plan.root / 'docs/Guide.md').write_text('# Present\n')
    path, declaration, contracts = _policy_document(campaign, selected,
        'Required [section](Guide.md#present).\n', role='required_instruction')
    original, = proof.check_document_references(campaign.plan, declaration, contracts=contracts)
    path.write_text(path.read_text().replace('(Guide.md', '(./Guide.md'))
    _refresh_policy_document(path, declaration)
    changed, = proof.check_document_references(campaign.plan, declaration,
        contracts=contracts, retained=[original.binding])
    assert not changed.blocked and changed.binding.claim_sha256 == original.binding.claim_sha256
    assert changed.binding.reference_sha256 != original.binding.reference_sha256


def test_publication_checks_authored_instructions_without_scanning_old_loss(campaign):
    master = campaign.plan.root / campaign.plan.path
    master.write_text(master.read_text() + '\nUnrelated history [old](Lost.md).\n')
    run, state, result, report = campaign.accepted('first')
    proof.publication_document_gate(campaign.plan, state)
    master.write_text(master.read_text() + '\nRequired [new](New.md).\n')
    with pytest.raises(proof.ReferenceRefused) as error:
        proof.publication_document_gate(campaign.plan, state)
    assert error.value.diagnostics[0]['condition'] == 'missing'
    assert error.value.diagnostics[0]['document'] == campaign.plan.path
    master.write_text(master.read_text().replace('(New.md)', '(./Queue.md)'))
    proof.publication_document_gate(campaign.plan, state)
    # The same historical loss becomes blocking as a current instruction.
    with pytest.raises(proof.ReferenceRefused):
        proof.preflight(campaign.plan, run, state)


def test_preflight_capacity_is_early_read_only_and_preserves_proof(campaign, monkeypatch):
    run, state, result, report = campaign.accepted('first')
    proof.preserve(campaign.plan, run, state, result)
    index = proof.locator(campaign.plan).read_bytes()
    planned = proof.preflight(campaign.plan, run, state)
    assert planned['projected_bytes'] > 0
    monkeypatch.setattr(bundle.retention, 'MAX_RETAINED_BYTES', planned['projected_bytes'])
    with pytest.raises(proof.ReferenceRefused) as error:
        proof.preflight(campaign.plan, run, state)
    assert error.value.diagnostics[0]['condition'] == 'capacity'
    assert proof.locator(campaign.plan).read_bytes() == index


def test_declared_aliases_verify_once_while_pinned_then_reverify_on_apply(campaign, monkeypatch):
    selected = _structured_publication(campaign)
    text = '[first](' + selected.reference + ') and [second](' + selected.reference + ').\n'
    path, declaration = _declared_document(campaign, selected, text, document='docs/Claim.md')
    count = []
    real = bundle.verified_record
    @contextmanager
    def counted(*args, **kwargs):
        count.append(args[0]['path'])
        with real(*args, **kwargs) as value:
            yield value
    monkeypatch.setattr(bundle, 'verified_record', counted)
    preview = proof.preview_document_links(campaign.plan, declaration)
    assert len(count) == 1
    proof.apply_document_links(campaign.plan, preview)
    assert len(count) == 2


def test_lifecycle_respects_declared_presentation_and_historical_roles(campaign):
    selected = _structured_publication(campaign)
    run, state, result, report = campaign.accepted('first')
    (campaign.plan.root / 'docs/Guide.md').write_text('# Present\n')
    _, declaration, contracts = _policy_document(campaign, selected,
        'Decoration [section](Guide.md#missing).\n', role='optional_presentation',
        document=campaign.plan.path)
    state.update(reference_documents=[declaration], reference_contracts=contracts)
    proof.preflight(campaign.plan, run, state)
    assert proof.publication_document_gate(campaign.plan, state) == []
    assert json.loads(json.dumps(state))['reference_bindings']
    _, declaration, contracts = _policy_document(campaign, selected,
        'Old result [record](Guide.md).\n', role='historical_information',
        document=campaign.plan.path)
    state.update(reference_documents=[declaration], reference_contracts=contracts,
                 reference_bindings=[], active_reference_consumers=list(contracts))
    proof.preflight(campaign.plan, run, state)
    state['active_reference_consumers'] = []  # Releasing a dependency changes relevance, not its claim.
    (campaign.plan.root / 'docs/Guide.md').unlink()
    proof.preflight(campaign.plan, run, state)
    state['active_reference_consumers'] = list(contracts)
    with pytest.raises(proof.ReferenceRefused) as error:
        proof.preflight(campaign.plan, run, state)
    assert error.value.diagnostics[0]['condition'] == 'missing'


def test_document_adapter_preserves_prior_required_role_on_downgrade(campaign):
    selected = _structured_publication(campaign)
    (campaign.plan.root / 'docs/Guide.md').write_text('# Present\n')
    _, declaration, contracts = _policy_document(campaign, selected,
        'Required [section](Guide.md#missing).\n', role='required_instruction')
    old, = proof.check_document_references(campaign.plan, declaration, contracts=contracts)
    consumer = declaration['references'][0]['consumer']
    consumer['role'] = 'optional_presentation'
    contracts[consumer['consumer_id']] = copy.deepcopy(consumer)
    changed, = proof.check_document_references(campaign.plan, declaration,
        contracts=contracts, retained=[old.binding])
    assert changed.blocked and changed.diagnostic.condition == 'conflict'


def test_document_role_cannot_hide_an_exact_evidence_selector(campaign):
    selected = _structured_publication(campaign)
    _, declaration, contracts = _policy_document(campaign, selected,
        'Decoration [proof](' + selected.reference + ').\n', role='optional_presentation')
    refused, = proof.check_document_references(campaign.plan, declaration, contracts=contracts)
    assert refused.blocked and refused.diagnostic.condition == 'identity'


def test_semantic_reader_reports_actionable_identity_without_private_claim_text(campaign, monkeypatch, capsys):
    selected = _structured_publication(campaign)
    _, declaration = _declared_document(campaign, selected,
        'Task queue: [Queue](Queue.md).\n[private claim](' + selected.reference + ')\n',
        document=campaign.plan.path)
    declaration['references'] = declaration['references'][-1:]
    declaration['references'][0]['consumer']['expected_context']['target'] = 'private-other-target'
    request = campaign.plan.root / 'declarations.json'
    request.write_bytes(bundle.encoded(dict(schema='onpc-evidence-documents', version=1,
                                           documents=[declaration])))
    monkeypatch.setattr(proof, '__file__', str(campaign.plan.root / 'tools/plan_evidence.py'))
    assert proof.main(['--plan', campaign.plan.path, '--declarations', str(request)]) == 2
    captured = capsys.readouterr()
    diagnostic = json.loads(captured.err.split('evidence-links: ', 1)[1])
    assert diagnostic['condition'] == 'identity'
    assert diagnostic['document'] == campaign.plan.path and diagnostic['line'] == 2
    assert diagnostic['expected'] != diagnostic['actual'] and diagnostic['recovery']
    assert 'private' not in captured.err


def test_active_consumer_does_not_activate_unrelated_history_in_same_document(campaign):
    selected = _structured_publication(campaign)
    run, state, result, report = campaign.accepted('first')
    (campaign.plan.root / 'docs/Guide.md').write_text('# Present\n')
    old = campaign.plan.root / 'docs/Old.md'
    old.write_text('# Old\n')
    _, declaration, contracts = _policy_document(campaign, selected,
        'Old [result](Old.md).\nRequired [guide](Guide.md#present).\n',
        role='historical_information', document=campaign.plan.path)
    current = declaration['references'][1]['consumer']
    current['role'] = 'required_instruction'
    contracts[current['consumer_id']] = copy.deepcopy(current)
    state.update(reference_documents=[declaration], reference_contracts=contracts,
                 active_reference_consumers=[current['consumer_id']])
    proof.preflight(campaign.plan, run, state)
    old.unlink()
    proof.preflight(campaign.plan, run, state)


def test_authored_master_evidence_joins_strict_publication_selection(campaign):
    run, state, result, report = campaign.accepted('first')
    missing = bundle.storage.directory('reports') / 'missing-result.json'
    master = campaign.plan.root / campaign.plan.path
    master.write_text(master.read_text() + '\nNew proof [report](' +
        os.path.relpath(missing, master.parent) + ').\n')
    assert str(missing) in proof.publication_document_gate(campaign.plan, state, result)
    with pytest.raises(proof.EvidenceUnavailable):
        proof.preserve(campaign.plan, run, state, result)


@pytest.mark.parametrize('name', ['Article.md', 'Article.MD'])
def test_authored_stage_document_uses_exact_git_baseline_without_rechecking_old_loss(campaign, name):
    root = campaign.plan.root
    relative = 'docs/' + name
    article = root / relative
    missing = bundle.storage.directory('reports') / 'old-missing.json'
    article.write_text('Unrelated old proof [old](' + os.path.relpath(missing, article.parent) + ').\n')
    for command in (['git', 'init', '-q'], ['git', 'add', '--', relative],
                    ['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                     'commit', '-qm', 'Original document']):
        import subprocess
        subprocess.run(command, cwd=root, check=True, capture_output=True)
    run, state, result, report = campaign.accepted('first')
    result['stage_paths'] = [relative]
    assert proof.publication_document_gate(campaign.plan, state, result) == []
    baseline = state.pop('reference_git_base')
    assert str(missing) in proof.publication_document_gate(campaign.plan, state, result)
    state['reference_git_base'] = baseline
    article.write_text(article.read_text() + '\nNew instruction [read](Absent.md).\n')
    with pytest.raises(proof.ReferenceRefused) as error:
        proof.publication_document_gate(campaign.plan, state, result)
    assert error.value.diagnostics[0]['document'] == relative
