"""FEED12 public preview applicability and independent unchanged-list check."""
from installed_journey import InstalledJourney, JourneyPlan
from attachment_items import SCREENS as ITEM_SCREENS
from file_chooser import stage_files, cleanup_files
from private_artifacts import require

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


class AttachmentPreviewJourney(InstalledJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.before_preview = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage not in ('attachment-details', 'attachment-preview', 'attachment-preview-return'):
            return
        current = tuple(tuple(item) for item in observed['ui']['attachment']['items'])
        if stage == 'attachment-details':
            require(self.before_preview is None, 'attachment:preview-replay')
            self.before_preview = current
        else:
            require(self.before_preview is not None and current == self.before_preview,
                    'attachment:preview-list-changed')
