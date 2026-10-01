"""035: verified native command launch, independently observed ordinary use."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop
from native_fixtures import fixture_actions


ENTRY = {
    'desktop': 'ui:native-desktop',
    'command': 'ui:native-command-launch',
    'opened': 'ui:native-opened',
    'submit': 'ui:native-submit',
    'submitted': 'ui:native-submitted',
    'close': 'ui:native-close',
    'closed': 'ui:native-closed',
}
SCREENS = {
    **fresh_desktop('parent'),
    'logout': 'system:parent-logout',
    **{'child-' + stage: tag for stage, tag in fresh_desktop('other-child').items()},
    'wrong-entry': 'ui:native-wrong-entry',
    **{'first-' + stage: tag for stage, tag in ENTRY.items()},
    'repeat-wrong-entry': 'ui:native-wrong-entry',
    'repeat-refusals': 'ui:native-command-refusals',
    **{'repeat-' + stage: tag for stage, tag in ENTRY.items()},
}
PLAN = JourneyPlan(
    prefix='native-app', worker_mode='native_app', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in SCREENS
               if stage.startswith('repeat-') or stage in ('first-close', 'first-closed')}},
    advance_after={'first-submitted': 'step-2'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    invocations=tuple(stage for stage in SCREENS
                      if stage in fresh_desktop('parent') or stage.startswith('child-')),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'native-child-login': ('other-child', 'child-standard-recipient-qualified',
                               'child-standard-recipient-rechecked'),
    },
)


class NativeAppJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
                         actions=fixture_actions() if actions is None else actions)
