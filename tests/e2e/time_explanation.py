"""PARENT09/PARENT20 and FLOW02 qualification with ordinary saved allowances."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, prefixed_stages, revocation_entry
from journey_checks import check_balances
from private_artifacts import require
from request_flow import CHOICES
from request_composition import RevocationJourney

STAGES = (
    'parent-toggle-enabled', 'parent-save-enabled',
    'allowance-15-select', 'allowance-15-read',
    'time-explanation-collapse', 'time-explanation-collapsed',
    'time-explanation-expand', 'time-explanation-wrong-child',
    'time-explanation-read', 'time-explanation-reread',
    'time-explanation-reach-wrong-child', 'time-explanation-config-wrong-child',
    'time-explanation-config-wrong-state',
    'time-explanation-collapse-again',
    'time-explanation-reach-read', 'time-explanation-reach-reread',
    'time-explanation-off-read', 'time-explanation-positive-read',
    'time-explanation-zero-read', 'time-explanation-zero-reread',
)
SCREENS = {
    **fresh_desktop('parent'),
    'parent-command': 'ui:parent-command-launch',
    **{stage: 'ui:' + stage for stage in (
        'parent-window', 'child-picker-opened', 'child-choice-highlighted',
        'parent-selected', *STAGES)},
}
SCREENS['time-explanation-collapse-again'] = 'ui:time-explanation-collapse'


PLAN = JourneyPlan(
    prefix='time-explanation', worker_mode='time_explanation', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in STAGES if stage.startswith('time-explanation-')}},
    advance_after={'allowance-15-read': 'step-2'},
)


class TimeExplanationJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in ('time-explanation-read', 'time-explanation-reread'):
            require((stage == 'time-explanation-read') ==
                    (getattr(self, 'earlier_time_observation', None) is None),
                    'time-explanation:read-order')
            check_balances(self, observed)
        elif stage in ('time-explanation-reach-read', 'time-explanation-reach-reread',
                       'time-explanation-positive-read'):
            check_balances(self, observed)
        elif stage in ('time-explanation-zero-read', 'time-explanation-zero-reread'):
            check_balances(self, observed, 0)


# Both qualifications compose the same real approval and retained Parent entry.
# Their response histories and comparison endpoints remain separate below.
REVOKE_ENTRY = revocation_entry(**CHOICES)
REVOKE_SCREENS = {
    **REVOKE_ENTRY,
    'before': 'ui:revoke-balances',
    **{prefix + '-' + action: 'ui:revoke-' + action
       for prefix in ('first', 'second')
       for action in ('open', 'warning', 'wrong-child', 'wrong-confirmation', 'cancel', 'balances')},
}
_login_stages = set(fresh_desktop('parent')) | set(prefixed_stages('return', fresh_desktop('parent')))
REVOKE_PLAN = JourneyPlan(
    prefix='revoke-cancel', worker_mode='revoke_cancel', screen_tags=REVOKE_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in REVOKE_SCREENS}},
    invocations=tuple(stage for stage in REVOKE_SCREENS if stage in _login_stages),
    challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
                'return': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked')},
    balance_checks={'allowance-configured': 900},
    assertions_after={'first-balances': 'first-cancel-preserved-settings-balances',
                      'second-balances': 'independent-cancel-preserved-settings-balances'},
)


REVOKE_CONFIRM_SCREENS = {
    **REVOKE_ENTRY,
    'before': 'ui:revoke-saved-balances',
    **{stage: 'ui:revoke-' + action for stage, action in (
        ('confirm-open', 'open'), ('confirm-warning', 'warning'),
        ('confirm-wrong-child', 'confirm-wrong-child'),
        ('confirm-refused', 'confirm-refused'), ('confirmed', 'confirm'),
        ('after', 'cleared-balances'))},
}
REVOKE_CONFIRM_PLAN = JourneyPlan(
    prefix='revocation', worker_mode='revocation', screen_tags=REVOKE_CONFIRM_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in REVOKE_CONFIRM_SCREENS}},
    invocations=REVOKE_PLAN.invocations, challenges=REVOKE_PLAN.challenges,
    balance_checks=REVOKE_PLAN.balance_checks,
    assertions_after={'after': 'confirmed-grant-cleared-daily-and-saved-policy-preserved'},
)


class RevokeCancelJourney(RevocationJourney):
    def __init__(self, context, progress, plan=REVOKE_PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions,
            window_checks={'supplied-parent-retained': 'before-window'}, approval_stage='new-estimate',
            read_checks={
            'before': (None, 'cancel'), 'first-balances': ('before', 'cancel'),
            'second-balances': ('before', 'cancel')})


class RevokeConfirmJourney(RevocationJourney):
    def __init__(self, context, progress, plan=REVOKE_CONFIRM_PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions,
            window_checks={'supplied-parent-retained': 'before-window'}, approval_stage='new-estimate',
            read_checks={
            'before': (None, 'confirm'), 'after': ('before', 'confirm')})
