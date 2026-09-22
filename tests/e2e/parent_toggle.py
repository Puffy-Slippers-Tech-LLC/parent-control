"""UI17's fixed installed Parent Screen time limit qualification."""

from installed_journey import InstalledJourney, JourneyPlan


PLAN = JourneyPlan(
    prefix='parent-toggle', worker_mode='parent_toggle',
    screen_tags={
        'parent-window': 'ui:parent-window',
        'child-picker-opened': 'ui:child-picker-opened',
        'child-choice-highlighted': 'ui:child-choice-highlighted',
        'parent-selected': 'ui:parent-selected',
        'wrong-control-refused': 'ui:parent-toggle-wrong-refused',
        'limit-enabled': 'ui:parent-toggle-enabled',
        'limit-disabled': 'ui:parent-toggle-disabled',
        'limit-current': 'ui:parent-toggle-current',
        'hidden-control-refused': 'ui:parent-toggle-hidden-refused',
        'disabled-settings': 'ui:parent-toggle-disabled-settings',
    },
    phases={
        'ready': 'setup', 'setup-detached': 'setup',
        'parent-window': 'start', 'child-picker-opened': 'step-1',
        'child-choice-highlighted': 'step-1', 'parent-selected': 'step-1',
        'wrong-control-refused': 'step-1', 'limit-enabled': 'step-1',
        'limit-disabled': 'step-2', 'limit-current': 'step-2',
        'hidden-control-refused': 'step-2', 'disabled-settings': 'step-2',
    },
    advance_after={'limit-enabled': 'step-2'},
)


class ParentToggleJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
