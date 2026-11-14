"""Discovery, honest progress, immediate failure reporting and provenance."""
from tests.support.vm_registry import vm_name

import io
from contextlib import nullcontext
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

import regression
import regression_events
import regression_process
import regression_schedule
from regression_resources import Admission, GIB, Sample
from regression_process import Control
import test_commands
from system_progress import Progress


@pytest.mark.parametrize('qualification', [False, True])
def test_e2e_subcategory_routes_only_matching_workers(tmp_path, monkeypatch, qualification):
    import runpy
    import vm_test_queue
    import vm_recording
    import vm_run_times

    selected = ({'subcategory': 'e2e-heavy'} if qualification else
                {'cases': [{'subcategory': 'general'}, {'subcategory': 'e2e-heavy'}]})
    monkeypatch.setattr(test_commands, 'validate_one', lambda *args: None)
    monkeypatch.setattr(runpy, 'run_path', lambda path: {
        'preflight': lambda *args, **kwargs: selected})
    workers = [SimpleNamespace(name=tag, family='one-family', vm_tags={tag})
               for tag in ('general', 'heavy')]
    options = ['--qualify-lunar-profile'] if qualification else []
    groups = vm_test_queue.execution_groups(tmp_path, ['e2e', *options], workers)
    assert [(group['key'], group['vm_tag'], group['vms']) for group in groups] == (
        [('e2e.general', 'general', ['general'])] if not qualification else []) + [
            ('e2e.e2e-heavy', 'heavy', ['heavy'])]
    assert groups[-1]['args'] == ['e2e', *options, '--subcategory', 'e2e-heavy']
    with pytest.raises(ValueError, match='no selected VM with vm_tag=heavy'):
        vm_test_queue.execution_groups(tmp_path, ['e2e', *options], workers[:1])
    if qualification:
        root = Path(__file__).resolve().parents[2]
        identity = vm_recording.case_identity(root, 'e2e', dict(nodeid=options[0]))
        assert identity[0] == 'check_e2e_lunar_profile'
        metadata = vm_run_times.metadata(root, 'e2e', options[0])
        assert metadata['id'] == identity[0]
        assert metadata['case_file'] == 'tests/integration/lunar_profile_qualification.py'
        launch_quit = vm_recording.case_identity(root, 'e2e', dict(nodeid='--qualify-lunar-launch-quit'))
        assert launch_quit[0] == 'check_e2e_lunar_launch_quit'
        assert vm_run_times.metadata(root, 'e2e', '--qualify-lunar-launch-quit')['id'] == launch_quit[0]


@pytest.fixture
def private_dispatch_source(monkeypatch):
    import test_source
    import host_compute
    # Synthetic checkouts own private leases, never the outer runner's lease.
    for name in (host_compute.VARIABLE, host_compute.TOKENS):
        monkeypatch.delenv(name, raising=False)
    for name in (test_source.VARIABLE, test_source.WRITER, test_source.IMPORTS,
                 test_source.STARTUP_READER, test_source.STARTUP_WRITER):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(test_source, '_local', threading.local())
    monkeypatch.setattr(test_source, '_generations', {})


@pytest.mark.parametrize(('concurrency', 'expected'), [(6, [2, 2, 2]), (5, [2, 2, 1]),
                                                     (2, [1, 1, 0])])
def test_pass_admission_balances_ready_families_and_rotates_refills(concurrency, expected):
    from vm_test_queue import FamilyAdmission
    vms = [SimpleNamespace(name=f'{family}-{index}', family=family, compute_unit=1)
           for family in ('a', 'b', 'c') for index in range(3)]
    admission = FamilyAdmission(vms)
    ready = [vm.name for vm in vms]
    active = []
    for _ in range(concurrency):
        name = admission.choose(ready, active)
        ready.remove(name)
        active.append(name)
    assert [sum(name.startswith(family) for name in active) for family in ('a', 'b', 'c')] == expected
    # Lower concurrency still eventually admits every family. A busy/drained
    # family supplies no ready VM and cannot strand another family's capacity.
    observed = set(active)
    for _ in range(9):
        ready.append(active.pop(0))
        name = admission.choose(ready, active)
        ready.remove(name)
        active.append(name)
        observed.add(name)
    assert {name[0] for name in observed} == {'a', 'b', 'c'}
    assert admission.choose(['a-0', 'a-1'], ['b-0']) == 'a-0'
    from host_compute import choose, units
    from collections import Counter
    balanced = [SimpleNamespace(name=f'{family}-{cost}', family=family, compute_unit=cost)
                for family in ('a', 'b') for cost in (1, 2)]
    selected = choose(balanced, units(4))
    totals = Counter()
    for vm in selected:
        totals[vm.family] += vm.compute_unit
    assert totals == {'a': 2, 'b': 2}
    equal = [SimpleNamespace(name=f'{family}-{i}', family=family, compute_unit=1)
             for family in ('a', 'b') for i in range(2)]
    assert Counter(vm.family for vm in choose(equal, units(3))) == {'a': 2, 'b': 1}
    exhausted = [vm for vm in balanced if vm.family != 'a' or vm.compute_unit == 1]
    assert Counter(vm.family for vm in choose(exhausted, units(3.5))) == {'a': 1, 'b': 1}


@pytest.mark.parametrize('impact,cleanup,failure_status', [
    ('no', True, 1), ('yes', True, 1), ('unsure', True, 1), ('no', False, 1),
    ('unsure', True, 130),
])
def test_repair_admission_starts_repair_before_remaining_work(
        tmp_path, monkeypatch, private_dispatch_source, impact, cleanup, failure_status):
    import test_source
    import vm_test_queue

    source_path = tmp_path / 'source'
    source_path.mkdir(mode=0o700)
    monkeypatch.setattr(test_source, 'source_directory', lambda *args, **kwargs: source_path)
    identity = dict(digest='a' * 64, generation=0)
    monkeypatch.setattr(vm_test_queue, 'source_identity', lambda _: dict(identity))
    vm = SimpleNamespace(name='sole-worker', family='family', compute_unit=1)
    companion = SimpleNamespace(name='companion', family='family', compute_unit=1)
    work = [dict(category='system', options=[], cases=[case], case=case, area=False)
            for case in ('first', 'second')]
    monkeypatch.setattr(vm_test_queue, 'repair_case_inventory',
                        lambda root, selected, control, **kwargs: [item['case'] for item in work])
    plan = ({'concurrency': 2}, [vm, companion], [], ['system'], [('system', [])], {'family': work})
    events = []
    failed = False
    together = threading.Barrier(2)
    first_assigned = threading.Event()
    initial_done = threading.Event()

    class Ready:
        def __init__(self, *args):
            self.worker = SimpleNamespace(vm=vm, receipt='owned')
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def attempt(self, name, callback):
            assert name == vm.name and test_source.WRITER in test_source.environment()
            return callback(self.worker)
        def release(self, name):
            assert name == vm.name
        def reserve(self, name):
            assert name == vm.name
        def run_ready(self, execute, *, choose, needed, completed, observed, service, keep_failed):
            assert keep_failed
            results = {target.name: dict(status=0, handoffs=[]) for target in (vm, companion)}
            def initial(target):
                if target is companion:
                    assert first_assigned.wait(5)
                with test_source.reader(tmp_path):
                    result = execute(SimpleNamespace(vm=target, receipt='owned'))
                    observed(target, result)
                return result
            with ThreadPoolExecutor(max_workers=2) as pool:
                initial_results = [(target, pool.submit(initial, target)) for target in (vm, companion)]
                for target, future in initial_results:
                    results[target.name] = completed(target, future.result(timeout=10))
            initial_done.set()
            while True:
                if service(self, True):
                    continue
                if not needed(vm):
                    break
                assert choose([vm.name], []) == vm.name
                with test_source.reader(tmp_path):
                    result = execute(self.worker)
                    observed(vm, result)
                results[vm.name] = completed(vm, result)
            return results

    monkeypatch.setattr(vm_test_queue, 'Executor', Ready)
    def execute(worker, assignment, inherited, recovering):
        nonlocal failed
        assert assignment['vm'] == worker.vm.name
        assert not recovering
        current = assignment.get('execution', assignment['work'])
        repairing = test_source.WRITER in test_source.environment()
        if not initial_done.is_set():
            if current['case'] == 'first':
                first_assigned.set()
            together.wait(timeout=5)
            if current['case'] == 'second':
                assert worker.interrupt.wait(5), 'companion guest steps were not interrupted'
                events.append(('interrupted', current['case']))
                return dict(status=130, interrupted=True, handoffs=[], evidence=dict(
                    assignment, passed=[], cleanup=True, diagnostic=False))
        events.append(('recheck' if repairing else 'normal', current['case']))
        status = failure_status if not failed and not repairing else 0
        failed |= bool(status)
        return dict(status=status, handoffs=[], evidence=dict(assignment, passed=[] if status else current['cases'],
                                                            cleanup=cleanup if status else True, diagnostic=False))
    def triage(ticket, result):
        events.append(('triage', impact))
        assert test_source.WRITER not in test_source.environment()
        return dict(source=identity, evidence_digest='b' * 64, decision=dict(
            impact=impact, reason='Scoped evidence.', scope=['private selected case'],
            evidence=['The other selected input is independent.'], classification='test_issue'))
    def repair(ticket, execution):
        events.append(('repair', ticket['case']))
        gate = test_source.RepairGate(tmp_path, root=tmp_path)
        assert gate.try_acquire(), 'the coordinator called repair before readers drained'
        try:
            result = execution.attempt('recheck')
            assert result['accepted']
            return dict(outcome='resolved', attempt=result['reference'], source_changed=False)
        finally:
            gate.release()

    result = vm_test_queue.execute_pass(tmp_path, plan, Control(), execute,
                                       actions=dict(triage=triage, repair=repair))
    assert result['status'] == 0 and not result['suspended']
    normal = events.index(('normal', 'second'))
    repairing = events.index(('repair', 'first'))
    assert repairing < normal
    assert events.count(('recheck', 'first')) == 1
    assert events.count(('interrupted', 'second')) == 1
    assert not result['pending_repairs'] and not result['unfinished']
    protection = test_source.SourceProtection(source_path)
    assert protection.owner() is None and not protection.impact_holds()


def test_snapshot_prerequisite_pause_resumes_same_pass_without_repair_or_task_charge(
        tmp_path, monkeypatch, private_dispatch_source):
    import test_source
    import vm_test_queue
    from launcher_runtime import TaskBudget

    monkeypatch.setattr(test_source, 'source_directory', lambda *args, **kwargs: tmp_path)
    monkeypatch.setattr(vm_test_queue, 'source_identity', lambda _: dict(digest='a' * 64, generation=0))
    vm = SimpleNamespace(name='worker', family='family', compute_unit=1)
    work = [dict(category='system', options=[], cases=[case], case=case, area=False)
            for case in ('first', 'second')]
    identity = dict(run='a' * 32, **{'pass': 'b' * 32})
    events = []
    paused = False
    active_control = None

    class Ready:
        def __init__(self, *args):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *_):
            events.append('joined')
        def run_ready(self, execute, *, choose, needed, completed, observed, service, keep_failed):
            results = {}
            while not active_control.stopped.is_set() and needed(vm):
                assert choose([vm.name], []) == vm.name
                value = execute(SimpleNamespace(vm=vm, receipt='owned'))
                observed(vm, value)
                results[vm.name] = completed(vm, value)
            return results
    monkeypatch.setattr(vm_test_queue, 'Executor', Ready)
    def execute(worker, assignment, inherited, recovering):
        nonlocal paused
        events.append('recover' if recovering else assignment['work']['case'])
        status = int(not paused and not recovering)
        paused |= bool(status)
        return dict(status=status, handoffs=[], output_tail='explicit prerequisite' if status else '',
                    evidence=(dict(assignment=assignment, cleanup=True) if recovering else
                              dict(assignment, passed=[] if status else assignment['work']['cases'],
                                   cleanup=True, diagnostic=False)))
    def prerequisite(name, result):
        assert name == vm.name and result['output_tail'] == 'explicit prerequisite'
        events.append('persisted')
        return True
    def unexpected(*args):
        pytest.fail('a snapshot prerequisite must not consume a repair session')
    budget = TaskBudget(tmp_path)
    budget.initialize(1)
    actions = dict(triage=unexpected, repair=unexpected, prerequisite=prerequisite,
                   admit_task=lambda category: budget.admit(key='category', concurrent=True),
                   settle_task=lambda category: budget.complete(key='category'))
    for resume in (False, True):
        active_control = Control()
        plan = ({'concurrency': 1}, [vm], [], ['--resume', 'system'] if resume else ['system'],
                [('system', [])], {'family': work})
        result = vm_test_queue.execute_pass(tmp_path, plan, active_control, execute,
                                            actions=actions, pass_identity=identity)
        assert {key: result[key] for key in ('run', 'pass')} == identity
        if not resume:
            assert result['prerequisite'] and result['stopped'] and result['status'] == 130
            assert events == ['first', 'persisted', 'joined']
        else:
            assert result['status'] == 0 and not result['prerequisite']
    assert events == ['first', 'persisted', 'joined', 'recover', 'first', 'second', 'joined']
    assert budget.read()['started'] == budget.read()['completed'] == 1


@pytest.mark.parametrize('failure_point', ['reservation', 'completion'])
def test_repair_mode_preserves_worker_failures_without_a_ticket(
        tmp_path, monkeypatch, private_dispatch_source, failure_point):
    import test_source
    import vm_test_queue

    monkeypatch.setattr(test_source, 'source_directory', lambda *args, **kwargs: tmp_path)
    monkeypatch.setattr(vm_test_queue, 'source_identity', lambda _: dict(digest='a' * 64, generation=0))
    vms = [SimpleNamespace(name=name, family='family', compute_unit=1) for name in ('failed-owner', 'other-owner')]
    work = dict(category='system', options=[], cases=['case'], case='case', area=False)
    plan = ({'concurrency': 1}, vms, [], ['system'], [('system', [])], {'family': [work]})
    class Ready:
        def __init__(self, *args):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def run_ready(self, execute, *, choose, needed, completed, observed, service, keep_failed):
            failure = (completed(vms[0], dict(status=2, handoffs=[], error='reservation failed'))
                       if failure_point == 'reservation' else dict(status=0, handoffs=[]))
            assert needed(vms[1])
            value = execute(SimpleNamespace(vm=vms[1], receipt='owned'))
            observed(vms[1], value)
            try:
                success = completed(vms[1], value)
            except ValueError as error:
                # The real executor converts completion exceptions after the
                # coordinator has already seen the successful attempt.
                success = dict(status=2, handoffs=[], cleanup=False, error=str(error))
            return {vms[0].name: failure, vms[1].name: success}
    monkeypatch.setattr(vm_test_queue, 'Executor', Ready)
    def execute(worker, assignment, inherited, recovering):
        return dict(status=0, handoffs=[], evidence=dict(assignment, passed=['case'], cleanup=True, diagnostic=False))
    def unexpected(*args):
        pytest.fail('an unticketed resource refusal must not run a repair action')
    def result_hook(*args):
        if failure_point == 'completion':
            raise ValueError('completion hook failed')
    result = vm_test_queue.execute_pass(tmp_path, plan, Control(), execute,
                                       actions=dict(triage=unexpected, repair=unexpected, result=result_hook))
    assert result['status'] == 1
    assert result['accepted'][0]['vm'] == 'other-owner'
    assert result['failures'] == ([dict(vm='failed-owner', status=2)] if failure_point == 'reservation' else [])


def test_execute_pass_claims_fifo_once_per_family_and_recovers_original_vm(tmp_path, monkeypatch):
    import vm_test_queue
    from test_checkpoint import PassCheckpoint
    from vm_case_queue import work_key
    vms = [SimpleNamespace(name=f'{family}-{index}', family=family, compute_unit=1)
           for family in ('a', 'b') for index in range(2)]
    work = [dict(category=category, options=[], cases=[case], case=case, area=False)
            for category, case in [('system', 'check_first'), ('e2e', 'E2E-001')]]
    plan = ({'concurrency': 2}, vms, ['unit'], ['system', 'e2e'],
            [('system', []), ('e2e', [])], {'a': work, 'b': work})
    retired, observed, recoveries, hosts = set(), [], [], []
    late_cleanup, clean_failure, attempt_root = [False], [False], [tmp_path]
    retain_failed = [False]
    class Ready:
        def __init__(self, root, pool, limit, stopped):
            assert pool == vms
            self.limit = limit
        def __enter__(self):
            return self
        def __exit__(self, *_):
            if late_cleanup[0]:
                raise ValueError('late executor check-in failure')
        def run_ready(self, execute, *, choose, needed, completed):
            results = {vm.name: dict(status=0, handoffs=[]) for vm in vms}
            while available := [vm for vm in vms if vm.name not in retired and needed(vm)]:
                names, selected = [vm.name for vm in available], []
                while names and len(selected) < self.limit:
                    name = choose(names, selected)
                    if name is None:
                        break
                    names.remove(name)
                    selected.append(name)
                if not selected:
                    break
                for name in selected:
                    vm = next(vm for vm in vms if vm.name == name)
                    results[name] = completed(vm, execute(SimpleNamespace(vm=vm, receipt='owned')))
                    if results[name]['status'] and not retain_failed[0]:
                        retired.add(name)
            return results
    monkeypatch.setattr(vm_test_queue, 'Executor', Ready)
    monkeypatch.setattr(vm_test_queue, 'source_identity', lambda root: {'digest': 'a' * 64, 'generation': 0})
    monkeypatch.setattr(vm_test_queue.test_source, 'reader', lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(test_commands, 'selections', lambda root, argv: [('unit', [])])
    fail = [True]
    recovery_status = [0]
    def execute(worker, assignment, inherited, recovering):
        assert assignment['vm'] == worker.vm.name
        state_path = PassCheckpoint(attempt_root[0], [], {}, {}).store.path / 'current.json'
        saved = PassCheckpoint.validate(json.loads(state_path.read_text()))
        partition = saved['families'][worker.vm.family]
        assert partition['claims'][work_key(assignment['work'])] == assignment
        if recovering:
            recoveries.append(worker.vm.name)
            if recovery_status[0]:
                assert recoveries.count(worker.vm.name) == 1, 'failed recovery was immediately retried'
            return dict(status=recovery_status[0], handoffs=[],
                        evidence=dict(assignment=assignment, cleanup=not recovery_status[0]))
        execution = assignment.get('execution', assignment['work'])
        observed.append((worker.vm.family, execution['case']))
        if fail[0] and worker.vm.family == 'b':
            fail[0] = False
            # Late cleanup fails after assertions; no pass may cross the join.
            return dict(status=1, handoffs=[], evidence=dict(assignment,
                passed=execution['cases'], cleanup=clean_failure[0], diagnostic=False))
        return dict(status=0, handoffs=[], evidence=dict(assignment,
            passed=execution['cases'], cleanup=True, diagnostic=False))
    def host(**kwargs):
        hosts.append('host')
        return dict(status=0)
    first = vm_test_queue.execute_pass(tmp_path, plan, Control(), execute, host=host)
    assert first['status'] == 1
    assert [case for family, case in observed if family == 'a'] == ['check_first', 'E2E-001']
    # The failed owner is not replaced by an equivalent VM until its cleanup.
    assert [case for family, case in observed if family == 'b'] == ['check_first', 'E2E-001']
    retired.clear()
    resumed = list(plan)
    resumed[3] = ['--resume', *plan[3]]
    recovery_status[0] = 2
    retain_failed[0] = True
    blocked = vm_test_queue.execute_pass(tmp_path, tuple(resumed), Control(), execute, host=host)
    assert blocked['status'] == 1 and blocked['suspended']
    assert recoveries == ['b-0']
    with PassCheckpoint.saved(tmp_path) as checkpoint:
        assert len(checkpoint.claims('b')) == 1
    retired.clear()
    recovery_status[0] = 0
    retain_failed[0] = False
    second = vm_test_queue.execute_pass(tmp_path, tuple(resumed), Control(), execute,
                                       host=host)
    assert second['status'] == 0
    assert recoveries == ['b-0', 'b-0'] and hosts == ['host']
    assert [(family, case) for family, case in observed if family == 'a'] == [
        ('a', 'check_first'), ('a', 'E2E-001')]
    assert len(second['accepted']) == 1

    history = dict(category='system', options=[], cases=['authorization::first', 'authorization::last'],
                   case='authorization::last', area=True)
    history_plan = (plan[0], vms, ['unit'], ['system'], [('system', [])],
                    {'a': [history], 'b': [history]})
    attempt_root[0] = tmp_path / 'focused'
    full = vm_test_queue.execute_pass(attempt_root[0], history_plan, Control(), execute, host=lambda **kwargs: dict(status=0))
    focused = list(history_plan)
    focused[3] = ['--resume', '--resume-case=authorization::first', '--resume-case-only', 'system']
    retry = vm_test_queue.execute_pass(attempt_root[0], tuple(focused), Control(), execute, host=lambda **kwargs: dict(status=0))
    assert full['status'] == retry['status'] == 0 and full['pass'] == retry['pass']
    assert len(retry['accepted']) == 2
    normal = list(history_plan)
    normal[3] = ['--resume', 'system']
    after = vm_test_queue.execute_pass(attempt_root[0], tuple(normal), Control(), execute, host=lambda **kwargs: dict(status=0))
    assert after['status'] == 0 and not after['accepted'] and after['pass'] == full['pass']
    focused[3] = ['--resume', '--resume-case=authorization::first', '--resume-area-only', 'system']
    assert vm_test_queue.execute_pass(attempt_root[0], tuple(focused), Control(), execute)['status'] == 0
    state_path = PassCheckpoint(attempt_root[0], [], {}, {}).store.path / 'current.json'
    before = state_path.read_bytes()
    for category, case in [('e2e', 'E2E-001'), ('system', 'upgrade::first')]:
        invalid = list(history_plan)
        invalid[3] = ['--resume', '--resume-case=' + case, '--resume-area-only', category]
        invalid[4] = [(category, [])]
        with pytest.raises(ValueError, match='independent system area'):
            vm_test_queue.execute_pass(attempt_root[0], tuple(invalid), Control(), execute)
        assert state_path.read_bytes() == before

    clean_failure[0] = True
    for late in (False, True):
        retired.clear()
        fail[0], late_cleanup[0] = True, late
        attempt_root[0] = tmp_path / ('late' if late else 'partial')
        if late:
            with pytest.raises(ValueError, match='late executor'):
                vm_test_queue.execute_pass(attempt_root[0], history_plan, Control(), execute, host=lambda **kwargs: dict(status=0))
        else:
            result = vm_test_queue.execute_pass(attempt_root[0], history_plan, Control(), execute, host=lambda **kwargs: dict(status=0))
            assert result['status'] == 1
        with PassCheckpoint.saved(attempt_root[0]) as checkpoint:
            assert checkpoint.passed('b', 'system') == (set() if late else {'authorization::first'})
            assert len(checkpoint.claims('b')) == 1

    # Continuation relinquishes only a qualified, joined original-worker
    # failure claim. Failed cases remain pending and never receive credit.
    late_cleanup[0], fail[0] = False, True
    retired.clear()
    attempt_root[0] = tmp_path / 'clean-failed-continuation'
    failed = vm_test_queue.execute_pass(attempt_root[0], history_plan, Control(), execute,
        host=lambda **kwargs: dict(status=0), continue_on_errors=True)
    assert failed['status'] == 1 and failed['cleanup_complete'] and not failed['suspended']
    with PassCheckpoint.saved(attempt_root[0]) as checkpoint:
        assert checkpoint.claims('b') == []
        assert checkpoint.passed('b', 'system') == {'authorization::first'}
        assert checkpoint.pending('b') == [history]

    late_cleanup[0], fail[0] = False, False
    retired.clear()
    attempt_root[0] = tmp_path / 'unrelated'
    unrelated = dict(category='system', options=[], cases=['check_other'], case='check_other', area=False)
    mixed = list(history_plan)
    mixed[5] = {'a': [history, unrelated], 'b': [history, unrelated]}
    selection = [['_host', ['unit']], ['_guest', ['system']]]
    pool = {vm.name: vm.family for vm in vms}
    with PassCheckpoint(attempt_root[0], selection, pool, mixed[5]) as checkpoint:
        target = checkpoint.claim('b', 'b-0', history, {'digest': 'a' * 64})
        other = checkpoint.claim('b', 'b-1', unrelated, {'digest': 'a' * 64})
    mixed[3] = ['--resume', '--resume-case=authorization::first', '--resume-case-only', 'system']
    previous_recoveries = list(recoveries)
    selected = vm_test_queue.execute_pass(attempt_root[0], tuple(mixed), Control(), execute, host=lambda **kwargs: dict(status=0))
    assert selected['status'] == 0 and recoveries == [*previous_recoveries, target['vm']]
    with PassCheckpoint.saved(attempt_root[0]) as checkpoint:
        assert checkpoint.claims('b') == [other]

    retired.clear()
    attempt_root[0] = tmp_path / 'reload'
    reloading = [False]
    monkeypatch.setattr(vm_test_queue.launcher_reload, 'pending', lambda: reloading[0])
    def reload_once(worker, assignment, inherited, recovering):
        if worker.vm.family == 'b':
            reloading[0] = True
            return dict(status=vm_test_queue.launcher_reload.STATUS, handoffs=[])
        return execute(worker, assignment, inherited, recovering)
    reload_plan = list(history_plan)
    reload_plan[3] = ['--stop-on-error', 'system']
    control = Control()
    reload_result = vm_test_queue.execute_pass(attempt_root[0], tuple(reload_plan), control,
                                              reload_once, host=lambda **kwargs: dict(status=0))
    assert reload_result['status'] == vm_test_queue.launcher_reload.STATUS
    assert not control.stopped.is_set()
    reloading[0] = False
    reload_plan[3] = ['--resume', *reload_plan[3]]
    retired.clear()
    resumed_reload = vm_test_queue.execute_pass(attempt_root[0], tuple(reload_plan), Control(), execute)
    assert resumed_reload['status'] == 0 and resumed_reload['pass'] == reload_result['pass']

    # A clean ordinary host failure remains a failure, but is not an ownership
    # suspension that would prohibit explicitly requested independent VM work.
    host_plan = ({'concurrency': 0}, [], ['unit'], [], [], {})
    for cleanup in (True, False):
        failed = vm_test_queue.execute_pass(tmp_path / 'host-failure', host_plan, Control(), execute,
            host=lambda **kwargs: dict(status=1, cleanup=cleanup))
        assert failed['status'] == 1
        assert failed['suspended'] is not cleanup
        assert failed['cleanup_complete'] is cleanup


@pytest.mark.parametrize(('selector', 'names'), [(None, ['one', 'two', 'three']),
                                               ('two,three', ['two', 'three'])])
def test_pass_plan_uses_only_the_requested_or_configured_pool(
        tmp_path, monkeypatch, private_dispatch_source, selector, names):
    from contextlib import contextmanager
    from dataclasses import replace
    import host_compute
    import launcher_reload
    import runpy
    import vm_recording
    import vm_pool
    import vm_selection
    import vm_test_queue
    config = vm_selection.vm_config
    host = config.HostConfig(max_compute_unit=6)
    configured = {name: config.VMConfig(name, tmp_path / name, enabled=name != 'offline',
        package_format='deb', family=family, fixture_path='fixtures', host=host,
        vm_tags=frozenset({'general'}))
        for name, family in [('one', 'a'), ('two', 'a'), ('three', 'b'), ('offline', 'b')]}
    monkeypatch.setattr(config, 'configuration', lambda path=None: (6, configured))
    monkeypatch.setattr(vm_pool, 'check_queue', lambda vms: None)
    monkeypatch.delenv(vm_selection.WORKER, raising=False)
    monkeypatch.delenv(vm_selection.VARIABLE, raising=False)
    monkeypatch.setenv(vm_selection.BATCH, '')
    monkeypatch.delenv(vm_selection.BATCH, raising=False)
    monkeypatch.setattr(vm_test_queue.test_source, 'reader', lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(vm_test_queue, 'case_inventory', lambda *args, **kwargs: ['E2E-001', 'E2E-002'])
    args, _ = test_commands.vm_request(['e2e', *(['--vm', selector] if selector else [])])
    plan = vm_test_queue._plan(tmp_path, args)
    assert [vm.name for vm in plan[1]] == names
    assert list(plan[-1]) == ['a', 'b']
    assert all([work['case'] for work in items] == ['E2E-001', 'E2E-002']
               for items in plan[-1].values())

    # Exercise this same pool guarantee at the sequential controller boundary:
    # repeated selectors share credit, and only the admitted group owns capture
    # and shutdown recovery. All guests/recorders remain private doubles.
    def validate_one(root, args):
        if any(arg in test_commands.CATEGORIES for arg in args[1:]):
            raise ValueError('split category selections')
    monkeypatch.setattr(test_commands, 'validate_one', validate_one)
    monkeypatch.setattr(runpy, 'run_path', lambda path: {
        'preflight': lambda *args, **kwargs: dict(cases=[dict(subcategory='general')])})
    monkeypatch.setattr(vm_test_queue.test_source, 'startup', lambda *args, **kwargs: nullcontext())
    owner = tmp_path / 'controller'
    owner.mkdir(mode=0o700)
    monkeypatch.setattr(launcher_reload, 'current', launcher_reload.ReloadRequest(owner))
    events, executions, exact_admissions = [], [], []
    active = []
    pending = [False]
    ordinary_failure = [False]

    @contextmanager
    def admit(candidates, *, exact, handoff):
        assert not active and not handoff
        assert all(vm.name in names for vm in candidates)
        exact_admissions.append(exact)
        families = {}
        for vm in candidates:
            families.setdefault(vm.family, []).append(vm)
        admitted = (list(candidates) if exact else
                    [workers[-1 if executions else 0] for workers in families.values()])
        active.extend(vm.name for vm in admitted)
        events.append('admit')
        yield admitted
        assert host_compute.admitted_names(owner) == (active if pending[0] else [])
        events.append('release')
        active.clear()

    @contextmanager
    def record(root, *, enabled, run):
        assert enabled and run == owner
        assert json.loads(os.environ[vm_selection.BATCH])['vms'] == active
        assert host_compute.admitted_names(owner) == active
        events.append('capture')
        yield SimpleNamespace(write_index=lambda *args: None)
        events.append('capture joined')

    def execute(root, args, **kwargs):
        assert host_compute.admitted_names(owner) == active
        executions.append(list(args))
        if ordinary_failure[0]:
            ordinary_failure[0] = False
            return dict(status=1, cleanup_complete=True)
        pending[0] = len(executions) == 2
        if pending[0]:
            return dict(status=1, suspended=True, cleanup_complete=False)
        return dict(status=0, cleanup_complete=True)

    monkeypatch.setattr(host_compute, 'launch', admit)
    monkeypatch.setattr(vm_recording, 'recording', record)
    monkeypatch.setattr(vm_test_queue, '_run_group', execute)
    requested = ['system', 'check_first', 'system', 'check_second', 'e2e']
    assert vm_test_queue.run(tmp_path, requested) == 1
    assert executions == [['system', 'check_first', 'system', 'check_second'],
                          ['e2e', '--subcategory', 'general']]
    assert events == ['admit', 'capture', 'capture joined', 'release'] * 2
    assert json.loads(os.environ[vm_selection.BATCH])['vms'] == names
    # An admitted worker must remain eligible; an unused candidate may go
    # offline without invalidating completed groups or the retained workers.
    configured['two'] = replace(configured['two'], enabled=False)
    vm_selection.execution_selection(selector)
    with pytest.raises(ValueError, match='original admitted VMs'):
        vm_test_queue.run(tmp_path, ['--resume', *requested])
    configured['two'] = replace(configured['two'], enabled=True)
    if selector is None:
        configured['one'] = replace(configured['one'], enabled=False)
    vm_selection.execution_selection(selector)
    assert vm_test_queue.run(tmp_path, ['--resume', *requested]) == 0
    assert executions[-1] == ['e2e', '--subcategory', 'general']
    assert exact_admissions == [False, False, True]
    assert events == ['admit', 'capture', 'capture joined', 'release'] * 3
    assert host_compute.admitted_names(owner) == []
    assert vm_test_queue.run(tmp_path, ['--resume', *requested]) == 0
    assert len(executions) == 3

    # Explicit continuation runs later groups while retaining the failure.
    # Resume retries only the failed group, not the already accepted group.
    continued = tmp_path / 'continued'
    selected = ['system', 'e2e', '--continue-on-errors']
    ordinary_failure[0] = True
    assert vm_test_queue.run(continued, selected) == 1
    assert executions[3:] == [['system'], ['e2e', '--subcategory', 'general']]
    assert vm_test_queue.run(continued, ['--resume', *selected]) == 0
    assert executions[5:] == [['system']]
    ordinary_failure[0] = True
    assert vm_test_queue.run(tmp_path / 'stop-on-failure', ['system', 'e2e']) == 1
    assert executions[6:] == [['system']]

    if selector is None:
        # An unentered group admits from current eligibility inside the same
        # original allowlist, including a VM whose tags changed since startup.
        from test_checkpoint import GroupCheckpoint
        configured['one'] = replace(configured['one'], enabled=True)
        configured['two'] = replace(configured['two'], vm_tags=frozenset({'heavy'}))
        vm_selection.execution_selection()
        future = tmp_path / 'future-group'
        selected = ['system', 'e2e']
        groups = vm_test_queue.execution_groups(future, selected, [configured[name] for name in names])
        with GroupCheckpoint(future, groups, names) as saved:
            saved.state['workers'][0] = ['one', 'three']
            saved.state['outcomes'][0] = dict(status=0, source_changed=False, terminal_failed=False)
            saved.save()
        configured['two'] = replace(configured['two'], vm_tags=frozenset({'general'}))
        before = len(executions)
        assert vm_test_queue.run(future, ['--resume', *selected]) == 0
        assert executions[before:] == [['e2e', '--subcategory', 'general']]
        assert not exact_admissions[-1]

    # Pre-group E2E owners retain their original selectors even though current
    # routing adds a subcategory. Reconnection keeps the scope, identity, and
    # admitted pool rather than manufacturing fresh family credit.
    from test_checkpoint import PassCheckpoint
    for name in names:
        configured[name] = replace(configured[name], enabled=True,
                                   vm_tags=frozenset({'general'}))
    vm_selection.execution_selection(selector)
    legacy = tmp_path / 'ungrouped'
    with PassCheckpoint(legacy, [['_host', []], ['_guest', ['e2e']]],
                        {name: configured[name].family for name in names}, plan[-1],
                        scope='repair-vm') as checkpoint:
        identity = {key: checkpoint.state[key] for key in ('run', 'pass')}

    def resume_legacy(root, args, **kwargs):
        assert args == ['--resume', 'e2e']
        assert kwargs['checkpoint_scope'] == 'repair-vm'
        assert kwargs['pass_identity'] == identity
        assert set(active) == set(names)
        return execute(root, args, **kwargs)

    monkeypatch.setattr(vm_test_queue, '_run_group', resume_legacy)
    before = len(executions)
    assert vm_test_queue.run(legacy, ['--resume', 'e2e'], pass_identity=identity,
                             checkpoint_scope='repair-vm') == 0
    assert executions[before:] == [['--resume', 'e2e']]
    assert exact_admissions[-1]


def test_ui_timings_preserve_nested_calls_failures_and_private_arguments():
    from tests.support.ui_timing import Timings
    now = [10.0]
    events = []
    timings = Timings(lambda kind, **fields: events.append((kind, fields)), lambda: now[0])
    timings.begin('test.py::case', 'call')
    error = KeyboardInterrupt('private-error')

    def inner(secret):
        assert secret == 'private-value'
        now[0] += 2
        raise error

    measured = timings.wrap(inner, 'atspi.rpc')
    with pytest.raises(KeyboardInterrupt) as caught:
        with timings.measure('reader.snapshot'):
            now[0] += 1
            measured('private-value')
    assert caught.value is error
    timings.publish('end')
    evidence = events[-1][1]
    assert evidence['elapsed_seconds'] == 3
    assert evidence['active'] == []
    assert evidence['operations']['reader.snapshot'] == dict(
        count=1, errors=1, seconds=3, self_seconds=1, max_seconds=3)
    assert evidence['operations']['atspi.rpc']['seconds'] == 2
    assert 'private-' not in str(events)


def test_ui_query_diagnostics_preserve_results_errors_and_private_arguments():
    from tests.support.ui_timing import Timings
    now, events = [0.0], []
    recorder = Timings(lambda kind, **fields: events.append(fields), lambda: now[0])
    recorder.begin('case', 'call')
    api, result = object(), object()
    error = ValueError('private-error')
    accessible = 'org.a11y.atspi.Accessible'
    properties = 'org.freedesktop.DBus.Properties'
    query = ('private-bus', '/private/path', properties, 'Get', 'ss',
             (accessible, 'Name'))

    def rpc(*args):
        assert args == (api, *query)
        now[0] += 1
        return result

    assert recorder.wrap_rpc(rpc)(api, *query) is result

    def failed_rpc(*args):
        now[0] += 2
        raise error

    with pytest.raises(ValueError) as caught:
        recorder.wrap_rpc(failed_rpc)(api, 'private-bus', '/private/path',
                                     'private-interface', 'private-method', '', ('private-value',))
    assert caught.value is error
    queries = [query, ('private-bus', '/private/path', properties, 'Get', 'ss',
                       (accessible, 'private-property'))]
    results = [result, error]

    def batch(owner, original):
        assert owner is api and original is queries
        now[0] += 1
        return results

    assert recorder.wrap_batch(batch)(api, queries) is results
    recorder.publish('end')
    evidence = events[-1]['queries']
    assert evidence['sync']['property.Name'] == dict(
        count=1, errors=0, seconds=1, max_seconds=1)
    assert evidence['sync']['other'] == dict(count=1, errors=1, seconds=2, max_seconds=2)
    assert evidence['batch'] == {'property.Name': dict(count=1, errors=0),
                                 'property.other': dict(count=1, errors=1)}
    assert evidence['batch_sizes'] == {'2': dict(count=1, aborted=0, seconds=1)}
    assert 'private-' not in str(events) and '/private/' not in str(events)
    recorder.begin('case', 'teardown')
    assert events[-1]['queries'] == {'sync': {}, 'batch': {}, 'batch_sizes': {}}
    assert evidence['sync']['other']['count'] == 1


def test_ui_query_diagnostics_preserve_interrupt_and_measure_stream_cost():
    from tests.support.ui_timing import Timings
    now, cpu, events = [0.0], [1.0], []

    def sink(kind, **fields):
        events.append(fields)
        now[0] += .1

    recorder = Timings(sink, lambda: now[0], lambda: cpu[0])
    recorder.begin('case', 'call')
    queries = [('private-bus', '/private/path', 'org.a11y.atspi.Accessible',
                'GetAttributes', '', ())]
    interruption = KeyboardInterrupt('private-interruption')

    def batch(api, original):
        assert original is queries
        now[0] += 1
        raise interruption

    with pytest.raises(KeyboardInterrupt) as caught:
        recorder.wrap_batch(batch)(object(), queries)
    assert caught.value is interruption
    cpu[0] += .3
    recorder.publish('end')
    assert events[-1]['cpu_seconds'] == pytest.approx(.3)
    assert events[-1]['output_seconds'] == pytest.approx(.1)
    assert events[-1]['queries']['batch_sizes'] == {'1': dict(count=1, aborted=1, seconds=1)}
    assert events[-1]['operations']['atspi.batch']['errors'] == 1
    assert not recorder.stack and 'private-' not in str(events)
    recorder.begin('case', 'teardown')
    recorder.publish('end')
    assert events[-1]['cpu_seconds'] == 0
    assert events[-1]['output_seconds'] == pytest.approx(.1)


def test_ui_trace_retains_nested_operation_identity_and_existing_reader_timing():
    from tests.support.ui_timing import Timings
    from tests.e2e.accessible_ui import AccessibleUI
    events, existing = [], []
    recorder = Timings(lambda kind, **fields: events.append((kind, fields)))
    reader = AccessibleUI(object(), root=lambda: None, timing=existing.append)
    reader._run = lambda *args, **kwargs: 42
    wrapped = recorder.wrap_reader_run(AccessibleUI.run)
    with recorder.span('gui.block'):
        assert wrapped(reader, 'child-picker-opened', 'private version') == 42
    trace = [fields for kind, fields in events if kind == 'ui-trace']
    assert [event['status'] for event in trace] == ['begin', 'begin', 'end', 'end']
    assert trace[1]['parent'] == trace[0]['span']
    assert trace[1]['registered_operation'] == 'child-picker-opened'
    timing = next(fields for kind, fields in events if kind == 'ui-reader-timing')
    assert timing['span'] == trace[1]['span']
    assert timing['tree_reads'] == 0
    assert len(existing) == 1
    assert reader.timing == existing.append
    assert 'private version' not in str(events)


def test_ui_timings_escape_case_capture_and_close_owned_descriptor(tmp_path):
    from tools.test_storage import scratch_descriptors
    root = Path(__file__).resolve().parents[2]
    (tmp_path / 'conftest.py').write_text('''
import os
import pytest
from tests.support.ui_timing import Timings
timings = None
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    global timings
    timings = Timings.retained()
    timings.begin(item.nodeid, 'setup')
    yield
@pytest.fixture
def record():
    return timings
def pytest_sessionfinish(session, exitstatus):
    descriptor = timings.stream.fileno()
    assert not os.get_inheritable(descriptor)
    timings.close()
    with pytest.raises(OSError):
        os.fstat(descriptor)
''')
    (tmp_path / 'test_sample.py').write_text('''
def test_capture(record):
    print('private-test-output')
    with record.measure('reader.snapshot'):
        pass
    record.publish('progress')
''')
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', str(tmp_path)],
        env=dict(os.environ, PYTHONPATH=str(root)), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=30, pass_fds=scratch_descriptors())
    output = result.stdout.decode()
    assert result.returncode == 0, output
    assert '"status": "progress"' in output
    assert '"reader.snapshot"' in output
    assert 'private-test-output' not in output


@pytest.fixture
def report(tmp_path):
    result = regression.Report(tmp_path)
    yield result
    result.close()


def test_standalone_report_holds_owner_until_late_failure_handoff_finishes(tmp_path, monkeypatch):
    import test_retention
    monkeypatch.delenv(test_retention.VARIABLE, raising=False)
    monkeypatch.delenv(test_retention.OWNER_VARIABLE, raising=False)
    report = regression.Report(tmp_path)
    owner = report.retention_session
    assert owner is not None
    assert test_retention.owner_descriptor() >= 0
    report.close(release=False)
    assert report.stream.closed and report.retention_session is owner
    assert test_retention.owner_descriptor() >= 0
    report.release_session()
    assert report.retention_session is None
    assert test_retention.token() is None


def test_closed_command_keeps_exact_inventory_failure_and_cleanup(report, tmp_path):
    run = regression.Run(tmp_path, report, Control(), host_only=True, continue_on_errors=True)
    run.dashboard.stream = io.StringIO()
    item = regression.Category('Exact selection', 1, nodeids=('file.py::case[param]',),
                               retry_category='unit', resumed_nodeids=('file.py::earlier',))
    run.categories.append(item)
    argv = ['tools/run-tests', 'unit', '-k', 'case', '--timeout', '45']
    execution = regression.Execution(run, item, command=argv, events=True)
    for event in [dict(kind='collection', total=1, nodeids=list(item.nodeids)),
                  dict(kind='failure', nodeid=item.nodeids[0], when='teardown'),
                  dict(kind='finished', nodeid=item.nodeids[0])]:
        execution.output((regression.PREFIX + json.dumps(event) + '\n').encode())
    with pytest.raises(ValueError, match='fixture setup or cleanup failed'):
        execution.finish(1)
    record = json.loads((report.directory / 'command-001.json').read_text())
    assert record['argv'] == argv
    assert record['selected_ids'] == ['file.py::case[param]']
    assert record['resumed_ids'] == ['file.py::earlier']
    assert record['completed_ids'] == record['failed_ids'] == ['file.py::case[param]']
    assert record['exit_status'] == 1 and record['cleanup'] == 'failed'
    assert execution.raw.closed
    assert report.commands == [record]
    execution.close()
    assert report.commands == [record]

    # A verified interruption keeps completed accounting without inventing a
    # failed last case merely because cancellation arrived during cleanup.
    checkpoint_events = []
    run.checkpoint = SimpleNamespace(event=lambda *args: checkpoint_events.append(args))
    interrupted = regression.Category('Interrupted selection', 1, nodeids=item.nodeids,
                                      retry_category='unit')
    run.categories.append(interrupted)
    attempt = regression.Execution(run, interrupted, command=argv, events=True)
    for event in [dict(kind='collection', total=1, nodeids=list(item.nodeids)),
                  dict(kind='finished', nodeid=item.nodeids[0]),
                  dict(kind='vm-cleanup', passed=True, interrupted=True)]:
        attempt.output((regression.PREFIX + json.dumps(event) + '\n').encode())
    run.control.stop()
    attempt.finish(130)
    attempt.close()
    assert interrupted.state == 'Interrupted' and interrupted.done == 1 and interrupted.failures == 0
    assert run.checkpoint.queue_vm_cleanup and run.checkpoint.queue_vm_interrupted
    assert not any(event[1]['kind'] == 'failure' for event in checkpoint_events)


@pytest.mark.parametrize('output', ['valid', 'missing-marker', 'missing-file', 'invalid-file',
                                  'stale', 'unregistered', 'replaced', 'symlink', 'ancestor-symlink'])
def test_successful_coverage_requires_its_actual_outputs(tmp_path, monkeypatch, output):
    import test_retention
    monkeypatch.delenv(test_retention.VARIABLE, raising=False)
    monkeypatch.delenv(test_retention.OWNER_VARIABLE, raising=False)
    store = test_retention.Store(tmp_path / 'coverage-retention')
    parent = tmp_path / 'coverage-parent'
    parent.mkdir(mode=0o700)
    directory = parent / 'coverage-output'

    def create_outputs(*, register=True):
        directory.mkdir(mode=0o700)
        if register and output != 'unregistered':
            test_retention.retain(directory)
        for name in ('coverage.xml', '.coverage'):
            if output == 'missing-file' and name == '.coverage':
                continue
            path = directory / name
            if output == 'invalid-file' and name == '.coverage':
                path.mkdir(mode=0o700)
            elif output == 'symlink' and name == '.coverage':
                path.symlink_to('coverage.xml')
            else:
                path.write_bytes(b'<coverage/>' if name == 'coverage.xml' else b'coverage database')
                path.chmod(0o600)

    if output == 'stale':
        with store.session():
            create_outputs()
    with store.session():
        if output != 'stale':
            create_outputs()
        report = regression.Report(tmp_path)
        displaced = None
        try:
            if output == 'replaced':
                displaced = directory.with_name('original-output')
                directory.rename(displaced)
                create_outputs(register=False)
            elif output == 'ancestor-symlink':
                displaced = parent.with_name('original-parent')
                parent.rename(displaced)
                parent.symlink_to(displaced, target_is_directory=True)
            run = regression.Run(tmp_path, report, Control(), host_only=True)
            run.dashboard.stream = io.StringIO()
            item = regression.Category('coverage', total=1, retry_category='coverage')
            run.categories = [item]
            execution = regression.Execution(run, item, command=['tools/run-tests', 'coverage'])
            if output != 'missing-marker':
                execution.output(('run-tests: output=' + str(directory) + '\n').encode())
            if output == 'valid':
                execution.finish(0)
                assert report.commands[-1]['status'] == 'passed'
                assert report.commands[-1]['cleanup'] == 'complete'
            else:
                with pytest.raises(ValueError, match='valid result files'):
                    execution.finish(0)
                assert item.state == 'Failed'
            assert execution.raw.closed
        finally:
            if output == 'replaced' and displaced is not None:
                for path in directory.iterdir():
                    path.unlink()
                directory.rmdir()
                displaced.rename(directory)
            elif output == 'ancestor-symlink' and displaced is not None:
                parent.unlink()
                displaced.rename(parent)
            report.close()


@pytest.mark.parametrize('kind,fields', [
    ('collection', {'total': 1}),
    ('finished', {'nodeid': 'case'}),
    ('failure', {'nodeid': 'case', 'when': 'call', 'detail': 'first line\nsecond: café'}),
])
def test_event_record_stays_complete_when_diagnostics_follow_each_write(
        report, tmp_path, monkeypatch, kind, fields):
    run = regression.Run(tmp_path, report, Control(), host_only=True)
    run.dashboard.stream = io.StringIO()
    item = regression.Category('Mixed output', 1)
    run.categories.append(item)
    execution = regression.Execution(run, item, events=True)
    diagnostic = b'prepare-vm: [connection:event-loop-failed]\n'

    class InterleavedOutput:
        def write(self, value):
            # A background writer can run between any two stream writes,
            # including print's separate record and newline writes.
            for byte in value.encode():
                execution.output(bytes([byte]))
            execution.output(diagnostic)
            return len(value)

        def flush(self):
            pass

    monkeypatch.setattr(regression_events.sys, '__stdout__', InterleavedOutput())
    try:
        regression_events.emit(kind, **fields)
        assert execution.inventory_seen == (kind == 'collection')
        assert item.done == (kind == 'finished')
        assert item.failures == (kind == 'failure')
        raw = (report.directory / 'category-001.log').read_text()
        events = [json.loads(line[len(regression.PREFIX):]) for line in raw.splitlines()
                  if line.startswith(regression.PREFIX)]
        assert events == [dict(kind=kind, **fields)]
        assert diagnostic.decode() in raw
    finally:
        execution.close()


@pytest.mark.parametrize('kind', ['finished', 'failure'])
def test_system_progress_survives_diagnostics_between_writes(monkeypatch, kind):
    chunks = []
    diagnostic = 'e2e-watch: [progress-disabled]\n'

    class InterleavedOutput:
        def write(self, value):
            chunks.extend((value, diagnostic))
            return len(value)

        def flush(self):
            pass

    monkeypatch.setattr(sys, 'stdout', InterleavedOutput())
    parser = Progress('installed', [SimpleNamespace(case_id='case')])
    parser((regression.PREFIX + json.dumps(dict(kind=kind, nodeid='test.py::case',
                                              detail='private guest diagnostic')) + '\n').encode())
    lines = ''.join(chunks).splitlines()
    events = [json.loads(line[len(regression.PREFIX):]) for line in lines
              if line.startswith(regression.PREFIX)]
    assert len(events) == 1
    assert events[0]['kind'] == kind and events[0]['nodeid'] == 'installed::case'
    assert 'private guest diagnostic' not in ''.join(chunks)
    assert diagnostic.strip() in lines

    if kind == 'finished':
        from system_progress import SystemWatchProgress
        executions = [SimpleNamespace(phase=phase, case_id='test_installed_package')
                      for phase in ('installed', 'rebooted')]
        watch = SystemWatchProgress(executions)
        watch.prepare_attempt(executions)
        chunks.clear()
        for index, execution in enumerate(executions):
            parser = Progress(execution.phase, [execution], watch=watch)
            parser((regression.PREFIX + json.dumps(dict(
                kind='finished', nodeid='test.py::' + execution.case_id,
                monotonic_ns=100 + index)) + '\n').encode())
        events = [json.loads(line[len(regression.PREFIX):])
                  for line in ''.join(chunks).splitlines() if line.startswith(regression.PREFIX)]
        # The first phase can checkpoint without closing its history's clip;
        # the last cannot complete until the cleanup owner explicitly releases it.
        assert len(events) == 1
        assert events[0]['envelope_pending'] is True
        assert events[0]['nodeid'] == 'installed::test_installed_package'
        watch.complete_attempt()
        events = [json.loads(line[len(regression.PREFIX):])
                  for line in ''.join(chunks).splitlines() if line.startswith(regression.PREFIX)]
        assert len(events) == 2
        assert events[-1]['nodeid'] == 'rebooted::test_installed_package'
        assert 'monotonic_ns' not in events[-1]


def test_event_burst_keeps_output_live_without_per_case_disk_barriers(report, tmp_path, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(regression.time, 'monotonic', lambda: now[0])
    report.last_sync = now[0]
    synced = []
    monkeypatch.setattr(regression.os, 'fsync', lambda fd: synced.append(os.readlink(f'/proc/self/fd/{fd}')))
    control = Control()
    run = regression.Run(tmp_path, report, control, host_only=True)
    run.dashboard.stream = io.StringIO()
    item = regression.Category('Burst', 200)
    run.categories.append(item)
    execution = regression.Execution(run, item, events=True)
    for index in range(200):
        execution.output((regression.PREFIX + json.dumps(dict(
            kind='finished', nodeid=f'case-{index}')) + '\n').encode())
        report.checkpoint()
    assert item.done == 200
    assert not synced
    assert 'case-199' in (report.directory / 'category-001.log').read_text()
    assert 'case-199' in (report.directory / 'report.md').read_text()
    now[0] += 1
    report.checkpoint()
    assert json.loads((report.directory / 'progress.json').read_text())[-1]['done'] == 200
    assert not synced
    now[0] += 4
    report.checkpoint()
    names = [Path(path).name for path in synced]
    assert set(names) >= {'category-001.log', 'report.md', 'progress.json', 'inventory-001.json'}
    assert names.index('inventory-001.json') < names.index('progress.json')
    assert names.index('inventory-001.json') < names.index(report.directory.name) < names.index('progress.json')
    before = len(synced)
    report.checkpoint()
    assert len(synced) == before
    execution.output(b'last cleanup output')
    execution.close()
    assert len(synced) > before


def test_checkpoint_error_closes_stream_and_does_not_claim_persistence(report, monkeypatch):
    def broken(_):
        raise OSError('disk unavailable')
    with monkeypatch.context() as patch:
        patch.setattr(regression.os, 'fsync', broken)
        with pytest.raises(OSError, match='disk unavailable'):
            report.close()
    assert report.stream.closed
    assert report.dirty


def test_inventory_directory_sync_failure_prevents_status_sync_and_can_retry(report, monkeypatch):
    report.snapshot([regression.Category('Inventory', 1, nodeids=('case',))])
    synced = []

    def sync(fd):
        path = Path(os.readlink(f'/proc/self/fd/{fd}'))
        synced.append(path.name)
        if path == report.directory:
            raise OSError('directory unavailable')

    with monkeypatch.context() as patch:
        patch.setattr(regression.os, 'fsync', sync)
        with pytest.raises(OSError, match='directory unavailable'):
            report.checkpoint(force=True)
    assert 'inventory-001.json' in synced
    assert 'progress.json' not in synced
    assert report.directory / 'inventory-001.json' in report.dirty
    assert report.directory / 'progress.json' in report.dirty
    report.checkpoint(force=True)
    assert not report.dirty


def test_large_inventory_is_not_rewritten_with_live_counts(report, monkeypatch):
    item = regression.Category('Large', 2000, nodeids=tuple(
        f'test.py::case[{index}-' + 'x' * 200 + ']' for index in range(2000)))
    publications = []
    publish = report.publish

    def record(name, value):
        publications.append((name, len(json.dumps(value).encode())))
        publish(name, value)

    monkeypatch.setattr(report, 'publish', record)
    report.snapshot([item])
    legacy_bytes = len(json.dumps(dict(vars(item), done=item.progress_done,
                                     total=item.progress_total), indent=2).encode())
    for count in range(1, 21):
        item.done = count
        report.snapshot([item])
        legacy_bytes += len(json.dumps(dict(vars(item), done=item.progress_done,
                                           total=item.progress_total), indent=2).encode())
    assert sum(name.startswith('inventory-') for name, _ in publications) == 1
    assert sum(size for name, size in publications if name == 'progress.json') < 20000
    optimized_bytes = sum(size for _, size in publications)
    assert optimized_bytes < legacy_bytes / 10
    print(f'Report I/O benchmark: legacy={legacy_bytes} optimized={optimized_bytes} bytes')
    progress, = json.loads((report.directory / 'progress.json').read_text())
    inventory, = json.loads((report.directory / progress['inventory_file']).read_text())
    assert progress['inventory_index'] == 0 and progress['done'] == 20
    assert 'nodeids' not in progress and 'resumed_nodeids' not in progress
    assert inventory['nodeids'] == list(item.nodeids)
    before = list(publications)
    report.snapshot([item])
    assert publications == before
    item.resumed_nodeids = ('previous-pass',)
    item.failed_nodeids = (item.nodeids[0],)
    item.failures = 1
    report.snapshot([item])
    progress, = json.loads((report.directory / 'progress.json').read_text())
    inventory, = json.loads((report.directory / progress['inventory_file']).read_text())
    assert progress['done'] == 21 and progress['total'] == 2001
    assert progress['failed_nodeids'] == [item.nodeids[0]]
    assert inventory['resumed_nodeids'] == ['previous-pass']
    assert sum(name.startswith('inventory-') for name, _ in publications) == 2
    original, = json.loads((report.directory / 'inventory-001.json').read_text())
    assert original['resumed_nodeids'] == []


@pytest.mark.parametrize('failed_publication', ['inventory-002.json', 'progress.json'])
def test_inventory_revisions_preserve_saved_status_through_failed_publication(report, monkeypatch,
                                                                            failed_publication):
    items = [regression.Category('First', 1, nodeids=('first',)),
             regression.Category('Second', 1, nodeids=('second',), resumed_nodeids=('retained',))]
    report.snapshot(items)
    status = report.directory / 'progress.json'
    original = status.read_bytes()
    saved = json.loads(original)
    publish = report.publish

    def fail(name, value):
        if name == failed_publication:
            raise OSError('publication unavailable')
        publish(name, value)

    with monkeypatch.context() as patch:
        patch.setattr(report, 'publish', fail)
        with pytest.raises(OSError, match='publication unavailable'):
            report.snapshot(items[::-1])
    assert status.read_bytes() == original
    report.snapshot(items[::-1])
    for rows, expected in [(saved, items), (json.loads(status.read_text()), items[::-1])]:
        for row, item in zip(rows, expected):
            inventory = json.loads((report.directory / row['inventory_file']).read_text())
            entry = inventory[row['inventory_index']]
            assert entry == dict(name=item.name, nodeids=list(item.nodeids),
                                 resumed_nodeids=list(item.resumed_nodeids))
    assert {row['inventory_file'] for row in saved} == {'inventory-001.json'}
    assert {row['inventory_file'] for row in json.loads(status.read_text())} == {'inventory-002.json'}


@pytest.mark.parametrize('collect_only', [False, True])
def test_unit_workers_emit_inventory_without_running_cleanup(tmp_path, monkeypatch, collect_only,
                                                              private_dispatch_source):
    import test_launcher
    calls = []
    command = ['pytest', *(['--collect-only'] if collect_only else []),
               '--', 'tests/unit/test_core.py']
    controller = SimpleNamespace(run=lambda command, **kwargs: calls.append((command, kwargs)) or 0)
    monkeypatch.setattr(regression_process.Control, 'installed', lambda *args, **kwargs: nullcontext(controller))
    monkeypatch.setattr(test_launcher, 'pytest_command', lambda *args: command)
    assert regression_process.host_run(tmp_path, 'unit', []) == 0
    assert len(calls) == 1
    assert calls[0][0] == command
    assert calls[0][1]['env']['ONPC_REGRESSION_EVENTS'] == '1'
    assert calls[0][1]['env']['ONPC_REGRESSION_INVENTORY'] == '1'


@pytest.mark.parametrize('verified', [False, True])
@pytest.mark.parametrize('category', ['ui', 'component'])
def test_host_workers_never_launch_cleanup_tests(tmp_path, monkeypatch, verified, category,
                                               private_dispatch_source):
    import test_activity
    import test_launcher
    calls = []
    controller = SimpleNamespace(run=lambda command, **kwargs: calls.append(command) or 0)
    monkeypatch.setattr(regression_process.Control, 'installed', lambda *args, **kwargs: nullcontext(controller))
    monkeypatch.setattr(test_launcher, 'pytest_command', lambda *args: ['pytest', 'selected'])
    monkeypatch.setattr(test_activity, 'cleanup_verified', lambda root: verified)
    monkeypatch.setattr(regression_process, 'safety_command', lambda root: ['safety'])
    assert regression_process.host_run(tmp_path, category, []) == 0
    assert calls == [['pytest', 'selected']]


@pytest.mark.parametrize('category', ['fixture-runtime', 'publish', 'artifacts', 'system', 'e2e'])
def test_dispatch_preserves_build_inputs_without_adding_cleanup_tests(tmp_path, monkeypatch, category,
                                                                     private_dispatch_source):
    import test_activity
    import test_retention
    calls = []
    plans = []
    def plan(root, selected_category, argv):
        plans.append((root, selected_category, argv))
        return [['selected']], True

    if category in ('system', 'e2e'):
        # Model the VM-aware artifact preparer in the confined checkout without running it
        # or allocating an untracked directory outside this test's fixture.
        preparer = tmp_path / 'tools/vm_artifacts.py'
        preparer.parent.mkdir()
        preparer.touch()
        artifacts = tmp_path / 'artifacts'
        artifacts.mkdir()
        monkeypatch.setattr(test_retention, 'allocate', lambda *args, **kwargs: str(artifacts))
    controller = SimpleNamespace(run=lambda command, **kwargs: calls.append(command) or 0)
    monkeypatch.setattr(regression_process.Control, 'installed', lambda *args, **kwargs: nullcontext(controller))
    monkeypatch.setattr(test_commands, 'plan', plan)
    # Like the command plan, preparation options belong to the synthetic selection;
    # do not send its placeholder argument through the real E2E preflight parser.
    monkeypatch.setattr(test_commands, 'vm_preparation_flags', lambda category, argv: [])
    # Fixture production has its own dispatch coverage; this synthetic checkout
    # exercises package preparation and must not start the real fixture builder.
    monkeypatch.setattr(test_commands, 'qualification_fixture_options', lambda *args, **kwargs: [])
    monkeypatch.setattr(test_activity, 'cleanup_verified', lambda root: True)
    monkeypatch.setattr(regression_process, 'safety_command', lambda root: ['safety'])
    assert regression_process.category_run(tmp_path, category, ['verify']) == 0
    expected = [['selected']]
    expected_plans = [(tmp_path, category, ['verify'])]
    if category in ('system', 'e2e'):
        expected.insert(0, ['/usr/bin/python3', '-B', str(preparer), '--output', str(artifacts),
                            '--vm', vm_name()])
        expected_plans.append((tmp_path, category, ['verify', '--artifacts=' + str(artifacts)]))
    assert calls == expected
    assert plans == expected_plans


def test_host_worker_failure_propagates_without_extra_tests(tmp_path, monkeypatch, private_dispatch_source):
    import test_activity
    import test_launcher
    calls = []
    controller = SimpleNamespace(run=lambda command, **kwargs: calls.append(command) or 1)
    monkeypatch.setattr(regression_process.Control, 'installed', lambda *args, **kwargs: nullcontext(controller))
    monkeypatch.setattr(test_launcher, 'pytest_command', lambda *args: ['pytest', 'selected'])
    monkeypatch.setattr(test_activity, 'cleanup_verified', lambda root: False)
    monkeypatch.setattr(regression_process, 'safety_command', lambda root: ['safety'])
    assert regression_process.host_run(tmp_path, 'ui', []) == 1
    assert calls == [['pytest', 'selected']]


@pytest.mark.parametrize('installed', ['--unattended', '--skip-backing-verification',
                                     '--unattended --skip-backing-verification',
                                     '--unattended --skip-backing-verification --retention-run='])
def test_old_dispatcher_is_refused_before_expensive_suites(monkeypatch, installed):
    import dev_privileges
    monkeypatch.setattr(dev_privileges, 'check', lambda _: None)
    monkeypatch.setattr(regression.Path, 'read_text', lambda _: installed)
    if all(value in installed for value in ('--unattended', '--skip-backing-verification', '--retention-run=')):
        regression.authorization()
    else:
        with pytest.raises(ValueError, match='setup.sh --test-tools-only'):
            regression.authorization()


@pytest.mark.parametrize('slots', [1, 2, 3, 4])
def test_live_branch_assignment_matches_actual_overlap_and_is_saved(report, tmp_path, slots):
    release = threading.Event()
    coordinator = threading.get_ident()
    class Commands(Control):
        def run(self, command, **kwargs):
            if command == ['long'] and slots > 1:
                assert release.wait(5)
            return 0
    run = regression.Run(tmp_path, report, Commands())
    run.dashboard.stream = io.StringIO()
    run.admission = SimpleNamespace(reason='at capacity',
        allows=lambda kind, active: len(active) < slots)
    names = ['long', 'short1', 'short2']
    if slots >= 4:
        names.extend(f'short{index}' for index in range(3, slots))
    items = [regression.Category(name, 1) for name in names]
    run.categories.extend(items)
    original = regression.Execution.finish
    def finish(execution, status):
        assert threading.get_ident() == coordinator
        if execution.item is items[-1]:
            release.set()
        return original(execution, status)
    from regression_schedule import Job
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(regression.Execution, 'finish', finish)
        run.host_jobs([Job(item.name, item, [item.name], estimate=10 - index)
                       for index, item in enumerate(items)])
    expected = {1: [1, 1, 1], 2: [1, 2, 2], 3: [1, 2, 3],
                4: [1, 2, 3, 4]}[slots]
    assert [item.branch for item in items] == expected
    saved = json.loads((report.directory / 'progress.json').read_text())[1:]
    assert [item['branch'] for item in saved] == expected
    assert all(item['state'] == 'Passed' for item in saved)


@pytest.mark.parametrize('continue_on_errors', [False, True])
@pytest.mark.parametrize('events', [False, True])
def test_first_failure_cancels_and_finalizes_with_handoff(
        tmp_path, monkeypatch, capsys, continue_on_errors, events):
    runs = []
    monkeypatch.setattr(regression_process, 'session_stop', threading.Event())

    def execute(run):
        runs.append(run)
        item = run.categories[0]
        item.retry_category = 'unit'
        execution = regression.Execution(run, item, events=events)
        if events:
            execution.output((regression.PREFIX + json.dumps(dict(
                kind='collection', total=1)) + '\n').encode())
            execution.output((regression.PREFIX + json.dumps(dict(
                kind='failure', nodeid='case', when='call')) + '\n').encode())
            assert run.control.stopped.is_set() is not continue_on_errors
            assert json.loads((run.report.directory / 'progress.json').read_text())[0]['failures'] == 1
        execution.output(b'normal owned cleanup finished\n')
        execution.finish(1)
        assert run.control.stopped.is_set() is not continue_on_errors

    monkeypatch.setattr(regression.Run, 'run', execute)
    assert regression.main(tmp_path, continue_on_errors=continue_on_errors) == 1
    run = runs[0]
    assert run.categories[0].state == 'Failed'
    assert run.report.stream.closed
    assert 'normal owned cleanup finished' in (run.report.directory / 'report.md').read_text()
    saved = json.loads((run.report.directory / 'progress.json').read_text())
    assert saved[0]['state'] == 'Failed'
    assert run.report.retention_session is None
    assert f'Failure handoff: {run.report.directory / "failure.json"}' in capsys.readouterr().out
    failure = json.loads((run.report.directory / 'failure.json').read_text())
    assert failure['failures'] == [dict(category=run.categories[0].retry_category,
                                      case='case' if events else '', vm='')]


def test_partial_failure_is_durable_before_cancellation(report, tmp_path):
    item = regression.Category('Fixture', 1)
    control = Control()
    run = regression.Run(tmp_path, report, control)
    run.categories.append(item)
    class Child:
        def run(self, command, **kwargs):
            kwargs['output'](b'failure diagnostic without newline')
            assert 'failure diagnostic without newline' in (report.directory / 'report.md').read_text()
            control.stop()
            return 130
        stopped = control.stopped
    run.control = Child()
    status, _ = run.execute(item, ['unused'])
    assert status == 130 and item.state == 'Interrupted'
    assert item.done == 0


@pytest.mark.parametrize('cancelled', [False, True])
def test_truncated_inventory_at_eof_requires_cancellation(report, tmp_path, cancelled):
    nodes = ('tests/unit/test_sample.py::test_first',)
    control = Control()
    run = regression.Run(tmp_path, report, control, host_only=True)
    run.dashboard.stream = io.StringIO()
    item = regression.Category('Truncated collector', 1, nodeids=nodes,
                               retry_category='unit')
    run.categories.append(item)
    execution = regression.Execution(run, item, events=True)
    fragment = (regression.PREFIX + '{"kind":"collection","nodeids":["test').encode()
    try:
        execution.output(fragment)
        if cancelled:
            control.stop()
            assert execution.finish(130)[0] == 130
            assert item.state == 'Interrupted'
            assert item.nodeids == nodes and item.total == 1 and item.done == 0
            assert not execution.inventory_seen
            assert regression.failure_targets([item]) == []
        else:
            with pytest.raises(json.JSONDecodeError):
                execution.finish(0)
            assert item.state != 'Passed'
        assert Path(execution.raw.name).read_bytes() == fragment
    finally:
        execution.close()


def test_cancelled_complete_malformed_event_still_refused(report, tmp_path):
    control = Control()
    run = regression.Run(tmp_path, report, control, host_only=True)
    run.dashboard.stream = io.StringIO()
    item = regression.Category('Malformed collector', 1, retry_category='unit')
    run.categories.append(item)
    execution = regression.Execution(run, item, events=True)
    try:
        control.stop()
        with pytest.raises(json.JSONDecodeError):
            execution.output((regression.PREFIX + '{"kind":\n').encode())
        assert item.state != 'Passed' and item.done == 0
    finally:
        execution.close()


@pytest.mark.parametrize('partial', [False, True])
@pytest.mark.parametrize('cancelled', [False, True])
def test_interrupted_collection_preserves_assigned_inventory_and_requires_cancellation(
        report, tmp_path, monkeypatch, partial, cancelled):
    nodes = ('tests/unit/test_sample.py::test_first',
             'tests/unit/test_sample.py::test_second')
    control = Control()
    run = regression.Run(tmp_path, report, control, host_only=True)
    run.dashboard.stream = io.StringIO()
    item = regression.Category('Interrupted collector', len(nodes), nodeids=nodes,
                               retry_category='unit')
    run.categories.append(item)
    execution = regression.Execution(run, item, events=True)
    session = SimpleNamespace(
        items=[SimpleNamespace(nodeid=nodes[0])] if partial else [],
        config=SimpleNamespace(option=SimpleNamespace(collectonly=False)))
    monkeypatch.setenv('ONPC_REGRESSION_EVENTS', '1')
    monkeypatch.setenv('ONPC_REGRESSION_INVENTORY', '1')
    monkeypatch.setattr(regression_events, 'emit', lambda kind, **fields:
        execution.output((regression.PREFIX + json.dumps(dict(kind=kind, **fields))
                          + '\n').encode()))
    try:
        if cancelled:
            control.stop()
        try:
            raise KeyboardInterrupt('private collection detail')
        except KeyboardInterrupt:
            regression_events.pytest_collection_finish(session)
        assert not execution.inventory_seen
        assert item.nodeids == nodes and item.total == len(nodes) and item.done == 0
        execution.output(b'owned cleanup finished\n')
        if cancelled:
            assert execution.finish(130)[0] == 130
            assert item.state == 'Interrupted' and item.failures == 0
            assert regression.failure_targets([item]) == []
            saved = json.loads((report.directory / 'progress.json').read_text())[-1]
            assert saved['state'] == 'Interrupted' and saved['done'] == 0
            assert saved['total'] == len(nodes)
        else:
            with pytest.raises(ValueError, match='missing test execution inventory'):
                execution.finish(2)
            assert item.state != 'Passed'
        raw = Path(execution.raw.name).read_text()
        assert 'collection_interrupted' in raw and 'owned cleanup finished' in raw
        assert 'private collection detail' not in raw
    finally:
        execution.close()


@pytest.mark.parametrize('cancelled', [False, True])
@pytest.mark.parametrize('fields,message', [
    (dict(total=0, nodeids=[]), 'test inventory changed after collection'),
    (dict(total=1, nodeids=['changed-case']), 'test inventory IDs changed after collection'),
    (dict(total=1), 'missing test inventory IDs'),
])
def test_completed_collection_inventory_guards_remain_active_during_cancellation(
        report, tmp_path, cancelled, fields, message):
    control = Control()
    run = regression.Run(tmp_path, report, control, host_only=True)
    run.dashboard.stream = io.StringIO()
    item = regression.Category('Invalid inventory', 1, nodeids=('assigned-case',))
    run.categories.append(item)
    execution = regression.Execution(run, item, events=True)
    try:
        if cancelled:
            control.stop()
        with pytest.raises(ValueError, match=message):
            execution.output((regression.PREFIX + json.dumps(dict(kind='collection', **fields))
                              + '\n').encode())
        assert item.state != 'Passed' and item.done == 0
    finally:
        execution.close()


@pytest.mark.parametrize('outcome', ['passed', 'failed', 'fail-fast', 'error', 'interrupted', 'interrupted-failure'])
def test_saved_investigation_prompt_links_closed_report(tmp_path, monkeypatch, capsys, outcome):
    import evidence_bundle
    import runner_evidence
    def no_archive(*_args, **_kwargs):
        pytest.fail('ordinary report attempted archival proof collection or recovery')
    monkeypatch.setattr(runner_evidence, 'ReportEvidence', no_archive)
    monkeypatch.setattr(runner_evidence, 'recover_pending', no_archive)
    monkeypatch.setattr(evidence_bundle, 'export', no_archive)
    runs = []

    def execute(run):
        runs.append(run)
        item = run.categories[0]
        item.done = 1
        item.failures = int(outcome in ('failed', 'fail-fast', 'interrupted-failure'))
        item.state = 'Failed' if item.failures else 'Passed'
        run.report.write('\nDetailed failure evidence stays in this report.\n')
        if outcome.startswith('interrupted'):
            run.control.stopped.set()
        if outcome == 'fail-fast':
            run.control.fail()
            monkeypatch.setattr(run, 'result_status', lambda: 130)
        if outcome == 'error':
            raise ValueError('discovery failure detail')

    monkeypatch.setattr(regression.Run, 'run', execute)
    status = regression.main(tmp_path)
    output = capsys.readouterr().out
    run = runs[0]
    assert run.report.stream.closed
    assert status == (130 if outcome.startswith('interrupted') else
                      0 if outcome == 'passed' else 1)
    assert 'Copy this prompt into a new Codex session:' not in output
    assert 'Investigate and fix the failures in ' not in output
    handoff = run.report.directory / 'failure.json'
    if outcome in ('passed', 'interrupted'):
        assert not handoff.exists()
        assert 'Failure handoff: ' not in output
    else:
        prompt = json.loads(handoff.read_text())['prompt']
        assert f'Failure handoff: {handoff}' in output
        assert str(tmp_path) in prompt
        assert str(run.report.directory / 'report.md') in prompt
        assert 'progress.json' in prompt
        assert 'rerun the relevant checks' in prompt
        assert 'tools/prepare-vm --vm NAME --mode auto --y' in prompt
        assert 'tools/prepare-appsnapshot --vm NAME --y' in prompt
        assert 'omit it for manual work' in prompt
        assert 'Detailed failure evidence' not in prompt
        assert output.index('Failure handoff: ') > output.rindex('Overall - ')
        assert '## Final result' in (run.report.directory / 'report.md').read_text()
        assert '<pre>' in (run.report.directory / 'report.md').read_text()


def test_report_initialization_failure_exposes_cause(tmp_path, monkeypatch, capsys):
    def broken(_):
        raise PermissionError('report directory is not writable')

    monkeypatch.setattr(regression, 'Report', broken)
    assert regression.main(tmp_path) == 1
    output = capsys.readouterr()
    assert 'Report initialization - 0% (0/1)' in output.out
    assert ('Report initialization failed: PermissionError: '
            'report directory is not writable') in output.err


def test_report_rejects_symlinked_parent(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    (tmp_path / 'output').symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        regression.Report(tmp_path)
    assert not list(outside.iterdir())


def test_report_registration_lost_sync_reply_preserves_committed_allocation(tmp_path, monkeypatch):
    import test_retention
    import test_storage
    retain = test_retention.retain
    def committed_then_failed(path, **kwargs):
        retain(path, **kwargs)
        raise OSError('synthetic lost registration sync reply')
    monkeypatch.setattr(test_retention, 'retain', committed_then_failed)
    with pytest.raises(OSError, match='lost registration sync reply'):
        regression.Report(tmp_path)
    store = test_retention.Store(test_storage.directory('state', root=tmp_path) / 'standalone-reports')
    with store.inspection() as state:
        allocation, = state['paths']
        assert Path(allocation['path']).is_dir()
        assert state['finished'] is True


def test_new_fixture_test_is_discovered_without_runner_edit(tmp_path):
    directory = tmp_path / 'tests/fixtures'
    directory.mkdir(parents=True)
    first = directory / 'test_one.py'
    first.touch()
    before, _ = test_commands.plan(tmp_path, 'fixture-runtime', [])
    second = directory / 'test_two.py'
    second.touch()
    after, _ = test_commands.plan(tmp_path, 'fixture-runtime', [])
    assert str(second) not in before[0] and str(second) in after[0]
    second.unlink()
    second.symlink_to(first)
    with pytest.raises(ValueError):
        test_commands.plan(tmp_path, 'fixture-runtime', [])


def test_internal_cancellation_is_a_failure_and_storage_failure_closes_report(tmp_path, monkeypatch):
    (tmp_path / 'docs/TestAutomation/Evidence').mkdir(parents=True)
    reports = []
    def execute(run):
        reports.append(run.report)
        run.control.stop()
        raise ValueError('changed source inputs')
    monkeypatch.setattr(regression.Run, 'run', execute)
    assert regression.main(tmp_path) == 1
    assert reports[-1].stream.closed
    def broken(*_):
        raise OSError('disk full')
    monkeypatch.setattr(regression.Report, 'snapshot', broken)
    assert regression.main(tmp_path) == 1
    assert reports[-1].stream.closed


def test_pytest_failure_precedes_suite_completion(tmp_path):
    root = Path(__file__).resolve().parents[2]
    test = tmp_path / 'test_sample.py'
    test.write_text('def test_failure():\n    assert False, "immediate failure"\n')
    env = dict(os.environ, PYTHONPATH=str(root / 'tools'), ONPC_REGRESSION_EVENTS='1')
    result = subprocess.run([sys.executable, '-m', 'pytest', '-p', 'regression_events',
                             '--noconftest', '-q', str(test)], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    output = result.stdout.decode()
    assert result.returncode == 1
    failure = output.index('"kind": "failure"')
    finished = output.index('"kind": "finished"')
    assert failure < finished
    assert 'immediate failure' in output[failure:finished]


@pytest.mark.parametrize('phase', ['setup', 'teardown'])
def test_fixture_failure_cancels_before_exit_and_retains_cleanup(report, tmp_path, monkeypatch, phase):
    control = Control()
    run = regression.Run(tmp_path, report, control, host_only=True)
    item = regression.Category('Failing fixture', 1)
    run.categories.append(item)
    execution = regression.Execution(run, item, events=True)
    synced = set()
    monkeypatch.setattr(regression.os, 'fsync',
                        lambda fd: synced.add(Path(os.readlink(f'/proc/self/fd/{fd}')).name))
    original_stop = control.stop

    def stop_after_persistence():
        assert {'category-001.log', 'report.md', 'progress.json'} <= synced
        original_stop()

    monkeypatch.setattr(control, 'stop', stop_after_persistence)
    failure = (regression.PREFIX + json.dumps(dict(
        kind='failure', nodeid='case', when=phase, detail='storage unavailable')) + '\n').encode()
    # A split pipe event cannot cancel before its complete durable record.
    execution.output(failure[:-1])
    assert not control.stopped.is_set()
    execution.output(failure[-1:])
    assert control.stopped.is_set()
    assert 'storage unavailable' in (report.directory / 'category-001.log').read_text()
    # The coordinator must still accept trailing owned-cleanup output.
    execution.output(b'owned cleanup finished\n')
    with pytest.raises(ValueError, match='fixture setup or cleanup failed'):
        execution.finish(130)
    assert item.state == 'Failed' and item.failures == 1
    assert 'owned cleanup finished' in (report.directory / 'category-001.log').read_text()


def test_guest_event_parser_never_forwards_unregistered_or_raw_secrets(capsys):
    parser = Progress('enforcement', [SimpleNamespace(case_id='test_allowed')])
    prefix = regression_events.PREFIX
    parser(b'password=secret\n')
    event = prefix + json.dumps(dict(kind='failure', nodeid='test.py::test_allowed',
                                     detail='password=secret')) + '\n'
    parser(event[:12].encode())
    parser(event[12:].encode())
    parser((prefix + json.dumps(dict(kind='finished', nodeid='test.py::unregistered')) + '\n').encode())
    output = capsys.readouterr().out
    assert 'enforcement::test_allowed' in output
    assert 'secret' not in output and 'unregistered' not in output


def test_skipped_pytest_case_prevents_false_green(monkeypatch, capsys):
    monkeypatch.setenv('ONPC_REGRESSION_EVENTS', '1')
    events = []
    monkeypatch.setattr(regression_events, 'emit', lambda kind, **fields: events.append((kind, fields)))
    regression_events.pytest_runtest_logreport(SimpleNamespace(
        failed=False, skipped=True, longrepr='missing prerequisite', nodeid='test_skipped', when='setup'))
    assert events == [('failure', dict(nodeid='test_skipped', when='setup', detail='missing prerequisite'))]


@pytest.mark.parametrize('fresh', [False, True])
def test_private_guest_failure_is_fsynced_before_public_event(tmp_path, monkeypatch, fresh):
    if fresh:
        tmp_path = tmp_path / 'results'
    monkeypatch.setenv('ONPC_REGRESSION_EVENTS', '1')
    monkeypatch.setenv('ONPC_REGRESSION_PRIVATE', str(tmp_path))
    events = []
    def emit(kind, **fields):
        assert 'private failure detail' in (tmp_path / 'regression-failures.jsonl').read_text()
        events.append(fields)
    monkeypatch.setattr(regression_events, 'emit', emit)
    regression_events.pytest_runtest_logreport(SimpleNamespace(
        failed=True, skipped=False, longrepr='private failure detail', nodeid='test_failed', when='call'))
    assert 'private failure detail' not in events[0]['detail']


def test_generated_reports_and_retention_are_ignored_by_source_provenance(tmp_path):
    root = Path(__file__).resolve().parents[2]
    # Debian source builds contain the ignore rules, but no checkout metadata.
    (tmp_path / '.gitignore').write_bytes((root / '.gitignore').read_bytes())
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    result = subprocess.run(['git', 'check-ignore',
                             'docs/TestAutomation/Evidence/test-all-runs/example/report.md'],
                            cwd=tmp_path, stdout=subprocess.PIPE, check=False)
    assert result.returncode == 0
    before = regression.source_identity(tmp_path)
    for relative in ('docs/TestAutomation/Evidence/test-all-runs/example/report.md',
                     'artifacts/test-retention/current.json', 'artifacts/test-retention/current.tmp',
                     'artifacts/test-retention/owner.lock', 'artifacts/test-retention/writer.lock',
                     'artifacts/test-retention/recovery-required'):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('generated state')
    assert regression.source_identity(tmp_path) == before
    (tmp_path / 'tools').mkdir()
    (tmp_path / 'tools/test_retention.py').write_text('changed implementation')
    assert regression.source_identity(tmp_path) != before


@pytest.mark.parametrize('output,previous,key', [
    ('', {}, 'build-a'),
    ('run-tests: output=/tmp/onpc-test-artifacts-a\n' * 2, {}, 'build-a'),
    ('run-tests: output=/tmp/onpc-test-artifacts-a', {'build-a': '/tmp/onpc-test-artifacts-a'}, 'build-b'),
    ('run-tests: output=/tmp/onpc-test-artifacts-b', {'build-a': '/tmp/onpc-test-artifacts-a'}, 'build-a'),
    ('run-tests: output=/tmp/foreign', {}, 'build-a'),
])
def test_invalid_builder_output_cannot_unlock_reproducibility(report, tmp_path, output, previous, key):
    from regression_schedule import Job
    run = regression.Run(tmp_path, report, Control())
    run.artifacts = previous.copy()
    item = regression.Category('build', 1, 1, 'Passed')
    run.categories.append(item)
    with pytest.raises(ValueError, match='package build output invalid'):
        run.complete_host(Job('artifacts', item, [], key=key), (0, output))
    assert item.state == 'Failed' and item.failures == 1
    assert run.artifacts == previous


def test_serial_builder_samples_resources_while_running_and_labels_the_observation(report, tmp_path):
    class Commands(Control):
        def run(self, command, **kwargs):
            for _ in range(3):
                kwargs['tick']()
            return 0

    run = regression.Run(tmp_path, report, Commands())
    run.wait_for_resources = lambda *_: None
    run.admission.update = lambda: run.observe_resources({'available': True, 'available_memory': 123})
    item = regression.Category('Publishing tests', 1)
    run.categories.append(item)
    assert run.execute(item, ['launcher', 'publish'])[0] == 0
    samples = [json.loads(line) for line in (report.directory / 'resources.jsonl').read_text().splitlines()]
    assert len(samples) == 3
    assert all(sample['running_categories'] == ['Publishing tests'] for sample in samples)
    assert item.state == 'Passed'


@pytest.mark.parametrize('failure', [None, 'build-a', 'build-b', 'publish-rpm'])
def test_independent_builds_finish_in_reverse_order_with_host_and_publishing_active(
        report, tmp_path, failure):
    entered = threading.Barrier(4)
    b_validated, a_validated = threading.Event(), threading.Event()
    completed = []

    class Commands(Control):
        def stop(self):
            super().stop()
            b_validated.set()
            a_validated.set()

        def run(self, command, *, output, **kwargs):
            key = command[0]
            if key != 'compare':
                entered.wait(5)
            if key == 'build-a':
                assert b_validated.wait(5), 'build B could not finish independently'
            elif key in ('publish-deb', 'publish-rpm'):
                assert a_validated.wait(5), 'builds waited for publishing or host work'
            if key.startswith('build-'):
                output(f'run-tests: output=/tmp/onpc-test-artifacts-{key}\n'.encode())
            if key == 'compare':
                assert command[1:] == ['/tmp/onpc-test-artifacts-build-a',
                                       '/tmp/onpc-test-artifacts-build-b']
            return int(key == failure)

    run = regression.Run(tmp_path, report, Commands(), host_builds=True, continue_on_errors=True)
    run.dashboard.stream = io.StringIO()
    run.admission = SimpleNamespace(allows=lambda *_: True)
    publishing = [regression.Category(name, 1) for name in ('DEB publishing', 'RPM publishing')]
    builds = [regression.Category(name, 1) for name in ('A', 'B', 'Comparison')]
    jobs = run.build_jobs(publishing, builds)
    original_complete = run.complete_host

    def complete(job, result):
        original_complete(job, result)
        completed.append(job.key)
        if job.key == 'build-b':
            b_validated.set()
        if job.key == 'build-a':
            a_validated.set()

    run.complete_host = complete
    # Use short fake commands, retaining the production graph and deferred
    # comparison lookup. Both real builders normally have identical argv.
    run.command = lambda kind, *args: ['compare', *args[1:]]
    for job in jobs[:4]:
        assert job.requires == ()
        job.command = [job.key]
    run.categories = [*publishing, *builds]
    run.host_jobs(jobs)
    assert completed.index('build-b') < completed.index('build-a')
    assert all(completed.index('build-a') < completed.index(kind)
               for kind in ('publish-deb', 'publish-rpm'))
    assert publishing[0].state == 'Passed'
    assert publishing[1].state == ('Failed' if failure == 'publish-rpm' else 'Passed')
    assert builds[2].state == ('Blocked' if failure in ('build-a', 'build-b') else 'Passed')
    assert set(run.artifacts) == {'build-a', 'build-b'} - {failure}


@pytest.mark.parametrize('io_burst', [False, True])
def test_real_host_plan_refills_branches_promptly(report, tmp_path, monkeypatch, io_burst):
    # Representative discovery sizes from the reported run. Run.run builds the
    # actual jobs, estimates and dependencies; do not duplicate its job ordering.
    inventory = {name: [f'tests/ui/{name}::test_{index}' for index in range(count)]
                 for name, count in [('test_request_form_component.py', 58),
                                     ('test_preview_smoke.py', 23),
                                     ('test_request_layout.py', 22),
                                     ('test_parent_feedback.py', 8),
                                     ('test_child_shell_lifecycle.py', 3)]}
    state = SimpleNamespace(now=100.0)
    monkeypatch.setattr(regression.time, 'monotonic', lambda: state.now)
    monkeypatch.setattr(regression, 'source_identity', lambda _: 'stable-inputs')
    import test_activity
    monkeypatch.setattr(test_activity, 'record_cleanup', lambda _: None)
    releases, scheduled = {}, []
    durations = {'DEB publishing tests': 40, 'Unit — Bucket 1': 12,
                 'UI — Request behavior': 80}
    import regression_unit
    monkeypatch.setitem(regression_unit.ESTIMATES, 'test_core.py', 150)
    unit_nodes = ('tests/unit/test_core.py::test_case',)

    class Workers(ThreadPoolExecutor):
        def submit(self, function, execution, command):
            release = releases[id(execution)] = threading.Event()
            def work():
                assert release.wait(30), 'simulated child was not released'
                return function(execution, command)
            future = super().submit(work)
            scheduled.append((state.now + durations.get(execution.item.name, 2),
                              release, future))
            return future

    class Commands(Control):
        builds = 0

        def stop(self):
            super().stop()
            for release in releases.values():
                release.set()

        def run(self, command, *, output, **kwargs):
            category = 'ui' if command[0].endswith('run-ui-tests') else command[1]
            if category in ('unit', 'component', 'fixture-runtime', 'ui'):
                nodes = ([node for ids in inventory.values() for node in ids
                          if node.partition('::')[0] in command] if category == 'ui' else
                         unit_nodes if category == 'unit' else ['case'])
                events = [dict(kind='collection', total=len(nodes), nodeids=nodes),
                          *(dict(kind='finished', nodeid=node) for node in nodes)]
                output(''.join(regression_events.PREFIX + json.dumps(event) + '\n'
                               for event in events).encode())
            elif category == 'artifacts' and ('build' in command or 'prepare' in command):
                self.builds += 1
                output(f'run-tests: output=/tmp/onpc-test-artifacts-refill{self.builds}\n'.encode())
            return 0

    run = regression.Run(tmp_path, report, Commands(), host_builds=True)
    run.dashboard.stream = io.StringIO()

    def discover(item, command, *, collect=False, **kwargs):
        # Only discovery and the prerequisite gate are simulated here. Host
        # jobs go through the real run_jobs/Execution/Commands.run path above.
        assert collect or (command[1] == 'unit' and any('cleanup_safety' in arg for arg in command))
        item.total = 1
        if command[0].endswith('run-ui-tests'):
            item.nodeids = tuple(node for ids in inventory.values() for node in ids)
            item.total = len(item.nodeids)
        elif command[1] == 'unit':
            item.nodeids = unit_nodes
        if not collect:
            item.done, item.state = item.total, 'Passed'
        return 0, ''

    def sample():
        io = 12 if io_burst and 140 <= state.now < 142 else (3 if state.now < 150 else 0)
        return Sample(20, 2, 32 * GIB, 24 * GIB, 0, 0, io, False)

    run.execute = discover
    # This test's simulated clock/pressure window describes the downstream
    # host queue. Cleanup phase ordering is exercised separately below.
    run.cleanup_jobs = lambda safety: None
    run.admission = Admission(SimpleNamespace(sample=sample), lambda: state.now)
    scheduler = regression.run_jobs

    def dispatch(jobs, **kwargs):
        original_tick = kwargs['tick']

        def tick():
            original_tick()
            state.now += 2
            assert state.now < 400, 'scheduler stranded ready work'
            due = [(release, future) for deadline, release, future in scheduled
                   if deadline <= state.now and not release.is_set()]
            for release, _ in due:
                release.set()
            # Make completion visible before the next coordinator pass, without
            # races between simulated time and the real worker threads.
            for _, future in due:
                assert future.result(timeout=5) == 0

        try:
            return scheduler(jobs, **{**kwargs, 'tick': tick})
        finally:
            for release in releases.values():
                release.set()

    monkeypatch.setattr(regression_schedule, 'ThreadPoolExecutor', Workers)
    monkeypatch.setattr(regression, 'run_jobs', dispatch)
    run.run()
    events = [json.loads(line) for line in (report.directory / 'schedule.jsonl').read_text().splitlines()]
    starts = {event['job']: event for event in events if event['event'] == 'start'}
    finishes = {event['job']: event for event in events if event['event'] == 'finish'}
    assert list(starts)[:4] == ['UI — Request behavior', 'publish-deb', 'Unit — Bucket 1', 'publish-rpm']
    component, unit = starts['Private D-Bus components'], starts['Unit — Bucket 1']
    assert unit['branch'] == 3 and component['branch'] == 4
    assert 0 <= component['monotonic'] - unit['monotonic'] <= 5
    preview = starts['UI — Preview smoke']
    assert preview['branch'] == starts['publish-deb']['branch']
    assert 0 <= preview['monotonic'] - finishes['publish-deb']['monotonic'] <= (10 if io_burst else 5)
    assert 'ui-request' in starts['publish-deb']['companions']
    assert 'publish-deb' in starts['publish-rpm']['companions']
    assert starts['build-a']['companions']
    assert starts['build-b']['companions']
    assert starts['compare']['monotonic'] >= finishes['build-a']['monotonic']
    assert starts['compare']['monotonic'] >= finishes['build-b']['monotonic']
    assert set(starts) == set(finishes)
    assert all(event['state'] == 'Passed' for event in finishes.values())
