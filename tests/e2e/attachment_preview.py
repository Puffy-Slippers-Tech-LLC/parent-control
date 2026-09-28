"""FEED12 public preview applicability and independent unchanged-list check."""
from installed_journey import JourneyPlan
from attachment_items import SCREENS as ITEM_SCREENS
from file_chooser import stage_files, cleanup_files
from attachment_composition import AttachmentJourney as AttachmentPreviewJourney

SCREENS = {key: value for key, value in ITEM_SCREENS.items()
           if key not in ('attachment-remove', 'attachment-remaining')}
SCREENS.update({stage: 'ui:' + stage for stage in
                ('attachment-preview', 'attachment-preview-return')})
PLAN = JourneyPlan(
    prefix='attachment-preview', worker_mode='attachment_preview', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS}},
    stage_actions={'parent-selected': 'chooser-fixtures',
                   'attachment-preview-return': 'chooser-cleanup'})


def journey(context, progress):
    return AttachmentPreviewJourney(context, progress, PLAN,
        actions={'chooser-fixtures': stage_files, 'chooser-cleanup': cleanup_files})
