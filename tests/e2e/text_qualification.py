"""UI16 fixed synthetic feedback replacement qualification, without submission."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop
from accessible_ui import TEXT_OPERATIONS

SCREENS = {
    **fresh_desktop('parent'),
    'parent-command': 'ui:parent-command-launch',
    **{stage: 'ui:' + stage for stage in (
        'parent-window', 'child-picker-opened', 'child-choice-highlighted',
        'parent-selected', 'text-disabled', 'text-wrong-entry', 'feedback-open',
        *(stage for stage in TEXT_OPERATIONS if stage.startswith('text-body-')),
        'feedback-close', 'feedback-reopen',
        *(stage for stage in TEXT_OPERATIONS if stage.startswith('text-reply-')),
        'feedback-finished')},
}
PLAN = JourneyPlan(
    prefix='text', worker_mode='text_qualification', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in SCREENS
               if stage.startswith('text-reply-') or stage in (
                   'feedback-close', 'feedback-reopen', 'feedback-finished')}},
    advance_after={'text-body-clear-read': 'step-2'},
)


class TextJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
