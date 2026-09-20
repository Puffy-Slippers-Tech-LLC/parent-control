"""The real shared feedback UI in parent, child-overlay and kiosk contexts."""

import pytest

from tests.support.feedback import dismiss_feedback_dialog, feedback_editor
from tests.support.request_form import launch_request, events


pytestmark = pytest.mark.ui


def wait_for_error_draft(ui, wait):
    editor = feedback_editor(ui, wait)
    wait(lambda: "Error categories: RuntimeError" in ui.content(editor),
         "error draft loaded")
    value = ui.content(editor)
    assert value.startswith("Something went wrong\nThe operation could not be completed.")
    return editor, value


def test_child_panel_stdin_entry_opens_a_prefilled_report(
        launch_ui, automation, wait_for_accessible_state):
    launch_ui("child_error_preview", wait_for_application=False)
    ui = automation
    wait_for_accessible_state(lambda: ui.showing("feedback-dialog"),
                              "child error report opens")
    _editor, value = wait_for_error_draft(ui, wait_for_accessible_state)
    assert "child panel could not refresh its timer" not in value
    assert ui.state("feedback-add-files", ui.api.StateType.SENSITIVE)


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_request_error_review_restrictions_and_submission(
        launch_ui, automation, wait_for_accessible_state, tmp_path, overlay):
    ui = automation
    _process, path = launch_request(
        launch_ui, tmp_path, overlay=overlay, scenario="service-failure",
        wait_for_application=False,
    )
    wait_for_accessible_state(lambda: ui.find("kiosk-request-submit") is not None,
                              "request controls publish IDs")
    wait_for_accessible_state(
        lambda: ui.state("kiosk-request-submit", ui.api.StateType.SENSITIVE),
        "request is ready",
    )
    ui.activate("kiosk-request-submit")
    wait_for_accessible_state(lambda: ui.find("kiosk-report-toggle") is not None,
                              "error result publishes reporting choice")
    assert ui.state("kiosk-report-toggle", ui.api.StateType.CHECKED)
    ui.activate("kiosk-result-action")
    wait_for_accessible_state(lambda: ui.showing("feedback-dialog"),
                              "error feedback opens")
    editor, value = wait_for_error_draft(ui, wait_for_accessible_state)
    assert "org.example.Secret" not in value
    assert "/private/path" not in value
    assert not events(path, "feedback")
    assert not events(path, "close_overlay" if overlay else "logout")
    for identity in ("feedback-add-files", "feedback-download-logs", "feedback-format-attachment"):
        assert (ui.showing(identity) if overlay
                else ui.absent(identity, within="feedback-dialog"))
    ui.activate("feedback-privacy-link")
    wait_for_accessible_state(lambda: ui.showing("feedback-privacy-dialog"),
                              "privacy explanation opens")
    assert (ui.showing("feedback-full-privacy-link") if overlay
            else ui.absent("feedback-full-privacy-link", within="feedback-privacy-dialog"))
    dismiss_feedback_dialog(ui, wait_for_accessible_state, "feedback-privacy-dialog",
                            within="feedback-dialog")
    ui.activate("feedback-toggle-logs")
    ui.activate("feedback-toggle-logs")
    assert (ui.showing("feedback-download-logs") if overlay
            else ui.absent("feedback-download-logs", within="feedback-dialog"))
    wait_for_accessible_state(lambda: ui.state("feedback-send", ui.api.StateType.SENSITIVE),
                              "error report is ready")
    ui.activate("feedback-send")
    wait_for_accessible_state(lambda: ui.showing("feedback-success-dialog"),
                              "feedback confirmation opens")
    component = "Child App" if overlay else "Kiosk App"
    assert events(path, "feedback")[0]["subject"] == (
        f"[Oh No! Parent Control] [{component}] Error Report"
    )
    assert not events(path, "close_overlay" if overlay else "logout")
    assert ui.absent("feedback-dialog", within="feedback-success-dialog")
    dismiss_feedback_dialog(ui, wait_for_accessible_state, "feedback-success-dialog",
                            within="kiosk-request-window")
    wait_for_accessible_state(
        lambda: bool(events(path, "close_overlay" if overlay else "logout")),
        "exit after success confirmation closes",
    )


def test_parent_discovery_error_opens_prefilled_feedback(
        launch_ui, automation, wait_for_accessible_state):
    launch_ui("parent_component_preview", environment_overrides={
        "ONPC_PARENT_COMPONENT_SCENARIO": "unavailable",
    }, wait_for_application=False)
    ui = automation
    wait_for_accessible_state(lambda: ui.showing("feedback-dialog"),
                              "parent discovery error report opens")
    _editor, value = wait_for_error_draft(ui, wait_for_accessible_state)
    assert "The operation could not be completed. Please try again later." in value
    assert "service unavailable" not in value
    assert ui.state("feedback-add-files", ui.api.StateType.SENSITIVE)
    wait_for_accessible_state(lambda: ui.state("feedback-send", ui.api.StateType.SENSITIVE),
                              "error report is ready")
    ui.activate("feedback-send")
    wait_for_accessible_state(lambda: ui.showing("feedback-success-dialog"),
                              "feedback confirmation opens")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_removing_logs_after_preparation_failure_preserves_edited_report(
        launch_ui, automation, wait_for_accessible_state, tmp_path, overlay):
    from dogtail import rawinput
    ui = automation
    _process, path = launch_request(
        launch_ui, tmp_path, overlay=overlay,
        scenario="service-failure-logs-unavailable", wait_for_application=False,
    )
    wait_for_accessible_state(lambda: ui.find("kiosk-request-submit") is not None,
                              "request controls publish IDs")
    wait_for_accessible_state(
        lambda: ui.state("kiosk-request-submit", ui.api.StateType.SENSITIVE),
        "request is ready",
    )
    ui.activate("kiosk-request-submit")
    wait_for_accessible_state(lambda: ui.find("kiosk-result-action") is not None,
                              "error result is public")
    ui.activate("kiosk-result-action")
    wait_for_accessible_state(lambda: ui.showing("feedback-dialog"),
                              "error feedback opens")
    editor, original = wait_for_error_draft(ui, wait_for_accessible_state)
    ui.focus(editor)
    rawinput.keyCombo("<Control>End")
    rawinput.typeText("\nMy account of what happened.")
    wait_for_accessible_state(lambda: "My account of what happened." in ui.content(editor),
                              "edited error draft loaded")
    draft = ui.content(editor)
    assert original.strip() in draft
    expected = "Logs could not be prepared. You can send this feedback without the attachment."
    wait_for_accessible_state(lambda: ui.text("feedback-status") == expected,
                              "collection failure is public")
    assert not ui.state("feedback-send", ui.api.StateType.SENSITIVE)
    assert ui.state("feedback-retry-logs", ui.api.StateType.SENSITIVE)
    ui.activate("feedback-toggle-logs")
    assert ui.text("feedback-logs-row") == "No logs attached"
    assert ui.content(editor) == draft
    assert not events(path, "feedback")
    ui.activate("feedback-send")
    wait_for_accessible_state(lambda: ui.showing("feedback-success-dialog"),
                              "feedback confirmation opens")
    assert draft.strip() in events(path, "feedback")[0]["message"]


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_result_toggle_and_exit_through_public_ids(
        launch_ui, automation, wait_for_accessible_state, tmp_path, overlay):
    ui = automation
    _process, path = launch_request(
        launch_ui, tmp_path, overlay=overlay,
        scenario="service-failure", wait_for_application=False,
    )
    wait_for_accessible_state(lambda: ui.find("kiosk-request-submit") is not None,
                              "request surface publishes its controls")
    wait_for_accessible_state(
        lambda: ui.state("kiosk-request-submit", ui.api.StateType.SENSITIVE),
        "request ready",
    )
    ui.activate("kiosk-request-submit")
    wait_for_accessible_state(lambda: ui.find("kiosk-report-toggle") is not None,
                              "error reporting control appears")
    assert ui.state("kiosk-report-toggle", ui.api.StateType.CHECKED)
    ui.activate("kiosk-report-row")
    wait_for_accessible_state(
        lambda: not ui.state("kiosk-report-toggle", ui.api.StateType.CHECKED),
        "reporting turned off",
    )
    assert not events(path, "close_overlay" if overlay else "logout")
    ui.activate("kiosk-result-action")
    wait_for_accessible_state(
        lambda: bool(events(path, "close_overlay" if overlay else "logout")),
        "result action exits",
    )
