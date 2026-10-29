"""Ordinary custom allowance commits, with independent reloads through Parent."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management

# Preset saves and their input guards belong to check_e2e_allowance_presets.
# Custom commits need only the selected child and enabled allowance editor.
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'custom-disabled': 'ui:custom-disabled',
    'parent-toggle-enabled': 'ui:parent-toggle-enabled',
    'parent-save-enabled': 'ui:parent-save-enabled',
    'custom-wrong-child': 'ui:custom-wrong-child',
}
for value in (1, 2, 3):
    SCREENS['custom-' + str(value) + '-open'] = 'ui:custom-' + str(value) + '-open'
    for action in ('focus', 'selected', 'read'):
        stage = 'text-daily-' + str(value) + '-' + action
        SCREENS[stage] = 'ui:' + stage
    for action in ('saved',):
        stage = 'custom-' + str(value) + '-' + action
        SCREENS[stage] = 'ui:' + stage
    # Leave and reselect the child so reopened text comes from saved preferences,
    # not the draft Entry. The shared API block validates the owning surface
    # before activation and independently observes the committed allowance.
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
    advance_after={'parent-save-enabled': 'step-2'},
)


class AllowanceJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
