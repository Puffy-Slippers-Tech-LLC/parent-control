"""Fixed read-only probes serviced by the current exclusive VM owner.

The root helper is the only client. Neither credentials nor checkout receipts
cross this endpoint. Abstract sockets disappear with their owner on a crash.
"""
import json
import os
from pathlib import Path
import re
import socket
import struct
import tempfile
import threading

from owned_commands import Commands
from watch_activity import operation, current


PROGRAM = '''import hashlib,json,pathlib,time
p=pathlib.Path
boot=hashlib.sha256(p('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest()
m={s[0].rstrip(':'):int(s[1]) for line in p('/proc/meminfo').read_text().splitlines()
   if len(s:=line.split())>1 and s[1].isdigit()}
v=dict(line.split() for line in p('/proc/vmstat').read_text().splitlines())
keys=('MemTotal','MemAvailable','MemFree','Cached','Buffers','SReclaimable','Shmem','SwapTotal','SwapFree')
pressure={}
for line in p('/proc/pressure/memory').read_text().splitlines():
    parts=line.split()
    pressure[parts[0]]=dict(item.split('=') for item in parts[1:])
assert boot==hashlib.sha256(p('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest()
print(json.dumps({'boot_sha256':boot,'sample_monotonic_ns':time.monotonic_ns(),
 'meminfo_kib':{k:m[k] for k in keys},
 'vmstat':{k:int(v[k]) for k in ('pswpin','pswpout','pgmajfault','oom_kill')},
 'pressure_total_us':{k:int(pressure[k]['total']) for k in ('some','full')}}))
'''


def address(vm):
    from vm_pool import identity
    return '\0onpc-vm-probe-' + identity(vm)


def peer_uid(peer):
    return struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]


def validate(sample):
    if (type(sample) is not dict or set(sample) != {
            'boot_sha256', 'sample_monotonic_ns', 'meminfo_kib', 'vmstat', 'pressure_total_us'}
            or not isinstance(sample['boot_sha256'], str)
            or re.fullmatch('[0-9a-f]{64}', sample['boot_sha256']) is None
            or type(sample['sample_monotonic_ns']) is not int or sample['sample_monotonic_ns'] < 0):
        raise ValueError('vm-probe:invalid-sample')
    for key, fields in (
            ('meminfo_kib', {'MemTotal', 'MemAvailable', 'MemFree', 'Cached', 'Buffers',
                             'SReclaimable', 'Shmem', 'SwapTotal', 'SwapFree'}),
            ('vmstat', {'pswpin', 'pswpout', 'pgmajfault', 'oom_kill'}),
            ('pressure_total_us', {'some', 'full'})):
        values = sample[key]
        if (type(values) is not dict or set(values) != fields
                or any(type(v) is not int or not 0 <= v < 2**63 for v in values.values())):
            raise ValueError('vm-probe:invalid-sample')
    return sample


class Server:
    def __init__(self, lease, transport):
        from vm_transport import Transport, guard_host
        self.uid = int(os.environ['PKEXEC_UID'])
        if os.geteuid() != 0 or self.uid <= 0 or lease.fd is None:
            raise ValueError('vm-probe:owner-required')
        config = dict(transport.config)
        if (lease.state['phase'] != 'running' or config['run'] != lease.state['run']
                or config['domain_uuid'] != lease.source.uuid
                or config['domain_id'] != lease.state['domain_id']):
            raise ValueError('vm-probe:running-transport-required')
        self.config = config
        commands = Commands()
        if transport.commands.directory is None:
            raise ValueError('vm-probe:command-storage-required')
        commands.directory = Path(tempfile.mkdtemp(prefix='live-probe-', dir=transport.commands.directory))
        commands.lock_fd = transport.commands.lock_fd
        commands.controller_fds = transport.commands.controller_fds
        # Do not share Commands or call lease.guard() from the probe thread:
        # the main owner uses mutable command status and baseline state.
        self.transport = Transport(config, commands, guard=guard_host)
        self.stop = threading.Event()
        self.finished = threading.Event()
        self.finished.set()  # No worker owns guest work until serve() begins.
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        try:
            self.socket.bind(address(config['domain_uuid']))
            self.socket.listen(1)
            self.socket.settimeout(.2)
            self.thread = threading.Thread(target=self.serve, name='live-vm-probe', daemon=True)
        except BaseException:
            self.socket.close()
            raise

    def serve(self):
        self.finished.clear()
        try:
            self._serve()
        finally:
            self.finished.set()

    def _serve(self):
        while not self.stop.is_set():
            try:
                peer, _ = self.socket.accept()
            except TimeoutError:
                continue
            with peer:
                try:
                    peer.settimeout(2)
                    if peer_uid(peer) != 0:
                        continue
                    raw = peer.recv(256)
                    if (self.stop.is_set() or raw != f'memory:{self.uid}'.encode('ascii')):
                        continue
                    with operation('Probing guest memory during the active run', priority=3):
                        try:
                            size = 0
                            def bound(data, stream):
                                nonlocal size
                                size += len(data)
                                if size > 4096:
                                    raise ValueError('vm-probe:oversized-sample')
                            sample = validate(json.loads(self.transport.call(
                                ['/usr/bin/python3', '-I', '-c', PROGRAM], timeout=10,
                                on_stream=bound)))
                            self.transport.guard(self.config)
                            result = dict(probe='memory', domain_uuid=self.config['domain_uuid'],
                                          run=self.config['run'], domain_id=self.config['domain_id'],
                                          sample=sample)
                            transcript = current()
                            if transcript is not None:
                                transcript.append('\n[VM probe] ' + json.dumps(result) + '\n')
                        except Exception:
                            result = {'error': 'vm-probe:sample-unavailable'}
                        peer.send(json.dumps(result).encode('ascii'))
                except OSError:
                    pass  # A disconnected diagnostic client never fails the test.

    def close(self):
        self.stop.set()
        # Drain the finite owned SSH command before its controller releases
        # ownership or changes the VM lifecycle. Never signal a foreign process.
        # A separate completion event remains authoritative even if an earlier
        # interrupted Thread.join() changed Python's thread bookkeeping.
        self.finished.wait()
        if self.thread.ident is not None:
            self.thread.join()
        self.socket.close()


def request(vm, uid):
    if os.geteuid() != 0 or uid <= 0:
        raise ValueError('vm-probe:authenticated-helper-required')
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as peer:
            peer.settimeout(70)
            peer.connect(address(vm))
            if peer_uid(peer) != 0:
                raise ValueError('vm-probe:untrusted-owner')
            peer.send(f'memory:{uid}'.encode('ascii'))
            raw = peer.recv(8193)
        if len(raw) > 8192:
            raise ValueError('vm-probe:oversized-reply')
        result = json.loads(raw)
        if result.get('error'):
            raise ValueError('vm-probe:sample-unavailable')
        if (set(result) != {'probe', 'domain_uuid', 'run', 'domain_id', 'sample'}
                or result['probe'] != 'memory' or result['domain_uuid'] != vm
                or not isinstance(result['run'], str)
                or re.fullmatch('[0-9a-f]{32}', result['run']) is None
                or type(result['domain_id']) is not int or result['domain_id'] < 0):
            raise ValueError('vm-probe:invalid-owner-reply')
        validate(result['sample'])
        return result
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError('vm-probe:no-active-owner-or-probe-unavailable') from error
