"""LIFE01 Parent closure/relaunch qualification, without selection repair."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_reopen

SCREENS = {
    **fresh_desktop('parent'),
    'desktop': 'ui:parent-restart-closed-refused',
    'parent-command': 'ui:parent-command-launch',
    'parent-window': 'ui:parent-window',
    'wrong-window-refused': 'ui:parent-restart-wrong-refused',
    **parent_reopen(),
}
PLAN = JourneyPlan(
    prefix='app-restart', worker_mode='app_restart', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
)


class AppRestartJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
