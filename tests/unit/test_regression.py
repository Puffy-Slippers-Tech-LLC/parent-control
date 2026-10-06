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


def test_ui_timings_checkpoint_active_operations_and_reset_phases():
    from tests.support.ui_timing import Timings
    now = [0.0]
    events = []
    timings = Timings(lambda kind, **fields: events.append(fields), lambda: now[0])
    timings.begin('case', 'setup')
    with timings.measure('reader.snapshot'):
        with timings.measure('atspi.rpc'):
            now[0] = 6
        assert events[-1]['status'] == 'progress'
        assert events[-1]['active'] == [{'operation': 'reader.snapshot', 'elapsed_seconds': 6}]
    assert 'reader.snapshot' not in events[-1]['operations']
    timings.begin('case', 'call')
    assert events[-1]['operations'] == {}
    sentinel = object()
    assert timings.wrap(lambda: sentinel, 'input.action')() is sentinel
    assert events[-1]['started'] == 6


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


def test_ui_trace_stage_time_and_operation_deltas_are_scoped():
    from tests.support.ui_timing import Timings
    events, now = [], [0.0]
    recorder = Timings(lambda kind, **fields: events.append(fields), lambda: now[0])
    with recorder.measure('atspi.rpc'):
        now[0] += 10
    with recorder.span('host.wait', predicate='test.py:1') as checkpoint:
        checkpoint('predicate', 1)
        with recorder.measure('atspi.rpc'):
            now[0] += 2
        checkpoint('pending', 1)
        checkpoint('sleep', 1)
        now[0] += .05
        checkpoint('predicate', 2)
        now[0] += 1
        checkpoint('ready', 2)
    result = events[-1]
    assert result['stages']['predicate'] == 3
    assert result['stages']['sleep'] == pytest.approx(.05)
    assert result['operations']['atspi.rpc']['count'] == 1
    assert result['operations']['atspi.rpc']['seconds'] == 2
    assert result['elapsed_seconds'] == pytest.approx(3.05)


def test_ui_timing_iterator_measures_consumption_and_forwards_owned_close():
    from tests.support.ui_timing import Timings
    now, closed = [0.0], []
    recorder = Timings(lambda *args, **kwargs: None, lambda: now[0])
    def nodes():
        try:
            now[0] += 1
            yield 42
            raise AssertionError('must not consume more nodes')
        finally:
            closed.append(True)
    iterator = recorder.wrap_iterator(nodes, 'reader.traversal')()
    assert not recorder.metrics
    assert next(iterator) == 42
    now[0] += 2
    iterator.close()
    assert closed == [True]
    assert recorder.metrics['reader.traversal']['seconds'] == 3
    assert recorder.metrics['reader.traversal']['count'] == 1
    assert recorder.stack == []


@pytest.mark.parametrize('suppress', [False, True])
def test_ui_timing_lifecycle_preserves_exit_protocol(suppress):
    from tests.support.ui_timing import Timings
    timings = Timings(lambda *args, **kwargs: None)
    error = ValueError('original')
    entered, exited = [], []

    class Manager:
        def __enter__(self):
            entered.append(True)
            return 42

        def __exit__(self, *args):
            exited.append(args)
            return suppress

    try:
        with timings.lifecycle(Manager(), 'preview') as value:
            assert value == 42
            raise error
    except ValueError as caught:
        assert not suppress and caught is error
    else:
        assert suppress
    assert entered == [True]
    assert len(exited) == 1 and exited[0][:2] == (ValueError, error)
    with timings.lifecycle(Manager(), 'preview'):
        pass
    assert exited[-1] == (None, None, None)


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


@pytest.mark.parametrize('failed', [False, True])
@pytest.mark.parametrize('phase', ['system', 'e2e'])
def test_overall_excludes_preparation_but_keeps_its_status(report, tmp_path, monkeypatch, failed, phase):
    run = regression.Run(tmp_path, report, Control(), phases=(phase,))
    monkeypatch.setattr(run, 'discover_vm', lambda *_: ['case'])
    monkeypatch.setattr(regression, 'authorization', lambda: None)
    monkeypatch.setattr(run, 'host_jobs', lambda *_: None)
    run.run_vm_only()
    discovery = run.categories[0]
    discovery.done, discovery.state = 1, 'Passed'
    preparation, suite = run.categories[1:]
    preparation.done, preparation.state = 1, 'Failed' if failed else 'Passed'
    preparation.failures = int(failed)
    suite.total, suite.done, suite.state = 24, 9, 'Running'
    lines = run.dashboard.render(run.dashboard.started)
    assert run.dashboard.ANSI.sub('', lines[-1]) == 'Overall - 37% (9/24) - 0.0m'
    assert lines[-1].startswith('\033[31m' if failed else '\033[97;1m')
    assert 'Package input preparation' in '\n'.join(lines)
    assert 'Discovery and prerequisites' in '\n'.join(lines)


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
    diagnostic = b'prepare-baseline: [connection:event-loop-failed]\n'

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
def test_unit_workers_emit_inventory_without_running_cleanup(tmp_path, monkeypatch, collect_only):
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
def test_host_workers_never_launch_cleanup_tests(tmp_path, monkeypatch, verified, category):
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
def test_dispatch_preserves_build_inputs_without_adding_cleanup_tests(tmp_path, monkeypatch, category):
    import test_activity
    import test_retention
    calls = []
    plans = []
    def plan(root, selected_category, argv):
        plans.append((root, selected_category, argv))
        return [['selected']], True

    if category == 'e2e':
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
    monkeypatch.setattr(test_activity, 'cleanup_verified', lambda root: True)
    monkeypatch.setattr(regression_process, 'safety_command', lambda root: ['safety'])
    assert regression_process.category_run(tmp_path, category, ['verify']) == 0
    expected = [['selected']]
    expected_plans = [(tmp_path, category, ['verify'])]
    if category == 'e2e':
        expected.insert(0, ['/usr/bin/python3', '-B', str(preparer), '--output', str(artifacts),
                            '--vm', vm_name()])
        expected_plans.append((tmp_path, category, ['verify', '--artifacts=' + str(artifacts)]))
    assert calls == expected
    assert plans == expected_plans


def test_host_worker_failure_propagates_without_extra_tests(tmp_path, monkeypatch):
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


def test_dashboard_colors_counts_and_no_diagnostics():
    categories = [regression.Category('Unit', 4, 4, 'Passed'),
                  regression.Category('UI', 10, 3, 'Running'),
                  regression.Category('VM', 2)]
    stream = io.StringIO()
    regression.Dashboard(categories, stream).draw(force=True)
    value = stream.getvalue()
    assert '\033[32m[✓] Unit - 100% (4/4) - 0s\033[0m' in value
    assert '\033[97;1m[Running] UI - 30% \033[0m(\033[32m3\033[0m/10)' in value
    assert '\033[90m[Pending] VM (2)\033[0m\n' in value
    assert 'Overall - 43% \033[0m(\033[32m7\033[0m/16)' in value
    categories[0].state = 'Failed'
    categories[0].failures = 1
    regression.Dashboard(categories, stream).draw(force=True)
    assert ('\033[31m[✗] Unit - 100% \033[0m(\033[32m3\033[0m/'
            '\033[31m1\033[0m/4)') in stream.getvalue()


def test_completed_dashboard_summary_is_green():
    dashboard = regression.Dashboard([regression.Category('Unit', 4, 4, 'Passed')], io.StringIO())
    dashboard.started = 100
    assert '\033[32mOverall - 100% (4/4) - 1.0m\033[0m' in dashboard.render(160)


def test_branch_frame_shows_both_running_counts_queue_and_real_wall_time():
    ui = regression.Category('UI', 10, 3, 'Running', started=100, host=True, branch=1)
    unit = regression.Category('Unit', 20, 8, 'Running', started=120, host=True, branch=2)
    queued = regression.Category('Components', 5, host=True, wait_reason='memory headroom')
    vm = regression.Category('VM', 2)
    dashboard = regression.Dashboard([ui, unit, queued, vm], io.StringIO())
    dashboard.started = dashboard.host_started = 100

    def frame(now):
        return dashboard.ANSI.sub('', '\n'.join(dashboard.render(now)))

    first = frame(160)
    assert '├─ Host branch 1 — running' in first
    assert '├─ Host branch 2 — running' in first
    assert 'Host branch 3' not in first
    assert 'Host branch 4' not in first
    assert first.count('├─ Host branch ') == 2
    styled = '\n'.join(dashboard.render(160))
    assert '\033[1m├─ Host branch 1 — running - 1.0m\033[0m' in styled
    assert 'No categories assigned' not in styled
    assert '│  └─ [Running] UI - 30% (3/10) - 1.0m' in first
    assert '│  └─ [Running] Unit - 40% (8/20) - 40s' in first
    assert first.index('Unassigned host work') < first.index('[Waiting] Components')
    assert '│    [Waiting] Components: memory headroom (5)\n' in first
    assert first.index('Join host branches') < first.index('[Pending] VM')
    assert 'Overall - 29% (11/37) - 1.0m' in first
    ui.done, unit.done = 6, 15
    second = frame(190)
    assert '[Running] UI - 60% (6/10) - 1.5m' in second
    assert '[Running] Unit - 75% (15/20) - 1.2m' in second
    assert 'Overall - 56% (21/37) - 1.5m' in second
    assert second.count('[Waiting] Components') == 1


def test_branch_totals_and_join_time_freeze_before_later_work():
    categories = [
        regression.Category('First', 1, 1, 'Passed', elapsed=60, host=True, branch=1),
        regression.Category('Second', 1, 1, 'Passed', elapsed=90, host=True, branch=1),
        regression.Category('Third', 1, 1, 'Passed', elapsed=120, host=True, branch=2),
        regression.Category('VM', 1),
    ]
    dashboard = regression.Dashboard(categories, io.StringIO())
    dashboard.started = 100
    dashboard.host_started = 160
    running = dashboard.ANSI.sub('', '\n'.join(dashboard.render(340)))
    assert '\n│\n└─ Join host branches — waiting for host work — 4.0m wall time' in running
    dashboard.host_elapsed = 180
    for now in (340, 700):
        styled = '\n'.join(dashboard.render(now))
        assert '\033[32m├─ Host branch 2 — finished - 2.0m\033[0m' in styled
        assert '\033[32m└─ Join host branches — passed — 4.0m wall time\033[0m' in styled
        frame = dashboard.ANSI.sub('', styled)
        assert 'Host branch 1 — finished - 2.5m' in frame
        assert 'Host branch 2 — finished - 2.0m' in frame
        assert 'Host branch 3' not in frame
        assert '\n│\n└─ Join host branches — passed — 4.0m wall time' in frame
        assert '\n\nOverall - 75% (3/4)' in frame
    dashboard.cleanup_started = dashboard.started
    dashboard.cleanup_elapsed = 48
    cleanup = regression.Category('Cleanup', 1, 1, 'Passed', host=True, branch=1,
                                  phase='cleanup')
    dashboard.categories = [cleanup]
    assert '\033[32mCleanup safety prerequisites\033[0m' in dashboard.render(340)
    assert ('\033[32m└─ Join cleanup prerequisites — passed — 0.8m wall time\033[0m'
            in '\n'.join(dashboard.branches([cleanup], 340, 'cleanup')))
    cleanup.state = 'Failed'
    assert '\033[32mCleanup safety prerequisites\033[0m' not in dashboard.render(340)
    failed = '\n'.join(dashboard.branches([cleanup], 340, 'cleanup'))
    assert '\033[1;31m├─ Host branch 1 — finished - 0.0m\033[0m' in failed
    assert '\033[32m└─ Join cleanup prerequisites' not in failed


def test_terminal_redraw_clips_long_names_and_erases_shrinking_queue(monkeypatch):
    class Terminal(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(regression.shutil, 'get_terminal_size', lambda: os.terminal_size((80, 24)))
    item = regression.Category('UI ' * 30, 10, host=True, wait_reason='memory headroom')
    stream = Terminal()
    dashboard = regression.Dashboard([item], stream)
    dashboard.draw(force=True)
    first = stream.getvalue()
    assert all(len(dashboard.ANSI.sub('', line)) <= 79 for line in first.splitlines())
    assert '…' in first
    previous = dashboard.lines
    stream.seek(0)
    stream.truncate()
    item.branch, item.state, item.wait_reason = 1, 'Running', ''
    dashboard.draw(force=True)
    assert stream.getvalue().startswith(f'\033[{previous}F')
    assert stream.getvalue().endswith('\033[J')
    assert dashboard.lines < previous


@pytest.mark.parametrize('height', [1, 2, 12, 24, 60])
def test_terminal_frames_stay_reachable_without_scrolling(monkeypatch, height):
    class Terminal(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(regression.shutil, 'get_terminal_size',
                        lambda: os.terminal_size((80, height)))
    items = [regression.Category(f'Completed {index}', 1, 1, 'Passed',
                                 host=True, branch=1) for index in range(30)]
    items.extend([regression.Category('Active UI', 10, 2, 'Running', host=True, branch=1),
                  regression.Category('Broken unit', 5, 3, 'Failed', host=True, branch=2),
                  regression.Category('Queued VM', 10)])
    stream = Terminal()
    dashboard = regression.Dashboard(items, stream)
    for done in (2, 5, 10):
        stream.seek(0)
        stream.truncate()
        items[-3].done = done
        dashboard.draw(force=True)
        output = stream.getvalue()
        plain = dashboard.ANSI.sub('', output)
        assert output.count('\n') <= height - 1
        assert dashboard.lines <= max(1, height - 1)
        assert plain.count('Overall - ') == 1
        if height >= 12:
            assert f'[Running] Active UI - {done * 10}%' in plain
            assert '[✗] Broken unit' in plain
            assert plain.count('Host branch 1') == 1
        if 2 < height < 60:
            assert 'rows hidden; full details in run report' in plain
        if height == 60:
            assert 'rows hidden' not in plain
            assert 'Completed 0' in plain


def test_terminal_height_keeps_fix_tests_category_beneath_overall():
    lines = [f'[Pending] Category {index}' for index in range(20)]
    lines.extend(['Overall - 50% (10/20) - 1.0m',
                  'Running category [unit] (1/13)'])
    visible = regression.Dashboard.fit_height(lines, 5)
    assert visible[-2:] == lines[-2:]


def test_terminal_dimensions_ignore_stale_environment(monkeypatch):
    class Terminal(io.StringIO):
        def isatty(self):
            return True

        def fileno(self):
            return 42

    monkeypatch.setenv('LINES', '60')
    monkeypatch.setenv('COLUMNS', '160')
    size = os.terminal_size((80, 12))

    def terminal_size(descriptor):
        assert descriptor == 42
        return size

    monkeypatch.setattr(regression.os, 'get_terminal_size', terminal_size)
    stream = Terminal()
    dashboard = regression.Dashboard(
        [regression.Category(f'Category {index}', 1) for index in range(30)], stream)
    for size in (size, os.terminal_size((40, 8)), os.terminal_size((100, 24))):
        previous = dashboard.terminal_size
        stream.seek(0)
        stream.truncate()
        dashboard.draw(force=True)
        output = stream.getvalue()
        assert dashboard.terminal_size == size
        assert output.count('\n') < size.lines
        assert all(len(dashboard.ANSI.sub('', line)) < size.columns
                   for line in output.splitlines())
        if previous is not None:
            assert output.startswith('\033[H\033[2J')


def test_terminal_resize_discards_invalid_cursor_offset(monkeypatch):
    class Terminal(io.StringIO):
        def isatty(self):
            return True

    size = os.terminal_size((120, 60))
    monkeypatch.setattr(regression.shutil, 'get_terminal_size', lambda: size)
    stream = Terminal()
    dashboard = regression.Dashboard(
        [regression.Category(f'Category {index}', 1) for index in range(30)], stream)
    for size in (size, os.terminal_size((40, 12)), os.terminal_size((120, 60))):
        previous = dashboard.terminal_size
        stream.seek(0)
        stream.truncate()
        dashboard.draw(force=True)
        output = stream.getvalue()
        if previous is not None:
            assert output.startswith('\033[H\033[2J')
        assert output.count('\n') < size.lines
        assert all(len(dashboard.ANSI.sub('', line)) < size.columns
                   for line in output.splitlines())


def test_nonterminal_output_keeps_all_categories(monkeypatch):
    monkeypatch.setattr(regression.shutil, 'get_terminal_size',
                        lambda: os.terminal_size((20, 5)))
    stream = io.StringIO()
    regression.Dashboard([regression.Category(f'Category {index}', 1)
                          for index in range(30)], stream).draw(force=True)
    assert stream.getvalue().count('[Pending] Category ') == 30
    assert 'rows hidden' not in stream.getvalue()


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
    output = run.dashboard.ANSI.sub('', run.dashboard.stream.getvalue())
    assert 'Join host branches — passed' in output
    if slots == 1:
        assert 'Host branch 2 — running' not in output
    if slots == 3:
        assert 'Host branch 3 — running' in output
    if slots == 4:
        assert 'Host branch 4 — running' in output


@pytest.mark.parametrize('continue_on_errors', [False, True])
@pytest.mark.parametrize('events', [False, True])
def test_first_failure_cancels_and_finalizes_with_prompt(
        tmp_path, monkeypatch, capsys, continue_on_errors, events):
    runs = []

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
    assert regression.main(tmp_path, continue_on_errors=continue_on_errors) == (1 if continue_on_errors else 130)
    run = runs[0]
    assert run.categories[0].state == 'Failed'
    assert run.report.stream.closed
    assert 'normal owned cleanup finished' in (run.report.directory / 'report.md').read_text()
    assert 'Copy this prompt into a new Codex session:' in capsys.readouterr().out
    failure = json.loads((run.report.directory / 'failure.json').read_text())
    assert failure['failures'] == [dict(category=run.categories[0].retry_category,
                                      case='case' if events else '', vm='')]


def test_failure_targets_keep_cases_stable_across_buckets_and_scope_vms():
    items = [regression.Category('Unit branch 2', failures=2, retry_category='unit',
                                 failed_nodeids=('test_a[variant]', 'test_b')),
             regression.Category('Unit branch 4', failures=1, retry_category='unit',
                                 failed_nodeids=('test_a[variant]',)),
             regression.Category('E2E', failures=1, retry_category='e2e',
                                 failed_nodeids=('E2E-004/terminal',)),
             regression.Category('System preparation', state='Failed', retry_category='system'),
             regression.Category('Interrupted companion', state='Interrupted', retry_category='ui')]
    assert regression.failure_targets(items, vm='guest-a') == [
        dict(category='unit', case='test_a[variant]', vm=''),
        dict(category='unit', case='test_b', vm=''),
        dict(category='e2e', case='E2E-004/terminal', vm='guest-a'),
        dict(category='system', case='', vm='guest-a')]


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


@pytest.mark.parametrize('outcome', ['passed', 'failed', 'error', 'interrupted', 'interrupted-failure'])
def test_final_investigation_prompt_links_closed_report(tmp_path, monkeypatch, capsys, outcome):
    runs = []

    def execute(run):
        runs.append(run)
        item = run.categories[0]
        item.done = 1
        item.failures = int(outcome in ('failed', 'interrupted-failure'))
        item.state = 'Failed' if item.failures else 'Passed'
        run.report.write('\nDetailed failure evidence stays in this report.\n')
        if outcome.startswith('interrupted'):
            run.control.stopped.set()
        if outcome == 'error':
            raise ValueError('discovery failure detail')

    monkeypatch.setattr(regression.Run, 'run', execute)
    status = regression.main(tmp_path)
    output = capsys.readouterr().out
    run = runs[0]
    assert run.report.stream.closed
    assert status == (130 if outcome.startswith('interrupted') else
                      0 if outcome == 'passed' else 1)
    marker = 'Copy this prompt into a new Codex session:'
    if outcome in ('passed', 'interrupted'):
        assert marker not in output
    else:
        prompt = output.split(marker)[1]
        assert str(tmp_path) in prompt
        assert str(run.report.directory / 'report.md') in prompt
        assert 'progress.json' in prompt
        assert 'rerun the relevant checks' in prompt
        assert 'tools/prepare-baseline --vm NAME --mode auto --y' in prompt
        assert 'tools/prepare-appsnapshot --vm NAME --y' in prompt
        assert 'omit it for manual work' in prompt
        assert 'Detailed failure evidence' not in prompt
        assert output.index(marker) > output.rindex('Overall - ')
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


def test_vm_memory_wait_stays_visible_after_host_join_and_in_short_terminal():
    hosts = [regression.Category(f'Host {i}', 1, 1, 'Passed', host=True, branch=i % 4 + 1)
             for i in range(20)]
    vm = regression.Category('Installed-system tests', 244, wait_reason=
                             'waiting for memory headroom (14.0 GiB available; requires 15.2 GiB)')
    dashboard = regression.Dashboard([*hosts, vm])
    dashboard.host_elapsed = 400
    rows = dashboard.fit_height(dashboard.render(800), 8)
    text = dashboard.ANSI.sub('', '\n'.join(rows))
    assert '[Waiting] Installed-system tests: waiting for memory headroom' in text
    assert '14.0 GiB available; requires 15.2 GiB' in text
    assert 'Join host branches — passed' in text


@pytest.mark.parametrize('failure', [None, 'build-a', 'build-b', 'publish'])
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
            elif key in ('publish', 'host'):
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
    publishing = regression.Category('Publishing', 1)
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
    for job in jobs[:3]:
        assert job.requires == ()
        job.command = [job.key]
    host_item = regression.Category('Host', 1)
    jobs.append(regression_schedule.Job('ui-layout', host_item, ['host'], estimate=100))
    run.categories = [publishing, *builds, host_item]
    run.host_jobs(jobs)
    assert completed.index('build-b') < completed.index('build-a')
    assert completed.index('build-a') < completed.index('publish')
    assert host_item.state == 'Passed'
    assert builds[2].state == ('Blocked' if failure in ('build-a', 'build-b') else 'Passed')
    assert set(run.artifacts) == {'build-a', 'build-b'} - {failure}


@pytest.mark.parametrize('io_burst', [False, True])
def test_real_host_plan_refills_branches_promptly(report, tmp_path, monkeypatch, io_burst):
    # Representative discovery sizes from the reported run. Run.run builds the
    # actual jobs, estimates and dependencies; do not duplicate its job ordering.
    inventory = {name: [f'tests/ui/{name}::test_{index}' for index in range(count)]
                 for name, count in [('test_request_form_component.py', 58),
                                     ('test_screen_preview.py', 20),
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
    durations = {'Publishing tests': 40, 'Unit — Bucket 1': 12,
                 'UI — Request behavior': 80, 'UI — Screen fidelity': 100}
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
    assert list(starts)[:4] == ['UI — Request behavior', 'publish', 'UI — Screen fidelity',
                               'Unit — Bucket 1']
    component, unit = starts['Private D-Bus components'], starts['Unit — Bucket 1']
    assert component['branch'] == unit['branch'] == 4
    assert 0 <= component['monotonic'] - finishes['Unit — Bucket 1']['monotonic'] <= 5
    preview = starts['UI — Preview smoke']
    assert preview['branch'] == starts['publish']['branch']
    assert 0 <= preview['monotonic'] - finishes['publish']['monotonic'] <= (10 if io_burst else 5)
    assert 'ui-request' in starts['publish']['companions']
    assert starts['build-a']['companions']
    assert starts['build-b']['companions']
    assert starts['compare']['monotonic'] >= finishes['build-a']['monotonic']
    assert starts['compare']['monotonic'] >= finishes['build-b']['monotonic']
    assert set(starts) == set(finishes)
    assert all(event['state'] == 'Passed' for event in finishes.values())


@pytest.mark.parametrize('with_system', [False, True])
def test_empty_e2e_inventory_refuses_with_reason_without_unused_build(
        report, tmp_path, monkeypatch, with_system):
    run = regression.Run(tmp_path, report, Control(),
                         phases=('system', 'e2e') if with_system else ('e2e',))
    run.dashboard.stream = io.StringIO()
    monkeypatch.setattr(run, 'wait_for_resources', lambda *_: None)
    calls = []

    def execute(command, *, output, **kwargs):
        calls.append(command[1:])
        if command[1:] == ['e2e', '--unattended', '--list', '--ready', '--vm', vm_name()]:
            output(json.dumps(dict(cases=[], excluded_pending_cases=['E2E-999/pending'])).encode())
        elif command[1:] == ['system', '--unattended', '--list', '--vm', vm_name()]:
            output(b'expected-executions: 1\n')
        elif command[1] == 'system':
            for event in (dict(kind='collection', total=1, nodeids=['system-case']),
                          dict(kind='finished', nodeid='system-case')):
                output((regression.PREFIX + json.dumps(event) + '\n').encode())
        else:
            pytest.fail('empty E2E inventory must not dispatch or build')
        return 0

    monkeypatch.setattr(run.control, 'run', execute)
    monkeypatch.setattr(regression, 'authorization',
                        lambda: pytest.fail('empty E2E-only run must not authorize VM work'))
    if with_system:
        system = regression.Category(regression.CATEGORY_NAMES['system'])
        graphical = regression.Category(regression.CATEGORY_NAMES['e2e'])
        run.categories.extend([system, graphical])
        run.artifacts['build-a'] = '/tmp/onpc-test-artifacts-fixture'
        ready = run.discover_vm(system, graphical)
        run.vm_tests(system, graphical, ready)
        assert system.state == 'Passed'
        assert len(calls) == 3
    else:
        run.run_vm_only()
        assert calls == [['e2e', '--unattended', '--list', '--ready', '--vm', vm_name()]]
        assert len(run.categories) == 2
        assert run.categories[0].state == 'Passed'
        graphical = run.categories[-1]
    assert graphical.state == 'Failed'
    assert graphical.total == graphical.done == graphical.failures == 0
    assert graphical.wait_reason == 'no ready E2E variants'
    text = (report.directory / 'report.md').read_text()
    assert 'Pending variants excluded: 1' in text
    assert 'no customer scenarios executed' in text
    assert 'pending_reason' in text


@pytest.mark.parametrize('category', ['system', 'e2e'])
@pytest.mark.parametrize('failure', [None, 'case', 'suite-cleanup', 'incomplete', 'interrupted'])
@pytest.mark.parametrize('continue_on_errors', [False, True])
def test_vm_aggregate_uses_one_suite_and_retains_progress_and_final_failure(
        report, tmp_path, monkeypatch, category, failure, continue_on_errors):
    run = regression.Run(tmp_path, report, Control(), phases=(category,),
                         continue_on_errors=continue_on_errors)
    run.dashboard.stream = io.StringIO()
    run.artifacts['build-a'] = '/tmp/onpc-test-artifacts-fixture'
    monkeypatch.setattr(run, 'wait_for_resources', lambda *args: None)
    cases = [f'E2E-999/case-{index}' for index in range(6)]
    item = regression.Category(regression.CATEGORY_NAMES[category])
    system, graphical = (item, None) if category == 'system' else (None, item)
    run.categories.append(item)
    calls = []

    def execute(command, *, output, **kwargs):
        calls.append(command)
        assert command[1] == category
        assert ('--ready' in command) == (category == 'e2e')
        assert not any(option in command for option in ('--scenario', '--area', '--test'))
        if '--list' in command:
            if category == 'system':
                output(f'expected-executions: {len(cases)}\n'.encode())
            else:
                output(json.dumps(dict(cases=[dict(case_id=case) for case in cases],
                                       excluded_pending_cases=[])).encode() + b'\n')
            return 0

        def event(kind, **fields):
            output((regression_events.PREFIX + json.dumps(dict(kind=kind, **fields)) + '\n').encode())

        event('collection', total=len(cases), nodeids=cases)
        for index, case in enumerate(cases):
            if failure == 'case' and index == 3:
                event('failure', nodeid=case, when='call', detail='case failed')
            event('finished', nodeid=case)
            assert item.done == index + 1
            if failure == 'interrupted' and index == 3:
                run.control.interrupt()
                break
            if failure in ('case', 'incomplete') and index == 3:
                break
        # The controller still owns suite restoration/audit after reporting a
        # failed case. No automatic STOP may reach it before that work exits.
        assert run.control.stopped.is_set() == (failure == 'interrupted')
        output(b'suite cleanup and final audit complete\n')
        return 130 if failure == 'interrupted' else int(failure in ('case', 'suite-cleanup'))

    monkeypatch.setattr(run.control, 'run', execute)
    ready = run.discover_vm(system, graphical)
    if graphical is not None:
        assert ready == cases and graphical.nodeids == tuple(cases)
    # System failure refuses any subsequent E2E suite even in continue mode.
    refused = category == 'system' and continue_on_errors and failure in ('case', 'suite-cleanup')
    with pytest.raises(ValueError, match='subsequent VM attempts refused') if refused else nullcontext():
        run.vm_tests(system, graphical, ready)
    assert len(calls) == 2  # One read-only inventory and one complete suite.
    assert item.done == (4 if failure in ('case', 'incomplete', 'interrupted') else 6)
    assert item.state == ('Passed' if failure is None else
                          'Interrupted' if failure == 'interrupted' else 'Failed')
    assert item.failures == int(failure == 'case')
    assert run.control.stopped.is_set() == (failure == 'interrupted' or
                                          (failure is not None and not continue_on_errors))


@pytest.mark.parametrize('fail_unit,fail_publish', [
    (False, False), (True, False), (False, True)])
@pytest.mark.parametrize('scope', ['all', 'all-future-category', 'host', 'host-builds', 'host-builds-serial',
                                  'host system', 'host e2e', 'system', 'e2e', 'system e2e'])
def test_entire_plan_discovers_ready_cases_and_preserves_failure(
        report, tmp_path, monkeypatch, fail_unit, fail_publish, scope):
    host_builds = scope.startswith('host-builds')
    phases = (('host', 'system', 'e2e') if scope in ('all', 'all-future-category') else
              ('host',) if host_builds else tuple(scope.split()))
    if scope == 'all-future-category':
        import test_commands
        monkeypatch.setitem(test_commands.CATEGORIES, 'ui-future-suite',
                            test_commands.CategorySpec('New implemented suite'))
    includes_host = 'host' in phases
    includes_vm = any(kind in phases for kind in ('system', 'e2e'))
    def authorize():
        assert includes_vm, 'host-only execution must not require privileged tooling'
    monkeypatch.setattr(regression, 'authorization', authorize)
    monkeypatch.setattr(regression, 'source_identity', lambda _: 'current-inputs')
    monkeypatch.setattr(regression, 'Admission', lambda **_: SimpleNamespace(
        reason='two categories active', allows=lambda kind, active: len(active) < 2,
        update=lambda: None, demands={}))
    monkeypatch.setattr(regression, 'vm_demand', lambda _: None)
    class Commands(Control):
        def __init__(self):
            super().__init__()
            self.calls = []
            self.builds = 0
        def run(self, command, *, output, **kwargs):
            self.calls.append(command)
            category = 'ui' if command[0].endswith('run-ui-tests') else command[1]
            if category == 'ui':
                assert command[command.index('-m') + 1] == 'not live_e2e'
            ui_ids = ['tests/ui/test_preview_smoke.py::test_one',
                      'tests/ui/test_request_form_component.py::test_two']
            unit_ids = ['tests/unit/test_core.py::test_one',
                        'tests/unit/test_core.py::test_two']
            safety_ids = ['tests/unit/test_fixture_cleanup_safety.py::test_one',
                          'tests/unit/test_graphical_lease.py::test_two']
            safety = category == 'unit' and any('cleanup_safety' in arg or 'test_graphical_lease.py' in arg
                                                for arg in command)
            if safety and '--collect-only' not in command:
                safety_ids = [node for node in safety_ids if node.partition('::')[0] in command]
            if category == 'ui' and '--collect-only' not in command:
                ui_ids = [node for node in ui_ids if node.partition('::')[0] in command]
            def event(kind, **fields):
                output((regression_events.PREFIX + json.dumps(dict(kind=kind, **fields)) + '\n').encode())
            if '--list' in command:
                if category == 'system':
                    output(b'expected-executions: 2\n')
                else:
                    assert '--ready' in command
                    output(json.dumps(dict(cases=[dict(case_id=case, status='ready') for case in
                                                 ('E2E-999/first', 'E2E-999/second')],
                                           excluded_pending_cases=['E2E-998/wait'])).encode() + b'\n')
            elif '--collect-only' in command:
                event('collection', total=2, **({'nodeids': ui_ids} if category == 'ui' else
                                               {'nodeids': safety_ids} if safety else
                                               {'nodeids': unit_ids} if category == 'unit' else {}))
            elif category in ('unit', 'component', 'ui', 'fixture-runtime', 'system'):
                nodes = (ui_ids if category == 'ui' else safety_ids if safety else
                         unit_ids if category == 'unit' else ('one', 'two'))
                if category != 'system':
                    event('collection', total=len(nodes),
                          **({'nodeids': nodes} if category in ('unit', 'ui') else {}))
                failed = category == 'unit' and fail_unit
                if failed:
                    event('failure', nodeid=nodes[0], detail='test assertion failed')
                    event('failure', nodeid=nodes[0], detail='test teardown failed')
                for node in nodes:
                    event('finished', nodeid=node)
                return int(failed)
            elif category == 'artifacts' and ('build' in command or 'prepare' in command):
                self.builds += 1
                output(f'run-tests: output=/tmp/onpc-test-artifacts-fake{self.builds}\n'.encode())
            elif category == 'publish':
                return int(fail_publish)
            elif category == 'e2e':
                assert '--ready' in command and '--scenario' not in command
                nodes = ['E2E-999/first', 'E2E-999/second']
                event('collection', total=len(nodes), nodeids=nodes)
                for node in nodes:
                    event('finished', nodeid=node)
            return 0
    control = Commands()
    run = regression.Run(tmp_path, report, control,
                         phases=phases,
                         serial_builds=scope == 'host-builds-serial', continue_on_errors=True)
    run.run()
    assert not any(item.phase == 'cleanup' for item in run.categories)
    assert not any('test_*cleanup_safety.py' in call for call in control.calls)
    if includes_host:
        assert all(item.retry_category == 'ui' for item in run.categories
                   if item.name.startswith('UI — '))
        assert all(item.retry_category == 'unit' for item in run.categories
                   if item.name.startswith(('Unit — ', 'Cleanup — ')))
    if scope == 'all-future-category':
        future, = [item for item in run.categories if item.name == 'New implemented suite']
        assert future.retry_category == 'ui-future-suite'
    if scope in ('all', 'all-future-category') and not (fail_unit or fail_publish):
        from test_commands import suite_inventory
        executed_kinds = {'ui' if call[0].endswith('run-ui-tests') else call[1]
                          for call in control.calls
                          if '--list' not in call and '--collect-only' not in call}
        assert executed_kinds == set(suite_inventory())
    if not includes_host:
        executed = [call for call in control.calls if '--list' not in call]
        assert [call[1] for call in executed] == ['artifacts', *phases]
        assert 'prepare' in executed[0]
        assert '--for-vm' in executed[0]
        assert all(item.state == 'Passed' for item in run.categories)
        assert control.builds == 1
        assert all(run.artifacts['build-a'] in call for call in executed[1:])
        return
    expected_failure = int(fail_unit or fail_publish)
    assert [item.state for item in run.categories].count('Failed') == expected_failure
    assert sum(item.failures for item in run.categories) == expected_failure
    if not fail_publish:
        assert all(item.done == item.total for item in run.categories)
    ui = [item for item in run.categories if item.name.startswith('UI — ')]
    assert len(ui) == 2 and sum(item.done for item in ui) == 2
    if not includes_vm:
        assert not any(call[1] in ('system', 'e2e') for call in control.calls)
        if not fail_unit and not fail_publish:
            assert 'Join host branches — passed' in run.dashboard.ANSI.sub('', '\n'.join(
                run.dashboard.render(0)))
        assert 'Scope: host' in (report.directory / 'report.md').read_text()
    if fail_publish:
        assert len([call for call in control.calls if 'artifacts' in call and 'build' in call]) == 2
        assert len([call for call in control.calls if 'compare' in call]) == 1
        assert not any(call[1] in ('system', 'e2e') and '--list' not in call
                       for call in control.calls)
        return
    assert len([call for call in control.calls if 'compare' in call]) == 1
    assert len([call for call in control.calls if 'publish' in call]) == 1
    package = [call for call in control.calls if 'artifacts' in call and '--for-vm' not in call]
    assert package[-1][-2:] == [run.artifacts['build-a'], run.artifacts['build-b']]
    assert set(package[-1][-2:]) == {'/tmp/onpc-test-artifacts-fake1', '/tmp/onpc-test-artifacts-fake2'}
    if not includes_vm:
        assert not any(call[1] in ('system', 'e2e') for call in control.calls)
        return
    preparation = [call for call in control.calls if '--for-vm' in call]
    assert len(preparation) == 1
    assert preparation[0][-2:] == ['--candidate', run.artifacts['build-a']]
    assert all(run.artifacts['build-vm'] in call for call in control.calls
               if call[1] in ('system', 'e2e') and '--list' not in call)
    e2e = [call for call in control.calls if 'e2e' in call and '--list' not in call]
    assert len(e2e) == int('e2e' in phases)
    if e2e:
        assert '--ready' in e2e[0] and '--scenario' not in e2e[0]
    assert not any('E2E-998/wait' in call for call in control.calls)
    # The full installed selection shares one setup/installation, not one
    # invocation per area or per collected functional test.
    system = [call for call in control.calls if 'system' in call and '--list' not in call]
    assert len(system) == int('system' in phases)
    if system:
        assert '--area' not in system[0] and '--test' not in system[0]
    executed = [call[1] for call in control.calls if '--list' not in call]
    first_vm = next(index for index, kind in enumerate(executed) if kind in ('system', 'e2e'))
    assert executed[first_vm:] == [kind for kind in phases if kind != 'host']
    for call in control.calls:
        assert '--skip-backing-verification' not in call

    assert ('VM backing verification: ' + run.verification_mode) in (report.directory / 'report.md').read_text()
    if fail_unit:
        assert 'test assertion failed' in (report.directory / 'report.md').read_text()
