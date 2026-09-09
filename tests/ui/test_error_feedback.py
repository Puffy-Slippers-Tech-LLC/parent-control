"""The real shared feedback UI in parent, child-overlay and kiosk contexts."""

import pytest

from tests.support.feedback import feedback_editor
from tests.support.request_form import launch_request, events

pytestmark = pytest.mark.ui


def test_child_panel_stdin_entry_opens_a_prefilled_report(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state):
    application, _log = launch_ui("child_error_preview")
    dialog = wait_for_accessible_node(application, "Send Feedback", "frame")
    editor = feedback_editor(application, wait_for_accessible_node)
    wait_for_accessible_state(
        lambda: "TypeError: child panel could not refresh its timer" in editor.text,
        "child panel error draft loaded",
    )
    assert editor.text.startswith("Something went wrong\nThe operation could not be completed.")
    assert wait_for_accessible_node(dialog, "Add files", "button").sensitive


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_request_error_review_restrictions_and_submission(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state, tmp_path, overlay):
    application, path = launch_request(launch_ui, tmp_path, overlay=overlay, scenario="service-failure")
    find = wait_for_accessible_node
    assert find(application, "REQUEST", "button").do_action(0)
    toggle = find(application, "Report this error", "switch")
    assert toggle.checked
    assert find(application, "Close" if overlay else "Return to Login", "button").do_action(0)
    dialog = find(application, "Send Feedback", "frame")
    editor = feedback_editor(application, find)
    wait_for_accessible_state(lambda: "RuntimeError: org.example.Secret /private/path" in editor.text,
                              "error draft loaded")
    assert editor.text.startswith("Request unavailable\nThe request could not be completed.")
    assert "\n--------------------\n" in editor.text
    assert not events(path, "feedback")
    assert not events(path, "close_overlay" if overlay else "logout")
    for label, role in (("Add files", "button"), ("Download", "button"),
                        ("Add attachment", "toggle button")):
        assert bool(dialog.is_child(label, role_name=role, retry=False)) is overlay
    assert find(dialog, "Privacy", "link").do_action(0)
    privacy = find(application, "Feedback privacy", "alert")
    assert bool(privacy.is_child("View full privacy notice", role_name="link", retry=False)) is overlay
    assert find(privacy, "Close", "button").do_action(0)
    # Re-adding logs must never reveal the kiosk download control.
    assert find(dialog, "Remove", "button").do_action(0)
    assert find(dialog, "Add logs", "button").do_action(0)
    assert bool(dialog.is_child("Download", role_name="button", retry=False)) is overlay
    assert find(dialog, "Send Feedback", "button").do_action(0)
    find(dialog, "Feedback submitted.")
    component = "Child App" if overlay else "Kiosk App"
    assert events(path, "feedback")[0]["subject"] == f"[Oh No! Parent Control] [{component}] Error Report"
    assert find(dialog, "Close", "button").do_action(0)
    wait_for_accessible_state(lambda: bool(events(path, "close_overlay" if overlay else "logout")),
                              "exit after review")


def test_parent_discovery_error_opens_prefilled_feedback(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state):
    application, _log = launch_ui("parent_component_preview", environment_overrides={
        "ONPC_PARENT_COMPONENT_SCENARIO": "unavailable",
    })
    dialog = wait_for_accessible_node(application, "Send Feedback", "frame")
    editor = feedback_editor(application, wait_for_accessible_node)
    wait_for_accessible_state(lambda: "RuntimeError: service unavailable" in editor.text,
                              "parent error draft loaded")
    assert "The Parent App could not load. Please try again later." in editor.text
    assert wait_for_accessible_node(dialog, "Add files", "button").sensitive
    assert wait_for_accessible_node(dialog, "Send Feedback", "button").do_action(0)
    wait_for_accessible_node(dialog, "Feedback submitted.")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_removing_logs_after_preparation_failure_preserves_edited_report(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state, tmp_path, overlay):
    from dogtail import rawinput

    application, path = launch_request(
        launch_ui, tmp_path, overlay=overlay, scenario="service-failure-logs-unavailable",
    )
    find = wait_for_accessible_node
    assert find(application, "REQUEST", "button").do_action(0)
    assert find(application, "Close" if overlay else "Return to Login", "button").do_action(0)
    dialog = find(application, "Send Feedback", "frame")
    editor = feedback_editor(application, find)
    wait_for_accessible_state(lambda: "RuntimeError:" in editor.text, "error draft loaded")
    original = editor.text
    assert editor.grab_focus()
    rawinput.keyCombo("<Control>End")
    rawinput.typeText("\nMy account of what happened.")
    wait_for_accessible_state(lambda: "My account of what happened." in editor.text,
                              "edited error draft loaded")
    draft = editor.text
    assert original.strip() in draft
    assert find(dialog, "Send Feedback", "button").do_action(0)
    find(dialog, "Logs could not be prepared. You can send this feedback without the attachment.")
    assert editor.text == draft
    assert find(dialog, "Remove", "button").do_action(0)
    find(dialog, "No logs attached")
    assert editor.text == draft
    assert not events(path, "feedback")
    # The editable draft and its bridge must agree when explicitly sent next.
    assert find(dialog, "Send Feedback", "button").do_action(0)
    find(dialog, "Feedback submitted.")
    assert draft.strip() in events(path, "feedback")[0]["message"]


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_result_toggle_and_exit_accept_real_pointer_input(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state, tmp_path, overlay):
    from dogtail import rawinput
    application, path = launch_request(launch_ui, tmp_path, overlay=overlay,
                                       scenario="service-failure-pointer")
    assert wait_for_accessible_node(application, "REQUEST", "button").do_action(0)
    toggle = wait_for_accessible_node(application, "Report this error", "switch")
    wait_for_accessible_state(lambda: any("report" in e["targets"] for e in events(path, "pointer_layout")),
                              "result pointer layout")
    targets = events(path, "pointer_layout")[-1]["targets"]
    rawinput.click(*targets["report"])
    wait_for_accessible_state(lambda: not toggle.checked, "pointer turns off reporting")
    assert not events(path, "close_overlay" if overlay else "logout")
    rawinput.click(*targets["result"])
    wait_for_accessible_state(lambda: bool(events(path, "close_overlay" if overlay else "logout")),
                              "pointer exits result")
