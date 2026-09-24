"""Private Codex/test-owner doubles; never contacts a model or VM."""

import json
import os
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


def agent(root):
    args = sys.argv[1:]
    calls = root / 'calls.jsonl'
    index = len(calls.read_text().splitlines()) if calls.exists() else 0
    step = json.loads((root / 'script.json').read_text())[index]
    with calls.open('a') as output:
        output.write(json.dumps({'args': args, 'prompt': sys.stdin.read(), 'pid': os.getpid(),
                                 'thread': os.environ.get('CODEX_THREAD_ID')}) + '\n')
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
    if step.get('wait'):
        while not (root / 'release').exists():
            time.sleep(.02)
    if step.get('crash'):
        return 9
    result = step['result']
    if step.get('close'):
        queue = root / 'docs/TestAutomation/E2E-Task-Queue.md'
        task = result['task_id']
        queue.write_text(queue.read_text().replace(f'| [ ] | {task} |', f'| [x] | {task} |'))
        plan = root / 'docs/TestAutomation/E2E-Execution-Plan.md'
        plan.write_text('Next task: **002 — [Second](second.md)**.\n')
    destination = Path(args[args.index('--output-last-message') + 1])
    destination.write_text(json.dumps(result) if not step.get('invalid') else 'bad result')
    print(json.dumps({'type': 'item.completed', 'item': {
        'type': 'agent_message', 'text': json.dumps(result)}}), flush=True)
    return 0


if __name__ == '__main__':
    if sys.argv[1] == '--nested':
        nested(Path(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4]))
    else:
        sys.exit(agent(Path.cwd()))
