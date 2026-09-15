"""E2E-030/parent's visible expectations and recorder phase boundaries."""

from installed_journey import (
    InstalledJourney, JourneyPlan, matched_screens as reconcile_screens, record_installed_journey,
)

SCREEN_TAGS = {
    'installed-greeter': 'onpc-gdm-parent-installed-account',
    'recipient-qualified': 'onpc-gdm-parent-masked-password',
    'desktop': 'onpc-parent-desktop', 'app-grid': 'onpc-parent-app-grid',
    'parent-selected': 'onpc-parent-child-selected', 'about': 'onpc-parent-about',
    'license': 'onpc-parent-license', 'about-returned': 'onpc-parent-about-legal',
    'parent-returned': 'onpc-parent-child-selected',
}
PLAN = JourneyPlan(
    prefix='parent', worker_mode='parent_about', review_mode='parent_review',
    screen_tags=SCREEN_TAGS,
    phases={
        'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
        'recipient-qualified': 'step-1', 'desktop': 'step-1', 'app-grid': 'step-1',
        'parent-selected': 'step-1', 'about': 'step-1', 'license': 'step-1',
        'about-returned': 'step-2', 'parent-returned': 'step-2',
    },
    # The reply permits closing LICENSE. Open the return phase before that input.
    advance_after={'license': 'step-2'},
)
STAGES = PLAN.stages


class ParentJourney(InstalledJourney):
    """The same plan is available to the fixed diagnostic qualification."""

    def __init__(self, context, progress, *, review=False):
        super().__init__(context, progress, PLAN, review=review)


def matched_screens(directory):
    return reconcile_screens(directory, PLAN)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN)


E2E_CASES = {'parent': execute}
