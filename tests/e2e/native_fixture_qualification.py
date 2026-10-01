"""035p's finite preparation/catalogue slice; complete cases stay separate."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management
from journey_checks import allowed_app_rows
from native_fixtures import check_catalogue, fixture_actions
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
    prefix='native-fixtures', worker_mode='native_fixtures', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            'wrong-child': 'step-2', 'wrong-page': 'step-2', 'reopened-rows': 'step-2'},
    advance_after={'app-rows': 'step-2'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-prepare'},
)


class NativeFixtureJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=fixture_actions() if actions is None else actions)
        self.initial_rows = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage not in ('app-rows', 'reopened-rows'):
            return
        rows = allowed_app_rows(self, observed)
        observed['comparison'].update(check_catalogue(rows))
        if stage == 'app-rows':
            require(self.initial_rows is None, 'native:catalogue-replay')
            self.initial_rows = rows
        else:
            require(self.initial_rows is not None and rows == self.initial_rows,
                    'native:independent-catalogue')
