"""One child's early idle return, original expiry and approved recovery."""
from copy import deepcopy
from dataclasses import replace
import time

from accessible_ui import KIOSK_BOUND_OPERATIONS, NAMED_CHILD_OPERATIONS, countdown_seconds
from app_restart_active import (AppRestartActiveJourney, PLAN as ACTIVE_PLAN,
                                SETUP as ACTIVE_SETUP, RETURN as ACTIVE_RETURN)
from countdown import CountdownObservation, check_countdown_balance
from installed_journey import record_installed_journey
from journey_blocks import (desktop_entry, desktop_return, fresh_desktop, native_activity_resume,
                            native_blocked_app, native_usable_app, prefixed_stages,
                            rejected_gdm_return, station_entry)
from kiosk_approved_flow import approved_request
from native_fixtures import fixture_actions
from private_artifacts import require
from real_interval import interval_action
from request_flow import prepared_request


GRANT_SECONDS = 600
RECOVERY_SECONDS = 1200
# Capture unchanged policy before issuance. The child's public countdown gives
# the original live balance without a round trip through Parent after approval.
SETUP = {}
for stage, tag in ACTIVE_SETUP.items():
    if stage.startswith(('issued-return-', 'issued-leave-', 'before-parent-')) or stage in (
            'issued-policy', 'before-policy'):
        continue
    SETUP[stage] = tag
    if stage == 'jordan-time':
        SETUP['prepared-policy'] = 'ui:revoke-saved-balances'
EARLY = {
    **prefixed_stages('early-child', desktop_entry('other-child', source='gdm', entry='retained')),
    'early-idle': 'ui:child-countdown-present',
    'early-countdown': 'ui:child-countdown-present',
    **{stage: 'ui:native-policy-activity' if stage == 'early-resume-opened' else tag
       for stage, tag in native_activity_resume('early-resume', child='other-child').items()},
    **desktop_return('early-leave', account='other-child'),
    **prefixed_stages('early-parent', desktop_entry('parent', source='gdm', entry='retained')),
    **{stage: tag for stage, tag in ACTIVE_RETURN.items()
       if stage not in ('original-close', 'original-closed', 'final-countdown')
       and stage != 'final-policy'
       and not stage.startswith(('hard-', 'soft-', 'final-parent-'))},
    'tour-countdown': 'ui:child-countdown-present',
}
EXPIRY = {'expiry-wait': 'ui:child-countdown-present'}
RECOVERY_CHOICES = dict(child='existing-fixture-child', approver='fixture-parent',
                        duration_seconds=RECOVERY_SECONDS, allow_soft=True)
RECOVERY = {
    'expired-return': 'system:standard-return-greeter',
    'expired-greeter': 'ui:gdm-returned',
    **prefixed_stages('expired-parent', desktop_entry('parent', source='gdm', entry='retained')),
    'expired-policy': 'ui:revoke-saved-balances',
    **desktop_return('expired-parent-leave', account='parent'),
    **prefixed_stages('denied-child', desktop_entry('other-child', source='gdm',
                                                   entry='retained', expected='time-denied')),
    **rejected_gdm_return(),
    **prefixed_stages('recovery-station', station_entry()),
    'recovery-jordan': 'ui:remembered-kiosk-jordan-read',
    **prefixed_stages('recovery', {
        **prepared_request(prefix='new', entry='open', initial='observed', **RECOVERY_CHOICES),
        **approved_request(**RECOVERY_CHOICES, exit='automatic', explicit=True)}),
    **prefixed_stages('recovered-parent', desktop_entry('parent', source='gdm', entry='retained')),
    'recovered-policy': 'ui:revoke-saved-balances',
    **desktop_return('recovered-parent-leave', account='parent'),
    **prefixed_stages('recovered-child', desktop_entry('other-child', source='gdm', entry='retained')),
    'recovered-countdown': 'ui:child-countdown-present',
    **{stage: 'ui:native-policy-activity' if stage == 'recovered-resume-opened' else tag
       for stage, tag in native_activity_resume('recovered-resume', child='other-child').items()},
    **prefixed_stages('recovered-hard', native_blocked_app('H')),
    **prefixed_stages('recovered-soft', native_usable_app('command', role='unmatched-soft')),
}
SCREENS = {**SETUP, **EARLY, **EXPIRY, **RECOVERY}
LOGINS = {**{prefix: binding[0] for prefix, binding in ACTIVE_PLAN.challenges.items()},
          'early-child': 'other-child', 'early-parent': 'parent',
          'expired-parent': 'parent', 'denied-child': 'other-child',
          'recovered-parent': 'parent', 'recovered-child': 'other-child'}
LOGINS = {prefix: role for prefix, role in LOGINS.items() if prefix + '-entry-guard' in SCREENS}
LOGIN_STAGES = {prefix + '-' + stage for prefix, role in LOGINS.items()
                for stage in fresh_desktop(role, 'time-denied' if prefix == 'denied-child' else 'success')}
PLAN = replace(ACTIVE_PLAN, prefix='idle-active-expired', worker_mode='idle_active_expired',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: phase for phase, screens in (('step-1', SETUP), ('step-2', EARLY),
                ('step-3', EXPIRY), ('step-4', RECOVERY)) for stage in screens},
            'installed-greeter': 'start'},
    advance_after={'capture-returned': 'step-2', 'tour-countdown': 'step-3', 'expiry-wait': 'step-4'},
    stage_actions={'desktop': 'native-verify', 'early-idle': 'early-idle', 'expiry-wait': 'idle-to-expiry'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES
                      or stage in rejected_gdm_return()),
    challenges={prefix: (role, prefix + '-' + ('recipient-qualified' if role == 'parent'
                     else 'child-recipient-qualified' if role == 'child' else 'standard-recipient-qualified'),
                     prefix + '-' + ('recipient-rechecked' if role == 'parent'
                     else 'child-recipient-rechecked' if role == 'child' else 'standard-recipient-rechecked'))
                for prefix, role in LOGINS.items()},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS
                    and not stage.startswith(('riley-', 'returned-riley-'))},
    kiosk_request=('other-child', 'parent', RECOVERY_SECONDS, True),
    kiosk_requests={stage: ('other-child', 'parent', GRANT_SECONDS, True)
                    for stage, tag in SETUP.items() if stage.startswith('request-')
                    and tag.removeprefix('ui:') in KIOSK_BOUND_OPERATIONS},
    activity_entries={stage + '-entry-guard': 'original-capture'
                      for stage in ('early-child', 'returned-jordan-entry', 'denied-child', 'recovered-child')},
    activity_checks={stage + '-opened': ('original-capture', 'same')
                     for stage in ('early-resume', 'resume', 'recovered-resume')},
    assertions_after={'recovered-soft-submitted': 'visible-result'},
)


class IdleJourney(AppRestartActiveJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.original_deadline_ns = None
        self.recovery_started = None
        self.recovered_balance = None
        self.latest_balance = None
        self.early_sample = None

    def check_settings(self, stage, observed):
        # The active lifecycle owner supplies immutable forms and saved-policy
        # comparisons; this case owns its shorter original grant and idle clocks.
        if stage != 'original-countdown':
            super().check_settings(stage, observed)
        if stage == 'request-approval-success':
            require(self.original_deadline_ns is None, 'idle:approval-replay')
            self.original_deadline_ns = time.monotonic_ns() + (GRANT_SECONDS + 2) * 1_000_000_000
        if stage in ('prepared-policy', 'expired-policy', 'recovered-policy'):
            self.check_policy(stage, observed)
        if stage == 'recovery-jordan':
            from ui_observations import RequestObservation
            require(RequestObservation.from_request(observed['ui']['request'],
                operation=PLAN.screen_tags[stage][3:]) == self.forms['capture-jordan'],
                'idle:expired-remembered-choices')
        if stage == 'recovery-approval-open':
            require(self.recovery_started is None, 'idle:recovery-replay')
            self.recovery_started = time.monotonic_ns()
        if stage in ('original-countdown', 'early-idle', 'early-countdown',
                     'tour-countdown', 'expiry-wait', 'recovered-countdown'):
            value = CountdownObservation.from_value(observed['ui']['countdown'], present=True,
                                                    child='existing-fixture-child')
            low, high = countdown_seconds(value.text)
            require(low >= (300 if stage in ('original-countdown', 'early-idle') else
                            600 if stage == 'recovered-countdown' else 1), 'idle:positive-margin')
            bounds = tuple(self.ui.read_bounds)
            if stage == 'original-countdown':
                require(self.approval_started is not None and self.original_balance is None,
                        'idle:missing-approval')
                elapsed = (bounds[1] - self.approval_started) / 1e9
                require(GRANT_SECONDS - elapsed - 2 < value.seconds <= GRANT_SECONDS,
                        'idle:original-grant')
                self.latest_balance = {'one_time': {'seconds': value.seconds, 'precision_seconds': 1},
                                       'observed_monotonic_ns': value.observed_monotonic_ns}
                self.original_balance = (deepcopy(self.latest_balance), bounds)
                return
            balance = self.recovered_balance if stage == 'recovered-countdown' else self.latest_balance
            observed['comparison'] = check_countdown_balance(value,
                seconds=balance['one_time']['seconds'], precision_seconds=balance['one_time']['precision_seconds'],
                observed_monotonic_ns=balance['observed_monotonic_ns'], max_elapsed_seconds=300)
            if stage == 'early-idle':
                before, earlier = self.original_balance
                minimum, maximum = (bounds[0] - earlier[1]) / 1e9, (bounds[1] - earlier[0]) / 1e9
                require(0 < minimum <= maximum
                        and before['one_time']['seconds'] - maximum - 4 < value.seconds
                        < before['one_time']['seconds'] - minimum + 4,
                        'idle:original-positive-deadline')
                self.early_sample = (low, high, bounds)
            elif stage == 'early-countdown':
                before_low, before_high, earlier = self.early_sample
                elapsed_min = (bounds[0] - earlier[1]) / 1e9
                elapsed_max = (bounds[1] - earlier[0]) / 1e9
                # Minute displays can retain their label over the fifteen-second
                # interval; require elapsed reduction within display precision.
                require(elapsed_min >= 15 and low <= before_high - elapsed_min + 2
                        and high >= before_low - elapsed_max - 2, 'idle:early-time-not-elapsing')

    def check_policy(self, stage, observed):
        value = observed['ui']['revoke_cancel']
        require(value['settings'] == {'child': 'existing-fixture-child', 'limit_enabled': True,
                                     'allowance': ['0 minutes']}, 'idle:saved-settings')
        saved = {key: deepcopy(value[key]) for key in ('settings', 'apps', 'rules')}
        if self.policies:
            require(saved == self.policies['prepared-policy'], 'idle:saved-rules-changed')
        self.policies[stage] = saved
        balance, bounds = value['balances'], tuple(self.ui.read_bounds)
        grant, precision = balance['one_time']['seconds'], balance['one_time']['precision_seconds']
        require(balance['daily']['seconds'] == 0
                and abs(balance['total']['seconds'] - grant) <= balance['total']['precision_seconds'],
                'idle:grant-only-balance')
        if stage == 'prepared-policy':
            require(grant == 0 and balance['total']['seconds'] == 0, 'idle:unexpected-grant')
        elif stage == 'expired-policy':
            require(time.monotonic_ns() > self.original_deadline_ns and grant == 0
                    and balance['total']['seconds'] == 0, 'idle:original-deadline-not-expired')
        elif stage == 'recovered-policy':
            require(self.recovery_started is not None, 'idle:missing-recovery')
            elapsed = (time.monotonic_ns() - self.recovery_started) / 1e9
            require(0 < elapsed < 600 and RECOVERY_SECONDS - elapsed - precision - 2 < grant
                    <= RECOVERY_SECONDS, 'idle:replacement-grant')
            self.recovered_balance = deepcopy(balance)
        else:
            before, earlier = self.original_balance
            minimum, maximum = (bounds[0] - earlier[1]) / 1e9, (bounds[1] - earlier[0]) / 1e9
            tolerance = precision + before['one_time']['precision_seconds'] + 2
            require(grant > 0
                    and 0 < minimum <= maximum
                    and before['one_time']['seconds'] - maximum - tolerance < grant
                    < before['one_time']['seconds'] - minimum + tolerance, 'idle:original-positive-deadline')
        if stage not in ('expired-policy', 'recovered-policy'):
            self.latest_balance = deepcopy(balance)

    @staticmethod
    def idle_to_expiry(journey, guard):
        require(journey.original_deadline_ns is not None, 'idle:missing-deadline')
        while (remaining := (journey.original_deadline_ns - time.monotonic_ns()) / 1e9) > 0:
            interval_action(min(300, remaining))(journey, guard)


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-022/idle-active-expired'
    record_installed_journey(recorder, context, PLAN, timeout=3600, journey_type=IdleJourney,
        actions={**fixture_actions(include_refusal=False, profile='activity'),
                 'early-idle': interval_action(15), 'idle-to-expiry': IdleJourney.idle_to_expiry})


E2E_CASES = {'idle-active-expired': execute}
