"""TIME04: normal app use under one measured natural-expiry deadline."""
from dataclasses import asdict
import math
import time

from accessible_ui import countdown_seconds
from countdown import CountdownSample
from private_artifacts import require
from real_interval import interval_action
from ui_observations import AppActivityObservation, compare_app_activity
import watch_activity


# Predeclared engineering test bounds, not changes to product timing promises.
# One-second scheduling retains TIME04's existing sampling precision. A sample
# completing more than 15 seconds after the previous completion is missed and
# fails, including transport outages; no new deadline is granted on recovery.
SAMPLE_INTERVAL_SECONDS = 1
MAX_SAMPLE_GAP_SECONDS = 15
# Match TIME04's existing upper-end-plus-15 observation allowance. Retries of
# read-only lock discovery and recovery share their original trigger clock.
LOCK_OBSERVATION_SECONDS = 15
LOCK_RETRY_SECONDS = 15
# Input challenges and peer isolation are functional verification, not expiry
# latency measurements. Allow slow navigation/transport without adding sleeps.
# Each complete sequence gets one original deadline, never a budget per retry.
LOCK_VERIFICATION_SECONDS = 180
# Recovery includes the complete guarded GDM return, two recipient proofs,
# authentication, original-window input and independent work readback. Those
# transport stages share this finite original recovery clock; this is not a
# product lock-effect allowance.
RECOVERY_SECONDS = 300
# Foreground-revocation engineering consumers declare this bound before input.
# It is deliberately explicit so a mismatch requires a behavior decision.
FOREGROUND_REVOCATION_RESPONSE_SECONDS = 15
# Leave both TIME04's ten-second quiet margin and one whole bounded read before
# expiry, since the engineering transport has no panel seconds to recheck.
ACTIVITY_CUTOFF_SECONDS = 10 + MAX_SAMPLE_GAP_SECONDS


def engineering_deadline(triggered_at, budget):
    """Anchor an observation/outage budget once to its original trigger."""
    require(type(triggered_at) in (int, float) and math.isfinite(triggered_at)
            and budget in (LOCK_OBSERVATION_SECONDS, LOCK_RETRY_SECONDS,
                           LOCK_VERIFICATION_SECONDS, RECOVERY_SECONDS,
                           FOREGROUND_REVOCATION_RESPONSE_SECONDS),
            'natural-expiry:engineering-budget')
    return triggered_at + budget


def _engineering_read(ui, guard, operation, *, deadline, boot_sha256, previous_completed):
    """A late completed read fails even when it happens to find a lock."""
    guard()
    started = time.monotonic()
    require(started < deadline and started - previous_completed <= MAX_SAMPLE_GAP_SECONDS,
            'natural-expiry:engineering-missed-sample')
    value = ui.observe('child-natural-expiry-engineering-' + operation)['natural_expiry']
    completed = time.monotonic()
    guard()
    require(ui.boot_proof == boot_sha256, 'natural-expiry:wrong-boot')
    require(completed < deadline, 'natural-expiry:engineering-deadline')
    require(completed - previous_completed <= MAX_SAMPLE_GAP_SECONDS,
            'natural-expiry:engineering-missed-sample')
    return value, completed


def await_engineering_expiry(ui, guard, activity, *, expiry_at, boot_sha256):
    """Use original work until a panel-independent lock, on the original clock.

    The caller owns fixture readiness, the real entitlement, transport and VM
    lease. ``expiry_at`` is the already established absolute controller monotonic
    expiry, never the time this observer or a retry begins. Only native lock
    input and its independent result can establish protection afterward.
    """
    require(type(activity) is AppActivityObservation, 'natural-expiry:engineering-entry')
    deadline = engineering_deadline(expiry_at, LOCK_OBSERVATION_SECONDS)
    previous_completed = time.monotonic()
    actions = 0
    session = None
    operation = 'observe'
    with watch_activity.operation('Observing natural expiry independently of the child panel'):
        while True:
            value, completed = _engineering_read(ui, guard, operation, deadline=deadline,
                boot_sha256=boot_sha256, previous_completed=previous_completed)
            session = session or value['session_sha256']
            require(value['session_sha256'] == session, 'natural-expiry:session-changed')
            actions += int(value['acted'])
            if value['state'] == 'locked':
                require(completed >= expiry_at, 'natural-expiry:premature-lock')
                return {'lock': value['lock'], 'session_sha256': session,
                        'expiry_at': expiry_at, 'observed_monotonic': completed,
                        'activity_actions': actions}
            compare_app_activity(AppActivityObservation.from_value(value['activity']), activity)
            previous_completed = completed
            # Stop mutations before zero using the original controller clock;
            # panel values and observer retries cannot extend usable input.
            operation = ('activity' if completed + SAMPLE_INTERVAL_SECONDS
                         < expiry_at - ACTIVITY_CUTOFF_SECONDS else 'observe')
            guard()
            require(time.monotonic() + SAMPLE_INTERVAL_SECONDS < deadline,
                    'natural-expiry:engineering-deadline')
            time.sleep(SAMPLE_INTERVAL_SECONDS)


def challenge_engineering_lock(ui, guard, send_shift, *, deadline, boot_sha256):
    """Fresh lock proof, one harmless native input and independent same-lock read.

    ``deadline`` belongs to the original lock/expiry history. The caller's input
    callback guards the owned VM immediately before and after one Shift; an
    exception or uncertain delivery is never replayed.
    """
    require(callable(send_shift), 'natural-expiry:engineering-input')
    ready, completed = _engineering_read(ui, guard, 'lock-ready', deadline=deadline,
        boot_sha256=boot_sha256, previous_completed=time.monotonic())
    require(ready['state'] == 'locked', 'natural-expiry:engineering-unlocked')
    guard()
    require(time.monotonic() < deadline, 'natural-expiry:engineering-deadline')
    send_shift()
    guard()
    result, completed = _engineering_read(ui, guard, 'lock-result', deadline=deadline,
        boot_sha256=boot_sha256, previous_completed=completed)
    require(result['state'] == 'locked' and result['session_sha256'] == ready['session_sha256']
            and result['lock']['surface_id'] == ready['lock']['surface_id'],
            'natural-expiry:engineering-lock-changed')
    return {'lock': result['lock'], 'session_sha256': result['session_sha256'],
            'observed_monotonic': completed, 'harmless_input': 'Shift'}


def await_natural_expiry(journey, guard, previous, activity):
    """Ready the public observer before activity; a deadline never proves Lock."""
    require(type(previous) is CountdownSample and type(activity) is AppActivityObservation,
            'natural-expiry:entry')
    low, high = countdown_seconds(previous.countdown.text)
    require(0 < low <= high <= 240, 'natural-expiry:positive-time')
    deadline = previous.read_bounds[0] / 1e9 + high + 15
    actions = 0
    initial_session = None
    operation = 'child-natural-expiry-observe'
    with watch_activity.operation('Using the child app until the independently observed natural lock'):
        while True:
            attempt_deadline = guard()
            require(journey.ui.boot_proof == previous.boot_sha256, 'natural-expiry:wrong-boot')
            require(time.monotonic() < min(deadline, attempt_deadline), 'natural-expiry:deadline')
            before = time.monotonic_ns()
            value = journey.ui.observe(operation)['natural_expiry']
            after = time.monotonic_ns()
            attempt_deadline = guard()
            require(journey.ui.boot_proof == previous.boot_sha256, 'natural-expiry:wrong-boot')
            require(after / 1e9 < min(deadline, attempt_deadline), 'natural-expiry:deadline')
            initial_session = initial_session or value['session_sha256']
            require(value['session_sha256'] == initial_session, 'natural-expiry:session-changed')
            actions += int(value['acted'])
            if value['state'] == 'locked':
                elapsed = [(before - previous.read_bounds[1]) / 1e9,
                           (after - previous.read_bounds[0]) / 1e9]
                require(actions > 0 and elapsed[1] >= low - 2,
                        'natural-expiry:premature-lock')
                return {'initial_countdown': asdict(previous), 'lock': value['lock'],
                        'elapsed_interval_seconds': elapsed, 'activity_actions': actions}
            compare_app_activity(AppActivityObservation.from_value(value['activity']), activity)
            require(0 <= value['seconds'] <= high + 2, 'natural-expiry:remaining-time')
            # Retain natural observation near zero; fresh session guards also
            # recheck immediately before each normal app action.
            operation = ('child-natural-expiry-activity' if value['seconds'] > 10
                         else 'child-natural-expiry-observe')
            require(time.monotonic() + 1 < min(deadline, attempt_deadline),
                    'natural-expiry:deadline')
            interval_action(1)(journey, guard)
