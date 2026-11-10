"""Case 197: a parent's Rest of the day approval ends at real local midnight."""

import datetime
import sys
from zoneinfo import ZoneInfo

from accessible_ui import countdown_seconds
from calendar_fixture import preset_ordinary_midnight
from countdown import CountdownSample
from guest_observations import calendar_epoch_bounds
from installed_journey import InstalledJourney, JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, fresh_desktop, native_activity_entry,
                            parent_management, prefixed_stages)
from journey_checks import check_balances, require_zero_grant
from kiosk_approved_flow import obtain_time
from native_fixtures import fixture_actions
from natural_expiry_observation import await_natural_expiry
from private_artifacts import require


SETUP = {
    **fresh_desktop('parent'), **parent_management(),
    'before-grant': 'ui:revoke-balances',
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
    'repeat-desktop': 'ui:desktop',
    'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned',
    **prefixed_stages('request', obtain_time(initial='observed', child='fixture-child',
        approver='fixture-parent', duration_seconds=0, allow_soft=False, exit='automatic')),
    'approved-clock': 'ui:gdm-returned',
    'approved-balance': 'ui:revoke-balances',
    **prefixed_stages('fresh', fresh_desktop('child')),
    **native_activity_entry('activity', child='child'),
}
EXPIRY = {
    'natural-expiry': 'ui:child-countdown-present',
    'lock-input-ready': 'ui:child-natural-expiry-lock-ready',
    'lock-result': 'ui:child-natural-expiry-lock-result',
}
RESULT = {
    'return-greeter': 'system:child-return-greeter', 'returned-gdm': 'ui:gdm-returned',
    **prefixed_stages('return', desktop_entry('parent', source='gdm', entry='retained')),
    'parent-retained': 'ui:retained-parent-read',
    'expired-balance': 'ui:time-explanation-refresh-read',
    'parent-switch': 'system:parent-switch-user', 'denied-greeter': 'ui:gdm-returned',
    **prefixed_stages('denied', desktop_entry('child', source='gdm', entry='retained',
                                             expected='time-denied')),
}
SCREENS = {**SETUP, **EXPIRY, **RESULT}
LOGIN_STAGES = (set(fresh_desktop('parent'))
    | set(prefixed_stages('fresh', fresh_desktop('child')))
    | set(prefixed_stages('return', fresh_desktop('parent')))
    | set(prefixed_stages('denied', fresh_desktop('child', 'time-denied'))))
PLAN = JourneyPlan(
    prefix='ordinary-rest-of-day', worker_mode='ordinary_rest_of_day', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SETUP}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in EXPIRY},
            **{stage: 'step-3' for stage in RESULT}},
    advance_after={'activity-capture': 'step-2', 'lock-result': 'step-3'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES or stage in EXPIRY),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
        'return': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked'),
        'denied': ('child', 'denied-child-recipient-qualified', 'denied-child-recipient-rechecked'),
    },
    kiosk_request=('child', 'parent', 0, False),
    stage_actions={'setup-detached': 'calendar-window', 'desktop': 'native-verify',
                   'natural-expiry': 'natural-expiry'},
    activity_entries={'natural-expiry': 'activity-capture'},
)


class RestOfDayJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        if actions is None:
            actions = {**fixture_actions(include_refusal=False),
                       'calendar-window': self.declare_window, 'natural-expiry': self.natural_expiry}
        super().__init__(context, progress, plan, actions=actions)
        self.window = None
        self.last_calendar = None
        self.balance_clock = None
        self.countdown_clock = None
        self.initial_countdown = None
        self.expiry = None

    def calendar(self):
        value = self.vm.local_calendar(boundary_epoch_ns=(
            self.window['midnight_epoch_ns'] if self.window else None))
        if self.last_calendar is not None:
            previous = self.last_calendar
            require(all(value[key] == previous[key] for key in
                        ('timezone', 'utc_offset_seconds', 'boot_sha256')),
                    'rest-of-day:calendar-identity-changed')
            elapsed = value['epoch_ns'] - previous['readback']['epoch_ns']
            require(value['monotonic_start_ns'] - previous['monotonic_end_ns'] - 1_000_000_000
                    <= elapsed <= value['monotonic_end_ns'] - previous['monotonic_start_ns']
                    + 1_000_000_000, 'rest-of-day:clock-discontinuity')
        require(self.boot is None or self.boot == value['boot_sha256'], 'rest-of-day:boot-changed')
        self.last_calendar = value
        return value

    @staticmethod
    def declare_window(journey, guard):
        guard()
        require(journey.window is None, 'rest-of-day:window-replayed')
        preparation = preset_ordinary_midnight(journey, guard)
        value = journey.calendar()
        require(value['timezone'] == preparation['timezone']
                and value['epoch_ns'] >= preparation['readback_epoch_ns'],
                'rest-of-day:preset-clock-readback')
        local = datetime.datetime.fromisoformat(value['local_time']).replace(
            tzinfo=ZoneInfo(value['timezone']))
        start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        midnight = start + datetime.timedelta(days=1)
        require(midnight.timestamp() - start.timestamp() == 86400
                and start.utcoffset() == local.utcoffset() == midnight.utcoffset(),
                'rest-of-day:not-an-ordinary-day')
        boundary = int(midnight.timestamp()) * 1_000_000_000
        remaining = (boundary - value['readback']['epoch_ns']) / 1e9
        require(1200 <= remaining <= 1800, 'rest-of-day:scheduled-window-unavailable')
        journey.window = {'date': local.date().isoformat(), 'timezone': value['timezone'],
            'window_start': (midnight - datetime.timedelta(minutes=30)).isoformat(),
            'window_end': (midnight - datetime.timedelta(minutes=20)).isoformat(),
            'midnight': midnight.isoformat(), 'midnight_epoch_ns': boundary,
            'clock_precision_seconds': 1, 'balance_maximum_precision_seconds': 60,
            'countdown_precision_seconds': 1, 'lock_allowance_seconds': 15,
            'daily_allowance_seconds': 0, 'request_seconds': 0}
        guard()
        return {'preparation': preparation, 'window': journey.window, 'clock': value}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        boundary = self.window['midnight_epoch_ns'] if self.window else None
        if stage == 'before-grant':
            require_zero_grant(observed['ui']['revoke_cancel']['balances'])
        if stage == 'allowance-configured':
            check_balances(self, observed, 0)
            clock = self.calendar()
            require(clock['readback']['epoch_ns'] + 900_000_000_000 < boundary,
                    'rest-of-day:preparation-margin')
            observed['calendar'] = clock
        if stage == 'request-new-estimate':
            choice = observed['ui']['valid_choice']
            require(choice['estimate'] == {'kind': 'midnight'}
                    and choice['request']['duration_seconds'] == 0,
                    'rest-of-day:midnight-footer')
        if stage == 'request-approval-open':
            clock = self.calendar()
            require(clock['readback']['epoch_ns'] + 600_000_000_000 < boundary,
                    'rest-of-day:approval-margin')
            observed['calendar'] = clock
        if stage == 'approved-clock':
            self.balance_clock = self.calendar()
            observed['calendar'] = self.balance_clock
        if stage == 'approved-balance':
            value = observed['ui']['revoke_cancel']
            require(value['settings'] == {'child': 'fixture-child', 'limit_enabled': True,
                                         'allowance': ['0 minutes']}, 'rest-of-day:saved-profile')
            after, before = self.calendar(), self.balance_clock
            require(before is not None and after['monotonic_end_ns'] - before['monotonic_start_ns']
                    <= 60_000_000_000, 'rest-of-day:deadline-comparison-precision')
            balances = value['balances']
            require(balances['daily']['seconds'] == 0, 'rest-of-day:daily-zero')
            for key in ('one_time', 'total'):
                item = balances[key]
                require(1 <= item['precision_seconds'] <= 60
                        and 0 < (boundary - after['readback']['epoch_ns']) / 1e9
                            - item['precision_seconds'] - 1 <= item['seconds']
                        <= (boundary - before['epoch_ns']) / 1e9 + item['precision_seconds'] + 1,
                        'rest-of-day:public-midnight-deadline')
            observed['calendar'] = after
        if stage == 'activity-capture':
            self.countdown_clock = self.calendar()
            observed['calendar'] = self.countdown_clock
        if stage == 'natural-expiry':
            require(self.initial_countdown is None and self.countdown_clock is not None,
                    'rest-of-day:missing-or-replayed-countdown')
            sample = CountdownSample.from_ui(observed['ui'], boot_sha256=observed['boot_sha256'])
            clock = self.countdown_clock
            lower, upper = calendar_epoch_bounds(clock, sample.guest_read_bounds)
            low, high = countdown_seconds(sample.countdown.text)
            require(300 <= low <= high <= 1500 and upper - lower <= 10_000_000_000
                    and type(sample.countdown.seconds) is int
                    and (boundary - upper) / 1e9 - 1 <= sample.countdown.seconds
                        <= (boundary - lower) / 1e9 + 1,
                    'rest-of-day:positive-countdown-to-midnight')
            self.initial_countdown = sample
        if stage == 'expired-balance':
            clock = self.calendar()
            require(self.expiry is not None and clock['epoch_ns'] >= boundary,
                    'rest-of-day:missing-midnight-expiry')
            check_balances(self, observed, 0)
            observed['calendar'] = clock

    @staticmethod
    def natural_expiry(journey, guard):
        require(journey.initial_countdown is not None and journey.expiry is None,
                'rest-of-day:expiry-entry')
        result = await_natural_expiry(journey, guard, journey.initial_countdown,
            journey.activity_observations['activity-capture'], maximum_seconds=1500)
        # The display's minute rounding cannot widen the actual midnight bound.
        lower, upper = calendar_epoch_bounds(journey.countdown_clock, result['lock_read_bounds'])
        boundary = journey.window['midnight_epoch_ns']
        offsets = [(lower - boundary) / 1e9, (upper - boundary) / 1e9]
        print('rest-of-day:lock-offset-seconds '
              f'lower={offsets[0]:.6f} upper={offsets[1]:.6f}',
              file=sys.stderr, flush=True)
        require(boundary - 1_000_000_000 <= lower <= upper < boundary + 15_000_000_000,
                'rest-of-day:midnight-lock-deadline')
        result['midnight_lock_offset_seconds'] = offsets
        journey.expiry = result
        result['calendar'] = journey.calendar()
        return result


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-044/ordinary-rest-of-day'
    record_installed_journey(recorder, context, PLAN, timeout=3600, journey_type=RestOfDayJourney)


E2E_CASES = {'ordinary-rest-of-day': execute}
