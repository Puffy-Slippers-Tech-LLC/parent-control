"""Case 158: change a daily allowance and retain it across children and restart."""

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (allowance_selection, custom_allowance, fresh_desktop,
                            parent_management, parent_reopen, prefixed_stages)
from ui_observations import SettingsObservation


ENTRY = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
}
CHILD_READBACK = {
    'away-open': 'ui:existing-child-picker-opened',
    'away-focus': 'ui:existing-child-choice-highlighted',
    'away-selected': 'ui:existing-returned',
    'back-open': 'ui:child-picker-opened',
    'back-focus': 'ui:child-choice-highlighted',
    'back-selected': 'ui:parent-selected',
}
VALUES = {
    **allowance_selection('preset-15', (15,)),
    'preset-15-read': 'ui:allowance-15-read',
    **allowance_selection('custom-choice', ('custom',)),
    **custom_allowance('custom', 1),
    **prefixed_stages('edited', CHILD_READBACK),
}
PERSISTENCE = {
    **parent_reopen(),
    **prefixed_stages('persist', CHILD_READBACK),
}
PLAN = JourneyPlan(
    prefix='allowance-case', worker_mode='allowance_case',
    screen_tags={**ENTRY, **VALUES, **PERSISTENCE},
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in ENTRY}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in VALUES},
            **{stage: 'step-3' for stage in PERSISTENCE}},
    advance_after={'installed-greeter': 'step-1', 'allowance-configured': 'step-2',
                   'edited-back-selected': 'step-3'},
    settings_checks={
        'parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
        'edited-away-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'edited-back-selected': SettingsObservation('fixture-child', True, ('1 minutes',)),
        'persist-away-selected': 'edited-away-selected',
        'persist-back-selected': 'edited-back-selected',
    },
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800)


E2E_CASES = {'boundaries': execute}
