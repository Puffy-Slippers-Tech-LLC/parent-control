"""FILE03 installed Open/Cancel qualification; no feedback submission."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop
from synthetic_files import SyntheticFiles

STAGES = ('feedback-open', 'chooser-wrong-entry', 'chooser-open',
          'chooser-location', 'chooser-files',
          'chooser-accept', 'chooser-attachments', 'chooser-reopen',
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


def stage_files(journey, guard):
    guard()
    journey.chooser_files = SyntheticFiles(journey.transport)
    return journey.chooser_files.call('stage')


def cleanup_files(journey, guard):
    guard()
    return journey.chooser_files.call('cleanup')


def journey(context, progress):
    return InstalledJourney(context, progress, PLAN,
                            actions={'chooser-fixtures': stage_files, 'chooser-cleanup': cleanup_files})
