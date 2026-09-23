"""SEARCH05 administrator launch, independent re-entry and normal closure."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_search


SCREENS = {
    **fresh_desktop('parent'),
    **parent_search(),
    'parent-window': 'ui:parent-window',
    'close-ready': 'ui:parent-search-close-ready',
    'closed': 'ui:parent-search-closed',
    'repeat-wrong-entry': 'ui:help-desktop-clear',
    'repeat-desktop': 'ui:fresh-parent-desktop',
    **{'repeat-' + stage: tag for stage, tag in parent_search().items()},
    'repeat-parent-window': 'ui:parent-window',
    'repeat-close-ready': 'ui:parent-search-close-ready',
    'repeat-closed': 'ui:parent-search-closed',
}
PLAN = JourneyPlan(
    prefix='parent-search-launch', worker_mode='parent_search_launch',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}},
)


class ParentSearchLaunchJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
