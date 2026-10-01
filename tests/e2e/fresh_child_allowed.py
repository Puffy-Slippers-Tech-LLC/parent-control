"""Fresh child success after an ordinary Parent allowance save."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management
from journey_checks import check_balances

SCREENS = {
    **fresh_desktop('parent'),
    **parent_management(),
    'allowance-configured': 'ui:time-explanation-positive-read',
    'repeat-desktop': 'ui:desktop',
    'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    'wrong-list': 'ui:gdm-other-list',
    'wrong-focused': 'ui:gdm-other-focused',
    'wrong-refused': 'ui:gdm-child-wrong-recipient-refused',
    'wrong-returned': 'ui:gdm-navigation-returned',
    **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
}
PLAN = JourneyPlan(
    prefix='fresh-child-allowed', worker_mode='fresh_child_allowed', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in SCREENS if stage.startswith(('wrong-', 'fresh-'))}},
    advance_after={'gdm-switched': 'step-2'},
    invocations=tuple(stage for stage in SCREENS
                      if stage in fresh_desktop('parent') or stage.startswith(('wrong-', 'fresh-'))),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
    },
    assertions_after={'allowance-configured': 'positive-daily-time',
                      'wrong-refused': 'wrong-recipient-refused',
                      'fresh-desktop': 'usable-child-desktop'},
)


class FreshChildAllowedJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'allowance-configured':
            check_balances(self, observed)
