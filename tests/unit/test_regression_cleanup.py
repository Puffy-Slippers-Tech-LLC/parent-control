"""Cleanup scope, isolation and the mandatory join before protected work."""

from collections import Counter
import io
import json
from types import SimpleNamespace

import pytest

import regression
from regression_cleanup import REVIEWED, buckets
from regression_events import PREFIX, pytest_collection_finish as collection_finish
from regression_process import Control
from regression_resources import compatible, HOST_WORKERS


def test_partition_keeps_modules_whole_and_future_cases_exclusive():
    paths = [f'tests/unit/test_{name}_cleanup_safety.py' for name in sorted(REVIEWED)]
    paths += ['tests/unit/test_graphical_lease.py', 'tests/unit/test_future_cleanup_safety.py']
    nodes = [path + '::test_case[' + variant + ']' for path in paths for variant in ('a', 'b')]
    plan = buckets(nodes)
    assert Counter(node for bucket in plan for node in bucket.nodeids) == Counter(nodes)
    assert len(plan) == HOST_WORKERS + 1
    assert all(sum(path + '::test_case[a]' in bucket.nodeids for bucket in plan) == 1 for path in paths)
    assert all(any(path + '::test_case[a]' in bucket.nodeids and path + '::test_case[b]' in bucket.nodeids
                   for bucket in plan) for path in paths)
    assert all(bucket.kind == ('cleanup-exclusive' if 'future' in bucket.name else 'cleanup')
               for bucket in plan)
    assert buckets(list(reversed(nodes)))[0].paths == plan[0].paths
    assert all(bucket.estimate > 0 for bucket in plan)


def test_long_modules_balance_without_splitting_retention_cases_or_fixtures():
    retention = 'tests/unit/test_test_retention_cleanup_safety.py'
    retention_nodes = [retention + '::test_one_hundred_runs_have_constant_retained_size[' + outcome + ']'
                       for outcome in ('pass', 'failure', 'interrupt')]
    retention_nodes += [retention + '::test_other', retention + '::test_future']
    nodes = retention_nodes + [f'tests/unit/test_{name}_cleanup_safety.py::test_case'
                              for name in ('backing_verification', 'e2e_leased_recording',
                                           'e2e_execution', 'e2e_recording')]
    plan = buckets(nodes)
    assert len(plan) == HOST_WORKERS
    assert Counter(node for bucket in plan for node in bucket.nodeids) == Counter(nodes)
    assert sum(retention in bucket.paths for bucket in plan) == 1
    assert any(set(retention_nodes) <= set(bucket.nodeids) for bucket in plan)
    assert all('::' not in path for bucket in plan for path in bucket.paths)
    assert max(bucket.estimate for bucket in plan) < sum(bucket.estimate for bucket in plan) / 3
    assert [bucket.paths for bucket in plan] == [bucket.paths for bucket in buckets(list(reversed(nodes)))]


def test_installed_and_watcher_cleanup_share_buckets_without_a_serial_tail():
    names = ('installed_journey', 'e2e_watch', 'parent_about', 'parent_setup',
             'backing_verification', 'e2e_leased_recording', 'e2e_execution', 'e2e_recording')
    nodes = [f'tests/unit/test_{name}_cleanup_safety.py::test_case[{variant}]'
             for name in names for variant in ('a', 'b')]
    plan = buckets(nodes)
    assert len(plan) == HOST_WORKERS
    assert Counter(node for bucket in plan for node in bucket.nodeids) == Counter(nodes)
    assert all(bucket.kind == 'cleanup' for bucket in plan)
    assert all(compatible(first.kind, second.kind) for first in plan for second in plan)
    for name in names:
        path = f'tests/unit/test_{name}_cleanup_safety.py'
        assert sum(path in bucket.paths for bucket in plan) == 1


def test_private_process_and_vm_double_cleanup_modules_have_no_serial_tail():
    names = ('appsnapshot', 'baseline_guest', 'e2e_suite', 'fix_tests', 'ui_watch')
    nodes = [f'tests/unit/test_{name}_cleanup_safety.py::test_case[{variant}]'
             for name in names for variant in ('a', 'b')]
    plan = buckets(nodes)
    assert len(plan) == HOST_WORKERS
    assert Counter(node for bucket in plan for node in bucket.nodeids) == Counter(nodes)
    assert all(bucket.kind == 'cleanup' for bucket in plan)
    assert all(compatible(first.kind, second.kind) for first in plan for second in plan)
    for name in names:
        path = f'tests/unit/test_{name}_cleanup_safety.py'
        assert sum(path in bucket.paths for bucket in plan) == 1


def test_unknown_only_scope_is_included_without_parallel_admission():
    nodes = ['tests/unit/test_future_cleanup_safety.py::test_case']
    plan = buckets(nodes)
    assert len(plan) == 1 and plan[0].kind == 'cleanup-exclusive'
    assert plan[0].nodeids == tuple(nodes)


@pytest.mark.parametrize('nodes', [None, [], ['tests/unit/test_ui_cleanup_safety.py::case'] * 2,
    ['tests/unit/test_other.py::case'], ['tests/ui/test_ui_cleanup_safety.py::case'],
    ['tests/unit/../test_ui_cleanup_safety.py::case'], ['tests/unit/test_ui_cleanup_safety.py'],
    ['tests/unit/test_ui_cleanup_safety.py::'], ['/tests/unit/test_ui_cleanup_safety.py::case'],
    ['tests//unit/test_ui_cleanup_safety.py::case']])
def test_invalid_partition_refuses(nodes):
    with pytest.raises(ValueError, match='cleanup inventory'):
        buckets(nodes)


@pytest.mark.parametrize('other', ['unit', 'ui', 'component', 'publish', 'artifacts', 'system', 'e2e',
                                 'cleanup-exclusive', 'unknown'])
def test_cleanup_admits_only_reviewed_cleanup_companions(other):
    assert compatible('cleanup', 'cleanup')
    assert not compatible('cleanup', other)
    assert not compatible(other, 'cleanup')
    assert not compatible('cleanup-exclusive', other)


def test_unit_inventory_event_carries_exact_ids(monkeypatch):
    import regression_events
    events = []
    monkeypatch.setenv('ONPC_REGRESSION_EVENTS', '1')
    monkeypatch.setenv('ONPC_REGRESSION_INVENTORY', '1')
    monkeypatch.setattr(regression_events, 'emit', lambda kind, **fields: events.append((kind, fields)))
    nodes = ['tests/unit/test_fixture_cleanup_safety.py::test_case']
    session = SimpleNamespace(items=[SimpleNamespace(nodeid=node) for node in nodes],
                              config=SimpleNamespace(option=SimpleNamespace(collectonly=True)))
    collection_finish(session)
    assert events == [('collection', dict(total=1, collection_only=True, nodeids=nodes))]


@pytest.mark.parametrize('reason,visible', [
    (f'{HOST_WORKERS} host categories already running', ''),
    ('waiting for required host jobs', ''),
    ('need 5 GiB available RAM', ': need 5 GiB available RAM'),
])
def test_waiting_rows_hide_routine_reasons_and_append_case_total(reason, visible):
    item = regression.Category('Unit', 1132, wait_reason=reason)
    dashboard = regression.Dashboard([item], io.StringIO())
    assert dashboard.ANSI.sub('', dashboard.category(item, 0)) == f'[Waiting] Unit{visible} (1132)'


@pytest.mark.parametrize('state', ['Interrupted', 'Blocked'])
def test_unstarted_rows_do_not_restore_hidden_reasons_after_cancellation(state):
    item = regression.Category('Unit', 1132, state=state,
                               wait_reason=f'{HOST_WORKERS} host categories already running')
    dashboard = regression.Dashboard([item], io.StringIO())
    assert 'host categories already running' not in dashboard.category(item, 0)


def test_phase_joins_preserve_counts_times_and_vertical_spacers():
    cleanup = regression.Category('Cleanup bucket', 2, 2, 'Passed', host=True,
                                  phase='cleanup', branch=1, elapsed=20)
    host = regression.Category('Unit', 3, 1, 'Running', host=True, branch=1, started=150)
    dashboard = regression.Dashboard([cleanup, host], io.StringIO())
    dashboard.started = 100
    dashboard.cleanup_started, dashboard.cleanup_elapsed = 110, 20
    dashboard.host_started = 130
    frame = dashboard.ANSI.sub('', '\n'.join(dashboard.render(190)))
    assert '\n│\n└─ Join cleanup prerequisites — passed — 0.5m wall time' in frame
    assert '\n│\n└─ Join host branches — waiting for host work — 1.5m wall time' in frame
    assert frame.index('Join cleanup prerequisites') < frame.index('[Running] Unit')
    assert 'Overall - 60% (3/5)' in frame


@pytest.mark.parametrize('ready_after,cancel_after', [(4, None), (100, None), (4, 1)])
def test_cleanup_warmup_is_bounded_cancellable_and_precedes_dispatch(tmp_path, monkeypatch,
                                                                  ready_after, cancel_after):
    from regression_schedule import Job
    now = [0.0]
    monkeypatch.setattr(regression.time, 'monotonic', lambda: now[0])
    (tmp_path / 'docs/TestAutomation/Evidence/test-all-runs').mkdir(parents=True)
    report = regression.Report(tmp_path)
    control = Control()

    def wait(seconds):
        now[0] += seconds
        if cancel_after is not None and now[0] >= cancel_after:
            control.stop()
    monkeypatch.setattr(control.stopped, 'wait', wait)
    run = regression.Run(tmp_path, report, control, host_only=True)
    run.dashboard.stream = io.StringIO()
    run.admission = SimpleNamespace(overlap_ready=lambda: now[0] >= ready_after)
    jobs = [Job('cleanup', regression.Category(str(index), 1), ['unused']) for index in range(4)]
    run.categories.extend(job.item for job in jobs)
    def dispatch(*_, **kwargs):
        assert now[0] >= min(ready_after, cancel_after or 6)
        assert now[0] <= min(ready_after, cancel_after or 6) + .11
        assert kwargs['control'].stopped.is_set() == (cancel_after is not None)
        return 0
    monkeypatch.setattr(regression, 'run_jobs', dispatch)
    try:
        run.host_jobs(jobs, phase='cleanup')
    finally:
        report.close()


@pytest.mark.parametrize('fault', ['none', 'assertion', 'missing-completion', 'changed-id',
                                  'missing-inventory', 'teardown', 'infrastructure', 'source', 'cancel'])
@pytest.mark.parametrize('slots', [1, HOST_WORKERS])
@pytest.mark.parametrize('continue_on_errors', [False, True])
def test_real_cleanup_phase_joins_before_publishing_gate(tmp_path, monkeypatch, fault, slots, continue_on_errors):
    import test_activity
    (tmp_path / 'docs/TestAutomation/Evidence/test-all-runs').mkdir(parents=True)
    report = regression.Report(tmp_path)
    nodes = [f'tests/unit/test_{name}_cleanup_safety.py::test_case'
             for name in ('fixture', 'ui', 'terminal', 'system_runner', 'probe_channel')]
    ended, published = set(), []
    source = ['a' * 64]
    monkeypatch.setattr(regression, 'source_identity', lambda _: source[0])

    class Commands(Control):
        def run(self, command, *, output, **kwargs):
            selected = [node for node in nodes if node.partition('::')[0] in command]
            def event(kind, **fields):
                output((PREFIX + json.dumps(dict(kind=kind, **fields)) + '\n').encode())
            affected = nodes[0] in selected
            if not (affected and fault == 'missing-inventory'):
                event('collection', total=len(selected), nodeids=[
                    node + '-changed' if node == nodes[0] and fault == 'changed-id' else node for node in selected])
            if affected and fault in ('assertion', 'teardown'):
                event('failure', nodeid=nodes[0], when='teardown' if fault == 'teardown' else 'call', detail='bad')
            for node in selected:
                if not (node == nodes[0] and fault == 'missing-completion'):
                    event('finished', nodeid=node)
            if affected and fault == 'source':
                source[0] = 'b' * 64
            if affected and fault == 'cancel':
                self.stop()
            ended.update(selected)
            return (2 if fault == 'infrastructure' else 1) if affected and fault in (
                'infrastructure', 'assertion', 'teardown') else 0

    run = regression.Run(tmp_path, report, Commands(), host_only=True,
                         continue_on_errors=continue_on_errors)
    run.inputs = source[0]
    run.dashboard.stream = io.StringIO()
    run.admission = SimpleNamespace(allows=lambda kind, active: len(active) < slots, reason='capacity')
    safety = regression.Category('Cleanup safety prerequisites', len(nodes), nodeids=tuple(nodes))
    downstream = regression.Category('Unit and contracts', 1)
    run.categories.extend([safety, downstream])

    def publish(digest):
        assert ended == set(nodes)
        saved = json.loads((report.directory / 'progress.json').read_text())
        assert all(item['state'] == 'Passed' for item in saved if item['phase'] == 'cleanup')
        assert downstream.state == 'Pending' and downstream.started is None
        published.append(digest)
    monkeypatch.setattr(test_activity, 'record_cleanup', publish)
    try:
        if fault in ('none', 'cancel', 'teardown') or (
                not continue_on_errors and fault in ('assertion', 'missing-completion')):
            # Teardown can latch cancellation before completion processing.
            try:
                run.cleanup_jobs(safety)
            except ValueError:
                assert fault == 'teardown'
        else:
            with pytest.raises(ValueError):
                run.cleanup_jobs(safety)
        assert published == (['a' * 64] if fault == 'none' else [])
        assert downstream.state == 'Pending' and downstream.started is None
        assert all(item.started is None for item in run.categories)
        if fault == 'none':
            events = [json.loads(line) for line in (report.directory / 'schedule.jsonl').read_text().splitlines()]
            assert len([event for event in events if event['event'] == 'finish']) == HOST_WORKERS
            assert all(event['phase'] == 'cleanup' for event in events if event['event'] == 'start')
    finally:
        report.close()
