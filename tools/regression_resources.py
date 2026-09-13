"""Conservative read-only admission for two host test categories.

CPU and memory reservations intentionally count active jobs' full budgets again
on top of observed host use. That pessimism protects against their future peaks
without attributing host processes or assuming instantaneous usage is a ceiling.
"""

from dataclasses import asdict, dataclass
import math
import os
from pathlib import Path
import subprocess
import time
from xml.etree import ElementTree

GIB = 1024 ** 3
SWAP_IN_LIMIT = 1024 ** 2  # Bytes/second; cold page reads below this are tolerated.


@dataclass(frozen=True)
class Demand:
    cpu: float
    memory: int


# Includes launcher safety processes. Heavy or unknown categories stay serial.
DEMANDS = {
    'ui': Demand(4, 4 * GIB),
    'unit': Demand(2, 2 * GIB),
    'component': Demand(2, GIB),
    'fixture-runtime': Demand(2, GIB),
    'source': Demand(2, GIB),
    'static': Demand(1, GIB),
    'child-node': Demand(2, GIB),
    'child-gjs': Demand(1, GIB),
    'backend': Demand(1, GIB),
}
PARALLEL = frozenset(DEMANDS)
DEMANDS.update(publish=Demand(2, 6 * GIB), artifacts=Demand(2, 4 * GIB),
               system=Demand(0, 0), e2e=Demand(0, 0))


def vm_demand(root):
    """Read only the pinned VM through the validated, already-installed helper."""
    result = subprocess.run([str(root / 'tools/test-vm'), 'xml'], check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            timeout=15, env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin'})
    tree = ElementTree.fromstring(result.stdout)
    cpus = int(tree.findtext('vcpu'))
    memory = tree.find('maxMemory')
    if memory is None:
        memory = tree.find('memory')
    units = {'KiB': 1024, 'MiB': 1024 ** 2, 'GiB': GIB, 'bytes': 1}
    amount = int(memory.text) * units[memory.get('unit', 'KiB')]
    if cpus <= 0 or amount <= 0:
        raise ValueError('invalid pinned VM resource declaration')
    # Reserve configured RAM, not only the guest's current resident pages,
    # plus QEMU/controller overhead. No VM settings are changed.
    return Demand(cpus + 1, amount + max(GIB, amount // 10))


@dataclass(frozen=True)
class Sample:
    capacity: float
    busy: float
    total_memory: int
    available_memory: int
    cpu_pressure: float
    memory_pressure: float
    io_pressure: float
    swapping: bool
    swap_in_bytes_per_second: float = 0
    swap_out_bytes_per_second: float = 0


class Monitor:
    def __init__(self, proc=Path('/proc'), cgroups=Path('/sys/fs/cgroup'), monotonic=time.monotonic):
        self.proc, self.cgroups = proc, cgroups
        self.previous = None
        self.clock = monotonic

    def sample(self):
        def pressure(name, line):
            rows = dict(row.split(' ', 1) for row in
                        (self.proc / 'pressure' / name).read_text().splitlines())
            return float(dict(field.split('=') for field in rows[line].split())['avg10'])

        ticks = list(map(int, (self.proc / 'stat').read_text().splitlines()[0].split()[1:9]))
        total, idle = sum(ticks), ticks[3] + ticks[4]
        vm = dict(row.split() for row in (self.proc / 'vmstat').read_text().splitlines())
        swap = (int(vm['pswpin']), int(vm['pswpout']))
        memory = {key: int(value.split()[0]) * 1024 for key, value in
                  (row.split(':', 1) for row in (self.proc / 'meminfo').read_text().splitlines())}
        capacity = float(len(os.sched_getaffinity(0)))
        total_memory, available = memory['MemTotal'], memory['MemAvailable']
        # Respect unified hierarchy limits, including ancestor quotas. Unknown
        # layouts cause serial fallback instead of guessing available capacity.
        membership = (self.proc / 'self/cgroup').read_text().strip()
        if not membership.startswith('0::/') or '\n' in membership:
            raise ValueError('unavailable unified resource limits')
        relative = Path(membership[4:])
        if '..' in relative.parts:
            raise ValueError('invalid cgroup membership')
        current = self.cgroups / relative
        while True:
            quota, period = (current / 'cpu.max').read_text().split() if current != self.cgroups else ('max', '100000')
            if quota != 'max':
                capacity = min(capacity, int(quota) / int(period))
            if current != self.cgroups:
                limit = (current / 'memory.max').read_text().strip()
                if limit != 'max':
                    limit = int(limit)
                    total_memory = min(total_memory, limit)
                    available = min(available, max(0, limit - int((current / 'memory.current').read_text())))
            if current == self.cgroups:
                break
            current = current.parent
        now = self.clock()
        previous, self.previous = self.previous, (total, idle, swap, now)
        if previous is None or total <= previous[0] or now <= previous[3]:
            raise ValueError('resource monitor warming up')
        interval = now - previous[3]
        page_size = os.sysconf('SC_PAGE_SIZE')
        swap_in, swap_out = ((current - before) * page_size / interval
                            for current, before in zip(swap, previous[2]))
        # Reading a few pages evicted earlier does not imply current reclaim.
        # Any new swap write still closes admission, as does >= 1 MiB/s of
        # swap reads. Memory reserves and PSI remain independent mandatory gates.
        swapping = swap_out > 0 or swap_in >= SWAP_IN_LIMIT
        # Aggregate /proc/stat spans all host CPUs, not only our affinity set.
        busy = (1 - (idle - previous[1]) / (total - previous[0])) * (os.cpu_count() or 1)
        result = Sample(capacity, max(0, busy), total_memory, available,
                        pressure('cpu', 'some'), pressure('memory', 'some'),
                        pressure('io', 'full'), swapping, swap_in, swap_out)
        if not all(math.isfinite(value) and value >= 0 for value in (
                result.capacity, result.busy, result.cpu_pressure,
                result.memory_pressure, result.io_pressure, swap_in, swap_out)):
            raise ValueError('invalid resource sample')
        return result


class Admission:
    def __init__(self, monitor=None, monotonic=time.monotonic, observe=lambda _: None):
        self.monitor = monitor or Monitor()
        self.clock = monotonic
        self.last = -math.inf
        self.healthy_since = None
        self.open = False
        self.sample = None
        self.reason = 'resource monitor warming up'
        self.demands = dict(DEMANDS)
        self.observe = observe

    def update(self):
        now = self.clock()
        if now - self.last < 2:
            return
        self.last = now
        try:
            self.sample = self.monitor.sample()
        except (OSError, ValueError, KeyError, IndexError, ZeroDivisionError):
            self.sample = None
            self.open = False
            self.healthy_since = None
            self.reason = 'resource measurements unavailable; serial execution'
            self.observe({'monotonic': now, 'available': False})
            return
        sample = self.sample
        high = (sample.cpu_pressure >= 10 or sample.memory_pressure >= 1
                or sample.io_pressure >= 2 or sample.swapping)
        low = (sample.cpu_pressure < 5 and sample.memory_pressure < .5
               and sample.io_pressure < 1 and not sample.swapping)
        if high:
            self.open = False
            self.healthy_since = None
        elif low:
            if self.healthy_since is None:
                self.healthy_since = now
            if now - self.healthy_since >= 20:
                self.open = True
        else:
            self.healthy_since = None
        self.reason = 'waiting for sustained resource headroom' if not self.open else 'resource headroom available'
        self.observe({'monotonic': now, 'available': True, 'overlap_gate': self.open,
                      **asdict(sample)})

    def allows(self, candidate, active):
        self.update()
        if len(active) >= 2:
            self.reason = 'two host categories already running'
            return False
        if active and (candidate not in PARALLEL or any(name not in PARALLEL for name in active)):
            self.reason = 'exclusive category requires an idle runner'
            return False
        if candidate not in DEMANDS:
            return not active
        if self.sample is None:
            return not active
        sample = self.sample
        demands = [self.demands[name] for name in [candidate, *active]]
        if any(d.cpu <= 0 or d.memory <= 0 for d in demands):
            raise ValueError('missing category resource reservation')
        reserve = max(2 * GIB, sample.total_memory * .2)
        if sample.available_memory < reserve + sum(d.memory for d in demands):
            self.reason = 'waiting for memory headroom'
            return False
        if (sample.cpu_pressure >= 10 or sample.memory_pressure >= 1
                or sample.io_pressure >= 2 or sample.swapping
                or sample.busy > sample.capacity * .75):
            self.reason = 'waiting for busy host to recover'
            return False
        if active and (not self.open or sample.busy + sum(d.cpu for d in demands) > sample.capacity * .75):
            self.reason = 'waiting for CPU/pressure headroom'
            return False
        # A single job may exceed our conservative CPU estimate on small hosts;
        # serialize it rather than deadlocking forever on an impossible budget.
        return True
