"""Case 57: inspect unavailable station requests with limits off throughout."""

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management, station_entry
from ui_observations import SettingsObservation


ENTRY = {
    **fresh_desktop('parent'),
    **parent_management(),
    'save-disabled': 'ui:parent-save-disabled',
    'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **station_entry(),
    'request-form': 'ui:kiosk-request-form',
}
CHOICES = {
    'child-choices-open': 'ui:kiosk-child-choices-open',
    'child-choices-closed': 'ui:kiosk-child-choices-closed',
    'child-selected': 'ui:kiosk-disabled-child-select',
}
RESULT = {
    'availability-read': 'ui:kiosk-disabled-form',
    'cancel-action': 'ui:kiosk-request-cancel',
    'cancel-returned': 'ui:gdm-station-returned',
}
PLAN = JourneyPlan(
    prefix='disabled-child', worker_mode='disabled_child',
    screen_tags={**ENTRY, **CHOICES, **RESULT},
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in ENTRY},
            'installed-greeter': 'start',
            **{stage: 'step-2' for stage in CHOICES},
            **{stage: 'step-3' for stage in RESULT}},
    advance_after={'installed-greeter': 'step-1',
                   'request-form': 'step-2', 'child-selected': 'step-3'},
    settings_checks={'parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',))},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800)


E2E_CASES = {'disabled-child': execute}
