"""Shared FLOW03 declarations; callers own entry, order and exact comparisons."""
from accessible_ui import ACCESS_CHOICES, FILTER_OPTIONS, MATCH_APP
from journey_blocks import filter_screens
from private_artifacts import require
from match_rules import match_edit
from access_choices import AccessChoiceJourney
from journey_checks import check_balances


class AppPolicyJourney(AccessChoiceJourney):
    """Compare declared time, match and access results before acknowledging input."""

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in self.plan.balance_checks:
            check_balances(self, observed, self.plan.balance_checks[stage])


def policy_edit(app, draft, access, prefix, *, filters=()):
    """Finite native binding for search → optional filters → match → access."""
    import re
    require(app == MATCH_APP and draft in (
        'match-precise', 'match-precise-basename', 'match-wildcard', 'match-wildcard-basename',
        'match-wildcard-appimages')
        and access in ACCESS_CHOICES and type(prefix) is str
        and re.fullmatch(r'[a-z][a-z0-9-]*', prefix), 'policy:binding')
    require(type(filters) is tuple and len(filters) <= 2
        and all(type(item) is tuple and len(item) == 2 and item[0] in FILTER_OPTIONS
                and type(item[1]) is int and 0 <= item[1] < 1 << len(FILTER_OPTIONS[item[0]])
                for item in filters)
        and len({item[0] for item in filters}) == len(filters), 'policy:filters')
    screens = {f'{prefix}-search-{action}': f'ui:text-catalogue-identifier-{action}'
               for action in ('focus', 'selected', 'read')}
    for kind, mask in filters:
        screens.update(filter_screens(kind, mask, prefix + '-' + kind))
    screens.update({
        prefix + '-found': 'ui:catalogue-identifier-rows',
        **match_edit(draft, prefix, editor=(prefix + '-open', prefix + '-old'),
                     row=prefix + '-match'),
        prefix + '-access-save': 'ui:access-' + access,
        prefix + '-access': 'ui:access-row', prefix + '-final-match': 'ui:match-row',
    })
    return screens
