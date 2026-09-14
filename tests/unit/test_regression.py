"""Discovery, honest progress, immediate failure reporting and provenance."""

import io
from contextlib import nullcontext
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


@pytest.fixture
def report(tmp_path):
    (tmp_path / 'docs/TestAutomation/Evidence').mkdir(parents=True)
    result = regression.Report(tmp_path)
    yield result
    result.close()


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
    calls = []
    controller = SimpleNamespace(run=lambda command, **kwargs: calls.append(command) or 0)
    monkeypatch.setattr(regression_process.Control, 'installed', lambda *args, **kwargs: nullcontext(controller))
    monkeypatch.setattr(test_commands, 'plan', lambda *args: ([['selected']], True))
    monkeypatch.setattr(test_activity, 'cleanup_verified', lambda root: True)
    monkeypatch.setattr(regression_process, 'safety_command', lambda root: ['safety'])
    assert regression_process.category_run(tmp_path, category, ['verify']) == 0
    assert calls == ([['selected']] if category == 'fixture-runtime' else [['safety'], ['selected']])


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
                                     '--unattended --skip-backing-verification'])
def test_old_dispatcher_is_refused_before_expensive_suites(monkeypatch, installed):
    import dev_privileges
    monkeypatch.setattr(dev_privileges, 'check', lambda _: None)
    monkeypatch.setattr(regression.Path, 'read_text', lambda _: installed)
    if '--unattended' in installed and '--skip-backing-verification' in installed:
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
    assert '\033[32m[✓] Unit - 100% \033[0m(\033[32m4\033[0m/4)' in value
    assert '\033[97;1m[Running] UI - 30% \033[0m(\033[32m3\033[0m/10)' in value
    assert '\033[90m[Pending] VM - 0% \033[0m(\033[32m0\033[0m/2)' in value
    assert 'Overall - 43% \033[0m(\033[32m7\033[0m/16)' in value
    categories[0].state = 'Failed'
    categories[0].failures = 1
    regression.Dashboard(categories, stream).draw(force=True)
    assert ('\033[31m[✗] Unit - 100% \033[0m(\033[32m3\033[0m/'
            '\033[31m1\033[0m/4)') in stream.getvalue()


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
    assert '├─ Host branch 3 — idle' in first
    assert '├─ Host branch 4 — idle' in first
    assert first.count('├─ Host branch ') == 4
    styled = '\n'.join(dashboard.render(160))
    assert '\033[1m├─ Host branch 1 — running; one category at a time\033[0m' in styled
    assert '\033[90m├─ Host branch 3 — idle; one category at a time\033[0m' in styled
    assert '│  └─ [Running] UI - 30% (3/10) - 1.0m' in first
    assert '│  └─ [Running] Unit - 40% (8/20) - 40s' in first
    assert first.index('Unassigned host work') < first.index('[Pending] Components')
    assert 'memory headroom' in first
    assert first.index('Join host branches') < first.index('[Pending] VM')
    assert 'Overall - 29% (11/37) - 1.0m' in first
    ui.done, unit.done = 6, 15
    second = frame(190)
    assert '[Running] UI - 60% (6/10) - 1.5m' in second
    assert '[Running] Unit - 75% (15/20) - 1.2m' in second
    assert 'Overall - 56% (21/37) - 1.5m' in second
    assert second.count('[Pending] Components') == 1


def test_terminal_redraw_clips_long_waits_and_erases_shrinking_queue(monkeypatch):
    class Terminal(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(regression.shutil, 'get_terminal_size', lambda: os.terminal_size((80, 24)))
    item = regression.Category('UI', 10, host=True, wait_reason='memory ' * 30)
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
    (tmp_path / 'docs/TestAutomation/Evidence').mkdir(parents=True)
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


def test_generated_reports_are_ignored_by_source_provenance(tmp_path):
    root = Path(__file__).resolve().parents[2]
    # Debian source builds contain the ignore rules, but no checkout metadata.
    (tmp_path / '.gitignore').write_bytes((root / '.gitignore').read_bytes())
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    result = subprocess.run(['git', 'check-ignore',
                             'docs/TestAutomation/Evidence/test-all-runs/example/report.md'],
                            cwd=tmp_path, stdout=subprocess.PIPE, check=False)
    assert result.returncode == 0


@pytest.mark.parametrize('output,previous,key', [
    ('', [], 'build-a'),
    ('run-tests: output=/tmp/onpc-test-artifacts-a\n' * 2, [], 'build-a'),
    ('run-tests: output=/tmp/onpc-test-artifacts-a', ['/tmp/onpc-test-artifacts-a'], 'build-b'),
    ('run-tests: output=/tmp/onpc-test-artifacts-a', [], 'build-b'),
    ('run-tests: output=/tmp/foreign', [], 'build-a'),
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


@pytest.mark.parametrize('fail_unit,fail_publish', [(False, False), (True, False), (False, True)])
@pytest.mark.parametrize('verify_backing_bytes', [True, False])
@pytest.mark.parametrize('scope', ['all', 'host', 'host-builds', 'host-builds-serial'])
def test_entire_plan_discovers_ready_cases_and_preserves_failure(
        report, tmp_path, monkeypatch, fail_unit, fail_publish, verify_backing_bytes, scope):
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
            ui_ids = ['tests/ui/test_preview_smoke.py::test_one',
                      'tests/ui/test_request_form_component.py::test_two']
            if category == 'ui' and '--collect-only' not in command:
                ui_ids = [node for node in ui_ids if node.partition('::')[0] in command]
            def event(kind, **fields):
                output((regression_events.PREFIX + json.dumps(dict(kind=kind, **fields)) + '\n').encode())
            if '--list' in command:
                if category == 'system':
                    output(b'expected-executions: 2\n')
                else:
                    output(json.dumps(dict(cases=[dict(case_id='E2E-999/future', status='ready'),
                                                  dict(case_id='E2E-998/wait', status='pending')],
                                           pending_cases=['E2E-998/wait'])).encode() + b'\n')
            elif '--collect-only' in command:
                event('collection', total=2, **({'nodeids': ui_ids} if category == 'ui' else {}))
            elif category in ('unit', 'component', 'ui', 'fixture-runtime', 'system'):
                safety = any('cleanup_safety' in item for item in command)
                if category != 'system':
                    event('collection', total=len(ui_ids) if category == 'ui' else 2,
                          **({'nodeids': ui_ids} if category == 'ui' else {}))
                if fail_unit and category == 'unit' and not safety:
                    event('failure', nodeid='one', detail='test assertion failed')
                    event('failure', nodeid='one', detail='test teardown failed')
                for node in ui_ids if category == 'ui' else ('one', 'two'):
                    event('finished', nodeid=node)
                return int(fail_unit and category == 'unit' and not safety)
            elif category == 'artifacts' and 'build' in command:
                self.builds += 1
                output(f'run-tests: output=/tmp/onpc-test-artifacts-fake{self.builds}\n'.encode())
            elif category == 'publish':
                return int(fail_publish)
            return 0
    control = Commands()
    run = regression.Run(tmp_path, report, control, verify_backing_bytes=verify_backing_bytes,
                         host_only=host_only, host_builds=host_builds,
                         serial_builds=scope == 'host-builds-serial')
    run.run()
    expected_failure = int(fail_unit or (fail_publish and not host_only))
    assert [item.state for item in run.categories].count('Failed') == expected_failure
    assert sum(item.failures for item in run.categories) == expected_failure
    if not fail_publish or host_only:
        assert all(item.done == item.total for item in run.categories)
    ui = [item for item in run.categories if item.nodeids is not None]
    assert len(ui) == 2 and sum(item.done for item in ui) == 2
    if host_only:
        assert not any(call[1] in ('system', 'e2e', 'publish', 'artifacts') for call in control.calls)
        if not fail_unit:
            assert 'Join host branches — passed' in run.dashboard.ANSI.sub('', '\n'.join(
                run.dashboard.render(0)))
        assert 'Scope: host branches only' in (report.directory / 'report.md').read_text()
        return
    if fail_publish:
        assert not any('artifacts' in call or ('system' in call and '--list' not in call)
                       or '--scenario' in call for call in control.calls)
        return
    assert len([call for call in control.calls if 'compare' in call]) == 1
    assert len([call for call in control.calls if 'publish' in call]) == 1
    package = [call for call in control.calls if 'artifacts' in call]
    assert package[-1][-2:] == ['/tmp/onpc-test-artifacts-fake1', '/tmp/onpc-test-artifacts-fake2']
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
