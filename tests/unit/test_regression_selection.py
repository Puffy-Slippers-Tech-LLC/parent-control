"""Every public test selection shares the aggregate's summary and evidence."""

import json
from unittest.mock import Mock

import pytest

import regression
import regression_process
import regression_selection
import test_commands
import test_activity
import test_recovery
from tests.support.paths import ROOT


@pytest.fixture
def source_identity(monkeypatch):
    # The report tests use a private directory, not a Git checkout.
    monkeypatch.setattr(regression, 'source_identity', lambda _: 'fixed-test-inputs')
    monkeypatch.setattr(regression_selection, 'source_identity', lambda _: 'fixed-test-inputs')


@pytest.mark.parametrize('category', [kind for kind in test_commands.CATEGORIES
                                     if kind not in test_commands.AGGREGATES])
def test_detached_categories_use_the_shared_report(monkeypatch, category):
    monkeypatch.setattr(test_commands, 'validate_one', lambda *_: None)
    run = Mock(return_value=7)
    monkeypatch.setattr(regression, 'main', run)
    monkeypatch.setattr(regression_process, 'category_run',
                        Mock(side_effect=AssertionError('raw output route')))
    monkeypatch.setattr(regression_process, 'host_run',
                        Mock(side_effect=AssertionError('raw output route')))
    assert test_commands._main([category, 'selection'], detached=True) == 7
    run.assert_called_once_with(ROOT, selections=[(category, ['selection'])])


@pytest.mark.parametrize('argv, expected', [
    (['static', 'all'], [('static', ['all'])]),
    (['unit', '-k', 'component'], [('unit', ['-k', 'component'])]),
    (['unit', '-k', 'component', 'static', 'shell'],
     [('unit', ['-k', 'component']), ('static', ['shell'])]),
    (['static', 'all', 'traceability', 'stage'],
     [('static', ['all']), ('traceability', ['stage'])]),
    (['unit', 'component', 'child-node'], [('unit', []), ('component', []), ('child-node', [])]),
])
def test_multiple_categories_preserve_each_selection(argv, expected):
    assert test_commands.selections(ROOT, argv) == expected
    test_commands.validate(ROOT, argv)


@pytest.mark.parametrize('argv', [
    ['static', 'shell', 'unit', '--bad-option'],
    ['unit', 'all'], ['all', 'unit'], ['static', 'system', '--list'],
])
def test_invalid_or_mixed_listing_selection_is_refused_before_execution(argv):
    with pytest.raises(ValueError):
        test_commands.validate(ROOT, argv)


@pytest.mark.parametrize('failed', [False, True])
def test_selected_summary_counts_timing_evidence_and_failure(tmp_path, monkeypatch, capsys, failed,
                                                          source_identity):
    commands = []

    def execute(self, command, *, output, **kwargs):
        commands.append(command)
        if command[1] == 'unit':
            events = [dict(kind='collection', total=2),
                      dict(kind='finished', nodeid='first')]
            if failed:
                events.append(dict(kind='failure', nodeid='second', when='call', detail='expected failure'))
            events.append(dict(kind='finished', nodeid='second'))
            output(b'raw child diagnostic\n')
            for event in events:
                output((regression.PREFIX + json.dumps(event) + '\n').encode())
            return int(failed)
        output(b'static diagnostic\n')
        return 0

    monkeypatch.setattr(regression.Control, 'run', execute)
    monkeypatch.setattr(regression_process, 'session_stop', None)
    result = regression.retained_main(tmp_path, selections=[('unit', ['-k', 'chosen']), ('static', ['shell'])])
    terminal = regression.Dashboard.ANSI.sub('', capsys.readouterr().out)
    assert 'Host branch 1' in terminal
    assert 'Join host branches' in terminal
    assert 'wall time' in terminal
    assert 'Host branch 2' not in terminal
    assert 'Private D-Bus components' not in terminal
    assert 'Ready E2E scenarios' not in terminal
    assert 'raw child diagnostic' not in terminal
    assert commands[0][1:] == ['unit', '--unattended', '-k', 'chosen']
    report_dir, = (tmp_path / 'docs/TestAutomation/Evidence/test-all-runs').iterdir()
    progress = json.loads((report_dir / 'progress.json').read_text())
    assert [item['name'] for item in progress] == ['Unit and contracts', 'Static checks']
    assert progress[0]['total'] == progress[0]['done'] == 2
    assert progress[0]['elapsed'] >= 0
    report = (report_dir / 'report.md').read_text()
    assert 'raw child diagnostic' in report
    assert 'Scope: selected categories only' in report
    assert 'complete regression' not in report
    if failed:
        assert result == 1
        assert len(commands) == 1
        assert progress[0]['state'] == 'Failed'
        assert progress[0]['failures'] == 1
        assert progress[1]['state'] == 'Blocked'
        assert 'Tests interrupted' not in terminal
        assert 'Copy this prompt' in terminal
    else:
        assert result == 0
        assert len(commands) == 2
        assert 'Overall - 100% (3/3)' in terminal
        assert 'Join host branches — passed' in terminal


def test_vm_only_summary_has_no_host_branches(tmp_path, monkeypatch, capsys, source_identity):
    monkeypatch.setattr(regression.Run, 'wait_for_resources', lambda *_: None)
    monkeypatch.setattr(regression.Control, 'run', lambda *_, **__: 0)
    assert regression.retained_main(tmp_path, selections=[('e2e', ['--id', '30'])]) == 0
    output = regression.Dashboard.ANSI.sub('', capsys.readouterr().out)
    assert 'Ready E2E scenarios - 100% (1/1)' in output
    assert 'Overall - 100% (1/1)' in output
    assert 'Host branch' not in output
    assert 'Join host' not in output


def test_later_vm_selection_still_requires_startup_recovery(tmp_path, monkeypatch):
    monkeypatch.setattr(test_activity, 'descriptors', lambda: (99,))
    recovery = Mock(return_value=0)
    monkeypatch.setattr(regression_process, 'category_run', recovery)
    assert test_recovery.before_run(tmp_path, ['unit', 'e2e'], categories=['unit', 'e2e']) == 0
    recovery.assert_called_once_with(tmp_path, 'integration', ['check_test_recovery'], pipe=False)
