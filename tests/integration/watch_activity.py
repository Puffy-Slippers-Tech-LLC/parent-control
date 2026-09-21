"""Bounded command transcript, delivered only to the authenticated VM caller.

No guest connection, input endpoint, process signalling or persistent raw log.
Unknown commands expose a label and completion only; transports opt reviewed
text commands in. Stdin, archives and private observation replies stay private.
"""

import atexit
from contextlib import contextmanager
from functools import wraps
import json
import os
from pathlib import Path
import re
import shlex
import socket
import struct
import threading
import time
import uuid

_instance = None
_attempted = False
_secrets = set()
CSI = re.compile(r'\x1b\[[0-9;:?]*[ABCDGHJKSTfhlmsu]')


class TerminalControls:
    """Keep display controls; discard OSC/DCS including split clipboard payloads."""

    def __init__(self):
        self.state = 'text'
        self.pending = bytearray()

    def feed(self, data):
        result = bytearray()
        for char in data:
            if self.state == 'text':
                if char == 27:
                    self.state = 'escape'
                elif char >= 32 or char in (8, 9, 10, 13):
                    result.append(char)
            elif self.state == 'escape':
                if char == 91:
                    self.state, self.pending = 'csi', bytearray(b'\x1b[')
                else:
                    self.state = 'string' if char in (93, 80, 94, 95) else 'text'
            elif self.state in ('csi', 'discard-csi'):
                if self.state == 'csi':
                    self.pending.append(char)
                if 64 <= char <= 126:
                    if self.state == 'csi' and CSI.fullmatch(self.pending.decode('ascii', errors='replace')):
                        result.extend(self.pending)
                    self.state, self.pending = 'text', bytearray()
                elif len(self.pending) > 128:
                    self.state, self.pending = 'discard-csi', bytearray()
            elif self.state == 'string':
                if char == 7:
                    self.state = 'text'
                elif char == 27:
                    self.state = 'string-escape'
            elif self.state == 'string-escape':
                self.state = 'text' if char == 92 else 'string'
        return bytes(result)


def secret(value):
    if value:
        _secrets.add(value)


def clean(text):
    text = TerminalControls().feed(text.encode('utf-8')).decode('utf-8')
    for value in tuple(_secrets):
        text = text.replace(value, '[redacted]')
    lines = []
    for line in text.split('\n'):
        plain = CSI.sub('', line)
        if (any(value in plain for value in tuple(_secrets)) or re.search(
                r'''(?i)(?:password|passwd|secret|token|authorization)["']?\s*[:=]|private key|ssh-ed25519|\$6\$''', plain)):
            line = '[private text omitted]'
        lines.append(line)
    text = '\n'.join(lines)
    return text


class Transcript:
    def __init__(self):
        self.lock = threading.Lock()
        self.text = ''
        self.sequence = 0
        self.offset = 0
        self.operations = {}
        self.intent = ('', 0)

    def begin(self, label, *, priority=1):
        token = object()
        with self.lock:
            self.operations[token] = (priority, time.monotonic_ns(), clean(label))
        return token

    def end(self, token):
        with self.lock:
            self.operations.pop(token, None)

    def announce(self, label):
        with self.lock:
            self.intent = (clean(label), time.monotonic_ns())

    def append(self, text):
        with self.lock:
            combined = self.text + clean(text)
            self.offset += max(0, len(combined) - 8000)
            self.text = combined[-8000:]
            self.sequence += 1

    def packet(self, run):
        with self.lock:
            label, started = self.intent
            priority = 0
            if self.operations:
                priority, started, label = max(self.operations.values())
            return json.dumps(dict(run=run, sequence=self.sequence,
                                   text=self.text, offset=self.offset,
                                   operation=' '.join(label.split())[:384],
                                   operation_started_ns=started,
                                   operation_priority=priority,
                                   operation_active=bool(self.operations)), ensure_ascii=False).encode()


class Publication:
    def __init__(self, uid):
        from e2e_watch import Publication as Registry
        self.transcript = Transcript()
        self.stop = threading.Event()
        self.registry = Registry(uid, uuid.uuid4().hex, registry='activity.json')
        self.uid = uid
        try:
            self.registry.server.settimeout(.2)
            self.registry.publish()
            self.thread = threading.Thread(target=self.serve, daemon=True, name='vm-watch-activity')
            self.thread.start()
        except BaseException:
            self.registry.close()
            raise

    def serve_peer(self, peer):
        # Authenticate before sending any transcript. Never read a request.
        uid = struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
        if uid == self.uid:
            peer.setblocking(False)
            peer.send(self.transcript.packet(self.registry.run))

    def serve(self):
        while not self.stop.is_set():
            try:
                peer, _ = self.registry.server.accept()
                with peer:
                    self.serve_peer(peer)
            except OSError:
                continue

    def close(self):
        self.stop.set()
        self.thread.join(timeout=1)
        self.registry.close()


def current():
    global _instance, _attempted
    uid = os.environ.get('PKEXEC_UID', '')
    if not _attempted and os.geteuid() == 0 and uid.isdecimal() and int(uid) > 0:
        _attempted = True
        try:
            _instance = Publication(int(uid))
            atexit.register(_instance.close)
        except Exception:
            # Optional viewing must never prevent the protected operation.
            return None
    return _instance.transcript if _instance is not None else None


def event(label):
    transcript = current()
    if transcript is not None:
        transcript.announce(label)
        transcript.append('\n[VM] ' + label + '\n')


@contextmanager
def operation(label, *, priority=2):
    """Publish trusted intent synchronously before work; restore enclosing intent.

    Use fixed nonsecret prose. A nested command cannot replace an enclosing
    operation (for example restoring a snapshot) with a guard's qemu-img probe.
    Each publisher has its own socket, so child transports and other controllers
    cannot overwrite its registration or erase its still-running operation.
    """
    transcript = current()
    token = transcript.begin(label, priority=priority) if transcript is not None else None
    try:
        yield
    finally:
        if transcript is not None:
            transcript.end(token)


def observed(label):
    """The shared entry guard for fixed VM operations, including non-SSH work."""
    def decorate(function):
        @wraps(function)
        def invoke(*args, **kwargs):
            with operation(label):
                return function(*args, **kwargs)
        return invoke
    return decorate


def remote_command(argv, has_input):
    """Expose reviewed command text without the SSH key/host/identity guard."""
    args = list(map(str, argv))
    for arg in args:
        if arg.startswith('ONPC_EXPECTED_RUN='):
            secret(arg.partition('=')[2])
    # Inline programs, file transfers and observation helpers can carry account
    # data or binary replies. They still appear as running/completed operations.
    private = has_input or any(arg in ('-c', 'tar', 'cat') or arg.endswith('.py') for arg in args)
    pytest = '-m' in args and args[args.index('-m') + 1:][:1] == ['pytest']
    helper = any(arg.endswith('/system_guest.py') for arg in args)
    if (pytest or helper) and not has_input:
        return 'SSH $ ' + shlex.join(args), True
    if private:
        return 'SSH $ ' + Path(args[0]).name + ' [private program or transfer]', False
    return 'SSH $ ' + shlex.join(args), True


class Command:
    def __init__(self, transcript, label, visible):
        self.transcript, self.visible = transcript, visible
        self.token = transcript.begin(label)
        self.pending = {'stdout': b'', 'stderr': b''}
        self.controls = {stream: TerminalControls() for stream in self.pending}
        self.dropping = set()
        transcript.append('\n' + label + '\n')
        if not visible:
            transcript.append('[private command data omitted]\n')

    def output(self, data, stream):
        if not self.visible:
            return
        pending = self.pending[stream] + self.controls[stream].feed(data)
        lines = re.split(rb'(?<=[\r\n])', pending)
        self.pending[stream] = lines.pop()
        if stream in self.dropping:
            if not lines:
                self.pending[stream] = b''
                return
            lines.pop(0)
            self.dropping.remove(stream)
        for line in lines:
            self.transcript.append(line.decode('utf-8', errors='replace'))
        if len(self.pending[stream]) > 65536:
            self.pending[stream] = b''
            self.dropping.add(stream)
            self.transcript.append('[oversized output line omitted]\n')

    def finish(self, status):
        for stream, data in self.pending.items():
            if data:
                self.controls[stream] = TerminalControls()
                self.output(b'\n', stream)
        self.transcript.append(f'[exit {status}]\n')
        self.transcript.end(self.token)


def command(args, selection=None):
    transcript = current()
    if transcript is None:
        return None
    label, visible = selection or ('Host $ ' + Path(args[0]).name, False)
    return Command(transcript, label, visible)
