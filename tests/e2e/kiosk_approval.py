"""Fixed AUTH02 approval after independent AUTH01 entry and refusal checks."""
from dataclasses import replace
from mate_prompt import PLAN as MATE_PLAN
from request_flow import RequestFlowJourney

SCREENS = {}
for stage, operation in MATE_PLAN.screen_tags.items():
    if stage == 'new-mate':
        SCREENS.update({
            'approval-open': 'ui:kiosk-mate-open',
            'approval-qualified': 'ui:kiosk-mate-qualified',
            'approval-rechecked': 'ui:kiosk-mate-rechecked',
            'approval-success': 'ui:kiosk-mate-submit-success',
        })
    elif stage != 'new-cancel':
        SCREENS[stage] = ('ui:kiosk-mate-refusals-cancel' if stage == 'open-mate' else operation)

PLAN = replace(MATE_PLAN, prefix='kiosk-approval', worker_mode='kiosk_approval',
               screen_tags=SCREENS, phases={
                   **{stage: phase for stage, phase in MATE_PLAN.phases.items()
                      if stage in SCREENS or stage in ('ready', 'setup-detached')},
                   **{stage: 'step-2' for stage in SCREENS if stage.startswith('approval-')}})


class KioskApprovalJourney(RequestFlowJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, plan=PLAN)
