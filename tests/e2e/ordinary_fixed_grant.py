"""Case 198: midnight neither resets nor extends a fixed parent approval."""

import datetime
from zoneinfo import ZoneInfo

from calendar_fixture import preset_ordinary_midnight
from countdown import CountdownSample
from installed_journey import InstalledJourney, JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, fresh_desktop, native_activity_entry,
                            native_activity_resume, parent_management, prefixed_stages)
from journey_checks import check_balances, require_zero_grant
from kiosk_approved_flow import approved_request
from native_fixtures import fixture_actions
from natural_expiry_observation import await_natural_expiry
from private_artifacts import require
from real_interval import interval_toward
from request_flow import prepared_request


CHOICES = dict(child='fixture-child', approver='fixture-parent',
               duration_seconds=1200, allow_soft=False)
PREPARE = {
    **fresh_desktop('parent'), **parent_management(),
    'before-grant': 'ui:revoke-balances',
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
    'repeat-desktop': 'ui:desktop',
    'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned',
    **prefixed_stages('request', prepared_request(prefix='new', entry='new',
                                                initial='observed', **CHOICES)),
    **{f'approval-wait-{i}': 'ui:kiosk-request-estimate' for i in range(1, 5)},
    **prefixed_stages('request', approved_request(**CHOICES, exit='automatic', explicit=True)),
    'approved-balance': 'ui:revoke-balances',
    **prefixed_stages('fresh', fresh_desktop('child')),
    **native_activity_entry('activity', child='child'),
    'initial-countdown': 'ui:child-countdown-present',
}
CROSSING = {
    **{f'midnight-wait-{i}': 'ui:child-countdown-present' for i in range(1, 7)},
    'before-countdown': 'ui:child-countdown-present',
    'cross-midnight': 'ui:child-countdown-present',
    'after-countdown': 'ui:child-countdown-present',
    **native_activity_resume('continued-activity', child='child'),
    'continued-activity-capture': 'ui:overlay-native-activity',
}
RESULT = {
    'natural-expiry': 'ui:child-countdown-present',
    'lock-input-ready': 'ui:child-natural-expiry-lock-ready',
    'lock-result': 'ui:child-natural-expiry-lock-result',
    'return-greeter': 'system:child-return-greeter', 'returned-gdm': 'ui:gdm-returned',
    **prefixed_stages('return', desktop_entry('parent', source='gdm', entry='retained')),
    'parent-retained': 'ui:retained-parent-read',
    'expired-balance': 'ui:time-explanation-refresh-read',
    'parent-switch': 'system:parent-switch-user', 'denied-greeter': 'ui:gdm-returned',
    **prefixed_stages('denied', desktop_entry('child', source='gdm', entry='retained',
                                             expected='time-denied')),
}
SCREENS = {**PREPARE, **CROSSING, **RESULT}
LOGIN_STAGES = (set(fresh_desktop('parent'))
    | set(prefixed_stages('fresh', fresh_desktop('child')))
    | set(prefixed_stages('return', fresh_desktop('parent')))
    | set(prefixed_stages('denied', fresh_desktop('child', 'time-denied'))))
TIME_STAGES = {stage for stage, tag in SCREENS.items() if tag == 'ui:child-countdown-present'}
PLAN = JourneyPlan(
    prefix='ordinary-fixed-grant', worker_mode='ordinary_fixed_grant', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in PREPARE}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in CROSSING},
            **{stage: 'step-3' for stage in RESULT}},
    advance_after={'initial-countdown': 'step-2', 'continued-activity-capture': 'step-3'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES | TIME_STAGES
                      or stage in ('lock-input-ready', 'lock-result')),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
        'return': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked'),
        'denied': ('child', 'denied-child-recipient-qualified', 'denied-child-recipient-rechecked'),
    },
    kiosk_request=('child', 'parent', 1200, False),
    stage_actions={'setup-detached': 'calendar-window', 'desktop': 'native-verify',
                   **{f'approval-wait-{i}': 'approval-wait' for i in range(1, 5)},
                   **{f'midnight-wait-{i}': 'midnight-wait' for i in range(1, 7)},
                   'cross-midnight': 'cross-midnight', 'natural-expiry': 'natural-expiry'},
    activity_entries={'natural-expiry': 'continued-activity-capture'},
    activity_checks={stage: ('activity-capture', 'same') for stage in
                     ('continued-activity-opened', 'continued-activity-capture')},
)


class FixedGrantJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        if actions is None:
            actions = {**fixture_actions(include_refusal=False),
                'calendar-window': self.declare_window, 'approval-wait': self.wait_approval,
                'midnight-wait': self.wait_before_midnight, 'cross-midnight': self.cross_midnight,
                'natural-expiry': self.natural_expiry}
        super().__init__(context, progress, plan, actions=actions)
        self.window = self.last_calendar = self.approval_start = self.approval_end = None
        self.deadline_bounds = self.countdown_clock = self.initial_countdown = None
        self.expiry = None
        self.before_midnight = self.after_midnight = False

    def calendar(self):
        value = self.vm.local_calendar(boundary_epoch_ns=(
            self.window['midnight_epoch_ns'] if self.window else None))
        if self.last_calendar is not None:
            previous = self.last_calendar
            require(all(value[key] == previous[key] for key in
                        ('timezone', 'utc_offset_seconds', 'boot_sha256')),
                    'fixed-grant:calendar-identity-changed')
            elapsed = value['epoch_ns'] - previous['readback']['epoch_ns']
            require(value['monotonic_start_ns'] - previous['monotonic_end_ns'] - 1_000_000_000
                    <= elapsed <= value['monotonic_end_ns'] - previous['monotonic_start_ns']
                    + 1_000_000_000, 'fixed-grant:clock-discontinuity')
        require(self.boot is None or self.boot == value['boot_sha256'], 'fixed-grant:boot-changed')
        self.last_calendar = value
        return value

    @staticmethod
    def declare_window(journey, guard):
        guard()
        require(journey.window is None, 'fixed-grant:window-replayed')
        preparation = preset_ordinary_midnight(journey, guard)
        value = journey.calendar()
        require(value['timezone'] == preparation['timezone']
                and value['epoch_ns'] >= preparation['readback_epoch_ns'],
                'fixed-grant:preset-clock-readback')
        local = datetime.datetime.fromisoformat(value['local_time']).replace(
            tzinfo=ZoneInfo(value['timezone']))
        start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        midnight = start + datetime.timedelta(days=1)
        require(midnight.timestamp() - start.timestamp() == 86400
                and start.utcoffset() == local.utcoffset() == midnight.utcoffset(),
                'fixed-grant:not-an-ordinary-day')
        boundary = int(midnight.timestamp()) * 1_000_000_000
        require(1200 <= (boundary - value['readback']['epoch_ns']) / 1e9 <= 1800,
                'fixed-grant:scheduled-window-unavailable')
        journey.window = {'date': local.date().isoformat(), 'timezone': value['timezone'],
            'midnight': midnight.isoformat(), 'midnight_epoch_ns': boundary,
            'approval_target_epoch_ns': boundary - 600_000_000_000,
            'request_seconds': 1200, 'daily_allowance_seconds': 0,
            'clock_precision_seconds': 1, 'balance_maximum_precision_seconds': 60,
            'countdown_precision_seconds': 1, 'lock_allowance_seconds': 15}
        return {'preparation': preparation, 'window': journey.window, 'clock': value}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        boundary = self.window['midnight_epoch_ns'] if self.window else None
        if stage == 'before-grant':
            require_zero_grant(observed['ui']['revoke_cancel']['balances'])
        if stage == 'allowance-configured':
            check_balances(self, observed, 0)
        if stage == 'request-new-estimate':
            choice = observed['ui']['valid_choice']
            require(choice['estimate']['kind'] == 'fixed'
                    and choice['estimate']['seconds'] == 1200
                    and choice['request']['duration_seconds'] == 1200,
                    'fixed-grant:request-estimate')
        if stage == 'request-approval-open':
            self.approval_start = self.calendar()
            now = self.approval_start['epoch_ns']
            require(boundary - 600_000_000_000 <= now
                    and self.approval_start['readback']['epoch_ns'] < boundary - 420_000_000_000,
                    'fixed-grant:approval-window')
            observed['calendar'] = self.approval_start
        if stage == 'request-approval-success':
            self.approval_end = self.calendar()
            require(self.approval_end['readback']['epoch_ns'] < boundary - 300_000_000_000,
                    'fixed-grant:child-entry-margin')
            observed['calendar'] = self.approval_end
        if stage == 'approved-balance':
            value = observed['ui']['revoke_cancel']
            require(value['settings'] == {'child': 'fixture-child', 'limit_enabled': True,
                                         'allowance': ['0 minutes']}, 'fixed-grant:saved-profile')
            require(value['balances']['daily']['seconds'] == 0, 'fixed-grant:daily-zero')
            clock = self.calendar()
            for key in ('one_time', 'total'):
                item = value['balances'][key]
                require(1 <= item['precision_seconds'] <= 60
                        and 1200 - (clock['readback']['epoch_ns'] - self.approval_start['epoch_ns']) / 1e9
                            - item['precision_seconds'] <= item['seconds'] <= 1200,
                        'fixed-grant:approved-balance')
            observed['calendar'] = clock
        if stage == 'activity-capture':
            self.countdown_clock = self.calendar()
            observed['calendar'] = self.countdown_clock
        if stage in TIME_STAGES:
            sample = CountdownSample.from_ui(observed['ui'], boot_sha256=observed['boot_sha256'])
            clock = self.countdown_clock or self.last_calendar
            low = clock['epoch_ns'] + sample.guest_read_bounds[0] - clock['guest_monotonic_end_ns']
            high = clock['epoch_ns'] + sample.guest_read_bounds[1] - clock['guest_monotonic_start_ns']
            seconds = sample.countdown.seconds
            require(type(seconds) is int and seconds > 0 and high - low <= 10_000_000_000,
                    'fixed-grant:countdown-precision')
            current = (low + (seconds - 1) * 1_000_000_000,
                       high + (seconds + 1) * 1_000_000_000)
            if stage == 'initial-countdown':
                require(self.deadline_bounds is None and high < boundary - 120_000_000_000
                        and current[0] > boundary + 300_000_000_000,
                        'fixed-grant:initial-spanning-grant')
                require(current[1] >= self.approval_start['epoch_ns'] + 1199_000_000_000
                        and current[0] <= self.approval_end['readback']['epoch_ns'] + 1201_000_000_000,
                        'fixed-grant:original-approval-deadline')
                self.deadline_bounds = current
            else:
                require(self.deadline_bounds is not None
                        and current[0] <= self.deadline_bounds[1]
                        and current[1] >= self.deadline_bounds[0],
                        'fixed-grant:original-deadline-changed')
            if stage == 'before-countdown':
                require(boundary - 180_000_000_000 <= low <= high < boundary,
                        'fixed-grant:before-midnight-witness')
                self.before_midnight = True
            if stage == 'after-countdown':
                require(self.before_midnight and boundary <= low <= high
                        < boundary + 180_000_000_000 and seconds >= 180,
                        'fixed-grant:after-midnight-access')
                self.after_midnight = True
            if stage == 'natural-expiry':
                require(self.after_midnight, 'fixed-grant:missing-continuation')
                self.initial_countdown = sample
            # Refresh the mapping after preserving this sample's original read.
            observed['calendar'] = self.calendar()
        if stage == 'expired-balance':
            require(self.expiry is not None, 'fixed-grant:missing-expiry')
            check_balances(self, observed, 0)
            observed['calendar'] = self.calendar()

    @staticmethod
    def wait_toward(journey, guard, target):
        guard()
        clock = journey.calendar()
        remaining = target - clock['epoch_ns']
        if remaining > 0:
            interval_toward(journey, guard, clock['monotonic_end_ns'] + remaining)
        # The next declared observation independently proves the result. Keep
        # one clock read plus one <=300-second wait inside the worker's budget.
        return {'clock_before_wait': clock, 'target_epoch_ns': target}

    @staticmethod
    def wait_approval(journey, guard):
        return journey.wait_toward(journey, guard, journey.window['approval_target_epoch_ns'])

    @staticmethod
    def wait_before_midnight(journey, guard):
        return journey.wait_toward(journey, guard,
                                  journey.window['midnight_epoch_ns'] - 120_000_000_000)

    @staticmethod
    def cross_midnight(journey, guard):
        require(journey.before_midnight, 'fixed-grant:missing-before-witness')
        return journey.wait_toward(journey, guard,
                                  journey.window['midnight_epoch_ns'] + 1_000_000_000)

    @staticmethod
    def natural_expiry(journey, guard):
        require(journey.initial_countdown is not None and journey.expiry is None,
                'fixed-grant:expiry-entry')
        result = await_natural_expiry(journey, guard, journey.initial_countdown,
            journey.activity_observations['continued-activity-capture'], maximum_seconds=1500)
        clock = journey.last_calendar
        start, end = result['lock_read_bounds']
        low = clock['epoch_ns'] + start - clock['guest_monotonic_end_ns']
        high = clock['epoch_ns'] + end - clock['guest_monotonic_start_ns']
        require(journey.deadline_bounds[0] - 1_000_000_000 <= low <= high
                < journey.deadline_bounds[1] + 15_000_000_000,
                'fixed-grant:original-deadline-lock')
        result['original_deadline_epoch_ns'] = journey.deadline_bounds
        result['lock_epoch_ns'] = [low, high]
        journey.expiry = result
        return result


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-044/ordinary-fixed-grant'
    record_installed_journey(recorder, context, PLAN, timeout=3600, journey_type=FixedGrantJourney)


E2E_CASES = {'ordinary-fixed-grant': execute}
