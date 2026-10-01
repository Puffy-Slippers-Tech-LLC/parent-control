"""047: native usable flows and explicit immutable activity comparisons."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, native_usable_app
from native_fixtures import fixture_actions


SCREENS = {
    **fresh_desktop('parent'),
    'logout': 'system:parent-logout',
    **{'child-' + stage: tag for stage, tag in fresh_desktop('other-child').items()},
    'wrong-entry': 'ui:native-activity-wrong-entry',
    **{'command-' + stage: tag for stage, tag in native_usable_app('command').items()},
    'command-capture': 'ui:native-activity',
    'command-reread': 'ui:native-activity',
    'command-close': 'ui:native-close',
    'command-closed': 'ui:native-closed',
    'repeat-wrong-entry': 'ui:native-activity-wrong-entry',
    **{'grid-' + stage: tag for stage, tag in native_usable_app('grid').items()},
    'grid-replacement-refused': 'ui:native-activity',
    'grid-capture': 'ui:native-activity',
    'grid-reread': 'ui:native-activity',
    'grid-close': 'ui:native-close',
    'grid-closed': 'ui:native-closed',
}
PLAN = JourneyPlan(
    prefix='app-activity', worker_mode='app_activity', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in SCREENS
               if stage.startswith('grid-') or stage.startswith('repeat-')
               or stage in ('command-close', 'command-closed')}},
    advance_after={'command-reread': 'step-2'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    invocations=tuple(stage for stage in SCREENS
                      if stage in fresh_desktop('parent') or stage.startswith('child-')),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'native-child-login': ('other-child', 'child-standard-recipient-qualified',
                               'child-standard-recipient-rechecked'),
    },
    activity_checks={
        'command-reread': ('command-capture', 'same'),
        'grid-replacement-refused': ('command-capture', 'replaced'),
        'grid-reread': ('grid-capture', 'same'),
    },
)


class NativeActivityJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
                         actions=fixture_actions() if actions is None else actions)
