"""PARENT09/PARENT20 and FLOW02 qualification with ordinary saved allowances."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop
from journey_checks import check_balances
from private_artifacts import require

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


# The consumer owns finite preparation and comparison endpoints. Shared leaves
# also serve later revocation cases; no seeded grant or confirmation occurs here.
from copy import deepcopy
from journey_blocks import parent_management, prefixed_stages, retained_parent_entry
from kiosk_approved_flow import obtain_time
from request_flow import CHOICES
from request_composition import KioskRequestJourney


REVOKE_SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-positive-read',
    'before-window': 'ui:retained-parent-leave',
    'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned',
    **obtain_time(initial='default', **CHOICES, exit='automatic'),
    **prefixed_stages('return', fresh_desktop('parent')),
    **prefixed_stages('supplied', retained_parent_entry(source='same-user')),
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
    **{stage: operation for stage, operation in REVOKE_SCREENS.items()
       if not stage.startswith(('first-', 'second-')) and stage != 'before'},
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


class RevocationJourney(KioskRequestJourney):
    """Shared immutable, elapsed-bounded comparisons with caller-owned endpoints.

    Each read check declares (earlier invocation or None, cancel/confirm result).
    The fixed qualification recipes supply their own independent histories.
    """
    def __init__(self, context, progress, plan, *, read_checks, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        require(all(stage in plan.screen_tags and mode in ('cancel', 'confirm')
                    and (before is None or before in plan.screen_tags
                         and plan.stages.index(before) < plan.stages.index(stage))
                    for stage, (before, mode) in read_checks.items()), 'revocation:read-plan')
        self.read_checks = dict(read_checks)
        self.revoke_reads = {}
        self.original_window = None
        self.grant_estimate = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'before-window':
            self.original_window = deepcopy(observed['ui']['retained_parent'])
        elif stage == 'supplied-parent-retained':
            require(self.original_window is not None and
                    observed['ui']['retained_parent'] == self.original_window,
                    'revoke-cancel:retained-parent')
        elif stage == 'new-estimate':
            self.grant_estimate = deepcopy(observed['ui']['valid_choice'])
        if stage not in self.read_checks:
            return
        capture, mode = self.read_checks[stage]
        require(stage not in self.revoke_reads, 'revoke-cancel:read-replay')
        value = observed['ui']['revoke_cancel']
        require(value['settings'] == {'child': 'fixture-child', 'limit_enabled': True,
                                     'allowance': ['15 minutes']}, 'revoke-cancel:settings')
        balances = value['balances']
        start, end = value['read_bounds']
        require(type(start) is int and type(end) is int and 0 < start <= end,
                'revoke-cancel:read-bounds')
        daily, grant, total = (balances[key]['seconds'] for key in ('daily', 'one_time', 'total'))
        precision = max(balances[key]['precision_seconds'] for key in ('daily', 'one_time', 'total'))
        require((abs(daily - 900) < precision if capture is None or mode == 'cancel' else daily >= 0)
                and (grant > 0 if capture is None or mode == 'cancel' else grant == 0)
                and abs(total - max(daily, grant)) < precision, 'revoke-cancel:real-grant')
        if capture is None:
            require(self.grant_estimate is not None, 'revoke-cancel:missing-approval')
            elapsed = (balances['observed_monotonic_ns'] -
                       self.grant_estimate['observed_monotonic_ns']) / 1e9
            expected = self.grant_estimate['estimate']['seconds']
            require(0 <= elapsed <= 600 and expected - elapsed - precision <= grant <= expected + precision,
                    'revoke-cancel:approved-balance')
        else:
            earlier = self.revoke_reads.get(capture)
            require(earlier is not None, 'revoke-cancel:missing-baseline')
            require(value['settings'] == earlier['settings'], 'revoke-cancel:changed-settings')
            if mode == 'confirm':
                require(value['apps'] == earlier['apps'] and value['rules'] == earlier['rules'],
                        'revocation:changed-app-rules')
            minimum = (start - earlier['read_bounds'][1]) / 1e9
            maximum = (end - earlier['read_bounds'][0]) / 1e9
            require(0 <= minimum <= maximum <= 120, 'revoke-cancel:elapsed-bound')
            for key in ('daily', 'one_time', 'total'):
                if mode == 'confirm' and key == 'one_time':
                    continue
                baseline_key = 'daily' if mode == 'confirm' and key == 'total' else key
                old, new = earlier['balances'][baseline_key], balances[key]
                tolerance = old['precision_seconds'] + new['precision_seconds']
                require(max(0, old['seconds'] - maximum) - tolerance <= new['seconds']
                        <= old['seconds'] + tolerance, 'revoke-cancel:changed-balance')
            observed.setdefault('comparison', {}).update(unchanged_settings=True)
            if mode == 'confirm':
                observed['comparison'].update(grant_cleared=True, unchanged_app_rules=True,
                                             unchanged_daily_with_elapsed_bounds=True)
            else:
                observed['comparison']['unchanged_balances_with_elapsed_bounds'] = True
        self.revoke_reads[stage] = deepcopy(value)


class RevokeCancelJourney(RevocationJourney):
    def __init__(self, context, progress, plan=REVOKE_PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions, read_checks={
            'before': (None, 'cancel'), 'first-balances': ('before', 'cancel'),
            'second-balances': ('before', 'cancel')})


class RevokeConfirmJourney(RevocationJourney):
    def __init__(self, context, progress, plan=REVOKE_CONFIRM_PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions, read_checks={
            'before': (None, 'confirm'), 'after': ('before', 'confirm')})
