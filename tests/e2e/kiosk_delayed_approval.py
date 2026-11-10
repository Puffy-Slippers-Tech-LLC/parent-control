"""Cases 224/230: daily time pauses, grants age, and two approvals add 30 seconds."""
from copy import deepcopy
import time

from countdown import CountdownObservation
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (daily_time_profile, desktop_entry, fresh_desktop,
                            native_activity_entry, native_activity_resume, prefixed_stages)
from native_fixtures import fixture_actions
from kiosk_approved_flow import obtain_time
from private_artifacts import require
from real_interval import interval_action
from request_composition import KioskRequestJourney
from request_flow import approval_and_return
from ui_observations import SettingsObservation


WAIT_SECONDS = 45
ADDITION_SECONDS = 30
MIN_REMAINING_SECONDS = 300
INITIAL_GRANT_SECONDS = 1200
DOMINANCE_SECONDS = 90
CHOICES = dict(child='fixture-child', approver='fixture-parent',
               duration_seconds=ADDITION_SECONDS, allow_soft=False)


def approval_plan(*, grant_dominant):
    """Compose each finite history directly from the shared public operations."""
    minutes = 30 if grant_dominant else 10
    screens = {
        **fresh_desktop('parent'),
        **daily_time_profile(source='desktop', entry='same-user', window='new',
                             initial_enabled=False, minutes=minutes),
        **prefixed_stages('initial', desktop_entry('child', source='gdm', entry='fresh')),
        **native_activity_entry('activity', child='child'),
        'initial-switch-ready': 'ui:fresh-child-desktop',
        'initial-switch': 'system:child-switch-user', 'initial-greeter': 'ui:gdm-returned',
        **prefixed_stages('balance', desktop_entry('parent', source='gdm', entry='retained')),
    }
    logins = {'parent-login': ('parent', ''), 'initial': ('child', 'initial-'),
              'balance': ('parent', 'balance-')}
    if grant_dominant:
        # Ready the original activity before the setup grant starts running.
        # This approval never replaces either measured 30-second request.
        screens.update({
            'setup-before': 'ui:time-explanation-refresh-read',
            'profile-desktop': 'ui:desktop',
            'profile-switch': 'system:parent-switch-user', 'profile-greeter': 'ui:gdm-returned',
            **prefixed_stages('profile-request', obtain_time(initial='default', child='fixture-child',
                approver='fixture-parent', duration_seconds=INITIAL_GRANT_SECONDS,
                allow_soft=True, exit='automatic')),
            **prefixed_stages('profile-return', desktop_entry('parent', source='gdm', entry='retained')),
        })
        logins['profile-return'] = ('parent', 'profile-return-')
    screens['first-before'] = 'ui:time-explanation-refresh-read'
    for request in ('first', 'second'):
        screens.update(prefixed_stages(request, {
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
        logins.update({request + '-retained': ('child', request + '-retained-'),
                       request + '-parent': ('parent', request + '-parent-')})
    login_stages = {prefix + stage for role, prefix in logins.values()
                    for stage in fresh_desktop(role)}
    wait_index = tuple(screens).index('first-approval-open')
    result_index = tuple(screens).index('first-countdown')
    return JourneyPlan(
        prefix='kiosk-delayed-approval',
        worker_mode='kiosk_delayed_grant_approval' if grant_dominant else 'kiosk_delayed_approval',
        screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: 'step-1' if index < wait_index else
                          'step-2' if index < result_index else 'step-3'
                   for index, stage in enumerate(screens)}, 'installed-greeter': 'start'},
        invocations=tuple(stage for stage in screens if stage in login_stages),
        challenges={name: (role, prefix + ('recipient-qualified' if role == 'parent' else
                                          'child-recipient-qualified'),
                           prefix + ('recipient-rechecked' if role == 'parent' else
                                      'child-recipient-rechecked'))
                    for name, (role, prefix) in logins.items()},
        settings_checks={'same-parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
                         'profile-settings': SettingsObservation('fixture-child', True, (f'{minutes} minutes',))},
        balance_checks={'profile-configured': minutes * 60},
        kiosk_request=('child', 'parent', ADDITION_SECONDS, False),
        activity_entries={request + '-retained-entry-guard': 'activity-capture'
                          for request in ('first', 'second')},
        activity_checks={request + '-' + stage: ('activity-capture', 'same')
                         for request in ('first', 'second') for stage in ('resume-opened', 'activity')},
        stage_actions={'desktop': 'native-verify', 'first-approval-open': 'real-interval'},
        assertions_after={'first-balances': 'delayed-current-balance-increment',
                          'second-balances': 'visible-result'},
    )


PLAN = approval_plan(grant_dominant=False)
GRANT_PLAN = approval_plan(grant_dominant=True)


class KioskDelayedApprovalJourney(KioskRequestJourney):
    tolerance = 2
    balance_profile = 'daily-only'

    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions if actions is not None else {
            **fixture_actions(include_refusal=False, profile='activity'),
            'real-interval': interval_action(WAIT_SECONDS)})
        self.before = {}
        self.estimates = {}
        self.issuance = {}
        self.entries = {}
        self.setup_before = None
        self.setup_issuance = None

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
        if self.current_stage.startswith('profile-request-'):
            if self.current_stage != 'profile-request-new-estimate':
                return
            require(self.balance_profile == 'grant-dominant' and self.setup_before is not None,
                    'kiosk-delayed:unexpected-setup-request')
            balance, earlier = self.setup_before
            _, high = self.elapsed(earlier, tuple(self.ui.read_bounds))
            precision = balance['daily']['precision_seconds'] + self.tolerance
            require(value['request']['child'] == 'fixture-child'
                    and value['request']['approver'] == 'fixture-parent'
                    and value['request']['allow_soft'] is True
                    and value['estimate']['kind'] == 'fixed'
                    and abs(value['estimate']['seconds'] - balance['daily']['seconds']
                            - INITIAL_GRANT_SECONDS) <= precision
                    and balance['daily']['seconds'] - high >= MIN_REMAINING_SECONDS,
                    'kiosk-delayed:setup-estimate')
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
            if self.balance_profile == 'grant-dominant':
                precision = max(balance[key]['precision_seconds'] for key in ('daily', 'one_time'))
                require(balance['daily']['seconds'] >= MIN_REMAINING_SECONDS
                        and balance['one_time']['seconds'] - balance['daily']['seconds']
                            > DOMINANCE_SECONDS + precision, 'kiosk-delayed:grant-dominant-entry')
            else:
                require(balance['one_time']['seconds'] == 0, 'kiosk-delayed:daily-only-entry')
        self.before[request] = (deepcopy(balance), bounds)

    def check_settings(self, stage, observed):
        self.current_stage = stage
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
        if stage == 'setup-before':
            balance = value['time_explanation']
            require(balance['child'] == 'fixture-child' and balance['one_time']['seconds'] == 0
                    and balance['daily']['seconds'] >= MIN_REMAINING_SECONDS,
                    'kiosk-delayed:setup-balances')
            self.setup_before = (deepcopy(balance), bounds)
        if stage == 'profile-request-approval-open':
            self.setup_issuance = bounds
        if stage == 'profile-request-approval-success':
            self.setup_issuance = (self.setup_issuance[0], bounds[1])
        if stage == 'first-before':
            self.capture_before('first', value['time_explanation'], bounds)
            if self.balance_profile == 'grant-dominant':
                balance, _ = self.setup_before
                low, high = self.elapsed(self.setup_issuance, bounds)
                actual = value['time_explanation']
                precision = (balance['daily']['precision_seconds']
                             + actual['one_time']['precision_seconds'] + self.tolerance)
                expected = balance['daily']['seconds'] + INITIAL_GRANT_SECONDS
                require(expected - high - precision <= actual['one_time']['seconds']
                        <= expected - low + precision
                        and abs(actual['daily']['seconds'] - balance['daily']['seconds']) <= precision,
                        'kiosk-delayed:setup-grant-increment')
        if stage in ('first-new-choices', 'second-new-choices'):
            self.choice_bounds = bounds
        if stage in ('first-approval-open', 'second-approval-open'):
            if request == 'first':
                self.prompt_bounds = bounds
            balance, earlier = self.before[request]
            _, high = self.elapsed(earlier, bounds)
            require(max(balance['daily']['seconds'], balance['one_time']['seconds'] - high)
                    >= MIN_REMAINING_SECONDS, 'kiosk-delayed:prompt-usable-margin')
            if request == 'first' and self.balance_profile == 'grant-dominant':
                require(balance['daily']['seconds'] >= MIN_REMAINING_SECONDS
                        and balance['one_time']['seconds'] - high - balance['daily']['seconds']
                            > DOMINANCE_SECONDS + self.tolerance,
                        'kiosk-delayed:prompt-grant-dominance')
        if stage in ('first-approval-rechecked', 'second-approval-rechecked'):
            if request == 'first':
                low, _ = self.elapsed(self.prompt_bounds, bounds)
                require(low >= WAIT_SECONDS, 'kiosk-delayed:real-prompt-wait')
            self.issuance[request] = bounds
        if stage in ('first-approval-success', 'second-approval-success'):
            self.issuance[request] = (self.issuance[request][0], bounds[1])
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
                if self.balance_profile == 'grant-dominant':
                    # A frozen estimate issued at authentication would add the
                    # deliberate wait to the original grant's actual deadline.
                    _, issued_high = self.elapsed(self.issuance['first'], bounds)
                    require(balance['one_time']['seconds'] + precision
                            < estimate['estimate']['seconds'] - issued_high - self.tolerance,
                            'kiosk-delayed:frozen-estimate-not-distinguished')
                else:
                    # The daily base pauses away; starting that grant at the
                    # earlier estimate would wrongly consume the prompt wait.
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


class GrantDominantKioskJourney(KioskDelayedApprovalJourney):
    balance_profile = 'grant-dominant'


def execute_grant(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-048/grant-dominant-kiosk'
    record_installed_journey(recorder, context, GRANT_PLAN, journey_type=GrantDominantKioskJourney)


E2E_CASES = {'daily-only-kiosk': execute, 'grant-dominant-kiosk': execute_grant}
