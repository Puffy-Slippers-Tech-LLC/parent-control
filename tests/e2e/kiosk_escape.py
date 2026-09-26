"""Case 48: prepare one kiosk request and Escape back to usable GDM."""

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management, station_entry
from kiosk_valid_duration import KioskValidDurationJourney
from request_flow import prepared_request


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'limit-enabled': 'ui:parent-toggle-enabled',
    'save-enabled': 'ui:parent-save-enabled',
    'allowance-15-select': 'ui:allowance-15-select',
    'allowance-15-read': 'ui:allowance-15-read',
    'time-explanation-read': 'ui:time-explanation-read',
    'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **station_entry(),
    **prepared_request(prefix='open', entry='open', initial='default',
                       child='fixture-child', approver='fixture-parent',
                       duration_seconds=75, allow_soft=True),
    'escape-ready': 'ui:kiosk-request-escape-ready',
    'escape-returned': 'ui:gdm-station-returned',
}
PLAN = JourneyPlan(
    prefix='kiosk-escape', worker_mode='kiosk_escape', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            'escape-ready': 'step-2', 'escape-returned': 'step-2'},
    advance_after={'open-estimate': 'step-2'},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=KioskValidDurationJourney)


E2E_CASES = {'kiosk-escape': execute}
