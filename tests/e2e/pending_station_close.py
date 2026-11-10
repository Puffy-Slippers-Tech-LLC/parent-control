"""FLOW17 station close: cancel real pending approval without granting time."""
from installed_journey import JourneyPlan
from journey_blocks import (fresh_desktop, parent_management, prefixed_stages,
                            retained_parent_entry, station_entry)
from kiosk_approved_flow import approved_request
from request_flow import CHOICES, prepared_request
from request_composition import CancelledRequestJourney


RETURN = {**fresh_desktop('parent'),
          **retained_parent_entry(source='same-user', desktop_observation=False)}
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned',
    **station_entry(),
    **prepared_request(prefix='open', entry='open', initial='default',
                       compact=True, **CHOICES),
    **approved_request(**CHOICES, exit='close'),
    **station_entry('cancel-'),
    'reopened-form': 'ui:kiosk-valid-fraction-soft-read',
    'cancel': 'ui:kiosk-request-cancel', 'cancel-returned': 'ui:gdm-station-returned',
    **prefixed_stages('return', RETURN),
    'balance-returned': 'ui:time-explanation-refresh-read',
}
PLAN = JourneyPlan(
    prefix='pending-station-close', worker_mode='pending_station_close', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    invocations=(*fresh_desktop('parent'),
                 *prefixed_stages('return', fresh_desktop('parent'))),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'return': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked'),
    },
    balance_checks={'allowance-configured': 1800},
    request_checks={'reopened-form': ('open-estimate', 'pending-station-close:choices-changed',
                                     'cancelled_request_preserved')},
    assertions_after={'new-returned': 'station-closed-and-usable-greeter',
                      'reopened-form': 'old-prompt-absent-and-usable-unchanged-form',
                      'balance-returned': 'no-grant-or-balance-increase'},
)


class PendingStationCloseJourney(CancelledRequestJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN, session_checks={},
                         balance_check=('allowance-configured', 'balance-returned', 1200))
