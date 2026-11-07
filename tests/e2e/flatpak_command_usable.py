"""116b: Jordan uses system Flatpaks and keeps work in separate S instances."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, native_usable_app
from flatpak_fixtures import fixture_actions


SCREENS = {
    **fresh_desktop('parent'),
    'logout': 'system:parent-logout',
    **{'child-' + stage: tag for stage, tag in fresh_desktop('other-child').items()},
    'refusals': 'ui:flatpak-command-refusals',
}
for name, role, instance in (('allowed', 'A', 'primary'), ('hard', 'H', 'primary'),
                              ('soft', 'S', 'primary'), ('soft-second', 'S', 'secondary')):
    SCREENS.update({name + '-' + stage: tag for stage, tag in native_usable_app(
        'command', role=role, kind='flatpak', instance=instance).items()})
    SCREENS[name + '-capture'] = 'ui:flatpak-' + name + '-activity'
    if name == 'soft-second':
        SCREENS['soft-reread'] = 'ui:flatpak-soft-activity'
    if name != 'soft':
        SCREENS[name + '-close'] = 'ui:flatpak-' + name + '-close'
        SCREENS[name + '-closed'] = 'ui:flatpak-' + name + '-closed'
SCREENS.update({'soft-close': 'ui:flatpak-soft-close',
                'soft-closed': 'ui:flatpak-soft-closed'})
PLAN = JourneyPlan(
    prefix='flatpak-command-usable', worker_mode='flatpak_command_usable', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'desktop': 'native-verify'},
    invocations=tuple(stage for stage in SCREENS
                      if stage in fresh_desktop('parent') or stage.startswith('child-')),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'native-child-login': ('other-child', 'child-standard-recipient-qualified',
                               'child-standard-recipient-rechecked'),
    },
    activity_checks={'soft-second-capture': ('soft-capture', 'separate'),
                     'soft-reread': ('soft-capture', 'same')},
)


class FlatpakCommandJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN, actions=fixture_actions(include_refusal=False))
