"""Discovery, honest progress, immediate failure reporting and provenance."""

import io
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
from regression_process import Control
import test_commands
from system_progress import Progress


@pytest.fixture
def report(tmp_path):
    (tmp_path / 'docs/TestAutomation/Evidence').mkdir(parents=True)
    result = regression.Report(tmp_path)
    yield result
    result.stream.close()


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


@pytest.mark.parametrize('slots', [1, 2])
def test_live_branch_assignment_matches_actual_overlap_and_is_saved(report, tmp_path, slots):
    release = threading.Event()
    coordinator = threading.get_ident()
    class Commands(Control):
        def run(self, command, **kwargs):
            if command == ['long'] and slots == 2:
                assert release.wait(5)
            return 0
    run = regression.Run(tmp_path, report, Commands())
    run.dashboard.stream = io.StringIO()
    run.admission = SimpleNamespace(reason='at capacity',
        allows=lambda kind, active: len(active) < slots)
    items = [regression.Category(name, 1) for name in ('long', 'short1', 'short2')]
    run.categories.extend(items)
    original = regression.Execution.finish
    def finish(execution, status):
        assert threading.get_ident() == coordinator
        if execution.item is items[2]:
            release.set()
        return original(execution, status)
    from regression_schedule import Job
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(regression.Execution, 'finish', finish)
        run.host_jobs([Job(item.name, item, [item.name], estimate=10 - index)
                       for index, item in enumerate(items)])
    expected = [1, 1, 1] if slots == 1 else [1, 2, 2]
    assert [item.branch for item in items] == expected
    saved = json.loads((report.directory / 'progress.json').read_text())[1:]
    assert [item['branch'] for item in saved] == expected
    assert all(item['state'] == 'Passed' for item in saved)
    output = run.dashboard.ANSI.sub('', run.dashboard.stream.getvalue())
    assert 'Join host branches — passed' in output
    if slots == 1:
        assert 'Host branch 2 — running' not in output


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


@pytest.mark.parametrize('fail_unit,fail_publish', [(False, False), (True, False), (False, True)])
@pytest.mark.parametrize('verify_backing_bytes', [True, False])
def test_entire_plan_discovers_ready_cases_and_preserves_failure(
        report, tmp_path, monkeypatch, fail_unit, fail_publish, verify_backing_bytes):
    monkeypatch.setattr(regression, 'authorization', lambda: None)
    monkeypatch.setattr(regression, 'source_identity', lambda _: 'current-inputs')
    monkeypatch.setattr(regression, 'Admission', lambda **_: SimpleNamespace(
        reason='two categories active', allows=lambda kind, active: len(active) < 2, demands={}))
    monkeypatch.setattr(regression, 'vm_demand', lambda _: None)
    class Commands(Control):
        def __init__(self):
            super().__init__()
            self.calls = []
            self.builds = 0
        def run(self, command, *, output, **kwargs):
            self.calls.append(command)
            category = 'ui' if command[0].endswith('run-ui-tests') else command[1]
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
                event('collection', total=2)
            elif category in ('unit', 'component', 'ui', 'fixture-runtime', 'system'):
                safety = any('cleanup_safety' in item for item in command)
                if category != 'system':
                    event('collection', total=2)
                if fail_unit and category == 'unit' and not safety:
                    event('failure', nodeid='one', detail='test assertion failed')
                    event('failure', nodeid='one', detail='test teardown failed')
                event('finished', nodeid='one')
                event('finished', nodeid='two')
                return int(fail_unit and category == 'unit' and not safety)
            elif category == 'artifacts' and 'build' in command:
                self.builds += 1
                output(f'run-tests: output=/tmp/onpc-test-artifacts-fake{self.builds}\n'.encode())
            elif category == 'publish':
                return int(fail_publish)
            return 0
    control = Commands()
    run = regression.Run(tmp_path, report, control, verify_backing_bytes=verify_backing_bytes)
    run.run()
    assert [item.state for item in run.categories].count('Failed') == int(fail_unit or fail_publish)
    assert sum(item.failures for item in run.categories) == int(fail_unit or fail_publish)
    assert all(item.done == item.total for item in run.categories)
    e2e = [call for call in control.calls if 'e2e' in call and '--scenario' in call]
    assert len(e2e) == 1 and e2e[0][e2e[0].index('--scenario') + 1] == 'E2E-999/future'
    assert not any('E2E-998/wait' in call for call in control.calls)
    assert len([call for call in control.calls if 'compare' in call]) == 1
    assert len([call for call in control.calls if 'publish' in call]) == 1
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
