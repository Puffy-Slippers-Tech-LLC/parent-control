"""Installed E2E-042 command documentation through guarded SSH stdout."""

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop

ENTRY = fresh_desktop('parent')
BINDINGS = ('parent-help', 'station-help', 'parent-manual', 'station-manual')
SCREENS = {
    **ENTRY,
}
for binding in BINDINGS:
    SCREENS.update({
        binding + '-content': 'command:' + binding,
        binding + '-desktop': 'ui:help-desktop-clear',
    })
SCREENS['complete'] = 'ui:help-desktop-clear'
PLAN = JourneyPlan(
    prefix='command-help', worker_mode='command_help', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'start' if stage == 'installed-greeter' else 'step-1' for stage in ENTRY},
            **{stage: 'step-1' for stage in SCREENS if stage not in ENTRY},
            **{binding + '-' + stage: 'step-2' for binding in BINDINGS
               for stage in ('content', 'desktop')},
            'complete': 'step-3'},
    advance_after={'desktop': 'step-2', 'station-manual-desktop': 'step-3'},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN)


E2E_CASES = {'command-help': execute}
