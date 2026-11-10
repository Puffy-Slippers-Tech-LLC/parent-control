"""Shared FLOW03 declarations; callers own entry, order and exact comparisons."""
from accessible_ui import ACCESS_CHOICES, FILTER_OPTIONS, MATCH_APP, BASELINE_POLICY_DRAFTS
from journey_blocks import filter_screens
from private_artifacts import require
from match_rules import match_edit
from access_choices import AccessChoiceJourney
from journey_checks import allowed_app_rows, check_balances
from native_fixtures import check_catalogue, fixture_actions


class AppPolicyJourney(AccessChoiceJourney):
    """Compare declared time, match and access results before acknowledging input."""

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in self.plan.balance_checks:
            check_balances(self, observed, self.plan.balance_checks[stage])


class NativePolicyJourney(AppPolicyJourney):
    """Native fixture readiness and the caller's initial catalogue binding."""

    def __init__(self, context, progress, plan, *, actions=None, alias=False):
        require(type(alias) is bool, 'policy:catalogue-binding')
        super().__init__(context, progress, plan,
                         actions=fixture_actions(include_refusal=False) if actions is None else actions)
        self.catalogue_alias = alias

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'initial-rows':
            rows = allowed_app_rows(self, observed)
            observed['comparison'].update(check_catalogue(rows, alias=self.catalogue_alias))


def policy_edit(app, draft, access, prefix, *, filters=(), setup=False):
    """Edit a policy; setup callers independently check the final saved policy.

    Setup omits intermediate row/editor reads already covered by that check.
    Input operations retain their normal ownership and save-completion guards.
    """
    import re
    require((app == MATCH_APP and draft in (
        'match-precise', 'match-precise-basename', 'match-wildcard', 'match-wildcard-basename',
        'match-wildcard-appimages') or draft in BASELINE_POLICY_DRAFTS
        and BASELINE_POLICY_DRAFTS[draft] == app)
        and access in ACCESS_CHOICES and type(prefix) is str
        and re.fullmatch(r'[a-z][a-z0-9-]*', prefix), 'policy:binding')
    require(type(setup) is bool and type(filters) is tuple and len(filters) <= 2
        and all(type(item) is tuple and len(item) == 2 and item[0] in FILTER_OPTIONS
                and type(item[1]) is int and 0 <= item[1] < 1 << len(FILTER_OPTIONS[item[0]])
                for item in filters)
        and len({item[0] for item in filters}) == len(filters), 'policy:filters')
    name = {'match-hard-precise': 'hard', 'match-soft-wildcard': 'soft',
            'match-soft-precise': 'soft',
            'match-alias-precise': 'alias', 'match-game-precise': 'game'}.get(draft)
    query = 'catalogue-' + name if name else 'catalogue-identifier'
    access_operation = 'access-' + (name + '-' if name else '')
    match_operation = 'match-' + (name + '-' if name else '')
    screens = {f'{prefix}-search-{action}': f'ui:text-{query}-{action}'
               for action in ('focus', 'selected', 'read')}
    for kind, mask in filters:
        screens.update(filter_screens(kind, mask, prefix + '-' + kind))
    screens.update({
        prefix + '-found': 'ui:' + query + '-rows',
        **match_edit(draft, prefix, editor=(prefix + '-open', prefix + '-old'),
                     row=prefix + '-match'),
        prefix + '-access-save': 'ui:' + access_operation + access,
        prefix + '-access': 'ui:' + access_operation + 'row',
        prefix + '-final-match': 'ui:' + match_operation + 'row',
    })
    if setup:
        for suffix in ('found', 'old', 'match', 'access', 'final-match'):
            del screens[prefix + '-' + suffix]
    return screens
