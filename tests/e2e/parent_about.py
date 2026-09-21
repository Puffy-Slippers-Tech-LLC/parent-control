"""E2E-030/parent's visible expectations and recorder phase boundaries."""

from installed_journey import (
    InstalledJourney, JourneyPlan, matched_screens as reconcile_screens, record_installed_journey,
)

SCREEN_TAGS = {
    'installed-greeter': 'ui:gdm-other-list',
    'other-parent-focused': 'ui:gdm-other-focused',
    'wrong-recipient-refused': 'ui:gdm-wrong-recipient-refused',
    'parent-list': 'ui:gdm-list', 'parent-focused': 'ui:gdm-focused',
    'recipient-qualified': 'ui:gdm-parent-recipient',
    'recipient-rechecked': 'ui:gdm-parent-recipient-rechecked',
    'desktop': 'ui:desktop',
    'search-ready': 'ui:parent-search-ready',
    'search-focused': 'ui:parent-search-focused',
    'search-entered': 'ui:parent-search-entered',
    'app-grid': 'ui:app-grid', 'parent-window': 'ui:parent-window',
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
        'other-parent-focused': 'step-1', 'wrong-recipient-refused': 'step-1',
        'parent-list': 'step-1', 'parent-focused': 'step-1',
        'recipient-qualified': 'step-1', 'recipient-rechecked': 'step-1',
        'desktop': 'step-1', 'app-grid': 'step-1',
        'search-ready': 'step-1', 'search-focused': 'step-1', 'search-entered': 'step-1',
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
