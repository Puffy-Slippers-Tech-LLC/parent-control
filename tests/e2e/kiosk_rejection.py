"""Fixed wrong-password rejection and independent password-free Cancel."""
from dataclasses import replace
from mate_prompt import PLAN as MATE_PLAN
from request_flow import RequestFlowJourney
from private_artifacts import require

SCREENS = {}
for stage, operation in MATE_PLAN.screen_tags.items():
    if stage == 'new-mate':
        SCREENS.update({
            'rejection-open': 'ui:kiosk-mate-rejection-open',
            'rejection-qualified': 'ui:kiosk-mate-rejection-qualified',
            'rejection-rechecked': 'ui:kiosk-mate-rejection-rechecked',
            'rejection-result': 'ui:kiosk-mate-submit-rejection',
            'rejection-form': 'ui:kiosk-valid-fraction-soft-read',
        })
    else:
        SCREENS[stage] = ('ui:kiosk-mate-refusals-cancel' if stage == 'open-mate' else operation)

PLAN = replace(MATE_PLAN, prefix='kiosk-rejection', worker_mode='kiosk_rejection',
               screen_tags=SCREENS, phases={
                   **{stage: phase for stage, phase in MATE_PLAN.phases.items() if stage in SCREENS
                      or stage in ('ready', 'setup-detached')},
                   **{stage: 'step-2' for stage in SCREENS if stage.startswith('rejection-')}})


class KioskRejectionJourney(RequestFlowJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, plan=PLAN)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'rejection-form':
            require(self.prepared is not None and self.prepared ==
                    observed['ui']['valid_choice']['request'], 'kiosk-rejection:changed-form')
            observed['comparison']['preserved_choices'] = True
