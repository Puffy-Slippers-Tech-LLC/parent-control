"""FEED01/03 fixed read-only installed Parent qualification."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop
from private_artifacts import require
from ui_observations import FeedbackObservation

SCREENS = {
    **fresh_desktop('parent'),
    'parent-command': 'ui:parent-command-launch',
    'parent-window': 'ui:parent-window',
    'child-picker-opened': 'ui:child-picker-opened',
    'child-choice-highlighted': 'ui:child-choice-highlighted',
    'parent-selected': 'ui:parent-selected',
    **{stage: 'ui:' + stage for stage in (
        'feedback-open', 'feedback-read', 'feedback-close', 'feedback-wrong-entry',
        'feedback-reopen', 'feedback-reread', 'feedback-finished')},
}
PLAN = JourneyPlan(
    prefix='feedback-read', worker_mode='feedback_read', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in ('feedback-close', 'feedback-wrong-entry',
                'feedback-reopen', 'feedback-reread', 'feedback-finished')}},
    advance_after={'feedback-read': 'step-2'},
)


class FeedbackReadJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
        self.initial_feedback = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage not in ('feedback-read', 'feedback-reread'):
            return
        current = FeedbackObservation.from_value(observed['ui']['feedback'])
        if stage == 'feedback-read':
            require(self.initial_feedback is None, 'feedback:replay')
            self.initial_feedback = current
        else:
            require(self.initial_feedback is not None and current == self.initial_feedback,
                    'feedback:independent-read')
