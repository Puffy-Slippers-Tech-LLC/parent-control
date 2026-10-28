"""Conversation protocol, result integrity and cancellation boundaries."""

import io
import json
from pathlib import Path

import pytest

import detached_launcher as launcher
from launcher_chat import AppSession, app_command, read_state, send_input, task_info
from launcher_render import AgentRenderer
from tests.support.write_e2e_fixtures import reply


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
    assert request['params']['ephemeral'] is False
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


@pytest.mark.parametrize('code', ['cyberPolicy', 'internalServerError', 'serverOverloaded', None])
def test_failed_turn_retains_provider_reason_without_acceptance_or_retry(conversation, code):
    session, _, _ = conversation
    ready(session)
    final(session)  # A partial final message cannot qualify a failed turn.
    error = {'message': 'Provider rejected the turn.', 'codexErrorInfo': code}
    with pytest.raises(ValueError, match='Provider rejected the turn') as failure:
        notify(session, 'turn/completed', turn={'id': 'turn', 'status': 'failed', 'error': error})
    retained = json.loads((session.run / 'agent-error.json').read_text())
    assert retained['message'] == str(failure.value)
    assert retained['codex_error_info'] == code and retained['context'] == 'turn failed'
    from launcher_runtime import AgentCapacityUnavailable
    assert isinstance(failure.value, AgentCapacityUnavailable) == (code == 'serverOverloaded')
    if code:
        assert code in retained['message']
    assert read_state(session.run)['status'] == 'finished'
    assert task_info(session.run, session.task)['last_error']
    assert not session.done and session.final is None and not session.completed
    assert not (session.run / 'agent-result.json').exists()
    assert packets(session) == []


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


def test_adviser_completion_cannot_finish_coordinator(conversation):
    session, _, _ = conversation
    ready(session)
    session.event({'method': 'turn/completed', 'params': {
        'threadId': 'adviser', 'turn': {'id': 'adviser-turn', 'status': 'completed'}}})
    assert session.turn == 'turn' and not session.done


def test_app_transport_preserves_policy_and_model_config():
    command = ['/opt/codex', '--ask-for-approval', 'never', 'exec',
               '-c', 'agents.max_depth=1', '-c', 'service_tier="default"',
               '--output-schema', '/schema', '-']
    actual = app_command(command)
    assert actual[:4] == ['/opt/codex', 'app-server', '--listen', 'stdio://']
    assert 'agents.max_depth=1' in actual and 'service_tier="default"' in actual
    assert 'approval_policy="never"' in actual and 'sandbox_mode="workspace-write"' in actual
    assert '--ephemeral' not in actual
