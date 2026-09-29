"""ABOUT02/03 link-only qualification; retained selector name for compatibility."""

from installed_journey import InstalledJourney, JourneyPlan
from parent_about import PLAN as ABOUT_PLAN


SCREEN_TAGS = {}
for stage, tag in ABOUT_PLAN.screen_tags.items():
    SCREEN_TAGS[stage] = tag
    if stage == 'license':
        SCREEN_TAGS['license-provider-refusals'] = 'ui:license-provider-refusals'

PLAN = JourneyPlan(
    prefix='license-provider', worker_mode='license_viewer_provider',
    screen_tags=SCREEN_TAGS,
    phases={**ABOUT_PLAN.phases, 'license-provider-refusals': 'step-1'},
    advance_after={'license-provider-refusals': 'step-2'},
    settings_checks=ABOUT_PLAN.settings_checks,
)


class LicenseViewerProviderJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
