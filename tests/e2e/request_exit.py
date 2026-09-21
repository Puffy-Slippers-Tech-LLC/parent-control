"""REQUEST11/12 qualification for kiosk Cancel and Escape exits."""

from installed_journey import InstalledJourney, JourneyPlan


PLAN = JourneyPlan(
    prefix='request-exit', worker_mode='request_exit',
    screen_tags={
        'cancel-greeter': 'ui:gdm-list',
        'cancel-parent-focused': 'ui:gdm-focused',
        'cancel-wrong-entry-refused': 'ui:gdm-station-wrong-entry-refused',
        'cancel-station-list': 'ui:gdm-station-list',
        'cancel-station-focused': 'ui:gdm-station-focused',
        'cancel-station-branch': 'ui:station-default-entry',
        'cancel-request-form': 'ui:kiosk-request-form',
        'cancel-action': 'ui:kiosk-request-cancel',
        'cancel-returned': 'ui:gdm-station-returned',
        'escape-greeter': 'ui:gdm-list',
        'escape-parent-focused': 'ui:gdm-focused',
        'escape-wrong-entry-refused': 'ui:gdm-station-wrong-entry-refused',
        'escape-station-list': 'ui:gdm-station-list',
        'escape-station-focused': 'ui:gdm-station-focused',
        'escape-station-branch': 'ui:station-default-entry',
        'escape-request-form': 'ui:kiosk-request-form',
        'escape-ready': 'ui:kiosk-request-escape-ready',
        'escape-returned': 'ui:gdm-station-returned',
    },
    phases={
        'ready': 'setup', 'setup-detached': 'setup',
        'cancel-greeter': 'start', 'cancel-parent-focused': 'start',
        'cancel-wrong-entry-refused': 'start',
        'cancel-station-list': 'step-1', 'cancel-station-focused': 'step-1',
        'cancel-station-branch': 'step-1', 'cancel-request-form': 'step-1',
        'cancel-action': 'step-1', 'cancel-returned': 'step-1',
        'escape-greeter': 'step-2', 'escape-parent-focused': 'step-2',
        'escape-wrong-entry-refused': 'step-2',
        'escape-station-list': 'step-2', 'escape-station-focused': 'step-2',
        'escape-station-branch': 'step-2', 'escape-request-form': 'step-2',
        'escape-ready': 'step-2', 'escape-returned': 'step-2',
    },
    advance_after={
        'cancel-wrong-entry-refused': 'step-1',
        'cancel-returned': 'step-2',
    },
)


class RequestExitJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
