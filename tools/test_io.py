"""Process-local pacing for durable test journals, without skipping syncs."""

from contextlib import contextmanager
from contextvars import ContextVar
import time

_pacing = ContextVar('test_journal_pacing', default=None)


@contextmanager
def low_io(*, minimum_interval=0.1):
    """Allow workers to pace by sync latency, and coordinators to add a floor."""
    current = _pacing.get()
    if current is not None and current[1] >= minimum_interval:
        yield
        return
    # Freeze this scope's clock functions. Tests can replace another module's
    # shared time.monotonic without moving an existing pacing deadline between
    # the real clock and a synthetic clock.
    token = _pacing.set([0.0, minimum_interval, time.monotonic, time.sleep])
    try:
        yield
    finally:
        _pacing.reset(token)


def sync(fd, operation):
    """Perform every requested sync, spacing durable flushes.

    Leave nine times the previous sync's duration idle, with the caller's
    minimum interval. Never accumulate idle credit or swallow an I/O failure.
    The caller supplies its OS operation so existing fault injection stays local.
    """
    pacing = _pacing.get()
    if pacing is None:
        return operation(fd)
    deadline, minimum_interval, clock, sleep = pacing
    delay = deadline - clock()
    if delay > 0:
        sleep(delay)
    started = clock()
    try:
        return operation(fd)
    finally:
        finished = clock()
        pacing[0] = finished + max(minimum_interval, 9 * (finished - started))
