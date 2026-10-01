"""077 caller-owned filter qualification; complete case 184 stays separate."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management, filter_screens
from native_fixtures import fixture_actions, check_catalogue, catalogue_rows
from private_artifacts import require
from ui_observations import AppRowsObservation


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'child-picker-opened': 'ui:existing-child-picker-opened',
    'child-choice-highlighted': 'ui:existing-child-choice-highlighted',
    'parent-selected': 'ui:existing-returned',
    'apps-page': 'ui:existing-apps',
    'initial-rows': 'ui:existing-parent-app-rows',
    'wrong-child': 'ui:catalogue-filter-wrong-child',
    'wrong-page': 'ui:catalogue-filter-wrong-page',
    'independent-entry': 'ui:existing-apps',
    **{f'text-catalogue-name-{action}': f'ui:text-catalogue-name-{action}'
       for action in ('focus', 'selected', 'read')},
    'name-rows': 'ui:catalogue-name-rows',
    **filter_screens('match-rule', 2, 'precise'),
    **filter_screens('access-rule', 1, 'allowed'),
    'filtered-rows': 'ui:catalogue-name-rows',
    'reopened-entry': 'ui:catalogue-name-reopened',
    **filter_screens('match-rule', 2, 'independent-precise'),
    **filter_screens('access-rule', 1, 'independent-allowed'),
    'independent-filtered-rows': 'ui:catalogue-name-rows',
    **filter_screens('match-rule', 3, 'restore-match'),
    **filter_screens('access-rule', 7, 'restore-access'),
    **{f'text-catalogue-clear-{action}': f'ui:text-catalogue-clear-{action}'
       for action in ('focus', 'selected', 'read')},
    'cleared-rows': 'ui:catalogue-clear-rows',
}
PLAN = JourneyPlan(
    prefix='catalogue', worker_mode='catalogue_filters', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS if stage != 'installed-greeter'},
            **{stage: 'step-2' for stage in tuple(SCREENS)[tuple(SCREENS).index('wrong-child'):]}},
    advance_after={'initial-rows': 'step-2'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage, operation in SCREENS.items()
                    if operation.startswith(('ui:text-', 'ui:filter-'))},
)


class CatalogueJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
                         actions=fixture_actions() if actions is None else actions)
        self.initial_rows = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        operation = self.plan.screen_tags.get(stage, '').removeprefix('ui:')
        if operation not in ('existing-parent-app-rows', 'catalogue-name-rows',
                             'catalogue-name-reopened', 'catalogue-clear-rows'):
            return
        rows = AppRowsObservation.from_rows(observed['ui']['apps']['rows'])
        observed['comparison'] = {'row_count': len(rows.rows)}
        if operation == 'existing-parent-app-rows':
            require(self.initial_rows is None, 'catalogue:replay')
            observed['comparison'].update(check_catalogue(rows))
            self.initial_rows = rows
        elif operation == 'catalogue-clear-rows':
            require(self.initial_rows is not None and rows == self.initial_rows, 'catalogue:clear')
        else:
            require(self.initial_rows is not None and rows.rows == catalogue_rows(
                'catalogue-name', self.initial_rows.rows, match_mask=2, access_mask=1),
                'catalogue:exact-results')
        observed['comparison']['complete_catalogue_result'] = True
