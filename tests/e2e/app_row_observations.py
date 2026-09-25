"""PARENT12/UI13 qualification; complete case 2 remains separate."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management
from journey_checks import allowed_app_rows
from private_artifacts import require


SCREENS = {
    **fresh_desktop('parent'),
    **parent_management(),
    'apps-page': 'ui:parent-apps-page',
    'app-rows': 'ui:parent-app-rows',
    'wrong-child': 'ui:parent-app-rows-wrong-child',
    'wrong-page': 'ui:parent-app-rows-wrong-page',
    'reopened-rows': 'ui:parent-app-rows-reopened',
}
PLAN = JourneyPlan(
    prefix='app-rows', worker_mode='app_row_observations', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            'wrong-child': 'step-2', 'wrong-page': 'step-2', 'reopened-rows': 'step-2'},
    advance_after={'app-rows': 'step-2'},
)


class AppRowJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
        self.initial_rows = None

    def check_settings(self, stage, observed):
        """Check caller-owned initial choices before the durable acknowledgement."""
        super().check_settings(stage, observed)
        if stage not in ('app-rows', 'reopened-rows'):
            return
        rows = allowed_app_rows(self, observed)
        if stage == 'app-rows':
            require(self.initial_rows is None, 'app-rows:replay')
            self.initial_rows = rows
        else:
            require(self.initial_rows is not None and rows == self.initial_rows,
                    'app-rows:independent-read')
