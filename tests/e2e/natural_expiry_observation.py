"""TIME04: normal app use under one measured natural-expiry deadline."""
from dataclasses import asdict
import time

from accessible_ui import countdown_seconds
from countdown import CountdownSample
from private_artifacts import require
from real_interval import interval_action
from ui_observations import AppActivityObservation, compare_app_activity
import watch_activity


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
