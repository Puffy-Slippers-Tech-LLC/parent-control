"""Shared immutable public match-rule comparisons; callers own order and entry."""
from accessible_ui import MATCH_APP, MATCH_RULES
from installed_journey import InstalledJourney
from private_artifacts import require
from feedback_composition import text_fragment
import re


def match_edit(draft, prefix, *, editor, row):
    """Read an owned editor, replace its draft and Save; observe the result.

    A rejected-directory Save opens the automatic report instead of a row.
    Callers own entry, report handling and exact policy comparisons.
    """
    require(draft in ('match-precise', 'match-precise-basename', 'match-wildcard',
                     'match-wildcard-basename', 'match-wildcard-appimages',
                     'match-rejected-directory'), 'match:edit-binding')
    require(type(editor) is tuple and len(editor) == 2
            and all(type(stage) is str and re.fullmatch(r'[a-z][a-z0-9-]*', stage)
                    for stage in (prefix, *editor)), 'match:edit-stages')
    require(row is None if draft == 'match-rejected-directory' else
            type(row) is str and re.fullmatch(r'[a-z][a-z0-9-]*', row),
            'match:edit-result')
    stages = (*editor, *text_fragment(draft, prefix + '-draft'), prefix + '-save',
              *((row,) if row is not None else ()))
    require(len(stages) == len(set(stages)), 'match:edit-stages')
    return {
        editor[0]: 'ui:match-open', editor[1]: 'ui:match-read',
        **text_fragment(draft, prefix + '-draft'),
        prefix + '-save': 'ui:match-rejected' if row is None else 'ui:match-save',
        **({row: 'ui:match-row'} if row is not None else {}),
    }


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
