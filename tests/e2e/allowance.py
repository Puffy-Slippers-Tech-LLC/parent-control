"""Ordinary custom allowance commits, with independent reloads through Parent."""

from installed_journey import InstalledJourney, JourneyPlan
from allowance_presets import SCREENS as PRESET_SCREENS

SCREENS = dict(PRESET_SCREENS)
# Refuse custom input before enabling, then reuse the qualified preset sequence.
items = list(SCREENS.items())
position = next(i for i, (stage, _) in enumerate(items) if stage == 'allowance-disabled')
items[position:position] = [('custom-disabled', 'ui:custom-disabled')]
SCREENS = dict(items)
SCREENS['custom-wrong-child'] = 'ui:custom-wrong-child'
for value in (1, 2, 3):
    SCREENS['custom-' + str(value) + '-open'] = 'ui:custom-' + str(value) + '-open'
    for action in ('focus', 'selected', 'read'):
        stage = 'text-daily-' + str(value) + '-' + action
        SCREENS[stage] = 'ui:' + stage
    for action in ('saved',):
        stage = 'custom-' + str(value) + '-' + action
        SCREENS[stage] = 'ui:' + stage
    # Leave and reselect the child so reopened text comes from saved preferences,
    # not the draft Entry. Each Enter consumes its own public focused proof.
    for suffix, operation in (
        ('away-open', 'existing-child-picker-opened'),
        ('away-focus', 'existing-child-choice-highlighted'),
        ('away-selected', 'existing-returned'),
        ('back-open', 'child-picker-opened'),
        ('back-focus', 'child-choice-highlighted'),
        ('back-selected', 'parent-selected'),
    ):
        SCREENS['custom-' + str(value) + '-' + suffix] = 'ui:' + operation
    stage = 'custom-' + str(value) + '-reopen'
    SCREENS[stage] = 'ui:' + stage

PLAN = JourneyPlan(
    prefix='allowance', worker_mode='allowance', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in SCREENS
               if stage.startswith(('custom-', 'text-daily-'))
               and stage != 'custom-disabled'}},
    advance_after={'allowance-15-reopen': 'step-2'},
)


class AllowanceJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
