"""Public access-choice qualification and reusable exact row comparisons."""
from accessible_ui import ACCESS_CHOICES, MATCH_APP
from installed_journey import JourneyPlan
from match_rules import MatchRuleJourney
from journey_blocks import fresh_desktop, parent_management
from native_fixtures import fixture_actions
from private_artifacts import require


class AccessChoiceJourney(MatchRuleJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.access_checks = dict(plan.access_checks)
        require(all(stage in plan.screen_tags and choice in ACCESS_CHOICES
                    for stage, choice in self.access_checks.items()), 'access:comparison-plan')
        self.access_seen = set()

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage not in self.access_checks:
            return
        require(stage not in self.access_seen, 'access:comparison-replay')
        require(observed.get('ui', {}).get('access') == {
            'app': MATCH_APP, 'choice': self.access_checks[stage]}, 'access:exact-choice')
        self.access_seen.add(stage)
        observed['comparison'] = {'exact_access_choice': True}


EDITS = {
    'wrong-row': 'ui:access-wrong-row',
    'editor-open': 'ui:match-open', 'disabled': 'ui:access-disabled',
    'editor-cancel': 'ui:match-cancel',
    **{stage: operation for choice in ACCESS_CHOICES for stage, operation in (
        (choice + '-save', 'ui:access-' + choice), (choice + '-row', 'ui:access-row'))},
    'independent-screen': 'ui:access-screen', 'independent-entry': 'ui:existing-apps',
    **{stage: operation for choice in ACCESS_CHOICES for stage, operation in (
        ('independent-' + choice + '-save', 'ui:access-' + choice),
        ('independent-' + choice + '-row', 'ui:access-row'))},
}
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'child-picker-opened': 'ui:existing-child-picker-opened',
    'child-choice-highlighted': 'ui:existing-child-choice-highlighted',
    'parent-selected': 'ui:existing-returned', 'apps-page': 'ui:existing-apps',
    'initial-row': 'ui:access-row', **EDITS,
}
PLAN = JourneyPlan(
    prefix='access-choices', worker_mode='access_choices', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS if stage != 'installed-greeter'},
            **{stage: 'step-2' for stage in EDITS}},
    advance_after={'initial-row': 'step-2'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage in ('initial-row', *EDITS)
                    if SCREENS[stage][3:] in ('match-open', 'match-cancel') or
                    SCREENS[stage][3:].startswith('access-')},
    access_checks={'initial-row': 'allowed', **{
        prefix + choice + '-row': choice for prefix in ('', 'independent-')
        for choice in ACCESS_CHOICES}},
)


def journey(context, progress, plan=PLAN, *, actions=None):
    return AccessChoiceJourney(context, progress, plan,
        actions=fixture_actions() if actions is None else actions)
