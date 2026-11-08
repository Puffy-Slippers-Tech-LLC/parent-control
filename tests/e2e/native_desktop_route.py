"""036b: a Parent block closes child work and denies its desktop relaunch."""
from dataclasses import replace

from journey_blocks import native_blocked_app, native_usable_app, prefixed_stages
from native_fixtures import fixture_actions
from native_policy_closure import PLAN as CLOSURE_PLAN, NativePolicyClosureJourney
from synthetic_files import desktop_entry_actions


# Reuse the qualified policy saves, child returns and immutable closure checks.
# Each round independently places and removes the child's trusted desktop entry.
SCREENS = {}
for stage, tag in CLOSURE_PLAN.screen_tags.items():
    name = stage.split('-', 1)[0]
    if name in ('hard', 'soft') and stage.startswith(name + '-activity-'):
        if stage == name + '-activity-desktop':
            activity = native_usable_app('desktop')
            if name == 'hard':
                activity['icon'] = 'ui:native-desktop-icon-refusals'
            SCREENS[name + '-place'] = 'ui:standard-desktop'
            SCREENS.update(prefixed_stages(name + '-activity', activity))
    elif name in ('hard', 'soft') and stage == name + '-denied-command':
        SCREENS.update(prefixed_stages(name + '-denied', native_blocked_app('A', route='desktop')))
    else:
        if name in ('hard', 'soft') and stage == name + '-logout':
            SCREENS[name + '-cleanup'] = 'ui:standard-desktop'
        SCREENS[stage] = tag

PLAN = replace(
    CLOSURE_PLAN, prefix='native-desktop-route', worker_mode='native_desktop_route',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={**CLOSURE_PLAN.stage_actions,
                   **{name + '-place': 'desktop-place' for name in ('hard', 'soft')},
                   **{name + '-cleanup': 'desktop-cleanup' for name in ('hard', 'soft')}},
)


class NativeDesktopRouteJourney(NativePolicyClosureJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN, actions={
            **fixture_actions(include_refusal=False), **desktop_entry_actions()})
