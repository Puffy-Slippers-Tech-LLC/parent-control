"""Shared request controls remain usable at supported display scales."""

import pytest

from tests.support.request_form import calls, launch_request


pytestmark = pytest.mark.ui


@pytest.mark.parametrize("overlay,dpi_scale", (
    (False, 1), (True, 1), (False, 1.25), (True, 1.25),
), ids=("kiosk", "child-overlay", "kiosk-fractional", "child-fractional"))
def test_request_layout_keeps_all_choices_and_submission_reachable(
        launch_ui, automation, request_display_scale, wait_for_accessible_state,
        tmp_path, overlay, dpi_scale):
    """Exercise the full form through public IDs after actual display scaling."""
    _process, path = launch_request(
        launch_ui, tmp_path, overlay=overlay, wait_for_application=False,
    )
    ui = automation
    wait_for_accessible_state(lambda: ui.find("kiosk-request-submit") is not None,
                              "scaled form publishes request control")
    wait_for_accessible_state(
        lambda: ui.state("kiosk-request-submit", ui.api.StateType.SENSITIVE),
        "scaled form is ready",
    )
    ui.activate("kiosk-approver-selector")
    wait_for_accessible_state(lambda: ui.find("kiosk-approver-choice-1010") is not None,
                              "expanded choices are published")
    ui.activate("kiosk-approver-choice-1010")
    ui.activate("kiosk-duration-300")
    ui.reveal("kiosk-request-status")
    ui.activate("kiosk-request-submit")
    method = "RequestOwnAccess" if overlay else "RequestAccess"
    wait_for_accessible_state(lambda: bool(calls(path, method)),
                              "scaled form submits selected values")
    assert calls(path, method)[0]["values"] == (
        [1010, 300, False] if overlay else [1001, 1010, 300, False]
    )
