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

PROBES = ('memory', 'cpu')
TOP_PROCESSES = 12

MEMORY_PROGRAM = '''import hashlib,json,pathlib,time
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

CPU_PROGRAM = '''import collections,hashlib,json,os,pathlib,re,time

def boot():
    return hashlib.sha256(pathlib.Path('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest()

def snapshot():
    cpu = tuple(map(int, pathlib.Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))
    pressure = pathlib.Path('/proc/pressure/cpu').read_text().splitlines()[0].split()
    vmstat = dict(line.split() for line in pathlib.Path('/proc/vmstat').read_text().splitlines())
    processes = {}
    with os.scandir('/proc') as entries:
        for entry in entries:
            if not entry.name.isdecimal():
                continue
            try:
                stat = pathlib.Path(entry.path, 'stat').read_text(errors='replace')
            except OSError:
                continue
            close = stat.rindex(')')
            name = re.sub('[^a-zA-Z0-9_.:-]', '_', stat[stat.index('(') + 1:close])[:15]
            fields = stat[close + 2:].split()
            processes[(entry.name, fields[19])] = (name or '_', int(fields[11]) + int(fields[12]))
    return time.monotonic_ns(), cpu, int(pressure[-1].split('=')[1]), vmstat, processes

identity = boot()
begin, cpu_before, pressure_before, vm_before, before = snapshot()
time.sleep(3)
end, cpu_after, pressure_after, vm_after, after = snapshot()
assert identity == boot()
by_name = collections.Counter()
for key in before.keys() & after.keys():
    name, ticks = after[key]
    delta = ticks - before[key][1]
    if delta > 0:
        by_name[name] += delta
cpu_delta = [current - previous for current, previous in zip(cpu_after, cpu_before)]
print(json.dumps(dict(boot_sha256=identity, sample_monotonic_ns=end, interval_ns=end-begin,
    ticks_per_second=os.sysconf('SC_CLK_TCK'), total_ticks=sum(cpu_delta),
    busy_ticks=sum(cpu_delta[:3] + cpu_delta[5:7]), pressure_some_us=pressure_after-pressure_before,
    swap_pages={k:int(vm_after[k])-int(vm_before[k]) for k in ('pswpin','pswpout')},
    matched_process_ticks=by_name.total(), processes=sorted(by_name.items(),
    key=lambda item: (-item[1], item[0]))[:''' + str(TOP_PROCESSES) + '''])))
'''


def address(vm):
    from vm_pool import identity
    return '\0onpc-vm-probe-' + identity(vm)


def peer_uid(peer):
    return struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]


def counter(value):
    return type(value) is int and 0 <= value < 2**63


def validate(sample, probe='memory'):
    memory_fields = {'meminfo_kib', 'vmstat', 'pressure_total_us'}
    cpu_counters = {'interval_ns', 'ticks_per_second', 'total_ticks', 'busy_ticks',
                    'pressure_some_us', 'matched_process_ticks'}
    fields = memory_fields if probe == 'memory' else cpu_counters | {'swap_pages', 'processes'}
    if (type(sample) is not dict or set(sample) != {
            'boot_sha256', 'sample_monotonic_ns', *fields}
            or not isinstance(sample['boot_sha256'], str)
            or re.fullmatch('[0-9a-f]{64}', sample['boot_sha256']) is None
            or not counter(sample['sample_monotonic_ns'])):
        raise ValueError('vm-probe:invalid-sample')
    if probe == 'cpu':
        processes = sample['processes']
        if (any(not counter(sample[key]) for key in cpu_counters)
                or not 0 < sample['interval_ns'] <= sample['sample_monotonic_ns']
                or not sample['ticks_per_second'] or not sample['total_ticks']
                or sample['busy_ticks'] > sample['total_ticks']
                or type(processes) is not list or len(processes) > TOP_PROCESSES
                or any(type(row) is not list or len(row) != 2 or type(row[0]) is not str
                       or re.fullmatch('[a-zA-Z0-9_.:-]{1,15}', row[0]) is None
                       or not counter(row[1]) or not row[1] for row in processes)
                or sum(row[1] for row in processes) > sample['matched_process_ticks']
                or len({row[0] for row in processes}) != len(processes)):
            raise ValueError('vm-probe:invalid-sample')
        groups = (('swap_pages', {'pswpin', 'pswpout'}),)
    else:
        groups = (
            ('meminfo_kib', {'MemTotal', 'MemAvailable', 'MemFree', 'Cached', 'Buffers',
                             'SReclaimable', 'Shmem', 'SwapTotal', 'SwapFree'}),
            ('vmstat', {'pswpin', 'pswpout', 'pgmajfault', 'oom_kill'}),
            ('pressure_total_us', {'some', 'full'}))
    for key, fields in groups:
        values = sample[key]
        if (type(values) is not dict or set(values) != fields
                or any(not counter(value) for value in values.values())):
            raise ValueError('vm-probe:invalid-sample')
    return sample


class Server:
    def __init__(self, lease, transport):
        from owned_commands import Commands
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
        from watch_activity import operation, current

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
                    probe = next((name for name in PROBES if raw == f'{name}:{self.uid}'.encode('ascii')), None)
                    if self.stop.is_set() or probe is None:
                        continue
                    with operation(f'Probing guest {probe} during the active run', priority=3):
                        try:
                            size = 0
                            def bound(data, stream):
                                nonlocal size
                                size += len(data)
                                if size > 4096:
                                    raise ValueError('vm-probe:oversized-sample')
                            program = MEMORY_PROGRAM if probe == 'memory' else CPU_PROGRAM
                            sample = validate(json.loads(self.transport.call(
                                ['/usr/bin/python3', '-I', '-c', program], timeout=10,
                                on_stream=bound)), probe)
                            self.transport.guard(self.config)
                            result = dict(probe=probe, domain_uuid=self.config['domain_uuid'],
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


def request(vm, uid, probe='memory'):
    if os.geteuid() != 0 or uid <= 0:
        raise ValueError('vm-probe:authenticated-helper-required')
    if probe not in PROBES:
        raise ValueError('vm-probe:unsupported-probe')
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as peer:
            peer.settimeout(70)
            peer.connect(address(vm))
            if peer_uid(peer) != 0:
                raise ValueError('vm-probe:untrusted-owner')
            peer.send(f'{probe}:{uid}'.encode('ascii'))
            raw = peer.recv(8193)
        if len(raw) > 8192:
            raise ValueError('vm-probe:oversized-reply')
        result = json.loads(raw)
        if type(result) is not dict or result.get('error'):
            raise ValueError('vm-probe:sample-unavailable')
        if (set(result) != {'probe', 'domain_uuid', 'run', 'domain_id', 'sample'}
                or result['probe'] != probe or result['domain_uuid'] != vm
                or not isinstance(result['run'], str)
                or re.fullmatch('[0-9a-f]{32}', result['run']) is None
                or type(result['domain_id']) is not int or result['domain_id'] < 0):
            raise ValueError('vm-probe:invalid-owner-reply')
        validate(result['sample'], probe)
        return result
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError('vm-probe:no-active-owner-or-probe-unavailable') from error
