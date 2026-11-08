"""036a: a parent's Hard/Soft save closes work and denies reopening from Files."""
from dataclasses import replace

from journey_blocks import native_blocked_app, native_usable_app, prefixed_stages
from native_policy_closure import PLAN as CLOSURE_PLAN, NativePolicyClosureJourney


# Keep the qualified policy/entry/immutable-closure composition. Replace only
# its launch routes; Files is dismissed before switching desktops or using N.
SCREENS = {}
for stage, tag in CLOSURE_PLAN.screen_tags.items():
    name = stage.split('-', 1)[0]
    if name in ('hard', 'soft') and stage.startswith(name + '-activity-'):
        if stage == name + '-activity-desktop':
            activity = {'desktop': 'ui:native-desktop', **native_usable_app('files'),
                        'dismiss': 'ui:native-files-allowed-dismiss'}
            if name == 'hard':
                activity['files'] = 'ui:native-files-allowed-launch-refusals'
            SCREENS.update(prefixed_stages(name + '-activity', activity))
    elif name in ('hard', 'soft') and stage == name + '-denied-command':
        SCREENS.update(prefixed_stages(name + '-denied', {
            **native_blocked_app('A', route='files'),
            'dismiss': 'ui:native-files-allowed-dismiss'}))
    else:
        SCREENS[stage] = tag

PLAN = replace(
    CLOSURE_PLAN, prefix='native-files-routes', worker_mode='native_files_routes',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
)


class NativeFilesRoutesJourney(NativePolicyClosureJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
