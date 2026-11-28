"""Case 268: conserve saved kiosk time through reboot and redeem before fresh login."""

from accessible_ui import NAMED_CHILD_OPERATIONS
from countdown import CountdownSample
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, fresh_desktop, native_activity_entry, native_usable_app,
                            prefixed_stages, rejected_gdm_return, station_entry)
from journey_checks import require_zero_grant
from kiosk_approved_flow import approved_request
from named_app_set import named_app_set
from native_fixtures import fixture_actions
from natural_expiry_observation import await_natural_expiry
from policy_edits import AppPolicyJourney
from private_artifacts import require
from real_interval import interval_action
from saved_time_retained_unlock import (APPS, DEFERRED_SECONDS, EXPIRE, INITIAL_SECONDS, SECONDS_MARGIN,
                                       TRANSFER_LEAD_SECONDS, PLAN as RETAINED_PLAN, approved_time,
                                       elapsed_interval, elapsed_result)


FULL_REQUEST = ('child', 'parent', INITIAL_SECONDS, True)
CANCELLED_REQUEST = ('child', 'parent', 75, True)
EXTRA_REQUEST = ('child', 'parent', DEFERRED_SECONDS, True)
MAXIMUM_SAVED_SECONDS = 2 * INITIAL_SECONDS + DEFERRED_SECONDS


def deferred_approval(prefix):
    return prefixed_stages(prefix, {
        'new-choices': 'ui:kiosk-request-select', 'new-estimate': 'ui:kiosk-request-estimate',
        **{f'approval-{stage}': f'ui:kiosk-saved-mate-{operation}' for stage, operation in (
            ('open', 'open'), ('qualified', 'qualified'), ('rechecked', 'rechecked'),
            ('success', 'submit-success'))},
    })


RUNNING = {
    **named_app_set(source='gdm', entry='fresh', window='new', child='child',
                    apps=APPS, prefix='rules', finish='parent'),
    'profile-before': 'ui:revoke-balances',
    'profile-zero': 'ui:time-explanation-setup-zero-read',
    'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned', 'initial-no-child': 'system:child-entry-fresh',
    **approved_time('initial'),
    'first-request-tab': 'ui:kiosk-saved-tab-request',
    **deferred_approval('first'),
    'first-saved-read': 'ui:kiosk-saved-read',
    'cancel-request-tab': 'ui:kiosk-saved-tab-request',
    'cancel-new-choices': 'ui:kiosk-request-select',
    'cancel-new-estimate': 'ui:kiosk-request-estimate',
    'cancel-prompt': 'ui:kiosk-mate-cancel',
    'cancel-approved-tab': 'ui:kiosk-saved-tab-approved',
    'cancel-saved-read': 'ui:kiosk-saved-read',
    'immediate-request-tab': 'ui:kiosk-saved-tab-request',
    **prefixed_stages('immediate', {
        'new-choices': 'ui:kiosk-request-select', 'new-estimate': 'ui:kiosk-request-estimate',
        **approved_request(child='fixture-child', approver='fixture-parent',
                           duration_seconds=INITIAL_SECONDS, allow_soft=True, exit='automatic', explicit=True),
    }),
    **approved_time('running'),
    'running-reread': 'ui:kiosk-saved-read',
}
SAVE_AND_REBOOT = {
    'extra-request-tab': 'ui:kiosk-saved-tab-request',
    **deferred_approval('extra'),
    'combined-read': 'ui:kiosk-saved-read',
    'before-reboot-cancel': 'ui:kiosk-request-cancel',
    'before-reboot-returned': 'ui:gdm-station-returned',
    **prefixed_stages('reboot-parent', desktop_entry('parent', source='gdm', entry='retained')),
    'reboot-requested': 'system:parent-desktop-identity', 'reboot-greeter': 'ui:gdm-list',
    **approved_time('rebooted'),
    'before-denial-cancel': 'ui:kiosk-request-cancel',
    'before-denial-returned': 'ui:gdm-station-returned',
    **prefixed_stages('denied', desktop_entry('child', source='gdm', entry='fresh', expected='time-denied')),
    **rejected_gdm_return(),
    **approved_time('reuse'),
}
REDEEM = {
    'use-saved': 'ui:kiosk-saved-use', 'use-returned': 'ui:gdm-station-returned',
    **prefixed_stages('fresh', desktop_entry('child', source='gdm', entry='fresh')),
    'countdown': 'ui:child-countdown-present',
    **native_activity_entry('activity', child='child'),
    **prefixed_stages('soft', native_usable_app('command', child='child', role='S')),
}
SCREENS = {**RUNNING, **SAVE_AND_REBOOT, **REDEEM, **EXPIRE}
LOGIN_STAGES = (*fresh_desktop('parent'), *prefixed_stages('reboot-parent', fresh_desktop('parent')),
                *prefixed_stages('denied', fresh_desktop('child', 'time-denied')),
                *prefixed_stages('fresh', fresh_desktop('child')))
INVOCATIONS = (*LOGIN_STAGES, *rejected_gdm_return(), 'natural-expiry', 'lock-input-ready', 'lock-result')
PLAN = JourneyPlan(
    prefix='saved-time-reboot-fresh-login', worker_mode='saved_time_fresh_login', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: f'step-{index}' for index, screens in enumerate(
                (RUNNING, SAVE_AND_REBOOT, REDEEM, EXPIRE), 1) for stage in screens},
            'installed-greeter': 'start'},
    advance_after={'running-reread': 'step-2', 'reuse-read': 'step-3', 'soft-submitted': 'step-4'},
    stage_actions={'desktop': 'native-verify', 'running-read': 'real-interval',
                   'natural-expiry': 'natural-expiry'},
    child_bindings={stage: 'child' for stage, tag in SCREENS.items()
                    if tag.removeprefix('ui:') in NAMED_CHILD_OPERATIONS},
    match_checks=RETAINED_PLAN.match_checks, access_checks=RETAINED_PLAN.access_checks,
    balance_checks={'profile-zero': 0},
    invocations=tuple(stage for stage in SCREENS if stage in INVOCATIONS),
    challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
                'reboot-parent': ('parent', 'reboot-parent-recipient-qualified', 'reboot-parent-recipient-rechecked'),
                'denied': ('child', 'denied-child-recipient-qualified', 'denied-child-recipient-rechecked'),
                'fresh': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked')},
    activity_entries={'natural-expiry': 'activity-capture'},
    reboot_transition=('reboot-requested', 'reboot-greeter'),
    kiosk_request=FULL_REQUEST,
    kiosk_requests={**{stage: CANCELLED_REQUEST for stage in ('cancel-new-choices', 'cancel-new-estimate')},
                    **{stage: EXTRA_REQUEST for stage in deferred_approval('extra')}},
    assertions_after={'running-reread': 'running-time-elapses', 'reuse-read': 'time-saved-and-stable',
                      'soft-submitted': 'saved-time-restores-access',
                      'after-read': 'restriction-returns-without-saved-copy'},
)


class SavedTimeFreshLoginJourney(AppPolicyJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, actions={
            **fixture_actions(include_refusal=False, profile='activity'),
            'real-interval': interval_action(2), 'natural-expiry': self.natural_expiry,
        } if actions is None else actions)
        self.running = None
        self.transfer = None
        self.saved = None
        self.redemption = None
        self.expiry_sample = None

    @staticmethod
    def check_balance(value, *, saved, running):
        require(value['child'] == 'fixture-child' and value['daily_seconds'] == 0
                and value['saved_seconds'] == saved and value['running_seconds'] == running
                and value['state'] == ('ready' if saved or running else 'empty')
                and value['actions']['use_saved'] is bool(saved)
                and value['actions']['pause'] is bool(running), 'saved-time:fresh-login-balance')

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        ui = observed.get('ui', {})
        value = ui.get('saved_time')
        if stage == 'profile-before':
            require_zero_grant(ui['revoke_cancel']['balances'])
        elif stage in ('initial-read', 'after-read'):
            self.check_balance(value, saved=0, running=0)
        elif stage in ('first-saved-read', 'cancel-saved-read'):
            self.check_balance(value, saved=INITIAL_SECONDS, running=0)
        elif stage in ('running-read', 'running-reread'):
            seconds = value['running_seconds']
            require(type(seconds) is int and 45 <= seconds <= INITIAL_SECONDS,
                    'saved-time:immediate-running-grant')
            self.check_balance(value, saved=INITIAL_SECONDS, running=seconds)
            if stage == 'running-reread':
                before, bounds = self.running
                low, high = elapsed_interval(bounds, self.ui.read_bounds)
                decrease = before - seconds
                require(0 < decrease and low - SECONDS_MARGIN <= decrease <= high + SECONDS_MARGIN,
                        'saved-time:running-decrease')
                observed['comparison'] = {'decrease_seconds': decrease,
                                          'elapsed_interval_seconds': elapsed_result(low, high)}
            self.running = (seconds, self.ui.read_bounds)
        elif stage == 'extra-approval-success':
            self.transfer = self.ui.read_bounds
        elif stage == 'combined-read':
            self.saved = value['saved_seconds']
            require(type(self.saved) is int and INITIAL_SECONDS + DEFERRED_SECONDS < self.saved
                    <= MAXIMUM_SAVED_SECONDS, 'saved-time:combined-balance')
            self.check_balance(value, saved=self.saved, running=0)
            before, bounds = self.running
            low, high = elapsed_interval(bounds, self.transfer)
            transferred = self.saved - INITIAL_SECONDS - DEFERRED_SECONDS
            require(before - high - TRANSFER_LEAD_SECONDS - SECONDS_MARGIN <= transferred
                    <= before - low - TRANSFER_LEAD_SECONDS + SECONDS_MARGIN,
                    'saved-time:transfer-conservation')
            observed['comparison'] = {'transferred_seconds': transferred,
                'elapsed_interval_seconds': elapsed_result(low + TRANSFER_LEAD_SECONDS,
                                                          high + TRANSFER_LEAD_SECONDS)}
        elif stage in ('rebooted-read', 'reuse-read'):
            self.check_balance(value, saved=self.saved, running=0)
        elif stage == 'use-saved':
            require(value['saved_seconds'] == self.saved, 'saved-time:wrong-redemption-balance')
            self.redemption = self.ui.read_bounds
        elif stage in ('countdown', 'natural-expiry'):
            current = CountdownSample.from_ui(ui, boot_sha256=observed['boot_sha256'])
            low, high = elapsed_interval(self.redemption, current.read_bounds,
                                         maximum_seconds=self.saved)
            seconds = current.countdown.seconds
            deduction = self.saved - seconds
            require(0 < seconds and 0 < deduction
                    and low - SECONDS_MARGIN <= deduction <= high + SECONDS_MARGIN,
                    'saved-time:redemption-countdown')
            observed['comparison'] = {'deducted_seconds': deduction,
                                      'elapsed_interval_seconds': elapsed_result(low, high)}
            if stage == 'natural-expiry':
                self.expiry_sample = current

    @staticmethod
    def natural_expiry(journey, guard):
        return await_natural_expiry(journey, guard, journey.expiry_sample,
                                    journey.activity_observations['activity-capture'], maximum_seconds=600)


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-066/saved-time-fresh-login'
    record_installed_journey(recorder, context, PLAN, journey_type=SavedTimeFreshLoginJourney)


E2E_CASES = {'saved-time-fresh-login': execute}
