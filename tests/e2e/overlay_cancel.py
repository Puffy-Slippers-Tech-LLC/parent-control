"""Case 44: Cancel one prepared overlay and resume the original child activity."""

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management, native_usable_app, overlay_entry
from native_fixtures import fixture_actions
from request_flow import prepared_request
from request_composition import KioskRequestJourney


EXIT_SCREENS = {
    'cancel': 'ui:overlay-request-cancel',
    'cancel-returned': 'ui:overlay-desktop',
    'activity-returned': 'ui:overlay-native-activity',
    'resumed-opened': 'ui:overlay-native-activity',
    'resumed-submit': 'ui:overlay-native-resubmit',
    'resumed-submitted': 'ui:overlay-native-submitted',
    'activity-close': 'ui:overlay-native-close',
    'activity-closed': 'ui:overlay-native-closed',
}
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-positive-read',
    'repeat-desktop': 'ui:desktop',
    'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
    **{'activity-' + stage: operation for stage, operation in
       native_usable_app('command', child='child').items()},
    'activity-capture': 'ui:overlay-native-activity',
    **overlay_entry('direct', 'command'),
    **prepared_request(prefix='open', entry='open', initial='default',
                       child='fixture-child', approver='fixture-parent',
                       duration_seconds=75, allow_soft=True, surface='overlay'),
    **EXIT_SCREENS,
}
PLAN = JourneyPlan(
    prefix='overlay-cancel', worker_mode='overlay_cancel', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in EXIT_SCREENS}},
    advance_after={'open-estimate': 'step-2'},
    stage_actions={'desktop': 'native-verify'},
    invocations=(*fresh_desktop('parent'),
                 *tuple('fresh-' + stage for stage in fresh_desktop('child')),
                 'direct-launch', 'direct-form'),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
    },
    balance_checks={'allowance-configured': 900},
    activity_checks={stage: ('activity-capture', 'same')
                     for stage in ('activity-returned', 'resumed-opened')},
    assertions_after={'resumed-submitted': 'visible-result'},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=KioskRequestJourney,
                             actions=fixture_actions(include_refusal=False))


E2E_CASES = {'child-overlay-cancel': execute}
