"""Visible Parent discovery journeys for both finite E2E-003 variants."""

from account_fixture import DynamicAccountFixture, EmptyAccountFixture
from installed_journey import JourneyPlan, record_installed_journey


PLAN = JourneyPlan(
    prefix="parent-discovery", worker_mode="parent_discovery",
    screen_tags={
        "installed-greeter": "onpc-gdm-parent-installed-account",
        "recipient-qualified": "onpc-gdm-parent-masked-password",
        "desktop": "onpc-parent-desktop",
        "app-grid": "onpc-parent-app-grid",
        "parent-selected": "onpc-parent-child-selected",
        "fixture-requested": "onpc-parent-child-selected",
        "new-child-visible": "onpc-parent-new-child-choice",
        "new-child-selected": "onpc-parent-new-child-selected",
        "existing-returned": "onpc-parent-child-selected",
    },
    phases={
        "ready": "setup", "setup-detached": "setup",
        "installed-greeter": "start", "recipient-qualified": "step-1",
        "desktop": "step-1", "app-grid": "step-1", "parent-selected": "step-1",
        "fixture-requested": "step-2", "new-child-visible": "step-2",
        "new-child-selected": "step-3", "existing-returned": "step-3",
    },
    advance_after={"parent-selected": "step-2", "new-child-visible": "step-3"},
    stage_actions={"fixture-requested": "create-account"},
)

EMPTY_PLAN = JourneyPlan(
    prefix="parent-empty", worker_mode="parent_discovery_none",
    screen_tags={
        "installed-greeter": "onpc-gdm-parent-installed-account",
        "recipient-qualified": "onpc-gdm-parent-masked-password",
        "desktop": "onpc-parent-desktop",
        "app-grid": "onpc-parent-app-grid",
        "fixture-requested": "onpc-parent-app-grid",
        "empty": "onpc-parent-empty",
    },
    phases={
        "ready": "setup", "setup-detached": "setup",
        "installed-greeter": "start", "recipient-qualified": "step-1",
        "desktop": "step-1", "app-grid": "step-1",
        "fixture-requested": "step-2", "empty": "step-3",
    },
    advance_after={"app-grid": "step-2", "fixture-requested": "step-3"},
    stage_actions={"fixture-requested": "prepare-empty"},
)


def execute(recorder, context):
    fixture = DynamicAccountFixture(context)
    record_installed_journey(
        recorder, context, PLAN, actions={"create-account": fixture.create},
    )


def execute_empty(recorder, context):
    fixture = EmptyAccountFixture(context)
    record_installed_journey(
        recorder, context, EMPTY_PLAN,
        actions={"prepare-empty": fixture.prepare},
    )


E2E_CASES = {"existing-and-new": execute, "none": execute_empty}
