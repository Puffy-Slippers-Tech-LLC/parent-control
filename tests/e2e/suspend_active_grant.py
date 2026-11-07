"""LIFE03: a child sleeps and returns to the same work before extra time ends."""

import time

from accessible_ui import countdown_seconds
from grant_only_profile import GrantOnlyProfileJourney, PLAN as PROFILE
from installed_journey import JourneyPlan
from journey_blocks import (fresh_desktop, prefixed_stages, native_activity_entry,
                            native_activity_resume, lock_challenge, lock_recipient)
from native_fixtures import fixture_actions
from private_artifacts import require


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


class SuspendActiveGrantJourney(GrantOnlyProfileJourney):
    def __init__(self, context, progress, *, plan=PLAN):
        require(plan is PLAN, 'suspend-active-grant:plan')
        super().__init__(context, progress, plan, grant_seconds=1200, actions={
            **fixture_actions(include_refusal=False, profile='activity'),
            'suspend-wake': self.suspend})
        self.sleep_deadline = None
        self.child_session = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'initial-countdown':
            seconds, _ = countdown_seconds(observed['ui']['countdown']['text'])
            # Leave several minutes for slow transport, public lock discovery,
            # two recipient proofs, password delivery and independent work use.
            require(seconds >= 600, 'suspend-active-grant:grant-headroom')
            self.sleep_deadline = time.monotonic() + 120
        if stage == 'suspend':
            require(self.sleep_deadline is not None, 'suspend-active-grant:missing-countdown')
            self.child_session = observed['system']['session_sha256']
        if stage in ('wake-session', 'returned-session'):
            require(self.child_session is not None
                    and observed['system']['session_sha256'] == self.child_session,
                    'suspend-active-grant:child-session-changed')
        if stage == 'returned-countdown':
            seconds, _ = countdown_seconds(observed['ui']['countdown']['text'])
            require(seconds > 0, 'suspend-active-grant:grant-expired-before-return')

    @staticmethod
    def suspend(journey, guard):
        require(journey.sleep_deadline is not None, 'suspend-active-grant:missing-deadline')
        return journey.submit_suspend(guard, duration=5,
                                      deadline=min(journey.sleep_deadline, guard()))
