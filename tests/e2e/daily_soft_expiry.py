"""Case 164: original grant expiry alone keeps daily access and Soft use."""
from dataclasses import replace
import time

from accessible_ui import countdown_seconds
from countdown import CountdownSample
from daily_soft_profile import PLAN as PROFILE_PLAN, SCREENS as PROFILE_SCREENS, DailySoftProfileJourney
from installed_journey import record_installed_journey
from journey_blocks import (fresh_desktop, native_activity_entry, native_activity_resume,
                            native_usable_app, prefixed_stages,
                            retained_app_activities, retained_app_visit)
from native_fixtures import fixture_actions
from private_artifacts import require
from real_interval import interval_action


PEER = retained_app_activities((('peer', 'other-child', 'fresh'),))
EXPIRY = {
    **native_activity_entry('allowed', child='child'),
    'expiry-wait-first': 'ui:child-countdown-present',
    'expiry-wait-last': 'ui:child-countdown-present',
    'expired-countdown': 'ui:child-countdown-present',
}
RESULTS = {
    **native_activity_resume('allowed-return', child='child'),
    'expired-soft-opened': 'ui:overlay-native-policy-soft-activity',
    'expired-soft-submit': 'ui:overlay-native-soft-resubmit',
    'expired-soft-submitted': 'ui:overlay-native-soft-submitted',
    # Close normally after proving the old window usable, so the next launch
    # independently establishes new execution rather than activating that window.
    'expired-soft-close': 'ui:overlay-native-soft-close',
    'expired-soft-closed': 'ui:overlay-native-soft-closed',
    **prefixed_stages('new-soft', native_usable_app('command', child='child', role='S')),
    'final-child-countdown': 'ui:child-countdown-present',
    **retained_app_visit('peer-return', account='other-child', source='desktop', source_account='child'),
}
SCREENS = {**PEER, **PROFILE_SCREENS, **EXPIRY, **RESULTS}
PEER_LOGINS = {prefix + '-' + stage for prefix in ('peer', 'peer-return')
               for stage in fresh_desktop('other-child')}
PARENT_LOGIN = set(fresh_desktop('parent'))
PLAN = replace(PROFILE_PLAN,
    worker_mode='daily_soft_expiry', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: phase for phase, screens in (
                ('step-1', {**PEER, **PROFILE_SCREENS}), ('step-2', EXPIRY),
                ('step-3', RESULTS)) for stage in screens},
            'peer-entry-guard': 'start', 'peer-installed-greeter': 'start'},
    advance_after={'positive-child-witness': 'step-2', 'expired-countdown': 'step-3'},
    invocations=tuple(stage for stage in SCREENS
                      if stage in set(PROFILE_PLAN.invocations) | PEER_LOGINS | PARENT_LOGIN),
    challenges={**PROFILE_PLAN.challenges,
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        **{prefix: ('other-child',
        prefix + '-standard-recipient-qualified', prefix + '-standard-recipient-rechecked')
        for prefix in ('peer', 'peer-return')}},
    activity_checks={**PROFILE_PLAN.activity_checks,
        'allowed-return-opened': ('allowed-capture', 'same'),
        'expired-soft-opened': ('soft-capture', 'same'),
        'peer-return-activity-opened': ('peer-activity-capture', 'same')},
    activity_entries={**PROFILE_PLAN.activity_entries,
        'peer-return-entry-guard': 'peer-activity-capture'},
    stage_actions={**PROFILE_PLAN.stage_actions,
        'expiry-wait-first': 'wait-original-expiry', 'expiry-wait-last': 'wait-original-expiry'},
    assertions_after={'peer-return-activity-submitted': 'visible-result'},
)


class DailySoftExpiryJourney(DailySoftProfileJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions if actions is not None else {
            **fixture_actions(include_refusal=False, profile='activity'),
            'real-interval': self.wait_away, 'wait-original-expiry': self.wait_expiry})
        self.expiry_controller_ns = None
        self.expiry_guest_ns = None
        self.peer_session = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'peer-desktop-identity':
            self.peer_session = observed['system']['session_sha256']
        if stage == 'peer-return-entry-guard':
            require(self.peer_session is not None and
                    observed['system']['session_sha256'] == self.peer_session,
                    'daily-soft-expiry:peer-session-replaced')
        if stage == 'return-balance':
            balance = self.return_balance
            upper = balance['one_time']['seconds'] + balance['one_time']['precision_seconds'] + 2
            self.expiry_guest_ns = balance['observed_monotonic_ns'] + upper * 1_000_000_000
            # The controller bracket ends after the guest read. Starting the
            # same interval there is conservative even if its reply was delayed.
            self.expiry_controller_ns = self.ui.read_bounds[1] + upper * 1_000_000_000
        if stage in ('expired-countdown', 'final-child-countdown'):
            sample = CountdownSample.from_ui(observed['ui'], boot_sha256=observed['boot_sha256'])
            require(sample.boot_sha256 == self.return_boot
                    and self.expiry_guest_ns is not None
                    and sample.guest_read_bounds[0] > self.expiry_guest_ns
                    and countdown_seconds(sample.countdown.text)[0] > 0,
                    'daily-soft-expiry:original-expiry-with-positive-daily-access')
            observed['comparison'] = {'original_grant_expired': True, 'daily_access_positive': True}

    @staticmethod
    def wait_expiry(journey, guard):
        require(journey.expiry_controller_ns is not None, 'daily-soft-expiry:missing-original-deadline')
        remaining = (journey.expiry_controller_ns - time.monotonic_ns()) / 1e9
        return interval_action(min(300, remaining))(journey, guard) if remaining > 0 else 0


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-038/none'
    record_installed_journey(recorder, context, PLAN, timeout=3000,
                             journey_type=DailySoftExpiryJourney)


E2E_CASES = {'none': execute}
