"""Exercise the feedback dialog through stable public accessibility IDs."""

import pytest
from tests.support.automation_ids import audit_product_controls
from tests.support.feedback import (
    dismiss_feedback_dialog,
    feedback_editor,
    type_feedback,
)


pytestmark = pytest.mark.ui


def open_feedback(launch_ui, ui, wait, *, scenario="normal", status=None,
                  collection_release=None):
    environment = {"ONPC_PARENT_COMPONENT_SCENARIO": scenario}
    if status is not None:
        environment["ONPC_FEEDBACK_STATUS"] = str(status)
    if collection_release is not None:
        environment["ONPC_FEEDBACK_COLLECTION_RELEASE"] = str(collection_release)
    _process, log = launch_ui(
        "parent_component_preview", environment_overrides=environment,
        wait_for_application=False,
    )
    wait(lambda: ui.find("parent-feedback-button") is not None,
         "Parent feedback action publishes its ID")
    ui.activate("parent-feedback-button")
    wait(lambda: ui.showing("feedback-dialog"), "feedback dialog opens")
    editor = feedback_editor(ui, wait)
    return editor, log


def test_feedback_footer_is_semantically_reachable_without_page_assumptions(
        launch_ui, automation, wait_for_accessible_state):
    open_feedback(launch_ui, automation, wait_for_accessible_state)
    automation.reveal("feedback-close")
    automation.reveal("feedback-send")
    assert automation.state("feedback-close", automation.api.StateType.SENSITIVE)


def test_feedback_draft_and_optional_attachment(
        launch_ui, automation, wait_for_accessible_state, collect_application_logs):
    ui = automation
    editor, log_path = open_feedback(launch_ui, ui, wait_for_accessible_state)
    for identity in (
        "feedback-format-bold", "feedback-format-italic", "feedback-format-underline",
        "feedback-format-strike", "feedback-format-ordered", "feedback-format-bulleted",
        "feedback-format-quote", "feedback-format-code", "feedback-format-link",
        "feedback-format-attachment", "feedback-format-clear",
    ):
        wait_for_accessible_state(lambda i=identity: ui.find(i) is not None,
                                  identity + " publishes its ID")
        assert ui.state(identity, ui.api.StateType.SENSITIVE)
    assert ui.state("feedback-add-files", ui.api.StateType.SENSITIVE)
    type_feedback(ui, "Feedback draft must stay local.", wait_for_accessible_state)
    ui.activate("feedback-privacy-link")
    wait_for_accessible_state(lambda: ui.showing("feedback-privacy-dialog"),
                              "privacy dialog opens")
    assert audit_product_controls(ui, "feedback-privacy-dialog")
    assert [relation.get_target(index)
            for relation in ui.target("feedback-privacy-dialog").get_relation_set()
            if relation.get_relation_type() == ui.api.RelationType.CONTROLLED_BY
            for index in range(relation.get_n_targets())] == [ui.target("feedback-dialog")]
    assert "Diagnostic logs do not collect account names" in ui.text("feedback-privacy-text")
    assert ui.showing("feedback-full-privacy-link")
    dismiss_feedback_dialog(ui, wait_for_accessible_state, "feedback-privacy-dialog",
                            within="feedback-dialog")
    wait_for_accessible_state(
        lambda: ui.state("feedback-download-logs", ui.api.StateType.SENSITIVE),
        "diagnostics are ready",
    )
    ui.activate("feedback-toggle-logs")
    wait_for_accessible_state(lambda: ui.text("feedback-logs-row") == "No logs attached",
                              "logs removed")
    ui.activate("feedback-toggle-logs")
    wait_for_accessible_state(lambda: ui.text("feedback-logs-row") == "diagnostic-logs.zip",
                              "logs restored")
    assert ui.content(editor).strip() == "Feedback draft must stay local."
    wait_for_accessible_state(lambda: ui.state("feedback-send", ui.api.StateType.SENSITIVE),
                              "feedback send is ready")
    ui.activate("feedback-close")
    wait_for_accessible_state(lambda: ui.absent("feedback-dialog", within="parent-window"),
                              "feedback dialog closed")
    ui.activate("parent-feedback-button")
    wait_for_accessible_state(lambda: ui.showing("feedback-dialog"),
                              "feedback dialog reopens")
    feedback_editor(ui, wait_for_accessible_state)
    assert ui.content(editor).strip() == "Feedback draft must stay local."
    log = collect_application_logs(log_path)
    assert "Feedback draft must stay local." not in log
    assert "Traceback" not in log
    assert "Theme parser error" not in log


def test_collection_progress_disables_send_but_allows_editing(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    ui = automation
    release = tmp_path / "feedback-collection-release"
    editor, _log = open_feedback(
        launch_ui, ui, wait_for_accessible_state,
        scenario="feedback-collecting",
        collection_release=release,
    )
    try:
        wait_for_accessible_state(lambda: ui.showing("feedback-collection-status"),
                                  "collection progress is public")
        assert not ui.state("feedback-send", ui.api.StateType.SENSITIVE)
        assert ui.state("feedback-close", ui.api.StateType.SENSITIVE)
        assert ui.state(editor, ui.api.StateType.SENSITIVE)
        type_feedback(ui, "Draft during collection", wait_for_accessible_state)
    finally:
        release.touch()
    wait_for_accessible_state(lambda: ui.find("feedback-logs-row") is not None
                              and ui.text("feedback-logs-row") == "diagnostic-logs.zip",
                              "diagnostics collection completes")
    wait_for_accessible_state(lambda: ui.state("feedback-send", ui.api.StateType.SENSITIVE),
                              "collection enables sending")
    assert ui.content(editor).strip() == "Draft during collection"
    assert ui.absent("feedback-collection-status", within="feedback-dialog")


@pytest.mark.parametrize("status", [202, 409, 413, 422])
def test_feedback_submission_outcomes(
        launch_ui, automation, wait_for_accessible_state,
        collect_application_logs, status):
    from tests.support.keyboard import key_combo, type_text
    ui = automation
    editor, log_path = open_feedback(
        launch_ui, ui, wait_for_accessible_state, status=status,
    )
    ui.activate("feedback-format-bold")
    type_feedback(ui, "A private feedback draft", wait_for_accessible_state)
    text = ui.target(editor).get_text_iface()
    attributes, start, end = ui.api.Text.get_attribute_run(text, 0, True)
    assert attributes["weight"] == "700"
    assert start == 0 and end >= len("A private feedback draft")
    if status == 202:
        # GTK does not implement AT-SPI Component.GrabFocus. Leave the web
        # editor with normal keyboard navigation and confirm the recipient
        # by ID before sending any text to the native entry.
        ui.focus(editor)
        key_combo(ui, editor, "<Control>Tab", state=ui.api.StateType.FOCUSED)
        wait_for_accessible_state(
            lambda: ui.state("feedback-reply-email", ui.api.StateType.FOCUSED),
            "reply email receives keyboard focus",
        )
        type_text(ui, "feedback-reply-email", "feedback@example.com")
    wait_for_accessible_state(lambda: ui.state("feedback-send", ui.api.StateType.SENSITIVE),
                              "feedback send is ready")
    ui.activate("feedback-send")
    if status == 409:
        wait_for_accessible_state(
            lambda: ui.text("feedback-send") == "Submit again (may duplicate)",
            "duplicate-safe retry offered",
        )
        assert ui.content(editor).strip() == "A private feedback draft"
        ui.activate("feedback-send")
    elif status == 413:
        wait_for_accessible_state(lambda: ui.showing("feedback-send-without-logs"),
                                  "send without logs offered")
        assert ui.content(editor).strip() == "A private feedback draft"
        ui.activate("feedback-send-without-logs")
    elif status == 422:
        expected = ("Feedback was not accepted. Your draft is preserved. Check your "
                    "feedback and reply address before sending again.")
        wait_for_accessible_state(lambda: ui.find("feedback-status") is not None
                                  and ui.text("feedback-status") == expected,
                                  "rejected feedback preserves draft")
        assert ui.content(editor).strip() == "A private feedback draft"
        assert ui.state(editor, ui.api.StateType.SENSITIVE)
        ui.activate("feedback-send")
    wait_for_accessible_state(lambda: ui.showing("feedback-success-dialog"),
                              "success confirmation opens")
    assert audit_product_controls(ui, "feedback-success-dialog")
    wait_for_accessible_state(lambda: ui.absent("feedback-dialog", within="parent-window"),
                              "feedback editor hides before confirmation dismissal")
    body = "Your feedback was sent successfully. We appreciate your help making the app better."
    if status == 202:
        body += ("\n\nWe may contact you at the email address you provided if we have "
                 "any follow-up questions.")
    assert ui.text("feedback-success-text") == body
    dismiss_feedback_dialog(ui, wait_for_accessible_state, "feedback-success-dialog",
                            within="parent-window")
    ui.activate("parent-feedback-button")
    wait_for_accessible_state(lambda: ui.showing("feedback-dialog"),
                              "feedback dialog reopens")
    feedback_editor(ui, wait_for_accessible_state)
    assert not ui.content(editor).strip()
    if status == 413:
        assert ui.text("feedback-logs-row") == "No logs attached"
    log = collect_application_logs(log_path)
    assert "A private feedback draft" not in log
    assert "Traceback" not in log
