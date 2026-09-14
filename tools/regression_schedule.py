"""Bounded owned command workers; output and result handling stay on the caller.

The bounded queue applies backpressure. On any coordinator failure we latch
cancellation, drain the queue, and join all children through their normal
cleanup paths before propagating the original exception.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import math
import queue
from typing import Callable

from regression_resources import Admission, HOST_WORKERS


@dataclass
class Job:
    kind: str
    item: object
    command: list | Callable[[], list]
    events: bool = False
    estimate: float = 0
    key: str = ''
    requires: tuple[str, ...] = ()


def ordered_jobs(jobs):
    """Validate the complete dependency graph before starting any child."""
    named = {job.key: job for job in jobs if job.key}
    if len(named) != sum(bool(job.key) for job in jobs) or len({id(job) for job in jobs}) != len(jobs):
        raise ValueError('duplicate scheduler job')
    for job in jobs:
        if not math.isfinite(job.estimate) or job.estimate < 0:
            raise ValueError('invalid job duration estimate')
        if any(key not in named for key in job.requires):
            raise ValueError('unknown scheduler prerequisite')
    scores, visiting = {}, set()

    def score(job):
        identity = id(job)
        if identity in visiting:
            raise ValueError('cyclic scheduler prerequisites')
        if identity not in scores:
            visiting.add(identity)
            followers = [other for other in jobs if job.key and job.key in other.requires]
            scores[identity] = job.estimate + max((score(other) for other in followers), default=0)
            visiting.remove(identity)
        return scores[identity]

    # Stable sorting preserves declared order for equal critical-path estimates.
    return sorted(jobs, key=lambda job: -score(job))


def run_jobs(jobs, *, control, begin, run_command, admission=None, waiting=lambda *_: None,
             tick=lambda: None, complete=lambda *_: None, blocked=lambda *_: None):
    admission = admission or Admission()
    pending = ordered_jobs(jobs)
    outcomes = {}
    active = {}
    messages = queue.Queue(maxsize=8)
    reasons = {}
    failure = None
    maximum = 0

    def wait_for(job, reason):
        if reasons.get(id(job)) != reason:
            waiting(job, reason)
            reasons[id(job)] = reason

    def worker(execution, command):
        def output(data):
            messages.put((execution, data))
        return run_command(command, output)

    with ThreadPoolExecutor(max_workers=HOST_WORKERS, thread_name_prefix='onpc-category') as workers:
        try:
            while pending or active:
                if hasattr(admission, 'update'):
                    admission.update()
                if control.stopped.is_set():
                    pending.clear()
                for job in list(pending):
                    if control.stopped.is_set():
                        break
                    if any(outcomes.get(key) is False for key in job.requires):
                        blocked(job, 'required host job failed')
                        if job.key:
                            outcomes[job.key] = False
                        pending.remove(job)
                        continue
                    if not all(outcomes.get(key) is True for key in job.requires):
                        wait_for(job, 'waiting for required host jobs')
                        continue
                    if len(active) >= HOST_WORKERS:
                        wait_for(job, f'{HOST_WORKERS} host categories already running')
                        continue
                    if not admission.allows(job.kind, [entry[0].kind for entry in active.values()]):
                        wait_for(job, admission.reason)
                        continue
                    command = job.command() if callable(job.command) else job.command
                    if control.stopped.is_set():
                        break
                    execution = begin(job)
                    if control.stopped.is_set():
                        execution.close()
                        break
                    try:
                        future = workers.submit(worker, execution, command)
                    except BaseException:
                        execution.close()
                        raise
                    active[future] = (job, execution)
                    if hasattr(admission, 'started'):
                        admission.started(job.kind)
                    maximum = max(maximum, len(active))
                    pending.remove(job)
                    reasons.pop(id(job), None)
                try:
                    execution, data = messages.get(timeout=.1)
                    execution.output(data)
                except queue.Empty:
                    pass
                # Worker completion means all its output has been enqueued.
                # Drain before finishing so partial/final events cannot be lost.
                while True:
                    try:
                        execution, data = messages.get_nowait()
                    except queue.Empty:
                        break
                    execution.output(data)
                for future in list(active):
                    if future.done():
                        while True:
                            try:
                                owner, data = messages.get_nowait()
                            except queue.Empty:
                                break
                            owner.output(data)
                        job, execution = active.pop(future)
                        try:
                            status = future.result()
                            result = execution.finish(status)
                            if not control.stopped.is_set():
                                complete(job, result)
                                if job.key:
                                    outcomes[job.key] = status == 0
                        finally:
                            execution.close()
                tick()
        except BaseException as error:
            failure = error
            control.stop()
        finally:
            # Continue draining even when persistence itself failed. Otherwise
            # a child could block forever behind a full output pipe during cleanup.
            while active:
                try:
                    execution, data = messages.get(timeout=.1)
                    if failure is None:
                        execution.output(data)
                except queue.Empty:
                    pass
                except BaseException as error:
                    failure = failure or error
                    control.stop()
                for future in list(active):
                    if future.done() and messages.empty():
                        _, execution = active.pop(future)
                        try:
                            status = future.result()
                            if failure is None:
                                execution.finish(status)
                        except BaseException as error:
                            failure = failure or error
                            control.stop()
                        finally:
                            execution.close()
    if failure is not None:
        raise failure
    return maximum
