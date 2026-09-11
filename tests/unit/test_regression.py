"""Discovery, honest progress, immediate failure reporting and provenance."""

import io
import json
import os
from pathlib import Path
import subprocess
import sys
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


def test_dashboard_colors_counts_and_no_diagnostics():
    categories = [regression.Category('Unit', 4, 4, 'Passed'),
                  regression.Category('UI', 10, 3, 'Running'),
                  regression.Category('VM', 2)]
    stream = io.StringIO()
    regression.Dashboard(categories, stream).draw(force=True)
    value = stream.getvalue()
    assert '\033[32m[✓] Unit - 100% (4 / 4)' in value
    assert '\033[97;1m[Running] UI - 30% (3 / 10)' in value
    assert '\033[90m[Pending] VM - 0% (0 / 2)' in value
    assert 'Overall - 43% (7 / 16)' in value
    categories[0].state = 'Failed'
    regression.Dashboard(categories, stream).draw(force=True)
    assert '\033[31m[✗] Unit' in stream.getvalue()


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


@pytest.mark.parametrize('fail_unit', [False, True])
def test_entire_plan_discovers_ready_cases_and_preserves_failure(report, tmp_path, monkeypatch, fail_unit):
    monkeypatch.setattr(regression, 'authorization', lambda: None)
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
                event('finished', nodeid='one')
                event('finished', nodeid='two')
                return int(fail_unit and category == 'unit' and not safety)
            elif category == 'artifacts' and 'build' in command:
                self.builds += 1
                output(f'run-tests: output=/tmp/onpc-test-artifacts-fake{self.builds}\n'.encode())
            return 0
    control = Commands()
    run = regression.Run(tmp_path, report, control)
    run.run()
    assert [item.state for item in run.categories].count('Failed') == int(fail_unit)
    assert all(item.done == item.total for item in run.categories)
    e2e = [call for call in control.calls if 'e2e' in call and '--scenario' in call]
    assert len(e2e) == 1 and e2e[0][-1] == 'E2E-999/future'
    assert not any('E2E-998/wait' in call for call in control.calls)
    assert len([call for call in control.calls if 'compare' in call]) == 1
    if fail_unit:
        assert 'test assertion failed' in (report.directory / 'report.md').read_text()
