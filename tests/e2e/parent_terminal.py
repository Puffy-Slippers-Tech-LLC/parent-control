"""Case 6: direct Parent command denial (stable legacy variant ID: terminal)."""

from installed_journey import JourneyPlan, record_installed_journey
from parent_access import PLAN as GRID_PLAN


ENTRY = {stage: GRID_PLAN.screen_tags[stage] for stage in (
    'installed-greeter', 'other-parent-focused', 'wrong-recipient-refused',
    'standard-list', 'standard-focused', 'standard-recipient-qualified',
    'standard-recipient-rechecked', 'desktop')}
SCREENS = {
    **ENTRY,
    'parent-command': 'ui:standard-parent-command-launch',
    'management-denied': 'ui:standard-management-denied',
    'denial-closed': 'ui:standard-parent-closed',
}
PLAN = JourneyPlan(
    prefix='parent-terminal', worker_mode='parent_terminal', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: GRID_PLAN.phases[stage] for stage in ENTRY},
            **{stage: 'step-1' for stage in SCREENS if stage not in ENTRY},
            **{stage: 'step-2' for stage in ('parent-command', 'management-denied', 'denial-closed')}},
    advance_after={'desktop': 'step-2'},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN)


E2E_CASES = {'terminal': execute}
