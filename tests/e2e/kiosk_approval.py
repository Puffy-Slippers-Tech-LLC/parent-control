"""Fixed AUTH02 approval after independent AUTH01 entry and refusal checks."""
from dataclasses import replace
from copy import deepcopy
from journey_blocks import desktop_entry, prefixed_stages, retained_parent_entry
from mate_prompt import PLAN as MATE_PLAN
from private_artifacts import require
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

# Consumers derive PLAN for the approval operation alone. Only this fixed
# qualification returns to Parent to observe the independently issued grant.
GRANT_SCREENS = {
    **prefixed_stages('return', desktop_entry('parent', source='gdm', entry='retained')),
    **prefixed_stages('supplied', retained_parent_entry(source='same-user')),
    'approved-balance': 'ui:time-explanation-reach-read',
}
QUALIFICATION_PLAN = replace(PLAN,
    screen_tags={**PLAN.screen_tags, **GRANT_SCREENS},
    phases={**PLAN.phases, **{stage: 'step-2' for stage in GRANT_SCREENS}},
    invocations=tuple(stage for stage, operation in GRANT_SCREENS.items()
                      if stage.startswith('return-') and operation.startswith('ui:')),
    challenges={'return': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked')},
    balance_checks={**PLAN.balance_checks, 'time-explanation-read': 900})


class KioskApprovalJourney(RequestFlowJourney):
    def __init__(self, context, progress, plan=QUALIFICATION_PLAN, *, actions=None,
                 daily_seconds=900):
        super().__init__(context, progress, plan=plan, actions=actions)
        self.daily_seconds = daily_seconds
        self.grant_estimate = None
        self.grant_observed = False

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'new-estimate':
            require(self.grant_estimate is None, 'kiosk-approval:estimate-replay')
            self.grant_estimate = deepcopy(observed['ui']['valid_choice'])
        if stage != 'approved-balance':
            return
        require(not self.grant_observed, 'kiosk-approval:balance-replay')
        require(self.grant_estimate is not None, 'kiosk-approval:missing-estimate')
        value = observed['ui']['time_explanation']
        require(value['child'] == 'fixture-child', 'kiosk-approval:wrong-child')
        estimate = self.grant_estimate
        expected = self.daily_seconds + 75
        require(estimate['estimate']['kind'] == 'fixed' and estimate['estimate']['seconds'] == expected,
                'kiosk-approval:expected-estimate')
        daily, grant, total = (value[key]['seconds'] for key in ('daily', 'one_time', 'total'))
        precision = max(value[key]['precision_seconds'] for key in ('daily', 'one_time', 'total'))
        require(abs(daily - self.daily_seconds) < value['daily']['precision_seconds'] and grant > 0
                and abs(total - max(daily, grant)) < precision,
                'kiosk-approval:real-grant')
        elapsed = (value['observed_monotonic_ns'] - estimate['observed_monotonic_ns']) / 1e9
        require(0 <= elapsed <= 600 and expected - elapsed - value['one_time']['precision_seconds']
                <= grant <= expected + value['one_time']['precision_seconds'],
                'kiosk-approval:approved-balance')
        observed.setdefault('comparison', {}).update(
            independent_grant=True, unchanged_daily=True, approved_estimate_with_elapsed_bounds=True)
        self.grant_observed = True
