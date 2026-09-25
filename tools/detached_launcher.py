"""Shared detached workflow ownership, Codex transport and terminal rendering.

Specializations supply the worker command and workflow; locks, fresh agent
processes, transcript retention and cancellation use one implementation.
"""

from contextlib import contextmanager
import codecs
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
from test_storage import scratch_descriptors

FRAME_DIRECTORY = 'ONPC_TEST_FRAME_DIRECTORY'
WORKFLOW_DIRECTORY = 'ONPC_WORKFLOW_DIRECTORY'
TAIL_BYTES = 128 * 1024
MAX_LOG_BYTES = 32 * 1024 * 1024
AGENT_GRACE = 3.0


@contextmanager
def lock(path):
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise ValueError('unsafe aggregate session lock')
        yield fd
    finally:
        os.close(fd)


def busy(fd):
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    fcntl.flock(fd, fcntl.LOCK_UN)
    return False


class Stopped(Exception):
    pass


def compact_log(path, *, writer_fd=None):
    """Bound the workflow transcript between owned operations; keep the latest tail."""
    descriptor = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'r+b') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1:
            raise ValueError('unsafe workflow transcript')
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
        raise ValueError('workflow state path contains a symlink')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = path.stat()
    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('workflow state directory must be caller-owned and private')
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
                 'ONPC_REGRESSION_INVENTORY', FRAME_DIRECTORY, WORKFLOW_DIRECTORY):
        result.pop(name, None)
    result['PYTHONUNBUFFERED'] = '1'
    return result


def agent_command(root, model, effort, run=None, *, schema=None):
    codex = shutil.which('codex')
    if codex is None:
        raise ValueError('Codex CLI is missing; install and authenticate it before running this launcher')
    command = [codex, '--ask-for-approval', 'never', 'exec', '--ephemeral',
            '--sandbox', 'workspace-write', '--model', model,
            '-c', f'model_reasoning_effort="{effort}"',
            '-c', 'history.persistence="none"', '-c', 'features.memories=false',
            '-c', 'features.multi_agent=false', '-c', 'features.multi_agent_v2=false',
            '--json', '--color', 'never', '--cd', str(root)]
    if run is not None:
        command += ['--output-schema', str(schema or Path(__file__).with_name('fix_tests_response.schema.json')),
                    '--output-last-message', str(run / 'agent-result.json')]
    return [*command, '-']


def supervise(root, run, owner, kind, command, *, nested=False, hide_task_completion=False):
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
    renderer = None
    if kind == 'agent':
        from launcher_render import AgentRenderer
        renderer = AgentRenderer(sys.stdout, command_log=run / 'agent-commands.log',
                                 hide_task_completion=hide_task_completion)
    source = (run / 'prompt.txt').open('rb') if kind == 'agent' else None
    log = (run / 'last-test.log').open('wb') if kind != 'agent' else None
    child_env = environment()
    if nested:
        child_env[WORKFLOW_DIRECTORY] = str(run)
    if kind != 'agent':
        child_env[FRAME_DIRECTORY] = str(run)
    child = subprocess.Popen(command, cwd=root, env=child_env,
                             stdin=source if source is not None else subprocess.DEVNULL,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE if renderer else subprocess.STDOUT,
                             start_new_session=True,
                             pass_fds=scratch_descriptors())
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
        if renderer and (run / 'agent-commands.log').exists():
            compact_log(run / 'agent-commands.log')
        if nested and finish_nested(root, run):
            status = status or 1
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
        if nested:
            finish_nested(root, run)
        os.close(owner)


def select(root, name, command, *, stop=False, stop_marker='cancel',
           on_attach=None, on_start=None):
    """Attach before evaluating new options; only the lock grants ownership."""
    from test_storage import directory as storage_directory
    directory = storage_directory(name, root=root)
    with lock(directory / 'gate') as gate, lock(directory / 'owner') as owner:
        fcntl.flock(gate, fcntl.LOCK_EX)
        if busy(owner):
            run = current_run(directory)
            if run is None:
                raise ValueError(f'active {name} owner has no readable run record')
            if on_attach is not None:
                on_attach(run)
            if stop:
                (run / stop_marker).touch(mode=0o600)
            return run, False
        if stop:
            return None, False
        run = directory / uuid.uuid4().hex
        # Validate and resolve prerequisites before allocating a new run.
        argv = command(run, owner)
        private_directory(run)
        import test_retention
        with test_retention.Store(directory / 'retention').session():
            test_retention.retain(run)
        if on_start is not None:
            on_start(run)
        fcntl.flock(owner, fcntl.LOCK_EX)
        atomic(directory / 'current.json', {'run': run.name})
        with (run / 'output').open('xb') as output:
            subprocess.Popen(argv, cwd=root, env=environment(), stdin=subprocess.DEVNULL,
                             stdout=output, stderr=subprocess.STDOUT, start_new_session=True,
                             pass_fds=(owner, *scratch_descriptors()))
        return run, True


@contextmanager
def nested_operation(root, child_run):
    """Register a test owner before spawn, serialized against parent cleanup.

    Attached/pre-existing test runs never call this hook. Directory identities
    and the test owner's lock, rather than PID lookup, govern cancellation.
    """
    value = os.environ.get(WORKFLOW_DIRECTORY)
    if not value:
        yield
        return
    from test_storage import directory
    parent = Path(value)
    if parent.parent != directory('write-e2e', root=root) or len(parent.name) != 32:
        raise ValueError('invalid workflow owner directory')
    private_directory(parent)
    with lock(parent / 'nested-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        with lock(parent.parent / 'owner') as owner:
            if (not busy(owner) or current_run(parent.parent) != parent
                    or (parent / 'cancel').exists() or (parent / 'nested-closed').exists()):
                raise ValueError('workflow owner is no longer accepting test operations')
        record = parent / 'nested.json'
        entries = json.loads(record.read_text()) if record.exists() else []
        info = child_run.stat()
        entries.append({'path': str(child_run), 'device': info.st_dev, 'inode': info.st_ino})
        atomic(record, entries)
        yield


def finish_nested(root, run):
    """Cancel only registered live test owners and await their guarded cleanup."""
    from test_storage import directory
    active = False
    with lock(run / 'nested-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        (run / 'nested-closed').touch(mode=0o600)
        record = run / 'nested.json'
        entries = json.loads(record.read_text()) if record.exists() else []
        allowed = (directory('sessions', root=root), directory('sessions-host', root=root))
        for entry in entries:
            child = Path(entry['path'])
            if child.parent not in allowed or child.is_symlink():
                raise ValueError('unsafe nested test record; preserve evidence')
            try:
                info = child.stat()
            except FileNotFoundError:
                # Completed sessions can expire under the runner's retention
                # policy while a long agent session starts further tests.
                continue
            if (info.st_dev, info.st_ino) != (entry['device'], entry['inode']):
                raise ValueError('nested test identity changed; preserve evidence')
            with lock(child / 'owner') as owner:
                if busy(owner):
                    active = True
                    (child / 'cancel').touch(mode=0o600)
                    print('launcher: waiting for owned test cleanup.', flush=True)
                    while busy(owner):
                        time.sleep(.1)
    return active


def follow(run, stream=None, *, label='launcher'):
    from launcher_render import LauncherDisplay
    stream = stream or sys.stdout
    with LauncherDisplay(stream, log_path=run / 'output') as display:
        return follow_output(run, stream, display, label=label)


def follow_output(run, stream, display, *, label='launcher', test_session=False,
                  destination=None, owner_busy=None):
    from launcher_progress import read_progress, repair_progress
    from launcher_render import clean
    decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
    forwarded = None
    with lock((run if test_session else run.parent) / 'owner') as owner, (run / 'output').open('rb') as output:
        offset = 0 if test_session else max(0, output.seek(0, os.SEEK_END) - TAIL_BYTES)
        output.seek(offset)
        if offset:
            output.readline()  # Reattach at a full line, not midway through UTF-8/ANSI.
        while True:
            if label == 'write-e2e':
                from launcher_question import pending, submit
                display.update_question(pending(run), lambda identity, choice, text:
                                        submit(run, identity, choice, text))
            display.poll_input()
            active = (owner_busy or busy)(owner)
            # A new invocation may already own a newer run after this one ends.
            active = active and (test_session or current_run(run.parent) == run)
            if output.tell() > os.fstat(output.fileno()).st_size:
                output.seek(0)
                decoder.reset()
                display.pending = ''
            steps = read_progress(run)
            frame = run / 'frame.json'
            lines = json.loads(frame.read_text()) if frame.exists() else []
            if destination is not None:
                if (steps, lines) != forwarded:
                    atomic(destination / 'frame.json', lines)
                    atomic(destination / 'test-controller.json', steps)
                    forwarded = (steps, lines)
            else:
                if label == 'fix-tests':
                    steps = repair_progress(run, steps)
                # Overall progress belongs to the controller pane, not the
                # rapidly refreshed detailed test tree. Legacy frames still work.
                if steps:
                    lines = [line for line in lines if not clean(line).startswith('Overall - ')]
                if not active:
                    lines = []
                display.update(steps, lines)
            data = output.read(65536)
            if data:
                display.write(decoder.decode(data))
                continue
            if not active:
                display.write(decoder.decode(b'', final=True), final=True)
                if test_session:
                    result = run / 'result'
                    status = int(result.read_text()) if result.exists() else 1
                    if not result.exists():
                        display.write('\nTest owner stopped without a final result; run is incomplete.\n', saved=False)
                    (run / 'delivered').touch(mode=0o600)
                    return status
                result = run / 'result.json'
                if not result.exists():
                    display.write(f'\n{label}: worker ended without a result; inspect the saved handoff before restarting.\n', saved=False)
                    return 1
                return json.loads(result.read_text())['status']
            time.sleep(.1)
