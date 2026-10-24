"""One runner-owned recording of the shared watch, with latest case clips.

VM workers report trusted case boundaries, never start their own encoders.
The user-owned endpoint accepts metadata only and has no VM input capability.
"""

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
import json
import bisect
import math
import os
from pathlib import Path
import secrets
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
from functools import lru_cache
from collections import defaultdict

VARIABLE = 'ONPC_VM_RECORDING_CONTROL'
ROOT = Path(__file__).resolve().parents[1]
_capture_tokens = defaultdict(dict)


@dataclass
class Window:
    category: str
    identifier: int
    start_ns: int
    end_ns: int
    title: str = ''
    failed: bool = False
    interrupted: bool = False
    vms: set = field(default_factory=set)


class Timeline:
    """Merge concurrent and lifecycle executions by persistent case identity."""

    def __init__(self):
        self.windows = {}
        self.active = {}
        self.last = {}
        self.finished_vms = set()

    def event(self, vm, category, identifier, kind, at_ns, title=''):
        if category not in ('system', 'e2e') or type(identifier) is not int or identifier < 1:
            raise ValueError('recording: invalid case identity')
        if kind not in ('prepared', 'started', 'finished', 'failure') or type(at_ns) is not int or at_ns < 0:
            raise ValueError('recording: invalid case event')
        key = category, identifier
        if key not in self.windows:
            self.windows[key] = Window(category, identifier, at_ns, at_ns, title)
        window = self.windows[key]
        window.start_ns = min(window.start_ns, at_ns)
        window.end_ns = max(window.end_ns, at_ns)
        window.vms.add(vm)
        if kind in ('prepared', 'started'):
            previous = self.active.get(vm)
            if previous is not None and previous != key:
                self.windows[previous].end_ns = max(self.windows[previous].end_ns, at_ns)
                self.windows[previous].interrupted = True
            self.active[vm] = key
            self.last[vm] = key
            self.finished_vms.discard(vm)
        elif kind == 'failure':
            window.failed = True
        elif self.active.get(vm) == key:
            del self.active[vm]

    def finish_vm(self, vm, at_ns):
        if vm in self.finished_vms:
            return
        self.finished_vms.add(vm)
        if vm in self.last:
            window = self.windows[self.last[vm]]
            window.end_ns = max(window.end_ns, at_ns)
            if vm in self.active:
                window.interrupted = True
                del self.active[vm]

    def close(self, at_ns):
        for vm in tuple(self.active):
            self.finish_vm(vm, at_ns)


@lru_cache(maxsize=8)
def e2e_identities(root):
    document = json.loads((root / 'tests/e2e/scenarios.json').read_text())
    return {scenario['id'] + '/' + variant['id']:
            (variant['coverage_id'], scenario['title'])
            for scenario in document['scenarios'] for variant in scenario['variants']}


def case_identity(root, category, event):
    """Resolve public IDs without changing existing pytest/checkpoint nodeids."""
    nodeid = event.get('nodeid')
    if not isinstance(nodeid, str):
        return None
    if category == 'system':
        sys.path.insert(0, str(root / 'tests/integration'))
        try:
            from system_case_ids import identity_for_event
            identity = identity_for_event(nodeid)
        finally:
            sys.path.pop(0)
        return (identity.numeric_id, identity.title) if identity else None
    if category == 'e2e':
        return e2e_identities(root).get(nodeid)
    return None


def request(endpoint, value, *, timeout=5):
    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as peer:
        peer.settimeout(timeout)
        peer.connect(endpoint['socket'])
        peer.sendall(json.dumps(dict(value, nonce=endpoint['nonce'])).encode())
        reply = json.loads(peer.recv(8192))
    if reply.get('ok') is not True:
        raise RuntimeError('recording: control request failed')
    return reply


def report_event(root, category, event):
    endpoint = os.environ.get(VARIABLE)
    if not endpoint or category not in ('system', 'e2e'):
        return
    if event.get('kind') == 'collection':
        if not event.get('nodeids'):
            return
        event = dict(kind='prepared', nodeid=event['nodeids'][0])
    if event.get('kind') not in ('prepared', 'started', 'finished', 'failure'):
        return
    identity = case_identity(root, category, event)
    if identity is None:
        raise ValueError('recording: unregistered VM case')
    from vm_selection import selected
    vm = selected()
    request(json.loads(endpoint), dict(op='event', vm=vm.name, category=category,
        id=identity[0], title=identity[1], kind=event['kind'], at_ns=time.monotonic_ns()))


def report_finished():
    endpoint = os.environ.get(VARIABLE)
    if endpoint:
        from vm_selection import selected
        vm = selected(required=False)
        if vm is not None:
            request(json.loads(endpoint), dict(op='finished', vm=vm.name, at_ns=time.monotonic_ns()))


def protected_endpoint(root=ROOT):
    """Privileged controllers locate only their authenticated caller's session."""
    if VARIABLE in os.environ:
        return json.loads(os.environ[VARIABLE])
    from recording_control import endpoint
    return endpoint(root)


@contextmanager
def protect_capture(root=ROOT):
    """Seal recorded pixels before secret input; ACK is independent of watch."""
    endpoint = protected_endpoint(root)
    if endpoint is None:
        yield
        return
    token = secrets.token_hex(16)
    from vm_selection import selected
    vm = selected(required=False)
    owner = vm.name if vm is not None else '__controller__'
    _capture_tokens[owner][token] = endpoint
    request(endpoint, dict(op='seal', token=token, sealed=True))
    try:
        yield
    except BaseException:
        # An uncertain secret operation remains opaque until session shutdown.
        raise
    else:
        request(endpoint, dict(op='seal', token=token, sealed=False))
        _capture_tokens[owner].pop(token, None)


def capture_safe_after_shutdown(root=ROOT):
    """Only an owned, independently verified off-state may recover failed seals."""
    if not any(_capture_tokens.values()):
        return
    if os.geteuid() != 0:
        raise ValueError('recording: trusted shutdown owner required')
    from vm_selection import selected
    vm = selected(required=False)
    if vm is None:
        return
    for token, endpoint in tuple(_capture_tokens[vm.name].items()):
        request(endpoint, dict(op='seal', token=token, sealed=False))
        del _capture_tokens[vm.name][token]


def playable(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=codec_name,width,height', '-of', 'json', str(path)],
        stdin=subprocess.DEVNULL, capture_output=True, timeout=15, check=True)
    streams = json.loads(result.stdout).get('streams', [])
    if not (len(streams) == 1 and streams[0].get('codec_name') in ('vp8', 'vp9') and
            streams[0].get('width', 0) > 0 and streams[0].get('height', 0) > 0):
        return False
    # Decode the complete candidate before it can displace the previous clip.
    # A valid first keyframe says nothing about damaged later packets. Null
    # output keeps validation memory bounded even for long lifecycle clips.
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path),
        '-map', '0:v:0', '-progress', 'pipe:1', '-nostats', '-f', 'null', '-'],
        stdin=subprocess.DEVNULL, capture_output=True, timeout=120, check=True)
    return any(line.startswith(b'frame=') and int(line.partition(b'=')[2]) > 0
               for line in decoded.stdout.splitlines())


def keyframes(path):
    # Packet flags identify stream-copy boundaries without decoding the whole
    # session. Complete candidate decoding remains the publication guard.
    result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'packet=pts_time,flags',
        '-of', 'json', str(path)], stdin=subprocess.DEVNULL, capture_output=True,
        timeout=120, check=True)
    values = []
    for packet in json.loads(result.stdout)['packets']:
        if 'K' not in packet.get('flags', ''):
            continue
        try:
            value = float(packet['pts_time'])
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError('recording: invalid keyframe timestamp') from error
        if not math.isfinite(value) or value < 0:
            raise RuntimeError('recording: invalid keyframe timestamp')
        values.append(value)
    if not values:
        raise RuntimeError('recording: no keyframe packets')
    return sorted(values)


class Session:
    """A single shared renderer/encoder for the complete selected VM queue."""

    def __init__(self, root=ROOT, *, vm_names=None):
        self.root = Path(root)
        self.stack = ExitStack()
        self.timeline = Timeline()
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.errors = []
        self.previous = os.environ.get(VARIABLE)
        self.process = self.control = self.server = self.thread = None
        self.identity = None
        self.pidfd = None
        self.broken = False
        self.publication = None
        self.started_ns = None
        self.paths = []
        self.records = []
        self.finalized = False
        self.summary = None
        self.configured = None
        self.vm_names = None if vm_names is None else tuple(vm_names)

    def exchange(self, value):
        with self.lock:
            if self.broken:
                raise RuntimeError('recording: control channel failed')
            try:
                self.control.sendall(json.dumps(value).encode())
                reply = json.loads(self.control.recv(65536))
                spans = []
                while value['op'] == 'close' and reply.get('event') == 'vm-spans':
                    chunk = reply.get('items')
                    if not isinstance(chunk, list) or len(chunk) > 128 or len(spans) > 1000000:
                        raise RuntimeError('recording: invalid span stream')
                    spans.extend(chunk)
                    reply = json.loads(self.control.recv(65536))
                if spans:
                    reply['vm_spans'] = spans + reply.get('vm_spans', [])
                expected = {'close': 'closed', 'seal': 'sealed'}[value['op']]
                if reply.get('event') != expected or (value['op'] == 'seal' and (
                        reply.get('token') != value['token'] or
                        type(reply.get('sealed')) is not bool or
                        (value['sealed'] and reply.get('sealed') is not True))):
                    raise RuntimeError('recording: mismatched renderer acknowledgement')
                return reply
            except (OSError, ValueError, RuntimeError, KeyError, TypeError):
                self.broken = True
                raise

    def start(self):
        from test_storage import runtime_directory, scratch_directory, scratch_descriptors
        from watch_recording_worker import launch_command, process_identity
        from recording_storage import Store
        from recording_control import Publication
        try:
            from vm_selection import vm_config, execution_binding
            configured = vm_config.registry(self.root / 'config/test-vm.json')
            names = self.vm_names
            if names is None:
                binding = execution_binding()
                names = (binding['vms'] if isinstance(binding, dict) else
                         (binding,) if binding is not None else tuple(configured))
            if not names or len(set(names)) != len(names) or set(names) - configured.keys():
                raise ValueError('recording: invalid runner VM queue')
            self.configured = {name: configured[name] for name in names}
            self.store = Store(root=self.root)
            self.publication = Publication(self.root)
            self.stack.callback(self.publication.close)
            runtime = self.stack.enter_context(runtime_directory(prefix='onpc-record-control-'))
            scratch = Path(self.stack.enter_context(tempfile.TemporaryDirectory(
                prefix='onpc-watch-recording-', dir=scratch_directory())))
            self.master = scratch / 'watch.webm'
            self.log = self.stack.enter_context((scratch / 'worker.log').open('xb'))
            os.fchmod(self.log.fileno(), 0o600)
            self.control, remote = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            self.control.settimeout(30)
            try:
                self.process = subprocess.Popen(launch_command(self.root, remote.fileno(), self.master,
                    owner_fd=self.publication.descriptors()[0], vm_names=tuple(self.configured)),
                    stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT,
                    pass_fds=(remote.fileno(), *scratch_descriptors(),
                              *self.publication.descriptors()), start_new_session=True)
                self.pidfd = os.pidfd_open(self.process.pid)
                self.identity = process_identity(self.process)
            finally:
                remote.close()
            ready = json.loads(self.control.recv(8192))
            if ready.get('event') != 'ready':
                raise RuntimeError('recording: renderer not ready; check development prerequisites')
            self.started_ns = ready['started_ns']
            self.server = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            self.server.bind(str(runtime / 'control'))
            self.server.listen(8)
            self.server.settimeout(.2)
            self.endpoint = dict(socket=str(runtime / 'control'), nonce=secrets.token_hex(24))
            self.publication.publish(self.endpoint)
            self.thread = threading.Thread(target=self.serve, daemon=True, name='recording-controller')
            self.thread.start()
            os.environ[VARIABLE] = json.dumps(self.endpoint)
            print('VM recording: enabled (shared watch, 5 fps)', flush=True)
            return self
        except BaseException:
            self.diagnostics()
            self.close(publish=False)
            raise

    def diagnostics(self):
        if getattr(self, 'log', None) is None or self.log.closed:
            return
        self.log.flush()
        with open(self.log.name, 'rb') as stream:
            stream.seek(0, os.SEEK_END)
            stream.seek(max(0, stream.tell() - 8192))
            tail = stream.read().decode('utf-8', errors='replace')
        if tail:
            print('Recording renderer diagnostics:\n' + tail, file=sys.stderr, flush=True)

    def serve(self):
        configured = self.configured
        while not self.stop.is_set():
            try:
                peer, _ = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with peer:
                peer.settimeout(5)
                try:
                    uid = struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
                    if uid not in (0, os.getuid()):
                        raise ValueError('recording: caller')
                    value = json.loads(peer.recv(8192))
                    if value.pop('nonce', None) != self.endpoint['nonce']:
                        raise ValueError('recording: session')
                    operation = value.get('op')
                    if operation == 'seal':
                        self.exchange(value)
                    elif value.get('vm') not in configured:
                        raise ValueError('recording: VM')
                    elif operation == 'event':
                        self.timeline.event(value['vm'], value['category'], value['id'],
                            value['kind'], value['at_ns'], value.get('title', ''))
                    elif operation == 'finished':
                        self.timeline.finish_vm(value['vm'], value['at_ns'])
                    else:
                        raise ValueError('recording: operation')
                    peer.sendall(b'{"ok":true}')
                except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
                    self.errors.append(type(error).__name__)
                    try:
                        peer.sendall(b'{"ok":false}')
                    except OSError:
                        pass

    def publish(self, summary):
        from test_storage import scratch_descriptors
        configured = self.configured
        ordered = sorted(configured, key=lambda name: int(configured[name].id))
        self.timeline.close(time.monotonic_ns())
        total = len(self.timeline.windows)

        def progress(completed):
            line = f'Recording: {completed}/{total}'
            if hasattr(sys.stdout, 'controller'):
                sys.stdout.controller('recording', [line])
            else:
                print('\r' + line, end='\n' if completed == total else '', flush=True)

        progress(0)
        frames = keyframes(self.master)
        for key, window in sorted(self.timeline.windows.items()):
            requested_start = max(0., (window.start_ns - self.started_ns) / 1e9)
            # Stream-copy starts on a real keyframe. Include every VM visible
            # in that short prelude in the honest final filename as well.
            start = frames[max(0, bisect.bisect_right(frames, requested_start) - 1)]
            end = min(summary['duration_seconds'], max(start + .2,
                (window.end_ns - self.started_ns) / 1e9))
            clip_start_ns = self.started_ns + int(start * 1e9)
            clip_end_ns = self.started_ns + int(end * 1e9)
            names = {span['vm'] for span in summary['vm_spans']
                     if span['start_ns'] < clip_end_ns and span['end_ns'] > clip_start_ns}
            if not names:
                raise RuntimeError('recording: no VM display captured for ' + str(key))
            if names - configured.keys():
                raise RuntimeError('recording: VM registry changed during capture')
            with self.store.begin(window.category, window.identifier) as recording:
                subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                    '-ss', f'{start:.6f}', '-i', str(self.master), '-t', f'{end-start:.6f}',
                    '-map', '0:v:0', '-c', 'copy', '-avoid_negative_ts', 'make_zero',
                    str(recording.path)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=self.log, timeout=120, check=True,
                    pass_fds=(*recording.descriptors(), *scratch_descriptors()))
                path = recording.publish([name for name in ordered if name in names], validate=playable)
                self.paths.append(path)
                self.records.append(dict(category=window.category, id=window.identifier,
                    title=window.title, path=str(path), sha256=recording.state['current']['sha256'],
                    failed=window.failed, interrupted=window.interrupted,
                    start_seconds=start, end_seconds=end))
                progress(len(self.records))

    def close(self, *, publish=True):
        if self.previous is None:
            os.environ.pop(VARIABLE, None)
        else:
            os.environ[VARIABLE] = self.previous
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=35)
            if self.thread.is_alive():
                self.broken = True
        if self.server is not None:
            self.server.close()
        try:
            if self.process is not None:
                from watch_recording_worker import stop_owned
                summary = None
                try:
                    if not self.broken and self.started_ns is not None and self.process.poll() is None:
                        summary = self.exchange(dict(op='close'))
                        self.summary = summary
                        if self.process.wait(timeout=15):
                            raise RuntimeError('recording: renderer cleanup failed')
                    if publish:
                        if summary is None or summary.get('event') != 'closed' or self.errors:
                            raise RuntimeError('recording: incomplete capture; previous recordings preserved')
                        self.publish(summary)
                        self.finalized = True
                finally:
                    if self.identity is not None:
                        stop_owned(self.process, self.identity)
                    elif self.pidfd is not None and self.process.poll() is None:
                        import signal
                        signal.pidfd_send_signal(self.pidfd, signal.SIGTERM)
                        self.process.wait(timeout=5)
        except BaseException:
            self.diagnostics()
            raise
        finally:
            if self.control is not None:
                self.control.close()
            if self.pidfd is not None:
                os.close(self.pidfd)
            self.stack.close()

    def write_index(self, run, status):
        with (run / 'recordings.json').open('x', encoding='utf-8') as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(dict(run_id=run.name, complete=self.finalized, status=status,
                policy='Latest files can be superseded; compare SHA-256 with this run.',
                capture=self.summary, recordings=self.records), stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())

    def __enter__(self):
        return self.start()

    def __exit__(self, kind, value, traceback):
        self.close()


@contextmanager
def recording(root, *, enabled):
    if enabled and VARIABLE in os.environ:
        from recording_control import endpoint
        if endpoint(root) != json.loads(os.environ[VARIABLE]):
            raise ValueError('recording: inherited controller differs from live owner')
        yield None
    elif enabled:
        with Session(root) as session:
            yield session
    else:
        yield None
