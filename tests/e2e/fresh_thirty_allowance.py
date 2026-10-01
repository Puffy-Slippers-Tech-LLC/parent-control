"""FLOW16 fresh Parent setup with a saved thirty-minute daily allowance."""

from dataclasses import replace
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management
from time_explanation import check_balances
from ui_observations import SettingsObservation

SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'balance-reread': 'ui:time-explanation-read',
    'wrong-child': 'ui:time-explanation-config-wrong-child',
    'wrong-state': 'ui:time-explanation-config-wrong-state',
    'wrong-window': 'ui:parent-new-window-refused',
    'final-settings': 'ui:parent-selected',
}
PLAN = JourneyPlan(
    prefix='fresh-thirty-allowance', worker_mode='fresh_thirty_allowance', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in ('balance-reread', 'wrong-child',
                                           'wrong-state', 'wrong-window', 'final-settings')}},
    advance_after={'allowance-configured': 'step-2'},
    settings_checks={'parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
                     'final-settings': SettingsObservation('fixture-child', True, ('30 minutes',))},
)
JORDAN_PLAN = replace(
    PLAN, prefix='jordan-thirty-allowance', worker_mode='jordan_thirty_allowance',
    screen_tags={**SCREENS,
                 'child-picker-opened': 'ui:existing-child-picker-opened',
                 'child-choice-highlighted': 'ui:existing-child-choice-highlighted',
                 'parent-selected': 'ui:existing-returned',
                 'final-settings': 'ui:existing-returned'},
    child_bindings={stage: 'existing' for stage in
                    ('allowance-configured', 'balance-reread', 'wrong-child', 'wrong-state')},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'final-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
)


class FreshThirtyAllowanceJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in ('allowance-configured', 'balance-reread'):
            check_balances(self, observed, 1800)
