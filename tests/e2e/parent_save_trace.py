"""Finite qualification of one Parent save and its settled public result."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop


SCREENS = {
    **fresh_desktop('parent'),
    'parent-command': 'ui:parent-command-launch',
    **{s: 'ui:' + s for s in ('parent-window', 'child-picker-opened',
       'child-choice-highlighted', 'parent-selected')},
    **{stage: operation for entry in ('first', 'second') for stage, operation in {
        f'{entry}-disabled': 'ui:parent-save-disabled',
        f'{entry}-wrong-child': 'ui:parent-trace-wrong-child-refused',
        f'{entry}-wrong-surface': 'ui:parent-trace-wrong-surface-refused',
        f'{entry}-observed-enable': 'ui:parent-save-trace',
        f'{entry}-independent-saved': 'ui:parent-save-enabled',
        **({'restore-disabled': 'ui:parent-toggle-disabled'} if entry == 'first' else {}),
    }.items()},
}
PLAN = JourneyPlan(
    prefix='parent-save-trace', worker_mode='parent_save_trace', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{s: 'step-1' for s in SCREENS}, 'installed-greeter': 'start',
            'restore-disabled': 'step-2',
            **{f'second-{s}': 'step-2' for s in ('disabled', 'wrong-child', 'wrong-surface',
                                              'observed-enable', 'independent-saved')}},
    advance_after={'first-independent-saved': 'step-2'},
    accessibility_inputs={f'{entry}-observed-enable': ('parent-toggle-enabled', True, 'save')
                          for entry in ('first', 'second')},
)


def journey(context, progress):
    return InstalledJourney(context, progress, PLAN)
