"""E2E-030/parent's visible expectations and recorder phase boundaries."""

from installed_journey import (
    InstalledJourney, JourneyPlan, matched_screens as reconcile_screens, record_installed_journey,
)
from journey_blocks import fresh_desktop

SCREEN_TAGS = {
    **fresh_desktop('parent'),
    'parent-command': 'ui:parent-command-launch',
    'parent-window': 'ui:parent-window',
    'child-picker-opened': 'ui:child-picker-opened',
    'child-choice-highlighted': 'ui:child-choice-highlighted',
    'parent-selected': 'ui:parent-selected', 'about': 'ui:about',
    'license': 'ui:license', 'license-closed': 'ui:license-closed',
    'about-returned': 'ui:about-returned',
    'parent-returned': 'ui:parent-returned',
}
PLAN = JourneyPlan(
    prefix='parent', worker_mode='parent_about', review_mode='parent_review',
    screen_tags=SCREEN_TAGS,
    phases={
        'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
        'parent-focused': 'step-1',
        'recipient-qualified': 'step-1', 'recipient-rechecked': 'step-1',
        'desktop': 'step-1', 'parent-command': 'step-1',
        'parent-window': 'step-1', 'child-picker-opened': 'step-1',
        'child-choice-highlighted': 'step-1',
        'parent-selected': 'step-1', 'about': 'step-1', 'license': 'step-1',
        'license-closed': 'step-2', 'about-returned': 'step-2', 'parent-returned': 'step-2',
    },
    # The reply permits closing LICENSE. Open the return phase before that input.
    advance_after={'license': 'step-2'},
    settings_checks={'parent-returned': 'parent-selected'},
)
STAGES = PLAN.stages


class ParentJourney(InstalledJourney):
    """The same plan is available to the fixed diagnostic qualification."""

    def __init__(self, context, progress, *, review=False):
        super().__init__(context, progress, PLAN, review=review)


def matched_screens(directory, observations=()):
    return reconcile_screens(directory, PLAN, observations)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN)


E2E_CASES = {'parent': execute}
