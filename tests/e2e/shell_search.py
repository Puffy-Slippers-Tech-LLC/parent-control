"""Standard-account search qualification without activating the web suggestion."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop


SCREENS = {
    **fresh_desktop('other-child'),
    **{'entry-' + stage: tag for stage, tag in {
        'desktop': 'ui:fresh-standard-desktop',
        'system-prompt': 'ui:fresh-standard-desktop',
        'app-grid': 'ui:standard-app-grid',
        'search-focused': 'ui:standard-search-focused',
        'search-started': 'ui:standard-search-started',
        'search-entered': 'ui:standard-search-entered',
        'unavailable': 'ui:standard-search-qualified',
    }.items()},
}
PLAN = JourneyPlan(
    prefix='shell-search', worker_mode='shell_search', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}},
)


class ShellSearchJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
