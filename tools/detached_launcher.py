"""Shared detached workflow ownership, agent supervision and terminal rendering.

Specializations supply the worker command and workflow; locks, fresh agent
processes, transcript retention and cancellation use one implementation.
"""

from contextlib import contextmanager, nullcontext, ExitStack
from dataclasses import replace
import fcntl
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import sys
import time
import traceback
import uuid
from test_storage import scratch_descriptors
from agent_adapter import Delegation, SessionRequest, prepare_session

FRAME_DIRECTORY = 'ONPC_TEST_FRAME_DIRECTORY'
WORKFLOW_DIRECTORY = 'ONPC_WORKFLOW_DIRECTORY'
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


def accept_stop(run):
    """Commit a queued boundary stop atomically against --cancel-stop."""
    with lock(run / 'stop-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        if not (run / 'stop').exists():
            return False
        (run / 'stopping').touch(mode=0o600)
        return True


def clear_stop_request(run):
    with lock(run / 'stop-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        if any((run / marker).exists() for marker in ('stopping', 'cancel', 'result.json')):
            raise ValueError('\033[31mLauncher is already stopping and is not cancellable.\033[0m')
        (run / 'stop').unlink(missing_ok=True)
    print('Stop request cancelled.', flush=True)


def mark_stopping(run):
    """Close cancellation before terminal cleanup, including natural exits."""
    with lock(run / 'stop-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        (run / 'stopping').touch(mode=0o600)


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


def exception_details(error):
    """Bound diagnostic text without collecting frame locals or credentials."""
    trace = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
    if len(trace) > 32768:
        trace = '[Earlier traceback omitted under the diagnostic limit.]\n' + trace[-32768:]
    return dict(error=str(error)[-8192:], error_type=type(error).__name__,
                traceback=trace)


def record_exception(run, context, error, **identity):
    """Keep failures through transcript compaction and later cleanup errors."""
    details = exception_details(error)
    print(f'{context}: {details["traceback"]}', file=sys.stderr, flush=True)
    if run is not None:
        try:
            from watch_output import read_json
            with lock(run / 'controller-errors-gate') as gate:
                fcntl.flock(gate, fcntl.LOCK_EX)
                try:
                    records = read_json(run / 'controller-errors.json', 8 * 1024 * 1024)
                except FileNotFoundError:
                    records = []
                if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
                    raise ValueError('invalid controller error records')
                atomic(run / 'controller-errors.json', [*records[-15:],
                    dict(details, context=context, recorded_at=time.time(), **identity)])
        except (OSError, ValueError) as logging_error:
            print(f'Could not retain controller error: {logging_error}', file=sys.stderr, flush=True)
    return details


def owner_record(run, **fields):
    """Publish one clock origin per backend spawn, shared by all observers."""
    from vm_pool import VARIABLE
    if VARIABLE in os.environ:
        fields['vm_checkout'] = os.environ[VARIABLE]
    return dict(fields, run=run.name, started_at=time.time(), started_monotonic=time.monotonic())


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
    # Keep authentication, configuration and policy; discard launcher FD claims.
    # The concrete adapter also discards native conversation identities.
    result = dict(os.environ)
    for name in ('ONPC_TEST_ACTIVITY_FD', 'ONPC_TEST_HOST_ACTIVITY_FD', 'ONPC_TEST_COMPATIBILITY_FD', 'ONPC_REGRESSION_EVENTS',
                 'ONPC_REGRESSION_INVENTORY', 'ONPC_TEST_RETRY_CASE', 'ONPC_TEST_COMPLETED_CASES',
                 FRAME_DIRECTORY, WORKFLOW_DIRECTORY, 'ONPC_REPAIR_STARTUP_FD',
                 'ONPC_REPAIR_WRITER_FD', 'ONPC_REPAIR_RECOVERY_ONLY',
                 'ONPC_LAUNCHER_RELOAD_BASELINE', 'ONPC_VM_RELOAD_KEEPER'):
        result.pop(name, None)
    result['PYTHONUNBUFFERED'] = '1'
    # Internal runner calls, including inventory discovery before a repair
    # invocation exists, belong to this controller's checkout.
    result['ONPC_LAUNCHER_CONTROLLER_ROOT'] = str(Path(__file__).resolve().parents[1])
    from test_source import environment as source_environment, VARIABLE, WRITER
    result.pop(VARIABLE, None)
    result.pop(WRITER, None)
    result.update(source_environment())
    return result


SOURCE_DISCOVERY_INSTRUCTIONS = """Follow AGENTS.md and the source-discovery contract in
docs/Approval-Tools.md#source-discovery-before-reads. Before reading or searching
source/test contents, use exact paths from current instructions, resolved links
or earlier successful checkout reads. Discover any other filename first with
rg --files on a known directory and quoted --glob filters, or tools/read-only files.
Never infer test filenames from module/launcher names, task titles or memory.
Reuse observed paths without relisting them. If a reference is absent, inspect
its containing directory and relevant symbols; distinguish planned tests from
existing source and generated inputs. Do not create placeholders or suppress
missing-path errors. A batched lookup with any missing operand is incomplete:
correct the selection and rerun the affected lookup before relying on it.
Include this discovery requirement in every delegated assignment.

"""


TASK_TITLE_INSTRUCTIONS = """When creating or revising execution-plan tasks, write the
task title itself as a short, plain-language explanation of what the task achieves.
Use everyday words that make sense without technical background; keep commands,
paths, internal labels and implementation details in the brief. Use the same title
in the queue, master pointer and brief heading, preserving task IDs and file paths.
The shared launcher displays that title directly, with no separate Explanation
section. Do not generate separate task explanation metadata. Follow the title
contract in docs/Execution-Plans.md#plan-format.

"""


def agent_command(root, model, effort, run=None, *, schema=None, permissions='workspace',
                  delegation=Delegation(), standard_speed=False, shell_environment=(),
                  extra_directories=(), selection=None, logical_tier=None):
    """Prepare a typed session; callers never modify native command arguments."""
    return prepare_session(SessionRequest(root=root, model=model, effort=effort,
        run=run, schema=schema or Path(__file__).with_name('fix_tests_response.schema.json'),
        permissions=permissions, delegation=delegation, standard_speed=standard_speed,
        shell_environment=tuple(shell_environment), extra_directories=tuple(extra_directories),
        instructions=SOURCE_DISCOVERY_INSTRUCTIONS + TASK_TITLE_INSTRUCTIONS,
        selection=selection, logical_tier=logical_tier), environment())


def descriptive_output(run):
    """Publish a bounded copy of this session's prose in its owned allocation."""
    from launcher_progress import read_progress
    from launcher_render import retained_tail
    steps = read_progress(run)
    current = next((step for step in reversed(steps)
                    if not step.get('pinned') and not step.get('replaces')), None)
    record = {'session': uuid.uuid4().hex, 'progress_key': current['key'] if current else None,
              'lines': []}
    path = run / 'descriptive-output.json'
    atomic(path, record)

    def append(value, *, provisional=False):
        if provisional:
            record['stream'] = list(retained_tail(value.splitlines()))
        else:
            record.pop('stream', None)
            record['lines'] = list(retained_tail([*record['lines'], *value.splitlines()]))
        stream = record.get('stream', [])
        lines = list(retained_tail([*record['lines'], *stream]))
        # Keep one shared observer budget without letting temporary previews
        # evict the authoritative prose retained in memory.
        atomic(path, dict(record, lines=lines[:-len(stream)] if stream else lines))

    return append


def supervise(root, run, owner, kind, command, *, nested=False, hide_task_completion=False,
              on_usage=None, interactive=False, task=None, on_model=None, capacity_recovery=True,
              subagents_follow_model=False, session_state=None):
    """Apply capacity recovery once per logical session, for every agent transport.

    Ordinary plans retain their checkpointed controller loop and opt out here.
    The owner stays pinned across attempts; each child receives its own duplicate.
    """
    if kind != 'agent' or not capacity_recovery:
        return _supervise_once(root, run, owner, kind, command, nested=nested,
            hide_task_completion=hide_task_completion, on_usage=on_usage,
            interactive=interactive, task=task, session_state=session_state)
    from launcher_runtime import AgentCapacityUnavailable, capacity_failure
    configured_model = command.request.model
    failures = 0
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        while True:
            (run / 'agent-error.json').unlink(missing_ok=True)
            if on_model is not None:
                on_model(command.request.model)
            try:
                return _supervise_once(root, run, os.dup(owner), kind, command, nested=nested,
                    hide_task_completion=hide_task_completion, on_usage=on_usage,
                    interactive=interactive, task=task, session_state=session_state)
            except AgentCapacityUnavailable as error:
                failures += 1
                delay, fallback, exhausted = capacity_failure(configured_model, failures,
                    selection=command.request.selection)
                if exhausted:
                    raise AgentCapacityUnavailable('model capacity recovery exhausted: ' + str(error)) from error
                requested = False

                def stop(*_):
                    nonlocal requested
                    requested = True
                    (run / 'cancel').touch(mode=0o600)

                for sig in previous:
                    signal.signal(sig, stop)
                if fallback:
                    model = command.adapter.capacity_fallback(configured_model)
                    delegation = command.request.delegation
                    if subagents_follow_model:
                        delegation = replace(delegation, model=model)
                    command = command.revised(model=model, delegation=delegation)
                    command.preflight()
                    print(f'Model still at capacity; using {model} for this session only '
                          'with the same reasoning effort.', flush=True)
                else:
                    print(f'Model at capacity; retrying this session after {delay} seconds.', flush=True)
                deadline = time.monotonic() + delay
                # The parent's pipe remains a liveness lease during backoff.
                with selectors.DefaultSelector() as parent:
                    parent.register(sys.stdin, selectors.EVENT_READ)
                    while True:
                        if requested or (run / 'cancel').exists() or parent.select(0):
                            return 130
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            break
                        parent.select(min(.1, remaining))
                prompt = getattr(error, 'prompt', (run / 'prompt.txt').read_text())
                prompt += ('\n\nThe preceding attempt failed with an explicit model capacity error. '
                           'Inspect and reconcile partial work before continuing the same task. '
                           'Preserve unrelated work, acceptance requirements and all permission, '
                           'delegation and cleanup boundaries. No preceding result is accepted. '
                           f'The coordinator model for this attempt is {command.request.model}; '
                           'this overrides earlier coordinator model labels only. Reasoning effort '
                           'is unchanged. Any capacity fallback applies only to this logical session; '
                           'the next session returns to the configured model.\n')
                (run / 'prompt.txt').write_text(prompt)
                (run / 'agent-result.json').unlink(missing_ok=True)
                if nested:
                    atomic(run / 'nested.json', [])
                    (run / 'nested-closed').unlink(missing_ok=True)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        os.close(owner)


def _supervise_once(root, run, owner, kind, command, *, nested=False, hide_task_completion=False,
                    on_usage=None, interactive=False, task=None, session_state=None):
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
        # A capacity failure may already be unwinding through child cleanup.
        # Keep cancellation visible to the retry loop after this frame exits.
        (run / 'cancel').touch(mode=0o600)

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
    presentation = command.presentation if kind == 'agent' and not interactive else None
    if kind == 'agent' and not interactive and presentation is None:
        os.close(owner)
        raise ValueError('batch agent session requires a presentation decoder')
    renderer = None
    session_view = None
    session_transcript = None
    if kind == 'agent':
        from launcher_render import AgentRenderer, SessionTranscript
        from launcher_chat import task_message
        provenance = dict(agent=command.adapter.name, model=command.request.model,
                          effort=command.request.effort, logical_tier=command.request.logical_tier)
        usage_callback = on_usage
        if usage_callback is not None:
            on_usage = lambda usage: usage_callback(dict(usage or {}, **provenance))
        session_view = dict(session=uuid.uuid4().hex, status='running',
            started_at=time.time(), interactive=interactive,
            **provenance)
        if session_state is not None and 'repair_failure' in session_state:
            session_view.update(repair_failure=session_state['repair_failure'],
                                task_session=session_state['task_sessions'])
        view_path = run / 'session-view.json'
        previous_view = json.loads(view_path.read_text()) if view_path.exists() else {}
        session_transcript = SessionTranscript(sys.stdout, run,
            append=previous_view.get('continue_transcript') is True)
        renderer = AgentRenderer(session_transcript, command_log=run / 'agent-commands.log',
                                 full_command_output=True,
                                 hide_task_completion=hide_task_completion, on_usage=on_usage,
                                 on_description=descriptive_output(run),
                                 on_message=(lambda text: task_message(run, task, text))
                                 if task is not None and not interactive else None)
    conversation = None
    if interactive:
        from launcher_chat import AppSession

        def interrupted_cleanup():
            if nested:
                finish_nested(root, run)
                with lock(run / 'nested-gate') as gate:
                    fcntl.flock(gate, fcntl.LOCK_EX)
                    atomic(run / 'nested.json', [])
                    (run / 'nested-closed').unlink(missing_ok=True)

        command = command.revised(interactive=True)
        conversation = AppSession(root, run, command, renderer, on_interrupted=interrupted_cleanup,
                                  session_state=session_state)
    source = (run / 'prompt.txt').open('rb') if kind == 'agent' and not interactive else None
    log = (run / 'last-test.log').open('wb') if kind != 'agent' else None
    child_env = dict(command.environment) if kind == 'agent' else environment()
    from test_source import environment as source_environment
    child_env.update(source_environment())
    if nested:
        child_env[WORKFLOW_DIRECTORY] = str(run)
    if kind != 'agent':
        child_env[FRAME_DIRECTORY] = str(run)
    try:
        child = subprocess.Popen(command.argv if kind == 'agent' else command,
                                 cwd=command.cwd if kind == 'agent' else root, env=child_env,
                                 stdin=subprocess.PIPE if interactive else source if source is not None else subprocess.DEVNULL,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE if renderer else subprocess.STDOUT,
                                 start_new_session=True,
                                 pass_fds=scratch_descriptors())
    except Exception as error:
        record_exception(run, f'{kind} spawn', error)
        if source is not None:
            source.close()
        if log is not None:
            log.close()
        raise
    if source is not None:
        source.close()
    descriptor = None
    try:
        if session_view is not None:
            atomic(run / 'session-view.json', session_view)
        descriptor = os.pidfd_open(child.pid)
        sent = None
        finished_at = None
        input_registered = False
        if conversation:
            os.set_blocking(child.stdin.fileno(), False)
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
                if conversation and not requested and not conversation.done:
                    conversation.poll()
                if conversation and not requested and not child.stdin.closed and not exited:
                    if conversation.done:
                        if input_registered:
                            poller.unregister(child.stdin)
                            input_registered = False
                        child.stdin.close()
                        finished_at = time.monotonic()
                    elif conversation.outgoing and not input_registered:
                        poller.register(child.stdin, selectors.EVENT_WRITE, 'input')
                        input_registered = True
                if finished_at is not None and time.monotonic() - finished_at >= AGENT_GRACE:
                    os.killpg(child.pid, signal.SIGTERM if time.monotonic() - finished_at < 2 * AGENT_GRACE else signal.SIGKILL)
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
                    if key.data == 'input':
                        try:
                            written = os.write(key.fd, conversation.outgoing)
                            del conversation.outgoing[:written]
                        except BlockingIOError:
                            continue
                        except BrokenPipeError as error:
                            raise ValueError('Agent conversation input closed before a workflow result; '
                                             'see retained output') from error
                        if not conversation.outgoing:
                            poller.unregister(key.fileobj)
                            input_registered = False
                    elif key.data == 'parent':
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
                            if presentation and key.data == 'output':
                                for event in presentation.finish():
                                    renderer.event(event)
                            continue
                        if log is not None:
                            log.write(data)
                            log.flush()
                        if renderer and key.data == 'output':
                            if conversation:
                                conversation.feed(data)
                            else:
                                for event in presentation.feed(data):
                                    renderer.event(event)
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
        if conversation and conversation.done and finished_at is not None and status in (
                -signal.SIGTERM, -signal.SIGKILL):
            status = 0  # The result was accepted before bounded server shutdown.
        if renderer and (run / 'agent-commands.log').exists():
            compact_log(run / 'agent-commands.log')
        nested_active = nested and finish_nested(root, run)
        if renderer and not conversation and status and not requested:
            from launcher_runtime import AgentCapacityUnavailable
            error = renderer.failure
            if error is not None and error['capacity']:
                message = str(error.get('message', 'Model at capacity'))
                atomic(run / 'agent-error.json', dict(message=message, context=error['context'],
                                                     **error['details']))
                raise AgentCapacityUnavailable(message)
        if nested_active:
            status = status or 1
        if conversation and not requested and not conversation.done and status == 0:
            raise ValueError('Agent conversation ended without a workflow result; see retained output')
        return 130 if requested else status if status >= 0 else 128 - status
    except Exception as error:
        from launcher_reload import ReloadRequested
        if not isinstance(error, (Stopped, ReloadRequested)):
            record_exception(run, f'{kind} supervision', error)
        raise
    finally:
        # Failure while supervising must not release ownership over a live child.
        if child.returncode is None:
            if kind == 'agent':
                os.killpg(child.pid, signal.SIGKILL)
            else:
                child.send_signal(signal.SIGINT)
            if child.stdin is not None and child.stdin.closed:
                child.stdin = None
            child.communicate()
        child.stdout.close()
        if child.stdin is not None:
            child.stdin.close()
        if child.stderr is not None:
            child.stderr.close()
        if descriptor is not None:
            os.close(descriptor)
        if log is not None:
            log.close()
            atomic(run / 'frame.json', [])
        try:
            if nested:
                finish_nested(root, run)  # Exceptions, rather than active owners, mean cleanup failed.
            if conversation:
                conversation.clear_preview()
        finally:
            try:
                if session_view is not None:
                    session_transcript.close()
                    atomic(run / 'session-view.json', dict(session_view, status='finished'))
            finally:
                os.close(owner)


def _start_record(path, *, private=True):
    """Read bounded caller-owned metadata without following replacements.

    Startup and resolver receipts require 0600. Legacy pipeline metadata uses
    atomic() and the caller's umask, protected by its private parent directory.
    """
    if not private:
        private_directory(path.parent)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or private and stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1
                or info.st_size > 16384):
            raise ValueError(f'unsafe workflow record: {path}')
        return json.loads(os.read(fd, 16385))
    finally:
        os.close(fd)


def _publish_start(path, value):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        temporary.unlink(missing_ok=True)


def _start_source(directory):
    path = directory / 'current.json'
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None, None
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_nlink != 1 or info.st_size > 16384):
            raise ValueError('unsafe workflow start source')
        raw = os.read(fd, 16385)
        return json.loads(raw), hashlib.sha256(raw).hexdigest()
    finally:
        os.close(fd)


def _clear_start(path):
    path.unlink()
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def _start_retention_source(store, directory, source_run):
    """Bind legacy journal tokens separately from their allocation names."""
    import test_retention as retention
    if source_run is not None and (not isinstance(source_run, str) or len(source_run) != 32
            or any(c not in '0123456789abcdef' for c in source_run)):
        raise ValueError('workflow source allocation label is invalid')
    if not store.path.exists():
        if source_run is not None:
            raise ValueError('workflow source has no retained allocation identity')
        return None, None
    with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False):
        with store.locked(fd, 'writer.lock'):
            state = store.read(fd)
            retention.finished_owner(fd, state)
            if state is None:
                if source_run is not None:
                    raise ValueError('workflow source has no retained allocation identity')
                return None, None
            records = [record for record in state['paths']
                       if record['path'] == str(directory / source_run)] if source_run else []
            if len(records) != 1 or state['paths'] != records:
                raise ValueError('workflow source is not the current retained allocation; preserve evidence')
            retention.remove(records[0], validate_only=True)
            return state['run'], records[0]


def _validate_start(directory, pending):
    if (not isinstance(pending, dict) or set(pending) != {
            'version', 'run', 'device', 'inode', 'source_run', 'source_sha256',
            'source_retention_run', 'source_allocation', 'phase', 'published_record'} or pending['version'] != 1
            or not isinstance(pending['run'], str) or len(pending['run']) != 32
            or any(c not in '0123456789abcdef' for c in pending['run'])
            or pending['phase'] not in ('allocated', 'registered', 'ready')):
        raise ValueError('invalid pending workflow start identity')
    run = directory / pending['run']
    info = run.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700
            or (info.st_dev, info.st_ino) != (pending['device'], pending['inode'])):
        raise ValueError('pending workflow start directory identity changed')
    source, checksum = _start_source(directory)
    if source is not None and source.get('run') == run.name:
        if pending['phase'] != 'ready' or source != pending['published_record']:
            raise ValueError('pending workflow publication identity changed')
        return run, True
    if checksum != pending['source_sha256'] or (source or {}).get('run') != pending['source_run']:
        raise ValueError('pending workflow source owner changed')
    return run, False


def _audit_start(store, directory, pending):
    """Audit the entire journal before session() can prune any source proof."""
    import test_retention as retention
    with store.opened() as fd, store.locked(fd, 'writer.lock'):
        state = store.read(fd)
        if state is None:
            if pending['source_retention_run'] is not None or pending['phase'] != 'allocated':
                raise ValueError('pending workflow retention journal is missing')
            return
        if state['run'] not in (pending['run'], pending['source_retention_run']):
            raise ValueError('pending workflow retention owner changed')
        expected = dict(path=str(directory / pending['run']), device=pending['device'],
                        inode=pending['inode'], mode=0o700)
        if state['run'] == pending['run'] and state['paths'] not in ([], [expected]):
            raise ValueError('pending workflow has foreign registered allocations')
        if (state['run'] == pending['source_retention_run']
                and state['paths'] != [pending['source_allocation']]):
            raise ValueError('pending workflow retained source identity changed')
        allocations = retention.latest_allocations([*state['history'], state])
        source = pending['source_allocation']
        if source is not None and (source not in [record for _, record in allocations]
                                   or not Path(source['path']).exists()):
            raise ValueError('pending workflow retained source is missing or replaced')
        allocated = 0
        for _, record in allocations:
            path = Path(record['path'])
            if (path.parent != directory or len(path.name) != 32
                    or any(c not in '0123456789abcdef' for c in path.name)):
                raise ValueError('pending workflow retention contains a foreign allocation')
            retention.remove(record, validate_only=True)
            allocated += retention.allocation_bytes(record)
        if allocated > retention.MAX_RETAINED_BYTES:
            raise ValueError('pending workflow exceeds retention budget; source evidence preserved')


def select(root, name, command, *, stop=False, cancel_stop=False, stop_marker='cancel',
           on_attach=None, on_start=None, namespace=None, resumable_start=False,
           reload=False, existing_only=False, launcher_name=None, public_argv=None, stop_argv=None,
           add_session=None, source_resume=False):
    """Attach before evaluating new options; only the lock grants ownership."""
    from test_storage import directory as storage_directory
    directory = storage_directory(name, root=root)
    if namespace is not None:
        if name != 'plans' or len(namespace) != 64 or any(c not in '0123456789abcdef' for c in namespace):
            raise ValueError('invalid plan workflow namespace')
        directory = private_directory(directory / namespace)
    import test_source
    source_participant = name in ('fix-tests', 'fix-tests-host')
    if source_participant:
        test_source.finish_admission()
    with lock(directory / 'gate') as gate, lock(directory / 'owner') as owner, ExitStack() as source:
        fcntl.flock(gate, fcntl.LOCK_EX)
        if source_participant:
            controls = ['--stop'] if stop else ['--reload'] if reload else ['--resume'] if source_resume else []
            source.enter_context(test_source.startup(root, controls, repair=True, wait=False))
        if busy(owner):
            run = current_run(directory)
            if run is None:
                raise ValueError(f'active {name} owner has no readable run record')
            record = json.loads((directory / 'current.json').read_text())
            if cancel_stop:
                expected = os.environ.get('ONPC_CANCEL_STOP_RUN')
                if expected is not None and expected != str(run):
                    raise ValueError('Launcher changed; refresh before trying again.')
                if not record.get('cancel_stop'):
                    raise ValueError('\033[31mLauncher is already stopping or does not support stop cancellation.\033[0m')
                # The directory gate pins current.json; the run gate serializes
                # removal with the worker committing its boundary stop.
                clear_stop_request(run)
                return run, False
            if not stop and name in ('fix-tests', 'write-e2e', 'plans'):
                from vm_pool import check_attachment
                check_attachment(record)
            if add_session is not None:
                expected = os.environ.get('ONPC_ADD_SESSION_RUN')
                if expected is not None and expected != str(run):
                    raise ValueError('Launcher changed; refresh before trying again.')
            if on_attach is not None:
                on_attach(run)
            if add_session is not None:
                from launcher_runtime import SessionAllowance
                limit = SessionAllowance(run).add(add_session)
                print(f'{name}: session allowance is now {limit}.', flush=True)
            if not stop:
                # Control-only attachments keep the published public launcher,
                # which can differ from the storage namespace.
                atomic(directory / 'current.json', dict(
                    record, launcher=launcher_name or record.get('launcher') or name))
            if stop:
                with lock(run / 'stop-gate') as stop_gate:
                    fcntl.flock(stop_gate, fcntl.LOCK_EX)
                    (run / stop_marker).touch(mode=0o600)
            elif reload:
                from launcher_reload import request
                request(run)
                print(f'{name}: reload requested; continuing the same run.', flush=True)
            return run, False
        if add_session is not None:
            raise ValueError('--add-session requires a running launcher')
        if stop or cancel_stop or existing_only:
            return None, False
        if source_participant and reload:
            test_source.restart_execution()
        pending_path = directory / 'pending-start.json'
        pending = None
        if not resumable_start and os.path.lexists(pending_path):
            raise ValueError('pending workflow start requires its resumable controller')
        if resumable_start and os.path.lexists(pending_path):
            pending = _start_record(pending_path)
            run, published = _validate_start(directory, pending)
            if published:
                import test_retention
                store = test_retention.Store(directory / 'retention')
                with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False):
                    _audit_start(store, directory, pending)
                _clear_start(pending_path)
                return run, False  # Never spawn a possibly already published worker twice.
        else:
            # Attachments, controls and pending-start recovery stay unchanged.
            # Sync a new run before constructing its job or prerequisites.
            source.close()
            from launcher_controller import sync_startup
            sync_startup(root, current_run(directory))
            if source_participant:
                source.enter_context(test_source.startup(root, controls, repair=True, wait=False))
            run = directory / uuid.uuid4().hex
        # Validate and resolve prerequisites before allocating a new run.
        argv = command(run, owner)
        private_directory(run)
        import test_retention
        store = test_retention.Store(directory / 'retention')
        if resumable_start and pending is None:
            source, checksum = _start_source(directory)
            source_retention_run, source_allocation = _start_retention_source(
                store, directory, (source or {}).get('run'))
            info = run.stat()
            pending = dict(version=1, run=run.name, device=info.st_dev, inode=info.st_ino,
                           source_run=(source or {}).get('run'), source_sha256=checksum,
                           source_retention_run=source_retention_run, source_allocation=source_allocation,
                           phase='allocated', published_record=None)
            _publish_start(pending_path, pending)
        guard = (lambda: _audit_start(store, directory, pending)) if resumable_start else None
        recover = (lambda state: state['run'] == pending['run']) if resumable_start else None
        with store.session(run=run.name if resumable_start else None, guard=guard, recover=recover):
            test_retention.retain(run)
        if resumable_start:
            pending['phase'] = 'registered'
            _publish_start(pending_path, pending)
        if on_start is not None:
            on_start(run)
        if resumable_start:
            _validate_start(directory, pending)
            with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False):
                _audit_start(store, directory, pending)
        fcntl.flock(owner, fcntl.LOCK_EX)
        published_record = owner_record(run, launcher=launcher_name or name,
                                       argv=list(sys.argv[1:] if public_argv is None else public_argv))
        published_record['cancel_stop'] = stop_marker == 'stop'
        if stop_argv is not None:
            published_record['stop_argv'] = list(stop_argv)
        if resumable_start:
            # Output exists before current publication so a ready interruption
            # remains inspectable, but can contain no worker bytes yet.
            try:
                output_fd = os.open(run / 'output', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            except FileExistsError:
                output_fd = os.open(run / 'output', os.O_WRONLY | os.O_NOFOLLOW)
                info = os.fstat(output_fd)
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                        or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1 or info.st_size):
                    os.close(output_fd)
                    raise ValueError('pending workflow output identity changed')
            try:
                pending.update(phase='ready', published_record=published_record)
                _publish_start(pending_path, pending)
                _publish_start(directory / 'current.json', published_record)
                _clear_start(pending_path)
            except BaseException:
                os.close(output_fd)
                raise
            output_context = os.fdopen(output_fd, 'wb')
        else:
            atomic(directory / 'current.json', published_record)
            output_context = (run / 'output').open('xb')
        with output_context as output:
            from launcher_reload import ReloadRequest
            import test_source
            # Fresh repair workers must import under the exact retained writer
            # before their normal FIFO recovery transfers ownership to this run.
            with (test_source.startup(root, ['--resume'], repair=True)
                  if name in ('fix-tests', 'fix-tests-host') else nullcontext()):
                child_environment = environment()
                if name in ('fix-tests', 'fix-tests-host'):
                    descriptor = child_environment.pop(test_source.VARIABLE, None)
                    child_environment.pop(test_source.WRITER, None)
                    if descriptor is not None:
                        child_environment['ONPC_REPAIR_STARTUP_FD'] = descriptor
                ReloadRequest(run).inherit(child_environment)
                try:
                    subprocess.Popen(argv, cwd=root, env=child_environment, stdin=subprocess.DEVNULL,
                                     stdout=output, stderr=subprocess.STDOUT, start_new_session=True,
                                     pass_fds=(owner, *scratch_descriptors()))
                except Exception as error:
                    record_exception(run, 'Controller spawn', error)
                    raise
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
    if parent.name == 'worktree-resolution':
        with worktree_resolution_owner(root, parent):
            _register_nested(parent, child_run)
            yield
        return
    plan_owner = (parent.parent.parent == directory('plans', root=root)
                  and len(parent.parent.name) == 64
                  and all(c in '0123456789abcdef' for c in parent.parent.name))
    if (parent.parent != directory('write-e2e', root=root) and not plan_owner) or (
            len(parent.name) != 32 or any(c not in '0123456789abcdef' for c in parent.name)):
        raise ValueError('invalid workflow owner directory')
    private_directory(parent)
    with lock(parent / 'nested-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        with lock(parent.parent / 'owner') as owner:
            if (not busy(owner) or current_run(parent.parent) != parent
                    or (parent / 'cancel').exists() or (parent / 'nested-closed').exists()):
                raise ValueError('workflow owner is no longer accepting test operations')
        _register_nested(parent, child_run)
        yield


def _register_nested(parent, child_run):
    """Register under the caller's held nested gate and authenticated owner."""
    record = parent / 'nested.json'
    entries = json.loads(record.read_text()) if record.exists() else []
    info = child_run.stat()
    entries.append({'path': str(child_run), 'device': info.st_dev, 'inode': info.st_ino})
    atomic(record, entries)


def propagation_source_run(root, source):
    """Resolve a VM pipeline's live workflow without moving its Git checkpoint."""
    from test_storage import directory
    if source.parent.parent == directory('fix-tests', root=root):
        private_directory(source)
        binding = _start_record(source / 'vm.json', private=False)['vm']
        name = 'host' if binding is None else binding
        expected = 'pipeline-' + hashlib.sha256(name.encode()).hexdigest()[:24]
        if (source.name != expected or
                _start_record(source / 'pipeline.json', private=False)['parent'] != str(source.parent)):
            raise ValueError('invalid propagation pipeline identity')
        return source.parent
    return source


@contextmanager
def worktree_resolution_owner(root, session):
    """Authenticate a destination resolver against its live source launcher.

    This child is inside the source's retained allocation, while its tests belong
    to the destination checkout. Neither directory names nor a live PID suffice.
    """
    from test_storage import directory
    private_directory(session)
    record = _start_record(session / 'propagation-owner.json')
    source, source_root = Path(record['run']), Path(record['root'])
    workflow = propagation_source_run(source_root, source)
    if session != source / 'worktree-resolution' or str(root.resolve()) != record['destination']:
        raise ValueError('worktree resolution checkout identity changed')
    plan_owner = (workflow.parent.parent == directory('plans', root=source_root)
                  and len(workflow.parent.name) == 64
                  and all(c in '0123456789abcdef' for c in workflow.parent.name))
    if (not plan_owner and workflow.parent not in tuple(directory(kind, root=source_root)
            for kind in ('write-e2e', 'fix-tests', 'fix-tests-host', 'sync-whatsnew'))):
        raise ValueError('invalid propagation source launcher')
    private_directory(source)
    info = source.stat()
    if [info.st_dev, info.st_ino] != record['identity']:
        raise ValueError('propagation source directory identity changed')
    with lock(session / 'nested-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        with lock(workflow.parent / 'owner') as source_owner, lock(session / 'owner') as owner:
            info = os.fstat(source_owner)
            if ([info.st_dev, info.st_ino] != record['owner_identity'] or not busy(source_owner)
                    or not busy(owner) or current_run(workflow.parent) != workflow
                    or (source / 'cancel').exists() or (workflow / 'cancel').exists()
                    or (session / 'cancel').exists()
                    or (session / 'nested-closed').exists()):
                raise ValueError('propagation source no longer accepts test operations')
            checkpoint_name = record.get('checkpoint', 'checkpoint.json')
            if checkpoint_name not in ('checkpoint.json', 'translation-state.json'):
                raise ValueError('invalid propagation checkpoint')
            checkpoint = json.loads((source / checkpoint_name).read_text())
            if record.get('pull'):
                checkpoint = checkpoint.get('upstream_pull', {})
            targets = checkpoint.get('worktree_propagation', {}).get('targets', [])
            if not any(item['path'] == str(root.resolve()) and item.get('phase') in
                       ('upstream', 'merge', 'restoring') for item in targets):
                raise ValueError('destination has no retained propagation transaction')
            yield


def nested_runs(root, run):
    """Resolve registered test runs with the shared path and identity guards."""
    from test_storage import directory
    record = run / 'nested.json'
    entries = json.loads(record.read_text()) if record.exists() else []
    allowed = (directory('sessions', root=root), directory('sessions-host', root=root))
    for entry in entries:
        child = Path(entry['path'])
        vm_session = (child.parent.parent == allowed[0]
                      and child.parent.name.startswith('vm-')
                      and not child.parent.is_symlink())
        if child.parent not in allowed and not vm_session or child.is_symlink():
            raise ValueError('unsafe nested test record; preserve evidence')
        try:
            info = child.stat()
        except FileNotFoundError:
            continue
        if (info.st_dev, info.st_ino) != (entry['device'], entry['inode']):
            raise ValueError('nested test identity changed; preserve evidence')
        yield child


def finish_nested(root, run):
    """Cancel only registered live test owners and await their guarded cleanup."""
    active = False
    with lock(run / 'nested-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        (run / 'nested-closed').touch(mode=0o600)
        for child in nested_runs(root, run):
            with lock(child / 'owner') as owner:
                if busy(owner):
                    active = True
                    (child / 'cancel').touch(mode=0o600)
                    print('launcher: waiting for owned test cleanup.', flush=True)
                    while busy(owner):
                        time.sleep(.1)
    return active


def finish_shutdown(root, run, *, restore_vms=True):
    """Join owned tests, then restore the stopped workflow's entire VM selection."""
    stopped = accept_stop(run)
    finish_nested(root, run)
    if not restore_vms or not (stopped or (run / 'cancel').exists()):
        return
    path = run / 'vm.json'
    # vm.json uses the existing save_binding/check_binding metadata contract;
    # unlike private startup receipts, older records use the caller's umask.
    record = json.loads(path.read_text()) if path.exists() else {'vm': None}
    if not isinstance(record, dict) or set(record) != {'vm'}:
        raise ValueError('invalid shutdown VM binding; preserve recovery records')
    binding = record['vm']
    if binding is None:
        return  # Host-only workflows must not acquire or change a VM.
    names = binding.get('vms') if isinstance(binding, dict) else [binding]
    if (not isinstance(names, list) or not names
            or any(not isinstance(name, str) or not name for name in names)):
        raise ValueError('invalid shutdown VM selection; preserve recovery records')
    # Cleanup is serial and uses the existing snapshot/instance ownership guards.
    # The recovery route borrows an enclosing checkout, or tries each VM's,
    # and waits for baseline restoration before checkin. Do not inherit the stop request
    # as cancellation of this recovery or register it as new agent-owned work.
    selection = ','.join(dict.fromkeys(names))
    print(f'launcher: restoring VMs to baseline before shutdown: {selection}.', flush=True)
    from vm_pool import Busy
    for name in dict.fromkeys(names):
        status = subprocess.run([str(root / 'tools/cleanup-e2e'), '--vm', name, '--if-available'],
                                cwd=root, env=environment(), stdin=subprocess.DEVNULL,
                                pass_fds=scratch_descriptors(), check=False).returncode
        if status == Busy.status:
            print(f'launcher: {name} is busy; recovery deferred to the next run. '
                  'Leaving the current VM owner untouched.', flush=True)
        elif status:
            raise ValueError(f'launcher: baseline cleanup failed (status={status}); '
                             'preserve recovery records and resume cleanup')


def report_start(run, *, label='launcher', started=False, stop=False, reload=False, stream=None):
    """Report controller admission, never the eventual workflow verdict."""
    action = ('stop requested for' if stop else 'reload requested for' if reload
              else 'started' if started else 'already running')
    print(f'\033[32m{label}: controller {action}: {run.name}.\033[0m '
          'Open ONPC: Watch to attach at any time.', file=stream or sys.stdout, flush=True)
    return 0
