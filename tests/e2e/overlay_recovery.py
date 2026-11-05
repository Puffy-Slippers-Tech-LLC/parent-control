"""Case 34: failed approvals preserve time, app blocks and remembered choices."""
from functools import partial

from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from feedback_composition import text_fragment
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, fresh_desktop, native_activity_entry,
                            native_usable_app, overlay_entry, parent_management,
                            prefixed_stages, retained_parent_entry)
from native_fixtures import fixture_actions
from policy_edits import policy_edit
from request_composition import GrantAppEffectsJourney
from request_flow import (CHOICES, overlay_approved_request, overlay_rejected_request,
                          prepared_request)


SETUP = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'apps-page': 'ui:parent-apps-page',
    **policy_edit(MATCH_APPS['H'], 'match-hard-precise', 'permanent', 'hard', setup=True),
    **policy_edit(MATCH_APPS['S'], 'match-soft-wildcard', 'conditional', 'soft', setup=True),
    **text_fragment('catalogue-clear', 'setup-clear'),
    'saved-policy': 'ui:revoke-saved-balances',
    'switch-ready': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **prefixed_stages('child-entry', desktop_entry('child', source='gdm', entry='fresh')),
    **native_activity_entry('activity', desktop_observation=False),
    **overlay_entry('entry', 'command'),
    **prepared_request(prefix='open', entry='open', initial='default', surface='overlay', **CHOICES),
}
FAILURES = {
    outcome: {
        **({**overlay_entry('entry', 'command', form_operation='overlay-valid-fraction-soft-read')}
           if outcome == 'cancel' else {}),
        **overlay_rejected_request(outcome=outcome, fresh_estimate=True, **CHOICES),
        'form-cancel': 'ui:overlay-request-cancel', 'returned': 'ui:overlay-desktop',
        'hard-denied': 'ui:overlay-native-hard-command-blocked',
        'soft-denied': 'ui:overlay-native-soft-command-blocked',
    } for outcome in ('rejection', 'cancel')
}
APPROVAL = {
    **overlay_entry('entry', 'command', form_operation='overlay-valid-fraction-soft-read'),
    'open-estimate': 'ui:overlay-fraction-estimate-refresh',
    **overlay_approved_request(exit='immediate', **CHOICES),
}
PARENT_RETURN = prefixed_stages('parent-return', desktop_entry('parent', source='gdm', entry='retained'))
SUCCESS = {
    **prefixed_stages('overlay-approval', APPROVAL),
    'approved-activity': 'ui:overlay-native-activity',
    'approved-activity-submit': 'ui:overlay-native-resubmit',
    'approved-activity-submitted': 'ui:overlay-native-submitted',
    'activity-close': 'ui:overlay-native-close', 'activity-closed': 'ui:overlay-native-closed',
    'approved-countdown': 'ui:child-countdown-present',
    **prefixed_stages('soft-use', native_usable_app('command', child='child', role='S', desktop_observation=False)),
    'soft-close': 'ui:overlay-native-soft-close', 'soft-closed': 'ui:overlay-native-soft-closed',
    'hard-denied': 'ui:overlay-native-hard-command-blocked',
    'child-switch-ready': 'ui:fresh-child-desktop', 'child-switch': 'system:child-switch-user',
    'child-greeter': 'ui:gdm-returned', **PARENT_RETURN,
    **prefixed_stages('supplied', retained_parent_entry(source='same-user', desktop_observation=False)),
    'approved-policy': 'ui:revoke-saved-balances',
}
SCREENS = {**SETUP,
           **prefixed_stages('overlay-rejection', FAILURES['rejection']),
           **prefixed_stages('overlay-cancel', FAILURES['cancel']), **SUCCESS}
_logins = set(prefixed_stages('child-entry', fresh_desktop('child'))) | set(PARENT_RETURN)
PLAN = JourneyPlan(
    # Reuse the qualified, single-use Riley/Jamie/75-second credential scopes.
    prefix='baseline-journey', worker_mode='overlay_recovery', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: phase for phase, screens in (
                ('step-1', SETUP),
                ('step-2', prefixed_stages('overlay-rejection', FAILURES['rejection'])),
                ('step-3', prefixed_stages('overlay-cancel', FAILURES['cancel'])),
                ('step-4', SUCCESS)) for stage in screens}, 'installed-greeter': 'start'},
    advance_after={'open-estimate': 'step-2', 'overlay-rejection-soft-denied': 'step-3',
                   'overlay-cancel-soft-denied': 'step-4'},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={stage: 'child' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    invocations=tuple(stage for stage, tag in SCREENS.items()
                      if tag.startswith('ui:') and (stage in _logins or stage in (
                          'entry-launch', 'entry-form', 'overlay-cancel-entry-launch',
                          'overlay-cancel-entry-form', 'overlay-approval-entry-launch',
                          'overlay-approval-entry-form'))),
    challenges={
        'child-entry': ('child', 'child-entry-child-recipient-qualified', 'child-entry-child-recipient-rechecked'),
        'parent-return': ('parent', 'parent-return-recipient-qualified', 'parent-return-recipient-rechecked')},
    balance_checks={'allowance-configured': 1800},
    request_checks={
        **{f'overlay-{outcome}-flow-preserved': (f'overlay-{outcome}-flow-before',
            'overlay-recovery:changed-failed-request', 'preserved_choices') for outcome in FAILURES},
        **{f'overlay-{outcome}-entry-form': ('open-estimate',
            'overlay-recovery:changed-remembered-request', 'remembered_choices')
           for outcome in ('cancel', 'approval')}},
    activity_checks={'approved-activity': ('activity-capture', 'same')},
    countdown_checks={'approved-countdown': ('overlay-approval-open-estimate', 'estimate', 1, 300)},
    assertions_after={'overlay-rejection-soft-denied': 'wrong-password-result',
                      'overlay-cancel-soft-denied': 'cancel-result',
                      'approved-policy': 'visible-result'},
)


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-013/child-overlay-recovery'
    record_installed_journey(recorder, context, PLAN, timeout=1800,
        actions=fixture_actions(include_refusal=False),
        journey_type=partial(GrantAppEffectsJourney,
            settings={'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['30 minutes']},
            app_rules={MATCH_APPS[role]: (access, MATCH_RULES[index])
                       for role, access, index in (('A', 'allowed', 0), ('H', 'permanent', 3), ('S', 'conditional', 4))},
            approval_stage='overlay-approval-open-estimate',
            policy_reads={'saved-policy': (None, 'zero'), 'approved-policy': ('saved-policy', 'positive')},
            approval_stages={'approved-policy': 'overlay-approval-open-estimate'},
            negative_estimates={f'overlay-{outcome}-flow-preserved': f'overlay-{outcome}-flow-before'
                                for outcome in FAILURES}, daily_seconds=1800))


E2E_CASES = {'child-overlay-recovery': execute}
