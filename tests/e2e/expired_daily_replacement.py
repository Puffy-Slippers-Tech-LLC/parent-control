"""Replace an away-expired grant with daily time left, then return to the child."""
from copy import deepcopy
from dataclasses import replace
import time

from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS, countdown_seconds
from countdown import CountdownObservation, check_countdown_balance
from grant_only_profile import GrantOnlyProfileJourney
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (custom_allowance, desktop_entry, desktop_return, fresh_desktop,
                            grant_only_time_profile, native_activity_resume,
                            native_usable_app, prefixed_stages)
from kiosk_approved_flow import obtain_time
from named_app_set import APPS, named_app_set
from native_fixtures import fixture_actions
from policy_edits import AppPolicyJourney
from private_artifacts import require
from real_interval import interval_toward


GRANT_SECONDS = 600
RECOVERY_SECONDS = 1200
LOGINS = {
    'setup-return': ('parent', 'retained'),
    'original-entry': ('child', 'fresh'),
    'daily-parent': ('parent', 'retained'),
    'departure-child': ('child', 'retained'),
    'expired-parent': ('parent', 'retained'),
    'replacement-child': ('child', 'fresh'),
}


def enter(prefix):
    role, entry = LOGINS[prefix]
    return prefixed_stages(prefix, desktop_entry(role, source='gdm', entry=entry))


PREPARATION = {
    **named_app_set(source='gdm', entry='fresh', window='new', child='child',
                    apps=APPS, prefix='rules'),
    **enter('setup-return'),
    **grant_only_time_profile(source='desktop', entry='same-user', window='retained',
        initial_enabled=False, revoke_first=False, duration_seconds=GRANT_SECONDS,
        request_initial='default', balance_readback=False),
    **enter('original-entry'),
    'original-countdown': 'ui:child-countdown-present',
    **prefixed_stages('original-soft', native_usable_app('command', child='child', role='S')),
    'original-capture': 'ui:overlay-native-policy-soft-activity',
    **desktop_return('original-leave', account='child'),
    **enter('daily-parent'),
    'daily-page': 'ui:parent-screen-page',
    **custom_allowance('daily', 30),
    'before-departure': 'ui:revoke-saved-balances',
}
EXPIRY = {
    **desktop_return('daily-parent-leave', account='parent'),
    **enter('departure-child'),
    **desktop_return('departure', account='child', action='logout'),
    'expiry-wait-first': 'ui:gdm-returned',
    'expiry-wait-last': 'ui:gdm-returned',
    **enter('expired-parent'),
    'expired-balances': 'ui:revoke-saved-balances',
    **desktop_return('expired-parent-leave', account='parent'),
}
REPLACEMENT = {
    **obtain_time(initial='observed', child='fixture-child', approver='fixture-parent',
                  duration_seconds=RECOVERY_SECONDS, allow_soft=False, exit='automatic'),
    **enter('replacement-child'),
    'replacement-countdown': 'ui:child-countdown-present',
    'hard-denied': 'ui:overlay-native-hard-command-blocked',
    'soft-denied': 'ui:overlay-native-soft-command-blocked',
    **prefixed_stages('allowed', native_usable_app('command', child='child', role='A')),
}
SCREENS = {**PREPARATION, **EXPIRY, **REPLACEMENT}
LOGIN_STAGES = {prefix + '-' + stage for prefix, (role, _entry) in LOGINS.items()
                for stage in fresh_desktop(role)}
PLAN = JourneyPlan(
    prefix='expired-daily-replacement', worker_mode='expired_daily_replacement', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: phase for phase, screens in (
            ('step-1', PREPARATION), ('step-2', EXPIRY), ('step-3', REPLACEMENT)) for stage in screens},
        'installed-greeter': 'start'},
    advance_after={'before-departure': 'step-2',
                   'expired-parent-leave-gdm-switched': 'step-3'},
    stage_actions={'desktop': 'native-verify', 'expiry-wait-first': 'real-interval',
                   'expiry-wait-last': 'real-interval'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={prefix: (role, prefix + '-' + ('child-' if role == 'child' else '')
                        + 'recipient-qualified',
                        prefix + '-' + ('child-' if role == 'child' else '')
                        + 'recipient-rechecked') for prefix, (role, _entry) in LOGINS.items()},
    child_bindings={stage: 'child' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    kiosk_request=('child', 'parent', RECOVERY_SECONDS, False),
    match_checks={f'rules-saved-{role.lower()}-match': (MATCH_APPS[role], rule)
                  for role, rule in (('A', MATCH_RULES[0]), ('H', MATCH_RULES[3]),
                                     ('S', MATCH_RULES[4]))},
    access_checks={f'rules-saved-{role.lower()}-access': (MATCH_APPS[role], access)
                   for role, access in (('A', 'allowed'), ('H', 'permanent'), ('S', 'conditional'))},
    assertions_after={'allowed-submitted': 'visible-result'},
)

INCLUDED_REPLACEMENT = {
    **obtain_time(initial='observed', child='fixture-child', approver='fixture-parent',
                  duration_seconds=RECOVERY_SECONDS, allow_soft=True, exit='automatic'),
    **enter('replacement-child'),
    'replacement-countdown': 'ui:child-countdown-present',
    'hard-denied': 'ui:overlay-native-hard-command-blocked',
    **prefixed_stages('soft', native_usable_app('command', child='child', role='S')),
    **prefixed_stages('allowed', native_usable_app('command', child='child', role='A')),
}
INCLUDED_SCREENS = {**PREPARATION, **EXPIRY, **INCLUDED_REPLACEMENT}
INCLUDED_PLAN = replace(PLAN, screen_tags=INCLUDED_SCREENS,
    phases={stage: 'step-3' if stage in INCLUDED_REPLACEMENT else PLAN.phases[stage]
            for stage in ('ready', 'setup-detached', *INCLUDED_SCREENS)},
    child_bindings={stage: 'child' for stage, tag in INCLUDED_SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    kiosk_request=('child', 'parent', RECOVERY_SECONDS, True),
)

RETAINED_EXPIRY = {
    **desktop_return('daily-parent-leave', account='parent'),
    'original-session': 'system:child-retained-locked',
    'expiry-wait-first': 'ui:gdm-returned',
    'expiry-wait-last': 'ui:gdm-returned',
    **enter('expired-parent'),
    'expired-balances': 'ui:revoke-saved-balances',
    **desktop_return('expired-parent-leave', account='parent'),
}
RETAINED_REPLACEMENT = {
    **obtain_time(initial='observed', child='fixture-child', approver='fixture-parent',
                  duration_seconds=RECOVERY_SECONDS, allow_soft=False, exit='automatic'),
    **prefixed_stages('replacement-child', desktop_entry('child', source='gdm', entry='retained')),
    'replacement-countdown': 'ui:child-countdown-present',
    'original-soft-closed': 'ui:overlay-native-policy-soft-closed',
    'hard-denied': 'ui:overlay-native-hard-command-blocked',
    'soft-denied': 'ui:overlay-native-soft-command-blocked',
    **prefixed_stages('allowed', native_usable_app('command', child='child', role='A')),
}
RETAINED_SCREENS = {
    **PREPARATION,
    **RETAINED_EXPIRY, **RETAINED_REPLACEMENT,
}
RETAINED_PLAN = replace(PLAN,
    worker_mode='expired_daily_replacement_retained', screen_tags=RETAINED_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: phase for phase, screens in (
                ('step-1', PREPARATION), ('step-2', RETAINED_EXPIRY),
                ('step-3', RETAINED_REPLACEMENT)) for stage in screens},
            'installed-greeter': 'start'},
    invocations=tuple(stage for stage in RETAINED_SCREENS if stage in LOGIN_STAGES),
    challenges={prefix: binding for prefix, binding in PLAN.challenges.items()
                if prefix != 'departure-child'},
    activity_entries={'replacement-child-entry-guard': 'original-capture'},
    activity_checks={'original-soft-closed': ('original-capture', 'closed')},
)

RETAINED_INCLUDED_REPLACEMENT = {
    **obtain_time(initial='observed', child='fixture-child', approver='fixture-parent',
                  duration_seconds=RECOVERY_SECONDS, allow_soft=True, exit='automatic'),
    **prefixed_stages('replacement-child', desktop_entry('child', source='gdm', entry='retained')),
    'replacement-countdown': 'ui:child-countdown-present',
    **native_activity_resume('original-soft-return', child='child', binding='policy-soft'),
    'original-soft-return-close': 'ui:overlay-native-soft-close',
    'original-soft-return-closed': 'ui:overlay-native-soft-closed',
    'hard-denied': 'ui:overlay-native-hard-command-blocked',
    **prefixed_stages('soft', native_usable_app('command', child='child', role='S')),
    **prefixed_stages('allowed', native_usable_app('command', child='child', role='A')),
}
RETAINED_INCLUDED_SCREENS = {**PREPARATION, **RETAINED_EXPIRY, **RETAINED_INCLUDED_REPLACEMENT}
RETAINED_INCLUDED_PLAN = replace(RETAINED_PLAN, screen_tags=RETAINED_INCLUDED_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: phase for phase, screens in (
                ('step-1', PREPARATION), ('step-2', RETAINED_EXPIRY),
                ('step-3', RETAINED_INCLUDED_REPLACEMENT)) for stage in screens},
            'installed-greeter': 'start'},
    invocations=tuple(stage for stage in RETAINED_INCLUDED_SCREENS if stage in LOGIN_STAGES),
    child_bindings={stage: 'child' for stage, tag in RETAINED_INCLUDED_SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    kiosk_request=('child', 'parent', RECOVERY_SECONDS, True),
    activity_checks={'original-soft-return-opened': ('original-capture', 'same')},
)


class ExpiredDailyReplacementJourney(GrantOnlyProfileJourney, AppPolicyJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        # Arm the original-deadline observer before any real approval.
        self.original_deadline_ns = None
        self.original_sample = None
        self.saved_policy = None
        self.expired_balance = None
        self.replacement_started = None
        self.replacement_estimate = None
        self.original_session = None
        super().__init__(context, progress, plan, grant_seconds=GRANT_SECONDS,
            actions=actions if actions is not None else {
                **fixture_actions(include_refusal=False, profile='activity'),
                'real-interval': self.remaining_interval})

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'profile-request-approval-success':
            require(self.original_deadline_ns is None, 'expired-daily:approval-replay')
            # Issuance precedes this public success. Wait beyond its conservative
            # upper endpoint, then independently require G=0 in Parent.
            self.original_deadline_ns = time.monotonic_ns() + (GRANT_SECONDS + 2) * 1_000_000_000
        if stage == 'original-countdown':
            value = CountdownObservation.from_value(observed['ui']['countdown'], present=True)
            require(countdown_seconds(value.text)[0] >= 300, 'expired-daily:initial-margin')
        if stage in ('before-departure', 'expired-balances'):
            value = observed['ui']['revoke_cancel']
            require(value['settings'] == {'child': 'fixture-child', 'limit_enabled': True,
                                         'allowance': ['30 minutes']}, 'expired-daily:saved-allowance')
            policy = {key: deepcopy(value[key]) for key in ('settings', 'apps', 'rules')}
            balance = value['balances']
            daily, grant, total = (balance[key]['seconds'] for key in ('daily', 'one_time', 'total'))
            precision = max(balance[key]['precision_seconds'] for key in ('daily', 'one_time', 'total'))
            require(daily >= 900 and abs(total - daily) <= precision, 'expired-daily:daily-margin')
            if stage == 'before-departure':
                require(self.approval_started is not None and self.original_deadline_ns is not None,
                        'expired-daily:missing-original-approval')
                elapsed = (time.monotonic_ns() - self.approval_started) / 1e9
                require(daily - grant > precision and grant - precision >= 300
                        and GRANT_SECONDS - elapsed - precision - 2 < grant <= GRANT_SECONDS,
                        'expired-daily:original-grant-preserved')
                self.saved_policy = policy
                self.original_sample = (deepcopy(balance), tuple(self.ui.read_bounds))
                observed['comparison'] = {'daily_dominant_original_grant': True,
                                          'original_grant_margin_seconds': grant - precision}
            else:
                require(policy == self.saved_policy, 'expired-daily:policy-changed')
                require(time.monotonic_ns() > self.original_deadline_ns and grant == 0,
                        'expired-daily:original-grant-not-expired')
                self.expired_balance = deepcopy(balance)
                observed['comparison'] = {'daily_positive_original_grant_expired': True,
                                          'saved_policy_unchanged': True}
        if stage == 'original-session':
            self.original_session = observed['system']['session_sha256']
        if stage == 'replacement-child-entry-guard' and self.plan.activity_entries:
            require(self.original_session is not None
                    and observed['system']['session_sha256'] == self.original_session,
                    'expired-daily:retained-session-replaced')
            observed['comparison'] = {'same_retained_child_session': True}
        if stage == 'departure-desktop' or (stage == 'daily-parent-leave-desktop'
                                            and self.plan.activity_entries):
            # Refuse the departure if navigation consumed the original grant.
            require(self.original_sample is not None, 'expired-daily:missing-original-sample')
            balance, bounds = self.original_sample
            remaining = (balance['one_time']['seconds'] - balance['one_time']['precision_seconds']
                         - (time.monotonic_ns() - bounds[0]) / 1e9)
            require(remaining > 0, 'expired-daily:departure-after-expiry')
        if stage == 'new-estimate':
            value = observed['ui']['valid_choice']
            require(all(value['request'][key] == expected for key, expected in {
                    'child': 'fixture-child', 'approver': 'fixture-parent',
                    'duration_seconds': RECOVERY_SECONDS,
                    'allow_soft': self.plan.kiosk_request[3]}.items())
                    and value['estimate']['kind'] == 'fixed'
                    and value['estimate']['seconds'] > RECOVERY_SECONDS + 900,
                    'expired-daily:replacement-choices')
            require(self.expired_balance is not None, 'expired-daily:missing-expired-balance')
            daily = self.expired_balance['daily']
            require(abs(value['estimate']['seconds'] - daily['seconds'] - RECOVERY_SECONDS)
                    <= daily['precision_seconds'], 'expired-daily:replacement-arithmetic')
            self.replacement_estimate = deepcopy(value['estimate'])
            self.replacement_started = value['observed_monotonic_ns']
        if stage == 'replacement-countdown':
            require(self.replacement_estimate is not None, 'expired-daily:missing-replacement')
            value = CountdownObservation.from_value(observed['ui']['countdown'], present=True)
            observed['comparison'] = check_countdown_balance(value,
                seconds=self.replacement_estimate['seconds'],
                precision_seconds=1,
                observed_monotonic_ns=self.replacement_started, max_elapsed_seconds=300)

    @staticmethod
    def remaining_interval(journey, guard):
        require(journey.original_deadline_ns is not None, 'expired-daily:missing-deadline')
        return interval_toward(journey, guard, journey.original_deadline_ns)


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-025/excluded-new-login'
    record_installed_journey(recorder, context, PLAN, timeout=3000,
                             journey_type=ExpiredDailyReplacementJourney)


def execute_retained(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-025/excluded-retained-unlock'
    record_installed_journey(recorder, context, RETAINED_PLAN, timeout=3000,
                             journey_type=ExpiredDailyReplacementJourney)


def execute_included(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-025/included-new-login'
    record_installed_journey(recorder, context, INCLUDED_PLAN, timeout=3000,
                             journey_type=ExpiredDailyReplacementJourney)


def execute_retained_included(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-025/included-retained-unlock'
    record_installed_journey(recorder, context, RETAINED_INCLUDED_PLAN, timeout=3000,
                             journey_type=ExpiredDailyReplacementJourney)


E2E_CASES = {'excluded-new-login': execute, 'excluded-retained-unlock': execute_retained,
             'included-new-login': execute_included,
             'included-retained-unlock': execute_retained_included}
