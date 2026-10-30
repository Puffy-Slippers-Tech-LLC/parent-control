"""Case 28: real two-minute approval, retained work and natural exhaustion."""

from dataclasses import replace

from accessible_ui import countdown_seconds
from countdown_daily import ACTIVITY_SCREENS, PLAN as DAILY_PLAN, CountdownActivityJourney
from grant_only_profile import GrantOnlyProfileJourney
from installed_journey import record_installed_journey
from journey_blocks import fresh_desktop, grant_only_time_profile
from private_artifacts import require


SCREENS = {
    **grant_only_time_profile(source='gdm', entry='fresh', window='new',
        initial_enabled=False, revoke_first=False, duration_seconds=120,
        request_initial='default', balance_readback=False),
    'profile-balance': 'ui:revoke-balances',
    **{stage: ('ui:overlay-native-activity' if stage in ('lock-ready', 'unlock-desktop') else tag)
       for stage, tag in ACTIVITY_SCREENS.items()
       if stage not in ('minute-progression', 'fresh-desktop', 'activity-desktop')},
}
LOGIN_PREFIXES = {'': 'parent-login', 'fresh-': 'child-login'}
LOGIN_STAGES = {prefix + stage for prefix in LOGIN_PREFIXES
                for stage in fresh_desktop('child' if prefix == 'fresh-' else 'parent')}
PLAN = replace(DAILY_PLAN,
    prefix='countdown-grant', worker_mode='countdown_grant', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in tuple(SCREENS)[tuple(SCREENS).index('lock-ready'):]},
            **{stage: 'step-3' for stage in tuple(SCREENS)[tuple(SCREENS).index('final-second-transition'):]}},
    invocations=tuple(stage for stage in SCREENS
                      if stage in LOGIN_STAGES or stage in DAILY_PLAN.invocations),
    challenges={identity: ('child' if prefix == 'fresh-' else 'parent',
        prefix + ('child-' if prefix == 'fresh-' else '') + 'recipient-qualified',
        prefix + ('child-' if prefix == 'fresh-' else '') + 'recipient-rechecked')
        for prefix, identity in LOGIN_PREFIXES.items()},
    settings_checks={}, balance_checks={},
    stage_actions={stage: action for stage, action in DAILY_PLAN.stage_actions.items()
                   if stage in SCREENS},
    activity_checks={**DAILY_PLAN.activity_checks,
                     **{stage: ('activity-capture', 'same')
                        for stage in ('lock-ready', 'unlock-desktop')}},
    assertions_after={**{stage: assertion for stage, assertion in DAILY_PLAN.assertions_after.items()
                        if stage in SCREENS}, 'final-second-transition': 'minute-progression'},
)


class CountdownGrantJourney(CountdownActivityJourney, GrantOnlyProfileJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'profile-balance':
            value = observed['ui']['revoke_cancel']['balances']
            self.balance = (value['total']['seconds'], value['total']['precision_seconds'],
                            value['observed_monotonic_ns'])
        if stage == 'initial-countdown':
            current = self.samples[stage]
            require(current.precision_seconds == 60 and current.countdown.text == '00:01',
                    'countdown-grant:minute-margin')
        if stage == 'returned-countdown':
            current = self.samples[stage]
            require(countdown_seconds(current.countdown.text)[0] >= 30,
                    'countdown-grant:remaining-activity-margin')
            # The real grant also runs during activity and unlock. Preserve the
            # original minute endpoint if that history crossed into seconds;
            # the same 90-second comparison still owns the whole transition.
            self.last_progress = (current if current.precision_seconds == 60 else
                                  self.samples['initial-countdown'])


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-011/grant-only'
    record_installed_journey(recorder, context, PLAN, journey_type=CountdownGrantJourney)


E2E_CASES = {'grant-only': execute}
