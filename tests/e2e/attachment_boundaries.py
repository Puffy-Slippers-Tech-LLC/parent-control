"""Finite FEED06 rejection compositions; no Send or private draft reads."""
from attachment_preview import PLAN as PREVIEW_PLAN, AttachmentPreviewJourney
from installed_journey import JourneyPlan
from file_chooser import stage_files, cleanup_files
from synthetic_files import SyntheticFiles
from private_artifacts import require


def boundary_batch(batch):
    require(batch in ('count', 'sixth', 'maximum', 'oversized', 'total', 'overflow'),
            'attachment:batch')
    return {f'boundary-{batch}-{step}': f'ui:boundary-{batch}-{step}'
            for step in ('before', 'open', 'location', 'files', 'accept', 'result', 'preserved')}


SCREENS = {**PREVIEW_PLAN.screen_tags,
    'attachment-remove': 'ui:attachment-remove', 'attachment-remaining': 'ui:attachment-remaining',
    'boundary-clear-small': 'ui:boundary-clear-small',
    **boundary_batch('count'), **boundary_batch('sixth'),
    'boundary-clear-count': 'ui:boundary-clear-count',
    'boundary-exclude-logs': 'ui:boundary-exclude-logs',
    **boundary_batch('maximum'), **boundary_batch('oversized'), **boundary_batch('total'),
    'boundary-remove-total': 'ui:boundary-remove-total', **boundary_batch('overflow')}
PLAN = JourneyPlan(prefix='attachment-boundaries', worker_mode='attachment_boundaries',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS}},
    stage_actions={'parent-selected': 'attachment-fixtures',
                   'boundary-overflow-preserved': 'attachment-cleanup'})


def stage_boundaries(journey, guard):
    stage_files(journey, guard)
    journey.boundary_files = []
    receipts = {}
    for profile in ('count', 'sixth', 'maximum', 'oversized', 'total', 'overflow'):
        guard()
        files = SyntheticFiles(journey.transport, profile)
        journey.boundary_files.append(files)
        receipts[profile] = files.call('stage')
    return receipts


def cleanup_boundaries(journey, guard):
    results = []
    for files in journey.boundary_files:
        guard()
        results.append(files.call('cleanup'))
    results.append(cleanup_files(journey, guard))
    return {'owned_cleanup': all(result == {'absent': True} for result in results)}


class AttachmentBoundariesJourney(AttachmentPreviewJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.boundary_before = {}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if not stage.startswith('boundary-') or not stage.endswith(('-before', '-result', '-preserved')):
            return
        _, batch, step = stage.split('-')
        value = observed['ui']['boundary']
        current = (tuple(tuple(item) for item in value['items']), value['include_logs'])
        if step == 'before':
            require(batch not in self.boundary_before, 'attachment:boundary-replay')
            self.boundary_before[batch] = current
        elif batch in ('sixth', 'oversized', 'overflow'):
            require(batch in self.boundary_before and current == self.boundary_before[batch],
                    'attachment:rejection-list-changed')


def journey(context, progress):
    return AttachmentBoundariesJourney(context, progress, PLAN,
        actions={'attachment-fixtures': stage_boundaries, 'attachment-cleanup': cleanup_boundaries})
