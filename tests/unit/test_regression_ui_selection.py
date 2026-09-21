"""UI-only dispatch reuses the host scheduler without widening its inventory."""

from collections import Counter
import io
import json
import threading

import pytest

import regression
import regression_selection
from regression_resources import compatible
from regression_ui import selected_options
import test_activity


@pytest.fixture
def ui_run(tmp_path, monkeypatch):
    root = tmp_path / 'checkout'
    files = ('test_request_form_component.py', 'test_request_layout.py',
             'test_parent_feedback.py', 'test_preview_smoke.py')
    for name in files:
        path = root / 'tests/ui' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    python = root / '.venv/onpc-ui-tests/bin/python'
    python.parent.mkdir(parents=True)
    python.touch(mode=0o755)
    monkeypatch.setattr(regression, 'source_identity', lambda _: 'unchanged')
    monkeypatch.setattr(regression_selection, 'source_identity', lambda _: 'unchanged')

    class Commands(regression.Control):
        def __init__(self):
            super().__init__()
            self.calls = []
            self.nodes = [f'tests/ui/{name}::test_case[chosen variant]' for name in files]
            self.safety = ['tests/unit/test_ui_cleanup_safety.py::test_owned',
                           'tests/unit/test_graphical_lease.py::test_lease']
            self.gate = False
            self.barrier = None
            self.cleanup_barrier = None
            self.fail = None
            self.cleaned = []

        def run(self, command, *, output, **kwargs):
            self.calls.append(command)
            kind = 'ui' if command[0].endswith('run-ui-tests') else command[1]
            assert kind in ('ui', 'unit', 'static'), 'UI scope expanded to another suite'
            if kind == 'static':
                return 0
            collect = '--collect-only' in command
            if kind == 'ui':
                nodes = self.nodes if collect else [node for node in self.nodes if node in command]
                if not collect:
                    assert self.gate, 'UI started before all cleanup buckets joined'
                    if self.barrier:
                        self.barrier.wait(timeout=5)
                    if self.fail == 'inventory':
                        nodes = [node.replace('test_case', 'test_changed') for node in nodes]
            else:
                assert all('cleanup_safety' in node or 'test_graphical_lease.py' in node
                           for node in self.safety)
                nodes = self.safety if collect else [node for node in self.safety
                                                     if node.partition('::')[0] in command]
                if not collect and self.cleanup_barrier:
                    self.cleanup_barrier.wait(timeout=5)

            def event(kind, **fields):
                output((regression.PREFIX + json.dumps(dict(kind=kind, **fields)) + '\n').encode())

            event('collection', total=len(nodes), nodeids=nodes)
            if collect:
                return 0
            failed = ((kind == 'unit' and self.fail == 'cleanup') or
                      (kind == 'ui' and self.fail in ('call', 'setup', 'teardown')))
            if failed:
                event('failure', nodeid=nodes[0], when=self.fail if kind == 'ui' else 'call')
            for node in nodes:
                event('finished', nodeid=node)
            self.cleaned.append(kind)
            return int(failed)

    control = Commands()

    def record(digest):
        assert digest == 'unchanged'
        modules = {node.partition('::')[0] for node in control.safety}
        assert control.cleaned.count('unit') == min(4, len(modules))
        control.gate = True

    monkeypatch.setattr(test_activity, 'record_cleanup', record)
    report = regression.Report(root)
    run = regression_selection.SelectedRun(root, report, control, [('ui', ['tests/ui', '-q'])])
    run.dashboard.stream = io.StringIO()
    run.admission = type('Capacity', (), dict(
        reason='test capacity', update=lambda _: None,
        allows=lambda _, kind, active: len(active) < 4 and
            all(compatible(kind, other) for other in active)))()
    yield run, control
    report.close()


@pytest.mark.parametrize('slots', [1, 2, 4])
def test_ui_only_uses_four_existing_branches_and_respects_admission(ui_run, slots):
    run, control = ui_run
    control.barrier = threading.Barrier(slots)
    run.admission.allows = lambda kind, active: len(active) < slots
    run.run()
    items = [item for item in run.categories if item.name.startswith('UI —')]
    assert len(items) == 4
    assert {item.branch for item in items} == set(range(1, slots + 1))
    assert all(item.state == 'Passed' for item in run.categories)
    assert Counter(node for item in items for node in item.nodeids) == Counter(control.nodes)
    assert all(item.done == item.total for item in items)
    assert not run.includes_vm and not run.artifacts
    text = (run.report.directory / 'report.md').read_text()
    assert f'maximum-active={slots}' in text
    assert 'Scope: selected categories only' in text
    assert control.cleaned.count('ui') == 4


def test_cleanup_only_selection_reuses_ui_gate_in_four_branches(ui_run):
    run, control = ui_run
    control.safety = [
        'tests/unit/test_ui_cleanup_safety.py::test_owned',
        'tests/unit/test_fixture_cleanup_safety.py::test_owned',
        'tests/unit/test_terminal_cleanup_safety.py::test_owned',
        'tests/unit/test_graphical_lease.py::test_owned',
    ]
    control.cleanup_barrier = threading.Barrier(4)
    run.selections = [(regression_selection.CLEANUP_SELECTION, [])]
    run.categories[:] = [regression.Category('Cleanup safety prerequisites', host=True)]
    run.run()
    items = [item for item in run.categories if item.name.startswith('Cleanup —')]
    assert len(items) == 4
    assert {item.branch for item in items} == {1, 2, 3, 4}
    assert all(item.state == 'Passed' for item in items)
    assert control.cleaned == ['unit'] * 4
    text = (run.report.directory / 'report.md').read_text()
    assert 'Cleanup scheduling:' in text and 'maximum-active=4' in text


def test_ui_selection_preserves_filters_exact_parameters_timeout_and_category_order(ui_run):
    run, control = ui_run
    control.nodes = control.nodes[:2]
    args = ['--timeout', '240s', 'tests/ui/test_request*.py', '-q', '-k', 'chosen',
            '-m', 'not live_e2e', '--ignore=tests/ui/test_preview_smoke.py', '--durations', '5']
    run.selections = [('static', ['shell']), ('ui', args), ('static', ['gjs'])]
    run.categories[:] = [regression.Category('before', 1, host=True), run.categories[0],
                         regression.Category('after', 1, host=True)]
    run.run()
    assert run.categories[0].state == run.categories[-1].state == 'Passed'
    assert control.calls[0][-1] == 'shell' and control.calls[-1][-1] == 'gjs'
    workers = [command for command in control.calls if command[0].endswith('run-ui-tests')
               and '--collect-only' not in command]
    assert len(workers) == 2
    assert Counter(node for command in workers for node in command if '::' in node) == Counter(control.nodes)
    for command in workers:
        assert command[2:4] == ['--timeout', '240s']
        assert '-k=chosen' in command and '-m=not live_e2e' in command
        assert '--ignore=tests/ui/test_preview_smoke.py' in command
        assert '--durations=5' in command
        assert 'tests/ui' not in command and 'tests/ui/test_request*.py' not in command


@pytest.mark.parametrize('failure', ['cleanup', 'inventory', 'setup', 'teardown'])
def test_ui_refuses_failed_gate_or_uncertain_execution_and_joins_workers(ui_run, failure):
    run, control = ui_run
    control.fail = failure
    with pytest.raises(ValueError):
        run.run()
    if failure == 'cleanup':
        assert not control.gate and 'ui' not in control.cleaned
    else:
        assert control.stopped.is_set()
        assert not any(item.state == 'Passed' for item in run.categories if item.name.startswith('UI —'))


def test_ui_assertions_fail_selection_and_prevent_later_categories(ui_run):
    run, control = ui_run
    control.fail = 'call'
    run.selections.append(('static', ['shell']))
    run.categories.append(regression.Category('later', 1, host=True))
    run.run()
    assert run.categories[-1].state == 'Pending'
    assert sum(item.failures for item in run.categories) == 4
    assert not any('static' in command for command in control.calls)


def test_unreviewed_ui_module_stays_included_but_exclusive(ui_run):
    run, control = ui_run
    (run.root / 'tests/ui/test_future.py').touch()
    control.nodes.append('tests/ui/test_future.py::test_case')
    run.run()
    starts = [json.loads(line) for line in (run.report.directory / 'schedule.jsonl').read_text().splitlines()
              if json.loads(line)['event'] == 'start']
    exclusive, = [event for event in starts if event['kind'] == 'ui-exclusive']
    assert exclusive['companions'] == []
    assert all('ui-exclusive' not in event['companions'] for event in starts)
    assert all(item.state == 'Passed' for item in run.categories)
    assert control.cleaned.count('ui') == 5


@pytest.mark.parametrize('flag', [['-x'], ['--exitfirst'], ['--maxfail', '2']])
def test_ui_failure_limits_keep_one_invocation(ui_run, flag):
    run, control = ui_run
    calls = []

    def execute(item, command, **kwargs):
        calls.append(command)
        item.state = 'Passed'
        return 0, ''

    run.execute = execute
    run.selections = [('ui', ['tests/ui', *flag])]
    run.run()
    assert len(calls) == 1 and calls[0][-len(flag):] == flag
    assert run.categories[0].branch == 1
    assert '--collect-only' not in calls[0]
    assert not control.calls


@pytest.mark.parametrize('nodes', [[], None, ['tests/ui/test_a.py::test_a'] * 2])
def test_ui_invalid_collection_refuses_before_cleanup(ui_run, nodes):
    run, control = ui_run
    control.nodes = nodes or []
    with pytest.raises(ValueError):
        run.run()
    assert len(control.calls) == 1 and not control.gate


def test_ui_defaults_timeout_but_never_adds_marker_exclusions(ui_run):
    run, _ = ui_run
    args, options = selected_options(run.root, ['-m', 'live_e2e', '--maxfail=0'])
    assert args[:2] == options[:2] == ['--timeout', '1800s']
    assert '-m=live_e2e' in options and not any('not live_e2e' in arg for arg in options)
