"""Task 004a's fixed repeated-page capability, without scenario registration."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop

INVOCATIONS = (
    'wrong-child-refused', 'baseline-first', 'apps-first', 'return-first',
    'baseline-second', 'apps-second', 'return-second',
)
SCREEN_TAGS = {
    **fresh_desktop('parent'),
    'parent-command': 'ui:parent-command-launch',
    'parent-window': 'ui:parent-window',
    'child-picker-opened': 'ui:child-picker-opened',
    'child-choice-highlighted': 'ui:child-choice-highlighted',
    'parent-selected': 'ui:parent-selected',
    'wrong-child-refused': 'ui:parent-page-wrong-child-refused',
    'baseline-first': 'ui:parent-selected',
    'apps-first': 'ui:parent-apps-page',
    'return-first': 'ui:parent-screen-page',
    'baseline-second': 'ui:parent-selected',
    'apps-second': 'ui:parent-apps-page',
    'return-second': 'ui:parent-screen-page',
}
PLAN = JourneyPlan(
    prefix='repeated-operations', worker_mode='repeated_operations',
    screen_tags=SCREEN_TAGS,
    phases={
        'ready': 'setup', 'setup-detached': 'setup',
        **{stage: 'step-1' for stage in SCREEN_TAGS},
        'installed-greeter': 'start',
        **{stage: 'step-2' for stage in INVOCATIONS[-3:]},
    },
    advance_after={'return-first': 'step-2'},
    invocations=INVOCATIONS,
    settings_checks={'return-first': 'baseline-first', 'return-second': 'baseline-second'},
    assertions_after={'return-first': 'first-return', 'return-second': 'second-return'},
)


class RepeatedOperationsJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
