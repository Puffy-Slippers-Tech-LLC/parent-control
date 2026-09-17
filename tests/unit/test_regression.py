"""Discovery, honest progress, immediate failure reporting and provenance."""

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


@pytest.fixture
def report(tmp_path):
    result = regression.Report(tmp_path)
    yield result
    result.close()


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
    assert {Path(path).name for path in synced} >= {'category-001.log', 'report.md', 'progress.json'}
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


@pytest.mark.parametrize('verified', [False, True])
@pytest.mark.parametrize('category', ['ui', 'component'])
def test_host_workers_reuse_only_verified_aggregate_cleanup(tmp_path, monkeypatch, verified, category):
    import test_activity
    import test_launcher
    calls = []
    controller = SimpleNamespace(run=lambda command, **kwargs: calls.append(command) or 0)
    monkeypatch.setattr(regression_process.Control, 'installed', lambda *args, **kwargs: nullcontext(controller))
    monkeypatch.setattr(test_launcher, 'pytest_command', lambda *args: ['pytest', 'selected'])
    monkeypatch.setattr(test_activity, 'cleanup_verified', lambda root: verified)
    monkeypatch.setattr(regression_process, 'safety_command', lambda root: ['safety'])
    assert regression_process.host_run(tmp_path, category, []) == 0
    assert calls == ([['pytest', 'selected']] if verified else [['safety'], ['pytest', 'selected']])


@pytest.mark.parametrize('category', ['fixture-runtime', 'publish', 'artifacts', 'system', 'e2e'])
def test_aggregate_cleanup_reuse_does_not_replace_build_or_vm_prerequisites(tmp_path, monkeypatch, category):
    import test_activity
    import test_retention
    calls = []
    plans = []
    def plan(root, selected_category, argv):
        plans.append((root, selected_category, argv))
        return [['selected']], True

    if category == 'e2e':
        # Model the artifact builder in the confined checkout without running it
        # or allocating an untracked directory outside this test's fixture.
        builder = tmp_path / 'tools/build_test_artifacts.py'
        builder.parent.mkdir()
        builder.touch()
        artifacts = tmp_path / 'artifacts'
        artifacts.mkdir()
        monkeypatch.setattr(test_retention, 'allocate', lambda *args, **kwargs: str(artifacts))
    controller = SimpleNamespace(run=lambda command, **kwargs: calls.append(command) or 0)
    monkeypatch.setattr(regression_process.Control, 'installed', lambda *args, **kwargs: nullcontext(controller))
    monkeypatch.setattr(test_commands, 'plan', plan)
    monkeypatch.setattr(test_activity, 'cleanup_verified', lambda root: True)
    monkeypatch.setattr(regression_process, 'safety_command', lambda root: ['safety'])
    assert regression_process.category_run(tmp_path, category, ['verify']) == 0
    expected = [['selected']] if category == 'fixture-runtime' else [['safety'], ['selected']]
    expected_plans = [(tmp_path, category, ['verify'])]
    if category == 'e2e':
        expected.insert(0, ['/usr/bin/python3', '-B', str(builder), '--output', str(artifacts)])
        expected_plans.append((tmp_path, category, ['verify', '--artifacts=' + str(artifacts)]))
    assert calls == expected
    assert plans == expected_plans


def test_failed_standalone_cleanup_prevents_host_worker(tmp_path, monkeypatch):
    import test_activity
    import test_launcher
    calls = []
    controller = SimpleNamespace(run=lambda command, **kwargs: calls.append(command) or 1)
    monkeypatch.setattr(regression_process.Control, 'installed', lambda *args, **kwargs: nullcontext(controller))
    monkeypatch.setattr(test_launcher, 'pytest_command', lambda *args: ['pytest', 'selected'])
    monkeypatch.setattr(test_activity, 'cleanup_verified', lambda root: False)
    monkeypatch.setattr(regression_process, 'safety_command', lambda root: ['safety'])
    assert regression_process.host_run(tmp_path, 'ui', []) == 1
    assert calls == [['safety']]


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
    (tmp_path / 'docs').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='report path contains a symlink'):
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


def test_private_guest_failure_is_fsynced_before_public_event(tmp_path, monkeypatch):
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
    durations = {'Publishing tests': 40, 'Unit and contracts': 12,
                 'UI — Request behavior': 80, 'UI — Screen fidelity': 100}

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
                          if node.partition('::')[0] in command] if category == 'ui' else ['case'])
                events = [dict(kind='collection', total=len(nodes), nodeids=nodes),
                          *(dict(kind='finished', nodeid=node) for node in nodes)]
                output(''.join(regression_events.PREFIX + json.dumps(event) + '\n'
                               for event in events).encode())
            elif category == 'artifacts' and 'build' in command:
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
                               'Unit and contracts']
    component, unit = starts['Private D-Bus components'], starts['Unit and contracts']
    assert component['branch'] == unit['branch'] == 4
    assert 0 <= component['monotonic'] - finishes['Unit and contracts']['monotonic'] <= 5
    preview = starts['UI — Preview and About']
    assert preview['branch'] == starts['publish']['branch']
    assert 0 <= preview['monotonic'] - finishes['publish']['monotonic'] <= (10 if io_burst else 5)
    assert 'ui-request' in starts['publish']['companions']
    assert starts['build-a']['companions']
    assert starts['build-b']['companions']
    assert starts['compare']['monotonic'] >= finishes['build-a']['monotonic']
    assert starts['compare']['monotonic'] >= finishes['build-b']['monotonic']
    assert set(starts) == set(finishes)
    assert all(event['state'] == 'Passed' for event in finishes.values())


@pytest.mark.parametrize('fail_unit,fail_publish,fail_safety', [
    (False, False, False), (True, False, False), (False, True, False), (False, False, True)])
@pytest.mark.parametrize('verify_backing_bytes', [True, False])
@pytest.mark.parametrize('scope', ['all', 'host', 'host-builds', 'host-builds-serial'])
def test_entire_plan_discovers_ready_cases_and_preserves_failure(
        report, tmp_path, monkeypatch, fail_unit, fail_publish, fail_safety, verify_backing_bytes, scope):
    host_only = scope == 'host'
    host_builds = scope.startswith('host-builds')
    def authorize():
        assert scope == 'all', 'host-only execution must not require privileged tooling'
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
                    output(json.dumps(dict(cases=[dict(case_id='E2E-999/future', status='ready')],
                                           excluded_pending_cases=['E2E-998/wait'])).encode() + b'\n')
            elif '--collect-only' in command:
                event('collection', total=2, **({'nodeids': ui_ids} if category == 'ui' else
                                               {'nodeids': safety_ids} if safety else {}))
            elif category in ('unit', 'component', 'ui', 'fixture-runtime', 'system'):
                nodes = ui_ids if category == 'ui' else safety_ids if safety else ('one', 'two')
                if category != 'system':
                    event('collection', total=len(nodes),
                          **({'nodeids': nodes} if category == 'ui' or safety else {}))
                failed = category == 'unit' and ((fail_unit and not safety) or (fail_safety and safety))
                if failed:
                    event('failure', nodeid='one', detail='test assertion failed')
                    event('failure', nodeid='one', detail='test teardown failed')
                for node in nodes:
                    event('finished', nodeid=node)
                return int(failed)
            elif category == 'artifacts' and 'build' in command:
                self.builds += 1
                output(f'run-tests: output=/tmp/onpc-test-artifacts-fake{self.builds}\n'.encode())
            elif category == 'publish':
                return int(fail_publish)
            return 0
    control = Commands()
    run = regression.Run(tmp_path, report, control, verify_backing_bytes=verify_backing_bytes,
                         host_only=host_only, host_builds=host_builds,
                         serial_builds=scope == 'host-builds-serial', continue_on_errors=True)
    if fail_safety:
        with pytest.raises(ValueError, match='cleanup safety prerequisites failed'):
            run.run()
        executed = [call for call in control.calls if '--collect-only' not in call and '--list' not in call]
        assert executed
        assert all(call[1] == 'unit' and any('cleanup_safety' in arg or 'test_graphical_lease.py' in arg
                                           for arg in call) for call in executed)
        return
    run.run()
    expected_failure = int(fail_unit or (fail_publish and not host_only))
    assert [item.state for item in run.categories].count('Failed') == expected_failure
    assert sum(item.failures for item in run.categories) == expected_failure
    if not fail_publish or host_only:
        assert all(item.done == item.total for item in run.categories)
    ui = [item for item in run.categories if item.name.startswith('UI — ')]
    assert len(ui) == 2 and sum(item.done for item in ui) == 2
    if host_only:
        assert not any(call[1] in ('system', 'e2e', 'publish', 'artifacts') for call in control.calls)
        if not fail_unit:
            assert 'Join host branches — passed' in run.dashboard.ANSI.sub('', '\n'.join(
                run.dashboard.render(0)))
        assert 'Scope: host branches only' in (report.directory / 'report.md').read_text()
        return
    if fail_publish:
        assert len([call for call in control.calls if 'artifacts' in call and 'build' in call]) == 2
        assert len([call for call in control.calls if 'compare' in call]) == 1
        assert not any(('system' in call and '--list' not in call)
                       or '--scenario' in call for call in control.calls)
        return
    assert len([call for call in control.calls if 'compare' in call]) == 1
    assert len([call for call in control.calls if 'publish' in call]) == 1
    package = [call for call in control.calls if 'artifacts' in call]
    assert package[-1][-2:] == [run.artifacts['build-a'], run.artifacts['build-b']]
    assert set(package[-1][-2:]) == {'/tmp/onpc-test-artifacts-fake1', '/tmp/onpc-test-artifacts-fake2'}
    if host_builds:
        assert not any(call[1] in ('system', 'e2e') for call in control.calls)
        return
    e2e = [call for call in control.calls if 'e2e' in call and '--scenario' in call]
    assert len(e2e) == 1 and e2e[0][e2e[0].index('--scenario') + 1] == 'E2E-999/future'
    assert not any('E2E-998/wait' in call for call in control.calls)
    # The full installed selection shares one setup/installation, not one
    # invocation per area or per collected functional test.
    system = [call for call in control.calls if 'system' in call and '--list' not in call]
    assert len(system) == 1 and '--area' not in system[0] and '--test' not in system[0]
    for call in control.calls:
        expected_skip = (not verify_backing_bytes and call[1] in ('system', 'e2e')
                         and '--list' not in call)
        assert ('--skip-backing-verification' in call) == expected_skip
    assert ('VM backing verification: ' + run.verification_mode) in (report.directory / 'report.md').read_text()
    if fail_unit:
        assert 'test assertion failed' in (report.directory / 'report.md').read_text()
