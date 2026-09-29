"""PARENT09/PARENT20 and FLOW02 qualification with ordinary saved allowances."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop
from journey_checks import check_balances
from private_artifacts import require

STAGES = (
    'parent-toggle-enabled', 'parent-save-enabled',
    'allowance-15-select', 'allowance-15-read',
    'time-explanation-collapse', 'time-explanation-collapsed',
    'time-explanation-expand', 'time-explanation-wrong-child',
    'time-explanation-read', 'time-explanation-reread',
    'time-explanation-reach-wrong-child', 'time-explanation-config-wrong-child',
    'time-explanation-config-wrong-state',
    'time-explanation-collapse-again',
    'time-explanation-reach-read', 'time-explanation-reach-reread',
    'time-explanation-off-read', 'time-explanation-positive-read',
    'time-explanation-zero-read', 'time-explanation-zero-reread',
)
SCREENS = {
    **fresh_desktop('parent'),
    'parent-command': 'ui:parent-command-launch',
    **{stage: 'ui:' + stage for stage in (
        'parent-window', 'child-picker-opened', 'child-choice-highlighted',
        'parent-selected', *STAGES)},
}
SCREENS['time-explanation-collapse-again'] = 'ui:time-explanation-collapse'


PLAN = JourneyPlan(
    prefix='time-explanation', worker_mode='time_explanation', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in STAGES if stage.startswith('time-explanation-')}},
    advance_after={'allowance-15-read': 'step-2'},
)


class TimeExplanationJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in ('time-explanation-read', 'time-explanation-reread'):
            require((stage == 'time-explanation-read') ==
                    (getattr(self, 'earlier_time_observation', None) is None),
                    'time-explanation:read-order')
            check_balances(self, observed)
        elif stage in ('time-explanation-reach-read', 'time-explanation-reach-reread',
                       'time-explanation-positive-read'):
            check_balances(self, observed)
        elif stage in ('time-explanation-zero-read', 'time-explanation-zero-reread'):
            check_balances(self, observed, 0)
