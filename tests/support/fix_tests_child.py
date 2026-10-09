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
    if kind == 'agent' and args == ['debug', 'models']:
        if (root / 'catalog.json').exists():
            print((root / 'catalog.json').read_text())
            return 0
        print(json.dumps({'models': [
            {'slug': 'gpt-6.1-sol', 'visibility': 'list', 'priority': 2,
             'supported_reasoning_levels': [{'effort': 'low'}, {'effort': 'medium'},
                                            {'effort': 'high'}, {'effort': 'xhigh'},
                                            {'effort': 'max'}]},
        ]}))
        return 0
    if kind == 'test' and args == ['--list']:
        if (root / 'inventory.json').exists():
            print((root / 'inventory.json').read_text())
            return 0
        print(json.dumps({name: {'description': name, 'args': []}
                          for name in ('unit', 'ui', 'system', 'e2e')}))
        return 0
    mode = (root / 'mode').read_text()
    test_args = [arg for arg in args if arg != '--resume' and not arg.startswith('--resume-case=')]
    category = test_args[1] if kind == 'test' else kind
    record = {'kind': kind, 'category': category, 'pid': os.getpid(), 'args': args}
    record['frame_directory'] = os.environ.get('ONPC_TEST_FRAME_DIRECTORY')
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

    if kind in ('test', 'recovery'):
        signal.signal(signal.SIGINT, interrupt)
        if mode == 'attach-once' and not (root / 'attached').exists():
            (root / 'attached').touch()
            print('Attached to run-tests session: previous', flush=True)
            return 0
        if kind == 'test':
            print('Started run-tests session: harmless', flush=True)
        if kind == 'test' and mode == 'agent-script':
            script = json.loads((root / 'script.json').read_text())
            marker = root / 'script-tests'
            index = int(marker.read_text()) if marker.exists() else 0
            marker.write_text(str(index + 1))
            if script.get('wait_test') == index:
                (root / 'test-ready').touch()
                deadline = time.monotonic() + 15
                while not (root / 'release').exists() and time.monotonic() < deadline:
                    time.sleep(.02)
            case = script['tests'][index]
            if case is None:
                return 0
            target = dict(category=category, case=case, vm='') if isinstance(case, str) else case
            handoff = root / 'failure.json'
            handoff.write_text(json.dumps({'prompt': 'LATEST FAILURE ONLY',
                'categories': [target['category']], 'failures': [target]}))
            print(f'Failure handoff: {handoff}', flush=True)
            return 1
        if mode in ('retention-once', 'recovery-wait'):
            if category == 'unit' and not (root / 'recovered').exists():
                print('retention: previous owner did not finish; preserve evidence for recovery',
                      flush=True)
                return 1
            if kind == 'recovery':
                (root / 'recovered').touch()
        if mode == 'retention-repair':
            if category == 'unit' and not (root / 'recovered').exists():
                print('retention: previous owner did not finish; preserve evidence for recovery',
                      flush=True)
                return 1
            if kind == 'recovery':
                if not (root / 'fixed').exists():
                    handoff = root / 'failure.json'
                    handoff.write_text(json.dumps({
                        'prompt': 'LATEST RECOVERY FAILURE ONLY',
                        'categories': ['unit'],
                    }))
                    print(f'Failure handoff: {handoff}', flush=True)
                    return 1
                (root / 'recovered').touch()
        if mode == 'test-wait' or (mode == 'recovery-wait' and kind == 'recovery'):
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
        print('Overall - 100% (1/1) - 0.0m', flush=True)
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
    app_mode = mode in ('agent-app', 'agent-uncertain', 'agent-app-blocked')
    blocked = ((mode == 'agent-blocked' and count == 0)
               or (mode == 'agent-app-blocked' and count == 1)
               or (mode == 'agent-blocked-twice' and count < 2))
    if not blocked and (mode not in ('agent-repeat', 'agent-app', 'agent-uncertain',
                                   'agent-app-blocked') or count >= 1):
        (root / 'fixed').touch()
    status = ('blocked' if blocked else
              'app_issue' if mode in ('agent-app', 'agent-app-blocked') and count == 0 else
              'uncertain' if mode == 'agent-uncertain' and count == 0 else
              'fixed' if (app_mode or mode == 'agent-repeat') and count >= 1 else
              'test_fixed')
    if mode == 'agent-script':
        status = json.loads((root / 'script.json').read_text())['agents'][count]
        blocked = status == 'blocked'
    reply = Path(args[args.index('--output-last-message') + 1])
    reply.write_text(json.dumps([] if mode == 'agent-invalid' else
                               {'status': status,
                                'summary': f'fixture result {count + 1}' if mode == 'agent-script' else 'fixture result',
                                'blocker': {
                                    'explanation': 'Expected the specified behavior; observed a mismatch.',
                                    'question': 'Which behavior should the repair preserve?',
                                    'options': ['Restore the specified behavior.',
                                                'Investigate the requirement before editing.']
                                } if blocked else None}))
    print(json.dumps({'type': 'item.completed', 'item': {
        'id': 'thinking', 'type': 'reasoning', 'text': 'PRIVATE REASONING FIXTURE'}}), flush=True)
    print(json.dumps({'type': 'item.completed', 'item': {
        'id': 'source', 'type': 'command_execution', 'command': 'cat example.py',
        'aggregated_output': '\n'.join(f'if value == {number}: return True' for number in range(30)),
        'exit_code': 0}}), flush=True)
    print(json.dumps({'type': 'item.completed', 'item': {
        'id': 'message', 'type': 'agent_message',
        'text': '**Formatted repair**\n\n```python\ndef repaired():\n    return True\n```'}}), flush=True)
    print('agent stderr diagnostic', file=sys.stderr, flush=True)
    if mode != 'agent-invalid':
        print(json.dumps({'type': 'turn.completed', 'usage': {
            'input_tokens': 100, 'cached_input_tokens': 40, 'output_tokens': 20}}), flush=True)
    print('PREVIOUS AGENT TRANSCRIPT MUST NOT BECOME INPUT', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
