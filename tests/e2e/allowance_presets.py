"""PARENT05 ordinary preset qualification in the shared installed envelope."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop

PRESET_STAGES = (
    'allowance-disabled', 'parent-toggle-enabled', 'parent-save-enabled',
    'allowance-wrong-child', 'allowance-0-select', 'allowance-0-read',
    'allowance-0-reopen', 'allowance-15-select', 'allowance-15-read',
    'allowance-15-reopen',
)
SCREENS = {
    **fresh_desktop('parent'),
    'parent-command': 'ui:parent-command-launch',
    **{stage: 'ui:' + stage for stage in (
        'parent-window', 'child-picker-opened', 'child-choice-highlighted',
        'parent-selected', *PRESET_STAGES)},
}
PLAN = JourneyPlan(
    prefix='allowance-presets', worker_mode='allowance_presets', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in PRESET_STAGES if stage.startswith('allowance-15-')}},
    advance_after={'allowance-0-reopen': 'step-2'},
)


class AllowancePresetsJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
