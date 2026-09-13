"""Two owned command workers; all output and result handling stays on the caller.

The bounded queue applies backpressure. On any coordinator failure we latch
cancellation, drain the queue, and join both children through their normal
cleanup paths before propagating the original exception.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import queue

from regression_resources import Admission


@dataclass
class Job:
    kind: str
    item: object
    command: list
    events: bool = False
    estimate: float = 0


def run_jobs(jobs, *, control, begin, run_command, admission=None, waiting=lambda *_: None,
             tick=lambda: None):
    admission = admission or Admission()
    pending = sorted(jobs, key=lambda job: -job.estimate)
    active = {}
    messages = queue.Queue(maxsize=8)
    last_reason = None
    failure = None
    maximum = 0

    def worker(execution, command):
        def output(data):
            messages.put((execution, data))
        return run_command(command, output)

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix='onpc-category') as workers:
        try:
            while pending or active:
                if hasattr(admission, 'update'):
                    admission.update()
                if control.stopped.is_set():
                    pending.clear()
                for job in list(pending):
                    if control.stopped.is_set():
                        break
                    if not admission.allows(job.kind, [entry[0].kind for entry in active.values()]):
                        reason = admission.reason
                        if reason != last_reason:
                            waiting(reason)
                            last_reason = reason
                        continue
                    execution = begin(job)
                    try:
                        future = workers.submit(worker, execution, job.command)
                    except BaseException:
                        execution.close()
                        raise
                    active[future] = (job, execution)
                    maximum = max(maximum, len(active))
                    pending.remove(job)
                    last_reason = None
                    if len(active) == 2:
                        break
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
                        _, execution = active[future]
                        execution.finish(future.result())
                        del active[future]
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
