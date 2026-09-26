"""Case 50: request-only station shortcuts, approval and automatic exit."""
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management, station_entry
from kiosk_approved_flow import approved_request
from kiosk_valid_duration import KioskValidDurationJourney
from request_flow import prepared_request

ENTRY = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
    'time-explanation-read': 'ui:time-explanation-read',
    'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **station_entry(),
    'request-form': 'ui:kiosk-request-form',
    **{f'restriction-{route}-{phase}': 'ui:kiosk-restriction-' + phase
       for route in ('overview', 'grid', 'terminal') for phase in ('ready', 'read')},
}
REQUEST = {
    **prepared_request(prefix='open', entry='open', initial='default',
                       child='fixture-child', approver='fixture-parent',
                       duration_seconds=75, allow_soft=True),
    **approved_request(child='fixture-child', approver='fixture-parent',
                       duration_seconds=75, allow_soft=True, exit='automatic'),
}
PLAN = JourneyPlan(
    prefix='kiosk-approval', worker_mode='restricted_station',
    screen_tags={**ENTRY, **REQUEST},
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in ENTRY}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in REQUEST}, 'new-returned': 'step-3'},
    advance_after={'installed-greeter': 'step-1',
                   'restriction-terminal-read': 'step-2', 'approval-success': 'step-3'},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=KioskValidDurationJourney)


E2E_CASES = {'approved': execute}
