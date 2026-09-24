"""PARENT12/UI13 qualification; complete case 2 remains separate."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop
from private_artifacts import require
from ui_observations import AppRowsObservation


SCREENS = {
    **fresh_desktop('parent'),
    'parent-command': 'ui:parent-command-launch',
    'parent-window': 'ui:parent-window',
    'child-picker-opened': 'ui:child-picker-opened',
    'child-choice-highlighted': 'ui:child-choice-highlighted',
    'parent-selected': 'ui:parent-selected',
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
        rows = AppRowsObservation.from_rows(observed['ui']['apps']['rows'])
        require(bool(rows.rows) and all(row[1] == 'allowed' for row in rows.rows),
                'app-rows:initial-allowed')
        if stage == 'app-rows':
            require(self.initial_rows is None, 'app-rows:replay')
            self.initial_rows = rows
        else:
            require(self.initial_rows is not None and rows == self.initial_rows,
                    'app-rows:independent-read')
        observed['comparison'] = {'initial_allowed': True, 'row_count': len(rows.rows)}
