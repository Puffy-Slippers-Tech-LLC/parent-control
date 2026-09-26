"""FEED09 snapshots after finite edits, without pressing Send.

Validation is currently triggered by Send, not edits. These observations must
therefore show no explanation and enabled Send even for malformed input. They
do not qualify submission rejection or the complete text/email scenario.
"""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop
from private_artifacts import require
from ui_observations import FeedbackStateObservation
from accessible_ui import TEXT_OPERATIONS, FEEDBACK_STATE_PROJECTIONS

EDITS = (
    ('body-whitespace', 'feedback-state-whitespace'),
    ('body-first', 'feedback-state-no-reply'),
    ('reply-malformed', 'feedback-state-malformed'),
    ('reply-first', 'feedback-state-valid'),
)
SCREENS = {
    **fresh_desktop('parent'),
    'parent-command': 'ui:parent-command-launch',
    **{stage: 'ui:' + stage for stage in (
        'parent-window', 'child-picker-opened', 'child-choice-highlighted',
        'parent-selected', 'feedback-open', 'feedback-state-empty',
        *(stage for binding, observed in EDITS for stage in (
            *(key for key, (value, _) in TEXT_OPERATIONS.items() if value == binding),
            observed)),
        'feedback-state-close', 'feedback-state-wrong-entry', 'feedback-state-reopen')},
}
PLAN = JourneyPlan(
    prefix='feedback-states', worker_mode='feedback_states', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in (
                'feedback-state-close', 'feedback-state-wrong-entry', 'feedback-state-reopen')}},
    advance_after={'feedback-state-valid': 'step-2'},
)


class FeedbackStatesJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
        self.valid = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage not in FEEDBACK_STATE_PROJECTIONS:
            return
        state = FeedbackStateObservation.from_value(observed['ui']['feedback_state'])
        require(state.draft == FEEDBACK_STATE_PROJECTIONS[stage], 'feedback:state-draft')
        require(state.validation == 'none' and state.send_enabled,
                'feedback:edit-only-controls')
        if stage == 'feedback-state-valid':
            require(self.valid is None, 'feedback:replay')
            self.valid = state
        if stage == 'feedback-state-reopen':
            require(self.valid is not None and state == self.valid,
                    'feedback:independent-state')
