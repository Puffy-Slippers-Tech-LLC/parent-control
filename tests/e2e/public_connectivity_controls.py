"""Task 193's fixed Parent usability qualification, reusing UI17's worker."""
from dataclasses import replace

from installed_journey import InstalledJourney
from offline_controls import offline_controls
from parent_toggle import PLAN as TOGGLE_PLAN


CONTROLS = tuple((input_operation, result_operation, {
    'child': 'fixture-child', 'result': 'saved', 'limit_enabled': enabled,
    'child_selector_enabled': True, 'toggle_enabled': True,
    'allowance_enabled': enabled,
}) for input_operation, result_operation, enabled in (
    ('parent-toggle-enabled', 'parent-save-enabled', True),
    ('parent-toggle-disabled', 'parent-save-disabled', False),
))
PLAN = replace(TOGGLE_PLAN,
    stage_actions={'wrong-child-refused': 'offline-parent-controls'})


def qualify(journey, guard):
    return offline_controls(journey, guard, entry='parent-save-disabled',
                            controls=CONTROLS, window='switch-parent-before')


def journey(context, progress):
    return InstalledJourney(context, progress, PLAN,
                            actions={'offline-parent-controls': qualify})
