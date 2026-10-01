"""Case 48: prepare one kiosk request and Escape back to usable GDM."""

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management
from request_composition import KioskRequestJourney
from request_flow import prepared_request, daily_station_entry


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    **daily_station_entry(),
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
                             journey_type=KioskRequestJourney)


E2E_CASES = {'kiosk-escape': execute}
