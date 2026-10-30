"""Case 27: daily time, retained work and countdown through natural exhaustion."""

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import countdown_activity, daily_time_profile, fresh_desktop
from journey_checks import CountdownActivityJourney, DailyTimeProfileJourney
from ui_observations import SettingsObservation


TIME_STAGES = ('initial-countdown', 'returned-countdown', 'minute-progression',
               'final-second-transition', 'second-progression',
               'independent-second-progression', 'natural-expiry')
SCREENS = {
    **fresh_desktop('parent'),
    **daily_time_profile(source='desktop', entry='same-user', window='new',
                         initial_enabled=False, minutes=4),
    **countdown_activity(TIME_STAGES[2:]),
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


class CountdownDailyJourney(CountdownActivityJourney, DailyTimeProfileJourney):
    minute_edge_limit = 3

    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, time_stages=TIME_STAGES,
                         no_grant_checks=('profile-before',),
                         actions=actions)


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-011/daily-only'
    record_installed_journey(recorder, context, PLAN, journey_type=CountdownDailyJourney)


E2E_CASES = {'daily-only': execute}
