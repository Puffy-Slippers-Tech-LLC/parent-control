"""Case 224: daily time pauses at the kiosk; two approvals each add 30 seconds."""
from copy import deepcopy
import time

from countdown import CountdownObservation
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (daily_time_profile, desktop_entry, fresh_desktop,
                            native_activity_entry, native_activity_resume, prefixed_stages)
from native_fixtures import fixture_actions
from private_artifacts import require
from real_interval import interval_action
from request_composition import KioskRequestJourney
from request_flow import approval_and_return
from ui_observations import SettingsObservation


WAIT_SECONDS = 45
ADDITION_SECONDS = 30
MIN_REMAINING_SECONDS = 300
CHOICES = dict(child='fixture-child', approver='fixture-parent',
               duration_seconds=ADDITION_SECONDS, allow_soft=False)
SCREENS = {
    **fresh_desktop('parent'),
    **daily_time_profile(source='desktop', entry='same-user', window='new',
                         initial_enabled=False, minutes=10),
    **prefixed_stages('initial', desktop_entry('child', source='gdm', entry='fresh')),
    **native_activity_entry('activity', child='child'),
    'initial-switch-ready': 'ui:fresh-child-desktop',
    'initial-switch': 'system:child-switch-user', 'initial-greeter': 'ui:gdm-returned',
    **prefixed_stages('balance', desktop_entry('parent', source='gdm', entry='retained')),
    'first-before': 'ui:time-explanation-refresh-read',
}
for request in ('first', 'second'):
    SCREENS.update(prefixed_stages(request, {
        'station-desktop': 'ui:desktop', 'station-switch': 'system:parent-switch-user',
        'station-greeter': 'ui:gdm-returned',
        **approval_and_return(prefix='new', entry='new', surface='kiosk',
                              child_entry='retained', **CHOICES),
        **native_activity_resume('resume', child='child'),
        'activity': 'ui:overlay-native-activity',
        'switch-ready': 'ui:fresh-child-desktop',
        'switch': 'system:child-switch-user', 'greeter': 'ui:gdm-returned',
        **prefixed_stages('parent', desktop_entry('parent', source='gdm', entry='retained')),
        'balances': 'ui:time-explanation-refresh-read',
    }))

LOGIN_GROUPS = {'parent-login': ('parent', ''), 'initial': ('child', 'initial-'),
                'balance': ('parent', 'balance-')}
for request in ('first', 'second'):
    LOGIN_GROUPS.update({request + '-retained': ('child', request + '-retained-'),
                         request + '-parent': ('parent', request + '-parent-')})
LOGIN_STAGES = {prefix + stage for role, prefix in LOGIN_GROUPS.values()
                for stage in fresh_desktop(role)}
WAIT_INDEX = tuple(SCREENS).index('first-approval-open')
RESULT_INDEX = tuple(SCREENS).index('first-countdown')
PLAN = JourneyPlan(
    prefix='kiosk-delayed-approval', worker_mode='kiosk_delayed_approval', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' if index < WAIT_INDEX else
                      'step-2' if index < RESULT_INDEX else 'step-3'
               for index, stage in enumerate(SCREENS)}, 'installed-greeter': 'start'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={name: (role, prefix + ('recipient-qualified' if role == 'parent' else
                                      'child-recipient-qualified'),
                       prefix + ('recipient-rechecked' if role == 'parent' else
                                  'child-recipient-rechecked'))
                for name, (role, prefix) in LOGIN_GROUPS.items()},
    settings_checks={'same-parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
                     'profile-settings': SettingsObservation('fixture-child', True, ('10 minutes',))},
    balance_checks={'profile-configured': 600},
    kiosk_request=('child', 'parent', ADDITION_SECONDS, False),
    activity_entries={request + '-retained-entry-guard': 'activity-capture'
                      for request in ('first', 'second')},
    activity_checks={request + '-' + stage: ('activity-capture', 'same')
                     for request in ('first', 'second') for stage in ('resume-opened', 'activity')},
    stage_actions={'desktop': 'native-verify', 'first-approval-open': 'real-interval',
                   'first-balances': 'cooldown'},
    assertions_after={'first-balances': 'delayed-current-balance-increment',
                      'second-balances': 'visible-result'},
)


class KioskDelayedApprovalJourney(KioskRequestJourney):
    tolerance = 2

    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions if actions is not None else {
            **fixture_actions(include_refusal=False, profile='activity'),
            'real-interval': interval_action(WAIT_SECONDS), 'cooldown': self.cooldown})
        self.before = {}
        self.estimates = {}
        self.issuance = {}
        self.entries = {}
        self.success_at = None

    def cooldown(self, journey, guard):
        require(self.success_at is not None, 'kiosk-delayed:missing-success')
        remaining = 5 - (time.monotonic() - self.success_at)
        return interval_action(remaining)(journey, guard) if remaining > 0 else 0

    def elapsed(self, before, after):
        low, high = (after[0] - before[1]) / 1e9, (after[1] - before[0]) / 1e9
        require(0 <= low <= high <= 600, 'kiosk-delayed:elapsed-bound')
        return low, high

    def check_estimate(self, observed):
        # Unlike an unused-child qualification, the second request has a live
        # grant. Its daily operand pauses away; only the grant ages at the kiosk.
        value = observed.get('ui', {}).get('valid_choice')
        if value is None:
            return
        request = 'first' if 'first' not in self.estimates else 'second'
        balance, earlier = self.before[request]
        bounds = (self.choice_bounds[0], self.ui.read_bounds[1])
        require((bounds[1] - bounds[0]) / 1e9 + 2 * self.tolerance < WAIT_SECONDS,
                'kiosk-delayed:estimate-precision')
        require(value['request']['child'] == 'fixture-child'
                and value['request']['approver'] == 'fixture-parent'
                and value['request']['duration_seconds'] == ADDITION_SECONDS
                and value['request']['allow_soft'] is False
                and value['estimate']['kind'] == 'fixed'
                and value['estimate']['precision_seconds'] == 1, 'kiosk-delayed:estimate-binding')
        low, high = self.elapsed(earlier, bounds)
        daily, grant = (balance[key]['seconds'] for key in ('daily', 'one_time'))
        precision = max(balance[key]['precision_seconds'] for key in ('daily', 'one_time')) + self.tolerance
        require(max(daily, grant - high) + ADDITION_SECONDS - precision
                <= value['estimate']['seconds']
                <= max(daily, grant - low) + ADDITION_SECONDS + precision,
                'kiosk-delayed:estimate-arithmetic')
        self.estimates[request] = (deepcopy(value), bounds)
        observed.setdefault('comparison', {})['current_maximum_plus_thirty'] = True

    def grant_bounds(self, request, bounds):
        balance, earlier = self.before[request]
        low, high = self.elapsed(earlier, bounds)
        issued_low, issued_high = self.elapsed(self.issuance[request], bounds)
        daily, grant = (balance[key]['seconds'] for key in ('daily', 'one_time'))
        return (max(daily - issued_high, grant - high) + ADDITION_SECONDS,
                max(daily - issued_low, grant - low) + ADDITION_SECONDS)

    def capture_before(self, request, balance, bounds):
        require(balance['child'] == 'fixture-child' and balance['daily']['seconds'] > 0
                and balance['total']['seconds'] >= MIN_REMAINING_SECONDS,
                'kiosk-delayed:usable-margin')
        if request == 'first':
            require(balance['one_time']['seconds'] == 0, 'kiosk-delayed:daily-only-entry')
        self.before[request] = (deepcopy(balance), bounds)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        request = stage.split('-')[0]
        if stage in ('first-retained-entry-guard', 'second-retained-entry-guard'):
            now = time.monotonic_ns()
            self.entries[request] = (now, now)
        value = observed.get('ui')
        if value is None:
            return
        bounds = tuple(self.ui.read_bounds)
        if stage == 'profile-before':
            require(value['time_explanation']['one_time']['seconds'] == 0,
                    'kiosk-delayed:unexpected-initial-grant')
        if stage == 'first-before':
            self.capture_before('first', value['time_explanation'], bounds)
        if stage in ('first-new-choices', 'second-new-choices'):
            self.choice_bounds = bounds
            if request == 'second':
                require(self.success_at is not None and time.monotonic() - self.success_at >= 5,
                        'kiosk-delayed:cooldown')
        if stage in ('first-approval-open', 'second-approval-open'):
            if request == 'first':
                self.prompt_bounds = bounds
            balance, earlier = self.before[request]
            _, high = self.elapsed(earlier, bounds)
            require(max(balance['daily']['seconds'], balance['one_time']['seconds'] - high)
                    >= MIN_REMAINING_SECONDS, 'kiosk-delayed:prompt-usable-margin')
        if stage in ('first-approval-rechecked', 'second-approval-rechecked'):
            if request == 'first':
                low, _ = self.elapsed(self.prompt_bounds, bounds)
                require(low >= WAIT_SECONDS, 'kiosk-delayed:real-prompt-wait')
            self.issuance[request] = bounds
        if stage in ('first-approval-success', 'second-approval-success'):
            self.issuance[request] = (self.issuance[request][0], bounds[1])
            if request == 'first':
                self.success_at = time.monotonic()
        if stage in ('first-countdown', 'second-countdown'):
            current = CountdownObservation.from_value(value['countdown'], present=True)
            read = tuple(value['countdown_read_bounds'])
            grant_low, grant_high = self.grant_bounds(request, read)
            _, active_high = self.elapsed(self.entries[request], read)
            daily = self.before[request][0]['daily']['seconds']
            precision = self.before[request][0]['daily']['precision_seconds'] + self.tolerance
            require(max(daily - active_high, grant_low) - precision <= current.seconds
                    <= max(daily, grant_high) + precision, 'kiosk-delayed:returned-countdown')
            observed.setdefault('comparison', {})['returned_usable_countdown'] = True
        if stage in ('first-balances', 'second-balances'):
            balance = value['time_explanation']
            require(balance['child'] == 'fixture-child', 'kiosk-delayed:wrong-child')
            low, high = self.grant_bounds(request, bounds)
            precision = max(balance[key]['precision_seconds'] for key in ('daily', 'one_time'))
            precision += max(self.before[request][0][key]['precision_seconds']
                             for key in ('daily', 'one_time')) + self.tolerance
            # The public interval must distinguish either omitted or doubled
            # additions, rather than merely accepting a broad timing range.
            require(high - low + 2 * precision < ADDITION_SECONDS
                    and 0 < low - precision <= balance['one_time']['seconds'] <= high + precision,
                    'kiosk-delayed:current-balance-increment')
            _, active_high = self.elapsed(self.entries[request], bounds)
            daily = self.before[request][0]['daily']['seconds']
            require(daily - active_high - precision <= balance['daily']['seconds'] <= daily + precision
                    and abs(balance['total']['seconds'] - max(balance['daily']['seconds'],
                        balance['one_time']['seconds'])) <= precision, 'kiosk-delayed:daily-and-total')
            if request == 'first':
                estimate, estimated_at = self.estimates['first']
                elapsed_low, _ = self.elapsed(estimated_at, bounds)
                # The daily base is paused during the prompt. A grant started
                # from the earlier estimate would wrongly consume the 45 s.
                require(balance['one_time']['seconds'] - precision >
                        estimate['estimate']['seconds'] - elapsed_low + self.tolerance,
                        'kiosk-delayed:prompt-time-wrongly-consumed')
                self.capture_before('second', balance, bounds)
            observed.setdefault('comparison', {}).update(
                independent_current_balance_increment=True, expected_grant_interval=[low, high],
                tolerance_seconds=precision, paused_daily_time=True)


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-048/daily-only-kiosk'
    record_installed_journey(recorder, context, PLAN, journey_type=KioskDelayedApprovalJourney)


E2E_CASES = {'daily-only-kiosk': execute}
