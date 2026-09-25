"""LIFE01 Parent closure/relaunch qualification, without selection repair."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop

SCREENS = {
    **fresh_desktop('parent'),
    'desktop': 'ui:parent-restart-closed-refused',
    'parent-command': 'ui:parent-command-launch',
    'parent-window': 'ui:parent-window',
    'wrong-window-refused': 'ui:parent-restart-wrong-refused',
    'prior-window': 'ui:parent-window',
    'close-ready': 'ui:parent-restart-ready',
    'closed': 'ui:parent-search-closed',
    'same-desktop': 'ui:desktop',
    'same-parent-command': 'ui:parent-command-launch',
    'same-parent-window': 'ui:parent-window',
    'initial-selection': 'ui:parent-initial-selection',
}
PLAN = JourneyPlan(
    prefix='app-restart', worker_mode='app_restart', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
)


class AppRestartJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
