"""Case 196: exhausted daily time renews as the preset guest crosses midnight."""

import datetime
from zoneinfo import ZoneInfo

from calendar_fixture import preset_ordinary_midnight
from countdown import CountdownSample, check_countdown_balance
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (daily_time_profile, desktop_entry, fresh_desktop,
                            native_activity_entry, native_activity_resume, prefixed_stages)
from journey_checks import DailyTimeProfileJourney
from native_fixtures import fixture_actions
from natural_expiry_observation import await_natural_expiry
from private_artifacts import require
from real_interval import interval_toward
import watch_activity
from ui_observations import SettingsObservation


SETUP = {
    **fresh_desktop('parent'),
    **daily_time_profile(source='desktop', entry='same-user', window='new',
                         initial_enabled=False, minutes=1),
    **prefixed_stages('fresh', fresh_desktop('child')),
    **native_activity_entry('activity', child='child'),
    'natural-expiry': 'ui:child-countdown-present',
    'return-greeter': 'system:child-return-greeter',
    'returned-gdm': 'ui:gdm-returned',
    **prefixed_stages('return', desktop_entry('parent', source='gdm', entry='retained')),
    'parent-retained': 'ui:retained-parent-read',
    'exhausted-balance': 'ui:time-explanation-refresh-read',
}
# One bounded TIME03 interval per worker rendezvous. No reply waits for the
# whole midnight window, and read-only TIME05 independently witnesses crossing.
WAITS = {f'midnight-wait-{index}': 'ui:desktop' for index in range(1, 7)}
RENEWED = {
    'renewed-balance': 'ui:time-explanation-refresh-read',
    'parent-switch': 'system:parent-switch-user',
    'renewed-greeter': 'ui:gdm-returned',
    **prefixed_stages('renewed', desktop_entry('child', source='gdm', entry='retained')),
    'renewed-countdown': 'ui:child-countdown-present',
    **native_activity_resume('renewed-activity', child='child'),
    'renewed-activity-capture': 'ui:overlay-native-activity',
}
SCREENS = {**SETUP, **WAITS, **RENEWED}
LOGIN_STAGES = (set(fresh_desktop('parent'))
    | set(prefixed_stages('fresh', fresh_desktop('child')))
    | set(prefixed_stages('return', fresh_desktop('parent')))
    | set(prefixed_stages('renewed', fresh_desktop('child'))))
PLAN = JourneyPlan(
    prefix='ordinary-daily-reset', worker_mode='ordinary_daily_reset', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SETUP}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in WAITS},
            **{stage: 'step-3' for stage in RENEWED}},
    advance_after={'exhausted-balance': 'step-2', 'midnight-wait-6': 'step-3'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES
                      or stage in ('natural-expiry', 'renewed-countdown')),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
        'return': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked'),
        'renewed': ('child', 'renewed-child-recipient-qualified', 'renewed-child-recipient-rechecked'),
    },
    settings_checks={'same-parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
                     'profile-settings': SettingsObservation('fixture-child', True, ('1 minutes',))},
    balance_checks={'profile-configured': 60},
    stage_actions={'setup-detached': 'calendar-window', 'desktop': 'native-verify',
                   'natural-expiry': 'natural-expiry',
                   **{stage: 'midnight-wait' for stage in WAITS}},
    activity_entries={'natural-expiry': 'activity-capture', 'renewed-entry-guard': 'activity-capture'},
    activity_checks={stage: ('activity-capture', 'same') for stage in
                     ('renewed-activity-opened', 'renewed-activity-capture')},
)


class DailyResetJourney(DailyTimeProfileJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        if actions is None:
            actions = {**fixture_actions(include_refusal=False),
                       'calendar-window': self.declare_window,
                       'natural-expiry': self.natural_expiry,
                       'midnight-wait': self.wait_midnight}
        super().__init__(context, progress, plan, no_grant_checks=('profile-before',), actions=actions)
        self.window = None
        self.last_calendar = None
        self.balance = None
        self.initial_countdown = None
        self.expiry = None
        self.exhausted = False
        self.renewed_balance = None

    def calendar(self):
        value = self.vm.local_calendar(boundary_epoch_ns=(
            self.window['midnight_epoch_ns'] if self.window else None))
        if self.last_calendar is not None:
            previous = self.last_calendar
            require(all(value[key] == previous[key] for key in
                        ('timezone', 'utc_offset_seconds', 'boot_sha256')),
                    'daily-reset:calendar-identity-changed')
            elapsed = value['epoch_ns'] - previous['readback']['epoch_ns']
            require(value['monotonic_start_ns'] - previous['monotonic_end_ns'] - 1_000_000_000
                    <= elapsed <= value['monotonic_end_ns'] - previous['monotonic_start_ns']
                    + 1_000_000_000, 'daily-reset:clock-discontinuity')
        require(self.boot is None or self.boot == value['boot_sha256'], 'daily-reset:boot-changed')
        self.last_calendar = value
        return value

    @staticmethod
    def declare_window(journey, guard):
        guard()
        require(journey.window is None, 'daily-reset:window-replayed')
        preparation = preset_ordinary_midnight(journey, guard)
        with watch_activity.operation('Declaring the guest midnight and comparison precision'):
            value = journey.calendar()
        require(value['timezone'] == preparation['timezone']
                and value['epoch_ns'] >= preparation['readback_epoch_ns'],
                'daily-reset:preset-clock-readback')
        local = datetime.datetime.fromisoformat(value['local_time']).replace(
            tzinfo=ZoneInfo(value['timezone']))
        start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        midnight = start + datetime.timedelta(days=1)
        require(midnight.timestamp() - start.timestamp() == 86400
                and start.utcoffset() == local.utcoffset() == midnight.utcoffset(),
                'daily-reset:not-an-ordinary-day')
        boundary = int(midnight.timestamp()) * 1_000_000_000
        remaining = (boundary - value['readback']['epoch_ns']) / 1e9
        require(1200 <= remaining <= 1800, 'daily-reset:scheduled-window-unavailable')
        journey.window = {'date': local.date().isoformat(), 'timezone': value['timezone'],
            'window_start': (midnight - datetime.timedelta(minutes=30)).isoformat(),
            'window_end': (midnight - datetime.timedelta(minutes=20)).isoformat(),
            'midnight': midnight.isoformat(), 'midnight_epoch_ns': boundary,
            'daily_allowance_seconds': 60, 'grant_seconds': 0,
            'clock_precision_seconds': 1, 'balance_maximum_precision_seconds': 60,
            'countdown_precision_seconds': 1}
        return {'preparation': preparation, 'window': journey.window, 'clock': value}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'profile-configured':
            self.balance = observed['ui']['time_explanation']
        if stage == 'profile-settings':
            value = self.calendar()
            require(value['readback']['epoch_ns'] + 600_000_000_000
                    < self.window['midnight_epoch_ns'], 'daily-reset:preparation-margin')
            observed['calendar'] = value
        if stage == 'natural-expiry':
            require(self.initial_countdown is None and self.balance is not None,
                    'daily-reset:missing-or-replayed-countdown')
            sample = CountdownSample.from_ui(observed['ui'], boot_sha256=observed['boot_sha256'])
            require(0 < sample.countdown.seconds <= 60, 'daily-reset:initial-countdown')
            observed['comparison'] = check_countdown_balance(sample.countdown,
                seconds=self.balance['total']['seconds'],
                precision_seconds=self.balance['total']['precision_seconds'],
                observed_monotonic_ns=self.balance['observed_monotonic_ns'])
            self.initial_countdown = sample
        if stage in ('exhausted-balance', 'renewed-balance'):
            clock = self.calendar()
            value = observed['ui']['time_explanation']
            renewed = stage == 'renewed-balance'
            require(self.expiry is not None and all(
                value[key]['seconds'] == expected
                and value[key]['precision_seconds'] <= 60
                for key, expected in zip(('daily', 'one_time', 'total'),
                                         (60, 0, 60) if renewed else (0, 0, 0))),
                'daily-reset:renewed-balance' if renewed else 'daily-reset:exhausted-balance')
            require((clock['epoch_ns'] >= self.window['midnight_epoch_ns']) == renewed,
                    'daily-reset:balance-wrong-side-of-midnight')
            if renewed:
                require(self.exhausted, 'daily-reset:missing-zero-witness')
                self.renewed_balance = value
            else:
                self.exhausted = True
            observed['calendar'] = clock
        if stage == 'renewed-countdown':
            require(self.renewed_balance is not None, 'daily-reset:renewal-not-observed')
            sample = CountdownSample.from_ui(observed['ui'], boot_sha256=observed['boot_sha256'])
            require(0 < sample.countdown.seconds <= 60, 'daily-reset:renewed-countdown')
            observed['comparison'] = check_countdown_balance(sample.countdown,
                seconds=60, precision_seconds=self.renewed_balance['total']['precision_seconds'],
                observed_monotonic_ns=self.renewed_balance['observed_monotonic_ns'])

    @staticmethod
    def natural_expiry(journey, guard):
        require(journey.initial_countdown is not None and journey.expiry is None,
                'daily-reset:expiry-entry')
        journey.expiry = await_natural_expiry(journey, guard, journey.initial_countdown,
                                             journey.activity_observations['activity-capture'])
        return journey.expiry

    @staticmethod
    def wait_midnight(journey, guard):
        require(journey.exhausted, 'daily-reset:missing-zero-witness')
        guard()
        clock = journey.calendar()
        remaining = journey.window['midnight_epoch_ns'] - clock['epoch_ns']
        if remaining > 0:
            # The latest read's controller end is a conservative target: no
            # early reply can be mistaken for the real midnight crossing.
            target = clock['monotonic_end_ns'] + remaining
            interval_toward(journey, guard, target)
        result = journey.calendar()
        return {'clock': result, 'midnight_crossed':
                result['epoch_ns'] >= journey.window['midnight_epoch_ns']}


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-044/ordinary-daily-reset'
    record_installed_journey(recorder, context, PLAN, timeout=3600, journey_type=DailyResetJourney)


E2E_CASES = {'ordinary-daily-reset': execute}
