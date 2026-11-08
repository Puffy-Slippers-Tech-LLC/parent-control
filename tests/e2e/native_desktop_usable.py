"""036g: exact per-child desktop placement, DING activation and real app use."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, native_usable_app, prefixed_stages
from native_fixtures import fixture_actions
from synthetic_files import desktop_entry_actions


SCREENS = {
    **fresh_desktop('parent'), 'logout': 'system:parent-logout',
    **prefixed_stages('child', fresh_desktop('other-child')),
}
for entry in ('first', 'independent'):
    SCREENS.update({
        entry + '-place': 'ui:standard-desktop',
        **prefixed_stages(entry, native_usable_app('desktop')),
        entry + '-close': 'ui:native-close', entry + '-closed': 'ui:native-closed',
        entry + '-cleanup': 'ui:standard-desktop',
    })
SCREENS['first-icon'] = 'ui:native-desktop-icon-refusals'
SCREENS['child-logout'] = 'system:standard-logout'
PLAN = JourneyPlan(
    prefix='native-desktop-usable', worker_mode='native_desktop_usable', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'desktop': 'native-verify',
                   **{entry + '-place': 'desktop-place' for entry in ('first', 'independent')},
                   **{entry + '-cleanup': 'desktop-cleanup' for entry in ('first', 'independent')}},
    invocations=tuple(stage for stage in SCREENS
                      if stage in fresh_desktop('parent') or stage.startswith('child-')
                      and stage != 'child-logout'),
    challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
                'native-child-login': ('other-child', 'child-standard-recipient-qualified',
                                       'child-standard-recipient-rechecked')},
)


class NativeDesktopJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN, actions={
            **fixture_actions(include_refusal=False), **desktop_entry_actions()})
