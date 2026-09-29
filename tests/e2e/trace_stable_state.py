"""Unchanged public feedback samples; no transition or scenario credit."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop

SCREENS = {
    **fresh_desktop('parent'),
    'parent-command': 'ui:parent-command-launch',
    **{stage: 'ui:' + stage for stage in (
        'parent-window', 'child-picker-opened', 'child-choice-highlighted',
        'parent-selected', 'feedback-open')},
    'trace-first-start': 'ui:feedback-trace-start',
    'trace-first-finish': 'ui:feedback-trace-finish',
    'feedback-close': 'ui:feedback-close',
    'feedback-state-wrong-entry': 'ui:feedback-state-wrong-entry',
    'feedback-open-again': 'ui:feedback-open',
    'trace-second-start': 'ui:feedback-trace-start',
    'trace-second-finish': 'ui:feedback-trace-finish',
}
PLAN = JourneyPlan(
    prefix='trace-stable', worker_mode='trace_stable_state', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in (
                'feedback-close', 'feedback-state-wrong-entry', 'feedback-open-again',
                'trace-second-start', 'trace-second-finish')}},
    advance_after={'trace-first-finish': 'step-2'},
)


def journey(context, progress):
    return InstalledJourney(context, progress, PLAN)
