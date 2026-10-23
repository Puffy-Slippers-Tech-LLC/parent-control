"""Runner terminal histories with private storage and real publication/rotation.

No VM, process, display, socket, service, shared cache or fixture build is owned.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace

import pytest

import evidence_bundle as bundle
import evidence_capture as capture
import regression
import runner_evidence as runner
import test_retention as retention
import test_storage as storage
import vm_test_queue


@pytest.fixture
def environment(tmp_path, monkeypatch):
    root = tmp_path / 'checkout'
    root.mkdir(mode=0o700)
    monkeypatch.setattr(storage, 'ROOT', root)
    monkeypatch.setattr(storage, 'BASE', root / 'output/test-runs')
    monkeypatch.delenv(retention.VARIABLE, raising=False)
    monkeypatch.delenv(retention.OWNER_VARIABLE, raising=False)
    monkeypatch.delenv('ONPC_RUNNER_INVOCATION', raising=False)
    monkeypatch.setattr(capture, '_authenticated_caller',
                        lambda: dict(uid=os.geteuid(), gid=os.getegid()))
    # Target registration only; no actual configuration or VM operation.
    monkeypatch.setattr(capture, 'validate_targets', lambda checkout, targets: None)
    monkeypatch.setattr(runner.regression_inputs, 'identity', lambda root: 'f' * 64)
    return root, retention.Store(storage.directory('state') / 'retention-host')


def allocate():
    return Path(retention.allocate(tempfile.mkdtemp, prefix='onpc-runner-test-'))


def closed_file(directory, name, value):
    path = directory / name
    path.write_bytes(value)
    path.chmod(0o600)
    return path


def command(target='', status='passed', cleanup='complete', **updates):
    value = dict(check='unit', category='unit', target=target,
                 argv=['tools/run-tests', '--test', 'exact_case'],
                 selected_ids=['test_module.py::exact_case'], resumed_ids=[],
                 completed_ids=['test_module.py::exact_case'], failed_ids=[],
                 exit_status=0, status=status, cleanup=cleanup,
                 provenance='worker', sequence=1)
    value.update(updates)
    return value


def finish(evidence, *, members=(), **updates):
    values = dict(categories=[dict(name='unit', selected_ids=['exact_case'])],
                  status='passed', cleanup='complete', sources_sha256='f' * 64,
                  inputs=dict(selector=['unit', 'exact_case']))
    values.update(updates)
    return evidence.finalize(members=members, **values)


def exact_reference(result, member):
    return next(reference for reference in result['references']
                if reference['member_id'] == member['member_id'])


def test_generated_document_link_uses_exact_runner_proof_after_rotation(environment, monkeypatch, capsys):
    import plan_evidence as proof
    root, store = environment
    docs = root / 'docs'
    docs.mkdir()
    (docs / 'Plan.md').write_text('Task queue: [Queue](Queue.md).\n')
    (docs / 'Queue.md').write_text('Unchanged queue.\n')
    plan = SimpleNamespace(root=root, path='docs/Plan.md', queue='docs/Queue.md')
    with store.session():
        producer = regression.Report(root)
        producer.write('original document proof\n')
        producer.command(command())
        producer.close(defer_capture=True)
        first = producer.finalize(status='passed', cleanup='complete', sources_sha256='f' * 64)
    record = next(item for item in first['records'] if item['context']['check'] == 'unit')
    member = next(item for item in record['members'] if item['role'] == 'result')
    consumer = next(item for item in first['consumers'] if item['expected_context'] == record['context'])
    selector = dict(kind='evidence', **{key: exact_reference(first, member)[key]
        for key in ('record_id', 'member_id', 'closure_sha256')})
    document = docs / 'nested/Evidence.md'
    document.parent.mkdir()
    original = Path(member['original_path'])
    text = '[$(touch sentinel)](' + os.path.relpath(original, document.parent) + ')\n'
    document.write_text(text)
    declaration = dict(document='docs/nested/Evidence.md', sha256=bundle.digest(document.read_bytes()),
        references=[dict(start=0, consumer=consumer, selector=selector, workflow='regression')])
    # Four real producer admissions retire the original; no acceptance rerun.
    for index in range(4):
        with store.session():
            later = regression.Report(root)
            later.command(command())
            later.close(defer_capture=True)
            latest = later.finalize(status='passed', cleanup='complete', sources_sha256='f' * 64)
    assert not original.exists()
    new_record = next(item for item in latest['records'] if item['context']['check'] == 'unit')
    new_member = next(item for item in new_record['members'] if item['role'] == 'result')
    assert new_member['sha256'] == member['sha256']  # Equal payload, different actual attempt.
    assert new_record['context']['attempt'] != record['context']['attempt']
    other_attempt = dict(declaration, references=[dict(declaration['references'][0],
        consumer=dict(consumer, expected_context=new_record['context']))])
    with pytest.raises(ValueError, match='context mismatch'):
        proof.preview_document_links(plan, other_attempt)
    with store.session():
        active = regression.Report(root)
        try:
            preview = proof.preview_document_links(plan, declaration)
            destination = preview['edits'][0]['after']
            assert destination == os.path.relpath(runner.reference_locator(root, 'regression'),
                                                document.parent) + '#onpc-evidence-v1:' + ':'.join(
                selector[key] for key in ('record_id', 'member_id', 'closure_sha256'))
            resolved = proof.resolve_reference(destination, consumer=consumer,
                read_scope=proof.reference_scope(plan, document=declaration['document'], workflow='regression'),
                count=0)
            assert resolved['record'] == record and resolved['member'] == member
            assert resolved['data'] == b'' and resolved['closure'][record['record_id']] == record
            request = root / 'declarations.json'
            request.write_bytes(bundle.encoded(dict(schema='onpc-evidence-documents', version=1,
                                                   documents=[declaration])))
            monkeypatch.setattr(proof, '__file__', str(root / 'tools/plan_evidence.py'))
            assert proof.main(['--plan=docs/Plan.md', '--declarations=' + str(request)]) == 0
            output = json.loads(capsys.readouterr().out)
            assert output['previews'] == [preview] and document.read_text() == text
            for malformed in (None, 42, ['docs/nested/Evidence.md']):
                bad = dict(declaration, document=malformed)
                request.write_bytes(bundle.encoded(dict(schema='onpc-evidence-documents', version=1,
                                                       documents=[bad])))
                assert proof.main(['--plan=docs/Plan.md', '--declarations=' + str(request)]) == 2
                refusal = capsys.readouterr()
                assert not refusal.out and 'semantic preview refused' in refusal.err
            assert proof.apply_document_links(plan, preview)
            assert document.read_text() == text.replace(os.path.relpath(original, document.parent), destination)
            assert not original.exists() and not (root / 'sentinel').exists()
        finally:
            active.command(command(check='active-completed'))
            active.close(defer_capture=True)
            active.finalize(status='passed', cleanup='complete', sources_sha256='f' * 64)


def test_report_a_survives_original_and_publication_generation_rotation_without_rerun(environment):
    root, store = environment
    invocations = 0
    with store.session():
        producer = regression.Report(root)
        directory = producer.directory
        report = directory / 'report.md'
        producer.write('original report A\n')
        log = closed_file(directory, 'command.log', b'exact complete command output\n')
        producer.member(log, 'command')
        invocations += 1
        producer.command(command(log=str(log)))
        categories = [regression.Category('unit', total=1, done=1, state='Passed',
            nodeids=('test_module.py::exact_case',), resumed_nodeids=('prior-case',))]
        producer.snapshot(categories)
        producer.close(defer_capture=True)
        first = producer.finalize(categories=categories, status='passed',
                                  cleanup='complete', sources_sha256='f' * 64)
        expected = {member['member_id']: Path(member['original_path']).read_bytes()
                    for record in first['records'] for member in record['members']}
        original_receipt = Path(first['receipt']['path'])
        assert producer.finalize() == first
    for index in range(5):
        with store.session():
            later = regression.Report(root)
            later.command(command(check=f'later-{index}'))
            later.close(defer_capture=True)
            later.finalize(status='passed', cleanup='complete', sources_sha256='f' * 64)
    assert not report.exists()
    assert not report.parent.exists()
    assert not original_receipt.exists()
    for record in first['records']:
        assert record['context']['sources_sha256'] == 'f' * 64
        for member in record['members']:
            consumer = next(value for value in first['consumers']
                            if value['expected_context'] == record['context'])
            saved = runner.resolve_reference(root, exact_reference(first, member), consumer=consumer)
            assert saved == expected[member['member_id']]
            assert hashlib.sha256(saved).hexdigest() == member['sha256']
    assert invocations == 1
    report_record = first['records'][-1]
    assert report_record['dependencies'] == sorted([
        dict(record_id=record['record_id'], closure_sha256=record['closure_sha256'])
        for record in first['records'][:-1]], key=lambda item: item['record_id'])


def test_standalone_report_first_use_owns_capture_until_close(environment, monkeypatch):
    root, _ = environment
    monkeypatch.setattr(runner.regression_inputs, 'identity', lambda root: 'e' * 64)
    producer = regression.Report(root)
    producer.write('standalone first-use diagnostic\n')
    producer.close()
    assert producer.retention_session is None
    assert retention.VARIABLE not in os.environ
    record = producer.receipt['records'][-1]
    assert record['status'] == 'diagnostic'
    assert record['cleanup']['state'] == 'pending'
    member = next(value for value in record['members']
                  if value['original_path'] == str(producer.directory / 'report.md'))
    assert b'standalone first-use' in runner.resolve_reference(
        root, exact_reference(producer.receipt, member))


@pytest.mark.parametrize('status,cleanup,exit_status', [
    ('passed', 'complete', 0), ('failed', 'complete', 1),
    ('failed', 'failed', 1), ('interrupted', 'pending', None),
    ('diagnostic', 'pending', None), ('not_run', 'complete', None),
])
def test_terminal_status_and_exact_two_target_selections_remain_truthful(
        environment, status, cleanup, exit_status):
    root, store = environment
    with store.session():
        evidence = runner.ReportEvidence(root, allocate())
        for target, ids in [('ubuntu', ['setup-case']), ('fedora', ['teardown-case'])]:
            evidence.command(command(target, status, cleanup, selected_ids=ids,
                resumed_ids=['prior-case'], completed_ids=[], exit_status=exit_status))
        result = finish(evidence, status=status, cleanup=cleanup)
    assert [record['context']['target'] for record in result['records']] == ['', 'ubuntu', 'fedora', '']
    start = result['records'][0]
    assert start['status'] == 'diagnostic'
    assert start['cleanup']['state'] == 'pending'
    for record in result['records'][1:]:
        assert record['status'] == status
        assert record['cleanup']['state'] == cleanup
        assert record['completeness'] == ('complete' if cleanup == 'complete' and
            status not in ('interrupted', 'diagnostic', 'not_run') else 'partial')
    for record, expected in zip(result['records'][1:], ['setup-case', 'teardown-case']):
        member = next(member for member in record['members'] if member['role'] == 'input')
        payload = json.loads(runner.resolve_reference(root, exact_reference(result, member)))
        assert payload['selected_ids'] == [expected]
        assert payload['resumed_ids'] == ['prior-case']


def test_failed_publication_keeps_original_and_blocks_rotation_without_retry(environment, monkeypatch):
    root, store = environment
    attempts = []
    real_export = bundle.export
    def denied(*args, **kwargs):
        attempts.append(1)
        raise PermissionError('synthetic helper denial')
    with store.session():
        directory = allocate()
        report = closed_file(directory, 'report.md', b'keep original\n')
        evidence = runner.ReportEvidence(root, directory)
        evidence.command(command())
        monkeypatch.setattr(bundle, 'export', denied)
        with pytest.raises(PermissionError, match='denial'):
            finish(evidence, members=[dict(path=report, role='result')])
        assert attempts == [1]
        state = json.loads((store.path / 'current.json').read_bytes())
        assert state['captures'] and all(not item.get('acknowledgement') for item in state['captures'])
        assert report.read_bytes() == b'keep original\n'
        monkeypatch.setattr(bundle, 'export', real_export)
        result = finish(evidence)
        assert len(result['capture_ids']) == len(state['captures'])
    for _ in range(5):
        with store.session():
            pass
    assert not report.exists()
    assert attempts == [1]


def test_unacknowledged_capture_preserves_original_at_retirement(environment, monkeypatch):
    root, store = environment
    with store.session():
        directory = allocate()
        report = closed_file(directory, 'report.md', b'required original\n')
        evidence = runner.ReportEvidence(root, directory)
        def missing(*args, **kwargs):
            raise ValueError('missing exact acknowledgement')
        monkeypatch.setattr(capture, 'acknowledge_capture', missing)
        with pytest.raises(ValueError, match='missing exact'):
            finish(evidence, members=[dict(path=report, role='result')])
    with store.session():
        pass
    with store.session():
        pass
    with pytest.raises(ValueError, match='verified acknowledgement'):
        with store.session():
            pass
    assert report.read_bytes() == b'required original\n'


def test_foreign_missing_or_linked_finalized_members_refuse(environment):
    root, store = environment
    with store.session():
        directory = allocate()
        original = closed_file(directory, 'result', b'result')
        linked = directory / 'linked'
        linked.symlink_to(original)
        for path in [linked, directory / 'absent', root / 'foreign']:
            evidence = runner.ReportEvidence(root, directory)
            with pytest.raises((ValueError, OSError)):
                finish(evidence, members=[dict(path=path, role='result')])
        assert original.read_bytes() == b'result'


def test_token_without_live_owner_cannot_mint_a_runner_capture(environment, monkeypatch):
    root, store = environment
    with store.session():
        directory = allocate()
        token = os.environ[retention.VARIABLE]
    monkeypatch.setenv(retention.VARIABLE, token)
    with pytest.raises(ValueError, match='live producer'):
        runner.ReportEvidence(root, directory)


def test_late_outer_files_are_separate_and_stale_reference_refuses(environment):
    root, store = environment
    with store.session():
        directory = allocate()
        report = closed_file(directory, 'report.md', b'closed report')
        evidence = runner.ReportEvidence(root, directory)
        first = finish(evidence, members=[dict(path=report, role='result')])
        failure = closed_file(directory, 'failure.json', b'{"late":"outer"}')
        outer = runner.ReportEvidence(root, directory)
        second = finish(outer, status='failed', members=[dict(path=failure, role='result')])
        assert all(member['original_path'] != str(failure)
                   for record in first['records'] for member in record['members'])
        assert any(member['original_path'] == str(failure)
                   for record in second['records'] for member in record['members'])
        with pytest.raises(ValueError, match='immutable'):
            evidence.command(command())
    reference = dict(first['references'][0], closure_sha256='0' * 64)
    with pytest.raises(ValueError):
        runner.resolve_reference(root, reference)


@pytest.mark.parametrize('missing', ['record', 'member'])
@pytest.mark.parametrize('corrupt', [False, True])
def test_exact_absence_requires_verified_publication_before_renewal(environment, missing, corrupt):
    root, store = environment
    with store.session():
        directory = allocate()
        report = closed_file(directory, 'report.md', b'exact original proof')
        producer = runner.ReportEvidence(root, directory)
        result = finish(producer, members=[dict(path=report, role='result')])
    reference = dict(result['references'][0], **{missing + '_id': '0' * 64})
    if corrupt:
        with Path(result['receipt']['path']).open('ab') as stream:
            stream.write(b'corrupt archive')
        with pytest.raises(ValueError):
            runner.resolve_reference(root, reference)
    else:
        with pytest.raises(bundle.LogicalEvidenceUnavailable) as refused:
            runner.resolve_reference(root, reference)
        assert refused.value.references == [{key: reference[key]
            for key in ('record_id', 'member_id', 'closure_sha256')}]


@pytest.mark.parametrize('cleanup', ['complete', 'pending', 'failed'])
def test_batch_join_verifies_real_worker_selection_attempt_and_cleanup(environment, monkeypatch, cleanup):
    root, store = environment
    invocation = dict(batch_run='a' * 32, attempt='b' * 32,
                      target='fixture-guest', selection=[('system', ['--id', '3'])])
    monkeypatch.setenv('ONPC_RUNNER_INVOCATION', json.dumps(invocation))
    with store.session():
        report = regression.Report(root)
        report.command(command(target=invocation['target'], cleanup=cleanup))
        categories = [regression.Category('system', total=1, done=1, state='Passed',
                                         nodeids=('exact_case',))]
        report.snapshot(categories)
        report.close(defer_capture=True)
        proof = report.finalize(categories=categories, status='passed', cleanup=cleanup,
                                sources_sha256='f' * 64)
    assert vm_test_queue.worker_cleanup(root, invocation['target'], 0, [proof], invocation) == cleanup
    for changed in (dict(invocation, attempt='c' * 32),
                    dict(invocation, selection=[['system', ['--id', '4']]])):
        with pytest.raises(ValueError, match='invocation does not match'):
            vm_test_queue.worker_cleanup(root, invocation['target'], 0, [proof], changed)
    changed_proof = json.loads(json.dumps(proof))
    changed_proof['references'][0]['closure_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='closure changed'):
        vm_test_queue.worker_cleanup(root, invocation['target'], 0, [changed_proof], invocation)
    assert vm_test_queue.worker_cleanup(root, invocation['target'], 0, [], invocation) == 'pending'


@pytest.mark.parametrize('failure', ['malformed-handoff', 'resolver-refusal'])
def test_batch_processing_failure_captures_real_partial_closure(environment, failure):
    root, store = environment
    vms = [SimpleNamespace(name='fixture-guest')]
    selection = [['system', ['--id', '3']]]
    with store.session():
        with pytest.raises((ValueError, FileNotFoundError)):
            with vm_test_queue.batch_evidence(root, store, vms, selection) as (directory, evidence):
                log = closed_file(directory, 'fixture-guest.log', b'original worker output\n')
                if failure == 'malformed-handoff':
                    json.loads('{broken')
                else:
                    runner.resolve_reference(root, dict(schema=1, workflow='missing',
                        record_id='a' * 64, member_id='b' * 64, closure_sha256='c' * 64))
        proof = evidence._result
        assert proof is not None
        terminal = proof['records'][-1]
        assert terminal['status'] == 'failed'
        assert terminal['completeness'] == 'partial'
        assert terminal['cleanup']['state'] == 'pending'
        member = next(item for item in terminal['members'] if item['original_path'] == str(log))
        assert runner.resolve_reference(root, exact_reference(proof, member)) == b'original worker output\n'
        assert all(charge.get('acknowledgement') for charge in
                   json.loads((store.path / 'current.json').read_bytes())['captures'])


def test_finished_owner_cannot_acknowledge_startup_without_terminal_closure(environment):
    root, store = environment
    with store.session():
        directory = allocate()
        evidence = runner.ReportEvidence(root, directory)
        original = closed_file(directory, 'report.md', b'interrupted result bytes\n')
        identifier = evidence._start['capture_id']
        with bundle.Selection(root, os.geteuid(), os.getegid(), [], [], [],
                              captures=[identifier]) as selection:
            bundle.export(selection, expected=selection.selection_sha256)
    request = capture.inspect_capture(root, os.geteuid(), os.getegid(), identifier)
    with pytest.raises(ValueError, match='exact terminal closure'):
        capture.acknowledge_capture(root, os.geteuid(), os.getegid(), identifier,
                                    expected=request['request_sha256'])
    for _ in range(2):
        with store.session():
            pass
    with pytest.raises(ValueError, match='verified acknowledgement'):
        with store.session():
            pass
    assert original.read_bytes() == b'interrupted result bytes\n'


def test_coverage_terminal_retains_declared_outputs_through_rotation(environment):
    root, store = environment
    with store.session():
        report = regression.Report(root)
        run = regression.Run(root, report, regression.Control(), host_only=True)
        item = regression.Category('coverage', total=1, retry_category='coverage')
        run.categories = [item]
        run.dashboard.categories = run.categories
        output = allocate()
        payloads = {'coverage.xml': b'<coverage original="true"/>', '.coverage': b'original coverage database'}
        for name, value in payloads.items():
            closed_file(output, name, value)
        execution = regression.Execution(run, item, command=['tools/run-tests', 'coverage'])
        execution.output(('run-tests: output=' + str(output) + '\n').encode())
        execution.finish(0)
        report.close(defer_capture=True)
        proof = report.finalize(categories=run.categories, status='passed', cleanup='complete')
    for _ in range(5):
        with store.session():
            pass
    assert not output.exists()
    for name, value in payloads.items():
        member = next(member for member in proof['records'][-1]['members']
                      if member['original_path'] == str(output / name))
        assert runner.resolve_reference(root, exact_reference(proof, member)) == value


def test_capture_recovery_keeps_existing_interrupted_initial_checks_route(environment, monkeypatch):
    root, store = environment
    with store.session():
        parent = storage.directory('reports', root=root)
        report = Path(retention.allocate(tempfile.mkdtemp, prefix='onpc-initial-checks-', dir=parent))
        closed_file(report, 'progress.json', json.dumps([
            dict(name='Discovery and prerequisites', state='Passed'),
            dict(name='Cleanup safety prerequisites', state='Running'),
            dict(name='Later checks', state='Pending', done=0, failures=0, started=None),
        ]).encode())
    with store.opened() as fd, store.locked(fd, 'writer.lock'):
        state = store.read(fd)
        previous_run = state['run']
        state['finished'] = False  # Simulate the existing dead initial-check owner.
        store.save(fd, state)
    import test_activity
    monkeypatch.setattr(test_activity, 'descriptors', lambda: (123,))
    monkeypatch.setattr(test_activity, 'retention_path', lambda root: store.path)
    called = []
    def admitted(*args, **kwargs):
        called.append(retention.token())
        return 0
    monkeypatch.setattr(regression, 'retained_main', admitted)
    assert regression.main(root, host_only=True) == 0
    assert len(called) == 1 and called[0] != previous_run
    assert report.exists()


def test_recovery_empty_directories_consume_one_cumulative_inventory_bound(environment):
    root, store = environment
    with store.session():
        directory = allocate()
        runner.ReportEvidence(root, directory)
        for branch in ('first', 'second'):
            parent = directory / branch
            parent.mkdir(mode=0o700)
            for index in range(2050):
                (parent / str(index)).mkdir(mode=0o700)
    with pytest.raises(ValueError, match='entry bound'):
        runner.recover_pending(root, store)
    assert directory.exists()


@pytest.mark.parametrize('failure', ['permissions', 'changed', 'interrupted'])
def test_start_lifecycle_preserves_preseal_failures_across_all_retirement_routes(
        environment, monkeypatch, failure):
    root, store = environment
    with store.session():
        directory = allocate()
        evidence = runner.ReportEvidence(root, directory)
        report = closed_file(directory, 'report.md', b'original result bytes\n')
        evidence.command(command())
        with monkeypatch.context() as local:
            if failure == 'permissions':
                report.chmod(0o620)
                expected_error = ValueError
            elif failure == 'changed':
                real_hash = capture._hash
                def changed(fd, size, output=None):
                    value = real_hash(fd, size, output)
                    report.write_bytes(b'changed original bytes\n')
                    return value
                local.setattr(capture, '_hash', changed)
                expected_error = ValueError
            else:
                real_member = evidence._member
                def interrupted(path, role):
                    if Path(path) == report:
                        raise KeyboardInterrupt('interrupted before terminal intent')
                    return real_member(path, role)
                local.setattr(evidence, '_member', interrupted)
                expected_error = KeyboardInterrupt
            with pytest.raises(expected_error):
                finish(evidence, members=[dict(path=report, role='result')])
        report.chmod(0o600)
        assert evidence._prepared is None
        state = json.loads((store.path / 'current.json').read_bytes())
        assert len(state['captures']) == 1
        start = state['captures'][0]
        assert start['intent']['record']['context']['check'] == 'report-start'
        assert start['intent']['record']['status'] == 'diagnostic'
        assert not start.get('acknowledgement')
        saved = report.read_bytes()
    before = (store.path / 'current.json').read_bytes()
    real_bytes = retention.allocation_bytes
    def oversized(record, **kwargs):
        return retention.MAX_RETAINED_BYTES + 1 if Path(record['path']) == directory else real_bytes(record, **kwargs)
    with monkeypatch.context() as local:
        local.setattr(retention, 'allocation_bytes', oversized)
        with store.opened() as fd, store.retirement(fd) as authorize, store.locked(fd, 'writer.lock'):
            state = store.read(fd)
            with pytest.raises(ValueError, match='capture|acknowledgement'):
                store.prune(fd, state, completed_guard=lambda paths: pytest.fail('retired pending source'),
                            authorize=authorize)
        with pytest.raises(ValueError, match='capture|acknowledgement'):
            store.reconcile(lambda: None,
                completed_guard=lambda paths: pytest.fail('reconciled pending source'))
    assert (store.path / 'current.json').read_bytes() == before
    assert report.read_bytes() == saved
    for _ in range(2):
        with store.session():
            pass
    with pytest.raises(ValueError, match='capture|acknowledgement'):
        with store.session():
            pass
    assert report.read_bytes() == saved


def test_inherited_invocation_is_immutable_provenance_under_live_owner(environment, monkeypatch):
    root, store = environment
    invocation = dict(batch='batch-id', worker='worker-id', target='ubuntu',
                      guest_args=['--category', 'unit', '--test', 'exact_case'])
    monkeypatch.setenv('ONPC_RUNNER_INVOCATION', json.dumps(invocation))
    with store.session():
        evidence = runner.ReportEvidence(root, allocate())
        monkeypatch.setenv('ONPC_RUNNER_INVOCATION', json.dumps(dict(worker='replacement')))
        result = finish(evidence)
    start, aggregate = result['records']
    startup = json.loads(runner.resolve_reference(root, exact_reference(result, start['members'][0])))
    assert startup['invocation'] == invocation
    assert startup['owner'] == start['context']['owner']
    assert startup['run'] == start['context']['run']
    member = next(member for member in aggregate['members']
                  if member['role'] == 'input'
                  and member['sha256'] == aggregate['context']['inputs_sha256'])
    inputs = json.loads(runner.resolve_reference(root, exact_reference(result, member)))
    assert inputs['invocation'] == invocation


def test_lost_preseal_object_recovers_original_run_without_rewriting_failed_attempt(
        environment, monkeypatch):
    root, store = environment
    old_command = command(status='failed', cleanup='failed', exit_status=1,
                          failed_ids=['test_module.py::exact_case'])
    with store.session() as original_run:
        directory = allocate()
        evidence = runner.ReportEvidence(root, directory)
        report = closed_file(directory, 'report.md', b'original failed attempt\n')
        inventory = closed_file(directory, 'inventory-001.json', b'["exact-case"]')
        evidence.command(old_command)
        start = evidence._start['record']
        member = evidence._member
        def before_seal(path, role):
            if Path(path) == report:
                raise ValueError('lost before terminal source hashing')
            return member(path, role)
        with monkeypatch.context() as local:
            local.setattr(evidence, '_member', before_seal)
            with pytest.raises(ValueError, match='lost before'):
                finish(evidence, status='failed', cleanup='failed',
                    members=[dict(path=report, role='result'), dict(path=inventory, role='input')])
        del evidence
    recovered, = runner.recover_pending(root, store)
    assert json.loads((store.path / 'current.json').read_bytes())['run'] == original_run
    assert recovered['records'][0] == start
    terminal = recovered['records'][-1]
    assert terminal['status'] == 'interrupted'
    assert terminal['completeness'] == 'partial'
    assert terminal['cleanup']['state'] == 'pending'
    assert terminal['context']['run'] == original_run
    command_member = next(member for member in terminal['members'] if member['role'] == 'command'
                          and Path(member['original_path']).name.endswith('-command.json'))
    payload = json.loads(runner.resolve_reference(root, exact_reference(recovered, command_member)))
    assert payload['commands'] == [old_command]
    expected = {member['member_id']: Path(member['original_path']).read_bytes()
                for record in recovered['records'] for member in record['members']}
    assert runner.recover_pending(root, store) == []
    for _ in range(5):
        with store.session():
            pass
    assert not directory.exists()
    for record in recovered['records']:
        for member in record['members']:
            assert runner.resolve_reference(root, exact_reference(recovered, member)) == expected[member['member_id']]


def test_lost_publication_reply_recovers_same_capture_attempts_and_stage(environment, monkeypatch):
    root, store = environment
    with store.session():
        directory = allocate()
        report = closed_file(directory, 'report.md', b'failed terminal already registered')
        evidence = runner.ReportEvidence(root, directory)
        evidence.command(command(status='failed', exit_status=1))
        def interrupt(stage):
            if stage == 'publication.copied':
                raise KeyboardInterrupt('lost publication process')
        with monkeypatch.context() as local:
            local.setattr(runner.publication, 'checkpoint', interrupt)
            with pytest.raises(KeyboardInterrupt, match='lost publication'):
                finish(evidence, status='failed', members=[dict(path=report, role='result')])
        original = json.loads((store.path / 'current.json').read_bytes())['captures']
        parent = bundle.plan_parent(root, runner.publication._namespace(original[0]['intent']))
        publication_state = json.loads((parent / 'retention' / 'capture-publication.json').read_bytes())
        stage = publication_state['pending']['allocation']
        del evidence
    recovered, = runner.recover_pending(root, store)
    assert set(recovered['capture_ids']) == {charge['capture_id'] for charge in original}
    assert recovered['records'] == [charge['intent']['record'] for charge in original]
    assert recovered['records'][-1]['status'] == 'failed'
    assert Path(recovered['receipt']['path']).parent == Path(stage['path'])
    assert all(charge.get('acknowledgement') for charge in
               json.loads((store.path / 'current.json').read_bytes())['captures'])


def test_targeted_terminal_retains_original_attempt_dependency_and_live_cleanup_scope(environment):
    root, store = environment
    resources = [dict(kind='maintenance', id='selected-target', disposition='preserved')]
    commands = [dict(argv=['fixed-probe', '--samples', '2'], timeout=60,
                     check=False, exit_status=1)]
    with store.session():
        first = runner.ReportEvidence(root, allocate(), workflow='qualification')
        original = finish(first, target='ubuntu', check='original-attempt',
                          status='diagnostic', cleanup='pending', cleanup_resources=resources,
                          command_log=commands)
        later = runner.ReportEvidence(root, allocate(), workflow='qualification')
        recovered = finish(later, target='ubuntu', check='recovery',
                           dependencies=original['records'], cleanup_resources=[
                               dict(kind='maintenance', id='selected-target', disposition='cleaned')])
    terminal = original['records'][-1]
    assert terminal['context']['target'] == 'ubuntu'
    assert terminal['context']['check'] == 'original-attempt'
    assert terminal['status'] == 'diagnostic'
    assert terminal['cleanup']['scope']['resources'] == resources
    command_member = next(member for member in terminal['members'] if member['role'] == 'command')
    assert json.loads(runner.resolve_reference(root, exact_reference(original, command_member))) == {
        'commands': commands}
    final = recovered['records'][-1]
    assert final['context']['check'] == 'recovery'
    assert {item['record_id'] for item in final['dependencies']} == {
        original['records'][-1]['record_id'], recovered['records'][0]['record_id']}
    for _ in range(5):
        with store.session():
            pass
    for result in (original, recovered):
        for record in result['records']:
            for member in record['members']:
                saved = runner.resolve_reference(root, exact_reference(result, member))
                assert hashlib.sha256(saved).hexdigest() == member['sha256']


def test_targeted_terminal_recovery_keeps_exact_context_and_cleanup_resources(environment, monkeypatch):
    root, store = environment
    resources = [dict(kind='maintenance', id='selected-target', disposition='preserved')]
    with store.session():
        evidence = runner.ReportEvidence(root, allocate(), workflow='qualification')
        def interrupted(stage):
            if stage == 'publication.copied':
                raise KeyboardInterrupt('targeted publication interrupted')
        with monkeypatch.context() as local:
            local.setattr(runner.publication, 'checkpoint', interrupted)
            with pytest.raises(KeyboardInterrupt, match='targeted publication'):
                finish(evidence, target='fedora', check='diagnostic-check', status='diagnostic',
                       cleanup='pending', cleanup_resources=resources)
        original = evidence._prepared[-1]['record']
    recovered, = runner.recover_pending(root, store)
    assert recovered['records'][-1] == original
    assert original['context']['target'] == 'fedora'
    assert original['context']['check'] == 'diagnostic-check'
    assert original['cleanup']['scope']['resources'] == resources


def test_checkpoint_identity_is_rechecked_after_sealing_before_publication(environment, monkeypatch):
    root, store = environment
    with store.session():
        directory = allocate()
        original = closed_file(directory, 'proof.json', b'original immutable proof')
        evidence = runner.ReportEvidence(root, directory)
        evidence.checkpoint_members([dict(path=original, role='result')])
        member = evidence._member
        swapped = False
        def replace_after_hash(path, role):
            nonlocal swapped
            result = member(path, role)
            if Path(path) == original and not swapped:
                swapped = True
                replacement = closed_file(directory, 'replacement.json', original.read_bytes())
                replacement.replace(original)
            return result
        monkeypatch.setattr(evidence, '_member', replace_after_hash)
        monkeypatch.setattr(bundle, 'export', lambda *args, **kwargs: pytest.fail('changed proof published'))
        with pytest.raises(ValueError, match='checkpointed source identity changed'):
            finish(evidence, members=[dict(path=original, role='result')])
        assert original.read_bytes() == b'original immutable proof'
        state = json.loads((store.path / 'current.json').read_bytes())
        assert state['captures'] and all(not item.get('acknowledgement') for item in state['captures'])


def test_recovery_without_terminal_declaration_preserves_closed_coverage_outputs(environment):
    root, store = environment
    with store.session():
        report = regression.Report(root)
        run = regression.Run(root, report, regression.Control(), host_only=True)
        category = regression.Category('coverage', total=1, retry_category='coverage')
        run.categories = [category]
        run.dashboard.categories = run.categories
        output = allocate()
        originals = {'coverage.xml': b'<coverage original="yes"/>', '.coverage': b'exact database'}
        for name, value in originals.items():
            closed_file(output, name, value)
        execution = regression.Execution(run, category, command=['tools/run-tests', 'coverage'])
        execution.output(('run-tests: output=' + str(output) + '\n').encode())
        execution.finish(0)
        report.close(defer_capture=True)
        directory = report.directory
        del execution, report, run
    recovered, = runner.recover_pending(root, store)
    assert recovered['records'][-1]['status'] == 'interrupted'
    for _ in range(5):
        with store.session():
            pass
    assert not directory.exists() and not output.exists()
    for name, value in originals.items():
        member = next(member for member in recovered['records'][-1]['members']
                      if member['original_path'] == str(output / name))
        assert runner.resolve_reference(root, exact_reference(recovered, member)) == value


@pytest.mark.parametrize('change', ['replaced', 'foreign'])
def test_recovery_refuses_replaced_report_or_foreign_declared_members(environment, change):
    root, store = environment
    with store.session():
        directory = allocate()
        evidence = runner.ReportEvidence(root, directory)
        report = closed_file(directory, 'report.md', b'preserve pending report')
        if change == 'foreign':
            foreign = closed_file(root, 'foreign-result', b'not an owned allocation')
            with pytest.raises(ValueError, match='live owned allocation'):
                finish(evidence, members=[dict(path=report, role='result'),
                                          dict(path=foreign, role='result')])
    if change == 'replaced':
        directory.rename(directory.with_name(directory.name + '-preserved'))
        directory.mkdir(mode=0o700)
        report = closed_file(directory, 'report.md', b'replacement must not be adopted')
    saved = report.read_bytes()
    with pytest.raises(ValueError, match='allocation|changed|replaced'):
        runner.recover_pending(root, store)
    assert report.read_bytes() == saved
    state = json.loads((store.path / 'current.json').read_bytes())
    assert all(not charge.get('acknowledgement') for charge in state['captures'])


def test_recovery_noop_and_active_or_marked_owner_refusals(environment):
    root, store = environment
    assert runner.recover_pending(root, store) == []
    assert not store.path.exists()
    with store.session():
        assert not json.loads((store.path / 'current.json').read_bytes()).get('captures')
        with pytest.raises(ValueError, match='another owner'):
            runner.recover_pending(root, store)
    before = (store.path / 'current.json').read_bytes()
    assert runner.recover_pending(root, store) == []
    assert (store.path / 'current.json').read_bytes() == before
    closed_file(store.path, 'recovery-required', b'existing public recovery must run first')
    with pytest.raises(ValueError, match='finished, unmarked'):
        runner.recover_pending(root, store)
    assert (store.path / 'current.json').read_bytes() == before
