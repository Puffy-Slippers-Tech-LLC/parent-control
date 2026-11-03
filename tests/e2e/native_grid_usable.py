"""035c: native Allowed fixture, grid launch and ordinary public draft submission."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, native_usable_app


ENTRY = {
    **native_usable_app('grid'),
    'close': 'ui:native-close',
    'closed': 'ui:native-closed',
}
SCREENS = {
    **fresh_desktop('other-child'),
    'wrong-entry': 'ui:native-wrong-entry',
    **{'first-' + stage: tag for stage, tag in ENTRY.items()},
    'repeat-wrong-entry': 'ui:native-wrong-entry',
    **{'repeat-' + stage: tag for stage, tag in ENTRY.items()
       if stage not in ('app-grid', 'opened', 'submit', 'submitted', 'close', 'closed')},
    'repeat-refusals': 'ui:native-grid-refusals',
    **{'repeat-' + stage: tag for stage, tag in ENTRY.items()
       if stage in ('app-grid', 'opened', 'submit', 'submitted', 'close', 'closed')},
}
PLAN = JourneyPlan(
    prefix='native-grid-usable', worker_mode='native_grid_usable', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in SCREENS
               if stage.startswith('repeat-') or stage in ('first-close', 'first-closed')}},
    advance_after={'first-submitted': 'step-2'},
)


class NativeGridJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
