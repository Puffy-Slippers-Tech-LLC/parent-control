"""Discovery, honest progress, immediate failure reporting and provenance."""
from tests.support.vm_registry import vm_name

import io
from contextlib import contextmanager, nullcontext
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
from regression_process import Control
import test_commands
from system_progress import Progress


@pytest.mark.parametrize('qualification', [False, True])
def test_e2e_subcategory_routes_only_matching_workers(tmp_path, monkeypatch, qualification):
    import runpy
    import vm_test_queue
    import vm_recording
    import vm_run_times
    from fix_tests import validation_command
    from test_results import classic_profile

    root = Path(__file__).resolve().parents[2]
    runner = runpy.run_path(str(root / 'tests/e2e/runner.py'))
    selected = ({'subcategory': 'e2e-heavy'} if qualification else {'cases': [
        {'subcategory': 'general', 'coverage_id': identity} for identity in (3, 22, 30)
    ] + [{'subcategory': 'e2e-heavy', 'coverage_id': 126}]})

    def preflight(args, **kwargs):
        if classic_profile(args):
            return {'desktop_session': 'gnome-classic', 'cases': [
                case for case in selected['cases'] if case['coverage_id'] in (22, 30)]}
        if '--subcategory' in args:
            tag = args[args.index('--subcategory') + 1]
            return {'cases': [case for case in selected['cases'] if case['subcategory'] == tag]}
        return selected

    monkeypatch.setattr(test_commands, 'validate_one', lambda *args: None)
    monkeypatch.setattr(runpy, 'run_path', lambda path: {**runner, 'preflight': preflight})
    workers = [SimpleNamespace(name=f'{family}-{tag}', family=family, vm_tags={tag},
                   require_build_target=lambda distribution=distribution: SimpleNamespace(distribution=distribution))
               for family, distribution in (('fedora44', 'fedora'), ('fedora45', 'fedora'), ('ubuntu26', 'ubuntu'))
               for tag in ('general', 'heavy')]
    general = [vm.name for vm in workers if 'general' in vm.vm_tags]
    heavy = [vm.name for vm in workers if 'heavy' in vm.vm_tags]
    options = ['--qualify-lunar-profile'] if qualification else []
    groups = vm_test_queue.execution_groups(tmp_path, ['e2e', *options], workers)
    assert [(group['key'], group['vm_tags'], group['vms']) for group in groups] == (
        [('e2e.general', 'general', general), ('e2e.general.gnome-classic', 'general', general[:2])]
        if not qualification else []) + [('e2e.e2e-heavy', 'heavy', heavy)]
    assert groups[-1]['args'] == ['e2e', *options, '--subcategory', 'e2e-heavy']
    if not qualification:
        assert groups[1]['args'] == ['e2e', '--subcategory=gnome-classic', '--id=22,30']
        retry = vm_test_queue.execution_groups(tmp_path,
            ['--resume', '--resume-case=E2E-008/fresh-login', '--resume-case-only', 'e2e', '--subcategory', 'general'],
            workers)
        assert [group['key'] for group in retry] == ['e2e.general']
        repair = validation_command({'category': 'e2e', 'case': 'E2E-008/fresh-login',
                                     'options': groups[1]['args'][1:], 'vm': workers[0].name})
        retry = vm_test_queue.execution_groups(tmp_path, repair[1:-2], [workers[0]])
        assert [group['key'] for group in retry] == ['e2e.general.gnome-classic']
        assert classic_profile(retry[0]['args'])
    with pytest.raises(ValueError, match='no selected VM with vm_tags=heavy'):
        vm_test_queue.execution_groups(tmp_path, ['e2e', *options], workers[:1])
    if qualification:
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


def test_execute_pass_claims_fifo_once_per_family_and_resumes_clear_results(tmp_path, monkeypatch):
    import vm_test_queue
    from test_results import ResultStore, VARIABLE, REPAIR_QUEUE

    monkeypatch.setenv(VARIABLE, str(tmp_path / 'results'))
    vms = [SimpleNamespace(name=family, family=family, compute_unit=1) for family in ('a', 'b')]
    work = [dict(category='e2e', options=[], cases=[case], case=case, area=False) for case in ('first', 'last')]
    plan = ({'concurrency': 2}, vms, [], ['e2e'], [('e2e', [])], {'a': work, 'b': work})
    observed = []
    fail = [True]

    class Ready:
        def __init__(self, root, pool, limit, stopped, **kwargs):
            self.pool = pool
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def run_ready(self, execute, *, choose, needed, completed):
            results = {vm.name: dict(status=0, handoffs=[]) for vm in self.pool}
            while available := [vm for vm in self.pool if needed(vm)]:
                name = choose(tuple(vm.name for vm in available), ())
                vm = next(vm for vm in available if vm.name == name)
                value = completed(vm, execute(SimpleNamespace(vm=vm)))
                results[name] = value
                if value['status']:
                    break
            return results

    monkeypatch.setattr(vm_test_queue, 'Executor', Ready)
    def execute(worker, assignment, inherited, group):
        case = assignment['execution']['case']
        observed.append((worker.vm.family, case))
        failed = fail[0] and case == 'last'
        if failed:
            fail[0] = False
        return dict(status=int(failed), handoffs=[], evidence=dict(assignment,
            passed=[] if failed else [case], failed=[case] if failed else [], cleanup=True))
    control = lambda: SimpleNamespace(stopped=threading.Event())
    result = vm_test_queue.execute_pass(tmp_path, plan, control(), execute)
    assert result['status'] == 1 and len(result['failures']) == 1
    assert result['failures'][0]['case'] == 'last'
    before = list(observed)
    selected = [dict(work[0], options=['first'])]
    narrowed = [*plan[:-1], {'a': selected, 'b': selected}]
    with monkeypatch.context() as repair:
        repair.setenv(REPAIR_QUEUE, '1')
        assert vm_test_queue.execute_pass(tmp_path, tuple(narrowed), control(), execute)['status'] == 0
        assert vm_test_queue.execute_pass(tmp_path, plan, control(), execute)['status'] == 1
        assert ResultStore().failure()['case'] == 'last'
    assert observed == before  # Known failures and omitted cases were not rerun.
    resumed = list(plan)
    resumed[3] = ['--resume', 'e2e']
    before = list(observed)
    # A pre-discovery failure is diagnostic history, not this attempt's verdict.
    ResultStore().record('e2e', 'command', '', 1, options=[])
    assert vm_test_queue.execute_pass(tmp_path, tuple(resumed), control(), execute)['status'] == 0
    assert [record['family'] for record in ResultStore().failures()] == ['command']
    with monkeypatch.context() as repair:
        repair.setenv(REPAIR_QUEUE, '1')
        assert vm_test_queue.execute_pass(tmp_path, tuple(resumed), control(), execute)['status'] == 0
    for family in ('a', 'b'):
        assert observed.count((family, 'first')) == 1
        assert ResultStore().passed('e2e', family) == {'first', 'last'}
    assert len(observed) > len(before)
    replay = [*plan[:3], ['--resume', '--resume-case=first', '--resume-case-only', 'e2e'], *plan[4:]]
    def cleanup_failure(worker, assignment, inherited, group):
        return dict(status=2, cleanup=False, handoffs=[], evidence=dict(
            assignment, passed=['first'], failed=[], cleanup=False))
    assert vm_test_queue.execute_pass(tmp_path, tuple(replay), control(), cleanup_failure)['status'] == 1
    assert 'first' in ResultStore().passed('e2e', 'a')
    assert all(not record['case'] for record in ResultStore().failures())
    import fix_tests
    from vm_case_queue import arguments
    failure = next(record for record in ResultStore().failures() if record.get('work'))
    command = fix_tests.validation_command(failure)
    assert command[2:-2] == arguments(work[0])
    ResultStore().record('e2e', 'b', '', 2, vm='b', options=[], work=work[1])
    with monkeypatch.context() as repair:
        repair.setenv(REPAIR_QUEUE, '1')
        assert ResultStore().select_failure('e2e', 'a', ['first'], [], vms=['a'])['vm'] == 'a'
        assert ResultStore().select_failure('e2e', 'b', ['last'], [], vms=['b'])['vm'] == 'b'
        assert ResultStore().select_failure('e2e', 'b', ['renamed'], ['renamed'], vms=['b']) is None
        current = dict(work[0], options=['current'])
        selected = ResultStore().select_failure('e2e', 'a', ['first', 'last'], ['current'], vms=['a'])
        assert fix_tests.validation_command(selected)[2:-2] == arguments(current)
    ResultStore().record('e2e', 'a', '', 2, vm='a', options=[], work=work[1])
    before = len(observed)
    assert vm_test_queue.execute_pass(tmp_path, tuple(replay), control(), execute)['status'] == 0
    assert len(observed) > before  # Enclosing cleanup was actually exercised.
    failures = [record for record in ResultStore().failures() if record.get('work')]
    assert len(failures) == 2 and {record['family'] for record in failures} == {'a', 'b'}
    assert all(record['work']['case'] == 'last' for record in failures)
    assert not ResultStore().complete('e2e', 'a', [])
    retry_last = [*plan[:3], ['--resume', '--resume-case=last', '--resume-case-only', 'e2e'], *plan[4:]]
    with monkeypatch.context() as repair:
        repair.setenv(REPAIR_QUEUE, '1')
        assert vm_test_queue.execute_pass(tmp_path, tuple(retry_last), control(), execute)['status'] == 0
    assert not [record for record in ResultStore().failures() if record.get('work')]
    # Reload preserves the earlier pass and leaves the interrupted case pending
    # in the repair ledger, even though the worker exited with status 130.
    import launcher_reload
    monkeypatch.setenv(VARIABLE, str(tmp_path / 'reload-results'))
    reloading = threading.Event()
    monkeypatch.setattr(launcher_reload, 'pending', reloading.is_set)
    before = len(observed)

    def interrupt_last(worker, assignment, inherited, group):
        if assignment['execution']['case'] == 'last':
            reloading.set()
            return dict(status=130, handoffs=[], evidence=dict(assignment,
                status=130, passed=['last'], failed=[], cleanup=False, interrupted=False))
        return execute(worker, assignment, inherited, group)

    outcome = vm_test_queue.execute_pass(tmp_path, plan, control(), interrupt_last)
    assert outcome['status'] == launcher_reload.STATUS and not outcome['cleanup_complete']
    assert not ResultStore().failures()
    interrupted = [(name, result) for name, result in outcome['results'].items()
                   if result['status'] == launcher_reload.STATUS]
    for name, result in interrupted:
        evidence = result['evidence']
        assert ResultStore().passed('e2e', evidence['family']) == {'first'}
        # A resume from an older controller retries its falsely recorded
        # reload failure through normal VM admission.
        ResultStore().record('e2e', evidence['family'], '', 1, vm=name, work=evidence['execution'],
            output_tail='Interrupted\nVM reload could not confirm a successful or cleanly interrupted attempt.')
    reloading.clear()
    with monkeypatch.context() as repair:
        repair.setenv(REPAIR_QUEUE, '1')
        assert vm_test_queue.execute_pass(tmp_path, tuple(resumed), control(), execute)['status'] == 0
    assert observed[before:].count(('a', 'first')) == observed[before:].count(('b', 'first')) == 1
    assert ResultStore().passed('e2e', 'a') == ResultStore().passed('e2e', 'b') == {'first', 'last'}
    assert not ResultStore().failures()
    # Ordinary execution has no repair result ledger to poison later runs.
    monkeypatch.delenv(VARIABLE)
    import test_commands
    monkeypatch.setattr(test_commands, 'selections', lambda *args: [('static', ['shell'])])
    host_plan = ({'concurrency': 1}, [], ['static', 'shell'], [], [], {})
    assert vm_test_queue.execute_pass(tmp_path, host_plan, control(), execute,
        host=lambda: dict(status=1, handoffs=[]))['status'] == 1
    assert vm_test_queue.execute_pass(tmp_path, host_plan, control(), execute,
        host=lambda: dict(status=0, handoffs=[]))['status'] == 0
    assert not ResultStore().failures()


@pytest.mark.parametrize('changed_during', ['last-case', 'reservation'])
@pytest.mark.parametrize('focused', [False, True])
def test_source_changes_refresh_pending_inventory_without_replaying_passes(
        tmp_path, monkeypatch, changed_during, focused):
    import launcher_controller
    import remote_sources
    import vm_test_queue
    from test_results import ResultStore, VARIABLE

    monkeypatch.setenv(VARIABLE, str(tmp_path / 'results'))
    identity = {'digest': 'first'}
    vm = SimpleNamespace(name='one', family='family', compute_unit=1)
    executed, captures, plans, joined, synchronized = [], [], [], [], []
    continue_on_errors = changed_during == 'reservation' and not focused
    class Sources:
        branch = 'main'
        def __init__(self, root, *, upgrade_tags):
            self.source = dict(identity)
        def __enter__(self):
            captures.append(self.source['digest'])
            return self
        def __exit__(self, *_):
            joined.append(self.source['digest'])
    class Ready:
        def __init__(self, root, pool, limit, stopped, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def run_ready(self, execute, *, choose, needed, completed, stop_on_error=True):
            value = dict(status=0, handoffs=[])
            while needed(vm):
                if changed_during == 'reservation':
                    identity['digest'] = 'changed'
                value = completed(vm, execute(SimpleNamespace(vm=vm)))
                if value['status'] and stop_on_error:
                    break
            return {'one': value}
    def plan(root, args):
        plans.append(list(args))
        cases = ['first', 'last'] + (['added'] if identity['digest'] == 'changed' else [])
        items = [dict(category='e2e', options=[], cases=[case], case=case, area=False) for case in cases]
        return ({'concurrency': 1}, [vm], [], args, [('e2e', [])], {'family': items})
    def execute(worker, assignment, inherited, group):
        case = assignment['execution']['case']
        executed.append((case, captures[-1]))
        if case == 'last' and changed_during == 'last-case':
            identity['digest'] = 'changed'
        if case == 'first' and continue_on_errors:
            return dict(status=1, handoffs=[], evidence=dict(assignment, passed=[], failed=[case], cleanup=True))
        return dict(status=0, handoffs=[], evidence=dict(assignment, passed=[case], failed=[], cleanup=True))
    def group(root, selected, **kwargs):
        return vm_test_queue.execute_pass(root, selected, SimpleNamespace(stopped=threading.Event()),
            execute, sources=kwargs['sources'], histories=kwargs['histories'],
            continue_on_errors=kwargs['continue_on_errors'])
    def synchronize(root, branch, run, *, defer_if_live):
        assert defer_if_live
        assert joined == captures
        synchronized.append(joined[-1])
        return True
    monkeypatch.setattr(launcher_controller, 'synchronize_boundary', synchronize)
    monkeypatch.setattr(remote_sources, 'FrozenSources', Sources)
    monkeypatch.setattr(vm_test_queue, 'Executor', Ready)
    monkeypatch.setattr(vm_test_queue, '_plan', plan)
    monkeypatch.setattr(vm_test_queue, '_run_workers', group)
    monkeypatch.setattr(vm_test_queue, 'source_identity', lambda root: dict(identity))
    monkeypatch.setattr(vm_test_queue.test_source, 'startup', lambda *args, **kwargs: nullcontext())
    if focused:
        ResultStore().record('e2e', 'family', 'last', 0, options=[])
        args = ['--resume', '--resume-case=last', '--resume-case-only', 'e2e']
    else:
        args = ['e2e']
    result = vm_test_queue._run_pass(tmp_path, args, upstream_run=tmp_path / 'run',
                                     continue_on_errors=continue_on_errors)
    assert result['status'] == int(continue_on_errors)
    assert captures == synchronized == ['first', 'changed']
    assert plans == [args, ['--resume', *[argument for argument in args if argument != '--resume']]]
    assert executed == ([('last', 'first')] if focused else
                        [('first', 'first'), ('last', 'first'), ('added', 'changed')])


@pytest.mark.parametrize(('selector', 'names'), [(None, ['one', 'two', 'three']),
                                               ('two,three', ['two', 'three'])])
def test_pass_plan_uses_only_the_requested_or_configured_pool(
        tmp_path, monkeypatch, private_dispatch_source, selector, names):
    from dataclasses import replace
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
    monkeypatch.setattr(config, 'read_document', lambda path=None, **kwargs:
                        {'families': [{'family': 'a'}, {'family': 'b'}]})
    monkeypatch.setattr(config, 'parse_configuration', lambda document: (6, configured))
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

    def validate_one(root, args):
        if any(arg in test_commands.CATEGORIES for arg in args[1:]):
            raise ValueError('split category selections')
    monkeypatch.setattr(test_commands, 'validate_one', validate_one)
    configured.update({name: replace(vm, vm_tags=frozenset({'general', 'heavy'}))
                       for name, vm in configured.items()})
    monkeypatch.setattr(runpy, 'run_path', lambda path: {
        'CLASSIC_COVERAGE_IDS': (22, 30),
        'preflight': lambda *args, **kwargs: dict(cases=[dict(subcategory='general', coverage_id=3),
                                                         dict(subcategory='e2e-heavy', coverage_id=126)])})
    def collect(root, category, options, **kwargs):
        if category == 'system':
            return [f'{options[0]}-{index}' for index in range(37)]
        return ['E2E-002' if 'e2e-heavy' in options else 'E2E-001']
    monkeypatch.setattr(vm_test_queue, 'case_inventory', collect)
    monkeypatch.setattr(vm_test_queue.test_source, 'startup', lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(launcher_reload, 'current', None)
    executions, totals = [], []

    def execute(root, args, **kwargs):
        groups = kwargs['vm_groups']
        assert all(group['vms'] == names for group in groups)
        executions.append([group['args'] for group in groups])
        progress = kwargs['overall_counts']
        totals.append(progress('system', 0, 0, 148))
        if len(groups) > 1:
            totals.append(progress('e2e.general', 2, 0, 2))
            totals.append(progress('e2e.e2e-heavy', 1, 1, 2))
        totals.append(progress('system', 148, 0, 148))
        if len(groups) > 1:
            totals.append(progress('e2e.e2e-heavy', 2, 0, 2))
        return dict(status=0, cleanup_complete=True)

    monkeypatch.setattr(vm_recording, 'recording', lambda *args, **kwargs: nullcontext(None))
    monkeypatch.setattr(vm_test_queue, '_run_pass', execute)
    from test_results import ResultStore, VARIABLE
    monkeypatch.setenv(VARIABLE, str(tmp_path / 'results'))
    results = ResultStore()
    results.record('system', 'command', '', 1, options=['check_first'])
    results.record('e2e', 'command', '', 1, options=[])
    requested = ['system', 'check_first', 'system', 'check_second', 'e2e']
    assert vm_test_queue.run(tmp_path, requested) == 0
    assert not results.failures()
    assert executions == [[['system', 'check_first', 'system', 'check_second'],
                           ['e2e', '--subcategory', 'general'],
                           ['e2e', '--subcategory', 'e2e-heavy']]]
    assert totals == [(0, 0, 152), (2, 0, 152), (3, 1, 152), (151, 1, 152), (152, 0, 152)]

    totals.clear()
    executions.clear()
    assert vm_test_queue.run(tmp_path, requested[:-1], accounting=requested) == 0
    assert executions == [[requested[:-1]]]
    assert totals == [(0, 0, 152), (148, 0, 152)]



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

    # An interruption or later command failure cannot turn a finished pass into
    # a fabricated failed case, regardless of cleanup reporting.
    checkpoint_events = []
    run.checkpoint = SimpleNamespace(event=lambda *args: checkpoint_events.append(args))
    interrupted = regression.Category('Interrupted selection', 1, nodeids=item.nodeids,
                                      retry_category='unit')
    run.categories.append(interrupted)
    attempt = regression.Execution(run, interrupted, command=argv, events=True)
    for event in [dict(kind='collection', total=1, nodeids=list(item.nodeids)),
                  dict(kind='finished', nodeid=item.nodeids[0])]:
        attempt.output((regression.PREFIX + json.dumps(event) + '\n').encode())
    run.control.stop()
    attempt.finish(130)
    attempt.close()
    assert interrupted.state == 'Interrupted' and interrupted.done == 1 and interrupted.failures == 0
    assert not any(event[1]['kind'] == 'failure' for event in checkpoint_events)
    run.control = Control()
    failed = regression.Category('Failed enclosing operation', 1, nodeids=item.nodeids,
                                 retry_category='unit')
    run.categories.append(failed)
    attempt = regression.Execution(run, failed, command=argv, events=True)
    for event in [dict(kind='collection', total=1, nodeids=list(item.nodeids)),
                  dict(kind='finished', nodeid=item.nodeids[0])]:
        attempt.output((regression.PREFIX + json.dumps(event) + '\n').encode())
    attempt.finish(1)
    assert failed.state == 'Failed' and failed.done == 1
    assert not any(event[1]['kind'] == 'failure' for event in checkpoint_events)


@pytest.mark.parametrize('route', ['suite', 'standalone', 'suite-with-failure'])
def test_observation_block_stops_vm_dispatch_and_keeps_clear_results(tmp_path, monkeypatch, route):
    from test_checkpoint import Checkpoint
    from test_results import OBSERVATION_BLOCKED_STATUS

    standalone = route == 'standalone'
    independent_failure = route == 'suite-with-failure'
    options = ['check_observation_fixture'] if standalone else ['--id', '1']
    checkpoint = Checkpoint(tmp_path, [('system', options)])
    earlier, failed, pending = ('fresh::test_' + case for case in ('earlier', 'failed', 'pending'))
    passed_ids = [] if standalone else [earlier]
    invocations, reports = [], []

    def controller(self, command, *, output, **kwargs):
        invocations.append(command)
        assert len(invocations) == 1

        def emit(kind, **fields):
            message = regression.PREFIX + json.dumps(dict(kind=kind, **fields)) + '\n'
            output(message.encode())

        if not standalone:
            nodeids = [earlier, failed, pending] if independent_failure else [earlier, pending]
            emit('collection', total=len(nodeids), nodeids=nodeids)
            emit('finished', nodeid=earlier)
            if independent_failure:
                emit('failure', nodeid=failed, when='call')
                emit('finished', nodeid=failed)
            emit('vm-cleanup', passed=True)
        return OBSERVATION_BLOCKED_STATUS

    def dispatch(run):
        reports.append(run.report)
        run.phases = ('system', 'e2e')
        run.categories[0].state = 'Passed'
        run.artifacts['build-a'] = 'fixture-artifacts'
        system = regression.Category('Observation check', 1 if standalone else None)
        later = regression.Category('Later E2E check')
        run.categories.extend((system, later))
        if standalone:
            run.vm_extras = [('system', options, system)]
        run.vm_tests(None if standalone else system, later, ready=True)

    monkeypatch.setattr(regression.Run, 'run', dispatch)
    monkeypatch.setattr(regression.Run, 'wait_for_resources', lambda *args: None)
    monkeypatch.setattr(Control, 'run', controller)
    status = regression.retained_main(tmp_path, host_only=True, checkpoint=checkpoint)

    assert status == (1 if independent_failure else OBSERVATION_BLOCKED_STATUS)
    assert checkpoint.passed('system') == set(passed_ids)
    assert not checkpoint.complete('system')
    report = reports[0]
    record, = report.commands
    assert record['exit_status'] == OBSERVATION_BLOCKED_STATUS
    assert record['cleanup'] == 'complete'
    failed_ids = [failed] if independent_failure else []
    assert record['completed_ids'] == sorted(passed_ids + failed_ids)
    assert record['failed_ids'] == failed_ids
    assert (report.directory / 'failure.json').exists() is independent_failure
    if not independent_failure:
        assert record['status'] == 'diagnostic'
        assert 'Observation blocked. Owned cleanup finished.' in (report.directory / 'report.md').read_text()


@pytest.mark.parametrize('output', ['valid', 'missing-marker', 'missing-file', 'invalid-file',
                                  'stale', 'replaced', 'ancestor-symlink'])
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
    failures = {}
    parser = Progress('installed', [SimpleNamespace(case_id='case')], failures=failures)
    parser((regression.PREFIX + json.dumps(dict(kind=kind, nodeid='test.py::case',
                                              detail='private guest diagnostic')) + '\n').encode())
    if kind == 'failure':
        assert not chunks
        regression_events.write_event(sys.stdout, **failures['installed::case'])
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
            parser = Progress(execution.phase, [execution], failures={}, watch=watch)
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


@pytest.mark.parametrize('category', ['fixture-runtime', 'artifacts', 'system', 'e2e'])
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


@pytest.mark.parametrize('cancelled,fields,message', [
    (False, dict(total=0, nodeids=[]), 'test inventory changed after collection'),
    (False, dict(total=1, nodeids=['changed-case']), 'test inventory IDs changed after collection'),
    (True, dict(total=1, nodeids=['changed-case']), 'test inventory IDs changed after collection'),
    (True, dict(total=1), 'missing test inventory IDs'),
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
    failures = {}
    parser = Progress('enforcement', [SimpleNamespace(case_id='test_allowed')], failures=failures)
    prefix = regression_events.PREFIX
    parser(b'password=secret\n')
    event = prefix + json.dumps(dict(kind='failure', nodeid='test.py::test_allowed',
                                     detail='password=secret')) + '\n'
    parser(event[:12].encode())
    parser(event[12:].encode())
    parser((prefix + json.dumps(dict(kind='finished', nodeid='test.py::unregistered')) + '\n').encode())
    assert not capsys.readouterr().out
    regression_events.write_event(sys.stdout, **failures['enforcement::test_allowed'])
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
