"""Cases 223/225: time keeps running while the parent decides, then adds twice."""
from copy import deepcopy
from dataclasses import replace
import time

from countdown import CountdownObservation
from grant_only_profile import GrantOnlyProfileJourney
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (daily_time_profile, desktop_entry, fresh_desktop,
                            grant_only_time_profile, prefixed_stages, retained_parent_entry)
from journey_checks import DailyTimeProfileJourney
from private_artifacts import require
from real_interval import interval_action
from request_flow import approval_and_return
from ui_observations import SettingsObservation


CHOICES = dict(child='fixture-child', approver='fixture-parent',
               duration_seconds=30, allow_soft=False)
PROMPT_WAIT_SECONDS = 45
# Grant time also runs during Parent visits and provider observations. Leave
# ample headroom for slow machines without extending the deliberate wait.
INITIAL_GRANT_SECONDS = 1200
MIN_APPROVAL_REMAINING_SECONDS = 300
SCREENS = {
    **fresh_desktop('parent'),
    **daily_time_profile(source='desktop', entry='same-user', window='new',
                         initial_enabled=False, minutes=10),
    **prefixed_stages('child-entry', desktop_entry('child', source='gdm', entry='fresh')),
}
for request in ('first', 'second'):
    SCREENS.update({
        request + '-before': 'ui:child-countdown-present',
        **prefixed_stages(request, approval_and_return(prefix='new', entry='new', **CHOICES)),
        **prefixed_stages(request + '-parent', retained_parent_entry(source='child-desktop')),
        request + '-balances': 'ui:revoke-balances',
    })
    if request == 'first':
        SCREENS.update({
            **prefixed_stages('return-child', desktop_entry('child', source='desktop',
                entry='retained', source_account='parent')),
            'cooldown': 'ui:fresh-child-desktop',
        })

FIRST_WAIT = tuple(SCREENS).index('first-approval-open')
FIRST_RESULT = tuple(SCREENS).index('first-countdown')
LOGIN_GROUPS = {'initial': ('parent', ''), 'child-entry': ('child', 'child-entry-'),
                'first-parent': ('parent', 'first-parent-'),
                'return-child': ('child', 'return-child-'),
                'second-parent': ('parent', 'second-parent-')}
CHALLENGES = {name: (role, prefix + ('recipient-qualified' if role == 'parent' else 'child-recipient-qualified'),
                    prefix + ('recipient-rechecked' if role == 'parent' else 'child-recipient-rechecked'))
              for name, (role, prefix) in LOGIN_GROUPS.items()}
LOGIN_STAGES = {prefix + stage for role, prefix in LOGIN_GROUPS.values()
                for stage in fresh_desktop(role)}
PLAN = JourneyPlan(
    prefix='delayed-approval', worker_mode='delayed_approval', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' if index < FIRST_WAIT else
                      'step-2' if index < FIRST_RESULT else 'step-3'
               for index, stage in enumerate(SCREENS)}, 'installed-greeter': 'start'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges=CHALLENGES,
    settings_checks={'same-parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
                     'profile-settings': SettingsObservation('fixture-child', True, ('10 minutes',))},
    balance_checks={'profile-configured': 600},
    overlay_request=('child', 'parent', 30, False),
    stage_actions={'first-approval-open': 'real-interval', 'cooldown': 'cooldown'},
    assertions_after={'first-countdown': 'delayed-current-balance-increment',
                      'second-balances': 'visible-result'},
)


GRANT_SCREENS = {
    **grant_only_time_profile(source='gdm', entry='fresh', window='new',
        initial_enabled=False, revoke_first=False, duration_seconds=INITIAL_GRANT_SECONDS,
        request_initial='default', balance_readback=False),
    **dict(list(SCREENS.items())[tuple(SCREENS).index('child-entry-entry-guard'):]),
}
GRANT_PLAN = replace(PLAN, worker_mode='delayed_grant_approval', screen_tags=GRANT_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: PLAN.phases.get(stage, 'step-1') for stage in GRANT_SCREENS},
            'installed-greeter': 'start'},
    invocations=tuple(stage for stage in GRANT_SCREENS if stage in LOGIN_STAGES),
    challenges={('parent-login' if name == 'initial' else name): binding
                for name, binding in CHALLENGES.items()},
    settings_checks={'parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',))},
    balance_checks={})


class DelayedApprovalChecks:
    # Exact canonical seconds have one-second precision. Include read latency
    # in each interval, plus two seconds for the native/public refresh boundary.
    tolerance = 2

    balance_profile = 'daily-only'

    def __init__(self, context, progress, plan, *, actions=None, **kwargs):
        super().__init__(context, progress, plan, **kwargs,
            actions=actions if actions is not None else {
                'real-interval': interval_action(PROMPT_WAIT_SECONDS), 'cooldown': self.cooldown})
        self.samples = {}
        self.estimates = {}
        self.success_at = None

    def cooldown(self, journey, guard):
        require(self.success_at is not None, 'delayed-approval:missing-success')
        remaining = 5 - (time.monotonic() - self.success_at)
        return interval_action(remaining)(journey, guard) if remaining > 0 else 0

    def elapsed(self, before, after):
        low = (after[0] - before[1]) / 1e9
        high = (after[1] - before[0]) / 1e9
        require(0 < low <= high <= 180, 'delayed-approval:elapsed-bound')
        return low, high

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        value = observed.get('ui', {})
        if stage in ('first-before', 'second-before', 'first-countdown', 'second-countdown'):
            countdown = CountdownObservation.from_value(value['countdown'], present=True)
            bounds = tuple(value['countdown_read_bounds'])
            require(bounds[1] - bounds[0] <= 10e9, 'delayed-approval:read-precision')
            self.samples[stage] = (countdown.seconds, bounds)
            if stage in ('first-before', 'second-before'):
                require(countdown.seconds >= MIN_APPROVAL_REMAINING_SECONDS,
                        'delayed-approval:usable-margin')
            if stage == 'second-before' and self.balance_profile == 'grant-only':
                # Grant-only time also elapses while visiting Parent.
                seconds, earlier = self.samples['first-countdown']
                low, high = self.elapsed(earlier, bounds)
                require(seconds - high - self.tolerance <= countdown.seconds
                        <= seconds - low + self.tolerance
                        and countdown.seconds > 0,
                        'delayed-approval:second-current-balance')
            elif stage in ('first-countdown', 'second-countdown'):
                request = stage.split('-')[0]
                seconds, earlier = self.samples[request + '-before']
                low, high = self.elapsed(earlier, bounds)
                require(seconds + 30 - high - self.tolerance <= countdown.seconds
                        <= seconds + 30 - low + self.tolerance,
                        'delayed-approval:current-balance-increment')
                if request == 'first':
                    require(low >= PROMPT_WAIT_SECONDS, 'delayed-approval:real-wait')
                    estimate, _ = self.estimates['first']
                    # A frozen estimate issued only after authentication would
                    # still exceed this independently read result by the wait.
                    _, since_submit = self.elapsed(self.submit_bounds, bounds)
                    require(countdown.seconds + self.tolerance
                            < estimate['estimate']['seconds'] - since_submit - self.tolerance,
                            'delayed-approval:frozen-estimate-not-distinguished')
                observed.setdefault('comparison', {}).update(
                    current_balance_increment=True, elapsed_interval_seconds=[low, high],
                    tolerance_seconds=self.tolerance)
        if stage in ('first-new-choices', 'second-new-choices'):
            self.choice_bounds = tuple(self.ui.read_bounds)
        if stage in ('first-new-estimate', 'second-new-estimate'):
            request = stage.split('-')[0]
            choice = deepcopy(value['valid_choice'])
            require(choice['request']['child'] == 'fixture-child'
                    and choice['request']['approver'] == 'fixture-parent'
                    and choice['request']['duration_seconds'] == 30
                    and choice['request']['allow_soft'] is False
                    and choice['estimate']['kind'] == 'fixed'
                    and choice['estimate']['precision_seconds'] == 1,
                    'delayed-approval:estimate-binding')
            bounds = (self.choice_bounds[0], self.ui.read_bounds[1])
            # The estimate can be calculated anywhere during choices/readback.
            # Its whole uncertainty interval, with both refresh margins, must
            # fit inside the deliberate wait. A fixed 20-second cap wrongly
            # rejected a distinguishable 28-second bracket on the live guest.
            require((bounds[1] - bounds[0]) / 1e9 + 2 * self.tolerance
                    < PROMPT_WAIT_SECONDS, 'delayed-approval:estimate-precision')
            seconds, earlier = self.samples[request + '-before']
            low, high = self.elapsed(earlier, bounds)
            require(seconds + 30 - high - self.tolerance <= choice['estimate']['seconds']
                    <= seconds + 30 - low + self.tolerance,
                    'delayed-approval:estimate-arithmetic')
            self.estimates[request] = (choice, bounds)
        if stage in ('first-approval-open', 'second-approval-open'):
            estimate, earlier = self.estimates[stage.split('-')[0]]
            _, elapsed = self.elapsed(earlier, tuple(self.ui.read_bounds))
            require(estimate['estimate']['seconds'] - 30 - elapsed - self.tolerance
                    >= MIN_APPROVAL_REMAINING_SECONDS,
                    'delayed-approval:prompt-usable-margin')
        if stage == 'first-approval-submit-ready':
            self.submit_bounds = tuple(self.ui.read_bounds)
        if stage == 'first-approval-success':
            self.success_at = time.monotonic()
        if stage.endswith('-balances'):
            request = stage.split('-')[0]
            balances = value['revoke_cancel']['balances']
            require(balances['child'] == 'fixture-child', 'delayed-approval:wrong-child')
            seconds, earlier = self.samples[request + '-countdown']
            low, high = self.elapsed(earlier, tuple(value['revoke_cancel']['read_bounds']))
            grant = balances['one_time']
            precision = grant['precision_seconds'] + self.tolerance
            require(seconds - high - precision <= grant['seconds']
                    <= seconds - low + precision
                    and grant['seconds'] > 0
                    and (balances['daily']['seconds'] == 0 if self.balance_profile == 'grant-only'
                         else balances['daily']['seconds'] > 0)
                    and abs(balances['total']['seconds'] - max(
                        balances['daily']['seconds'], grant['seconds'])) <= precision,
                    'delayed-approval:parent-balances')
            observed.setdefault('comparison', {})['independent_parent_balances'] = True


class DelayedApprovalJourney(DelayedApprovalChecks, DailyTimeProfileJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, no_grant_checks=('profile-before',), actions=actions)


class GrantDelayedApprovalJourney(DelayedApprovalChecks, GrantOnlyProfileJourney):
    balance_profile = 'grant-only'

    def __init__(self, context, progress, plan=GRANT_PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.initial_grant_bounds = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'profile-request-new-estimate':
            choice = observed['ui']['valid_choice']
            require(choice['request']['duration_seconds'] == INITIAL_GRANT_SECONDS
                    and choice['estimate']['kind'] == 'fixed'
                    and choice['estimate']['seconds'] == INITIAL_GRANT_SECONDS,
                    'delayed-approval:initial-grant-estimate')
        if stage == 'profile-request-approval-success':
            self.initial_grant_bounds = (self.approval_started, self.ui.read_bounds[1])
        if stage == 'first-before':
            require(self.initial_grant_bounds is not None, 'delayed-approval:missing-initial-grant')
            seconds, bounds = self.samples[stage]
            low, high = self.elapsed(self.initial_grant_bounds, bounds)
            require(INITIAL_GRANT_SECONDS - high - self.tolerance <= seconds
                    <= INITIAL_GRANT_SECONDS - low + self.tolerance,
                    'delayed-approval:initial-grant-countdown')
        if stage.endswith('-balances'):
            require(observed['ui']['revoke_cancel']['settings'] == {
                'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['0 minutes']},
                'delayed-approval:saved-zero-daily')


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, journey_type=DelayedApprovalJourney)


def execute_grant(recorder, context):
    record_installed_journey(recorder, context, GRANT_PLAN, journey_type=GrantDelayedApprovalJourney)


E2E_CASES = {'daily-only-child-overlay': execute, 'grant-only-child-overlay': execute_grant}
