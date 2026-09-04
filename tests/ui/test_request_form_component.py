"""Semantic component coverage for the shared kiosk and child request form."""

from __future__ import annotations

import json

import pytest


pytestmark = pytest.mark.ui


def records(path):
    return [] if not path.exists() else [json.loads(line) for line in path.read_text().splitlines()]


def launch_request(launch_ui, tmp_path, *, overlay, scenario="normal"):
    path = tmp_path / f"request-{overlay}-{scenario}.jsonl"
    application, _log = launch_ui("request_component_preview", environment_overrides={
        "ONPC_REQUEST_COMPONENT_EVENTS_PATH": str(path),
        "ONPC_REQUEST_COMPONENT_OVERLAY": "1" if overlay else "0",
        "ONPC_REQUEST_COMPONENT_SCENARIO": scenario,
    })
    return application, path


def calls(path, method):
    return [item for item in records(path)
            if item["event"] == "call" and item["method"] == method]


def events(path, event):
    return [item for item in records(path) if item["event"] == event]


def send_escape(application):
    """Send Escape through Dogtail's hermetic Mutter input backend."""
    from dogtail.rawinput import press_key

    press_key("Escape")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_shared_loading_keeps_controls_disabled_until_preferences_arrive(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state, tmp_path, overlay):
    loading, _path = launch_request(launch_ui, tmp_path, overlay=overlay, scenario="loading")
    request = wait_for_accessible_node(loading, "REQUEST", "button")
    assert not request.sensitive
    wait_for_accessible_state(lambda: request.sensitive, "loaded request controls")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_control_disabled_never_submits(launch_ui, wait_for_accessible_node, tmp_path, overlay):
    disabled, _path = launch_request(launch_ui, tmp_path, overlay=overlay,
                                     scenario="control-disabled")
    wait_for_accessible_node(disabled, "Screen limit is not enabled in Parent App", "label")
    assert not wait_for_accessible_node(disabled, "REQUEST", "button").sensitive


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_no_approver_explains_why_request_is_unavailable(
        launch_ui, wait_for_accessible_node, tmp_path, overlay):
    unavailable, _path = launch_request(launch_ui, tmp_path, overlay=overlay,
                                        scenario="no-approvers")
    wait_for_accessible_node(unavailable, "No local interactive administrator accounts are available.", "label")
    assert not wait_for_accessible_node(unavailable, "REQUEST", "button").sensitive


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_shared_predefined_approver_and_soft_choices_submit(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state, tmp_path, overlay):
    application, path = launch_request(launch_ui, tmp_path, overlay=overlay)
    request = wait_for_accessible_node(application, "REQUEST", "button")
    assert wait_for_accessible_node(application, "Approving parent", "button").do_action(0)
    assert wait_for_accessible_node(application, "Avery Quinn", "button").do_action(0)
    assert wait_for_accessible_node(application, "Request 5 minutes", "toggle button").do_action(0)
    wait_for_accessible_state(
        lambda: any(call["values"][1] == "300" for call in calls(path, "UpdateRequestPreferences")),
        "saved predefined duration",
    )
    assert wait_for_accessible_node(
        application, "Allow soft blocked apps", "button",
    ).do_action(0)
    wait_for_accessible_state(
        lambda: any(call["values"][3] is True
                    for call in calls(path, "UpdateRequestPreferences")),
        "saved soft-app choice",
    )
    assert request.do_action(0)
    method = "RequestOwnAccess" if overlay else "RequestAccess"
    wait_for_accessible_state(lambda: bool(calls(path, method)), "submitted request")
    assert calls(path, method)[0]["values"] == (
        [1010, 300, True] if overlay else [1001, 1010, 300, True]
    )


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_shared_rest_of_day_choice_submits_zero_seconds(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state, tmp_path, overlay):
    application, path = launch_request(launch_ui, tmp_path, overlay=overlay, scenario="rest-of-day")
    request = wait_for_accessible_node(application, "REQUEST", "button")
    wait_for_accessible_state(lambda: request.sensitive, "loaded rest-of-day preference")
    assert request.do_action(0)
    method = "RequestOwnAccess" if overlay else "RequestAccess"
    wait_for_accessible_state(lambda: bool(calls(path, method)), "rest-of-day request")
    assert calls(path, method)[0]["values"] == (
        [1000, 0, False] if overlay else [1001, 1000, 0, False]
    )


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_shared_custom_duration_preserves_fractional_minute_precision(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state, tmp_path, overlay):
    application, path = launch_request(launch_ui, tmp_path, overlay=overlay, scenario="remembered")
    request = wait_for_accessible_node(application, "REQUEST", "button")
    wait_for_accessible_state(lambda: request.sensitive, "loaded remembered custom duration")
    assert request.do_action(0)
    method = "RequestOwnAccess" if overlay else "RequestAccess"
    wait_for_accessible_state(lambda: bool(calls(path, method)), "custom-duration request")
    assert calls(path, method)[0]["values"] == (
        [1010, 150, True] if overlay else [1001, 1010, 150, True]
    )


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
@pytest.mark.parametrize("scenario", ("custom-too-small", "custom-too-large"))
def test_shared_custom_duration_rejects_values_outside_range(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state,
        tmp_path, overlay, scenario):
    application, path = launch_request(launch_ui, tmp_path, overlay=overlay, scenario=scenario)
    request = wait_for_accessible_node(application, "REQUEST", "button")
    wait_for_accessible_state(lambda: request.sensitive, "loaded invalid custom duration")
    assert request.do_action(0)
    wait_for_accessible_node(application, "Enter a number from 0.1 to 1440 minutes.", "label")
    assert not calls(path, "RequestOwnAccess" if overlay else "RequestAccess")


def test_kiosk_child_selection_reloads_that_childs_preferences(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state, tmp_path):
    kiosk, _path = launch_request(launch_ui, tmp_path, overlay=False)
    assert wait_for_accessible_node(kiosk, "Child account", "button").do_action(0)
    assert wait_for_accessible_node(kiosk, "Sam Rivera", "button").do_action(0)
    wait_for_accessible_state(
        lambda: any(call["values"] == [1002] for call in calls(_path, "GetPreferences")),
        "selected child's preferences",
    )


def test_kiosk_no_child_explains_how_to_continue(launch_ui, wait_for_accessible_node, tmp_path):
    no_child, _path = launch_request(launch_ui, tmp_path, overlay=False, scenario="no-children")
    wait_for_accessible_node(no_child, "No local standard accounts are available. Create one, then reopen this screen.", "label")


def test_child_overlay_uses_fixed_child_identity(launch_ui, wait_for_accessible_node,
                                                  wait_for_accessible_state, tmp_path):
    child, path = launch_request(launch_ui, tmp_path, overlay=True)
    wait_for_accessible_state(
        lambda: bool(calls(path, "GetOwnAccount")), "own child identity lookup",
    )
    assert not wait_for_accessible_node(child, "Child account", "button").sensitive
    assert not calls(path, "ListManagedUsers")


@pytest.mark.parametrize("overlay, scenario, expected", (
    (False, "denied", "Request denied"), (True, "denied", "Request denied"),
    (False, "cancelled", "Choose the account and approving administrator"),
    (True, "cancelled", "Choose the account and approving administrator"),
))
def test_outcomes_are_actionable_and_redacted(launch_ui, wait_for_accessible_node,
                                              wait_for_accessible_state, tmp_path,
                                              overlay, scenario, expected):
    application, path = launch_request(launch_ui, tmp_path, overlay=overlay, scenario=scenario)
    assert wait_for_accessible_node(application, "REQUEST", "button").do_action(0)
    method = "RequestOwnAccess" if overlay else "RequestAccess"
    wait_for_accessible_state(lambda: bool(calls(path, method)), "request outcome")
    wait_for_accessible_node(application, expected, "label")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_service_failure_shows_only_redacted_public_copy(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state, tmp_path, overlay):
    application, path = launch_request(
        launch_ui, tmp_path, overlay=overlay, scenario="service-failure",
    )
    assert wait_for_accessible_node(application, "REQUEST", "button").do_action(0)
    wait_for_accessible_state(lambda: bool(events(path, "result")), "public failure result")
    result = events(path, "result")[0]
    assert result["title"] == "Request unavailable"
    assert "org.example" not in result["detail"]
    assert "/private/path" not in result["detail"]


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_single_flight_ignores_escape_while_authentication_is_active(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state, tmp_path, overlay):
    pending, path = launch_request(launch_ui, tmp_path, overlay=overlay, scenario="slow-request")
    request = wait_for_accessible_node(pending, "REQUEST", "button")
    assert request.do_action(0)
    assert not request.sensitive
    send_escape(pending)
    wait_for_accessible_state(lambda: bool(events(path, "escape")), "active-request Escape")
    assert events(path, "escape")[0]["handled"] is False
    method = "RequestOwnAccess" if overlay else "RequestAccess"
    wait_for_accessible_state(lambda: len(calls(path, method)) == 1, "one in-flight request")
    wait_for_accessible_state(lambda: bool(events(path, "result")), "completed request")
    assert not events(path, "logout")
    assert not events(path, "close_overlay")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_remembered_choices_are_shared_but_mute_is_surface_specific(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state, tmp_path, overlay):
    application, path = launch_request(launch_ui, tmp_path, overlay=overlay, scenario="remembered")
    request = wait_for_accessible_node(application, "REQUEST", "button")
    wait_for_accessible_state(lambda: request.sensitive, "loaded remembered choices")
    assert wait_for_accessible_node(application, "Mute request-screen sound", "button").do_action(0)
    wait_for_accessible_state(lambda: bool(calls(path, "SetRequestMuted")), "saved mute")
    assert calls(path, "SetRequestMuted")[0]["values"] == [
        1001, "child" if overlay else "kiosk", False if overlay else True,
    ]


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_escape_uses_each_modes_idle_exit_behavior(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state, tmp_path, overlay):
    application, path = launch_request(launch_ui, tmp_path, overlay=overlay)
    wait_for_accessible_node(application, "REQUEST", "button")
    send_escape(application)
    wait_for_accessible_state(lambda: bool(events(path, "escape")), "idle Escape")
    assert events(path, "escape")[0]["handled"] is True
    expected = "close_overlay" if overlay else "logout"
    wait_for_accessible_state(lambda: bool(events(path, expected)), f"{expected} callback")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_cancel_uses_each_modes_idle_exit_behavior(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state, tmp_path, overlay):
    application, path = launch_request(launch_ui, tmp_path, overlay=overlay)
    assert wait_for_accessible_node(application, "CANCEL", "button").do_action(0)
    expected = "close_overlay" if overlay else "logout"
    wait_for_accessible_state(lambda: bool(events(path, expected)), f"Cancel {expected}")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_result_action_uses_each_modes_exit_behavior(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state, tmp_path, overlay):
    application, path = launch_request(
        launch_ui, tmp_path, overlay=overlay, scenario="service-failure",
    )
    assert wait_for_accessible_node(application, "REQUEST", "button").do_action(0)
    wait_for_accessible_state(lambda: bool(events(path, "result")), "failure result")
    action = "Close" if overlay else "Return to Login"
    assert wait_for_accessible_node(application, action, "button").do_action(0)
    expected = "close_overlay" if overlay else "logout"
    wait_for_accessible_state(lambda: bool(events(path, expected)), f"result {expected}")


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_approval_uses_each_modes_result_exit_callback(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state, tmp_path, overlay):
    application, path = launch_request(launch_ui, tmp_path, overlay=overlay)
    assert wait_for_accessible_node(application, "REQUEST", "button").do_action(0)
    wait_for_accessible_state(lambda: bool(events(path, "result")), "approval result")
    assert events(path, "result")[0]["title"] == (
        "Time granted" if overlay else "Request approved"
    )
    expected = "close_overlay" if overlay else "logout"
    wait_for_accessible_state(lambda: bool(events(path, expected)), f"approved {expected}")
