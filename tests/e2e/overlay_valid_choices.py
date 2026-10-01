"""048e: finite valid overlay values, independent entry and usable Cancel return."""
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management, native_usable_app, overlay_entry
from native_fixtures import fixture_actions
from request_composition import KioskRequestJourney

CHILD_SCREENS = {
    **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
    **{'activity-' + stage: operation for stage, operation in native_usable_app('command', child='child').items()},
    'activity-capture': 'ui:overlay-native-activity',
    **overlay_entry('direct', 'command'),
    'wrong-surface-refused': 'ui:overlay-valid-refusals',
    **{stage: 'ui:' + stage for stage in (
        'overlay-valid-approver-select', 'overlay-valid-approver-read',
        'overlay-valid-preset-select', 'overlay-valid-preset-read', 'overlay-valid-custom-open',
        'text-overlay-fraction-focus', 'text-overlay-fraction-selected', 'text-overlay-fraction-read',
        'overlay-valid-fraction-read', 'overlay-valid-rest-select', 'overlay-valid-rest-read',
        'overlay-valid-soft-select', 'overlay-valid-soft-read',
        'overlay-valid-excluded-select', 'overlay-valid-excluded-read')},
    'cancel': 'ui:overlay-request-cancel', 'returned-desktop': 'ui:overlay-desktop',
    'activity-returned': 'ui:overlay-native-activity',
    **overlay_entry('independent', 'command', form_operation='overlay-valid-excluded-read'),
    'independent-preset': 'ui:overlay-valid-preset-select',
    'independent-read': 'ui:overlay-valid-preset-read',
    'independent-cancel': 'ui:overlay-request-cancel',
    'independent-desktop': 'ui:overlay-desktop',
    'activity-independent': 'ui:overlay-native-activity',
    'activity-close': 'ui:overlay-native-close', 'activity-closed': 'ui:overlay-native-closed',
}
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-positive-read',
    'wrong-account-refused': 'ui:overlay-wrong-account-refused',
    'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **CHILD_SCREENS,
}
PLAN = JourneyPlan(
    prefix='overlay-valid-choices', worker_mode='overlay_valid_choices', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in CHILD_SCREENS}},
    advance_after={'gdm-switched': 'step-2'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    invocations=(*fresh_desktop('parent'),
                 *tuple('fresh-' + stage for stage in fresh_desktop('child')),
                 'direct-launch', 'direct-form', 'independent-launch', 'independent-form',
                 'independent-preset', 'independent-read', 'independent-cancel',
                 'independent-desktop'),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
    },
    balance_checks={'allowance-configured': 900},
    activity_checks={'activity-returned': ('activity-capture', 'same'),
                     'activity-independent': ('activity-capture', 'same')},
    assertions_after={'overlay-valid-fraction-read': 'fraction-estimate',
                      'overlay-valid-excluded-read': 'valid-choices',
                      'activity-returned': 'same-usable-activity',
                      'activity-independent': 'independent-cancel-activity'},
)


class OverlayValidChoicesJourney(KioskRequestJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
                         actions=fixture_actions() if actions is None else actions)
