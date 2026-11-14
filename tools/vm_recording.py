"""One runner-owned recording of the shared watch, with latest case clips.

VM workers report trusted case boundaries, never start their own encoders.
The user-owned endpoint accepts metadata only and has no VM input capability.
"""

from contextlib import ExitStack, contextmanager
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
from pathlib import Path
import secrets
import shutil
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
_phase_nodes = {}
_phase_attempts = {}


@lru_cache(maxsize=8)
def e2e_identities(root):
    document = json.loads((root / 'tests/e2e/scenarios.json').read_text())
    return {scenario['id'] + '/' + variant['id']:
            (variant['coverage_id'], scenario['title'])
            for scenario in document['scenarios'] for variant in scenario['variants']}


E2E_QUALIFICATIONS = {
    '--qualify-lunar-tray': ('check_e2e_lunar_tray',
        'Observe Lunar running for the child',
        'tests/integration/lunar_profile_qualification.py'),
    '--qualify-lunar-launch-quit': ('check_e2e_lunar_launch_quit',
        'Launch Lunar and Quit through its normal controls',
        'tests/integration/lunar_profile_qualification.py'),
    '--qualify-lunar-profile': ('check_e2e_lunar_profile',
        "Check that the child's game launchers are ready",
        'tests/integration/lunar_profile_qualification.py'),
}


def case_identity(root, category, event):
    """Resolve public IDs without changing existing pytest/checkpoint nodeids."""
    nodeid = event.get('nodeid')
    if not isinstance(nodeid, str):
        return None
    if category == 'system':
        if re.fullmatch(r'check_[a-z][a-z0-9_]*', nodeid):
            return nodeid, nodeid.removeprefix('check_').replace('_', ' ').capitalize()
        sys.path.insert(0, str(root / 'tests/integration'))
        try:
            from system_case_ids import identity_for_event
            identity = identity_for_event(nodeid)
        finally:
            sys.path.pop(0)
        return (identity.numeric_id, identity.title) if identity else None
    if category == 'e2e':
        if nodeid in E2E_QUALIFICATIONS:
            return E2E_QUALIFICATIONS[nodeid][:2]
        return e2e_identities(root).get(nodeid)
    return None


def request(endpoint, value, *, timeout=180):
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
    from test_commands import CATEGORIES
    if not endpoint or category not in CATEGORIES or CATEGORIES[category].scope != 'vm':
        return
    from vm_selection import selected
    vm = selected()
    phase_key = endpoint, vm.name, category
    if event.get('kind') == 'collection':
        if not event.get('nodeids'):
            return
        pending = defaultdict(set)
        for nodeid in event['nodeids']:
            identity = case_identity(root, category, dict(nodeid=nodeid))
            if identity is not None:
                pending[identity[0]].add(nodeid)
        _phase_nodes[phase_key] = pending
        _phase_attempts[phase_key] = secrets.token_hex(16)
        event = dict(kind='prepared', nodeid=event['nodeids'][0])
    if event.get('kind') not in ('prepared', 'started', 'finished', 'failure'):
        return
    identity = case_identity(root, category, event)
    if identity is None:
        raise ValueError('recording: unregistered VM case')
    pending = _phase_nodes.get(phase_key, {}).get(identity[0], set())
    attempt = _phase_attempts.get(phase_key)
    if event['kind'] == 'finished':
        pending.discard(event['nodeid'])
        if not any(_phase_nodes.get(phase_key, {}).values()):
            _phase_nodes.pop(phase_key, None)
            _phase_attempts.pop(phase_key, None)
        if event.get('envelope_pending') is True:
            return None
    reply = request(json.loads(endpoint), dict(op='event', vm=vm.name, category=category,
        id=identity[0], title=identity[1], kind=event['kind'], at_ns=time.monotonic_ns(),
        more_phases=bool(pending) if event['kind'] == 'finished' else False,
        attempt=attempt))
    record = reply.get('recording')
    if record:
        print(describe(record), flush=True)
    return record


def describe(record):
    uri = Path(record['path']).as_uri()
    from vm_selection import vm_config
    origin = vm_config.remote_origin()
    if origin is not None:
        uri = 'onpc-recording://' + origin['host'] + uri.removeprefix('file://')
    text = 'Recording: [Open recording](<' + uri + '>)'
    for error in record.get('errors', [])[:4]:
        seconds = int(error['seconds'] + .5)
        hours, rest = divmod(seconds, 3600)
        minutes, rest = divmod(rest, 60)
        text += (f'\nRecording error: {hours:02}:{minutes:02}:{rest:02} '
                 f"({seconds}s, frame {error['frame']}, "
                 f"{error['vm']}; {error['kind']})")
    return text


def intervention_recording(root, category, nodeid):
    from test_commands import CATEGORIES
    if not nodeid or category not in CATEGORIES or CATEGORIES[category].scope != 'vm':
        return ''
    try:
        record = latest(root, category, nodeid)
        return '\n\n' + describe(record) if record else ''
    except (OSError, ValueError) as error:
        return f'\n\nRecording unavailable: {type(error).__name__}; inspect runner diagnostics.'


def latest(root, category, nodeid):
    """Read a verified latest receipt for an intervention, without creating media."""
    from recording_storage import Store
    from vm_selection import selected, vm_config
    identity = case_identity(root, category, dict(nodeid=nodeid))
    if identity is None:
        return None
    vm = selected(required=False)
    names = [vm.name] if vm is not None else vm_config.registry(root / 'config/environment.json')
    records = []
    for name in names:
        try:
            with Store(root=root, create=False).vm_owner(category, identity[0], name) as owner:
                current = owner.state['current']
                owner._verify(current)
                records.append(dict(owner.state['provenance'], vm=name,
                    path=str(owner.store.path / current['name']), sha256=current['sha256']))
        except FileNotFoundError:
            continue
    return max(records, key=lambda record: record['published_at'], default=None)


def workflow_records(root, run, previous=()):
    """Keep finite latest receipts across agent sessions without retaining media."""
    from detached_launcher import nested_runs
    from recording_storage import Store
    from vm_selection import vm_config
    candidates = list(previous)
    records = {}
    try:
        children = list(nested_runs(root, run)) if (run / 'nested.json').exists() else []
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'Recording links unavailable: {type(error).__name__}; retained task state unchanged.',
              file=sys.stderr, flush=True)
        children = []
    for child in children:
        try:
            # Index metadata is optional and bounded; media ownership remains
            # with Store. Never offer a superseded clip's old error offsets.
            fd = os.open(child / 'recordings.json', os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd) as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_size > 8 * 1024 * 1024:
                    raise ValueError('recording: unsafe index')
                index = json.load(stream)
            candidates.extend(index['recordings'])
        except FileNotFoundError:
            continue
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f'Recording links unavailable: {type(error).__name__}; retained task state unchanged.',
                  file=sys.stderr, flush=True)
    for record in candidates:
        try:
            names = [record['vm']] if record.get('vm') else vm_config.registry(root / 'config/environment.json')
            for vm in names:
                key = record['category'], record['id'], vm
                try:
                    with Store(root=root, create=False).vm_owner(*key) as owner:
                        current = owner.state['current']
                        owner._verify(current)
                        records[key] = dict(owner.state['provenance'], category=key[0], id=key[1], vm=vm,
                            path=str(owner.store.path / current['name']), sha256=current['sha256'])
                except FileNotFoundError:
                    continue
        except FileNotFoundError:
            continue
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f'Recording links unavailable: {type(error).__name__}; retained task state unchanged.',
                  file=sys.stderr, flush=True)
    return sorted(records.values(), key=lambda record: record['published_at'])[-4:]


def workflow_recordings(root, run, *, limit=1400, previous=()):
    """Latest review links from this workflow's registered, identity-bound tests."""
    return recording_links(workflow_records(root, run, previous), limit=limit)


def recording_links(records, *, limit=1400):
    """Fit whole recording receipts, never cut a clickable path in half."""
    descriptions = []
    for record in reversed(records):
        text = describe(record)
        if len('\n\n'.join([*descriptions, text])) <= limit:
            descriptions.append(text)
    return '\n\n'.join(descriptions)


def report_finished():
    endpoint = os.environ.get(VARIABLE)
    if endpoint:
        from vm_selection import selected
        vm = selected(required=False)
        if vm is not None:
            request(json.loads(endpoint), dict(op='finished', vm=vm.name, at_ns=time.monotonic_ns()))


def report_failure(root=ROOT):
    """Timestamp a host controller's failure before it starts owned cleanup."""
    at_ns = time.monotonic_ns()
    if VARIABLE not in os.environ and os.geteuid() != 0:
        return
    from vm_selection import selected
    vm = selected(required=False)
    if vm is None:
        return
    endpoint = protected_endpoint(root)
    if endpoint is not None:
        request(endpoint, dict(op='failure', vm=vm.name, at_ns=at_ns))


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


class Session:
    """One shared renderer; bounded encoders publish at each case boundary."""

    def __init__(self, root=ROOT, *, vm_names=None, run=None):
        self.root = Path(root)
        self.run = run
        self.stack = ExitStack()
        self.cases = {}
        self.suspended = {}
        self.active = {}
        self.case_lock = threading.Lock()
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
                while value['op'] in ('close', 'end') and reply.get('event') == 'vm-spans':
                    chunk = reply.get('items')
                    if not isinstance(chunk, list) or len(chunk) > 128 or len(spans) > 1000000:
                        raise RuntimeError('recording: invalid span stream')
                    spans.extend(chunk)
                    reply = json.loads(self.control.recv(65536))
                if spans:
                    reply['vm_spans'] = spans + reply.get('vm_spans', [])
                expected = {'close': 'closed', 'seal': 'sealed', 'begin': 'begun', 'end': 'ended'}[value['op']]
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
        from test_storage import runtime_directory, scratch_directory
        from watch_recording_worker import (launch_command, launch_environment, process_identity,
                                            shared_owner_descriptors)
        from recording_storage import Store
        from recording_control import Publication
        try:
            from vm_selection import vm_config, execution_binding
            configured = vm_config.registry(self.root / 'config/environment.json')
            names = self.vm_names
            if names is None:
                binding = execution_binding()
                names = (binding['vms'] if isinstance(binding, dict) else
                         (binding,) if binding is not None else tuple(configured))
            if not names or len(set(names)) != len(names) or set(names) - configured.keys():
                raise ValueError('recording: invalid runner VM queue')
            self.configured = {name: configured[name] for name in names}
            if self.run is not None:
                from watch_output import read_json
                try:
                    previous = read_json(self.run / 'recordings.json', limit=8 * 1024 * 1024)
                    records = previous['recordings']
                    if (previous.get('run_id') != self.run.name or not isinstance(records, list)
                            or any(not isinstance(record, dict)
                                or not {'category', 'id', 'vm'} <= record.keys() for record in records)):
                        raise ValueError('recording: invalid previous group index')
                    self.records = list(records)
                except FileNotFoundError:
                    pass
                except (OSError, ValueError, KeyError, TypeError) as error:
                    print(f'Recording index unavailable: {type(error).__name__}; '
                          'earlier media remains in its publication store.', file=sys.stderr, flush=True)
            self.store = Store(root=self.root)
            self.publication = Publication(self.root)
            self.stack.callback(self.publication.close)
            runtime = self.stack.enter_context(runtime_directory(prefix='onpc-record-control-'))
            scratch = self.scratch = Path(self.stack.enter_context(tempfile.TemporaryDirectory(
                prefix='onpc-watch-recording-', dir=scratch_directory())))
            self.log = self.stack.enter_context((scratch / 'worker.log').open('xb'))
            os.fchmod(self.log.fileno(), 0o600)
            self.control, remote = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            self.control.settimeout(30)
            try:
                self.process = subprocess.Popen(launch_command(self.root, remote.fileno(),
                    owner_fd=self.publication.descriptors()[0], vm_names=tuple(self.configured)),
                    env=launch_environment(),
                    stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT,
                    pass_fds=(remote.fileno(), *shared_owner_descriptors(),
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
            self.handlers = ThreadPoolExecutor(max_workers=len(self.configured) + 2,
                                              thread_name_prefix='recording-peer')
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
        while not self.stop.is_set():
            try:
                peer, _ = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self.handlers.submit(self.handle, peer)

    def handle(self, peer):
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
                record = None
                if operation == 'seal':
                    # Validation/publication never holds this control lock.
                    self.exchange(value)
                elif value.get('vm') not in self.configured:
                    raise ValueError('recording: VM')
                else:
                    with self.case_lock:
                        if operation == 'event':
                            record = self.event(value)
                        elif operation == 'failure':
                            key = self.active.get(value['vm'])
                            if key is not None:
                                self.event(dict(value, category=key[0], id=key[1], kind='failure'))
                        elif operation == 'finished':
                            record = self.finish_attempt(value['vm'])
                        else:
                            raise ValueError('recording: operation')
                peer.sendall(json.dumps(dict(ok=True, recording=record)).encode())
            except Exception as error:
                self.errors.append(type(error).__name__)
                try:
                    peer.sendall(b'{"ok":false}')
                except OSError:
                    pass

    def event(self, value):
        from recording_storage import case_identity as valid_identity, _token
        category, identifier, vm = value['category'], value['id'], value['vm']
        kind, at_ns = value['kind'], value['at_ns']
        if (not _token(category) or not valid_identity(identifier)
                or kind not in ('prepared', 'started', 'failure', 'finished')
                or type(at_ns) is not int or not 0 <= at_ns <= time.monotonic_ns()):
            raise ValueError('recording: invalid case event')
        key = category, identifier
        if kind == 'finished' and self.active.get(vm) != key:
            return None
        if vm in self.active and self.active[vm] != key:
            self.finish_vm(vm, interrupted=True)
        if vm not in self.cases:
            if kind == 'finished':
                return None
            # Encoder scratch is owned by the inherited scratch/controller
            # leases. The final per-case lease is held only during publication,
            # so simultaneous VMs can finish the same case independently.
            path = self.scratch / (secrets.token_hex(16) + '.webm')
            case = self.suspended.pop((vm, *key), None)
            if case is not None and case['attempt'] != value.get('attempt'):
                for part in case['parts']:
                    part.unlink(missing_ok=True)
                case = None
            if case is None:
                case = dict(errors=[], title=value.get('title', ''),
                    interrupted=False, parts=[], duration_seconds=0., vm_names=set())
            case.update(attempt=value.get('attempt'), path=path)
            self.cases[vm] = case
            self.active[vm] = key
            ready = self.exchange(dict(op='begin', category=category, id=identifier, vm=vm, path=str(path)))
            self.cases[vm]['started_ns'] = ready['started_ns']
        case = self.cases[vm]
        self.active[vm] = key
        if kind == 'failure' and not case['errors']:
            elapsed_ns = max(0, at_ns - case['started_ns'])
            seconds = case['duration_seconds'] + elapsed_ns / 1_000_000_000
            milliseconds = int(seconds * 1000)
            hours, rest = divmod(milliseconds, 3600000)
            minutes, rest = divmod(rest, 60000)
            case['errors'].append(dict(seconds=seconds, frame=int(seconds * 5), vm=vm,
                timestamp=f'{hours:02}:{minutes:02}:{rest / 1000:06.3f}', kind='failure observed'))
        if kind == 'finished':
            return self.finish_vm(vm, more_phases=value.get('more_phases') is True)

    def finish_vm(self, vm, *, interrupted=False, more_phases=False):
        key = self.active.get(vm)
        if key is None:
            return None
        case = self.cases[vm]
        case['interrupted'] |= interrupted
        category, identifier = key
        summary = self.exchange(dict(op='end', category=category, id=identifier, vm=vm))
        self.active.pop(vm)
        names = {span['vm'] for span in summary['vm_spans']}
        # Initial VM startup may precede the first available display texture;
        # the case's configured panel still identifies that recorded attempt.
        if not names:
            names = {vm}
        if names - self.configured.keys():
            raise ValueError('recording: unknown captured VM')
        case['parts'].append(case['path'])
        case['duration_seconds'] += summary['duration_seconds']
        case['vm_names'].update(names)
        case['fps'] = summary['fps']
        del self.cases[vm]
        if more_phases and not interrupted and not case['errors']:
            self.suspended[vm, *key] = case
            return None
        return self.publish_case(vm, key, case, more_phases=more_phases and not interrupted)

    def finish_attempt(self, vm):
        """Preserve review clips when an attempt stops between lifecycle phases."""
        record = self.finish_vm(vm, interrupted=True)
        for key in tuple(self.suspended):
            if key[0] == vm:
                case = self.suspended.pop(key)
                case['interrupted'] = True
                record = self.publish_case(vm, key[1:], case)
        return record

    def publish_case(self, vm, key, case, *, more_phases=False):
        from recording_storage import vm_case_id
        category, identifier = key
        ordered = sorted(case['vm_names'], key=lambda name: int(self.configured[name].id))
        metadata = dict(title=case['title'], vm=vm, errors=case['errors'],
                        failed=bool(case['errors']), interrupted=case['interrupted'],
                        duration_seconds=case['duration_seconds'], fps=case['fps'])
        try:
            with self.store.begin(category, vm_case_id(identifier, vm)) as owner:
                if len(case['parts']) == 1:
                    shutil.copyfile(case['path'], owner.path)
                else:
                    from test_storage import scratch_descriptors
                    # All segments have identical encoder settings and private,
                    # generated basenames. Join only this attempt's phases.
                    listing = case['path'].with_suffix('.ffconcat')
                    try:
                        listing.write_text('ffconcat version 1.0\n' + ''.join(
                            f"file '{part.name}'\n" for part in case['parts']))
                        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat',
                            '-safe', '1', '-i', str(listing), '-c', 'copy', str(owner.path)],
                            stdin=subprocess.DEVNULL, check=True, timeout=120,
                            pass_fds=(*scratch_descriptors(), *owner.descriptors()))
                    finally:
                        listing.unlink(missing_ok=True)
                path = owner.publish(ordered, validate=playable, metadata=metadata)
                record = dict(metadata, category=category, id=identifier, path=str(path),
                              sha256=owner.state['current']['sha256'])
            # An index contains only the current recording for each identity.
            self.records[:] = [old for old in self.records
                               if (old['category'], old['id'], old.get('vm')) != (*key, vm)]
            self.records.append(record)
            if self.run is not None:
                self.write_index(self.run, None)
            return record
        finally:
            if more_phases:
                # Keep a failing phase reviewable even if later phases cannot
                # run, while retaining its segments if execution continues.
                self.suspended[vm, *key] = case
            else:
                for part in case['parts']:
                    part.unlink(missing_ok=True)

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
        if hasattr(self, 'handlers'):
            self.handlers.shutdown(wait=True)
        try:
            if self.process is not None:
                from watch_recording_worker import stop_owned
                summary = None
                try:
                    if not self.broken and self.started_ns is not None and self.process.poll() is None:
                        for vm in set(self.active) | {key[0] for key in self.suspended}:
                            self.finish_attempt(vm)
                        summary = self.exchange(dict(op='close'))
                        self.summary = summary
                        if self.process.wait(timeout=15):
                            raise RuntimeError('recording: renderer cleanup failed')
                    if publish:
                        if summary is None or summary.get('event') != 'closed' or self.errors:
                            raise RuntimeError('recording: incomplete capture; previous recordings preserved')
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
            self.cases.clear()
            self.suspended.clear()
            if self.control is not None:
                self.control.close()
            if self.pidfd is not None:
                os.close(self.pidfd)
            self.stack.close()

    def write_index(self, run, status):
        # Reload/resume keeps the run directory but creates a new capture.
        # Publish its complete snapshot without truncating the previous index
        # or letting optional review metadata mask a result/reload exception.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                    prefix='.recordings-', suffix='.tmp', dir=run, delete=False) as stream:
                temporary = Path(stream.name)
                os.fchmod(stream.fileno(), 0o600)
                json.dump(dict(run_id=run.name, complete=self.finalized, status=status,
                    policy='Latest files can be superseded; compare SHA-256 with this run.',
                    capture=self.summary, recordings=self.records), stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(run / 'recordings.json')
        except OSError as error:
            print(f'Recording index could not be saved: {error}; '
                  'test result and continuation retained.', file=sys.stderr, flush=True)
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError as error:
                    print(f'Recording index temporary file could not be removed: {error}',
                          file=sys.stderr, flush=True)

    def __enter__(self):
        return self.start()

    def __exit__(self, kind, value, traceback):
        self.close()


@contextmanager
def recording(root, *, enabled, run=None):
    if enabled and VARIABLE in os.environ:
        from recording_control import endpoint
        if endpoint(root) != json.loads(os.environ[VARIABLE]):
            raise ValueError('recording: inherited controller differs from live owner')
        yield None
    elif enabled:
        with Session(root, run=run) as session:
            yield session
    else:
        yield None
