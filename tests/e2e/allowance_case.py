"""Case 158: representative presets, custom boundaries and per-child persistence."""

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management
from allowance_boundaries import BOUNDARY_SCREENS
from allowance_values import REPRESENTATIVE_PRESETS
from ui_observations import SettingsObservation


ENTRY = {
    **fresh_desktop('parent'), **parent_management(),
    'editor-disabled': 'ui:allowance-disabled',
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
}
VALUES = {
    **{f'preset-{value}-{action}': f'ui:allowance-{value}-{action}'
       for value in REPRESENTATIVE_PRESETS for action in ('select', 'read')},
    **BOUNDARY_SCREENS,
}
PERSISTENCE = {
    'prior-window': 'ui:parent-window',
    'close-ready': 'ui:parent-restart-ready',
    'closed': 'ui:parent-search-closed',
    'same-desktop': 'ui:desktop',
    'same-parent-command': 'ui:parent-command-launch',
    'same-parent-window': 'ui:parent-window',
    'initial-selection': 'ui:parent-initial-selection',
    'persist-away-open': 'ui:existing-child-picker-opened',
    'persist-away-focus': 'ui:existing-child-choice-highlighted',
    'persist-away-selected': 'ui:existing-returned',
    'persist-back-open': 'ui:child-picker-opened',
    'persist-back-focus': 'ui:child-choice-highlighted',
    'persist-back-selected': 'ui:parent-selected',
    'persist-saved': 'ui:allowance-15-read',
    'persist-editor': 'ui:custom-15-reopen',
}
PLAN = JourneyPlan(
    prefix='allowance-case', worker_mode='allowance_case',
    screen_tags={**ENTRY, **VALUES, **PERSISTENCE},
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in ENTRY}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in VALUES},
            **{stage: 'step-3' for stage in PERSISTENCE}},
    advance_after={'installed-greeter': 'step-1', 'allowance-configured': 'step-2',
                   'invalid-over-reopen': 'step-3'},
    settings_checks={
        'parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
        'persist-away-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'persist-back-selected': SettingsObservation('fixture-child', True, ('15 minutes',)),
    },
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800)


E2E_CASES = {'boundaries': execute}
