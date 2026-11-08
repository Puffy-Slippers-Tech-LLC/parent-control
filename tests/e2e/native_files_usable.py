"""036f: exact Files activation and a distinct window preserving original work."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, native_usable_app
from native_fixtures import fixture_actions


SCREENS = {
    **fresh_desktop('parent'),
    'logout': 'system:parent-logout',
    **{'child-' + stage: tag for stage, tag in fresh_desktop('other-child').items()},
    **{'first-' + stage: tag for stage, tag in native_usable_app('files').items()},
    'first-dismiss': 'ui:native-files-allowed-dismiss',
    'first-close': 'ui:native-files-allowed-close',
    'first-closed': 'ui:native-files-allowed-closed',
    **{'earlier-' + stage: tag for stage, tag in native_usable_app('command', role='S').items()},
    'earlier-capture': 'ui:native-unmatched-soft-activity',
    'second-desktop': 'ui:standard-desktop',
    **{'second-' + stage: tag for stage, tag in native_usable_app(
        'files', role='S', desktop_observation=False).items()},
    'second-dismiss': 'ui:native-files-soft-dismiss',
    'second-capture': 'ui:native-files-soft-activity',
    'earlier-reread': 'ui:native-unmatched-soft-activity',
    'second-close': 'ui:native-files-soft-close',
    'second-closed': 'ui:native-files-soft-closed',
    'earlier-close': 'ui:native-unmatched-soft-close',
    'earlier-closed': 'ui:native-unmatched-soft-closed',
    'child-logout': 'system:standard-logout',
}
PLAN = JourneyPlan(
    prefix='native-files-usable', worker_mode='native_files_usable', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    invocations=tuple(stage for stage in SCREENS
                      if stage in fresh_desktop('parent') or stage.startswith('child-')
                      and stage != 'child-logout'),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'native-child-login': ('other-child', 'child-standard-recipient-qualified',
                               'child-standard-recipient-rechecked'),
    },
    activity_checks={'second-capture': ('earlier-capture', 'separate'),
                     'earlier-reread': ('earlier-capture', 'same')},
)


class NativeFilesJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN, actions=fixture_actions())
