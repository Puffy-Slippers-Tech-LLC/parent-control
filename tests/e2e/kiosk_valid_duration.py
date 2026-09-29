"""REQUEST04/05/06/08 valid kiosk choices; no approval or complete case credit."""

from installed_journey import JourneyPlan
from kiosk_eligible_choices import SCREENS as ACCOUNT_SCREENS
from request_composition import KioskRequestJourney

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


class KioskValidDurationJourney(KioskRequestJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
