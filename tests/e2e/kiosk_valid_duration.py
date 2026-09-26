"""REQUEST04/05/06/08 valid kiosk choices; no approval or complete case credit."""

from installed_journey import InstalledJourney, JourneyPlan
from kiosk_eligible_choices import SCREENS as ACCOUNT_SCREENS
from private_artifacts import require

SCREENS = {}
for stage, operation in ACCOUNT_SCREENS.items():
    SCREENS[stage] = operation
    if stage == 'wrong-entry':
        SCREENS['valid-wrong-entry'] = 'ui:parent-kiosk-valid-refused'
    if stage == 'save-enabled':
        for item in ('allowance-15-select', 'allowance-15-read', 'time-explanation-read'):
            SCREENS[item] = 'ui:' + item
for item in ('kiosk-valid-preset-select', 'kiosk-valid-preset-read', 'kiosk-valid-custom-open',
             'text-kiosk-fraction-focus', 'text-kiosk-fraction-selected', 'text-kiosk-fraction-read',
             'kiosk-valid-fraction-read', 'kiosk-valid-rest-select', 'kiosk-valid-rest-read',
             'kiosk-valid-soft-select', 'kiosk-valid-soft-read',
             'kiosk-valid-excluded-select', 'kiosk-valid-excluded-read',
             'kiosk-request-cancel', 'gdm-station-returned'):
    SCREENS[item] = 'ui:' + item

PLAN = JourneyPlan(
    prefix='kiosk-valid-duration', worker_mode='kiosk_valid_duration', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in list(SCREENS)[list(SCREENS).index('switch-user'):]}},
    advance_after={'time-explanation-read': 'step-2'},
)


class KioskValidDurationJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
        self.balance = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'time-explanation-read':
            self.balance = observed['ui']['time_explanation']
        choice = observed.get('ui', {}).get('valid_choice')
        if choice is None:
            return
        require(self.balance is not None, 'kiosk-valid:missing-balance')
        elapsed = (choice['observed_monotonic_ns'] - self.balance['observed_monotonic_ns']) / 1e9
        require(0 <= elapsed <= 600, 'kiosk-valid:elapsed-bound')
        if choice['estimate']['kind'] == 'fixed':
            daily, grant = (self.balance[key]['seconds'] for key in ('daily', 'one_time'))
            requested = choice['request']['duration_seconds']
            actual = choice['estimate']['seconds']
            precision = max(self.balance[key]['precision_seconds'] for key in ('daily', 'one_time'))
            require(max(0, max(daily, grant) - elapsed) + requested - precision <= actual
                    <= max(daily, grant) + requested + precision, 'kiosk-valid:estimate-bounds')
            # The fresh selected child has never signed in: a broad elapsed
            # interval must not conceal a wrong request or double-added balance.
            require(abs(actual - (max(daily, grant) + requested)) <= precision,
                    'kiosk-valid:unused-child-estimate')
        observed['comparison'] = {'estimate_bounds': True, 'no_authentication': True}
