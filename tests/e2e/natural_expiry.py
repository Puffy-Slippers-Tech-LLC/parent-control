"""TIME04: public daily-only preparation and actual use until natural lock."""

import json
import time

from countdown import CountdownSample, check_countdown_balance
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import (daily_time_profile, desktop_entry, fresh_desktop,
                            native_activity_entry, native_activity_resume, prefixed_stages)
from journey_checks import DailyTimeProfileJourney
from native_fixtures import fixture_actions
from natural_expiry_observation import (
    LOCK_VERIFICATION_SECONDS, RECOVERY_SECONDS,
    SAMPLE_INTERVAL_SECONDS, FOREGROUND_REVOCATION_RESPONSE_SECONDS,
    await_engineering_expiry, await_natural_expiry, engineering_deadline,
)
from private_artifacts import require
import session_control
from ui_observations import (AppActivityObservation, SettingsObservation, UiObservations,
                             compare_app_activity)


SCREENS = {
    **fresh_desktop('parent'),
    'wrong-account-refused': 'ui:child-natural-expiry-wrong-account-refused',
    **daily_time_profile(source='desktop', entry='same-user', window='new',
                         initial_enabled=False, minutes=4),
    **prefixed_stages('fresh', fresh_desktop('child')),
    **native_activity_entry('activity', child='child'),
    'natural-expiry': 'ui:child-countdown-present',
    'lock-input-ready': 'ui:child-natural-expiry-lock-ready',
    'lock-result': 'ui:child-natural-expiry-lock-result',
}
LOGIN_STAGES = set(fresh_desktop('parent')) | set(prefixed_stages('fresh', fresh_desktop('child')))
PLAN = JourneyPlan(
    prefix='natural-expiry', worker_mode='natural_expiry', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in SCREENS
               if stage.startswith(('fresh-', 'activity-', 'lock-')) or stage == 'natural-expiry'}},
    advance_after={'gdm-switched': 'step-2'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES
                      or stage in ('wrong-account-refused', 'natural-expiry', 'lock-input-ready', 'lock-result')),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
    },
    settings_checks={
        'same-parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
        'profile-settings': SettingsObservation('fixture-child', True, ('4 minutes',)),
    },
    balance_checks={'profile-configured': 240},
    stage_actions={'desktop': 'native-verify', 'natural-expiry': 'natural-expiry'},
    activity_entries={'natural-expiry': 'activity-capture'},
    assertions_after={'wrong-account-refused': 'wrong-account-refused',
                      'profile-configured': 'daily-only-time',
                      'fresh-desktop': 'usable-child-desktop',
                      'activity-capture': 'usable-native-activity',
                      'natural-expiry': 'natural-enforced-lock',
                      'lock-result': 'lock-owns-normal-input'},
)


class NaturalExpiryJourney(DailyTimeProfileJourney):
    """The fixed qualification owns its preparation and independent endpoints."""

    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        if actions is None:
            actions = {**fixture_actions(include_refusal=False),
                       'natural-expiry': self.natural_expiry}
        super().__init__(context, progress, plan, no_grant_checks=('profile-before',),
                         actions=actions)
        self.balance = None
        self.initial_countdown = None
        self.natural_expiry_result = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'profile-configured':
            value = observed['ui']['time_explanation']
            self.balance = (value['total']['seconds'], value['total']['precision_seconds'],
                            value['observed_monotonic_ns'])
        if stage == 'natural-expiry':
            require(self.balance is not None and self.initial_countdown is None,
                    'natural-expiry:missing-or-replayed-entry')
            current = CountdownSample.from_ui(observed['ui'], boot_sha256=observed['boot_sha256'])
            observed['comparison'] = check_countdown_balance(current.countdown,
                seconds=self.balance[0], precision_seconds=self.balance[1],
                observed_monotonic_ns=self.balance[2])
            self.initial_countdown = current

    @staticmethod
    def natural_expiry(journey, guard):
        require(journey.initial_countdown is not None and journey.natural_expiry_result is None
                and 'activity-capture' in journey.activity_observations,
                'natural-expiry:missing-or-replayed-entry')
        result = await_natural_expiry(journey, guard, journey.initial_countdown,
                                     journey.activity_observations['activity-capture'])
        journey.natural_expiry_result = result
        return result


# The installed system-282 owner supplies one live lease and its prepared
# activity fixture. This is its engineering history, not another E2E journey.
SYSTEM_SCREENS = {
    'return-greeter': 'system:child-return-greeter',
    **prefixed_stages('initial', desktop_entry('child', source='gdm', entry='retained')),
    **native_activity_entry('activity', child='child'),
    'natural-expiry': 'ui:child-natural-expiry-engineering-observe',
    'lock-input-ready': 'ui:child-natural-expiry-engineering-lock-ready',
    'lock-result': 'ui:child-natural-expiry-engineering-lock-result',
    'recovery-greeter': 'system:child-return-greeter',
    **prefixed_stages('recovered', desktop_entry('child', source='gdm', entry='retained')),
    **native_activity_resume('recovery-activity', child='child'),
    'recovery-work': 'ui:overlay-native-activity',
    'child-switch': 'system:child-switch-user',
    'child-greeter': 'ui:gdm-returned',
    **prefixed_stages('peer', desktop_entry('parent', source='gdm', entry='fresh')),
    **native_activity_entry('peer-activity', child='parent'),
    'peer-expiry': 'ui:parent-native-activity',
    'peer-work': 'ui:parent-native-activity',
    'child-locked': 'system:child-enter-locked-from-parent',
    'peer-lock-input-ready': 'ui:child-natural-expiry-engineering-lock-ready',
    'peer-lock-result': 'ui:child-natural-expiry-engineering-lock-result',
    'final-greeter': 'system:child-return-greeter',
    **prefixed_stages('final', desktop_entry('child', source='gdm', entry='retained')),
    **native_activity_resume('final-activity', child='child'),
    'final-work': 'ui:overlay-native-activity',
}
_SYSTEM_ENTRIES = {stage for prefix, account in (
    ('initial', 'child'), ('recovered', 'child'), ('peer', 'parent'), ('final', 'child'))
    for stage in prefixed_stages(prefix, fresh_desktop(account))}
_SYSTEM_INVOCATIONS = {'natural-expiry', 'lock-input-ready', 'lock-result',
    'recovery-work', 'child-greeter', 'peer-expiry', 'peer-work',
    'peer-lock-input-ready', 'peer-lock-result', 'final-work'}
SYSTEM_PLAN = JourneyPlan(
    prefix='system-graphical-expiry', worker_mode='system_graphical_expiry',
    screen_tags=SYSTEM_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SYSTEM_SCREENS}},
    invocations=tuple(stage for stage in SYSTEM_SCREENS
                      if stage in _SYSTEM_ENTRIES | _SYSTEM_INVOCATIONS),
    challenges={prefix: (account, prefix + '-' + role + 'qualified',
                        prefix + '-' + role + 'rechecked')
                for prefix, account, role in (
                    ('initial', 'child', 'child-recipient-'),
                    ('recovered', 'child', 'child-recipient-'),
                    ('peer', 'parent', 'recipient-'),
                    ('final', 'child', 'child-recipient-'))},
    stage_actions={'natural-expiry': 'natural-lock',
                   'lock-result': 'natural-recovery', 'peer-expiry': 'peer-expiry',
                   'child-locked': 'peer-lock-entry', 'peer-lock-result': 'peer-recovery'},
    activity_entries={'natural-expiry': 'activity-capture',
                      'recovered-entry-guard': 'activity-capture',
                      'final-entry-guard': 'activity-capture'},
    activity_checks={stage: (capture, 'same') for stage, capture in (
        ('recovery-activity-opened', 'activity-capture'), ('recovery-work', 'activity-capture'),
        ('peer-expiry', 'peer-activity-capture'),
        ('peer-work', 'peer-activity-capture'), ('final-activity-opened', 'activity-capture'),
        ('final-work', 'activity-capture'))},
)


def _system_history_command(transport, command):
    """The maintained installed guest leaf owns finite fixture transitions."""
    import system_runner
    started = time.monotonic()
    raw = transport.call(['env', 'ONPC_EXPECTED_RUN=' + transport.config['run'],
        'PYTHONDONTWRITEBYTECODE=1', '/usr/bin/python3', '-B',
        system_runner.PAYLOAD + '/system_graphical_expiry.py', command],
        timeout=120)
    require(type(raw) is bytes and 0 < len(raw) < 1024, 'expiry:history-response')
    value = json.loads(raw)
    if command in ('host-complete', 'revoke-complete'):
        require(value == {'completed': True}, 'expiry:history-incomplete')
        return value
    if command in ('revoke-zero', 'revoke-positive'):
        require(type(value) is dict and set(value) == {'revoked_monotonic_ns'}
                and type(value['revoked_monotonic_ns']) is int
                and value['revoked_monotonic_ns'] > 0, 'expiry:revoke-response')
        return value
    require(type(value) is dict and set(value) == {'remaining_seconds'}
            and type(value['remaining_seconds']) in (int, float)
            and 0 < value['remaining_seconds'] <= 1200, 'expiry:history-grant-response')
    # Conservative controller lower endpoint: grant read latency never adds
    # time to the original expiry or outage budget.
    return started + value['remaining_seconds']


class SystemGraphicalExpiryJourney(InstalledJourney):
    def __init__(self, context, progress, plan=SYSTEM_PLAN, *, actions=None, transport=None):
        if actions is None:
            # The installed owner has already verified its complete fixture
            # union and renewed its receipt after reboot. The narrower E2E
            # activity-only trust checker cannot describe that union.
            actions = {'natural-lock': self.natural_lock, 'natural-recovery': self.natural_recovery,
                       'peer-expiry': self.peer_expiry, 'peer-lock-entry': self.peer_lock_entry,
                       'peer-recovery': self.peer_recovery}
        super().__init__(context, progress, plan, actions=actions, transport=transport)
        self.original_session = None
        self.lock_deadline = None
        self.recovery_deadline = None
        self.peer_deadline = None
        self.peer_lock = None

    def check_settings(self, stage, observed):
        if stage in ('initial-entry-guard', 'recovered-entry-guard', 'final-entry-guard'):
            identity = observed['system']['session_sha256']
            self.original_session = self.original_session or identity
            require(identity == self.original_session, 'expiry:original-session-changed')
        if stage in ('lock-input-ready', 'lock-result'):
            require(time.monotonic() < self.lock_deadline, 'expiry:locked-input-deadline')
        if stage == 'peer-lock-input-ready':
            value = observed['ui']['natural_expiry']
            require(value['session_sha256'] == self.original_session,
                    'expiry:original-session-changed')
            self.peer_lock = value['lock']['surface_id']
        if stage == 'peer-lock-result':
            require(self.peer_lock is not None
                    and observed['ui']['natural_expiry']['lock']['surface_id'] == self.peer_lock,
                    'expiry:peer-lock-changed')
        if stage in ('peer-lock-input-ready', 'peer-lock-result', 'peer-work'):
            require(time.monotonic() < self.peer_deadline, 'expiry:peer-expiry-deadline')
        if stage in ('recovery-work', 'final-work'):
            require(time.monotonic() < self.recovery_deadline, 'expiry:recovery-deadline')

    @staticmethod
    def natural_lock(journey, guard):
        guard()
        expiry_at = _system_history_command(journey.transport, 'natural-grant')
        result = await_engineering_expiry(journey.ui, guard,
            journey.activity_observations['activity-capture'],
            expiry_at=expiry_at, boot_sha256=journey.boot)
        require(result['activity_actions'] > 0, 'expiry:no-original-app-input')
        # The observer above must establish protection by expiry + 15 seconds.
        # Subsequent guarded input/readback measures protection, not lock latency.
        journey.lock_deadline = engineering_deadline(
            result['observed_monotonic'], LOCK_VERIFICATION_SECONDS)
        return result

    @staticmethod
    def _recover(journey, guard, command):
        guard()
        triggered = time.monotonic()
        _system_history_command(journey.transport, command)
        journey.recovery_deadline = engineering_deadline(triggered, RECOVERY_SECONDS)
        guard()
        return {'declared_recovery_grant_seconds': 1200}

    @staticmethod
    def natural_recovery(journey, guard):
        return journey._recover(journey, guard, 'natural-recovery')

    @staticmethod
    def peer_recovery(journey, guard):
        return journey._recover(journey, guard, 'peer-recovery')

    @staticmethod
    def peer_lock_entry(journey, guard):
        guard()
        require(time.monotonic() < journey.peer_deadline, 'expiry:peer-expiry-deadline')
        # Start a fresh observer for this history, then let peer-lock-input-ready
        # make the single fresh public lock read and compare the original child.
        # Do not discover the same surface again before that input guard.
        journey.ui = UiObservations(journey.transport, progress=journey.watch_progress)
        journey.ui.boot_guard = journey.boot
        guard()
        return {'lock_observer_ready': True}

    @staticmethod
    def peer_expiry(journey, guard):
        guard()
        identity = session_control.observe(journey.transport, 'parent-entry-same')['session_sha256']
        previous = time.monotonic()
        expiry_at = _system_history_command(journey.transport, 'peer-grant')
        # This history verifies foreground peer continuity and protected child
        # input after expiry. The natural-lock history owns the strict timing
        # measurement; do not charge peer input/navigation to its 15-second bound.
        journey.peer_deadline = engineering_deadline(expiry_at, LOCK_VERIFICATION_SECONDS)
        while True:
            guard()
            require(time.monotonic() - previous <= LOCK_VERIFICATION_SECONDS,
                    'expiry:peer-missed-sample')
            require(session_control.observe(journey.transport, 'parent-entry-same')['session_sha256']
                    == identity, 'expiry:peer-session-changed')
            value = journey.ui.observe('parent-native-activity')
            completed = time.monotonic()
            require(journey.ui.boot_proof == journey.boot
                    and completed - previous <= LOCK_VERIFICATION_SECONDS
                    and completed < journey.peer_deadline, 'expiry:peer-missed-sample')
            compare_app_activity(AppActivityObservation.from_value(value['activity']),
                                 journey.activity_observations['peer-activity-capture'])
            guard()
            if completed >= expiry_at:
                # One deliberate supporting-app action after the child's
                # deadline; transport uncertainty never replays this input.
                journey.ui.observe('parent-native-resubmit')
                value = journey.ui.observe('parent-native-activity')
                compare_app_activity(AppActivityObservation.from_value(value['activity']),
                                     journey.activity_observations['peer-activity-capture'])
                require(journey.ui.boot_proof == journey.boot
                        and time.monotonic() - completed <= LOCK_VERIFICATION_SECONDS
                        and time.monotonic() < journey.peer_deadline,
                        'expiry:peer-missed-sample')
                guard()
                return {'same_foreground_graphical_session': True, 'original_peer_work': True,
                        'real_input_after_child_expiry': True, 'expiry_at': expiry_at}
            previous = completed
            time.sleep(SAMPLE_INTERVAL_SECONDS)


REVOKE_SCREENS = {
    'return-greeter': 'system:child-return-greeter',
    **prefixed_stages('initial', desktop_entry('child', source='gdm', entry='retained')),
    **native_activity_entry('activity', child='child'),
    'revoke-zero': 'ui:child-natural-expiry-observe',
    'lock-input-ready': 'ui:child-natural-expiry-engineering-lock-ready',
    'lock-result': 'ui:child-natural-expiry-engineering-lock-result',
    'recovery-greeter': 'system:child-return-greeter',
    **prefixed_stages('recovered', desktop_entry('child', source='gdm', entry='retained')),
    **native_activity_resume('recovery-activity', child='child'),
    'recovery-work': 'ui:overlay-native-activity',
    'revoke-positive': 'ui:child-natural-expiry-observe',
    **native_activity_resume('positive-activity', child='child'),
    'positive-work': 'ui:overlay-native-activity',
}
REVOKE_PLAN = JourneyPlan(
    prefix='system-foreground-revoke', worker_mode='system_foreground_revoke',
    screen_tags=REVOKE_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in REVOKE_SCREENS}},
    invocations=tuple(stage for stage in REVOKE_SCREENS if stage in _SYSTEM_ENTRIES
                      or stage in ('revoke-zero', 'lock-input-ready', 'lock-result',
                                   'recovery-work', 'revoke-positive', 'positive-work')),
    challenges={prefix: ('child', prefix + '-child-recipient-qualified',
                         prefix + '-child-recipient-rechecked')
                for prefix in ('initial', 'recovered')},
    stage_actions={'revoke-zero': 'revoke-zero', 'lock-result': 'positive-setup',
                   'recovery-work': 'reset-observer', 'revoke-positive': 'revoke-positive'},
    activity_entries={'revoke-zero': 'activity-capture',
                      'recovered-entry-guard': 'activity-capture'},
    activity_checks={stage: ('activity-capture', 'same') for stage in (
        'recovery-activity-opened', 'recovery-work', 'positive-activity-opened', 'positive-work')},
)


class ForegroundRevokeJourney(SystemGraphicalExpiryJourney):
    def __init__(self, context, progress, plan=REVOKE_PLAN, *, actions=None, transport=None):
        if actions is None:
            actions = {
            'revoke-zero': self.revoke_zero, 'positive-setup': self.positive_setup,
            'reset-observer': self.reset_observer, 'revoke-positive': self.revoke_positive}
        super().__init__(context, progress, plan, transport=transport, actions=actions)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in ('revoke-zero', 'revoke-positive'):
            value = observed['ui']['natural_expiry']
            require(value['state'] == 'desktop' and value['session_sha256'] == self.original_session
                    and 600 < value['seconds'] <= 1200, 'expiry:revoke-entry')
            compare_app_activity(AppActivityObservation.from_value(value['activity']),
                                 self.activity_observations['activity-capture'])

    @staticmethod
    def revoke_zero(journey, guard):
        guard()
        value = _system_history_command(journey.transport, 'revoke-zero')
        triggered = value['revoked_monotonic_ns']
        journey.ui.natural_expiry_deadline_ns = triggered + int(
            FOREGROUND_REVOCATION_RESPONSE_SECONDS * 1e9)
        result = journey.ui.observe('child-natural-expiry-wait-lock')['natural_expiry']
        guard()
        require(journey.ui.boot_proof == journey.boot
                and result['session_sha256'] == journey.original_session
                and result['lock_read_bounds'][0] >= triggered, 'expiry:revoke-lock-identity')
        journey.lock_deadline = engineering_deadline(time.monotonic(), LOCK_VERIFICATION_SECONDS)
        return {'revoked_monotonic_ns': triggered, 'lock': result}

    @staticmethod
    def positive_setup(journey, guard):
        return journey._recover(journey, guard, 'revoke-positive-setup')

    @staticmethod
    def reset_observer(journey, guard):
        guard()
        journey.ui = UiObservations(journey.transport, progress=journey.watch_progress)
        journey.ui.boot_guard = journey.boot
        return {'observer_reset_after_verified_recovery': True}

    @staticmethod
    def revoke_positive(journey, guard):
        guard()
        value = _system_history_command(journey.transport, 'revoke-positive')
        observe_until = time.monotonic() + FOREGROUND_REVOCATION_RESPONSE_SECONDS
        finish_by = engineering_deadline(time.monotonic(), LOCK_VERIFICATION_SECONDS)
        # Keep the child foreground throughout the same response window. Each
        # input uses fresh session/app proofs; a cached positive grant cannot
        # satisfy the independently observed daily-only countdown.
        while True:
            guard()
            result = journey.ui.observe('child-natural-expiry-activity')['natural_expiry']
            require(journey.ui.boot_proof == journey.boot and result['state'] == 'desktop'
                    and result['session_sha256'] == journey.original_session
                    and result['acted'] and 0 < result['seconds'] <= 1200
                    and time.monotonic() < finish_by,
                    'expiry:positive-revoke-input')
            compare_app_activity(AppActivityObservation.from_value(result['activity']),
                                 journey.activity_observations['activity-capture'])
            if time.monotonic() >= observe_until:
                require(result['seconds'] <= 900, 'expiry:positive-revoke-stale-grant')
                return {'daily_only_seconds': result['seconds'],
                        'usable_through_response_window': True}
            time.sleep(SAMPLE_INTERVAL_SECONDS)


def run_system_graphical_expiry(directory, lease, transport, ledger, *, expected_inputs,
                               progress, context, credentials=None, foreground_revoke=False):
    """Compose engineering input checks before the installed PAM password tests."""
    from desktop_session import run_attached
    _system_history_command(transport, 'revoke-ready' if foreground_revoke else 'host-ready')
    result = run_attached(directory, lease, transport, ledger,
        REVOKE_PLAN if foreground_revoke else SYSTEM_PLAN,
        expected_inputs=expected_inputs, progress=progress, context=context,
        credentials=credentials, journey_type=(ForegroundRevokeJourney if foreground_revoke
                                              else SystemGraphicalExpiryJourney), timeout=1800)
    _system_history_command(transport, 'revoke-complete' if foreground_revoke else 'host-complete')
    return result
