"""Persistent FIFO requests for public detached launchers."""

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import uuid

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from detached_launcher import _start_record, busy, current_run, durable_json, environment, lock
from test_storage import directory as storage_directory


FILE = 'queue.json'
LIMIT = 256 * 1024
ADMISSION_LIMIT = LIMIT - 16 * 1024  # Reserve room for the head ticket's diagnostic.
RETRY = 75
TOKEN = re.compile(r'[0-9a-f]{32}')
PROGRAM = re.compile(r'(?!\.{1,2}$)[\w.-]{1,100}')
REPLAY = 'ONPC_LAUNCHER_QUEUE_REPLAY'


def ticket_id(value):
    return isinstance(value, str) and TOKEN.fullmatch(value) is not None


def read(directory):
    try:
        value = _start_record(directory / FILE, limit=LIMIT)
    except FileNotFoundError:
        return dict(active=None, items=[])
    if not isinstance(value, dict) or 'active' not in value:
        raise ValueError('Invalid launcher queue.')
    active, items = value.get('active'), value.get('items')
    if (not isinstance(items, list) or active is not None and not (
            isinstance(active, dict) and ticket_id(active.get('run'))) or
            any(not isinstance(row, dict) or not ticket_id(row.get('id')) or
                not isinstance(row.get('program'), str) or not PROGRAM.fullmatch(row['program']) or
                not isinstance(row.get('branch'), str) or not isinstance(row.get('label'), str) or
                not isinstance(row.get('error', ''), str) or
                (row.get('resume') is not None and not isinstance(row['resume'], dict)) or
                not isinstance(row.get('args'), list) or any(not isinstance(arg, str) or '\0' in arg
                                                            for arg in row['args'])
                for row in items)):
        raise ValueError('Invalid launcher queue.')
    return value


def save(directory, state, *, limit=LIMIT):
    if len(json.dumps(state)) > limit:
        raise ValueError('Launcher queue is full. Remove a waiting ticket first.')
    durable_json(directory / FILE, state)


def session_scope(directory):
    return directory.name.startswith(('sessions', 'vm-'))


def current(directory):
    run = current_run(directory)
    owner = (run / 'owner' if run is not None else None) if session_scope(directory) else directory / 'owner'
    if owner is None:
        return run, False
    with lock(owner) as descriptor:
        return run, busy(descriptor)


def complete(directory, run):
    from watch_output import read_json
    path = directory / run
    try:
        if session_scope(directory):
            status = read_json(path / 'result')
            return (type(status) is int and status >= 0 and not (path / 'interrupted.json').exists()
                    and (status != 130 or (path / 'cancel').exists()))
        value = read_json(path / 'result.json')
        status = value.get('status') if isinstance(value, dict) else None
        return type(status) is int and status >= 0 and not value.get('interrupted')
    except (FileNotFoundError, ValueError):
        return False


def paused(directory, state, run, active):
    previous = state['active']
    return bool(previous and not (active and run and run.name == previous['run']) and
                not complete(directory, previous['run']))


def retire_completed(directory):
    """Forget a finished queue owner before an untracked start can prune it."""
    state = read(directory)
    if state['active'] is not None and complete(directory, state['active']['run']):
        state['active'] = None
        save(directory, state)


@contextmanager
def gate(directory, *, wait=True):
    with lock(directory / 'gate') as descriptor:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX if wait else fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('Launcher is handling another request. Refresh and try again.') from error
        yield


@contextmanager
def reset_gate(root, *, exclusive=False):
    with lock(reset_path(root)) as descriptor:
        fcntl.flock(descriptor, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield descriptor


def reset_path(root):
    return storage_directory('state', root=root) / 'queue-reset'


@dataclass(frozen=True)
class Receipt:
    ticket: str | None = None
    warning: str = ''

    def report(self, label, stream):
        if self.ticket:
            print(f'{label}: queued {self.ticket}.', file=stream, flush=True)
        if self.warning:
            print(f'{label}: {self.warning}', file=stream, flush=True)
        return 0


def replay_options():
    marker = json.loads(os.environ.get(REPLAY, 'null'))
    return marker[2] if marker is not None and len(marker) > 2 else {}


class Submission:
    """Called with the launcher's own gate held, before its normal start."""

    def __init__(self, root, directory, request, recovery):
        self.root, self.directory, self.request = root, directory, request
        self.recovery = recovery
        marker = os.environ.get(REPLAY)
        self.replay = json.loads(marker) if marker else None

    @classmethod
    def public(cls, root, directory, label=None):
        from launcher_controller import queue_invocation
        context = queue_invocation()
        if context is None:
            return None
        invocation, recovery = context
        return cls(root, directory, dict(program=invocation.name, branch=invocation.branch,
                                         args=invocation.arguments, label=label or invocation.name,
                                         **invocation.resolved), recovery)

    def admit(self, run, active):
        state = read(self.directory)
        waiting = state['items']
        interrupted = paused(self.directory, state, run, active)
        if self.replay is not None:
            if self.replay[0] != str(self.directory):
                raise ValueError('Queued command now resolves to a different launcher scope. Remove and resubmit it.')
            if not waiting or self.replay[1] != waiting[0]['id']:
                return Receipt()
            if active or interrupted:
                from launcher_controller import RetryQueuedStartup
                raise RetryQueuedStartup('The launcher scope is not ready for its next ticket.')
            self.previous_run = (_start_record(self.directory / 'current.json', private=False, limit=LIMIT)
                                 if run is not None else None)
            return None
        if active and not state['active']:
            if run is None:
                raise ValueError('Active launcher has no readable run record.')
            state['active'] = dict(run=run.name, ticket=None)
        if not active and (self.recovery == 'reset' or interrupted and self.recovery):
            return None
        if active or interrupted or waiting:
            ticket = uuid.uuid4().hex
            if len(json.dumps(self.request)) > 16 * 1024:
                raise ValueError('Queued command exceeds 16 KiB.')
            waiting.append(dict(self.request, id=ticket))
            save(self.directory, state, limit=ADMISSION_LIMIT)
            warning = 'Queue paused because the previous run was interrupted.' if interrupted else ''
            if not interrupted:
                warning = self.wake()
            return Receipt(ticket, warning)
        return None

    @contextmanager
    def starting(self, run):
        previous = read(self.directory)
        waiting = previous['items']
        ticket = waiting[0]['id'] if self.replay is not None else None
        remaining = waiting[1:] if ticket else waiting
        save(self.directory, dict(active=dict(run=run.name, ticket=ticket), items=remaining))
        try:
            yield
        except (OSError, ValueError):
            if ticket:
                # Popen reported a failed spawn. Restore the request and the
                # previous owner so the helper can report the error on its head.
                # A crash during spawn retains the newer, interrupted owner.
                current = self.directory / 'current.json'
                if self.previous_run is None:
                    current.unlink(missing_ok=True)
                else:
                    durable_json(current, self.previous_run)
                save(self.directory, previous)
            raise
        if self.replay is None and remaining:
            warning = self.wake()
            if warning:
                print(warning, file=sys.stderr, flush=True)

    def wake(self):
        try:
            wake(self.root, self.directory)
        except OSError as error:
            return f'Tickets are saved. Could not start the queue helper: {error}'
        return ''


def wake(root, directory):
    with lock(directory / 'queue-helper') as owner:
        try:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        import host_compute
        import test_source
        import vm_pool
        import watch_control
        from test_results import REPAIR_QUEUE, VARIABLE as REPAIR_RESULTS
        from vm_selection import BATCH, VARIABLE
        child_environment = environment()
        # Replay is independent of the caller that happened to wake the queue.
        for name in (test_source.VARIABLE, test_source.WRITER, test_source.IMPORTS,
                     test_source.STARTUP_READER, test_source.STARTUP_WRITER, BATCH, VARIABLE,
                     host_compute.VARIABLE, host_compute.TOKENS, vm_pool.VARIABLE, watch_control.VARIABLE,
                     REPAIR_QUEUE, REPAIR_RESULTS, 'ONPC_RUNNER_INVOCATION', 'ONPC_WATCH_RUN',
                     'ONPC_LAUNCHER_CONTROLLER_ROOT', 'ONPC_MAKE_VM', 'ONPC_E2E_VM',
                     'MAKELEVEL', 'MAKEFLAGS', 'MFLAGS'):
            child_environment.pop(name, None)
        subprocess.Popen([sys.executable, '-IBu', str(Path(__file__).resolve()),
                          'drain', str(root), str(directory), str(owner)],
                         cwd=root, env=child_environment, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True, pass_fds=(owner,))


def drain(root, directory, owner):
    while True:
        with gate(directory):
            try:
                state = read(directory)
                run, active = current(directory)
                if not state['items'] or paused(directory, state, run, active):
                    os.close(owner)
                    return
                row = state['items'][0]
            except BaseException:
                os.close(owner)
                raise
        if active:
            time.sleep(2)
            continue
        # Hold the shared lease through admission, including if this helper
        # dies while the replay process is still starting.
        with reset_gate(root) as lease:
            options = {'resume': row['resume']} if 'resume' in row else {}
            result = subprocess.run([sys.executable, '-IBu', str(Path(__file__).resolve()),
                                     'replay', str(root), json.dumps(row)],
                                    cwd=root, env=dict(os.environ, **{
                                        REPLAY: json.dumps([str(directory), row['id'], options])}),
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, errors='replace',
                                    pass_fds=(lease,))
        if result.returncode == RETRY:
            time.sleep(5)
            continue
        with gate(directory):
            state = read(directory)
            if state['items'] and state['items'][0]['id'] == row['id']:
                # Keep failed startup requests visible and removable. Another
                # submission or removal can wake the helper after correction.
                state['items'][0]['error'] = result.stdout.strip()[-1024:] or 'Launcher did not start.'
                save(directory, state)
                os.close(owner)
                return


def replay(root, row):
    from launcher_controller import DESTINATION
    program, branch, args = row['program'], row['branch'], row['args']
    command = root / 'tools' / program
    if command.is_symlink() or not command.is_file():
        raise ValueError('Queued public launcher is unavailable.')
    os.environ[DESTINATION] = json.dumps(dict(root=str(root), branch=branch, launcher=program,
                                             pid=os.getpid(), public_argv=['--branch', branch, *args]))
    os.execv(sys.executable, [sys.executable, '-IBu', str(command), *args])


def locations(root, *, on_error=None):
    from launcher_controller import _OWNER_KINDS
    for kind in _OWNER_KINDS:
        try:
            directory = storage_directory(kind, root=root, create=False)
            scopes = [] if kind == 'plans' else [directory]
            pattern = {'plans': r'[0-9a-f]{64}', 'sessions': r'vm-.+'}.get(kind)
            if pattern:
                scopes.extend(child for child in sorted(directory.iterdir())
                              if re.fullmatch(pattern, child.name)
                              and not child.is_symlink() and child.is_dir())
        except FileNotFoundError:
            continue
        except (OSError, ValueError) as error:
            if on_error is None:
                raise
            on_error(f'{kind}: {error}')
            continue
        yield from scopes


def scope_tickets(directory, program):
    from watch_output import active_run
    state = read(directory)
    if not state['items']:
        return
    try:
        run = active_run(directory, workflow=not session_scope(directory), record_limit=LIMIT)
    except FileNotFoundError:
        run = None
    interrupted = paused(directory, state, run, run is not None)
    for row in state['items']:
        if program is None or row['program'] == program:
            yield dict(id=row['id'], launcher=row['label'], paused=interrupted,
                       command=shlex.join([f"tools/{row['program']}", *row['args']]),
                       error=row.get('error', ''))


def tickets(root, program=None, *, on_error=None):
    for directory in locations(root, on_error=on_error):
        try:
            yield from scope_tickets(directory, program)
        except (OSError, ValueError, KeyError, TypeError) as error:
            if on_error is None:
                raise ValueError(f'{directory.name}: invalid launcher queue: {error}') from error
            on_error(f'{directory.name}: {error}')


def cancel(root, ticket, program=None, *, wait=True):
    if not ticket_id(ticket):
        raise ValueError('Invalid queue ticket ID.')
    for directory in locations(root, on_error=lambda _error: None):
        try:
            items = read(directory)['items']
        except (OSError, ValueError):
            continue  # A damaged scope cannot hide tickets in healthy scopes.
        if not any(row['id'] == ticket for row in items):
            continue
        with gate(directory, wait=wait):
            state = read(directory)
            for index, row in enumerate(state['items']):
                if row['id'] == ticket and (program is None or row['program'] == program):
                    del state['items'][index]
                    save(directory, state)
                    if index == 0 and state['items'] and not paused(directory, state, *current(directory)):
                        try:
                            wake(root, directory)
                        except OSError:
                            pass  # Cancellation was already saved.
                    return
    raise ValueError('Ticket already started or was removed. Refresh the queue.')


if __name__ == '__main__':
    action, root, *args = sys.argv[1:]
    if action == 'drain':
        drain(Path(root), Path(args[0]), int(args[1]))
    elif action == 'replay':
        replay(Path(root), json.loads(args[0]))
