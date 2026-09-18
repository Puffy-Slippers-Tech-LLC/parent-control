"""Complete installed E2E-042 command-help recipe and INFO02 qualification."""

from installed_journey import JourneyPlan, record_installed_journey
from parent_about import SCREEN_TAGS

ENTRY = {stage: SCREEN_TAGS[stage] for stage in (
    'installed-greeter', 'other-parent-focused', 'wrong-recipient-refused',
    'parent-list', 'parent-focused', 'recipient-qualified', 'recipient-rechecked', 'desktop')}
BINDINGS = ('parent-help', 'station-help', 'parent-manual', 'station-manual')
SCREENS = {
    **ENTRY,
    'system-prompt': 'ui:help-system-prompt',
    'terminal-wrong-surface': 'ui:help-terminal-wrong-surface',
    'terminal-opened': 'ui:help-terminal-input',
    'terminal-opened-focused': 'ui:help-terminal-focused',
}
for binding in BINDINGS:
    SCREENS.update({
        binding + '-entry': 'ui:help-terminal-focused',
        binding + '-content': 'ui:help-content-' + binding,
        binding + '-returned': 'ui:help-shell-ready',
        binding + '-closed': 'ui:help-terminal-closed',
    })
SCREENS['complete'] = 'ui:help-terminal-closed'
PLAN = JourneyPlan(
    prefix='command-help', worker_mode='command_help', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'start' if stage == 'installed-greeter' else 'step-1' for stage in ENTRY},
            **{stage: 'step-1' for stage in SCREENS if stage not in ENTRY},
            **{binding + '-' + stage: 'step-2' for binding in BINDINGS
               for stage in ('entry', 'content', 'returned', 'closed')},
            'complete': 'step-3'},
    advance_after={'terminal-opened-focused': 'step-2', 'station-manual-closed': 'step-3'},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN)


E2E_CASES = {'command-help': execute}
