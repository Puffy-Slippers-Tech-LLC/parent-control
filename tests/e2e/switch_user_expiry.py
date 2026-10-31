"""Cases 25/26: a child's original grant expires while another user works."""

import time

from accessible_ui import countdown_seconds
from countdown import CountdownObservation, check_countdown_balance
from grant_only_profile import GrantOnlyProfileJourney
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, fresh_desktop, grant_only_time_profile,
                            native_activity_entry, native_activity_resume,
                            prefixed_stages, rejected_gdm_return, retained_app_activities,
                            retained_app_visit)
from native_fixtures import fixture_actions
from private_artifacts import require
from real_interval import interval_action


GRANT_SECONDS = 600
WORK_INTERVAL_SECONDS = 150

PREPARATION = {
    **grant_only_time_profile(source='gdm', entry='fresh', window='new',
        initial_enabled=False, revoke_first=False, duration_seconds=GRANT_SECONDS,
        request_initial='default', balance_readback=False),
    **prefixed_stages('child-start', desktop_entry('child', source='gdm', entry='fresh')),
    'initial-countdown': 'ui:child-countdown-present',
    **prefixed_stages('parent-work', desktop_entry('parent', source='desktop',
        entry='retained', source_account='child')),
    **native_activity_entry('parent-activity', child='parent'),
}
# Four finite periods of normal app use and 150 real seconds. The original
# grant is at most ten minutes; no approval or policy write occurs in this loop.
WORK = {
    stage: tag
    for number in range(1, 5)
    for stage, tag in {
        **native_activity_resume(f'work-{number}', child='parent'),
        f'work-{number}-wait': 'ui:parent-native-activity',
    }.items()
}
RETURN = {
    'original-interval-passed': 'ui:parent-native-activity',
    **prefixed_stages('child-return', desktop_entry('child', source='desktop',
        entry='retained', expected='time-denied', source_account='parent')),
    **rejected_gdm_return(),
    **retained_app_visit('parent-return', account='parent', source='gdm'),
    'parent-usable-activity': 'ui:parent-native-activity',
}
SCREENS = {**PREPARATION, **WORK, **RETURN}
LOGIN_PREFIXES = {'': 'parent', 'child-start-': 'child',
                  'parent-work-': 'parent', 'child-return-': 'child', 'parent-return-': 'parent'}
LOGIN_STAGES = {prefix + stage for prefix, account in LOGIN_PREFIXES.items()
                for stage in fresh_desktop(account, 'time-denied' if prefix == 'child-return-'
                                            else 'success')}
PLAN = JourneyPlan(
    prefix='switch-user-expiry-parent', worker_mode='switch_user_expiry_parent',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in PREPARATION}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in WORK}, **{stage: 'step-3' for stage in RETURN}},
    advance_after={'parent-activity-capture': 'step-2', 'work-4-wait': 'step-3'},
    stage_actions={'desktop': 'native-verify',
                   **{f'work-{number}-wait': 'real-interval' for number in range(1, 5)}},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES
                      or stage in rejected_gdm_return()),
    challenges={
        ('parent-login' if not prefix else prefix.rstrip('-')):
            (account, prefix + ('child-' if account == 'child' else '') + 'recipient-qualified',
             prefix + ('child-' if account == 'child' else '') + 'recipient-rechecked')
        for prefix, account in LOGIN_PREFIXES.items()},
    activity_checks={stage: ('parent-activity-capture', 'same')
                     for stage, tag in {**WORK, **RETURN}.items()
                     if tag == 'ui:parent-native-activity'},
    activity_entries={'parent-return-entry-guard': 'parent-activity-capture'},
    assertions_after={'parent-usable-activity': 'visible-result'},
)


OTHER_PREPARATION = {
    **retained_app_activities((('other-setup', 'other-child', 'fresh'),)),
    **grant_only_time_profile(source='gdm', entry='fresh', window='new',
        initial_enabled=False, revoke_first=False, duration_seconds=GRANT_SECONDS,
        request_initial='default', balance_readback=False),
    **prefixed_stages('child-start', desktop_entry('child', source='gdm', entry='fresh')),
    'initial-countdown': 'ui:child-countdown-present',
    **retained_app_visit('other-work', account='other-child', source='desktop',
                         source_account='child'),
    'other-child-active': 'ui:native-activity',
}
OTHER_WORK = {
    stage: tag
    for number in range(1, 5)
    for stage, tag in {
        **native_activity_resume(f'work-{number}', child='other-child'),
        f'work-{number}-wait': 'ui:native-activity',
    }.items()
}
OTHER_RETURN = {
    'original-interval-passed': 'ui:native-activity',
    **prefixed_stages('child-return', desktop_entry('child', source='desktop',
        entry='retained', expected='time-denied', source_account='other-child')),
    **rejected_gdm_return(),
    **retained_app_visit('other-return', account='other-child', source='gdm'),
    'other-usable-activity': 'ui:native-activity',
}
OTHER_SCREENS = {**OTHER_PREPARATION, **OTHER_WORK, **OTHER_RETURN}
OTHER_LOGINS = {'other-setup-': 'other-child', '': 'parent', 'child-start-': 'child',
                'other-work-': 'other-child', 'child-return-': 'child',
                'other-return-': 'other-child'}
OTHER_LOGIN_STAGES = {prefix + stage for prefix, account in OTHER_LOGINS.items()
    for stage in fresh_desktop(account, 'time-denied' if prefix == 'child-return-' else 'success')}
OTHER_PLAN = JourneyPlan(
    prefix='switch-user-expiry-other-child', worker_mode='switch_user_expiry_other_child',
    screen_tags=OTHER_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in OTHER_PREPARATION},
            'other-setup-entry-guard': 'start',
            **{stage: 'step-2' for stage in OTHER_WORK},
            **{stage: 'step-3' for stage in OTHER_RETURN}},
    advance_after={'other-child-active': 'step-2', 'work-4-wait': 'step-3'},
    stage_actions={'desktop': 'native-verify',
                   **{f'work-{number}-wait': 'real-interval' for number in range(1, 5)}},
    invocations=tuple(stage for stage in OTHER_SCREENS if stage in OTHER_LOGIN_STAGES
                      or stage in rejected_gdm_return()),
    challenges={('parent-login' if not prefix else prefix.rstrip('-')):
        (account, prefix + {'parent': '', 'child': 'child-', 'other-child': 'standard-'}[account]
         + 'recipient-qualified',
         prefix + {'parent': '', 'child': 'child-', 'other-child': 'standard-'}[account]
         + 'recipient-rechecked') for prefix, account in OTHER_LOGINS.items()},
    activity_checks={stage: ('other-setup-activity-capture', 'same')
                     for stage, tag in OTHER_SCREENS.items()
                     if tag == 'ui:native-activity' and stage != 'other-setup-activity-capture'},
    activity_entries={'other-work-source-desktop': 'other-setup-activity-capture',
                      'other-return-entry-guard': 'other-setup-activity-capture'},
    assertions_after={'other-usable-activity': 'visible-result'},
)


class SwitchUserExpiryJourney(GrantOnlyProfileJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions if actions is not None else {
            **fixture_actions(include_refusal=False),
            'real-interval': interval_action(WORK_INTERVAL_SECONDS)})
        self.grant_balance = None
        self.earliest_deadline_ns = None
        self.original_deadline_ns = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'profile-request-new-estimate':
            value = observed['ui']['valid_choice']
            require(value['request']['duration_seconds'] == GRANT_SECONDS
                    and value['estimate']['kind'] == 'fixed'
                    and value['estimate']['seconds'] == GRANT_SECONDS,
                    'switch-expiry:grant-estimate')
            self.grant_balance = (GRANT_SECONDS, value['estimate']['precision_seconds'],
                                  value['observed_monotonic_ns'])
        # Public authentication observations bracket the actual grant issuance.
        # Keep these original controller-clock deadlines throughout the journey.
        if stage == 'profile-request-approval-open':
            self.earliest_deadline_ns = self.approval_started + (GRANT_SECONDS - 2) * 1_000_000_000
        if stage == 'profile-request-approval-success':
            self.original_deadline_ns = time.monotonic_ns() + (GRANT_SECONDS + 2) * 1_000_000_000
        if stage == 'initial-countdown':
            require(self.grant_balance is not None, 'switch-expiry:missing-grant')
            current = CountdownObservation.from_value(observed['ui']['countdown'], present=True)
            require(countdown_seconds(current.text)[0] > 0, 'switch-expiry:initial-time-exhausted')
            observed['comparison'] = check_countdown_balance(current,
                seconds=self.grant_balance[0], precision_seconds=self.grant_balance[1],
                observed_monotonic_ns=self.grant_balance[2], sampling_seconds=30)
        if stage in ('parent-activity-capture', 'other-child-active'):
            require(self.earliest_deadline_ns is not None
                    and time.monotonic_ns() < self.earliest_deadline_ns,
                    'switch-expiry:foreground-started-too-late')
        if stage == 'original-interval-passed':
            require(self.original_deadline_ns is not None
                    and time.monotonic_ns() > self.original_deadline_ns,
                    'switch-expiry:original-interval-not-passed')
            observed['comparison'] = {'original_grant_interval_passed': True}


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-010/parent'
    record_installed_journey(recorder, context, PLAN, journey_type=SwitchUserExpiryJourney)


def execute_other_child(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-010/other-child'
    record_installed_journey(recorder, context, OTHER_PLAN, journey_type=SwitchUserExpiryJourney)


E2E_CASES = {'parent': execute, 'other-child': execute_other_child}
