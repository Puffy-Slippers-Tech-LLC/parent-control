"""Finite qualification recipe for independent named-child custom saves."""
from accessible_ui import NAMED_CUSTOM_OPERATIONS, ALLOWANCE_KEYBOARD_OPERATIONS
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import (fresh_desktop, parent_management,
                            custom_child_selection, custom_save_entry, ordinary_custom_save)
from ui_observations import SettingsObservation

SCREENS = {**fresh_desktop('parent'), **parent_management()}
SCREENS.update(dict(zip(('child-picker-opened', 'child-choice-highlighted', 'parent-selected'),
                       custom_child_selection('entry', 'existing').values())))
SCREENS.update({'disabled-refused': 'ui:parent-custom-trace-disabled-refused',
                'setup': 'ui:named-custom-setup'})
for entry in ('first', 'second'):
    SCREENS.update(custom_save_entry(entry, 'existing'))
SCREENS.update({
    **ordinary_custom_save('riley', 'child', 7),
    **custom_child_selection('final-away', 'existing'),
    'jordan-final': 'ui:custom-6-reopen',
    **custom_child_selection('final-back', 'child'),
    'riley-final': 'ui:custom-7-reopen',
})
CHILDREN = {stage: ('child' if stage.startswith('riley-') else 'existing')
            for stage, tag in SCREENS.items()
            if tag[3:] in NAMED_CUSTOM_OPERATIONS or tag[3:] in ALLOWANCE_KEYBOARD_OPERATIONS
            or tag == 'ui:parent-custom-save-trace'}
PLAN = JourneyPlan(
    prefix='named-child-custom-saves', worker_mode='named_child_custom_saves',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-2' if stage.startswith(('second-', 'riley-', 'final-', 'jordan-final'))
               else 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    advance_after={'first-reopened': 'step-2'},
    child_bindings=CHILDREN,
    accessibility_inputs={f'{entry}-rapid': ('parent-custom-trace-focus', 6, 'custom-save')
                          for entry in ('first', 'second')},
    custom_inputs={f'{entry}-rapid': (5, 6) for entry in ('first', 'second')},
    settings_checks={
        **{f'{entry}-back-selected': SettingsObservation('existing-fixture-child', True, ('6 minutes',))
           for entry in ('first', 'second')},
        'final-away-selected': SettingsObservation('existing-fixture-child', True, ('6 minutes',)),
        'final-back-selected': SettingsObservation('fixture-child', True, ('7 minutes',)),
    },
)


def journey(context, progress):
    return InstalledJourney(context, progress, PLAN)
