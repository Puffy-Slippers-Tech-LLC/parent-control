"""FLOW01 same-user entry and FLOW16's bounded zero/positive setup slice."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management
from time_explanation import check_balances
from ui_observations import SettingsObservation

SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
    'zero-reread': 'ui:time-explanation-read',
    'wrong-child': 'ui:time-explanation-config-wrong-child',
    'wrong-window': 'ui:parent-new-window-refused',
    'close-ready': 'ui:parent-search-close-ready',
    'closed': 'ui:parent-search-closed',
    'same-window-absent': 'ui:parent-new-window-absent',
    'same-desktop': 'ui:desktop',
    **{'same-' + stage: tag for stage, tag in parent_management().items()},
    'same-allowance-configured': 'ui:time-explanation-setup-positive-read',
    'positive-reread': 'ui:time-explanation-read',
    'final-settings': 'ui:parent-selected',
}
PLAN = JourneyPlan(
    prefix='set-allowance', worker_mode='set_allowance', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in list(SCREENS)[list(SCREENS).index('close-ready'):]}},
    advance_after={'wrong-window': 'step-2'},
    settings_checks={
        'same-parent-selected': SettingsObservation('fixture-child', True, ('0 minutes',)),
        'final-settings': SettingsObservation('fixture-child', True, ('15 minutes',)),
    },
)


class SetAllowanceJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in ('allowance-configured', 'zero-reread'):
            check_balances(self, observed, 0)
        elif stage in ('same-allowance-configured', 'positive-reread'):
            check_balances(self, observed, 900)
