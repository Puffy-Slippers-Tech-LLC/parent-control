"""Case 29: daily plus approved time, retained work and natural exhaustion."""

from accessible_ui import countdown_seconds
from grant_only_profile import GrantOnlyProfileJourney
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import countdown_activity, fresh_desktop, grant_only_time_profile
from journey_checks import CountdownActivityJourney
from private_artifacts import require


TIME_STAGES = ('initial-countdown', 'returned-countdown', 'minute-progression',
               'final-second-transition', 'second-progression',
               'independent-second-progression', 'natural-expiry')
SCREENS = {
    **grant_only_time_profile(source='gdm', entry='fresh', window='new',
        initial_enabled=False, revoke_first=False, duration_seconds=240,
        request_initial='default', balance_readback=False, daily_minutes=4),
    'profile-balance': 'ui:revoke-balances',
    **{stage: ('ui:overlay-native-activity' if stage in ('lock-ready', 'unlock-desktop') else tag)
       for stage, tag in countdown_activity(TIME_STAGES[2:]).items()
       if stage not in ('fresh-desktop', 'activity-desktop')},
}
LOGIN_STAGES = {*fresh_desktop('parent'),
                *('fresh-' + stage for stage in fresh_desktop('child'))}
PLAN = JourneyPlan(
    prefix='countdown-combined', worker_mode='countdown_combined', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in tuple(SCREENS)[tuple(SCREENS).index('lock-ready'):]},
            **{stage: 'step-3' for stage in tuple(SCREENS)[tuple(SCREENS).index('minute-progression'):]}},
    advance_after={'activity-capture': 'step-2', 'usable-activity': 'step-3'},
    invocations=tuple(stage for stage in SCREENS
                      if stage in LOGIN_STAGES or stage in TIME_STAGES
                      or stage in ('lock-input-ready', 'lock-result')),
    challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked')},
    stage_actions={'desktop': 'native-verify', 'minute-progression': 'minute-progress',
                   'final-second-transition': 'final-transition',
                   'second-progression': 'second-progress',
                   'independent-second-progression': 'second-progress',
                   'natural-expiry': 'natural-expiry'},
    activity_entries={'natural-expiry': 'activity-capture'},
    activity_checks={stage: ('activity-capture', 'same') for stage in (
        'returned-activity', 'resume-opened', 'usable-activity', 'lock-ready', 'unlock-desktop')},
    assertions_after={'activity-capture': 'usable-child-activity',
                      'returned-countdown': 'resumed-time', 'usable-activity': 'retained-work',
                      'minute-progression': 'minute-progression',
                      'independent-second-progression': 'second-progression',
                      'lock-result': 'visible-result'},
)


class CountdownCombinedJourney(CountdownActivityJourney, GrantOnlyProfileJourney):
    # Four daily minutes plus four approved minutes permit at most seven edges.
    minute_edge_limit = 7

    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, time_stages=TIME_STAGES,
                         daily_minutes=4, grant_seconds=240, actions=actions)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'profile-balance':
            value = observed['ui']['revoke_cancel']['balances']['total']
            self.balance = (value['seconds'], value['precision_seconds'],
                            observed['ui']['revoke_cancel']['balances']['observed_monotonic_ns'])
        if stage in ('initial-countdown', 'returned-countdown'):
            current = self.samples[stage]
            require(current.precision_seconds == 60
                    and countdown_seconds(current.countdown.text)[0]
                        >= (180 if stage == 'initial-countdown' else 120),
                    'countdown-combined:minute-margin')


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-011/combined'
    record_installed_journey(recorder, context, PLAN, journey_type=CountdownCombinedJourney)


E2E_CASES = {'combined': execute}
