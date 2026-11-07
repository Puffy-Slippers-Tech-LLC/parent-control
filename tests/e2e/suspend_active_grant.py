"""LIFE03: the same child's active and elapsed-grant returns from real sleep."""

import time
from dataclasses import replace

from accessible_ui import countdown_seconds
from grant_only_profile import GrantOnlyProfileJourney, PLAN as PROFILE
from installed_journey import JourneyPlan
from journey_blocks import (fresh_desktop, prefixed_stages, native_activity_entry,
                            native_activity_resume, lock_challenge, lock_recipient,
                            grant_only_time_profile)
from native_fixtures import fixture_actions
from private_artifacts import require
from real_interval import wait_until


RETURN = {
    **prefixed_stages('fresh', fresh_desktop('child')),
    **native_activity_entry('activity', child='child'),
    'initial-countdown': 'ui:child-countdown-present',
    'suspend': 'system:child-entry-same',
    'wake-session': 'system:child-entry-lock',
    **lock_challenge(entry='challenge', account='child'), **lock_recipient(account='child'),
    'unlock-desktop': 'ui:fresh-child-desktop',
    'returned-session': 'system:child-entry-same',
    'returned-countdown': 'ui:child-countdown-present',
    **native_activity_resume('resume', child='child'),
    'usable-activity': 'ui:overlay-native-activity',
}
SCREENS = {**PROFILE.screen_tags, **RETURN}
PLAN = JourneyPlan(
    prefix='suspend-active-grant', worker_mode='suspend_active_grant', screen_tags=SCREENS,
    phases={**PROFILE.phases, **{stage: 'step-2' for stage in RETURN}},
    invocations=PROFILE.invocations + tuple('fresh-' + stage for stage in fresh_desktop('child')),
    challenges={**PROFILE.challenges,
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked')},
    stage_actions={'desktop': 'native-verify', 'suspend': 'suspend-wake'},
    activity_checks={'resume-opened': ('activity-capture', 'same'),
                     'usable-activity': ('activity-capture', 'same')},
    assertions_after={**PROFILE.assertions_after, 'usable-activity': 'same-work-after-suspend'},
)

# The same worker and power operation also qualify the real expired return.
# Ten minutes leaves setup/authentication headroom; only the final four minutes
# are spent asleep, within LIFE03's existing bounded interval.
EXPIRED_RETURN = {
    **prefixed_stages('fresh', fresh_desktop('child')),
    **native_activity_entry('activity', child='child'),
    'initial-countdown': 'ui:child-countdown-present',
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
EXPIRED_PROFILE = grant_only_time_profile(source='gdm', entry='fresh', window='new',
    initial_enabled=False, revoke_first=False, duration_seconds=600, request_initial='default')
EXPIRED_PLAN = replace(PLAN, prefix='suspend-expired-grant',
    screen_tags={**EXPIRED_PROFILE, **EXPIRED_RETURN},
    phases={**PROFILE.phases, **{stage: 'step-2' for stage in EXPIRED_RETURN}},
    stage_actions={'desktop': 'native-verify', 'expiry-wait': 'real-interval',
                   'suspend': 'suspend-wake'},
    activity_checks={}, kiosk_request=('child', 'parent', 600, True),
    assertions_after={**PROFILE.assertions_after,
        'wake-session': 'same-child-after-original-deadline',
        'time-denied': 'specific-time-denial-no-desktop',
        'retained-after': 'same-retained-locked-child'})


class SuspendActiveGrantJourney(GrantOnlyProfileJourney):
    def __init__(self, context, progress, *, plan=PLAN):
        require(plan is PLAN or plan is EXPIRED_PLAN, 'suspend-active-grant:plan')
        self.expired = plan is EXPIRED_PLAN
        super().__init__(context, progress, plan, grant_seconds=600 if self.expired else 1200, actions={
            **fixture_actions(include_refusal=False, profile='activity'),
            **({'real-interval': self.wait_for_sleep} if self.expired else {}),
            'suspend-wake': self.suspend})
        self.sleep_deadline = None
        self.child_session = None
        self.original_deadline = None
        self.initial_read = None
        self.sleep_seconds = 5

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'initial-countdown':
            seconds, _ = countdown_seconds(observed['ui']['countdown']['text'])
            # Leave several minutes for slow transport, public lock discovery,
            # two recipient proofs, password delivery and independent work use.
            require(seconds >= (300 if self.expired else 600),
                    self.plan.prefix + ':grant-headroom')
            self.sleep_deadline = time.monotonic() + (900 if self.expired else 120)
            if self.expired:
                self.initial_read = (observed['ui']['countdown']['seconds'], tuple(self.ui.read_bounds))
                # The exact public seconds and controller read bracket bound the
                # original elapsed deadline without trusting the suspended clock.
                self.original_deadline = self.initial_read[1][1] / 1e9 + self.initial_read[0] + 2
        if stage == 'suspend-countdown':
            seconds = observed['ui']['countdown']['seconds']
            before, earlier = self.initial_read
            bounds = tuple(self.ui.read_bounds)
            minimum, maximum = (bounds[0] - earlier[1]) / 1e9, (bounds[1] - earlier[0]) / 1e9
            require(60 <= seconds <= 250 and 0 < minimum <= maximum
                    and before - maximum - 4 < seconds < before - minimum + 4,
                    'suspend-expired-grant:original-positive-deadline')
            self.sleep_seconds = self.original_deadline + 5 - time.monotonic()
            require(0 < self.sleep_seconds <= 300, 'suspend-expired-grant:sleep-interval')
        if stage == 'suspend':
            require(self.sleep_deadline is not None, 'suspend-active-grant:missing-countdown')
            self.child_session = observed['system']['session_sha256']
        if stage in ('wake-session', 'returned-session', 'retained-after'):
            require(self.child_session is not None
                    and observed['system']['session_sha256'] == self.child_session,
                    'suspend-active-grant:child-session-changed')
        if stage == 'wake-session' and self.expired:
            require(self.original_deadline is not None and time.monotonic() > self.original_deadline,
                    'suspend-expired-grant:deadline-not-elapsed')
            observed['comparison'] = {'original_deadline_elapsed': True,
                'original_deadline_monotonic': self.original_deadline,
                'same_retained_child': True}
        if stage == 'returned-countdown':
            seconds, _ = countdown_seconds(observed['ui']['countdown']['text'])
            require(seconds > 0, 'suspend-active-grant:grant-expired-before-return')

    @staticmethod
    def wait_for_sleep(journey, guard):
        require(journey.original_deadline is not None, 'suspend-expired-grant:missing-countdown')
        wait_until(journey, guard, journey.original_deadline - 240)
        return {'original_deadline_monotonic': journey.original_deadline}

    @staticmethod
    def suspend(journey, guard):
        require(journey.sleep_deadline is not None, 'suspend-active-grant:missing-deadline')
        if journey.expired:
            require(time.monotonic() + 60 < journey.original_deadline,
                    'suspend-expired-grant:late-suspend')
        result = journey.submit_suspend(guard, duration=journey.sleep_seconds,
                                        deadline=min(journey.sleep_deadline, guard()))
        if journey.expired:
            require(result['suspended_monotonic'] < journey.original_deadline < result['wake_monotonic'],
                    'suspend-expired-grant:deadline-not-crossed-asleep')
        return result
