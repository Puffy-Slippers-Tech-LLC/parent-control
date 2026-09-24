"""The scripting loop never resumes an agent or repeats composite categories."""

import json
import io
from pathlib import Path
from unittest.mock import Mock

import pytest

import fix_tests
import detached_launcher
import regression
import regression_selection
import test_commands
from tests.support.paths import ROOT


def failure(prompt, *categories):
    return {'prompt': prompt, 'categories': list(categories)}


def test_category_status_uses_the_discovered_inventory_position():
    categories = ['unit', 'future-suite', 'e2e']
    assert fix_tests.category_status('future-suite', categories) == (
        '\033[1;36mRunning category [future-suite] (2/3)\033[0m')
    assert fix_tests.category_status('all', categories) is None


@pytest.mark.parametrize('requested, expected', [
    ([], ['unit', 'ui', 'future-suite', 'system', 'e2e']),
    (['host'], ['unit', 'ui', 'future-suite']),
    (['host-builds', 'unit', 'system'], ['unit', 'ui', 'future-suite', 'system']),
    (['ui', 'unit', 'ui'], ['unit', 'ui']),
    (['unit ui'], ['unit', 'ui']),
    (['all', 'host'], ['unit', 'ui', 'future-suite', 'system', 'e2e']),
])
def test_selected_inventory_expands_and_deduplicates(requested, expected):
    inventory = {name: {'args': ['--case', 'two words']} for name in
                 ('unit', 'ui', 'future-suite', 'system', 'e2e')}
    selected = test_commands.suite_inventory(requested, inventory=inventory)
    assert list(selected) == expected
    assert all(selected[name] is inventory[name] for name in expected)


@pytest.mark.parametrize('requested', [['typo'], ['unit', 'coverage'], [' ']])
def test_invalid_selection_is_refused(requested):
    with pytest.raises(ValueError):
        test_commands.suite_inventory(requested, inventory={'unit': {'args': []}})


def test_selected_rounds_reverify_earlier_leaves_after_repairs():
    pending = iter([
        ('unit', None), ('ui', failure('first ui', 'ui')), ('ui', None),
        ('unit', failure('unit regression', 'unit')), ('unit', None), ('ui', None),
        ('unit', None), ('ui', None),
    ])
    prompts = []

    def test(category):
        expected, result = next(pending)
        assert category == expected
        return result

    fix_tests.run_loop(['unit', 'ui'], test, prompts.append, lambda: None, selected=True)
    assert list(pending) == []
    assert prompts == ['first ui', 'unit regression']


def test_cli_forwards_category_arguments(monkeypatch):
    select = Mock(return_value=(None, False))
    monkeypatch.setattr(fix_tests, 'select', select)
    assert fix_tests.main(['unit', 'ui']) == 0
    assert select.call_args.kwargs['categories'] == ['unit', 'ui']


def test_rounds_repair_only_failed_categories_with_latest_prompt(capsys):
    pending = iter([
        ('unit', failure('unit first', 'unit')),
        ('unit', failure('unit second', 'unit')), ('unit', None),
        ('ui', None), ('system', None), ('e2e', None),
        ('all', failure('aggregate ui', 'ui')), ('ui', failure('ui only', 'ui')),
        ('ui', None), ('all', None),
    ])
    prompts, calls = [], []

    def test(category):
        expected, result = next(pending)
        assert category == expected
        calls.append(category)
        return result

    fix_tests.run_loop(['unit', 'ui', 'system', 'e2e'], test, prompts.append, lambda: None)
    assert list(pending) == []
    assert calls.count('system') == calls.count('e2e') == 1
    assert prompts == ['unit first', 'unit second', 'aggregate ui', 'ui only']
    assert 'Running category' not in capsys.readouterr().out


def test_multiple_aggregate_failures_recheck_companions_before_repair():
    pending = iter([None, None, failure('both', 'unit', 'ui', 'unit'), None, None, None])
    calls, prompts = [], []

    def test(category):
        calls.append(category)
        return next(pending)

    fix_tests.run_loop(['unit', 'ui'], test, prompts.append, lambda: None)
    assert calls == ['unit', 'ui', 'all', 'unit', 'ui', 'all']
    assert prompts == ['both']


def test_cancellation_never_starts_an_agent_or_next_test():
    repair = Mock(side_effect=fix_tests.Stopped)
    test = Mock(return_value=failure('current', 'unit'))
    with pytest.raises(fix_tests.Stopped):
        fix_tests.run_loop(['unit', 'ui'], test, repair, lambda: None)
    test.assert_called_once_with('unit')
    repair.assert_called_once_with('current')


def test_unmapped_aggregate_failure_is_not_a_fabricated_category_pass():
    test = Mock(side_effect=[None, failure('infrastructure')])
    repair = Mock()
    with pytest.raises(ValueError, match='no runnable retry category'):
        fix_tests.run_loop(['unit'], test, repair, lambda: None)
    repair.assert_not_called()


def test_agent_is_ephemeral_high_sol_with_policy_and_without_parent_context(monkeypatch):
    monkeypatch.setattr(fix_tests.shutil, 'which', lambda _: '/opt/codex')
    for key in ('CODEX_THREAD_ID', 'CODEX_PARENT_THREAD_ID', 'CODEX_SESSION_ID',
                'ONPC_TEST_ACTIVITY_FD', fix_tests.FRAME_DIRECTORY):
        monkeypatch.setenv(key, 'previous-context')
    command = fix_tests.agent_command(ROOT, 'gpt-6-sol', fix_tests.DEFAULT_EFFORT)
    assert command[:5] == ['/opt/codex', '--ask-for-approval', 'never', 'exec', '--ephemeral']
    assert command[command.index('--model') + 1] == 'gpt-6-sol'
    assert 'model_reasoning_effort="high"' in command
    assert 'features.memories=false' in command and 'history.persistence="none"' in command
    assert 'workspace-write' in command
    assert '--json' in command
    assert command[command.index('--color') + 1] == 'never'
    assert not {'resume', 'fork', '--last', '--ignore-rules', '--dangerously-bypass-approvals-and-sandbox'} & set(command)
    assert command[-1] == '-'
    assert 'previous-context' not in fix_tests.environment().values()
    assert fix_tests.repair_prompt('LATEST FAILURE').startswith('LATEST FAILURE\n')
    assert 'status "test_fixed"' in fix_tests.repair_prompt('LATEST FAILURE')
    assert 'status "uncertain"' in fix_tests.repair_prompt('LATEST FAILURE')


def test_model_catalog_selects_latest_visible_high_sol_and_strongest(monkeypatch):
    monkeypatch.setattr(fix_tests.shutil, 'which', lambda _: '/opt/codex')

    def entry(slug, priority, *, visibility='list', high=True):
        return {'slug': slug, 'priority': priority, 'visibility': visibility,
                'supported_reasoning_levels': [{'effort': 'high' if high else 'medium'}]}

    catalog = {'models': [
        entry('gpt-6-astra', 2), entry('gpt-6-sol', 3),
        entry('gpt-6.1-sol', 4), entry('gpt-7-sol', 1, visibility='hide'),
        entry('gpt-7-astra', 1, high=False),
    ]}
    run = Mock(return_value=Mock(stdout=json.dumps(catalog)))
    monkeypatch.setattr(fix_tests.subprocess, 'run', run)
    assert fix_tests.available_models() == ('gpt-6.1-sol', 'gpt-6-astra')
    assert run.call_args.args[0] == ['/opt/codex', 'debug', 'models']


def test_agent_transcript_formats_markdown_and_code_across_byte_boundaries():
    from fix_tests_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    renderer = AgentRenderer(stream)
    event = {'type': 'item.completed', 'item': {
        'id': 'message', 'type': 'agent_message',
        'text': '**Repair café**\n\n```python\ndef fixed():\n    return True\n```'}}
    encoded = json.dumps(event, ensure_ascii=False).encode()
    for byte in encoded:
        renderer.feed(bytes([byte]))
    assert stream.getvalue() == ''
    renderer.finish()  # EOF also renders a final event without a newline.
    rendered = Text.from_ansi(stream.getvalue())
    assert 'Repair café' in rendered.plain
    assert '**' not in rendered.plain and '```' not in rendered.plain
    assert 'def fixed():' in rendered.plain and 'return True' in rendered.plain
    code_start = rendered.plain.index('def fixed')
    assert any(span.start >= code_start and span.style.color for span in rendered.spans)
    assert '\ufffd' not in rendered.plain


def test_agent_transcript_preserves_activity_failures_and_unknown_events():
    from fix_tests_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    renderer = AgentRenderer(stream)

    def emit(kind, item):
        renderer.feed((json.dumps({'type': kind, 'item': item}) + '\n').encode())

    command = {'id': 'cmd', 'type': 'command_execution', 'command': 'cat example.py'}
    emit('item.started', command)
    emit('item.updated', command)
    emit('item.completed', {**command, 'aggregated_output': 'failure details', 'exit_code': 2})
    emit('item.completed', {'type': 'file_change', 'status': 'completed', 'changes': [
        {'kind': 'update', 'path': 'example.py', 'diff': '-old\n+new'}]})
    emit('item.updated', {'type': 'todo_list', 'items': [
        {'text': 'Keep assertion', 'completed': True}]})
    emit('item.completed', {'type': 'mcp_tool_call', 'server': 'local', 'tool': 'read',
                            'result': {'content': [{'type': 'text', 'text': 'tool result'}]}})
    emit('item.completed', {'type': 'web_search', 'query': 'public docs'})
    emit('item.completed', {'type': 'agent_message', 'text': json.dumps({
        'status': 'blocked', 'summary': '**Missing prerequisite**'})})
    renderer.feed(b'{"type":"turn.failed","error":{"message":"agent failed"}}\n')
    renderer.feed(b'{"type":"future.event","detail":"keep unknown evidence"}\n')
    renderer.feed(b'{"type":"item.completed","item":null}\n')
    renderer.feed(b'plain diagnostic\npartial diagnostic')
    renderer.finish()
    text = Text.from_ansi(stream.getvalue()).plain
    assert text.count('cat example.py') == 1
    for expected in ('failure details', 'Exit 2', 'example.py', '-old', '+new',
                     'Keep assertion', 'tool result', 'public docs', 'Repair blocked',
                     'Missing prerequisite', 'agent failed', 'keep unknown evidence',
                     'null', 'plain diagnostic', 'partial diagnostic'):
        assert expected in text
    assert '\033[?1049' not in stream.getvalue()


def test_follow_keeps_unicode_across_reads_and_reattaches_at_complete_lines(tmp_path, monkeypatch):
    run = tmp_path / 'run'
    run.mkdir()
    original = 'x' * 65535 + 'é\n\033[32mretained café\033[0m\n'
    (run / 'output').write_text(original)
    fix_tests.atomic(run / 'result.json', {'status': 0})
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0
    assert output.getvalue() == original
    monkeypatch.setattr(detached_launcher, 'TAIL_BYTES', len('é\n\033[32mretained café\033[0m\n'.encode()) - 1)
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0
    assert output.getvalue() == '\033[32mretained café\033[0m\n'


@pytest.mark.parametrize('tty', [False, True])
def test_follow_refreshes_retained_frames_and_preserves_logs(tmp_path, monkeypatch, tty):
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'output').write_text('category started\n')
    fix_tests.atomic(run / 'frame.json', ['Overall - 0%'])
    fix_tests.atomic(run / 'category.json', 'Running category [unit] (1/4)')
    fix_tests.atomic(run / 'result.json', {'status': 0})
    monkeypatch.setattr(detached_launcher, 'current_run', lambda _: run)
    monkeypatch.setattr(detached_launcher, 'busy', lambda _: True)
    polls = 0

    def advance(_):
        nonlocal polls
        polls += 1
        if polls == 1:
            fix_tests.atomic(run / 'frame.json', ['Overall - 50%'])
        elif polls == 3:
            fix_tests.atomic(run / 'frame.json', [])
            (run / 'output').write_text('category started\nfinal summary\n')
            monkeypatch.setattr(detached_launcher, 'busy', lambda _: False)

    monkeypatch.setattr(detached_launcher.time, 'sleep', advance)
    output = io.StringIO()
    monkeypatch.setattr(output, 'isatty', lambda: tty)
    assert fix_tests.follow(run, output) == 0
    text = output.getvalue()
    assert text.count('category started') == text.count('final summary') == 1
    assert 'Overall - 0%' in text and 'Overall - 50%' in text
    assert 'Overall - 50%\n\033[2KRunning category [unit] (1/4)' in text
    if tty:
        assert text.count('\033[?1049h') == text.count('\033[?1049l') == 1
        assert '\033[2F' in text
        assert text.index('\033[?1049l') < text.index('final summary')
    else:
        assert text.count('Overall - 50%') == 1
        assert '\033[?1049' not in text


def test_granular_inventory_order_excludes_every_duplicate_helper():
    inventory = test_commands.suite_inventory()
    assert list(inventory)[:2] == ['unit', 'ui']
    assert list(inventory)[-2:] == ['system', 'e2e']
    helpers = {kind for kind, spec in test_commands.CATEGORIES.items()
               if not spec.leaf or not spec.implemented}
    assert set(inventory).isdisjoint(helpers)
    assert set(inventory) | helpers == set(test_commands.CATEGORIES)
    assert inventory['ui']['args'] == ['--timeout', '1800s', '-m', 'not live_e2e']
    for category, spec in inventory.items():
        test_commands.validate(ROOT, ['--stop-on-error', category, *spec['args']])


def test_future_categories_follow_readiness_without_a_second_allowlist(monkeypatch):
    for name, spec in {
        'future-suite': test_commands.CategorySpec('New implemented suite'),
        'future-composite': test_commands.CategorySpec('Combined suites', leaf=False),
        'future-help': test_commands.CategorySpec('Inspection only', leaf=False),
        'future-pending': test_commands.CategorySpec('Waiting for implementation', implemented=False),
    }.items():
        monkeypatch.setitem(test_commands.CATEGORIES, name, spec)
    inventory = test_commands.suite_inventory()
    assert list(inventory)[-3:] == ['future-suite', 'system', 'e2e']
    assert not {'future-composite', 'future-help', 'future-pending'} & inventory.keys()
    monkeypatch.setitem(test_commands.CATEGORIES, 'future-pending',
                        test_commands.CategorySpec('Now implemented'))
    assert 'future-pending' in test_commands.suite_inventory()
    assert 'future-help' in test_commands.usage()


def test_launcher_orders_available_inventory_and_preserves_arguments():
    inventory = {name: {'args': ['--selected', 'two words']} for name in
                 ('e2e', 'new-suite', 'ui', 'unit', 'system')}
    ordered = fix_tests.category_inventory(json.dumps(inventory))
    assert list(ordered) == ['unit', 'ui', 'new-suite', 'system', 'e2e']
    assert ordered['new-suite']['args'] == ['--selected', 'two words']
    assert list(fix_tests.category_inventory('{"new-suite": {"args": []}}')) == ['new-suite']


@pytest.mark.parametrize('value', ['{}', '[]', '{"unit": {}}', '{"unit": {"args": "-x"}}'])
def test_invalid_category_inventory_is_refused(value):
    with pytest.raises(ValueError):
        fix_tests.category_inventory(value)


def test_new_category_failure_has_a_runnable_handoff(tmp_path, monkeypatch):
    monkeypatch.setitem(test_commands.CATEGORIES, 'future-suite',
                        test_commands.CategorySpec('New implemented suite'))
    monkeypatch.setattr(regression_selection, 'source_identity', lambda _: 'fixed')
    monkeypatch.setattr(regression, 'source_identity', lambda _: 'fixed')
    monkeypatch.setattr(regression.Control, 'run', lambda *_args, **_kwargs: 1)
    assert regression.retained_main(tmp_path, selections=[('future-suite', [])]) == 1
    report, = (tmp_path / 'output/test-runs/host/reports').iterdir()
    assert json.loads((report / 'failure.json').read_text())['categories'] == ['future-suite']


def test_stop_on_error_reaches_the_selected_coordinator(monkeypatch):
    run = Mock(return_value=7)
    monkeypatch.setattr(regression, 'main', run)
    assert test_commands._main(['--stop-on-error', 'unit'], detached=True) == 7
    run.assert_called_once_with(ROOT, selections=[('unit', [])], stop_on_error=True)
    with pytest.raises(ValueError):
        test_commands.validate(ROOT, ['--stop-on-error', 'all', '--continue-on-errors'])


@pytest.mark.parametrize('enabled', [False, True])
def test_selected_fail_fast_persists_failure_before_cancelling(tmp_path, monkeypatch, enabled):
    monkeypatch.setattr(regression, 'source_identity', lambda _: 'fixed')
    monkeypatch.setattr(regression_selection, 'source_identity', lambda _: 'fixed')
    observed = []

    def run_selected(run):
        item = run.categories[0]
        item.retry_category = 'unit'
        execution = regression.Execution(run, item, events=True)
        execution.output((regression.PREFIX + json.dumps(
            {'kind': 'failure', 'nodeid': 'test_one', 'when': 'call', 'detail': 'expected failure'}) + '\n').encode())
        observed.append(run.control.stopped.is_set())
        execution.finish(1)

    monkeypatch.setattr(regression_selection.SelectedRun, 'run', run_selected)
    status = regression.retained_main(tmp_path, selections=[('unit', [])], stop_on_error=enabled)
    assert status == (130 if enabled else 1)
    assert observed == [enabled]
    report, = (tmp_path / 'output/test-runs/host/reports').iterdir()
    handoff = json.loads((report / 'failure.json').read_text())
    assert handoff['categories'] == ['unit']
    assert str(report / 'report.md') in handoff['prompt']
    assert json.loads((report / 'progress.json').read_text())[0]['failures'] == 1


def test_bare_artifacts_includes_both_builds_and_comparison(tmp_path, monkeypatch):
    monkeypatch.setattr(regression_selection, 'source_identity', lambda _: 'fixed')
    commands = []

    def jobs(run, planned):
        for job in planned:
            command = job.command() if callable(job.command) else job.command
            commands.append(command[1:])
            job.item.state = 'Passed'
            if job.key in ('build-a', 'build-b'):
                run.artifacts[job.key] = '/tmp/onpc-' + job.key

    monkeypatch.setattr(regression.Run, 'host_jobs', jobs)
    report = regression.Report(tmp_path)
    try:
        run = regression_selection.SelectedRun(tmp_path, report, regression.Control(), [('artifacts', [])])
        run.run()
    finally:
        report.close()
    assert commands == [
        ['artifacts', '--unattended', 'build'], ['artifacts', '--unattended', 'build'],
        ['artifacts', '--unattended', 'compare', '/tmp/onpc-build-a', '/tmp/onpc-build-b']]
