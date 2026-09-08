#!/usr/bin/python3 -IB
"""Run one fresh Codex CLI session per documented implementation slice."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid


ROOT = Path(__file__).resolve().parents[1]
BACKLOG = Path('docs/TestAutomation/Test-Automation.md')
HANDOFF = Path('docs/TestAutomation/Continuation.md')
PROMPT = Path('docs/TestAutomation/Unattended-Prompt.md')
SUMMARY = Path('docs/Test-Automation-Slice-Summary.md')
STORAGE = Path('output/codex-slices')
MODEL = 'gpt-6-astra'
EFFORT = 'high'
BLOCKERS = ('none', 'approval', 'environment', 'decision', 'no-ready-task')
SUMMARY_FIELDS = {
    'task': 'Task',
    'completed': 'Completed',
    'verification': 'Verification and cleanup',
    'next': 'Next session',
    'remaining_sessions': 'Estimated sessions remaining for this task',
    'remaining_minutes': 'Estimated minutes remaining for this task',
    'estimate_basis': 'Estimate basis and uncertainty',
}
SCHEMA = {
    'type': 'object',
    'properties': {
        'status': {'type': 'string', 'enum': ['continue', 'complete', 'blocked']},
        'cleanup_complete': {'type': 'boolean'},
        'made_progress': {'type': 'boolean'},
        'blocker': {'type': 'string', 'enum': list(BLOCKERS)},
        'summary': {
            'type': 'object',
            'properties': {key: {'type': 'string'} for key in SUMMARY_FIELDS},
            'required': list(SUMMARY_FIELDS),
            'additionalProperties': False,
        },
    },
    'required': ['status', 'cleanup_complete', 'made_progress', 'blocker', 'summary'],
    'additionalProperties': False,
}


class Error(Exception):
    """A condition that must stop the loop without starting another worker."""


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def summary_timestamp():
    """Return a human-readable completion time in this computer's local zone."""
    return datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')


class LiveOutput:
    """Display CLI events without copying their contents to a log or state file."""

    def __init__(self, stream):
        self.stream = stream
        self.lock = threading.Lock()
        self.items = {}

    def write(self, text):
        if not text:
            return
        # Keep line breaks/tabs, but discard terminal control sequences.
        text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
        text = ''.join(char for char in text if char in '\n\t' or char.isprintable())
        with self.lock:
            if self.stream is not None:
                try:
                    self.stream.write(text)
                    self.stream.flush()
                except (OSError, ValueError):
                    # A detached run must survive closure of its original terminal.
                    self.stream = None

    def event(self, event):
        kind = event.get('type', '')
        item = event.get('item')
        if kind in ('error', 'turn.failed'):
            self.write(f"\nCodex error: {event.get('message', event.get('error', 'Unknown error'))}\n")
            return
        if not isinstance(kind, str) or not kind.startswith('item.') or not isinstance(item, dict):
            return
        item_type = item.get('type', 'item')
        key = item.get('id', item_type)
        if not isinstance(key, str):
            return
        previous = self.items.get(key, {})
        text = item.get('text')
        if item_type in ('agent_message', 'reasoning') and isinstance(text, str):
            # The final structured response is rendered as the session summary.
            try:
                final = json.loads(text)
            except ValueError:
                final = None
            if not isinstance(final, dict) or set(final) != set(SCHEMA['required']):
                before = previous.get('text', '')
                if not previous:
                    self.write('\nCodex:\n')
                self.write(text[len(before):] if text.startswith(before) else '\n' + text)
                if kind == 'item.completed':
                    self.write('\n')
        elif item_type == 'command_execution':
            if not previous:
                self.write(f"\n$ {item.get('command', '')}\n")
            output = item.get('aggregated_output', '')
            before = previous.get('aggregated_output', '')
            if isinstance(output, str) and isinstance(before, str):
                self.write(output[len(before):] if output.startswith(before) else output)
            if kind == 'item.completed':
                self.write(f"\nCommand {item.get('status', 'completed')} (exit {item.get('exit_code', 'unknown')}).\n")
        elif item != previous:
            # File changes, MCP results, search and plan updates are terminal-only.
            self.write(f'\n{item_type}: {json.dumps(item, ensure_ascii=False)}\n')
        if kind == 'item.completed':
            self.items.pop(key, None)
        else:
            self.items[key] = item


def append_summary(root, text):
    """Open write-only with O_APPEND. Never read, parse or rewrite prior entries."""
    descriptor = os.open(root / SUMMARY, os.O_WRONLY | os.O_APPEND | os.O_CREAT
                         | os.O_NOFOLLOW | os.O_NONBLOCK, 0o644)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise Error('The slice summary log must be a regular file.')
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        with os.fdopen(descriptor, 'a', encoding='utf-8', closefd=False) as stream:
            stream.write(text)
            stream.flush()
            os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextmanager
def live_output(args):
    descriptor = getattr(args, 'live_output_fd', None)
    if descriptor is None:
        # Detached supervisors write lifecycle messages to launcher.log. Their
        # raw CLI stream must never fall back to that file.
        yield LiveOutput(None if getattr(args, 'request_id', None) else sys.stdout)
    else:
        if not stat.S_ISCHR(os.fstat(descriptor).st_mode):
            raise Error('The inherited live-output descriptor must be a terminal.')
        if not os.isatty(descriptor):
            # The original terminal may close between start and supervisor boot.
            yield LiveOutput(None)
            return
        stream = os.fdopen(os.dup(descriptor), 'w', encoding='utf-8', buffering=1)
        try:
            yield LiveOutput(stream)
        finally:
            try:
                stream.close()
            except OSError:
                # A failed terminal write may leave a buffered tail to flush.
                pass


def finish_session(root, session, outcome, note, live, update):
    if session['report_attempted']:
        return
    # Never retry an uncertain/partially written append by rewriting the log.
    session['report_attempted'] = True
    completed = session.get('completed_at') or summary_timestamp()
    minutes = session.get('duration_minutes')
    if minutes is None:
        minutes = math.ceil(max(0, time.monotonic() - session['started']) / 60)
    text = (f"\n\n## Session {session['number']} — {completed}\n\n"
            f"- Completion: {completed}\n"
            f"- Duration: {minutes} minutes (rounded up)\n"
            f"- Outcome: {outcome}\n"
            f"- Settings: `{session['model']}` / `{session['effort']}`\n"
            f"- Attempt: `{session['attempt']}`\n")
    if note:
        text += f'- Supervisor: {note}\n'
    result = session.get('result')
    if result is not None:
        if outcome == 'needs-review':
            text += '\nThe following is the worker report; acceptance or cleanup is unconfirmed.\n'
        for key, label in SUMMARY_FIELDS.items():
            value = result['summary'][key].strip().replace('\n', '\n  ')
            text += f'\n- {label}: {value}\n'
        if result['blocker'] != 'none':
            text += f"\n- Blocker: {result['blocker']}\n"
    else:
        text += ('\n- Completed: No valid end-of-session report was returned; work is unconfirmed.\n'
                 '- Next session: Retry only if the supervisor confirms a failure before tool use; '
                 'otherwise reconcile the current task handoff and owned operations.\n'
                 '- Estimated sessions/minutes remaining: Unknown.\n')
    try:
        append_summary(root, text)
    except OSError as exc:
        raise Error(f'Could not append the slice summary (errno {exc.errno}); '
                    'reconcile this attempt before restarting.') from exc
    live.write(text + '\n')
    update(last_session={'number': session['number'], 'completed_at': completed,
                         'duration_minutes': minutes, 'outcome': outcome},
           summary_path=str(SUMMARY))


def private_directory(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir() or path.stat().st_uid != os.getuid():
        raise Error('Loop storage must be a caller-owned directory, not a symlink.')
    if path.stat().st_mode & 0o077:
        raise Error('Loop storage must have mode 0700.')


def write_json(path, value):
    """Replace control state atomically; never truncate an earlier attempt log."""
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink()
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_state(storage):
    path = storage / 'state.json'
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text())
    except (ValueError, OSError) as exc:
        raise Error('Unreadable loop state; reconcile the previous run before restarting.') from exc
    if not isinstance(value, dict):
        raise Error('Invalid loop state; reconcile the previous run before restarting.')
    return value


@contextmanager
def exclusive(storage):
    descriptor = os.open(storage / 'lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Error('Another loop or its Codex child still holds this checkout lock.') from exc
        yield descriptor
    finally:
        # Closing our copy preserves the lock if an interrupted worker inherited it.
        os.close(descriptor)


def checklist(root):
    text = (root / BACKLOG).read_text()
    sections = text.split('## Unfinished tasks\n')
    if len(sections) != 2:
        raise Error('The authoritative unfinished-task section is missing or ambiguous.')
    section = sections[1].split('\n## ', 1)[0]
    result = {}
    for line in section.splitlines():
        if not line.startswith('- ['):
            continue
        match = re.fullmatch(r'- \[([ xX])\] \[Task ([A-Z0-9]+) [^\n]+\]\([^\n]+\)', line)
        if not match or match[2] in result:
            raise Error('The authoritative checklist contains a malformed or duplicate task.')
        result[match[2]] = match[1].lower() == 'x'
    if not result:
        raise Error('An empty checklist is not evidence of completion.')
    return result


def handoff_digest(root):
    return hashlib.sha256((root / HANDOFF).read_bytes()).hexdigest()


def validate_result(path):
    try:
        value = json.loads(path.read_text())
    except (ValueError, OSError) as exc:
        raise Error('Codex did not produce a valid structured handoff; inspect the current task handoff.') from exc
    if (not isinstance(value, dict) or set(value) != set(SCHEMA['required'])
            or value['status'] not in ('continue', 'complete', 'blocked')
            or type(value['cleanup_complete']) is not bool
            or type(value['made_progress']) is not bool
            or value['blocker'] not in BLOCKERS):
        raise Error('Codex returned an invalid structured handoff.')
    if (value['status'] == 'blocked') != (value['blocker'] != 'none'):
        raise Error('Codex returned inconsistent blocker and status fields.')
    summary = value['summary']
    if (not isinstance(summary, dict) or set(summary) != set(SUMMARY_FIELDS)
            or any(not isinstance(text, str) or not text.strip() or len(text) > 8000
                   or any(not char.isprintable() and char not in '\n\t' for char in text)
                   for text in summary.values())):
        raise Error('Codex returned an invalid end-of-session summary.')
    return value


def transient_error(value):
    """Classify without retaining or printing arbitrary CLI/provider error text."""
    message = str(value).lower()
    if any(term in message for term in ('insufficient_quota', 'unauthorized', 'invalid api key')):
        return False
    return any(term in message for term in (
        'rate_limit', 'rate limit', 'usage_limit', 'usage limit',
        '429', '502', '503', '504', 'connection reset', 'stream disconnected',
    ))


def invoke(root, attempt, command, lock_fd, update, live):
    """Display both streams live, retaining only allowlisted lifecycle metadata."""
    observed = {'completed': False, 'failed': False, 'transient': False,
                'tools_seen': False, 'invalid_event': False}
    prompt = (root / PROMPT).read_text()
    prompt += '\nThe supervisor has selected these exact settings: '
    prompt += f'{command[command.index("--model") + 1]} / '
    prompt += command[command.index('-c') + 1].split('=', 1)[1] + '.\n'
    # Ephemeral CLI sessions and this renderer retain no in-session transcript.
    # Only the final structured report and allowlisted control metadata are saved.
    with (attempt / 'events.jsonl').open('x') as events:
        process = subprocess.Popen(
            command, cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace',
            start_new_session=True, pass_fds=(lock_fd,),
        )
        def drain_stderr():
            for line in process.stderr:
                live.write(line)

        drain = threading.Thread(target=drain_stderr, daemon=True)
        drain.start()
        try:
            update(cli_pid=process.pid)
            process.stdin.write(prompt)
            process.stdin.close()
            for line in process.stdout:
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise ValueError('not an object')
                except ValueError:
                    observed['invalid_event'] = True
                    live.write(line)
                    continue
                live.event(event)
                kind = event.get('type')
                metadata = {'time': stamp()}
                if kind == 'thread.started':
                    try:
                        thread = str(uuid.UUID(event['thread_id']))
                    except (KeyError, TypeError, ValueError, AttributeError):
                        observed['invalid_event'] = True
                        continue
                    update(thread_id=thread)
                    metadata.update(type=kind, thread_id=thread)
                elif kind in ('turn.started', 'turn.completed', 'turn.failed', 'error'):
                    metadata['type'] = kind
                    if kind == 'turn.completed':
                        observed['completed'] = True
                        usage = event.get('usage', {})
                        if isinstance(usage, dict):
                            metadata['usage'] = {
                                key: usage[key] for key in (
                                    'input_tokens', 'cached_input_tokens', 'output_tokens',
                                    'reasoning_output_tokens',
                                ) if type(usage.get(key)) is int and usage[key] >= 0
                            }
                    elif kind == 'turn.failed':
                        observed['failed'] = True
                        observed['transient'] = transient_error(event.get('error', {}))
                elif isinstance(kind, str) and kind.startswith('item.'):
                    item = event.get('item', {})
                    if not isinstance(item, dict) or item.get('type') not in ('reasoning', 'agent_message'):
                        observed['tools_seen'] = True
                    # Tool details, reasoning and model prose are not supervisor logs.
                    continue
                else:
                    observed['invalid_event'] = True
                    continue
                events.write(json.dumps(metadata) + '\n')
                events.flush()
        finally:
            # Never kill a model-owned test/VM operation to enforce a slice timer.
            # Await this exact child even if the supervisor encounters an error.
            if not process.stdin.closed:
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass
            # Keep the pipe open and drain it on a supervisor write/parse error;
            # closing a live worker's stdout could abort it with SIGPIPE.
            for _line in process.stdout:
                pass
            process.stdout.close()
            process.wait()
            drain.join()
            process.stderr.close()
            live.items.clear()
    return process.returncode, observed


def preflight(root):
    for document in (BACKLOG, HANDOFF, PROMPT):
        if not (root / document).is_file():
            raise Error('A required continuation document is missing.')
    executable = shutil.which('codex')
    if executable is None:
        raise Error('Codex CLI must be installed and signed in before starting this launcher.')
    help_result = subprocess.run([executable, 'exec', '--help'], capture_output=True, text=True, check=False)
    if help_result.returncode or not all(option in help_result.stdout for option in (
            '--approve-for-me', '--ephemeral', '--output-schema', '--json', '--output-last-message')):
        raise Error('This launcher requires Codex exec with auto-review, ephemeral sessions and structured output support.')
    return executable


def wait_retry(delay, stopping, stop_requested):
    deadline = time.monotonic() + delay
    while time.monotonic() < deadline and not stopping():
        stop_requested.wait(min(1, max(0, deadline - time.monotonic())))


def run(root, args):
    storage = root / STORAGE
    private_directory(storage)
    with exclusive(storage) as lock_fd, live_output(args) as live:
        state = read_state(storage)
        request_id = getattr(args, 'request_id', None) or str(uuid.uuid4())
        own_start = state.get('status') == 'launching' and state.get('request_id') == request_id
        if state.get('status') in ('launching', 'running', 'needs-review') and not (args.reconciled or own_start):
            raise Error('Previous work needs reconciliation; see state.json and the saved handoff. '
                        'Use --reconciled only after checking the recorded operation and cleanup.')

        def update(**fields):
            state.update(fields, updated=stamp())
            write_json(storage / 'state.json', state)

        def announce(message):
            print(message, flush=True)
            if live.stream is not sys.stdout:
                live.write(message + '\n')

        update(status='launching', request_id=request_id)
        executable = preflight(root)
        tasks = checklist(root)
        expected = set(state.get('tasks', ()))
        if expected - tasks.keys():
            raise Error('Recorded tasks disappeared from the checklist; reconcile its completion record.')
        expected.update(tasks)
        stop_requested = threading.Event()

        def request_stop(_signum, _frame):
            stop_requested.set()

        old_signals = {sig: signal.signal(sig, request_stop) for sig in (signal.SIGINT, signal.SIGTERM)}

        def stopping():
            if stop_requested.is_set():
                return True
            try:
                request = json.loads((storage / 'STOP').read_text())
            except FileNotFoundError:
                return False
            except ValueError as exc:
                raise Error('The stop request is unreadable; refusing to start more work.') from exc
            # A new invocation ignores an earlier run's stop request. Never
            # unlink a marker during startup: that could erase a new request.
            return not isinstance(request, dict) or request.get('request_id') == request_id

        completed_slices = 0
        retries = 0
        session = None
        try:
            while True:
                if stopping() or (args.max_slices and completed_slices >= args.max_slices):
                    update(status='stopped', reason='slice-boundary')
                    return 0
                tasks = checklist(root)
                if expected - tasks.keys():
                    raise Error('Recorded tasks disappeared from the checklist.')
                expected.update(tasks)
                if all(tasks.values()):
                    update(status='complete', reason='checklist-complete', tasks=sorted(expected))
                    announce('All documented tasks are complete.')
                    return 0
                model, effort = MODEL, EFFORT
                before = handoff_digest(root)
                attempt = storage / ('slice-' + uuid.uuid4().hex)
                private_directory(attempt)
                write_json(attempt / 'schema.json', SCHEMA)
                number = state.get('sessions_started', 0) + 1
                update(status='running', reason='slice', attempt=attempt.name,
                       model=model, effort=effort, tasks=sorted(expected),
                       cli_pid=None, thread_id=None, sessions_started=number)
                command = [executable, 'exec', '--approve-for-me', '--ephemeral', '--model', model,
                           '-c', f'model_reasoning_effort="{effort}"',
                           '--cd', str(root), '--json', '--color', 'never',
                           '--output-schema', str(attempt / 'schema.json'),
                           '--output-last-message', str(attempt / 'result.json'), '-']
                announce(f'{stamp()} Starting fresh session {number} with {model} / {effort}.')
                session = {'number': number, 'model': model, 'effort': effort,
                           'attempt': attempt.name, 'started': time.monotonic(),
                           'report_attempted': False}
                code, observed = invoke(root, attempt, command, lock_fd, update, live)
                session.update(completed_at=summary_timestamp(),
                               duration_minutes=math.ceil(max(0, time.monotonic() - session['started']) / 60))
                write_json(attempt / 'exit.json', {'exit_code': code, **observed})
                # Retry only an explicit transient failed turn that never called
                # a tool. Errors after tools ran require operation reconciliation.
                if (code != 0 and observed['failed'] and observed['transient']
                        and not observed['completed'] and not observed['tools_seen']
                        and not observed['invalid_event'] and handoff_digest(root) == before
                        and retries < args.max_api_retries):
                    delay = min(60 * 2 ** retries, 3600)
                    retries += 1
                    finish_session(root, session, 'retry', 'Transient failure before tool use; '
                                   f'retrying in {math.ceil(delay / 60)} minutes.', live, update)
                    update(status='retry-wait', reason='transient-before-tools', retry=retries)
                    announce(f'Transient API failure before tool use; retrying in {delay}s.')
                    wait_retry(delay, stopping, stop_requested)
                    continue
                if code != 0 or not observed['completed'] or observed['failed'] or observed['invalid_event']:
                    raise Error('Codex exited without a clean completed turn; inspect the current task handoff and owned operations.')
                result = validate_result(attempt / 'result.json')
                session['result'] = result
                if not result['cleanup_complete']:
                    raise Error('The slice did not confirm completed operation collection and cleanup.')
                current = checklist(root)
                if expected - current.keys():
                    raise Error('A slice removed recorded checklist tasks.')
                if result['status'] == 'blocked':
                    finish_session(root, session, 'blocked', 'Cleanup confirmed; outside input required.', live, update)
                    update(status='blocked', reason=result['blocker'])
                    announce('No ready work can proceed. Read the current task handoff for the blocker.')
                    return 2
                if result['status'] == 'complete':
                    if not all(current.values()):
                        raise Error('Codex reported completion while checklist tasks remain unfinished.')
                    if handoff_digest(root) == before:
                        raise Error('Codex did not save a final completion handoff in Continuation.md.')
                    finish_session(root, session, 'complete', 'Checklist, cleanup and final handoff confirmed.', live, update)
                    update(status='complete', reason='checklist-and-handoff-complete', tasks=sorted(current))
                    announce('All documented tasks are complete.')
                    return 0
                if not result['made_progress'] or handoff_digest(root) == before:
                    raise Error('The slice reported no progress or did not update Continuation.md.')
                if all(current.values()):
                    raise Error('The checklist is complete but Codex did not return a completion handoff.')
                completed_slices += 1
                retries = 0
                finish_session(root, session, 'continue', 'Cleanup and handoff confirmed.', live, update)
                update(status='between-slices', reason='verified-handoff', tasks=sorted(current))
                announce(f'Session {number} summary appended to {SUMMARY}.')
        except (Error, OSError) as exc:
            if session is not None and not session['report_attempted']:
                note = f'Local I/O or process startup failed (errno {exc.errno}).' if isinstance(exc, OSError) else str(exc)
                try:
                    finish_session(root, session, 'needs-review', note, live, update)
                except (Error, OSError):
                    announce('The session summary could not be confirmed; reconcile the current attempt.')
            update(status='needs-review', reason='unconfirmed-handoff')
            if isinstance(exc, OSError):
                raise Error(f'Local I/O or process startup failed (errno {exc.errno}); '
                            'reconcile the current task handoff and owned operations before restarting.') from exc
            raise
        finally:
            for sig, handler in old_signals.items():
                signal.signal(sig, handler)


def main(argv=None, *, root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('action', choices=('start', 'run', 'status', 'stop'))
    parser.add_argument('--max-slices', type=int, default=0, help='Stop after this many slices; 0 runs until complete.')
    parser.add_argument('--max-api-retries', type=int, default=12, help='Retries per consecutive transient failure before tool use.')
    parser.add_argument('--reconciled', action='store_true', help='Operator has reconciled an interrupted run and all owned cleanup.')
    parser.add_argument('--request-id', help=argparse.SUPPRESS)
    parser.add_argument('--live-output-fd', type=int, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.request_id:
        try:
            args.request_id = str(uuid.UUID(args.request_id))
        except ValueError:
            parser.error('request-id must be a UUID')
    if args.max_slices < 0 or not 0 <= args.max_api_retries <= 100:
        parser.error('max-slices must be nonnegative; max-api-retries must be between 0 and 100')
    try:
        storage = root / STORAGE
        if args.action == 'status':
            state = read_state(storage)
            print(json.dumps(state or {'status': 'not-started'}, indent=2, sort_keys=True))
            return 0
        if args.action == 'stop':
            if not storage.is_dir():
                print('No loop has been started.')
                return 0
            private_directory(storage)
            state = read_state(storage)
            write_json(storage / 'STOP', {'requested': stamp(), 'request_id': state.get('request_id')})
            print('Stop requested. The current slice will finish and clean up before the loop exits.')
            return 0
        if args.action == 'start':
            private_directory(storage)
            with exclusive(storage):
                state = read_state(storage)
                if state.get('status') in ('launching', 'running', 'needs-review') and not args.reconciled:
                    raise Error('Previous work needs reconciliation; read state.json and the task handoff.')
                preflight(root)
                request_id = str(uuid.uuid4())
                state.update(status='launching', request_id=request_id, updated=stamp())
                write_json(storage / 'state.json', state)
            command = [sys.executable, '-I', '-B', str(root / 'tools/codex_slices.py'), 'run',
                       '--max-slices', str(args.max_slices), '--max-api-retries', str(args.max_api_retries),
                       '--request-id', request_id]
            if args.reconciled:
                command.append('--reconciled')
            terminal_fds = ()
            if sys.stdout.isatty():
                # Duplicate before redirecting the child's stdout to launcher.log.
                descriptor = os.dup(sys.stdout.fileno())
                command.extend(('--live-output-fd', str(descriptor)))
                terminal_fds = (descriptor,)
            try:
                with (storage / 'launcher.log').open('a') as log:
                    child = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL,
                                             stdout=log, stderr=log, start_new_session=True,
                                             pass_fds=terminal_fds)
            finally:
                for descriptor in terminal_fds:
                    os.close(descriptor)
            try:
                code = child.wait(timeout=1)
            except subprocess.TimeoutExpired:
                print(f'Launcher started (PID {child.pid}). Use status or stop to manage it.')
                return 0
            print('Launcher exited; read output/codex-slices/launcher.log and run status.')
            return code
        return run(root, args)
    except Error as exc:
        print(f'codex-slices: {exc}', file=sys.stderr)
        return 2
    except OSError as exc:
        print(f'codex-slices: local I/O or process startup failed (errno {exc.errno}).', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
