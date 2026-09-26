"""Case 192: station information and unchanged request after About closes."""

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management, station_entry
from request_flow import prepared_request
from restricted_station_about import RestrictedStationAboutJourney


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **station_entry(),
    **prepared_request(prefix='open', entry='open', initial='default',
                       child='fixture-child', approver='fixture-parent',
                       duration_seconds=75, allow_soft=True),
    'about-open': 'ui:kiosk-about-open',
    'about-read': 'ui:kiosk-about-read',
    'about-close-ready': 'ui:kiosk-about-close-ready',
    'about-closed': 'ui:kiosk-about-closed',
    'form-returned': 'ui:kiosk-valid-fraction-soft-read',
    'cancel': 'ui:kiosk-request-cancel',
    'returned': 'ui:gdm-station-returned',
}
PLAN = JourneyPlan(
    prefix='kiosk-about', worker_mode='kiosk_about', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            'about-open': 'step-2', 'about-read': 'step-2',
            **{stage: 'step-3' for stage in ('about-close-ready', 'about-closed',
                                            'form-returned', 'cancel', 'returned')}},
    advance_after={'open-estimate': 'step-2', 'about-read': 'step-3'},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=RestrictedStationAboutJourney)


E2E_CASES = {'kiosk': execute}
