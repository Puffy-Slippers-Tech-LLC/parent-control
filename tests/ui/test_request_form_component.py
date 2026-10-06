"""Semantic component coverage for the shared kiosk and child request form."""

from __future__ import annotations

import json

import pytest
from tests.support.events import read_events as records
from tests.support.request_form import launch_request, calls, events


pytestmark = pytest.mark.ui


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
    monkeypatch.setattr(reader, 'require_child_overlay_session', lambda: None)
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
    reader.close_id('about-dialog')
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
    monkeypatch.setattr(reader, 'require_child_overlay_session', lambda: None)
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


def status(ui, wait, expected):
    wait(lambda: ui.text("kiosk-request-status") == expected, expected)


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
    request_ui.activate("kiosk-request-submit")
    method = "RequestOwnAccess" if overlay else "RequestAccess"
    wait_for_accessible_state(lambda: bool(calls(path, method)), "rest-of-day request")
    assert calls(path, method)[0]["values"] == (
        [1000, 0, False] if overlay else [1001, 1000, 0, False]
    )


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_responsive_form_accepts_semantic_selection_and_submission(
        launch_ui, wait_for_accessible_state, tmp_path, overlay):
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi
    from tests.support.automation import Automation

    _application, path = launch_request(launch_ui, tmp_path, overlay=overlay,
                                       wait_for_application=False)
    ui = Automation(Atspi, lambda: Atspi.get_desktop(0), owner_pids=launch_ui.owner_pids,
                    application_ids=launch_ui.application_ids,
                    application_owners=launch_ui.application_owners,
                    complete_read_wait=wait_for_accessible_state)
    wait_for_accessible_state(lambda: ui.find("kiosk-request-submit") is not None,
                              "request surface publishes its controls")
    wait_for_accessible_state(
        lambda: ui.state("kiosk-request-submit", Atspi.StateType.SENSITIVE),
        "loaded request controls",
    )
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
                    for call in calls(path, "UpdateRequestPreferences")),
        "custom 45-minute choice saved",
    )
    if seconds == 1800:
        assert ui.target("kiosk-duration-1800").get_name() == "Request 30 minutes"
        ui.activate("kiosk-duration-1800")
        wait_for_accessible_state(
            lambda: any(call["values"][1] == "1800"
                        for call in calls(path, "UpdateRequestPreferences")),
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


def test_kiosk_child_selection_reloads_that_childs_preferences(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path):
    ui = request_ui
    path = open_request(launch_ui, tmp_path, ui, wait_for_accessible_state,
                        overlay=False)
    ready(ui, wait_for_accessible_state)
    ui.setValue("kiosk-child-selector", "1002")
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
    (False, "cancelled", "Estimated time remaining if approved: 1h 17m"),
    (True, "cancelled", "Estimated time remaining if approved: 1h 17m"),
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
def test_single_flight_refuses_cancel_while_authentication_is_active(
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
        from tests.support.automation import AutomationError
        with pytest.raises(AutomationError, match='application-ui:Unavailable'):
            request_ui.activate("kiosk-request-cancel")
        # Observe the real form after refusal, independently of the input and
        # synthetic broker log. Hidden result controls may remain inventoried.
        assert request_ui.showing("kiosk-request-window")
        assert request_ui.showing("kiosk-request-submit")
        assert not request_ui.state("kiosk-request-submit", request_ui.api.StateType.SENSITIVE)
        assert request_ui.absent("kiosk-result-title", within="kiosk-request-window")
    finally:
        # Complete the synthetic authentication only after checking refusal.
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


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_footer_estimate_tracks_requested_duration(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay)
    status(request_ui, wait_for_accessible_state,
           "Estimated time remaining if approved: 1h 17m")
    request_ui.activate("kiosk-duration-300")
    status(request_ui, wait_for_accessible_state,
           "Estimated time remaining if approved: 52m")
    assert calls(path, "GetTimeStatus")[-1]["values"] == [1001, 300]


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
@pytest.mark.parametrize("scenario, expected", (
    ("rest-of-day", "If approved, access until midnight."),
    ("two-hours-grant-only", "Estimated time remaining if approved: 2h"),
    ("estimate-unavailable", "Time estimate unavailable"),
))
def test_footer_special_cases_keep_requests_available(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay, scenario, expected):
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay, scenario=scenario)
    if scenario == "estimate-unavailable":
        # Dismiss the normal error report before checking the underlying form's
        # availability; the public API correctly blocks input behind a modal.
        wait_for_accessible_state(lambda: request_ui.showing("feedback-dialog"),
                                  "estimate error report opens")
        request_ui.activate("feedback-close")
        wait_for_accessible_state(
            lambda: request_ui.absent("feedback-dialog", within="kiosk-request-window"),
            "estimate error report closes")
    status(request_ui, wait_for_accessible_state, expected)
    assert request_ui.state("kiosk-request-submit", request_ui.api.StateType.SENSITIVE)
    if scenario == "rest-of-day":
        assert not calls(path, "GetTimeStatus")


def test_footer_estimate_changes_with_selected_child(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path):
    ui = request_ui
    path = open_request(launch_ui, tmp_path, ui, wait_for_accessible_state,
                        overlay=False)
    status(ui, wait_for_accessible_state,
           "Estimated time remaining if approved: 1h 17m")
    ui.setValue("kiosk-child-selector", "1002")
    status(ui, wait_for_accessible_state,
           "Estimated time remaining if approved: 45m")
    assert calls(path, "GetTimeStatus")[-1]["values"] == [1002, 1800]


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_footer_estimate_tracks_custom_edits_and_preserves_validation(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    ui = request_ui
    open_request(launch_ui, tmp_path, ui, wait_for_accessible_state,
                 overlay=overlay, scenario="remembered")
    status(ui, wait_for_accessible_state,
           "Estimated time remaining if approved: 49m 30s")
    for value, expected in (
        ("0.5", "Estimated time remaining if approved: 47m 30s"),
        ("0.09", "Enter a number from 0.1 to 1440 minutes."),
        ("5", "Estimated time remaining if approved: 52m"),
    ):
        ui.setText("kiosk-custom-duration", value)
        status(ui, wait_for_accessible_state, expected)
