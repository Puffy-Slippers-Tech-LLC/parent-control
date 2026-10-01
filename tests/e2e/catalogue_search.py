"""077b finite PARENT10 qualification; policy/filter cases remain separate."""
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management
from native_fixtures import CataloguePolicyJourney, fixture_actions

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
    catalogue_checks={'initial-rows': 'initial',
        **{stage: ('catalogue-name', 3, 7) for stage in ('name-rows', 'reopened-name')},
        **{stage: ('catalogue-absent', 3, 7) for stage in ('absent-rows', 'reopened-absent')},
        'cleared-rows': 'unchanged'},
)


class CatalogueSearchJourney(CataloguePolicyJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
                         actions=fixture_actions() if actions is None else actions)
