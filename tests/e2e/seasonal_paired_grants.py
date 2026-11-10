"""Shared two-child history across a real seasonal clock change."""

import datetime
from dataclasses import replace
from zoneinfo import ZoneInfo

from accessible_ui import KIOSK_BOUND_OPERATIONS, OVERLAY_BOUND_OPERATIONS, NAMED_TIME_OPERATIONS
from calendar_fixture import preset_spring_forward, preset_fall_back
from countdown import CountdownSample
from guest_observations import calendar_epoch_bounds
from installed_journey import InstalledJourney, JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, fresh_desktop, native_activity_entry,
                            native_activity_resume, parent_management, parent_selection, prefixed_stages)
from journey_checks import check_balances, require_zero_grant
from kiosk_approved_flow import approved_request, obtain_time
from native_fixtures import fixture_actions
from natural_expiry_observation import await_natural_expiry
from private_artifacts import require
from real_interval import interval_toward
from request_flow import prepared_request


BINDINGS = {'jordan': ('other-child', 'parent', 0, False),
            'riley': ('child', 'parent', 600, False)}
CHOICES = {name: dict(child='existing-fixture-child' if name == 'jordan' else 'fixture-child',
                      approver='fixture-parent', duration_seconds=binding[2], allow_soft=False)
           for name, binding in BINDINGS.items()}
ENTRIES = {}
LOGIN_STAGES = set(fresh_desktop('parent'))


def entry(prefix, account, mode, expected='success'):
    ENTRIES[prefix] = account
    LOGIN_STAGES.update(prefixed_stages(prefix, fresh_desktop(account, expected)))
    return prefixed_stages(prefix, desktop_entry(account, source='gdm', entry=mode, expected=expected))


def estimate(prefix):
    return {prefix + '-' + stage: 'ui:' + operation for stage, operation in (
        ('launch', 'child-command-launch'), ('select', 'overlay-request-select'),
        ('read', 'overlay-request-estimate'), ('cancel', 'overlay-request-cancel'),
        ('desktop', 'overlay-desktop'))}


PREPARE = {
    **fresh_desktop('parent'), **parent_management(),
    'riley-before-grant': 'ui:revoke-balances',
    'riley-zero': 'ui:time-explanation-setup-zero-read',
    **prefixed_stages('jordan-settings', parent_selection(child='existing', screen_limits=True)),
    'jordan-before-grant': 'ui:revoke-balances',
    'jordan-zero': 'ui:time-explanation-setup-zero-read',
    'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **prefixed_stages('jordan-request', obtain_time(initial='observed', **CHOICES['jordan'], exit='automatic')),
    **entry('jordan-fresh', 'other-child', 'fresh'),
    **native_activity_entry('jordan-activity', child='other-child'),
    'jordan-before-countdown': 'ui:child-countdown-present',
    **estimate('jordan-before-estimate'),
    'jordan-switch': 'system:standard-switch-user', 'jordan-greeter': 'ui:gdm-returned',
    **prefixed_stages('riley-request', prepared_request(prefix='new', entry='new', initial='observed',
                                                       **CHOICES['riley'])),
    **{f'approval-wait-{i}': 'ui:kiosk-request-estimate' for i in range(1, 7)},
    **prefixed_stages('riley-request', approved_request(**CHOICES['riley'], exit='automatic', explicit=True)),
    **entry('riley-fresh', 'child', 'fresh'),
    **native_activity_entry('riley-activity', child='child'),
    **estimate('riley-before-estimate'),
    'riley-before-countdown': 'ui:child-countdown-present',
}
CROSSING = {
    'cross-transition': 'ui:child-countdown-present',
    'riley-after-countdown': 'ui:child-countdown-present',
    **estimate('riley-after-estimate'),
    **native_activity_resume('riley-continued', child='child'),
    'riley-switch': 'system:child-switch-user', 'riley-greeter': 'ui:gdm-returned',
    **entry('jordan-return', 'other-child', 'retained'),
    'jordan-after-countdown': 'ui:child-countdown-present',
    **estimate('jordan-after-estimate'),
    **native_activity_resume('jordan-continued', child='other-child'),
    'jordan-return-switch': 'system:standard-switch-user', 'jordan-return-greeter': 'ui:gdm-returned',
    **entry('riley-return', 'child', 'retained'),
    **native_activity_resume('riley-final-work', child='child'),
    'riley-expiry-countdown': 'ui:child-countdown-present',
}
RESULT = {
    'natural-expiry': 'ui:child-countdown-present',
    'lock-input-ready': 'ui:child-natural-expiry-lock-ready',
    'lock-result': 'ui:child-natural-expiry-lock-result',
    'return-greeter': 'system:child-return-greeter', 'returned-gdm': 'ui:gdm-returned',
    **entry('parent-return', 'parent', 'retained'),
    'parent-retained': 'ui:retained-parent-read',
    **prefixed_stages('expired-settings', parent_selection(screen_limits=True)),
    'expired-balance': 'ui:time-explanation-refresh-read',
    'parent-switch': 'system:parent-switch-user', 'denied-greeter': 'ui:gdm-returned',
    **entry('denied', 'child', 'retained', 'time-denied'),
    'denied-return-ready': 'ui:gdm-child-denied-return-ready',
    'denied-return-state': 'ui:gdm-child-denied-return-state',
    'denied-returned': 'ui:gdm-child-denied-returned',
    **entry('jordan-final', 'other-child', 'retained'),
    'jordan-final-countdown': 'ui:child-countdown-present',
    **native_activity_resume('jordan-final-work', child='other-child'),
}
SCREENS = {**PREPARE, **CROSSING, **RESULT}
CHALLENGES = {'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked')}
for prefix, role in ENTRIES.items():
    recipient = 'recipient-' if role == 'parent' else 'child-recipient-' if role == 'child' else 'standard-recipient-'
    CHALLENGES[prefix] = (role, prefix + '-' + recipient + 'qualified', prefix + '-' + recipient + 'rechecked')

# Every product input/read and both credential proofs retain the same explicit
# child/request. Only this finite two-child history changes that child by stage.
JORDAN_STAGES = {stage for stage in SCREENS if stage.startswith('jordan-')}
KIOSK_BINDINGS = {stage: BINDINGS['jordan'] for stage in JORDAN_STAGES
                  if SCREENS[stage].removeprefix('ui:') in KIOSK_BOUND_OPERATIONS}
OVERLAY_BINDINGS = {stage: BINDINGS['jordan'] for stage in JORDAN_STAGES
                    if SCREENS[stage].removeprefix('ui:') in OVERLAY_BOUND_OPERATIONS}
ACTIVITY_CHECKS = {stage: (name + '-activity-capture', 'same')
    for name in ('jordan', 'riley') for stage in SCREENS
    if stage.startswith((name + '-continued-', name + '-final-work-'))
    and stage.endswith('-opened')}
PLAN = JourneyPlan(
    prefix='spring-forward-paired-grants', worker_mode='spring_forward_paired_grants', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in PREPARE}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in CROSSING}, **{stage: 'step-3' for stage in RESULT}},
    advance_after={'riley-before-countdown': 'step-2', 'riley-expiry-countdown': 'step-3'},
    invocations=tuple(stage for stage, tag in SCREENS.items() if stage in LOGIN_STAGES
        or tag == 'ui:child-countdown-present' or stage in (
            'lock-input-ready', 'lock-result', 'denied-return-ready', 'denied-return-state', 'denied-returned')),
    challenges=CHALLENGES, kiosk_request=BINDINGS['riley'], kiosk_requests=KIOSK_BINDINGS,
    overlay_request=BINDINGS['riley'], overlay_requests=OVERLAY_BINDINGS,
    child_bindings={'parent-retained': 'existing', **{stage: 'existing' for stage in JORDAN_STAGES
                    if SCREENS[stage][3:] in NAMED_TIME_OPERATIONS | {'revoke-balances'}}},
    stage_actions={'setup-detached': 'calendar-window', 'desktop': 'native-verify',
        **{f'approval-wait-{i}': 'approval-wait' for i in range(1, 7)},
        'cross-transition': 'cross-transition', 'natural-expiry': 'natural-expiry'},
    activity_checks=ACTIVITY_CHECKS,
    activity_entries={'natural-expiry': 'riley-activity-capture'},
)
FALL_BACK_PLAN = replace(PLAN, prefix='fall-back-paired-grants', worker_mode='fall_back_paired_grants')


class PairedGrantsJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions if actions is not None else {
            **fixture_actions(include_refusal=False), 'calendar-window': self.declare_window,
            'approval-wait': self.wait_approval, 'cross-transition': self.cross_transition,
            'natural-expiry': self.natural_expiry})
        self.window = self.last_calendar = self.expiry = self.expiry_sample = None
        self.approvals, self.deadlines = {}, {}
        self.before, self.after = set(), set()

    def calendar(self):
        value = self.vm.local_calendar(boundary_epoch_ns=(
            self.window['transition_epoch_ns'] if self.window else None))
        previous = self.last_calendar
        if previous is not None:
            require(all(value[key] == previous[key] for key in ('timezone', 'boot_sha256')),
                    'spring-grants:calendar-identity-changed')
            elapsed = value['epoch_ns'] - previous['readback']['epoch_ns']
            require(value['monotonic_start_ns'] - previous['monotonic_end_ns'] - 1_000_000_000
                    <= elapsed <= value['monotonic_end_ns'] - previous['monotonic_start_ns']
                    + 1_000_000_000, 'spring-grants:clock-discontinuity')
        require(self.boot is None or self.boot == value['boot_sha256'], 'spring-grants:boot-changed')
        if self.window:
            offset = self.window['offset_before_seconds' if value['epoch_ns'] <
                self.window['transition_epoch_ns'] else 'offset_after_seconds']
            require(value['utc_offset_seconds'] == offset, 'spring-grants:unexpected-offset')
        self.last_calendar = value
        return value

    @staticmethod
    def declare_window(journey, guard):
        require(journey.window is None, 'spring-grants:window-replayed')
        fall_back = journey.plan.prefix == 'fall-back-paired-grants'
        prepared = (preset_fall_back if fall_back else preset_spring_forward)(journey, guard)
        day_seconds = (25 if fall_back else 23) * 3600
        clock = journey.calendar()
        zone = ZoneInfo(clock['timezone'])
        boundary = prepared['transition_epoch_ns']
        local = datetime.datetime.fromtimestamp(clock['epoch_ns'] / 1e9, zone)
        start = datetime.datetime.combine(local.date(), datetime.time(), zone)
        midnight = start + datetime.timedelta(days=1)
        require(clock['timezone'] == prepared['timezone']
                and clock['epoch_ns'] >= prepared['readback_epoch_ns']
                and 1500 <= (boundary - clock['readback']['epoch_ns']) / 1e9 <= 1800
                and midnight.timestamp() - start.timestamp() == day_seconds
                and int(midnight.timestamp()) * 1_000_000_000 == prepared['midnight_epoch_ns']
                and datetime.datetime.fromtimestamp(boundary / 1e9 - 1, zone).utcoffset().total_seconds()
                    == prepared['offset_before_seconds']
                and datetime.datetime.fromtimestamp(boundary / 1e9, zone).utcoffset().total_seconds()
                    == prepared['offset_after_seconds'], 'spring-grants:eligible-window')
        journey.window = {key: prepared[key] for key in ('timezone', 'transition_epoch_ns',
            'midnight_epoch_ns', 'offset_before_seconds', 'offset_after_seconds')}
        journey.window.update(date=local.date().isoformat(), day_seconds=day_seconds,
            approval_target_epoch_ns=boundary - 300_000_000_000,
            countdown_precision_seconds=1, balance_maximum_precision_seconds=60,
            observation_order=['Jordan before', 'Riley before', 'Riley after', 'Jordan after',
                               'Riley natural expiry and time refusal', 'Jordan final access'])
        return {'preparation': prepared, 'window': journey.window, 'clock': clock}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        boundary = self.window['transition_epoch_ns'] if self.window else None
        if stage.endswith('-before-grant'):
            require_zero_grant(observed['ui']['revoke_cancel']['balances'])
        if stage in ('jordan-zero', 'riley-zero', 'expired-balance'):
            check_balances(self, observed, 0)
        if stage.endswith(('request-approval-open', 'request-approval-success')):
            name = stage.split('-')[0]
            clock = self.calendar()
            require(clock['readback']['epoch_ns'] < boundary, 'spring-grants:approval-after-transition')
            if stage.endswith('-open'):
                if name == 'riley':
                    require(boundary - 300_000_000_000 <= clock['epoch_ns']
                            and clock['readback']['epoch_ns'] < boundary - 180_000_000_000,
                            'spring-grants:fixed-approval-window')
                self.approvals[name] = [clock['epoch_ns']]
            else:
                self.approvals[name].append(clock['readback']['epoch_ns'])
                require(name != 'riley' or clock['readback']['epoch_ns'] < boundary - 120_000_000_000,
                        'spring-grants:prechange-entry-margin')
            observed['calendar'] = clock
        if stage.endswith('countdown') or stage in ('cross-transition', 'natural-expiry'):
            name = 'jordan' if stage.startswith('jordan-') else 'riley'
            child = 'existing-fixture-child' if name == 'jordan' else 'fixture-child'
            sample = CountdownSample.from_ui(observed['ui'], boot_sha256=observed['boot_sha256'], child=child)
            clock = self.calendar()
            low, high = calendar_epoch_bounds(clock, sample.guest_read_bounds)
            seconds = sample.countdown.seconds
            require(type(seconds) is int and seconds > 0 and high - low < 10_000_000_000,
                    'spring-grants:countdown-precision')
            current = (low + (seconds - 2) * 1_000_000_000,
                       high + (seconds + 2) * 1_000_000_000)
            if name == 'jordan':
                require(current[0] <= self.window['midnight_epoch_ns'] <= current[1],
                        'spring-grants:original-local-midnight-deadline')
            else:
                issued = self.approvals['riley']
                require(current[0] <= issued[1] + 602_000_000_000
                        and current[1] >= issued[0] + 598_000_000_000,
                        'spring-grants:original-elapsed-deadline')
            if stage.endswith('before-countdown'):
                require(high < boundary, 'spring-grants:missing-before-witness')
                self.deadlines[name] = current
                self.before.add(name)
            else:
                original = self.deadlines[name]
                require(current[0] <= original[1] and current[1] >= original[0],
                        'spring-grants:deadline-changed')
            if stage.endswith('after-countdown'):
                require(self.before == {'jordan', 'riley'} and boundary <= low <= high
                        < boundary + 300_000_000_000, 'spring-grants:missing-after-witness')
                self.after.add(name)
            if stage == 'natural-expiry':
                require(self.after == {'jordan', 'riley'} and seconds >= 30,
                        'spring-grants:expiry-observation-margin')
                self.expiry_sample = sample
            observed['calendar'] = clock
        if stage.endswith('estimate-read') or stage.endswith('request-new-estimate'):
            name = stage.split('-')[0]
            value = observed['ui']['valid_choice']
            require(value['request']['child'] == CHOICES[name]['child'], 'spring-grants:estimate-child')
            if name == 'jordan':
                require(value['estimate'] == {'kind': 'midnight'}, 'spring-grants:midnight-estimate')
            else:
                clock = self.calendar()
                item = value['estimate']
                require(item['kind'] == 'fixed' and 1 <= item['precision_seconds'] <= 60,
                        'spring-grants:fixed-estimate-precision')
                if name not in self.deadlines:
                    # The kiosk request precedes approval; the overlay follows it.
                    if stage.endswith('request-new-estimate'):
                        require(item['seconds'] == 600, 'spring-grants:initial-fixed-estimate')
                    else:
                        issued = self.approvals[name]
                        require(1200 - (clock['readback']['epoch_ns'] - issued[0]) / 1e9
                                - item['precision_seconds'] <= item['seconds'] <= 1200,
                                'spring-grants:approved-fixed-estimate')
                else:
                    original = self.deadlines[name]
                    start, end = value['estimate_read_bounds']
                    low, high = calendar_epoch_bounds(clock, (start, end))
                    require(0 < start <= end <= clock['guest_monotonic_start_ns']
                            and end - start <= 45_000_000_000,
                            'spring-grants:estimate-calculation-bounds')
                    require((original[0] - high) / 1e9 + 600
                            - item['precision_seconds'] - 2 <= item['seconds']
                            <= (original[1] - low) / 1e9 + 600
                            + item['precision_seconds'] + 2, 'spring-grants:elapsed-estimate-changed')
                    observed['estimate_calculation_epoch_ns'] = [low, high]
                observed['calendar'] = clock

    @staticmethod
    def wait_toward(journey, guard, target):
        guard()
        clock = journey.calendar()
        if target > clock['epoch_ns']:
            interval_toward(journey, guard, clock['monotonic_end_ns'] + target - clock['epoch_ns'])
        return {'clock_before_wait': clock, 'target_epoch_ns': target}

    @staticmethod
    def wait_approval(journey, guard):
        return journey.wait_toward(journey, guard, journey.window['approval_target_epoch_ns'])

    @staticmethod
    def cross_transition(journey, guard):
        require(journey.before == {'jordan', 'riley'}, 'spring-grants:missing-paired-before')
        return journey.wait_toward(journey, guard, journey.window['transition_epoch_ns'] + 1_000_000_000)

    @staticmethod
    def natural_expiry(journey, guard):
        require(journey.expiry_sample is not None and journey.expiry is None, 'spring-grants:expiry-entry')
        result = await_natural_expiry(journey, guard, journey.expiry_sample,
            journey.activity_observations['riley-activity-capture'], maximum_seconds=600)
        low, high = calendar_epoch_bounds(journey.last_calendar, result['lock_read_bounds'])
        original = journey.deadlines['riley']
        require(original[0] - 1_000_000_000 <= low <= high < original[1] + 15_000_000_000,
                'spring-grants:original-deadline-lock')
        journey.expiry = result
        return {**result, 'original_deadline_epoch_ns': original, 'lock_epoch_ns': [low, high]}


def execute(recorder, context, plan):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-044/' + plan.prefix
    record_installed_journey(recorder, context, plan, timeout=3600, journey_type=PairedGrantsJourney)
