"""Scripted test orchestration. Each repair is a fresh, ephemeral Codex process.

Only the worker owns loop state. Observers may disappear at any time. A small
subprocess supervisor retains the owner lock and watches its parent's pipe, so
even SIGKILL of the worker cancels the current operation before releasing it.
"""

import argparse
import codecs
import fcntl
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from regression_session import FRAME_DIRECTORY, busy, lock
from test_commands import suite_inventory


DEFAULT_EFFORT = 'high'
APP_EFFORT = 'high'
TAIL_BYTES = 128 * 1024
MAX_LOG_BYTES = 32 * 1024 * 1024
AGENT_GRACE = 3.0
STALE_RETENTION = 'retention: previous owner did not finish; preserve evidence for recovery'


class Stopped(Exception):
    pass


def compact_log(path, *, writer_fd=None):
    """Bound the repair transcript between owned operations; keep the latest tail."""
    descriptor = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'r+b') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1:
            raise ValueError('unsafe repair transcript')
        if info.st_size <= MAX_LOG_BYTES:
            return
        stream.seek(-MAX_LOG_BYTES // 2, os.SEEK_END)
        stream.readline()
        tail = stream.read()
        stream.seek(0)
        stream.write(b'[Earlier transcript expired under the storage limit.]\n' + tail)
        stream.truncate()
        stream.flush()
        if writer_fd is not None:
            writer = os.fstat(writer_fd)
            if (writer.st_dev, writer.st_ino) == (info.st_dev, info.st_ino):
                os.lseek(writer_fd, 0, os.SEEK_END)


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
                 'ONPC_REGRESSION_INVENTORY', FRAME_DIRECTORY):
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
            '--json', '--color', 'never', '--cd', str(root)]
    if run is not None:
        command += ['--output-schema', str(Path(__file__).with_name('fix_tests_response.schema.json')),
                    '--output-last-message', str(run / 'agent-result.json')]
    return [*command, '-']


def available_models():
    codex = shutil.which('codex')
    if codex is None:
        raise ValueError('Codex CLI is missing; install and authenticate it before running fix-tests')
    catalog = subprocess.run([codex, 'debug', 'models'], env=environment(),
                             capture_output=True, text=True, check=True)
    response = json.loads(catalog.stdout)
    models = response.get('models') if isinstance(response, dict) else None
    if not isinstance(models, list):
        raise ValueError('Codex returned an invalid model catalog')
    listed = [entry for entry in models if isinstance(entry, dict)
              and entry.get('visibility') == 'list'
              and isinstance(entry.get('slug'), str)
              and isinstance(entry.get('priority'), int)
              and not isinstance(entry.get('priority'), bool)
              and isinstance(entry.get('supported_reasoning_levels'), list)
              and any(isinstance(level, dict) and level.get('effort') == 'high'
                      for level in entry['supported_reasoning_levels'])]
    sol = [entry for entry in listed
           if re.fullmatch(r'gpt-(\d+(?:\.\d+)*)-sol', entry['slug'])]
    if not sol:
        raise ValueError('Codex model catalog has no listed high-reasoning Sol model')
    newest_sol = max(sol, key=lambda entry: tuple(
        int(part) for part in entry['slug'][4:-4].split('.')))
    strongest = min(listed, key=lambda entry: entry['priority'])
    return newest_sol['slug'], strongest['slug']


def repair_prompt(prompt, *, app_issue=None):
    instructions = (
        'Classify the failure from the evidence as a test issue, an app issue, or '
        'uncertain before editing. If it is a test issue, fix it in this session '
        'and return status "test_fixed". If it is an app issue, make no edits and return '
        'status "app_issue" with a concise reason. If classification remains '
        'uncertain, make no edits and return status "uncertain" with the competing '
        'explanations. The launcher will start a stronger agent for either of the '
        'last two statuses. '
        if app_issue is None else
        'The first session classified this as an app issue or uncertain and ended. '
        'Recheck the classification using the original failure evidence, then fix '
        'the root cause in this checkout. Return status "fixed" after a repair. '
        f'Its classification was: {app_issue}\n\n')
    return (prompt + '\n\n'
            'This is one independent repair attempt in tools/fix-tests. '
            + instructions + 'Preserve unrelated work. Follow AGENTS.md '
            'and docs/Approval-Tools.md. Do not change expected product behavior or weaken, '
            'skip or delete tests to obtain a pass. Report any missing authority or '
            'prerequisite using status "blocked" in the final result. '
            'The script owns test execution: finish after classification or repair; '
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


def category_status(category, categories):
    try:
        index = categories.index(category)
    except ValueError:
        return None
    return (f'\033[1;36mRunning category [{category}] '
            f'({index + 1}/{len(categories)})\033[0m')


def run_loop(categories, test, repair, check_stop, *, selected=False):
    """No session objects or past prompts survive a repair/category iteration."""
    def finish_category(category, failure):
        while failure is not None:
            check_stop()
            repair(failure['prompt'])
            check_stop()
            failure = test(category)

    for category in categories:
        check_stop()
        finish_category(category, test(category))
    if selected:
        # A later repair can break an earlier leaf. Require a whole selected
        # pass without repairs before finishing, never widening to all.
        while True:
            clean = True
            for category in categories:
                check_stop()
                failure = test(category)
                if failure is not None:
                    clean = False
                    finish_category(category, failure)
            if clean:
                return
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
    elif kind == 'recovery':
        command = [str(root / 'tools/cleanup-e2e')]
    else:
        command = agent_command(root, model, effort, run)
    renderer = None
    if kind == 'agent':
        from fix_tests_render import AgentRenderer
        renderer = AgentRenderer(sys.stdout)
    source = (run / 'prompt.txt').open('rb') if kind == 'agent' else None
    log = (run / 'last-test.log').open('wb') if kind != 'agent' else None
    child_env = environment()
    if kind != 'agent':
        child_env[FRAME_DIRECTORY] = str(run)
    child = subprocess.Popen(command, cwd=root, env=child_env,
                             stdin=source if source is not None else subprocess.DEVNULL,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE if renderer else subprocess.STDOUT,
                             start_new_session=True)
    if source is not None:
        source.close()
    descriptor = None
    try:
        descriptor = os.pidfd_open(child.pid)
        sent = None
        ready = kind != 'test'
        pending = b''
        with selectors.DefaultSelector() as poller:
            poller.register(sys.stdin, selectors.EVENT_READ, 'parent')
            poller.register(child.stdout, selectors.EVENT_READ, 'output')
            if child.stderr is not None:
                poller.register(child.stderr, selectors.EVENT_READ, 'diagnostic')
            poller.register(descriptor, selectors.EVENT_READ, 'exit')
            exited = False
            output_open = 2 if renderer else 1
            while not exited or output_open:
                requested = requested or (run / 'cancel').exists()
                if requested and sent is None and ready:
                    sent = time.monotonic()
                    try:
                        if kind != 'agent':
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
                            output_open -= 1
                            if renderer and key.data == 'output':
                                renderer.finish()
                            continue
                        if log is not None:
                            log.write(data)
                            log.flush()
                        if renderer and key.data == 'output':
                            renderer.feed(data)
                        else:
                            sys.stdout.buffer.write(data)
                        sys.stdout.flush()
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
        if child.stderr is not None:
            child.stderr.close()
        if descriptor is not None:
            os.close(descriptor)
        if log is not None:
            log.close()
            atomic(run / 'frame.json', [])
        os.close(owner)


def worker(root, run, owner, model, effort, app_model, requested='[]'):
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    def cancel(*_):
        (run / 'cancel').touch(mode=0o600)

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, cancel)

    def check_stop():
        if (run / 'cancel').exists():
            raise Stopped()

    def execute(kind, category='', options=(), *, agent_model=None, agent_effort=None):
        check_stop()
        command = ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                   '--supervise', str(root), str(run), str(owner), kind, category,
                   agent_model or model, agent_effort or effort,
                   json.dumps(options)]
        # The supervisor inherits ownership, but the test/agent does not. Its
        # stdin pipe is a liveness lease, not an interactive agent conversation.
        with subprocess.Popen(command, cwd=root, env=environment(), stdin=subprocess.PIPE,
                              pass_fds=(owner,), start_new_session=True) as child:
            status = child.wait()
        sys.stdout.flush()
        compact_log(run / 'output', writer_fd=1)
        if (run / 'last-test.log').exists():
            compact_log(run / 'last-test.log')
        check_stop()
        return status

    def test(category):
        def run_requested(requested, options, description):
            while True:
                status = execute('test', requested, options)
                # run-tests consumes an active/unread predecessor before honoring
                # new arguments. Its result must never count as our requested run.
                with (run / 'last-test.log').open('rb') as stream:
                    attached = b'Attached to run-tests session:' in stream.read(8192)
                if not attached:
                    return status
                print(f'fix-tests: previous run-tests output delivered; starting {description}.',
                      flush=True)

        recovered = False
        while True:
            status_line = category_status(category, categories)
            atomic(run / 'category.json', status_line)
            print(f'\nfix-tests: running {category}', flush=True)
            status = run_requested(category, inventory.get(category, {}).get('args', []),
                                   'the requested category')
            if status == 0:
                if status_line is not None:
                    print(status_line, flush=True)
                return None
            if STALE_RETENTION in read_tail(run / 'last-test.log'):
                if recovered:
                    raise ValueError('test runner remained stale after automatic recovery; '
                                     'see last-test.log')
                print('fix-tests: interrupted test ownership found; recovering both retention scopes.',
                      flush=True)
                recovery_status = execute('recovery')
                if recovery_status:
                    if status_line is not None:
                        print(status_line, flush=True)
                    return handoff(run)
                recovered = True
                continue
            if status_line is not None:
                print(status_line, flush=True)
            return handoff(run)

    def repair(prompt):
        print(f'\nfix-tests: classify and repair ({model}, {effort})', flush=True)
        (run / 'prompt.txt').write_text(repair_prompt(prompt), encoding='utf-8')
        # Truncate only our own last reply; an agent crash cannot reuse it.
        (run / 'agent-result.json').write_text('')
        status = execute('agent')
        if status:
            raise ValueError(f'repair agent exited with status {status}; inspect the output before restarting')
        result = json.loads((run / 'agent-result.json').read_text())
        if not isinstance(result, dict):
            raise ValueError('repair agent did not return a result object')
        if result.get('status') in ('app_issue', 'uncertain'):
            classification = result['status'] + ': ' + str(result.get('summary', ''))
            print(f'\nfix-tests: app review ({app_model}, {APP_EFFORT}); {classification}',
                  flush=True)
            (run / 'prompt.txt').write_text(
                repair_prompt(prompt, app_issue=classification), encoding='utf-8')
            (run / 'agent-result.json').write_text('')
            status = execute('agent', agent_model=app_model, agent_effort=APP_EFFORT)
            if status:
                raise ValueError(f'app review agent exited with status {status}; '
                                 'inspect the output before restarting')
            result = json.loads((run / 'agent-result.json').read_text())
            if not isinstance(result, dict):
                raise ValueError('app review agent did not return a result object')
            if result.get('status') != 'fixed':
                raise ValueError('repair blocked: ' + str(result.get('summary', 'no repair result')))
        elif result.get('status') != 'test_fixed':
            raise ValueError('repair blocked: ' + str(result.get('summary', 'no repair result')))

    status = 1
    try:
        try:
            from fix_tests_render import AgentRenderer  # Check before expensive tests.
        except ImportError as error:
            raise ValueError('agent rendering requires the setup-provided python3-rich package') from error
        agent_command(root, model, effort)  # Fail before running expensive tests.
        listing = subprocess.run([str(root / 'tools/run-tests'), '--list'], cwd=root,
                                 env=environment(), capture_output=True, text=True, check=True)
        requested = json.loads(requested)
        inventory = suite_inventory(requested, inventory=category_inventory(listing.stdout))
        categories = list(inventory)
        print('fix-tests: category pass, then ' +
              ('selected leaf passes' if requested else 'complete all passes') +
              ' until success', flush=True)
        print('fix-tests: categories: ' + ', '.join(categories), flush=True)
        run_loop(categories, test, repair, check_stop, selected=bool(requested))
        print('\nfix-tests: ' + ('all selected categories passed.' if requested else
              'all categories and the complete regression passed.'), flush=True)
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


def select(root, *, stop=False, model=None, effort=DEFAULT_EFFORT, categories=()):
    legacy = root / 'artifacts/fix-tests'
    if (legacy / 'owner').exists():
        with lock(legacy / 'owner') as owner:
            if busy(owner):
                run = current_run(legacy)
                if run is None:
                    raise ValueError('active legacy fix-tests owner has no readable run record')
                if stop:
                    (run / 'cancel').touch(mode=0o600)
                return run, False
    from test_storage import directory as storage_directory
    directory = storage_directory('fix-tests', root=root)
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
        default_model, app_model = available_models()
        model = default_model if model is None else model
        # Completed, cancelled and abruptly killed runs never block a new run.
        # Keep their logs; neither PID files nor cancel markers grant ownership.
        run = private_directory(directory / uuid.uuid4().hex)
        import test_retention
        with test_retention.Store(directory / 'retention').session():
            test_retention.retain(run)
        fcntl.flock(owner, fcntl.LOCK_EX)
        atomic(directory / 'current.json', {'run': run.name})
        with (run / 'output').open('xb') as output:
            subprocess.Popen(['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                              '--worker', str(root), str(run), str(owner), model, effort,
                              app_model,
                              json.dumps(categories)],
                             cwd=root, env=environment(), stdin=subprocess.DEVNULL,
                             stdout=output, stderr=subprocess.STDOUT, start_new_session=True,
                             pass_fds=(owner,))
        return run, True


def follow(run, stream=None):
    from regression import Dashboard
    stream = stream or sys.stdout
    dashboard = Dashboard([], stream=stream)
    try:
        return follow_output(run, stream, dashboard)
    finally:
        dashboard.restore_terminal()


def follow_output(run, stream, dashboard):
    last_frame = None
    decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
    with lock(run.parent / 'owner') as owner, (run / 'output').open('rb') as output:
        offset = max(0, output.seek(0, os.SEEK_END) - TAIL_BYTES)
        output.seek(offset)
        if offset:
            output.readline()  # Reattach at a full line, not midway through UTF-8/ANSI.
        while True:
            active = busy(owner)
            # A new invocation may already own a newer run after this one ends.
            active = active and current_run(run.parent) == run
            if output.tell() > os.fstat(output.fileno()).st_size:
                output.seek(0)
                decoder.reset()
            data = output.read(65536)
            if data:
                dashboard.restore_terminal()
                stream.write(decoder.decode(data))
                stream.flush()
                continue
            if not active:
                dashboard.restore_terminal()
                stream.write(decoder.decode(b'', final=True))
                result = run / 'result.json'
                if not result.exists():
                    stream.write('\nfix-tests: worker ended without a result; invoke again to start fresh.\n')
                    stream.flush()
                    return 1
                return json.loads(result.read_text())['status']
            frame = run / 'frame.json'
            if frame.exists():
                lines = json.loads(frame.read_text())
                if lines:
                    try:
                        category_status = json.loads((run / 'category.json').read_text())
                    except (OSError, ValueError):
                        category_status = None
                    if isinstance(category_status, str):
                        lines.append(category_status)
                if not lines:
                    dashboard.restore_terminal()
                elif stream.isatty() or lines != last_frame:
                    dashboard.draw_lines(lines)
                last_frame = lines
            time.sleep(.1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--stop', action='store_true', help='stop the active run, like Ctrl+C')
    parser.add_argument('--model', help='initial repair model (default: latest available Sol)')
    parser.add_argument('--effort', choices=('low', 'medium', 'high', 'xhigh'),
                        default=DEFAULT_EFFORT, help='reasoning effort (default: high)')
    parser.add_argument('categories', nargs='*', metavar='CATEGORY',
                        help='leaf categories, host (or host-builds), or all; accepts "unit ui"; '
                             'omitting categories preserves the full regression loop')
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
        run, started = select(root, stop=requested, model=args.model, effort=args.effort,
                              categories=args.categories)
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
