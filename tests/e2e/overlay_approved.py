"""Case 46: Cancel, surface close and approved exit preserve the same work."""

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (fresh_desktop, parent_management, native_activity_entry,
                            native_activity_resume, prefixed_stages)
from native_fixtures import fixture_actions
from request_flow import prepared_request, overlay_approved_request
from request_composition import KioskRequestJourney


RETURN_SCREENS = {
    'resumed-opened': 'ui:overlay-native-activity',
    'resumed-submit': 'ui:overlay-native-resubmit',
    'resumed-submitted': 'ui:overlay-native-submitted',
    'countdown': 'ui:child-countdown-present',
    'activity-close': 'ui:overlay-native-close',
    'activity-closed': 'ui:overlay-native-closed',
}
EXIT_SCREENS = {}
for prefix, initial, exit_stages in (
        ('cancel-exit', 'default', {'cancel': 'ui:overlay-request-cancel',
                                  'cancel-returned': 'ui:overlay-desktop'}),
        ('close-exit', 'selected', {'escape-ready': 'ui:overlay-request-escape-ready',
                                  'escape-returned': 'ui:overlay-desktop'})):
    EXIT_SCREENS.update(prefixed_stages(prefix, {
        **prepared_request(prefix='open', entry='new', initial=initial,
                           child='fixture-child', approver='fixture-parent',
                           duration_seconds=75, allow_soft=True, surface='overlay'),
        **exit_stages, **native_activity_resume('resumed', child='child'),
    }))
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-positive-read',
    'repeat-desktop': 'ui:desktop',
    'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
    **native_activity_entry('activity'),
    **EXIT_SCREENS,
    **prepared_request(prefix='open', entry='new', initial='selected',
                       child='fixture-child', approver='fixture-parent',
                       duration_seconds=75, allow_soft=True, surface='overlay'),
    **overlay_approved_request(child='fixture-child', approver='fixture-parent',
                               duration_seconds=75, allow_soft=True, exit='immediate'),
    **RETURN_SCREENS,
}
PLAN = JourneyPlan(
    prefix='overlay-approved-exit', worker_mode='overlay_approved', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-4' for stage in SCREENS
               if stage.startswith('open-') or stage.startswith('approval-')
               or stage == 'returned' or stage in RETURN_SCREENS},
            **{stage: 'step-2' if stage.startswith('cancel-exit-') else 'step-3'
               for stage in EXIT_SCREENS}},
    advance_after={'activity-capture': 'step-2',
                   'cancel-exit-resumed-submitted': 'step-3',
                   'close-exit-resumed-submitted': 'step-4'},
    stage_actions={'desktop': 'native-verify'},
    invocations=(*fresh_desktop('parent'),
                 *tuple('fresh-' + stage for stage in fresh_desktop('child')),
                 *(stage for stage in SCREENS
                   if stage.endswith(('open-entry-launch', 'open-entry-form')))),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
    },
    balance_checks={'allowance-configured': 900},
    activity_checks={stage: ('activity-capture', 'same') for stage in (
        'cancel-exit-resumed-opened', 'close-exit-resumed-opened', 'resumed-opened')},
    countdown_checks={'countdown': ('open-estimate', 'estimate', 1, 180)},
    assertions_after={'cancel-exit-resumed-submitted': 'cancel-result',
                      'close-exit-resumed-submitted': 'close-result',
                      'countdown': 'visible-result'},
)


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    # Approved exit must resume the same activity captured before the request.
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-015/child-overlay-approved'
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=KioskRequestJourney,
                             actions=fixture_actions(include_refusal=False))


E2E_CASES = {'child-overlay-approved': execute}
