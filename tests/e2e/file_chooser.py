"""FILE03 installed Open/Cancel qualification; no feedback submission."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop
from synthetic_files import fixture_actions
from attachment_composition import file_handoff

STAGES = ('feedback-open', 'chooser-wrong-entry', *file_handoff(),
          'chooser-attachments', 'chooser-reopen',
          'chooser-cancel', 'chooser-preserved')
SCREENS = {**fresh_desktop('parent'), 'parent-command': 'ui:parent-command-launch',
           **{stage: 'ui:' + stage for stage in (
               'parent-window', 'child-picker-opened', 'child-choice-highlighted',
               'parent-selected', *STAGES)}}
PLAN = JourneyPlan(
    prefix='file-chooser', worker_mode='file_chooser', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS}},
    stage_actions={'parent-selected': 'chooser-fixtures', 'chooser-preserved': 'chooser-cleanup'})


ACTIONS = fixture_actions(('standard',))
# Retained imports for existing compositions; implementation lives in the library.
stage_files = ACTIONS['chooser-fixtures']
cleanup_files = ACTIONS['chooser-cleanup']


def journey(context, progress, plan=PLAN):
    return InstalledJourney(context, progress, plan,
                            actions=ACTIONS)
