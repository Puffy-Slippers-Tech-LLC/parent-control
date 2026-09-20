"""Functional reachability at supported scales through public automation IDs."""

import hashlib

import pytest
from tests.support.events import read_events
from tests.support.feedback import feedback_editor


pytestmark = pytest.mark.ui


def open_parent(launch_ui, ui, wait, *, environment=None):
    launch_ui(
        "parent_component_preview",
        environment_overrides=environment,
        wait_for_application=False,
    )
    wait(lambda: ui.find("parent-window") is not None, "Parent publishes its window ID")
    wait(lambda: ui.state("parent-screen-limit-toggle", ui.api.StateType.SENSITIVE),
         "Parent controls load")


@pytest.mark.parametrize("dpi_scale", (1, 1.25))
def test_parent_allowance_choices_remain_semantically_reachable(
        launch_ui, automation, wait_for_accessible_state, request_display_scale,
        dpi_scale, tmp_path):
    events = tmp_path / "events.jsonl"
    ui = automation
    open_parent(
        launch_ui, ui, wait_for_accessible_state,
        environment={"ONPC_PARENT_COMPONENT_EVENTS_PATH": str(events)},
    )
    ui.activate("parent-daily-limit-selector")
    wait_for_accessible_state(lambda: ui.showing("parent-daily-limit-1410"),
                              "last allowance choice can be revealed")
    ui.activate("parent-daily-limit-1410")
    wait_for_accessible_state(
        lambda: any(event["event"] == "set_parent_control"
                    and event["daily_limit_minutes"] == 1410
                    for event in read_events(events)),
        "last allowance choice saves",
    )
    ui.activate("parent-daily-limit-selector")
    wait_for_accessible_state(lambda: ui.showing("parent-daily-limit-custom"),
                              "custom choice can be revealed")
    ui.activate("parent-daily-limit-custom")
    wait_for_accessible_state(lambda: ui.showing("parent-custom-daily-limit"),
                              "custom editor opens")
    assert ui.state("parent-custom-daily-limit", ui.api.StateType.SENSITIVE)


@pytest.mark.parametrize("dpi_scale", (1, 1.25))
def test_parent_app_controls_and_filters_remain_reachable(
        launch_ui, automation, wait_for_accessible_state, request_display_scale,
        dpi_scale):
    from tests.support.keyboard import press_key

    ui = automation
    open_parent(launch_ui, ui, wait_for_accessible_state)
    ui.activate("parent-page-app-limits")
    wait_for_accessible_state(lambda: ui.find("parent-app-search") is not None
                              and ui.state("parent-app-search", ui.api.StateType.SENSITIVE),
                              "app catalogue loads")
    ui.activate("parent-legend-toggle")
    wait_for_accessible_state(
        lambda: ui.state("parent-legend-toggle", ui.api.StateType.PRESSED),
        "legend toggle becomes pressed",
    )
    ui.reveal("parent-legend-content")
    assert ui.showing("parent-legend-content")
    for trigger, choice in (
        ("parent-filter-match-rule", "parent-filter-match-rule-precise"),
        ("parent-filter-access-rule", "parent-filter-access-rule-permanent"),
    ):
        ui.activate(trigger)
        wait_for_accessible_state(lambda c=choice: ui.showing(c),
                                  choice + " is revealed")
        checked = ui.state(choice, ui.api.StateType.CHECKED)
        ui.activate(choice, action_name="check.toggle")
        wait_for_accessible_state(
            lambda c=choice, old=checked:
                ui.state(c, ui.api.StateType.CHECKED) != old,
            choice + " toggles",
        )
        assert ui.state(choice, ui.api.StateType.FOCUSED)
        press_key(ui, choice, "Escape", state=ui.api.StateType.FOCUSED)
        wait_for_accessible_state(lambda c=choice: ui.absent(c, within="parent-window"),
                                  choice + " menu closes")


@pytest.mark.parametrize("dpi_scale", (1, 1.25))
def test_feedback_editor_and_actions_remain_reachable(
        launch_ui, automation, wait_for_accessible_state, request_display_scale,
        dpi_scale):
    ui = automation
    open_parent(
        launch_ui, ui, wait_for_accessible_state,
        environment={"ONPC_PARENT_COMPONENT_SCENARIO": "feedback-attachments"},
    )
    ui.activate("parent-feedback-button")
    wait_for_accessible_state(lambda: ui.showing("feedback-dialog"),
                              "feedback opens")
    feedback_editor(ui, wait_for_accessible_state)
    ui.activate("feedback-format-style")
    wait_for_accessible_state(lambda: ui.showing("feedback-format-heading-2"),
                              "heading style can be revealed")
    ui.activate("feedback-format-heading-2")
    for identity in ("feedback-close", "feedback-send"):
        ui.reveal(identity)
    key = hashlib.sha256(b"sample-4.txt\0test attachment").hexdigest()[:16]
    wait_for_accessible_state(
        lambda: ui.showing(f"feedback-remove-attachment-{key}"),
        "last attachment action can be revealed",
    )
    ui.activate(f"feedback-remove-attachment-{key}")
    wait_for_accessible_state(
        lambda: ui.absent(f"feedback-attachment-{key}", within="feedback-dialog"),
        "last attachment is removed",
    )
    ui.activate("feedback-close")
    wait_for_accessible_state(lambda: ui.absent("feedback-dialog", within="parent-window"),
                              "feedback closes")


@pytest.mark.parametrize("dpi_scale", (1, 1.25))
@pytest.mark.parametrize("launcher,menu", (
    ("parent_component_preview", "parent-menu-button"),
    ("kiosk_preview", "kiosk-menu-button"),
    ("child_overlay_preview", "kiosk-menu-button"),
))
def test_about_content_remains_semantically_reachable(
        launch_ui, automation, wait_for_accessible_state, request_display_scale,
        dpi_scale, launcher, menu):
    launch_ui(launcher, wait_for_application=False)
    ui = automation
    wait_for_accessible_state(lambda: ui.find(menu) is not None,
                              "application menu publishes its ID")
    ui.activate(menu)
    about = ("parent-menu-about" if launcher == "parent_component_preview"
             else "kiosk-menu-item-about")
    wait_for_accessible_state(lambda: ui.showing(about), "About action opens")
    ui.activate(about)
    wait_for_accessible_state(lambda: ui.showing("about-dialog"), "About opens")
    ui.reveal("about-copyright")
    assert ui.text("about-copyright") == (
        "© 2026 Puffy Slippers Tech LLC\nGPL-3.0-only · No warranty."
    )
