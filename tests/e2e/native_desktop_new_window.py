"""036h: desktop activation opens another S window and preserves original work."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, prefixed_stages
from native_fixtures import fixture_actions
from synthetic_files import desktop_entry_actions


SCREENS = {
    **fresh_desktop('parent'), 'logout': 'system:parent-logout',
    **prefixed_stages('child', fresh_desktop('other-child')),
    'place': 'ui:standard-desktop',
}
for entry in ('first', 'independent'):
    SCREENS.update({
        entry + '-earlier-command': 'ui:native-soft-primary-command-launch',
        **{entry + '-earlier-' + action: 'ui:native-soft-primary-' + action
           for action in ('opened', 'submit', 'submitted')},
        entry + '-earlier-capture': 'ui:native-soft-primary-activity',
        entry + '-second-icon': 'ui:native-soft-desktop-icon',
        entry + '-second-selected': 'ui:native-soft-desktop-selected',
        **{entry + '-second-' + action: 'ui:native-soft-secondary-' + action
           for action in ('opened', 'submit', 'submitted')},
        entry + '-second-capture': 'ui:native-soft-secondary-activity',
        entry + '-earlier-reread': 'ui:native-soft-primary-activity',
        **{entry + '-' + window + '-' + action: 'ui:native-soft-' + instance + '-' + action
           for window, instance in (('second', 'secondary'), ('earlier', 'primary'))
           for action in ('close', 'closed')},
    })
SCREENS.update({'cleanup': 'ui:standard-desktop', 'child-logout': 'system:standard-logout'})
PLAN = JourneyPlan(
    prefix='native-desktop-new-window', worker_mode='native_desktop_new_window', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'desktop': 'native-verify', 'place': 'desktop-place', 'cleanup': 'desktop-cleanup'},
    invocations=tuple(stage for stage in SCREENS
                      if stage in fresh_desktop('parent') or stage.startswith('child-')
                      and stage != 'child-logout'),
    challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
                'native-child-login': ('other-child', 'child-standard-recipient-qualified',
                                       'child-standard-recipient-rechecked')},
    activity_checks={**{entry + '-second-capture': (entry + '-earlier-capture', 'separate')
                       for entry in ('first', 'independent')},
                     **{entry + '-earlier-reread': (entry + '-earlier-capture', 'same')
                        for entry in ('first', 'independent')}},
)


class NativeDesktopNewWindowJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN, actions={
            **fixture_actions(include_refusal=False), **desktop_entry_actions(role='S')})
