"""FEED05 and FEED10(dialog): a synthetic draft, with Send untouched."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop
from private_artifacts import require
from ui_observations import FeedbackObservation
from accessible_ui import TEXT_OPERATIONS

SCREENS = {
    **fresh_desktop('parent'),
    'parent-command': 'ui:parent-command-launch',
    **{stage: 'ui:' + stage for stage in (
        'parent-window', 'child-picker-opened', 'child-choice-highlighted',
        'parent-selected', 'feedback-close-refused', 'feedback-open',
        *(stage for stage, (binding, _) in TEXT_OPERATIONS.items()
          if binding in ('body-first', 'reply-first')),
        'feedback-draft', 'feedback-privacy-open', 'feedback-privacy-returned',
        'feedback-draft-reread', 'feedback-draft-closed',
        'feedback-draft-reopen')},
    'privacy-independent': 'ui:feedback-privacy-open',
    'privacy-independent-returned': 'ui:feedback-privacy-returned',
}
PLAN = JourneyPlan(
    prefix='feedback-privacy', worker_mode='feedback_privacy', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in (
                'feedback-draft-reread', 'feedback-draft-closed',
                'feedback-draft-reopen', 'privacy-independent',
                'privacy-independent-returned')}},
    advance_after={'feedback-privacy-returned': 'step-2'},
)


class FeedbackPrivacyJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
        self.draft = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage not in ('feedback-draft', 'feedback-privacy-returned',
                         'feedback-draft-reread', 'feedback-draft-reopen',
                         'privacy-independent-returned'):
            return
        current = FeedbackObservation.from_value(observed['ui']['feedback'])
        require(current.draft == 'synthetic-first', 'feedback:expected-draft')
        if stage == 'feedback-draft':
            require(self.draft is None, 'feedback:replay')
            self.draft = current
        else:
            require(self.draft is not None and current == self.draft,
                    'feedback:preserved-draft')
