"""Direct overlay entry, normal panel discovery and deliberate singleton launch."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management, overlay_entry
from journey_checks import check_balances

SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-positive-read',
    'wrong-account-refused': 'ui:overlay-wrong-account-refused',
    'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
    **overlay_entry('direct', 'command'),
    'direct-cancel': 'ui:overlay-qualification-cancel',
    'independent-desktop': 'ui:overlay-desktop',
    **overlay_entry('independent', 'command'),
    'independent-cancel': 'ui:overlay-qualification-cancel',
    'panel-desktop': 'ui:overlay-desktop',
    **overlay_entry('panel', 'panel'),
    **overlay_entry('singleton', 'panel-reopen'),
    'panel-cancel': 'ui:overlay-qualification-cancel',
    'closed-desktop': 'ui:overlay-desktop',
}
PLAN = JourneyPlan(
    prefix='shell-panel', worker_mode='shell_panel', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in list(SCREENS)[list(SCREENS).index('fresh-installed-greeter'):]}},
    advance_after={'gdm-switched': 'step-2'},
    invocations=tuple(stage for stage in SCREENS if stage in fresh_desktop('parent')
                      or stage.startswith('fresh-')
                      or stage in list(SCREENS)[list(SCREENS).index('direct-launch'):]),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
    },
    assertions_after={
        'allowance-configured': 'positive-daily-time',
        'wrong-account-refused': 'wrong-account-refused',
        'direct-form': 'direct-single-fixed-child-form',
        'independent-form': 'independent-single-fixed-child-form',
        'singleton-form': 'panel-single-fixed-child-form',
        'closed-desktop': 'qualification-closed',
    },
)


class ShellPanelJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'allowance-configured':
            check_balances(self, observed)
