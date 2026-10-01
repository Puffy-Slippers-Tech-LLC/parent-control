"""Immutable TIME01 results and explicit elapsed-time/rounding comparisons."""

from dataclasses import dataclass

from accessible_ui import countdown_seconds, validate_countdown
from private_artifacts import require


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
                            observed_monotonic_ns, max_elapsed_seconds=180):
    """Compare public balances, allowing only declared rounding and real elapsed time.

    Time spent outside the child's active session may consume none of its daily
    allowance. It cannot consume more than the real interval between these reads.
    Horizontal minutes are floored; final seconds are exact. This is not a tick test.
    """
    require(isinstance(countdown, CountdownObservation) and countdown.present,
            'countdown:presence-required')
    require(type(seconds) is int and 0 < seconds < 86400
            and type(precision_seconds) is int and 1 <= precision_seconds <= 60
            and type(observed_monotonic_ns) is int and observed_monotonic_ns > 0
            and type(max_elapsed_seconds) is int and 0 < max_elapsed_seconds <= 300,
            'countdown:balance-binding')
    elapsed = (countdown.observed_monotonic_ns - observed_monotonic_ns) / 1_000_000_000
    require(0 < elapsed <= max_elapsed_seconds, 'countdown:elapsed-bound')
    low, high = countdown_seconds(countdown.text)
    # Two seconds cover the product's estimate update and sampling boundary.
    require(low <= seconds + precision_seconds - 1 + 2
            and high >= seconds - precision_seconds + 1 - elapsed - 2,
            'countdown:balance-mismatch')
    return {'elapsed_seconds': elapsed, 'rounding_seconds': precision_seconds,
            'sampling_seconds': 2, 'display_interval_seconds': [low, high]}
