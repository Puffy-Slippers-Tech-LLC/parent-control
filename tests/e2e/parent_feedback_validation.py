"""Case 153: installed empty-message rejection and recovery to usable editing."""

from feedback_composition import FeedbackValidationJourney, text_fragment
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management


ENTRY = {
    **fresh_desktop('parent'), **parent_management(),
    'feedback-open': 'ui:feedback-open', 'feedback-state-empty': 'ui:feedback-state-empty',
}
MATRIX = {
    'rejection-empty-send': 'ui:rejection-empty-send',
    'rejection-empty-read': 'ui:rejection-empty-read',
    **text_fragment('body-first'), **text_fragment('reply-first'),
}
REVIEW = {
    'recovery-close': 'ui:feedback-state-close',
    'recovery-reopen': 'ui:feedback-state-reopen',
    'review-valid': 'ui:feedback-state-valid',
    'feedback-state-close': 'ui:feedback-state-close',
}
SCREENS = {**ENTRY, **MATRIX, **REVIEW}
PLAN = JourneyPlan(
    prefix='feedback-validation', worker_mode='feedback_validation', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in (*ENTRY, *MATRIX)}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in REVIEW}},
    advance_after={'text-reply-first-read': 'step-2'},
    invocations=tuple(stage for stage, operation in SCREENS.items() if operation != 'ui:' + stage),
)


ValidationJourney = FeedbackValidationJourney


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, journey_type=FeedbackValidationJourney)


E2E_CASES = {'validation': execute}
