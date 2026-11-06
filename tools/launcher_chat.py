"""Private observer mailbox and shared interactive conversation for workflows.

The existing supervisor owns the process, logs and nested-test cleanup. This
module owns input/completion gates; adapters own native conversation protocols.
Observers never signal agent PIDs.
"""

import codecs
import fcntl
import json
import time

from agent_adapter import SessionEvent
import detached_launcher as launcher
from launcher_render import SCROLLBACK_CHARACTERS, clean
from launcher_progress import read_progress
from launcher_runtime import AgentCapacityUnavailable

MAX_INPUT = 64 * 1024
MAX_QUEUE = 256 * 1024
STATUS_PREFIX = 'LAUNCHER_STATUS '
TASK_STATUSES = (
    'Investigating',
    'Root cause identified, fixing',
    'Testing fix, previous error point not reached yet',
    'Testing fix, previous error point passed',
    'Running',
    'Collecting diagnostic evidence',
    'Diagnostic case passed; awaiting interpretation',
)


def task_info(run, task):
    path = run / 'task-info.json'
    info = json.loads(path.read_text()) if path.exists() else {}
    if info.get('task_id') == task:
        return {key: value for key, value in info.items() if key != 'previous_tasks'}
    return info.get('previous_tasks', {}).get(task, {'task_id': task})


def update_task_info(run, task, value):
    """Retain task-local error and status clocks through retries/suspension."""
    path = run / 'task-info.json'
    previous = json.loads(path.read_text()) if path.exists() else {}
    history = previous.get('previous_tasks', {}).copy()
    if previous.get('task_id') not in (None, task):
        history[previous['task_id']] = {key: item for key, item in previous.items()
                                       if key != 'previous_tasks'}
    current = task_info(run, task)
    previous_status = current.get('status')
    current.update(value)
    if 'last_error' in value:
        current['last_error_at'] = time.time()
        current['status'] = value.get('status', TASK_STATUSES[0])
    if not current.get('last_error') or current['last_error'] == '-':
        current['status'] = 'Running'
    elif current.get('status') not in TASK_STATUSES or current['status'] == 'Running':
        current['status'] = TASK_STATUSES[0]
    if current['status'] != previous_status or 'status_at' not in current:
        current['status_at'] = time.time()
    history.pop(task, None)
    launcher.atomic(path, dict(current, previous_tasks=history))


def task_info_instructions(run, task):
    info = task_info(run, task)
    # Older sessions may retain this field; titles now come from the task queue.
    info.pop('explanation', None)
    return ("\nThe launcher displays the task's title directly from the execution plan. "
            "Do not send a separate task explanation. In your first commentary, "
            "send a single line beginning LAUNCHER_STATUS followed by a JSON object. "
            "Use everyday, non-technical language without commands, paths or error codes. "
            "Use status only with one of these exact values: " + json.dumps(TASK_STATUSES) + ". "
            "Use Running while there is no last error. Use Investigating when a new error occurs. "
            "Otherwise keep the retained "
            "status until the facts change. Report Root cause identified, fixing only after identifying "
            "the cause. Before launching a test or retry that will verify the fix at the previous "
            "error point, send a separate commentary line: "
            'LAUNCHER_STATUS {"status":"Testing fix, previous error point not reached yet"}. '
            "Do this before the verification tool call, not after its result; do not leave the "
            "panel on fixing while that verification runs. Keep this yellow status during setup, "
            "earlier steps and waiting for evidence that the previous error point passed. Report "
            "Testing fix, previous error point passed only after observing that evidence. Starting "
            "or completing unrelated tests does not prove it. If a changed fix needs fresh "
            "verification, report the yellow status again before its retry even if an earlier "
            "candidate passed that point. "
            "When an error occurs in this task, send last_error with a short plain-language summary "
            "and status Investigating. The launcher timestamps it. Report each new occurrence once, "
            "including a recurrence; do not repeat an old error on retries or reconnects. "
            "Omit last_error until an error occurs; never clear it or replace it with a dash after fixing it. "
            "Retained task information: " + json.dumps(info) + ". "
            "Update status when it changes. "
            "These fields are presentation only, never acceptance evidence, and are independent "
            "of your required final workflow JSON. Developer messages steer the current work; "
            "preserve the original task and acceptance requirements.\n")


def status_update(run, task, text):
    """Validate panel metadata identically for app-server and JSONL agents."""
    value = json.loads(text)
    if not isinstance(value, dict) or set(value) - {'explanation', 'status', 'last_error'}:
        raise ValueError('invalid task update')
    if any(not isinstance(v, str) or not v.strip() or len(v) > 2000 for v in value.values()):
        raise ValueError('invalid task update')
    value = {k: clean(v).strip() for k, v in value.items()}
    if any(not v for v in value.values()) or ('status' in value and value['status'] not in TASK_STATUSES):
        raise ValueError('invalid task update')
    if value.get('last_error') == '-':
        raise ValueError('last error must describe a new occurrence')
    if 'last_error' in value:
        value.setdefault('status', TASK_STATUSES[0])
    update_task_info(run, task, value)


def task_message(run, task, text):
    """Consume valid status commentary wherever it appears, preserving prose."""
    parts = []
    cursor = search = 0
    while (start := text.find(STATUS_PREFIX, search)) != -1:
        search = start + len(STATUS_PREFIX)
        if start and not text[start - 1].isspace():
            continue
        payload = text[search:].lstrip()
        try:
            _, end = json.JSONDecoder().raw_decode(payload)
            status_update(run, task, payload[:end])
        except (ValueError, TypeError):
            continue
        parts.append(text[cursor:start])
        cursor = search = len(text) - len(payload) + end
    if not parts:
        return text
    parts.append(text[cursor:])
    return ''.join(parts).strip()


def read_state(run):
    try:
        return json.loads((run / 'chat-state.json').read_text())
    except FileNotFoundError:
        return {'session': None, 'status': 'starting'}


def send_input(run, kind, text='', *, cancel_waiting=True, expected_session=None):
    if kind not in ('message', 'interrupt') or len(text.encode('utf-8')) > MAX_INPUT:
        raise ValueError('chat message is too large or invalid')
    with launcher.lock(run / 'chat-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        state = read_state(run)
        if expected_session is not None and state.get('session') != expected_session:
            raise ValueError('Session changed; review the current session before sending.')
        if kind == 'interrupt' and state['status'] in ('interrupting', 'cleaning'):
            # A second Ctrl+C cancels the workflow, even before turn cleanup
            # finishes. Repeated Escape only interrupts the current turn.
            if cancel_waiting:
                (run / 'cancel').touch(mode=0o600)
            return
        if kind == 'interrupt' and state['status'] in ('waiting', 'blocked', 'finished'):
            if cancel_waiting:
                (run / 'cancel').touch(mode=0o600)
            return
        path = run / 'chat-inbox.json'
        entries = json.loads(path.read_text()) if path.exists() else []
        if kind == 'interrupt' and any(entry['kind'] == 'interrupt'
                and entry['session'] == state['session'] for entry in entries):
            if cancel_waiting:
                (run / 'cancel').touch(mode=0o600)
            return
        entries.append({'kind': kind, 'text': text, 'session': state['session'],
                        'cancel_waiting': cancel_waiting})
        if len(json.dumps(entries).encode('utf-8')) > MAX_QUEUE:
            raise ValueError('chat queue is full; wait for the agent to read it')
        launcher.atomic(path, entries)


def take_input(run):
    with launcher.lock(run / 'chat-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        path = run / 'chat-inbox.json'
        entries = json.loads(path.read_text()) if path.exists() else []
        if entries:
            launcher.atomic(path, [])
        return entries


class AppSession:
    def __init__(self, root, run, command, renderer, *, on_interrupted=None,
                 session_state=None):
        self.root, self.run, self.renderer = root, run, renderer
        state = (session_state if session_state is not None else
                 json.loads((run / 'checkpoint.json').read_text()))
        self.session = state.get('total_sessions', state['task_sessions'])
        self.task_session = state['task_sessions']
        self.task = state['task_id']
        update_task_info(run, self.task, {})
        self.model = command.request.model
        self.effort = command.request.effort
        self.prompt = (run / 'prompt.txt').read_text()
        self.protocol = command.protocol
        if self.protocol is None:
            raise ValueError('interactive agent session requires a protocol handler')
        self.outgoing = self.protocol.outgoing
        self.messages = []
        self.capacity_inputs = []
        self.final = None
        self.final_text = ''
        self.done = False
        self.completed = False
        self.interrupt_requested = False
        self.interrupting = False
        self.on_interrupted = on_interrupted
        progress = read_progress(run)
        self.progress_key = progress[-1]['key'] if progress else None
        self.started_at = time.time()
        self.turn_started_at = None
        self.streaming_id = None
        self.streaming_text = ''
        self.streaming_dirty = False
        self.preview_at = 0
        self.publish('starting')
        self.protocol.start()

    def publish(self, status):
        with launcher.lock(self.run / 'chat-gate') as gate:
            fcntl.flock(gate, fcntl.LOCK_EX)
            self.publish_locked(status)

    def publish_locked(self, status):
        state = {
            'session': self.session, 'task_session': self.task_session,
            'task_id': self.task, 'status': status, 'started_at': self.started_at,
            'model': self.model, 'effort': self.effort,
            'progress_key': self.progress_key}
        if status == 'running' and self.turn_started_at is not None:
            state['turn_started_at'] = self.turn_started_at
        if status == 'finished':
            state['finished_at'] = time.time()
        launcher.atomic(self.run / 'chat-state.json', state)

    def start_turn(self, text):
        self.final = None
        self.final_text = ''
        self.completed = False
        self.turn_started_at = time.time()
        self.publish('running')
        self.protocol.start_turn(text)

    def preview(self, *, force=False):
        now = time.monotonic()
        if not self.streaming_dirty or (not force and now < self.preview_at):
            return
        self.preview_at = now + .1
        self.streaming_dirty = False
        text = self.streaming_text
        # Status metadata and workflow results are interpreted only after item
        # completion. Withhold incomplete status prefixes as well as payloads.
        if text.lstrip().startswith(('{', '```')):
            text = ''
        else:
            text = text.split(STATUS_PREFIX, 1)[0]
            for size in range(len(STATUS_PREFIX) - 1, 0, -1):
                if text.endswith(STATUS_PREFIX[:size]):
                    text = text[:-size]
                    break
        self.renderer.preview_message(text)

    def clear_preview(self):
        if self.streaming_id is None and not self.streaming_dirty:
            return
        self.streaming_id = None
        self.streaming_text = ''
        self.streaming_dirty = True
        self.preview(force=True)

    def poll(self):
        if self.done:
            return
        for entry in take_input(self.run):
            if entry['session'] not in (None, self.session):
                # Text submitted at a session boundary still reaches the next
                # agent. An old interrupt must never stop that new session.
                if entry['kind'] == 'interrupt':
                    continue
            if entry['kind'] == 'message':
                self.messages.append(entry['text'])
                self.capacity_inputs.append(entry['text'])
            elif self.interrupt_requested or self.interrupting:
                # The next key can arrive after take_input drains the inbox
                # but before the first interruption is published.
                if entry.get('cancel_waiting', True):
                    (self.run / 'cancel').touch(mode=0o600)
            else:
                self.interrupt_requested = True
        if self.interrupt_requested and self.protocol.active_turn and not self.interrupting:
            self.protocol.interrupt()
            self.interrupting = True
            self.publish('interrupting')
        # Complete interruption and owned cleanup before delivering a queued
        # continuation. Late acknowledgements still belong to the old turn.
        self.finish_turn()
        if (self.messages and self.protocol.ready and not self.interrupt_requested
                and not self.protocol.turn_requests_pending):
            text = '\n\n'.join(self.messages)
            self.messages.clear()
            self.renderer.message(text, 'You')
            if self.protocol.active_turn:
                self.protocol.steer(text)
            else:
                self.start_turn(text)
        # Publish at most ten times per second, even with a continuously ready
        # output pipe. Completed text still replaces the preview immediately.
        self.preview()

    def finish_turn(self):
        # Only poll() may accept a result: response handlers cannot know whether
        # the observer has queued new input since the previous mailbox read.
        if self.completed and not self.protocol.turn_requests_pending:
            if self.interrupt_requested:
                self.publish('cleaning')
                if self.on_interrupted:
                    self.on_interrupted()
                self.interrupt_requested = self.interrupting = False
                self.final = None
                self.publish('waiting')
                self.renderer.message('Interrupted. Send a message to continue, or press Ctrl+C again to exit.')
            elif self.messages:
                return
            else:
                # Serialize the final mailbox check and acceptance against
                # send_input(), including input arriving after take_input().
                with launcher.lock(self.run / 'chat-gate') as gate:
                    fcntl.flock(gate, fcntl.LOCK_EX)
                    inbox = self.run / 'chat-inbox.json'
                    if inbox.exists() and json.loads(inbox.read_text()):
                        return
                    if self.final is not None:
                        launcher.atomic(self.run / 'agent-result.json', self.final)
                    else:
                        # A successful turn without a usable result belongs to
                        # the shared response-recovery gate, not an idle chat
                        # that needs developer input to make progress.
                        (self.run / 'agent-result.json').write_text(self.final_text, encoding='utf-8')
                    self.publish_locked('finished')
                    self.done = True
            self.completed = False

    def feed(self, data):
        for event in self.protocol.feed(data):
            self.event(event)

    def fail(self, failure):
        """Retain the provider's reason before supervisor cleanup exits."""
        self.clear_preview()
        message = failure['message']
        self.final = None
        self.completed = False
        launcher.atomic(self.run / 'agent-error.json', {
            'message': message, 'context': failure['context'], **failure['details']})
        update_task_info(self.run, self.task, {'last_error': clean(failure['task_error'])})
        self.publish('finished')
        if failure['capacity']:
            failure = AgentCapacityUnavailable(message)
            failure.prompt = self.prompt
            if self.capacity_inputs:
                failure.prompt += '\n\nDeveloper messages received during this session:\n' + json.dumps(self.capacity_inputs)
            raise failure
        raise ValueError(message)

    def event(self, event):
        kind, data = event.kind, event.data
        if kind == 'ready':
            self.start_turn(self.prompt)
        elif kind == 'retry_input':
            self.messages.insert(0, data['text'])
        elif kind == 'discard_result':
            self.final = None
        elif kind == 'text_delta':
            if data['id'] != self.streaming_id:
                self.streaming_id = data['id']
                self.streaming_text = ''
            self.streaming_text = (self.streaming_text + data['text'])[:SCROLLBACK_CHARACTERS]
            self.streaming_dirty = True
        elif kind == 'text':
            self.text(data)
        elif kind in ('item', 'diagnostic', 'command_output', 'usage', 'notice'):
            self.renderer.event(event)
        elif kind == 'turn_completed':
            self.clear_preview()
            if data['interrupted']:
                self.interrupt_requested = True
                self.final = None
                self.completed = True
                self.publish('interrupting')
            else:
                # Poll the mailbox before accepting the result, including text
                # submitted while the completion notification was in transit.
                self.completed = True
        elif kind == 'failure':
            self.fail(data)

    def text(self, data):
        if not data['complete']:
            self.streaming_id = data['id']
            self.streaming_text = data['text'][:SCROLLBACK_CHARACTERS]
            self.streaming_dirty = True
            return
        # Completed text is authoritative; provisional output cannot be a result.
        self.clear_preview()
        text = task_message(self.run, self.task, data['text'])
        if not text:
            return
        value = self.protocol.finalize_result(text)
        self.final_text = text
        self.final = (value if value is not None and value.get('task_id') == self.task
                      and 'status' in value else None)
        self.renderer.event(SessionEvent('text', dict(data, text=text)))

    def status_update(self, text):
        try:
            status_update(self.run, self.task, text)
        except (ValueError, TypeError):
            # Rejected metadata is still an agent message. Use the shared
            # renderer so its prose reaches both transcript panes.
            self.renderer.event(SessionEvent('text', {
                'text': STATUS_PREFIX + text, 'complete': True}))


class ChatEditor:
    """Multiline Unicode editor; Enter sends, Alt+Enter/Ctrl+J inserts a line."""
    def __init__(self, send):
        self.send = send
        self.text = ''
        self.cursor = 0
        self.pending = b''
        self.paste = False
        self.paste_cr = False
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        self.error = ''

    def insert(self, text):
        if len((self.text + text).encode('utf-8')) > MAX_INPUT:
            self.error = 'Message is too long.'
            return
        self.text = self.text[:self.cursor] + text + self.text[self.cursor:]
        self.cursor += len(text)

    def feed(self, data):
        self.pending += data
        keys = (b'\x1b[200~', b'\x1b[201~', b'\x1b[13;2u', b'\x1b[27;2;13~',
                b'\x1b\r', b'\x1b[A', b'\x1b[B', b'\x1b[C', b'\x1b[D',
                b'\x1b[H', b'\x1b[F', b'\x1bOH', b'\x1bOF', b'\x1b[3~')
        while self.pending:
            key = next((key for key in keys if self.pending.startswith(key)), None)
            if key is None and any(key.startswith(self.pending) for key in keys):
                break
            if key:
                self.pending = self.pending[len(key):]
                if key in (b'\x1b[200~', b'\x1b[201~'):
                    self.paste = key == b'\x1b[200~'
                    self.paste_cr = False
                elif self.paste:
                    continue
                elif key in (b'\x1b\r', b'\x1b[13;2u', b'\x1b[27;2;13~'):
                    self.insert('\n')
                elif key == b'\x1b[D':
                    self.cursor = max(0, self.cursor - 1)
                elif key == b'\x1b[C':
                    self.cursor = min(len(self.text), self.cursor + 1)
                elif key in (b'\x1b[H', b'\x1bOH'):
                    self.cursor = self.text.rfind('\n', 0, self.cursor) + 1
                elif key in (b'\x1b[F', b'\x1bOF'):
                    end = self.text.find('\n', self.cursor)
                    self.cursor = len(self.text) if end < 0 else end
                elif key == b'\x1b[3~':
                    self.text = self.text[:self.cursor] + self.text[self.cursor + 1:]
                elif key in (b'\x1b[A', b'\x1b[B'):
                    lines = self.text.split('\n')
                    line = self.text[:self.cursor].count('\n')
                    column = self.cursor - (self.text.rfind('\n', 0, self.cursor) + 1)
                    line = max(0, line - 1) if key == b'\x1b[A' else min(len(lines) - 1, line + 1)
                    self.cursor = sum(len(v) + 1 for v in lines[:line]) + min(column, len(lines[line]))
                continue
            byte, self.pending = self.pending[:1], self.pending[1:]
            if self.paste:
                if byte != b'\n' or not self.paste_cr:
                    self.insert('\n' if byte == b'\r' else '    ' if byte == b'\t' else clean(self.decoder.decode(byte)))
                self.paste_cr = byte == b'\r'
            elif byte in (b'\r', b'\n'):
                if byte == b'\n':
                    self.insert('\n')
                elif self.text.strip():
                    try:
                        self.send(self.text)
                    except (OSError, ValueError) as error:
                        self.error = str(error)
                    else:
                        self.text, self.cursor, self.error = '', 0, ''
            elif byte in (b'\x7f', b'\x08') and self.cursor:
                self.text = self.text[:self.cursor - 1] + self.text[self.cursor:]
                self.cursor -= 1
            elif byte == b'\x15':
                start = self.text.rfind('\n', 0, self.cursor) + 1
                self.text = self.text[:start] + self.text[self.cursor:]
                self.cursor = start
            elif byte == b'\x0b':
                end = self.text.find('\n', self.cursor)
                end = len(self.text) if end < 0 else end + (end == self.cursor)
                self.text = self.text[:self.cursor] + self.text[end:]
            elif byte == b'\x01':
                self.cursor = self.text.rfind('\n', 0, self.cursor) + 1
            elif byte == b'\x05':
                end = self.text.find('\n', self.cursor)
                self.cursor = len(self.text) if end < 0 else end
            elif byte >= b' ':
                self.insert(clean(self.decoder.decode(byte)))
