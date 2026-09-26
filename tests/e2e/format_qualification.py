"""Installed UI24/FEED04 bold range qualification; never submits feedback."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop
from private_artifacts import require

STAGES = (
    'feedback-open', 'text-body-first-focus', 'text-body-first-selected',
    'text-body-first-read', 'format-before', 'format-focus', 'format-home',
    'format-selected', 'format-read', 'format-close', 'format-wrong-entry', 'format-reopen',
)
SCREENS = {
    **fresh_desktop('parent'), 'parent-command': 'ui:parent-command-launch',
    **{stage: 'ui:' + stage for stage in (
        'parent-window', 'child-picker-opened', 'child-choice-highlighted',
        'parent-selected', *STAGES)},
}
PLAN = JourneyPlan(
    prefix='format', worker_mode='format_qualification', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in STAGES[-3:]}},
    advance_after={'format-read': 'step-2'},
)


class FormatJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
        self.formatted = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage not in ('format-before', 'format-read', 'format-reopen'):
            return
        result = observed['ui']['formatting']
        require(result == [
            {'start': 0, 'end': 9, 'weight': 'normal' if stage == 'format-before' else 'bold'},
            {'start': 9, 'end': 23, 'weight': 'normal'},
        ], 'format:range-result')
        if stage == 'format-read':
            require(self.formatted is None, 'format:replay')
            self.formatted = result
        if stage == 'format-reopen':
            require(self.formatted is not None and result == self.formatted,
                    'format:independent-entry')
