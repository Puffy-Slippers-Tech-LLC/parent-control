"""Case 159: real save ordering and independent named-child persistence."""

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (fresh_desktop, parent_management, parent_reopen,
                            custom_child_selection, custom_save_entry, ordinary_custom_save)
from ui_observations import SettingsObservation


ENTRY = {**fresh_desktop('parent'), **parent_management()}
ENTRY.update({
    'child-picker-opened': 'ui:existing-child-picker-opened',
    'child-choice-highlighted': 'ui:existing-child-choice-highlighted',
    'parent-selected': 'ui:existing-returned',
})
ENTRY.update({
    'disabled-refused': 'ui:parent-custom-trace-disabled-refused',
    'setup': 'ui:named-custom-setup',
})
EDITS = {
    **custom_save_entry('jordan', 'existing'),
    **ordinary_custom_save('riley', 'child', 7),
    **custom_child_selection('final-away', 'existing'),
    'jordan-final-read': 'ui:custom-6-reopen',
    **custom_child_selection('final-back', 'child'),
    'riley-final': 'ui:custom-7-reopen',
    'repeat-desktop': 'ui:desktop',
    'repeat-parent-command': 'ui:parent-command-launch',
    'repeat-parent-window': 'ui:parent-window',
    'repeat-window-count': 'ui:parent-window-count',
    'repeat-selected': 'ui:parent-selected',
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
    'disabled-refused', 'setup', 'jordan-open', 'jordan-focus',
    'jordan-wrong-child', 'jordan-rapid', 'jordan-saved',
    'jordan-reopened', 'jordan-final-read', 'jordan-after-restart')}
PLAN = JourneyPlan(
    prefix='save-order', worker_mode='save_order', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in ENTRY}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in EDITS},
            **{stage: 'step-3' for stage in PERSISTENCE}},
    advance_after={'installed-greeter': 'step-1', 'setup': 'step-2',
                   'repeat-selected': 'step-3'},
    child_bindings=CHILDREN,
    accessibility_inputs={'jordan-rapid': ('parent-custom-trace-focus', 6, 'custom-save')},
    keyboard_inputs={'jordan-rapid': (5, 6)},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'jordan-back-selected': SettingsObservation('existing-fixture-child', True, ('6 minutes',)),
        'final-away-selected': SettingsObservation('existing-fixture-child', True, ('6 minutes',)),
        'final-back-selected': SettingsObservation('fixture-child', True, ('7 minutes',)),
        'repeat-selected': 'final-back-selected',
        'reopen-jordan-selected': SettingsObservation('existing-fixture-child', True, ('6 minutes',)),
        'reopen-riley-selected': SettingsObservation('fixture-child', True, ('7 minutes',)),
    },
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800)


E2E_CASES = {'save-order': execute}
