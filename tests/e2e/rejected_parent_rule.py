"""Task 186's finite rejected-directory/report qualification, without Send."""
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management
from parent_reports import ParentReportJourney, report_review
from match_rules import MATCH_RULES, match_edit
from native_fixtures import fixture_actions

SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'child-picker-opened': 'ui:existing-child-picker-opened',
    'child-choice-highlighted': 'ui:existing-child-choice-highlighted',
    'parent-selected': 'ui:existing-returned',
    'apps-page': 'ui:existing-apps', 'initial-rule': 'ui:match-row',
    'report-wrong-entry': 'ui:parent-report-refused',
    **match_edit('match-wildcard', 'confirmed',
                 editor=('confirmed-open', 'confirmed-read'), row='confirmed-rule'),
    **match_edit('match-rejected-directory', 'rejected',
                 editor=('editor-open', 'editor-read'), row=None),
    **report_review('review'),
    'restored-rule': 'ui:match-row',
    **match_edit('match-rejected-directory', 'independent',
                 editor=('independent-open', 'independent-read'), row=None),
    **report_review('independent'),
    'final-rule': 'ui:match-row',
}
PLAN = JourneyPlan(
    prefix='rejected-parent-rule', worker_mode='rejected_parent_rule', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS if stage != 'installed-greeter'},
            **{stage: 'step-2' for stage in (
                'independent-open', 'independent-read', 'independent-draft-focus',
                'independent-draft-selected', 'independent-draft-read', 'independent-save',
                *report_review('independent'), 'final-rule')}},
    advance_after={'restored-rule': 'step-2'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage in (
        'initial-rule', 'confirmed-open', 'confirmed-read', 'confirmed-draft-focus',
        'confirmed-draft-selected', 'confirmed-draft-read', 'confirmed-save', 'confirmed-rule',
        'editor-open', 'editor-read', 'rejected-draft-focus', 'rejected-draft-selected',
        'rejected-draft-read', 'rejected-save', 'restored-rule', 'independent-open',
        'independent-read', 'independent-draft-focus', 'independent-draft-selected',
        'independent-draft-read', 'independent-save', 'final-rule')},
    match_checks={'initial-rule': MATCH_RULES[0], 'confirmed-open': 'initial-rule',
        'confirmed-read': 'initial-rule', 'confirmed-rule': MATCH_RULES[1],
        'editor-open': 'confirmed-rule', 'editor-read': 'confirmed-rule',
        'restored-rule': 'confirmed-rule', 'independent-open': 'confirmed-rule',
        'independent-read': 'confirmed-rule', 'final-rule': 'confirmed-rule'},
)


def journey(context, progress, plan=PLAN, *, actions=None):
    return ParentReportJourney(context, progress, plan,
        actions=fixture_actions() if actions is None else actions)
