"""Cases 17/19: Cancel keeps work; Confirm revokes only the selected child's grant."""
from copy import deepcopy
from dataclasses import replace

from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (allowance_selection, desktop_entry, fresh_desktop,
                            native_activity_entry, native_activity_resume, native_blocked_app,
                            parent_management, prefixed_stages,
                            rejected_gdm_return, retained_app_activities, retained_app_visit,
                            retained_parent_entry)
from journey_checks import RetainedDesktopJourney, require_zero_grant
from kiosk_approved_flow import obtain_time
from named_app_set import named_app_set
from native_fixtures import fixture_actions
from policy_edits import AppPolicyJourney
from private_artifacts import require
from request_composition import KioskRequestJourney


APPS = ((MATCH_APPS['A'], 'match-precise', 'allowed'),
        (MATCH_APPS['H'], 'match-hard-precise', 'permanent'),
        (MATCH_APPS['S'], 'match-soft-precise', 'conditional'))
CHOICES = dict(child='existing-fixture-child', approver='fixture-parent',
               duration_seconds=1200, allow_soft=True)
PREPARATION = {
    **fresh_desktop('parent'), **parent_management(child='existing'),
    'initial-balance': 'ui:time-explanation-reach-read',
    'enable': 'ui:parent-toggle-enabled', **allowance_selection('zero', (0,)),
    'zero-balance': 'ui:time-explanation-refresh-read',
    **named_app_set(source='desktop', entry='same-user', window='retained',
                    child='existing', apps=APPS, prefix='rules'),
    **retained_app_activities((('riley', 'child', 'fresh'),)),
    **prefixed_stages('request', obtain_time(initial='observed', **CHOICES, exit='automatic')),
    **prefixed_stages('jordan', desktop_entry('other-child', source='gdm', entry='fresh')),
    **native_activity_entry('allowed', child='other-child', binding='policy'),
    **native_activity_entry('soft', child='other-child', binding='unmatched-soft'),
    'jordan-desktop-identity': 'system:standard-entry-same',
    **prefixed_stages('parent-before', desktop_entry('parent', source='desktop',
        entry='retained', source_account='other-child')),
    **prefixed_stages('supplied', retained_parent_entry(source='same-user', desktop_observation=False)),
    'before': 'ui:revoke-saved-balances',
}
CANCEL = {
    'cancel-open': 'ui:revoke-open', 'cancel': 'ui:revoke-cancel',
    'cancel-balance': 'ui:revoke-saved-balances',
    **retained_app_visit('cancel-child', account='other-child', source='desktop', source_account='parent'),
    'cancel-child-activity-opened': 'ui:native-policy-activity',
    'cancel-soft': 'ui:native-unmatched-soft-activity',
    'cancel-soft-submit': 'ui:native-unmatched-soft-resubmit',
    'cancel-soft-submitted': 'ui:native-unmatched-soft-submitted',
    **prefixed_stages('parent-confirm', desktop_entry('parent', source='desktop',
        entry='retained', source_account='other-child')),
    'confirm-before': 'ui:revoke-saved-balances',
}
CONFIRM = {
    'confirm-open': 'ui:revoke-open', 'confirm': 'ui:revoke-confirm',
    'confirmed-balance': 'ui:revoke-cleared-balances',
    **prefixed_stages('denied-child', desktop_entry('other-child', source='desktop',
        entry='retained', expected='time-denied', source_account='parent')),
    **rejected_gdm_return(),
    **retained_app_visit('riley-return', account='child', source='gdm'),
    'riley-usable': 'ui:overlay-native-activity',
}
SCREENS = {**PREPARATION, **CANCEL, **CONFIRM}
LOGINS = {'': 'parent', 'riley-': 'child', 'jordan-': 'other-child',
          'parent-before-': 'parent',
          'cancel-child-': 'other-child', 'parent-confirm-': 'parent',
          'denied-child-': 'other-child', 'riley-return-': 'child'}
LOGIN_STAGES = {prefix + stage for prefix, account in LOGINS.items()
                for stage in fresh_desktop(account, 'time-denied' if prefix == 'denied-child-' else 'success')}
ACTIVITIES = {
    'cancel-child-activity-opened': ('allowed-capture', 'same'),
    'cancel-soft': ('soft-capture', 'same'),
    'riley-return-activity-opened': ('riley-activity-capture', 'same'),
    'riley-usable': ('riley-activity-capture', 'same'),
}
PLAN = JourneyPlan(
    prefix='revocation-case', worker_mode='revocation_case', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in PREPARATION}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in CANCEL}, **{stage: 'step-3' for stage in CONFIRM}},
    advance_after={'installed-greeter': 'step-1', 'before': 'step-2', 'confirm-before': 'step-3'},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    match_checks={'rules-saved-' + role.lower() + '-match': (MATCH_APPS[role], MATCH_RULES[index])
                  for role, index in (('A', 0), ('H', 3), ('S', 5))},
    access_checks={'rules-saved-' + role.lower() + '-access': (MATCH_APPS[role], access)
                   for role, access in (('A', 'allowed'), ('H', 'permanent'), ('S', 'conditional'))},
    activity_checks=ACTIVITIES,
    activity_entries={'cancel-child-source-desktop': 'allowed-capture',
                      'riley-return-entry-guard': 'riley-activity-capture'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES or stage in rejected_gdm_return()),
    challenges={('parent-login' if not prefix else prefix.rstrip('-')):
        (account, prefix + recipient + 'qualified', prefix + recipient + 'rechecked')
        for prefix, account in LOGINS.items()
        for recipient in ({'parent': 'recipient-', 'child': 'child-recipient-',
                           'other-child': 'standard-recipient-'}[account],)},
    kiosk_request=('other-child', 'parent', 1200, True),
    assertions_after={'riley-usable': 'visible-result'},
)

# The positive-daily branch keeps the same continuous preparation/Cancel history.
# Confirm returns to the original desktop instead of expecting time-limit denial.
REMAINING_PREPARATION = {
    {'zero-ready': 'daily-ready', 'zero-confirm': 'daily-confirm',
     'zero-balance': 'daily-balance'}.get(stage, stage):
        {'zero-ready': 'ui:allowance-keyboard-30-click',
         'zero-confirm': 'ui:allowance-keyboard-30-selected',
         'soft-capture': 'ui:native-policy-soft-activity'}.get(stage, tag)
    for stage, tag in PREPARATION.items()
}
REMAINING_CANCEL = {stage: 'ui:native-policy-soft-activity' if stage == 'cancel-soft' else tag
                    for stage, tag in CANCEL.items()}
REMAINING_CONFIRM = {
    'confirm-open': 'ui:revoke-open', 'confirm': 'ui:revoke-confirm',
    'confirmed-balance': 'ui:revoke-cleared-balances',
    **prefixed_stages('confirmed-child', desktop_entry('other-child', source='desktop',
        entry='retained', source_account='parent')),
    'confirmed-soft-closed': 'ui:native-policy-soft-closed',
    **native_activity_resume('confirmed-allowed', child='other-child'),
    # The original A activity is a policy activity, not the generic activity fixture.
    **prefixed_stages('denied-hard', native_blocked_app('H')),
    **prefixed_stages('denied-soft', native_blocked_app('S')),
    **retained_app_visit('riley-return', account='child', source='desktop', source_account='other-child'),
    'riley-usable': 'ui:overlay-native-activity',
}
REMAINING_CONFIRM['confirmed-allowed-opened'] = 'ui:native-policy-activity'
REMAINING_SCREENS = {**REMAINING_PREPARATION, **REMAINING_CANCEL, **REMAINING_CONFIRM}
REMAINING_LOGINS = {prefix: account for prefix, account in LOGINS.items() if prefix != 'denied-child-'}
REMAINING_LOGINS['confirmed-child-'] = 'other-child'
REMAINING_LOGIN_STAGES = {prefix + stage for prefix, account in REMAINING_LOGINS.items()
                          for stage in fresh_desktop(account)}
REMAINING_PLAN = replace(PLAN, worker_mode='revocation_remaining_case',
    screen_tags=REMAINING_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in REMAINING_PREPARATION}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in REMAINING_CANCEL},
            **{stage: 'step-3' for stage in REMAINING_CONFIRM}},
    child_bindings={stage: 'existing' for stage, tag in REMAINING_SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    activity_checks={**ACTIVITIES,
        'confirmed-soft-closed': ('soft-capture', 'closed'),
        'confirmed-allowed-opened': ('allowed-capture', 'same')},
    activity_entries={**PLAN.activity_entries, 'confirmed-child-source-desktop': 'allowed-capture'},
    invocations=tuple(stage for stage in REMAINING_SCREENS if stage in REMAINING_LOGIN_STAGES),
    challenges={('parent-login' if not prefix else prefix.rstrip('-')):
        (account, prefix + recipient + 'qualified', prefix + recipient + 'rechecked')
        for prefix, account in REMAINING_LOGINS.items()
        for recipient in ({'parent': 'recipient-', 'child': 'child-recipient-',
                           'other-child': 'standard-recipient-'}[account],)},
)


class RevocationCaseJourney(RetainedDesktopJourney, AppPolicyJourney, KioskRequestJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        self.daily_minutes = 30 if plan.worker_mode == 'revocation_remaining_case' else 0
        allowance = [str(self.daily_minutes) + ' minutes']
        super().__init__(context, progress, plan,
            actions=fixture_actions(include_refusal=False) if actions is None else actions,
            parent_expected={'rules-before': {'page': 'app-limits', 'settings': {
                'child': CHOICES['child'], 'limit_enabled': True, 'allowance': allowance}}},
            parent_checks={'supplied-parent-retained': 'rules-before'}, window_checks={},
            session_checks={'cancel-child-entry-guard': 'jordan-desktop-identity',
                            ('confirmed-child-entry-guard' if self.daily_minutes else
                             'denied-child-entry-guard'): 'jordan-desktop-identity',
                            'riley-return-entry-guard': 'riley-desktop-identity'})
        self.reads = {}
        self.grant_estimate = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'request-new-estimate':
            self.grant_estimate = deepcopy(observed['ui']['valid_choice'])
        if stage in ('initial-balance', 'zero-balance', 'daily-balance'):
            balances = observed['ui']['time_explanation']
            require_zero_grant(balances)
            if stage == 'zero-balance':
                require(balances['daily']['seconds'] == balances['total']['seconds'] == 0,
                        'revocation-case:zero-daily')
                self.balance = deepcopy(balances)
            elif stage == 'daily-balance':
                require(balances['daily']['seconds'] >= 1500,
                        'revocation-case:daily-preparation-margin')
                self.balance = deepcopy(balances)
        if stage not in ('before', 'cancel-balance', 'confirm-before', 'confirmed-balance'):
            return
        value = observed['ui']['revoke_cancel']
        require(value['settings'] == {'child': CHOICES['child'], 'limit_enabled': True,
                                      'allowance': [str(self.daily_minutes) + ' minutes']},
                'revocation-case:saved-settings')
        balances = value['balances']
        daily, grant, total = (balances[key]['seconds'] for key in ('daily', 'one_time', 'total'))
        require((daily >= 900 if self.daily_minutes else daily == 0)
                and abs(total - max(daily, grant)) < balances['total']['precision_seconds'],
                'revocation-case:daily-and-total')
        require(grant == 0 if stage == 'confirmed-balance' else grant > 300,
                'revocation-case:cleared-grant' if stage == 'confirmed-balance' else
                'revocation-case:active-grant-margin')
        if stage == 'before':
            require(self.grant_estimate is not None, 'revocation-case:missing-approval')
            elapsed = (balances['observed_monotonic_ns']
                       - self.grant_estimate['observed_monotonic_ns']) / 1e9
            precision = balances['one_time']['precision_seconds']
            approved = self.grant_estimate['estimate']['seconds']
            require(0 <= elapsed <= 900 and approved - elapsed - precision <= grant <= approved + precision,
                    'revocation-case:approved-balance')
        earlier_stage = {'cancel-balance': 'before', 'confirm-before': 'cancel-balance',
                         'confirmed-balance': 'confirm-before'}.get(stage)
        if earlier_stage:
            earlier = self.reads[earlier_stage]
            require(all(value[key] == earlier[key] for key in ('settings', 'apps', 'rules')),
                    'revocation-case:saved-policy-changed')
            maximum = (value['read_bounds'][1] - earlier['read_bounds'][0]) / 1e9
            old_daily = earlier['balances']['daily']
            daily_precision = old_daily['precision_seconds'] + balances['daily']['precision_seconds']
            require(0 <= maximum <= 900
                    and max(0, old_daily['seconds'] - maximum) - daily_precision <= daily
                    <= old_daily['seconds'] + daily_precision,
                    'revocation-case:daily-balance-changed')
            if stage != 'confirmed-balance':
                minimum = (value['read_bounds'][0] - earlier['read_bounds'][1]) / 1e9
                maximum = (value['read_bounds'][1] - earlier['read_bounds'][0]) / 1e9
                old = earlier['balances']['one_time']
                tolerance = old['precision_seconds'] + balances['one_time']['precision_seconds']
                require(0 <= minimum <= maximum <= 900
                        and max(0, old['seconds'] - maximum) - tolerance <= grant
                        <= max(0, old['seconds'] - minimum) + tolerance,
                        'revocation-case:cancel-changed-grant')
        self.reads[stage] = deepcopy(value)
        observed.setdefault('comparison', {}).update(zero_daily=not self.daily_minutes,
            grant_cleared=stage == 'confirmed-balance', saved_policy_preserved=bool(earlier_stage))


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-007/zero-single'
    record_installed_journey(recorder, context, PLAN, timeout=1800, journey_type=RevocationCaseJourney)


def execute_remaining(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-007/remaining-single'
    record_installed_journey(recorder, context, REMAINING_PLAN, timeout=2400,
                             journey_type=RevocationCaseJourney)


E2E_CASES = {'zero-single': execute, 'remaining-single': execute_remaining}
