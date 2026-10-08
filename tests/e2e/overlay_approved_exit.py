"""048d: fixed Shell approval, explicit success and the original child activity."""
from dataclasses import replace
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management, native_activity_entry, overlay_entry
from native_fixtures import fixture_actions
from request_flow import prepared_request, overlay_approved_request, overlay_rejected_request, CHOICES
from request_composition import KioskRequestJourney

CHILD_ENTRY_SCREENS = {
    **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
    **native_activity_entry('activity'),
    **overlay_entry('direct', 'command'),
    'wrong-surface-refused': 'ui:overlay-valid-refusals',
    **prepared_request(prefix='open', entry='open', initial='default',
                       child='fixture-child', approver='fixture-parent', duration_seconds=75,
                       allow_soft=True, surface='overlay'),
}
ACTIVITY_RETURN_SCREENS = {
    'activity-returned': 'ui:overlay-native-activity',
    'activity-close': 'ui:overlay-native-close', 'activity-closed': 'ui:overlay-native-closed',
}
CHILD_SCREENS = {**CHILD_ENTRY_SCREENS, **overlay_approved_request(**CHOICES, exit='automatic'),
                 **ACTIVITY_RETURN_SCREENS}
ENTRY_SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-positive-read',
    'wrong-account-refused': 'ui:overlay-wrong-account-refused',
    'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned', **CHILD_ENTRY_SCREENS,
}
SCREENS = {**ENTRY_SCREENS, **overlay_approved_request(**CHOICES, exit='automatic'),
           **ACTIVITY_RETURN_SCREENS}
PLAN = JourneyPlan(
    prefix='overlay-approved-exit', worker_mode='overlay_approved_exit', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS},
            **{stage: 'step-2' for stage in CHILD_SCREENS}, 'installed-greeter': 'start'},
    advance_after={'gdm-switched': 'step-2'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    invocations=(*fresh_desktop('parent'),
                 *tuple('fresh-' + stage for stage in fresh_desktop('child')),
                 'direct-launch', 'direct-form'),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
    },
    balance_checks={'allowance-configured': 900},
    activity_checks={'activity-returned': ('activity-capture', 'same')},
    assertions_after={'approval-open': 'shell-recipient-and-refusals',
                      'approval-success': 'explicit-form-success',
                      'returned': 'automatic-child-return',
                      'activity-returned': 'same-usable-activity'},
)


IMMEDIATE_PLAN = replace(PLAN, worker_mode='overlay_approval_immediate',
    screen_tags={**SCREENS, 'approval-success': 'ui:overlay-approval-immediate'},
    assertions_after={**PLAN.assertions_after, 'returned': 'immediate-child-return'})


FLOW_REJECTION_SCREENS = {
    **ENTRY_SCREENS, **overlay_rejected_request(outcome='rejection', **CHOICES),
    **overlay_approved_request(**CHOICES, exit='automatic'), **ACTIVITY_RETURN_SCREENS,
}
FLOW_REJECTION_PLAN = replace(PLAN, prefix='overlay-approval-flow', worker_mode='overlay_flow_rejection',
    screen_tags=FLOW_REJECTION_SCREENS,
    phases={**PLAN.phases, **{stage: 'step-2' for stage in FLOW_REJECTION_SCREENS if stage not in PLAN.phases}},
    request_checks={'flow-preserved': ('flow-before', 'overlay-flow:changed-form', 'preserved_choices')},
    assertions_after={'flow-preserved': 'rejection-preserved-usable-no-error-form', **PLAN.assertions_after})
FLOW_CANCEL_SCREENS = {
    **ENTRY_SCREENS, **overlay_rejected_request(outcome='cancel', **CHOICES),
    **overlay_approved_request(**CHOICES, exit='immediate'), **ACTIVITY_RETURN_SCREENS,
}
FLOW_CANCEL_PLAN = replace(PLAN, prefix='overlay-approval-flow', worker_mode='overlay_flow_cancel',
    screen_tags=FLOW_CANCEL_SCREENS,
    phases={**PLAN.phases, **{stage: 'step-2' for stage in FLOW_CANCEL_SCREENS if stage not in PLAN.phases}},
    request_checks=FLOW_REJECTION_PLAN.request_checks,
    assertions_after={'flow-preserved': 'cancel-preserved-usable-no-error-form', **IMMEDIATE_PLAN.assertions_after})


class OverlayApprovedExitJourney(KioskRequestJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
                         actions=fixture_actions() if actions is None else actions)
