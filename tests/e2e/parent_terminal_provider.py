"""PARENT01 standard-account command, denial, and desktop-return qualification."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop


SCREENS = {
    **fresh_desktop('other-child'),
    'wrong-entry': 'ui:fresh-standard-desktop',
    'entry-desktop': 'ui:fresh-standard-desktop',
    'entry-parent-command': 'ui:standard-parent-command-launch',
    'entry-management-denied': 'ui:standard-management-denied',
    'entry-denial-closed': 'ui:standard-parent-closed',
}
PLAN = JourneyPlan(
    prefix='parent-terminal-provider', worker_mode='parent_terminal_provider',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'start' if stage == 'installed-greeter' else
               'step-2' if stage == 'entry-denial-closed' else 'step-1'
               for stage in SCREENS}},
    advance_after={'entry-management-denied': 'step-2'},
)


class ParentTerminalProviderJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
