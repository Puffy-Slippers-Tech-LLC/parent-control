"""E2E-004/app-grid's standard-user actions and visible expectations."""

from installed_journey import InstalledJourney, JourneyPlan, record_installed_journey


PLAN = JourneyPlan(
    prefix="parent-access", worker_mode="parent_access",
    review_mode="parent_access_review",
    screen_tags={
        "installed-greeter": "onpc-gdm-parent-installed-account",
        "recipient-qualified": "onpc-gdm-other-child-masked-password",
        "desktop": "onpc-parent-desktop",
        "app-grid": "onpc-parent-app-grid",
        "unavailable": "onpc-parent-standard-unavailable",
    },
    phases={
        "ready": "setup", "setup-detached": "setup",
        "installed-greeter": "start", "recipient-qualified": "step-1",
        "desktop": "step-1", "app-grid": "step-1",
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
