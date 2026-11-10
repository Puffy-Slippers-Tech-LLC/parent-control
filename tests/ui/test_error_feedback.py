"""The real shared feedback UI in parent, child-overlay and kiosk contexts."""

import pytest

from tests.support.feedback import dismiss_feedback_dialog, feedback_editor
from tests.support.request_form import launch_request, events, submit_request


pytestmark = pytest.mark.ui


@pytest.mark.parametrize('surface', ('parent', 'kiosk', 'child-overlay'))
def test_product_update_modal_reboot_and_dismissal(
        launch_ui, automation, wait_for_accessible_state, tmp_path, monkeypatch, surface):
    ui, wait = automation, wait_for_accessible_state
    if surface == 'parent':
        path = tmp_path / 'parent-reboot.jsonl'
        process, _log = launch_ui(
            'parent_component_preview', wait_for_application=False, complete_language_setup=False,
            environment_overrides={'ONPC_PARENT_COMPONENT_SCENARIO': 'startup-reboot',
                                   'ONPC_PARENT_COMPONENT_EVENTS_PATH': str(path)})
    else:
        _process, path = launch_request(launch_ui, tmp_path,
                                       overlay=surface == 'child-overlay', scenario='reboot-required',
                                       complete_language_setup=False)
        underlying = 'kiosk-request-window'
    wait(lambda: ui.showing('update-required-dialog'), 'product update modal opens')
    binding = 'overlay' if surface == 'child-overlay' else surface
    # The preview's simulated session/UID supplies no installed ownership credit.
    monkeypatch.setattr(ui.reader, 'require_child_overlay_session', lambda child=None: None)
    assert ui.reader.restart_notice(binding) == {'surface': binding,
        'texts': {'update-required-message':
            'Restart the computer for Oh No! Parent Control to work properly.',
            'update-required-close': 'Close', 'update-required-reboot': 'Reboot now'},
        'modal': True, 'policy_blocked': True}
    assert ui.state('update-required-dialog', ui.api.StateType.MODAL)
    assert len(ui.find_all('update-required-dialog')) == 1
    assert ui.text('update-required-message') == (
        'Restart the computer for Oh No! Parent Control to work properly.')
    assert ui.text('update-required-reboot') == 'Reboot now'
    assert ui.absent('feedback-dialog', within='update-required-dialog')
    if surface == 'parent':
        for identity in ('parent-window', 'parent-startup-window', 'parent-reboot-window'):
            assert ui.absent(identity, within='update-required-dialog')
    assert not events(path, 'reboot-requested')
    ui.reader.trace_boot = 'a' * 64
    ui.reader.restart_action(binding, 'reboot')
    wait(lambda: ui.showing('update-required-status'), 'reboot refusal remains actionable')
    assert ui.text('update-required-status') == 'The operation could not be completed. Please try again later.'
    assert len(events(path, 'reboot-requested')) == 1
    assert ui.state('update-required-reboot', ui.api.StateType.SENSITIVE)
    ui.reader.restart_action(binding, 'close')
    if surface == 'parent':
        wait(lambda: process.poll() is not None, 'closing the only dialog exits Parent')
        assert process.returncode == 0
        assert not ui.find_all('update-required-dialog')
    else:
        wait(lambda: ui.absent('update-required-dialog', within=underlying), 'modal dismissed')
        ui.reader.restart_closed(binding)
    assert not events(path, 'feedback')
    assert not events(path, 'logout') and not events(path, 'close_overlay')
    if surface != 'parent':
        assert ui.text('kiosk-result-title') == 'Restart required'
        assert ui.state('kiosk-result-action', ui.api.StateType.SENSITIVE)


@pytest.mark.parametrize('language,heading,categories', [
    ('de', 'Ein Fehler ist aufgetreten', 'Fehlerkategorien'),
    ('ru', 'Произошла ошибка', 'Категории ошибок'),
])
def test_error_report_initial_explanation_uses_request_language(
        launch_ui, automation, wait_for_accessible_state, tmp_path,
        language, heading, categories):
    from tests.support.localization_review import switch_language
    ui, wait = automation, wait_for_accessible_state
    launch_request(launch_ui, tmp_path, overlay=True, scenario='service-failure',
                   wait_for_application=False)
    wait(lambda: ui.state('kiosk-request-submit', ui.api.StateType.SENSITIVE), 'ready')
    switch_language(ui, wait, 'kiosk', language)
    ui.activate('kiosk-request-submit')
    wait(lambda: ui.showing('kiosk-report-toggle'), 'error result opens')
    ui.activate('kiosk-result-action')
    wait(lambda: ui.showing('feedback-dialog'), 'error report opens')
    editor = feedback_editor(ui, wait)
    wait(lambda: ui.content(editor).startswith(heading + '\n'), 'localized explanation loads')
    draft = ui.content(editor)
    assert categories + ': RuntimeError' in draft
    assert 'The operation could not be completed' not in draft
    assert 'org.example.Secret' not in draft and '/private/path' not in draft


def wait_for_error_draft(ui, wait):
    from tests.support.localization_review import public_label_names

    editor = feedback_editor(ui, wait)
    wait(lambda: "Error categories: RuntimeError" in ui.content(editor),
         "error draft loaded")
    value = ui.content(editor)
    assert value.startswith("Something went wrong\nThe operation could not be completed.")
    assert ui.text('feedback-dialog') == 'Report an Error'
    assert ui.text('feedback-send') == 'Send Error Report'
    labels = public_label_names(ui, 'feedback-content')
    assert 'Sorry about the inconvenience' in labels
    assert 'Something went wrong. Help us fix it by sending a report.' in labels
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


@pytest.mark.parametrize("overlay,retry", (
    pytest.param(False, False, id="kiosk"),
    pytest.param(True, False, id="child-overlay"),
    pytest.param(True, True, id="child-overlay-retry"),
))
def test_request_error_review_restrictions_and_submission(
        launch_ui, automation, wait_for_accessible_state, tmp_path, overlay, retry):
    ui = automation
    retry_release = tmp_path / "feedback-retry-release" if retry else None
    _process, path = launch_request(
        launch_ui, tmp_path, overlay=overlay, scenario="service-failure",
        wait_for_application=False,
        feedback_status=503 if retry else 202, feedback_retry_release=retry_release,
    )
    submit_request(ui, wait_for_accessible_state)
    wait_for_accessible_state(lambda: ui.find("kiosk-report-toggle") is not None,
                              "error result publishes reporting choice")
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
    wait_for_accessible_state(lambda: ui.text("feedback-logs-row") == "No logs attached",
                              "diagnostic logs are removed")
    ui.activate("feedback-toggle-logs")
    wait_for_accessible_state(
        lambda: ui.text("feedback-logs-row") == "diagnostic-logs.zip",
        "diagnostic logs are restored",
    )
    assert (ui.showing("feedback-download-logs") if overlay
            else ui.absent("feedback-download-logs", within="feedback-dialog"))
    if overlay:
        ui.setText("feedback-reply-email", "first@example.invalid")
    else:
        assert ui.content("feedback-reply-email") == ""
    wait_for_accessible_state(lambda: ui.state("feedback-send", ui.api.StateType.SENSITIVE),
                              "error report is ready")
    try:
        ui.activate("feedback-send")
        if retry:
            wait_for_accessible_state(
                lambda: ui.text("feedback-status").startswith(
                    "Could not confirm submission. Retrying in "),
                "child sees the automatic report retry",
            )
            assert ui.showing("feedback-dialog")
            assert ui.text("feedback-close") == "Stop sending and close"
            assert ui.state("feedback-close", ui.api.StateType.SENSITIVE)
            assert not ui.state("feedback-send", ui.api.StateType.SENSITIVE)
            assert ui.absent("feedback-success-dialog", within="kiosk-request-window")
            assert not events(path, "close_overlay") and not events(path, "logout")
    finally:
        if retry_release is not None:
            retry_release.touch()
    if not overlay:
        assert ui.absent("feedback-anonymous-dialog", within="kiosk-request-window")
    wait_for_accessible_state(lambda: ui.showing("feedback-success-dialog"),
                              "feedback confirmation opens")
    component = "Child App" if overlay else "Kiosk App"
    submissions = events(path, "feedback")
    assert len(submissions) == (2 if retry else 1)
    assert submissions[0]["subject"] == (
        f"[Oh No! Parent Control] [{component}] Error Report"
    )
    body = "Your feedback was sent successfully. We appreciate your help making the app better."
    if overlay:
        assert "Reply email: first@example.invalid\n" in submissions[0]["message"]
        body += ("\n\nWe may contact you at the email address you provided if we have "
                 "any follow-up questions.")
    else:
        assert "Reply email: not provided\n" in submissions[0]["message"]
    assert ui.text("feedback-success-text") == body
    assert ui.state("feedback-success-dialog", ui.api.StateType.MODAL)
    assert not events(path, "close_overlay" if overlay else "logout")
    assert ui.absent("feedback-dialog", within="kiosk-request-window")
    dismiss_feedback_dialog(ui, wait_for_accessible_state, "feedback-success-dialog",
                            within="kiosk-request-window")
    wait_for_accessible_state(
        lambda: bool(events(path, "close_overlay" if overlay else "logout")),
        "exit after success confirmation closes",
    )
    assert len(events(path, "close_overlay" if overlay else "logout")) == 1
    assert not events(path, "logout" if overlay else "close_overlay")
    assert ui.absent("feedback-dialog", within="kiosk-request-window")
    assert len(events(path, "feedback")) == (2 if retry else 1)


@pytest.mark.parametrize("late_status", (503, 202), ids=("late-retry", "late-success"))
def test_child_stops_sending_report_before_late_response(
        launch_ui, automation, wait_for_accessible_state, collect_application_logs,
        tmp_path, late_status):
    ui, wait = automation, wait_for_accessible_state
    release = tmp_path / "feedback-retry-release"
    launches = []

    def record_launch(*args, **kwargs):
        launched = launch_ui(*args, **kwargs)
        launches.append(launched)
        return launched

    _process, path = launch_request(
        record_launch, tmp_path, overlay=True, scenario="service-failure",
        feedback_status=503, feedback_retry_release=release,
        feedback_retry_status=late_status,
    )
    submit_request(ui, wait)
    wait(lambda: ui.showing("kiosk-report-toggle"), "child can review the failed request")
    ui.activate("kiosk-result-action")
    wait(lambda: ui.showing("feedback-dialog"), "child's error report opens")
    wait_for_error_draft(ui, wait)
    wait(lambda: ui.state("feedback-send", ui.api.StateType.SENSITIVE),
         "child's report is ready to send")
    try:
        ui.activate("feedback-send")
        wait(lambda: ui.text("feedback-status").startswith(
            "Could not confirm submission. Retrying in "),
            "child sees the automatic retry")
        assert ui.text("feedback-close") == "Stop sending and close"
        assert ui.state("feedback-close", ui.api.StateType.SENSITIVE)
        assert not ui.state("feedback-send", ui.api.StateType.SENSITIVE)
        assert not events(path, "close_overlay") and not events(path, "logout")
        wait(lambda: len(events(path, "feedback")) == 2,
             "the automatic retry is pending in the fake HTTP session")
        ui.activate("feedback-close")
        wait(lambda: ui.absent("feedback-dialog", within="kiosk-request-window"),
             "Stop directly closes the report without confirmation")
        wait(lambda: bool(events(path, "close_overlay")),
             "closing the report calls the overlay exit before the response is released")
        assert len(events(path, "close_overlay")) == 1
        assert not events(path, "logout")
        assert ui.absent("feedback-success-dialog", within="kiosk-request-window")
    finally:
        release.touch()

    # ErrorHandler destroys the closed report. Synchronize with its real
    # completion handler's existing diagnostic before checking the public UI;
    # a released HTTP response alone would not prove that handler ran.
    outcome = "success" if late_status == 202 else "cancelled"
    log_path = launches[0][1]
    wait(lambda: f"feedback submission finished outcome={outcome}" in
         collect_application_logs(log_path),
         "the closed report handles the late response")
    assert ui.absent("feedback-dialog", within="kiosk-request-window")
    assert ui.absent("feedback-success-dialog", within="kiosk-request-window")
    assert len(events(path, "feedback")) == 2
    assert len(events(path, "close_overlay")) == 1
    assert not events(path, "logout")


def test_parent_discovery_error_opens_prefilled_feedback(
        launch_ui, automation, wait_for_accessible_state):
    # Fatal discovery replaces language setup with the error report.
    launch_ui("parent_component_preview", environment_overrides={
        "ONPC_PARENT_COMPONENT_SCENARIO": "unavailable",
    }, wait_for_application=False, complete_language_setup=False)
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
    wait_for_accessible_state(lambda: ui.showing("feedback-anonymous-dialog"),
                              "Parent error report asks before anonymous submission")
    ui.activate("feedback-send-anonymously")
    wait_for_accessible_state(lambda: ui.showing("feedback-success-dialog"),
                              "feedback confirmation opens")


@pytest.mark.parametrize("overlay,send_without_logs,feedback_status", (
    pytest.param(False, False, 202, id="kiosk"),
    pytest.param(True, False, 202, id="child-overlay"),
    pytest.param(False, True, 202, id="kiosk-send-without-logs"),
    pytest.param(False, True, 400, id="kiosk-send-without-logs-rejected"),
))
def test_removing_logs_after_preparation_failure_preserves_edited_report(
        launch_ui, automation, wait_for_accessible_state, tmp_path, overlay,
        send_without_logs, feedback_status):
    from tests.support.application_ui import utf16_length
    ui = automation
    _process, path = launch_request(
        launch_ui, tmp_path, overlay=overlay,
        scenario="service-failure-logs-unavailable", wait_for_application=False,
        feedback_status=feedback_status,
    )
    submit_request(ui, wait_for_accessible_state)
    wait_for_accessible_state(lambda: ui.find("kiosk-result-action") is not None,
                              "error result is public")
    ui.activate("kiosk-result-action")
    wait_for_accessible_state(lambda: ui.showing("feedback-dialog"),
                              "error feedback opens")
    editor, original = wait_for_error_draft(ui, wait_for_accessible_state)
    expected = "Logs could not be prepared. You can send this feedback without the attachment."
    wait_for_accessible_state(lambda: ui.text("feedback-status") == expected,
                              "collection failure is public")
    assert not ui.state("feedback-send", ui.api.StateType.SENSITIVE)
    assert ui.state("feedback-retry-logs", ui.api.StateType.SENSITIVE)
    ui.setValue('feedback-editor-selection', {
        'index': utf16_length(ui.getText(editor)), 'length': 0})
    ui.setText('feedback-editor-insert', "\nMy account of what happened.")
    wait_for_accessible_state(lambda: "My account of what happened." in ui.content(editor),
                              "edited error draft loaded")
    draft = ui.content(editor)
    assert original.strip() in draft
    if send_without_logs:
        assert ui.state("feedback-close", ui.api.StateType.SENSITIVE)
        for identity in ("feedback-add-files", "feedback-download-logs",
                         "feedback-format-attachment"):
            assert ui.absent(identity, within="feedback-dialog")
        ui.activate("feedback-privacy-link")
        wait_for_accessible_state(lambda: ui.showing("feedback-privacy-dialog"),
                                  "privacy explanation opens")
        privacy = ui.text("feedback-privacy-text")
        assert "diagnostic logs are emailed to support" in privacy
        assert "Diagnostic logs do not collect account names" in privacy
        assert ui.absent("feedback-full-privacy-link", within="feedback-privacy-dialog")
        dismiss_feedback_dialog(ui, wait_for_accessible_state, "feedback-privacy-dialog",
                                within="feedback-dialog")
        assert ui.content(editor) == draft
        assert not events(path, "feedback")
        assert not events(path, "logout") and not events(path, "close_overlay")
        ui.activate("feedback-send-without-logs")
    else:
        ui.activate("feedback-toggle-logs")
        wait_for_accessible_state(lambda: ui.text("feedback-logs-row") == "No logs attached",
                                  "failed diagnostics are removed")
        assert ui.content(editor) == draft
        assert not events(path, "feedback")
        ui.activate("feedback-send")
    if feedback_status == 400:
        wait_for_accessible_state(lambda: ui.text("feedback-status") == (
            "Feedback was not accepted. Your draft is preserved. Check your feedback "
            "and reply address before sending again."), "report rejection is public")
    else:
        wait_for_accessible_state(lambda: ui.showing("feedback-success-dialog"),
                                  "feedback confirmation opens")
    submissions = events(path, "feedback")
    assert len(submissions) == 1
    assert draft.strip() in submissions[0]["message"]
    assert submissions[0]["attachments"] == []
    if feedback_status == 400:
        assert ui.showing("feedback-dialog")
        assert ui.content(editor) == draft
        assert ui.state("feedback-close", ui.api.StateType.SENSITIVE)
        assert ui.state("feedback-send", ui.api.StateType.SENSITIVE)
        assert ui.absent("feedback-success-dialog", within="kiosk-request-window")
        assert not events(path, "logout") and not events(path, "close_overlay")
        return
    if send_without_logs:
        assert submissions[0]["subject"] == "[Oh No! Parent Control] [Kiosk App] Error Report"
        assert ui.text("feedback-success-text") == (
            "Your feedback was sent successfully. We appreciate your help making the app better.")
        assert ui.state("feedback-success-dialog", ui.api.StateType.MODAL)
        assert ui.absent("feedback-dialog", within="kiosk-request-window")
        assert not events(path, "logout") and not events(path, "close_overlay")
        dismiss_feedback_dialog(ui, wait_for_accessible_state, "feedback-success-dialog",
                                within="kiosk-request-window")
        wait_for_accessible_state(lambda: bool(events(path, "logout")),
                                  "station exits after manual thanks dismissal")
        assert len(events(path, "logout")) == 1
        assert not events(path, "close_overlay")
        assert ui.absent("feedback-dialog", within="kiosk-request-window")
        assert len(events(path, "feedback")) == 1


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_result_toggle_and_exit_through_public_ids(
        launch_ui, automation, wait_for_accessible_state, tmp_path, overlay):
    ui = automation
    _process, path = launch_request(
        launch_ui, tmp_path, overlay=overlay,
        scenario="service-failure", wait_for_application=False,
    )
    submit_request(ui, wait_for_accessible_state)
    wait_for_accessible_state(lambda: ui.find("kiosk-report-toggle") is not None,
                              "error reporting control appears")
    ui.activate("kiosk-report-row")
    assert not events(path, "close_overlay" if overlay else "logout")
    ui.activate("kiosk-result-action")
    wait_for_accessible_state(
        lambda: bool(events(path, "close_overlay" if overlay else "logout")),
        "result action exits",
    )
    assert not events(path, "feedback")
