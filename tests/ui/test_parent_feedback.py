"""Exercise the feedback dialog without sending real email."""

import pytest
from dogtail import rawinput


pytestmark = pytest.mark.ui


def feedback_editor(application, wait_for_accessible_node):
    section = wait_for_accessible_node(application, "Your feedback", "section")
    return section.child(role_name="entry")


def type_feedback(editor, value, wait_for_accessible_state):
    assert editor.grab_focus()
    rawinput.typeText(value)
    wait_for_accessible_state(
        lambda: editor.text.strip() == value,
        "rich feedback editor receives typed text",
    )


def test_feedback_footer_visible_without_scrolling(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state):
    application, _log_path = launch_ui("parent_component_preview")
    assert wait_for_accessible_node(application, "Feedback", "button").do_action(0)
    dialog = wait_for_accessible_node(application, "Send Feedback", "frame")
    for label in ("Close", "Send Feedback"):
        button = wait_for_accessible_node(dialog, label, "button")

        def inside_dialog():
            x, y, width, height = dialog.extents
            bx, by, bw, bh = button.extents
            return (bw > 0 and bh > 0 and x <= bx and y <= by
                    and bx + bw <= x + width and by + bh <= y + height)

        wait_for_accessible_state(inside_dialog, f"{label} fully visible")
        ancestor = button.parent
        while ancestor != dialog:
            assert ancestor.roleName != "scroll pane"
            ancestor = ancestor.parent


def test_feedback_draft_and_optional_attachment(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state,
        collect_application_logs):
    application, log_path = launch_ui("parent_component_preview")
    assert wait_for_accessible_node(application, "Feedback", "button").do_action(0)
    message = feedback_editor(application, wait_for_accessible_node)
    for label in (
        "Bold", "Italic", "Underline", "Strikethrough", "Numbered list",
        "Bulleted list", "Quote", "Code block", "Insert link",
        "Add attachment", "Remove formatting",
    ):
        assert wait_for_accessible_node(application, label, "toggle button").sensitive
    assert wait_for_accessible_node(application, "Add files", "button").sensitive
    type_feedback(message, "Feedback draft must stay local.", wait_for_accessible_state)
    privacy = wait_for_accessible_node(application, "Privacy", "link")
    assert privacy.do_action(0)
    privacy_dialog = wait_for_accessible_node(
        application, "Feedback privacy", "alert",
    )
    wait_for_accessible_node(
        privacy_dialog,
        "Your feedback, reply email, files, and optional diagnostic logs are "
        "sent to support and kept for 7 days. Diagnostic logs do not collect "
        "personally identifiable information (PII), such as account names, email "
        "addresses, or file contents. Review files and logs before sending.",
    )
    wait_for_accessible_node(
        privacy_dialog, "View full privacy notice", "link",
    )
    assert wait_for_accessible_node(privacy_dialog, "Close", "button").do_action(0)
    assert wait_for_accessible_node(application, "Download", "button").sensitive
    remove = wait_for_accessible_node(application, "Remove", "button")
    assert remove.do_action(0)
    wait_for_accessible_node(application, "No logs attached")
    assert wait_for_accessible_node(application, "Add logs", "button").do_action(0)
    wait_for_accessible_node(application, "diagnostic-logs.zip")
    assert message.text.strip() == "Feedback draft must stay local."
    assert wait_for_accessible_node(application, "Send Feedback", "button").sensitive
    dialog = wait_for_accessible_node(application, "Send Feedback", "frame")
    assert wait_for_accessible_node(dialog, "Close", "button").do_action(0)
    wait_for_accessible_state(
        lambda: not application.is_child("Send Feedback", role_name="frame", retry=False),
        "feedback dialog closed",
    )
    assert wait_for_accessible_node(application, "Feedback", "button").do_action(0)
    assert feedback_editor(application, wait_for_accessible_node).text.strip() == "Feedback draft must stay local."
    log = collect_application_logs(log_path)
    assert "Feedback draft must stay local." not in log
    assert "Traceback" not in log
    assert "Theme parser error" not in log


@pytest.mark.parametrize("status", [202, 409, 413, 422])
def test_feedback_submission_outcomes(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state,
        collect_application_logs, status):
    application, log_path = launch_ui(
        "parent_component_preview", environment_overrides={"ONPC_FEEDBACK_STATUS": str(status)},
    )
    assert wait_for_accessible_node(application, "Feedback", "button").do_action(0)
    dialog = wait_for_accessible_node(application, "Send Feedback", "frame")
    message = feedback_editor(application, wait_for_accessible_node)
    assert wait_for_accessible_node(application, "Bold", "toggle button").do_action(0)
    type_feedback(message, "A private feedback draft", wait_for_accessible_state)
    assert wait_for_accessible_node(dialog, "Send Feedback", "button").do_action(0)
    if status == 409:
        retry = wait_for_accessible_node(application, "Submit again (may duplicate)", "button")
        assert message.text.strip() == "A private feedback draft"
        assert retry.do_action(0)
    elif status == 413:
        without = wait_for_accessible_node(application, "Send without logs", "button")
        assert message.text.strip() == "A private feedback draft"
        assert without.do_action(0)
        wait_for_accessible_node(application, "No logs attached")
    elif status == 422:
        wait_for_accessible_node(application, "Feedback was not accepted. Your draft is preserved. Check your feedback and reply address before sending again.")
        assert message.text.strip() == "A private feedback draft"
        assert message.sensitive
        assert wait_for_accessible_node(dialog, "Send Feedback", "button").do_action(0)
    wait_for_accessible_node(application, "Feedback submitted.")
    wait_for_accessible_state(lambda: not message.text.strip(), "accepted feedback clears draft")
    log = collect_application_logs(log_path)
    assert "A private feedback draft" not in log
    assert "Traceback" not in log
