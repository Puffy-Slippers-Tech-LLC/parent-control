"""Case 36: two failed station approvals preserve restrictions before recovery."""
from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS, countdown_seconds
from approval_flow import rejected_request
from feedback_composition import text_fragment
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, fresh_desktop, native_usable_app,
                            parent_management, prefixed_stages, rejected_gdm_return,
                            retained_parent_entry, station_entry)
from kiosk_approved_flow import approved_request
from native_fixtures import fixture_actions
from policy_edits import policy_edit
from private_artifacts import require
from request_composition import GrantAppEffectsJourney
from request_flow import CHOICES, continued_request, prepared_request


ENTRIES = {
    **{outcome + '-child': prefixed_stages(outcome + '-child', desktop_entry(
        'child', source='gdm', entry='fresh', expected='time-denied'))
       for outcome in ('rejection', 'cancel')},
    **{prefix: prefixed_stages(prefix, desktop_entry('parent', source='gdm', entry='retained'))
       for prefix in ('rejection-parent', 'cancel-parent', 'approved-parent')},
    'approved-child': prefixed_stages('approved-child', desktop_entry(
        'child', source='gdm', entry='fresh')),
}
SETUP = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
    'apps-page': 'ui:parent-apps-page',
    **policy_edit(MATCH_APPS['H'], 'match-hard-precise', 'permanent', 'hard', setup=True),
    **policy_edit(MATCH_APPS['S'], 'match-soft-wildcard', 'conditional', 'soft', setup=True),
    **text_fragment('catalogue-clear', 'setup-clear'),
    'saved-policy': 'ui:revoke-saved-balances',
    'setup-switch-ready': 'ui:desktop', 'setup-switch': 'system:parent-switch-user',
    'setup-greeter': 'ui:gdm-returned',
    **prefixed_stages('kiosk-rejection', prepared_request(
        prefix='open', entry='new', initial='default', compact=True, **CHOICES)),
}
FAILURES = {}
for outcome, next_scope in (('rejection', 'kiosk-cancel'), ('cancel', 'kiosk-final')):
    FAILURES[outcome] = {
        **prefixed_stages('kiosk-' + outcome, {
            **rejected_request(outcome=outcome, **CHOICES),
            'form-cancel': 'ui:kiosk-request-cancel', 'form-returned': 'ui:gdm-station-returned'}),
        **ENTRIES[outcome + '-child'],
        **prefixed_stages(outcome + '-child', rejected_gdm_return()),
        **ENTRIES[outcome + '-parent'],
        **prefixed_stages(outcome + '-supplied', retained_parent_entry(
            source='same-user', desktop_observation=False)),
        outcome + '-policy': 'ui:revoke-saved-balances',
        outcome + '-switch': 'system:parent-switch-user', outcome + '-greeter': 'ui:gdm-returned',
        **prefixed_stages(next_scope, station_entry()),
        next_scope + '-remembered': 'ui:kiosk-valid-fraction-soft-read',
    }
SUCCESS = {
    **prefixed_stages('kiosk-final', {
        **continued_request(surface='kiosk', initial_seconds=75, duration_seconds=1200),
        **approved_request(**{**CHOICES, 'duration_seconds': 1200}, exit='automatic')}),
    **ENTRIES['approved-child'], 'child-countdown': 'ui:child-countdown-present',
    **prefixed_stages('soft-use', native_usable_app(
        'command', child='child', role='S', desktop_observation=False)),
    'soft-close': 'ui:overlay-native-soft-close', 'soft-closed': 'ui:overlay-native-soft-closed',
    'hard-denied': 'ui:overlay-native-hard-command-blocked',
    'child-switch-ready': 'ui:fresh-child-desktop', 'child-switch': 'system:child-switch-user',
    'child-greeter': 'ui:gdm-returned', **ENTRIES['approved-parent'],
    **prefixed_stages('approved-supplied', retained_parent_entry(
        source='same-user', desktop_observation=False)),
    'approved-policy': 'ui:revoke-saved-balances',
}
SCREENS = {**SETUP, **FAILURES['rejection'], **FAILURES['cancel'], **SUCCESS}
_entries = {stage for fragment in ENTRIES.values() for stage in fragment}
_returns = {stage for outcome in FAILURES for stage in prefixed_stages(
    outcome + '-child', rejected_gdm_return())}
PLAN = JourneyPlan(
    prefix='baseline-journey', worker_mode='kiosk_recovery', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: phase for phase, screens in (
                ('step-1', SETUP), ('step-2', FAILURES['rejection']),
                ('step-3', FAILURES['cancel']), ('step-4', SUCCESS)) for stage in screens},
            'installed-greeter': 'start'},
    advance_after={'kiosk-rejection-open-estimate': 'step-2',
                   'kiosk-cancel-remembered': 'step-3', 'kiosk-final-remembered': 'step-4'},
    stage_actions={'desktop': 'native-verify'},
    invocations=tuple(stage for stage, tag in SCREENS.items()
                      if tag.startswith('ui:') and stage in _entries | _returns),
    challenges={prefix: ('child' if prefix.endswith('-child') else 'parent',
        prefix + ('-child-recipient-qualified' if prefix.endswith('-child') else '-recipient-qualified'),
        prefix + ('-child-recipient-rechecked' if prefix.endswith('-child') else '-recipient-rechecked'))
        for prefix in ENTRIES},
    child_bindings={stage: 'child' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    balance_checks={'allowance-configured': 0},
    request_checks={
        **{'kiosk-' + outcome + '-flow-preserved': ('kiosk-' + outcome + '-flow-before',
            'kiosk-recovery:changed-failed-request', 'preserved_choices') for outcome in FAILURES},
        **{stage: ('kiosk-rejection-open-estimate',
            'kiosk-recovery:changed-remembered-request', 'remembered_choices') for stage in (
                'kiosk-cancel-remembered', 'kiosk-final-remembered', 'kiosk-final-new-form')}},
    countdown_checks={'child-countdown': ('kiosk-final-new-estimate', 1200, 1, 300)},
    assertions_after={'kiosk-cancel-remembered': 'wrong-password-result',
                      'kiosk-final-remembered': 'cancel-result', 'approved-policy': 'visible-result'},
)


class KioskRecoveryJourney(GrantAppEffectsJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions,
            settings={'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['0 minutes']},
            app_rules={MATCH_APPS[role]: (access, MATCH_RULES[index])
                       for role, access, index in (
                           ('A', 'allowed', 0), ('H', 'permanent', 3), ('S', 'conditional', 4))},
            approval_stage='kiosk-final-new-estimate', policy_reads={
                'saved-policy': (None, 'zero'), 'rejection-policy': ('saved-policy', 'zero'),
                'cancel-policy': ('saved-policy', 'zero'), 'approved-policy': ('saved-policy', 'positive')})

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'child-countdown':
            require(countdown_seconds(self.countdowns[stage].text)[0] >= 300,
                    'kiosk-recovery:child-return-margin')


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-013/kiosk-recovery'
    record_installed_journey(recorder, context, PLAN, timeout=1800,
        actions=fixture_actions(include_refusal=False), journey_type=KioskRecoveryJourney)


E2E_CASES = {'kiosk-recovery': execute}
