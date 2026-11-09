"""FLOW17 Switch User: cancel pending approval without changing choices or time."""
from installed_journey import JourneyPlan
from journey_blocks import (fresh_desktop, parent_management, overlay_entry,
                            prefixed_stages, retained_parent_entry)
from request_flow import CHOICES, prepared_request, overlay_authentication
from request_composition import CancelledRequestJourney


RETURN = retained_parent_entry(source='child-desktop')
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **prefixed_stages('fresh', fresh_desktop('child')),
    'child-session-before': 'system:child-desktop-identity',
    **overlay_entry('direct', 'command'),
    **prepared_request(prefix='open', entry='open', initial='default',
                       surface='overlay', **CHOICES),
    **overlay_authentication(result='switch-user', prefix='interruption'),
    'form-returned': 'ui:overlay-valid-fraction-soft-read',
    'cancel': 'ui:overlay-request-cancel', 'returned': 'ui:overlay-desktop',
    **prefixed_stages('return', RETURN),
    'balance-returned': 'ui:time-explanation-refresh-read',
}
PLAN = JourneyPlan(
    prefix='pending-overlay-switch', worker_mode='pending_overlay_switch', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    invocations=(*fresh_desktop('parent'),
                 *prefixed_stages('fresh', fresh_desktop('child')),
                 *overlay_entry('direct', 'command'),
                 *prefixed_stages('interruption', fresh_desktop('child')),
                 *prefixed_stages('return', fresh_desktop('parent'))),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
        'interruption': ('child', 'interruption-child-recipient-qualified',
                         'interruption-child-recipient-rechecked'),
        'return': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked'),
    },
    balance_checks={'allowance-configured': 1800},
    request_checks={'form-returned': ('open-estimate', 'pending-switch:choices-changed',
                                     'cancelled_request_preserved')},
    assertions_after={'interruption-source-greeter': 'child-locked-and-greeter-usable',
                      'form-returned': 'cancelled-prompt-and-usable-unchanged-form',
                      'balance-returned': 'no-grant-or-balance-increase'},
)


class PendingOverlaySwitchJourney(CancelledRequestJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions,
            session_checks={'interruption-desktop': 'child-session-before'},
            balance_check=('allowance-configured', 'balance-returned', 1200))
