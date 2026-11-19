"""Restricted station: approval, denial or cancellation and normal exit."""
from approval_flow import rejected_request
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management, station_entry
from kiosk_approved_flow import approved_request
from request_composition import KioskRequestJourney
from request_flow import CHOICES, prepared_request

ENTRY = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
    'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **station_entry(),
    'request-form': 'ui:kiosk-request-form',
}
IDLE_RESTRICTIONS = {
    **{f'restriction-{route}-{phase}': f'ui:kiosk-restriction-{route}-{phase}'
       for route in ('overview', 'grid', 'terminal') for phase in ('ready', 'read')},
}
PREPARE = prepared_request(prefix='open', entry='open', initial='default',
                           compact=True, **CHOICES)
REQUEST = {**PREPARE, **approved_request(exit='automatic', **CHOICES)}
PLAN = JourneyPlan(
    prefix='kiosk-approval', worker_mode='restricted_station',
    screen_tags={**ENTRY, **IDLE_RESTRICTIONS, **REQUEST},
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in (*ENTRY, *IDLE_RESTRICTIONS)}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in REQUEST}, 'new-returned': 'step-3'},
    advance_after={'installed-greeter': 'step-1',
                   'restriction-terminal-read': 'step-2', 'approval-success': 'step-3'},
    balance_checks={'allowance-configured': 0},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=KioskRequestJourney)


PREPARED_RESTRICTIONS = {
    **{f'after-restriction-{route}-{phase}': 'ui:kiosk-restriction-prepared-' + phase
       for route in ('overview', 'grid', 'terminal') for phase in ('ready', 'read')},
}
UNAPPROVED_EXIT = {'new-cancel': 'ui:kiosk-request-cancel',
                   'new-returned': 'ui:gdm-station-returned'}


def unapproved_plan(variant, outcome):
    request = {**PREPARE, **rejected_request(outcome=outcome, **CHOICES), **PREPARED_RESTRICTIONS}
    return JourneyPlan(
        prefix='kiosk-approval-flow', worker_mode='restricted_station_' + variant,
        screen_tags={**ENTRY, **request, **UNAPPROVED_EXIT},
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: 'step-1' for stage in ENTRY}, 'installed-greeter': 'start',
                **{stage: 'step-2' for stage in request},
                **{stage: 'step-3' for stage in UNAPPROVED_EXIT}},
        advance_after={'installed-greeter': 'step-1', 'request-form': 'step-2',
                       'after-restriction-terminal-read': 'step-3'},
        balance_checks={'allowance-configured': 0},
        request_checks={'flow-preserved': ('flow-before', 'approval-flow:changed-form', 'preserved_choices')},
    )


DENIED_PLAN = unapproved_plan('denied', 'rejection')
CANCELLED_PLAN = unapproved_plan('cancelled', 'cancel')


def execute_denied(recorder, context):
    record_installed_journey(recorder, context, DENIED_PLAN, timeout=1800,
                             journey_type=KioskRequestJourney)


def execute_cancelled(recorder, context):
    record_installed_journey(recorder, context, CANCELLED_PLAN, timeout=1800,
                             journey_type=KioskRequestJourney)


E2E_CASES = {'approved': execute, 'denied': execute_denied, 'cancelled': execute_cancelled}
