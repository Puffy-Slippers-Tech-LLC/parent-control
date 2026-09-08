"""Exercise serial fresh sessions against a local fake CLI, with no VM or API."""
import argparse
from datetime import datetime, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
import pty
import re
import select
import signal
import time

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('codex_slices', ROOT / 'tools/codex_slices.py')
loop = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(loop)

FAKE_CODEX = r'''#!/usr/bin/python3
import json
from pathlib import Path
import sys
import uuid

if '--help' in sys.argv:
    print('--approve-for-me --ephemeral --output-schema --json --output-last-message')
    raise SystemExit(0)
root = Path.cwd()
calls = root / 'calls.jsonl'
number = len(calls.read_text().splitlines()) if calls.exists() else 0
with calls.open('a') as stream:
    stream.write(json.dumps({'argv': sys.argv[1:], 'prompt': sys.stdin.read()}) + '\n')
step = json.loads((root / 'steps.json').read_text())[number]
def emit(value):
    print(json.dumps(value), flush=True)
emit({'type': 'thread.started', 'thread_id': str(uuid.uuid4())})
emit({'type': 'turn.started'})
if step.get('tools', True):
    emit({'type': 'item.started', 'item': {'id': 'cmd', 'type': 'command_execution', 'command': 'sensitive-placeholder'}})
    emit({'type': 'item.completed', 'item': {'id': 'cmd', 'type': 'command_execution',
          'command': 'sensitive-placeholder', 'aggregated_output': 'live-command-result\n',
          'status': 'completed', 'exit_code': 0}})
emit({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'sensitive-placeholder'}})
print('live-stderr-placeholder', file=sys.stderr, flush=True)
if step.get('await_gate'):
    import time
    deadline = time.monotonic() + 5
    while not (root / 'terminal-closed').exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    print('output-after-terminal-closure', file=sys.stderr, flush=True)
    emit({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'message-after-terminal-closure'}})
if step.get('failure'):
    emit({'type': 'turn.failed', 'error': {'message': step['failure']}})
    raise SystemExit(1)
handoff = root / 'docs/TestAutomation/Continuation.md'
if step.get('handoff', True):
    handoff.write_text(handoff.read_text() + f'\nNext observable result {number}.\n')
if step.get('settings'):
    handoff.write_text(handoff.read_text().replace('`model-one` / `high`', '`model-two` / `max`'))
backlog = root / 'docs/TestAutomation/Test-Automation.md'
if step.get('check_all'):
    backlog.write_text(backlog.read_text().replace('- [ ]', '- [x]'))
if step.get('delete_task'):
    backlog.write_text('\n'.join(line for line in backlog.read_text().splitlines() if 'Task 20 ' not in line))
if step.get('stop'):
    state = json.loads((root / 'output/codex-slices/state.json').read_text())
    (root / 'output/codex-slices/STOP').write_text(json.dumps({'request_id': state['request_id']}))
response = step.get('result', {'status': 'continue', 'cleanup_complete': True,
                             'made_progress': True, 'blocker': 'none'})
response.setdefault('summary', {
    'task': '19B — current qualification', 'completed': f'Completed slice result {number}.',
    'verification': 'Selected checks passed; owned operations exited and cleanup confirmed.',
    'next': 'Run the next required qualification.' if response['status'] != 'complete' else 'No tasks remain.',
    'remaining_sessions': '1–2' if response['status'] != 'complete' else '0',
    'remaining_minutes': '90–120' if response['status'] != 'complete' else '0',
    'estimate_basis': 'Measured qualification duration; correction contingency remains.',
})
if step.get('omit_summary'):
    response.pop('summary')
if not step.get('omit_result'):
    Path(sys.argv[sys.argv.index('--output-last-message') + 1]).write_text(json.dumps(response))
    emit({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(response)}})
if step.get('invalid_event'):
    print('sensitive-placeholder')
emit({'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': 5,
                                       'private': 'sensitive-placeholder'}})
'''


@pytest.fixture
def rig(tmp_path, monkeypatch):
    docs = tmp_path / 'docs/TestAutomation'
    docs.mkdir(parents=True)
    (tmp_path / loop.BACKLOG).write_text(
        '# Tasks\n\n## Unfinished tasks\n\n'
        '- [ ] [Task 19B — First](Task-19.md#task-19b)\n'
        '- [ ] [Task 20 — Second](Task-20.md)\n')
    (tmp_path / loop.HANDOFF).write_text('- Settings: **`model-one` / `high`**, reason.\n')
    (tmp_path / loop.PROMPT).write_bytes((ROOT / loop.PROMPT).read_bytes())
    (tmp_path / 'tools').mkdir()
    (tmp_path / 'tools/codex_slices.py').write_bytes((ROOT / 'tools/codex_slices.py').read_bytes())
    binary_dir = tmp_path / 'bin'
    binary_dir.mkdir()
    codex = binary_dir / 'codex'
    codex.write_text(FAKE_CODEX)
    codex.chmod(0o700)
    monkeypatch.setenv('PATH', str(binary_dir) + os.pathsep + os.environ.get('PATH', ''))

    def prepare(steps):
        (tmp_path / 'steps.json').write_text(json.dumps(steps))
        return tmp_path

    return prepare


def run(root, *, limit=0, retries=0):
    return loop.run(root, argparse.Namespace(max_slices=limit, max_api_retries=retries, reconciled=False))


def calls(root):
    path = root / 'calls.jsonl'
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def complete(**fields):
    return {'status': 'complete', 'cleanup_complete': True, 'made_progress': True, 'blocker': 'none', **fields}


def test_two_fresh_sessions_keep_pinned_settings_despite_handoff_changes(rig):
    root = rig([{'settings': True}, {'check_all': True, 'result': complete()}])
    assert run(root) == 0
    launched = calls(root)
    assert len(launched) == 2
    for call in launched:
        assert call['argv'][0] == 'exec'
        assert 'resume' not in call['argv'] and 'fork' not in call['argv']
        assert '--approve-for-me' in call['argv']
        assert '--ephemeral' in call['argv']
        assert '--ignore-rules' not in call['argv']
        assert 'sensitive-placeholder' not in call['prompt']
        assert call['argv'][call['argv'].index('--model') + 1] == 'gpt-6-astra'
        assert 'model_reasoning_effort="high"' in call['argv']
        assert 'model_reasoning_effort="max"' not in call['argv']
    storage = root / loop.STORAGE
    state = loop.read_state(storage)
    assert state['status'] == 'complete'
    assert state['sessions_started'] == 2
    assert state['last_session']['number'] == 2
    events = [path.read_text() for path in storage.glob('slice-*/events.jsonl')]
    assert len(events) == 2
    assert len({json.loads(event.splitlines()[0])['thread_id'] for event in events}) == 2
    assert all('sensitive-placeholder' not in event for event in events)
    assert all('"input_tokens": 10' in event for event in events)


@pytest.mark.parametrize('step, message', [
    ({'result': complete()}, 'tasks remain unfinished'),
    ({'check_all': True, 'handoff': False, 'result': complete()}, 'completion handoff'),
    ({'result': complete(cleanup_complete=False)}, 'cleanup'),
    ({'result': {'status': 'continue', 'cleanup_complete': True, 'made_progress': False, 'blocker': 'none'}}, 'no progress'),
    ({'handoff': False}, 'did not update'),
    ({'delete_task': True}, 'removed recorded'),
    ({'omit_result': True}, 'structured handoff'),
    ({'omit_summary': True}, 'structured handoff'),
    ({'result': complete(summary={})}, 'end-of-session summary'),
    ({'invalid_event': True}, 'clean completed turn'),
    ({'check_all': True}, 'completion handoff'),
    ({'failure': 'rate_limit exceeded'}, 'clean completed turn'),
])
def test_uncertain_result_never_starts_another_worker(rig, step, message):
    root = rig([step])
    with pytest.raises(loop.Error, match=message):
        run(root)
    assert len(calls(root)) == 1
    assert loop.read_state(root / loop.STORAGE)['status'] == 'needs-review'
    with pytest.raises(loop.Error, match='reconciliation'):
        run(root)
    assert len(calls(root)) == 1


def test_clean_blocker_stops_without_claiming_completion(rig):
    root = rig([{'result': {'status': 'blocked', 'cleanup_complete': True,
                           'made_progress': True, 'blocker': 'approval'}}])
    assert run(root) == 2
    assert loop.read_state(root / loop.STORAGE)['status'] == 'blocked'
    assert len(calls(root)) == 1


@pytest.mark.parametrize('stop', ['file', 'signal', 'limit'])
def test_stop_waits_for_clean_handoff_and_never_starts_next_slice(rig, stop, monkeypatch):
    root = rig([{'stop': stop == 'file'}])
    if stop == 'signal':
        original = loop.invoke

        def invoke_with_stop(*args, **kwargs):
            # Exercise the installed handler directly; never signal pytest or
            # any unrelated host process to simulate a stop request.
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
            return original(*args, **kwargs)

        monkeypatch.setattr(loop, 'invoke', invoke_with_stop)
    previous = signal.getsignal(signal.SIGTERM)
    assert run(root, limit=1 if stop == 'limit' else 0) == 0
    assert signal.getsignal(signal.SIGTERM) == previous
    state = loop.read_state(root / loop.STORAGE)
    assert state['status'] == 'stopped'
    assert 'Next observable result' in (root / loop.HANDOFF).read_text()
    assert len(calls(root)) == 1


def test_retry_only_transient_failed_turn_before_tools(rig, monkeypatch):
    root = rig([{'tools': False, 'failure': 'rate_limit exceeded'},
                {'check_all': True, 'result': complete()}])
    waits = []
    monkeypatch.setattr(loop, 'wait_retry', lambda delay, *_: waits.append(delay))
    assert run(root, retries=1) == 0
    assert len(calls(root)) == 2
    assert waits == [60]


def test_auth_failure_does_not_retry(rig):
    root = rig([{'tools': False, 'failure': 'unauthorized invalid api key'}])
    with pytest.raises(loop.Error, match='clean completed turn'):
        run(root, retries=1)
    assert len(calls(root)) == 1


def test_transient_failure_after_tools_does_not_retry(rig):
    root = rig([{'tools': True, 'failure': 'rate_limit exceeded'}])
    with pytest.raises(loop.Error, match='clean completed turn'):
        run(root, retries=1)
    assert len(calls(root)) == 1


def test_a_new_run_ignores_only_the_previous_runs_stop_request(rig):
    root = rig([{'stop': True}, {'check_all': True, 'result': complete()}])
    assert run(root) == 0
    assert loop.read_state(root / loop.STORAGE)['status'] == 'stopped'
    assert run(root) == 0
    assert loop.read_state(root / loop.STORAGE)['status'] == 'complete'
    assert len(calls(root)) == 2


def test_stop_during_detached_start_is_not_lost(rig):
    root = rig([])
    storage = root / loop.STORAGE
    loop.private_directory(storage)
    request_id = '718e11b8-1c72-471d-9222-fb2b37283ed4'
    loop.write_json(storage / 'state.json', {'status': 'launching', 'request_id': request_id})
    assert loop.main(['stop'], root=root) == 0
    args = argparse.Namespace(max_slices=0, max_api_retries=0, reconciled=False, request_id=request_id)
    assert loop.run(root, args) == 0
    assert loop.read_state(storage)['status'] == 'stopped'
    assert calls(root) == []


def test_detached_start_targets_this_checkout_and_preserves_records(rig):
    root = rig([{'check_all': True, 'result': complete()}])
    assert loop.main(['start'], root=root) == 0
    state = loop.read_state(root / loop.STORAGE)
    assert state['status'] == 'complete'
    assert len(calls(root)) == 1
    assert 'All documented tasks are complete.' in (root / loop.STORAGE / 'launcher.log').read_text()
    for path in (root / loop.STORAGE).rglob('*'):
        if path.is_file():
            assert 'sensitive-placeholder' not in path.read_text()
            assert 'live-command-result' not in path.read_text()
            assert 'live-stderr-placeholder' not in path.read_text()


def test_existing_lock_prevents_overlapping_worker(rig):
    root = rig([])
    storage = root / loop.STORAGE
    loop.private_directory(storage)
    with loop.exclusive(storage):
        with pytest.raises(loop.Error, match='checkout lock'):
            run(root)
    assert calls(root) == []


def test_state_write_failure_awaits_the_exact_spawned_cli(rig, monkeypatch):
    root = rig([{}])
    original_write = loop.write_json
    original_popen = loop.subprocess.Popen
    spawned = []
    failed = False

    def popen(*args, **kwargs):
        process = original_popen(*args, **kwargs)
        spawned.append(process)
        return process

    def write(path, value):
        nonlocal failed
        if not failed and path.name == 'state.json' and value.get('cli_pid'):
            failed = True
            raise OSError(28, 'sensitive-placeholder')
        original_write(path, value)

    monkeypatch.setattr(loop.subprocess, 'Popen', popen)
    monkeypatch.setattr(loop, 'write_json', write)
    with pytest.raises(loop.Error, match='errno 28') as error:
        run(root)
    assert 'sensitive-placeholder' not in str(error.value)
    assert len(calls(root)) == 1
    assert all(process.returncode is not None for process in spawned)
    assert loop.read_state(root / loop.STORAGE)['status'] == 'needs-review'


def test_complete_checklist_needs_no_model_run(rig):
    root = rig([])
    path = root / loop.BACKLOG
    path.write_text(path.read_text().replace('- [ ]', '- [x]'))
    assert run(root) == 0
    assert calls(root) == []


@pytest.mark.parametrize('text', [
    '## Unfinished tasks\nNo tasks.\n',
    '## Unfinished tasks\n- [ ] invalid\n',
    '## Unfinished tasks\n- [x] [Task 20 — A](a.md)\n- [x] [Task 20 — B](b.md)\n',
    '## Something else\n- [x] [Task 20 — A](a.md)\n',
])
def test_missing_empty_malformed_or_duplicate_checklist_cannot_mean_done(rig, text):
    root = rig([])
    (root / loop.BACKLOG).write_text(text)
    with pytest.raises(loop.Error):
        run(root)
    assert calls(root) == []


def test_current_project_checklist_is_readable():
    assert loop.checklist(ROOT)


def test_status_does_not_create_state(rig, capsys):
    root = rig([])
    assert loop.main(['status'], root=root) == 0
    assert json.loads(capsys.readouterr().out) == {'status': 'not-started'}
    assert not (root / loop.STORAGE).exists()


def test_summaries_append_without_reading_history_across_restarts(rig, monkeypatch):
    root = rig([{'stop': True}, {'check_all': True, 'result': complete()}])
    summary = root / loop.SUMMARY
    # Even undecodable old bytes must be preserved without being loaded.
    old = b'# Prior log\nprevious-context-must-not-be-loaded\xff'
    summary.write_bytes(old)
    inode = summary.stat().st_ino
    original_open = loop.os.open
    original_path_open = Path.open
    appends = []

    def checked_open(path, flags, *args, **kwargs):
        if Path(path) == summary:
            assert flags & os.O_ACCMODE == os.O_WRONLY
            assert flags & os.O_APPEND
            assert not flags & os.O_TRUNC
            appends.append(path)
        return original_open(path, flags, *args, **kwargs)

    def checked_path_open(path, *args, **kwargs):
        if path == summary:
            pytest.fail('the supervisor tried to read or rewrite the summary history')
        return original_path_open(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(loop.os, 'open', checked_open)
        patch.setattr(Path, 'open', checked_path_open)
        assert run(root) == 0
        assert run(root) == 0
    assert len(appends) == 2
    assert summary.stat().st_ino == inode
    saved = summary.read_bytes()
    assert saved.startswith(old)
    new = saved[len(old):].decode()
    assert new.count('## Session ') == 2
    assert new.index('## Session 1') < new.index('## Session 2')
    assert 'Completed slice result 0.' in new and 'Completed slice result 1.' in new
    assert 'Estimated sessions remaining for this task: 1–2' in new
    assert 'Estimated minutes remaining for this task: 90–120' in new
    assert 'Next session: Run the next required qualification.' in new
    assert 'Measured qualification duration' in new
    assert 'sensitive-placeholder' not in new
    for call in calls(root):
        assert 'previous-context-must-not-be-loaded' not in call['prompt']
        assert 'Completed slice result' not in call['prompt']
        assert 'Never read, search, diff, edit or include docs/Test-Automation-Slice-Summary.md' in call['prompt']


def test_completion_timestamp_and_elapsed_duration_are_measured_in_minutes(rig, monkeypatch):
    root = rig([{'check_all': True, 'result': complete()}])
    ticks = [100.0]
    original = loop.invoke

    class Clock:
        @staticmethod
        def now(_tz=None):
            return datetime(2026, 9, 8, 18, 42, 59, tzinfo=timezone.utc)

    def timed_invoke(*args, **kwargs):
        value = original(*args, **kwargs)
        ticks[0] += 125.0
        return value

    monkeypatch.setattr(loop, 'datetime', Clock)
    monkeypatch.setattr(loop.time, 'monotonic', lambda: ticks[0])
    monkeypatch.setattr(loop, 'invoke', timed_invoke)
    assert run(root) == 0
    saved = (root / loop.SUMMARY).read_text()
    local_completion = datetime(2026, 9, 8, 18, 42, 59, tzinfo=timezone.utc).astimezone()
    assert f"Completion: {local_completion.strftime('%Y-%m-%d %H:%M %Z')}" in saved
    assert 'Duration: 3 minutes (rounded up)' in saved
    assert '18:42:59' not in saved
    assert loop.read_state(root / loop.STORAGE)['last_session']['duration_minutes'] == 3


@pytest.mark.parametrize('step, outcome', [
    ({'result': {'status': 'blocked', 'cleanup_complete': True,
                'made_progress': True, 'blocker': 'environment'}}, 'blocked'),
    ({'failure': 'unauthorized'}, 'needs-review'),
    ({'result': complete(cleanup_complete=False)}, 'needs-review'),
    ({'omit_summary': True}, 'needs-review'),
])
def test_failed_and_blocked_sessions_have_exactly_one_honest_end_entry(rig, step, outcome):
    root = rig([step])
    if outcome == 'needs-review':
        with pytest.raises(loop.Error):
            run(root)
    else:
        assert run(root) == 2
    saved = (root / loop.SUMMARY).read_text()
    assert saved.count('## Session ') == 1
    assert f'Outcome: {outcome}' in saved
    if outcome == 'needs-review':
        assert 'unconfirmed' in saved
    assert re.search(r'Completion: \d{4}-\d\d-\d\d \d\d:\d\d \S+\n', saved)


def test_summary_append_failure_stops_before_next_session(rig, monkeypatch):
    root = rig([{}, {'check_all': True, 'result': complete()}])
    attempts = []

    def failed_append(*args):
        attempts.append(args)
        raise OSError(28, 'sensitive-placeholder')

    monkeypatch.setattr(loop, 'append_summary', failed_append)
    with pytest.raises(loop.Error, match='Could not append the slice summary') as error:
        run(root)
    assert 'sensitive-placeholder' not in str(error.value)
    assert len(attempts) == 1
    assert len(calls(root)) == 1
    assert loop.read_state(root / loop.STORAGE)['status'] == 'needs-review'


def test_summary_symlink_is_not_followed(rig):
    root = rig([{}])
    target = root / 'unrelated.md'
    target.write_text('preserve this unrelated file')
    (root / loop.SUMMARY).symlink_to(target)
    with pytest.raises(loop.Error, match='Could not append the slice summary'):
        run(root)
    assert target.read_text() == 'preserve this unrelated file'
    assert len(calls(root)) == 1


def test_foreground_displays_session_output_but_preserves_only_the_end_report(rig, capsys):
    root = rig([{'check_all': True, 'result': complete()}])
    assert run(root) == 0
    output = capsys.readouterr().out
    assert 'Codex:\nsensitive-placeholder' in output
    assert '$ sensitive-placeholder' in output
    assert 'live-command-result' in output
    assert 'live-stderr-placeholder' in output
    assert 'Completed slice result 0.' in output
    for path in [root / loop.SUMMARY, *(root / loop.STORAGE).rglob('*')]:
        if path.is_file():
            saved = path.read_text()
            assert 'sensitive-placeholder' not in saved
            assert 'live-command-result' not in saved
            assert 'live-stderr-placeholder' not in saved


def test_live_renderer_shows_incremental_messages_commands_and_tool_results():
    stream = io.StringIO()
    live = loop.LiveOutput(stream)
    for kind, text in [('item.started', 'Checking'), ('item.updated', 'Checking tests'),
                       ('item.completed', 'Checking tests now.')]:
        live.event({'type': kind, 'item': {'id': 'm', 'type': 'agent_message', 'text': text}})
    for kind, output in [('item.started', ''), ('item.updated', 'first\n'),
                         ('item.completed', 'first\nsecond\n')]:
        live.event({'type': kind, 'item': {'id': 'c', 'type': 'command_execution',
                   'command': 'tools/run-unit-tests tests/unit/test_codex_slices.py -q',
                   'aggregated_output': output, 'status': 'completed', 'exit_code': 0}})
    for item in [{'id': 'f', 'type': 'file_change', 'changes': [{'path': 'example.py', 'kind': 'update'}]},
                 {'id': 'p', 'type': 'todo_list', 'items': [{'text': 'Verify', 'completed': True}]},
                 {'id': 't', 'type': 'mcp_tool_call', 'result': {'content': 'tool result'}}]:
        live.event({'type': 'item.completed', 'item': item})
    text = stream.getvalue()
    assert 'Checking tests now.' in text
    assert text.count('first\n') == 1 and text.count('second\n') == 1
    assert text.count('$ tools/run-unit-tests') == 1
    assert 'example.py' in text and 'Verify' in text and 'tool result' in text
    assert not live.items


@pytest.mark.parametrize('close_terminal', [False, True])
def test_detached_live_output_uses_terminal_and_survives_its_closure(rig, monkeypatch, close_terminal):
    root = rig([{'await_gate': True, 'check_all': True, 'result': complete()}])
    master, slave = pty.openpty()
    children = []
    popen = loop.subprocess.Popen

    def record_child(command, *args, **kwargs):
        process = popen(command, *args, **kwargs)
        if str(root / 'tools/codex_slices.py') in command:
            children.append(process)
        return process

    chunks = []

    def collect():
        if master is not None and select.select([master], [], [], 0.05)[0]:
            chunks.append(os.read(master, 65536).decode())

    try:
        with os.fdopen(slave, 'w', buffering=1) as terminal, monkeypatch.context() as patch:
            patch.setattr(loop.sys, 'stdout', terminal)
            patch.setattr(loop.subprocess, 'Popen', record_child)
            assert loop.main(['start'], root=root) == 0
            assert len(children) == 1
            deadline = time.monotonic() + 5
            while 'sensitive-placeholder' not in ''.join(chunks) and time.monotonic() < deadline:
                collect()
            assert 'sensitive-placeholder' in ''.join(chunks)
            if close_terminal:
                os.close(master)
                master = None
            (root / 'terminal-closed').touch()
            deadline = time.monotonic() + 10
            while children[0].poll() is None and time.monotonic() < deadline:
                if master is None:
                    time.sleep(0.01)
                else:
                    collect()
            assert children[0].wait(timeout=1) == 0
            if master is not None:
                collect()
        assert loop.read_state(root / loop.STORAGE)['status'] == 'complete'
        assert 'Completed slice result 0.' in (root / loop.SUMMARY).read_text()
        if not close_terminal:
            assert 'Completed slice result 0.' in ''.join(chunks)
        saved = (root / loop.STORAGE / 'launcher.log').read_text()
        assert 'sensitive-placeholder' not in saved
        assert 'live-stderr-placeholder' not in saved
        assert 'message-after-terminal-closure' not in saved
    finally:
        # Release and await only the explicitly spawned fake supervisor. No signals.
        (root / 'terminal-closed').touch()
        for child in children:
            child.wait(timeout=10)
        if master is not None:
            os.close(master)
