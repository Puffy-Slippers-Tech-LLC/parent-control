"""Private Codex/test-owner doubles; never contacts a model or VM."""

import json
import os
import re
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import detached_launcher as launcher
from test_storage import directory


def nested(root, owner, run):
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    (root / 'nested-ready').touch()
    while not (run / 'cancel').exists() and not (root / 'release-nested').exists():
        time.sleep(.02)
    # Make cancellation tests observe the lifetime of guarded cleanup.
    (root / 'cleanup-started').touch()
    time.sleep(.3)
    (root / 'nested-cleaned').touch()
    os.close(owner)


def agent(root, *, prompt=None, thread_start=None, turn_start=None, emit=None):
    args = sys.argv[1:]
    calls = root / 'calls.jsonl'
    index = len(calls.read_text().splitlines()) if calls.exists() else 0
    step = json.loads((root / 'script.json').read_text())[index]
    with calls.open('a') as output:
        output.write(json.dumps({'args': args, 'prompt': sys.stdin.read() if prompt is None else prompt,
                                 'pid': os.getpid(), 'thread_start': thread_start,
                                 'turn_start': turn_start,
                                 'thread': os.environ.get('CODEX_THREAD_ID')}) + '\n')
    if emit:
        emit('item/completed', item={'id': 'working', 'type': 'agentMessage',
                                     'text': '**Working** on the task.'})
    else:
        print(json.dumps({'type': 'item.completed', 'item': {
            'type': 'agent_message', 'text': '**Working** on the task.'}}), flush=True)
    if step.get('nested'):
        import fcntl
        run = directory('sessions', root=root) / ('b' * 32)
        run.mkdir(mode=0o700)
        with launcher.lock(run / 'owner') as owner:
            fcntl.flock(owner, fcntl.LOCK_EX)
            with launcher.nested_operation(root, run):
                subprocess.Popen([sys.executable, '-B', __file__, '--nested', str(root),
                                  str(owner), str(run)], pass_fds=(owner,), start_new_session=True,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        while not (root / 'nested-ready').exists():
            time.sleep(.02)
    (root / f'agent-ready-{index + 1}').touch()
    if step.get('close_input'):
        os.close(0)
        (root / 'input-closed').touch()
        while not (root / 'release').exists():
            time.sleep(.02)
        return 9
    if step.get('interactive'):
        for line in sys.stdin:
            request = json.loads(line)
            method = request['method']
            print(json.dumps({'id': request['id'], 'result':
                {'turnId': 'turn'} if method == 'turn/steer' else {}}), flush=True)
            if method == 'turn/steer':
                (root / 'steering.json').write_text(json.dumps(request['params']['input']))
            elif method == 'turn/interrupt':
                emit('turn/completed', turn={'id': 'turn', 'status': 'interrupted'})
                return 0
        return 9
    if step.get('wait'):
        while not (root / 'release').exists():
            time.sleep(.02)
    if step.get('crash'):
        return 9
    if step.get('stop'):
        # Exercise the launcher's public session-boundary stop, without a
        # separate total-session budget in the production worker.
        (Path(os.environ[launcher.WORKFLOW_DIRECTORY]) / 'stop').touch()
    for name, content in step.get('writes', {}).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    result = step['result']
    if step.get('close'):
        queue = root / 'docs/TestAutomation/E2E-Task-Queue.md'
        task = result['task_id']
        queue.write_text(queue.read_text().replace(f'| [ ] | {task} |', f'| [x] | {task} |'))
        plan = root / 'docs/TestAutomation/E2E-Execution-Plan.md'
        remaining = re.findall(r'^\| \[ \] \| ([^|]+) \|', queue.read_text(), re.MULTILINE)
        plan.write_text(f'Next task: **{remaining[0].strip()} — Next**.\n' if remaining else
                        'All active tasks complete.\n')
    if emit:
        usage = step.get('usage') or {}
        emit('thread/tokenUsage/updated', tokenUsage={'last': {
            'inputTokens': usage.get('input_tokens'), 'cachedInputTokens': usage.get('cached_input_tokens'),
            'outputTokens': usage.get('output_tokens'),
            'reasoningOutputTokens': usage.get('reasoning_output_tokens')}})
        emit('item/completed', item={'id': 'final', 'type': 'agentMessage',
                                     'text': 'bad result' if step.get('invalid') else json.dumps(result)})
        if step.get('invalid'):
            return 9
        emit('turn/completed', turn={'id': 'turn', 'status': 'completed'})
    else:
        destination = Path(args[args.index('--output-last-message') + 1])
        destination.write_text(json.dumps(result) if not step.get('invalid') else 'bad result')
        print(json.dumps({'type': 'item.completed', 'item': {
            'type': 'agent_message', 'text': json.dumps(result)}}), flush=True)
        print(json.dumps({'type': 'turn.completed', 'usage': step.get('usage')}), flush=True)
    return 0


def app_server(root):
    thread_start = None

    def emit(method, **params):
        print(json.dumps({'method': method, 'params': dict(threadId='thread', **params)}), flush=True)

    for line in sys.stdin:
        request = json.loads(line)
        method = request['method']
        if method == 'initialized':
            continue
        result = {'thread': {'id': 'thread'}} if method == 'thread/start' else (
            {'turn': {'id': 'turn'}} if method == 'turn/start' else {})
        print(json.dumps({'id': request['id'], 'result': result}), flush=True)
        if method == 'thread/start':
            thread_start = request['params']
        elif method == 'turn/start':
            emit('turn/started', turn={'id': 'turn'})
            status = agent(root, prompt=request['params']['input'][0]['text'],
                           thread_start=thread_start, turn_start=request['params'], emit=emit)
            if status:
                return status
    return 0


if __name__ == '__main__':
    if sys.argv[1] == '--nested':
        nested(Path(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4]))
    elif sys.argv[1] == 'app-server':
        sys.exit(app_server(Path.cwd()))
    else:
        sys.exit(agent(Path.cwd()))
