"""Case 171: cancelled approval adds no access; a fresh approval still works."""
from copy import deepcopy

from access_choices import AccessChoiceJourney
from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, fresh_desktop, native_blocked_app,
                            native_usable_app, overlay_entry, parent_management,
                            prefixed_stages, retained_parent_entry)
from named_app_set import APPS, named_app_set, saved_rows
from native_fixtures import fixture_actions
from pending_overlay_lock import PendingOverlayLockJourney
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
    **overlay_entry('recovery', 'command', form_operation='overlay-valid-fraction-soft-read'),
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


class OverlayLockCaseJourney(PendingOverlayLockJourney, AccessChoiceJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.approval_estimate = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'child-session-returned':
            require(observed['system']['session_sha256'] == self.child_session,
                    'overlay-lock:child-session-replaced')
        if stage == 'recovery-form':
            self.approval_estimate = deepcopy(observed['ui']['valid_choice'])
        if stage == 'approved-balance':
            after = observed['ui']['time_explanation']
            before = self.approval_estimate
            require(before is not None and after['child'] == before['request']['child'],
                    'overlay-lock:approved-balance-owner')
            elapsed = (after['observed_monotonic_ns'] - before['observed_monotonic_ns']) / 1e9
            grant = after['one_time']['seconds']
            precision = after['one_time']['precision_seconds'] + before['estimate']['precision_seconds']
            require(0 <= elapsed <= 600 and grant > 0
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


E2E_CASES = {'overlay-lock': execute}
