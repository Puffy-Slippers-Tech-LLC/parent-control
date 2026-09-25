"""Bounded worker ordering, serialized evidence, and safe scheduler failures."""

from types import SimpleNamespace
import threading

import pytest

from regression_process import Control
from regression_resources import Admission, GIB, Sample
from regression_schedule import Job, ordered_jobs, run_jobs
from regression_ui import buckets
from regression_unit import buckets as unit_buckets


class Capacity:
    reason = 'two categories running'

    def __init__(self, slots=2):
        self.slots = slots

    def allows(self, candidate, active):
        return len(active) < self.slots


@pytest.mark.parametrize('io_pressure', [0, 25, 100])
@pytest.mark.parametrize('category', ['ui', 'cleanup', 'unit', 'unit-private-contracts'])
def test_host_work_fills_four_branches_despite_background_io(io_pressure, category):
    nodes = [f'tests/ui/{name}::test_case' for name in (
        'test_request_layout.py', 'test_parent_feedback.py',
        'test_automation_identity.py', 'test_fixture_gui.py')]
    plan = buckets(nodes)
    if category == 'unit':
        # These previously formed eleven exclusive jobs behind the four unit
        # buckets, leaving three branches idle throughout the serial tail.
        nodes = [f'tests/unit/test_{name}.py::test_case' for name in (
            'appsnapshot_cleanup_safety', 'baseline_guest_cleanup_safety',
            'e2e_request_exit', 'e2e_suite_cleanup_safety', 'e2e_toggle',
            'fix_tests', 'fix_tests_cleanup_safety',
            'qualification_storage_cleanup_safety', 'ui_watch',
            'ui_watch_cleanup_safety', 'vm_watch_session_cleanup_safety')]
        plan = unit_buckets(nodes)
        assert len(plan) == 4
        assert sorted(node for bucket in plan for node in bucket.nodeids) == sorted(nodes)
    if category == 'unit-private-contracts':
        nodes = [f'tests/unit/test_{name}.py::test_case' for name in (
            'build_package', 'challenges_cleanup_safety', 'clean_install_cleanup_safety',
            'customer_reboot_cleanup_safety', 'e2e_app_rows', 'e2e_feedback_read',
            'e2e_kiosk_no_approver', 'launcher_render', 'package_authority_cleanup_safety',
            'package_install_cleanup_safety', 'product_free_entry_cleanup_safety',
            'repeated_operations_cleanup_safety')]
        plan = unit_buckets(nodes)
        assert len(plan) == 4
        assert sorted(node for bucket in plan for node in bucket.nodeids) == sorted(nodes)
    kinds = ['cleanup'] * 4 if category == 'cleanup' else [bucket.kind for bucket in plan]
    release = threading.Event()
    state = SimpleNamespace(now=0)
    sample = Sample(20, 2, 32 * GIB, 24 * GIB, 0, 0, io_pressure, False)
    admission = Admission(SimpleNamespace(sample=lambda: sample), lambda: state.now)
    started, finished = [], []

    def begin(job):
        assert not finished
        started.append(job.kind)
        if len(started) == 4:
            release.set()
        return SimpleNamespace(output=lambda _: None,
            finish=lambda _: finished.append(job.kind), close=lambda: None)

    def command(argv, emit):
        assert release.wait(10), 'reviewed modules left available branches idle'
        return 0

    def tick():
        state.now += 2
        assert state.now <= 60, 'I/O pressure stranded idle host branches'

    maximum = run_jobs([Job(kind, None, [kind]) for kind in kinds],
        control=Control(), admission=admission, begin=begin, run_command=command, tick=tick)
    assert maximum == 4
    assert started == kinds
    assert sorted(finished) == sorted(started)


def test_cold_admission_starts_companions_promptly_and_keeps_startup_memory_reserved():
    release = threading.Event()
    state = SimpleNamespace(now=0)
    sample = Sample(20, 2, 32 * GIB, 13 * GIB, 0, 0, 0, False, io_pressure_avg10=4)
    admission = Admission(SimpleNamespace(sample=lambda: sample), lambda: state.now)
    kinds = ['ui-request', 'ui-screen', 'ui-preview', 'unit']
    started, finished = {}, []

    def begin(job):
        assert not finished
        started[job.kind] = state.now
        if len(started) == len(kinds):
            release.set()
        return SimpleNamespace(output=lambda _: None,
                               finish=lambda _: finished.append(job.kind), close=lambda: None)

    def command(argv, emit):
        assert release.wait(10), 'eligible startup branches were stranded'
        return 0

    def tick():
        state.now += 2

    maximum = run_jobs([Job(kind, None, [kind]) for kind in kinds], control=Control(),
                      admission=admission, begin=begin, run_command=command, tick=tick)
    assert maximum == 4
    assert started['ui-request'] == 0
    assert started['ui-screen'] == started['unit'] == 4
    assert started['ui-preview'] == 20
    assert set(finished) == set(kinds)


@pytest.mark.parametrize('available_gib,expected_workers', [(5, 2), (8, 3)])
def test_real_admission_fills_host_branches_within_memory_budget(available_gib, expected_workers):
    release = threading.Event()
    state = SimpleNamespace(now=0, sample=Sample(20, 2, 32 * GIB, 8 * GIB, 0, 0, 0, False))
    admission = Admission(SimpleNamespace(sample=lambda: state.sample), lambda: state.now)
    admission.update()
    state.now = 20
    admission.update()
    started, finished = [], []

    def begin(job):
        started.append((job.kind, state.now))
        if job.kind == 'publish':
            state.sample = Sample(20, 2, 32 * GIB, available_gib * GIB, 0, 0, 0, False)
        def finish(status):
            assert status == 0
            finished.append(job.kind)
            if job.kind == 'component':
                assert 'publish' not in finished
                release.set()
        return SimpleNamespace(output=lambda _: None, finish=finish, close=lambda: None)

    def command(argv, emit):
        if argv[0] == 'publish':
            assert release.wait(5)
        return 0

    def tick():
        state.now += 2

    maximum = run_jobs([
        Job('publish', None, ['publish'], estimate=100),
        Job('unit', None, ['unit'], estimate=50),
        Job('component', None, ['component'], estimate=10),
    ], control=Control(), admission=admission, begin=begin, run_command=command, tick=tick)
    assert maximum == expected_workers
    assert [kind for kind, _ in started] == ['publish', 'unit', 'component']
    assert started[1][1] >= started[0][1] + 20
    assert set(finished) == {'unit', 'component', 'publish'}
    assert finished.index('component') < finished.index('publish')


@pytest.mark.parametrize('slots', [3, 4])
@pytest.mark.parametrize('available_gib', [8, 14])
def test_real_admission_fills_ui_branches_after_startup_at_low_cpu_load(slots, available_gib):
    release = threading.Event()
    state = SimpleNamespace(now=0, sample=Sample(20, 6, 32 * GIB, available_gib * GIB, 0, 0, 0, False))
    admission = Admission(SimpleNamespace(sample=lambda: state.sample), lambda: state.now)
    admission.update()
    state.now = 20
    admission.update()
    kinds = ['ui-request', 'ui-screen', 'ui-preview', 'ui-layout', 'ui-feedback', 'ui-shell'][:slots]
    started, finished = [], []

    def begin(job):
        assert not finished
        started.append((job.kind, state.now))
        if len(started) == slots:
            release.set()

        def finish(status):
            assert status == 0
            finished.append(job.kind)

        return SimpleNamespace(output=lambda _: None, finish=finish, close=lambda: None)

    def command(argv, emit):
        assert release.wait(10), 'low CPU usage stranded eligible UI branches'
        return 0

    def tick():
        state.now += 2

    maximum = run_jobs([Job(kind, None, [kind]) for kind in kinds],
        control=Control(), admission=admission, begin=begin, run_command=command, tick=tick)
    assert maximum == slots
    assert [kind for kind, _ in started] == kinds
    assert started[2][1] >= started[0][1] + 20
    assert set(finished) == set(kinds)


@pytest.mark.parametrize('companion', ['ui-screen', 'ui-request'])
def test_publishing_refills_when_unit_and_component_are_exhausted(companion):
    release = threading.Event()
    state = SimpleNamespace(now=0, sample=Sample(20, 4, 32 * GIB, 8 * GIB, 0, 0, 0, False))
    admission = Admission(SimpleNamespace(sample=lambda: state.sample), lambda: state.now)
    admission.update()
    state.now = 20
    admission.update()
    started, finished = {}, {}
    reasons = []

    def begin(job):
        started[job.kind] = state.now
        if job.kind == 'publish':
            state.sample = Sample(20, 4, 32 * GIB, 7 * GIB, 0, 0, 0, False)
        if job.kind == companion:
            assert 'component' in finished
            assert 'publish' not in finished
            release.set()

        def finish(status):
            assert status == 0
            finished[job.kind] = state.now

        return SimpleNamespace(output=lambda _: None, finish=finish, close=lambda: None)

    def command(argv, emit):
        if argv[0] == 'publish':
            assert release.wait(5), 'publishing stranded an eligible screen companion'
        return 0

    def tick():
        state.now += 2

    maximum = run_jobs([
        Job('publish', None, ['publish'], estimate=374),
        Job('unit', None, ['unit'], estimate=177),
        Job('component', None, ['component'], estimate=25),
        Job(companion, None, [companion], estimate=20),
        Job('ui-preview', None, ['ui-preview'], estimate=10),
    ], control=Control(), admission=admission, begin=begin, run_command=command,
       tick=tick, waiting=lambda job, reason: reasons.append((job.kind, reason)))
    assert maximum == 3
    assert list(started) == ['publish', 'unit', 'component', companion, 'ui-preview']
    assert started[companion] - finished['component'] <= 2
    assert started['ui-preview'] >= finished['publish']
    assert ('ui-preview', 'waiting for incompatible active host work to finish') in reasons


def test_recorded_observations_admit_request_after_io_and_cpu_recovery():
    # Run 20260914T172159Z-eb26d6e2: component completion at 23417.663,
    # with publishing, screen and units still active. Replay its next samples.
    observations = [
        (23416.465, 2.711, 13.873, 23215812608),
        (23418.470, 3.963, 2.949, 23041966080),
        (23420.546, 4.618, .008, 23269101568),
        (23422.629, 4.286, 1.650, 23080796160),
        (23424.690, 3.898, 3.234, 22253932544),
    ]
    state = SimpleNamespace(now=23402.303, sample=None)
    admission = Admission(SimpleNamespace(sample=lambda: state.sample), lambda: state.now)
    for kind, started in [('publish', 23402.303), ('ui-screen', 23406.385),
                          ('unit', 23406.424)]:
        state.now = started
        admission.started(kind)
    active = ['publish', 'ui-screen', 'unit']
    for index, (now, busy, io, memory) in enumerate(observations):
        state.now = now
        state.sample = Sample(20, busy, 32733335552, memory, .521, 0, io, False)
        allowed = admission.allows('ui-request', active)
        assert allowed is (index == 4)
    assert admission.allows('ui-request', active)
    assert not admission.allows('ui-preview', active)
    assert not admission.allows('artifacts', active)


def test_long_job_overlaps_sequential_short_jobs_and_callbacks_stay_on_coordinator():
    release = threading.Event()
    main = threading.get_ident()
    calls, output, finished = [], [], []
    active, maximum = set(), 0

    class Execution:
        def __init__(self, job):
            nonlocal maximum
            assert threading.get_ident() == main
            self.name = job.kind
            calls.append(self.name)
            active.add(self.name)
            maximum = max(maximum, len(active))

        def output(self, data):
            assert threading.get_ident() == main
            output.append((self.name, data))

        def finish(self, status):
            assert threading.get_ident() == main and status == 0
            assert (self.name, b'final') in output
            active.remove(self.name)
            finished.append(self.name)
            if self.name == 'short2':
                assert 'long' in active
                release.set()

        def close(self):
            pass

    def command(argv, emit):
        if argv[0] == 'long':
            assert release.wait(5)
        emit(b'final')
        return 0

    jobs = [Job('short1', None, ['short1'], estimate=2),
            Job('long', None, ['long'], estimate=100),
            Job('short2', None, ['short2'], estimate=1)]
    run_jobs(jobs, control=Control(), begin=Execution, run_command=command, admission=Capacity())
    assert calls == ['long', 'short1', 'short2']
    assert finished == ['short1', 'short2', 'long'] and maximum == 2


def test_serial_admission_preserves_complete_scope():
    finished = []
    jobs = [Job(str(i), None, [str(i)], estimate=i) for i in range(4)]
    def begin(job):
        return SimpleNamespace(output=lambda _: None, finish=lambda _: finished.append(job.kind), close=lambda: None)
    run_jobs(jobs, control=Control(), begin=begin, run_command=lambda *_: 0, admission=Capacity(1))
    assert finished == ['3', '2', '1', '0']


def test_four_workers_overlap_and_fifth_waits_even_if_admission_allows_more():
    entered = threading.Barrier(4)
    release = threading.Event()
    started, finished, reasons = [], [], []

    def begin(job):
        if job.kind == '4':
            assert finished
        started.append(job.kind)
        return SimpleNamespace(output=lambda _: None,
            finish=lambda _: finished.append(job.kind), close=lambda: None)

    def command(argv, emit):
        if argv[0] != '4':
            entered.wait(timeout=5)
            assert release.wait(5)
        return 0

    def waiting(job, reason):
        reasons.append((job.kind, reason))
        if job.kind == '4':
            release.set()

    maximum = run_jobs([Job(str(i), None, [str(i)]) for i in range(5)],
        control=Control(), begin=begin, run_command=command, admission=Capacity(10),
        waiting=waiting)
    assert maximum == 4
    assert started == ['0', '1', '2', '3', '4']
    assert set(finished) == set(started)
    assert ('4', '4 host categories already running') in reasons


def test_quiet_workers_refresh_both_branches_on_coordinator():
    release = threading.Event()
    entered = threading.Barrier(2)
    coordinator = threading.get_ident()
    ticks = []
    def command(argv, emit):
        entered.wait(timeout=5)
        assert release.wait(5)
        return 0
    def tick():
        assert threading.get_ident() == coordinator
        ticks.append(True)
        release.set()
    run_jobs([Job(str(i), None, [str(i)]) for i in range(2)], control=Control(),
             begin=lambda _: SimpleNamespace(output=lambda _: None, finish=lambda _: None, close=lambda: None),
             run_command=command, admission=Capacity(), tick=tick)
    assert ticks


@pytest.mark.parametrize('slots', [2, 3, 4])
def test_report_failure_drains_backpressure_and_joins_all_workers(slots):
    control = Control()
    cleaned = set()
    entered = threading.Barrier(slots)

    def output(_):
        raise OSError('evidence unavailable')

    def command(argv, emit):
        entered.wait(timeout=5)
        for _ in range(30):
            emit(b'output')
        assert control.stopped.wait(5)
        cleaned.add(argv[0])
        return 130

    jobs = [Job(str(i), None, [str(i)]) for i in range(slots + 1)]
    with pytest.raises(OSError, match='evidence unavailable'):
        run_jobs(jobs, control=control,
                 begin=lambda _: SimpleNamespace(output=output, finish=lambda _: None, close=lambda: None),
                 run_command=command, admission=Capacity(slots))
    assert cleaned == {str(i) for i in range(slots)}


def test_cancellation_prevents_pending_jobs_and_waits_for_both_workers():
    control = Control()
    entered = threading.Barrier(2)
    cleaned, finished = set(), []
    def command(argv, emit):
        entered.wait(timeout=5)
        control.stop()
        emit(b'cleanup')
        cleaned.add(argv[0])
        return 130
    jobs = [Job(str(i), None, [str(i)]) for i in range(4)]
    run_jobs(jobs, control=control,
             begin=lambda job: SimpleNamespace(output=lambda _: None,
                 finish=lambda status: finished.append((job.kind, status)), close=lambda: None),
             run_command=command, admission=Capacity())
    assert cleaned == {'0', '1'} and sorted(finished) == [('0', 130), ('1', 130)]


def test_dependencies_wait_for_coordinator_validation_and_preserve_other_slot():
    release = threading.Event()
    started, completed = [], []
    coordinator = threading.get_ident()

    def compare_command():
        assert threading.get_ident() == coordinator
        assert completed == ['publish', 'a', 'b']
        return ['compare', 'artifact-a', 'artifact-b']

    def command(argv, emit):
        started.append(argv[0])
        if argv[0] == 'companion':
            assert release.wait(5)
        emit(b'final output')
        return 0

    def complete(job, result):
        assert threading.get_ident() == coordinator
        if job.key:
            completed.append(job.key)
        if job.key == 'compare':
            release.set()

    jobs = [Job('build', None, compare_command, key='compare', requires=('b',)),
            Job('build', None, ['b'], key='b', requires=('a',)),
            Job('build', None, ['a'], key='a', requires=('publish',)),
            Job('publish', None, ['publish'], key='publish'),
            Job('companion', None, ['companion'], estimate=100)]
    maximum = run_jobs(jobs, control=Control(),
        begin=lambda _: SimpleNamespace(output=lambda _: None, finish=lambda _: None, close=lambda: None),
        run_command=command, complete=complete, admission=Capacity(10))
    assert maximum == 2
    assert started == ['companion', 'publish', 'a', 'b', 'compare']
    assert completed == ['publish', 'a', 'b', 'compare']


@pytest.mark.parametrize('failed', ['publish', 'a', 'b', 'compare'])
def test_failed_dependency_blocks_only_its_descendants(failed):
    calls, blocked = [], []
    keys = ['publish', 'a', 'b', 'compare']
    jobs = [Job(key, None, [key], key=key, requires=(keys[index - 1],) if index else ())
            for index, key in enumerate(keys)]
    jobs.append(Job('independent', None, ['independent']))

    def command(argv, emit):
        calls.append(argv[0])
        return int(argv[0] == failed)

    run_jobs(jobs, control=Control(), admission=Capacity(),
        begin=lambda _: SimpleNamespace(output=lambda _: None, finish=lambda _: None, close=lambda: None),
        run_command=command, blocked=lambda job, _: blocked.append(job.key))
    assert set(calls) == {*keys[:keys.index(failed) + 1], 'independent'}
    assert set(blocked) == set(keys[keys.index(failed) + 1:])


@pytest.mark.parametrize('jobs', [
    [Job('a', None, [], key='same'), Job('b', None, [], key='same')],
    [Job('a', None, [], requires=('missing',))],
    [Job('a', None, [], key='a', requires=('a',))],
    [Job('a', None, [], key='a', requires=('b',)), Job('b', None, [], key='b', requires=('a',))],
    [Job('a', None, [], estimate=float('nan'))],
])
def test_invalid_plan_refuses_before_any_launch(jobs):
    with pytest.raises(ValueError):
        run_jobs(jobs, control=Control(), begin=lambda _: pytest.fail('unexpected launch'),
                 run_command=lambda *_: pytest.fail('unexpected command'))


def test_prerequisites_inherit_downstream_duration_priority():
    first = Job('first', None, [], key='first', estimate=1)
    later = Job('later', None, [], key='later', requires=('first',), estimate=100)
    unrelated = Job('other', None, [], estimate=50)
    assert ordered_jobs([unrelated, later, first]) == [first, later, unrelated]


@pytest.mark.parametrize('failure', ['cancel', 'validation'])
def test_completion_cancellation_or_invalid_artifact_never_resolves_dependent_command(failure):
    control = Control()
    closed = []

    def complete(job, result):
        if failure == 'cancel':
            control.stop()
        else:
            raise ValueError('invalid artifact')

    jobs = [Job('build', None, ['build'], key='build'),
            Job('compare', None, lambda: pytest.fail('dependent command resolved'), requires=('build',))]
    def run():
        return run_jobs(jobs, control=control, complete=complete, admission=Capacity(),
            begin=lambda job: SimpleNamespace(output=lambda _: None, finish=lambda _: None,
                                              close=lambda: closed.append(job.kind)),
            run_command=lambda *_: 0)
    if failure == 'validation':
        with pytest.raises(ValueError, match='invalid artifact'):
            run()
    else:
        run()
    assert closed == ['build']
