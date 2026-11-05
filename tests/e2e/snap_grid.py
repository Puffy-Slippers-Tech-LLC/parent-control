"""109a: allowed Snap grid use, new window and preserved original activity."""
from installed_journey import JourneyPlan
from journey_blocks import app_policy_entry, fresh_desktop, native_usable_app, prefixed_stages
from snap_fixtures import SnapFixtureJourney
from private_artifacts import require


SCREENS = {
    **app_policy_entry(child='existing', allowance=None, initial_rows=False),
    'app-rows': 'ui:existing-parent-app-rows',
    'logout': 'system:parent-logout',
    **prefixed_stages('child', fresh_desktop('other-child')),
}
for name, role, route, instance in (
        ('allowed', 'A', 'grid', 'primary'), ('hard', 'H', 'grid', 'primary'),
        ('earlier', 'S', 'command', 'secondary'), ('soft', 'S', 'grid', 'primary')):
    SCREENS.update({name + '-' + stage: tag for stage, tag in native_usable_app(
        route, kind='snap', role=role, instance=instance).items()})
    binding = 'soft-second' if name == 'earlier' else name
    SCREENS[name + '-capture'] = 'ui:snap-' + binding + '-activity'
    if name == 'allowed':
        SCREENS['refusals'] = 'ui:snap-grid-refusals'
    if name == 'soft':
        SCREENS['earlier-reread'] = 'ui:snap-soft-second-activity'
    if name != 'earlier':
        SCREENS[name + '-close'] = 'ui:snap-' + binding + '-close'
        SCREENS[name + '-closed'] = 'ui:snap-' + binding + '-closed'
SCREENS['earlier-close'] = 'ui:snap-soft-second-close'
SCREENS['earlier-closed'] = 'ui:snap-soft-second-closed'
PLAN = JourneyPlan(
    prefix='snap-grid', worker_mode='snap_grid', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    invocations=tuple((*fresh_desktop('parent'),
                       *prefixed_stages('child', fresh_desktop('other-child')))),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'native-child-login': ('other-child', 'child-standard-recipient-qualified',
                               'child-standard-recipient-rechecked'),
    },
    activity_checks={'earlier-reread': ('earlier-capture', 'same')},
)


class SnapGridJourney(SnapFixtureJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)

    def check_activity(self, stage, observed):
        super().check_activity(stage, observed)
        if stage == 'soft-capture':
            first = self.activity_observations['earlier-capture']
            second = self.activity_observations[stage]
            require(first.pid != second.pid and first.endpoint != second.endpoint,
                    'snap:grid-separate-window')
            observed['comparison'] = {'separate_window': True, 'outcome': 'passed'}
