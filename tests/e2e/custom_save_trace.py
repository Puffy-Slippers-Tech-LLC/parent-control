"""Finite independent qualification of rapid saves and final allowance readback."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management, allowance_selection
from ui_observations import SettingsObservation

SCREENS = {**fresh_desktop('parent'), **parent_management(),
           'disabled-refused': 'ui:parent-custom-trace-disabled-refused',
           'enable': 'ui:parent-toggle-enabled', 'enabled': 'ui:parent-save-enabled'}
for entry in ('first', 'second'):
    SCREENS.update({
        **allowance_selection(entry + '-preset', (15,)),
        **allowance_selection(entry + '-choice', ('custom',)),
        f'{entry}-open': 'ui:custom-6-open',
        f'{entry}-focus': 'ui:text-daily-6-focus',
        f'{entry}-wrong-child': 'ui:parent-trace-wrong-child-refused',
        f'{entry}-wrong-surface': 'ui:parent-trace-wrong-surface-refused',
        f'{entry}-rapid': 'ui:parent-custom-save-trace',
        f'{entry}-saved': 'ui:custom-6-saved',
        **{f'{entry}-{suffix}': 'ui:' + operation for suffix, operation in (
            ('away-open', 'existing-child-picker-opened'),
            ('away-focus', 'existing-child-choice-highlighted'),
            ('away-selected', 'existing-returned'),
            ('back-open', 'child-picker-opened'),
            ('back-focus', 'child-choice-highlighted'),
            ('back-selected', 'parent-selected'))},
        f'{entry}-reopened': 'ui:custom-6-reopen',
    })

PLAN = JourneyPlan(
    prefix='custom-save-trace', worker_mode='custom_save_trace', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{s: 'step-2' if s.startswith('second-') else 'step-1' for s in SCREENS},
            'installed-greeter': 'start'},
    advance_after={'first-reopened': 'step-2'},
    accessibility_inputs={f'{entry}-rapid': ('parent-custom-trace-focus', 6, 'custom-save')
                          for entry in ('first', 'second')},
    custom_inputs={f'{entry}-rapid': (5, 6) for entry in ('first', 'second')},
    settings_checks={f'{entry}-back-selected': SettingsObservation(
        'fixture-child', True, ('6 minutes',)) for entry in ('first', 'second')},
)


def journey(context, progress):
    return InstalledJourney(context, progress, PLAN)
