"""AUTH01 proof/refusal qualification, without password submission."""
from dataclasses import replace
from request_flow import PLAN as FLOW_PLAN, RequestFlowJourney

SCREENS = {}
for stage, operation in FLOW_PLAN.screen_tags.items():
    SCREENS[stage] = operation
    if stage == 'open-selections':
        SCREENS['invalid-custom-open'] = 'ui:kiosk-valid-custom-open'
        for action in ('focus', 'selected', 'read'):
            name = 'text-kiosk-invalid-letters-' + action
            SCREENS[name] = 'ui:' + name
        for action in ('ready', 'submit', 'read'):
            name = 'kiosk-invalid-letters-' + action
            SCREENS[name] = 'ui:' + name
    if stage == 'valid-wrong-entry':
        SCREENS['mate-wrong-entry'] = 'ui:parent-mate-refused'
    if stage in ('open-estimate', 'new-estimate'):
        SCREENS[stage.replace('estimate', 'mate')] = (
            'ui:kiosk-mate-cancel' if stage == 'open-estimate'
            else 'ui:kiosk-mate-refusals-cancel')

PLAN = replace(FLOW_PLAN, prefix='mate-prompt', worker_mode='mate_prompt', screen_tags=SCREENS,
               phases={**FLOW_PLAN.phases,
                       **{stage: 'step-2' for stage in SCREENS if stage not in FLOW_PLAN.phases},
                       'mate-wrong-entry': 'step-1',
                       'open-mate': 'step-2', 'new-mate': 'step-2'})


class MatePromptJourney(RequestFlowJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, plan=PLAN)
