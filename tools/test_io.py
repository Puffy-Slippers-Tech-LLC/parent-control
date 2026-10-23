"""Optional low-I/O pacing for a runner coordinator's durable journals."""

from contextlib import contextmanager
from contextvars import ContextVar
import time

_pacing = ContextVar('test_journal_pacing', default=None)


@contextmanager
def low_io():
    """Keep pacing process-local; separately executed test workers are unaffected."""
    if _pacing.get() is not None:
        yield
        return
    token = _pacing.set([0.0])
    try:
        yield
    finally:
        _pacing.reset(token)


def sync(fd, operation):
    """Perform every requested sync, spacing coordinator journal flushes.

    Leave at least 100 ms between flushes and nine times the previous sync's
    duration idle. Never accumulate idle credit or swallow an I/O failure.
    The caller supplies its OS operation so existing fault injection stays local.
    """
    pacing = _pacing.get()
    if pacing is None:
        return operation(fd)
    delay = pacing[0] - time.monotonic()
    if delay > 0:
        time.sleep(delay)
    started = time.monotonic()
    try:
        return operation(fd)
    finally:
        finished = time.monotonic()
        pacing[0] = finished + max(0.1, 9 * (finished - started))
