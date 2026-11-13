"""Shared controller lifetime and cooperative cancellation of owned work."""

from contextlib import contextmanager
import threading
import time

import launcher_reload


current_run = None


@contextmanager
def watching(run=None):
    """Bind reload and cancellation to this exact controller publication."""
    global current_run
    previous = current_run
    try:
        with launcher_reload.watching(run) as request:
            current_run = request.run if request is not None else None
            yield request
    finally:
        current_run = previous


class CancellationEvent(threading.Event):
    """Keep operation-local stops separate from durable launcher cancellation."""

    def __init__(self, run=None):
        super().__init__()
        self.run = current_run if run is None else run

    def is_set(self):
        return super().is_set() or (self.run is not None and (self.run / 'cancel').exists())

    def wait(self, timeout=None):
        if self.run is None:
            return super().wait(timeout)
        deadline = None if timeout is None else time.monotonic() + timeout
        while not self.is_set():
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                return False
            super().wait(0.1 if remaining is None else min(0.1, remaining))
        return True
