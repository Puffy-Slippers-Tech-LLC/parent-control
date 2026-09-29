"""Finite FEED06 rejection compositions; no Send or private draft reads."""
from attachment_preview import PLAN as PREVIEW_PLAN
from installed_journey import JourneyPlan
from synthetic_files import fixture_actions
from attachment_composition import (boundary_batch, attachment_removal,
                                    AttachmentJourney as AttachmentBoundariesJourney)


SCREENS = {**PREVIEW_PLAN.screen_tags,
    **attachment_removal(),
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


ACTIONS = fixture_actions(('standard', 'count', 'sixth', 'maximum', 'oversized', 'total', 'overflow'),
                          stage='attachment-fixtures', cleanup='attachment-cleanup')
stage_boundaries = ACTIONS['attachment-fixtures']
cleanup_boundaries = ACTIONS['attachment-cleanup']


def journey(context, progress):
    return AttachmentBoundariesJourney(context, progress, PLAN,
        actions=ACTIONS)
