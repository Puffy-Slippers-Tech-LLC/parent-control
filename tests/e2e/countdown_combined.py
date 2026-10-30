"""Case 29: daily plus approved time, retained work and natural exhaustion."""

from dataclasses import replace

from accessible_ui import countdown_seconds
from countdown_daily import ACTIVITY_SCREENS, PLAN as DAILY_PLAN, CountdownActivityJourney
from countdown_grant import PLAN as GRANT_PLAN
from grant_only_profile import GrantOnlyProfileJourney
from installed_journey import record_installed_journey
from journey_blocks import grant_only_time_profile
from private_artifacts import require


SCREENS = {
    **grant_only_time_profile(source='gdm', entry='fresh', window='new',
        initial_enabled=False, revoke_first=False, duration_seconds=120,
        request_initial='default', balance_readback=False, daily_minutes=4),
    'profile-balance': 'ui:revoke-balances',
    **{stage: ('ui:overlay-native-activity' if stage in ('lock-ready', 'unlock-desktop') else tag)
       for stage, tag in ACTIVITY_SCREENS.items()
       if stage not in ('fresh-desktop', 'activity-desktop')},
}
PLAN = replace(GRANT_PLAN,
    prefix='countdown-combined', worker_mode='countdown_combined', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in tuple(SCREENS)[tuple(SCREENS).index('lock-ready'):]},
            **{stage: 'step-3' for stage in tuple(SCREENS)[tuple(SCREENS).index('minute-progression'):]}},
    invocations=tuple(stage for stage in SCREENS
                      if stage in GRANT_PLAN.invocations or stage == 'minute-progression'),
    stage_actions={stage: action for stage, action in DAILY_PLAN.stage_actions.items()
                   if stage in SCREENS},
    assertions_after=DAILY_PLAN.assertions_after,
)


class CountdownCombinedJourney(CountdownActivityJourney, GrantOnlyProfileJourney):
    # Four daily minutes plus two approved minutes permit at most five edges.
    minute_edge_limit = 5

    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, daily_minutes=4, actions=actions)

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
