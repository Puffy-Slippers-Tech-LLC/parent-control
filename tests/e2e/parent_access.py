"""E2E-004/app-grid's standard-user actions and visible expectations."""

from installed_journey import InstalledJourney, JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop


PLAN = JourneyPlan(
    prefix="parent-access", worker_mode="parent_access",
    review_mode="parent_access_review",
    screen_tags={
        **fresh_desktop('other-child'),
        "system-prompt": "ui:standard-system-prompt",
        "app-grid": "ui:standard-app-grid",
        "search-focused": "ui:standard-search-focused",
        "search-started": "ui:standard-search-started",
        "search-entered": "ui:standard-search-entered",
        "unavailable": "ui:standard-parent-unavailable",
    },
    phases={
        "ready": "setup", "setup-detached": "setup",
        "installed-greeter": "start", "other-parent-focused": "step-1",
        "wrong-recipient-refused": "step-1", "standard-list": "step-1",
        "standard-focused": "step-1", "standard-recipient-qualified": "step-1",
        "standard-recipient-rechecked": "step-1",
        "desktop": "step-1", "system-prompt": "step-1", "app-grid": "step-1",
        "search-focused": "step-2",
        "search-started": "step-2",
        "search-entered": "step-2",
        "unavailable": "step-2",
    },
    advance_after={"app-grid": "step-2"},
)


class ParentAccessJourney(InstalledJourney):
    def __init__(self, context, progress, *, review=False):
        super().__init__(context, progress, PLAN, review=review)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN)


E2E_CASES = {"app-grid": execute}
