"""Five-second TIME03 slice; complete consumer scenarios remain separate."""
from copy import deepcopy

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management
from private_artifacts import require
from real_interval import interval_action

SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'parent-window': 'ui:about-interval-refused',
    'about': 'ui:about',
    'before': 'ui:about-interval-read',
    'after': 'ui:about-interval-read',
}
PLAN = JourneyPlan(
    prefix='real-interval', worker_mode='real_interval', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'before': 'real-interval'},
)


class RealIntervalJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
                         actions=actions or {'real-interval': interval_action(5)})
        self.about_before = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if observed.get('ui', {}).get('operation') != 'about-interval-read':
            return
        current = observed['ui']['about_interval']
        if self.about_before is None:
            self.about_before = deepcopy(current)
        else:
            require(current == self.about_before, 'time03:about-window-changed')
