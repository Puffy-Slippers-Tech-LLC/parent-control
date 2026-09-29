"""FEED07/13 fixed attachment metadata and removal qualification."""
from installed_journey import JourneyPlan
from file_chooser import SCREENS, journey as chooser_journey
from attachment_composition import attachment_removal

SCREENS = {**SCREENS, 'attachment-details': 'ui:attachment-details',
           **attachment_removal()}
# Wrong-entry is checked before any files are supplied.
SCREENS = {key: value for stage, tag in SCREENS.items()
           for key, value in ([(stage, tag), ('attachment-wrong-entry', 'ui:attachment-wrong-entry')]
                              if stage == 'feedback-open' else [(stage, tag)])}
PLAN = JourneyPlan(
    prefix='attachment-items', worker_mode='attachment_items', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS}},
    stage_actions={'parent-selected': 'chooser-fixtures', 'attachment-remaining': 'chooser-cleanup'})


def journey(context, progress):
    return chooser_journey(context, progress, PLAN)
