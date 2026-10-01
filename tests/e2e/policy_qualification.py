"""079 finite installed FLOW03 qualification, independent of complete cases."""
from accessible_ui import MATCH_APP, MATCH_RULES
from access_choices import AccessChoiceJourney
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management
from native_fixtures import fixture_actions
from policy_edits import policy_edit


# Exact* leaves unrelated space-bearing ELF fixtures outside the match, which
# cannot receive safe path allowances. Cover those fixture AppImages explicitly;
# the qualification proves editing, not isolated child enforcement.
FILTERED = policy_edit(MATCH_APP, 'match-wildcard-appimages', 'permanent', 'filtered',
                      filters=(('match-rule', 3), ('access-rule', 7)))
INDEPENDENT = policy_edit(MATCH_APP, 'match-precise', 'conditional', 'independent')
EDITS = {
    'wrong-row': 'ui:access-wrong-row', 'wrong-child': 'ui:catalogue-filter-wrong-child',
    'wrong-page': 'ui:catalogue-filter-wrong-page', 'restored-entry': 'ui:existing-apps',
    **FILTERED,
    'soft-save': 'ui:access-conditional', 'soft-row': 'ui:access-row',
    'allowed-save': 'ui:access-allowed', 'allowed-row': 'ui:access-row',
    'independent-screen': 'ui:access-screen', 'independent-entry': 'ui:existing-apps',
    'reread-match': 'ui:match-row', 'reread-access': 'ui:access-row',
    **INDEPENDENT,
    'final-screen': 'ui:access-screen', 'final-entry': 'ui:existing-apps',
    'final-match': 'ui:match-row', 'final-access': 'ui:access-row',
}
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'child-picker-opened': 'ui:existing-child-picker-opened',
    'child-choice-highlighted': 'ui:existing-child-choice-highlighted',
    'parent-selected': 'ui:existing-returned', 'apps-page': 'ui:existing-apps',
    'initial-match': 'ui:match-row', 'initial-access': 'ui:access-row', **EDITS,
}
PLAN = JourneyPlan(
    prefix='policy', worker_mode='policy_edit', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS if stage != 'installed-greeter'},
            **{stage: 'step-2' for stage in EDITS}},
    advance_after={'initial-access': 'step-2'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage, operation in SCREENS.items()
                    if operation.startswith(('ui:text-', 'ui:filter-', 'ui:match-', 'ui:access-'))},
    match_checks={
        'initial-match': MATCH_RULES[0], 'filtered-open': 'initial-match',
        'filtered-old': 'initial-match', 'filtered-match': MATCH_RULES[2],
        'filtered-final-match': 'filtered-match', 'reread-match': 'filtered-match',
        'independent-open': 'filtered-match', 'independent-old': 'filtered-match',
        'independent-match': MATCH_RULES[0], 'independent-final-match': 'independent-match',
        'final-match': 'independent-match',
    },
    access_checks={'initial-access': 'allowed', 'filtered-access': 'permanent',
        'soft-row': 'conditional', 'allowed-row': 'allowed', 'reread-access': 'allowed',
        'independent-access': 'conditional', 'final-access': 'conditional'},
)


def journey(context, progress, plan=PLAN, *, actions=None):
    return AccessChoiceJourney(context, progress, plan,
        actions=fixture_actions() if actions is None else actions)
