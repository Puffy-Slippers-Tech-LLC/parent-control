"""Case 152: formatted one-file draft preservation and app-exit reset."""
from attachment_composition import file_handoff
from feedback_composition import FeedbackDraftJourney, text_fragment
from feedback_formats import all_formats, format_stages
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop
from synthetic_files import fixture_actions

ENTRY = {
    **fresh_desktop('parent'), 'parent-command': 'ui:parent-command-launch',
    **{stage: 'ui:' + stage for stage in (
        'parent-window', 'child-picker-opened', 'child-choice-highlighted', 'parent-selected',
        'switch-parent-before', 'switch-viewer-launch', 'switch-parent-ready', 'switch-parent',
        'feedback-open')},
}
EDIT = {
    **text_fragment('body-blocks'), **text_fragment('reply-first'),
    'formats-before': 'ui:formats-before', **all_formats(),
    **{stage: 'ui:' + stage for stage in format_stages('clear')},
    **all_formats('restore-'), **file_handoff('draft-chooser'),
    'feedback-draft': 'ui:draft-feedback-draft',
}
REVIEW = {
    'switch-draft-before': 'ui:draft-switch-draft-before',
    'switch-viewer-ready': 'ui:switch-viewer-ready', 'switch-viewer': 'ui:switch-viewer',
    'switch-feedback-ready': 'ui:switch-feedback-ready', 'switch-feedback': 'ui:draft-switch-feedback',
    **{stage: 'ui:draft-' + stage for stage in (
        'feedback-privacy-open', 'feedback-privacy-returned', 'feedback-draft-reread')},
    'feedback-draft-closed': 'ui:feedback-draft-closed',
    'feedback-draft-reopen': 'ui:draft-feedback-draft-reopen',
    'reset-feedback-draft-reread': 'ui:draft-feedback-draft-reread',
    'reset-feedback-draft-closed': 'ui:feedback-draft-closed',
    'prior-window': 'ui:parent-window', 'close-ready': 'ui:parent-restart-ready',
    'closed': 'ui:parent-search-closed', 'same-desktop': 'ui:desktop',
    'same-parent-command': 'ui:parent-command-launch', 'same-parent-window': 'ui:parent-window',
    'initial-selection': 'ui:parent-initial-selection',
    'feedback-wrong-entry': 'ui:feedback-wrong-entry',
    'feedback-reopen': 'ui:draft-feedback-reopen', 'feedback-reread': 'ui:draft-feedback-reread',
}
SCREENS = {**ENTRY, **EDIT, **REVIEW}
PLAN = JourneyPlan(
    prefix='feedback-draft', worker_mode='feedback_draft', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in (*ENTRY, *EDIT)}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in REVIEW}},
    advance_after={'feedback-draft': 'step-2'},
    stage_actions={'parent-selected': 'chooser-fixtures', 'feedback-reread': 'chooser-cleanup'},
    invocations=tuple(stage for stage, operation in SCREENS.items() if operation != 'ui:' + stage),
)
ACTIONS = fixture_actions(('single',))


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, actions=ACTIONS,
                             journey_type=FeedbackDraftJourney)


E2E_CASES = {'draft-reopen': execute}
