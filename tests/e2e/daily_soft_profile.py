"""FLOW18: return with daily-dominant time and the original Soft exception.

The consumer owns natural expiry and any subsequent restoring action. This
composition makes no policy edit after its real six-second additional approval.
"""
from copy import deepcopy
import time

from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS, countdown_seconds
from countdown import CountdownSample, check_countdown_balance
from installed_journey import JourneyPlan
from journey_blocks import (desktop_entry, desktop_return, grant_only_time_profile,
                            native_usable_app, prefixed_stages, retained_parent_entry)
from journey_checks import require_zero_grant
from named_app_set import APPS, named_app_set
from native_fixtures import fixture_actions
from policy_edits import AppPolicyJourney
from private_artifacts import require
from real_interval import interval_action


ENTRIES = {
    'setup-return': prefixed_stages('setup-return', desktop_entry(
        'parent', source='gdm', entry='retained')),
    'first-child': prefixed_stages('first-child', desktop_entry(
        'child', source='gdm', entry='fresh')),
    'away-parent': prefixed_stages('away-parent', desktop_entry(
        'parent', source='desktop', entry='retained', source_account='child')),
    'returned-child': prefixed_stages('returned-child', desktop_entry(
        'child', source='gdm', entry='retained')),
}


def daily_soft_profile():
    """Finite FLOW18 declaration, from fresh app-policy setup to child witness."""
    return {
        **named_app_set(source='gdm', entry='fresh', window='new', child='child',
                        apps=APPS, prefix='apps'),
        **ENTRIES['setup-return'],
        **grant_only_time_profile(source='desktop', entry='same-user', window='retained',
            initial_enabled=False, revoke_first=False, daily_minutes=10,
            duration_seconds=6, request_initial='observed', balance_readback=False),
        **ENTRIES['first-child'],
        **prefixed_stages('soft', native_usable_app('command', child='child', role='S')),
        'soft-capture': 'ui:overlay-native-policy-soft-activity',
        **ENTRIES['away-parent'],
        **prefixed_stages('away', retained_parent_entry(
            source='same-user', desktop_observation=False)),
        'away-balance': 'ui:time-explanation-refresh-read',
        'return-balance': 'ui:time-explanation-refresh-read',
        **desktop_return('leave-parent', account='parent'),
        **ENTRIES['returned-child'],
        'soft-preserved': 'ui:overlay-native-policy-soft-activity',
        'positive-child-witness': 'ui:child-countdown-present',
    }


SCREENS = daily_soft_profile()
LOGIN_STAGES = {stage for entry in ENTRIES.values() for stage, tag in entry.items()
                if tag.startswith('ui:') and not stage.endswith(('-source-desktop', '-source-greeter'))}
PLAN = JourneyPlan(
    prefix='daily-soft-profile', worker_mode='daily_soft_profile', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    kiosk_request=('child', 'parent', 6, True),
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={prefix: (account, prefix + '-' + role + '-qualified', prefix + '-' + role + '-rechecked')
                for prefix, account, role in (
                    ('setup-return', 'parent', 'recipient'),
                    ('first-child', 'child', 'child-recipient'),
                    ('away-parent', 'parent', 'recipient'),
                    ('returned-child', 'child', 'child-recipient'))},
    child_bindings={stage: 'child' for stage, tag in SCREENS.items()
                    if tag.removeprefix('ui:') in NAMED_CHILD_OPERATIONS},
    match_checks={f'apps-saved-{role}-match': (MATCH_APPS[role.upper()], MATCH_RULES[index])
                  for role, index in (('a', 0), ('h', 3), ('s', 4))},
    access_checks={f'apps-saved-{role}-access': (MATCH_APPS[role.upper()], access)
                   for role, access in (('a', 'allowed'), ('h', 'permanent'), ('s', 'conditional'))},
    activity_checks={'soft-preserved': ('soft-capture', 'same')},
    activity_entries={'returned-child-entry-guard': 'soft-capture'},
    stage_actions={'desktop': 'native-verify', 'away-balance': 'real-interval'},
    assertions_after={'positive-child-witness': 'daily-dominant-original-soft-exception'},
)


class DailySoftProfileJourney(AppPolicyJourney):
    """Use actual public reserves; refuse an infeasible return without top-ups."""
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions if actions is not None else {
            **fixture_actions(include_refusal=False, profile='activity'),
            'real-interval': self.wait_away})
        self.parent_window = None
        self.away_balance = None
        self.return_balance = None
        self.return_boot = None
        self.away_wait = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        ui = observed.get('ui', {})
        if stage == 'profile-before':
            require_zero_grant(ui['revoke_cancel']['balances'])
        if stage == 'profile-daily':
            balance = ui['time_explanation']
            require_zero_grant(balance)
            require(540 <= balance['daily']['seconds'] <= 600,
                    'flow18:daily-preparation-margin')
        if stage == 'profile-window':
            self.parent_window = deepcopy(ui['retained_parent'])
        if stage == 'away-parent-retained':
            require(self.parent_window is not None and ui['retained_parent'] == self.parent_window,
                    'flow18:retained-parent')
        if stage in ('away-balance', 'return-balance'):
            balance = ui['time_explanation']
            require(balance['child'] == 'fixture-child', 'flow18:balance-child')
            daily, grant, total = (balance[key]['seconds'] for key in ('daily', 'one_time', 'total'))
            precision = max(balance[key]['precision_seconds'] for key in ('daily', 'one_time', 'total'))
            require(daily > 0 and grant > 0 and abs(total - max(daily, grant)) <= precision,
                    'flow18:positive-balances')
            if stage == 'away-balance':
                self.away_balance = deepcopy(balance)
                # Target a broad gap, not a narrow near-expiry grant window.
                # Leave 30 seconds beyond the required 180-second gap for reads.
                self.away_wait = max(0, 210 - (daily - grant - 2 * precision))
                require(self.away_wait <= 300 and grant - precision - self.away_wait >= 240,
                        'flow18:unreachable-return-margin')
            else:
                require(self.away_balance is not None, 'flow18:missing-away-balance')
                elapsed = (balance['observed_monotonic_ns']
                           - self.away_balance['observed_monotonic_ns']) / 1e9
                require(0 < elapsed <= 360, 'flow18:away-deadline')
                previous = self.away_balance
                require(abs(daily - previous['daily']['seconds']) <= 2 * precision
                        and abs(grant - (previous['one_time']['seconds'] - elapsed)) <= 3 * precision,
                        'flow18:inactive-daily-original-grant')
                require(grant - precision >= 180 and daily - grant - 2 * precision >= 180,
                        'flow18:parent-return-reserves')
                self.return_balance = deepcopy(balance)
                self.return_boot = observed['boot_sha256']
                observed['comparison'] = {'daily_dominant': True,
                    'grant_reserve_seconds': grant - precision,
                    'dominance_reserve_seconds': daily - grant - 2 * precision}
        if stage == 'positive-child-witness':
            require(self.return_balance is not None, 'flow18:missing-return-balance')
            sample = CountdownSample.from_ui(ui, boot_sha256=observed['boot_sha256'])
            require(sample.boot_sha256 == self.return_boot, 'flow18:changed-boot')
            balance = self.return_balance
            elapsed = (sample.guest_read_bounds[1] - balance['observed_monotonic_ns']) / 1e9
            require(0 < elapsed <= 180, 'flow18:child-return-deadline')
            grant_low = balance['one_time']['seconds'] - balance['one_time']['precision_seconds'] - elapsed
            # Do not subtract any return time for the upper bound: transport
            # delay can only reduce G. The independent panel interval is max(D,G).
            grant_high = balance['one_time']['seconds'] + balance['one_time']['precision_seconds']
            daily_low, _ = countdown_seconds(sample.countdown.text)
            require(daily_low > grant_high and grant_low > 0,
                    'flow18:child-daily-dominant-positive-grant')
            observed['comparison'] = {**check_countdown_balance(sample.countdown,
                seconds=balance['daily']['seconds'],
                precision_seconds=balance['daily']['precision_seconds'],
                observed_monotonic_ns=balance['observed_monotonic_ns']),
                'daily_lower_seconds': daily_low, 'grant_lower_seconds': grant_low,
                'grant_upper_seconds': grant_high, 'daily_dominant_positive_grant': True}

    @staticmethod
    def wait_away(journey, guard):
        require(journey.away_balance is not None and journey.away_wait is not None,
                'flow18:missing-away-balance')
        if journey.away_wait == 0:
            guard()
            return {'elapsed_seconds': 0}
        started = time.monotonic()
        elapsed = interval_action(journey.away_wait)(journey, guard)
        require(time.monotonic() - started >= journey.away_wait, 'flow18:away-wait')
        return {'elapsed_seconds': elapsed}
