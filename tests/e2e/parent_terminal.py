"""Case 6: direct Parent command denial (stable legacy variant ID: terminal)."""

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop


ENTRY = fresh_desktop('other-child')
SCREENS = {
    **ENTRY,
    'parent-command': 'ui:standard-parent-command-launch',
    'management-denied': 'ui:standard-management-denied',
    'denial-closed': 'ui:standard-parent-closed',
}
PLAN = JourneyPlan(
    prefix='parent-terminal', worker_mode='parent_terminal', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'start' if stage == 'installed-greeter' else 'step-1' for stage in ENTRY},
            **{stage: 'step-2' for stage in ('parent-command', 'management-denied', 'denial-closed')}},
    advance_after={'desktop': 'step-2'},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN)


E2E_CASES = {'terminal': execute}
