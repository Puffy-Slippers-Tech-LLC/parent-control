"""Scripted test orchestration. Each repair is a fresh, ephemeral Codex process.

Only the worker owns loop state. Observers may disappear at any time. A small
subprocess supervisor retains the owner lock and watches its parent's pipe, so
even SIGKILL of the worker cancels the current operation before releasing it.
"""

import argparse
import fcntl
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from regression_session import busy, lock


DEFAULT_MODEL = 'gpt-5.6-sol'
DEFAULT_EFFORT = 'high'
TAIL_BYTES = 128 * 1024
AGENT_GRACE = 3.0


class Stopped(Exception):
    pass


def atomic(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value), encoding='utf-8')
    temporary.replace(path)


def private_directory(path):
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError('fix-tests state path contains a symlink')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = path.stat()
    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('fix-tests state directory must be caller-owned and private')
    return path


def current_run(directory):
    try:
        name = json.loads((directory / 'current.json').read_text())['run']
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(name, str) or len(name) != 32 or any(c not in '0123456789abcdef' for c in name):
        return None
    run = directory / name
    return private_directory(run) if run.is_dir() else None


def environment():
    # Keep authentication, configuration and policy; discard inherited thread
    # identities and launcher FD claims. No parent conversation is ever passed.
    result = dict(os.environ)
    for name in ('CODEX_THREAD_ID', 'CODEX_PARENT_THREAD_ID', 'CODEX_SESSION_ID',
                 'ONPC_TEST_ACTIVITY_FD', 'ONPC_REGRESSION_EVENTS',
                 'ONPC_REGRESSION_INVENTORY'):
        result.pop(name, None)
    result['PYTHONUNBUFFERED'] = '1'
    return result


def agent_command(root, model, effort, run=None):
    codex = shutil.which('codex')
    if codex is None:
        raise ValueError('Codex CLI is missing; install and authenticate it before running fix-tests')
    command = [codex, '--ask-for-approval', 'never', 'exec', '--ephemeral',
            '--sandbox', 'workspace-write', '--model', model,
            '-c', f'model_reasoning_effort="{effort}"',
            '-c', 'history.persistence="none"', '-c', 'features.memories=false',
            '-c', 'features.multi_agent=false', '-c', 'features.multi_agent_v2=false',
            '--color', 'never', '--cd', str(root)]
    if run is not None:
        command += ['--output-schema', str(Path(__file__).with_name('fix_tests_response.schema.json')),
                    '--output-last-message', str(run / 'agent-result.json')]
    return [*command, '-']


def repair_prompt(prompt):
    return (prompt + '\n\n'
            'This is one independent repair attempt in tools/fix-tests. Fix the recorded '
            'root cause in this checkout and preserve unrelated work. Follow AGENTS.md '
            'and docs/Approval-Tools.md. Do not change expected product behavior or weaken, '
            'skip or delete tests to obtain a pass. Report any missing authority or '
            'prerequisite using status "blocked" in the final result. Otherwise use '
            'status "fixed" so the script can validate your repair. '
            'The script owns test execution: finish after the repair; '
            'do not launch tests, fix-tests, background jobs or other agent sessions. '
            'Do not read or resume previous Codex sessions, histories, memories or repair '
            'transcripts. Use only this failure handoff and the current repository.\n')


def read_tail(path):
    with path.open('rb') as stream:
        stream.seek(max(0, stream.seek(0, os.SEEK_END) - TAIL_BYTES))
        return stream.read().decode('utf-8', errors='replace')


def handoff(run):
    lines = read_tail(run / 'last-test.log').splitlines()
    paths = [line.removeprefix('Failure handoff: ') for line in lines
             if line.startswith('Failure handoff: ')]
    if not paths:
        raise ValueError('test runner did not produce a failure handoff; see last-test.log')
    value = json.loads(Path(paths[-1]).read_text())
    if (not isinstance(value, dict) or not isinstance(value.get('prompt'), str)
            or not value['prompt'].strip() or not isinstance(value.get('categories'), list)):
        raise ValueError('invalid test failure handoff')
    return value


def category_inventory(output):
    inventory = json.loads(output)
    if not isinstance(inventory, dict) or not inventory:
        raise ValueError('run-tests returned no implemented leaf categories')
    for category, spec in inventory.items():
        if (not isinstance(category, str) or not category or category.startswith('-')
                or not isinstance(spec, dict) or not isinstance(spec.get('args'), list)
                or not all(isinstance(arg, str) for arg in spec['args'])):
            raise ValueError('invalid run-tests category inventory')
    # The runner owns eligibility. Order the available leaves without requiring
    # an unimplemented category just to satisfy a positional check.
    return {category: inventory[category] for category in (
        *(name for name in ('unit', 'ui') if name in inventory),
        *(name for name in inventory if name not in ('unit', 'ui', 'system', 'e2e')),
        *(name for name in ('system', 'e2e') if name in inventory))}


def run_loop(categories, test, repair, check_stop):
    """No session objects or past prompts survive a repair/category iteration."""
    def finish_category(category, failure):
        while failure is not None:
            check_stop()
            repair(failure['prompt'])
            check_stop()
            failure = test(category)

    for index, category in enumerate(categories, 1):
        check_stop()
        print(f'\n\033[1;36mRunning category [{category}] ({index}/{len(categories)})\033[0m',
              flush=True)
        finish_category(category, test(category))
    while True:
        check_stop()
        failure = test('all')
        if failure is None:
            return
        failed = failure['categories']
        if not failed or any(category not in categories for category in failed):
            raise ValueError('aggregate failure has no runnable retry category; inspect its handoff')
        # Parallel companions can report more than one failure before cleanup.
        # Each category is repaired against fresh evidence after the first one.
        for index, category in enumerate(dict.fromkeys(failed)):
            check_stop()
            finish_category(category, failure if index == 0 else test(category))


def supervise(root, run, owner, kind, category, model, effort, test_args='[]'):
    """Own one child until it is reaped; EOF means the loop worker died.

    Tests get the runner's Ctrl+C path with unlimited time for guarded cleanup.
    Agents get SIGTERM immediately, then bounded process-group termination.
    The unreaped child pins its own process-group identity until cleanup ends.
    """
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    requested = False

    def stop(*_):
        nonlocal requested
        requested = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    # A stop can arrive after the worker's check but before this supervisor
    # starts. Do not begin another operation for an already cancelled run.
    with selectors.DefaultSelector() as parent:
        parent.register(sys.stdin, selectors.EVENT_READ)
        parent_gone = bool(parent.select(0))
    if requested or parent_gone or (run / 'cancel').exists():
        os.close(owner)
        return 130
    if kind == 'test':
        options = json.loads(test_args)
        command = [str(root / 'tools/run-tests'), '--stop-on-error', category, *options]
    else:
        command = agent_command(root, model, effort, run)
    source = (run / 'prompt.txt').open('rb') if kind == 'agent' else None
    log = (run / 'last-test.log').open('wb') if kind == 'test' else None
    child = subprocess.Popen(command, cwd=root, env=environment(),
                             stdin=source if source is not None else subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             start_new_session=True)
    if source is not None:
        source.close()
    descriptor = None
    try:
        descriptor = os.pidfd_open(child.pid)
        sent = None
        ready = kind == 'agent'
        pending = b''
        with selectors.DefaultSelector() as poller:
            poller.register(sys.stdin, selectors.EVENT_READ, 'parent')
            poller.register(child.stdout, selectors.EVENT_READ, 'output')
            poller.register(descriptor, selectors.EVENT_READ, 'exit')
            exited = False
            output_open = True
            while not exited or output_open:
                requested = requested or (run / 'cancel').exists()
                if requested and sent is None and ready:
                    sent = time.monotonic()
                    try:
                        if kind == 'test':
                            signal.pidfd_send_signal(descriptor, signal.SIGINT)
                        else:
                            os.killpg(child.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                if kind == 'agent' and sent is not None and time.monotonic() - sent >= AGENT_GRACE:
                    os.killpg(child.pid, signal.SIGKILL)
                for key, _ in poller.select(.1):
                    if key.data == 'parent':
                        if not os.read(key.fd, 1):
                            poller.unregister(key.fileobj)
                        requested = True
                    elif key.data == 'exit':
                        # Do not reap yet: retain the process-group identity.
                        exited = True
                        poller.unregister(key.fileobj)
                        if kind == 'agent':
                            os.killpg(child.pid, signal.SIGKILL)
                    else:
                        data = os.read(key.fd, 65536)
                        if not data:
                            poller.unregister(key.fileobj)
                            output_open = False
                            continue
                        if log is not None:
                            log.write(data)
                            log.flush()
                        sys.stdout.buffer.write(data)
                        sys.stdout.buffer.flush()
                        if not ready:
                            pending = (pending + data)[-8192:]
                            ready = b' run-tests session:' in pending
            if kind == 'agent':
                # Close any same-session subprocess left behind by the agent.
                os.killpg(child.pid, signal.SIGKILL)
        status = child.wait()
        return 130 if requested else status if status >= 0 else 128 - status
    finally:
        # Failure while supervising must not release ownership over a live child.
        if child.returncode is None:
            if kind == 'agent':
                os.killpg(child.pid, signal.SIGKILL)
            else:
                child.send_signal(signal.SIGINT)
            child.communicate()
        child.stdout.close()
        if descriptor is not None:
            os.close(descriptor)
        if log is not None:
            log.close()
        os.close(owner)


def worker(root, run, owner, model, effort):
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    def cancel(*_):
        (run / 'cancel').touch(mode=0o600)

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, cancel)

    def check_stop():
        if (run / 'cancel').exists():
            raise Stopped()

    def execute(kind, category='', options=()):
        check_stop()
        command = ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                   '--supervise', str(root), str(run), str(owner), kind, category, model, effort,
                   json.dumps(options)]
        # The supervisor inherits ownership, but the test/agent does not. Its
        # stdin pipe is a liveness lease, not an interactive agent conversation.
        with subprocess.Popen(command, cwd=root, env=environment(), stdin=subprocess.PIPE,
                              pass_fds=(owner,), start_new_session=True) as child:
            status = child.wait()
        check_stop()
        return status

    def test(category):
        while True:
            print(f'\nfix-tests: running {category}', flush=True)
            status = execute('test', category, inventory.get(category, {}).get('args', []))
            # run-tests consumes an active/unread predecessor before honoring
            # new arguments. Its result must never count as our requested run.
            with (run / 'last-test.log').open('rb') as stream:
                attached = b'Attached to run-tests session:' in stream.read(8192)
            if not attached:
                return None if status == 0 else handoff(run)
            print('fix-tests: previous run-tests output delivered; starting the requested category.', flush=True)

    def repair(prompt):
        print(f'\nfix-tests: fresh repair session ({model}, {effort})', flush=True)
        (run / 'prompt.txt').write_text(repair_prompt(prompt), encoding='utf-8')
        # Truncate only our own last reply; an agent crash cannot reuse it.
        (run / 'agent-result.json').write_text('')
        status = execute('agent')
        if status:
            raise ValueError(f'repair agent exited with status {status}; inspect the output before restarting')
        result = json.loads((run / 'agent-result.json').read_text())
        if not isinstance(result, dict):
            raise ValueError('repair agent did not return a result object')
        if result.get('status') != 'fixed':
            raise ValueError('repair blocked: ' + str(result.get('summary', 'no repair result')))

    status = 1
    try:
        agent_command(root, model, effort)  # Fail before running expensive tests.
        listing = subprocess.run([str(root / 'tools/run-tests'), '--list'], cwd=root,
                                 env=environment(), capture_output=True, text=True, check=True)
        inventory = category_inventory(listing.stdout)
        categories = list(inventory)
        print('fix-tests: category pass, then complete all passes until success', flush=True)
        print('fix-tests: categories: ' + ', '.join(categories), flush=True)
        run_loop(categories, test, repair, check_stop)
        print('\nfix-tests: all categories and the complete regression passed.', flush=True)
        status = 0
    except Stopped:
        print('\nfix-tests: stopped; owned operation cleanup finished.', flush=True)
        status = 130
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'\nfix-tests: {error}', file=sys.stderr, flush=True)
    finally:
        atomic(run / 'result.json', {'status': status})
        os.close(owner)
    return status


def select(root, *, stop=False, model=DEFAULT_MODEL, effort=DEFAULT_EFFORT):
    directory = private_directory(root / 'artifacts/fix-tests')
    with lock(directory / 'gate') as gate, lock(directory / 'owner') as owner:
        fcntl.flock(gate, fcntl.LOCK_EX)
        if busy(owner):
            run = current_run(directory)
            if run is None:
                raise ValueError('active fix-tests owner has no readable run record')
            if stop:
                (run / 'cancel').touch(mode=0o600)
            return run, False
        if stop:
            return None, False
        # Completed, cancelled and abruptly killed runs never block a new run.
        # Keep their logs; neither PID files nor cancel markers grant ownership.
        run = private_directory(directory / uuid.uuid4().hex)
        fcntl.flock(owner, fcntl.LOCK_EX)
        atomic(directory / 'current.json', {'run': run.name})
        with (run / 'output').open('xb') as output:
            subprocess.Popen(['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                              '--worker', str(root), str(run), str(owner), model, effort],
                             cwd=root, env=environment(), stdin=subprocess.DEVNULL,
                             stdout=output, stderr=subprocess.STDOUT, start_new_session=True,
                             pass_fds=(owner,))
        return run, True


def follow(run, stream=None):
    stream = stream or sys.stdout
    with lock(run.parent / 'owner') as owner, (run / 'output').open('rb') as output:
        output.seek(max(0, output.seek(0, os.SEEK_END) - TAIL_BYTES))
        while True:
            active = busy(owner)
            # A new invocation may already own a newer run after this one ends.
            active = active and current_run(run.parent) == run
            data = output.read(65536)
            if data:
                stream.write(data.decode('utf-8', errors='replace'))
                stream.flush()
                continue
            if not active:
                result = run / 'result.json'
                if not result.exists():
                    stream.write('\nfix-tests: worker ended without a result; invoke again to start fresh.\n')
                    stream.flush()
                    return 1
                return json.loads(result.read_text())['status']
            time.sleep(.1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--stop', action='store_true', help='stop the active run, like Ctrl+C')
    parser.add_argument('--model', default=DEFAULT_MODEL, help='repair model (default: Sol)')
    parser.add_argument('--effort', choices=('low', 'medium', 'high', 'xhigh'),
                        default=DEFAULT_EFFORT, help='reasoning effort (default: high)')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    run = None
    requested = args.stop

    def cancel(*_):
        nonlocal requested
        requested = True
        if run is not None:
            (run / 'cancel').touch(mode=0o600)

    previous = signal.signal(signal.SIGINT, cancel)
    try:
        run, started = select(root, stop=requested, model=args.model, effort=args.effort)
        if run is None:
            print('fix-tests: no active launcher.')
            return 0
        if requested:
            cancel()
        print(f'fix-tests: {"started" if started else "attached to"} {run.name}; log: {run / "output"}', flush=True)
        print('Closing the terminal detaches. Ctrl+C or tools/fix-tests --stop cancels.', flush=True)
        return follow(run)
    except BrokenPipeError:
        return 0  # The detached owner continues independently.
    except (OSError, ValueError) as error:
        print(f'fix-tests: {error}', file=sys.stderr)
        return 2
    finally:
        signal.signal(signal.SIGINT, previous)


if __name__ == '__main__':
    mode, root, run, owner, *options = sys.argv[1:]
    if mode == '--worker':
        sys.exit(worker(Path(root), Path(run), int(owner), *options))
    if mode == '--supervise':
        sys.exit(supervise(Path(root), Path(run), int(owner), *options))
    raise SystemExit('private fix-tests worker entry point')
