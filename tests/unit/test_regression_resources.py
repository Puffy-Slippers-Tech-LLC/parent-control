"""Admission budgets and pressure hysteresis use deterministic observations."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from regression_resources import Admission, Demand, GIB, Monitor, Sample, PARALLEL, compatible, vm_demand


def healthy():
    return Sample(20, 2, 32 * GIB, 24 * GIB, 0, 0, 0, False)


def gate():
    state = SimpleNamespace(now=0, sample=healthy())
    admission = Admission(SimpleNamespace(sample=lambda: state.sample), lambda: state.now)
    return state, admission


def warm(state, admission, active=('ui',)):
    for kind in active:
        admission.started(kind)
    admission.update()
    state.now += 20
    admission.update()


def test_second_category_waits_for_fresh_healthy_samples_then_short_jobs_fill_slots():
    state, admission = gate()
    assert admission.allows('ui', [])
    assert not admission.allows('unit', ['ui'])
    state.now = 2
    assert not admission.allows('unit', ['ui'])
    state.now = 3
    assert not admission.allows('unit', ['ui'])  # Cached readings cannot confirm recovery.
    state.now = 4
    assert admission.allows('unit', ['ui'])
    assert admission.allows('component', ['ui', 'unit'])
    assert admission.allows('static', ['ui', 'unit', 'component'])
    assert not admission.allows('child-gjs', ['ui', 'unit', 'component', 'static'])
    assert admission.reason == '4 host categories already running'
    assert admission.allows('component', ['ui'])


@pytest.mark.parametrize('field,value', [('cpu_pressure', 10), ('memory_pressure', 1),
                                        ('io_pressure', 10), ('swapping', True)])
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
    state.now += 2
    assert not admission.allows('unit', ['ui'])
    state.now += 2
    assert admission.allows('unit', ['ui'])


def test_memory_budget_applies_even_to_single_job_and_cpu_budget_reduces_overlap():
    state, admission = gate()
    warm(state, admission)
    state.now += 2
    state.sample = replace(healthy(), available_memory=5 * GIB)
    assert not admission.allows('ui', [])
    state.now += 2
    state.sample = replace(healthy(), busy=14)
    assert not admission.allows('unit', ['ui'])
    assert admission.allows('unit', [])


def test_moderate_recorded_io_does_not_close_an_open_gate():
    state, admission = gate()
    warm(state, admission, active=('unit',))
    state.now += 2
    # Current host run 20260914T025211Z-d6979e89, monotonic 119153.582034563.
    state.sample = Sample(20, 2.2162029056882537, 32733339648, 11046166528,
                          .3569413056258864, 0, 7.194374158303749, False)
    assert admission.allows('ui-screen', ['unit'])
    state.now += 2
    state.sample = replace(state.sample, io_pressure=10)
    assert not admission.allows('ui-screen', ['unit'])
    assert admission.reason == 'waiting for I/O pressure to recover'
    state.sample = replace(state.sample, io_pressure=0)
    for _ in range(2):
        state.now += 2
        assert not admission.allows('ui-screen', ['unit'])
    state.now += 2
    assert admission.allows('ui-screen', ['unit'])


def test_unknown_categories_are_exclusive_and_missing_metrics_fall_back_to_serial():
    state, admission = gate()
    warm(state, admission)
    assert not admission.allows('future-heavy-suite', ['ui'])
    assert admission.allows('future-heavy-suite', [])
    admission.monitor.sample = lambda: (_ for _ in ()).throw(OSError('missing'))
    state.now += 2
    assert not admission.allows('unit', ['ui'])
    assert admission.allows('unit', [])


def test_two_ui_buckets_keep_growth_headroom_and_unreviewed_modules_stay_exclusive():
    state, admission = gate()
    assert not admission.allows('ui', ['ui'])
    warm(state, admission)
    assert admission.allows('ui', ['ui'])
    assert not admission.allows('ui-exclusive', ['ui'])
    assert not admission.allows('ui', ['ui-exclusive'])
    assert admission.allows('ui-exclusive', [])
    state.now += 2
    state.sample = replace(healthy(), available_memory=6 * GIB)
    assert not admission.allows('ui', ['ui'])
    assert admission.allows('ui', [])


@pytest.mark.parametrize('kind', ['ui-accessible', 'ui-watch'])
def test_reviewed_e2e_ui_modules_keep_resource_and_pairing_limits(kind):
    state, admission = gate()
    warm(state, admission, active=('ui-layout', 'ui-feedback'))
    assert admission.allows(kind, ['ui-layout', 'ui-feedback'])
    for other in ('ui-shell', 'ui-accessible', 'ui-watch', 'artifacts'):
        assert compatible(kind, other) and compatible(other, kind)
    for other in ('publish', 'system', 'e2e', 'ui-exclusive'):
        assert not compatible(kind, other) and not compatible(other, kind)
    state.now += 2
    state.sample = replace(healthy(), available_memory=8 * GIB - 1)
    assert not admission.allows(kind, ['ui-layout', 'ui-feedback'])
    assert 'memory headroom' in admission.reason


@pytest.mark.parametrize('build', ['publish'])
@pytest.mark.parametrize('companion', ['unit', 'component', 'ui-screen', 'ui-request'])
def test_build_pairings_are_symmetric_and_still_require_headroom(build, companion):
    state, admission = gate()
    assert not admission.allows(build, [companion])
    warm(state, admission, active=(build, companion))
    assert admission.allows(build, [companion])
    assert admission.allows(companion, [build])
    state.now += 2
    state.sample = replace(healthy(), available_memory=3 * GIB)
    assert not admission.allows(build, [companion])
    assert not admission.allows(companion, [build])


@pytest.mark.parametrize('candidate,active,required_gib', [
    ('unit', ['ui-screen'], 5),
    ('ui-layout', ['ui-screen'], 7),
    ('ui-preview', ['ui-request'], 7),
    ('publish', ['unit'], 9),
    ('unit', ['publish'], 5),
    ('component', ['publish'], 4),
    ('ui-screen', ['publish'], 7),
    ('publish', ['ui-screen'], 9),
    ('ui-layout', ['ui-screen', 'ui-request'], 8),
    ('component', ['publish', 'unit'], 5),
    ('component', ['ui-screen', 'unit', 'static'], 5),
    ('component', ['ui-request', 'ui-screen', 'ui-preview'], 5),
    ('ui-shell', ['ui-request', 'ui-screen', 'unit'], 8),
    ('ui-request', [], 6),
    ('artifacts', ['artifacts'], 7),
    ('artifacts', ['publish', 'unit'], 8),
])
def test_host_memory_boundary_reserves_candidate_and_active_growth(candidate, active, required_gib):
    state, admission = gate()
    warm(state, admission, active=active)
    state.now += 2
    state.sample = replace(healthy(), available_memory=required_gib * GIB - 1)
    assert not admission.allows(candidate, active)
    assert admission.reason == (f'waiting for memory headroom ({required_gib:.1f} GiB '
                                f'available; requires {required_gib:.1f} GiB)')
    state.now += 2
    state.sample = replace(state.sample, available_memory=required_gib * GIB)
    assert admission.allows(candidate, active)


@pytest.mark.parametrize('total_gib', [16, 32, 64, 128])
def test_seven_gib_available_admits_host_companions_independent_of_installed_ram(total_gib):
    state, admission = gate()
    state.sample = replace(healthy(), total_memory=total_gib * GIB, available_memory=7 * GIB)
    warm(state, admission, active=('ui-screen',))
    assert admission.allows('unit', ['ui-screen'])
    assert admission.allows('ui-layout', ['ui-screen'])


@pytest.mark.parametrize('candidate', ['ui-feedback', 'ui-shell'])
def test_recorded_idle_branch_memory_sample_respects_reduced_worker_cap(candidate):
    # Run 20260914T010021Z-8419fee6 at monotonic 112239.879626133:
    # branch 4 was idle; five established jobs made the old growth sum demand
    # 11 GiB despite 9.57 GiB available and all other admission gates passing.
    state, admission = gate()
    active = ['ui-request', 'ui-screen', 'ui-preview', 'ui-layout', 'unit']
    state.sample = Sample(20, 5.772238514173997, 32733339648, 10280558592,
                          1.2861386787729767, 0, .7075686650497106, False)
    warm(state, admission, active=active)
    assert not admission.allows(candidate, active)
    assert admission.reason == '4 host categories already running'


def test_memory_growth_pool_never_caps_startup_or_uses_a_stale_sample():
    state, admission = gate()
    active = ['ui-request', 'ui-screen']
    warm(state, admission, active=active)
    admission.started('ui-layout')
    active.append('ui-layout')
    state.sample = replace(healthy(), available_memory=12 * GIB - 1)
    state.now += 2
    assert not admission.allows('ui-shell', active)
    assert admission.reason == 'waiting for memory headroom (12.0 GiB available; requires 12.0 GiB)'
    state.sample = replace(healthy(), available_memory=12 * GIB)
    state.now += 2
    assert admission.allows('ui-shell', active)

    state.sample = replace(healthy(), available_memory=8 * GIB)
    state.now += 15
    assert not admission.allows('ui-shell', active)
    state.now += 1
    assert not admission.allows('ui-shell', active)  # Last sample still predates startup expiry.
    state.now += 1
    assert admission.allows('ui-shell', active)
    admission.started('ui-layout')
    assert not admission.allows('ui-shell', active)


def test_third_category_checks_both_companions_and_total_cpu_budget():
    state, admission = gate()
    warm(state, admission, active=('publish', 'unit'))
    assert admission.allows('component', ['publish', 'unit'])
    assert not admission.allows('ui-preview', ['unit', 'publish'])
    assert admission.allows('artifacts', ['unit', 'component'])
    state.now += 2
    state.sample = replace(healthy(), busy=12)
    assert admission.allows('component', ['unit'])
    assert not admission.allows('component', ['publish', 'unit'])


def test_fourth_category_checks_all_companions_and_total_cpu_budget():
    state, admission = gate()
    active = ['unit', 'component', 'static']
    warm(state, admission, active=active)
    assert admission.allows('ui-screen', active)
    assert not admission.allows('publish', active)
    assert admission.allows('artifacts', active)
    state.now += 2
    state.sample = replace(healthy(), busy=9)
    assert admission.allows('ui-screen', active[:2])
    assert not admission.allows('ui-screen', active)


@pytest.mark.parametrize('slots,limit', [(3, 9), (4, 8)])
@pytest.mark.parametrize('excess,allowed', [(0, True), (.01, False)])
def test_ui_buckets_budget_measured_cpu_plus_active_growth(slots, limit, excess, allowed):
    state, admission = gate()
    active = ['ui-request', 'ui-screen', 'ui-preview'][:slots - 1]
    warm(state, admission, active=active)
    state.now += 2
    state.sample = replace(healthy(), busy=limit + excess)
    assert admission.allows('ui-shell', active) is allowed
    if not allowed:
        assert admission.reason == ('waiting for CPU headroom '
                                    f'(needs {slots + 3:.1f} free cores below 15.0-core limit)')


def test_cpu_startup_reservation_waits_for_fresh_sample_and_restarts_on_launch():
    state, admission = gate()
    warm(state, admission, active=())
    state.sample = replace(healthy(), busy=6)
    active = ['ui-request', 'ui-screen', 'ui-preview']
    for kind in active:
        admission.started(kind)
    state.now += 2
    assert not admission.allows('ui-layout', active)
    state.now += 17
    assert not admission.allows('ui-layout', active)
    state.now += 1
    assert not admission.allows('ui-layout', active)  # Cached sample is too old.
    state.now += 1
    assert admission.allows('ui-layout', active)
    admission.started('ui-preview')
    assert not admission.allows('ui-layout', active)


def test_publishing_does_not_strand_component_with_eight_gib_available():
    state, admission = gate()
    warm(state, admission)
    admission.started('publish')
    state.now += 2
    state.sample = replace(healthy(), available_memory=8 * GIB)
    assert not admission.allows('component', ['publish'])
    state.now += 20
    assert admission.allows('component', ['publish'])


def test_startup_reservation_requires_fresh_sample_and_restarts_for_next_launch():
    state, admission = gate()
    warm(state, admission)
    state.now += 2
    state.sample = replace(healthy(), available_memory=7 * GIB)
    admission.started('ui-screen')
    assert not admission.allows('ui-layout', ['ui-screen'])
    state.now += 19
    assert not admission.allows('ui-layout', ['ui-screen'])
    state.now += 1
    # The cached sample predates the end of startup, even though time elapsed.
    assert not admission.allows('ui-layout', ['ui-screen'])
    state.now += 1
    assert admission.allows('ui-layout', ['ui-screen'])
    admission.started('ui-screen')
    assert not admission.allows('ui-layout', ['ui-screen'])


@pytest.mark.parametrize('kind', ['system', 'e2e'])
@pytest.mark.parametrize('total_gib', [24, 32, 64, 128])
def test_vm_keeps_full_guest_overhead_and_fixed_desktop_reserve(kind, total_gib):
    state, admission = gate()
    admission.demands[kind] = Demand(7, 13 * GIB)
    state.sample = replace(healthy(), total_memory=total_gib * GIB, available_memory=15 * GIB - 1)
    assert not admission.allows(kind, [])
    state.now += 2
    state.sample = replace(state.sample, available_memory=15 * GIB)
    assert admission.allows(kind, [])
    state.now += 2
    state.sample = replace(state.sample, available_memory=18 * GIB)
    assert admission.allows(kind, [])


@pytest.mark.parametrize('other', ['publish', 'system', 'e2e', 'ui',
                                 'ui-layout', 'ui-feedback', 'ui-preview', 'ui-shell',
                                 'ui-exclusive', 'ui-future', 'fixture-runtime',
                                 'source', 'static', 'child-node', 'child-gjs', 'backend'])
@pytest.mark.parametrize('build', ['publish'])
def test_unqualified_pairings_never_depend_on_launch_order(build, other):
    state, admission = gate()
    warm(state, admission)
    assert not compatible(build, other)
    assert not admission.allows(build, [other])
    assert not admission.allows(other, [build])


@pytest.mark.parametrize('other', sorted(PARALLEL | {'publish', 'artifacts'}))
def test_artifact_operations_admit_private_companions_in_either_order(other):
    state, admission = gate()
    warm(state, admission, active=('artifacts', other))
    assert compatible('artifacts', other)
    assert compatible(other, 'artifacts')
    assert admission.allows('artifacts', [other])
    assert admission.allows(other, ['artifacts'])
    state.now += 2
    state.sample = replace(healthy(), available_memory=3 * GIB)
    assert not admission.allows('artifacts', [other])
    assert not admission.allows(other, ['artifacts'])


@pytest.mark.parametrize('other', ['system', 'e2e', 'ui-exclusive', 'future-job'])
def test_artifact_operations_keep_vm_and_unknown_work_exclusive(other):
    assert not compatible('artifacts', other)
    assert not compatible(other, 'artifacts')


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


@pytest.mark.parametrize('kind', ['artifacts', 'system', 'e2e'])
@pytest.mark.parametrize('initially_open', [False, True])
@pytest.mark.parametrize('io_pressure,exclusive_allowed,host_allowed', [
    (1.999, True, True), (2, False, True), (9.999, False, True), (10, False, False),
])
def test_host_io_relaxation_preserves_exclusive_launch_limit(
        kind, initially_open, io_pressure, exclusive_allowed, host_allowed):
    state, admission = gate()
    admission.demands.update(system=Demand(7, 13 * GIB), e2e=Demand(7, 13 * GIB))
    if initially_open:
        warm(state, admission)
    state.now += 2
    state.sample = replace(healthy(), io_pressure=io_pressure)
    assert admission.allows(kind, []) is exclusive_allowed
    if not exclusive_allowed:
        assert admission.reason == 'waiting for I/O pressure to recover'
    assert admission.allows('publish', []) is host_allowed
    assert admission.allows('unit', []) is host_allowed


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


@pytest.mark.parametrize('field,value', [('cpu_pressure', 7), ('io_pressure', 5),
                                        ('io_pressure', 9.999)])
def test_marginal_pressure_does_not_open_closed_gate_or_flap_open_gate(field, value):
    state, admission = gate()
    state.sample = replace(healthy(), **{field: value})
    warm(state, admission)
    assert not admission.open
    state.sample = healthy()
    state.now += 2
    warm(state, admission)
    assert admission.open
    state.now += 2
    state.sample = replace(healthy(), **{field: value})
    assert admission.allows('unit', ['ui'])


@pytest.fixture
def monitored_host(tmp_path, monkeypatch):
    proc = tmp_path / 'proc'
    proc.mkdir()
    (proc / 'self').mkdir()
    (proc / 'pressure').mkdir()
    (proc / 'self/cgroup').write_text('0::/user/job\n')
    (proc / 'meminfo').write_text('MemTotal: 33554432 kB\nMemAvailable: 25165824 kB\n')
    (proc / 'stat').write_text('cpu 100 0 0 900 0 0 0 0\n')
    (proc / 'vmstat').write_text('pswpin 5\npswpout 10\n')
    for name in ('cpu', 'memory', 'io'):
        (proc / 'pressure' / name).write_text('some avg10=0.00 total=0\nfull avg10=0.00 total=0\n')
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
    state = SimpleNamespace(now=0, proc=proc)
    state.monitor = Monitor(proc, cgroups, lambda: state.now)
    return state


@pytest.mark.parametrize('reads,writes,swapping', [(1, 0, False), (512, 0, True), (0, 1, True)])
def test_monitor_respects_ancestor_limits_and_detects_swap_activity(monitored_host,
                                                                  reads, writes, swapping):
    state = monitored_host
    proc, monitor = state.proc, state.monitor
    with pytest.raises(ValueError, match='warming'):
        monitor.sample()
    state.now = 2
    (proc / 'stat').write_text('cpu 110 0 0 990 0 0 0 0\n')
    (proc / 'vmstat').write_text(f'pswpin {5 + reads}\npswpout {10 + writes}\n')
    sample = monitor.sample()
    assert sample.capacity == 6
    assert sample.busy == pytest.approx(2)
    assert sample.total_memory == 12 * GIB and sample.available_memory == 7 * GIB
    assert sample.swapping is swapping
    assert sample.swap_in_bytes_per_second == reads * 2048
    assert sample.swap_out_bytes_per_second == writes * 2048


def test_monitor_uses_current_stalls_and_retains_trailing_averages(monitored_host):
    state = monitored_host
    observations = []
    admission = Admission(state.monitor, lambda: state.now, observations.append)
    admission.update()  # Prime CPU, swap and PSI counters together.
    assert admission.sample is None
    for now in (2, 4, 6):
        state.now = now
        (state.proc / 'stat').write_text(f'cpu {100 + now * 5} 0 0 {900 + now * 45} 0 0 0 0\n')
        for name, average, stall_per_second in [('cpu', 30, 20_000),
                                                ('memory', 3, 2_000), ('io', 12, 5_000)]:
            total = now * stall_per_second
            (state.proc / 'pressure' / name).write_text(
                f'some avg10={average} total={total}\nfull avg10={average} total={total}\n')
        admission.update()
        assert admission.open is (now == 6)
    sample = admission.sample
    assert (sample.cpu_pressure, sample.memory_pressure, sample.io_pressure) == (2, .2, .5)
    assert (sample.cpu_pressure_avg10, sample.memory_pressure_avg10, sample.io_pressure_avg10) == (30, 3, 12)
    assert observations[-1]['pressure_basis'] == 'sample interval'
    assert observations[-1]['pressure_healthy_seconds'] == 4
    assert observations[-1]['pressure_recovery_seconds'] == 4
    assert observations[-1]['io_pressure_high'] == 10
    assert observations[-1]['io_pressure_low'] == 5
    assert observations[-1]['exclusive_io_pressure_high'] == 2
    assert observations[-1]['io_pressure_avg10'] == 12
    assert admission.allows('child-gjs', ['static'])

    # A new burst must close admission immediately, even before avg10 catches up.
    state.now = 8
    (state.proc / 'stat').write_text('cpu 140 0 0 1260 0 0 0 0\n')
    (state.proc / 'pressure/io').write_text('some avg10=0 total=230000\nfull avg10=0 total=230000\n')
    assert not admission.allows('child-gjs', ['static'])
    assert not admission.open
    assert admission.sample.io_pressure == 10
    assert admission.sample.io_pressure_avg10 == 0


@pytest.mark.parametrize('counter', ['-1', 'missing'])
def test_invalid_pressure_counters_disable_overlap(monitored_host, counter):
    state = monitored_host
    admission = Admission(state.monitor, lambda: state.now)
    admission.update()
    state.now = 2
    (state.proc / 'stat').write_text('cpu 110 0 0 990 0 0 0 0\n')
    suffix = '' if counter == 'missing' else f' total={counter}'
    (state.proc / 'pressure/io').write_text(f'full avg10=0{suffix}\n')
    assert not admission.allows('child-gjs', ['static'])
    assert admission.sample is None
    assert admission.allows('child-gjs', [])


def test_pressure_counter_reset_disables_overlap_then_recovers(monitored_host):
    state = monitored_host
    (state.proc / 'pressure/io').write_text('full avg10=0 total=100000\n')
    admission = Admission(state.monitor, lambda: state.now)
    admission.update()
    (state.proc / 'pressure/io').write_text('full avg10=0 total=0\n')
    for now in (2, 4, 6, 8):
        state.now = now
        (state.proc / 'stat').write_text(f'cpu {100 + now * 5} 0 0 {900 + now * 45} 0 0 0 0\n')
        admission.update()
        if now == 2:
            assert admission.sample is None
        assert admission.open is (now == 8)
