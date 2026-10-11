"""Conversation delivery, interruption and editable resizable terminal panes."""

import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import termios

import pytest

import detached_launcher as launcher
from launcher_chat import AppSession, ChatEditor, app_command, read_state, send_input
from launcher_render import AgentRenderer
from tests.support.terminal_screen import Terminal
from tests.support.write_e2e_fixtures import reply
from write_e2e import task_info_instructions
from write_e2e_display import WriteE2EDisplay


@pytest.fixture
def conversation(tmp_path):
    (tmp_path / 'checkpoint.json').write_text(json.dumps({
        'task_id': '001', 'task_sessions': 1, 'total_sessions': 1}))
    (tmp_path / 'prompt.txt').write_text('Implement the task.')
    schema = Path(__file__).parents[2] / 'tools/write_e2e_response.schema.json'
    command = ['/opt/codex', '--model', 'gpt-6.1-sol', '--output-schema', str(schema)]
    output = io.StringIO()
    cleanups = []
    session = AppSession(tmp_path, tmp_path, command, AgentRenderer(output),
                         on_interrupted=lambda: cleanups.append(True))
    return session, output, cleanups


def packets(session):
    result = [json.loads(line) for line in session.outgoing.splitlines()]
    session.outgoing.clear()
    return result


def respond(session, request, result):
    session.feed((json.dumps({'id': request['id'], 'result': result}) + '\n').encode())


def ready(session):
    request, = packets(session)
    assert request['method'] == 'initialize'
    respond(session, request, {})
    initialized, request = packets(session)
    assert initialized['method'] == 'initialized'
    assert request['params']['ephemeral'] is True
    assert request['params']['approvalPolicy'] == 'never'
    respond(session, request, {'thread': {'id': 'thread'}})
    request, = packets(session)
    assert request['params']['outputSchema']['type'] == 'object'
    respond(session, request, {'turn': {'id': 'turn'}})


def notify(session, method, **params):
    session.event({'method': method, 'params': dict(threadId='thread', **params)})


def final(session):
    notify(session, 'item/completed', item={'id': 'final', 'type': 'agentMessage',
                                           'text': json.dumps(reply())})


def test_active_message_steers_and_interrupt_keeps_same_session(conversation, tmp_path):
    session, output, cleanups = conversation
    ready(session)
    send_input(tmp_path, 'message', 'Keep the child signed in.\nCheck the countdown.')
    session.poll()
    steer, = packets(session)
    assert steer['method'] == 'turn/steer'
    assert steer['params']['expectedTurnId'] == 'turn'
    respond(session, steer, {'turnId': 'turn'})
    send_input(tmp_path, 'interrupt')
    session.poll()
    interrupt, = packets(session)
    assert interrupt['method'] == 'turn/interrupt'
    respond(session, interrupt, {})
    notify(session, 'turn/completed', turn={'id': 'turn', 'status': 'interrupted'})
    session.poll()
    assert not session.done and cleanups == [True]
    assert read_state(tmp_path)['status'] == 'waiting'
    assert not (tmp_path / 'cancel').exists()
    send_input(tmp_path, 'message', 'Continue with the same task.')
    session.poll()
    request, = packets(session)
    assert request['method'] == 'turn/start'
    assert request['params']['threadId'] == 'thread'
    respond(session, request, {'turn': {'id': 'next-turn'}})
    assert read_state(tmp_path)['session'] == 1
    assert 'Keep the child signed in.' in output.getvalue()


def test_second_interrupt_only_cancels_when_waiting(conversation, tmp_path):
    session, _, _ = conversation
    ready(session)
    send_input(tmp_path, 'interrupt')
    send_input(tmp_path, 'interrupt')
    session.poll()
    request, = packets(session)
    assert request['method'] == 'turn/interrupt'
    assert not (tmp_path / 'cancel').exists()
    respond(session, request, {})
    notify(session, 'turn/completed', turn={'id': 'turn', 'status': 'interrupted'})
    session.poll()
    send_input(tmp_path, 'interrupt')
    assert (tmp_path / 'cancel').exists()


def test_repeated_interrupt_during_cleanup_does_not_poison_continuation(conversation):
    session, _, _ = conversation
    ready(session)
    session.on_interrupted = lambda: send_input(session.run, 'interrupt')
    send_input(session.run, 'interrupt')
    session.poll()
    interrupt, = packets(session)
    respond(session, interrupt, {})
    notify(session, 'turn/completed', turn={'id': 'turn', 'status': 'interrupted'})
    session.poll()
    assert read_state(session.run)['status'] == 'waiting'
    send_input(session.run, 'message', 'Continue normally.')
    session.poll()
    request, = packets(session)
    assert request['method'] == 'turn/start'
    respond(session, request, {'turn': {'id': 'next-turn'}})
    final(session)
    notify(session, 'turn/completed', turn={'id': 'next-turn', 'status': 'completed'})
    session.poll()
    assert session.done and not (session.run / 'cancel').exists()


def test_message_at_completed_turn_boundary_is_delivered_once(conversation, tmp_path):
    session, _, _ = conversation
    ready(session)
    send_input(tmp_path, 'message', 'Explain the remaining problem.')
    session.poll()
    steer, = packets(session)
    final(session)
    notify(session, 'turn/completed', turn={'id': 'turn', 'status': 'completed'})
    session.event({'id': steer['id'], 'error': {'message': 'No active turn'}})
    session.poll()
    request, = packets(session)
    assert request['method'] == 'turn/start'
    assert request['params']['input'][0]['text'] == 'Explain the remaining problem.'
    respond(session, request, {'turn': {'id': 'next-turn'}})
    assert not session.done
    final(session)
    notify(session, 'turn/completed', turn={'id': 'next-turn', 'status': 'completed'})
    session.poll()
    assert session.done
    assert json.loads((tmp_path / 'agent-result.json').read_text()) == reply()


def test_queued_input_arriving_with_result_prevents_premature_close(conversation, tmp_path):
    session, _, _ = conversation
    ready(session)
    final(session)
    notify(session, 'turn/completed', turn={'id': 'turn', 'status': 'completed'})
    send_input(tmp_path, 'message', 'Review the parent experience too.')
    session.poll()
    request, = packets(session)
    assert request['method'] == 'turn/start' and not session.done


def test_completion_before_steering_ack_still_closes(conversation):
    session, _, _ = conversation
    ready(session)
    send_input(session.run, 'message', 'Keep going.')
    session.poll()
    request, = packets(session)
    final(session)
    notify(session, 'turn/completed', turn={'id': 'turn', 'status': 'completed'})
    respond(session, request, {'turnId': 'turn'})
    session.poll()
    assert session.done


def test_non_race_steering_error_refuses_without_replaying(conversation):
    session, _, _ = conversation
    ready(session)
    send_input(session.run, 'message', 'Keep going.')
    session.poll()
    request, = packets(session)
    with pytest.raises(ValueError, match='turn/steer'):
        session.event({'id': request['id'], 'error': {'message': 'Invalid request'}})
    assert not session.messages


def test_interrupt_racing_completed_turn_leaves_input_open(conversation):
    session, _, cleanups = conversation
    ready(session)
    send_input(session.run, 'interrupt')
    session.poll()
    request, = packets(session)
    final(session)
    notify(session, 'turn/completed', turn={'id': 'turn', 'status': 'completed'})
    session.event({'id': request['id'], 'error': {'message': 'No active turn'}})
    session.poll()
    assert not session.done and cleanups == [True]
    assert read_state(session.run)['status'] == 'waiting'


def test_interrupt_queued_after_completion_still_waits_for_cleanup(conversation):
    session, _, cleanups = conversation
    ready(session)
    final(session)
    notify(session, 'turn/completed', turn={'id': 'turn', 'status': 'completed'})
    send_input(session.run, 'interrupt')
    session.poll()
    assert cleanups == [True] and not session.done
    assert read_state(session.run)['status'] == 'waiting'


def test_message_queued_before_final_ack_is_not_lost(conversation):
    session, _, _ = conversation
    ready(session)
    send_input(session.run, 'message', 'First instruction.')
    session.poll()
    steer, = packets(session)
    final(session)
    notify(session, 'turn/completed', turn={'id': 'turn', 'status': 'completed'})
    send_input(session.run, 'message', 'Review the remaining problem.')
    respond(session, steer, {'turnId': 'turn'})
    session.poll()
    request, = packets(session)
    assert not session.done
    assert request['method'] == 'turn/start'
    assert request['params']['input'][0]['text'] == 'Review the remaining problem.'


def test_input_racing_result_commit_is_preserved(conversation, monkeypatch):
    import launcher_chat
    session, _, _ = conversation
    ready(session)
    final(session)
    notify(session, 'turn/completed', turn={'id': 'turn', 'status': 'completed'})
    take = launcher_chat.take_input

    def arriving_input(run):
        entries = take(run)
        send_input(run, 'message', 'One more check before finishing.')
        return entries

    monkeypatch.setattr(launcher_chat, 'take_input', arriving_input)
    session.poll()
    assert not session.done
    monkeypatch.setattr(launcher_chat, 'take_input', take)
    session.poll()
    request, = packets(session)
    assert request['params']['input'][0]['text'] == 'One more check before finishing.'


@pytest.mark.parametrize('interrupted', [False, True])
def test_interrupt_cleanup_waits_for_ack_and_keeps_queued_continuation(conversation, interrupted):
    session, _, cleanups = conversation
    ready(session)
    send_input(session.run, 'interrupt')
    send_input(session.run, 'message', 'Continue after cleanup.')
    session.poll()
    interrupt, = packets(session)
    final(session)
    notify(session, 'turn/completed', turn={
        'id': 'turn', 'status': 'interrupted' if interrupted else 'completed'})
    assert cleanups == []
    if interrupted:
        respond(session, interrupt, {})
    else:
        session.event({'id': interrupt['id'], 'error': {'message': 'No active turn'}})
    session.poll()
    request, = packets(session)
    assert cleanups == [True] and not session.done
    assert request['method'] == 'turn/start'
    assert request['params']['input'][0]['text'] == 'Continue after cleanup.'


def test_steering_retries_preserve_order_across_turn_boundary(conversation):
    session, _, _ = conversation
    ready(session)
    send_input(session.run, 'message', 'First instruction.')
    session.poll()
    steer, = packets(session)
    send_input(session.run, 'message', 'Second instruction.')
    session.poll()
    assert packets(session) == []
    final(session)
    notify(session, 'turn/completed', turn={'id': 'turn', 'status': 'completed'})
    session.event({'id': steer['id'], 'error': {'message': 'No active turn'}})
    session.poll()
    request, = packets(session)
    assert request['method'] == 'turn/start'
    assert request['params']['input'][0]['text'] == 'First instruction.\n\nSecond instruction.'


def test_adviser_completion_cannot_finish_coordinator(conversation):
    session, _, _ = conversation
    ready(session)
    session.event({'method': 'turn/completed', 'params': {
        'threadId': 'adviser', 'turn': {'id': 'adviser-turn', 'status': 'completed'}}})
    assert session.turn == 'turn' and not session.done


def test_explanation_is_retained_while_only_status_changes(conversation, tmp_path):
    session, _, _ = conversation
    ready(session)
    explanation = 'Checks that the time shown to a child decreases once each minute.'
    session.status_update(json.dumps({'explanation': explanation}))
    session.status_update(json.dumps({'status': 'The timer skipped a minute. Checking how it refreshes.'}))
    info = json.loads((tmp_path / 'task-info.json').read_text())
    assert info['explanation'] == explanation
    prompt = task_info_instructions(tmp_path, '001')
    assert 'Omit explanation unless' in prompt
    assert explanation in prompt
    assert 'Include explanation:' in task_info_instructions(tmp_path, '002')


def test_app_transport_preserves_policy_and_model_config():
    command = ['/opt/codex', '--ask-for-approval', 'never', 'exec', '--ephemeral',
               '-c', 'agents.max_depth=1', '-c', 'service_tier="default"',
               '--output-schema', '/schema', '-']
    actual = app_command(command)
    assert actual[:4] == ['/opt/codex', 'app-server', '--listen', 'stdio://']
    assert 'agents.max_depth=1' in actual and 'service_tier="default"' in actual
    assert 'approval_policy="never"' in actual and 'sandbox_mode="workspace-write"' in actual
    assert '--ephemeral' not in actual


def test_multiline_editor_paste_delete_unicode_and_submission():
    sent = []
    editor = ChatEditor(sent.append)
    for byte in '孩子'.encode():
        editor.feed(bytes([byte]))
    editor.feed(b'\x1b\rsecond\x1b[A\x1b[F!')
    assert editor.text == '孩子!\nsecond'
    editor.feed(b'\x1b[B\x1b[H\x7f')
    assert editor.text == '孩子!second'
    editor.feed(b'\x1b[F\x1b[200~\nmore\nlines\x1b[201~')
    assert sent == [] and editor.text.endswith('more\nlines')
    editor.feed(b'\r')
    assert sent == ['孩子!second\nmore\nlines']
    assert editor.text == '' and editor.cursor == 0
    editor.feed(b'\x1b[200~one\r\ntwo\rthree\x1b[201~')
    assert editor.text == 'one\ntwo\nthree'


def display_fixture(tmp_path, width=120, height=36):
    terminal = Terminal(width, height)
    display = WriteE2EDisplay(terminal, run=tmp_path, terminal_size=lambda: terminal.size)
    display.chat_state = {'session': 1, 'task_session': 1, 'task_id': '001', 'status': 'running'}
    display.task_info = {'task_id': '001', 'explanation': 'Checks the child countdown.'}
    display.update([{'key': 'counter', 'pinned': True, 'lines': ['Tasks: 1/3']},
                    {'key': '1', 'lines': ['Task 001: Countdown', 'Session [1]: Writing code']}], [])
    return display, terminal


def test_split_drag_resize_and_task_summary_location(tmp_path):
    display, terminal = display_fixture(tmp_path)
    display.write('Output belongs on the left.\n')
    assert display.divider_column == round((terminal.size.columns - 2) * .75) + 1
    lines = terminal.visible().splitlines()
    assert lines[0] == 'Tasks: 1/3'
    assert 'Task 001:' not in lines[0]
    assert lines[2].split('│')[0].strip() == 'Output belongs on the left.'
    assert 'Task 001:' in lines[2].split('│')[1]
    display.mouse(35, display.divider_column, 4, False)
    assert '\033]22;ew-resize\033\\' in terminal.getvalue()
    display.mouse(0, display.divider_column, 4, False)
    display.mouse(32, 61, 4, False)
    display.mouse(0, 61, 4, True)
    ratio = display.ratio
    assert ratio == 60 / 118
    for width, height in ((180, 45), (40, 20), (2, 2), (120, 36)):
        terminal.resize(width, height)
        display.draw()
        assert display.ratio == ratio
        assert all(len(line) <= width for line in terminal.visible().splitlines())
    display.close()
    assert '\033[?1003l' in terminal.getvalue()


def test_typing_anywhere_grows_and_shrinks_composer_without_changing_explanation(tmp_path):
    display, terminal = display_fixture(tmp_path)
    display.focus = 'bottom'
    display.handle_input(b'first\x1b\rsecond\x1b\rthird')
    assert display.focus == 'chat'
    before, _, _ = display.editor_rows(29)
    assert len(before) == 3
    display.handle_input(b'\x15\x7f\x15\x7f')
    after, _, _ = display.editor_rows(29)
    assert len(after) == 1
    assert display.task_info['explanation'] == 'Checks the child countdown.'
    assert 'Checks the child countdown.' in ' '.join(terminal.visible().split())
    previous = terminal.getvalue()
    display.draw()
    assert terminal.getvalue() == previous


def test_chat_ctrl_c_does_not_signal_output_and_cancel_button_uses_same_mailbox(tmp_path):
    display, _ = display_fixture(tmp_path)
    launcher.atomic(tmp_path / 'chat-state.json', display.chat_state)
    display.focus = 'bottom'
    display.handle_input(b'\x03')
    assert not (tmp_path / 'cancel').exists()
    assert json.loads((tmp_path / 'chat-inbox.json').read_text())[0]['kind'] == 'interrupt'
    column, row = display.cancel_button
    display.mouse(0, column, row, False)
    assert len(json.loads((tmp_path / 'chat-inbox.json').read_text())) == 2


def test_output_scrolling_returns_to_latest_without_losing_draft(tmp_path):
    display, terminal = display_fixture(tmp_path)
    display.write(''.join(f'output {index}\n' for index in range(100)))
    display.handle_input(b'keep this draft\x1b[5~')
    assert display.offsets['bottom'] > 0
    assert display.editor.text == 'keep this draft'
    column, row = display.bottom_button
    display.mouse(0, column, row, False)
    assert display.offsets['bottom'] == 0
    assert 'output 99' in terminal.visible()
    assert display.editor.text == 'keep this draft'


def test_input_flags_restore_after_exception(tmp_path, monkeypatch):
    master, slave = os.openpty()
    try:
        with os.fdopen(os.dup(slave), 'w') as stream, os.fdopen(os.dup(slave), 'r') as source:
            original = termios.tcgetattr(slave)
            monkeypatch.setattr('sys.stdin', source)
            monkeypatch.setattr('os.tcgetpgrp', lambda _: os.getpgrp())
            monkeypatch.setenv('TERM', 'xterm')
            with pytest.raises(RuntimeError):
                with WriteE2EDisplay(stream, run=tmp_path):
                    assert not termios.tcgetattr(slave)[3] & termios.ISIG
                    raise RuntimeError('observer failed')
            assert termios.tcgetattr(slave) == original
    finally:
        os.close(master)
        os.close(slave)


def test_installed_app_server_protocol_fields(tmp_path):
    codex = shutil.which('codex')
    if codex is None:
        # The maintained unit environment omits user Node installations from
        # PATH; inspect the ordinary NVM install without launching a login shell.
        versions = Path.home() / '.nvm/versions/node'
        codex = next((str(path) for path in sorted(versions.glob('*/bin/codex'), reverse=True)
                      if path.is_file()), None)
    if codex is None:
        pytest.skip('Codex CLI is not installed; protocol unit doubles still apply')
    destination = tmp_path / 'protocol'
    result = subprocess.run([codex, 'app-server', 'generate-json-schema', '--experimental',
                             '--out', str(destination)], capture_output=True, text=True, timeout=30,
                            env={**os.environ, 'PATH': str(Path(codex).parent) + ':' + os.environ['PATH']})
    assert result.returncode == 0, result.stderr
    thread = json.loads((destination / 'v2/ThreadStartParams.json').read_text())
    assert {'ephemeral', 'sandbox', 'approvalPolicy', 'model', 'cwd'} <= thread['properties'].keys()
    turn = json.loads((destination / 'v2/TurnStartParams.json').read_text())
    assert {'outputSchema', 'threadId', 'input'} <= turn['properties'].keys()
    steer = json.loads((destination / 'v2/TurnSteerParams.json').read_text())
    assert {'expectedTurnId', 'threadId', 'input'} <= steer['properties'].keys()
