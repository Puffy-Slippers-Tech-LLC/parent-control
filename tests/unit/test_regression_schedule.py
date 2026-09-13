"""Two-worker ordering, serialized evidence, and safe scheduler failures."""

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


def test_report_failure_drains_backpressure_and_joins_all_workers():
    control = Control()
    cleaned = set()
    entered = threading.Barrier(2)

    def output(_):
        raise OSError('evidence unavailable')

    def command(argv, emit):
        entered.wait(timeout=5)
        for _ in range(30):
            emit(b'output')
        assert control.stopped.wait(5)
        cleaned.add(argv[0])
        return 130

    jobs = [Job(str(i), None, [str(i)]) for i in range(3)]
    with pytest.raises(OSError, match='evidence unavailable'):
        run_jobs(jobs, control=control,
                 begin=lambda _: SimpleNamespace(output=output, finish=lambda _: None, close=lambda: None),
                 run_command=command, admission=Capacity())
    assert cleaned == {'0', '1'}


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
