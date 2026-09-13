"""UI partitions preserve coverage and refuse uncertain inventories/fixtures."""

from collections import Counter
import io
import json

import pytest

from regression import Category, Execution, Report, Run
from regression_events import PREFIX
from regression_process import Control
from regression_ui import GROUPS, buckets


def test_partition_covers_all_cases_once_and_keeps_modules_together():
    nodes = [f'tests/ui/{filename}::test_case[{variant}]'
             for _, filenames, _ in GROUPS for filename in filenames for variant in ('kiosk', 'overlay')]
    nodes += ['tests/ui/future/test_new.py::test_future']
    plan = buckets(nodes)
    assert Counter(node for bucket in plan for node in bucket.nodeids) == Counter(nodes)
    assert len(plan) == 7
    assert plan[-1].kind == 'ui-exclusive'
    assert len({path for bucket in plan for path in bucket.paths}) == sum(len(b.paths) for b in plan)
    assert [b.paths for b in plan if b.name == 'UI — Nested Shell'] == [
        ('tests/ui/test_child_shell_lifecycle.py',)]


@pytest.mark.parametrize('nodes', [None, [], ['tests/ui/test_a.py::test_a'] * 2,
    ['tests/unit/test_a.py::test_a'], ['tests/ui/../test_a.py::test_a'],
    ['/tests/ui/test_a.py::test_a'], ['tests/ui/test_a.py']])
def test_invalid_partition_refuses(nodes):
    with pytest.raises(ValueError, match='UI inventory'):
        buckets(nodes)


@pytest.fixture
def execution(tmp_path):
    (tmp_path / 'docs/TestAutomation/Evidence/test-all-runs').mkdir(parents=True)
    report = Report(tmp_path)
    run = Run(tmp_path, report, Control(), host_only=True)
    run.dashboard.stream = io.StringIO()
    item = Category('UI', 1, nodeids=('tests/ui/test_a.py::test_a',))
    run.categories.append(item)
    execution = Execution(run, item, events=True)
    yield execution
    execution.close()
    report.stream.close()


def event(execution, kind, **fields):
    execution.line((PREFIX + json.dumps(dict(kind=kind, **fields))).encode())


@pytest.mark.parametrize('ids', [None, ['tests/ui/test_a.py::test_changed'],
                               ['tests/ui/test_a.py::test_a'] * 2])
def test_execution_refuses_missing_changed_or_duplicate_inventory(execution, ids):
    with pytest.raises(ValueError, match='inventory'):
        event(execution, 'collection', total=1, **({} if ids is None else {'nodeids': ids}))


def test_execution_refuses_uncollected_test_and_missing_inventory(execution):
    with pytest.raises(ValueError, match='uncollected'):
        event(execution, 'finished', nodeid='tests/ui/test_a.py::test_other')
    with pytest.raises(ValueError, match='missing UI execution inventory'):
        execution.finish(0)


@pytest.mark.parametrize('phase', ['setup', 'teardown'])
def test_ui_fixture_failure_refuses_further_work(execution, phase):
    node = execution.item.nodeids[0]
    event(execution, 'collection', total=1, nodeids=[node])
    event(execution, 'failure', nodeid=node, when=phase)
    event(execution, 'finished', nodeid=node)
    with pytest.raises(ValueError, match='further host work refused'):
        execution.finish(1)
    assert execution.item.state == 'Failed'


def test_ui_missing_completion_cannot_pass(execution):
    event(execution, 'collection', total=1, nodeids=list(execution.item.nodeids))
    execution.finish(0)
    assert execution.item.state == 'Failed'
