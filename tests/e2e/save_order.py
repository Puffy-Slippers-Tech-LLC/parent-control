"""Case 159: real save ordering and independent named-child persistence."""

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (fresh_desktop, parent_management, parent_reopen,
                            custom_child_selection, custom_save_entry, ordinary_custom_save,
                            allowance_selection)
from ui_observations import SettingsObservation
from journey_checks import AllowanceJourney


ENTRY = {**fresh_desktop('parent'), **parent_management()}
ENTRY.update({
    'child-picker-opened': 'ui:existing-child-picker-opened',
    'child-choice-highlighted': 'ui:existing-child-choice-highlighted',
    'parent-selected': 'ui:existing-returned',
})
ENTRY.update({
    'setup': 'ui:named-custom-setup',
})
EDITS = {
    **allowance_selection('jordan-preset', (15,)),
    **custom_save_entry('jordan', 'existing', qualification=False),
    **ordinary_custom_save('riley', 'child', 7, qualification=False),
    **custom_child_selection('final-away', 'existing'),
    'jordan-final-read': 'ui:custom-6-reopen',
    **custom_child_selection('final-back', 'child'),
    'riley-final': 'ui:custom-7-reopen',
}
PERSISTENCE = {
    **parent_reopen(),
    **custom_child_selection('reopen-jordan', 'existing'),
    'jordan-after-restart': 'ui:custom-6-reopen',
    **custom_child_selection('reopen-riley', 'child'),
    'riley-reopened': 'ui:custom-7-reopen',
}
SCREENS = {**ENTRY, **EDITS, **PERSISTENCE}
CHILDREN = {stage: 'existing' for stage in (
    'setup', 'jordan-rapid',
    'jordan-final-read', 'jordan-after-restart')}
CHILDREN.update({stage: 'existing' for stage in (
    *allowance_selection('jordan-preset', (15,)),
    *allowance_selection('jordan-choice', ('custom',)))})
PLAN = JourneyPlan(
    prefix='save-order', worker_mode='save_order', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in ENTRY}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in EDITS},
            **{stage: 'step-3' for stage in PERSISTENCE}},
    advance_after={'installed-greeter': 'step-1', 'setup': 'step-2',
                   'riley-final': 'step-3'},
    child_bindings=CHILDREN,
    accessibility_inputs={'jordan-rapid': ('parent-custom-trace-focus', 6, 'custom-save')},
    custom_inputs={'jordan-rapid': (5, 6)},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'final-away-selected': SettingsObservation('existing-fixture-child', True, ('6 minutes',)),
        'final-back-selected': SettingsObservation('fixture-child', True, ('7 minutes',)),
        'reopen-jordan-selected': SettingsObservation('existing-fixture-child', True, ('6 minutes',)),
        'reopen-riley-selected': SettingsObservation('fixture-child', True, ('7 minutes',)),
    },
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800, journey_type=AllowanceJourney)


E2E_CASES = {'save-order': execute}
