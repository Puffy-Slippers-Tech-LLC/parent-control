"""Complete E2E-004 terminal route, with independent entry qualification."""

from installed_journey import JourneyPlan, record_installed_journey
from parent_access import PLAN as GRID_PLAN


ENTRY = {stage: GRID_PLAN.screen_tags[stage] for stage in (
    'installed-greeter', 'other-parent-focused', 'wrong-recipient-refused',
    'standard-list', 'standard-focused', 'standard-recipient-qualified',
    'standard-recipient-rechecked', 'desktop', 'system-prompt')}
SCREENS = {
    **ENTRY,
    'terminal-wrong-surface': 'ui:standard-terminal-wrong-surface',
    'terminal-opened': 'ui:standard-terminal-input',
    'terminal-opened-focused': 'ui:standard-terminal-focused',
    'terminal-first-closed': 'ui:standard-terminal-closed',
    'terminal-input': 'ui:standard-terminal-input',
    'terminal-focused': 'ui:standard-terminal-focused',
    'management-denied': 'ui:standard-management-denied',
    'denial-closed': 'ui:standard-denial-closed',
    'terminal-closed': 'ui:standard-terminal-closed',
}
PLAN = JourneyPlan(
    prefix='parent-terminal', worker_mode='parent_terminal', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: GRID_PLAN.phases[stage] for stage in ENTRY},
            **{stage: 'step-1' for stage in SCREENS if stage not in ENTRY},
            **{stage: 'step-2' for stage in ('management-denied', 'denial-closed', 'terminal-closed')}},
    advance_after={'terminal-focused': 'step-2'},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN)


E2E_CASES = {'terminal': execute}
