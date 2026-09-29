"""FILE03 Save qualification; FILE08 archive inspection remains separate."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop
from synthetic_files import save_destination_actions
from attachment_composition import save_handoff, save_cancellation


SCREENS = {
    **fresh_desktop('parent'), 'parent-command': 'ui:parent-command-launch',
    **{s: 'ui:' + s for s in ('parent-window', 'child-picker-opened',
                              'child-choice-highlighted', 'parent-selected')},
    **{stage: operation for entry in ('first', 'second') for stage, operation in {
        entry + '-feedback': 'ui:feedback-open',
        entry + '-collection': 'ui:feedback-collection-ready',
        entry + '-refused': 'ui:save-chooser-wrong-entry',
        **save_handoff(entry),
        **save_cancellation(entry),
        entry + '-close': 'ui:feedback-close',
    }.items()},
}
PLAN = JourneyPlan(
    prefix='save-chooser', worker_mode='save_chooser', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{s: 'step-1' for s in SCREENS}},
    stage_actions={stage: action for entry in ('first', 'second') for stage, action in {
        entry + '-refused': 'save-prepare', entry + '-result': 'save-read',
        entry + '-preserved': 'save-preserved', entry + '-close': 'save-cleanup',
    }.items()},
)


def journey(context, progress):
    return InstalledJourney(context, progress, PLAN, actions=save_destination_actions())
