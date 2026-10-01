"""Case 205: review and dismiss reports from real rejected Parent rules."""
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management
from feedback_composition import text_fragment
from parent_reports import ParentReportJourney, report_review, report_close
from match_rules import MATCH_RULES
from native_fixtures import fixture_actions


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'child-picker-opened': 'ui:existing-child-picker-opened',
    'child-choice-highlighted': 'ui:existing-child-choice-highlighted',
    'parent-selected': 'ui:existing-returned',
    'apps-page': 'ui:existing-apps', 'initial-rule': 'ui:match-row',
    'confirmed-open': 'ui:match-open', 'confirmed-read': 'ui:match-read',
    **text_fragment('match-wildcard', 'confirmed-draft'),
    'confirmed-save': 'ui:match-save', 'confirmed-rule': 'ui:match-row',
    'editor-open': 'ui:match-open', 'editor-read': 'ui:match-read',
    **text_fragment('match-rejected-directory', 'rejected-draft'),
    'rejected-save': 'ui:match-rejected',
    **report_review('review'),
    'restored-rule': 'ui:match-row',
    'repeat-open': 'ui:match-open', 'repeat-read': 'ui:match-read',
    **text_fragment('match-rejected-directory', 'repeat-draft'),
    'repeat-save': 'ui:match-rejected',
    **report_close('decline'),
    'final-rule': 'ui:match-row',
}
PLAN = JourneyPlan(
    prefix='parent-error-report', worker_mode='parent_error_report', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS if stage != 'installed-greeter'},
            **{stage: 'step-2' for stage in (*report_review('review'), 'restored-rule')},
            **{stage: 'step-3' for stage in (
                'repeat-open', 'repeat-read', *text_fragment('match-rejected-directory', 'repeat-draft'),
                'repeat-save', *report_close('decline'), 'final-rule')}},
    advance_after={'rejected-save': 'step-2', 'restored-rule': 'step-3'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage in (
        'initial-rule', 'confirmed-open', 'confirmed-read',
        *text_fragment('match-wildcard', 'confirmed-draft'), 'confirmed-save', 'confirmed-rule',
        'editor-open', 'editor-read', *text_fragment('match-rejected-directory', 'rejected-draft'),
        'rejected-save', 'restored-rule', 'repeat-open', 'repeat-read',
        *text_fragment('match-rejected-directory', 'repeat-draft'), 'repeat-save', 'final-rule')},
    match_checks={'initial-rule': MATCH_RULES[0], 'confirmed-open': 'initial-rule',
        'confirmed-read': 'initial-rule', 'confirmed-rule': MATCH_RULES[1],
        'editor-open': 'confirmed-rule', 'editor-read': 'confirmed-rule',
        'restored-rule': 'confirmed-rule', 'repeat-open': 'confirmed-rule',
        'repeat-read': 'confirmed-rule', 'final-rule': 'confirmed-rule'},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=ParentReportJourney, actions=fixture_actions())


E2E_CASES = {'parent-error-report': execute}
