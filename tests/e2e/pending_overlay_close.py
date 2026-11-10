"""FLOW17 app-close: cancel pending approval and reopen the child's request."""
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
    **overlay_authentication(result='close', prefix='interruption'),
    'child-session-after': 'system:child-desktop-identity',
    **overlay_entry('reopen', 'command', form_operation='overlay-valid-fraction-soft-read'),
    'cancel': 'ui:overlay-request-cancel', 'returned': 'ui:overlay-desktop',
    **prefixed_stages('return', RETURN),
    'balance-returned': 'ui:time-explanation-refresh-read',
}
PLAN = JourneyPlan(
    prefix='pending-overlay-close', worker_mode='pending_overlay_close', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    invocations=(*fresh_desktop('parent'),
                 *prefixed_stages('fresh', fresh_desktop('child')),
                 *overlay_entry('direct', 'command'),
                 *overlay_entry('reopen', 'command'),
                 *prefixed_stages('return', fresh_desktop('parent'))),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
        'return': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked'),
    },
    balance_checks={'allowance-configured': 1800},
    request_checks={'reopen-form': ('open-estimate', 'pending-close:choices-changed',
                                   'cancelled_request_preserved')},
    assertions_after={'interruption-closed': 'old-prompt-and-request-absent-with-usable-desktop',
                      'reopen-form': 'cancelled-prompt-and-usable-unchanged-form',
                      'balance-returned': 'no-grant-or-balance-increase'},
)


class PendingOverlayCloseJourney(CancelledRequestJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions,
            session_checks={'child-session-after': 'child-session-before'},
            balance_check=('allowance-configured', 'balance-returned', 1200))
