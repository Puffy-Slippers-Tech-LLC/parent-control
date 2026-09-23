"""REQUEST01/03 qualification: enter and read the disabled-child station."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import station_entry


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
