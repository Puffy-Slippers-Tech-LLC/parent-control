"""Expired-grant persistence across app reopening, sign-out and reboot."""
from copy import deepcopy
from dataclasses import replace
import time

from accessible_ui import MATCH_APPS, MATCH_RULES, countdown_seconds
from countdown import CountdownObservation, check_countdown_balance
from grant_only_profile import GrantOnlyProfileJourney
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, desktop_return, fresh_desktop, grant_only_time_profile,
                            native_activity_entry, native_activity_resume, native_usable_app,
                            overlay_entry, parent_reopen, parent_selection, prefixed_stages,
                            rejected_gdm_return, station_entry)
from kiosk_approved_flow import obtain_time
from named_app_set import APPS, named_app_set
from native_fixtures import fixture_actions
from policy_edits import AppPolicyJourney
from private_artifacts import require
from real_interval import interval_toward


GRANT_SECONDS = 600
RECOVERY_SECONDS = 1200
LOGINS = {}


def enter(prefix, role, entry, expected='success'):
    LOGINS[prefix] = (role, expected)
    return prefixed_stages(prefix, desktop_entry(role, source='gdm', entry=entry,
                                                expected=expected))


SETUP = {
    **named_app_set(source='gdm', entry='fresh', window='new', child='child',
                    apps=APPS, prefix='rules'),
    **enter('setup-return', 'parent', 'retained'),
    **grant_only_time_profile(source='desktop', entry='same-user', window='retained',
        initial_enabled=False, revoke_first=False, duration_seconds=GRANT_SECONDS,
        request_initial='default', balance_readback=False),
    **enter('original-entry', 'child', 'fresh'),
    'original-countdown': 'ui:child-countdown-present',
    **native_activity_entry('original', child='child'),
}
BOUNDARY = {
    **overlay_entry('first-overlay', 'command', form_operation='overlay-grant-form'),
    'first-overlay-cancel': 'ui:overlay-qualification-cancel',
    'first-overlay-returned': 'ui:overlay-desktop',
    **overlay_entry('reopened-overlay', 'command', form_operation='overlay-grant-form'),
    'reopened-overlay-cancel': 'ui:overlay-qualification-cancel',
    'reopened-overlay-returned': 'ui:overlay-desktop',
    **desktop_return('original-leave', account='child'),
    **enter('before-parent', 'parent', 'retained'),
    'before-policy': 'ui:revoke-saved-balances',
    **prefixed_stages('reopen', parent_reopen()),
    **prefixed_stages('returned-child', parent_selection(screen_limits=True)),
    'returned-policy': 'ui:revoke-saved-balances',
    **desktop_return('returned-parent-leave', account='parent'),
    # The initial real approval closed this form. Reopen and close it normally;
    # recovery later reopens it again with explicitly selected replacement data.
    **prefixed_stages('reopened-station', station_entry()),
    'reopened-station-cancel': 'ui:kiosk-request-cancel',
    'reopened-station-returned': 'ui:gdm-station-returned',
}
EXPIRY = {
    'expiry-wait-first': 'ui:gdm-returned',
    'expiry-wait-last': 'ui:gdm-returned',
}
RECOVERY = {
    **enter('expired-parent', 'parent', 'retained'),
    'expired-policy': 'ui:revoke-saved-balances',
    **desktop_return('expired-parent-leave', account='parent'),
    **enter('denied-child', 'child', 'retained', 'time-denied'),
    **rejected_gdm_return(),
    **obtain_time(initial='observed', child='fixture-child', approver='fixture-parent',
                  duration_seconds=RECOVERY_SECONDS, allow_soft=False, exit='automatic'),
    **enter('recovered-parent', 'parent', 'retained'),
    'recovered-policy': 'ui:revoke-saved-balances',
    **desktop_return('recovered-parent-leave', account='parent'),
    **enter('recovered-child', 'child', 'retained'),
    'recovered-countdown': 'ui:child-countdown-present',
    **native_activity_resume('resume', child='child'),
    'hard-denied': 'ui:overlay-native-hard-command-blocked',
    'soft-denied': 'ui:overlay-native-soft-command-blocked',
    'retained-work': 'ui:overlay-native-activity',
    # Prove the original work survived recovery before normally closing it.
    # The new Allowed launch uses the same primary fixture window identity.
    'original-close': 'ui:overlay-native-close',
    'original-closed': 'ui:overlay-native-closed',
    **prefixed_stages('allowed', native_usable_app('command', child='child', role='A')),
}
SCREENS = {**SETUP, **BOUNDARY, **EXPIRY, **RECOVERY}
LOGIN_STAGES = {prefix + '-' + stage for prefix, (role, expected) in LOGINS.items()
                for stage in fresh_desktop(role, expected)}
PLAN = JourneyPlan(
    prefix='app-restart-expired', worker_mode='app_restart_expired', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: phase for phase, screens in (
            ('step-1', SETUP), ('step-2', BOUNDARY), ('step-3', EXPIRY),
            ('step-4', RECOVERY)) for stage in screens}, 'installed-greeter': 'start'},
    advance_after={'original-capture': 'step-2', 'reopened-station-returned': 'step-3',
                   'expiry-wait-last': 'step-4'},
    stage_actions={'desktop': 'native-verify', 'expiry-wait-first': 'real-interval',
                   'expiry-wait-last': 'real-interval'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES
                      or stage in rejected_gdm_return()
                      or stage in ('first-overlay-launch', 'first-overlay-form',
                                   'reopened-overlay-launch', 'reopened-overlay-form')),
    challenges={prefix: (role, prefix + '-' + ('child-' if role == 'child' else '')
                        + 'recipient-qualified',
                        prefix + '-' + ('child-' if role == 'child' else '')
                        + 'recipient-rechecked') for prefix, (role, _expected) in LOGINS.items()},
    kiosk_request=('child', 'parent', RECOVERY_SECONDS, False),
    match_checks={f'rules-saved-{role.lower()}-match': (MATCH_APPS[role], rule)
                  for role, rule in (('A', MATCH_RULES[0]), ('H', MATCH_RULES[3]),
                                     ('S', MATCH_RULES[4]))},
    access_checks={f'rules-saved-{role.lower()}-access': (MATCH_APPS[role], access)
                   for role, access in (('A', 'allowed'), ('H', 'permanent'), ('S', 'conditional'))},
    activity_entries={'denied-child-entry-guard': 'original-capture',
                      'recovered-child-entry-guard': 'original-capture'},
    activity_checks={'resume-opened': ('original-capture', 'same'),
                     'retained-work': ('original-capture', 'same')},
    assertions_after={'allowed-submitted': 'visible-result'},
)


# Sign-out ends the original activity. Keep the same real grant, saved-policy
# comparisons and recovery, then prove access with new windows in a fresh session.
SIGN_OUT_BOUNDARY = {
    **desktop_return('original-leave', account='child'),
    **enter('before-parent', 'parent', 'retained'),
    'before-policy': 'ui:revoke-saved-balances',
    **desktop_return('boundary-parent-leave', account='parent'),
    **enter('boundary-child-entry', 'child', 'retained'),
    **desktop_return('boundary-child', account='child', action='logout'),
    **enter('returned-parent', 'parent', 'retained'),
    'returned-policy': 'ui:revoke-saved-balances',
    **desktop_return('returned-parent-leave', account='parent'),
}
SIGN_OUT_RECOVERY = {
    stage: (tag.removesuffix('retained') + 'fresh'
            if stage in ('denied-child-entry-guard', 'recovered-child-entry-guard') else tag)
    for stage, tag in RECOVERY.items()
    if not stage.startswith('resume-') and stage not in (
        'retained-work', 'original-close', 'original-closed')
}
SIGN_OUT_SCREENS = {**SETUP, **SIGN_OUT_BOUNDARY, **EXPIRY, **SIGN_OUT_RECOVERY}
SIGN_OUT_PLAN = replace(PLAN, prefix='sign-out-in-expired', worker_mode='sign_out_in_expired',
    screen_tags=SIGN_OUT_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: phase for phase, screens in (
            ('step-1', SETUP), ('step-2', SIGN_OUT_BOUNDARY), ('step-3', EXPIRY),
            ('step-4', SIGN_OUT_RECOVERY)) for stage in screens}, 'installed-greeter': 'start'},
    advance_after={'original-capture': 'step-2', 'returned-parent-leave-gdm-switched': 'step-3',
                   'expiry-wait-last': 'step-4'},
    invocations=tuple(stage for stage in SIGN_OUT_SCREENS if stage in {
        prefix + '-' + leaf for prefix, (role, expected) in LOGINS.items()
        for leaf in fresh_desktop(role, expected)} or stage in rejected_gdm_return()),
    challenges={prefix: (role, prefix + '-' + ('child-' if role == 'child' else '')
                        + 'recipient-qualified',
                        prefix + '-' + ('child-' if role == 'child' else '')
                        + 'recipient-rechecked') for prefix, (role, _expected) in LOGINS.items()},
    activity_entries={}, activity_checks={},
)


REBOOT_BOUNDARY = {
    **desktop_return('original-leave', account='child'),
    **enter('before-parent', 'parent', 'retained'),
    'before-policy': 'ui:revoke-saved-balances',
    'reboot-requested': 'system:parent-desktop-identity',
    'reboot-greeter': 'ui:gdm-list',
    **enter('returned-parent', 'parent', 'fresh'),
    'returned-parent-launch-desktop': 'ui:desktop',
    'returned-parent-launch-parent-command': 'ui:parent-command-launch',
    'returned-parent-launch-parent-window': 'ui:parent-window',
    **prefixed_stages('returned-child', parent_selection(screen_limits=True)),
    'returned-policy': 'ui:revoke-saved-balances',
    **desktop_return('returned-parent-leave', account='parent'),
}
REBOOT_SCREENS = {**SETUP, **REBOOT_BOUNDARY, **EXPIRY, **SIGN_OUT_RECOVERY}
REBOOT_PLAN = replace(SIGN_OUT_PLAN, prefix='reboot-expired', worker_mode='reboot_expired',
    screen_tags=REBOOT_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: phase for phase, screens in (
            ('step-1', SETUP), ('step-2', REBOOT_BOUNDARY), ('step-3', EXPIRY),
            ('step-4', SIGN_OUT_RECOVERY)) for stage in screens}, 'installed-greeter': 'start'},
    invocations=tuple(stage for stage in SIGN_OUT_PLAN.invocations if stage in REBOOT_SCREENS),
    challenges={prefix: binding for prefix, binding in SIGN_OUT_PLAN.challenges.items()
                if prefix + '-entry-guard' in REBOOT_SCREENS},
    reboot_transition=('reboot-requested', 'reboot-greeter'),
)


class AppRestartExpiredJourney(GrantOnlyProfileJourney, AppPolicyJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, grant_seconds=GRANT_SECONDS,
            actions=actions if actions is not None else {
                **fixture_actions(include_refusal=False, profile='activity'),
                'real-interval': self.remaining_interval})
        self.original_deadline_ns = None
        self.original_balance = None
        self.saved_policy = None
        self.recovery_started = None
        self.recovered_balance = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'profile-request-approval-success':
            require(self.original_deadline_ns is None, 'app-restart-expired:approval-replay')
            # Public authentication brackets issuance; this conservative upper
            # endpoint remains fixed through reopening, waiting and denial.
            self.original_deadline_ns = time.monotonic_ns() + (GRANT_SECONDS + 2) * 1_000_000_000
        if stage == 'original-countdown':
            value = CountdownObservation.from_value(observed['ui']['countdown'], present=True)
            require(countdown_seconds(value.text)[0] >= 300,
                    'app-restart-expired:insufficient-setup-margin')
        if stage in ('before-policy', 'returned-policy', 'expired-policy', 'recovered-policy'):
            self.check_policy(stage, observed)
        if stage == 'expiry-wait-last':
            # check_settings precedes the stage action; the subsequent expired
            # Parent read independently verifies the completed wait and zero time.
            require(self.original_deadline_ns is not None, 'app-restart-expired:missing-deadline')
        if stage == 'approval-open':
            require(self.recovery_started is None, 'app-restart-expired:recovery-replay')
            self.recovery_started = time.monotonic_ns()
        if stage == 'new-estimate':
            value = observed['ui']['valid_choice']
            require(value['request']['child'] == 'fixture-child'
                    and value['request']['approver'] == 'fixture-parent'
                    and value['request']['duration_seconds'] == RECOVERY_SECONDS
                    and value['request']['allow_soft'] is False
                    and value['estimate']['kind'] == 'fixed'
                    and value['estimate']['seconds'] == RECOVERY_SECONDS,
                    'app-restart-expired:replacement-choices')
        if stage == 'recovered-countdown':
            value = CountdownObservation.from_value(observed['ui']['countdown'], present=True)
            require(self.recovered_balance is not None and countdown_seconds(value.text)[0] >= 600,
                    'app-restart-expired:recovery-margin')
            balance = self.recovered_balance
            observed['comparison'] = check_countdown_balance(value,
                seconds=balance['one_time']['seconds'],
                precision_seconds=balance['one_time']['precision_seconds'],
                observed_monotonic_ns=balance['observed_monotonic_ns'], max_elapsed_seconds=300)

    def check_policy(self, stage, observed):
        value = observed['ui']['revoke_cancel']
        require(value['settings'] == {'child': 'fixture-child', 'limit_enabled': True,
                                     'allowance': ['0 minutes']},
                'app-restart-expired:saved-settings')
        saved = {key: deepcopy(value[key]) for key in ('settings', 'apps', 'rules')}
        if self.saved_policy is None:
            require(stage == 'before-policy', 'app-restart-expired:missing-policy')
            self.saved_policy = saved
        else:
            require(saved == self.saved_policy, 'app-restart-expired:saved-policy-changed')
        balance = value['balances']
        grant = balance['one_time']['seconds']
        precision = balance['one_time']['precision_seconds']
        require(balance['daily']['seconds'] == 0
                and abs(balance['total']['seconds'] - grant) <= balance['total']['precision_seconds'],
                'app-restart-expired:grant-only-balance')
        if stage == 'expired-policy':
            require(self.original_deadline_ns is not None
                    and time.monotonic_ns() > self.original_deadline_ns and grant == 0
                    and balance['total']['seconds'] == 0,
                    'app-restart-expired:original-deadline-not-expired')
            observed['comparison'] = {'original_deadline_elapsed': True, 'saved_policy_unchanged': True}
        elif stage == 'recovered-policy':
            require(self.recovery_started is not None, 'app-restart-expired:missing-replacement')
            elapsed = (time.monotonic_ns() - self.recovery_started) / 1e9
            require(0 < elapsed < 600 and RECOVERY_SECONDS - elapsed - precision - 2 < grant
                    <= RECOVERY_SECONDS, 'app-restart-expired:replacement-grant')
            self.recovered_balance = deepcopy(balance)
        elif stage == 'before-policy':
            require(self.approval_started is not None and grant >= 180,
                    'app-restart-expired:original-grant-margin')
            elapsed = (time.monotonic_ns() - self.approval_started) / 1e9
            require(GRANT_SECONDS - elapsed - precision - 2 < grant <= GRANT_SECONDS,
                    'app-restart-expired:original-grant')
            self.original_balance = (deepcopy(balance), tuple(self.ui.read_bounds))
        else:
            before, earlier = self.original_balance
            bounds = self.ui.read_bounds
            minimum, maximum = (bounds[0] - earlier[1]) / 1e9, (bounds[1] - earlier[0]) / 1e9
            tolerance = precision + before['one_time']['precision_seconds'] + 2
            require(grant > 0 and 0 < minimum <= maximum
                    and before['one_time']['seconds'] - maximum - tolerance < grant
                    < before['one_time']['seconds'] - minimum + tolerance,
                    'app-restart-expired:deadline-changed-on-reopen')
            observed['comparison'] = {'original_positive_deadline': True, 'saved_policy_unchanged': True}

    @staticmethod
    def remaining_interval(journey, guard):
        require(journey.original_deadline_ns is not None, 'app-restart-expired:missing-deadline')
        return interval_toward(journey, guard, journey.original_deadline_ns)


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-022/app-restart-expired'
    record_installed_journey(recorder, context, PLAN, timeout=3000,
                             journey_type=AppRestartExpiredJourney)


def execute_sign_out(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-022/sign-out-in-expired'
    record_installed_journey(recorder, context, SIGN_OUT_PLAN, timeout=3000,
                             journey_type=AppRestartExpiredJourney)


def execute_reboot(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-022/reboot-expired'
    record_installed_journey(recorder, context, REBOOT_PLAN, timeout=3000,
                             journey_type=AppRestartExpiredJourney)


E2E_CASES = {'app-restart-expired': execute, 'sign-out-in-expired': execute_sign_out,
             'reboot-expired': execute_reboot}
