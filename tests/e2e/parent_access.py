"""E2E-004/app-grid's standard-user actions and visible expectations."""

from installed_journey import InstalledJourney, JourneyPlan, record_installed_journey


PLAN = JourneyPlan(
    prefix="parent-access", worker_mode="parent_access",
    review_mode="parent_access_review",
    screen_tags={
        "installed-greeter": "ui:gdm-other-list",
        "other-parent-focused": "ui:gdm-other-focused",
        "wrong-recipient-refused": "ui:gdm-standard-wrong-recipient-refused",
        "standard-list": "ui:gdm-standard-list",
        "standard-focused": "ui:gdm-standard-focused",
        "standard-recipient-qualified": "ui:gdm-standard-recipient",
        "standard-recipient-rechecked": "ui:gdm-standard-recipient-rechecked",
        "desktop": "ui:standard-desktop",
        "system-prompt": "ui:standard-system-prompt",
        "app-grid": "ui:standard-app-grid",
        "search-focused": "ui:standard-search-focused",
        "search-started": "ui:standard-search-started",
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
