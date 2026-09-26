"""FLOW07 leaves the preserved form open; its caller deliberately approves later."""
from dataclasses import replace
from kiosk_approved_flow import PLAN as BASE_PLAN, approved_request
from request_flow import CHOICES, RequestFlowJourney
from private_artifacts import require


def rejected_request(*, outcome, child, approver, duration_seconds, allow_soft):
    approved_request(child=child, approver=approver, duration_seconds=duration_seconds,
                     allow_soft=allow_soft, exit='automatic')
    require(outcome in ('rejection', 'cancel'), 'approval-flow:outcome')
    stages = {'flow-before': 'ui:kiosk-valid-fraction-soft-read'}
    if outcome == 'rejection':
        stages.update({
            'rejection-open': 'ui:kiosk-mate-rejection-open',
            'rejection-qualified': 'ui:kiosk-mate-rejection-qualified',
            'rejection-rechecked': 'ui:kiosk-mate-rejection-rechecked',
            'rejection-result': 'ui:kiosk-mate-submit-rejection',
        })
    else:
        stages['flow-cancel'] = 'ui:kiosk-mate-cancel'
    stages['flow-preserved'] = 'ui:kiosk-valid-fraction-soft-read'
    return stages


def plan(outcome):
    stages = dict(list(BASE_PLAN.screen_tags.items())[:list(BASE_PLAN.screen_tags).index('approval-open')])
    stages.update(rejected_request(outcome=outcome, **CHOICES))
    stages.update(approved_request(**CHOICES, exit='automatic'))
    return replace(BASE_PLAN, prefix='kiosk-approval-flow', worker_mode='approval_flow_' + outcome, screen_tags=stages,
                   phases={**BASE_PLAN.phases, **{stage: 'step-2' for stage in stages
                                                 if stage not in BASE_PLAN.phases}})


REJECTION_PLAN = plan('rejection')
CANCEL_PLAN = plan('cancel')


class ApprovalFlowJourney(RequestFlowJourney):
    def __init__(self, context, progress, plan=REJECTION_PLAN, *, actions=None):
        super().__init__(context, progress, plan=plan, actions=actions)
        self.before_rejection = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'flow-before':
            self.before_rejection = dict(observed['ui']['valid_choice']['request'])
        if stage == 'flow-preserved':
            require(self.before_rejection is not None and self.before_rejection ==
                    observed['ui']['valid_choice']['request'], 'approval-flow:changed-form')
            observed['comparison']['preserved_choices'] = True
