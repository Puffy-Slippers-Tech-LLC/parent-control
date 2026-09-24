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

    rounds = []
    fix_tests.run_loop(['unit', 'ui'], test, prompts.append, lambda: None, selected=True,
                       round_changed=rounds.append)
    assert rounds == [1, 2]
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
    from launcher_render import AgentRenderer
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
    from launcher_render import AgentRenderer
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
    assert text.count('Read example.py') == 1
    assert 'failure details' in text
    for expected in ('Exit 2', 'example.py', '-old', '+new',
                     'Keep assertion', 'tool result', 'public docs', 'Repair blocked',
                     'Missing prerequisite', 'agent failed', 'keep unknown evidence',
                     'null', 'plain diagnostic', 'partial diagnostic'):
        assert expected in text
    assert '\033[?1049' not in stream.getvalue()


@pytest.mark.parametrize('width', [40, 100])
def test_agent_transcript_separates_messages_and_interleaved_command_results(width):
    from launcher_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    renderer = AgentRenderer(stream, width=width)
    commands = [dict(id=name, type='command_execution', command='cat ' + name)
                for name in ('first.py', 'second.py')]
    for command in commands:
        renderer.event({'type': 'item.started', 'item': command})
    renderer.event({'type': 'item.completed', 'item': {
        'type': 'agent_message', 'text': '**Checking results**'}})
    renderer.event({'type': 'item.completed', 'item': {
        **commands[1], 'aggregated_output': 'if fault:\n    raise EvidenceError()\n',
        'exit_code': 0}})
    renderer.event({'type': 'item.completed', 'item': {
        **commands[0], 'aggregated_output': '\033[2J[bold]failure[/bold]', 'exit_code': 2}})
    # Interleaved results repeat their command context, without panel chrome.
    plain = Text.from_ansi(stream.getvalue()).plain
    assert '╭' not in plain and 'Result ·' not in plain and '• Agent' not in plain
    assert 'Exit 2' in plain and 'Exit 0' not in plain
    assert 'Checking results' in plain
    for hidden in ('if fault:', 'EvidenceError'):
        assert hidden not in plain
    assert '[bold]failure[/bold]' in plain
    assert plain.count('Read first.py') == plain.count('Read second.py') == 2
    assert '**' not in plain and '\033[2J' not in stream.getvalue()
    assert all(len(line) <= width for line in plain.splitlines()), repr(plain)


def test_agent_transcript_renders_empty_completed_command_without_start_event():
    from launcher_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    AgentRenderer(stream).event({'type': 'item.completed', 'item': {
        'id': 'empty', 'type': 'command_execution', 'command': 'true',
        'aggregated_output': '', 'exit_code': 0}})
    plain = Text.from_ansi(stream.getvalue()).plain
    assert plain.strip() == '• Ran true'
    assert '(no output)' not in plain


@pytest.mark.parametrize('width', [40, 60, 100])
def test_transcript_observer_preserves_message_alignment_at_terminal_width(monkeypatch, width):
    from launcher_render import AgentRenderer, TranscriptWriter
    from rich.text import Text
    source = io.StringIO()
    paragraphs = [
        'The **launcher** output keeps wrapped text aligned beneath the first word '
        'while preserving café and 日本語 in the retained transcript.',
        'The next paragraph uses the same indentation and keeps its blank separator.',
    ]
    AgentRenderer(source).event({'type': 'item.completed', 'item': {
        'type': 'agent_message', 'text': '\n\n'.join(paragraphs)}})
    output = io.StringIO()
    monkeypatch.setattr(output, 'isatty', lambda: True)
    monkeypatch.setattr(output, 'fileno', lambda: 123)
    monkeypatch.setattr(detached_launcher.os, 'get_terminal_size',
                        lambda fd: detached_launcher.os.terminal_size((width, 24)))
    writer = TranscriptWriter(output)
    # Observer reads may split ANSI sequences or fall in the middle of a row.
    for char in source.getvalue():
        writer.write(char)
    writer.write('', final=True)
    rendered = Text.from_ansi(output.getvalue())
    lines = rendered.plain.splitlines()
    content = [line for line in lines if line.strip()]
    assert content[0].startswith('• The launcher')
    assert all(line.startswith('  ') for line in content[1:])
    assert all(Text(line).cell_len <= width for line in lines)
    assert ' '.join(rendered.plain.split()) == (
        '• ' + ' '.join(' '.join(paragraphs).replace('**', '').split()))
    next_paragraph = next(i for i, line in enumerate(lines) if 'The next paragraph' in line)
    assert not lines[next_paragraph - 1].strip()
    start = rendered.plain.index('launcher')
    assert any(span.start <= start < span.end and span.style.bold for span in rendered.spans)


def test_agent_transcript_hides_reasoning_but_keeps_user_facing_updates():
    from launcher_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    renderer = AgentRenderer(stream)
    for kind in ('item.started', 'item.updated', 'item.completed'):
        renderer.event({'type': kind, 'item': {
            'type': 'reasoning', 'text': 'Internal deliberation'}})
    assert stream.getvalue() == ''
    renderer.event({'type': 'item.completed', 'item': {
        'type': 'agent_message', 'text': 'Checking the renderer.'}})
    assert 'Checking the renderer.' in Text.from_ansi(stream.getvalue()).plain


@pytest.mark.parametrize('command', ['example --check', "/bin/bash -lc 'example --check'"])
@pytest.mark.parametrize('output', ['', 'short result', '\n'.join(
    f'if value == {number}: return True' for number in range(30))])
@pytest.mark.parametrize('exit_code', [0, 2])
def test_command_output_is_compact_and_retained(tmp_path, command, output, exit_code):
    from launcher_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    archive = tmp_path / 'agent-commands.log'
    renderer = AgentRenderer(stream, command_log=archive)
    for identity in ('first', 'second'):
        renderer.event({'type': 'item.completed', 'item': {
            'id': identity, 'type': 'command_execution', 'command': command,
            'aggregated_output': output, 'exit_code': exit_code}})
    rendered = Text.from_ansi(stream.getvalue())
    if output:
        assert output.splitlines()[0] in rendered.plain
    if len(output.splitlines()) > 3:
        assert '+27 lines (agent-commands.log)' in rendered.plain
        assert output.splitlines()[2] in rendered.plain
        assert output.splitlines()[3] not in rendered.plain
        assert output.splitlines()[-1] not in rendered.plain
    assert ('Exit 2' in rendered.plain) == (exit_code == 2)
    assert 'Exit 0' not in rendered.plain
    assert '/bin/bash' not in rendered.plain
    retained = archive.read_text()
    assert retained == ''.join(
        f'\nCommand {identity}: {command}\n{output}\nExit: {exit_code}\n'
        for identity in ('first', 'second'))


@pytest.mark.parametrize('separator', ['\n', '\r\n', '\r'])
def test_command_preview_bounds_multiline_status_output(separator):
    from launcher_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    output = separator.join([
        'Session started', 'Reattach instructions', '│',
        '│  Arbitrary scheduler status', '│    Arbitrary work progress',
    ])
    AgentRenderer(stream).event({'type': 'item.completed', 'item': {
        'id': 'status', 'type': 'command_execution', 'command': 'example',
        'aggregated_output': output, 'exit_code': 0}})
    rendered = Text.from_ansi(stream.getvalue()).plain
    assert 'Session started' in rendered
    assert 'Reattach instructions' in rendered
    assert 'Arbitrary' not in rendered
    assert '+2 lines' in rendered


def test_command_markdown_output_is_hidden_without_archive():
    from launcher_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    AgentRenderer(stream).event({'type': 'item.completed', 'item': {
        'id': 'docs', 'type': 'command_execution', 'command': 'cat README.md',
        'aggregated_output': '**Instructions**\n\n```python\ndef fixed():\n    return True\n```',
        'exit_code': 0}})
    rendered = Text.from_ansi(stream.getvalue())
    assert 'Instructions' not in rendered.plain and 'def fixed():' not in rendered.plain
    assert '**' not in rendered.plain and '```' not in rendered.plain
    assert '• Explored' in rendered.plain and 'Read README.md' in rendered.plain


def test_compact_command_colors_and_wrapping():
    from launcher_render import AgentRenderer
    from rich.color import Color
    from rich.text import Text
    stream = io.StringIO()
    renderer = AgentRenderer(stream, width=40)
    renderer.event({'type': 'item.completed', 'item': {
        'id': 'links', 'type': 'command_execution',
        'command': '/bin/bash -lc "tools/read-only links \'tests/README.md\'"',
        'aggregated_output': 'links: documents=1 checked=31 missing=0', 'exit_code': 0}})
    rendered = Text.from_ansi(stream.getvalue())
    assert '• Ran tools/read-only' in rendered.plain
    assert '└ links:' in rendered.plain
    assert all(len(line) <= 40 for line in rendered.plain.splitlines()), repr(rendered.plain)
    for word, color in [('tools/read-only', 'bright_blue'), ("'tests/README.md'", 'green'),
                        ('links: documents', 'bright_black')]:
        start = rendered.plain.index(word)
        assert any(span.start <= start < span.end and
                   span.style.color.get_truecolor() == Color.parse(color).get_truecolor()
                   for span in rendered.spans if span.style.color)


def test_consecutive_exploration_is_grouped_and_messages_break_the_group():
    from launcher_render import AgentRenderer
    from rich.color import Color
    from rich.text import Text
    stream = io.StringIO()
    renderer = AgentRenderer(stream, width=50)
    for identity, command in enumerate([
            "rg -n '^## |^###' 'docs/Approval-Tools.md'",
            "cat 'tools/launcher_render.py' 'tests/unit/test_fix_tests.py'",
            "sed -n '1,20p' 'tests/README.md'"]):
        item = {'id': str(identity), 'type': 'command_execution', 'command': command}
        renderer.event({'type': 'item.started', 'item': item})
        renderer.event({'type': 'item.completed', 'item': {
            **item, 'exit_code': 0, 'aggregated_output': 'hidden contents'}})
    rendered = Text.from_ansi(stream.getvalue())
    text = rendered.plain
    assert text.count('• Explored') == 1
    assert 'Search ^## |^### in Approval-Tools.md' in text
    assert 'Read launcher_render.py, test_fix_tests.py' in text
    assert '    Read README.md' in text
    assert 'hidden contents' not in text and 'tools/' not in text
    for word, color in [('└', 'bright_black'), ('Search', '#0066ff'),
                        ('^## |^###', '#24292f'), (' in ', 'bright_black'),
                        ('Approval-Tools.md', '#24292f'),
                        ('launcher_render.py', '#24292f'), ('README.md', '#24292f')]:
        start = text.index(word)
        expected = Color.parse(color).get_truecolor()
        assert all(rendered.get_style_at_offset(renderer.console, offset).color.get_truecolor()
                   == expected for offset in range(start, start + len(word)))
    renderer.event({'type': 'item.completed', 'item': {
        'type': 'agent_message', 'text': 'Checking.'}})
    renderer.event({'type': 'item.completed', 'item': {
        **item, 'id': 'next', 'exit_code': 0}})
    assert Text.from_ansi(stream.getvalue()).plain.count('• Explored') == 2


@pytest.mark.parametrize('command', ['cat file; touch other', 'rg word file && build',
                                    'cat $(command)', 'cat `command`'])
def test_compound_commands_are_not_hidden_as_exploration(command):
    from launcher_render import AgentRenderer
    assert AgentRenderer(io.StringIO()).exploration({'command': command}) is None


def test_diff_has_syntax_colors_line_numbers_and_changed_backgrounds():
    from launcher_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    AgentRenderer(stream, width=40).event({'type': 'item.completed', 'item': {
        'type': 'file_change', 'status': 'completed', 'changes': [{
            'kind': 'update', 'path': 'example.py',
            'diff': '@@ -95,2 +70,2 @@\n-    return "old"\n+    return "new"\n     pass'}]}})
    text = Text.from_ansi(stream.getvalue())
    assert '95 - ' in text.plain and '70 + ' in text.plain and '71   ' in text.plain
    backgrounds = {span.style.bgcolor.get_truecolor() for span in text.spans if span.style.bgcolor}
    assert (255, 235, 233) in backgrounds and (218, 251, 225) in backgrounds
    assert any(span.style.color for span in text.spans
               if text.plain[span.start:span.end].strip() == 'return')


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
    from launcher_progress import publish_progress
    monkeypatch.setenv('TERM', 'xterm-256color')
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'output').write_text('category started\n')
    fix_tests.atomic(run / 'frame.json', ['Overall - 0%'])
    publish_progress(run, 'test', ['Round 1: Category: unit (1/4)', 'Status: Running tests'])
    fix_tests.atomic(run / 'test-controller.json', [
        {'key': 'unit', 'lines': ['Category: unit (1/1) | Overall - 0%']}])
    fix_tests.atomic(run / 'result.json', {'status': 0})
    monkeypatch.setattr(detached_launcher, 'current_run', lambda _: run)
    monkeypatch.setattr(detached_launcher, 'busy', lambda _: True)
    polls = 0

    def advance(_):
        nonlocal polls
        polls += 1
        if polls == 1:
            fix_tests.atomic(run / 'frame.json', ['Overall - 50%'])
            fix_tests.atomic(run / 'test-controller.json', [
                {'key': 'unit', 'lines': ['Category: unit (1/1) | Overall - 50%']}])
        elif polls == 3:
            fix_tests.atomic(run / 'frame.json', [])
            (run / 'output').write_text('category started\nfinal summary\n')
            monkeypatch.setattr(detached_launcher, 'busy', lambda _: False)

    monkeypatch.setattr(detached_launcher.time, 'sleep', advance)
    output = io.StringIO()
    monkeypatch.setattr(output, 'isatty', lambda: tty)
    assert fix_tests.follow(run, output) == 0
    text = output.getvalue()
    assert 'category started' in text and 'final summary' in text
    assert 'Overall - 0%' in text and 'Overall - 50%' in text
    from rich.text import Text
    assert 'Round 1: Category: unit (1/4) | Overall - 50%' in Text.from_ansi(text).plain
    assert 'Status: Running tests' in text
    if tty:
        assert text.count('\033[?1049h') == text.count('\033[?1049l') == 1
        assert text.index('final summary') < text.index('\033[?1049l')
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
