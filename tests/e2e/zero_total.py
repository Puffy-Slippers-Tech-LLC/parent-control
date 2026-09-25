"""Case 161: zero balances keep idle Revoke disabled with limits on and off."""

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management
from ui_observations import SettingsObservation


ENTRY = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
}
AVAILABILITY = {
    'revoke-on': 'ui:parent-revoke-disabled-on',
    'limit-disabled': 'ui:parent-toggle-disabled',
    'save-disabled': 'ui:parent-save-disabled',
    'revoke-off': 'ui:parent-revoke-disabled-off',
}
PLAN = JourneyPlan(
    prefix='zero-total', worker_mode='zero_total',
    screen_tags={**ENTRY, **AVAILABILITY, 'retained-allowance': 'ui:parent-selected'},
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in ENTRY}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in AVAILABILITY}, 'retained-allowance': 'step-3'},
    advance_after={'installed-greeter': 'step-1', 'allowance-configured': 'step-2',
                   'revoke-off': 'step-3'},
    settings_checks={
        'parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
        'retained-allowance': SettingsObservation('fixture-child', False, ('0 minutes',)),
    },
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800)


E2E_CASES = {'zero-total': execute}
