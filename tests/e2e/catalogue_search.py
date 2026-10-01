"""077b finite PARENT10 qualification; policy/filter cases remain separate."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management
from native_fixtures import fixture_actions, check_catalogue, search_rows
from private_artifacts import require
from ui_observations import AppRowsObservation

SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'child-picker-opened': 'ui:existing-child-picker-opened',
    'child-choice-highlighted': 'ui:existing-child-choice-highlighted',
    'parent-selected': 'ui:existing-returned',
    'apps-page': 'ui:existing-apps',
    'initial-rows': 'ui:existing-parent-app-rows',
    'wrong-child': 'ui:existing-parent-app-rows-wrong-child',
    'wrong-page': 'ui:existing-parent-app-rows-wrong-page',
    'independent-entry': 'ui:existing-apps',
    **{f'text-{binding}-{action}': f'ui:text-{binding}-{action}'
       for binding in ('catalogue-name',) for action in ('focus', 'selected', 'read')},
    'name-rows': 'ui:catalogue-name-rows',
    'incomplete-result': 'ui:catalogue-incomplete-refused',
    'reopened-name': 'ui:catalogue-name-reopened',
    **{f'text-{binding}-{action}': f'ui:text-{binding}-{action}'
       for binding in ('catalogue-absent',) for action in ('focus', 'selected', 'read')},
    'absent-rows': 'ui:catalogue-absent-rows',
    'reopened-absent': 'ui:catalogue-absent-reopened',
    **{f'text-{binding}-{action}': f'ui:text-{binding}-{action}'
       for binding in ('catalogue-clear',) for action in ('focus', 'selected', 'read')},
    'cleared-rows': 'ui:catalogue-clear-rows',
}
PLAN = JourneyPlan(
    prefix='catalogue-search', worker_mode='catalogue_search', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS if stage != 'installed-greeter'},
            **{stage: 'step-2' for stage in tuple(SCREENS)[tuple(SCREENS).index('wrong-child'):]}},
    advance_after={'initial-rows': 'step-2'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage in SCREENS
                    if stage.startswith('text-')},
)


class CatalogueSearchJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
                         actions=fixture_actions() if actions is None else actions)
        self.initial_rows = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        bindings = {'name-rows': 'catalogue-name', 'reopened-name': 'catalogue-name',
                    'absent-rows': 'catalogue-absent', 'reopened-absent': 'catalogue-absent'}
        if stage not in ('initial-rows', 'cleared-rows', *bindings):
            return
        rows = AppRowsObservation.from_rows(observed['ui']['apps']['rows'])
        observed['comparison'] = {'row_count': len(rows.rows)}
        if stage == 'initial-rows':
            require(self.initial_rows is None, 'catalogue:replay')
            observed['comparison'].update(check_catalogue(rows))
            self.initial_rows = rows
        elif stage == 'cleared-rows':
            require(self.initial_rows is not None and rows == self.initial_rows,
                    'catalogue:clear')
        else:
            require(rows.rows == search_rows(bindings[stage]), 'catalogue:exact-results')
        observed['comparison']['complete_catalogue_result'] = True
