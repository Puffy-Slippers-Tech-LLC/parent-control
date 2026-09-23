"""ABOUT02/03 fixed installed viewer qualification."""

from installed_journey import InstalledJourney, JourneyPlan
from parent_about import PLAN as ABOUT_PLAN


SCREEN_TAGS = {}
for stage, tag in ABOUT_PLAN.screen_tags.items():
    if stage == 'license':
        for kind in ('unrelated', 'empty'):
            for phase in ('launched', 'ready', 'closed'):
                operation = 'license-' + kind + '-' + phase
                SCREEN_TAGS[operation] = 'ui:' + operation
        SCREEN_TAGS['about-rechecked'] = 'ui:about-rechecked'
    SCREEN_TAGS[stage] = tag
    if stage == 'license':
        for phase in ('launched', 'ready', 'closed'):
            operation = 'license-ambiguous-' + phase
            SCREEN_TAGS[operation] = 'ui:' + operation
        SCREEN_TAGS['license-provider-refusals'] = 'ui:license-provider-refusals'

PLAN = JourneyPlan(
    prefix='license-provider', worker_mode='license_viewer_provider',
    screen_tags=SCREEN_TAGS,
    phases={**ABOUT_PLAN.phases,
            **{'license-' + kind + '-' + phase: 'step-1'
               for kind in ('unrelated', 'empty')
               for phase in ('launched', 'ready', 'closed')},
            'about-rechecked': 'step-1',
            **{'license-ambiguous-' + phase: 'step-1'
               for phase in ('launched', 'ready', 'closed')},
            'license-provider-refusals': 'step-1'},
    advance_after={'license-provider-refusals': 'step-2'},
    settings_checks=ABOUT_PLAN.settings_checks,
)


class LicenseViewerProviderJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
