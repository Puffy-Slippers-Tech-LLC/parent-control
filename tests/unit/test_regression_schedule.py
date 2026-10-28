"""Scheduler execution integrity and cleanup behavior."""

from types import SimpleNamespace
import threading

import pytest

from regression_process import Control
from regression_schedule import Job, run_jobs


class Capacity:
    reason = 'two categories running'

    def __init__(self, slots=2):
        self.slots = slots

    def allows(self, candidate, active):
        return len(active) < self.slots


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
