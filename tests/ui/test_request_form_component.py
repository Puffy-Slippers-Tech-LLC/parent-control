"""Semantic component coverage for the shared kiosk and child request form."""

from __future__ import annotations

import json
import re

import pytest
from tests.support.events import read_events as records
from tests.support.request_form import launch_request, calls, events


pytestmark = pytest.mark.ui


def test_remembered_overlay_binding_uses_local_approver_and_native_shared_choices(
        launch_ui, automation, wait_for_accessible_state, monkeypatch):
    from gi.repository import GLib
    from tests.e2e.accessible_ui import AccessibleUI, CHILD, EXISTING_CHILD, PARENT, OTHER_PARENT
    from tests.e2e.ui_observations import RequestObservation

    launch_ui('child_overlay_preview')
    ui = automation
    wait_for_accessible_state(lambda: ui.find('kiosk-request-submit') is not None,
                              'overlay form available')
    reader = AccessibleUI(ui.api, timeout=15, query_errors=ui.query_errors,
        owner_pids=ui.owner_pids, application_ids=ui.application_ids,
        application_owners=ui.application_owners, application_owner_history=ui.application_owner_history,
        fixture_uids={CHILD: 1001, EXISTING_CHILD: 1002, PARENT: 1000, OTHER_PARENT: 1010},
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    monkeypatch.setattr(reader, 'require_child_overlay_session', lambda child=CHILD: None)
    monkeypatch.setattr(reader, 'interactive_approver_uids', lambda: {'1000', '1010'})
    assert ui.find('kiosk-child-selector').get_description() == 'Selected account: ' + CHILD + '.'
    # The preview's broker seed is Jamie; explicitly establish the installed
    # journey's local overlay approver before checking the shared tuple.
    assert ui.find('kiosk-approver-selector').get_description() == 'Selected account: ' + PARENT + '.'
    for action in ('approver', 'custom', 'text', 'apps'):
        reader.run('remembered-overlay-riley-' + action, '')
    operation = 'remembered-overlay-riley-read'
    request = RequestObservation.from_request(reader.run(operation, '')['request'], operation=operation)
    assert request.child == 'fixture-child' and request.approver == 'other-fixture-parent'
    assert request.duration_seconds == 150 and request.custom_text == '2.5' and request.allow_soft is False
    assert reader.run('transfer-overlay-riley-refused', '')['outcome'] == 'passed'


def test_overlay_about_license_shared_reader_and_unchanged_form(
        launch_ui, automation, wait_for_accessible_state, monkeypatch):
    from gi.repository import GLib
    from tests.e2e.accessible_ui import AccessibleUI, CHILD, EXISTING_CHILD, PARENT, OTHER_PARENT
    from tests.support.gui_blocks import run_block
    from tests.support.paths import ROOT

    launch_ui('child_overlay_preview')
    ui = automation
    wait_for_accessible_state(lambda: ui.find('kiosk-request-submit') is not None,
                              'overlay form available')
    reader = AccessibleUI(ui.api, timeout=15, query_errors=ui.query_errors,
        owner_pids=ui.owner_pids, application_ids=ui.application_ids,
        application_owners=ui.application_owners, application_owner_history=ui.application_owner_history,
        fixture_uids={CHILD: 1001, EXISTING_CHILD: 1002, PARENT: 1000, OTHER_PARENT: 1010},
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    monkeypatch.setattr(reader, 'require_child_overlay_session', lambda child=CHILD: None)
    # This preview declares synthetic approvers, independent of host OS accounts.
    # Keep the shared reader's exact offered-account check against that fixture.
    monkeypatch.setattr(reader, 'interactive_approver_uids', lambda: {'1000', '1010'})
    for operation in ('overlay-valid-approver-select', 'overlay-valid-custom-open'):
        reader.run(operation, '')
    run_block(reader, 'replace', 'overlay-fraction')
    reader.run('overlay-valid-fraction-soft-select', '')
    before = reader.run('overlay-valid-fraction-soft-read', '')['valid_choice']['request']
    version = json.loads((ROOT / 'data/app.json').read_text())['version']
    reader.run('overlay-about-refused', version)
    reader.run('overlay-help-read', version)
    reader.run('overlay-information-about', version)
    reader.run('overlay-license-read', version)
    reader.run('overlay-website-read', version)
    reader.run('overlay-privacy-read', version)
    reader.run('overlay-support-read', version)
    reader.run('overlay-legal-notices-read', version)
    reader.run('overlay-about-close-ready', version)
    # The shared operation owns the close action and verifies return to the form.
    reader.run('overlay-about-closed', version)
    assert reader.run('overlay-valid-fraction-soft-read', '')['valid_choice']['request'] == before


def test_shared_overlay_choice_adapter_and_fractional_text_on_native_gtk(
        launch_ui, automation, wait_for_accessible_state, monkeypatch):
    from gi.repository import GLib
    from tests.e2e.accessible_ui import AccessibleUI, CHILD, EXISTING_CHILD, PARENT, OTHER_PARENT, KIOSK_INVALID_VALUES
    from tests.e2e.ui_observations import RequestObservation
    from tests.support.gui_blocks import run_block

    launch_ui('child_overlay_preview')
    ui = automation
    wait_for_accessible_state(lambda: ui.find('kiosk-request-submit') is not None,
                              'overlay form available')
    reader = AccessibleUI(ui.api, timeout=15, query_errors=ui.query_errors,
        owner_pids=ui.owner_pids, application_ids=ui.application_ids,
        application_owners=ui.application_owners, application_owner_history=ui.application_owner_history,
        fixture_uids={CHILD: 1001, EXISTING_CHILD: 1002, PARENT: 1000, OTHER_PARENT: 1010},
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    # Host preview identity is supplied by its process owner, not a guest login.
    monkeypatch.setattr(reader, 'require_child_overlay_session', lambda child=CHILD: None)
    # This preview declares synthetic approvers, independent of host OS accounts.
    # Keep the shared reader's exact offered-account check against that fixture.
    monkeypatch.setattr(reader, 'interactive_approver_uids', lambda: {'1000', '1010'})
    reader.run('overlay-valid-refusals', '')
    for operation in ('overlay-valid-approver-select', 'overlay-valid-preset-select',
                      'overlay-valid-preset-read', 'overlay-valid-custom-open'):
        reader.run(operation, '')
    run_block(reader, 'replace', 'overlay-fraction')
    result = reader.run('overlay-valid-fraction-read', '')
    request = RequestObservation.from_request(result['valid_choice']['request'],
                                             operation='overlay-valid-fraction-read')
    assert request.duration_seconds == 75 and request.custom_text == '1.25'
    assert request.child == 'fixture-child' and request.child_selector_enabled is False
    for operation in ('overlay-valid-rest-select', 'overlay-valid-rest-read',
                      'overlay-valid-soft-select', 'overlay-valid-soft-read',
                      'overlay-valid-excluded-select', 'overlay-valid-excluded-read'):
        reader.run(operation, '')
    reader.run('overlay-valid-custom-open', '')
    for binding, value in KIOSK_INVALID_VALUES.items():
        run_block(reader, 'replace', 'overlay-invalid-' + binding)
        for action in ('ready', 'submit', 'read'):
            operation = f'overlay-invalid-{binding}-{action}'
            result = reader.run(operation, '')
            request = RequestObservation.from_request(result['invalid_choice']['request'], operation=operation)
            assert request.custom_text == value and request.request_enabled
    reader.run('overlay-request-cancel', '')
    wait_for_accessible_state(lambda: ui.find('kiosk-request-window') is None,
                              'shared exit closed overlay')


@pytest.fixture
def request_ui(automation):
    return automation


def open_request(launch_ui, tmp_path, ui, wait, *, overlay, scenario="normal",
                 selections_path=None, loading_release=None, request_release=None):
    _process, path = launch_request(
        launch_ui, tmp_path, overlay=overlay, scenario=scenario,
        selections_path=selections_path, wait_for_application=False,
        loading_release=loading_release,
        request_release=request_release,
    )
    wait(lambda: ui.find("kiosk-request-window") is not None,
         "request window publishes its ID")
    wait(lambda: ui.find("kiosk-request-submit") is not None,
         "request action publishes its ID")
    return path


def ready(ui, wait):
    def request_is_ready():
        button = ui.find("kiosk-request-submit")
        return button is not None and button.get_state_set().contains(ui.api.StateType.SENSITIVE)

    wait(request_is_ready, "request controls ready")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_custom_hours_save_restore_and_submit(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    ui, wait = request_ui, wait_for_accessible_state
    path = open_request(launch_ui, tmp_path, ui, wait, overlay=overlay)
    ready(ui, wait)
    ui.activate("kiosk-duration-custom")
    assert ui.getValue("kiosk-custom-duration-units") == "minutes"
    assert ui.getChoices("kiosk-custom-duration-units") == ["minutes", "hours"]
    assert ui.getText("kiosk-custom-duration-units") == "minutes"
    assert ui.getValue("kiosk-custom-duration-unit-minutes") is True
    assert ui.getValue("kiosk-custom-duration-unit-hours") is False
    ui.setValue("kiosk-custom-duration-units", "hours")
    assert ui.getValue("kiosk-custom-duration-unit-hours") is True
    assert ui.getValue("kiosk-custom-duration-unit-minutes") is False
    ui.activate("kiosk-custom-duration-unit-minutes")
    assert ui.getValue("kiosk-custom-duration-units") == "minutes"
    ui.activate("kiosk-custom-duration-unit-hours")
    assert ui.getValue("kiosk-custom-duration-units") == "hours"
    assert ui.getText("kiosk-custom-duration-units") == "hours"
    ui.setText("kiosk-custom-duration", "1.5")
    wait(lambda: any(call["values"][1:] == ["custom", 90.0, False, 1000, "hours"]
                     for call in calls(path, "UpdateRequestPreferencesWithUnit")),
         "hours and equivalent minutes saved together")
    if not overlay:
        ui.setValue("kiosk-child-selector", "1002")
        ready(ui, wait)
        ui.activate("kiosk-duration-custom")
        assert ui.getValue("kiosk-custom-duration-units") == "minutes"
        ui.setValue("kiosk-child-selector", "1001")
        wait(lambda: ui.getValue("kiosk-custom-duration-units") == "hours",
             "first child's unit restored")
        assert ui.getValue("kiosk-custom-duration-unit-hours") is True
        assert ui.getValue("kiosk-custom-duration-unit-minutes") is False
        assert ui.getText("kiosk-custom-duration") == "1.5"
    ui.activate("kiosk-request-submit")
    method = "RequestOwnAccess" if overlay else "RequestAccess"
    wait(lambda: bool(calls(path, method)), "hour duration submitted")
    assert calls(path, method)[0]["values"] == (
        [1000, 5400, False] if overlay else [1001, 1000, 5400, False])


def status(ui, wait, expected):
    wait(lambda: ui.text("kiosk-request-status") == expected, expected)


def approved_status(ui, wait, expected, *, text=None):
    wait(lambda: (node := ui.find("kiosk-approved-status")) is not None
         and node.getValue() == expected, f"Approved time status is {expected}")
    if text is not None:
        assert ui.showing("kiosk-approved-status")
        assert ui.getText("kiosk-approved-status") == text


def lock_confirmation(ui):
    client = ui.target("kiosk-request-window").client
    modal = client.getSurfaceById("kiosk-lock-confirmation")
    metadata, = [surface for surface in client.listSurfaces() if surface["id"] == modal.id]
    assert metadata["visible"] and metadata["modal"]
    assert metadata["parent_id"] == "kiosk-request-window"
    return modal


def assert_lock_confirmation_copy(modal, title, duration):
    assert modal.getText("kiosk-lock-title") == title
    body = modal.getText("kiosk-lock-body")
    assert f"About {duration} will be saved." in body
    assert all(detail in body for detail in ("lock now", "password", "Approved time", "request station"))


def wait_for_confirmation_closed(ui, wait):
    client = ui.target("kiosk-request-window").client
    wait(lambda: not any(surface["id"] == "kiosk-lock-confirmation" and surface["visible"]
                        for surface in client.listSurfaces()), "lock confirmation closes")
    assert ui.showing("kiosk-request-window")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_approved_time_tabs_preserve_request_choices_and_show_combined_balances(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    ui, wait = request_ui, wait_for_accessible_state
    path = open_request(launch_ui, tmp_path, ui, wait, overlay=overlay, scenario="approved-combined")
    ready(ui, wait)
    assert ui.getValue("kiosk-request-tabs") == "request"
    assert ui.getText("kiosk-tab-request") == "Request time"
    assert ui.getText("kiosk-tab-approved") == "Approved time"
    assert ui.absent("kiosk-preferences-button", within="kiosk-request-window")
    assert ui.absent("kiosk-request-logo", within="kiosk-request-window")
    assert ui.getValue("kiosk-tab-request") is True
    assert ui.getValue("kiosk-tab-approved") is False
    assert ui.showing("kiosk-approver-selector")
    ui.setValue("kiosk-approver-selector", "1010")
    ui.setValue("kiosk-duration", "custom")
    ui.setValue("kiosk-custom-duration-units", "hours")
    ui.setText("kiosk-custom-duration", "1.25")
    ui.setValue("kiosk-soft-apps-toggle", True)

    ui.activate("kiosk-tab-approved")
    approved_status(ui, wait, "ready")
    assert ui.getValue("kiosk-request-tabs") == "approved"
    assert ui.getValue("kiosk-tab-request") is False
    assert ui.getValue("kiosk-tab-approved") is True
    ui.activate("kiosk-tab-approved")
    assert ui.getValue("kiosk-tab-approved") is True
    assert not ui.showing("kiosk-approver-selector")
    assert not ui.showing("kiosk-request-submit")
    assert not ui.showing("kiosk-request-status")
    assert ui.showing("kiosk-request-cancel")
    assert ui.showing("kiosk-child-selector")
    assert ui.getValue("kiosk-child-selector") == "1001"
    assert ui.state("kiosk-child-selector", ui.api.StateType.SENSITIVE) is (not overlay)
    assert 1020 <= ui.getValue("kiosk-approved-running") <= 1080
    assert ui.getValue("kiosk-approved-saved") == 1200
    assert ui.getText("kiosk-approved-saved") == "20m"
    assert ui.getText("kiosk-approved-use-saved") == "Add saved time to the timer"

    ui.setValue("kiosk-request-tabs", "request")
    assert ui.getValue("kiosk-tab-request") is True
    assert ui.showing("kiosk-request-submit")
    assert ui.showing("kiosk-request-status")
    assert ui.showing("kiosk-approver-selector")
    assert ui.getValue("kiosk-approver-selector") == "1010"
    assert ui.getValue("kiosk-duration") == "custom"
    assert ui.getValue("kiosk-custom-duration-units") == "hours"
    assert ui.getText("kiosk-custom-duration") == "1.25"
    assert ui.getValue("kiosk-soft-apps-toggle") is True
    assert not (calls(path, "PauseGrant") or calls(path, "UseSavedTime")
                or calls(path, "RequestDeferredAccess") or calls(path, "RequestAccess")
                or calls(path, "RequestOwnAccess"))

    if not overlay:
        ui.setValue("kiosk-request-tabs", "approved")
        ui.setValue("kiosk-child-selector", "1002")
        wait(lambda: ui.showing("kiosk-approved-saved")
             and ui.getValue("kiosk-approved-saved") == 480, "new child's saved balance")
        assert ui.getValue("kiosk-request-tabs") == "approved"
        assert not ui.showing("kiosk-approved-running")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_approved_time_pause_pending_and_saved_balance(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    ui, wait = request_ui, wait_for_accessible_state
    release = tmp_path / "pause-release"
    path = open_request(launch_ui, tmp_path, ui, wait, overlay=overlay,
                        scenario="approved-running", request_release=release)
    ready(ui, wait)
    ui.activate("kiosk-tab-approved")
    approved_status(ui, wait, "ready")
    assert ui.getText("kiosk-approved-running-status") == "Timer running"
    assert 1020 <= ui.getValue("kiosk-approved-running") <= 1080
    assert 660 <= ui.getValue("kiosk-approved-daily") <= 720
    assert not ui.showing("kiosk-approved-use-saved")

    try:
        ui.activate("kiosk-approved-pause")
        if overlay:
            modal = lock_confirmation(ui)
            assert_lock_confirmation_copy(modal, "Pause and lock the screen?", "18m")
            modal.activate(modal.id)
            wait_for_confirmation_closed(ui, wait)
            assert ui.getValue("kiosk-request-tabs") == "approved"
            assert not calls(path, "PauseGrant")

            ui.activate("kiosk-approved-pause")
            lock_confirmation(ui).close()
            wait_for_confirmation_closed(ui, wait)
            assert not calls(path, "PauseGrant")

            ui.activate("kiosk-approved-pause")
            modal = lock_confirmation(ui)
            assert modal.getText("kiosk-lock-confirm") == "Pause and lock"
            modal.activate("kiosk-lock-confirm")
        wait_for_confirmation_closed(ui, wait)
        approved_status(ui, wait, "pending", text="Updating approved time…")
        assert [item["values"] for item in calls(path, "PauseGrant")] == [[1001, 5]]
        assert not ui.state("kiosk-tab-request", ui.api.StateType.SENSITIVE)
        assert not ui.state("kiosk-child-selector", ui.api.StateType.SENSITIVE)
        assert ui.getValue("kiosk-child-selector") == "1001"
        assert not ui.showing("kiosk-approved-pause")
        assert not ui.showing("kiosk-approved-use-saved")
    finally:
        release.touch()

    if overlay:
        wait(lambda: bool(events(path, "close_overlay")), "pause closes behind the lock")
        return
    approved_status(ui, wait, "ready")
    assert not ui.showing("kiosk-approved-running")
    assert ui.getValue("kiosk-approved-saved") == 1080
    assert ui.getText("kiosk-approved-use-saved") == "Use saved time"
    assert ui.getText("kiosk-approved-saved-hint") == (
        "Add it to your time now." if overlay else "Start the timer and return to sign-in."
    )
    ui.activate("kiosk-approved-use-saved")
    assert [item["values"] for item in calls(path, "UseSavedTime")] == [[1001, 6]]
    wait(lambda: ui.showing("kiosk-result-title")
         and ui.getText("kiosk-result-title") == "Timer running", "timer started confirmation")
    wait(lambda: bool(events(path, "logout")), "started timer returns to sign-in")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
@pytest.mark.parametrize("scenario", ("approved-covered", "approved-deadline"))
def test_approved_time_grants_without_pausable_balance(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay, scenario):
    ui, wait = request_ui, wait_for_accessible_state
    open_request(launch_ui, tmp_path, ui, wait, overlay=overlay, scenario=scenario)
    ready(ui, wait)
    ui.activate("kiosk-tab-approved")
    approved_status(ui, wait, "ready")
    running_status = ui.getText("kiosk-approved-running-status")
    if scenario == "approved-covered":
        assert running_status == "Covered by today's daily time"
        assert 660 <= ui.getValue("kiosk-approved-daily") <= 720
        assert not ui.showing("kiosk-approved-running")
    else:
        assert re.fullmatch(r"Approved until (?:[01][0-9]|2[0-3]):[0-5][0-9]", running_status)
    assert not ui.showing("kiosk-approved-pause")
    assert not ui.showing("kiosk-approved-use-saved")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_grant_status_retry_works_from_both_tabs_until_daily_only_is_known(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    ui, wait = request_ui, wait_for_accessible_state
    path = open_request(launch_ui, tmp_path, ui, wait, overlay=overlay, scenario="approved-retry")
    status(ui, wait, "Time controls are busy. Try again.")
    assert ui.getValue("kiosk-request-tabs") == "request"
    assert not ui.state("kiosk-tab-approved", ui.api.StateType.SENSITIVE)
    ui.activate("kiosk-request-retry")
    ready(ui, wait)
    ui.activate("kiosk-tab-approved")
    approved_status(ui, wait, "unavailable", text="Time status unavailable")
    assert not ui.showing("kiosk-approved-running")
    assert not ui.showing("kiosk-approved-saved")
    assert not ui.showing("kiosk-approved-daily")
    ui.activate("kiosk-approved-retry")
    approved_status(ui, wait, "busy", text="Time controls are busy. Try again.")
    assert not ui.state("kiosk-tab-request", ui.api.StateType.SENSITIVE)
    assert not ui.state("kiosk-child-selector", ui.api.StateType.SENSITIVE)
    ui.activate("kiosk-approved-retry")
    approved_status(ui, wait, "recovery", text="Time status unavailable")
    assert not ui.showing("kiosk-approved-pause")
    assert not ui.showing("kiosk-approved-use-saved")
    ui.activate("kiosk-approved-retry")
    approved_status(ui, wait, "empty", text="No approved time available")
    assert len(calls(path, "GetGrantStatus")) == 5
    assert not ui.showing("kiosk-approved-retry")
    assert not ui.showing("kiosk-approved-pause")
    assert not ui.showing("kiosk-approved-use-saved")
    assert 660 <= ui.getValue("kiosk-approved-daily") <= 720
    ui.activate("kiosk-approved-request-more")
    assert ui.getValue("kiosk-request-tabs") == "request"


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_save_for_later_menu_dismisses_or_dispatches_selected_action(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    ui, wait = request_ui, wait_for_accessible_state
    path = open_request(launch_ui, tmp_path, ui, wait, overlay=overlay, scenario="approved-running")
    ready(ui, wait)
    status(ui, wait, "Estimated remaining time: 1h")
    assert ui.getValue("kiosk-request-menu") is False
    assert not ui.showing("kiosk-request-save-for-later")
    ui.activate("kiosk-request-menu")
    assert ui.getValue("kiosk-request-menu") is True
    assert ui.showing("kiosk-request-save-for-later")
    assert ui.getText("kiosk-request-save-hint") == "Saved if approved: 48m"
    ui.setValue("kiosk-request-menu", False)
    assert ui.getValue("kiosk-request-menu") is False
    assert ui.showing("kiosk-request-submit")
    assert not calls(path, "RequestDeferredAccess")

    ui.setValue("kiosk-duration", "custom")
    ui.setText("kiosk-custom-duration", "0.09")
    ui.activate("kiosk-request-menu")
    ui.activate("kiosk-request-save-for-later")
    status(ui, wait, "Enter a number from 0.1 to 1440 minutes.")
    assert ui.getValue("kiosk-request-menu") is False
    assert not calls(path, "RequestDeferredAccess")
    ui.setValue("kiosk-duration", "1800")

    ui.setValue("kiosk-request-menu", True)
    wait(lambda: ui.state("kiosk-request-save-for-later", ui.api.StateType.SENSITIVE),
         "saved estimate ready")
    ui.activate("kiosk-request-save-for-later")
    assert ui.getValue("kiosk-request-menu") is False
    if overlay:
        modal = lock_confirmation(ui)
        assert_lock_confirmation_copy(modal, "Save for later and lock?", "48m")
        assert modal.getText("kiosk-lock-cancel") == "Cancel"
        modal.activate("kiosk-lock-cancel")
        wait_for_confirmation_closed(ui, wait)
        assert not calls(path, "RequestDeferredAccess")
        ui.activate("kiosk-request-menu")
        ui.activate("kiosk-request-save-for-later")
        modal = lock_confirmation(ui)
        assert modal.getText("kiosk-lock-confirm") == "Continue"
        modal.activate("kiosk-lock-confirm")
    wait_for_confirmation_closed(ui, wait)
    assert [item["values"] for item in calls(path, "RequestDeferredAccess")] == [[1001, 1000, 1800, False, 5]]
    assert not calls(path, "RequestOwnAccess" if overlay else "RequestAccess")
    if overlay:
        wait(lambda: bool(events(path, "close_overlay")), "saved approval closes behind the lock")
    else:
        approved_status(ui, wait, "ready")
        assert ui.getValue("kiosk-request-tabs") == "approved"
        assert ui.getValue("kiosk-approved-saved") == 2880
        assert not events(path, "logout")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_saved_approval_without_pause_stays_open_until_saved_time_is_used(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    ui, wait = request_ui, wait_for_accessible_state
    path = open_request(launch_ui, tmp_path, ui, wait, overlay=overlay)
    status(ui, wait, "Estimated remaining time: 1h 17m")
    ui.activate("kiosk-request-menu")
    assert ui.getText("kiosk-request-save-hint") == "Saved if approved: 30m"
    ui.activate("kiosk-request-save-for-later")
    approved_status(ui, wait, "ready")
    assert ui.getValue("kiosk-request-tabs") == "approved"
    assert ui.getValue("kiosk-approved-saved") == 1800
    assert len(events(path, "countdown-refresh")) == int(overlay)
    assert not events(path, "close_overlay") and not events(path, "logout")
    ui.activate("kiosk-approved-use-saved")
    wait(lambda: ui.showing("kiosk-result-title")
         and ui.getText("kiosk-result-title") == "Timer running", "timer started confirmation")
    assert len(events(path, "countdown-refresh")) == 2 * int(overlay)
    assert [item["values"] for item in calls(path, "UseSavedTime")] == [[1001, 6]]
    exit_event = "close_overlay" if overlay else "logout"
    wait(lambda: bool(events(path, exit_event)), "timer confirmation follows the surface exit")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_cancelled_parent_prompt_keeps_deferred_mode_and_request_choices(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    ui, wait = request_ui, wait_for_accessible_state
    release = tmp_path / "parent-cancel"
    path = open_request(launch_ui, tmp_path, ui, wait, overlay=overlay,
                        scenario="deferred-cancelled", request_release=release)
    status(ui, wait, "Estimated remaining time: 1h 17m")
    ui.setValue("kiosk-approver-selector", "1010")
    ui.setValue("kiosk-soft-apps-toggle", True)
    ui.activate("kiosk-request-menu")
    ui.activate("kiosk-request-save-for-later")
    try:
        status(ui, wait, "Waiting for approval…")
        for control in ("kiosk-request-submit", "kiosk-request-menu", "kiosk-tab-approved",
                        "kiosk-child-selector", "kiosk-approver-selector", "kiosk-request-cancel"):
            assert not ui.state(control, ui.api.StateType.SENSITIVE)
        wait(lambda: bool(calls(path, "RequestDeferredAccess")), "parent request dispatched")
    finally:
        release.touch()
    status(ui, wait, "Estimated remaining time: 1h 17m")
    assert ui.getValue("kiosk-approver-selector") == "1010"
    assert ui.getValue("kiosk-soft-apps-toggle") is True
    assert [item["values"] for item in calls(path, "RequestDeferredAccess")] == [[1001, 1010, 1800, True, 5]]
    assert not calls(path, "RequestOwnAccess" if overlay else "RequestAccess")
    assert not events(path, "countdown-refresh")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_saved_approval_with_pause_failure_shows_saved_and_running_time(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    ui, wait = request_ui, wait_for_accessible_state
    path = open_request(launch_ui, tmp_path, ui, wait, overlay=overlay, scenario="deferred-partial")
    status(ui, wait, "Estimated remaining time: 1h")
    ui.activate("kiosk-request-menu")
    ui.activate("kiosk-request-save-for-later")
    if overlay:
        lock_confirmation(ui).activate("kiosk-lock-confirm")
    approved_status(ui, wait, "ready")
    assert ui.getValue("kiosk-approved-saved") == 1800
    assert ui.getText("kiosk-approved-running-status") == "Timer running"
    assert ui.getText("kiosk-approved-feedback") == (
        "The timer could not be paused." if overlay else "Alex Morgan is using the desktop.")
    assert not events(path, "close_overlay") and not events(path, "logout")
    assert len(events(path, "countdown-refresh")) == int(overlay)


@pytest.mark.parametrize("scenario, message", (
    ("pause-stale", "The time status changed. Try again."),
    ("pause-after-lock", "The timer could not be paused."),
))
def test_overlay_pause_refusal_and_failure_keep_the_form_open(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, scenario, message):
    ui, wait = request_ui, wait_for_accessible_state
    path = open_request(launch_ui, tmp_path, ui, wait, overlay=True, scenario=scenario)
    ready(ui, wait)
    ui.activate("kiosk-tab-approved")
    approved_status(ui, wait, "ready")
    ui.activate("kiosk-approved-pause")
    lock_confirmation(ui).activate("kiosk-lock-confirm")
    wait(lambda: ui.showing("kiosk-approved-feedback")
         and ui.getText("kiosk-approved-feedback") == message, "pause failure is visible in the form")
    approved_status(ui, wait, "ready")
    assert ui.getText("kiosk-approved-running-status") == "Timer running"
    assert len(calls(path, "PauseGrant")) == 1
    assert len(calls(path, "GetGrantStatus")) >= 2
    assert not events(path, "close_overlay")


def test_lost_redemption_reply_rereads_after_recovery_without_using_twice(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path):
    ui, wait = request_ui, wait_for_accessible_state
    path = open_request(launch_ui, tmp_path, ui, wait, overlay=False, scenario="redeem-lost")
    ready(ui, wait)
    ui.activate("kiosk-tab-approved")
    approved_status(ui, wait, "ready")
    assert ui.getValue("kiosk-approved-saved") == 480
    ui.activate("kiosk-approved-use-saved")
    approved_status(ui, wait, "ready")
    wait(lambda: ui.showing("kiosk-approved-running"), "recovered running balance is visible")
    assert not ui.showing("kiosk-approved-saved")
    assert [item["values"] for item in calls(path, "UseSavedTime")] == [[1001, 5]]
    assert len(calls(path, "GetGrantStatus")) >= 3


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_shared_loading_keeps_controls_disabled_until_preferences_arrive(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    release = tmp_path / "preferences-release"
    try:
        path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                            overlay=overlay, scenario="loading", loading_release=release)
        wait_for_accessible_state(lambda: bool(calls(path, "GetPreferences")),
                                  "preferences request is pending")
        assert not request_ui.state("kiosk-request-submit", request_ui.api.StateType.SENSITIVE)
        request_ui.activate("kiosk-tab-approved")
        approved_status(request_ui, wait_for_accessible_state, "loading", text="Loading time status…")
        assert not request_ui.showing("kiosk-approved-saved")
        request_ui.activate("kiosk-tab-request")
        assert not events(path, "preferences-ready")
        assert not events(path, "preferences-release-timeout")
    finally:
        release.touch()
    wait_for_accessible_state(lambda: bool(events(path, "preferences-ready")),
                              "preferences response is delivered")
    ready(request_ui, wait_for_accessible_state)


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_control_disabled_never_submits(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay, scenario="control-disabled")
    wait_for_accessible_state(
        lambda: request_ui.text("kiosk-screen-limit-notice") ==
        "Screen limit is not enabled in Parent App", "disabled-screen explanation")
    assert not request_ui.state("kiosk-request-submit", request_ui.api.StateType.SENSITIVE)
    request_ui.activate("kiosk-tab-approved")
    approved_status(request_ui, wait_for_accessible_state, "disabled",
                    text="Screen limit is not enabled in Parent App")
    assert not request_ui.showing("kiosk-approved-pause")
    assert not request_ui.showing("kiosk-approved-use-saved")
    assert not calls(path, "RequestOwnAccess" if overlay else "RequestAccess")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_no_approver_explains_why_request_is_unavailable(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay, scenario="no-approvers")
    status(request_ui, wait_for_accessible_state,
           "No local interactive administrator accounts are available.")
    assert not request_ui.state("kiosk-request-submit", request_ui.api.StateType.SENSITIVE)
    assert not calls(path, "RequestOwnAccess" if overlay else "RequestAccess")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_shared_predefined_approver_and_soft_choices_submit(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    ui = request_ui
    path = open_request(launch_ui, tmp_path, ui, wait_for_accessible_state,
                        overlay=overlay)
    ready(ui, wait_for_accessible_state)
    ui.setValue("kiosk-approver-selector", "1010")
    ui.activate("kiosk-duration-300")
    ui.setValue("kiosk-soft-apps-toggle", True)
    ui.activate("kiosk-request-submit")
    method = "RequestOwnAccess" if overlay else "RequestAccess"
    wait_for_accessible_state(lambda: bool(calls(path, method)), "submitted request")
    assert calls(path, method)[0]["values"] == (
        [1010, 300, True] if overlay else [1001, 1010, 300, True]
    )


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_shared_rest_of_day_choice_submits_zero_seconds(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay, scenario="rest-of-day")
    ready(request_ui, wait_for_accessible_state)
    request_ui.activate("kiosk-request-menu")
    assert request_ui.showing("kiosk-request-save-for-later")
    assert not request_ui.state("kiosk-request-save-for-later", request_ui.api.StateType.SENSITIVE)
    assert request_ui.getText("kiosk-request-save-hint") == "Rest of the day can't be saved."
    request_ui.setValue("kiosk-request-menu", False)
    assert not events(path, "request-save-for-later")
    request_ui.activate("kiosk-request-submit")
    method = "RequestOwnAccess" if overlay else "RequestAccess"
    wait_for_accessible_state(lambda: bool(calls(path, method)), "rest-of-day request")
    assert calls(path, method)[0]["values"] == (
        [1000, 0, False] if overlay else [1001, 1000, 0, False]
    )


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_responsive_form_accepts_semantic_selection_and_submission(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    ui, wait = request_ui, wait_for_accessible_state
    path = open_request(launch_ui, tmp_path, ui, wait, overlay=overlay)
    ready(ui, wait)
    ui.activate("kiosk-duration-300")
    ui.activate("kiosk-request-submit")
    method = "RequestOwnAccess" if overlay else "RequestAccess"
    wait_for_accessible_state(lambda: bool(calls(path, method)), "submitted request")
    assert calls(path, method)[0]["values"] == (
        [1000, 300, False] if overlay else [1001, 1000, 300, False]
    )


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_shared_custom_duration_preserves_fractional_minute_precision(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay, scenario="remembered")
    ready(request_ui, wait_for_accessible_state)
    request_ui.activate("kiosk-request-submit")
    method = "RequestOwnAccess" if overlay else "RequestAccess"
    wait_for_accessible_state(lambda: bool(calls(path, method)), "custom-duration request")
    assert calls(path, method)[0]["values"] == (
        [1010, 150, True] if overlay else [1001, 1010, 150, True]
    )


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
@pytest.mark.parametrize("seconds", (1800, 2700), ids=("30-minute-preset", "45-minute-custom"))
def test_custom_45_minutes_and_30_minute_preset_submit_distinct_durations(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay, seconds):
    ui = request_ui
    path = open_request(launch_ui, tmp_path, ui, wait_for_accessible_state,
                        overlay=overlay, scenario="remembered")
    ready(ui, wait_for_accessible_state)
    ui.setText("kiosk-custom-duration", "45")
    wait_for_accessible_state(
        lambda: any(call["values"][1:3] == ["custom", 45.0]
                    for call in calls(path, "UpdateRequestPreferencesWithUnit")),
        "custom 45-minute choice saved",
    )
    if seconds == 1800:
        assert ui.target("kiosk-duration-1800").get_name() == "Request 30 minutes"
        ui.activate("kiosk-duration-1800")
        wait_for_accessible_state(
            lambda: any(call["values"][1] == "1800"
                        for call in calls(path, "UpdateRequestPreferencesWithUnit")),
            "30-minute preset replaces custom choice",
        )
    ui.activate("kiosk-request-submit")
    method = "RequestOwnAccess" if overlay else "RequestAccess"
    wait_for_accessible_state(lambda: bool(calls(path, method)), "duration submitted")
    assert calls(path, method)[0]["values"] == (
        [1010, seconds, True] if overlay else [1001, 1010, seconds, True]
    )


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
@pytest.mark.parametrize("scenario", ("custom-too-small", "custom-too-large"))
def test_shared_custom_duration_rejects_values_outside_range(
        launch_ui, request_ui, wait_for_accessible_state,
        tmp_path, overlay, scenario):
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay, scenario=scenario)
    ready(request_ui, wait_for_accessible_state)
    request_ui.activate("kiosk-request-submit")
    status(request_ui, wait_for_accessible_state,
           "Enter a number from 0.1 to 1440 minutes.")
    assert not calls(path, "RequestOwnAccess" if overlay else "RequestAccess")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_custom_hours_range_feedback(launch_ui, request_ui, wait_for_accessible_state,
                                     tmp_path, overlay):
    ui = request_ui
    path = open_request(launch_ui, tmp_path, ui, wait_for_accessible_state,
                        overlay=overlay, scenario="custom-too-large")
    ready(ui, wait_for_accessible_state)
    ui.setValue("kiosk-custom-duration-units", "hours")
    ui.setText("kiosk-custom-duration", "200")
    status(ui, wait_for_accessible_state, "Allowed range: 0.0016666667 – 24 hours.")
    ui.activate("kiosk-request-submit")
    status(ui, wait_for_accessible_state, "Allowed range: 0.0016666667 – 24 hours.")
    assert not calls(path, "RequestOwnAccess" if overlay else "RequestAccess")


def test_kiosk_child_selection_reloads_that_childs_preferences(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path):
    ui = request_ui
    path = open_request(launch_ui, tmp_path, ui, wait_for_accessible_state,
                        overlay=False)
    ready(ui, wait_for_accessible_state)
    ui.activate("kiosk-child-selector")
    ui.activate("kiosk-child-choice-1002")
    wait_for_accessible_state(
        lambda: any(call["values"] == [1002] for call in calls(path, "GetPreferences")),
        "selected child's preferences",
    )


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
@pytest.mark.parametrize("stale", (False, True), ids=("remembered", "removed-accounts"))
def test_local_selections_restore_only_eligible_accounts(
        launch_ui, request_ui, wait_for_accessible_state,
        tmp_path, overlay, stale):
    selections = tmp_path / "request-selections.json"
    selections.write_text(json.dumps({
        "child_uid": 9999 if stale else 1002,
        "approver_uid": 9998 if stale else 1010,
    }))
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay, selections_path=selections)
    ready(request_ui, wait_for_accessible_state)
    target = 1001 if overlay or stale else 1002
    approver = 1000 if stale else 1010
    assert calls(path, "GetPreferences")[0]["values"] == [target]
    if overlay:
        assert not request_ui.state("kiosk-child-selector", request_ui.api.StateType.SENSITIVE)
        assert not calls(path, "ListManagedUsers")
        assert json.loads(selections.read_text())["child_uid"] == (9999 if stale else 1002)
    request_ui.activate("kiosk-request-submit")
    method = "RequestOwnAccess" if overlay else "RequestAccess"
    wait_for_accessible_state(lambda: bool(calls(path, method)), "request with local selections")
    assert calls(path, method)[0]["values"] == (
        [approver, 1800, False] if overlay else [target, approver, 1800, False]
    )


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_local_selection_changes_are_saved_before_submission(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    selections = tmp_path / "request-selections.json"
    ui = request_ui
    path = open_request(launch_ui, tmp_path, ui, wait_for_accessible_state,
                        overlay=overlay, selections_path=selections)
    ready(ui, wait_for_accessible_state)
    ui.setValue("kiosk-approver-selector", "1010")
    wait_for_accessible_state(
        lambda: selections.exists() and json.loads(selections.read_text()).get("approver_uid") == 1010,
        "locally saved approver",
    )
    if not overlay:
        ui.setValue("kiosk-child-selector", "1002")
        wait_for_accessible_state(
            lambda: json.loads(selections.read_text()).get("child_uid") == 1002,
            "locally saved child",
        )
        ready(ui, wait_for_accessible_state)
    stored = json.loads(selections.read_text())
    assert stored == ({"approver_uid": 1010} if overlay else
                      {"child_uid": 1002, "approver_uid": 1010})
    assert not calls(path, "RequestOwnAccess" if overlay else "RequestAccess")


def test_kiosk_no_child_explains_how_to_continue(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path):
    open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                 overlay=False, scenario="no-children")
    status(request_ui, wait_for_accessible_state,
           "No local standard accounts are available. Create one, then reopen this screen.")


def test_child_overlay_uses_fixed_child_identity(launch_ui, request_ui,
                                                  wait_for_accessible_state, tmp_path):
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=True)
    wait_for_accessible_state(
        lambda: bool(calls(path, "GetOwnAccount")), "own child identity lookup",
    )
    assert not request_ui.state("kiosk-child-selector", request_ui.api.StateType.SENSITIVE)
    assert not calls(path, "ListManagedUsers")


@pytest.mark.parametrize("overlay, scenario, expected", (
    (False, "denied", "Request denied"), (True, "denied", "Request denied"),
    (False, "cancelled", "Estimated remaining time: 1h 17m"),
    (True, "cancelled", "Estimated remaining time: 1h 17m"),
))
def test_outcomes_are_actionable_and_redacted(launch_ui, request_ui,
                                              wait_for_accessible_state, tmp_path,
                                              overlay, scenario, expected):
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay, scenario=scenario)
    ready(request_ui, wait_for_accessible_state)
    request_ui.activate("kiosk-request-submit")
    method = "RequestOwnAccess" if overlay else "RequestAccess"
    wait_for_accessible_state(lambda: bool(calls(path, method)), "request outcome")
    if scenario == "denied":
        status(request_ui, wait_for_accessible_state, expected)
        ready(request_ui, wait_for_accessible_state)
    else:
        status(request_ui, wait_for_accessible_state, expected)


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_service_failure_shows_only_redacted_public_copy(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                 overlay=overlay, scenario="service-failure")
    ready(request_ui, wait_for_accessible_state)
    request_ui.activate("kiosk-request-submit")
    wait_for_accessible_state(
        lambda: request_ui.showing("kiosk-result-title")
        and request_ui.getText("kiosk-result-title") == "Request unavailable",
        "redacted failure title is public",
    )
    detail = request_ui.getText("kiosk-result-detail")
    assert "org.example" not in detail
    assert "/private/path" not in detail


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_single_flight_disables_request_controls_while_authentication_is_active(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    release = tmp_path / "request-release"
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay, scenario="slow-request", request_release=release)
    ready(request_ui, wait_for_accessible_state)
    try:
        request_ui.activate("kiosk-request-submit")
        wait_for_accessible_state(
            lambda: not request_ui.state("kiosk-request-submit", request_ui.api.StateType.SENSITIVE),
            "single-flight request is disabled")
        method = "RequestOwnAccess" if overlay else "RequestAccess"
        wait_for_accessible_state(lambda: len(calls(path, method)) == 1,
                                  "one in-flight request")
        assert not request_ui.state("kiosk-request-cancel", request_ui.api.StateType.SENSITIVE)
        # Observe the disabled form while the single request is in flight.
        assert request_ui.showing("kiosk-request-window")
        assert request_ui.showing("kiosk-request-submit")
        assert not request_ui.state("kiosk-request-submit", request_ui.api.StateType.SENSITIVE)
        assert request_ui.absent("kiosk-result-title", within="kiosk-request-window")
        assert len(calls(path, method)) == 1
    finally:
        # Complete the synthetic authentication after checking the busy form.
        release.touch()
    expected = "Time granted" if overlay else "Request approved"
    wait_for_accessible_state(
        lambda: request_ui.showing("kiosk-result-title")
        and request_ui.getText("kiosk-result-title") == expected,
        "completed request is public")
    assert request_ui.showing("kiosk-request-window")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_mute_control_stays_hidden_with_remembered_preferences(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay, scenario="remembered")
    ready(request_ui, wait_for_accessible_state)
    assert request_ui.absent("kiosk-mute-button", within="kiosk-request-window")
    assert not calls(path, "SetRequestMuted")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_cancel_uses_each_modes_idle_exit_behavior(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay)
    request_ui.activate("kiosk-request-cancel")
    expected = "close_overlay" if overlay else "logout"
    wait_for_accessible_state(lambda: bool(events(path, expected)), f"Cancel {expected}")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_result_action_uses_each_modes_exit_behavior(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay, scenario="service-failure")
    ready(request_ui, wait_for_accessible_state)
    request_ui.activate("kiosk-request-submit")
    wait_for_accessible_state(
        lambda: request_ui.showing("kiosk-result-title")
        and request_ui.getText("kiosk-result-title") == "Request unavailable",
        "failure result")
    wait_for_accessible_state(lambda: request_ui.find("kiosk-report-row") is not None,
                              "report choice published")
    request_ui.activate("kiosk-report-row")
    request_ui.activate("kiosk-result-action")
    expected = "close_overlay" if overlay else "logout"
    wait_for_accessible_state(lambda: bool(events(path, expected)), f"result {expected}")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_approval_uses_each_modes_result_exit_callback(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay)
    ready(request_ui, wait_for_accessible_state)
    request_ui.activate("kiosk-request-submit")
    wait_for_accessible_state(
        lambda: request_ui.showing("kiosk-result-title")
        and request_ui.getText("kiosk-result-title") == (
            "Time granted" if overlay else "Request approved"),
        "approval result is public",
    )
    expected = "close_overlay" if overlay else "logout"
    wait_for_accessible_state(lambda: bool(events(path, expected)), f"approved {expected}")
    assert len(events(path, "countdown-refresh")) == int(overlay)


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_footer_estimate_tracks_requested_duration(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay)
    status(request_ui, wait_for_accessible_state,
           "Estimated remaining time: 1h 17m")
    request_ui.activate("kiosk-duration-300")
    status(request_ui, wait_for_accessible_state,
           "Estimated remaining time: 52m")
    assert calls(path, "GetGrantStatus")[-1]["values"] == [1001, 300]


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
@pytest.mark.parametrize("scenario, expected", (
    ("rest-of-day", "If approved, access until midnight."),
    ("two-hours-grant-only", "Estimated remaining time: 2h"),
    ("estimate-unavailable", "Time estimate unavailable"),
))
def test_footer_special_cases_keep_requests_available(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay, scenario, expected):
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay, scenario=scenario)
    status(request_ui, wait_for_accessible_state, expected)
    assert request_ui.state("kiosk-request-submit", request_ui.api.StateType.SENSITIVE)
    if scenario == "estimate-unavailable":
        assert request_ui.absent("feedback-dialog", within="kiosk-request-window")
        request_ui.activate("kiosk-request-cancel")
        expected_exit = "close_overlay" if overlay else "logout"
        wait_for_accessible_state(lambda: bool(events(path, expected_exit)),
                                  "unavailable estimate leaves Cancel usable")
    if scenario == "rest-of-day":
        request_ui.activate("kiosk-request-menu")
        assert not request_ui.state("kiosk-request-save-for-later", request_ui.api.StateType.SENSITIVE)
        assert request_ui.getText("kiosk-request-save-hint") == "Rest of the day can't be saved."
        assert not calls(path, "GetTimeStatus")


def test_footer_estimate_changes_with_selected_child(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path):
    ui = request_ui
    path = open_request(launch_ui, tmp_path, ui, wait_for_accessible_state,
                        overlay=False)
    status(ui, wait_for_accessible_state,
           "Estimated remaining time: 1h 17m")
    ui.setValue("kiosk-child-selector", "1002")
    status(ui, wait_for_accessible_state,
           "Estimated remaining time: 45m")
    assert calls(path, "GetGrantStatus")[-1]["values"] == [1002, 1800]


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_older_broker_reports_saved_time_unavailable_and_can_still_approve_now(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    ui, wait = request_ui, wait_for_accessible_state
    path = open_request(launch_ui, tmp_path, ui, wait, overlay=overlay, scenario="older-broker")
    status(ui, wait, "Estimated remaining time: 1h 17m")
    ui.activate("kiosk-request-menu")
    assert not ui.state("kiosk-request-save-for-later", ui.api.StateType.SENSITIVE)
    ui.setValue("kiosk-request-menu", False)
    ui.activate("kiosk-tab-approved")
    approved_status(ui, wait, "unavailable", text="Time status unavailable")
    assert not ui.showing("kiosk-approved-saved")
    assert not ui.showing("kiosk-approved-pause")
    ui.activate("kiosk-tab-request")
    ui.activate("kiosk-request-submit")
    wait(lambda: ui.showing("kiosk-result-title"), "legacy approval result")
    assert ui.getText("kiosk-result-title") == ("Time granted" if overlay else "Request approved")
    assert len(calls(path, "RequestOwnAccess" if overlay else "RequestAccess")) == 1
    assert not calls(path, "RequestDeferredAccess")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_footer_estimate_tracks_custom_edits_and_preserves_validation(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    ui = request_ui
    open_request(launch_ui, tmp_path, ui, wait_for_accessible_state,
                 overlay=overlay, scenario="remembered")
    status(ui, wait_for_accessible_state,
           "Estimated remaining time: 49m 30s")
    for value, expected in (
        ("0.5", "Estimated remaining time: 47m 30s"),
        ("0.09", "Enter a number from 0.1 to 1440 minutes."),
        ("5", "Estimated remaining time: 52m"),
    ):
        ui.setText("kiosk-custom-duration", value)
        status(ui, wait_for_accessible_state, expected)
