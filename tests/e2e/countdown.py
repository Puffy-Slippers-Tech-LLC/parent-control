"""Immutable TIME01 results and explicit elapsed-time/rounding comparisons."""

from dataclasses import asdict, dataclass
import re
import time

from accessible_ui import countdown_seconds, validate_countdown
from private_artifacts import require
from real_interval import interval_action


@dataclass(frozen=True)
class CountdownObservation:
    present: bool
    text: str | None
    observed_monotonic_ns: int
    stable_ms: int

    @classmethod
    def from_value(cls, value, *, present):
        value = validate_countdown(value, present)
        return cls(value['present'], value['text'], value['observed_monotonic_ns'],
                   value['stable_ms'])


def check_countdown_balance(countdown, *, seconds, precision_seconds,
                            observed_monotonic_ns, max_elapsed_seconds=180,
                            sampling_seconds=30):
    """Compare public balances, allowing only declared rounding and real elapsed time.

    Time spent outside the child's active session may consume none of its daily
    allowance. It cannot consume more than the real interval between these reads.
    Horizontal minutes are floored; final seconds are exact. This is not a tick test.
    Callers may declare up to thirty seconds for estimate refresh and read latency.
    """
    require(isinstance(countdown, CountdownObservation) and countdown.present,
            'countdown:presence-required')
    require(type(seconds) is int and 0 < seconds < 86400
            and type(precision_seconds) is int and 1 <= precision_seconds <= 60
            and type(observed_monotonic_ns) is int and observed_monotonic_ns > 0
            and type(max_elapsed_seconds) is int and 0 < max_elapsed_seconds <= 300
            and type(sampling_seconds) is int and 0 <= sampling_seconds <= 30,
            'countdown:balance-binding')
    elapsed = (countdown.observed_monotonic_ns - observed_monotonic_ns) / 1_000_000_000
    require(0 < elapsed <= max_elapsed_seconds, 'countdown:elapsed-bound')
    low, high = countdown_seconds(countdown.text)
    require(low <= seconds + precision_seconds - 1 + sampling_seconds
            and high >= seconds - precision_seconds + 1 - elapsed - sampling_seconds,
            'countdown:balance-mismatch')
    return {'elapsed_seconds': elapsed, 'rounding_seconds': precision_seconds,
            'sampling_seconds': sampling_seconds, 'display_interval_seconds': [low, high]}


@dataclass(frozen=True)
class CountdownSample:
    """One immutable public endpoint, bracketed on the controller's clock."""
    countdown: CountdownObservation
    read_bounds: tuple
    boot_sha256: str

    def __post_init__(self):
        require(type(self.countdown) is CountdownObservation and self.countdown.present
                and type(self.read_bounds) is tuple and len(self.read_bounds) == 2
                and all(type(item) is int and item > 0 for item in self.read_bounds)
                and self.read_bounds[0] <= self.read_bounds[1]
                and type(self.boot_sha256) is str
                and re.fullmatch(r'[0-9a-f]{64}', self.boot_sha256), 'countdown:sample-binding')

    @classmethod
    def from_ui(cls, value, *, boot_sha256):
        countdown = CountdownObservation.from_value(value.get('countdown'), present=True)
        bounds = value.get('countdown_read_bounds')
        require(type(bounds) in (list, tuple) and len(bounds) == 2
                and all(type(item) is int and item > 0 for item in bounds)
                and bounds[0] <= bounds[1]
                and type(boot_sha256) is str and re.fullmatch(r'[0-9a-f]{64}', boot_sha256),
                'countdown:sample-binding')
        return cls(countdown, tuple(bounds), boot_sha256)

    @property
    def precision_seconds(self):
        return 60 if ':' in self.countdown.text else 1

    def elapsed_since(self, previous, *, max_elapsed_seconds):
        require(type(previous) is CountdownSample, 'countdown:sample-required')
        require(self.boot_sha256 == previous.boot_sha256, 'countdown:wrong-owner')
        require(self.countdown.observed_monotonic_ns > previous.countdown.observed_monotonic_ns
                and self.read_bounds[0] > previous.read_bounds[1], 'countdown:stale-sample')
        low = (self.read_bounds[0] - previous.read_bounds[1]) / 1_000_000_000
        high = (self.read_bounds[1] - previous.read_bounds[0]) / 1_000_000_000
        require(0 < low <= high <= max_elapsed_seconds, 'countdown:progress-bound')
        return low, high


def _progress_binding(precision_seconds, previous_precision_seconds, tolerance_seconds,
                      max_elapsed_seconds):
    previous_precision_seconds = (precision_seconds if previous_precision_seconds is None
                                  else previous_precision_seconds)
    require(type(precision_seconds) is int and precision_seconds in (1, 60)
            and type(previous_precision_seconds) is int
            and (previous_precision_seconds, precision_seconds) in ((60, 60), (60, 1), (1, 1))
            and type(tolerance_seconds) is int and 0 <= tolerance_seconds <= 2
            and type(max_elapsed_seconds) is int and 0 < max_elapsed_seconds <= 300,
            'countdown:progress-binding')
    return previous_precision_seconds


def _require_precision(sample, precision_seconds):
    require(sample.precision_seconds == precision_seconds,
            'countdown:minute-required' if precision_seconds == 60 else 'countdown:seconds-required')


def check_countdown_progress(current, previous, *, precision_seconds, tolerance_seconds,
                             max_elapsed_seconds, previous_precision_seconds=None):
    """Require progress at the declared precision, including a minute→seconds edge.

    Each display supplies an interval. Their possible decrease must intersect
    the independently bracketed elapsed interval, including only the caller's
    declared estimate tolerance. Skipped ticks are permitted; unchanged values
    and increases never establish progress.
    """
    require(type(current) is CountdownSample and type(previous) is CountdownSample,
            'countdown:sample-required')
    previous_precision_seconds = _progress_binding(precision_seconds, previous_precision_seconds,
                                                   tolerance_seconds, max_elapsed_seconds)
    elapsed_low, elapsed_high = current.elapsed_since(previous,
        max_elapsed_seconds=max_elapsed_seconds)
    _require_precision(previous, previous_precision_seconds)
    _require_precision(current, precision_seconds)
    before = countdown_seconds(previous.countdown.text)
    after = countdown_seconds(current.countdown.text)
    require(after[0] < before[0], 'countdown:no-progress')
    decrease = [before[0] - after[1], before[1] - after[0]]
    require(decrease[0] <= elapsed_high + tolerance_seconds
            and decrease[1] >= elapsed_low - tolerance_seconds,
            'countdown:progress-mismatch')
    return {'elapsed_interval_seconds': [elapsed_low, elapsed_high],
            'decrease_interval_seconds': decrease,
            'precision_seconds': precision_seconds,
            'previous_precision_seconds': previous_precision_seconds,
            'tolerance_seconds': tolerance_seconds}


def await_countdown_progress(journey, guard, previous, *, precision_seconds,
                            tolerance_seconds, max_elapsed_seconds,
                            previous_precision_seconds=None, initial_sample=None):
    """Read-only reacquisition under one unchanged deadline and attempt guard."""
    require(type(previous) is CountdownSample, 'countdown:sample-required')
    # Validate caller precision/tolerance before any wait or public read.
    previous_precision_seconds = _progress_binding(precision_seconds, previous_precision_seconds,
                                                   tolerance_seconds, max_elapsed_seconds)
    _require_precision(previous, previous_precision_seconds)
    require(initial_sample is None or type(initial_sample) is CountdownSample,
            'countdown:sample-required')
    deadline = previous.read_bounds[0] / 1_000_000_000 + max_elapsed_seconds
    guard()
    require(journey.ui.boot_proof == previous.boot_sha256, 'countdown:wrong-owner')
    last = previous
    def consider(current):
        guard()
        require(journey.ui.boot_proof == previous.boot_sha256, 'countdown:wrong-owner')
        current.elapsed_since(last, max_elapsed_seconds=max_elapsed_seconds)
        require(time.monotonic() < deadline
                and current.read_bounds[1] / 1_000_000_000 < deadline,
                'countdown:progress-bound')
        require(countdown_seconds(current.countdown.text)[0]
                <= countdown_seconds(last.countdown.text)[0], 'countdown:no-progress')
        if current.precision_seconds != precision_seconds:
            require(previous_precision_seconds == 60 and precision_seconds == 1
                    and current.precision_seconds == 60, 'countdown:seconds-required')
            return None
        if current.countdown.text != previous.countdown.text:
            comparison = check_countdown_progress(current, previous,
                precision_seconds=precision_seconds, tolerance_seconds=tolerance_seconds,
                max_elapsed_seconds=max_elapsed_seconds,
                previous_precision_seconds=previous_precision_seconds)
            return current, {'before': asdict(previous), 'after': asdict(current),
                             'comparison': comparison}
        return None

    if initial_sample is not None:
        result = consider(initial_sample)
        if result is not None:
            return result
        last = initial_sample
    while True:
        require(time.monotonic() + 1 < deadline, 'countdown:progress-bound')
        interval_action(1)(journey, guard)
        guard()
        require(time.monotonic() < deadline, 'countdown:progress-bound')
        value = journey.ui.observe('child-countdown-present')
        guard()
        current = CountdownSample.from_ui(value, boot_sha256=journey.ui.boot_proof)
        result = consider(current)
        if result is not None:
            return result
        last = current
