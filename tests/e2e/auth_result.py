"""Immediate approved exit leaf; compose with qualified automatic/rejection leaves."""
from dataclasses import replace
from kiosk_approval import PLAN as APPROVAL_PLAN
from request_flow import RequestFlowJourney

PLAN = replace(APPROVAL_PLAN, worker_mode='auth_result',
               screen_tags={**APPROVAL_PLAN.screen_tags,
                            'approval-success': 'ui:kiosk-mate-submit-immediate'})


class AuthResultJourney(RequestFlowJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, plan=PLAN)
