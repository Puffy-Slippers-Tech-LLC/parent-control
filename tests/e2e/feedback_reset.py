"""FEED10(app-exit): compare an empty draft before any restorative input."""

from installed_journey import InstalledJourney, JourneyPlan
from feedback_privacy import SCREENS as PRIVACY_SCREENS
from app_restart import SCREENS as RESTART_SCREENS
from private_artifacts import require
from ui_observations import FeedbackObservation

SCREENS = {}
for stage, operation in PRIVACY_SCREENS.items():
    SCREENS[stage] = operation
    if stage == 'feedback-draft':
        break
SCREENS.update({stage: 'ui:' + stage for stage in (
    'feedback-draft-reread', 'feedback-draft-closed')})
SCREENS.update({stage: operation for stage, operation in RESTART_SCREENS.items()
                if stage in ('prior-window', 'close-ready', 'closed', 'same-desktop',
                             'same-parent-command', 'same-parent-window', 'initial-selection')})
SCREENS.update({stage: 'ui:' + stage for stage in (
    'feedback-wrong-entry', 'feedback-reopen', 'feedback-reread')})
PLAN = JourneyPlan(
    prefix='feedback-reset', worker_mode='feedback_reset', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
)
# No customer-selected attachments; the independently collected default
# diagnostic archive is separate from the in-memory customer draft.
EMPTY_DRAFT = FeedbackObservation('initial-empty', ('diagnostic-logs.zip',),
                                  'ready', 'none', 'ready')


class FeedbackResetJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.draft = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in ('feedback-draft', 'feedback-draft-reread'):
            current = FeedbackObservation.from_value(observed['ui']['feedback'])
            require(current.draft == 'synthetic-first', 'feedback-reset:nonempty-entry')
            if stage == 'feedback-draft':
                require(self.draft is None, 'feedback-reset:replay')
                self.draft = current
            else:
                require(current == self.draft, 'feedback-reset:prior-draft')
        elif stage in ('feedback-reopen', 'feedback-reread'):
            require(self.draft is not None, 'feedback-reset:missing-entry')
            require(FeedbackObservation.from_value(observed['ui']['feedback']) == EMPTY_DRAFT,
                    'feedback-reset:empty-draft')
