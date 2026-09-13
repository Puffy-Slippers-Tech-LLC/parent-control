"""Admission budgets and pressure hysteresis use deterministic observations."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from regression_resources import Admission, Demand, GIB, Monitor, Sample, vm_demand


def healthy():
    return Sample(20, 2, 32 * GIB, 24 * GIB, 0, 0, 0, False)


def gate():
    state = SimpleNamespace(now=0, sample=healthy())
    admission = Admission(SimpleNamespace(sample=lambda: state.sample), lambda: state.now)
    return state, admission


def warm(state, admission):
    admission.update()
    state.now += 20
    admission.update()


def test_second_category_waits_for_twenty_seconds_then_short_jobs_fill_slot():
    state, admission = gate()
    assert admission.allows('ui', [])
    assert not admission.allows('unit', ['ui'])
    state.now = 19
    assert not admission.allows('unit', ['ui'])
    state.now = 22
    assert admission.allows('unit', ['ui'])
    assert not admission.allows('component', ['ui', 'unit'])
    assert admission.allows('component', ['ui'])


@pytest.mark.parametrize('field,value', [('cpu_pressure', 10), ('memory_pressure', 1),
                                        ('io_pressure', 2), ('swapping', True)])
def test_pressure_closes_gate_and_requires_full_healthy_window(field, value):
    state, admission = gate()
    warm(state, admission)
    assert admission.allows('unit', ['ui'])
    state.now += 2
    state.sample = replace(state.sample, **{field: value})
    assert not admission.allows('unit', ['ui'])
    state.sample = healthy()
    state.now += 2
    assert not admission.allows('unit', ['ui'])
    state.now += 20
    assert admission.allows('unit', ['ui'])


def test_memory_budget_applies_even_to_single_job_and_cpu_budget_reduces_overlap():
    state, admission = gate()
    warm(state, admission)
    state.now += 2
    state.sample = replace(healthy(), available_memory=7 * GIB)
    assert not admission.allows('ui', [])
    state.now += 2
    state.sample = replace(healthy(), busy=14)
    assert not admission.allows('unit', ['ui'])
    assert admission.allows('unit', [])


def test_unknown_categories_are_exclusive_and_missing_metrics_fall_back_to_serial():
    state, admission = gate()
    warm(state, admission)
    assert not admission.allows('future-heavy-suite', ['ui'])
    assert admission.allows('future-heavy-suite', [])
    admission.monitor.sample = lambda: (_ for _ in ()).throw(OSError('missing'))
    state.now += 2
    assert not admission.allows('unit', ['ui'])
    assert admission.allows('unit', [])


def test_busy_host_defers_even_serial_vm_or_build_before_acquiring_resources():
    state, admission = gate()
    admission.demands['system'] = Demand(7, 13 * GIB)
    state.sample = replace(healthy(), busy=18)
    assert not admission.allows('system', [])
    assert not admission.allows('publish', [])
    assert not admission.allows('unit', [])
    state.now += 2
    state.sample = healthy()
    assert admission.allows('system', [])
    assert not admission.allows('system', ['unit'])


def test_vm_reservation_uses_configured_ram_and_cpu_through_pinned_reader(tmp_path, monkeypatch):
    calls = []
    def read(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(stdout="<domain><vcpu>6</vcpu><memory unit='MiB'>12000</memory></domain>")
    monkeypatch.setattr('subprocess.run', read)
    demand = vm_demand(tmp_path)
    assert demand.cpu == 7
    assert demand.memory == 12000 * 1024 ** 2 * 11 // 10
    assert calls[0][0] == [str(tmp_path / 'tools/test-vm'), 'xml']
    assert calls[0][1]['timeout'] == 15 and calls[0][1]['check']


def test_marginal_pressure_does_not_open_closed_gate_or_flap_open_gate():
    state, admission = gate()
    state.sample = replace(healthy(), cpu_pressure=7)
    warm(state, admission)
    assert not admission.open
    state.sample = healthy()
    state.now += 2
    warm(state, admission)
    assert admission.open
    state.now += 2
    state.sample = replace(healthy(), cpu_pressure=7)
    assert admission.allows('unit', ['ui'])


@pytest.mark.parametrize('reads,writes,swapping', [(1, 0, False), (512, 0, True), (0, 1, True)])
def test_monitor_respects_ancestor_limits_and_detects_swap_activity(tmp_path, monkeypatch,
                                                                  reads, writes, swapping):
    proc = tmp_path / 'proc'
    proc.mkdir()
    (proc / 'self').mkdir()
    (proc / 'pressure').mkdir()
    (proc / 'self/cgroup').write_text('0::/user/job\n')
    (proc / 'meminfo').write_text('MemTotal: 33554432 kB\nMemAvailable: 25165824 kB\n')
    (proc / 'stat').write_text('cpu 100 0 0 900 0 0 0 0\n')
    (proc / 'vmstat').write_text('pswpin 5\npswpout 10\n')
    for name in ('cpu', 'memory', 'io'):
        (proc / 'pressure' / name).write_text('some avg10=0.00\nfull avg10=0.00\n')
    cgroups = tmp_path / 'cgroups'
    (cgroups / 'user/job').mkdir(parents=True)
    for path in (cgroups / 'user', cgroups / 'user/job'):
        (path / 'cpu.max').write_text('max 100000')
        (path / 'memory.max').write_text('max')
    (cgroups / 'user/cpu.max').write_text('600000 100000')
    (cgroups / 'user/memory.max').write_text(str(12 * GIB))
    (cgroups / 'user/memory.current').write_text(str(5 * GIB))
    monkeypatch.setattr('os.sched_getaffinity', lambda _: set(range(20)))
    monkeypatch.setattr('os.cpu_count', lambda: 20)
    monkeypatch.setattr('os.sysconf', lambda _: 4096)
    ticks = iter([0, 2])
    monitor = Monitor(proc, cgroups, lambda: next(ticks))
    with pytest.raises(ValueError, match='warming'):
        monitor.sample()
    (proc / 'stat').write_text('cpu 110 0 0 990 0 0 0 0\n')
    (proc / 'vmstat').write_text(f'pswpin {5 + reads}\npswpout {10 + writes}\n')
    sample = monitor.sample()
    assert sample.capacity == 6
    assert sample.busy == pytest.approx(2)
    assert sample.total_memory == 12 * GIB and sample.available_memory == 7 * GIB
    assert sample.swapping is swapping
    assert sample.swap_in_bytes_per_second == reads * 2048
    assert sample.swap_out_bytes_per_second == writes * 2048
