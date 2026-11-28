"""Case 267: conserve a running grant and redeem it into the retained desktop."""

from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from countdown import CountdownSample
from grant_only_profile import GrantOnlyProfileJourney
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, fresh_desktop, grant_only_time_profile,
                            native_activity_entry, native_activity_resume, native_usable_app,
                            prefixed_stages, station_entry)
from named_app_set import named_app_set
from native_fixtures import fixture_actions
from natural_expiry_observation import await_natural_expiry
from policy_edits import AppPolicyJourney
from private_artifacts import require
from real_interval import interval_action


INITIAL_SECONDS = 180
DEFERRED_SECONDS = 60
SECONDS_MARGIN = 2
TRANSFER_LEAD_SECONDS = 5
APPS = ((MATCH_APPS['A'], 'match-precise', 'allowed'),
        (MATCH_APPS['S'], 'match-soft-wildcard', 'conditional'))


def approved_time(prefix):
    return {**prefixed_stages(prefix, station_entry()),
            f'{prefix}-child': 'ui:kiosk-request-child',
            f'{prefix}-tab': 'ui:kiosk-saved-tab-approved',
            f'{prefix}-read': 'ui:kiosk-saved-read'}


def time_restriction(prefix):
    return {**prefixed_stages(prefix, desktop_entry('child', source='locked', entry='lock',
                                                  expected='time-denied')),
            f'{prefix}-return-greeter': 'system:child-return-greeter',
            f'{prefix}-returned': 'ui:gdm-returned'}


RUNNING = {
    **named_app_set(source='gdm', entry='fresh', window='new', child='child',
                    apps=APPS, prefix='rules'),
    **prefixed_stages('setup-return', desktop_entry('parent', source='gdm', entry='retained')),
    **grant_only_time_profile(source='desktop', entry='same-user', window='retained',
        initial_enabled=False, revoke_first=False, duration_seconds=INITIAL_SECONDS,
        request_initial='default', balance_readback=False),
    **prefixed_stages('fresh', desktop_entry('child', source='gdm', entry='fresh')),
    **native_activity_entry('activity', child='child'),
    **prefixed_stages('soft', native_usable_app('command', child='child', role='S')),
    'soft-capture': 'ui:overlay-native-policy-soft-activity',
    'child-switch-ready': 'ui:fresh-child-desktop',
    'child-switch': 'system:child-switch-user',
    'child-greeter': 'ui:gdm-returned',
    'retained-before': 'system:child-retained-locked',
    **prefixed_stages('running', station_entry()),
    'running-child': 'ui:kiosk-request-child',
    'approved-tab': 'ui:kiosk-saved-tab-approved',
    'running-read': 'ui:kiosk-saved-read',
    'running-reread': 'ui:kiosk-saved-read',
}
SAVE = {
    'request-tab': 'ui:kiosk-saved-tab-request',
    'new-choices': 'ui:kiosk-request-select',
    'new-estimate': 'ui:kiosk-request-estimate',
    **{f'approval-{stage}': f'ui:kiosk-saved-mate-{operation}' for stage, operation in (
        ('open', 'open'), ('qualified', 'qualified'), ('rechecked', 'rechecked'),
        ('success', 'submit-success'))},
    'saved-read': 'ui:kiosk-saved-read',
    'saved-cancel': 'ui:kiosk-request-cancel',
    'saved-returned': 'ui:gdm-station-returned',
    'saved-retained-locked': 'system:child-retained-locked',
    'enter-locked': 'system:child-enter-locked',
    **time_restriction('denial'),
    'retained-after-save': 'system:child-retained-locked',
    **approved_time('reuse'),
}
REDEEM = {
    'use-saved': 'ui:kiosk-saved-use',
    'use-returned': 'ui:gdm-station-returned',
    **prefixed_stages('retained', desktop_entry('child', source='gdm', entry='retained')),
    'countdown': 'ui:child-countdown-present',
    'recovery-identity': 'system:child-entry-same',
    **native_activity_resume('resume-soft', child='child', binding='policy-soft'),
    'soft-retained': 'ui:overlay-native-policy-soft-activity',
}
EXPIRE = {
    'natural-expiry': 'ui:child-countdown-present',
    'lock-input-ready': 'ui:child-natural-expiry-lock-ready',
    'lock-result': 'ui:child-natural-expiry-lock-result',
    **time_restriction('expired'),
    'retained-after-expiry': 'system:child-retained-locked',
    **approved_time('after'),
    'after-cancel': 'ui:kiosk-request-cancel',
    'after-returned': 'ui:gdm-station-returned',
}
SCREENS = {**RUNNING, **SAVE, **REDEEM, **EXPIRE}
LOGINS = {'setup-return': 'parent', 'fresh': 'child', 'retained': 'child'}
LOGIN_STAGES = {f'{prefix}-{stage}' for prefix, account in LOGINS.items()
                for stage in fresh_desktop(account)}
PLAN = JourneyPlan(
    prefix='saved-time-retained-unlock', worker_mode='saved_time_retained_unlock',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: f'step-{index}' for index, screens in enumerate(
                (RUNNING, SAVE, REDEEM, EXPIRE), 1) for stage in screens},
            'installed-greeter': 'start'},
    advance_after={'running-reread': 'step-2', 'reuse-read': 'step-3',
                   'soft-retained': 'step-4'},
    stage_actions={'desktop': 'native-verify', 'running-read': 'real-interval',
                   'natural-expiry': 'natural-expiry'},
    child_bindings={stage: 'child' for stage, tag in SCREENS.items()
                    if tag.removeprefix('ui:') in NAMED_CHILD_OPERATIONS},
    match_checks={'rules-saved-a-match': (MATCH_APPS['A'], MATCH_RULES[0]),
                  'rules-saved-s-match': (MATCH_APPS['S'], MATCH_RULES[4])},
    access_checks={'rules-saved-a-access': (MATCH_APPS['A'], 'allowed'),
                   'rules-saved-s-access': (MATCH_APPS['S'], 'conditional')},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES
                      or stage in ('natural-expiry', 'lock-input-ready', 'lock-result')),
    challenges={prefix: (account, f'{prefix}-' + ('child-' if account == 'child' else '')
                         + 'recipient-qualified',
                         f'{prefix}-' + ('child-' if account == 'child' else '')
                         + 'recipient-rechecked') for prefix, account in LOGINS.items()},
    activity_entries={'retained-entry-guard': 'soft-capture', 'natural-expiry': 'activity-capture'},
    activity_checks={'resume-soft-opened': ('soft-capture', 'same'),
                     'soft-retained': ('soft-capture', 'same')},
    kiosk_request=('child', 'parent', DEFERRED_SECONDS, True),
    assertions_after={'running-reread': 'running-time-elapses', 'reuse-read': 'time-saved-and-stable',
                      'soft-retained': 'saved-time-restores-access',
                      'after-read': 'restriction-returns-without-saved-copy'},
)


def elapsed_interval(before, after):
    """Bracket elapsed time between events observed within two controller reads."""
    low = (after[0] - before[1]) / 1e9
    high = (after[1] - before[0]) / 1e9
    require(0 < low <= high <= INITIAL_SECONDS, 'saved-time:read-interval')
    return low, high


def elapsed_result(low, high):
    return [round(low, 3), round(high, 3)]


class SavedTimeRetainedUnlockJourney(GrantOnlyProfileJourney, AppPolicyJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, grant_seconds=INITIAL_SECONDS, actions={
            **fixture_actions(include_refusal=False, profile='activity'),
            'real-interval': interval_action(2),
            'natural-expiry': self.natural_expiry,
        } if actions is None else actions)
        self.running = None
        self.transfer = None
        self.saved = None
        self.redemption = None
        self.retained_session = None
        self.expiry_sample = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'retained-before':
            self.retained_session = observed['system']['session_sha256']
        if stage in ('saved-retained-locked', 'denial-entry-guard', 'retained-after-save',
                     'retained-entry-guard', 'recovery-identity', 'expired-entry-guard',
                     'retained-after-expiry'):
            require(self.retained_session is not None
                    and observed['system']['session_sha256'] == self.retained_session,
                    'saved-time:retained-session-replaced')

        value = observed.get('ui', {}).get('saved_time')
        if stage in ('running-read', 'running-reread', 'saved-read', 'reuse-read', 'after-read'):
            require(value['child'] == 'fixture-child' and value['daily_seconds'] == 0,
                    'saved-time:wrong-child-or-daily-balance')
        if stage in ('running-read', 'running-reread'):
            seconds = value['running_seconds']
            require(value['state'] == 'ready' and type(seconds) is int and 45 <= seconds <= INITIAL_SECONDS
                    and value['saved_seconds'] == 0 and value['actions']['pause']
                    and not value['actions']['use_saved'], 'saved-time:initial-running-grant')
            if stage == 'running-reread':
                before, bounds = self.running
                low, high = elapsed_interval(bounds, self.ui.read_bounds)
                decrease = before - seconds
                require(0 < decrease and low - SECONDS_MARGIN <= decrease <= high + SECONDS_MARGIN,
                        'saved-time:running-decrease')
                observed['comparison'] = {'decrease_seconds': decrease,
                                          'elapsed_interval_seconds': elapsed_result(low, high)}
            self.running = (seconds, self.ui.read_bounds)
        elif stage == 'profile-request-new-estimate':
            initial = observed['ui']['valid_choice']
            require(initial['request']['child'] == 'fixture-child'
                    and initial['request']['approver'] == 'fixture-parent'
                    and initial['request']['duration_seconds'] == INITIAL_SECONDS
                    and initial['request']['allow_soft'] is True
                    and initial['estimate']['kind'] == 'fixed'
                    and initial['estimate']['seconds'] == INITIAL_SECONDS,
                    'saved-time:initial-request')
        elif stage == 'new-estimate':
            choice = observed['ui']['valid_choice']['request']
            require(choice['child'] == 'fixture-child' and choice['approver'] == 'fixture-parent'
                    and choice['duration_seconds'] == DEFERRED_SECONDS and choice['custom_text'] == '1'
                    and choice['allow_soft'] is True, 'saved-time:deferred-request')
        elif stage == 'approval-success':
            self.transfer = self.ui.read_bounds
        elif stage in ('saved-read', 'reuse-read'):
            saved = value['saved_seconds']
            require(value['state'] == 'ready' and type(saved) is int
                    and DEFERRED_SECONDS < saved <= INITIAL_SECONDS + DEFERRED_SECONDS
                    and value['running_seconds'] == 0 and value['actions']['use_saved']
                    and not value['actions']['pause'], 'saved-time:saved-without-running-time')
            if stage == 'saved-read':
                before, bounds = self.running
                low, high = elapsed_interval(bounds, self.transfer)
                # The kiosk schedules the end of the running grant five seconds
                # after capture during approval. Account for that interval even
                # if the success screen appears before the scheduled end.
                low += TRANSFER_LEAD_SECONDS
                high += TRANSFER_LEAD_SECONDS
                transferred = saved - DEFERRED_SECONDS
                require(before - high - SECONDS_MARGIN <= transferred <= before - low + SECONDS_MARGIN,
                        'saved-time:transfer-conservation')
                self.saved = saved
                observed['comparison'] = {'transferred_seconds': transferred,
                                          'elapsed_interval_seconds': elapsed_result(low, high)}
            else:
                require(saved == self.saved, 'saved-time:changed-across-kiosk-visits')
        elif stage == 'use-saved':
            require(value['saved_seconds'] == self.saved, 'saved-time:wrong-redemption-balance')
            self.redemption = self.ui.read_bounds
        elif stage in ('countdown', 'natural-expiry'):
            current = CountdownSample.from_ui(observed['ui'], boot_sha256=observed['boot_sha256'])
            low, high = elapsed_interval(self.redemption, current.read_bounds)
            seconds = current.countdown.seconds
            deduction = self.saved - seconds
            require(0 < seconds and 0 < deduction
                    and low - SECONDS_MARGIN <= deduction <= high + SECONDS_MARGIN,
                    'saved-time:redemption-countdown')
            observed['comparison'] = {'deducted_seconds': deduction,
                                      'elapsed_interval_seconds': elapsed_result(low, high)}
            if stage == 'natural-expiry':
                self.expiry_sample = current
        elif stage == 'after-read':
            require(value['state'] == 'empty' and value['running_seconds'] == 0
                    and value['saved_seconds'] == 0 and not value['actions']['use_saved'],
                    'saved-time:spent-balance-reappeared')

    @staticmethod
    def natural_expiry(journey, guard):
        return await_natural_expiry(journey, guard, journey.expiry_sample,
                                    journey.activity_observations['activity-capture'])


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-066/saved-time-retained-unlock'
    record_installed_journey(recorder, context, PLAN, journey_type=SavedTimeRetainedUnlockJourney)


E2E_CASES = {'saved-time-retained-unlock': execute}
