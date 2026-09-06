"""Delayed broker replies and footer priority without a graphical session."""

from types import MethodType, SimpleNamespace
from unittest.mock import Mock

import pytest

from common.oh_no_parent_control_ui.duration import format_duration
from oh_no_parent_control_kiosk.main import RequestWindow, _time_estimate_label
from oh_no_parent_control_kiosk.request_content import RequestContent


def bind_methods(target, cls, names):
    for name in names:
        setattr(target, name, MethodType(getattr(cls, name), target))
    return target


def estimate_window():
    form = SimpleNamespace(
        time_estimate_selection=Mock(return_value=(1001, 300)),
        set_time_estimate=Mock(),
    )
    return bind_methods(SimpleNamespace(
        _request_content=form, _estimate_closed=False, _estimate_revision=1,
        _estimate_in_flight=False, _estimate_debounce_id=0,
        _state=SimpleNamespace(in_flight=False),
        _stack=SimpleNamespace(get_visible_child_name=lambda: "request"),
        _preview=False, _bus_call=Mock(),
    ), RequestWindow, (
        "_refresh_time_estimate", "_time_estimate_done", "_finish_time_estimate",
    ))


def reply(window, seconds=1200, error=None):
    callback = window._bus_call.call_args.args[3]
    connection = SimpleNamespace(call_finish=Mock(
        side_effect=error,
        return_value=SimpleNamespace(unpack=lambda: (900, 0, 300, seconds)),
    ))
    callback(connection, object())


@pytest.mark.parametrize("error", (None, RuntimeError("private backend details")))
def test_old_child_reply_is_discarded_and_latest_selection_is_fetched(error):
    window = estimate_window()
    window._refresh_time_estimate()
    window._request_content.time_estimate_selection.return_value = (1002, 600)
    window._estimate_revision += 1
    window._refresh_time_estimate()
    assert window._bus_call.call_count == 1
    reply(window, error=error)
    window._request_content.set_time_estimate.assert_not_called()
    assert window._bus_call.call_count == 2
    assert window._bus_call.call_args.args[1].unpack() == (1002, 600)
    reply(window, seconds=1800)
    window._request_content.set_time_estimate.assert_called_once_with(
        "Estimated time remaining if approved: 30m",
    )


def test_periodic_refresh_updates_estimate_and_recovers_after_failure():
    window = estimate_window()
    window._refresh_time_estimate()
    reply(window, error=RuntimeError("private backend details"))
    window._request_content.set_time_estimate.assert_called_with("Time estimate unavailable")
    window._refresh_time_estimate()
    reply(window, seconds=1190)
    window._request_content.set_time_estimate.assert_called_with(
        "Estimated time remaining if approved: 19m 50s",
    )


@pytest.mark.parametrize("selection", (None, (1001, 0)))
def test_invalid_and_rest_of_day_selections_do_not_query_time(selection):
    window = estimate_window()
    window._request_content.time_estimate_selection.return_value = selection
    window._refresh_time_estimate()
    window._bus_call.assert_not_called()
    if selection:
        window._request_content.set_time_estimate.assert_called_once_with(
            "If approved, access until midnight.",
        )


def test_destroyed_window_ignores_pending_reply():
    window = estimate_window()
    window._refresh_time_estimate()
    window._estimate_closed = True
    reply(window)
    window._request_content.set_time_estimate.assert_not_called()
    assert window._refresh_time_estimate() is False
    assert window._bus_call.call_count == 1


@pytest.mark.parametrize("state, expected", (
    ({"_validation_error": "Request denied"}, "Request denied"),
    ({"_controls_enabled": False}, "Waiting for approval…"),
    ({"_controls_enabled": False, "_validation_error": "Request denied"}, "Waiting for approval…"),
    ({"_screen_time_limit_enabled": None}, "Loading request details…"),
    ({"_accounts_loaded": False}, "Loading accounts…"),
    ({"_screen_time_limit_enabled": False}, "Screen limit is not enabled in Parent App"),
    ({}, "Estimated time remaining if approved: 35m"),
))
def test_estimate_refresh_preserves_higher_priority_footer_messages(state, expected):
    form = bind_methods(SimpleNamespace(
        _accounts_loaded=True, _approvers_loaded=True, _account_uids=[1001],
        _approver_uids=[1000], _screen_time_limit_enabled=True,
        _validation_error=None, _controls_enabled=True,
        selected=Mock(return_value=(1001, "Child", 1000, 300, False)),
        _status=Mock(),
    ), RequestContent, ("set_time_estimate", "_update_status"))
    for key, value in state.items():
        setattr(form, key, value)
    form.set_time_estimate("Estimated time remaining if approved: 35m")
    form._status.set_text.assert_called_once_with(expected)


@pytest.mark.parametrize("seconds, expected", (
    (0, "0m"), (-1, "0m"), (6, "0m 6s"), (65, "1m 5s"),
    (59 * 60, "59m"), (60 * 60, "1h"), (77 * 60, "1h 17m"),
    (2 * 60 * 60, "2h"), (2 * 60 * 60 + 5, "2h 5s"),
    (90 * 60 + 30, "1h 30m 30s"), (24 * 60 * 60, "24h"),
))
def test_shared_duration_format_preserves_precision_and_omits_zero_minutes(seconds, expected):
    assert format_duration(seconds) == expected
    assert _time_estimate_label(seconds) == f"Estimated time remaining if approved: {expected}"
