"""Shared watch resource sampling and viewer selection."""

from collections import deque
from pathlib import Path
import time


class ResourceUsage:
    """Host utilization sampled once per second, without external commands."""

    def __init__(self, proc=Path('/proc'), block=Path('/sys/block'), clock=time.monotonic):
        self.proc, self.block, self.clock = proc, block, clock
        self.previous_cpu = self.previous_disks = None
        self.last = None
        self.label = ''
        self.history = deque(maxlen=60)
        self.charts = []

    def text(self):
        now = self.clock()
        if self.last is not None and now - self.last < 1:
            return self.label
        interval = now - self.last if self.last is not None else 0
        self.last = now
        cpu = memory = disk = None
        try:
            # Guest counters are already included in user/nice; count them once.
            ticks = list(map(int, (self.proc / 'stat').read_text().splitlines()[0].split()[1:9]))
            total, idle = sum(ticks), ticks[3] + ticks[4]
            if self.previous_cpu is not None:
                elapsed, resting = total - self.previous_cpu[0], idle - self.previous_cpu[1]
                if elapsed > 0 and 0 <= resting <= elapsed:
                    cpu = 100 * (elapsed - resting) / elapsed
            self.previous_cpu = total, idle
        except (OSError, ValueError, IndexError):
            self.previous_cpu = None
        try:
            values = {key: int(value.split()[0]) for key, value in
                      (row.split(':', 1) for row in (self.proc / 'meminfo').read_text().splitlines())}
            if values['MemTotal'] > 0:
                memory = 100 * (1 - values['MemAvailable'] / values['MemTotal'])
        except (OSError, ValueError, IndexError, KeyError):
            pass
        try:
            disks = {}
            for row in (self.proc / 'diskstats').read_text().splitlines():
                fields = row.split()
                # Whole physical devices only: exclude partitions, loop devices
                # and stacked virtual mappings of the same underlying disks.
                if (self.block / fields[2] / 'device').exists():
                    disks[tuple(fields[:3])] = int(fields[12])
            if self.previous_disks is not None and interval > 0:
                # Use elapsed I/O busy time (iostat %util), rather than summed
                # request times, which double-count concurrent I/O. A busy
                # device is not necessarily at its throughput limit on NVMe.
                activity = [(busy - self.previous_disks[key]) / (interval * 10)
                            for key, busy in disks.items()
                            if key in self.previous_disks and busy >= self.previous_disks[key]]
                if activity:
                    disk = max(activity)
            self.previous_disks = disks
        except (OSError, ValueError, IndexError):
            self.previous_disks = None
        def percentage(value):
            return f'{max(0, min(100, value)):3.0f}%' if value is not None else '   —'
        self.history.append((now, cpu, memory, disk))
        self.charts = []
        for index, (name, value) in enumerate(zip(('CPU', 'Memory', 'Disk'), (cpu, memory, disk)), 1):
            segments, segment, previous = [], [], None
            for sample in self.history:
                stamp, reading = sample[0], sample[index]
                if stamp < now - 59:
                    continue
                if reading is None or (previous is not None and stamp - previous > 2.5):
                    if segment:
                        segments.append(segment)
                        segment = []
                if reading is not None:
                    segment.append(((stamp - now + 59) / 59, 1 - max(0, min(100, reading)) / 100))
                previous = stamp
            if segment:
                segments.append(segment)
            self.charts.append(dict(label=name, text=percentage(value), segments=segments))
        self.label = ' | '.join(f'{chart["label"]}: {chart["text"]}' for chart in self.charts)
        return self.label


def viewer_entries(entries, *, scope='all', vm_ids=None, current_vms=None):
    """Keep checkout UI workers, followed by one source per VM in ID order."""
    result, vms = {}, {}
    for entry, value in entries.items():
        if scope != 'all' and entry[0] != scope:
            continue
        if entry[1].startswith('ui-'):
            result[entry] = value
            continue
        if (scope == 'all' and current_vms is not None and entry[1] not in current_vms
                and not (value[2] or value[3])):
            # Other worktrees can retain a retired VM name/layout. Keep their
            # live controllers observable, without adding stale idle global tabs.
            continue
        previous = vms.get(entry[1])
        # Prefer the current controller, then a running unlocked display, over
        # an idle registration from another checkout. Ties keep discovery order.
        if previous is None or (value[3], value[2]) > (previous[1][3], previous[1][2]):
            vms[entry[1]] = entry, value
    ids = vm_ids or {}
    for entry, value in sorted(vms.values(), key=lambda item: (
            ids.get(item[0]) is None, int(ids.get(item[0]) or 0))):
        result[entry] = value
    return result
