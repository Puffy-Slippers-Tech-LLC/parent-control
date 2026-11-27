"""Observe grant transitions without recording account identity.

UIDs and grant timestamps already belong to broker policy state. They remain
in this bounded in-memory lookup; no diagnostic event receives them.
"""

from collections import OrderedDict
from contextvars import ContextVar
from datetime import datetime, timedelta
from functools import wraps
import threading

from common.oh_no_parent_control_ui.diagnostic_events import get_logger

LOG = get_logger("grant")
_pending = ContextVar("saved_time_diagnostics", default=None)


def _emit_saved_time(event_id, warning, fields):
    """Send reviewed scalar fields without letting diagnostics interrupt a transfer."""
    try:
        emit = LOG.warning if warning else LOG.info
        emit(event_id, **fields)
    except Exception:
        pass


def log_saved_time(event_id, *, warning=False, **fields):
    pending = _pending.get()
    if pending is None:
        _emit_saved_time(event_id, warning, fields)
    else:
        pending.append((event_id, warning, fields))


def buffer_saved_time_logs(callback):
    """Keep synchronous log storage outside the lock/capture and pause deadlines."""
    @wraps(callback)
    def buffered(*args, **kwargs):
        pending = []
        token = _pending.set(pending)
        try:
            return callback(*args, **kwargs)
        finally:
            _pending.reset(token)
            for item in pending:
                _emit_saved_time(*item)

    return buffered


def log_pause_overrun(monotonic, deadline, stage):
    try:
        elapsed = monotonic() - deadline
        if elapsed >= 0:
            log_saved_time("grant.pause-overrun", warning=True, stage=stage,
                           overrun_ms=int(min(2147483647, elapsed * 1000)))
    except Exception:
        pass


class GrantDiagnostics:
    def __init__(self):
        self._observed = OrderedDict()
        self._lock = threading.Lock()
        self._clock = None

    def _state(self, uid):
        state = self._observed.setdefault(uid, {
            "value": None, "written": None, "uncertain": False,
        })
        self._observed.move_to_end(uid)
        while len(self._observed) > 128:
            self._observed.popitem(last=False)
        return state

    def write_started(self, uid):
        # A failed/timeout reply cannot establish that the write did not apply.
        with self._lock:
            state = self._state(uid)
            state["uncertain"] = True
            state["written"] = None

    def wrote(self, uid, value):
        """Record a successful write only after its read-back has matched."""
        with self._lock:
            state = self._state(uid)
            state["written"] = value
            state["uncertain"] = False

    def observe(self, uid, value, now, monotonic, *, is_current=None):
        issued, duration = value
        if (type(issued) is not int or type(duration) is not int
                or not 0 <= issued <= 2**64 - 1 or not 0 <= duration <= 2**32 - 1):
            LOG.warning("grant.invalid")
            return
        wall = int(now.timestamp())
        with self._lock:
            # Check under this lock so a concurrent writer cannot publish a
            # newer candidate before an outdated observation is discarded.
            if is_current is not None and not is_current():
                return
            if self._clock is not None:
                prior_wall, prior_mono = self._clock
                discrepancy = (wall - prior_wall) - (monotonic - prior_mono)
                if abs(discrepancy) > 5:
                    LOG.warning("grant.clock-divergence", direction="forward" if discrepancy > 0 else "backward",
                                seconds=min(86400, int(abs(discrepancy))))
            self._clock = (wall, monotonic)
            state = self._state(uid)
            prior = state["value"]
            written = state["written"]
            state["written"] = None
            if prior == value and written is None:
                return
            source = "unknown" if prior is None or state["uncertain"] else "external"
            if written == value:
                source = "our-app"
            elif written is not None:
                source = "unknown"
                state["uncertain"] = True
            state["value"] = value
            remaining = max(0, issued + duration - wall)
            previous = 0 if prior is None else max(0, sum(prior) - wall)
            # Compare absolute second-resolution expiry, not durations rounded
            # on opposite sides of a fractional observation second.
            next_midnight = datetime.combine(
                now.date() + timedelta(days=1), datetime.min.time(), tzinfo=now.tzinfo)
            midnight = remaining > 0 and issued + duration == int(next_midnight.timestamp())
            if source == "external" and midnight and remaining > previous:
                # AccountsService exposes the resulting state, not the UI
                # action or authentication that produced it.
                LOG.info("grant.external-rest-of-day",
                         observed_at=now.astimezone().isoformat(timespec="milliseconds"),
                         remaining=min(remaining, 2**32 - 1))
            LOG.info("grant.observed-timed", source=source,
                     observed_at=now.astimezone().isoformat(timespec="milliseconds"),
                     previous_known=prior is not None,
                     previous=min(previous, 2**32 - 1), remaining=min(remaining, 2**32 - 1),
                     ends_at_midnight=midnight)
