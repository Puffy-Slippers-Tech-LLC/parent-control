"""REQUEST11/12 qualification for kiosk Cancel and Escape exits."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import station_entry


PLAN = JourneyPlan(
    prefix='request-exit', worker_mode='request_exit',
    screen_tags={
        **station_entry('cancel-'),
        'cancel-request-form': 'ui:kiosk-request-form',
        'cancel-action': 'ui:kiosk-request-cancel',
        'cancel-returned': 'ui:gdm-station-returned',
        **station_entry('escape-'),
        'escape-request-form': 'ui:kiosk-request-form',
        'escape-ready': 'ui:kiosk-request-escape-ready',
        'escape-returned': 'ui:gdm-station-returned',
    },
    phases={
        'ready': 'setup', 'setup-detached': 'setup',
        'cancel-station-list': 'start', 'cancel-station-focused': 'step-1',
        'cancel-station-branch': 'step-1', 'cancel-request-form': 'step-1',
        'cancel-action': 'step-1', 'cancel-returned': 'step-1',
        'escape-station-list': 'step-2', 'escape-station-focused': 'step-2',
        'escape-station-branch': 'step-2', 'escape-request-form': 'step-2',
        'escape-ready': 'step-2', 'escape-returned': 'step-2',
    },
    advance_after={
        'cancel-station-list': 'step-1',
        'cancel-returned': 'step-2',
    },
)


class RequestExitJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
