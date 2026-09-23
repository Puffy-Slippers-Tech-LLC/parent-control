"""REQUEST04 station account selection qualification; no complete case credit."""

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
    'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **station_entry(),
    'request-form': 'ui:kiosk-request-form',
    'wrong-choices': 'ui:kiosk-choice-refusals',
    'child-selected': 'ui:kiosk-child-select',
    'approver-selected': 'ui:kiosk-approver-select',
    'selections-read': 'ui:kiosk-enabled-form',
}
PLAN = JourneyPlan(
    prefix='kiosk-eligible-choices', worker_mode='kiosk_eligible_choices',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS},
            'installed-greeter': 'start',
            **{stage: 'step-2' for stage in list(SCREENS)[list(SCREENS).index('switch-user'):]}},
    advance_after={'save-enabled': 'step-2'},
)


class KioskEligibleChoicesJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
