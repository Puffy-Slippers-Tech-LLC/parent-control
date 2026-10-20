"""Conversation delivery, interruption and editable resizable terminal panes."""

import base64
import io
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import termios

import pytest

import detached_launcher as launcher
from launcher_chat import (AppSession, ChatEditor, TASK_STATUSES, app_command, read_state,
                           send_input, task_info, update_task_info)
from launcher_render import AgentRenderer
from tests.support.terminal_screen import Terminal
from tests.support.write_e2e_fixtures import reply
from write_e2e import task_info_instructions
from launcher_display import TaskDisplay
from launcher_view import plan_progress, e2e_progress


@pytest.fixture
def conversation(tmp_path):
    (tmp_path / 'checkpoint.json').write_text(json.dumps({
        'task_id': '001', 'task_sessions': 1, 'total_sessions': 1}))
    (tmp_path / 'prompt.txt').write_text('Implement the task.')
    launcher.atomic(tmp_path / 'controller.json', [{'key': 'runtime-1', 'lines': ['Task 001', 'Session [1]']}])
    schema = Path(__file__).parents[2] / 'tools/write_e2e_response.schema.json'
    command = ['/opt/codex', '--model', 'gpt-6.1-sol', '-c', 'model_reasoning_effort="high"',
               '--output-schema', str(schema)]
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
    assert request['params']['sandbox'] == 'workspace-write'
    respond(session, request, {'thread': {'id': 'thread'}})
    request, = packets(session)
    assert request['params']['outputSchema']['type'] == 'object'
    respond(session, request, {'turn': {'id': 'turn'}})


def notify(session, method, **params):
    session.event({'method': method, 'params': dict(threadId='thread', **params)})


def final(session):
    notify(session, 'item/completed', item={'id': 'final', 'type': 'agentMessage',
                                           'text': json.dumps(reply())})


@pytest.mark.parametrize('text', [None, 'plain prose', '[]', '{"status":"continue","task_id":"wrong"}'])
def test_successful_turn_without_matching_result_reaches_workflow_recovery(conversation, text):
    session, _, _ = conversation
    ready(session)
    if text is not None:
        notify(session, 'item/completed', item={'id': 'final', 'type': 'agentMessage', 'text': text})
    notify(session, 'turn/completed', turn={'id': 'turn', 'status': 'completed'})
    session.poll()
    assert session.done and read_state(session.run)['status'] == 'finished'
    assert (session.run / 'agent-result.json').read_text() == (text or '')


@pytest.mark.parametrize('text', ['plain prose', '[]', '{"status":"continue","task_id":"wrong"}'])
def test_malformed_last_response_cannot_reuse_earlier_structured_message(conversation, text):
    session, _, _ = conversation
    ready(session)
    final(session)
    notify(session, 'item/completed', item={'id': 'last', 'type': 'agentMessage', 'text': text})
    notify(session, 'turn/completed', turn={'id': 'turn', 'status': 'completed'})
    session.poll()
    assert session.done and (session.run / 'agent-result.json').read_text() == text


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
    assert read_state(session.run)['status'] == 'finished'
    assert 'Invalid request' in json.loads((session.run / 'agent-error.json').read_text())['message']


@pytest.mark.parametrize('code', ['cyberPolicy', 'internalServerError', None])
def test_failed_turn_retains_provider_reason_without_acceptance_or_retry(conversation, code):
    session, _, _ = conversation
    ready(session)
    final(session)  # A partial final message cannot qualify a failed turn.
    error = {'message': 'Provider rejected the turn.', 'codexErrorInfo': code}
    with pytest.raises(ValueError, match='Provider rejected the turn') as failure:
        notify(session, 'turn/completed', turn={'id': 'turn', 'status': 'failed', 'error': error})
    retained = json.loads((session.run / 'agent-error.json').read_text())
    assert retained['message'] == str(failure.value)
    if code:
        assert code in retained['message']
    assert read_state(session.run)['status'] == 'finished'
    assert task_info(session.run, session.task)['last_error']
    assert not session.done and session.final is None and not session.completed
    assert not (session.run / 'agent-result.json').exists()
    assert packets(session) == []


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
    session.status_update(json.dumps({'last_error': 'The timer skipped a minute.',
                                     'status': 'Investigating'}))
    session.status_update(json.dumps({'status': 'Root cause identified, fixing'}))
    info = json.loads((tmp_path / 'task-info.json').read_text())
    assert info['explanation'] == explanation
    assert info['last_error'] == 'The timer skipped a minute.'
    assert info['status'] == 'Root cause identified, fixing'
    prompt = task_info_instructions(tmp_path, '001')
    assert 'Omit explanation unless' in prompt
    assert explanation in prompt
    assert 'Include explanation:' in task_info_instructions(tmp_path, '002')
    assert all(status in prompt for status in TASK_STATUSES)


def test_errors_keep_their_age_across_retries_and_task_suspension(conversation, tmp_path, monkeypatch):
    session, _, _ = conversation
    clock = [1000.0]
    monkeypatch.setattr('launcher_chat.time.time', lambda: clock[0])
    session.status_update(json.dumps({'last_error': 'The child countdown stopped.'}))
    assert task_info(tmp_path, '001')['last_error_at'] == 1000.0
    clock[0] += 120
    session.status_update(json.dumps({'status': TASK_STATUSES[2]}))
    update_task_info(tmp_path, '001', {})  # A new session must retain the error clock.
    assert task_info(tmp_path, '001')['last_error_at'] == 1000.0
    update_task_info(tmp_path, '002', {})
    assert 'last_error' not in task_info(tmp_path, '002')
    update_task_info(tmp_path, '002', {'last_error': 'The request could not be sent.'})
    update_task_info(tmp_path, '001', {})
    assert task_info(tmp_path, '001')['last_error'] == 'The child countdown stopped.'
    assert task_info(tmp_path, '001')['last_error_at'] == 1000.0
    assert task_info(tmp_path, '001')['status'] == TASK_STATUSES[2]
    session.status_update(json.dumps({'last_error': 'The child countdown stopped.'}))
    assert task_info(tmp_path, '001')['last_error_at'] == 1120.0  # A real recurrence.
    assert task_info(tmp_path, '001')['status'] == 'Investigating'


def test_status_clock_resets_only_on_status_changes_and_survives_task_suspension(tmp_path, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr('launcher_chat.time.time', lambda: clock[0])
    update_task_info(tmp_path, '001', {})
    assert task_info(tmp_path, '001')['status_at'] == 1000.0
    clock[0] += 60
    update_task_info(tmp_path, '001', {'explanation': 'Checks the countdown.', 'status': 'Running'})
    assert task_info(tmp_path, '001')['status_at'] == 1000.0
    update_task_info(tmp_path, '001', {'last_error': 'The countdown stopped.'})
    assert task_info(tmp_path, '001')['status_at'] == 1060.0
    clock[0] += 60
    update_task_info(tmp_path, '001', {'last_error': 'The countdown stopped again.'})
    assert task_info(tmp_path, '001')['status_at'] == 1060.0
    update_task_info(tmp_path, '001', {'status': TASK_STATUSES[1]})
    assert task_info(tmp_path, '001')['status_at'] == 1120.0
    clock[0] += 60
    update_task_info(tmp_path, '002', {})
    assert task_info(tmp_path, '002')['status_at'] == 1180.0
    update_task_info(tmp_path, '001', {})  # Resume without restarting the clock.
    assert task_info(tmp_path, '001')['status_at'] == 1120.0
    assert task_info(tmp_path, '001')['status'] == TASK_STATUSES[1]


@pytest.mark.parametrize('transport', ['app', 'jsonl'])
@pytest.mark.parametrize('value', [
    {'status': 'Running session 1.'}, {'last_error_at': 0}, {'status_at': 0},
    {'last_error': ''}, {'last_error': '-'}, {'last_error': 42}, {'status': '\033[31m'},
])
def test_invalid_panel_updates_preserve_the_previous_task_information(conversation, tmp_path, value, transport):
    session, output, _ = conversation
    session.renderer.on_description = launcher.descriptive_output(tmp_path)
    session.status_update(json.dumps({'last_error': 'The countdown stopped.'}))
    before = (tmp_path / 'task-info.json').read_text()
    if transport == 'app':
        session.status_update(json.dumps(value))
    else:
        from launcher_chat import task_message
        session.renderer.on_message = lambda text: task_message(tmp_path, session.task, text)
        session.renderer.event({'type': 'item.completed', 'item': {
            'type': 'agent_message', 'text': 'LAUNCHER_STATUS ' + json.dumps(value)}})
    assert (tmp_path / 'task-info.json').read_text() == before
    assert 'LAUNCHER_STATUS' in output.getvalue()
    record = json.loads((tmp_path / 'descriptive-output.json').read_text())
    assert '\n'.join(record['lines']) + '\n' == output.getvalue()


@pytest.mark.parametrize('separator', [' ', '\n', '\n\n'])
@pytest.mark.parametrize('indent', [None, 2])
def test_status_commentary_preserves_only_prose_in_both_transcripts(conversation, tmp_path, separator, indent):
    session, output, _ = conversation
    ready(session)
    session.renderer.on_description = launcher.descriptive_output(tmp_path)
    session.status_update(json.dumps({'last_error': 'The restart requirement was lost.'}))
    error_at = task_info(tmp_path, session.task)['last_error_at']
    prose = ('The retry exposed two separate issues. Ubuntu needs the existing route for '
             'finishing configuration that is already unpacked. Fedora loses the original '
             'installation’s restart requirement during a retry. I’m preserving that '
             'requirement and keeping both final restart checks.')
    update = {'status': 'Root cause identified, fixing',
              'explanation': 'Preserves the "restart" requirement, including a literal }.'}
    text = 'LAUNCHER_STATUS ' + json.dumps(update, indent=indent) + separator + prose
    notify(session, 'item/completed', item={'id': 'commentary', 'type': 'agentMessage', 'text': text})
    expected = io.StringIO()
    AgentRenderer(expected).event({'type': 'item.completed', 'item': {
        'type': 'agent_message', 'text': prose}})
    assert output.getvalue() == expected.getvalue()
    assert 'LAUNCHER_STATUS' not in output.getvalue()
    info = task_info(tmp_path, session.task)
    assert info['status'] == update['status']
    assert info['explanation'] == update['explanation']
    assert info['last_error_at'] == error_at
    record = json.loads((tmp_path / 'descriptive-output.json').read_text())
    assert record['lines']
    assert '\n'.join(record['lines']) + '\n' == output.getvalue()
    assert session.final is None


def test_valid_panel_update_stays_out_of_descriptive_output(conversation, tmp_path):
    session, output, _ = conversation
    ready(session)
    session.renderer.on_description = launcher.descriptive_output(tmp_path)
    text = 'LAUNCHER_STATUS ' + json.dumps({'explanation': 'Checks the restart requirement.'})
    notify(session, 'item/completed', item={'id': 'status', 'type': 'agentMessage', 'text': text})
    assert task_info(tmp_path, session.task)['explanation'] == 'Checks the restart requirement.'
    assert not output.getvalue()
    assert not json.loads((tmp_path / 'descriptive-output.json').read_text())['lines']


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


def display_fixture(tmp_path, width=120, height=36, input_mode='chat'):
    terminal = Terminal(width, height)
    display = TaskDisplay(terminal, run=tmp_path, input_mode=input_mode,
                          terminal_size=lambda: terminal.size)
    display.chat_state = {'session': 1, 'task_session': 1, 'task_id': '001', 'status': 'running'}
    display.task_info = {'task_id': '001', 'explanation': 'Checks the child countdown.'}
    display.update([{'key': 'counter', 'pinned': True, 'lines': ['Tasks: 1/3']},
                    {'key': '1', 'lines': ['Task 001: Countdown', 'Session [1]: Writing code']}], [])
    return display, terminal


@pytest.mark.parametrize('heading,elapsed', [
    ('Task 4-5b: Aborted cleanup and rollback — complete', 'duration unavailable'),
    ('Task 4-5b: Aborted cleanup and rollback (sessions=2, duration=12m) — Complete', '12m'),
    ('\033[32m✓ Task 4-5b: Aborted cleanup and rollback (1h 12m)\033[0m', '1h 12m'),
])
def test_completed_overview_normalizes_legacy_rows_without_changing_owner_records(tmp_path, heading, elapsed):
    display, terminal = display_fixture(tmp_path, width=240)
    steps = [{'key': 'complete-4-5b', 'lines': [heading], 'replaces': ['4-5b']},
             {'key': '4-5c', 'lines': ['Task 4-5c: Current task', 'Session [1]: Working']}]
    original = json.dumps(steps)
    display.update(steps, [])
    expected = f'✓ Task 4-5b: Aborted cleanup and rollback ({elapsed})'
    assert expected in terminal.visible()
    row = next(row for row in display.previous[:display.top_height] if row.plain.startswith('✓ Task 4-5b:'))
    assert all(row.get_style_at_offset(display.console, offset).color.number == 2
               for offset in range(len(expected)))
    assert all(row.get_style_at_offset(display.console, offset).bold
               for offset in range(len('✓ '), len('✓ Task 4-5b:')))
    assert '— complete' not in terminal.visible().lower()
    assert json.dumps(steps) == original
    before = terminal.getvalue()
    display.update(steps, [])
    assert terminal.getvalue() == before


@pytest.mark.parametrize('status,color', zip(TASK_STATUSES, ('#0098ff', '#0098ff', 'yellow', 'green')))
def test_current_task_panel_labels_error_clock_and_status_colors(tmp_path, monkeypatch, status, color):
    clock = [1000.0]
    monkeypatch.setattr('launcher_display.time.time', lambda: clock[0])
    display, terminal = display_fixture(tmp_path, width=400)

    def panel():
        return [row[display.divider_column:] for row in display.previous[display.top_height + 1:]]

    def line(prefix):
        return next(row for row in panel() if row.plain.startswith(prefix))

    empty = line('Last Error:')
    assert empty.plain.rstrip() == 'Last Error: -'
    assert not empty.get_style_at_offset(display.console, len('Last Error: ')).bold
    assert empty.get_style_at_offset(display.console, len('Last Error: ')).color is None
    assert line('Status:').plain.rstrip() == 'Status: Running (0m ago)'
    assert line('Status:').get_style_at_offset(display.console, len('Status: ')).color.name == '#0098ff'
    for no_error in ('', '-', '  '):
        display.task_info.update(last_error=no_error, status=status)
        display.draw()
        assert line('Last Error:').plain.rstrip() == 'Last Error: -'
        assert line('Status:').plain.rstrip() == 'Status: Running (0m ago)'
    display.task_info.update(last_error='The countdown stopped.', last_error_at=1000.0,
                             status=status, status_at=1000.0)
    clock[0] += 120
    display.draw()
    rows = [row.plain.rstrip() for row in panel()]
    header = rows.index('Explanation:')
    assert rows[header + 1] == 'Checks the child countdown.'
    assert set(rows[header - 1]) == set(rows[header + 2]) == {'─'}
    assert rows[header + 3] == 'Last Error: The countdown stopped. (2m ago)'
    assert rows[header + 4] == ''
    assert rows[header + 5] == 'Status: ' + status + ' (2m ago)'
    for prefix in ('Explanation:', 'Last Error:', 'Status:'):
        row = line(prefix)
        assert all(row.get_style_at_offset(display.console, offset).bold for offset in range(len(prefix)))
    error = line('Last Error:')
    for offset in range(len('Last Error: '), len('Last Error: The countdown stopped.')):
        style = error.get_style_at_offset(display.console, offset)
        assert style.color.name == 'red' and not style.bold
    status_row = line('Status:')
    assert status_row.get_style_at_offset(display.console, 0).color is None
    for offset in range(len('Status: ' + status), len(status_row.plain.rstrip())):
        assert status_row.get_style_at_offset(display.console, offset).color.name == '#0098ff'
    for offset in range(len('Status: '), len('Status: ' + status)):
        style = status_row.get_style_at_offset(display.console, offset)
        assert style.color.name == color and not style.bold
    assert '**' not in terminal.visible()
    before = terminal.getvalue()
    clock[0] += 59
    display.draw()
    assert terminal.getvalue() == before
    clock[0] += 1
    display.draw()
    assert '(3m ago)' in line('Last Error:').plain
    assert '(3m ago)' in line('Status:').plain
    # An observer reconnect keeps the owner's timestamp.
    launcher.atomic(tmp_path / 'task-info.json', display.task_info)
    launcher.atomic(tmp_path / 'chat-state.json', display.chat_state)
    reconnected, _ = display_fixture(tmp_path, width=400)
    reconnected.refresh_chat()
    reconnected.chat_state = display.chat_state.copy()
    reconnected.draw()
    assert '(3m ago)' in ''.join(row.plain for row in reconnected.previous)
    assert 'Status: ' + status + ' (3m ago)' in ''.join(row.plain for row in reconnected.previous)
    # A suspended task can be rendered before its next agent session starts.
    update_task_info(tmp_path, '002', {})
    reconnected.refresh_chat()
    reconnected.draw()
    assert 'Last Error: The countdown stopped. (3m ago)' in ''.join(row.plain for row in reconnected.previous)
    # Stale metadata must not leak while the next task's session starts.
    display.chat_state['progress_key'] = '1'
    display.update([{'key': '2', 'lines': ['Task 002: Next', 'Session [1]: Writing code']}], [])
    assert line('Last Error:').plain.rstrip() == 'Last Error: -'
    assert line('Status:').plain.rstrip() == 'Status: Running (0m ago)'


@pytest.mark.parametrize('input_mode', ['chat', 'question', 'none'])
@pytest.mark.parametrize('retained', [True, False])
def test_status_age_refreshes_without_output_and_resets_on_change(tmp_path, monkeypatch, input_mode, retained):
    clock = [1000.0]
    monkeypatch.setattr('launcher_display.time.time', lambda: clock[0])
    display, terminal = display_fixture(tmp_path, width=400, input_mode=input_mode)
    if retained:
        update_task_info(tmp_path, '001', {})
        display.task_info = task_info(tmp_path, '001')
        display.draw()

    def status():
        return next(row[display.divider_column:].plain.rstrip() for row in display.previous
                    if row[display.divider_column:].plain.startswith('Status:'))

    assert status() == 'Status: Running (0m ago)'
    before = terminal.getvalue()
    clock[0] += 59
    display.draw()
    assert terminal.getvalue() == before
    clock[0] += 1
    display.draw()
    assert status() == 'Status: Running (1m ago)'
    clock[0] = 1000.0 + 72 * 60
    display.draw()
    assert status() == 'Status: Running (1h 12m ago)'
    # Changing status restarts its clock, independent of the older error age.
    if retained:
        update_task_info(tmp_path, '001', {'last_error': 'The countdown stopped.'})
        display.task_info = task_info(tmp_path, '001')
    else:
        display.task_info.update(last_error='The countdown stopped.', status='Investigating')
    display.draw()
    assert status() == 'Status: Investigating (0m ago)'
    clock[0] += 60
    display.draw()
    assert status() == 'Status: Investigating (1m ago)'


@pytest.mark.parametrize('input_mode', ['chat', 'question', 'none'])
def test_all_task_panels_enable_wheel_by_default_and_release_mouse_with_f2(tmp_path, input_mode):
    terminal = Terminal(120, 36)
    display = TaskDisplay(terminal, run=tmp_path, input_mode=input_mode,
                          terminal_size=lambda: terminal.size)
    # Only the output protocol needs an attached input descriptor in this
    # screen double; no OS input or terminal restoration is performed here.
    display.input_fd = 123
    display.update([{'key': '1', 'lines': ['Task 001', 'Session [1]']}], [])
    display.write('Selectable execution text.\n')
    question = {'id': 'decision', 'question': 'Continue?', 'options': ['Yes', 'No']}
    display.update_question(question, lambda *args: None)
    display.update_question(None, lambda *args: None)
    assert display.mouse_capture
    output = terminal.getvalue()
    assert '\033[?1006h' in output and '\033[?1049h' in output
    assert ('F2: native selection' if input_mode == 'chat' else 'F2/m: native selection') in terminal.visible()
    display.handle_input(b'\x1bOQ')
    assert not display.mouse_capture
    for mode in (1000, 1002, 1003, 1006):
        assert f'\033[?{mode}h' not in terminal.getvalue()[len(output):]
        assert f'\033[?{mode}l' in terminal.getvalue()[len(output):]


@pytest.mark.parametrize('input_mode', ['chat', 'question', 'none'])
@pytest.mark.parametrize('height', [1, 3, 36])
def test_task_screen_keeps_shell_history_outside_panes(tmp_path, input_mode, height):
    terminal = Terminal(120, height)
    terminal.write('existing shell history\noriginal shell prompt> ')
    history = list(terminal.scrollback)
    display = TaskDisplay(terminal, run=tmp_path, input_mode=input_mode,
                          terminal_size=lambda: terminal.size)
    display.update([{'key': 'task', 'lines': ['Task 001: Countdown']}], [])
    display.write(''.join(f'output {index}\n' for index in range(2100)))
    assert terminal.scrollback == history
    assert terminal.normal_screen is not None
    assert 'original shell prompt>' not in terminal.visible()
    assert display.mouse_capture
    if display.output_height:
        before = terminal.visible().splitlines()
        draft = display.editor.text
        display.handle_input(f'\033[<64;2;{display.top_height + 2}M'.encode())
        after = terminal.visible().splitlines()
        assert display.offsets['bottom'] == 3
        assert before[:display.top_height + 1] == after[:display.top_height + 1]
        assert [row[display.divider_column:] for row in before] == [
            row[display.divider_column:] for row in after]
        assert display.editor.text == draft
        assert terminal.scrollback == history
    protocol = terminal.getvalue()
    display.draw()
    assert terminal.getvalue() == protocol
    terminal.resize(100, 40)
    display.draw()
    assert 'original shell prompt>' not in terminal.visible()
    assert terminal.scrollback == history


def test_task_screen_restores_shell_and_replays_partial_lines_once_on_exit(tmp_path):
    display, terminal = display_fixture(tmp_path, width=40)
    display.write('first\npart')
    display.write('ial ✓\nunfinished')
    assert list(display.transcript) == ['first', 'partial ✓']
    assert display.pending == 'unfinished'
    assert not terminal.scrollback
    terminal.resize(80, 40)
    display.draw()
    display.close()
    protocol = terminal.getvalue()
    restored = protocol.split('\033[?1049l', 1)[1]
    assert restored.count('first\n') == 1
    assert restored.count('partial ✓\n') == 1
    assert restored.count('unfinished\n') == 1
    assert terminal.normal_screen is None
    assert terminal.cursor_visible
    display.close()
    assert terminal.getvalue() == protocol


def test_controller_transitions_do_not_leak_dashboard_rows_into_shell_history(tmp_path):
    display, terminal = display_fixture(tmp_path)
    steps = [{'key': 'task', 'lines': ['Task 002', 'Session 1']}]
    display.update(steps, ['dashboard 1'])
    history = list(terminal.scrollback)
    display.update(steps, ['dashboard 2'])
    assert terminal.scrollback == history
    steps[0]['lines'][-1] = 'Session 2'
    display.update(steps, ['dashboard 3'])
    assert terminal.scrollback == history == []
    assert 'Session 2' in terminal.visible()


def test_task_screen_filters_child_cursor_controls_and_preserves_color(tmp_path):
    display, terminal = display_fixture(tmp_path)
    before = len(terminal.getvalue())
    display.write('\033[2J\033[Hfirst output\n\033[31mfinal warning\033[0m\n')
    assert 'first output' in terminal.visible()
    assert 'final warning' in terminal.visible()
    assert not terminal.scrollback
    protocol = terminal.getvalue()[before:]
    assert '\033[2J' not in protocol and '\033[H' not in protocol
    assert '\033[31m' in protocol
    assert 'Task 001:' in terminal.visible()


@pytest.mark.parametrize('input_mode', ['chat', 'question'])
def test_pending_question_keeps_pane_wheel_and_selection_toggle_available(tmp_path, input_mode):
    terminal = Terminal(120, 20)
    display = TaskDisplay(terminal, run=tmp_path, input_mode=input_mode,
                          terminal_size=lambda: terminal.size)
    question = {'id': 'decision', 'question': 'Continue?', 'options': ['Yes', 'No'],
                'explanation': '\n'.join(f'reason {index}' for index in range(60))}
    sent = []
    display.update_question(question, lambda *args: sent.append(args))
    assert display.mouse_capture
    display.handle_input(f'\033[<65;{display.divider_column + 2};{terminal.size.lines}M'.encode())
    assert display.offsets['info'] > 0
    for byte in b'\x1b[12~':
        display.handle_input(bytes([byte]))
    assert not display.mouse_capture
    display.update_question(question, lambda *args: sent.append(args))
    assert not display.mouse_capture
    display.handle_input(b'\x1bOQ')
    assert display.mouse_capture
    assert not sent and not terminal.scrollback


@pytest.mark.parametrize('fragmented', [False, True])
def test_nonchat_question_paste_cannot_toggle_mouse_or_activate_controls(tmp_path, fragmented):
    display, _ = display_fixture(tmp_path, input_mode='question')
    sent = []
    question = {'id': 'decision', 'question': 'Continue?', 'options': ['Yes', 'No']}
    display.update_question(question, lambda *args: sent.append(args))
    display.handle_input(b'3')
    payload = b'\x1b[200~draft\x1bOQ\x1b[12~\x1b[<64;2;4M\r\x1b[201~'
    for data in ([bytes([byte]) for byte in payload] if fragmented else [payload]):
        display.handle_input(data)
    assert display.mouse_capture
    assert display.offsets['bottom'] == 0
    assert not sent
    assert display.question.text.startswith('draft')
    # A real F2 arriving in the same read as typed instructions still works.
    display.handle_input(b'more\x1bOQ')
    assert not display.mouse_capture
    assert display.question.text.endswith('more')
    assert not sent


@pytest.mark.parametrize('toggle', [b'\x1bOQ', b'\x1b[12~'])
def test_chat_mouse_toggle_restores_native_selection_without_touching_draft(tmp_path, toggle):
    display, terminal = display_fixture(tmp_path)
    display.input_fd = 123
    display.mouse_capture = False
    display.set_mouse_mode()
    display.handle_input(b'keep my draft')
    column, row = 9, display.chat_top
    click = f'\033[<0;{column};{row}M'.encode()
    # A stale report in selection mode must not affect the conversation.
    display.handle_input(click)
    assert not (tmp_path / 'chat-inbox.json').exists()
    for byte in toggle:
        display.handle_input(bytes([byte]))
    assert display.mouse_capture
    assert '\033[?1003h' in terminal.getvalue()
    assert 'F2: native selection' in terminal.visible()
    display.handle_input(f'\033[<0;{display.divider_column};4M'.encode())
    assert display.dragging == 'bottom' and display.pointer
    display.handle_input(toggle)
    assert not display.mouse_capture
    assert display.dragging is None and not display.pointer
    assert 'F2: scroll/resize' in terminal.visible()
    restored = terminal.getvalue().rsplit('\033[?1003h', 1)[1]
    assert '\033[?1003l' in restored and '\033[?1006l' in restored
    display.handle_input(click)
    assert not (tmp_path / 'chat-inbox.json').exists()
    assert display.editor.text == 'keep my draft'
    # Paste content cannot take ownership of the mouse, nor may the normal
    # letter m stop being editable conversation text.
    display.handle_input(b'\x1b[200~' + toggle + b'\x1b[201~m')
    assert not display.mouse_capture
    assert display.editor.text.endswith('m')


def copied_text(terminal):
    return [base64.b64decode(value).decode('utf-8') for value in
            re.findall(r'\x1b\]52;c;([^\x1b]*)\x1b\\', terminal.getvalue())]


@pytest.mark.parametrize('input_mode', ['chat', 'question', 'none'])
@pytest.mark.parametrize('side', ['left', 'right'])
def test_drag_copy_stays_in_starting_panel_across_vertical_separator(tmp_path, input_mode, side):
    display, terminal = display_fixture(tmp_path, input_mode=input_mode)
    display.update([{'key': 'task', 'lines': ['right first', 'right second']}], [])
    display.write('left first\nleft second\n')
    row = display.top_height + 2
    if side == 'left':
        start, end = (1, row), (terminal.size.columns, row + 1)
    else:
        # Reverse selection across the divider exercises clipping on the left.
        start = (display.divider_column + len('right second'), row + 1)
        end = (1, row)
    for button, point, suffix in [(0, start, 'M'), (32, end, 'M'), (0, end, 'm')]:
        report = f'\033[<{button};{point[0]};{point[1]}{suffix}'.encode()
        for byte in report:  # Fragmented mouse reports must remain selections.
            display.handle_input(bytes([byte]))
    assert copied_text(terminal) == [f'{side} first\n{side} second']
    assert not (tmp_path / 'chat-inbox.json').exists()
    assert display.editor.text == ''
    assert display.ratio == .75


def test_panel_copy_preserves_wide_and_combining_characters_without_other_panel(tmp_path):
    display, terminal = display_fixture(tmp_path)
    display.write('孩子 e\u0301\nsecond\n')
    row = display.top_height + 2
    # Begin in the second cell of a wide character; include the whole glyph.
    display.handle_input(f'\033[<0;2;{row}M'.encode())
    display.handle_input(f'\033[<32;7;{row}M'.encode())
    display.handle_input(f'\033[<0;7;{row}m'.encode())
    assert copied_text(terminal) == ['孩子 e\u0301']


def test_panel_copy_uses_drag_snapshot_and_resize_cancels_selection(tmp_path):
    display, terminal = display_fixture(tmp_path)
    display.write('original first\noriginal second\n')
    row = display.top_height + 2
    display.handle_input(f'\033[<0;1;{row}M'.encode())
    display.handle_input(f'\033[<32;100;{row + 1}M'.encode())
    display.write('new output while selecting\n')
    display.handle_input(f'\033[<0;100;{row + 1}m'.encode())
    assert copied_text(terminal) == ['original first\noriginal second']
    display.handle_input(f'\033[<0;1;{row}M'.encode())
    terminal.resize(80, 30)
    display.draw()
    display.handle_input(f'\033[<0;80;{row + 1}m'.encode())
    assert len(copied_text(terminal)) == 1
    assert display.selection is None


def test_panel_click_and_divider_drag_do_not_replace_clipboard(tmp_path):
    display, terminal = display_fixture(tmp_path)
    row = display.top_height + 2
    for column in (1, display.divider_column):
        display.handle_input(f'\033[<0;{column};{row}M'.encode())
        display.handle_input(f'\033[<0;{column};{row}m'.encode())
    assert copied_text(terminal) == []
    assert display.dragging is None


@pytest.mark.parametrize('side', ['left', 'right'])
def test_top_panel_copy_cannot_escape_to_other_panels(tmp_path, side):
    display, terminal = display_fixture(tmp_path)
    display.task_totals = (1, 2, 3)
    display.draw()
    column = 1 if side == 'left' else display.divider_column + 1
    display.handle_input(f'\033[<0;{column};1M'.encode())
    # Cross both the vertical and horizontal panel boundaries.
    end_column = 120 if side == 'left' else 1
    display.handle_input(f'\033[<32;{end_column};36M'.encode())
    display.handle_input(f'\033[<0;{end_column};36m'.encode())
    copied = copied_text(terminal)
    assert len(copied) == 1
    assert copied[0].startswith('Tasks: 1/3' if side == 'left' else 'Total Tasks: 1/2/3')
    assert '│' not in copied[0]
    assert 'Task 001' not in copied[0]
    assert ('Total Tasks:' if side == 'left' else 'Tasks: 1/3') not in copied[0]


def test_description_copy_excludes_scrollbar_and_status_panel(tmp_path):
    display, terminal = display_fixture(tmp_path, height=50)
    display.description = {'lines': [f'description {index}' for index in range(100)]}
    display.draw()
    assert display.description_scrollbar
    column, row = display.divider_column + 1, display.description_top
    display.handle_input(f'\033[<0;{column};{row}M'.encode())
    display.handle_input(b'\033[<32;120;60M')
    display.handle_input(b'\033[<0;120;60m')
    copied = copied_text(terminal)[0]
    assert copied.startswith('description ')
    assert copied.endswith('description 99')
    assert all(line.startswith('description ') for line in copied.splitlines())


def test_session_clock_keeps_owner_origin_across_turns_and_freezes_on_finish(conversation, monkeypatch):
    session, _, _ = conversation
    started = read_state(session.run)['started_at']
    assert read_state(session.run)['progress_key'] == 'runtime-1'
    monkeypatch.setattr('launcher_chat.time.time', lambda: started + 125)
    for status in ('running', 'interrupting', 'cleaning', 'waiting', 'running'):
        session.publish(status)
        assert read_state(session.run)['started_at'] == started
        assert 'finished_at' not in read_state(session.run)
    session.publish('finished')
    state = read_state(session.run)
    assert state['started_at'] == started
    assert state['finished_at'] == started + 125


@pytest.mark.parametrize('progress', [plan_progress, e2e_progress])
def test_fresh_backend_session_clock_reaches_real_workflow_display(conversation, monkeypatch, progress):
    session, _, _ = conversation
    run = session.run
    started = session.started_at
    # Include the styling used by E2E and a cumulative session number distinct
    # from the task's session number. Read real owner publications, not UI fields.
    launcher.atomic(run / 'controller.json', [{'key': 'runtime-1', 'lines': [
        'Task 001: Countdown', '\033[1mSession [1]\033[22m: gpt-6.1-sol xhigh']}])
    session.session = 8
    session.publish('running')
    monkeypatch.setattr('launcher_display.time.time', lambda: started + 12 * 60)
    for _ in range(2):
        terminal = Terminal(240, 36)
        display = TaskDisplay(terminal, run=run, terminal_size=lambda: terminal.size)
        display.refresh_chat()
        steps = json.loads((run / 'controller.json').read_text())
        display.update(progress(run, steps, []), [])
        assert 'Session [1]: gpt-6.1-sol xhigh; 12m' in terminal.visible()


@pytest.mark.parametrize('progress', [plan_progress, e2e_progress])
def test_working_clock_follows_active_turn_across_reconnection_and_continuation(conversation, monkeypatch, progress):
    session, _, cleanups = conversation
    clock = [session.started_at + 10]
    monkeypatch.setattr('launcher_chat.time.time', lambda: clock[0])
    launcher.atomic(session.run / 'controller.json', [{'key': 'runtime-1', 'lines': [
        'Task 001: Countdown', 'Session [1]: gpt-6.1-sol xhigh']}])
    ready(session)
    assert read_state(session.run)['turn_started_at'] == clock[0]

    def reconnect():
        terminal = Terminal(120, 36)
        display = TaskDisplay(terminal, run=session.run, terminal_size=lambda: terminal.size)
        display.refresh_chat()
        steps = json.loads((session.run / 'controller.json').read_text())
        display.update(progress(session.run, steps, []), [])
        return display, terminal

    display, terminal = reconnect()
    assert 'Working (0s)' in terminal.visible()
    unchanged = terminal.getvalue()
    display.draw()
    assert terminal.getvalue() == unchanged
    for elapsed, duration in ((1, '1s'), (59, '59s'), (60, '1m 0s'),
                              (125, '2m 5s'), (3605, '1h 0m 5s')):
        clock[0] = session.started_at + 10 + elapsed
        display.draw()
        assert f'Working ({duration})' in terminal.visible()
    display, terminal = reconnect()
    assert 'Working (1h 0m 5s)' in terminal.visible()
    # Steering an active turn retains its clock.
    send_input(session.run, 'message', 'Keep going.')
    session.poll()
    steer, = packets(session)
    respond(session, steer, {'turnId': 'turn'})
    assert read_state(session.run)['turn_started_at'] == session.started_at + 10
    send_input(session.run, 'interrupt')
    session.poll()
    interrupt, = packets(session)
    respond(session, interrupt, {})
    display.refresh_chat()
    display.draw()
    assert 'Working (' not in terminal.visible()
    notify(session, 'turn/completed', turn={'id': 'turn', 'status': 'interrupted'})
    session.poll()
    assert cleanups == [True]
    display.refresh_chat()
    display.draw()
    assert 'Working (' not in terminal.visible()
    unchanged = terminal.getvalue()
    clock[0] += 1
    display.draw()
    assert terminal.getvalue() == unchanged
    send_input(session.run, 'message', 'Continue.')
    session.poll()
    request, = packets(session)
    respond(session, request, {'turn': {'id': 'next-turn'}})
    display.refresh_chat()
    display.draw()
    assert 'Working (0s)' in terminal.visible()
    assert read_state(session.run)['started_at'] == session.started_at
    final(session)
    notify(session, 'turn/completed', turn={'id': 'next-turn', 'status': 'completed'})
    session.poll()
    display.refresh_chat()
    display.draw()
    assert 'Working (' not in terminal.visible()


@pytest.mark.parametrize('progress_key', ['1', '001'])
def test_session_duration_refreshes_without_output_and_survives_reconnection(tmp_path, monkeypatch, progress_key):
    clock = [1000.0]
    monkeypatch.setattr('launcher_display.time.time', lambda: clock[0])
    display, terminal = display_fixture(tmp_path, width=240)
    display.steps[-1]['key'] = progress_key
    display.chat_state.update(progress_key=progress_key, session=8)
    display.chat_state['started_at'] = clock[0]
    display.draw()
    assert 'Writing code; 0m' in terminal.visible()
    unchanged = terminal.getvalue()
    clock[0] += 59
    display.draw()
    assert terminal.getvalue() != unchanged
    assert 'Working (59s)' in terminal.visible()
    assert 'Writing code; 0m' in terminal.visible()
    clock[0] += 1
    display.draw()
    assert 'Writing code; 1m' in terminal.visible()
    for elapsed, duration in ((12 * 60, '12m'), (3599, '59m'), (3600, '1h 0m'), (4330, '1h 12m')):
        clock[0] = 1000 + elapsed
        display.draw()
        assert 'Writing code; ' + duration in terminal.visible()

    launcher.atomic(tmp_path / 'chat-state.json', display.chat_state)
    reconnected, screen = display_fixture(tmp_path, width=240)
    reconnected.steps[-1]['key'] = progress_key
    reconnected.refresh_chat()
    reconnected.draw()
    assert 'Writing code; 1h 12m' in screen.visible()
    reconnected.chat_state.update(status='finished', finished_at=clock[0])
    reconnected.draw()
    # Session time stops; only the independent status age keeps refreshing.
    unchanged = [row.plain for row in reconnected.previous if 'Status:' not in row.plain]
    clock[0] += 120
    reconnected.draw()
    assert [row.plain for row in reconnected.previous if 'Status:' not in row.plain] == unchanged
    assert 'Writing code; 1h 12m' in screen.visible()
    assert 'Working (' not in screen.visible()
    assert 'Status: Running (2m ago)' in screen.visible()
    assert reconnected.steps[-1]['lines'][-1] == 'Session [1]: Writing code'

    # At the next session boundary stale owner metadata must not leak a clock.
    reconnected.update([{'key': '2', 'lines': ['Task 002: Next', 'Session [1]: Writing code']}], [])
    assert 'Writing code;' not in screen.visible()
    assert 'Working (' not in screen.visible()
    reconnected.chat_state.update(session=9, progress_key='2', started_at=clock[0], status='running')
    reconnected.chat_state.pop('finished_at')
    reconnected.draw()
    assert 'Writing code; 0m' in screen.visible()

    # Ordinary plans reuse the task key across retries. The next session line
    # must not borrow the old attempt's elapsed time during that transition.
    reconnected.update([{'key': '001', 'lines': ['Task 001: Countdown', 'Session [2]: Writing code']}], [])
    assert 'Writing code;' not in screen.visible()
    reconnected.chat_state.update(task_id='001', task_session=2, progress_key='001')
    reconnected.draw()
    assert 'Writing code; 0m' in screen.visible()


def test_split_drag_resize_and_task_summary_location(tmp_path):
    display, terminal = display_fixture(tmp_path)
    display.write('Output belongs on the left.\n')
    assert display.divider_column == round((terminal.size.columns - 2) * .75) + 1
    lines = terminal.visible().splitlines()
    assert lines[0].split('│')[0].strip() == 'Tasks: 1/3'
    assert 'Task 001:' not in lines[0]
    assert lines[display.top_height + 1].split('│')[0].strip() == 'Output belongs on the left.'
    assert 'Task 001:' in lines[display.top_height + 1].split('│')[1]
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


def test_total_duration_survives_observers_and_tasks_but_resets_for_new_backend(tmp_path, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr('launcher_display.time.monotonic', lambda: clock[0])
    run = tmp_path / 'first'
    run.mkdir()
    launcher.atomic(tmp_path / 'current.json', launcher.owner_record(run))
    display, terminal = display_fixture(run, width=240)
    assert 'Total Duration: 0m' in terminal.visible()
    lines = terminal.visible().splitlines()
    assert 'Total Tasks:' in lines[0].split('│')[1]
    assert 'Total Duration:' in lines[1].split('│')[1]
    unchanged = terminal.getvalue()
    clock[0] += 59
    display.draw()
    assert terminal.getvalue() == unchanged
    clock[0] += 1
    display.draw()
    assert 'Total Duration: 1m' in terminal.visible()
    display.update([{'key': '2', 'lines': ['Task 002: Next', 'Session [1]: Writing code']}], [])
    assert 'Total Duration: 1m' in terminal.visible()
    for elapsed, duration in ((12 * 60, '12m'), (3599, '59m'), (3600, '1h 0m'), (4330, '1h 12m')):
        clock[0] = 1000 + elapsed
        display.draw()
        assert 'Total Duration: ' + duration in terminal.visible()
    reconnected, screen = display_fixture(run, width=240)
    assert 'Total Duration: 1h 12m' in screen.visible()
    clock[0] += 60
    reconnected.draw()
    assert 'Total Duration: 1h 13m' in screen.visible()
    # A new owner publishes a fresh run and clock; reconnecting never does.
    next_run = tmp_path / 'second'
    next_run.mkdir()
    launcher.atomic(tmp_path / 'current.json', launcher.owner_record(next_run))
    restarted, screen = display_fixture(next_run, width=240)
    assert 'Total Duration: 0m' in screen.visible()
    clock[0] += 60
    restarted.draw()
    assert 'Total Duration: 1m' in screen.visible()


@pytest.mark.parametrize('input_mode', ['chat', 'question', 'none'])
def test_top_and_bottom_dividers_stay_aligned_during_drag_and_resize(tmp_path, input_mode):
    display, terminal = display_fixture(tmp_path, input_mode=input_mode)

    def assert_aligned():
        assert display.top_divider_column == display.divider_column
        if terminal.size.columns >= 4:
            lines = terminal.visible().splitlines()
            assert all(line[display.divider_column - 1] == '│'
                       for index, line in enumerate(lines) if index != display.top_height)

    assert_aligned()
    display.mouse(0, display.top_divider_column, 1, False)
    display.mouse(32, 61, 1, False)
    assert display.ratio == 60 / 118
    assert_aligned()
    display.mouse(0, 61, 1, True)
    assert_aligned()
    # Drag the lower divider across the horizontal boundary.
    display.mouse(0, display.divider_column, display.top_height + 2, False)
    display.mouse(32, 80, 1, False)
    assert display.ratio == 79 / 118
    assert_aligned()
    display.mouse(0, 80, 1, True)
    assert_aligned()
    for width, height in ((160, 40), (40, 20), (2, 2), (120, 36)):
        terminal.resize(width, height)
        display.draw()
        assert display.ratio == 79 / 118
        assert_aligned()
    display.close()


@pytest.mark.parametrize('draft', ['', 'abc', 'first\nsecond', '界x'])
def test_chat_underline_cursor_tracks_insertion_while_output_scrolls(tmp_path, draft):
    display, terminal = display_fixture(tmp_path)
    display.handle_input(draft.encode())
    if draft:
        display.handle_input(b'\x1b[D')
    # Enough output to create a scrollbar, whose offset must never affect
    # the independent composer caret position.
    display.write(''.join(f'output {index}\n' for index in range(100)))
    expected_row = display.chat_top + draft.count('\n')
    expected_column = 2 + (len(draft.rsplit('\n', 1)[-1]) - 1 if draft else 0)
    if draft == '界x':
        expected_column = 4  # The wide character occupies two terminal cells.
    for _ in range(2):
        assert terminal.cursor_visible
        assert (terminal.row, terminal.column) == (expected_row, expected_column)
        assert terminal.getvalue().endswith('\033[3 q\033[?25h')
        display.mouse(0, 2, display.top_height + 2, False)
        display.mouse(64, 2, display.top_height + 2, False)
    assert display.focus == 'bottom'


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


@pytest.mark.parametrize('width,height', [(120, 36), (200, 40), (40, 20), (120, 7), (120, 5)])
def test_composer_keeps_complete_bottom_border_when_draft_and_terminal_resize(conversation, tmp_path, width, height):
    display, terminal = display_fixture(tmp_path)
    display.refresh_chat()
    terminal.resize(width, height)
    for draft in ('', 'first\nsecond\nthird', '\n'.join(['long draft'] * 80), ''):
        display.editor.text = draft
        display.editor.cursor = len(draft)
        display.draw()
        left = [line[:display.divider_column - 1] for line in terminal.visible().splitlines()]
        border_index = next((index for index, line in enumerate(left) if line.startswith('╰')), None)
        assert border_index is not None, terminal.visible()
        border = left[border_index]
        assert border.endswith('╯')
        assert border[1:-1] and set(border[1:-1]) == {'─'}
        assert len(border) == len(left[border_index - 1])
        assert left[border_index - 1].startswith('│ ')
        assert left[border_index - 1].endswith(' │')
        if height > 5:
            assert left[border_index + 1].startswith('gpt-6.1-sol high')
            assert display.previous[border_index + 1].get_style_at_offset(display.console, 0).dim


def test_chat_ctrl_c_does_not_signal_output_and_uses_mailbox(tmp_path):
    display, _ = display_fixture(tmp_path)
    launcher.atomic(tmp_path / 'chat-state.json', display.chat_state)
    display.focus = 'bottom'
    display.handle_input(b'\x03')
    assert not (tmp_path / 'cancel').exists()
    assert json.loads((tmp_path / 'chat-inbox.json').read_text())[0]['kind'] == 'interrupt'


@pytest.mark.parametrize('width,height', [(40, 20), (120, 36)])
def test_clicking_composer_after_scrolling_to_bottom_keeps_turn_running(conversation, tmp_path, width, height):
    session, _, _ = conversation
    ready(session)
    display, terminal = display_fixture(tmp_path, width=width, height=height)
    display.handle_input(b'keep this draft')
    display.write(''.join(f'output {index}\n' for index in range(100)))
    display.handle_input(b'\x1b[5~')
    assert display.offsets['bottom'] > 0
    column, row = display.bottom_button
    display.handle_input(f'\033[<0;{column};{row}M\033[<0;{column};{row}m'.encode())
    assert display.offsets['bottom'] == 0

    # The whole composer, including its border, must be safe to click for focus.
    for row in range(display.chat_top, height + 1):
        for column in range(1, display.divider_column):
            display.handle_input(f'\033[<0;{column};{row}M\033[<0;{column};{row}m'.encode())
    session.poll()
    assert packets(session) == []
    assert read_state(tmp_path)['status'] == 'running'
    assert '[Cancel]' not in terminal.visible()
    assert display.editor.text == 'keep this draft'
    assert not (tmp_path / 'cancel').exists()
    display.handle_input(b'\r')
    session.poll()
    steer, = packets(session)
    assert steer['method'] == 'turn/steer'
    assert steer['params']['input'][0]['text'] == 'keep this draft'


def test_escape_interrupts_turn_and_preserves_session_and_draft(conversation, tmp_path, monkeypatch):
    session, _, cleanups = conversation
    ready(session)
    display, _ = display_fixture(tmp_path)
    clock = [0.0]
    monkeypatch.setattr('launcher_display.time.monotonic', lambda: clock[0])
    display.handle_input(b'keep this draft\x1b')
    display.poll_input()
    assert packets(session) == []
    clock[0] = .2
    display.poll_input()
    session.poll()
    interrupt, = packets(session)
    assert interrupt['method'] == 'turn/interrupt'
    respond(session, interrupt, {})
    notify(session, 'turn/completed', turn={'id': 'turn', 'status': 'interrupted'})
    session.poll()
    assert cleanups == [True]
    assert read_state(tmp_path)['status'] == 'waiting'
    display.handle_input(b'\x1b')
    clock[0] = .4
    display.poll_input()
    assert not (tmp_path / 'cancel').exists()
    assert display.editor.text == 'keep this draft'
    display.handle_input(b'\r')
    session.poll()
    continuation, = packets(session)
    assert continuation['method'] == 'turn/start'
    assert continuation['params']['threadId'] == 'thread'
    assert continuation['params']['input'][0]['text'] == 'keep this draft'


@pytest.mark.parametrize('status', ['interrupting', 'cleaning', 'waiting', 'blocked', 'finished'])
def test_escape_never_exits_idle_or_interrupted_launcher(tmp_path, monkeypatch, status):
    display, _ = display_fixture(tmp_path)
    launcher.atomic(tmp_path / 'chat-state.json', dict(display.chat_state, status=status))
    clock = [0.0]
    monkeypatch.setattr('launcher_display.time.monotonic', lambda: clock[0])
    display.handle_input(b'\x1b')
    clock[0] = .2
    display.poll_input()
    assert not (tmp_path / 'cancel').exists()
    assert not (tmp_path / 'chat-inbox.json').exists()


def test_escape_prefixes_and_paste_do_not_interrupt(tmp_path, monkeypatch):
    display, _ = display_fixture(tmp_path)
    launcher.atomic(tmp_path / 'chat-state.json', display.chat_state)
    clock = [0.0]
    monkeypatch.setattr('launcher_display.time.monotonic', lambda: clock[0])
    display.handle_input(b'ab\x1b')
    clock[0] = .05
    display.handle_input(b'[D!\x1b')
    display.handle_input(b'\rnext\x1b')
    display.handle_input(b'[200~pasted\x1b')
    clock[0] = 1.0
    display.poll_input()
    display.handle_input(b'\x03\rtext\x1b[201~')
    display.poll_input()
    assert display.editor.text == 'a!\nnextpasted\ntextb'
    assert not (tmp_path / 'chat-inbox.json').exists()
    assert not (tmp_path / 'cancel').exists()


def test_output_scrolling_returns_to_latest_without_losing_draft(tmp_path):
    display, terminal = display_fixture(tmp_path)
    display.write(''.join(f'output {index}\n' for index in range(100)))
    display.handle_input(b'keep this draft')
    chat_top = display.chat_top
    composer = terminal.visible().splitlines()[chat_top - 1:]
    display.handle_input(b'\x1b[5~')
    assert display.offsets['bottom'] > 0
    assert display.editor.text == 'keep this draft'
    assert display.chat_top == chat_top
    assert terminal.visible().splitlines()[chat_top - 1:] == composer
    display.write('new session output\n')
    assert terminal.visible().splitlines()[chat_top - 1:] == composer
    offset = display.offsets['bottom']
    display.mouse(64, 3, chat_top + 1, False)
    assert display.offsets['bottom'] == offset
    column, row = display.bottom_button
    assert row < chat_top
    display.mouse(0, column, row, False)
    assert display.offsets['bottom'] == 0
    assert 'output 99' in terminal.visible()
    assert display.editor.text == 'keep this draft'
    assert terminal.visible().splitlines()[chat_top - 1:] == composer


@pytest.mark.parametrize('input_mode', ['chat', 'question', 'none'])
def test_descriptive_pane_scrolls_independently_and_reconnects(tmp_path, input_mode):
    display, terminal = display_fixture(tmp_path, width=240, input_mode=input_mode)
    launcher.atomic(tmp_path / 'controller.json', display.steps)
    launcher.atomic(tmp_path / 'chat-state.json', display.chat_state)
    launcher.atomic(tmp_path / 'task-info.json', display.task_info)
    append = launcher.descriptive_output(tmp_path)
    renderer = AgentRenderer(io.StringIO(), on_description=append)
    for index in range(80):
        renderer.event({'type': 'item.completed', 'item': {'type': 'agent_message',
            'text': f'The child countdown remains responsive. Update {index}.'}})
    display.write('Full output includes commands and agent messages.\n')
    display.refresh_chat()
    display.draw()
    assert 'Update 79.' in terminal.visible()
    status = next(i for i, row in enumerate(display.previous)
                  if row.plain[display.divider_column:].startswith('Status:'))
    assert set(display.previous[status + 1].plain[display.divider_column:]) == {'─'}
    before = terminal.visible().splitlines()
    first, start, thumb, travel, limit = display.description_scrollbar
    column = terminal.size.columns - 1
    assert before[first + start - 1][column - 1] == '█'
    display.mouse(64, column - 2, first, False)
    assert display.offsets['description'] == 3 and display.offsets['bottom'] == 0
    assert [row[:display.divider_column] for row in terminal.visible().splitlines()] == [
        row[:display.divider_column] for row in before]
    assert terminal.visible().splitlines()[:first - 1] == before[:first - 1]
    # New prose preserves a reader's position while the left transcript follows.
    scrolled = [row[display.divider_column:-1] for row in terminal.visible().splitlines()[first - 1:]]
    append('\n• Another natural-language update.\n')
    display.refresh_chat()
    display.draw()
    assert [row[display.divider_column:-1] for row in terminal.visible().splitlines()[first - 1:]] == scrolled
    first, start, thumb, travel, limit = display.description_scrollbar
    display.mouse(0, column, first + start, False)
    assert display.description_grab == 0
    display.mouse(32, 2, 1, False)
    assert display.offsets['description'] == limit
    assert 'Update 0.' in terminal.visible()
    display.mouse(0, 2, 1, True)
    display.mouse(0, column, first + display.description_height - 1, False)
    assert display.offsets['description'] == 0
    display.mouse(0, column - 2, first, False)
    display.handle_input(b'\x1b[5~')
    assert display.offsets['description'] > 0 and display.offsets['bottom'] == 0
    display.handle_input(b'\x1b[6~')
    assert display.offsets['description'] == 0
    display.handle_input(b'\x1bOQ')
    assert display.description_scrollbar is None and display.description_grab is None
    display.handle_input(b'\x1bOQ')
    assert display.description_scrollbar
    terminal.resize(100, 24)
    display.draw()
    assert display.description_scrollbar and '─' in terminal.visible()
    reconnected, other = display_fixture(tmp_path, width=240, input_mode=input_mode)
    reconnected.refresh_chat()
    reconnected.draw()
    assert 'Another natural-language update.' in other.visible()
    # Progress for another task must not display the previous session's prose.
    reconnected.update([{'key': 'next', 'lines': ['Task 002: Next']}], [])
    assert 'Update 79.' not in other.visible()
    assert 'Another natural-language update.' not in other.visible()
    display.offsets['description'] = 4
    launcher.descriptive_output(tmp_path)
    display.refresh_chat()
    display.draw()
    assert display.offsets['description'] == 0 and not display.description_scrollbar
    assert 'Update 79.' not in terminal.visible()
    assert not terminal.scrollback


@pytest.mark.parametrize('input_mode', ['chat', 'question', 'none'])
def test_task_scrollbar_drag_track_and_bottom_button_preserve_fixed_panes(tmp_path, input_mode):
    display, terminal = display_fixture(tmp_path, input_mode=input_mode)
    display.write(''.join(f'output {index}\n' for index in range(1000)))
    if input_mode == 'chat':
        display.handle_input(b'keep my draft')
    display.offsets['bottom'] = 400
    display.draw()
    before = terminal.visible().splitlines()
    first, start, thumb, travel, limit = display.scrollbar
    column = display.divider_column - 1
    assert before[first - 1 + start][column - 1] == '█'
    assert display.bottom_button == (column, first + display.output_height - 1)
    display.handle_input(f'\033[<0;{column};{first + start}M'.encode())
    assert display.scrollbar_grab == 0
    assert display.offsets['bottom'] == 400
    # Continue a thumb drag even after the pointer leaves its column/track.
    display.handle_input(b'\033[<32;2;1M')
    assert display.offsets['bottom'] == limit
    after = terminal.visible().splitlines()
    assert 'output 0' in terminal.visible()
    assert before[:display.top_height + 1] == after[:display.top_height + 1]
    assert [row[display.divider_column:] for row in before] == [
        row[display.divider_column:] for row in after]
    if input_mode == 'chat':
        assert display.editor.text == 'keep my draft'
        assert before[display.chat_top - 1:] == after[display.chat_top - 1:]
    display.handle_input(b'\033[<0;2;1m')
    assert display.scrollbar_grab is None
    display.handle_input(f'\033[<32;{column};{first + travel}M'.encode())
    assert display.offsets['bottom'] == limit
    # Track clicks and the pinned bottom button are separate targets.
    display.handle_input(f'\033[<0;{column};{first + travel}M'.encode())
    assert display.offsets['bottom'] == 0
    display.handle_input(f'\033[<64;2;{first}M'.encode())
    assert display.offsets['bottom'] == 3
    column, row = display.bottom_button
    display.handle_input(f'\033[<0;{column};{row}M'.encode())
    assert display.offsets['bottom'] == 0
    assert not terminal.scrollback


def test_task_scrollbar_restores_native_selection_and_reflows_on_resize(tmp_path):
    display, terminal = display_fixture(tmp_path)
    display.write(''.join(f'output {index}\n' for index in range(100)))
    first, start, *_ = display.scrollbar
    column = display.divider_column - 1
    display.handle_input(f'\033[<0;{column};{first + start}M'.encode())
    assert display.scrollbar_grab == 0
    display.handle_input(b'\x1bOQ')
    assert not display.mouse_capture
    assert display.scrollbar_grab is None and display.scrollbar is None
    assert display.bottom_button is None
    display.handle_input(f'\033[<32;{column};{first}M'.encode())
    assert display.offsets['bottom'] == 0
    display.handle_input(b'\x1bOQ')
    assert display.mouse_capture and display.scrollbar
    terminal.resize(80, 20)
    display.draw()
    assert display.divider_column - 1 != column
    column, row = display.bottom_button
    assert row < display.chat_top <= terminal.size.lines
    assert terminal.visible().splitlines()[row - 1][column - 1] == '↓'
    assert not terminal.scrollback


def test_input_flags_restore_after_exception(tmp_path, monkeypatch):
    master, slave = os.openpty()
    try:
        with os.fdopen(os.dup(slave), 'w') as stream, os.fdopen(os.dup(slave), 'r') as source:
            original = termios.tcgetattr(slave)
            monkeypatch.setattr('sys.stdin', source)
            monkeypatch.setattr('os.tcgetpgrp', lambda _: os.getpgrp())
            monkeypatch.setenv('TERM', 'xterm')
            with pytest.raises(RuntimeError):
                with TaskDisplay(stream, run=tmp_path) as display:
                    assert not termios.tcgetattr(slave)[3] & termios.ISIG
                    sent = []
                    display.editor.send = sent.append
                    # Exercise the line discipline, not just the byte parser:
                    # normal terminals send CR for Enter and LF for Ctrl+J.
                    for data in (b'first\r', b'second\nline\r',
                                 b'third\x1b[13;2uline\r',
                                 b'fourth\x1b[27;2;13~line\r'):
                        os.write(master, data)
                        display.handle_input(os.read(slave, len(data)))
                    assert sent == ['first', 'second\nline', 'third\nline', 'fourth\nline']
                    raise RuntimeError('observer failed')
            assert termios.tcgetattr(slave) == original
            os.set_blocking(master, False)
            # A PTY read may return only one kernel packet even after flush.
            # Drain all available packets before asserting restored modes.
            output = b''
            while True:
                try:
                    packet = os.read(master, 65536)
                except BlockingIOError:
                    break
                if not packet:
                    break
                output += packet
            assert b'\x1b[>4;2m\x1b[>1u' in output
            assert b'\x1b[<u\x1b[>4;0m' in output
    finally:
        os.close(master)
        os.close(slave)


def test_installed_app_server_protocol_fields(tmp_path, conversation):
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
    session, _, _ = conversation
    initialize, = packets(session)
    respond(session, initialize, {})
    _, request = packets(session)
    # Check emitted values, not just field names: sandboxPolicy uses camelCase
    # variants, but thread/start's sandbox is a separate kebab-case enum.
    assert request['params']['sandbox'] in thread['definitions']['SandboxMode']['enum']
    turn = json.loads((destination / 'v2/TurnStartParams.json').read_text())
    assert {'outputSchema', 'threadId', 'input'} <= turn['properties'].keys()
    steer = json.loads((destination / 'v2/TurnSteerParams.json').read_text())
    assert {'expectedTurnId', 'threadId', 'input'} <= steer['properties'].keys()
