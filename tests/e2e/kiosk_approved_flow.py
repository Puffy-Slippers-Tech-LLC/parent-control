"""Finite kiosk FLOW05/06; preparation and approval retain their owned leaves."""
from dataclasses import replace
from kiosk_approval import PLAN as APPROVAL_PLAN
from private_artifacts import require
from request_flow import CHOICES, RequestFlowJourney, prepared_request


def approved_request(*, child, approver, duration_seconds, allow_soft, exit):
    """FLOW05 from the independently prepared form; one invocation per attempt."""
    require(dict(child=child, approver=approver, duration_seconds=duration_seconds,
                 allow_soft=allow_soft) == CHOICES
            and type(duration_seconds) is int and allow_soft is True,
            'approved-flow:choices')
    require(exit == 'automatic', 'approved-flow:exit')
    return {
        'approval-open': 'ui:kiosk-mate-open',
        'approval-qualified': 'ui:kiosk-mate-qualified',
        'approval-rechecked': 'ui:kiosk-mate-rechecked',
        'approval-success': 'ui:kiosk-mate-submit-success',
        'new-returned': 'ui:gdm-station-returned',
    }


def obtain_time(*, initial, child, approver, duration_seconds, allow_soft, exit):
    """FLOW06 starts at GDM; no policy setup or later child login is implicit."""
    choices = dict(child=child, approver=approver, duration_seconds=duration_seconds,
                   allow_soft=allow_soft)
    approval = approved_request(**choices, exit=exit)
    return {**prepared_request(prefix='new', entry='new', initial=initial, **choices),
            **approval}


# Keep the independent open-form/refusal qualification, then compose fresh FLOW06.
_entry = list(APPROVAL_PLAN.screen_tags).index('cancel-station-list')
SCREENS = dict(list(APPROVAL_PLAN.screen_tags.items())[:_entry])
SCREENS.update(obtain_time(initial='selected', **CHOICES, exit='automatic'))
PLAN = replace(APPROVAL_PLAN, worker_mode='kiosk_approved_flow', screen_tags=SCREENS)


class KioskApprovedFlowJourney(RequestFlowJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, plan=PLAN)
