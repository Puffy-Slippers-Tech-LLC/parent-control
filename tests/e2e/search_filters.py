"""Case 184: Jordan's real catalogue search/filter sample preserves policy."""
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management, filter_screens
from native_fixtures import CataloguePolicyJourney, fixture_actions
from ui_observations import SettingsObservation


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'child-picker-opened': 'ui:existing-child-picker-opened',
    'child-choice-highlighted': 'ui:existing-child-choice-highlighted',
    'parent-selected': 'ui:existing-returned',
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'balance-reread': 'ui:time-explanation-read',
    'saved-settings': 'ui:existing-returned',
    'apps-page': 'ui:existing-apps',
    'legend-expanded': 'ui:policy-legend-expand',
    'legend-read': 'ui:policy-legend-read',
    'initial-rows': 'ui:existing-parent-app-rows',
    **{f'text-catalogue-name-{action}': f'ui:text-catalogue-name-{action}'
       for action in ('focus', 'selected', 'read')},
    'name-rows': 'ui:catalogue-name-rows',
    **filter_screens('match-rule', 2, 'precise'),
    **filter_screens('access-rule', 1, 'allowed'),
    'filtered-rows': 'ui:catalogue-name-rows',
    **filter_screens('match-rule', 3, 'restore-match'),
    **filter_screens('access-rule', 7, 'restore-access'),
    **{f'text-catalogue-clear-{action}': f'ui:text-catalogue-clear-{action}'
       for action in ('focus', 'selected', 'read')},
    'cleared-rows': 'ui:catalogue-clear-rows',
}
SAMPLE_STAGES = {
    **{f'text-catalogue-name-{action}': 'step-2' for action in ('focus', 'selected', 'read')},
    'name-rows': 'step-2',
    **{stage: 'step-2' for stage in filter_screens('match-rule', 2, 'precise')},
    **{stage: 'step-2' for stage in filter_screens('access-rule', 1, 'allowed')},
    'filtered-rows': 'step-2',
    **{stage: 'step-2' for stage in filter_screens('match-rule', 3, 'restore-match')},
    **{stage: 'step-2' for stage in filter_screens('access-rule', 7, 'restore-access')},
    **{f'text-catalogue-clear-{action}': 'step-2' for action in ('focus', 'selected', 'read')},
    'cleared-rows': 'step-3',
}
PLAN = JourneyPlan(
    prefix='search-filters', worker_mode='search_filters', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS if stage != 'installed-greeter'},
            **SAMPLE_STAGES},
    advance_after={'initial-rows': 'step-2', 'text-catalogue-clear-read': 'step-3'},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    balance_checks={'allowance-configured': 1800, 'balance-reread': 1800},
    child_bindings={stage: 'existing' for stage in (
        'allowance-configured', 'balance-reread',
        *filter_screens('match-rule', 2, 'precise'),
        *filter_screens('access-rule', 1, 'allowed'),
        *filter_screens('match-rule', 3, 'restore-match'),
        *filter_screens('access-rule', 7, 'restore-access'),
        *{f'text-catalogue-{binding}-{action}': None
          for binding in ('name', 'clear') for action in ('focus', 'selected', 'read')})},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    catalogue_checks={'initial-rows': 'initial', 'name-rows': ('catalogue-name', 3, 7),
                      'filtered-rows': ('catalogue-name', 2, 1), 'cleared-rows': 'unchanged'},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=CataloguePolicyJourney, actions=fixture_actions())


E2E_CASES = {'search-filters': execute}
