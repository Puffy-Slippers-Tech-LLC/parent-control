"""Case 28: real approval, retained work and natural exhaustion."""

from accessible_ui import countdown_seconds
from grant_only_profile import GrantOnlyProfileJourney
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import countdown_activity, fresh_desktop, grant_only_time_profile
from journey_checks import CountdownActivityJourney
from private_artifacts import require


TIME_STAGES = ('initial-countdown', 'returned-countdown', 'minute-progression', 'final-second-transition',
               'second-progression', 'independent-second-progression', 'natural-expiry')
SCREENS = {
    **grant_only_time_profile(source='gdm', entry='fresh', window='new',
        initial_enabled=False, revoke_first=False, duration_seconds=600,
        request_initial='default', balance_readback=False),
    'profile-balance': 'ui:revoke-balances',
    **{stage: ('ui:overlay-native-activity' if stage in ('lock-ready', 'unlock-desktop') else tag)
       for stage, tag in countdown_activity(TIME_STAGES[2:]).items()
       if stage not in ('fresh-desktop', 'activity-desktop')},
}
LOGIN_PREFIXES = {'': 'parent-login', 'fresh-': 'child-login'}
LOGIN_STAGES = {prefix + stage for prefix in LOGIN_PREFIXES
                for stage in fresh_desktop('child' if prefix == 'fresh-' else 'parent')}
PLAN = JourneyPlan(
    prefix='countdown-grant', worker_mode='countdown_grant', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in tuple(SCREENS)[tuple(SCREENS).index('lock-ready'):]},
            **{stage: 'step-3' for stage in tuple(SCREENS)[tuple(SCREENS).index('minute-progression'):]}},
    advance_after={'activity-capture': 'step-2', 'usable-activity': 'step-3'},
    invocations=tuple(stage for stage in SCREENS
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
                      'independent-second-progression': 'second-progression',
                      'lock-result': 'visible-result', 'minute-progression': 'minute-progression'},
)


class CountdownGrantJourney(CountdownActivityJourney, GrantOnlyProfileJourney):
    minute_edge_limit = 9

    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, time_stages=TIME_STAGES,
                         grant_seconds=600, actions=actions)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'profile-balance':
            value = observed['ui']['revoke_cancel']['balances']
            self.balance = (value['total']['seconds'], value['total']['precision_seconds'],
                            value['observed_monotonic_ns'])
        if stage == 'initial-countdown':
            current = self.samples[stage]
            require(current.precision_seconds == 60
                    and countdown_seconds(current.countdown.text)[0] >= 180,
                    'countdown-grant:minute-margin')
        if stage == 'returned-countdown':
            current = self.samples[stage]
            require(current.precision_seconds == 60
                    and countdown_seconds(current.countdown.text)[0] >= 120,
                    'countdown-grant:remaining-activity-margin')


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-011/grant-only'
    record_installed_journey(recorder, context, PLAN, journey_type=CountdownGrantJourney)


E2E_CASES = {'grant-only': execute}
