"""048d: fixed Shell approval, explicit success and the original child activity."""
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management, native_usable_app, overlay_entry
from native_fixtures import fixture_actions
from request_flow import prepared_request, overlay_authentication
from request_composition import KioskRequestJourney

CHILD_SCREENS = {
    **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
    **{'activity-' + stage: operation for stage, operation in native_usable_app('command', child='child').items()},
    'activity-capture': 'ui:overlay-native-activity',
    **overlay_entry('direct', 'command'),
    'wrong-surface-refused': 'ui:overlay-valid-refusals',
    **prepared_request(prefix='open', entry='open', initial='default',
                       child='fixture-child', approver='fixture-parent', duration_seconds=75,
                       allow_soft=True, surface='overlay'),
    **overlay_authentication(result='approval', prefix='approval'),
    'returned': 'ui:overlay-desktop',
    'activity-returned': 'ui:overlay-native-activity',
    'activity-close': 'ui:overlay-native-close', 'activity-closed': 'ui:overlay-native-closed',
}
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-positive-read',
    'wrong-account-refused': 'ui:overlay-wrong-account-refused',
    'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned', **CHILD_SCREENS,
}
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


class OverlayApprovedExitJourney(KioskRequestJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
                         actions=fixture_actions() if actions is None else actions)
