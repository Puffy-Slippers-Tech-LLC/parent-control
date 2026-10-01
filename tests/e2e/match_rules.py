"""Shared immutable public match-rule comparisons; callers own order and entry."""
from accessible_ui import MATCH_APP, MATCH_RULES
from installed_journey import InstalledJourney
from private_artifacts import require


class MatchRuleJourney(InstalledJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        stages = list(plan.screen_tags)
        self.match_checks = dict(plan.match_checks)
        for stage, expected in self.match_checks.items():
            require(stage in stages and (expected in MATCH_RULES or
                    expected in stages and stages.index(expected) < stages.index(stage)),
                    'match:comparison-plan')
        self.match_values = {}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage not in self.match_checks:
            return
        require(stage not in self.match_values, 'match:comparison-replay')
        value = observed.get('ui', {}).get('match')
        require(type(value) is dict and set(value) == {'app', 'rule'}
                and value['app'] == MATCH_APP and value['rule'] in MATCH_RULES,
                'match:observation')
        expected = self.match_checks[stage]
        if expected not in MATCH_RULES:
            require(expected in self.match_values, 'match:missing-capture')
            expected = self.match_values[expected][1]
        require(value['rule'] == expected, 'match:exact-rule')
        self.match_values[stage] = (value['app'], value['rule'])
        observed['comparison'] = {'exact_match_rule': True}
