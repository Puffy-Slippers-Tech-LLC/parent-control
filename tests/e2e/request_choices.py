"""REQUEST08 disabled-child qualification; complete case 57 remains separate."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, station_entry


SCREENS = {
    **fresh_desktop('parent'),
    'parent-command': 'ui:parent-command-launch',
    'parent-window': 'ui:parent-window',
    'child-picker-opened': 'ui:child-picker-opened',
    'child-choice-highlighted': 'ui:child-choice-highlighted',
    'parent-selected': 'ui:parent-selected',
    'wrong-entry': 'ui:parent-kiosk-refused',
    'limit-enabled': 'ui:parent-toggle-enabled',
    'save-enabled': 'ui:parent-save-enabled',
    'limit-disabled': 'ui:parent-toggle-disabled',
    'save-disabled': 'ui:parent-save-disabled',
    'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **station_entry(),
    'request-form': 'ui:kiosk-request-form',
    'wrong-choices': 'ui:kiosk-choice-refusals',
    'child-selected': 'ui:kiosk-disabled-child-select',
    'availability-read': 'ui:kiosk-disabled-form',
}
PLAN = JourneyPlan(
    prefix='request-choices', worker_mode='request_choices', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS},
            'installed-greeter': 'start',
            **{stage: 'step-2' for stage in list(SCREENS)[list(SCREENS).index('switch-user'):]}},
    advance_after={'save-disabled': 'step-2'},
)


class RequestChoicesJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
