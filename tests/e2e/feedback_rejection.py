"""Invalid-only feedback qualification, with public input and result proofs."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop
from private_artifacts import require
from ui_observations import FeedbackStateObservation
from accessible_ui import REJECTION_CASES, TEXT_OPERATIONS, REJECTION_FORMATS, DUPLICATE_OPERATIONS


def text_stages(binding):
    return tuple(stage for stage, (value, _) in TEXT_OPERATIONS.items() if value == binding)


STAGES = (
    'feedback-open', 'rejection-empty-send', 'rejection-empty-read',
    *text_stages('body-first'), 'rejection-valid-refusal',
    *text_stages('reply-malformed'), 'rejection-malformed-send', 'rejection-malformed-read',
    *text_stages('reply-clear'), *text_stages('body-hidden-base'),
    'rejection-hidden-focus', 'rejection-hidden-caret', 'rejection-hidden-input-read',
    'rejection-hidden-send', 'rejection-hidden-read', *text_stages('body-complex-75'),
    *(stage for stage, (binding, _) in DUPLICATE_OPERATIONS.items()
      if binding.startswith('body-complex')),
    *(f'rejection-format-{kind}-{action}' for kind in REJECTION_FORMATS for action in ('focus', 'apply')),
    'rejection-complex-send', 'rejection-complex-read', 'rejection-close',
    'rejection-wrong-entry', 'rejection-reopen', 'rejection-reopened-send', 'rejection-reopened-read',
)
SCREENS = {
    **fresh_desktop('parent'), 'parent-command': 'ui:parent-command-launch',
    **{stage: 'ui:' + stage for stage in (
        'parent-window', 'child-picker-opened', 'child-choice-highlighted',
        'parent-selected', *STAGES)},
}
PLAN = JourneyPlan(
    prefix='feedback-rejection', worker_mode='feedback_rejection', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in (
                'rejection-close', 'rejection-wrong-entry', 'rejection-reopen',
                'rejection-reopened-send', 'rejection-reopened-read')}},
    advance_after={'rejection-complex-read': 'step-2'},
)


class FeedbackRejectionJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
        self.complex = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'rejection-reopen':
            state = FeedbackStateObservation.from_value(observed['ui']['feedback_state'])
            require(self.complex is not None and state.draft == self.complex.draft
                    and state.validation == 'none' and state.send_enabled,
                    'rejection:independent-entry')
        elif stage in {f'rejection-{case}-read' for case in REJECTION_CASES}:
            case = stage.removeprefix('rejection-').removesuffix('-read')
            state = FeedbackStateObservation.from_value(observed['ui']['feedback_state'])
            projection, explanation = REJECTION_CASES[case]
            require(state.draft == projection and state.validation == explanation
                    and state.send_enabled, 'rejection:public-result')
            if case == 'complex':
                require(self.complex is None, 'rejection:replay')
                self.complex = state
