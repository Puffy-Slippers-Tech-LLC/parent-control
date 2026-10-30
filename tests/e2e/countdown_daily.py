"""Case 27: daily time, retained work and countdown through natural exhaustion."""

from accessible_ui import countdown_seconds
from countdown import (CountdownSample, await_countdown_progress,
                       check_countdown_balance, check_countdown_progress)
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (daily_time_profile, fresh_desktop, lock_challenge,
                            lock_recipient, native_activity_entry,
                            native_activity_resume, prefixed_stages)
from journey_checks import DailyTimeProfileJourney
from native_fixtures import fixture_actions
from natural_expiry_observation import await_natural_expiry
from private_artifacts import require
from ui_observations import AppActivityObservation, SettingsObservation, compare_app_activity


TIME_STAGES = ('initial-countdown', 'returned-countdown', 'minute-progression',
               'final-second-transition', 'second-progression',
               'independent-second-progression', 'natural-expiry')
ACTIVITY_SCREENS = {
    **prefixed_stages('fresh', fresh_desktop('child')),
    'initial-countdown': 'ui:child-countdown-present',
    **native_activity_entry('activity', child='child'),
    'lock-ready': 'ui:fresh-child-desktop', 'lock': 'system:child-lock',
    **lock_challenge(account='child'), **lock_recipient(account='child'),
    'unlock-desktop': 'ui:fresh-child-desktop',
    'returned-countdown': 'ui:child-countdown-present',
    'returned-activity': 'ui:overlay-native-activity',
    **native_activity_resume('resume', child='child'),
    'usable-activity': 'ui:overlay-native-activity',
    **{stage: 'ui:child-countdown-present' for stage in TIME_STAGES[2:]},
    'lock-input-ready': 'ui:child-natural-expiry-lock-ready',
    'lock-result': 'ui:child-natural-expiry-lock-result',
}
SCREENS = {
    **fresh_desktop('parent'),
    **daily_time_profile(source='desktop', entry='same-user', window='new',
                         initial_enabled=False, minutes=4),
    **ACTIVITY_SCREENS,
}
PLAN = JourneyPlan(
    prefix='countdown-daily', worker_mode='countdown_daily', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in tuple(SCREENS)[tuple(SCREENS).index('lock-ready'):]},
            **{stage: 'step-3' for stage in tuple(SCREENS)[tuple(SCREENS).index('minute-progression'):]}},
    advance_after={'activity-capture': 'step-2', 'usable-activity': 'step-3'},
    invocations=tuple(stage for stage in SCREENS if stage in fresh_desktop('parent')
                      or stage.startswith('fresh-') or stage in TIME_STAGES
                      or stage in ('lock-input-ready', 'lock-result')),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
    },
    settings_checks={'same-parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
                     'profile-settings': SettingsObservation('fixture-child', True, ('4 minutes',))},
    balance_checks={'profile-configured': 240},
    stage_actions={'desktop': 'native-verify', 'minute-progression': 'minute-progress',
                   'final-second-transition': 'final-transition',
                   'second-progression': 'second-progress',
                   'independent-second-progression': 'second-progress',
                   'natural-expiry': 'natural-expiry'},
    activity_entries={'natural-expiry': 'activity-capture'},
    activity_checks={stage: ('activity-capture', 'same')
                     for stage in ('returned-activity', 'resume-opened', 'usable-activity')},
    assertions_after={'activity-capture': 'usable-child-activity',
                      'returned-countdown': 'resumed-time', 'usable-activity': 'retained-work',
                      'minute-progression': 'minute-progression',
                      'independent-second-progression': 'second-progression',
                      'lock-result': 'visible-result'},
)


class CountdownActivityJourney:
    """Shared retained-work and immutable countdown comparisons for E2E-011."""

    minute_edge_limit = 3

    def __init__(self, context, progress, plan, *, actions=None, **kwargs):
        if actions is None:
            available = {
                **fixture_actions(include_refusal=False), 'minute-progress': self.minutes,
                'final-transition': self.transition, 'second-progress': self.seconds,
                'natural-expiry': self.expiry}
            actions = {name: action for name, action in available.items()
                       if name in plan.stage_actions.values()}
        super().__init__(context, progress, plan, **kwargs,
                         actions=actions)
        self.balance = None
        self.samples = {}
        self.last_progress = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'profile-configured':
            value = observed['ui']['time_explanation']
            self.balance = (value['total']['seconds'], value['total']['precision_seconds'],
                            value['observed_monotonic_ns'])
        if stage not in TIME_STAGES:
            return
        current = CountdownSample.from_ui(observed['ui'], boot_sha256=observed['boot_sha256'])
        require(stage not in self.samples and countdown_seconds(current.countdown.text)[0] > 0,
                'countdown-daily:missed-or-replayed-window')
        if stage == 'initial-countdown':
            require(self.balance is not None, 'countdown:missing-balance')
            observed['comparison'] = check_countdown_balance(current.countdown,
                seconds=self.balance[0], precision_seconds=self.balance[1],
                observed_monotonic_ns=self.balance[2])
        elif stage == 'returned-countdown':
            previous = self.samples['initial-countdown']
            current.elapsed_since(previous, max_elapsed_seconds=180)
            require(countdown_seconds(current.countdown.text)[0]
                    <= countdown_seconds(previous.countdown.text)[0], 'countdown-daily:return-reset')
            observed['comparison'] = check_countdown_balance(current.countdown,
                seconds=countdown_seconds(previous.countdown.text)[0],
                precision_seconds=previous.precision_seconds,
                observed_monotonic_ns=previous.countdown.observed_monotonic_ns)
        else:
            previous = self.last_progress or self.samples['returned-countdown']
            current.elapsed_since(previous, max_elapsed_seconds=90 if stage in (
                'minute-progression', 'final-second-transition') else 15)
            require(countdown_seconds(current.countdown.text)[0]
                    <= countdown_seconds(previous.countdown.text)[0], 'countdown:no-progress')
            if stage == 'natural-expiry' and current.countdown.text != previous.countdown.text:
                observed['comparison'] = check_countdown_progress(current, previous,
                    precision_seconds=1, tolerance_seconds=2, max_elapsed_seconds=15)
        self.samples[stage] = current

    @staticmethod
    def minutes(journey, guard):
        current = journey.samples['minute-progression']
        require(current.precision_seconds == 60 and countdown_seconds(current.countdown.text)[0] >= 120,
                'countdown-daily:minute-margin')
        activity = journey.activity_observations['activity-capture']
        guard()
        value = journey.ui.observe('child-natural-expiry-observe')['natural_expiry']
        guard()
        require(value['state'] == 'desktop', 'countdown-daily:early-lock')
        compare_app_activity(AppActivityObservation.from_value(value['activity']), activity)
        progressions, activities = [], []
        # Each profile declares its finite number of minute edges. Every edge
        # keeps its 90-second bound; ordinary app use resumes between them.
        while current.countdown.text != '00:01':
            require(len(progressions) < journey.minute_edge_limit, 'countdown-daily:minute-bound')
            current, comparison = await_countdown_progress(journey, guard, current,
                precision_seconds=60, tolerance_seconds=2, max_elapsed_seconds=90)
            progressions.append(comparison)
            guard()
            value = journey.ui.observe('child-natural-expiry-activity')['natural_expiry']
            guard()
            require(value['state'] == 'desktop' and value['acted'], 'countdown-daily:early-lock')
            compare_app_activity(AppActivityObservation.from_value(value['activity']), activity)
            activities.append(value)
        journey.last_progress = current
        return {'progressions': progressions, 'activities': activities}

    @staticmethod
    def transition(journey, guard):
        current, result = await_countdown_progress(journey, guard, journey.last_progress,
            precision_seconds=1, previous_precision_seconds=60, tolerance_seconds=2,
            max_elapsed_seconds=90, initial_sample=journey.samples['final-second-transition'])
        require(countdown_seconds(current.countdown.text)[0] > 0, 'countdown:final-window-missed')
        journey.last_progress = current
        return result

    @staticmethod
    def seconds(journey, guard):
        stage = ('independent-second-progression' if 'independent-second-progression' in journey.samples
                 else 'second-progression')
        current, result = await_countdown_progress(journey, guard, journey.last_progress,
            precision_seconds=1, tolerance_seconds=2, max_elapsed_seconds=15,
            initial_sample=journey.samples[stage])
        require(countdown_seconds(current.countdown.text)[0] > 0, 'countdown:final-window-missed')
        journey.last_progress = current
        return result

    @staticmethod
    def expiry(journey, guard):
        return await_natural_expiry(journey, guard, journey.samples['natural-expiry'],
                                    journey.activity_observations['activity-capture'])


class CountdownDailyJourney(CountdownActivityJourney, DailyTimeProfileJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, no_grant_checks=('profile-before',),
                         actions=actions)


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-011/daily-only'
    record_installed_journey(recorder, context, PLAN, journey_type=CountdownDailyJourney)


E2E_CASES = {'daily-only': execute}
