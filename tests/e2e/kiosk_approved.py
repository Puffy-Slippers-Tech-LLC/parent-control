"""Case 49: offered approved exit, usable GDM and independently entered child."""

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management, station_entry
from request_composition import KioskRequestJourney
from request_flow import prepared_request
from kiosk_approved_flow import approved_request


CHILD_SCREENS = {'fresh-' + stage: operation
                 for stage, operation in fresh_desktop('child').items()}
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
    **approved_request(child='fixture-child', approver='fixture-parent',
                       duration_seconds=75, allow_soft=True, exit='immediate'),
    **CHILD_SCREENS,
    'countdown': 'ui:child-countdown-present',
}
PLAN = JourneyPlan(
    prefix='kiosk-approval', worker_mode='kiosk_approved', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in SCREENS
               if stage in ('approval-success', 'new-returned', 'countdown')
               or stage in CHILD_SCREENS}},
    advance_after={'approval-rechecked': 'step-2'},
    balance_checks={'time-explanation-read': 900},
    countdown_checks={'countdown': ('open-estimate', 975, 1, 180)},
    invocations=tuple(CHILD_SCREENS),
    challenges={'child-login': ('child', 'fresh-child-recipient-qualified',
                                'fresh-child-recipient-rechecked')},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=KioskRequestJourney)


E2E_CASES = {'kiosk-approved': execute}
