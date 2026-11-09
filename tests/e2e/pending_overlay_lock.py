"""FLOW17 lock: cancel a real pending approval and preserve choices and time."""
from copy import deepcopy

from installed_journey import JourneyPlan
from journey_blocks import (fresh_desktop, parent_management, overlay_entry,
                            prefixed_stages, retained_parent_entry)
from request_flow import CHOICES, prepared_request, overlay_authentication
from request_composition import KioskRequestJourney
from private_artifacts import require


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
    **overlay_authentication(result='lock', prefix='interruption'),
    'form-returned': 'ui:overlay-valid-fraction-soft-read',
    'cancel': 'ui:overlay-request-cancel', 'returned': 'ui:overlay-desktop',
    **prefixed_stages('return', RETURN),
    'balance-returned': 'ui:time-explanation-refresh-read',
}
PLAN = JourneyPlan(
    prefix='pending-overlay-lock', worker_mode='pending_overlay_lock', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    invocations=(*fresh_desktop('parent'),
                 *prefixed_stages('fresh', fresh_desktop('child')),
                 *overlay_entry('direct', 'command'),
                 *prefixed_stages('return', fresh_desktop('parent'))),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
        'return': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked'),
    },
    balance_checks={'allowance-configured': 1800},
    request_checks={'form-returned': ('open-estimate', 'pending-lock:choices-changed',
                                     'cancelled_request_preserved')},
    assertions_after={'interruption-challenge': 'child-screen-locked',
                      'form-returned': 'cancelled-prompt-and-usable-unchanged-form',
                      'balance-returned': 'no-grant-or-balance-increase'},
)


class PendingOverlayLockJourney(KioskRequestJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.original_balance = None
        self.child_session = None

    def check_settings(self, stage, observed):
        if stage == 'child-session-before':
            self.child_session = observed['system']['session_sha256']
        if stage == 'interruption-unlock-session':
            require(self.child_session is not None
                    and observed['system']['session_sha256'] == self.child_session,
                    'pending-lock:child-session-replaced')
        if stage == 'balance-returned':
            before = self.original_balance
            after = observed['ui']['time_explanation']
            require(before is not None and after['child'] == before['child'],
                    'pending-lock:balance-owner')
            elapsed = (after['observed_monotonic_ns'] - before['observed_monotonic_ns']) / 1e9
            require(0 <= elapsed <= 1200, 'pending-lock:balance-elapsed')
            require(after['one_time']['seconds'] == 0, 'pending-lock:unexpected-grant')
            for key in ('daily', 'total'):
                precision = before[key]['precision_seconds'] + after[key]['precision_seconds']
                require(max(0, before[key]['seconds'] - elapsed) - precision
                        <= after[key]['seconds'] <= before[key]['seconds'] + precision,
                        'pending-lock:changed-balance')
        super().check_settings(stage, observed)
        if stage == 'allowance-configured':
            self.original_balance = deepcopy(observed['ui']['time_explanation'])
        if stage == 'balance-returned':
            observed.setdefault('comparison', {})['unchanged_balances_allowing_elapsed_time'] = True
