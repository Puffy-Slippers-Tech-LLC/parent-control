"""ABOUT02/03 link-only qualification; retained selector name for compatibility."""

from dataclasses import replace
from installed_journey import InstalledJourney, JourneyPlan
from parent_about import PLAN as ABOUT_PLAN


SCREEN_TAGS = {}
for stage, tag in ABOUT_PLAN.screen_tags.items():
    SCREEN_TAGS[stage] = tag
    # Link qualification has its own stages beyond the customer About read.
    if stage == 'about':
        SCREEN_TAGS['license'] = 'ui:license'
        SCREEN_TAGS['license-provider-refusals'] = 'ui:license-provider-refusals'
        SCREEN_TAGS['license-closed'] = 'ui:license-closed'

PLAN = JourneyPlan(
    prefix='license-provider', worker_mode='license_viewer_provider',
    screen_tags=SCREEN_TAGS,
    phases={**ABOUT_PLAN.phases, 'license': 'step-1',
            'license-provider-refusals': 'step-1', 'license-closed': 'step-2'},
    advance_after={'license-provider-refusals': 'step-2'},
    settings_checks=ABOUT_PLAN.settings_checks,
)


class LicenseViewerProviderJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)


WEBSITE_PLAN = replace(
    PLAN, prefix='parent-website', worker_mode='parent_website',
    screen_tags={**PLAN.screen_tags, 'license': 'ui:website-clickable',
                 'license-provider-refusals': 'ui:website-clickable'},
)


class ParentWebsiteJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, WEBSITE_PLAN)


PRIVACY_PLAN = replace(
    PLAN, prefix='parent-privacy', worker_mode='parent_privacy',
    screen_tags={**PLAN.screen_tags, 'license': 'ui:privacy-clickable',
                 'license-provider-refusals': 'ui:privacy-clickable'},
)


class ParentPrivacyJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PRIVACY_PLAN)


SUPPORT_PLAN = replace(
    PLAN, prefix='parent-support', worker_mode='parent_support',
    screen_tags={**PLAN.screen_tags, 'license': 'ui:support-clickable',
                 'license-provider-refusals': 'ui:support-clickable'},
)


class ParentSupportJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, SUPPORT_PLAN)


INFORMATION_TAGS = {}
for stage, tag in PLAN.screen_tags.items():
    if stage == 'about':
        INFORMATION_TAGS['help'] = 'ui:parent-help-clickable'
        tag = 'ui:parent-information-about'
    elif stage in ('license', 'license-provider-refusals'):
        tag = 'ui:parent-information-clickable'
    INFORMATION_TAGS[stage] = tag

INFORMATION_PLAN = replace(
    PLAN, prefix='parent-information', worker_mode='parent_information',
    screen_tags=INFORMATION_TAGS,
    phases={**PLAN.phases, 'help': 'step-1'},
)


class ParentInformationJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, INFORMATION_PLAN)
