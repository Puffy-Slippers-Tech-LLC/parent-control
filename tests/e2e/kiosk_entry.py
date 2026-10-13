"""REQUEST01/03 qualification: enter and read the disabled-child station."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import station_entry
import json
import system_runner as system


PLAN = JourneyPlan(
    prefix='kiosk-entry', worker_mode='kiosk_entry',
    screen_tags={
        **station_entry(),
        'request-form': 'ui:kiosk-request-form',
    },
    phases={
        'ready': 'setup', 'setup-detached': 'setup',
        'station-list': 'start',
        'station-focused': 'step-1', 'station-branch': 'step-2', 'request-form': 'step-2',
    },
    advance_after={'station-list': 'step-1', 'station-focused': 'step-2'},
)


class KioskEntryJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)

    def check_request(self, stage, observed):
        super().check_request(stage, observed)
        if stage == 'request-form':
            # This qualification also supplies an engineering census. Customer
            # scenario classes retain only their public workflow assertions.
            self.context.lease.guard()
            result = self.transport.call(['env',
                'ONPC_EXPECTED_RUN=' + self.context.lease.state['run'],
                'PYTHONDONTWRITEBYTECODE=1', '/usr/bin/python3', '-B',
                system.PAYLOAD + '/system_kiosk_confinement.py', 'census'], timeout=45)
            observed['engineering_confinement'] = json.loads(result)
