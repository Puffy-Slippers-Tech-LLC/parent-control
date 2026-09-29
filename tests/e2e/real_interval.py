"""TIME03: bounded monotonic elapsed time, with no product-state assertion."""
import math
import time

from private_artifacts import require
import watch_activity


def wait_real_interval(duration, *, deadline, guard, progress):
    """Check ownership/deadline at most 250 ms apart; publish five checkpoints.

    The deadline is the attempt's absolute monotonic deadline. Callbacks must
    remain bounded; cancellation and any guard/progress failure propagate.
    """
    require(type(duration) in (int, float) and math.isfinite(duration)
            and 0 < duration <= 300, 'time03:duration')
    require(type(deadline) in (int, float) and math.isfinite(deadline), 'time03:deadline')
    require(callable(guard) and callable(progress), 'time03:callbacks')
    guard()
    started = time.monotonic()
    require(started + duration < deadline, 'time03:insufficient-budget')

    def check():
        guard()
        now = time.monotonic()
        require(now < deadline, 'time03:deadline')
        return now - started

    for checkpoint in range(5):
        target = duration * checkpoint / 4
        elapsed = check()
        while elapsed < target:
            remaining = deadline - time.monotonic()
            require(remaining > 0, 'time03:deadline')
            time.sleep(min(0.25, target - elapsed, remaining))
            elapsed = check()
        progress(checkpoint, elapsed)
        elapsed = check()
    return elapsed


def interval_action(duration):
    """Bind finite recipe data to the installed journey's guarded stage action."""
    def action(journey, guard):
        deadline = guard()
        def progress(checkpoint, elapsed):
            watch_activity.event(f'Real interval checkpoint {checkpoint}/4')
            if journey.watch_progress is not None:
                journey.watch_progress.operation(
                    f'Waiting the declared real interval: checkpoint {checkpoint}/4')
        with watch_activity.operation('Waiting the declared real interval under the attempt guard'):
            return wait_real_interval(duration, deadline=deadline,
                                      guard=guard, progress=progress)
    return action
