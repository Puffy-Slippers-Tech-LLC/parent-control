"""Case 152: text, bold and emoji in an installed file-bearing draft lifecycle."""
from attachment_composition import file_handoff
from feedback_composition import FeedbackDraftJourney, privacy_review, text_fragment
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management, parent_reopen
from synthetic_files import fixture_actions
from window_switch import window_switch_entry

ENTRY = {
    **fresh_desktop('parent'), **parent_management(),
    **window_switch_entry(), 'feedback-open': 'ui:feedback-open',
}
EDIT = {
    **text_fragment('body-first'),
    **{stage: 'ui:' + stage for stage in (
        'format-before', 'format-focus', 'format-home', 'format-selected', 'format-read',
        'text-scalar-body-smoke-focus', 'text-scalar-body-smoke-caret', 'text-scalar-body-smoke-read')},
    **text_fragment('reply-first'), **file_handoff('draft-chooser'),
    'feedback-draft': 'ui:draft-feedback-draft',
}
REVIEW = {
    'switch-draft-before': 'ui:draft-switch-draft-before',
    'switch-viewer-ready': 'ui:switch-viewer-ready', 'switch-viewer': 'ui:switch-viewer',
    'switch-feedback-ready': 'ui:switch-feedback-ready', 'switch-feedback': 'ui:draft-switch-feedback',
    **privacy_review(profile='formatted-file'),
    'feedback-draft-reread': 'ui:draft-feedback-draft-reread',
    'feedback-draft-closed': 'ui:feedback-draft-closed',
    'feedback-draft-reopen': 'ui:draft-feedback-draft-reopen',
    'reset-feedback-draft-reread': 'ui:draft-feedback-draft-reread',
    'reset-feedback-draft-closed': 'ui:feedback-draft-closed',
    **parent_reopen(),
    'feedback-reopen': 'ui:draft-feedback-reopen',
}
SCREENS = {**ENTRY, **EDIT, **REVIEW}
PLAN = JourneyPlan(
    prefix='feedback-draft', worker_mode='feedback_draft', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in (*ENTRY, *EDIT)}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in REVIEW}},
    advance_after={'feedback-draft': 'step-2'},
    stage_actions={'parent-selected': 'chooser-fixtures', 'feedback-reopen': 'chooser-cleanup'},
    invocations=tuple(stage for stage, operation in SCREENS.items() if operation != 'ui:' + stage),
)
ACTIONS = fixture_actions(('single',))


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, actions=ACTIONS,
                             journey_type=FeedbackDraftJourney)


E2E_CASES = {'draft-reopen': execute}
