"""Exercise the feedback design through the production parent menu."""

import pytest


pytestmark = pytest.mark.ui


def test_feedback_draft_and_optional_attachment(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state,
        collect_application_logs):
    application, log_path = launch_ui("parent_component_preview")
    menu = wait_for_accessible_node(application, "Parent app menu", "button")
    assert menu.child(role_name="toggle button", retry=False).do_action(0)
    assert wait_for_accessible_node(application, "Send Feedback", "button").do_action(0)
    message = wait_for_accessible_node(application, "Your feedback", "text")
    message.text = "Feedback draft must stay local."
    remove = wait_for_accessible_node(application, "Remove", "button")
    assert remove.do_action(0)
    wait_for_accessible_node(application, "No logs attached")
    assert wait_for_accessible_node(application, "Add logs", "button").do_action(0)
    wait_for_accessible_node(application, "diagnostic-logs.zip")
    assert message.text == "Feedback draft must stay local."
    assert not wait_for_accessible_node(application, "Send Feedback", "button").sensitive
    assert wait_for_accessible_node(application, "Cancel", "button").do_action(0)
    wait_for_accessible_state(
        lambda: not application.is_child("Send Feedback", role_name="frame", retry=False),
        "feedback dialog closed",
    )
    log = collect_application_logs(log_path)
    assert "Feedback draft must stay local." not in log
    assert "Traceback" not in log
    assert "Theme parser error" not in log
