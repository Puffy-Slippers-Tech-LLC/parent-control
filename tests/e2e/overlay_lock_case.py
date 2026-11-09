"""Cases 171–173: interrupted approval adds no access; fresh approval works."""
from copy import deepcopy
from dataclasses import replace

from access_choices import AccessChoiceJourney
from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, fresh_desktop, native_blocked_app,
                            native_usable_app, native_activity_entry, native_activity_resume,
                            overlay_entry, parent_management,
                            prefixed_stages, retained_parent_entry)
from named_app_set import APPS, named_app_set, saved_rows
from native_fixtures import fixture_actions
from request_composition import CancelledRequestJourney, _estimate_read_bounds
from private_artifacts import require
from request_flow import CHOICES, overlay_authentication, overlay_approved_request, prepared_request


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    **named_app_set(source='desktop', entry='same-user', window='retained',
                    child='child', apps=APPS, prefix='rules'),
    **prefixed_stages('fresh', fresh_desktop('child')),
    'child-session-before': 'system:child-desktop-identity',
    **prefixed_stages('initial-hard', native_blocked_app('H', child='child')),
    **prefixed_stages('initial-soft', native_blocked_app('S', child='child')),
    **overlay_entry('direct', 'command'),
    **prepared_request(prefix='open', entry='open', initial='default', surface='overlay', **CHOICES),
    **overlay_authentication(result='lock', prefix='interruption'),
    'form-returned': 'ui:overlay-valid-fraction-soft-read',
    'cancel': 'ui:overlay-request-cancel', 'cancel-returned': 'ui:overlay-desktop',
    **prefixed_stages('return', retained_parent_entry(source='child-desktop')),
    'balance-returned': 'ui:time-explanation-refresh-read',
    'returned-apps': 'ui:parent-apps-page', **saved_rows(APPS, 'returned'),
    **prefixed_stages('child-return', desktop_entry('child', source='desktop', entry='retained',
                                                 source_account='parent')),
    'child-session-returned': 'system:child-desktop-identity',
    **prefixed_stages('cancelled-hard', native_blocked_app('H', child='child')),
    **prefixed_stages('cancelled-soft', native_blocked_app('S', child='child')),
    **overlay_entry('recovery', 'command', form_operation='overlay-fraction-estimate-refresh'),
    **overlay_approved_request(exit='automatic', **CHOICES),
    'countdown': 'ui:child-countdown-present',
    **prefixed_stages('approved-hard', native_blocked_app('H', child='child')),
    **prefixed_stages('approved-soft', native_usable_app('command', child='child', role='S')),
    'soft-close': 'ui:overlay-native-soft-close', 'soft-closed': 'ui:overlay-native-soft-closed',
    **prefixed_stages('final', retained_parent_entry(source='child-desktop')),
    'approved-balance': 'ui:time-explanation-refresh-read',
}
LOGINS = {'fresh': ('child', 'fresh-'), 'return': ('parent', 'return-'),
          'child-return': ('child', 'child-return-'), 'final': ('parent', 'final-')}
LOGIN_STAGES = {*fresh_desktop('parent'),
                *(prefix + stage for account, prefix in LOGINS.values() for stage in fresh_desktop(account))}
STEP2 = tuple(SCREENS).index('interruption-pending-approval')
STEP3 = tuple(SCREENS).index('form-returned')
PLAN = JourneyPlan(
    prefix='overlay-lock-case', worker_mode='overlay_lock_case', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' if index < STEP2 else 'step-2' if index < STEP3 else 'step-3'
               for index, stage in enumerate(SCREENS)}, 'installed-greeter': 'start'},
    advance_after={'open-estimate': 'step-2', 'interruption-dismissed': 'step-3'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES
                     or stage in ('direct-launch', 'direct-form', 'recovery-launch', 'recovery-form')),
    challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        **{name: (account, prefix + ('child-recipient-qualified' if account == 'child' else 'recipient-qualified'),
                  prefix + ('child-recipient-rechecked' if account == 'child' else 'recipient-rechecked'))
           for name, (account, prefix) in LOGINS.items()}},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={stage: 'child' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    balance_checks={'allowance-configured': 1800},
    match_checks={prefix + '-' + role.lower() + '-match': (MATCH_APPS[role], rule)
                  for prefix in ('rules-saved', 'returned')
                  for role, rule in (('A', MATCH_RULES[0]), ('H', MATCH_RULES[3]), ('S', MATCH_RULES[4]))},
    access_checks={prefix + '-' + role.lower() + '-access': (MATCH_APPS[role], choice)
                   for prefix in ('rules-saved', 'returned')
                   for role, choice in (('A', 'allowed'), ('H', 'permanent'), ('S', 'conditional'))},
    overlay_request=('child', 'parent', 75, True),
    request_checks={stage: ('open-estimate', 'overlay-lock:choices-changed', 'preserved_cancelled_choices')
                    for stage in ('form-returned', 'recovery-form')},
    countdown_checks={'countdown': ('recovery-form', 'estimate', 1, 300)},
    assertions_after={'approved-balance': 'visible-result'},
)


# Keep the complete recipes together; only the interruption and retained-work
# endpoints differ. Qualifications continue to own their independent plans.
SWITCH_SCREENS = {}
for stage, operation in SCREENS.items():
    if stage == 'direct-launch':
        SWITCH_SCREENS.update(native_activity_entry('activity', child='child'))
    if stage == 'interruption-pending-approval':
        SWITCH_SCREENS.update(overlay_authentication(result='switch-user', prefix='interruption'))
    if stage.startswith('interruption-'):
        continue
    SWITCH_SCREENS[stage] = operation
    if stage == 'countdown':
        SWITCH_SCREENS.update(native_activity_resume('resumed', child='child'))
        SWITCH_SCREENS.update({'activity-close': 'ui:overlay-native-close',
                               'activity-closed': 'ui:overlay-native-closed'})
SWITCH_STEP2 = tuple(SWITCH_SCREENS).index('interruption-pending-approval')
SWITCH_STEP3 = tuple(SWITCH_SCREENS).index('form-returned')
SWITCH_PLAN = replace(PLAN, prefix='overlay-switch-case', worker_mode='overlay_switch_case',
    screen_tags=SWITCH_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' if index < SWITCH_STEP2 else 'step-2' if index < SWITCH_STEP3 else 'step-3'
               for index, stage in enumerate(SWITCH_SCREENS)}, 'installed-greeter': 'start'},
    invocations=tuple(stage for stage in SWITCH_SCREENS
                      if stage in PLAN.invocations
                      or stage in prefixed_stages('interruption', fresh_desktop('child'))),
    challenges={**PLAN.challenges, 'interruption': ('child', 'interruption-child-recipient-qualified',
                                                   'interruption-child-recipient-rechecked')},
    child_bindings={stage: 'child' for stage, tag in SWITCH_SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    activity_checks={'resumed-opened': ('activity-capture', 'same')})


SIGNOUT_SCREENS = {}
for stage, operation in SCREENS.items():
    if stage == 'interruption-pending-approval':
        SIGNOUT_SCREENS.update(overlay_authentication(result='sign-out', prefix='interruption'))
    if stage.startswith('interruption-'):
        continue
    if stage == 'form-returned':
        SIGNOUT_SCREENS['child-session-after'] = 'system:child-desktop-identity'
        SIGNOUT_SCREENS.update(overlay_entry('reopen', 'command',
            form_operation='overlay-valid-fraction-soft-read'))
        continue
    SIGNOUT_SCREENS[stage] = operation
SIGNOUT_STEP2 = tuple(SIGNOUT_SCREENS).index('interruption-pending-approval')
SIGNOUT_STEP3 = tuple(SIGNOUT_SCREENS).index('child-session-after')
SIGNOUT_PLAN = replace(PLAN, prefix='overlay-signout-case', worker_mode='overlay_signout_case',
    screen_tags=SIGNOUT_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' if index < SIGNOUT_STEP2 else 'step-2' if index < SIGNOUT_STEP3 else 'step-3'
               for index, stage in enumerate(SIGNOUT_SCREENS)}, 'installed-greeter': 'start'},
    invocations=tuple(stage for stage in SIGNOUT_SCREENS
                      if stage in PLAN.invocations
                      or stage in prefixed_stages('interruption', fresh_desktop('child'))
                      or stage in overlay_entry('reopen', 'command')),
    challenges={**PLAN.challenges, 'interruption': ('child', 'interruption-child-recipient-qualified',
                                                   'interruption-child-recipient-rechecked')},
    child_bindings={stage: 'child' for stage, tag in SIGNOUT_SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    request_checks={stage: ('open-estimate', 'overlay-signout:choices-changed', 'preserved_cancelled_choices')
                    for stage in ('reopen-form', 'recovery-form')})


class OverlayLockCaseJourney(CancelledRequestJourney, AccessChoiceJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        signed_out = plan.worker_mode == 'overlay_signout_case'
        super().__init__(context, progress, plan, actions=actions,
            session_checks={stage: 'child-session-before' for stage in (
                ('child-session-after' if signed_out else
                 'interruption-desktop' if 'interruption-desktop' in plan.screen_tags
                 else 'interruption-unlock-session'),
                'child-session-returned')},
            fresh_session=signed_out,
            balance_check=('allowance-configured', 'balance-returned', 1200))
        self.approval_estimate = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'child-session-returned' and self.fresh_session:
            require(self.session_captures[stage] == self.session_captures['child-session-after'],
                    'overlay-signout:replacement-session-changed')
        if stage == 'recovery-form':
            _estimate_read_bounds(observed['ui']['valid_choice'], 'overlay-lock:approval-read-bounds')
            self.approval_estimate = deepcopy(observed['ui']['valid_choice'])
        if stage == 'approved-balance':
            after = observed['ui']['time_explanation']
            before = self.approval_estimate
            require(before is not None and after['child'] == before['request']['child'],
                    'overlay-lock:approved-balance-owner')
            start, end = _estimate_read_bounds(before, 'overlay-lock:approval-read-bounds')
            elapsed = (after['observed_monotonic_ns'] - start) / 1e9
            grant = after['one_time']['seconds']
            precision = after['one_time']['precision_seconds'] + before['estimate']['precision_seconds']
            require(after['observed_monotonic_ns'] >= end and 0 <= elapsed <= 600 and grant > 0
                    and before['estimate']['seconds'] - elapsed - precision <= grant
                    <= before['estimate']['seconds'] + precision,
                    'overlay-lock:approved-time-addition')
            observed.setdefault('comparison', {})['fresh_approval_added_time'] = True


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-039/overlay-lock'
    record_installed_journey(recorder, context, PLAN, timeout=2400,
        actions=fixture_actions(include_refusal=False), journey_type=OverlayLockCaseJourney)


def execute_switch(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-039/overlay-switch'
    record_installed_journey(recorder, context, SWITCH_PLAN, timeout=2400,
        actions=fixture_actions(include_refusal=False), journey_type=OverlayLockCaseJourney)


def execute_signout(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-039/overlay-signout'
    record_installed_journey(recorder, context, SIGNOUT_PLAN, timeout=2400,
        actions=fixture_actions(include_refusal=False), journey_type=OverlayLockCaseJourney)


E2E_CASES = {'overlay-lock': execute, 'overlay-switch': execute_switch,
             'overlay-signout': execute_signout}
