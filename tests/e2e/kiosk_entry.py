"""REQUEST01/03 qualification: enter and read the disabled-child station."""

from installed_journey import InstalledJourney, JourneyPlan


PLAN = JourneyPlan(
    prefix='kiosk-entry', worker_mode='kiosk_entry',
    screen_tags={
        'installed-greeter': 'ui:gdm-list',
        'wrong-parent-focused': 'ui:gdm-focused',
        'wrong-entry-refused': 'ui:gdm-station-wrong-entry-refused',
        'station-list': 'ui:gdm-station-list',
        'station-focused': 'ui:gdm-station-focused',
        'station-branch': 'ui:station-default-entry',
        'request-form': 'ui:kiosk-request-form',
    },
    phases={
        'ready': 'setup', 'setup-detached': 'setup',
        'installed-greeter': 'start', 'wrong-parent-focused': 'start',
        'wrong-entry-refused': 'start', 'station-list': 'step-1',
        'station-focused': 'step-1', 'station-branch': 'step-2', 'request-form': 'step-2',
    },
    advance_after={'wrong-entry-refused': 'step-1', 'station-focused': 'step-2'},
)


class KioskEntryJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
