"""Finite, harmless test/agent doubles for fix-tests process qualification."""

import json
import hashlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main():
    root = Path.cwd()
    kind, *args = sys.argv[1:]
    if kind == '--worker':
        from contextlib import nullcontext
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
        import fix_tests
        import vm_pool
        vm_pool.selected_reservation = lambda **kwargs: nullcontext()
        vm_pool.reservation = lambda *args, **kwargs: nullcontext()
        root, run, owner, *options = args
        return fix_tests.worker(Path(root), Path(run), int(owner), *options)
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
    script = json.loads((root / 'script.json').read_text()) if mode == 'agent-script' else {}
    if script.get('record_git'):
        record['pushed_subject'] = subprocess.run(
            ['git', 'log', '-1', '--format=%s', '@{upstream}'], cwd=root,
            capture_output=True, text=True, check=True, timeout=10).stdout.strip()
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
        script = json.loads((root / 'script.json').read_text()) if mode == 'agent-script' else {}
        if kind == 'test':
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
            from test_checkpoint import Checkpoint
            from vm_selection import vm_config
            options, _ = vm_config.extract_selector(test_args[2:])
            selections = script.get('checkpoint', [(category, options)])
            try:
                checkpoint = Checkpoint(root, selections, resume='--resume' in args,
                                        **({} if 'checkpoint' in script else {'binding': ''}))
            except ValueError as error:
                print(f'Test runner infrastructure failed: ValueError: {error}', flush=True)
                return 1
            for arg in args:
                if arg.startswith('--resume-case='):
                    checkpoint.event(category, dict(kind='failure', nodeid=arg.partition('=')[2]), set())
        if kind == 'test' and mode == 'agent-script':
            if 'checkpoint' in script:
                checkpoint.event(category, dict(kind='finished', nodeid='earlier-pass'), set())
                checkpoint.save()
            marker = root / 'script-tests'
            index = int(marker.read_text()) if marker.exists() else 0
            marker.write_text(str(index + 1))
            if script.get('wait_test') == index:
                (root / 'test-ready').touch()
                deadline = time.monotonic() + 15
                while not (root / 'release').exists() and time.monotonic() < deadline:
                    time.sleep(.02)
            case = script['tests'][index]
            # Model runner-owned completion evidence, including the exact case
            # after teardown. Different failures remain unknown unless listed.
            passed = script.get('passed', {}).get(str(index), [])
            if case is None:
                passed = [*passed, *[item if isinstance(item, str) else item['case']
                                    for item in script['tests'][:index] if item is not None]]
            for node in passed:
                if node and node not in script.get('unexecuted', []):
                    checkpoint.event(category, dict(kind='finished', nodeid=node), set())
            checkpoint.save()
            if case is None:
                for item in script['tests'][:index]:
                    if not isinstance(item, dict) or item['category'] != category:
                        continue
                    guest = Checkpoint(root, [(category, options)], resume=True, binding=item['vm'])
                    guest.event(category, dict(kind='finished', nodeid=item['case']), set())
                    guest.save()
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
        script = json.loads((root / 'script.json').read_text())
        status = script['agents'][count]
        blocked = status == 'blocked'
        for update in script.get('panel_updates', []):
            print(json.dumps({'type': 'item.completed', 'item': {
                'id': 'panel', 'type': 'agent_message',
                'text': 'LAUNCHER_STATUS ' + json.dumps(update)}}), flush=True)
        if 'replace_checkpoint' in script:
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
            from test_checkpoint import Checkpoint
            checkpoint = Checkpoint(root, script['replace_checkpoint'])
            if script.get('invalid_checkpoint'):
                (checkpoint.store.path / checkpoint.name).write_text('{}')
    reply = Path(args[args.index('--output-last-message') + 1])
    stage_paths = []
    if status in ('fixed', 'test_fixed', 'diagnostic_ready'):
        failures = json.loads((root / 'failure.json').read_text()).get('failures', [])
        identity = json.dumps(failures[0] if failures else {}, sort_keys=True)
        path = script.get('repair_path', 'repair-' + hashlib.sha256(identity.encode()).hexdigest()[:12] + '.py')
        (root / path).write_text(f'fixture repair {count + 1}\n')
        stage_paths = [path]
        if script.get('omit_paths_once') and count == 0:
            stage_paths = []
    reply.write_text(json.dumps([] if mode == 'agent-invalid' else
                               {'status': status,
                                'stage_paths': stage_paths,
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
