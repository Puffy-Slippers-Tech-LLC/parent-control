"""C04w: one genuine Riley/Jamie challenge across a guarded human pause."""
from dataclasses import replace

from journey_blocks import fresh_desktop, parent_management, station_entry
from kiosk_approval import KioskApprovalJourney, QUALIFICATION_PLAN, GRANT_SCREENS
from request_flow import prepared_request, CHOICES
from real_interval import interval_action

SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
    'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned',
    **station_entry(),
    **prepared_request(prefix='new', entry='open', initial='default', **CHOICES),
    'approval-open': 'ui:kiosk-pause-mate-open',
    'approval-qualified': 'ui:kiosk-pause-mate-qualified',
    'approval-rechecked': 'ui:kiosk-pause-mate-rechecked',
    'approval-success': 'ui:kiosk-pause-mate-submit-success',
    'new-returned': 'ui:gdm-station-returned',
    **GRANT_SCREENS,
}
PLAN = replace(QUALIFICATION_PLAN, prefix='baseline-auth-pause', worker_mode='baseline_auth_pause',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS}},
    advance_after={}, request_checks={}, balance_checks={'allowance-configured': 0},
    stage_actions={'approval-open': 'real-interval'})


class BaselineAuthPauseJourney(KioskApprovalJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, daily_seconds=0,
                         actions={'real-interval': interval_action(45)} if actions is None else actions)
