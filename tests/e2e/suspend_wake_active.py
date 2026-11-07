"""A child wakes with the original approved time, work and household choices."""
from copy import deepcopy
from dataclasses import replace
import time

from accessible_ui import countdown_seconds
from app_restart_active import AppRestartActiveJourney, PLAN as ACTIVE, SETUP, RETURN
from countdown import CountdownObservation, check_countdown_balance
from installed_journey import record_installed_journey
from journey_blocks import desktop_entry, desktop_return, fresh_desktop, native_activity_resume, prefixed_stages
from native_fixtures import fixture_actions
from private_artifacts import require


BOUNDARY = {
    **desktop_return('boundary-parent-leave', account='parent'),
    **prefixed_stages('boundary-child', desktop_entry('other-child', source='gdm', entry='retained')),
    'boundary-countdown': 'ui:child-countdown-present',
    'suspend': 'system:standard-entry-same',
    'wake-session': 'system:standard-entry-lock',
    # Return from the already locked desktop without another Lock or an
    # unqualified Jordan lock-screen password route. GDM authenticates the
    # same retained desktop through the shared, qualified entry operation.
    'wake-return': 'system:standard-return-greeter',
    'wake-greeter': 'ui:gdm-returned',
    **prefixed_stages('wake-child', desktop_entry('other-child', source='gdm', entry='retained')),
    'returned-session': 'system:standard-entry-same',
    'wake-countdown': 'ui:child-countdown-present',
    **{stage: 'ui:native-policy-activity' if stage == 'wake-resume-opened' else tag
       for stage, tag in native_activity_resume('wake-resume', child='other-child').items()},
    **desktop_return('wake-leave', account='other-child'),
    **prefixed_stages('boundary-parent', desktop_entry('parent', source='gdm', entry='retained')),
}
SCREENS = {**SETUP, **BOUNDARY, **RETURN}
LOGINS = {prefix: binding[0] for prefix, binding in ACTIVE.challenges.items()}
LOGINS.update({'boundary-child': 'other-child', 'wake-child': 'other-child', 'boundary-parent': 'parent'})
LOGIN_STAGES = {prefix + '-' + stage for prefix, role in LOGINS.items() for stage in fresh_desktop(role)}
PLAN = replace(ACTIVE, prefix='suspend-wake-active', worker_mode='suspend_wake_active',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SETUP}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in BOUNDARY},
            **{stage: 'step-3' if index <= list(RETURN).index('returned-policy') else 'step-4'
               for index, stage in enumerate(RETURN)}},
    advance_after={'before-policy': 'step-2', 'boundary-parent-desktop': 'step-3',
                   'returned-policy': 'step-4'},
    stage_actions={'desktop': 'native-verify', 'suspend': 'suspend-wake'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={prefix: (role, prefix + '-' + ('recipient-qualified' if role == 'parent'
                    else 'child-recipient-qualified' if role == 'child' else 'standard-recipient-qualified'),
                    prefix + '-' + ('recipient-rechecked' if role == 'parent'
                    else 'child-recipient-rechecked' if role == 'child' else 'standard-recipient-rechecked'))
                for prefix, role in LOGINS.items()},
    activity_entries={**ACTIVE.activity_entries,
                      **{prefix + '-entry-guard': 'original-capture'
                         for prefix in ('boundary-child', 'wake-child')}},
    activity_checks={**ACTIVE.activity_checks, 'wake-resume-opened': ('original-capture', 'same')},
)


class SuspendWakeActiveJourney(AppRestartActiveJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.child_session = None
        self.sleep_deadline = None
        self.boundary_balance = None
        self.boundary_countdown = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'before-policy':
            self.boundary_balance = deepcopy(observed['ui']['revoke_cancel']['balances'])
        if stage in ('boundary-countdown', 'wake-countdown'):
            value = CountdownObservation.from_value(observed['ui']['countdown'], present=True,
                                                    child='existing-fixture-child')
            require(countdown_seconds(value.text)[0] >= 300, 'suspend-wake-active:active-margin')
            bounds = tuple(self.ui.read_bounds)
            if stage == 'boundary-countdown':
                balance = self.boundary_balance
                require(balance is not None, 'suspend-wake-active:missing-policy')
                observed['comparison'] = check_countdown_balance(value,
                    seconds=balance['one_time']['seconds'],
                    precision_seconds=balance['one_time']['precision_seconds'],
                    observed_monotonic_ns=balance['observed_monotonic_ns'], max_elapsed_seconds=300)
                self.boundary_countdown = (value.seconds, bounds)
                self.sleep_deadline = time.monotonic() + 180
            else:
                require(self.boundary_countdown is not None, 'suspend-wake-active:missing-countdown')
                before, earlier = self.boundary_countdown
                minimum, maximum = (bounds[0] - earlier[1]) / 1e9, (bounds[1] - earlier[0]) / 1e9
                require(0 < minimum <= maximum < 1200
                        and before - maximum - 4 < value.seconds < before - minimum + 4,
                        'suspend-wake-active:original-positive-deadline')
                observed['comparison'] = {'original_positive_deadline': True}
        if stage == 'suspend':
            self.child_session = observed['system']['session_sha256']
        if stage in ('wake-session', 'wake-child-entry-guard', 'returned-session',
                     'returned-jordan-entry-entry-guard'):
            require(self.child_session is not None
                    and observed['system']['session_sha256'] == self.child_session,
                    'suspend-wake-active:child-session-changed')

    @staticmethod
    def suspend(journey, guard):
        require(journey.sleep_deadline is not None, 'suspend-wake-active:missing-countdown')
        return journey.submit_suspend(guard, duration=5,
                                      deadline=min(journey.sleep_deadline, guard()))


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-022/suspend-wake-active'
    record_installed_journey(recorder, context, PLAN, timeout=3600,
        journey_type=SuspendWakeActiveJourney,
        actions={**fixture_actions(include_refusal=False, profile='activity'),
                 'suspend-wake': SuspendWakeActiveJourney.suspend})


E2E_CASES = {'suspend-wake-active': execute}
