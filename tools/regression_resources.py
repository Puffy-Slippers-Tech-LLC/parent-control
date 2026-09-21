"""Read-only resource admission for bounded host test categories.

Memory admission budgets new allocations against observed available memory,
with a startup reservation and a growth allowance for active jobs. CPU admission
likewise reserves new work and growth above measured usage; no host process
attribution or ownership inference is used.
"""

from dataclasses import asdict, dataclass
import math
import os
from pathlib import Path
import subprocess
import time
from xml.etree import ElementTree

from regression_ui import KINDS as UI_KINDS

GIB = 1024 ** 3
HOST_WORKERS = 4
HOST_MEMORY_RESERVE = 2 * GIB
ACTIVE_MEMORY_GROWTH = GIB
ACTIVE_MEMORY_GROWTH_POOL = 2 * GIB
ACTIVE_CPU_GROWTH = 1
RESOURCE_STARTUP_SECONDS = 20
PRESSURE_RECOVERY_SECONDS = 4
# Host-wide I/O stalls are advisory for ordinary host tests: background disk
# traffic can report sustained PSI on an otherwise idle desktop. Keep these
# thresholds for build/VM work and companions sharing a branch set with builds.
IO_PRESSURE_HIGH = 10
IO_PRESSURE_LOW = 5
# Artifact and VM launches keep the original conservative I/O admission limit.
EXCLUSIVE_IO_PRESSURE_HIGH = 2
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
DEMANDS.update({kind: DEMANDS['ui'] for kind in UI_KINDS})
PARALLEL = frozenset(DEMANDS)
DEMANDS.update({'ui-exclusive': Demand(4, 4 * GIB)})
DEMANDS['unit-exclusive'] = DEMANDS['unit']
DEMANDS.update({kind: DEMANDS['unit'] for kind in ('cleanup', 'cleanup-exclusive')})
DEMANDS.update(publish=Demand(2, 6 * GIB), artifacts=Demand(2, 4 * GIB),
               system=Demand(0, 0), e2e=Demand(0, 0))

# Publishing companions with reviewed isolation. Units/components have live
# overlap evidence; screen fidelity and request behavior use private compositor/
# bus/PipeWire/XDG state and per-test evidence, separate from publishing's private
# sbuild tree. Keep these identities explicit; other UI buckets stay excluded.
# Keep these symmetric: launch order must not change isolation requirements.
BUILD_KINDS = frozenset(('publish', 'artifacts'))
BUILD_COMPANIONS = frozenset(('unit', 'component', 'ui-screen', 'ui-request'))
# Artifact construction reads the checkout and writes only private source,
# package and fixture directories. It neither installs nor launches the product.
ARTIFACT_COMPANIONS = PARALLEL | BUILD_KINDS


def compatible(first, second):
    if first.startswith('cleanup') or second.startswith('cleanup'):
        return first == second == 'cleanup'
    if 'artifacts' in (first, second):
        return (second if first == 'artifacts' else first) in ARTIFACT_COMPANIONS
    if first in BUILD_KINDS:
        return second in BUILD_COMPANIONS
    if second in BUILD_KINDS:
        return first in BUILD_COMPANIONS
    return first in PARALLEL and second in PARALLEL


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
    cpu_pressure_avg10: float | None = None
    memory_pressure_avg10: float | None = None
    io_pressure_avg10: float | None = None


class Monitor:
    def __init__(self, proc=Path('/proc'), cgroups=Path('/sys/fs/cgroup'), monotonic=time.monotonic):
        self.proc, self.cgroups = proc, cgroups
        self.previous = None
        self.clock = monotonic

    def sample(self):
        def pressure(name, line):
            rows = dict(row.split(' ', 1) for row in
                        (self.proc / 'pressure' / name).read_text().splitlines())
            fields = dict(field.split('=') for field in rows[line].split())
            average, total = float(fields['avg10']), int(fields['total'])
            if not math.isfinite(average) or average < 0 or total < 0:
                raise ValueError('invalid pressure measurement')
            return average, total

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
        pressures = [pressure('cpu', 'some'), pressure('memory', 'some'), pressure('io', 'full')]
        pressure_totals = [value for _, value in pressures]
        now = self.clock()
        previous, self.previous = self.previous, (total, idle, swap, now, pressure_totals)
        if previous is None or total <= previous[0] or now <= previous[3]:
            raise ValueError('resource monitor warming up')
        interval = now - previous[3]
        page_size = os.sysconf('SC_PAGE_SIZE')
        swap_in, swap_out = ((current - before) * page_size / interval
                            for current, before in zip(swap, previous[2]))
        # PSI totals are microseconds stalled. Use the same observation interval
        # as CPU/swap, so a completed I/O burst does not keep admission closed
        # while avg10 decays and then incur another recovery window. Retain the
        # kernel averages in evidence to distinguish current stalls from history.
        current_pressure = [(current - before) / (interval * 10_000)
                            for current, before in zip(pressure_totals, previous[4])]
        # Reading a few pages evicted earlier does not imply current reclaim.
        # Any new swap write still closes admission, as does >= 1 MiB/s of
        # swap reads. Memory reserves and PSI remain independent mandatory gates.
        swapping = swap_out > 0 or swap_in >= SWAP_IN_LIMIT
        # Aggregate /proc/stat spans all host CPUs, not only our affinity set.
        busy = (1 - (idle - previous[1]) / (total - previous[0])) * (os.cpu_count() or 1)
        result = Sample(capacity, max(0, busy), total_memory, available,
                        *current_pressure, swapping, swap_in, swap_out,
                        *(average for average, _ in pressures))
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
        self.io_healthy_since = None
        self.io_open = False
        self.sample = None
        self.reason = 'resource monitor warming up'
        self.demands = dict(DEMANDS)
        self.observe = observe
        self.startup_until = {}

    def started(self, kind):
        # Keep the full active budget until a sample taken after startup can
        # reflect the new worker. Same-kind launches extend the reservation.
        self.startup_until[kind] = self.clock() + RESOURCE_STARTUP_SECONDS

    def overlap_ready(self):
        """Allow a bounded phase warm-up; missing metrics retain serial fallback."""
        self.update()
        return self.sample is None or self.open

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
            self.io_open = False
            self.io_healthy_since = None
            self.reason = 'resource measurements unavailable; serial execution'
            self.observe({'monotonic': now, 'available': False})
            return
        sample = self.sample
        high = sample.cpu_pressure >= 10 or sample.memory_pressure >= 1 or sample.swapping
        low = sample.cpu_pressure < 5 and sample.memory_pressure < .5 and not sample.swapping
        if high:
            self.open = False
            self.healthy_since = None
        elif low:
            if self.healthy_since is None:
                self.healthy_since = now
            if now - self.healthy_since >= PRESSURE_RECOVERY_SECONDS:
                self.open = True
        else:
            self.healthy_since = None
        # Preserve the original combined recovery window for I/O-sensitive work.
        # Ordinary host work must neither wait on nor reset this separate gate.
        if high or sample.io_pressure >= IO_PRESSURE_HIGH:
            self.io_open = False
            self.io_healthy_since = None
        elif low and sample.io_pressure < IO_PRESSURE_LOW:
            if self.io_healthy_since is None:
                self.io_healthy_since = now
            if now - self.io_healthy_since >= PRESSURE_RECOVERY_SECONDS:
                self.io_open = True
        else:
            self.io_healthy_since = None
        self.reason = 'waiting for sustained resource headroom' if not self.open else 'resource headroom available'
        self.observe({'monotonic': now, 'available': True, 'overlap_gate': self.open,
                      'host_io_pressure_advisory': True, 'io_overlap_gate': self.io_open,
                      'pressure_basis': 'sample interval',
                      'pressure_healthy_seconds': (0 if self.healthy_since is None
                                                   else now - self.healthy_since),
                      'pressure_recovery_seconds': PRESSURE_RECOVERY_SECONDS,
                      'io_pressure_high': IO_PRESSURE_HIGH,
                      'io_pressure_low': IO_PRESSURE_LOW,
                      'exclusive_io_pressure_high': EXCLUSIVE_IO_PRESSURE_HIGH,
                      **asdict(sample)})

    def allows(self, candidate, active):
        self.update()
        if len(active) >= HOST_WORKERS:
            self.reason = f'{HOST_WORKERS} host categories already running'
            return False
        if any(not compatible(candidate, name) for name in active):
            self.reason = ('exclusive work waits for all host branches to finish'
                           if candidate in ('unit-exclusive', 'ui-exclusive', 'cleanup-exclusive')
                           else 'waiting for incompatible active host work to finish')
            return False
        if candidate not in DEMANDS:
            return not active
        if self.sample is None:
            return not active
        sample = self.sample
        demands = [self.demands[name] for name in [candidate, *active]]
        if any(d.cpu <= 0 or d.memory <= 0 for d in demands):
            raise ValueError('missing category resource reservation')
        # MemAvailable already reflects resident active work. Reserve the full
        # candidate, plus a shared growth pool for established workers. Adding
        # 1 GiB per branch without a cap stranded the sixth worker despite low
        # pressure. Startup budgets stay outside that pool: they may not yet
        # be reflected in the available-memory sample.
        # VM demand already includes all configured guest RAM plus controller/
        # QEMU overhead. Keep the same fixed desktop reserve as host work;
        # a percentage of installed RAM needlessly blocks larger machines.
        reserve = HOST_MEMORY_RESERVE
        starting = [self.last < self.startup_until.get(name, math.inf) for name in active]
        startup_memory = sum(demand.memory for demand, startup in zip(demands[1:], starting)
                             if startup)
        growth_memory = min(ACTIVE_MEMORY_GROWTH_POOL, sum(
            min(demand.memory, ACTIVE_MEMORY_GROWTH)
            for demand, startup in zip(demands[1:], starting) if not startup))
        required = reserve + demands[0].memory + startup_memory + growth_memory
        if sample.available_memory < required:
            self.reason = (f'waiting for memory headroom ({sample.available_memory / GIB:.1f} GiB '
                           f'available; requires {required / GIB:.1f} GiB)')
            return False
        io_limit = (EXCLUSIVE_IO_PRESSURE_HIGH if candidate in ('artifacts', 'system', 'e2e')
                    else IO_PRESSURE_HIGH)
        io_sensitive = candidate in ('publish', 'artifacts', 'system', 'e2e') or any(
            kind in BUILD_KINDS for kind in active)
        for limited, resource in ((sample.swapping, 'swap activity'),
                                  (sample.memory_pressure >= 1, 'memory pressure'),
                                  (io_sensitive and sample.io_pressure >= io_limit, 'I/O pressure'),
                                  (sample.cpu_pressure >= 10, 'CPU pressure'),
                                  (sample.busy > sample.capacity * .75, 'CPU utilization')):
            if limited:
                self.reason = f'waiting for {resource} to recover'
                return False
        if active and (not self.open or (io_sensitive and not self.io_open)):
            self.reason = 'waiting for sustained resource headroom'
            return False
        # Measured busy CPU already includes established workers. Budget their
        # possible growth instead of adding their entire demand a second time.
        # Newly launched workers still need full reservations until a fresh
        # post-startup sample, including launches within the same scheduler pass.
        additional_cpu = demands[0].cpu + sum(
            demand.cpu if startup else min(demand.cpu, ACTIVE_CPU_GROWTH)
            for demand, startup in zip(demands[1:], starting))
        if active and sample.busy + additional_cpu > sample.capacity * .75:
            self.reason = (f'waiting for CPU headroom (needs {additional_cpu:.1f} free cores '
                           f'below {sample.capacity * .75:.1f}-core limit)')
            return False
        # A single job may exceed our conservative CPU estimate on small hosts;
        # serialize it rather than deadlocking forever on an impossible budget.
        return True
