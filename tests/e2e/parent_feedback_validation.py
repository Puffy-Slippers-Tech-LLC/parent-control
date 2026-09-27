"""Case 153: the complete local validation matrix, Privacy and dialog retention."""

from feedback_composition import FeedbackValidationJourney, text_fragment
from feedback_length import length_boundary
from feedback_states import edit_states
from feedback_rejection import STAGES as REJECTION_STAGES
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop


ENTRY = {
    **fresh_desktop('parent'), 'parent-command': 'ui:parent-command-launch',
    **{stage: 'ui:' + stage for stage in (
        'parent-window', 'child-picker-opened', 'child-choice-highlighted', 'parent-selected',
        'switch-parent-before', 'switch-viewer-launch', 'switch-parent-ready', 'switch-parent',
        'feedback-open', 'feedback-state-empty')},
}
MATRIX = {
    **edit_states(),
    **text_fragment('reply-clear', 'length-reply-clear'),
    **length_boundary('ascii'),
    'length-ascii-close': 'ui:length-ascii-close',
    'length-ascii-reopen': 'ui:length-ascii-reopen',
    **length_boundary('mixed'),
    'length-mixed-close': 'ui:length-mixed-close',
    'length-mixed-reopen': 'ui:length-mixed-reopen',
    **text_fragment('body-clear'),
    'rejection-empty-send': 'ui:rejection-empty-send',
    'rejection-empty-read': 'ui:rejection-empty-read',
    **text_fragment('body-first', 'invalid-body-first'),
    'rejection-valid-refusal': 'ui:rejection-valid-refusal',
    **text_fragment('reply-malformed', 'invalid-reply-malformed'),
    'rejection-malformed-send': 'ui:rejection-malformed-send',
    'rejection-malformed-read': 'ui:rejection-malformed-read',
    **text_fragment('reply-clear'),
    **{stage: 'ui:' + stage for stage in REJECTION_STAGES
       if stage not in ('feedback-open', 'rejection-empty-send', 'rejection-empty-read',
                        'rejection-valid-refusal', 'rejection-malformed-send', 'rejection-malformed-read',
                        *text_fragment('body-first'), *text_fragment('reply-malformed'),
                        *text_fragment('reply-clear'))},
    'review-reset-close': 'ui:rejection-close', 'review-reset-open': 'ui:rejection-reopen',
    **text_fragment('body-first', 'review-body-first'),
    **text_fragment('reply-first', 'review-reply-first'),
    'review-valid': 'ui:feedback-state-valid',
}
REVIEW = {stage: 'ui:' + stage for stage in (
    'switch-draft-before', 'switch-viewer-ready', 'switch-viewer',
    'switch-feedback-ready', 'switch-feedback',
    'feedback-draft', 'feedback-privacy-open', 'feedback-privacy-returned',
    'feedback-draft-reread', 'feedback-draft-closed', 'feedback-draft-reopen')}
SCREENS = {**ENTRY, **MATRIX, **REVIEW}
PLAN = JourneyPlan(
    prefix='feedback-validation', worker_mode='feedback_validation', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in (*ENTRY, *MATRIX)}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in REVIEW}},
    advance_after={'review-valid': 'step-2'},
    invocations=tuple(stage for stage, operation in MATRIX.items() if operation != 'ui:' + stage),
)


class ValidationJourney(FeedbackValidationJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, journey_type=ValidationJourney)


E2E_CASES = {'validation': execute}
