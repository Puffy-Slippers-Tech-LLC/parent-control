"""One caller-owned text edit inside a sampled public feedback trace."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop

SCREENS = {
    **fresh_desktop('parent'),
    'parent-command': 'ui:parent-command-launch',
    **{stage: 'ui:' + stage for stage in (
        'parent-window', 'child-picker-opened', 'child-choice-highlighted',
        'parent-selected', 'feedback-open')},
    **{stage: operation for entry in ('first', 'second') for stage, operation in (
        (f'trace-{entry}-start', 'ui:feedback-trace-start'),
        *((f'{entry}-{suffix}', f'ui:text-body-first-{suffix}')
          for suffix in ('focus', 'selected', 'read')),
        (f'trace-{entry}-finish', 'ui:feedback-trace-finish'),
        *((*((f'clear-{suffix}', f'ui:text-body-clear-{suffix}')
              for suffix in ('focus', 'selected', 'read')),
           ('trace-close', 'ui:feedback-close'),
           ('trace-wrong-entry', 'ui:feedback-state-wrong-entry'),
           ('trace-open-again', 'ui:feedback-open')) if entry == 'first' else ()),
    )},
}
PLAN = JourneyPlan(
    prefix='trace-transition', worker_mode='trace_transition', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in SCREENS
               if stage.startswith(('clear-', 'trace-close', 'trace-wrong', 'trace-open',
                                    'trace-second', 'second-'))}},
    advance_after={'trace-first-finish': 'step-2'},
    trace_bindings={f'trace-{entry}-start': 'body-first' for entry in ('first', 'second')},
)


def journey(context, progress):
    return InstalledJourney(context, progress, PLAN)
