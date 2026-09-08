#!/usr/bin/python3 -IB
"""Run one fresh Codex CLI session per documented implementation slice."""
from __future__ import annotations

import argparse
import codecs
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import shlex
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
import uuid

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.syntax import Syntax
except ImportError:
    Console = Markdown = Syntax = None


ROOT = Path(__file__).resolve().parents[1]
BACKLOG = Path('docs/TestAutomation/Test-Automation.md')
HANDOFF = Path('docs/TestAutomation/Continuation.md')
PROMPT = Path('docs/TestAutomation/Unattended-Prompt.md')
SUMMARY = Path('docs/Test-Automation-Slice-Summary.md')
STORAGE = Path('output/codex-slices')
MODELS = frozenset(('gpt-5.6-sol', 'gpt-6-astra', 'gpt-5.6-terra', 'gpt-5.6-luna'))
EFFORTS = frozenset(('low', 'medium', 'high', 'xhigh', 'max'))
USAGE_FIELDS = ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens')
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
            'description': (
                'Concise, self-contained session report. Preserve material findings, '
                'failures, verification scope, cleanup and next actions. Reference '
                'evidence paths and test IDs instead of repeating scripts, patches, '
                'commands or tool output. Expand when necessary for a correct handoff.'
            ),
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


class Busy(Error):
    """The checkout is owned by an existing supervisor or worker."""


def monitor_address(storage):
    # Linux abstract sockets avoid persistent output files and pathname limits.
    identity = hashlib.sha256(os.fsencode(storage.resolve())).hexdigest()
    return f'\0onpc-slices-{os.getuid()}-{identity}'


def same_user(connection):
    credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
    return struct.unpack('3i', credentials)[1] == os.getuid()


class MonitorHub:
    """Bounded, memory-only output fanout; slow monitors never block workers."""

    def __init__(self, storage, live):
        self.storage, self.live = storage, live
        self.clients = {}
        self.lock = threading.Lock()
        self.stopping = threading.Event()

    def __enter__(self):
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.server.bind(monitor_address(self.storage))
            self.server.listen(16)
            self.server.setblocking(False)
        except BaseException:
            self.server.close()
            raise
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.live.monitor = self
        self.thread.start()
        return self

    def publish(self, block):
        packet = (json.dumps(block) + '\n').encode('utf-8')
        with self.lock:
            for client, pending in list(self.clients.items()):
                if len(pending) + len(packet) > 8 * 1024 * 1024:
                    client.close()
                    del self.clients[client]
                else:
                    pending.extend(packet)

    def serve(self):
        while not self.stopping.is_set():
            with self.lock:
                try:
                    client, _ = self.server.accept()
                except BlockingIOError:
                    pass
                else:
                    if same_user(client) and len(self.clients) < 16:
                        client.setblocking(False)
                        self.clients[client] = bytearray()
                    else:
                        client.close()
                for client, pending in list(self.clients.items()):
                    if not pending:
                        try:
                            if client.recv(1, socket.MSG_PEEK) == b'':
                                client.close()
                                del self.clients[client]
                        except BlockingIOError:
                            pass
                        except OSError:
                            client.close()
                            del self.clients[client]
                        continue
                    try:
                        sent = client.send(pending)
                        del pending[:sent]
                    except BlockingIOError:
                        pass
                    except OSError:
                        client.close()
                        del self.clients[client]
            self.stopping.wait(0.02)

    def __exit__(self, *exc):
        self.live.monitor = None
        # End the monitor stream explicitly after the final output. A retained
        # socket descriptor must not leave monitors waiting indefinitely for EOF.
        self.publish({'type': 'launcher.exiting'})
        # Give final status output a bounded opportunity to drain.
        deadline = time.monotonic() + 0.25
        while time.monotonic() < deadline:
            with self.lock:
                if not any(self.clients.values()):
                    break
            time.sleep(0.01)
        self.stopping.set()
        self.thread.join()
        for client in self.clients:
            client.close()
        self.server.close()


def attach_monitor(storage):
    """Follow future output only; never modify state or signal the supervisor."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        # The checkout lock may precede listener startup by a short interval.
        for attempt in range(20):
            try:
                connection.connect(monitor_address(storage))
                break
            except (ConnectionRefusedError, FileNotFoundError):
                if attempt == 19:
                    raise Error('An existing worker holds the checkout lock but has no monitor endpoint. '
                                'It may predate monitoring support; its session was left unchanged.')
                time.sleep(0.05)
        if not same_user(connection):
            raise Error('Monitor endpoint belongs to another user.')
        live = LiveOutput(sys.stdout)
        live.write('Monitoring ongoing session. Ctrl+C detaches only this monitor.\n')
        try:
            with connection.makefile('r', encoding='utf-8') as stream:
                for line in stream:
                    try:
                        block = json.loads(line)
                    except ValueError:
                        break  # A disconnected slow monitor may have a partial block.
                    if block == {'type': 'launcher.exiting'}:
                        return 0
                    live.display(**block)
                    if live.stream is None:
                        return 0
        except KeyboardInterrupt:
            live.write('\nMonitor detached; session left unchanged.\n')
            return 0
        live.write('\nMonitor connection closed. Use status to inspect the session.\n')
    return 0


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def summary_timestamp():
    """Return a human-readable completion time in this computer's local zone."""
    return datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')


def file_read_path(command):
    """Recognize simple file reads for display only; never execute or read paths.

    Keep searches, diffs, numbered source, pipelines and mixed output literal.
    Unwrap the CLI's shell command string without evaluating shell syntax.
    """
    if not isinstance(command, str):
        return None
    try:
        words = shlex.split(command)
        if (len(words) == 3 and Path(words[0]).name in ('bash', 'sh')
                and words[1] in ('-c', '-lc')):
            words = shlex.split(words[2])
    except ValueError:
        return None
    if not words:
        return None
    program, args = Path(words[0]).name, words[1:]
    if program == 'cat':
        paths = args
    elif program in ('head', 'tail'):
        if len(args) >= 2 and args[0] == '-n' and re.fullmatch(r'[+-]?\d+', args[1]):
            paths = args[2:]
        elif args and re.fullmatch(r'-\d+', args[0]):
            paths = args[1:]
        else:
            paths = args
    elif (program == 'sed' and len(args) >= 2 and args[0] == '-n'
          and re.fullmatch(r'(?:\d+|\$)(?:,(?:\d+|\$))?p', args[1])):
        paths = args[2:]
    elif (program == 'read-only' and len(args) >= 3 and args[0] == 'slice'
          and args[1].isdigit() and args[2].isdigit()):
        paths = args[3:]
    else:
        return None
    if paths[:1] == ['--']:
        paths = paths[1:]
    if (len(paths) == 1 and not paths[0].startswith('-')
            and not any(char in paths[0] for char in '\n\r;|&<>`$*?[]')):
        return paths[0]
    return None


class LiveOutput:
    """Render CLI events locally; this display is not sent back to the worker.

    Filtering this stream cannot reduce that worker's model tokens. Control
    unnecessary generation through PROMPT/SCHEMA and focused worker tool reads.
    Keep command output available here for the operator's diagnosis.
    """

    def __init__(self, stream):
        self.stream = stream
        self.monitor = None
        self.lock = threading.Lock()
        self.items = {}
        self.console = None
        if (Console is not None and stream is not None and stream.isatty()
                and os.environ.get('TERM') != 'dumb'):
            self.console = Console(file=stream, markup=False, highlight=False)

    @staticmethod
    def clean(text):
        # Keep line breaks/tabs, but discard terminal control sequences.
        text = re.sub(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)', '', text)
        text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
        return ''.join(char for char in text if char in '\n\t' or char.isprintable())

    def write(self, text, *, style=None):
        self.display(text, markdown=False, style=style)

    def markdown(self, text):
        self.display(text, markdown=True)

    def finish(self):
        """Tell attached monitors that no more launcher output will follow."""
        with self.lock:
            if self.monitor is not None:
                self.monitor.publish({'type': 'launcher.exiting'})

    def display(self, text, *, markdown=False, lexer=None, style=None):
        if not text:
            return
        text = self.clean(text)
        with self.lock:
            if self.monitor is not None:
                self.monitor.publish(dict(text=text, markdown=markdown, lexer=lexer, style=style))
            if self.stream is not None:
                try:
                    if self.console is not None:
                        # Detached supervisors retain a separate terminal fd;
                        # standard streams and inherited COLUMNS may be stale.
                        # Query each block so subsequent output follows resizes.
                        try:
                            columns = os.get_terminal_size(self.stream.fileno()).columns
                        except (AttributeError, OSError, ValueError):
                            columns = 0
                        self.console.width = columns if columns > 0 else None
                    if markdown and self.console is not None:
                        # Only the renderer may generate terminal formatting.
                        # Disable OSC links; show destinations as ordinary text.
                        self.console.print(Markdown(text, hyperlinks=False))
                    elif lexer and self.console is not None:
                        self.console.print(Syntax(text, lexer, background_color='default',
                                                  word_wrap=True))
                    elif style and self.console is not None:
                        self.console.print(text, style=style, end='', soft_wrap=True)
                    else:
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
                if self.console is not None:
                    # Render complete blocks once: partial fences/tables cannot
                    # be safely appended as separately formatted fragments.
                    if kind == 'item.completed':
                        self.write('\nCodex:\n')
                        self.markdown(text)
                        self.write('\n')
                else:
                    before = previous.get('text', '')
                    if not previous:
                        self.write('\nCodex:\n')
                    self.write(text[len(before):] if text.startswith(before) else '\n' + text)
                    if kind == 'item.completed':
                        self.write('\n')
        elif item_type == 'command_execution':
            command = item.get('command', previous.get('command', ''))
            if not previous:
                self.write(f'\n$ {command}\n', style='bold cyan')
            output = item.get('aggregated_output', '')
            before = previous.get('aggregated_output', '')
            if isinstance(output, str) and isinstance(before, str):
                path = file_read_path(command) if self.console is not None else None
                markdown = path is not None and Path(path).suffix.lower() in ('.md', '.markdown')
                lexer = Syntax.guess_lexer(path) if path and not markdown else None
                if markdown or lexer not in (None, 'text', 'default'):
                    # Render complete excerpts once so partial Markdown blocks
                    # and multiline source tokens retain their context.
                    if kind == 'item.completed':
                        if item.get('exit_code') == 0:
                            self.display(output, markdown=markdown, lexer=lexer)
                        else:
                            self.write(output)
                else:
                    self.write(output[len(before):] if output.startswith(before) else output)
            if kind == 'item.completed':
                self.write(f"\nCommand {item.get('status', 'completed')} (exit {item.get('exit_code', 'unknown')}).\n",
                           style='dim green' if item.get('exit_code') == 0 else 'bold red')
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
            '- Processing: Standard\n'
            f"- Attempt: `{session['attempt']}`\n")
    usage = session.get('usage', {})
    counts = '; '.join(f'{key}: {usage[key]}' for key in USAGE_FIELDS if key in usage)
    text += f'- CLI token counts: {counts or "not reported"}. These are not weekly allowance measurements.\n'
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
    live.markdown(text + '\n')
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
            raise Busy('Another loop or its Codex child still holds this checkout lock.') from exc
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


def session_settings(root, saved=None):
    """Read one explicit handoff choice, or preserve an interrupted session's choice."""
    if saved is None:
        lines = [line for line in (root / HANDOFF).read_text().splitlines()
                 if line.startswith('- Settings:')]
        if len(lines) != 1:
            raise Error('Continuation.md must contain exactly one - Settings: line; no model fallback is used.')
        match = re.fullmatch(r'- Settings: \*\*`([a-z0-9.-]+)` / `([a-z]+)`\*\*\.', lines[0])
        if match is None:
            raise Error('Malformed Continuation.md settings; use - Settings: **`<model>` / `<effort>`**.')
        model, effort = match.groups()
    else:
        model, effort = saved.get('model'), saved.get('effort')
    if not isinstance(model, str) or model not in MODELS:
        raise Error('Unsupported or missing model selection; review the documented model policy.')
    if not isinstance(effort, str) or effort not in EFFORTS:
        raise Error('Unsupported or missing reasoning effort; review the documented model policy.')
    return model, effort


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


def kill_requested(storage, request_id):
    try:
        request = json.loads((storage / 'KILL').read_text())
    except FileNotFoundError:
        return False
    except ValueError:
        return False
    return isinstance(request, dict) and request.get('request_id') == request_id


def interrupt_child(process, requested, finished, killed):
    """Signal only our Popen child; never trust a saved PID or scan descendants."""
    while not finished.wait(0.1):
        if requested() and process.poll() is None:
            killed.set()
            process.send_signal(signal.SIGINT)
            if not finished.wait(2) and process.poll() is None:
                process.kill()
            return


def child_output(process):
    """Drain both pipes while the owned child lives, with a bounded exit drain.

    A tool can inherit either pipe and outlive Codex. Its open descriptor must
    not keep the supervisor running after Codex exits. Never signal that tool.
    """
    decoders = {pipe: codecs.getincrementaldecoder('utf-8')('replace')
                for pipe in (process.stdout, process.stderr)}
    pending = ''
    exit_remaining = None
    with selectors.DefaultSelector() as selector:
        for pipe in decoders:
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ)
        while selector.get_map():
            if process.poll() is not None and exit_remaining is None:
                # Drain at most one pipe capacity after exit. This includes
                # every byte already buffered even when rendering is slow,
                # while bounding output from an inherited writer that continues.
                exit_remaining = {key.fileobj: fcntl.fcntl(key.fd, fcntl.F_GETPIPE_SZ)
                                  for key in selector.get_map().values()}
            ready = selector.select(timeout=0.05)
            if not ready and exit_remaining is not None:
                break
            for key, _mask in ready:
                pipe = key.fileobj
                try:
                    limit = min(65536, exit_remaining[pipe]) if exit_remaining is not None else 65536
                    data = os.read(pipe.fileno(), limit)
                except BlockingIOError:
                    continue
                text = decoders[pipe].decode(data)
                if exit_remaining is not None:
                    exit_remaining[pipe] -= len(data)
                if not data or (exit_remaining is not None and exit_remaining[pipe] == 0):
                    selector.unregister(pipe)
                if pipe is process.stderr:
                    if text:
                        yield pipe, text
                else:
                    pending += text
                    lines = pending.split('\n')
                    pending = lines.pop()
                    for line in lines:
                        yield pipe, line + '\n'
        for pipe, decoder in decoders.items():
            text = decoder.decode(b'', final=True)
            if pipe is process.stdout:
                pending += text
            elif text:
                yield pipe, text
        if pending:
            yield process.stdout, pending


def invoke(root, attempt, command, lock_fd, update, live):
    """Display both streams live, retaining only allowlisted lifecycle metadata."""
    observed = {'completed': False, 'failed': False, 'transient': False,
                'tools_seen': False, 'invalid_event': False}
    prompt = (root / PROMPT).read_text()
    prompt += '\nThe supervisor has selected these exact settings: '
    prompt += f'{command[command.index("--model") + 1]} / '
    prompt += command[command.index('-c') + 1].split('=', 1)[1] + '.\n'
    prompt += ('Processing is Standard. These are this session\'s actual settings; '
               'reassess the next slice under the model policy instead of copying them automatically.\n')
    if 'resume' in command:
        prompt += ('\nResume the interrupted conversation. Before continuing, reconcile '
                   'any interrupted tools, owned operations and cleanup; do not blindly '
                   'repeat operations. Return the required structured report.\n')
    request_id = read_state(root / STORAGE).get('request_id')
    finished, killed = threading.Event(), threading.Event()
    # Codex retains its own resumable session; supervisor logs contain metadata only.
    with (attempt / 'events.jsonl').open('x') as events:
        process = subprocess.Popen(
            command, cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace',
            start_new_session=True, pass_fds=(lock_fd,),
        )
        watcher = threading.Thread(target=interrupt_child, args=(
            process, lambda: kill_requested(root / STORAGE, request_id), finished, killed),
            daemon=True)
        watcher.start()
        output = child_output(process)
        try:
            update(cli_pid=process.pid)
            process.stdin.write(prompt)
            process.stdin.close()
            for pipe, line in output:
                if pipe is process.stderr:
                    live.write(line)
                    continue
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
                                key: usage[key] for key in USAGE_FIELDS
                                if type(usage.get(key)) is int and usage[key] >= 0
                            }
                            observed['usage'] = metadata['usage']
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
            for _pipe, _line in output:
                pass
            process.stdout.close()
            process.wait()
            finished.set()
            watcher.join()
            process.stderr.close()
            live.items.clear()
    observed['killed'] = killed.is_set()
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
            '--approve-for-me', '--output-schema', '--json', '--output-last-message')):
        raise Error('This launcher requires Codex exec with auto-review and structured output support.')
    resume_help = subprocess.run([executable, 'exec', 'resume', '--help'],
                                 capture_output=True, text=True, check=False)
    if resume_help.returncode or '--output-schema' not in resume_help.stdout:
        raise Error('This launcher requires Codex exec resume with structured output support.')
    return executable


def wait_retry(delay, stopping, stop_requested):
    deadline = time.monotonic() + delay
    while time.monotonic() < deadline and not stopping():
        stop_requested.wait(min(1, max(0, deadline - time.monotonic())))


def saved_thread(state):
    if not state.get('resumable'):
        raise Error('The killed session was not saved for resumption; reconcile it before using --reconciled.')
    try:
        return str(uuid.UUID(state['thread_id']))
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise Error('The killed session has no saved thread ID to resume; reconcile it before using --reconciled.') from exc


def run(root, args):
    storage = root / STORAGE
    private_directory(storage)
    with exclusive(storage) as lock_fd, live_output(args) as live, MonitorHub(storage, live):
        state = read_state(storage)
        request_id = getattr(args, 'request_id', None) or str(uuid.uuid4())
        own_start = state.get('status') == 'launching' and state.get('request_id') == request_id
        resume_thread = None
        if ((state.get('status') == 'killed' and not args.reconciled)
                or (own_start and state.get('thread_id') is not None)):
            resume_thread = saved_thread(state)
        if state.get('status') in ('launching', 'running', 'needs-review', 'killed') and not (args.reconciled or own_start or resume_thread):
            raise Error('Previous work needs reconciliation; see state.json and the saved handoff. '
                        'Use --reconciled only after checking the recorded operation and cleanup.')

        def update(**fields):
            state.update(fields, updated=stamp())
            write_json(storage / 'state.json', state)

        def announce(message, *, style=None, final=False):
            if live.stream is not sys.stdout:
                print(message, flush=True)
            live.write(message + '\n', style=style)
            # Do not make an attached console wait for context-manager or
            # socket teardown after it has already received the final notice.
            if final:
                live.finish()

        executable = preflight(root)
        tasks = checklist(root)
        expected = set(state.get('tasks', ()))
        if expected - tasks.keys():
            raise Error('Recorded tasks disappeared from the checklist; reconcile its completion record.')
        expected.update(tasks)
        update(status='launching', request_id=request_id, resumable=True, thread_id=resume_thread,
               cli_pid=None,
               max_slices=args.max_slices, max_api_retries=args.max_api_retries)
        stop_requested = threading.Event()

        def request_stop(_signum, _frame):
            stop_requested.set()

        old_signals = {sig: signal.signal(sig, request_stop) for sig in (signal.SIGINT, signal.SIGTERM)}

        def stopping():
            if stop_requested.is_set() or kill_requested(storage, request_id):
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
                if kill_requested(storage, request_id):
                    update(status='killed', reason='operator-kill', cli_pid=None)
                    announce('Session killed. Launcher exiting.', style='bold red', final=True)
                    return 0
                if stopping() or (args.max_slices and completed_slices >= args.max_slices):
                    update(status='stopped', reason='slice-boundary', cli_pid=None)
                    announce('Session stopped at a safe slice boundary. Launcher exiting.',
                             style='bold red', final=True)
                    return 0
                tasks = checklist(root)
                if expected - tasks.keys():
                    raise Error('Recorded tasks disappeared from the checklist.')
                expected.update(tasks)
                if all(tasks.values()) and not resume_thread:
                    update(status='complete', reason='checklist-complete', tasks=sorted(expected),
                           cli_pid=None)
                    announce('All documented tasks are complete.', final=True)
                    return 0
                model, effort = session_settings(root, state if resume_thread else None)
                before = handoff_digest(root)
                attempt = storage / ('slice-' + uuid.uuid4().hex)
                private_directory(attempt)
                write_json(attempt / 'schema.json', SCHEMA)
                number = state.get('sessions_started', 0) + 1
                update(status='running', reason='slice', attempt=attempt.name,
                       model=model, effort=effort, service_tier='default',
                       settings_source='saved-session' if resume_thread else 'continuation', tasks=sorted(expected),
                       cli_pid=None, thread_id=resume_thread, resumable=True, sessions_started=number)
                command = [executable, 'exec', '--approve-for-me', '--model', model,
                           '-c', f'model_reasoning_effort="{effort}"',
                           '-c', 'service_tier="default"',
                           '--cd', str(root), '--json', '--color', 'never',
                           '--output-schema', str(attempt / 'schema.json'),
                           '--output-last-message', str(attempt / 'result.json')]
                command += ['resume', resume_thread, '-'] if resume_thread else ['-']
                announce(f'{stamp()} {"Resuming" if resume_thread else "Starting fresh"} session {number} with {model} / {effort}, Standard processing.')
                attempted_thread = resume_thread
                resume_thread = None
                session = {'number': number, 'model': model, 'effort': effort,
                           'attempt': attempt.name, 'started': time.monotonic(),
                           'report_attempted': False}
                code, observed = invoke(root, attempt, command, lock_fd, update, live)
                # cli_pid identifies a currently owned live child, not
                # historical metadata. Clear it before evaluating the outcome.
                update(cli_pid=None)
                session['usage'] = observed.get('usage', {})
                session.update(completed_at=summary_timestamp(),
                               duration_minutes=math.ceil(max(0, time.monotonic() - session['started']) / 60))
                write_json(attempt / 'exit.json', {'exit_code': code, **observed})
                if observed.get('killed') or kill_requested(storage, request_id) or code < 0:
                    operator_kill = observed.get('killed') or kill_requested(storage, request_id)
                    finish_session(root, session, 'killed',
                                   'Session interrupted; work and cleanup are unconfirmed.', live, update)
                    update(status='killed', reason='operator-kill' if operator_kill else 'worker-signal', cli_pid=None)
                    announce('Session killed. Launcher exiting. Use start to continue the saved conversation.',
                             style='bold red', final=True)
                    return 0 if operator_kill else 2
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
                    # A resumed conversation still owns its earlier work. A
                    # pre-tool transport retry must not replace it or its settings.
                    resume_thread = attempted_thread
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
                    announce('Session stopped: no ready work can proceed. Read the current task handoff for the blocker.',
                             style='bold red', final=True)
                    return 2
                if result['status'] == 'complete':
                    if not all(current.values()):
                        raise Error('Codex reported completion while checklist tasks remain unfinished.')
                    if handoff_digest(root) == before:
                        raise Error('Codex did not save a final completion handoff in Continuation.md.')
                    finish_session(root, session, 'complete', 'Checklist, cleanup and final handoff confirmed.', live, update)
                    update(status='complete', reason='checklist-and-handoff-complete', tasks=sorted(current))
                    announce('All documented tasks are complete.', final=True)
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
            update(status='needs-review', reason='unconfirmed-handoff', cli_pid=None)
            announce('Session stopped: review required. Launcher exiting; inspect the current task handoff.',
                     style='bold red', final=True)
            if isinstance(exc, OSError):
                raise Error(f'Local I/O or process startup failed (errno {exc.errno}); '
                            'reconcile the current task handoff and owned operations before restarting.') from exc
            raise
        finally:
            for sig, handler in old_signals.items():
                signal.signal(sig, handler)


def wait_for_restart(root, args):
    """Wait for the old run's lock, then exec the launcher as it exists on disk.

    This runs in a detached process so even a supervisor loaded before restart
    support can finish via its existing STOP protocol. Never signal that process
    or infer successful cleanup merely from its disappearance.
    """
    storage = root / STORAGE
    private_directory(storage)
    startup_deadline = time.monotonic() + 5
    while True:
        try:
            request = json.loads((storage / 'STOP').read_text())
        except (FileNotFoundError, ValueError):
            request = {}
        if (not isinstance(request, dict)
                or request.get('request_id') != args.restart_of
                or request.get('restart_id') != args.request_id
                or kill_requested(storage, args.restart_of)):
            print('Queued restart cancelled by a newer control request.', flush=True)
            return 0
        try:
            with exclusive(storage):
                state = read_state(storage)
                if state.get('request_id') != args.restart_of:
                    print('Queued restart cancelled: another run has taken over.', flush=True)
                    return 0
                if state.get('status') == 'launching' and time.monotonic() < startup_deadline:
                    # start releases its reservation lock before its child boots.
                    pass
                elif state.get('status') == 'complete':
                    print('Queued restart cancelled: all documented tasks are complete.', flush=True)
                    return 0
                elif state.get('status') != 'stopped':
                    raise Error('Queued restart refused: the previous run did not stop at a safe boundary. '
                                'Inspect status and the current task handoff.')
                else:
                    state.update(status='launching', request_id=args.request_id, thread_id=None,
                                 resumable=True, updated=stamp())
                    write_json(storage / 'state.json', state)
                    break
        except Busy:
            pass
        time.sleep(0.1)
    command = [sys.executable, '-I', '-B', str(root / 'tools/codex_slices.py'), 'run',
               '--request-id', args.request_id, '--max-slices', str(args.max_slices),
               '--max-api-retries', str(args.max_api_retries)]
    if args.live_output_fd is not None:
        os.set_inheritable(args.live_output_fd, True)
        command.extend(('--live-output-fd', str(args.live_output_fd)))
    print('Previous launcher stopped safely. Reloading launcher code from disk.', flush=True)
    os.execv(sys.executable, command)


def main(argv=None, *, root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('action', choices=('start', 'run', 'status', 'stop', 'restart', 'kill'),
                        help='start detached, resume a killed conversation, or monitor an ongoing run; '
                             'run foreground; '
                             'status inspect; stop at slice boundary; restart after safe stop; kill interrupt now')
    parser.add_argument('--max-slices', type=int, help='Stop after this many slices; default 0 runs until complete; restart inherits the saved limit.')
    parser.add_argument('--max-api-retries', type=int, help='Retries per consecutive transient failure before tool use; default 12; restart inherits the saved limit.')
    parser.add_argument('--reconciled', action='store_true', help='Start fresh after the operator has reconciled an interrupted run and all owned cleanup.')
    parser.add_argument('--request-id', help=argparse.SUPPRESS)
    parser.add_argument('--live-output-fd', type=int, help=argparse.SUPPRESS)
    parser.add_argument('--restart-of', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.request_id:
        try:
            args.request_id = str(uuid.UUID(args.request_id))
        except ValueError:
            parser.error('request-id must be a UUID')
    if args.restart_of and (args.action != 'run' or not args.request_id):
        parser.error('restart-of requires run and request-id')
    if args.action == 'restart' and args.reconciled:
        parser.error('restart cannot bypass handoff checks with --reconciled')
    if ((args.max_slices is not None and args.max_slices < 0)
            or (args.max_api_retries is not None and not 0 <= args.max_api_retries <= 100)):
        parser.error('max-slices must be nonnegative; max-api-retries must be between 0 and 100')
    try:
        storage = root / STORAGE
        saved = read_state(storage) if args.action == 'restart' else {}
        if args.max_slices is None:
            args.max_slices = saved.get('max_slices', 0)
        if args.max_api_retries is None:
            args.max_api_retries = saved.get('max_api_retries', 12)
        if (type(args.max_slices) is not int or args.max_slices < 0
                or type(args.max_api_retries) is not int or not 0 <= args.max_api_retries <= 100):
            raise Error('Saved launcher limits are invalid; specify valid limits explicitly.')
        if args.restart_of:
            return wait_for_restart(root, args)
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
        if args.action == 'kill':
            state = read_state(storage)
            if state.get('status') not in ('launching', 'running', 'retry-wait', 'between-slices'):
                print('No ongoing session to kill.')
                return 0
            private_directory(storage)
            if not state.get('resumable'):
                raise Error('This run predates kill/resume support; use stop and restart the launcher.')
            write_json(storage / 'KILL', {'requested': stamp(), 'request_id': state.get('request_id')})
            print('Kill requested. The active Codex child will be interrupted immediately; use status to confirm exit.')
            return 0
        if args.action == 'restart':
            state = read_state(storage)
            if state.get('status') not in ('launching', 'running', 'retry-wait', 'between-slices'):
                print('No ongoing launcher to restart. Use start to begin a run.')
                return 0
            if not state.get('request_id'):
                raise Error('The ongoing launcher has no run identity; stop it and use start after it exits.')
            private_directory(storage)
            request_id = str(uuid.uuid4())
            args.restart_of = state['request_id']
            write_json(storage / 'STOP', {'requested': stamp(), 'request_id': args.restart_of,
                                         'restart_id': request_id})
        if args.action == 'start':
            private_directory(storage)
            with exclusive(storage):
                state = read_state(storage)
                resume_thread = (saved_thread(state)
                                 if state.get('status') == 'killed' and not args.reconciled else None)
                if state.get('status') in ('launching', 'running', 'needs-review') and not args.reconciled:
                    raise Error('Previous work needs reconciliation; read state.json and the task handoff.')
                preflight(root)
                if resume_thread or not all(checklist(root).values()):
                    session_settings(root, state if resume_thread else None)
                request_id = str(uuid.uuid4())
                state.update(status='launching', request_id=request_id, resumable=True,
                             thread_id=resume_thread, updated=stamp(),
                             max_slices=args.max_slices, max_api_retries=args.max_api_retries)
                write_json(storage / 'state.json', state)
        if args.action in ('start', 'restart'):
            command = [sys.executable, '-I', '-B', str(root / 'tools/codex_slices.py'), 'run',
                       '--max-slices', str(args.max_slices), '--max-api-retries', str(args.max_api_retries),
                       '--request-id', request_id]
            if args.reconciled:
                command.append('--reconciled')
            if args.restart_of:
                command.extend(('--restart-of', args.restart_of))
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
                if args.action == 'restart':
                    print('Restart queued. The current slice will finish and clean up, then the launcher '
                          'will reload from disk. Use stop to cancel the restart.')
                else:
                    print(f'Launcher started (PID {child.pid}). Use status or stop to manage it.')
                return 0
            print('Launcher exited; read output/codex-slices/launcher.log and run status.')
            return code
        return run(root, args)
    except Busy as exc:
        if args.action == 'start':
            try:
                return attach_monitor(storage)
            except KeyboardInterrupt:
                return 0
            except (Error, OSError) as monitor_error:
                print(f'codex-slices: {monitor_error}', file=sys.stderr)
                return 2
        print(f'codex-slices: {exc}', file=sys.stderr)
        return 2
    except Error as exc:
        print(f'codex-slices: {exc}', file=sys.stderr)
        return 2
    except OSError as exc:
        print(f'codex-slices: local I/O or process startup failed (errno {exc.errno}).', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
