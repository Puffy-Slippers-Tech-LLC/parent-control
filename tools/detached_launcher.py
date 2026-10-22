"""Shared detached workflow ownership, Codex transport and terminal rendering.

Specializations supply the worker command and workflow; locks, fresh agent
processes, transcript retention and cancellation use one implementation.
"""

from contextlib import contextmanager
import codecs
import fcntl
import hashlib
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
    # Keep authentication, configuration and policy; discard inherited thread
    # identities and launcher FD claims. No parent conversation is ever passed.
    result = dict(os.environ)
    for name in ('CODEX_THREAD_ID', 'CODEX_PARENT_THREAD_ID', 'CODEX_SESSION_ID',
                 'ONPC_TEST_ACTIVITY_FD', 'ONPC_TEST_HOST_ACTIVITY_FD', 'ONPC_REGRESSION_EVENTS',
                 'ONPC_REGRESSION_INVENTORY', FRAME_DIRECTORY, WORKFLOW_DIRECTORY):
        result.pop(name, None)
    result['PYTHONUNBUFFERED'] = '1'
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


SUBAGENT_CONTEXT_INSTRUCTIONS = """This launcher coordinator is ephemeral and has no
stored rollout to fork. On every spawn_agent call, explicitly set fork_turns="none".
Never omit fork_turns or use "all": copying the coordinator's stored conversation
can fail with "no rollout found". Give every helper a self-contained assignment
with its exact scope, paths, relevant instructions, current evidence and disjoint
write ownership. This applies to workers, monitors, advisers and backend reviewers;
it does not authorize delegation beyond the launcher's existing policy.

"""


BACKEND_REVIEW_INSTRUCTIONS = """For product backend code involving core functionalities,
AGENTS.md requires an independent code review by the backend_reviewer agent
(GPT-6 Astra xHigh) before completing the changes. This mandate applies across
all launchers, including repair, recovery and optimization sessions. It overrides
Sol-only and no-delegation rules only for this required review; keep the launcher's
existing coordinator, implementation, consultation and escalation model policy.
Do not request this review for changes outside core backend code. Give the reviewer
the exact owned changes, relevant source/contracts and validation evidence in a
fresh context. Pause implementation while it reviews; wait for its findings and
close it before resuming. Resolve actionable findings and revalidate material
revisions; obtain a fresh review of material backend revisions before completion.
Record the review findings and resolution in the existing summary or handoff.
A missing or failed review is incomplete work, never a completed change; use the
launcher's existing continuation or blocker route. Review gives no test or installed
acceptance credit. The reviewer cannot implement, test, control resources or delegate.
"""


def agent_command(root, model, effort, run=None, *, schema=None, adviser_config=None, delegation=False):
    codex = shutil.which('codex')
    if codex is None:
        raise ValueError('Codex CLI is missing; install and authenticate it before running this launcher')
    command = [codex, '--ask-for-approval', 'never', 'exec', '--ephemeral',
            '--sandbox', 'workspace-write', '--model', model,
            '-c', f'model_reasoning_effort="{effort}"',
            '-c', 'history.persistence="none"', '-c', 'features.memories=false',
            '-c', 'features.multi_agent=true',
            '-c', 'features.multi_agent_v2=false',
            '-c', 'agents.enabled=true',
            '-c', 'developer_instructions=' + json.dumps(
                SOURCE_DISCOVERY_INSTRUCTIONS + SUBAGENT_CONTEXT_INSTRUCTIONS
                + BACKEND_REVIEW_INSTRUCTIONS),
            '-c', 'agents.backend_reviewer.description="Mandatory independent review of core backend changes only; no implementation"',
            '-c', 'agents.backend_reviewer.config_file=' + json.dumps(str(Path(__file__).with_name('backend_reviewer.toml'))),
            '--json', '--color', 'never', '--cd', str(root)]
    if adviser_config is None and not delegation:
        # Review-only access does not enable ordinary worker/adviser delegation.
        command += ['-c', 'agents.max_concurrent_threads_per_session=1',
                    '-c', 'agents.max_depth=1']
    if adviser_config is not None:
        # V1 supports a depth bound. One child slot plus the coordinator's
        # wait/close protocol keeps consultations sequential.
        command += ['-c', 'agents.max_concurrent_threads_per_session=1',
                    '-c', 'agents.max_depth=1',
                    '-c', 'agents.default_subagent_model="gpt-6.1-sol"',
                    '-c', 'agents.default_subagent_reasoning_effort="max"',
                    '-c', 'agents.e2e_adviser.description="Bounded read-only diagnosis or review; no implementation or tests"',
                    '-c', 'agents.e2e_adviser.config_file=' + json.dumps(str(adviser_config))]
    if delegation:
        if adviser_config is None:
            command += ['-c', 'agents.max_concurrent_threads_per_session=3', '-c', 'agents.max_depth=1',
                    '-c', 'agents.default_subagent_model="gpt-6.1-sol"',
                    '-c', 'agents.default_subagent_reasoning_effort="medium"']
        command += ['-c', 'agents.plan_monitor.description="Routine read-only monitoring; no resource ownership or mutations"',
                    '-c', 'agents.plan_monitor.config_file=' + json.dumps(str(Path(__file__).with_name('plan_monitor.toml'))),
                    '-c', 'agents.plan_worker.description="Bounded routine work or coverage refresh on explicitly assigned files"',
                    '-c', 'agents.plan_worker.config_file=' + json.dumps(str(Path(__file__).with_name('plan_worker.toml')))]
    if run is not None:
        command += ['--output-schema', str(schema or Path(__file__).with_name('fix_tests_response.schema.json')),
                    '--output-last-message', str(run / 'agent-result.json')]
    return [*command, '-']


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

    def append(value):
        record['lines'] = list(retained_tail([*record['lines'], *value.splitlines()]))
        atomic(path, record)

    return append


def supervise(root, run, owner, kind, command, *, nested=False, hide_task_completion=False,
              on_usage=None, interactive=False, task=None):
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
        from launcher_chat import task_message
        renderer = AgentRenderer(sys.stdout, command_log=run / 'agent-commands.log',
                                 hide_task_completion=hide_task_completion, on_usage=on_usage,
                                 on_description=descriptive_output(run),
                                 on_message=(lambda text: task_message(run, task, text))
                                 if task is not None and not interactive else None)
    conversation = None
    if interactive:
        from launcher_chat import AppSession, app_command

        def interrupted_cleanup():
            if nested:
                finish_nested(root, run)
                with lock(run / 'nested-gate') as gate:
                    fcntl.flock(gate, fcntl.LOCK_EX)
                    atomic(run / 'nested.json', [])
                    (run / 'nested-closed').unlink(missing_ok=True)

        conversation = AppSession(root, run, command, renderer, on_interrupted=interrupted_cleanup)
        command = app_command(command)
    source = (run / 'prompt.txt').open('rb') if kind == 'agent' and not interactive else None
    log = (run / 'last-test.log').open('wb') if kind != 'agent' else None
    child_env = environment()
    if nested:
        child_env[WORKFLOW_DIRECTORY] = str(run)
    if kind != 'agent':
        child_env[FRAME_DIRECTORY] = str(run)
    child = subprocess.Popen(command, cwd=root, env=child_env,
                             stdin=subprocess.PIPE if interactive else source if source is not None else subprocess.DEVNULL,
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
                            raise ValueError('Codex conversation input closed before a workflow result; '
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
                            if renderer and key.data == 'output':
                                renderer.finish()
                            continue
                        if log is not None:
                            log.write(data)
                            log.flush()
                        if renderer and key.data == 'output':
                            if conversation:
                                conversation.feed(data)
                            else:
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
        if conversation and conversation.done and finished_at is not None and status in (
                -signal.SIGTERM, -signal.SIGKILL):
            status = 0  # The result was accepted before bounded server shutdown.
        if renderer and (run / 'agent-commands.log').exists():
            compact_log(run / 'agent-commands.log')
        if nested and finish_nested(root, run):
            status = status or 1
        if conversation and not requested and not conversation.done:
            raise ValueError('Codex conversation ended without a workflow result; see retained output')
        return 130 if requested else status if status >= 0 else 128 - status
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
                finish_nested(root, run)
        finally:
            os.close(owner)


def _start_record(path):
    """Read a finite private startup identity without following replacements."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1
                or info.st_size > 16384):
            raise ValueError('unsafe pending workflow start record')
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


def select(root, name, command, *, stop=False, stop_marker='cancel',
           on_attach=None, on_start=None, on_prepare=None, namespace=None, resumable_start=False):
    """Attach before evaluating new options; only the lock grants ownership."""
    from test_storage import directory as storage_directory
    directory = storage_directory(name, root=root)
    if namespace is not None:
        if name != 'plans' or len(namespace) != 64 or any(c not in '0123456789abcdef' for c in namespace):
            raise ValueError('invalid plan workflow namespace')
        directory = private_directory(directory / namespace)
    with lock(directory / 'gate') as gate, lock(directory / 'owner') as owner:
        fcntl.flock(gate, fcntl.LOCK_EX)
        if busy(owner):
            run = current_run(directory)
            if run is None:
                raise ValueError(f'active {name} owner has no readable run record')
            if not stop and name in ('fix-tests', 'write-e2e', 'plans'):
                from vm_pool import check_attachment
                check_attachment(json.loads((directory / 'current.json').read_text()))
            if on_attach is not None:
                on_attach(run)
            if stop:
                (run / stop_marker).touch(mode=0o600)
            return run, False
        if stop:
            return None, False
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
            run = directory / uuid.uuid4().hex
        if on_prepare is not None:
            on_prepare(run)
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
        published_record = owner_record(run)
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
    if session != source / 'worktree-resolution' or str(root.resolve()) != record['destination']:
        raise ValueError('worktree resolution checkout identity changed')
    plan_owner = (source.parent.parent == directory('plans', root=source_root)
                  and len(source.parent.name) == 64
                  and all(c in '0123456789abcdef' for c in source.parent.name))
    if (not plan_owner and source.parent not in tuple(directory(kind, root=source_root)
            for kind in ('write-e2e', 'fix-tests', 'fix-tests-host'))):
        raise ValueError('invalid propagation source launcher')
    private_directory(source)
    info = source.stat()
    if [info.st_dev, info.st_ino] != record['identity']:
        raise ValueError('propagation source directory identity changed')
    with lock(session / 'nested-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        with lock(source.parent / 'owner') as source_owner, lock(session / 'owner') as owner:
            info = os.fstat(source_owner)
            if ([info.st_dev, info.st_ino] != record['owner_identity'] or not busy(source_owner)
                    or not busy(owner) or current_run(source.parent) != source
                    or (source / 'cancel').exists() or (session / 'cancel').exists()
                    or (session / 'nested-closed').exists()):
                raise ValueError('propagation source no longer accepts test operations')
            checkpoint = json.loads((source / 'checkpoint.json').read_text())
            targets = checkpoint.get('worktree_propagation', {}).get('targets', [])
            if not any(item['path'] == str(root.resolve()) and item.get('phase') in
                       ('upstream', 'merge', 'restoring') for item in targets):
                raise ValueError('destination has no retained propagation transaction')
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
            vm_session = (child.parent.parent == allowed[0]
                          and child.parent.name.startswith('vm-')
                          and not child.parent.is_symlink())
            if child.parent not in allowed and not vm_session or child.is_symlink():
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


def follow(run, stream=None, *, label='launcher', view=None, display=None):
    from launcher_view import view_for
    stream = stream or sys.stdout
    view = view or view_for(label)
    if display is not None:
        return follow_output(run, stream, display, label=label, view=view)
    display = view.display(stream, run)
    with display:
        return follow_output(run, stream, display, label=label, view=view)


def follow_output(run, stream, display, *, label='launcher', test_session=False,
                  destination=None, owner_busy=None, view=None):
    from launcher_view import view_for
    from launcher_render import clean
    from watch_output import JsonReader, snapshot
    reader = JsonReader()
    view = view or view_for(label)
    decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
    forwarded = None
    with lock((run if test_session else run.parent) / 'owner') as owner, (run / 'output').open('rb') as output:
        offset = 0 if test_session else max(0, output.seek(0, os.SEEK_END) - TAIL_BYTES)
        output.seek(offset)
        if offset:
            output.readline()  # Reattach at a full line, not midway through UTF-8/ANSI.
        while True:
            if hasattr(display, 'refresh_chat'):
                display.refresh_chat()
            if view.questions:
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
            try:
                steps = snapshot(run / 'controller.json', steps=True, reader=reader)
                lines = snapshot(run / 'frame.json', reader=reader)
                if destination is None and steps is not None:
                    steps = view.progress(run, steps,
                        snapshot(run / 'test-controller.json', steps=True, reader=reader))
            except (OSError, ValueError, KeyError, TypeError):
                # Refused metadata must not prevent draining the complete log
                # or delivering the owner's final result. Never forward it.
                steps = lines = None
            if steps is None:
                if destination is None:
                    display.draw()
            elif destination is not None:
                if (steps, lines) != forwarded:
                    atomic(destination / 'frame.json', lines)
                    atomic(destination / 'test-controller.json', steps)
                    forwarded = (steps, lines)
            else:
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
