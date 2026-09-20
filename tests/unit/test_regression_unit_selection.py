"""Selected unit execution uses host buckets without adding other coverage."""

from collections import Counter
import io
import json
import threading

import pytest

import regression
import regression_selection
from regression_resources import compatible


@pytest.fixture
def unit_run(tmp_path, monkeypatch):
    root = tmp_path / 'checkout'
    files = ('test_core.py', 'test_app_policy.py', 'test_preferences.py', 'test_config.py')
    for name in files:
        path = root / 'tests/unit' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    monkeypatch.setattr(regression, 'source_identity', lambda _: 'unchanged')
    monkeypatch.setattr(regression_selection, 'source_identity', lambda _: 'unchanged')

    class Commands(regression.Control):
        def __init__(self):
            super().__init__()
            self.calls = []
            self.nodes = [f'tests/unit/{name}::test_case[chosen variant]' for name in files]
            self.barrier = None
            self.fail = None
            self.cleaned = []

        def run(self, command, *, output, **kwargs):
            self.calls.append(command)
            assert command[1] in ('unit', 'static'), 'unit scope expanded to another suite'
            if command[1] == 'static':
                return 0
            collect = '--collect-only' in command
            nodes = self.nodes if collect else [node for node in self.nodes if node in command]
            if not collect and self.barrier:
                self.barrier.wait(timeout=5)
            if not collect and self.fail == 'inventory':
                nodes = [node.replace('test_case', 'test_changed') for node in nodes]

            def event(kind, **fields):
                output((regression.PREFIX + json.dumps(dict(kind=kind, **fields)) + '\n').encode())

            event('collection', total=len(nodes), nodeids=nodes)
            if collect:
                return 0
            failed = self.fail in ('call', 'setup', 'teardown')
            if failed:
                event('failure', nodeid=nodes[0], when=self.fail)
            if self.fail != 'completion':
                for node in nodes:
                    event('finished', nodeid=node)
            self.cleaned.extend(nodes)
            return int(failed)

    control = Commands()
    report = regression.Report(root)
    run = regression_selection.SelectedRun(root, report, control, [('unit', ['tests/unit', '-q'])])
    run.dashboard.stream = io.StringIO()
    run.admission = type('Capacity', (), dict(
        reason='test capacity', update=lambda _: None,
        allows=lambda _, kind, active: len(active) < 4 and
            all(compatible(kind, other) for other in active)))()
    yield run, control
    report.close()


@pytest.mark.parametrize('slots', [1, 2, 4])
def test_unit_uses_available_branches_without_extra_categories(unit_run, slots):
    run, control = unit_run
    control.barrier = threading.Barrier(slots)
    run.admission.allows = lambda kind, active: len(active) < slots
    run.run()
    assert len(run.categories) == 4
    assert {item.branch for item in run.categories} == set(range(1, slots + 1))
    assert all(item.state == 'Passed' and item.done == item.total for item in run.categories)
    assert Counter(node for item in run.categories for node in item.nodeids) == Counter(control.nodes)
    assert Counter(control.cleaned) == Counter(control.nodes)
    assert not run.includes_vm and not run.artifacts
    assert sum('--collect-only' in command for command in control.calls) == 1
    assert f'maximum-active={slots}' in (run.report.directory / 'report.md').read_text()


def test_unit_retains_exact_selectors_filters_and_category_order(unit_run):
    run, control = unit_run
    control.nodes = control.nodes[:2]
    args = [*control.nodes, '-q', '-k', 'chosen', '-m', 'unit',
            '--ignore=tests/unit/test_preferences.py', '--durations', '5', '--maxfail=0']
    run.selections = [('static', ['shell']), ('unit', args), ('static', ['gjs'])]
    run.categories[:] = [regression.Category('before', 1, host=True), run.categories[0],
                         regression.Category('after', 1, host=True)]
    run.run()
    assert run.categories[0].state == run.categories[-1].state == 'Passed'
    assert control.calls[0][-1] == 'shell' and control.calls[-1][-1] == 'gjs'
    workers = [command for command in control.calls
               if command[1] == 'unit' and '--collect-only' not in command]
    assert len(workers) == 2
    assert Counter(node for command in workers for node in command if '::' in node) == Counter(control.nodes)
    for command in workers:
        assert '-k=chosen' in command and '-m=unit' in command
        assert '--ignore=tests/unit/test_preferences.py' in command
        assert '--durations=5' in command and '--maxfail=0' in command
        assert 'tests/unit' not in command
        assert '--timeout' not in command


@pytest.mark.parametrize('failure', ['inventory', 'setup', 'teardown'])
def test_unit_refuses_uncertain_execution_and_joins_workers(unit_run, failure):
    run, control = unit_run
    control.fail = failure
    with pytest.raises(ValueError):
        run.run()
    assert control.stopped.is_set()
    assert not any(item.state == 'Passed' for item in run.categories)


@pytest.mark.parametrize('failure', ['call', 'completion'])
def test_failed_unit_selection_prevents_later_categories(unit_run, failure):
    run, control = unit_run
    control.fail = failure
    run.selections.append(('static', ['shell']))
    run.categories.append(regression.Category('later', 1, host=True))
    run.run()
    assert run.categories[-1].state == 'Pending'
    assert all(item.state == 'Failed' for item in run.categories[:-1])
    assert not any('static' in command for command in control.calls)


def test_unknown_unit_module_runs_exclusively_without_being_omitted(unit_run):
    run, control = unit_run
    (run.root / 'tests/unit/test_future.py').touch()
    control.nodes.append('tests/unit/test_future.py::test_case')
    run.run()
    starts = [json.loads(line) for line in (run.report.directory / 'schedule.jsonl').read_text().splitlines()
              if json.loads(line)['event'] == 'start']
    exclusive, = [event for event in starts if event['kind'] == 'unit-exclusive']
    assert exclusive['companions'] == []
    assert all('unit-exclusive' not in event['companions'] for event in starts)
    assert all(item.state == 'Passed' for item in run.categories)
    assert Counter(control.cleaned) == Counter(control.nodes)


@pytest.mark.parametrize('flag', [['-x'], ['--exitfirst'], ['--maxfail', '2']])
def test_unit_failure_limits_keep_one_invocation(unit_run, flag):
    run, control = unit_run
    calls = []

    def execute(item, command, **kwargs):
        calls.append(command)
        item.state = 'Passed'
        return 0, ''

    run.execute = execute
    run.selections = [('unit', ['tests/unit', *flag])]
    run.run()
    assert len(calls) == 1 and calls[0][-len(flag):] == flag
    assert run.categories[0].branch == 1
    assert '--collect-only' not in calls[0]
    assert not control.calls


@pytest.mark.parametrize('nodes', [[], None, ['tests/unit/test_core.py::test_a'] * 2])
def test_unit_invalid_collection_refuses_before_workers(unit_run, nodes):
    run, control = unit_run
    control.nodes = nodes or []
    with pytest.raises(ValueError):
        run.run()
    assert len(control.calls) == 1 and not control.cleaned
