"""PANEL01/02 installed slice with an independently supplied child desktop."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management
from journey_checks import check_balances
from private_artifacts import require


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-positive-read',
    'wrong-account-refused': 'ui:child-countdown-animation-wrong-account-refused',
    'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
    'animation-set': 'ui:child-countdown-animation-on',
    'animation-read': 'ui:child-countdown-animation-read',
}
PLAN = JourneyPlan(prefix='countdown-animation', worker_mode='countdown_animation',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in SCREENS
               if stage.startswith('fresh-') or stage.startswith('animation-')}},
    advance_after={'gdm-switched': 'step-2'},
    invocations=tuple(stage for stage in SCREENS if stage in fresh_desktop('parent')
                      or stage.startswith('fresh-') or stage.startswith('animation-')),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
    },
    assertions_after={'allowance-configured': 'positive-daily-time',
                      'wrong-account-refused': 'wrong-account-refused',
                      'fresh-desktop': 'usable-child-desktop',
                      'animation-set': 'animation-enabled',
                      'animation-read': 'independent-animation-enabled'})


class CountdownAnimationJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.animation_observed_ns = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'allowance-configured':
            check_balances(self, observed)
        if stage in ('animation-set', 'animation-read'):
            value = observed['ui']['panel_animation']
            require(value['animation'] is True, 'panel-animation:enabled-result')
            if stage == 'animation-read':
                require(self.animation_observed_ns is not None
                        and value['observed_monotonic_ns'] > self.animation_observed_ns,
                        'panel-animation:independent-read')
            self.animation_observed_ns = value['observed_monotonic_ns']
