"""Core observer guarantees: bounded transcripts, safe input and owned teardown."""

import io
import json
import os
import signal
import select
import termios

import pytest
from tests.support.terminal_screen import Terminal

from launcher_render import AgentRenderer, LauncherDisplay
from launcher_progress import publish_progress
import regression_session


@pytest.fixture
def terminal(monkeypatch):
    terminal = Terminal()
    monkeypatch.setenv('TERM', 'xterm-256color')
    monkeypatch.setattr('launcher_render.shutil.get_terminal_size', lambda **kwargs: terminal.size)
    return terminal


def test_descriptive_output_copies_agent_messages_without_activity_or_user_input(tmp_path):
    import detached_launcher as launcher
    from rich.text import Text
    publish_progress(tmp_path, 'session-1', ['Task 001', 'Session [1]'])
    stream = io.StringIO()
    renderer = AgentRenderer(stream, on_description=launcher.descriptive_output(tmp_path))
    prose = 'The countdown now keeps running while the child switches applications.'
    renderer.event({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': prose}})
    first = json.loads((tmp_path / 'descriptive-output.json').read_text())
    assert '\n'.join(first['lines']) + '\n' == stream.getvalue()
    assert first['progress_key'] == 'session-1'
    renderer.message('Please keep my changes.', 'You')
    renderer.event({'type': 'item.completed', 'item': {'id': 'command',
        'type': 'command_execution', 'command': 'cat example.txt', 'exit_code': 0,
        'aggregated_output': 'This looks like natural-language output from a command.'}})
    renderer.event({'type': 'item.completed', 'item': {'type': 'file_change',
        'changes': [{'path': 'example.txt', 'kind': 'update'}]}})
    renderer.event({'type': 'item.completed', 'item': {'type': 'todo_list',
        'items': [{'text': 'Check the countdown.', 'completed': False}]}})
    renderer.event({'type': 'item.completed', 'item': {'type': 'mcp_tool_call',
        'server': 'example', 'tool': 'read', 'result': 'Tool prose.'}})
    renderer.event({'type': 'item.completed', 'item': {'type': 'agent_message',
        'text': json.dumps({'internal': 'Structured workflow output.'})}})
    assert json.loads((tmp_path / 'descriptive-output.json').read_text()) == first
    # Do not discard real prose merely because it starts with an activity verb.
    renderer.event({'type': 'item.completed', 'item': {'type': 'agent_message',
        'text': 'Wrote the correction; the countdown now survives application switches.'}})
    record = json.loads((tmp_path / 'descriptive-output.json').read_text())
    description = Text.from_ansi('\n'.join(record['lines'])).plain
    assert prose in description and 'Wrote the correction;' in description
    assert 'Explored' in Text.from_ansi(stream.getvalue()).plain
    # A new session resets only the duplicate presentation, not the full log.
    launcher.descriptive_output(tmp_path)
    fresh = json.loads((tmp_path / 'descriptive-output.json').read_text())
    assert fresh['session'] != record['session'] and fresh['lines'] == []
    assert prose in Text.from_ansi(stream.getvalue()).plain


def test_descriptive_output_retention_is_bounded(tmp_path):
    import detached_launcher as launcher
    from launcher_render import SCROLLBACK_CHARACTERS, SCROLLBACK_LINES
    append = launcher.descriptive_output(tmp_path)
    append('older\n' * (SCROLLBACK_LINES + 20))
    append('x' * (SCROLLBACK_CHARACTERS + 20) + '\nnewest\n')
    lines = json.loads((tmp_path / 'descriptive-output.json').read_text())['lines']
    assert len(lines) <= SCROLLBACK_LINES
    assert sum(map(len, lines)) <= SCROLLBACK_CHARACTERS
    assert lines[-1] == 'newest' and 'older' not in lines


def test_partial_and_unsaved_output_have_a_text_budget(terminal, monkeypatch):
    monkeypatch.setattr('launcher_render.SCROLLBACK_CHARACTERS', 128)
    display = LauncherDisplay(terminal)
    for _ in range(30):
        display.write('old text ' * 4, saved=False)
        assert len(display.pending) + sum(map(len, display.transcript)) <= 128
        assert sum(map(len, display.unsaved)) <= 128
    display.write('newest text', final=True, saved=False)
    assert not display.pending
    assert ''.join(display.transcript).endswith('newest text')
    assert ''.join(display.unsaved).endswith('newest text')
    assert sum(map(len, display.transcript)) <= 128


def test_step_history_has_a_text_budget(terminal, monkeypatch):
    monkeypatch.setattr('launcher_render.SCROLLBACK_CHARACTERS', 128)
    display = LauncherDisplay(terminal)
    for index in range(30):
        display.update([{'key': str(index), 'lines': ['step ' + str(index)] * 10}], [])
        assert sum(len(line) for lines in display.step_history.values() for line in lines) <= 128
    assert list(display.step_history)[-1] == '29'


@pytest.mark.parametrize('reason', ['success', 'error', 'interrupt'])
def test_mouse_input_is_not_echoed_and_terminal_modes_are_restored(terminal, monkeypatch, reason):
    master, slave = os.openpty()
    try:
        original = termios.tcgetattr(slave)
        with os.fdopen(os.dup(slave), 'r') as source:
            monkeypatch.setattr('launcher_render.sys.stdin', source)
            monkeypatch.setattr(terminal, 'fileno', lambda: slave)
            monkeypatch.setattr('launcher_render.os.get_terminal_size', lambda fd: terminal.size)
            monkeypatch.setattr('launcher_render.os.tcgetpgrp', lambda fd: os.getpgrp())
            try:
                with LauncherDisplay(terminal) as display:
                    display.update([{'key': 'task', 'lines': ['Task']}], [])
                    current = termios.tcgetattr(slave)
                    assert not current[3] & (termios.ECHO | termios.ICANON)
                    assert current[3] & termios.ISIG == original[3] & termios.ISIG
                    assert '\x1b[?1002h' not in terminal.getvalue()
                    os.write(master, b'm')
                    assert select.select([slave], [], [], 1)[0]
                    display.poll_input()
                    assert display.mouse_capture
                    before = terminal.getvalue()
                    # Empty top pane scroll and terminal arrow fallback must neither
                    # repaint content nor echo raw escape sequences into the screen.
                    os.write(master, b'\x1b[<0;2;1M\x1b[<64;2;1M\x1b[A\x1b[B\x1b[B\x1b')
                    assert select.select([slave], [], [], 1)[0]
                    display.poll_input()
                    assert display.focus == 'top'
                    assert display.offsets == {'top': 0, 'bottom': 0}
                    assert terminal.getvalue() == before
                    assert not select.select([master], [], [], 0)[0]
                    if reason == 'error':
                        raise RuntimeError('test exit')
                    if reason == 'interrupt':
                        raise KeyboardInterrupt
            except (RuntimeError, KeyboardInterrupt):
                if reason == 'success':
                    raise
            assert termios.tcgetattr(slave) == original
            assert '\x1b[?1002h\x1b[?1006h' in terminal.getvalue()
            assert '\x1b[?1002l\x1b[?1006l' in terminal.getvalue()
    finally:
        os.close(master)
        os.close(slave)


@pytest.mark.parametrize('height,reason,observer', [
    (24, reason, 'workflow')
    for reason in ('success', 'interrupt', 'error', 'hup', 'term', 'quit')
] + [(1, 'success', 'tests'), (3, 'error', 'tests')])
def test_observer_preserves_output_on_every_exit(terminal, monkeypatch, tmp_path, height, reason, observer):
    import detached_launcher

    monkeypatch.setattr('launcher_display.time.strftime', lambda format: '09:07')
    monkeypatch.setattr('launcher_display.time.monotonic', lambda: 5000)
    monkeypatch.setattr('launcher_display.owner_clock', lambda run: {'started_monotonic': 680})
    terminal.resize(80, height)
    terminal.write('original shell prompt> ')
    (tmp_path / 'output').write_text('earliest output\n' + 'old output\n' * 2100
                                    + 'agent transcript\nunfinished output')
    signals = {'hup': signal.SIGHUP, 'term': signal.SIGTERM, 'quit': signal.SIGQUIT}
    handlers = {sig: signal.SIG_DFL for sig in signals.values()}
    monkeypatch.setattr(signal, 'getsignal', lambda sig: handlers[sig])
    monkeypatch.setattr(signal, 'signal', lambda sig, handler: handlers.__setitem__(sig, handler))
    monkeypatch.delenv(regression_session.FRAME_DIRECTORY, raising=False)

    def output(run, stream, display, **kwargs):
        display.update([{'key': 'task', 'lines': ['controller header', 'session status']}],
                       ['[Running] test details'])
        display.write('agent transcript\nunfinished output')
        # Even an observer which only read the tail must leave the shell's
        # scrollback alone until detaching, then replay its complete saved log.
        assert 'earliest output' not in terminal.scrollback
        assert terminal.normal_screen is not None
        if reason == 'interrupt':
            raise KeyboardInterrupt
        if reason == 'error':
            raise RuntimeError('observer failed')
        if reason in signals:
            sig = signals[reason]
            handlers[sig](sig, None)
        return 0

    monkeypatch.setattr(detached_launcher, 'follow_output', output)
    follow = detached_launcher.follow if observer == 'workflow' else regression_session.follow
    if reason == 'success':
        assert follow(tmp_path, terminal) == 0
    else:
        exception = KeyboardInterrupt if reason == 'interrupt' else RuntimeError if reason == 'error' else SystemExit
        with pytest.raises(exception) as caught:
            follow(tmp_path, terminal)
        if reason in signals:
            assert caught.value.code == 128 + signals[reason]
    restored = terminal.getvalue().split('\033[?1049l', 1)[1]
    assert 'earliest output\n' in restored
    assert restored.count('old output\n') == 2100
    assert 'controller header' in restored and 'session status' in restored
    from launcher_render import clean
    assert clean(restored).endswith('agent transcript\nunfinished output\n\ncontroller header\n'
                                    'Ended: 09:07\nDuration: 1h 12m\n')
    assert '\033[2J' not in restored and '\033[H' not in restored
    assert '[Running] test details' not in restored
    assert '─' not in restored
    assert '\033[?1049h' not in restored
    assert terminal.normal_screen is None
    assert terminal.cursor_visible
    assert 'original shell prompt>' in terminal.scrollback
    assert all(handler == signal.SIG_DFL for handler in handlers.values())


def test_exit_replay_filters_cursor_controls_preserves_color_and_runs_once(terminal, tmp_path):
    log = tmp_path / 'output'
    log.write_text('\033[2J\033[Hfirst output\n\033[31mfinal warning\033[0m\n')
    display = LauncherDisplay(terminal, log_path=log)
    display.write('final warning\n')
    display.close()
    restored = terminal.getvalue().split('\033[?1049l', 1)[1]
    assert 'first output' in restored and 'final warning' in restored
    assert '\033[2J' not in restored and '\033[H' not in restored
    assert '\033[31m' in restored
    before = terminal.getvalue()
    display.close()
    assert terminal.getvalue() == before


def test_exit_without_readable_log_preserves_live_transcript(terminal, tmp_path):
    with LauncherDisplay(terminal, log_path=tmp_path / 'missing') as display:
        display.write('observed output\npartial line')
    assert terminal.getvalue().split('\033[?1049l', 1)[1].endswith(
        'observed output\npartial line\n')


@pytest.mark.parametrize('observer', ['workflow', 'tests'])
@pytest.mark.parametrize('finished', [True, False])
def test_real_output_follow_replays_log_and_missing_result_notice(terminal, tmp_path, monkeypatch,
                                                                 observer, finished):
    import detached_launcher

    run = tmp_path / 'run'
    run.mkdir()
    (run / 'output').write_text('first result\nlast result\n')
    publish_progress(run, 'task', ['Task complete' if finished else 'Task running'])
    if finished:
        (run / 'result').write_text('0')
        (run / 'result.json').write_text('{"status": 0}')
    monkeypatch.delenv(regression_session.FRAME_DIRECTORY, raising=False)
    follow = detached_launcher.follow if observer == 'workflow' else regression_session.follow
    assert follow(run, terminal) == (0 if finished else 1)
    restored = terminal.getvalue().split('\033[?1049l', 1)[1]
    assert restored.count('first result\nlast result\n') == 1
    if not finished:
        assert ('run is incomplete' if observer == 'tests' else 'worker ended without a result') in restored


def test_pipe_does_not_replay_saved_log(tmp_path):
    log = tmp_path / 'output'
    log.write_text('old output\nnew output\n')
    stream = io.StringIO()
    with LauncherDisplay(stream, log_path=log) as display:
        display.write('new output\n')
    assert stream.getvalue() == 'new output\n'


def test_pasted_newlines_do_not_submit_other_automatically(terminal):
    question = {'id': 'q', 'question': 'What should we do?', 'options': ['Repair', 'Review']}
    answers = []
    display = LauncherDisplay(terminal)
    display.update_question(question, lambda *answer: answers.append(answer))
    display.handle_input(b'3\x1b[200~Review\nfirst\r\n\x1b[201~')
    assert not answers
    display.handle_input(b'\r')
    assert answers == [('q', 2, 'Review first  ')]
    display.close()


def test_blocked_structured_result_is_displayed_only_by_workflow():
    from tests.support.write_e2e_fixtures import reply
    stream = io.StringIO()
    reported = []
    renderer = AgentRenderer(stream, hide_task_completion=True, on_usage=reported.append)
    renderer.event({'type': 'item.completed', 'item': {'type': 'agent_message',
                                                     'text': json.dumps(reply('blocked'))}})
    usage = {'input_tokens': 100, 'cached_input_tokens': 80, 'output_tokens': 20}
    renderer.event({'type': 'turn.completed', 'usage': usage})
    assert stream.getvalue() == ''
    assert reported == [usage]


@pytest.mark.parametrize('label', ['write-e2e', 'fix-tests'])
def test_workflow_observer_routes_keyboard_answer_to_persisted_question(terminal, tmp_path, monkeypatch, label):
    import detached_launcher
    from launcher_question import pending
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'output').write_text('A prerequisite is waiting.\n')
    detached_launcher.atomic(run / 'question.json', {
        'id': 'q', 'question': 'What should we do?', 'options': ['Repair', 'Review'], 'answer': None})
    detached_launcher.atomic(run / 'result.json', {'status': 0})

    def answer(display):
        if display.question is not None:
            display.handle_input(b'2\r')

    monkeypatch.setattr(LauncherDisplay, 'poll_input', answer)
    assert detached_launcher.follow(run, terminal, label=label) == 0
    assert pending(run) is None
    assert json.loads((run / 'question.json').read_text())['answer'] == 'Review'


def test_display_preserves_custom_and_ignored_signal_handlers(terminal, monkeypatch):
    handlers = {signal.SIGHUP: signal.SIG_IGN, signal.SIGTERM: lambda *_: None,
                signal.SIGQUIT: signal.SIG_DFL}
    original = handlers.copy()
    monkeypatch.setattr(signal, 'getsignal', lambda sig: handlers[sig])
    monkeypatch.setattr(signal, 'signal', lambda sig, handler: handlers.__setitem__(sig, handler))
    with LauncherDisplay(terminal):
        assert handlers[signal.SIGHUP] == signal.SIG_IGN
        assert handlers[signal.SIGTERM] is original[signal.SIGTERM]
    assert handlers == original
