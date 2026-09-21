"""Finite, harmless test/agent doubles for fix-tests process qualification."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main():
    root = Path.cwd()
    kind, *args = sys.argv[1:]
    if kind == 'test' and args == ['--list']:
        if (root / 'inventory.json').exists():
            print((root / 'inventory.json').read_text())
            return 0
        print(json.dumps({name: {'description': name, 'args': []}
                          for name in ('unit', 'ui', 'system', 'e2e')}))
        return 0
    mode = (root / 'mode').read_text()
    category = args[1] if kind == 'test' else 'agent'
    record = {'kind': kind, 'category': category, 'pid': os.getpid(), 'args': args}
    if kind == 'agent':
        record['prompt'] = sys.stdin.read()
        record['thread'] = os.environ.get('CODEX_THREAD_ID')
    with (root / 'calls').open('a') as stream:
        stream.write(json.dumps(record) + '\n')

    def interrupt(*_):
        (root / 'test-interrupted').touch()
        time.sleep(.15)
        (root / 'test-cleaned').touch()
        raise SystemExit(130)

    if kind == 'test':
        signal.signal(signal.SIGINT, interrupt)
        if mode == 'attach-once' and not (root / 'attached').exists():
            (root / 'attached').touch()
            print('Attached to run-tests session: previous', flush=True)
            return 0
        print('Started run-tests session: harmless', flush=True)
        if mode == 'test-wait':
            (root / 'test-ready').touch()
            deadline = time.monotonic() + 15
            while not (root / 'release').exists() and time.monotonic() < deadline:
                time.sleep(.02)
        if mode.startswith('agent') and not (root / 'fixed').exists():
            handoff = root / 'failure.json'
            count = int((root / 'repair-count').read_text()) if (root / 'repair-count').exists() else 0
            prompt = f'LATEST FAILURE ONLY {count + 1}' if mode == 'agent-repeat' else 'LATEST FAILURE ONLY'
            handoff.write_text(json.dumps({'prompt': prompt, 'categories': [category]}))
            print(f'Failure handoff: {handoff}', flush=True)
            return 1
        return 0

    if mode == 'agent-wait':
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        # A descendant shares the recorded agent's isolated process group.
        child = subprocess.Popen([sys.executable, '-c',
                                  'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(15)'])
        (root / 'descendant').write_text(str(child.pid))
        (root / 'agent-ready').touch()
        time.sleep(15)
    count = int((root / 'repair-count').read_text()) if (root / 'repair-count').exists() else 0
    (root / 'repair-count').write_text(str(count + 1))
    if mode != 'agent-repeat' or count >= 1:
        (root / 'fixed').touch()
    reply = Path(args[args.index('--output-last-message') + 1])
    reply.write_text(json.dumps([] if mode == 'agent-invalid' else
                               {'status': 'blocked' if mode == 'agent-blocked' else 'fixed',
                                'summary': 'fixture result'}))
    print('PREVIOUS AGENT TRANSCRIPT MUST NOT BECOME INPUT', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
