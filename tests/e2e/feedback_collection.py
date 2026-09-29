"""FEED09 waits for finished diagnostics on two independent entries."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop


SCREENS = {
    **fresh_desktop('parent'),
    'parent-command': 'ui:parent-command-launch',
    **{s: 'ui:' + s for s in ('parent-window', 'child-picker-opened',
                             'child-choice-highlighted', 'parent-selected')},
    **{stage: operation for entry in ('first', 'second') for stage, operation in {
        f'{entry}-open': 'ui:feedback-open',
        f'{entry}-collection': 'ui:feedback-collection-ready',
        f'{entry}-independent': 'ui:feedback-state-empty',
        f'{entry}-refused': 'ui:feedback-collection-refused',
        f'{entry}-close': 'ui:feedback-close',
    }.items()},
}
PLAN = JourneyPlan(
    prefix='feedback-collection', worker_mode='feedback_collection', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{s: 'step-1' for s in SCREENS}, 'installed-greeter': 'start',
            **{f'second-{s}': 'step-2' for s in ('open', 'collection', 'independent', 'refused', 'close')}},
    advance_after={'first-close': 'step-2'},
)


def journey(context, progress):
    return InstalledJourney(context, progress, PLAN)
