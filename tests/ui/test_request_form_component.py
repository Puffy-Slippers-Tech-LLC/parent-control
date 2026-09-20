"""Semantic component coverage for the shared kiosk and child request form."""

from __future__ import annotations

import json

import pytest
from tests.support.events import read_events as records
from tests.support.request_form import launch_request, calls, events


pytestmark = pytest.mark.ui


@pytest.fixture
def request_ui(automation):
    return automation


def open_request(launch_ui, tmp_path, ui, wait, *, overlay, scenario="normal",
                 selections_path=None):
    _process, path = launch_request(
        launch_ui, tmp_path, overlay=overlay, scenario=scenario,
        selections_path=selections_path, wait_for_application=False,
    )
    wait(lambda: ui.find("kiosk-request-window") is not None,
         "request window publishes its ID")
    wait(lambda: ui.find("kiosk-request-submit") is not None,
         "request action publishes its ID")
    return path


def ready(ui, wait):
    wait(lambda: ui.state("kiosk-request-submit", ui.api.StateType.SENSITIVE),
         "request controls ready")


def status(ui, wait, expected):
    wait(lambda: ui.text("kiosk-request-status") == expected, expected)


def send_escape(ui):
    """Send Escape through Dogtail's hermetic Mutter input backend."""
    from tests.support.keyboard import press_key

    ui.reveal("kiosk-request-window")
    press_key(ui, "kiosk-request-window", "Escape", state=ui.api.StateType.ACTIVE)


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_shared_loading_keeps_controls_disabled_until_preferences_arrive(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                 overlay=overlay, scenario="loading")
    assert not request_ui.state("kiosk-request-submit", request_ui.api.StateType.SENSITIVE)
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
    ui.activate("kiosk-approver-selector")
    wait_for_accessible_state(lambda: ui.find("kiosk-approver-choice-1010") is not None,
                              "approver choice published")
    ui.activate("kiosk-approver-choice-1010")
    ui.activate("kiosk-duration-300")
    wait_for_accessible_state(
        lambda: any(call["values"][1] == "300" for call in calls(path, "UpdateRequestPreferences")),
        "saved predefined duration",
    )
    ui.activate("kiosk-soft-apps-row")
    wait_for_accessible_state(
        lambda: any(call["values"][3] is True
                    for call in calls(path, "UpdateRequestPreferences")),
        "saved soft-app choice",
    )
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
    assert ui.target("kiosk-child-selected-1001").get_name() == "Alex Morgan"
    assert ui.target("kiosk-approver-selected-1000").get_name() == "Taylor Morgan"
    ui.activate("kiosk-duration-300")
    wait_for_accessible_state(
        lambda: any(call["values"][1] == "300"
                    for call in calls(path, "UpdateRequestPreferences")),
        "selected duration saved",
    )
    ui.activate("kiosk-request-submit")
    method = "RequestOwnAccess" if overlay else "RequestAccess"
    wait_for_accessible_state(lambda: bool(calls(path, method)), "submitted request")
    assert calls(path, method)[0]["values"] == (
        [1000, 300, False] if overlay else [1001, 1000, 300, False]
    )


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_expanded_form_keeps_request_reachable(
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
    wait_for_accessible_state(lambda: ui.find("kiosk-approver-selector") is not None,
                              "request surface publishes its controls")
    wait_for_accessible_state(
        lambda: ui.state("kiosk-approver-selector", Atspi.StateType.SENSITIVE),
        "loaded approver",
    )
    ui.activate("kiosk-approver-selector")
    wait_for_accessible_state(lambda: ui.find("kiosk-approver-choice-1010") is not None,
                              "expanded approver choices are published")
    ui.reveal("kiosk-approver-choice-1010")
    ui.activate("kiosk-request-submit")
    method = "RequestOwnAccess" if overlay else "RequestAccess"
    wait_for_accessible_state(lambda: bool(calls(path, method)),
                              "expanded form permits submission")
    assert len(calls(path, method)) == 1


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
    ui.activate("kiosk-child-selector")
    wait_for_accessible_state(lambda: ui.find("kiosk-child-choice-1002") is not None,
                              "second child choice published")
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
    ui.activate("kiosk-approver-selector")
    wait_for_accessible_state(lambda: ui.find("kiosk-approver-choice-1010") is not None,
                              "approver choice published")
    ui.activate("kiosk-approver-choice-1010")
    wait_for_accessible_state(
        lambda: selections.exists() and json.loads(selections.read_text()).get("approver_uid") == 1010,
        "locally saved approver",
    )
    if not overlay:
        ui.activate("kiosk-child-selector")
        wait_for_accessible_state(lambda: ui.find("kiosk-child-choice-1002") is not None,
                                  "second child choice published")
        ui.activate("kiosk-child-choice-1002")
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
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay, scenario="service-failure")
    ready(request_ui, wait_for_accessible_state)
    request_ui.activate("kiosk-request-submit")
    wait_for_accessible_state(lambda: bool(events(path, "result")), "public failure result")
    result = events(path, "result")[0]
    assert result["title"] == "Request unavailable"
    assert "org.example" not in result["detail"]
    assert "/private/path" not in result["detail"]
    wait_for_accessible_state(
        lambda: request_ui.text("kiosk-result-title") == "Request unavailable",
        "redacted failure title is public",
    )
    assert "org.example" not in request_ui.text("kiosk-result-detail")
    assert "/private/path" not in request_ui.text("kiosk-result-detail")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_single_flight_ignores_escape_while_authentication_is_active(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay, scenario="slow-request")
    ready(request_ui, wait_for_accessible_state)
    request_ui.activate("kiosk-request-submit")
    wait_for_accessible_state(
        lambda: not request_ui.state("kiosk-request-submit", request_ui.api.StateType.SENSITIVE),
        "single-flight request is disabled")
    method = "RequestOwnAccess" if overlay else "RequestAccess"
    wait_for_accessible_state(lambda: len(calls(path, method)) == 1,
                              "one in-flight request")
    send_escape(request_ui)
    wait_for_accessible_state(lambda: bool(events(path, "escape")), "active-request Escape")
    assert events(path, "escape")[0]["handled"] is False
    wait_for_accessible_state(lambda: bool(events(path, "result")), "completed request")
    assert not events(path, "logout")
    assert not events(path, "close_overlay")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_mute_control_stays_hidden_with_remembered_preferences(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay, scenario="remembered")
    ready(request_ui, wait_for_accessible_state)
    assert request_ui.absent("kiosk-mute-button", within="kiosk-request-window")
    assert not calls(path, "SetRequestMuted")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_escape_uses_each_modes_idle_exit_behavior(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    path = open_request(launch_ui, tmp_path, request_ui, wait_for_accessible_state,
                        overlay=overlay)
    ready(request_ui, wait_for_accessible_state)
    send_escape(request_ui)
    wait_for_accessible_state(lambda: bool(events(path, "escape")), "idle Escape")
    assert events(path, "escape")[0]["handled"] is True
    expected = "close_overlay" if overlay else "logout"
    wait_for_accessible_state(lambda: bool(events(path, expected)), f"{expected} callback")


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
    wait_for_accessible_state(lambda: bool(events(path, "result")), "failure result")
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
    wait_for_accessible_state(lambda: bool(events(path, "result")), "approval result")
    assert events(path, "result")[0]["title"] == (
        "Time granted" if overlay else "Request approved"
    )
    wait_for_accessible_state(
        lambda: request_ui.text("kiosk-result-title") == events(path, "result")[0]["title"],
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
    ui.activate("kiosk-child-selector")
    wait_for_accessible_state(lambda: ui.find("kiosk-child-choice-1002") is not None,
                              "second child choice published")
    ui.activate("kiosk-child-choice-1002")
    status(ui, wait_for_accessible_state,
           "Estimated time remaining if approved: 45m")
    assert calls(path, "GetTimeStatus")[-1]["values"] == [1002, 1800]


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_footer_estimate_tracks_custom_edits_and_preserves_validation(
        launch_ui, request_ui, wait_for_accessible_state, tmp_path, overlay):
    from tests.support.keyboard import key_combo, type_text
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
        ui.focus("kiosk-custom-duration")
        key_combo(ui, "kiosk-custom-duration", "<Control>a",
                  state=ui.api.StateType.FOCUSED)
        type_text(ui, "kiosk-custom-duration", value)
        status(ui, wait_for_accessible_state, expected)
