"""226b public legend qualification; complete case 184 remains separate."""
from installed_journey import JourneyPlan
from fresh_thirty_allowance import JORDAN_PLAN
from native_fixtures import CataloguePolicyJourney, fixture_actions


SCREENS = {
    **{stage: operation for stage, operation in JORDAN_PLAN.screen_tags.items()
       if stage not in ('wrong-child', 'wrong-state', 'wrong-window', 'final-settings')},
    'apps-page': 'ui:existing-apps',
    'initial-rows': 'ui:existing-parent-app-rows',
    'wrong-child': 'ui:policy-legend-wrong-child',
    'wrong-page': 'ui:policy-legend-wrong-page',
    'independent-entry': 'ui:existing-apps',
    'legend-expanded': 'ui:policy-legend-expand',
    'legend-read': 'ui:policy-legend-read',
    'independent-open-read': 'ui:policy-legend-read',
    'final-rows': 'ui:existing-parent-app-rows',
}
PLAN = JourneyPlan(
    prefix='policy-legend', worker_mode='policy_legend', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS if stage != 'installed-greeter'},
            **{stage: 'step-2' for stage in tuple(SCREENS)[tuple(SCREENS).index('wrong-child'):]}},
    advance_after={'initial-rows': 'step-2'},
    settings_checks={'parent-selected': JORDAN_PLAN.settings_checks['parent-selected']},
    child_bindings={stage: 'existing' for stage in ('allowance-configured', 'balance-reread')},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    balance_checks={'allowance-configured': 1800, 'balance-reread': 1800},
    catalogue_checks={'initial-rows': 'initial', 'final-rows': 'unchanged'},
)


class PolicyLegendJourney(CataloguePolicyJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
                         actions=fixture_actions() if actions is None else actions)
