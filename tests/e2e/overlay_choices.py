"""048a: overlay FLOW04, invalid submission and distinct Cancel/Escape returns."""
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management, native_usable_app, overlay_entry
from native_fixtures import fixture_actions
from request_flow import prepared_request
from request_composition import KioskRequestJourney

CHOICES = dict(child='fixture-child', approver='fixture-parent', duration_seconds=75,
               allow_soft=True, surface='overlay')
CHILD_SCREENS = {
    **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
    **{'activity-' + stage: operation for stage, operation in native_usable_app('command', child='child').items()},
    'activity-capture': 'ui:overlay-native-activity',
    **overlay_entry('direct', 'command'),
    'wrong-surface-refused': 'ui:overlay-valid-refusals',
    **prepared_request(prefix='open', entry='open', initial='default', **CHOICES),
    'cancel': 'ui:overlay-request-cancel', 'cancel-returned': 'ui:overlay-desktop',
    'activity-cancel': 'ui:overlay-native-activity',
    **prepared_request(prefix='new', entry='new', initial='selected', **CHOICES),
    'exclude-soft': 'ui:overlay-valid-fraction-excluded-select',
    'excluded-read': 'ui:overlay-valid-fraction-excluded-read',
    **{operation: 'ui:' + operation for binding in ('below',)
       for operation in (
           *tuple('text-overlay-invalid-' + binding + '-' + action for action in ('focus', 'selected', 'read')),
           *tuple('overlay-invalid-' + binding + '-' + action for action in ('ready', 'submit', 'read')))},
    'escape-ready': 'ui:overlay-request-escape-ready', 'escape-returned': 'ui:overlay-desktop',
    'activity-escape': 'ui:overlay-native-activity',
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
    prefix='overlay-choices', worker_mode='overlay_choices', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in CHILD_SCREENS}},
    advance_after={'gdm-switched': 'step-2'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    invocations=(*fresh_desktop('parent'),
                 *tuple('fresh-' + stage for stage in fresh_desktop('child')),
                 'direct-launch', 'direct-form', 'new-entry-launch', 'new-entry-form'),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
    },
    balance_checks={'allowance-configured': 900},
    request_checks={'new-estimate': ('open-estimate', 'overlay-flow:reproduced-choices', 'reproduced_choices')},
    activity_checks={'activity-cancel': ('activity-capture', 'same'),
                     'activity-escape': ('activity-capture', 'same')},
    assertions_after={'open-estimate': 'open-flow-estimate', 'activity-cancel': 'cancel-same-activity',
                      'new-estimate': 'new-flow-reproduced', 'overlay-invalid-below-read': 'invalid-no-authentication',
                      'activity-escape': 'escape-same-activity'},
)


class OverlayChoicesJourney(KioskRequestJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
                         actions=fixture_actions() if actions is None else actions)
