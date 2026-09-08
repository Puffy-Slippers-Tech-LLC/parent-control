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
import threading
import time

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('codex_slices', ROOT / 'tools/codex_slices.py')
loop = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(loop)


@pytest.mark.parametrize('detach', [False, True])
def test_start_monitors_owned_run_without_changing_it(tmp_path, monkeypatch, capsys, detach):
    storage = tmp_path / loop.STORAGE
    loop.private_directory(storage)
    loop.write_json(storage / 'state.json', {'status': 'running', 'request_id': 'unchanged'})
    before = (storage / 'state.json').read_bytes()
    ready = threading.Event()
    finish = threading.Event()
    errors = []

    def supervisor():
        try:
            with loop.exclusive(storage), loop.MonitorHub(storage, loop.LiveOutput(None)) as hub:
                ready.set()
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    with hub.lock:
                        connected = bool(hub.clients)
                    if connected:
                        break
                    time.sleep(0.01)
                assert connected
                hub.live.write('ongoing progress\n')
                if detach:
                    assert finish.wait(3)
                    assert (storage / 'state.json').read_bytes() == before
                    with pytest.raises(loop.Busy):
                        with loop.exclusive(storage):
                            pass
        except BaseException as exc:
            errors.append(exc)

    original = loop.LiveOutput.display

    def display(self, text, **kwargs):
        if detach and self.stream is not None and text == 'ongoing progress\n':
            raise KeyboardInterrupt
        return original(self, text, **kwargs)

    monkeypatch.setattr(loop.LiveOutput, 'display', display)
    monkeypatch.setattr(loop, 'preflight', lambda root: pytest.fail('monitor must not launch Codex'))
    thread = threading.Thread(target=supervisor)
    thread.start()
    try:
        assert ready.wait(3)
        assert loop.main(['start', '--max-slices', '9', '--reconciled'], root=tmp_path) == 0
        assert (storage / 'state.json').read_bytes() == before
        assert not (storage / 'STOP').exists()
        assert not (storage / 'KILL').exists()
    finally:
        finish.set()
        thread.join(4)
    assert not thread.is_alive()
    assert not errors
    output = capsys.readouterr().out
    assert 'Monitoring ongoing session' in output
    assert ('Monitor detached' if detach else 'ongoing progress') in output
    assert sorted(path.name for path in storage.iterdir()) == ['lock', 'state.json']


def test_old_running_launcher_is_left_unchanged(tmp_path, monkeypatch, capsys):
    storage = tmp_path / loop.STORAGE
    loop.private_directory(storage)
    monkeypatch.setattr(loop.time, 'sleep', lambda _: None)
    with loop.exclusive(storage):
        assert loop.main(['start'], root=tmp_path) == 2
    assert 'no monitor endpoint' in capsys.readouterr().err
    assert not (storage / 'state.json').exists()


def test_monitor_fanout_reconnect_and_bounded_buffer(tmp_path):
    storage = tmp_path / loop.STORAGE
    live = loop.LiveOutput(None)

    def wait_clients(hub, count):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            with hub.lock:
                if len(hub.clients) == count:
                    return
            time.sleep(0.01)
        pytest.fail('monitor connections did not settle')

    def connect():
        client = loop.socket.socket(loop.socket.AF_UNIX, loop.socket.SOCK_STREAM)
        client.settimeout(3)
        client.connect(loop.monitor_address(storage))
        return client

    with loop.MonitorHub(storage, live) as hub:
        with connect() as first, connect() as second:
            wait_clients(hub, 2)
            live.markdown('**shared progress**')
            for client in (first, second):
                with client.makefile('r') as stream:
                    block = json.loads(stream.readline())
                assert block['text'] == '**shared progress**'
                assert block['markdown'] is True
        wait_clients(hub, 0)
        live.write('unobserved output is discarded')
        with connect() as reconnected:
            wait_clients(hub, 1)
            live.write('next slice')
            with reconnected.makefile('r') as stream:
                assert json.loads(stream.readline())['text'] == 'next slice'
            # Saturation disconnects only the monitor, without retaining output.
            hub.publish({'text': 'x' * (8 * 1024 * 1024)})
            wait_clients(hub, 0)
            assert reconnected.recv(1) == b''
    assert live.monitor is None
    assert not storage.exists()

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
thread_id = sys.argv[sys.argv.index('resume') + 1] if 'resume' in sys.argv else str(uuid.uuid4())
emit({'type': 'thread.started', 'thread_id': thread_id})
emit({'type': 'turn.started'})
if step.get('signal_exit'):
    import signal
    signal.raise_signal(signal.SIGTERM)
if step.get('kill'):
    import signal
    import time
    if step.get('ignore_interrupt'):
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    storage = root / 'output/codex-slices'
    state = json.loads((storage / 'state.json').read_text())
    (storage / 'KILL').write_text(json.dumps({'request_id': state['request_id']}))
    time.sleep(10)
    raise SystemExit('kill did not interrupt the worker')
if step.get('tools', True):
    command = step.get('command', 'sensitive-placeholder')
    emit({'type': 'item.started', 'item': {'id': 'cmd', 'type': 'command_execution', 'command': command}})
    emit({'type': 'item.completed', 'item': {'id': 'cmd', 'type': 'command_execution',
          'command': command, 'aggregated_output': step.get('output', 'live-command-result\n'),
          'status': 'completed', 'exit_code': 0}})
emit({'type': 'item.completed', 'item': {'type': 'agent_message',
      'text': step.get('message', 'sensitive-placeholder')}})
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


@pytest.fixture
def start_and_wait(monkeypatch):
    children = []
    popen = loop.subprocess.Popen

    def record_child(command, *args, **kwargs):
        process = popen(command, *args, **kwargs)
        if 'run' in command:
            children.append(process)
        return process

    monkeypatch.setattr(loop.subprocess, 'Popen', record_child)

    def start(root, *options):
        assert loop.main(['start', *options], root=root) == 0
        assert children[-1].wait(timeout=10) == 0

    yield start
    for child in children:
        child.wait(timeout=10)


def test_two_fresh_sessions_keep_pinned_settings_despite_handoff_changes(rig):
    root = rig([{'settings': True}, {'check_all': True, 'result': complete()}])
    assert run(root) == 0
    launched = calls(root)
    assert len(launched) == 2
    for call in launched:
        assert call['argv'][0] == 'exec'
        assert 'resume' not in call['argv'] and 'fork' not in call['argv']
        assert '--approve-for-me' in call['argv']
        assert '--ephemeral' not in call['argv']
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


@pytest.mark.parametrize('ignore_interrupt', [False, True])
def test_kill_interrupts_and_start_reuses_exact_thread_then_returns_to_fresh_slices(rig, start_and_wait, ignore_interrupt):
    root = rig([{'kill': True, 'ignore_interrupt': ignore_interrupt}, {},
                {'check_all': True, 'result': complete()}])
    started = time.monotonic()
    assert run(root) == 0
    assert time.monotonic() - started < 8
    state = loop.read_state(root / loop.STORAGE)
    assert state['status'] == 'killed'
    thread = state['thread_id']
    assert state['last_session']['outcome'] == 'killed'
    assert len(calls(root)) == 1
    start_and_wait(root)
    launched = calls(root)
    assert len(launched) == 3
    assert launched[1]['argv'][-3:] == ['resume', thread, '-']
    assert 'reconcile' in launched[1]['prompt']
    assert 'resume' not in launched[2]['argv']
    assert loop.read_state(root / loop.STORAGE)['status'] == 'complete'


def test_kill_during_retry_wait_prevents_another_worker(rig, monkeypatch):
    root = rig([{'tools': False, 'failure': 'rate_limit exceeded'}])

    def wait(_delay, stopping, _event):
        assert loop.main(['kill'], root=root) == 0
        assert stopping()

    monkeypatch.setattr(loop, 'wait_retry', wait)
    assert run(root, retries=1) == 0
    assert loop.read_state(root / loop.STORAGE)['status'] == 'killed'
    assert len(calls(root)) == 1


def test_start_preflight_failure_preserves_killed_session(rig, monkeypatch):
    root = rig([])
    storage = root / loop.STORAGE
    loop.private_directory(storage)
    state = {'status': 'killed', 'resumable': True,
             'thread_id': '718e11b8-1c72-471d-9222-fb2b37283ed4'}
    loop.write_json(storage / 'state.json', state)
    monkeypatch.setattr(loop.shutil, 'which', lambda _: None)
    assert loop.main(['start'], root=root) == 2
    assert loop.read_state(storage) == state


@pytest.mark.parametrize('state', [{'status': 'killed', 'resumable': True},
                                 {'status': 'killed', 'thread_id': 'invalid', 'resumable': True},
                                 {'status': 'killed', 'thread_id': 'old-ephemeral'}])
def test_start_refuses_missing_or_unsaved_killed_thread(rig, state):
    root = rig([])
    storage = root / loop.STORAGE
    loop.private_directory(storage)
    loop.write_json(storage / 'state.json', state)
    assert loop.main(['start'], root=root) == 2
    assert calls(root) == []
    assert loop.read_state(storage) == state


@pytest.mark.parametrize('state, options', [
    ({}, []), ({'status': 'stopped'}, []), ({'status': 'complete'}, []),
    ({'status': 'killed', 'resumable': True,
      'thread_id': '718e11b8-1c72-471d-9222-fb2b37283ed4'}, ['--reconciled']),
])
def test_start_launches_fresh_when_no_resume_needed(rig, start_and_wait, state, options):
    root = rig([{'check_all': True, 'result': complete()}])
    storage = root / loop.STORAGE
    loop.private_directory(storage)
    loop.write_json(storage / 'state.json', state)
    start_and_wait(root, *options)
    assert len(calls(root)) == 1
    assert 'resume' not in calls(root)[0]['argv']
    assert loop.read_state(storage)['status'] == 'complete'


def test_separate_resume_command_is_removed(rig):
    root = rig([])
    with pytest.raises(SystemExit) as error:
        loop.main(['resume'], root=root)
    assert error.value.code == 2
    assert not (root / loop.STORAGE).exists()


def test_kill_command_targets_request_without_signaling_saved_pid(rig, monkeypatch):
    root = rig([])
    storage = root / loop.STORAGE
    loop.private_directory(storage)
    loop.write_json(storage / 'state.json', {'status': 'running', 'request_id': 'current',
                                            'resumable': True, 'cli_pid': 1})
    monkeypatch.setattr(os, 'kill', lambda *_: pytest.fail('signaled an unowned saved PID'))
    assert loop.main(['kill'], root=root) == 0
    assert loop.kill_requested(storage, 'current')
    assert not loop.kill_requested(storage, 'previous')


@pytest.mark.parametrize('exited', [False, True])
def test_interrupt_child_cleanup_safety_signals_only_live_owned_child(exited):
    class Child:
        def __init__(self):
            self.signals = []

        def poll(self):
            return 0 if exited else None

        def send_signal(self, sig):
            self.signals.append(sig)

        def kill(self):
            self.signals.append(signal.SIGKILL)

    class Finished:
        def __init__(self):
            self.waits = 0

        def wait(self, _timeout):
            self.waits += 1
            return self.waits > 2

    child = Child()
    killed = loop.threading.Event()
    loop.interrupt_child(child, lambda: True, Finished(), killed)
    assert child.signals == ([] if exited else [signal.SIGINT, signal.SIGKILL])
    assert killed.is_set() is not exited


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


class TerminalBuffer(io.StringIO):
    def isatty(self):
        return True


@pytest.mark.parametrize('held_pipes', [('stdout',), ('stderr',), ('stdout', 'stderr')])
@pytest.mark.parametrize('step, status, code', [
    ({'stop': True}, 'stopped', 0),
    ({'kill': True}, 'killed', 0),
    ({'kill': True, 'ignore_interrupt': True}, 'killed', 0),
    ({'signal_exit': True}, 'killed', 2),
])
def test_shutdown_exits_with_red_notice_even_when_pipes_remain_open(
        rig, monkeypatch, held_pipes, step, status, code):
    root = rig([step])
    monkeypatch.setenv('TERM', 'xterm-256color')
    monkeypatch.delenv('NO_COLOR', raising=False)
    terminal = TerminalBuffer()
    monkeypatch.setattr(loop.sys, 'stdout', terminal)
    popen = loop.subprocess.Popen
    writers = []
    children = []

    def launch(command, **kwargs):
        if '--help' in command:
            return popen(command, **kwargs)
        readers = {}
        for name in held_pipes:
            reader, writer = os.pipe()
            readers[name] = reader
            writers.append(writer)
            kwargs[name] = writer
        child = popen(command, **kwargs)
        children.append(child)
        for name, reader in readers.items():
            setattr(child, name, os.fdopen(reader, 'r', encoding='utf-8'))
        return child

    monkeypatch.setattr(loop.subprocess, 'Popen', launch)
    finished = loop.threading.Event()

    def close_writers():
        while writers:
            os.close(writers.pop())

    def release_on_timeout():
        # A regression must fail on elapsed time rather than hang the suite.
        if not finished.wait(8):
            close_writers()

    watchdog = loop.threading.Thread(target=release_on_timeout)
    watchdog.start()
    try:
        started = time.monotonic()
        assert run(root) == code
        assert time.monotonic() - started < 6
        assert all(child.poll() is not None for child in children)
        assert loop.read_state(root / loop.STORAGE)['status'] == status
        assert len(calls(root)) == 1
        output = terminal.getvalue()
        notice = '\x1b[1;31m' + output.rsplit('\x1b[1;31m', 1)[-1]
        assert f'Session {status}' in notice
        assert 'Launcher exiting' in notice
        assert '\x1b[1;31m' in notice and notice.endswith('\x1b[0m')
        terminal.write('shell still usable\n')
        assert terminal.getvalue().endswith('shell still usable\n')
    finally:
        finished.set()
        watchdog.join()
        close_writers()
        for child in children:
            child.wait(timeout=12)


@pytest.mark.parametrize('action', ['start', 'run'])
@pytest.mark.parametrize('step, status', [({'stop': True}, 'stopped'), ({'kill': True}, 'killed')])
def test_stopped_launcher_exits_without_closing_real_terminal(rig, monkeypatch, action, step, status):
    root = rig([step])
    monkeypatch.setenv('TERM', 'xterm-256color')
    monkeypatch.delenv('NO_COLOR', raising=False)
    master, slave = pty.openpty()
    children = []
    popen = loop.subprocess.Popen

    def record_child(command, *args, **kwargs):
        child = popen(command, *args, **kwargs)
        children.append(child)
        return child

    try:
        with os.fdopen(slave, 'w', buffering=1) as terminal:
            if action == 'start':
                with monkeypatch.context() as patch:
                    patch.setattr(loop.sys, 'stdout', terminal)
                    patch.setattr(loop.subprocess, 'Popen', record_child)
                    assert loop.main(['start'], root=root) == 0
            else:
                record_child([loop.sys.executable, '-I', '-B', str(root / 'tools/codex_slices.py'), 'run'],
                             stdin=loop.subprocess.DEVNULL, stdout=terminal, stderr=terminal,
                             start_new_session=True)
            for child in children:
                assert child.wait(timeout=8) == 0
            terminal.write('shell still usable\n')
            output = ''
            while select.select([master], [], [], 0.1)[0]:
                output += os.read(master, 65536).decode()
            assert f'Session {status}' in loop.LiveOutput.clean(output)
            assert '\x1b[1;31mSession' in output
            assert 'shell still usable' in output
            assert loop.read_state(root / loop.STORAGE)['status'] == status
            if action == 'start':
                log = (root / loop.STORAGE / 'launcher.log').read_text()
                assert f'Session {status}' in log and '\x1b[' not in log
    finally:
        for child in children:
            child.wait(timeout=12)
        os.close(master)


DOCUMENT_EXCERPT = (
    '<!-- Preserve incoming links from historical evidence records. -->\n'
    '<a id="continuation-handoff"></a>\n\n'
    '## Completion handoff\n\n'
    '**Completed this session:** built verified inputs and ran the checks.\n'
)


@pytest.mark.parametrize('command', [
    'cat docs/Continuation.md',
    '/usr/bin/cat -- "docs/Completion handoff.MD"',
    'head -n 20 docs/Continuation.md',
    'tail -20 docs/Continuation.markdown',
    "sed -n '1,20p' docs/Continuation.md",
    "sed -n '20,$p' -- docs/Continuation.md",
    'tools/read-only slice 1 20 docs/Continuation.md',
    '/bin/bash -lc "sed -n \'1,20p\' docs/Continuation.md"',
])
def test_terminal_renders_markdown_file_excerpt_once(monkeypatch, command):
    monkeypatch.setenv('TERM', 'xterm-256color')
    monkeypatch.delenv('NO_COLOR', raising=False)
    stream = TerminalBuffer()
    live = loop.LiveOutput(stream)
    for kind, output in [('item.started', ''),
                         ('item.updated', DOCUMENT_EXCERPT[:110]),
                         ('item.completed', DOCUMENT_EXCERPT)]:
        live.event({'type': kind, 'item': {
            'id': 'read', 'type': 'command_execution', 'command': command,
            'aggregated_output': output, 'exit_code': 0, 'status': 'completed'}})
        if kind != 'item.completed':
            assert live.clean(stream.getvalue()) == f'\n$ {command}\n'
    styled = stream.getvalue()
    assert '\x1b[' in styled
    output = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', styled)
    assert output.count('Completion handoff') == (2 if 'Completion handoff.MD' in command else 1)
    assert 'Completed this session:' in output
    assert '## Completion' not in output and '**Completed' not in output
    assert '<!--' not in output and '<a id=' not in output
    assert 'Command completed (exit 0).' in output
    assert not live.items


@pytest.mark.parametrize('command', [
    'cat docs/example.unknownextension', 'cat -n docs/example.md',
    "rg -n '##' docs/example.md", 'git diff -- docs/example.md',
    'cat docs/example.md docs/example.py', 'cat docs/example.md | head',
    'cat docs/example.md; cat docs/other.md',
    'cat docs/example.md && cat docs/other.md',
    'cat $(echo docs/example.md)', 'cat docs/*.md',
    "sed -n '1,20p;=' docs/example.md", 'cat "unterminated.md', None,
])
def test_other_command_output_stays_literal_and_streams(monkeypatch, command):
    monkeypatch.setenv('TERM', 'xterm-256color')
    stream = TerminalBuffer()
    live = loop.LiveOutput(stream)
    for kind, output in [('item.updated', '## literal\n'),
                         ('item.completed', '## literal\n**output**\n')]:
        live.event({'type': kind, 'item': {
            'id': 'command', 'type': 'command_execution', 'command': command,
            'aggregated_output': output, 'exit_code': 0}})
        assert output in stream.getvalue()
    assert stream.getvalue().count('## literal') == 1
    assert '## literal\n**output**\n' in stream.getvalue()


@pytest.mark.parametrize('fallback', ['redirected', 'dumb', 'missing', 'failed'])
def test_markdown_file_read_plain_fallback(monkeypatch, fallback):
    monkeypatch.setenv('TERM', 'dumb' if fallback == 'dumb' else 'xterm')
    if fallback == 'missing':
        monkeypatch.setattr(loop, 'Console', None)
    stream = io.StringIO() if fallback == 'redirected' else TerminalBuffer()
    live = loop.LiveOutput(stream)
    for kind in ('item.updated', 'item.completed'):
        live.event({'type': kind, 'item': {
            'id': 'read', 'type': 'command_execution', 'command': 'cat docs/example.md',
            'aggregated_output': DOCUMENT_EXCERPT, 'exit_code': 1 if fallback == 'failed' else 0}})
        if fallback != 'failed' or kind == 'item.completed':
            assert DOCUMENT_EXCERPT in stream.getvalue()
    assert stream.getvalue().count(DOCUMENT_EXCERPT) == 1
    if fallback != 'failed':
        assert '\x1b[' not in stream.getvalue()


@pytest.mark.parametrize('command,source', [
    ('/bin/bash -lc "sed -n \'350,372p\' tests/integration/system_caller.py"',
     '    return self\n\ndef drop_identity(uid, *, allow_root=False):\n'
     '    # Only an explicitly opted-in caller may retain UID 0.\n'
     '    os.setresuid(uid, uid, uid)\n'),
    ('tools/read-only slice 1 20 child/example.js', 'const enabled = true;\n'),
    ('cat config/example.json', '{"enabled": true}\n'),
    ('head -n 20 tools/example.sh', 'if true; then\n    echo "hello"\nfi\n'),
])
def test_terminal_highlights_source_excerpt_once(monkeypatch, command, source):
    monkeypatch.setenv('TERM', 'xterm-256color')
    monkeypatch.delenv('NO_COLOR', raising=False)
    stream = TerminalBuffer()
    live = loop.LiveOutput(stream)
    for kind, output in [('item.started', ''), ('item.updated', source[:12]),
                         ('item.completed', source)]:
        live.event({'type': kind, 'item': {
            'id': 'source', 'type': 'command_execution', 'command': command,
            'aggregated_output': output, 'exit_code': 0, 'status': 'completed'}})
        if kind != 'item.completed':
            assert live.clean(stream.getvalue()) == f'\n$ {command}\n'
    styled = stream.getvalue()
    excerpt = styled[styled.index(command) + len(command):]
    excerpt = excerpt[:excerpt.index('Command')]
    assert '\x1b[' in excerpt
    # Token colors must occur inside the source, not only in command labels.
    assert source not in styled
    plain = live.clean(styled)
    for line in source.splitlines():
        if line:
            assert plain.count(line) == 1
    assert 'Command completed (exit 0).' in plain
    assert not live.items


@pytest.mark.parametrize('fallback', ['redirected', 'dumb', 'missing', 'no_color', 'failed'])
def test_source_excerpt_fallback_and_sanitization(monkeypatch, fallback):
    monkeypatch.setenv('TERM', 'dumb' if fallback == 'dumb' else 'xterm-256color')
    if fallback == 'missing':
        monkeypatch.setattr(loop, 'Console', None)
    if fallback == 'no_color':
        monkeypatch.setenv('NO_COLOR', '1')
    stream = io.StringIO() if fallback == 'redirected' else TerminalBuffer()
    live = loop.LiveOutput(stream)
    source = 'def example():\n    return True\n'
    live.event({'type': 'item.completed', 'item': {
        'id': 'source', 'type': 'command_execution', 'command': 'cat example.py',
        'aggregated_output': '\x1b[2J\x1b]0;untrusted title\x07' + source,
        'exit_code': 1 if fallback == 'failed' else 0}})
    styled = stream.getvalue()
    assert '\x1b[2J' not in styled and 'untrusted title' not in styled
    assert source in live.clean(styled)
    if fallback in ('redirected', 'dumb', 'missing'):
        assert '\x1b[' not in styled
    if fallback == 'no_color':
        assert not re.search(r'\x1b\[(?:3[0-9]|9[0-7]|38;)', styled)


def test_terminal_renders_completed_markdown_once(monkeypatch):
    assert loop.Console is not None, 'Run ./setup.sh --dependencies-only for python3-rich'
    monkeypatch.setenv('TERM', 'xterm-256color')
    monkeypatch.setenv('NO_COLOR', '1')
    stream = TerminalBuffer()
    live = loop.LiveOutput(stream)
    message = ('## Readable heading\n\nA **bold phrase** and `inline code`.\n\n'
               '- List entry\n\n| Name | Status |\n| --- | --- |\n| Example | Done |\n\n'
               '```python\nprint("hello")\n```\n')
    for kind, text in [('item.started', '## Readable'),
                       ('item.updated', message), ('item.completed', message)]:
        live.event({'type': kind, 'item': {'id': 'm', 'type': 'agent_message', 'text': text}})
        if kind != 'item.completed':
            assert stream.getvalue() == ''
    output = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', stream.getvalue())
    assert output.count('Readable heading') == 1
    assert '## ' not in output and '**' not in output and '```' not in output
    for expected in ('bold phrase', 'inline code', 'List entry', 'Example', 'Done', 'print'):
        assert expected in output
    assert not live.items
    live.event({'type': 'item.completed', 'item': {
        'id': 'final', 'type': 'agent_message',
        'text': json.dumps(complete(summary={key: 'Done' for key in loop.SUMMARY_FIELDS}))}})
    assert 'cleanup_complete' not in stream.getvalue()


@pytest.mark.parametrize('fallback', ['redirected', 'dumb', 'missing'])
def test_markdown_plain_fallback(monkeypatch, fallback):
    monkeypatch.setenv('TERM', 'dumb' if fallback == 'dumb' else 'xterm')
    if fallback == 'missing':
        monkeypatch.setattr(loop, 'Console', None)
    stream = io.StringIO() if fallback == 'redirected' else TerminalBuffer()
    live = loop.LiveOutput(stream)
    live.markdown('## Heading\n\n**text**\n')
    assert stream.getvalue() == '## Heading\n\n**text**\n'


@pytest.mark.parametrize('file_excerpt', [False, True])
def test_terminal_markdown_tracks_output_descriptor_width(monkeypatch, file_excerpt):
    import termios

    monkeypatch.setenv('TERM', 'xterm')
    monkeypatch.setenv('COLUMNS', '80')
    master, slave = pty.openpty()
    try:
        stream = TerminalBuffer()
        monkeypatch.setattr(stream, 'fileno', lambda: slave)
        live = loop.LiveOutput(stream)
        for width in (120, 48, 160):
            termios.tcsetwinsize(slave, (24, width))
            stream.seek(0)
            stream.truncate()
            if file_excerpt:
                # Exercise the list excerpt shown by the launcher's sed reads,
                # including headings and list indentation at the actual width.
                excerpt = '\n'.join((ROOT / 'docs/Specification.md').read_text().splitlines()[35:42])
                live.event({'type': 'item.completed', 'item': {
                    'id': 'read', 'type': 'command_execution',
                    'command': '/bin/bash -lc "sed -n \'36,42p\' docs/Specification.md"',
                    'aggregated_output': excerpt, 'exit_code': 0, 'status': 'completed'}})
                output = live.clean(stream.getvalue())
                lines = output.split('\n', 2)[2].split('\nCommand completed', 1)[0].splitlines()
                assert 'Application access' in output
            else:
                live.markdown('# System design\n\n' + 'flowing text ' * 40)
                lines = live.clean(stream.getvalue()).splitlines()
                assert len(lines[0]) == width
                lines = lines[3:]
            assert all(len(line) <= width for line in lines)
            # Rich pads lines; only visible prose proves wrapping uses the width.
            assert max(len(line.rstrip()) for line in lines) > width - 15
    finally:
        os.close(slave)
        os.close(master)


def test_terminal_markdown_sanitizes_input_and_survives_closed_stream(monkeypatch):
    monkeypatch.setenv('TERM', 'xterm')
    stream = TerminalBuffer()
    live = loop.LiveOutput(stream)
    live.markdown('safe\x1b[2J\x1b]0;untrusted title\x07 text')
    assert '\x1b[2J' not in stream.getvalue()
    assert 'untrusted title' not in stream.getvalue()
    stream.close()
    live.markdown('## Terminal closed')
    assert live.stream is None
    live.markdown('## Still closed')


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
@pytest.mark.parametrize('source_file', [False, True])
def test_detached_live_output_uses_terminal_and_survives_its_closure(rig, monkeypatch, close_terminal, source_file):
    monkeypatch.setenv('TERM', 'xterm-256color')
    monkeypatch.setenv('TERM_PROGRAM', 'vscode')
    monkeypatch.setenv('COLORTERM', 'truecolor')
    monkeypatch.delenv('NO_COLOR', raising=False)
    root = rig([{'await_gate': True, 'check_all': True, 'result': complete(),
                 'command': ('/bin/bash -lc "sed -n \'350,372p\' tests/integration/system_caller.py"'
                             if source_file else "sed -n '1,20p' docs/Continuation.md"),
                 'output': ('def drop_identity(uid, *, allow_root=False):\n    return uid\n'
                            if source_file else DOCUMENT_EXCERPT),
                 'message': '## Rendered heading\n\nA **rendered phrase**.\n'}])
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
            while 'rendered phrase' not in ''.join(chunks) and time.monotonic() < deadline:
                collect()
            output = ''.join(chunks)
            assert 'rendered phrase' in output
            assert '\x1b[' in output
            assert '## Rendered heading' not in output
            assert '**rendered phrase**' not in output
            if source_file:
                assert 'def drop_identity' in loop.LiveOutput.clean(output)
                assert 'def drop_identity' not in output
            else:
                assert 'Completion handoff' in output
            assert '## Completion handoff' not in output
            assert '**Completed this session:**' not in output
            assert '<!--' not in output and '<a id=' not in output
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
            output = ''.join(chunks)
            assert 'Completed slice result 0.' in output
            assert '### ' not in output and '**' not in output
        saved = (root / loop.STORAGE / 'launcher.log').read_text()
        assert 'sensitive-placeholder' not in saved
        assert 'live-stderr-placeholder' not in saved
        assert 'message-after-terminal-closure' not in saved
        assert 'Rendered heading' not in saved
        assert 'Completion handoff' not in saved
        assert '\x1b[' not in saved
    finally:
        # Release and await only the explicitly spawned fake supervisor. No signals.
        (root / 'terminal-closed').touch()
        for child in children:
            child.wait(timeout=10)
        if master is not None:
            os.close(master)
