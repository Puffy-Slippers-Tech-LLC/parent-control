"""Finite match-editor qualifications; callers share public operations/comparisons."""
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management
from match_rules import MatchRuleJourney, MATCH_RULES
from native_fixtures import fixture_actions

EDIT_SCREENS = {
    'editor-open': 'ui:match-open', 'editor-read': 'ui:match-read',
    'wrong-app': 'ui:match-wrong-app', 'ambiguous': 'ui:match-ambiguous',
    **{f'cancel-draft-{action}': f'ui:text-match-wildcard-{action}'
       for action in ('focus', 'selected', 'read')},
    'cancel': 'ui:match-cancel', 'cancelled-rule': 'ui:match-row',
    'independent-open': 'ui:match-open', 'independent-read': 'ui:match-read',
    **{f'save-draft-{action}': f'ui:text-match-wildcard-{action}'
       for action in ('focus', 'selected', 'read')},
    'save': 'ui:match-save', 'saved-rule': 'ui:match-row',
}
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'child-picker-opened': 'ui:existing-child-picker-opened',
    'child-choice-highlighted': 'ui:existing-child-choice-highlighted',
    'parent-selected': 'ui:existing-returned',
    'apps-page': 'ui:existing-apps', 'initial-rule': 'ui:match-row',
    **EDIT_SCREENS,
}
PLAN = JourneyPlan(
    prefix='match-save-cancel', worker_mode='match_save_cancel', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS if stage != 'installed-greeter'},
            **{stage: 'step-2' for stage in EDIT_SCREENS}},
    advance_after={'initial-rule': 'step-2'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    child_bindings={'initial-rule': 'existing', **{stage: 'existing' for stage in EDIT_SCREENS}},
    match_checks={'initial-rule': MATCH_RULES[0], 'editor-open': 'initial-rule',
        'editor-read': 'initial-rule', 'cancelled-rule': 'initial-rule',
        'independent-open': 'initial-rule', 'independent-read': 'initial-rule',
        'saved-rule': MATCH_RULES[1]},
)

EDITOR_SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'child-picker-opened': 'ui:existing-child-picker-opened',
    'child-choice-highlighted': 'ui:existing-child-choice-highlighted',
    'parent-selected': 'ui:existing-returned',
    'apps-page': 'ui:existing-apps', 'initial-rule': 'ui:match-row',
}
EDITOR_EDITS = {
    'editor-open': 'ui:match-open', 'editor-read': 'ui:match-read',
    'wrong-app': 'ui:match-wrong-app', 'ambiguous': 'ui:match-ambiguous',
    **{f'invalid-draft-{action}': f'ui:text-match-invalid-empty-{action}'
       for action in ('focus', 'selected', 'read')},
    'invalid': 'ui:match-invalid-empty', 'invalid-cancel': 'ui:match-cancel',
    'unchanged-rule': 'ui:match-row',
    'valid-open': 'ui:match-open', 'valid-read': 'ui:match-read',
    **{f'save-draft-{action}': f'ui:text-match-wildcard-{action}'
       for action in ('focus', 'selected', 'read')},
    'save': 'ui:match-save', 'saved-rule': 'ui:match-row',
    'independent-open': 'ui:match-open', 'independent-read': 'ui:match-read',
    'reset': 'ui:match-reset', 'reset-rule': 'ui:match-row',
    'reset-reopen': 'ui:match-open', 'reset-read': 'ui:match-read',
    'cancel': 'ui:match-cancel', 'final-rule': 'ui:match-row',
}
EDITOR_SCREENS.update(EDITOR_EDITS)
EDITOR_PLAN = JourneyPlan(
    prefix='match-editor', worker_mode='match_editor', screen_tags=EDITOR_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in EDITOR_SCREENS if stage != 'installed-greeter'},
            **{stage: 'step-2' for stage in EDITOR_EDITS}},
    advance_after={'initial-rule': 'step-2'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    child_bindings={'initial-rule': 'existing', **{stage: 'existing' for stage in EDITOR_EDITS}},
    match_checks={'initial-rule': MATCH_RULES[0], 'editor-open': 'initial-rule',
        'editor-read': 'initial-rule', 'unchanged-rule': 'initial-rule',
        'valid-open': 'initial-rule', 'valid-read': 'initial-rule',
        'saved-rule': MATCH_RULES[1], 'independent-open': 'saved-rule',
        'independent-read': 'saved-rule', 'reset-rule': 'initial-rule',
        'reset-reopen': 'initial-rule', 'reset-read': 'initial-rule', 'final-rule': 'initial-rule'},
)


def journey(context, progress, plan=PLAN, *, actions=None):
    return MatchRuleJourney(context, progress, plan,
                            actions=fixture_actions() if actions is None else actions)
