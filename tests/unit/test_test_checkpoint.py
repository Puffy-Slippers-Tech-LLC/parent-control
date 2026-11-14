"""Resume preserves passes and retries failures without trusting in-flight work.

All state and subprocess outputs are private pytest trees. The only real child
is a synchronously waited pytest with synthetic cases; there are no live VMs,
model sessions, displays, cleanup owners or shared launcher files.
"""

import json
import os
import subprocess
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import regression
import regression_events
import regression_selection
import test_commands
from test_checkpoint import Checkpoint, PassCheckpoint, EXCLUDE, ONLY
from tests.support.paths import ROOT


def pass_work(*cases):
    return dict(category='system', options=['--area', 'authorization'],
                cases=list(cases), case=cases[-1], area=True)


def pass_evidence(assignment, passed, **values):
    return dict(assignment, passed=passed, cleanup=True, diagnostic=False, **values)


def test_pass_credit_belongs_to_exact_attempt_and_family_after_cleanup(tmp_path):
    work = pass_work('authorization::first', 'authorization::last')
    pool = {'one': 'deb', 'two': 'deb', 'three': 'rpm'}
    families = {family: [work] for family in ('deb', 'rpm')}
    selection = [('system', work['options'])]
    with PassCheckpoint(tmp_path, selection, pool, families) as checkpoint:
        assignment = checkpoint.claim('deb', 'one', work, {'digest': 'a' * 64, 'generation': 0})
        assert checkpoint.pending('deb') == []
        assert checkpoint.claim('deb', 'two', work, 'a' * 64) is None
        evidence = pass_evidence(assignment, work['cases'])
        original = json.dumps(checkpoint.state, sort_keys=True)
        for field, value in [('attempt', '0' * 32), ('vm', 'two'), ('source', 'b' * 64),
                             ('selection', []), ('diagnostic', True)]:
            with pytest.raises(ValueError, match='evidence'):
                checkpoint.accept(assignment, dict(evidence, **{field: value}), 0)
            assert json.dumps(checkpoint.state, sort_keys=True) == original
        assert not checkpoint.accept(assignment, dict(evidence, cleanup=False), 0)
        assert checkpoint.passed('deb', 'system') == set()
        # Preemption retains only finished cases, including the group's last
        # case if it really finished; it never invents a failed target.
        assert not checkpoint.accept(assignment, dict(evidence, passed=[work['cases'][-1]]),
                                     130, interrupted=True)
        assert checkpoint.passed('deb', 'system') == {work['cases'][-1]}
        checkpoint.recover(assignment, cleanup=True)
        assignment = checkpoint.claim('deb', 'two', work, {'digest': 'a' * 64, 'generation': 0})
        evidence = pass_evidence(assignment, work['cases'])
        assert checkpoint.accept(assignment, evidence, 0)
        assert checkpoint.passed('deb', 'system') == set(work['cases'])
        assert checkpoint.passed('rpm', 'system') == set()
        assert checkpoint.pending('rpm') == [work]
        checkpoint.state['host_complete'] = True
        checkpoint.save()
        identity = checkpoint.state['run'], checkpoint.state['pass']
    with PassCheckpoint(tmp_path, selection, pool, families, resume=True) as checkpoint:
        assert (checkpoint.state['run'], checkpoint.state['pass']) == identity
        assert checkpoint.state['host_complete']
        assert checkpoint.pending('deb') == []
        assert checkpoint.pending('rpm') == [work]
        with pytest.raises(ValueError, match='stale'):
            checkpoint.accept(assignment, evidence, 0)
    with pytest.raises(ValueError, match='selection differs'):
        with PassCheckpoint(tmp_path, selection, {'three': 'rpm'}, {'rpm': [work]}, resume=True):
            pass


def test_pass_scopes_preserve_independent_repair_resume_and_guard_bindings(tmp_path):
    from test_checkpoint import GroupCheckpoint, family_claims_pending, guard_scheduling_checkpoints

    host_selection = [['_host', ['static']]]
    work = pass_work('authorization::selected')
    with PassCheckpoint(tmp_path, host_selection, {}, {}, scope='repair-host') as host:
        host.state['host_complete'] = True
        host.save()
        host_identity = host.state['run'], host.state['pass']
        with pytest.raises(ValueError, match='another checkpoint scope'):
            with PassCheckpoint(tmp_path, host_selection, {}, {}, scope='repair-vm',
                                identity=dict(zip(('run', 'pass'), host_identity))):
                pass
        with PassCheckpoint(tmp_path, [('system', work['options'])], {'one': 'deb'},
                            {'deb': [work]}, scope='repair-vm') as guests:
            claim = guests.claim('deb', 'one', work, 'a' * 64)
            guests.enqueue_failure(claim, pass_evidence(claim, []), 1)
            guest_identity = {key: guests.state[key] for key in ('run', 'pass')}
            guest_selection = guests.state['selection']
            guest_state = json.loads(json.dumps(guests.state))
            with PassCheckpoint(tmp_path, host_selection, {}, {}) as ordinary:
                assert ordinary.store.path != host.store.path != guests.store.path
                assert family_claims_pending(tmp_path, 'one') == 1
                guard_scheduling_checkpoints(tmp_path)
    with PassCheckpoint(tmp_path, host_selection, {}, {}):
        pass  # A fresh ordinary pass must not replace either repair owner.
    with PassCheckpoint(tmp_path, host_selection, {}, {}, scope='repair-host', resume=True) as host:
        assert (host.state['run'], host.state['pass']) == host_identity
        assert host.state['host_complete']
        with PassCheckpoint.saved(tmp_path, scope='repair-vm') as guests:
            assert guests.claims() == [claim]
        invalid = dict(host.state, scope='repair-vm')
        with pytest.raises(ValueError, match='identity or selection'):
            PassCheckpoint.validate(invalid, scope='repair-host')

    # A pre-group repair resumes its exact owner in place; it cannot adopt a
    # different selection, identity, pool or a newly split multi-group request.
    groups = [dict(key='system', category='system', args=['system', *work['options']],
                   vm_tag='general', vms=['one'])]
    options = dict(resume=True, identity=guest_identity, scope='repair-vm',
                   ungrouped_selection=guest_selection)
    for changed in (dict(identity=dict(run='1' * 32, **{'pass': '2' * 32})),
                    dict(ungrouped_selection=[])):
        with pytest.raises(ValueError, match='selection differs'):
            with GroupCheckpoint(tmp_path, groups, ['one'], **dict(options, **changed)):
                pass
    for requested_groups, pool in ((groups, []),
                                   ([dict(groups[0], vms=[])], ['one']),
                                   ([*groups, dict(groups[0], key='other')], ['one'])):
        with pytest.raises(ValueError, match='selection differs'):
            with GroupCheckpoint(tmp_path, requested_groups, pool, **options):
                pass
    with pytest.raises(ValueError, match='unfinished owners'):
        with GroupCheckpoint(tmp_path, groups, ['one'], scope='repair-vm'):
            pass
    for _ in range(2):
        with GroupCheckpoint(tmp_path, groups, ['one'], **options) as saved:
            assert saved.group_identity(0) == guest_identity
            assert saved.group_scope(0) == 'repair-vm'
            assert saved.state['workers'] == [['one']]
        with PassCheckpoint.saved(tmp_path, scope='repair-vm') as guests:
            assert guests.state == guest_state


def test_pass_failed_target_stays_on_original_vm_until_owned_recovery(tmp_path, monkeypatch):
    import test_activity
    from contextlib import nullcontext
    from test_checkpoint import family_claims_pending, recover_family_claims
    work = pass_work('authorization::first', 'authorization::last')
    overlapping = dict(work, options=['--area', 'authorization', '--test', 'last'])
    selection = [('system', [])]
    pool, families = {'one': 'deb', 'two': 'deb'}, {'deb': [work, overlapping]}
    with PassCheckpoint(tmp_path, selection, pool, families) as checkpoint:
        assignment = checkpoint.claim('deb', 'one', work, 'a' * 64)
        assert checkpoint.claim('deb', 'two', overlapping, 'a' * 64) is None
        assert not checkpoint.accept(assignment, pass_evidence(assignment, work['cases']), 1)
        assert checkpoint.passed('deb', 'system') == {work['cases'][0]}
        assert checkpoint.claims() == [assignment]
        assert family_claims_pending(tmp_path, 'one') == 1
        monkeypatch.setattr(test_activity, 'exclusive_vm_progress', nullcontext)
        with pytest.raises(ValueError, match='another owner'):
            recover_family_claims(tmp_path, 'one')
    with pytest.raises(ValueError, match='uncertain claims'):
        with PassCheckpoint(tmp_path, selection, pool, families):
            pass
    assert recover_family_claims(tmp_path, 'two') == 0
    assert family_claims_pending(tmp_path, 'one') == 1
    assert recover_family_claims(tmp_path, 'one') == 1
    with PassCheckpoint(tmp_path, selection, pool, families, resume=True) as checkpoint:
        assert checkpoint.passed('deb', 'system') == {work['cases'][0]}
        retried = checkpoint.claim('deb', 'two', work, 'a' * 64)
        assert retried['attempt'] != assignment['attempt']
        assert retried['assignment'] != assignment['assignment']
        assert retried['run'] == assignment['run']
        checkpoint.recover(retried, cleanup=True)


def test_pass_failure_fifo_keeps_exact_attempts_without_accepting_them(tmp_path):
    first, second = pass_work('authorization::first'), pass_work('authorization::second')
    selection, pool, families = [('system', [])], {'one': 'deb', 'two': 'deb'}, {'deb': [first, second]}
    source = dict(digest='a' * 64, generation=0)
    with PassCheckpoint(tmp_path, selection, pool, families) as checkpoint:
        assert 'repairs' not in checkpoint.state
        assignment = checkpoint.claim('deb', 'one', first, source)
        other = checkpoint.claim('deb', 'two', second, source)
        evidence = pass_evidence(assignment, [], command=['never', 'persist', 'this'])
        original = json.dumps(checkpoint.state, sort_keys=True)
        with pytest.raises(ValueError, match='evidence'):
            checkpoint.enqueue_failure(assignment, dict(evidence, attempt=other['attempt']), 1)
        with pytest.raises(ValueError, match='evidence'):
            checkpoint.enqueue_failure(assignment, dict(evidence, diagnostic=True), 1)
        with pytest.raises(ValueError, match='outside'):
            checkpoint.enqueue_failure(assignment, evidence, 1, case='authorization::unselected')
        assert json.dumps(checkpoint.state, sort_keys=True) == original
        ticket = checkpoint.enqueue_failure(assignment, evidence, 1)
        assert checkpoint.enqueue_failure(assignment, evidence, 1) == ticket
        for execution in (dict(first, cases=[], case=None, area=False),
                          dict(first, case=None, area=False)):
            with pytest.raises(ValueError, match='one exact case'):
                checkpoint.begin_attempt(ticket['id'], 'verification', source, execution)
        unfinished = dict(pass_evidence(other, []), cleanup=False)
        later = checkpoint.enqueue_failure(other, unfinished, 2)
        assert [item['id'] for item in checkpoint.repair_tickets()] == [ticket['id'], later['id']]
        assert ticket['id'] != ticket['transaction']
        assert {field: ticket[field] for field in assignment} == assignment
        assert 'command' not in ticket
        assert checkpoint.passed('deb', 'system') == set()
        assert checkpoint.claims() == [assignment, other]
        checkpoint.recover(assignment, cleanup=True)
        checkpoint.recover(other, cleanup=True)
    with pytest.raises(ValueError, match='pending repairs'):
        with PassCheckpoint(tmp_path, selection, pool, families):
            pass
    with PassCheckpoint(tmp_path, selection, pool, families, resume=True) as checkpoint:
        assert checkpoint.repair_tickets() == [ticket, later]
        assert checkpoint.repair_tickets()[0]['vm'] == 'one'
        assert checkpoint.pending('deb') == [first, second]
        with pytest.raises(ValueError, match='stale'):
            checkpoint.enqueue_failure(assignment, evidence, 1)


def test_vm_repair_pass_keeps_captured_source_after_checkout_changes(tmp_path):
    work = dict(pass_work('authorization::first'), area=False)
    original = dict(digest='a' * 64, generation=0)
    incoming = dict(digest='b' * 64, generation=1)
    with PassCheckpoint(tmp_path, [('system', [])], {'one': 'deb'}, {'deb': [work]}) as checkpoint:
        assignment = checkpoint.claim('deb', 'one', work, original)
        ticket = checkpoint.enqueue_failure(assignment, pass_evidence(assignment, []), 1)
        reference = checkpoint.begin_attempt(ticket['id'], 'recheck', original, work)
        attempt = dict(assignment, attempt=reference['attempt'], execution=work)
        result = checkpoint.finish_attempt(ticket['id'], reference,
            pass_evidence(attempt, work['cases']), 0, source=incoming)
        assert result['accepted'] and result['source'] == original
        checkpoint.settle_repair(ticket['id'], 'resolved', reference=result)
        assert checkpoint.passed('deb', 'system') == set(work['cases'])
        PassCheckpoint.validate(checkpoint.state)


def test_pass_retained_attempts_keep_exact_case_bounds(tmp_path):
    work = pass_work('authorization::first', 'authorization::last')
    source = dict(digest='a' * 64, generation=0)
    with PassCheckpoint(tmp_path, [('system', [])], {'one': 'deb'}, {'deb': [work]}) as checkpoint:
        assignment = checkpoint.claim('deb', 'one', work, source)
        ticket = checkpoint.enqueue_failure(assignment, pass_evidence(assignment, []), 1)
        target = dict(work, case=work['cases'][0], cases=work['cases'][:1], area=False)
        checkpoint.begin_attempt(ticket['id'], 'verification', source, target)
        for invalid in (dict(target, cases=[], case=None), dict(target, case=None), work):
            saved = json.loads(json.dumps(checkpoint.state))
            saved['repairs'][0]['attempts'][0]['execution'] = invalid
            with pytest.raises(ValueError, match='one exact case'):
                PassCheckpoint.validate(saved)
    command = dict(category='static', options=[], cases=[], case=None, area=False)
    with PassCheckpoint(tmp_path / 'command', [['_host', ['static']]], {}, {}) as checkpoint:
        ticket = checkpoint.host_failure(command, source, 1)
        checkpoint.begin_attempt(ticket['id'], 'verification', source, command)
        PassCheckpoint.validate(checkpoint.state)


def test_pass_retired_failure_keeps_ownership_and_only_credits_selected_replacement(tmp_path, monkeypatch):
    import sys
    retired = dict(category='system', options=['--area', 'authorization'],
                   cases=['check_retired', 'check_removed'], case='check_removed', area=False)
    replacement = dict(retired, cases=['check_current'], case='check_current')
    source = dict(digest='a' * 64, generation=0)
    selection, pool = [('system', ['--area', 'authorization'])], {'original': 'deb'}
    with PassCheckpoint(tmp_path, selection, pool, {'deb': [retired]}) as checkpoint:
        original = checkpoint.claim('deb', 'original', retired, source)
        ticket = checkpoint.enqueue_failure(original, pass_evidence(original, []), 1)
    monkeypatch.setitem(sys.modules, 'system_case_ids', SimpleNamespace(
        UNBOUND_CASES={1: ('retired',)},
        identity_for_event=lambda case: SimpleNamespace(numeric_id=1) if case == 'check_retired' else None))
    with PassCheckpoint(tmp_path, selection, pool, {'deb': [replacement]}, resume=True) as checkpoint:
        assert checkpoint.claims() == [original]
        assert checkpoint.repair_tickets()[0]['work'] == retired
        assert checkpoint.pending('deb') == [replacement]
        with pytest.raises(ValueError, match='current original selection'):
            checkpoint.begin_attempt(ticket['id'], 'recheck', source, dict(retired, cases=['check_removed']))
        reference = checkpoint.begin_attempt(ticket['id'], 'recheck', source, replacement)
        assignment = {field: ticket[field] for field in (
            'run', 'pass', 'selection', 'family', 'vm', 'work', 'assignment')}
        assignment.update(attempt=reference['attempt'], source=source, execution=replacement)
        accepted = checkpoint.finish_attempt(ticket['id'], reference,
            pass_evidence(assignment, ['check_current']), 0, source=source)
        assert accepted['accepted']
        checkpoint.settle_repair(ticket['id'], 'resolved', reference=accepted)
        assert checkpoint.claims() == []
        assert checkpoint.passed('deb', 'system') == {'check_current'}
        assert checkpoint.pending('deb') == []
    with PassCheckpoint(tmp_path, selection, pool, {'deb': [replacement]}, resume=True) as checkpoint:
        assert checkpoint.passed('deb', 'system') == {'check_current'}
        assert checkpoint.state['repairs'][0]['work'] == retired


def test_pass_impact_requires_current_source_and_evidence_without_completion_credit(tmp_path):
    work = pass_work('authorization::first')
    selection, pool, families = [('system', [])], {'one': 'deb'}, {'deb': [work]}
    original_source = dict(digest='a' * 64, generation=0)
    current_source = dict(digest='b' * 64, generation=1, inputs={'fixture': 'f' * 64})
    decision = dict(impact='no', reason='Only the selected private fixture failed.',
                    scope=['selected case'], evidence=['Private fixture output'], classification='test_issue')
    digest = 'c' * 64
    with PassCheckpoint(tmp_path, selection, pool, families) as checkpoint:
        assignment = checkpoint.claim('deb', 'one', work, original_source)
        ticket = checkpoint.enqueue_failure(assignment, pass_evidence(assignment, []), 1)
        assert checkpoint.impact(ticket['id'], source=current_source, evidence_digest=digest)['impact'] == 'unsure'
        with pytest.raises(ValueError, match='positive scoped evidence'):
            checkpoint.record_impact(ticket['id'], dict(decision, evidence=[]),
                                     source=current_source, evidence_digest=digest)
        binding = checkpoint.record_impact(ticket['id'], decision, source=current_source, evidence_digest=digest)
        assert binding['ticket'] == ticket['id'] and binding['attempt'] == assignment['attempt']
        assert checkpoint.impact(ticket['id'], source=current_source, evidence_digest=digest) == decision
        for changed_source, changed_digest in (
                (dict(current_source, digest='d' * 64), digest),
                (dict(current_source, generation=2), digest),
                (dict(current_source, generation=True), digest),
                (dict(current_source, inputs={'fixture': 'g' * 64}), digest),
                (current_source, 'e' * 64)):
            assert checkpoint.impact(ticket['id'], source=changed_source,
                                     evidence_digest=changed_digest)['impact'] == 'unsure'
        assert checkpoint.repair_tickets()[0]['source'] == original_source
        assert checkpoint.claims() == [assignment] and checkpoint.passed('deb', 'system') == set()
        # Impact decisions cannot release claims or accept a failed execution.
        checkpoint.record_impact(ticket['id'], dict(decision, impact='yes'),
                                 source=current_source, evidence_digest=digest)
        checkpoint.record_impact(ticket['id'], dict(decision, impact='unsure'),
                                 source=current_source, evidence_digest=digest)
        assert checkpoint.passed('deb', 'system') == set()
        checkpoint.record_impact(ticket['id'], decision, source=current_source, evidence_digest=digest)
    with PassCheckpoint(tmp_path, selection, pool, families, resume=True) as checkpoint:
        assert checkpoint.impact(ticket['id'], source=current_source, evidence_digest=digest) == decision
        assert checkpoint.repair_tickets()[0]['source'] == original_source
        assert checkpoint.passed('deb', 'system') == set()
        corrupted = json.loads(json.dumps(checkpoint.state))
        corrupted['repairs'][0]['impact']['attempt'] = '0' * 32
        PassCheckpoint.validate(corrupted)
        checkpoint.state = corrupted
        checkpoint.save()
    with PassCheckpoint(tmp_path, selection, pool, families, resume=True) as checkpoint:
        assert checkpoint.repair_tickets()[0]['impact']['attempt'] == '0' * 32
        assert checkpoint.impact(ticket['id'], source=current_source, evidence_digest=digest)['impact'] == 'unsure'
        checkpoint.state['repairs'][0]['impact']['attempt'] = assignment['attempt']
        checkpoint.state['repairs'][0]['impact']['decision']['evidence'] = []
        assert checkpoint.impact(ticket['id'], source=current_source, evidence_digest=digest)['impact'] == 'unsure'
        assert checkpoint.passed('deb', 'system') == set()


def test_pass_resume_adds_standalone_work_and_deduplicates_qualified_cases(tmp_path):
    original = dict(category='system', options=[], cases=['check_first'], case='check_first', area=False)
    repeated = dict(original, options=['check_first'])
    added = dict(original, cases=['check_added'], case='check_added')
    pool = {'one': 'deb'}
    selection = [('_guest', ['system'])]
    with PassCheckpoint(tmp_path, selection, pool, {'deb': [original, original, repeated]}) as checkpoint:
        assignment = checkpoint.claim('deb', 'one', original, 'a' * 64)
        checkpoint.accept(assignment, pass_evidence(assignment, ['check_first']), 0)
        assert checkpoint.pending('deb') == []
    with PassCheckpoint(tmp_path, selection, pool, {'deb': [original, repeated, added]}, resume=True) as checkpoint:
        assert checkpoint.pending('deb') == [added]
        assert checkpoint.passed('deb', 'system') == {'check_first'}
    with pytest.raises(ValueError, match='inventory differs'):
        with PassCheckpoint(tmp_path, selection, pool, {'deb': [added]}, resume=True):
            pass


def test_pass_refuses_legacy_resume_without_relabeling_accepted_progress(tmp_path):
    legacy = Checkpoint(tmp_path, [('system', ['check_first'])],
                        namespace='run-tests-family', binding='legacy-family')
    legacy.event('system', dict(kind='finished', nodeid='check_first'), set())
    legacy.save()
    path = legacy.store.path / legacy.name
    original = path.read_bytes()
    work = dict(category='system', options=['check_first'], cases=['check_first'],
                case='check_first', area=False)
    with pytest.raises(ValueError, match='original supported implementation'):
        with PassCheckpoint(tmp_path, [('system', ['check_first'])], {'one': 'deb'},
                            {'deb': [work]}, resume=True):
            pass
    assert path.read_bytes() == original
    with PassCheckpoint(tmp_path, [('system', ['check_first'])], {'one': 'deb'}, {'deb': [work]}):
        pass
    assert path.read_bytes() == original


def test_pass_preserves_nonoverlapping_legacy_vm_claim(tmp_path):
    legacy = Checkpoint(tmp_path, [('system', ['check_first'])],
                        namespace='run-tests-family', binding='legacy-family')
    legacy.state['queue_claims'] = {'a' * 64: 'occupied'}
    legacy.save()
    path = legacy.store.path / legacy.name
    original = path.read_bytes()
    work = dict(category='system', options=['check_first'], cases=['check_first'],
                case='check_first', area=False)
    with PassCheckpoint(tmp_path, [('system', ['check_first'])], {'free': 'deb'}, {'deb': [work]}):
        pass
    assert path.read_bytes() == original
    with pytest.raises(ValueError, match='original supported implementation'):
        with PassCheckpoint(tmp_path, [('system', ['check_first'])],
                            {'occupied': 'deb'}, {'deb': [work]}):
            pass
    assert path.read_bytes() == original



def event(checkpoint, kind, case, failed=()):
    checkpoint.event('unit', dict(kind=kind, nodeid=case), set(failed))


def test_resume_keeps_only_finished_nonfailed_cases_and_fresh_run_resets(tmp_path):
    selection = [('unit', ['-x'])]
    checkpoint = Checkpoint(tmp_path, selection)
    event(checkpoint, 'finished', 'test.py::passed')
    event(checkpoint, 'failure', 'test.py::failed')
    event(checkpoint, 'finished', 'test.py::failed', ['test.py::failed'])
    checkpoint.finish([])
    resumed = Checkpoint(tmp_path, selection, resume=True)
    assert resumed.passed('unit') == {'test.py::passed'}
    assert not resumed.complete('unit')
    assert Checkpoint(tmp_path, selection).passed('unit') == set()


def test_failed_teardown_revokes_an_earlier_completion(tmp_path):
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    event(checkpoint, 'finished', 'case')
    event(checkpoint, 'failure', 'case')
    assert Checkpoint(tmp_path, [('unit', [])], resume=True).passed('unit') == set()


def test_focused_retry_preserves_other_passes_without_completing_the_category(tmp_path):
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    event(checkpoint, 'finished', 'earlier')
    event(checkpoint, 'finished', 'repaired')
    checkpoint.retry('unit', 'repaired')
    assert checkpoint.passed('unit') == {'earlier'}
    event(checkpoint, 'finished', 'repaired')
    checkpoint.finish([SimpleNamespace(retry_category='unit', count_overall=True, state='Passed')])
    resumed = Checkpoint(tmp_path, [('unit', [])], resume=True)
    assert resumed.passed('unit') == {'earlier', 'repaired'}
    assert not resumed.complete('unit')
    assert resumed.retry_case is None


def test_retry_filter_never_reports_unexecuted_cases_as_resumed(monkeypatch):
    monkeypatch.setenv(ONLY, 'repaired')
    monkeypatch.setenv(EXCLUDE, '["earlier"]')
    items = [SimpleNamespace(nodeid=name) for name in ('earlier', 'repaired', 'remaining')]
    session = SimpleNamespace()
    config = SimpleNamespace(hook=SimpleNamespace(pytest_deselected=Mock()))
    regression_events.pytest_collection_modifyitems(session, config, items)
    assert [item.nodeid for item in items] == ['repaired']
    assert session.onpc_resumed_nodeids == ()
    assert not session.onpc_resume_empty


def test_retry_filter_runs_only_the_case_and_missing_case_is_not_a_pass(tmp_path):
    (tmp_path / 'test_sample.py').write_text(
        'def test_repaired():\n    pass\ndef test_remaining():\n    assert False\n')
    environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                       ONPC_REGRESSION_EVENTS='1', ONPC_REGRESSION_INVENTORY='1')
    environment.pop(EXCLUDE, None)
    command = ['/usr/bin/python3', '-B', '-m', 'pytest', '-p', 'no:cacheprovider',
               '-p', 'tools.regression_events', '--rootdir=.', '-q', 'test_sample.py']
    for case, expected in [('test_repaired', 0), ('test_missing', 5)]:
        environment[ONLY] = 'test_sample.py::' + case
        result = subprocess.run(command, cwd=tmp_path, env=environment,
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == expected, result.stdout + result.stderr
        events = [json.loads(line[len(regression_events.PREFIX):])
                  for line in result.stdout.splitlines() if line.startswith(regression_events.PREFIX)]
        assert [event['nodeid'] for event in events if event['kind'] == 'finished'] == (
            [environment[ONLY]] if expected == 0 else [])


def test_large_resume_checkpoint_batches_passes_but_saves_failure_and_shutdown(
        tmp_path, monkeypatch):
    import test_checkpoint

    clock = [0.0]
    monkeypatch.setattr(test_checkpoint, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    initial = [f'tests/unit/test_sample.py::test_case[{index}-' + 'x' * 200 + ']'
               for index in range(2000)]
    checkpoint.entry('unit')['passed'] = initial
    checkpoint.save()
    saves = []
    save = checkpoint.store.save

    def persist(fd, value, **kwargs):
        saves.append(clock[0])
        return save(fd, value, **kwargs)

    monkeypatch.setattr(checkpoint.store, 'save', persist)
    for index in range(1, 601):
        clock[0] = index / 10
        event(checkpoint, 'finished', f'new-{index}')
    assert saves == list(range(5, 61, 5))
    path = checkpoint.store.path / checkpoint.name
    assert set(json.loads(path.read_text())['categories']['unit']['passed']) == (
        set(initial) | {f'new-{index}' for index in range(1, 601)})

    clock[0] = 60.1
    event(checkpoint, 'failure', initial[0])
    assert saves[-1] == 60.1
    assert initial[0] not in json.loads(path.read_text())['categories']['unit']['passed']
    event(checkpoint, 'finished', 'pending-at-shutdown')
    assert 'pending-at-shutdown' not in json.loads(path.read_text())['categories']['unit']['passed']
    checkpoint.finish([])
    resumed = Checkpoint(tmp_path, [('unit', [])], resume=True)
    assert resumed.passed('unit') == checkpoint.passed('unit')
    assert 'pending-at-shutdown' in resumed.passed('unit')
    assert not resumed.complete('unit')


def test_failed_resume_checkpoint_sync_keeps_pending_passes_for_retry(tmp_path, monkeypatch):
    import test_checkpoint

    clock = [0.0]
    monkeypatch.setattr(test_checkpoint, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    clock[0] = 5

    def broken(*_args, **_kwargs):
        raise OSError('checkpoint sync failed')

    with monkeypatch.context() as local:
        local.setattr(checkpoint.store, 'save', broken)
        with pytest.raises(OSError, match='checkpoint sync failed'):
            event(checkpoint, 'finished', 'first')
    assert checkpoint.dirty and checkpoint.synced == 0
    event(checkpoint, 'finished', 'second')
    assert not checkpoint.dirty
    assert Checkpoint(tmp_path, [('unit', [])], resume=True).passed('unit') == {'first', 'second'}


def test_resume_checks_every_repeated_category_selection(tmp_path):
    selection = [('unit', ['-k', 'first']), ('unit', ['-k', 'second'])]
    checkpoint = Checkpoint(tmp_path, selection)
    event(checkpoint, 'finished', 'passed')
    checkpoint.save()
    assert Checkpoint(tmp_path, selection, resume=True).passed('unit') == {'passed'}
    with pytest.raises(ValueError, match='selection differs'):
        Checkpoint(tmp_path, [('unit', ['-k', 'changed']), selection[1]], resume=True)


@pytest.mark.parametrize('invalid', ['passed', 'round', 'pending'])
def test_changed_selection_does_not_mask_invalid_saved_progress(tmp_path, invalid):
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    if invalid == 'passed':
        checkpoint.entry('unit')['passed'] = [None]
    else:
        checkpoint.state[invalid] = 0 if invalid == 'round' else 'missing-category'
    checkpoint.save()
    path = checkpoint.store.path / checkpoint.name
    original = path.read_bytes()
    with pytest.raises(ValueError, match='invalid resume'):
        Checkpoint(tmp_path, [('ui', [])], resume=True)
    assert path.read_bytes() == original


@pytest.mark.parametrize('replacement', ['symlink', 'hardlink', 'mode', 'malformed'])
def test_checkpoint_refuses_unsafe_or_malformed_state(tmp_path, replacement):
    checkpoint = Checkpoint(tmp_path, [('e2e', [])], binding='guest-one')
    path = checkpoint.store.path / checkpoint.name
    if replacement == 'symlink':
        path.rename(path.with_name('original'))
        path.symlink_to(path.with_name('original'))
    elif replacement == 'hardlink':
        os.link(path, path.with_name('alias'))
    elif replacement == 'mode':
        path.chmod(0o644)
    else:
        path.write_text('{')
    with pytest.raises((ValueError, OSError)):
        Checkpoint(tmp_path, [('system', ['check_first'])], resume=True,
                   binding='guest-one', recover_missing=True)


@pytest.mark.parametrize('resume', [False, True])
def test_incompatible_scheduler_cannot_reset_progress_or_ownership(tmp_path, resume):
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    checkpoint.entry('unit').update(passed=['accepted-case'], complete=True)
    checkpoint.state.update(round=3, pending='unit', queue_claims={'claim': 'original-vm'},
                            source_owner='original-repair', transaction='original-git', charged=7)
    checkpoint.state['scheduling']['version'] += 1
    checkpoint.save()
    original = {path: path.read_bytes() for path in checkpoint.store.path.iterdir() if path.is_file()}
    with pytest.raises(ValueError, match='original supported implementation.*--reset'):
        Checkpoint(tmp_path, [('unit', [])], resume=resume)
    assert {path: path.read_bytes() for path in original} == original


def test_run_cutover_preserves_legacy_claims_transactions_and_charged_admissions(tmp_path, monkeypatch):
    import test_checkpoint
    from detached_launcher import atomic

    child = tmp_path / 'pipeline-owned'
    family = tmp_path / 'family-cases'
    child.mkdir()
    family.mkdir()
    records = {
        tmp_path / 'vm.json': {'vm': {'vms': ['original-vm'], 'concurrency': 1}},
        child / 'checkpoint.json': {'repairs': {'repair': {'source_owner': 'original-source'}},
                                    'pending': 'repair', 'commit_intent': {'commit': 'original-commit'}},
        tmp_path / 'limits.json': {'tasks': 9, 'started': 7, 'completed': 5},
        family / 'retained.json': {'version': 1, 'family': 'original-family', 'completed': ['accepted'],
                                   'claims': {'pending': 'original-vm'}, 'items': {'pending': {}}},
    }
    for path, value in records.items():
        atomic(path, value)
    original = {path: path.read_bytes() for path in records}
    for guard in (test_checkpoint.guard_scheduling_run, test_checkpoint.guard_repair_scheduling_run):
        with pytest.raises(ValueError, match='original supported implementation.*--reset'):
            guard(tmp_path)
    assert {path: path.read_bytes() for path in records} == original

    # Fresh logical admissions have a distinct identity; neither ordinary
    # bounded-worker state nor old family credit may be relabeled as repair state.
    current = tmp_path / 'current'
    current.mkdir()
    marker = test_checkpoint.repair_scheduling_marker()
    atomic(current / 'scheduling.json', marker)
    atomic(current / 'vm.json', {'vm': {'vms': ['original-vm'], 'concurrency': 1}})
    atomic(current / 'limits.json', dict(scheduling=marker, tasks=9, started=2, completed=1,
                                        admissions={'round-1:system': False, 'round-1:unit': True}))
    atomic(current / 'checkpoint.json', dict(scheduling=marker, repairs={}))
    assert test_checkpoint.guard_repair_scheduling_run(current) == marker
    atomic(current / 'limits.json', records[tmp_path / 'limits.json'])
    unchanged = (current / 'limits.json').read_bytes()
    with pytest.raises(ValueError, match='incompatible repair scheduling state'):
        test_checkpoint.guard_repair_scheduling_run(current)
    assert (current / 'limits.json').read_bytes() == unchanged


def test_large_case_inventory_uses_private_snapshot_instead_of_large_environment(tmp_path, monkeypatch):
    # This private checkpoint must not inherit the outer repair run's exclusions.
    monkeypatch.delenv('ONPC_REPAIR_FAILED_CASES', raising=False)
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    cases = ['tests/unit/test_core.py::test_case[' + str(index) + 'x' * 200 + ']'
             for index in range(2000)]
    checkpoint.entry('unit')['passed'] = cases
    checkpoint.save()
    resumed = Checkpoint(tmp_path, [('unit', [])], resume=True)
    value = resumed.environment('unit')
    assert len(value) < 1024
    assert regression_events.completed_cases(value) == set(cases)


def test_oversized_completion_cannot_poison_the_next_retry(tmp_path, monkeypatch):
    # Keep the synthetic retry independent of the outer repair run's exclusions.
    monkeypatch.delenv('ONPC_REPAIR_FAILED_CASES', raising=False)
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    boundary = 'p' * regression_events.MAX_CASE_ID_LENGTH
    oversized = boundary + 'x'
    event(checkpoint, 'finished', boundary)
    event(checkpoint, 'finished', oversized)
    checkpoint.save()
    resumed = Checkpoint(tmp_path, [('unit', [])], resume=True)
    assert resumed.passed('unit') == {boundary}
    assert regression_events.completed_cases(resumed.environment('unit')) == {boundary}


def test_resume_repairs_legacy_oversized_ids_without_resetting_other_passes(tmp_path, monkeypatch):
    # Keep this private checkpoint independent of the outer repair run's exclusions.
    monkeypatch.delenv('ONPC_REPAIR_FAILED_CASES', raising=False)
    selection = [('unit', []), ('static', ['shell'])]
    checkpoint = Checkpoint(tmp_path, selection)
    oversized = 'tests/unit/test_progress.py::test_case[' + 'x' * 120000 + ']'
    checkpoint.entry('unit').update(passed=['valid-pass', oversized], complete=True)
    checkpoint.entry('static')['complete'] = True
    checkpoint.save()
    resumed = Checkpoint(tmp_path, selection, resume=True)
    assert resumed.passed('unit') == {'valid-pass'}
    assert not resumed.complete('unit')
    assert resumed.complete('static')
    assert regression_events.completed_cases(resumed.environment('unit')) == {'valid-pass'}
    saved = json.loads((resumed.store.path / resumed.name).read_text())
    assert saved['categories']['unit']['passed'] == ['valid-pass']
    assert Checkpoint(tmp_path, selection, resume=True).state == saved


@pytest.mark.parametrize('invalid', [None, '', '\n', 123, 'duplicate'])
def test_oversized_recovery_still_refuses_malformed_inventory(tmp_path, invalid):
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    oversized = 'x' * (regression_events.MAX_CASE_ID_LENGTH + 1)
    passed = [oversized, oversized] if invalid == 'duplicate' else [oversized, invalid]
    checkpoint.entry('unit')['passed'] = passed
    checkpoint.save()
    original = (checkpoint.store.path / checkpoint.name).read_bytes()
    with pytest.raises(ValueError, match='invalid resume case inventory'):
        Checkpoint(tmp_path, [('unit', [])], resume=True)
    assert (checkpoint.store.path / checkpoint.name).read_bytes() == original


def test_pytest_resume_snapshot_still_refuses_oversized_ids(tmp_path):
    oversized = 'x' * (regression_events.MAX_CASE_ID_LENGTH + 1)
    with pytest.raises(ValueError, match='invalid resume case inventory'):
        regression_events.completed_cases(json.dumps([oversized]))
    snapshot = tmp_path / 'snapshot.json'
    snapshot.write_text(json.dumps([oversized]))
    snapshot.chmod(0o600)
    with pytest.raises(ValueError, match='invalid resume case inventory'):
        regression_events.completed_cases('@' + str(snapshot))


def test_repair_replay_removes_only_its_case_from_the_resume_snapshot(tmp_path, monkeypatch):
    # Keep this private checkpoint independent of the outer repair run's exclusions.
    monkeypatch.delenv('ONPC_REPAIR_FAILED_CASES', raising=False)
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    checkpoint.entry('unit').update(passed=['previous', 'diagnostic'], complete=True)
    checkpoint.save()
    resumed = Checkpoint(tmp_path, [('unit', [])], resume=True)
    resumed.event('unit', dict(kind='failure', nodeid='diagnostic'), set())
    assert not resumed.complete('unit')
    assert regression_events.completed_cases(resumed.environment('unit')) == {'previous'}


@pytest.mark.parametrize('oversized', [False, True])
@pytest.mark.parametrize('interrupted', [False, True])
def test_real_pytest_resume_retries_failed_or_interrupted_case(tmp_path, interrupted, oversized):
    source = tmp_path / 'test_sample.py'
    source.write_text('''from pathlib import Path
import pytest
def record(name):
    with Path('calls').open('a') as stream:
        stream.write(name + '\\n')
@pytest.mark.parametrize('value', [None], ids=['PASSED_ID'])
def test_passed(value):
    record('passed')
def test_retry():
    record('retry')
    if not Path('fixed').exists():
        EXCEPTION
def test_pending():
    record('pending')
'''.replace('EXCEPTION', 'raise KeyboardInterrupt()' if interrupted else 'assert False')
   .replace('PASSED_ID', 'p' * 70000 if oversized else 'passed'))
    environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                       ONPC_REGRESSION_EVENTS='1', ONPC_REGRESSION_INVENTORY='1')
    environment.pop(EXCLUDE, None)
    command = ['/usr/bin/python3', '-B', '-m', 'pytest', '-p', 'no:cacheprovider',
               '-p', 'tools.regression_events', '-x', '-q', 'test_sample.py']
    first = subprocess.run(command, cwd=tmp_path, env=environment, capture_output=True,
                           text=True, timeout=30)
    assert first.returncode == (2 if interrupted else 1), first.stdout + first.stderr
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    failed = set()
    for line in first.stdout.splitlines():
        if line.startswith(regression_events.PREFIX):
            value = json.loads(line[len(regression_events.PREFIX):])
            if value['kind'] == 'failure':
                failed.add(value['nodeid'])
            checkpoint.event('unit', value, failed)
    checkpoint.finish([])
    source.with_name('fixed').touch()
    environment[EXCLUDE] = json.dumps(sorted(Checkpoint(tmp_path, [('unit', [])], resume=True).passed('unit')))
    second = subprocess.run(command, cwd=tmp_path, env=environment, capture_output=True,
                            text=True, timeout=30)
    assert second.returncode == 0, second.stdout + second.stderr
    assert (tmp_path / 'calls').read_text().splitlines() == (
        ['passed', 'retry', 'passed', 'retry', 'pending'] if oversized else
        ['passed', 'retry', 'retry', 'pending'])
    events = [json.loads(line[len(regression_events.PREFIX):])
              for line in second.stdout.splitlines() if line.startswith(regression_events.PREFIX)]
    collection = next(value for value in events if value['kind'] == 'collection')
    assert collection['total'] == (3 if oversized else 2)
    assert collection.get('resumed_nodeids', []) == json.loads(environment[EXCLUDE])
    if not oversized:
        assert collection['resumed_nodeids'][0].endswith('test_sample.py::test_passed[passed]')


def test_all_completed_inventory_succeeds_but_genuinely_empty_inventory_does_not(monkeypatch):
    monkeypatch.setenv(EXCLUDE, '["case"]')
    config = SimpleNamespace(hook=SimpleNamespace(pytest_deselected=Mock()))
    session = SimpleNamespace(exitstatus=5)
    items = [SimpleNamespace(nodeid='case')]
    regression_events.pytest_collection_modifyitems(session, config, items)
    regression_events.pytest_sessionfinish(session, 5)
    assert items == [] and session.exitstatus == 0
    empty = SimpleNamespace(exitstatus=5)
    regression_events.pytest_collection_modifyitems(empty, config, [])
    regression_events.pytest_sessionfinish(empty, 5)
    assert empty.exitstatus == 5
    session.exitstatus = 1
    regression_events.pytest_sessionfinish(session, 5)
    assert session.exitstatus == 1


def test_repository_pytest_configuration_registers_resume_hooks():
    cases = ['tests/unit/test_test_checkpoint.py::' + name for name in (
        'test_resume_keeps_only_finished_nonfailed_cases_and_fresh_run_resets',
        'test_failed_teardown_revokes_an_earlier_completion')]
    environment = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT), str(ROOT / 'tools'))),
                       PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', ONPC_REGRESSION_EVENTS='1',
                       ONPC_REGRESSION_INVENTORY='1', **{EXCLUDE: json.dumps([cases[0]])})
    result = subprocess.run(['/usr/bin/python3', '-B', '-m', 'pytest',
                             '-p', 'no:cacheprovider', '--collect-only', '-q', *cases],
                            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    events = [json.loads(line[len(regression_events.PREFIX):])
              for line in result.stdout.splitlines() if line.startswith(regression_events.PREFIX)]
    assert [value['nodeids'] for value in events if value['kind'] == 'collection'] == [[cases[1]]]
    assert [value['resumed_nodeids'] for value in events if value['kind'] == 'collection'] == [[cases[0]]]


@pytest.mark.parametrize('selector', [['-k', 'teardown'], ['-m', 'contract']])
def test_resume_counts_only_completed_cases_matching_original_selectors(selector):
    cases = ['tests/unit/test_test_checkpoint.py::' + name for name in (
        'test_failed_teardown_revokes_an_earlier_completion',
        'test_resume_keeps_only_finished_nonfailed_cases_and_fresh_run_resets')]
    # This module is classified as unit; -m contract excludes both cases.
    environment = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT), str(ROOT / 'tools'))),
                       PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', ONPC_REGRESSION_EVENTS='1',
                       ONPC_REGRESSION_INVENTORY='1', **{EXCLUDE: json.dumps(cases)})
    result = subprocess.run(['/usr/bin/python3', '-B', '-m', 'pytest',
                             '-p', 'no:cacheprovider', '--collect-only', '-q', *selector, *cases],
                            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == (0 if selector[0] == '-k' else 5), result.stdout + result.stderr
    events = [json.loads(line[len(regression_events.PREFIX):])
              for line in result.stdout.splitlines() if line.startswith(regression_events.PREFIX)]
    collection = next(value for value in events if value['kind'] == 'collection')
    assert collection.get('resumed_nodeids', []) == (cases[:1] if selector[0] == '-k' else [])


def test_selected_run_skips_completed_category_and_retains_serial_failure_limit(tmp_path, monkeypatch):
    # Keep this private checkpoint independent of the outer repair run's exclusions.
    monkeypatch.delenv('ONPC_REPAIR_FAILED_CASES', raising=False)
    selection = [('static', ['shell']), ('unit', ['-x'])]
    checkpoint = Checkpoint(tmp_path, selection)
    checkpoint.finish([SimpleNamespace(retry_category='static', count_overall=True, state='Passed')])
    event(checkpoint, 'finished', 'tests/unit/test_core.py::passed')
    checkpoint.finish([])
    calls = []
    monkeypatch.setattr(regression_selection, 'source_identity', lambda _: 'f' * 64)
    monkeypatch.setattr(regression.host, 'environment', lambda _: {})
    monkeypatch.setattr(regression_selection, 'pytest_command',
                        lambda *_: ['pytest', 'no:cacheprovider', '-x', '--'])

    def run(self, command, *, output, env, **kwargs):
        calls.append(command)
        assert regression_events.completed_cases(env[EXCLUDE]) == {'tests/unit/test_core.py::passed'}
        value = dict(kind='collection', total=1, nodeids=['tests/unit/test_core.py::retry'])
        output((regression_events.PREFIX + json.dumps(value) + '\n').encode())
        if '--collect-only' not in command:
            output((regression_events.PREFIX + json.dumps(dict(kind='finished',
                    nodeid='tests/unit/test_core.py::retry')) + '\n').encode())
        return 0

    monkeypatch.setattr(regression.Control, 'run', run)
    assert regression.retained_main(tmp_path, selections=selection, checkpoint=Checkpoint(
        tmp_path, selection, resume=True)) == 0
    assert len(calls) == 2 and all(command[1] == 'unit' and '-x' in command for command in calls)


@pytest.mark.parametrize('kind', ['unit', 'ui'])
def test_parallel_resume_preserves_completed_buckets_without_executing_them(tmp_path, monkeypatch, kind):
    retained = f'tests/{kind}/test_completed.py::test_passed'
    pending = f'tests/{kind}/test_pending.py::test_retry'
    bucket = lambda name, node: SimpleNamespace(
        name=name, nodeids=(node,), paths=(node.split('::')[0],), kind=kind, estimate=1)
    partition = Mock(return_value=[bucket('Completed bucket', retained), bucket('Pending bucket', pending)])
    monkeypatch.setattr(regression, kind + '_buckets', partition)
    with closing(regression.Report(tmp_path)) as report:
        run = regression.Run(tmp_path, report, regression.Control(), host_only=True)
        inventory = regression.Category('Inventory', 1, nodeids=(pending,), resumed_nodeids=(retained,))
        run.categories[:] = [inventory]
        jobs = run.pytest_jobs(kind, inventory, [], exact=True)
        assert set(partition.call_args.args[0]) == {retained, pending}
        assert len(jobs) == 1 and jobs[0].item.nodeids == (pending,)
        assert pending in jobs[0].command and retained not in jobs[0].command
        assert run.categories[0].state == 'Passed'
        frame = run.dashboard.ANSI.sub('', '\n'.join(run.dashboard.render(run.dashboard.started)))
        assert 'Completed bucket - 100% (1/1)' in frame
        assert 'Overall - 50% (1/2)' in frame
