"""The real shared feedback UI in parent, child-overlay and kiosk contexts."""

import pytest

from tests.support.feedback import dismiss_feedback_dialog, feedback_editor
from tests.support.request_form import launch_request, events


pytestmark = pytest.mark.ui


@pytest.mark.parametrize('surface', ('parent', 'kiosk', 'child-overlay'))
def test_product_update_modal_reboot_and_dismissal(
        launch_ui, automation, wait_for_accessible_state, tmp_path, surface):
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
    assert ui.state('update-required-dialog', ui.api.StateType.MODAL)
    assert len(ui.find_all('update-required-dialog')) == 1
    assert ui.text('update-required-message') == (
        'A product update was installed. Restart the computer for Oh No! Parent Control to work properly.')
    assert ui.text('update-required-reboot') == 'Reboot now'
    assert ui.absent('feedback-dialog', within='update-required-dialog')
    if surface == 'parent':
        for identity in ('parent-window', 'parent-startup-window', 'parent-reboot-window'):
            assert ui.absent(identity, within='update-required-dialog')
    assert not events(path, 'reboot-requested')
    ui.activate('update-required-reboot')
    wait(lambda: ui.showing('update-required-status'), 'reboot refusal remains actionable')
    assert ui.text('update-required-status') == 'The operation could not be completed. Please try again later.'
    assert len(events(path, 'reboot-requested')) == 1
    assert ui.state('update-required-reboot', ui.api.StateType.SENSITIVE)
    ui.activate('update-required-close')
    if surface == 'parent':
        wait(lambda: process.poll() is not None, 'closing the only dialog exits Parent')
        assert process.returncode == 0
        assert not ui.find_all('update-required-dialog')
    else:
        wait(lambda: ui.absent('update-required-dialog', within=underlying), 'modal dismissed')
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
    wait_for_accessible_state(lambda: ui.text("feedback-logs-row") == "No logs attached",
                              "diagnostic logs are removed")
    ui.activate("feedback-toggle-logs")
    wait_for_accessible_state(
        lambda: ui.text("feedback-logs-row") == "diagnostic-logs.zip",
        "diagnostic logs are restored",
    )
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
    from tests.support.keyboard import key_combo, type_text
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
    key_combo(ui, editor, "<Control>End", state=ui.api.StateType.FOCUSED)
    type_text(ui, editor, "\nMy account of what happened.")
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
    wait_for_accessible_state(lambda: ui.text("feedback-logs-row") == "No logs attached",
                              "failed diagnostics are removed")
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
