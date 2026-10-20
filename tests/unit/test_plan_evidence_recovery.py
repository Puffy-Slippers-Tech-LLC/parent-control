"""Exact controller evidence disclosures preserve acceptance and saved ownership."""

import copy
import json
from pathlib import Path
import shutil

import pytest

from execution_plan import Plan
import plan_evidence_recovery as recovery


@pytest.fixture
def scene(tmp_path, monkeypatch):
    docs = tmp_path / 'docs'
    docs.mkdir()
    (docs / 'plan.md').write_text('Task queue: [Queue](queue.md).\nNext task: **repair — Repair**.\n')
    (docs / 'repair.md').write_text('# Evidence repair\nAcceptance: host\n')
    (docs / 'consumer.md').write_text('# Consumer\nAcceptance: review\n')
    old = 'Review passed; [551 checks](../expired/result.json); no runtime resources.'
    consumer = 'Reviewed; [590 checks](../reports/current/report.md); remaining links pending.'
    text = ('| Done | ID | Task | Requires | Scope | Estimate |\n'
            '| --- | --- | --- | --- | --- | --- |\n'
            f'| [x] | old | [Old decision](decision.md) | Baseline | fixed old scope | {old} |\n'
            '| [ ] | repair | [Repair](repair.md) | old | finite repair | 30 min |\n'
            f'| [ ] | consumer | [Consumer](consumer.md) | old, repair | fixed consumer scope | {consumer} |\n')
    queue = docs / 'queue.md'
    queue.write_text(text)
    plan = Plan.load(tmp_path, 'docs/plan.md')
    task = dict(task_id='repair', title='Repair', brief=str(docs / 'repair.md'),
                acceptance='host', targets=[])
    consumer_task = dict(task_id='consumer', title='Consumer', brief=str(docs / 'consumer.md'),
                         acceptance='review', targets=[])
    suspended = dict(task_id='consumer', task=consumer_task, task_sessions=3,
                     total_sessions=3, session_limit=6, stage_baseline={'owned.md': 'original'},
                     protected_staged=['foreign.md'], queue_before=plan.state(),
                     queue_structure=plan.structure(selected='consumer'), phase='recover')
    state = dict(task_id='repair', task=task, task_sessions=1, total_sessions=4,
                 session_limit=5, stage_baseline={'owned.md': 'original'},
                 protected_staged=['foreign.md'], queue_before=plan.state(),
                 queue_structure=plan.structure(selected='repair'),
                 suspended_tasks={'consumer': suspended}, phase='recover', in_flight=False,
                 summary='Returned at a clean boundary', handoff='Preserve all work')
    run = tmp_path / 'run'
    run.mkdir(mode=0o700)
    raw = json.dumps(state).encode()
    (run / 'checkpoint.json').write_bytes(raw)
    authority = json.dumps(dict(answer=dict(question='Reconcile?', answer='Reconcile automatically.'),
                                phase='complete', in_flight=False, task_id='old',
                                queue_before={'old': True, 'consumer': False})).encode()
    (tmp_path / 'authorization.json').write_bytes(authority)
    new = old.replace('[551 checks](../expired/result.json)',
                      '[551 checks' + recovery.LABEL_SUFFIX + '](../bundle/evidence.zip)')
    new_consumer = consumer.replace('../reports/current/report.md', '../bundle/evidence.zip')
    request = dict(version=1, plan=plan.path, queue=plan.queue, task=task,
                   baseline_sha256=recovery.protected_digest(state),
                   queue_sha256=recovery.digest(queue.read_bytes()),
                   authorization=dict(checkpoint='authorization.json',
                       sha256=recovery.digest(authority),
                       answer_sha256=recovery.digest(recovery.encoded(json.loads(authority)['answer']))),
                   corrections=[dict(task_id='old', kind='historical-disclosure',
                                     before=old, after=new, proof={'accepted': 'old'}),
                                dict(task_id='consumer', kind='retained-destination',
                                     before=consumer, after=new_consumer, proof={'exact': 'consumer'})])

    class Scene:
        def write_request(self):
            (docs / 'repair.md').write_text('# Evidence repair\nAcceptance: host\n'
                '```plan-evidence-recovery\n' + json.dumps(self.request) + '\n```\n')

        def recover(self, **kwargs):
            return recovery.recover_evidence(self.plan, self.state, self.run,
                                             verify_proof=self.verify, **kwargs)

        def verify(self, correction, request):
            self.verified.append((correction['task_id'], copy.deepcopy(correction['proof'])))

    result = Scene()
    result.root, result.plan, result.queue, result.run = tmp_path, plan, queue, run
    result.state, result.raw, result.request = state, raw, request
    result.old, result.consumer, result.authority = old, consumer, authority
    result.verified = []
    result.closed = []
    monkeypatch.setattr(recovery.launcher, 'finish_nested',
                        lambda root, run: result.closed.append(run))
    result.write_request()
    return result


def test_controller_corrects_only_reviewed_links_and_preserves_checkpoint(scene):
    original = copy.deepcopy(scene.state)
    updated = scene.recover()
    assert scene.plan.state() == original['queue_before']
    assert recovery.LABEL_SUFFIX in scene.queue.read_text()
    assert '../expired/result.json' not in scene.queue.read_text()
    assert scene.verified == [('old', {'accepted': 'old'}), ('consumer', {'exact': 'consumer'})]
    expected = copy.deepcopy(original)
    for correction in scene.request['corrections']:
        for saved in [expected, *expected['suspended_tasks'].values()]:
            row = next(row for row in saved['queue_structure'] if row[2] == correction['task_id'])
            if row[6] != '<selected task estimate>':
                row[6] = correction['after']
    marker = updated['evidence_recovery']
    assert marker['request_sha256'] == recovery.digest(recovery.encoded(scene.request))
    assert {key: value for key, value in updated.items() if key != 'evidence_recovery'} == expected
    assert scene.state == original
    assert json.loads((scene.run / 'checkpoint.json').read_bytes()) == updated
    backup, = scene.run.glob('checkpoint-before-evidence-*.json')
    assert json.loads(backup.read_bytes()) == {'checkpoint_utf8': scene.raw.decode()}
    receipt = json.loads((scene.run / 'evidence-recovery.json').read_bytes())
    assert receipt['complete'] is True
    assert receipt['checkpoint_utf8'].encode() == scene.raw
    assert receipt['authorization_utf8'].encode() == scene.authority
    assert scene.closed == [scene.run]
    scene.plan.validate_recovery(updated)
    scene.plan.validate_recovery(updated['suspended_tasks']['consumer'])


def test_no_request_leaves_checkpoint_and_queue_unchanged(scene):
    Path(scene.state['task']['brief']).write_text('# Repair\nAcceptance: host\n')
    queue = scene.queue.read_bytes()
    assert scene.recover() is scene.state
    assert scene.queue.read_bytes() == queue
    assert not (scene.run / 'evidence-recovery.json').exists()


def test_completed_task_with_removed_temporary_brief_has_no_recovery_request(scene):
    Path(scene.state['task']['brief']).unlink()
    scene.state.update(phase='complete', in_flight=False)
    assert scene.recover() is scene.state
    assert not (scene.run / 'evidence-recovery.json').exists()


@pytest.mark.parametrize('field', ['result_recovery', 'pending_completion', 'git_reconciliation'])
def test_removed_brief_during_ordinary_result_recovery_has_no_evidence_request(scene, field):
    Path(scene.state['task']['brief']).unlink()
    scene.state.update(phase='recover', in_flight=False)
    scene.state[field] = {'retained': 'ordinary owner'}
    assert scene.recover() is scene.state
    assert not (scene.run / 'evidence-recovery.json').exists()


@pytest.mark.parametrize('field', ['task_id', 'task', 'queue_before', 'queue_structure',
                                 'task_sessions', 'total_sessions', 'session_limit',
                                 'stage_baseline', 'protected_staged', 'suspended_tasks',
                                 'commit_intent', 'pull_intent', 'pending_completion', 'evidence_inputs',
                                 'evidence_attempt', 'evidence_capture_requires_brief', 'evidence_recovery',
                                 'evidence_source'])
def test_material_checkpoint_changes_refuse(scene, field):
    scene.state[field] = {'changed': True}
    (scene.run / 'checkpoint.json').write_text(json.dumps(scene.state))
    with pytest.raises((ValueError, TypeError, AttributeError)):
        scene.recover()
    assert not (scene.run / 'evidence-recovery.json').exists()


@pytest.mark.parametrize('defect', ['completion', 'scope', 'requires', 'order', 'title', 'acceptance',
                                 'suspended-acceptance'])
def test_review_request_cannot_adopt_unrelated_edits(scene, defect):
    text = scene.queue.read_text()
    if defect == 'completion':
        text = text.replace('| [x] | old |', '| [ ] | old |')
    elif defect == 'scope':
        text = text.replace('fixed old scope', 'reduced scope')
    elif defect == 'requires':
        text = text.replace('| old, repair |', '| repair |')
    elif defect == 'order':
        lines = text.splitlines(keepends=True)
        lines[2], lines[4] = lines[4], lines[2]
        text = ''.join(lines)
    elif defect == 'title':
        text = text.replace('[Consumer]', '[Changed consumer]')
    elif defect == 'acceptance':
        Path(scene.state['task']['brief']).write_text(
            Path(scene.state['task']['brief']).read_text().replace('Acceptance: host', 'Acceptance: review'))
    else:
        (scene.root / 'docs/consumer.md').write_text('# Consumer\nAcceptance: host\n')
    scene.queue.write_text(text)
    # Even an updated queue digest cannot authorize changed baseline fields.
    scene.request['queue_sha256'] = recovery.digest(scene.queue.read_bytes())
    if defect != 'acceptance':
        scene.write_request()
    with pytest.raises(ValueError):
        scene.recover()
    assert not (scene.run / 'evidence-recovery.json').exists()


@pytest.mark.parametrize('defect', ['free-label', 'prose', 'link-count', 'drop-disclosure',
                                 'unfinished-disclosure', 'existing-original', 'proof'])
def test_narrow_corrections_refuse_fabricated_or_unreviewed_claims(scene, defect):
    item = scene.request['corrections'][0]
    if defect == 'free-label':
        item['after'] = item['after'].replace('551 checks' + recovery.LABEL_SUFFIX, '551 checks passed')
    elif defect == 'prose':
        item['after'] = item['after'].replace('no runtime resources', 'cleanup unnecessary')
    elif defect == 'link-count':
        item['after'] += ' [extra](../bundle/evidence.zip)'
    elif defect == 'drop-disclosure':
        item['after'] = item['after'].replace(recovery.LABEL_SUFFIX, '')
    elif defect == 'unfinished-disclosure':
        item = scene.request['corrections'][1]
        item['kind'] = 'historical-disclosure'
        item['after'] = item['after'].replace('[590 checks]', '[590 checks' + recovery.LABEL_SUFFIX + ']')
    elif defect == 'existing-original':
        path = scene.root / 'expired' / 'result.json'
        path.parent.mkdir()
        path.write_text('existing proof')
    else:
        def refuse(*_):
            raise ValueError('exact proof changed')
        scene.verify = refuse
    scene.write_request()
    with pytest.raises(ValueError):
        scene.recover()
    assert not (scene.run / 'evidence-recovery.json').exists()


@pytest.mark.parametrize('boundary', ['before-queue', 'after-queue', 'after-checkpoint'])
def test_interrupted_controller_publication_resumes_exact_transaction(scene, monkeypatch, boundary):
    original_publish = recovery._publish_queue
    original_atomic = recovery.launcher.atomic
    failed = False

    def publish(path, payload):
        nonlocal failed
        if boundary == 'before-queue' and not failed:
            failed = True
            raise OSError('interrupted before queue')
        original_publish(path, payload)
        if boundary == 'after-queue' and not failed:
            failed = True
            raise OSError('interrupted after queue')

    def atomic(path, value):
        nonlocal failed
        original_atomic(path, value)
        if boundary == 'after-checkpoint' and path.name == 'checkpoint.json' and not failed:
            failed = True
            raise OSError('interrupted after checkpoint')

    monkeypatch.setattr(recovery, '_publish_queue', publish)
    monkeypatch.setattr(recovery.launcher, 'atomic', atomic)
    with pytest.raises(OSError, match='interrupted'):
        scene.recover()
    assert json.loads((scene.run / 'evidence-recovery.json').read_bytes())['complete'] is False
    # Reopen with exactly the checkpoint that survived the interruption.
    scene.state = json.loads((scene.run / 'checkpoint.json').read_bytes())
    updated = scene.recover()
    assert json.loads((scene.run / 'evidence-recovery.json').read_bytes())['complete'] is True
    assert scene.plan.validate_recovery(updated) == updated['queue_before']
    assert len(list(scene.run.glob('checkpoint-before-evidence-*.json'))) == 1


def test_verified_bundle_authorization_survives_original_source_expiration(scene):
    scene.request['authorization']['checkpoint'] = '/original/retained/checkpoint.json'
    scene.request['authorization']['bundle'] = 'verified-bundle.zip'
    scene.write_request()
    (scene.root / 'authorization.json').unlink()
    updated = scene.recover(read_authorization=lambda request: scene.authority)
    scene.state = updated
    # A committed transaction reuses its retained authority rather than a source
    # that can rotate; normal restart guards continue to protect the saved state.
    assert scene.recover(read_authorization=lambda _: pytest.fail('re-read expired source')) == updated


def test_changed_authorization_refuses_before_publication(scene):
    (scene.root / 'authorization.json').write_text('{}')
    with pytest.raises(ValueError, match='authorization changed'):
        scene.recover()
    assert not (scene.run / 'evidence-recovery.json').exists()


def test_changed_queue_after_interruption_is_preserved_and_refused(scene, monkeypatch):
    monkeypatch.setattr(recovery, '_publish_queue', lambda *_: (_ for _ in ()).throw(OSError('stop')))
    with pytest.raises(OSError):
        scene.recover()
    scene.queue.write_text(scene.queue.read_text() + '\nUnrelated change.\n')
    changed = scene.queue.read_bytes()
    with pytest.raises(ValueError, match='transaction payload changed'):
        scene.recover()
    assert scene.queue.read_bytes() == changed
    assert (scene.run / 'checkpoint.json').read_bytes() == scene.raw


def test_nested_cleanup_refusal_precedes_all_evidence_transaction_mutations(scene, monkeypatch):
    queue = scene.queue.read_bytes()
    checkpoint = (scene.run / 'checkpoint.json').read_bytes()

    def refuse(*_):
        raise ValueError('nested test identity changed; preserve evidence')

    monkeypatch.setattr(recovery.launcher, 'finish_nested', refuse)
    with pytest.raises(ValueError, match='nested test identity changed'):
        scene.recover()
    assert scene.queue.read_bytes() == queue
    assert (scene.run / 'checkpoint.json').read_bytes() == checkpoint
    assert not list(scene.run.glob('checkpoint-before-evidence-*'))
    assert not (scene.run / 'evidence-recovery.json').exists()


def test_unsafe_run_owner_refuses_before_nested_cleanup_or_publication(scene):
    scene.run.chmod(0o755)
    with pytest.raises(ValueError, match='private recorded run owner'):
        scene.recover()
    assert scene.closed == []
    assert (scene.run / 'checkpoint.json').read_bytes() == scene.raw
    assert not (scene.run / 'evidence-recovery.json').exists()


def test_interrupted_transaction_retry_still_requires_owned_nested_cleanup(scene, monkeypatch):
    monkeypatch.setattr(recovery, '_publish_queue',
                        lambda *_: (_ for _ in ()).throw(OSError('interrupted queue publication')))
    with pytest.raises(OSError):
        scene.recover()
    receipt = scene.run / 'evidence-recovery.json'
    retained = receipt.read_bytes()
    queue = scene.queue.read_bytes()
    monkeypatch.setattr(recovery.launcher, 'finish_nested',
                        lambda *_: (_ for _ in ()).throw(ValueError('unsafe nested owner')))
    with pytest.raises(ValueError, match='unsafe nested owner'):
        scene.recover()
    assert receipt.read_bytes() == retained
    assert scene.queue.read_bytes() == queue
    assert (scene.run / 'checkpoint.json').read_bytes() == scene.raw


@pytest.mark.parametrize('expire_original', [False, True])
def test_applied_request_survives_later_runs_and_session_progress(scene, expire_original):
    updated = scene.recover()
    original_run = scene.run
    next_run = original_run.with_name('next-run')
    next_run.mkdir(mode=0o700)
    updated.update(task_sessions=2, total_sessions=5, session_limit=10,
                   phase='recover', summary='Later continuation')
    (next_run / 'checkpoint.json').write_text(json.dumps(updated))
    if expire_original:
        shutil.rmtree(original_run)
    scene.run, scene.state = next_run, updated
    before = copy.deepcopy(updated)
    scene.verify = lambda *_: pytest.fail('reapplied an already committed request')
    assert scene.recover() == before
    assert (next_run / 'checkpoint.json').read_bytes() == json.dumps(before).encode()
    assert not (next_run / 'evidence-recovery.json').exists()
    assert scene.closed == [original_run, next_run]


@pytest.mark.parametrize('defect', ['request', 'receipt', 'marker', 'baseline'])
def test_later_run_refuses_altered_applied_request_or_transaction(scene, defect):
    updated = scene.recover()
    original_run = scene.run
    next_run = original_run.with_name('next-run')
    next_run.mkdir(mode=0o700)
    if defect == 'request':
        scene.request['corrections'][0]['after'] += ' changed'
        scene.write_request()
    elif defect == 'receipt':
        receipt = original_run / 'evidence-recovery.json'
        receipt.write_bytes(receipt.read_bytes() + b' ')
    elif defect == 'marker':
        updated['evidence_recovery']['transaction']['queue_after'] += ' changed'
    else:
        updated['queue_structure'][0][6] = scene.old
    (next_run / 'checkpoint.json').write_text(json.dumps(updated))
    scene.run, scene.state = next_run, updated
    before = (next_run / 'checkpoint.json').read_bytes()
    with pytest.raises(ValueError):
        scene.recover()
    assert (next_run / 'checkpoint.json').read_bytes() == before
    assert not (next_run / 'evidence-recovery.json').exists()


def test_permitted_prior_destination_repairs_preserve_original_archived_claims(scene):
    original = scene.state['queue_structure'][0][6]
    # An earlier ordinary destination-only repair is legal and must not require
    # rewriting the original saved queue or its authorization checkpoint.
    current = original.replace('../expired/result.json', '../expired/repaired-result.json')
    scene.queue.write_text(scene.queue.read_text().replace(original, current))
    scene.request['corrections'][0]['before'] = current
    scene.request['queue_sha256'] = recovery.digest(scene.queue.read_bytes())
    scene.write_request()
    updated = scene.recover()
    scene.plan.validate_recovery(updated)
    backup, = scene.run.glob('checkpoint-before-evidence-*.json')
    assert original in json.loads(backup.read_bytes())['checkpoint_utf8']


def bundle_verifier_scene(scene, monkeypatch):
    member = str(scene.root / 'reports/current/report.md')
    authority_member = '/original/checkpoint.json'
    bundle = scene.root / 'bundle/evidence.zip'
    report_sha = 'a' * 64
    entries = [dict(path=member, sha256=report_sha, bytes=123),
               dict(path=authority_member, sha256=recovery.digest(scene.authority), bytes=len(scene.authority))]
    scene.request['authorization'].update(checkpoint=authority_member, bundle=str(bundle))
    historical, consumer = scene.request['corrections']
    historical['proof'] = dict(bundle=str(bundle), links=[dict(
        before='../expired/result.json', member=authority_member, sha256=recovery.digest(scene.authority))])
    consumer['proof'] = dict(bundle=str(bundle), links=[dict(
        before='../reports/current/report.md', member=member, sha256=report_sha)])
    calls = []

    def inspect(plan, path, **kwargs):
        assert path == bundle
        calls.append(kwargs)
        if kwargs:
            assert kwargs['member'] == authority_member
            return scene.authority
        return {'manifest': {'files': entries}}

    monkeypatch.setattr(recovery, '_inspect_bundle', inspect)
    return historical, consumer, entries, calls


def test_production_proof_verifier_distinguishes_disclosure_from_exact_reports(scene, monkeypatch):
    historical, consumer, _, calls = bundle_verifier_scene(scene, monkeypatch)
    recovery.verify_proof(scene.plan, historical, scene.request)
    recovery.verify_proof(scene.plan, consumer, scene.request)
    assert any(item.get('member') == '/original/checkpoint.json' for item in calls)


@pytest.mark.parametrize('defect', ['uncovered-link', 'wrong-member', 'wrong-digest',
                                 'wrong-destination', 'report-substitution', 'old-proof-present',
                                 'unaccepted-row', 'unaccepted-checkpoint'])
def test_production_proof_refuses_changed_or_substitute_proof(scene, monkeypatch, defect):
    historical, consumer, entries, _ = bundle_verifier_scene(scene, monkeypatch)
    selected = historical
    if defect == 'uncovered-link':
        historical['proof']['links'] = []
    elif defect == 'wrong-member':
        historical['proof']['links'][0]['member'] = '/missing/member'
    elif defect == 'wrong-digest':
        historical['proof']['links'][0]['sha256'] = 'b' * 64
    elif defect == 'wrong-destination':
        historical['after'] = historical['after'].replace('../bundle/', '../other/')
    elif defect == 'report-substitution':
        selected = consumer
        consumer['proof']['links'][0].update(member='/original/checkpoint.json',
                                             sha256=recovery.digest(scene.authority))
    elif defect == 'old-proof-present':
        entries.append(dict(path=str(scene.root / 'expired/result.json'), sha256='c' * 64, bytes=1))
    elif defect == 'unaccepted-row':
        historical['task_id'] = 'consumer'
    else:
        authority = json.loads(scene.authority)
        authority['phase'] = 'recover'
        scene.authority = json.dumps(authority).encode()
        scene.request['authorization']['sha256'] = recovery.digest(scene.authority)
        entries[1]['sha256'] = recovery.digest(scene.authority)
        historical['proof']['links'][0]['sha256'] = recovery.digest(scene.authority)
    with pytest.raises(ValueError):
        recovery.verify_proof(scene.plan, selected, scene.request)
