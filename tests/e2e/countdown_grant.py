"""Cases 28 and 29: approved time, retained work and natural exhaustion."""
from functools import partial

from accessible_ui import countdown_seconds
from grant_only_profile import GrantOnlyProfileJourney
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import countdown_activity, fresh_desktop, grant_only_time_profile
from journey_checks import CountdownActivityJourney
from private_artifacts import require


TIME_STAGES = ('initial-countdown', 'returned-countdown', 'minute-progression', 'final-second-transition',
               'second-progression', 'independent-second-progression', 'natural-expiry')
LOGIN_PREFIXES = {'': 'parent-login', 'fresh-': 'child-login'}
LOGIN_STAGES = {prefix + stage for prefix in LOGIN_PREFIXES
                for stage in fresh_desktop('child' if prefix == 'fresh-' else 'parent')}


def grant_countdown_plan(profile, *, grant_seconds, daily_minutes):
    screens = {
        **grant_only_time_profile(source='gdm', entry='fresh', window='new',
            initial_enabled=False, revoke_first=False, duration_seconds=grant_seconds,
            request_initial='default', balance_readback=False, daily_minutes=daily_minutes),
        'profile-balance': 'ui:revoke-balances',
        **{stage: ('ui:overlay-native-activity' if stage in ('lock-ready', 'unlock-desktop') else tag)
           for stage, tag in countdown_activity(TIME_STAGES[2:]).items()
           if stage not in ('fresh-desktop', 'activity-desktop')},
    }
    stages = tuple(screens)
    return JourneyPlan(
        prefix=f'countdown-{profile}', worker_mode=f'countdown_{profile}', screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: 'step-1' for stage in screens}, 'installed-greeter': 'start',
                **{stage: 'step-2' for stage in stages[stages.index('lock-ready'):]},
                **{stage: 'step-3' for stage in stages[stages.index('minute-progression'):]}},
        advance_after={'activity-capture': 'step-2', 'usable-activity': 'step-3'},
        invocations=tuple(stage for stage in screens
                          if stage in LOGIN_STAGES or stage in TIME_STAGES
                          or stage in ('lock-input-ready', 'lock-result')),
        challenges={identity: ('child' if prefix == 'fresh-' else 'parent',
            prefix + ('child-' if prefix == 'fresh-' else '') + 'recipient-qualified',
            prefix + ('child-' if prefix == 'fresh-' else '') + 'recipient-rechecked')
            for prefix, identity in LOGIN_PREFIXES.items()},
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


class CountdownGrantJourney(CountdownActivityJourney, GrantOnlyProfileJourney):
    minute_edge_limit = 9
    daily_minutes = 0
    grant_seconds = 600

    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, time_stages=TIME_STAGES,
                         daily_minutes=self.daily_minutes, grant_seconds=self.grant_seconds,
                         actions=actions)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'profile-balance':
            value = observed['ui']['revoke_cancel']['balances']
            self.balance = (value['total']['seconds'], value['total']['precision_seconds'],
                            value['observed_monotonic_ns'])
        margins = {'initial-countdown': 180, 'returned-countdown': 120}
        if stage in margins:
            current = self.samples[stage]
            require(current.precision_seconds == 60
                    and countdown_seconds(current.countdown.text)[0] >= margins[stage],
                    f'{self.plan.prefix}:{stage}-minute-margin')


class CountdownCombinedJourney(CountdownGrantJourney):
    # Four daily minutes plus four approved minutes permit at most seven edges.
    minute_edge_limit = 7
    daily_minutes = 4
    grant_seconds = 240


PLAN = grant_countdown_plan('grant', grant_seconds=CountdownGrantJourney.grant_seconds,
                            daily_minutes=CountdownGrantJourney.daily_minutes)
COMBINED_PLAN = grant_countdown_plan('combined', grant_seconds=CountdownCombinedJourney.grant_seconds,
                                     daily_minutes=CountdownCombinedJourney.daily_minutes)


def execute(recorder, context, *, variant, plan, journey_type):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-011/' + variant
    record_installed_journey(recorder, context, plan, journey_type=journey_type)


E2E_CASES = {
    'grant-only': partial(execute, variant='grant-only', plan=PLAN, journey_type=CountdownGrantJourney),
    'combined': partial(execute, variant='combined', plan=COMBINED_PLAN, journey_type=CountdownCombinedJourney),
}
