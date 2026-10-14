"""Engineering qualification of exposed kiosk Preferences restrictions."""

import json

from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management, station_entry
from request_flow import prepared_request
from request_composition import KioskRequestJourney
import system_runner as system


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **station_entry(),
    **prepared_request(prefix='open', entry='open', initial='default',
                       child='fixture-child', approver='fixture-parent',
                       duration_seconds=75, allow_soft=True),
    'preferences-confined': 'ui:kiosk-preferences-confinement',
    'form-returned': 'ui:kiosk-valid-fraction-soft-read',
    'cancel': 'ui:kiosk-request-cancel',
    'returned': 'ui:gdm-station-returned',
}
PLAN = JourneyPlan(
    prefix='kiosk-preferences-confinement', worker_mode='kiosk_preferences_confinement',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            'preferences-confined': 'step-2',
            **{stage: 'step-3' for stage in ('form-returned', 'cancel', 'returned')}},
    advance_after={'open-estimate': 'step-2', 'preferences-confined': 'step-3'},
    balance_checks={'allowance-configured': 1800},
    request_checks={'form-returned': (
        'open-estimate', 'kiosk-preferences:changed-form', 'unchanged_form')},
)


class KioskPreferencesConfinementJourney(KioskRequestJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)

    def check_request(self, stage, observed):
        super().check_request(stage, observed)
        if stage == 'preferences-confined':
            # This engineering census supplements the public surface result;
            # it supplies no preference editing or reminder feature acceptance.
            self.context.lease.guard()
            result = self.transport.call(['env',
                'ONPC_EXPECTED_RUN=' + self.context.lease.state['run'],
                'PYTHONDONTWRITEBYTECODE=1', '/usr/bin/python3', '-B',
                system.PAYLOAD + '/system_kiosk_confinement.py', 'census'], timeout=45)
            observed['engineering_confinement'] = json.loads(result)
