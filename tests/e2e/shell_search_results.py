"""Fixed installed qualification of the Parent Shell search result."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop


PLAN = JourneyPlan(
    prefix='shell-search-results', worker_mode='shell_search_results',
    screen_tags={
        **fresh_desktop('parent'),
        'system-prompt': 'ui:fresh-parent-desktop',
        'app-grid': 'ui:parent-search-ready',
        'search-focused': 'ui:parent-search-focused',
        'search-started': 'ui:shell-search-started',
        'search-entered': 'ui:parent-search-entered',
        'wrong-result-refused': 'ui:shell-search-wrong-result-refused',
        'result': 'ui:app-grid',
        'search-cleared': 'ui:shell-search-cleared',
        'dismissed': 'ui:shell-search-dismissed',
    },
    phases={
        'ready': 'setup', 'setup-detached': 'setup',
        **{stage: 'start' if stage == 'installed-greeter' else 'step-1'
           for stage in fresh_desktop('parent')},
        **{stage: 'step-2' for stage in (
            'system-prompt', 'app-grid', 'search-focused', 'search-started',
            'search-entered', 'wrong-result-refused', 'result', 'search-cleared',
            'dismissed')},
    },
    advance_after={'desktop': 'step-2'},
)


class ShellSearchResultsJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
