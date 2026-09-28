"""Shared feedback input declarations and immutable public-result comparisons."""

from accessible_ui import FEEDBACK_STATE_PROJECTIONS, LENGTH_OBSERVATIONS, REJECTION_CASES
from feedback_rejection import text_stages
from private_artifacts import require
from ui_observations import FeedbackObservation, FeedbackStateObservation
from window_switch import WindowSwitchJourney


def text_fragment(binding, prefix=None):
    """Give repeated UI16 operations distinct invocation identities."""
    return {(prefix + stage.removeprefix('text-' + binding) if prefix else stage): 'ui:' + stage
            for stage in text_stages(binding)}


class FeedbackValidationJourney(WindowSwitchJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.states = {}
        self.draft = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        operation = self.plan.screen_tags.get(stage, '').removeprefix('ui:')
        expected = None
        if operation in FEEDBACK_STATE_PROJECTIONS:
            expected = (FEEDBACK_STATE_PROJECTIONS[operation], 'none')
        elif operation in LENGTH_OBSERVATIONS:
            expected = LENGTH_OBSERVATIONS[operation]
        elif operation == 'rejection-reopen':
            expected = ('rejection-complex', 'none')
        elif operation.startswith('rejection-') and operation.endswith('-read'):
            expected = REJECTION_CASES.get(operation.removeprefix('rejection-').removesuffix('-read'))
        if expected is not None:
            current = FeedbackStateObservation.from_value(observed['ui']['feedback_state'])
            require((current.draft, current.validation, current.send_enabled)
                    == (*expected, True), 'feedback:matrix-result')
            if operation == 'rejection-reopen':
                earlier = self.states.get('rejection-complex-read')
                require(earlier is not None and current.draft == earlier.draft,
                        'feedback:matrix-preservation')
            if operation == 'rejection-reopened-read':
                require(current == self.states.get('rejection-complex-read'),
                        'feedback:matrix-preservation')
            require(stage not in self.states, 'feedback:matrix-replay')
            self.states[stage] = current
        if operation in ('feedback-draft', 'feedback-privacy-returned',
                         'feedback-draft-reread', 'feedback-draft-reopen'):
            current = FeedbackObservation.from_value(observed['ui']['feedback'])
            require(current.draft == 'synthetic-first', 'feedback:expected-draft')
            if operation == 'feedback-draft':
                require(self.draft is None, 'feedback:replay')
                self.draft = current
            else:
                require(self.draft is not None and current == self.draft,
                        'feedback:preserved-draft')


class FeedbackDraftJourney(WindowSwitchJourney):
    """Compare complete independent file-bearing drafts and a fresh empty app."""
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.draft = None

    def check_settings(self, stage, observed):
        from attachment_composition import compare_formatted_draft
        super().check_settings(stage, observed)
        operation = self.plan.screen_tags.get(stage, '').removeprefix('ui:')
        if 'draft_state' not in observed.get('ui', {}):
            return
        reset = operation in ('draft-feedback-reopen', 'draft-feedback-reread')
        value = compare_formatted_draft(observed['ui']['draft_state'], reset=reset)
        if operation == 'draft-feedback-draft':
            require(self.draft is None, 'feedback:replay')
            self.draft = value
        else:
            require(self.draft is not None, 'feedback:missing-prior-draft')
            if not reset:
                require(value == self.draft, 'feedback:preserved-draft')
