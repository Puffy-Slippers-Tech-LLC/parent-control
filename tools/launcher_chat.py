"""Private observer mailbox and Codex app-server conversation for write-e2e.

The existing supervisor owns the process, logs and nested-test cleanup. This
module owns only the conversation protocol; observers never signal agent PIDs.
"""

import codecs
import fcntl
import json
from pathlib import Path

import detached_launcher as launcher
from launcher_render import clean

MAX_INPUT = 64 * 1024
MAX_QUEUE = 256 * 1024
STATUS_PREFIX = 'LAUNCHER_STATUS '


def read_state(run):
    try:
        return json.loads((run / 'chat-state.json').read_text())
    except FileNotFoundError:
        return {'session': None, 'status': 'starting'}


def send_input(run, kind, text='', *, cancel_waiting=True):
    if kind not in ('message', 'interrupt') or len(text.encode('utf-8')) > MAX_INPUT:
        raise ValueError('chat message is too large or invalid')
    with launcher.lock(run / 'chat-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        state = read_state(run)
        if kind == 'interrupt' and state['status'] in ('interrupting', 'cleaning'):
            # Repeated Cancel/Ctrl+C during the same interruption must not
            # become a fresh interrupt after cleanup has reopened the session.
            return
        if kind == 'interrupt' and state['status'] in ('waiting', 'blocked', 'finished'):
            if cancel_waiting:
                (run / 'cancel').touch(mode=0o600)
            return
        path = run / 'chat-inbox.json'
        entries = json.loads(path.read_text()) if path.exists() else []
        entries.append({'kind': kind, 'text': text, 'session': state['session']})
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


def app_command(command):
    """Preserve the launcher's policy overrides, replacing exec-only switches."""
    config = [value for index, value in enumerate(command) if index and command[index - 1] == '-c']
    return [command[0], 'app-server', '--listen', 'stdio://',
            *[arg for value in config for arg in ('-c', value)],
            '-c', 'approval_policy="never"', '-c', 'sandbox_mode="workspace-write"']


class AppSession:
    def __init__(self, root, run, command, renderer, *, on_interrupted=None):
        self.root, self.run, self.renderer = root, run, renderer
        state = json.loads((run / 'checkpoint.json').read_text())
        self.session = state.get('total_sessions', state['task_sessions'])
        self.task_session = state['task_sessions']
        self.task = state['task_id']
        self.model = command[command.index('--model') + 1]
        self.schema = json.loads(Path(command[command.index('--output-schema') + 1]).read_text())
        self.prompt = (run / 'prompt.txt').read_text()
        self.thread = self.turn = None
        self.pending = b''
        self.requests = {}
        self.counter = 0
        self.outgoing = bytearray()
        self.messages = []
        self.final = None
        self.done = False
        self.completed = False
        self.interrupt_requested = False
        self.interrupting = False
        self.on_interrupted = on_interrupted
        self.publish('starting')
        self.request('initialize', {'clientInfo': {'name': 'onpc_write_e2e',
                     'title': 'Write E2E', 'version': '1.0'},
                     'capabilities': {'experimentalApi': True}})

    def publish(self, status):
        with launcher.lock(self.run / 'chat-gate') as gate:
            fcntl.flock(gate, fcntl.LOCK_EX)
            self.publish_locked(status)

    def publish_locked(self, status):
        launcher.atomic(self.run / 'chat-state.json', {
            'session': self.session, 'task_session': self.task_session,
            'task_id': self.task, 'status': status})

    def request(self, method, params):
        self.counter += 1
        self.requests[self.counter] = (method, params)
        self.encode({'id': self.counter, 'method': method, 'params': params})

    def encode(self, packet):
        self.outgoing.extend((json.dumps(packet) + '\n').encode('utf-8'))

    def start_turn(self, text):
        self.final = None
        self.completed = False
        self.publish('running')
        self.request('turn/start', {'threadId': self.thread,
                     'input': [{'type': 'text', 'text': text}], 'outputSchema': self.schema})

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
            elif not self.interrupting:
                self.interrupt_requested = True
        if self.interrupt_requested and self.turn and not self.interrupting:
            self.request('turn/interrupt', {'threadId': self.thread, 'turnId': self.turn})
            self.interrupting = True
            self.publish('interrupting')
        # Complete interruption and owned cleanup before delivering a queued
        # continuation. Late acknowledgements still belong to the old turn.
        self.finish_turn()
        if (self.messages and self.thread and not self.interrupt_requested
                and not self.turn_requests_pending()):
            text = '\n\n'.join(self.messages)
            self.messages.clear()
            self.renderer.message(text, 'You')
            if self.turn:
                self.request('turn/steer', {'threadId': self.thread, 'expectedTurnId': self.turn,
                             'input': [{'type': 'text', 'text': text}]})
            else:
                self.start_turn(text)

    def turn_requests_pending(self):
        return any(method in ('turn/start', 'turn/steer', 'turn/interrupt')
                   for method, _ in self.requests.values())

    def finish_turn(self):
        # Only poll() may accept a result: response handlers cannot know whether
        # the observer has queued new input since the previous mailbox read.
        if self.completed and not self.turn_requests_pending():
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
            elif self.final is not None:
                # Serialize the final mailbox check and acceptance against
                # send_input(), including input arriving after take_input().
                with launcher.lock(self.run / 'chat-gate') as gate:
                    fcntl.flock(gate, fcntl.LOCK_EX)
                    inbox = self.run / 'chat-inbox.json'
                    if inbox.exists() and json.loads(inbox.read_text()):
                        return
                    launcher.atomic(self.run / 'agent-result.json', self.final)
                    self.publish_locked('finished')
                    self.done = True
            else:
                self.publish('waiting')
            self.completed = False

    def feed(self, data):
        lines = (self.pending + data).split(b'\n')
        self.pending = lines.pop()
        for line in lines:
            self.event(json.loads(line))

    def event(self, packet):
        if 'method' not in packet:
            method, params = self.requests.pop(packet['id'])
            if 'error' in packet:
                if method == 'turn/steer' and (self.completed or self.turn is None):
                    # The turn can finish between the observer's send and the
                    # server's read. Deliver once as a new turn in that case.
                    self.messages.insert(0, params['input'][0]['text'])
                    return
                if method == 'turn/interrupt' and self.completed:
                    # The completion won the race with interruption. Keep the
                    # conversation open rather than accepting its old result.
                    self.final = None
                    return
                raise ValueError(f"Codex {method}: {packet['error']}")
            result = packet['result']
            if method == 'initialize':
                self.encode({'method': 'initialized', 'params': {}})
                self.request('thread/start', {'model': self.model, 'cwd': str(self.root),
                             'approvalPolicy': 'never', 'sandbox': 'workspace-write',
                             'ephemeral': True})
            elif method == 'thread/start':
                self.thread = result['thread']['id']
                self.start_turn(self.prompt)
            elif method == 'turn/start':
                if not self.completed:
                    self.turn = result['turn']['id']
            return
        method, params = packet['method'], packet.get('params', {})
        if 'id' in packet:
            # Never grant a server-initiated approval or execute a requested
            # client tool. Workflow decisions use the existing blocker contract.
            self.encode({'id': packet['id'], 'error': {'code': -32601,
                         'message': 'Client operation unavailable; report a workflow blocker.'}})
            return
        # Adviser notifications must not replace the coordinator's turn/result.
        if params.get('threadId') not in (None, self.thread):
            return
        if method == 'turn/started':
            self.turn = params['turn']['id']
        elif method in ('item/started', 'item/completed'):
            self.item(params['item'], method == 'item/completed')
        elif method == 'thread/tokenUsage/updated' and self.renderer.on_usage:
            usage = params['tokenUsage']['last']
            self.renderer.on_usage({'input_tokens': usage.get('inputTokens'),
                'cached_input_tokens': usage.get('cachedInputTokens'),
                'output_tokens': usage.get('outputTokens'),
                'reasoning_output_tokens': usage.get('reasoningOutputTokens')})
        elif method == 'turn/completed':
            turn = params['turn']
            self.turn = None
            if turn['status'] == 'interrupted':
                self.interrupt_requested = True
                self.final = None
                self.completed = True
                self.publish('interrupting')
            elif turn['status'] == 'failed':
                raise ValueError(f"Codex turn failed: {turn.get('error')}")
            else:
                # Poll the mailbox before accepting the result, including text
                # submitted while the completion notification was in transit.
                self.completed = True
        elif method in ('error', 'warning'):
            self.renderer.message(str(params.get('message', params)), 'Agent notice')

    def item(self, item, complete):
        kind = item['type']
        if kind == 'agentMessage':
            if not complete:
                return
            text = item['text']
            if text.startswith(STATUS_PREFIX):
                self.status_update(text[len(STATUS_PREFIX):])
                return
            try:
                value = json.loads(text)
            except ValueError:
                value = None
            if isinstance(value, dict) and value.get('task_id') == self.task and 'status' in value:
                self.final = value
            item = {'id': item['id'], 'type': 'agent_message', 'text': text}
        elif kind == 'commandExecution':
            item = {'id': item['id'], 'type': 'command_execution', 'command': item['command'],
                    'aggregated_output': item.get('aggregatedOutput', ''),
                    'exit_code': item.get('exitCode'), 'status': item.get('status')}
        elif kind == 'fileChange':
            changes = [dict(change, kind=change['kind'].get('type', 'update')
                            if isinstance(change.get('kind'), dict) else change.get('kind', 'update'))
                       for change in item['changes']]
            item = dict(item, type='file_change', changes=changes)
        elif kind == 'mcpToolCall':
            item = dict(item, type='mcp_tool_call')
        elif kind == 'webSearch':
            item = dict(item, type='web_search')
        elif kind in ('reasoning', 'userMessage'):
            return
        else:
            if complete:
                self.renderer.code(json.dumps(item, ensure_ascii=False), 'json')
            return
        self.renderer.event({'type': 'item.completed' if complete else 'item.started', 'item': item})

    def status_update(self, text):
        try:
            value = json.loads(text)
            if not isinstance(value, dict) or set(value) - {'explanation', 'status'}:
                raise ValueError('invalid task update')
            if any(not isinstance(v, str) or not v.strip() or len(v) > 2000 for v in value.values()):
                raise ValueError('invalid task update')
            path = self.run / 'task-info.json'
            previous = json.loads(path.read_text()) if path.exists() else {}
            if previous.get('task_id') != self.task:
                previous = {'task_id': self.task}
            launcher.atomic(path, dict(previous, **{k: clean(v) for k, v in value.items()}))
        except (ValueError, TypeError):
            self.renderer.message(STATUS_PREFIX + text)


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
