"""Two independent fresh-child entries for TIME01's desktop binding."""

from countdown import CountdownObservation, check_countdown_balance
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management
from journey_checks import check_balances
from private_artifacts import require


def plan(present):
    require(type(present) is bool, 'countdown:profile')
    screens = {
        **fresh_desktop('parent'), **parent_management(),
        'allowance-configured': 'ui:time-explanation-positive-read',
        **({} if present else {'limits-disabled': 'ui:time-explanation-off-read'}),
        'wrong-account-refused': 'ui:child-countdown-wrong-account-refused',
        'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
        'gdm-switched': 'ui:gdm-returned',
        **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
        **{stage: 'ui:child-countdown-' + ('present' if present else 'absent')
           for stage in ('countdown', 'independent-countdown')},
    }
    return JourneyPlan(
        prefix='countdown-' + ('enabled' if present else 'off'),
        worker_mode='countdown_enabled' if present else 'countdown_off', screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: 'step-1' for stage in screens}, 'installed-greeter': 'start',
                **{stage: 'step-2' for stage in screens
                   if stage.startswith('fresh-') or 'countdown' in stage}},
        advance_after={'gdm-switched': 'step-2'},
        invocations=tuple(stage for stage in screens if stage in fresh_desktop('parent')
                          or stage.startswith('fresh-') or 'countdown' in stage),
        challenges={
            'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
            'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
        },
        assertions_after={'allowance-configured': 'positive-daily-time',
                          'wrong-account-refused': 'wrong-account-refused',
                          'fresh-desktop': 'usable-child-desktop',
                          'countdown': 'countdown-present' if present else 'countdown-absent',
                          'independent-countdown': 'independent-countdown'},
    )


PLAN = plan(True)
OFF_PLAN = plan(False)


class CountdownJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.balance = None
        self.countdown = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'allowance-configured':
            check_balances(self, observed)
            value = observed['ui']['time_explanation']
            self.balance = (value['total']['seconds'], value['total']['precision_seconds'],
                            value['observed_monotonic_ns'])
        operation = self.plan.screen_tags.get(stage)
        if operation in ('ui:child-countdown-present', 'ui:child-countdown-absent'):
            value = CountdownObservation.from_value(observed['ui']['countdown'],
                present=operation == 'ui:child-countdown-present')
            if self.countdown is not None:
                require(value.observed_monotonic_ns > self.countdown.observed_monotonic_ns,
                        'countdown:stale-observation')
            if value.present:
                require(self.balance is not None, 'countdown:missing-balance')
                observed['comparison'] = check_countdown_balance(value, seconds=self.balance[0],
                    precision_seconds=self.balance[1], observed_monotonic_ns=self.balance[2])
            self.countdown = value
