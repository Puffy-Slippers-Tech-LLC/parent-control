"""UI22: one declared invalidating edit, with independent FEED09 readback."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, observed_text
from private_artifacts import require
from ui_observations import FeedbackStateObservation


SCREENS = {
    **fresh_desktop('parent'),
    'parent-command': 'ui:parent-command-launch',
    **{s: 'ui:' + s for s in ('parent-window', 'child-picker-opened',
       'child-choice-highlighted', 'parent-selected', 'feedback-open')},
    **{stage: operation for entry in ('first', 'second') for stage, operation in {
        **{f'prepare-{entry}-{s}': f'ui:text-body-first-{s}'
           for s in ('focus', 'selected', 'read')},
        **observed_text(entry, 'body-clear'),
        f'independent-{entry}': 'ui:feedback-state-empty',
        **({'trace-close': 'ui:feedback-close',
            'trace-wrong-entry': 'ui:feedback-state-wrong-entry',
            'trace-open-again': 'ui:feedback-open'} if entry == 'first' else {}),
    }.items()},
}
PLAN = JourneyPlan(
    prefix='compose-observation', worker_mode='compose_observation', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{s: 'step-1' for s in SCREENS}, 'installed-greeter': 'start',
            **{s: 'step-2' for s in SCREENS if s.startswith(
                ('trace-close', 'trace-wrong', 'trace-open', 'prepare-second',
                 'trace-second', 'second-', 'independent-second'))}},
    advance_after={'independent-first': 'step-2'},
    trace_bindings={f'trace-{e}-start': 'body-clear' for e in ('first', 'second')},
    trace_terminals={f'trace-{e}-finish': FeedbackStateObservation('initial-empty', 'none', True)
                     for e in ('first', 'second')},
)


class ComposeObservationJourney(InstalledJourney):
    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        operation = self.plan.screen_tags.get(stage)
        if operation == 'ui:feedback-trace-finish':
            self.terminal_state = FeedbackStateObservation.from_value(
                observed['ui']['samples'][-1]['state'])
        if operation == 'ui:feedback-state-empty':
            require(FeedbackStateObservation.from_value(observed['ui']['feedback_state']) ==
                    getattr(self, 'terminal_state', None) ==
                    FeedbackStateObservation('initial-empty', 'none', True),
                    'ui:trace-independent-snapshot')


def journey(context, progress):
    return ComposeObservationJourney(context, progress, PLAN)
