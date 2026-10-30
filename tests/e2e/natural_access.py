"""Case 22: animated daily exhaustion, approved recovery and fresh denial."""

from copy import deepcopy

from accessible_ui import countdown_seconds
from countdown import CountdownSample, check_countdown_balance
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (daily_time_profile, desktop_entry, fresh_desktop,
                            native_activity_entry, native_activity_resume,
                            prefixed_stages, retained_parent_entry)
from kiosk_approved_flow import obtain_time
from natural_expiry import NaturalExpiryJourney
from native_fixtures import fixture_actions
from private_artifacts import require
from request_flow import CHOICES
from ui_observations import SettingsObservation


PROFILE = daily_time_profile(source='desktop', entry='same-user', window='new',
                             initial_enabled=False, minutes=2)
_switch = tuple(PROFILE).index('repeat-desktop')
PREPARATION = {
    **fresh_desktop('parent'),
    **dict(list(PROFILE.items())[:_switch]),
    'policy-before': 'ui:revoke-saved-balances',
    **dict(list(PROFILE.items())[_switch:]),
    **prefixed_stages('fresh', desktop_entry('child', source='gdm', entry='fresh')),
    'before-animation': 'ui:child-countdown-present',
    'animation-set': 'ui:child-countdown-animation-on',
    'animation-read': 'ui:child-countdown-animation-read',
    **native_activity_entry('activity', child='child'),
}
EXHAUSTION = {
    'natural-expiry': 'ui:child-countdown-present',
    'lock-input-ready': 'ui:child-natural-expiry-lock-ready',
    'lock-result': 'ui:child-natural-expiry-lock-result',
}
RESTRICTION = {
    'curtain': 'ui:child-lock-curtain',
    'reveal-ready': 'ui:child-lock-reveal-ready',
    'time-denied': 'ui:child-lock-time-denied',
    'return-greeter': 'system:child-return-greeter',
    'denied-returned': 'ui:gdm-returned',
    'retained-before': 'system:child-retained-locked',
}
RECOVERY = {
    # Leave time for retained recovery, normal logout and fresh Parent reads.
    **obtain_time(initial='default', **{**CHOICES, 'duration_seconds': 600}, exit='automatic'),
    **prefixed_stages('recovery', desktop_entry('child', source='gdm', entry='retained')),
    'recovery-identity': 'system:child-entry-same',
    'recovery-activity': 'ui:overlay-native-activity',
    **native_activity_resume('resume', child='child'),
    'usable-activity': 'ui:overlay-native-activity',
    'logout-ready': 'ui:fresh-child-desktop',
    'logout': 'system:child-logout',
    'gdm-logged-out': 'ui:gdm-returned',
}
REVOCATION = {
    **prefixed_stages('return', fresh_desktop('parent')),
    **prefixed_stages('supplied', retained_parent_entry(source='same-user')),
    'before-revoke': 'ui:revoke-saved-balances',
    'confirm-open': 'ui:revoke-open',
    'confirm-warning': 'ui:revoke-warning',
    'confirmed': 'ui:revoke-confirm',
    'after-revoke': 'ui:revoke-cleared-balances',
    'parent-leave-ready': 'ui:desktop',
    'parent-leave': 'system:parent-switch-user',
    'final-greeter': 'ui:gdm-returned',
}
DENIAL = prefixed_stages('denied', desktop_entry(
    'child', source='gdm', entry='fresh', expected='time-denied'))
SCREENS = {**PREPARATION, **EXHAUSTION, **RESTRICTION, **RECOVERY, **REVOCATION, **DENIAL}
LOGIN_STAGES = (set(fresh_desktop('parent'))
    | set(prefixed_stages('fresh', fresh_desktop('child')))
    | set(prefixed_stages('recovery', fresh_desktop('child')))
    | set(prefixed_stages('return', fresh_desktop('parent')))
    | set(prefixed_stages('denied', fresh_desktop('child', 'time-denied'))))
PLAN = JourneyPlan(
    prefix='natural-access', worker_mode='natural_access', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in PREPARATION}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in EXHAUSTION},
            **{stage: 'step-3' for stage in RESTRICTION},
            **{stage: 'step-4' for stage in RECOVERY},
            **{stage: 'step-5' for stage in REVOCATION},
            **{stage: 'step-6' for stage in DENIAL}},
    advance_after={'activity-capture': 'step-2', 'lock-result': 'step-3',
                   'retained-before': 'step-4', 'gdm-logged-out': 'step-5',
                   'final-greeter': 'step-6'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES
        or stage in EXHAUSTION or stage in ('before-animation', 'animation-set', 'animation-read')),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'fresh': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
        'recovery': ('child', 'recovery-child-recipient-qualified', 'recovery-child-recipient-rechecked'),
        'return': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked'),
        'denied': ('child', 'denied-child-recipient-qualified', 'denied-child-recipient-rechecked'),
    },
    settings_checks={'same-parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
                     'profile-settings': SettingsObservation('fixture-child', True, ('2 minutes',))},
    balance_checks={'profile-configured': 120},
    stage_actions={'desktop': 'native-verify', 'natural-expiry': 'natural-expiry'},
    activity_entries={'natural-expiry': 'activity-capture'},
    activity_checks={stage: ('activity-capture', 'same') for stage in
                     ('recovery-activity', 'resume-opened', 'usable-activity')},
    assertions_after={'lock-result': 'natural-lock', 'time-denied': 'retained-denial',
                      'usable-activity': 'approved-recovery', 'after-revoke': 'revoked-time',
                      'denied-denied': 'visible-result'},
)


class NaturalAccessJourney(NaturalExpiryJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions if actions is not None else {
            **fixture_actions(include_refusal=False, profile='activity'),
            'natural-expiry': self.natural_expiry})
        self.animation_observed_ns = None
        self.before_animation = None
        self.policy = None
        self.before_revoke = None
        self.retained_session = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        ui = observed.get('ui', {})
        if stage == 'before-animation':
            self.before_animation = CountdownSample.from_ui(ui, boot_sha256=observed['boot_sha256'])
            require(self.balance is not None, 'natural-access:missing-balance')
            observed['comparison'] = check_countdown_balance(self.before_animation.countdown,
                seconds=self.balance[0], precision_seconds=self.balance[1],
                observed_monotonic_ns=self.balance[2])
        if stage in ('animation-set', 'animation-read'):
            value = ui['panel_animation']
            require(value['animation'] is True and (stage == 'animation-set' or
                self.animation_observed_ns is not None and
                value['observed_monotonic_ns'] > self.animation_observed_ns),
                'natural-access:animation-readback')
            self.animation_observed_ns = value['observed_monotonic_ns']
        if stage == 'natural-expiry':
            require(self.before_animation is not None and self.animation_observed_ns is not None,
                    'natural-access:missing-animation')
            low, high = countdown_seconds(self.before_animation.countdown.text)
            observed['comparison'] = check_countdown_balance(self.initial_countdown.countdown,
                seconds=low, precision_seconds=high - low + 1,
                observed_monotonic_ns=self.before_animation.countdown.observed_monotonic_ns)
        if stage == 'retained-before':
            self.retained_session = observed['system']['session_sha256']
        if stage in ('recovery-entry-guard', 'recovery-identity'):
            require(self.retained_session is not None and
                    observed['system']['session_sha256'] == self.retained_session,
                    'natural-access:retained-session-replaced')
        if stage == 'new-estimate':
            value = ui['valid_choice']
            require(value['request']['duration_seconds'] == 600 and
                    value['estimate']['kind'] == 'fixed' and value['estimate']['seconds'] == 600,
                    'natural-access:temporary-approval-estimate')
        if stage not in ('policy-before', 'before-revoke', 'after-revoke'):
            return
        value = ui['revoke_cancel']
        require(value['settings'] == {'child': 'fixture-child', 'limit_enabled': True,
                                      'allowance': ['2 minutes']}, 'natural-access:allowance-changed')
        if stage == 'policy-before':
            self.policy = deepcopy(value)
            return
        require(self.policy is not None and all(value[key] == self.policy[key]
                for key in ('settings', 'apps', 'rules')), 'natural-access:policy-changed')
        balances = value['balances']
        require(balances['daily']['seconds'] == 0, 'natural-access:daily-not-exhausted')
        if stage == 'before-revoke':
            require(balances['one_time']['seconds'] > 0 and
                    balances['total']['seconds'] == balances['one_time']['seconds'],
                    'natural-access:missing-temporary-grant')
            self.before_revoke = deepcopy(value)
        else:
            require(self.before_revoke is not None and
                    value['read_bounds'][0] > self.before_revoke['read_bounds'][1] and
                    balances['one_time']['seconds'] == balances['total']['seconds'] == 0,
                    'natural-access:revoked-balances')
        observed['comparison'] = {'unchanged_allowance_and_app_access': True,
                                  'daily_exhausted': True,
                                  'grant_cleared': stage == 'after-revoke'}


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-008/fresh-login'
    record_installed_journey(recorder, context, PLAN, journey_type=NaturalAccessJourney)


E2E_CASES = {'fresh-login': execute}
