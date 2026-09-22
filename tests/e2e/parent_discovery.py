"""Visible Parent discovery journeys for both finite E2E-003 variants."""

from account_fixture import DynamicAccountFixture, EmptyAccountFixture
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_search
from ui_observations import SettingsObservation


PLAN = JourneyPlan(
    prefix="parent-discovery", worker_mode="parent_discovery",
    screen_tags={
        **fresh_desktop('parent'),
        **parent_search(),
        "parent-window": "ui:parent-window",
        "child-picker-opened": "ui:discovery-child-picker-opened",
        "child-choice-highlighted": "ui:discovery-child-choice-highlighted",
        "parent-selected": "ui:discovery-selected",
        "existing-apps": "ui:existing-apps",
        "fixture-requested": "ui:discovery-ready",
        "new-child-visible": "ui:new-child-picker-opened",
        "new-child-choice-highlighted": "ui:new-child-choice-highlighted",
        "new-child-selected": "ui:new-child-selected",
        "new-child-apps": "ui:new-child-apps",
        "new-child-screen": "ui:new-child-screen",
        "existing-child-picker-opened": "ui:existing-child-picker-opened",
        "existing-child-choice-highlighted": "ui:existing-child-choice-highlighted",
        "existing-returned": "ui:existing-returned",
    },
    phases={
        "ready": "setup", "setup-detached": "setup",
        "installed-greeter": "start", "recipient-qualified": "step-1",
        "other-parent-focused": "step-1", "wrong-recipient-refused": "step-1",
        "parent-list": "step-1", "parent-focused": "step-1", "recipient-rechecked": "step-1",
        "desktop": "step-1", "app-grid": "step-1", "parent-selected": "step-1",
        "search-ready": "step-1", "search-focused": "step-1", "search-entered": "step-1",
        "parent-window": "step-1",
        "child-picker-opened": "step-1", "child-choice-highlighted": "step-1",
        "existing-apps": "step-1",
        "fixture-requested": "step-2", "new-child-visible": "step-2",
        "new-child-selected": "step-3", "existing-returned": "step-3",
        "new-child-choice-highlighted": "step-3", "new-child-apps": "step-3",
        "new-child-screen": "step-3", "existing-child-picker-opened": "step-3",
        "existing-child-choice-highlighted": "step-3",
    },
    advance_after={"installed-greeter": "step-1", "existing-apps": "step-2", "new-child-visible": "step-3"},
    stage_actions={"fixture-requested": "create-account"},
    settings_checks={
        "parent-selected": SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        "fixture-requested": "parent-selected",
        "new-child-screen": "new-child-selected",
        "existing-returned": "parent-selected",
    },
)

EMPTY_PLAN = JourneyPlan(
    prefix="parent-empty", worker_mode="parent_discovery_none",
    screen_tags={
        **fresh_desktop('parent'),
        **parent_search(),
        "fixture-requested": "ui:app-grid",
        "empty": "ui:parent-empty",
    },
    phases={
        "ready": "setup", "setup-detached": "setup",
        "installed-greeter": "start", "recipient-qualified": "step-1",
        "other-parent-focused": "step-1", "wrong-recipient-refused": "step-1",
        "parent-list": "step-1", "parent-focused": "step-1", "recipient-rechecked": "step-1",
        "desktop": "step-1", "app-grid": "step-1",
        "search-ready": "step-1", "search-focused": "step-1", "search-entered": "step-1",
        "fixture-requested": "step-2", "empty": "step-3",
    },
    advance_after={"installed-greeter": "step-1", "app-grid": "step-2", "fixture-requested": "step-3"},
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
