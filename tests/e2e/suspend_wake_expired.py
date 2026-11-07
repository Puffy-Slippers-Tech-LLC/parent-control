"""Time expires during sleep; a parent's new approval restores the child's work."""
from dataclasses import replace
import time

from app_restart_expired import AppRestartExpiredJourney, PLAN as EXPIRED, SETUP, RECOVERY
from journey_blocks import desktop_entry, desktop_return, fresh_desktop, prefixed_stages
from installed_journey import record_installed_journey
from native_fixtures import fixture_actions
from private_artifacts import require
from real_interval import interval_action


BOUNDARY = {
    **desktop_return('original-leave', account='child'),
    **prefixed_stages('before-parent', desktop_entry('parent', source='gdm', entry='retained')),
    'before-policy': 'ui:revoke-saved-balances',
    **desktop_return('boundary-parent-leave', account='parent'),
    **prefixed_stages('boundary-child', desktop_entry('child', source='gdm', entry='retained')),
    'boundary-countdown': 'ui:child-countdown-present',
    'expiry-wait': 'system:child-entry-same',
    'suspend-countdown': 'ui:child-countdown-present',
    'suspend': 'system:child-entry-same',
    'wake-session': 'system:child-entry-lock',
    'denial-ready': 'ui:child-lock-time-denial-ready',
    'time-denied': 'ui:child-lock-time-denied',
    'return-greeter': 'system:child-return-greeter',
    'denied-returned': 'ui:gdm-returned',
    'retained-after': 'system:child-retained-locked',
}
# The native restriction above already proves denial before replacement.
# Retain the same desktop/work; another GDM denial adds no customer outcome.
RETURN = {stage: tag for stage, tag in RECOVERY.items()
          if not stage.startswith(('denied-child-', 'denied-return'))}
SCREENS = {**SETUP, **BOUNDARY, **RETURN}
LOGINS = {**{prefix: role for prefix, (role, _first, _second) in EXPIRED.challenges.items()
             if prefix + '-entry-guard' in SCREENS},
          'boundary-child': 'child'}
LOGIN_STAGES = {prefix + '-' + stage for prefix, role in LOGINS.items()
                for stage in fresh_desktop(role)}
PLAN = replace(EXPIRED, prefix='suspend-wake-expired', worker_mode='suspend_wake_expired',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SETUP}, 'installed-greeter': 'start',
            **{stage: 'step-3' if stage in ('expiry-wait', 'suspend-countdown', 'suspend',
                                          'wake-session', 'denial-ready', 'time-denied',
                                          'return-greeter', 'denied-returned', 'retained-after')
               else 'step-2' for stage in BOUNDARY},
            **{stage: 'step-4' for stage in RETURN}},
    advance_after={'original-capture': 'step-2', 'boundary-countdown': 'step-3',
                   'retained-after': 'step-4'},
    stage_actions={'desktop': 'native-verify', 'expiry-wait': 'real-interval',
                   'suspend': 'suspend-wake'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={prefix: (role, prefix + '-' + ('child-' if role == 'child' else '')
                        + 'recipient-qualified',
                        prefix + '-' + ('child-' if role == 'child' else '')
                        + 'recipient-rechecked') for prefix, role in LOGINS.items()},
    activity_entries={'boundary-child-entry-guard': 'original-capture',
                      'recovered-child-entry-guard': 'original-capture'},
)


class SuspendWakeExpiredJourney(AppRestartExpiredJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.child_session = None
        self.boundary_countdown = None
        self.sleep_seconds = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'boundary-countdown':
            require(self.original_deadline_ns is not None, 'suspend-wake-expired:missing-deadline')
            self.boundary_countdown = (observed['ui']['countdown']['seconds'], tuple(self.ui.read_bounds))
            require(self.boundary_countdown[0] >= 300, 'suspend-wake-expired:setup-margin')
        if stage == 'suspend-countdown':
            require(self.boundary_countdown is not None, 'suspend-wake-expired:missing-countdown')
            before, earlier = self.boundary_countdown
            bounds = tuple(self.ui.read_bounds)
            seconds = observed['ui']['countdown']['seconds']
            minimum, maximum = (bounds[0] - earlier[1]) / 1e9, (bounds[1] - earlier[0]) / 1e9
            require(60 <= seconds <= 250 and 0 < minimum <= maximum
                    and before - maximum - 4 < seconds < before - minimum + 4,
                    'suspend-wake-expired:original-positive-deadline')
            self.sleep_seconds = self.original_deadline_ns / 1e9 + 5 - time.monotonic()
            require(0 < self.sleep_seconds <= 300, 'suspend-wake-expired:sleep-interval')
        if stage == 'suspend':
            self.child_session = observed['system']['session_sha256']
        if stage in ('wake-session', 'retained-after', 'recovered-child-entry-guard'):
            require(self.child_session is not None
                    and observed['system']['session_sha256'] == self.child_session,
                    'suspend-wake-expired:child-session-changed')
        if stage == 'wake-session':
            require(time.monotonic_ns() > self.original_deadline_ns,
                    'suspend-wake-expired:deadline-not-elapsed')
            observed['comparison'] = {'original_deadline_elapsed': True, 'same_retained_child': True}

    @staticmethod
    def wait_for_sleep(journey, guard):
        require(journey.original_deadline_ns is not None, 'suspend-wake-expired:missing-deadline')
        while (remaining := journey.original_deadline_ns / 1e9 - 240 - time.monotonic()) > 0:
            interval_action(min(300, remaining))(journey, guard)
        return {'original_deadline_monotonic_ns': journey.original_deadline_ns}

    @staticmethod
    def suspend(journey, guard):
        require(journey.sleep_seconds is not None
                and time.monotonic() + 60 < journey.original_deadline_ns / 1e9,
                'suspend-wake-expired:late-suspend')
        result = journey.submit_suspend(guard, duration=journey.sleep_seconds,
                                        deadline=min(time.monotonic() + 600, guard()))
        require(result['suspended_monotonic'] < journey.original_deadline_ns / 1e9
                < result['wake_monotonic'], 'suspend-wake-expired:deadline-not-crossed-asleep')
        return result


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-022/suspend-wake-expired'
    record_installed_journey(recorder, context, PLAN, timeout=3600,
        journey_type=SuspendWakeExpiredJourney,
        actions={**fixture_actions(include_refusal=False, profile='activity'),
                 'real-interval': SuspendWakeExpiredJourney.wait_for_sleep,
                 'suspend-wake': SuspendWakeExpiredJourney.suspend})


E2E_CASES = {'suspend-wake-expired': execute}
