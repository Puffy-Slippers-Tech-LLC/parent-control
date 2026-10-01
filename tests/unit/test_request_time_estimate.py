"""Asynchronous request-window preferences and estimates without a display."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from common.oh_no_parent_control_ui.duration import format_duration
from common.oh_no_parent_control_ui.diagnostic_events import decode
from oh_no_parent_control_kiosk.main import RequestWindow, _time_estimate_label
from oh_no_parent_control_kiosk.request_content import RequestContent
from tests.support.objects import bind_methods


@pytest.fixture(autouse=True)
def plain_presentation(monkeypatch):
    from tests.support.objects import set_plain_text
    monkeypatch.setattr('oh_no_parent_control_kiosk.main.set_text', set_plain_text)
    monkeypatch.setattr('oh_no_parent_control_kiosk.request_content.set_text', set_plain_text)


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
        _preview=False, _child_overlay=False, _bus_call=Mock(),
        _errors=Mock(),
    ), RequestWindow, (
        "_refresh_time_estimate", "_time_estimate_done", "_finish_time_estimate",
    ))


@pytest.mark.parametrize("language,requested,prompt", [
    ("", False, True), ("fr", False, False), ("fr", True, True),
])
def test_language_startup_uses_caller_preference_and_only_prompts_when_needed(
        language, requested, prompt):
    window = SimpleNamespace(
        _estimate_closed=False, _language_load_failed=False,
        _language_requested=requested, _open_language_dialog=Mock(), _language_saved=Mock(),
        _apply_language=Mock(return_value=True))
    RequestWindow._language_loaded(window, language)
    assert window._own_language == language
    assert not window._language_loading
    assert window._open_language_dialog.called == prompt
    window._apply_language.assert_called_once_with(language)
    assert window._language_saved.called == (not prompt)


@pytest.mark.parametrize("closed,error", [(False, None), (False, RuntimeError("private")),
                                         (True, None), (True, RuntimeError("private"))])
def test_language_save_uses_own_account_api_and_ignores_late_callbacks(closed, error):
    window = SimpleNamespace(_preview=False, _estimate_closed=False, _bus_call=Mock(),
                             _child_overlay=True, _language_revision=0,
                             _language_target_uid=None)
    success, failure = Mock(), Mock()
    RequestWindow._save_language(window, "pt-BR", success, failure)
    method, parameters, signature, callback = window._bus_call.call_args.args
    assert method == "SetOwnLanguage"
    assert parameters.unpack() == ("pt-BR",)  # No child or approver UID.
    assert signature == "(s)"
    window._estimate_closed = closed
    connection = SimpleNamespace(call_finish=Mock(
        side_effect=error, return_value=SimpleNamespace(unpack=lambda: ("pt-BR",))))
    callback(connection, object())
    assert success.called == (not closed and error is None)
    assert failure.called == (not closed and error is not None)


def test_language_read_coalesces_preferences_requests_and_retries_after_failure():
    window = bind_methods(SimpleNamespace(
        _estimate_closed=False, _language_loading=False, _preview=False,
        _child_overlay=True, _language_revision=0,
        _bus_call=Mock(), _show_error=Mock(), _stack=Mock(), _result_detail=Mock(),
        _language_readiness=Mock(), _language_requested=True, _language_load_failed=False,
        _open_language_dialog=Mock(), _apply_language=Mock(return_value=True),
    ), RequestWindow, ("_load_language", "_language_done", "_language_failed", "_language_loaded"))
    window._load_language()
    window._load_language()
    assert window._bus_call.call_count == 1
    assert window._bus_call.call_args.args[:3] == ("GetOwnLanguage", None, "(s)")
    callback = window._bus_call.call_args.args[3]
    with patch("oh_no_parent_control_kiosk.main.set_automation_id"):
        callback(SimpleNamespace(call_finish=Mock(side_effect=RuntimeError("private"))), object())
    assert not window._language_loading
    assert window._language_load_failed
    window._load_language()
    callback(SimpleNamespace(call_finish=Mock(
        return_value=SimpleNamespace(unpack=lambda: ("de",)))), object())
    assert window._bus_call.call_count == 2
    assert not window._language_load_failed
    window._stack.set_visible_child_name.assert_called_once_with("request")
    window._open_language_dialog.assert_called_once_with()


@pytest.mark.parametrize('error', (None, RuntimeError('old child failure')))
def test_child_language_switch_discards_superseded_reads_including_reselection(error):
    window = bind_methods(SimpleNamespace(
        _estimate_closed=False, _language_loading=False, _preview=False,
        _child_overlay=False, _language_revision=0, _language_target_uid=None,
        _language_dialog=None, _stack=Mock(), _language_readiness=Mock(),
        _applied_language='en',
        _bus_call=Mock(), _language_loaded=Mock(), _language_failed=Mock(),
    ), RequestWindow, ('_select_language_child', '_load_language', '_language_done'))
    with patch('oh_no_parent_control_kiosk.main.set_automation_id'):
        window._select_language_child(1001)
        old_callback = window._bus_call.call_args.args[3]
        window._select_language_child(1002)
        window._select_language_child(1001)
    method, parameters, signature, callback = window._bus_call.call_args.args
    assert (method, parameters.unpack(), signature) == ('GetChildLanguage', (1001,), '(s)')
    old_callback(SimpleNamespace(call_finish=Mock(side_effect=error,
        return_value=SimpleNamespace(unpack=lambda: ('fr',)))), object())
    window._language_loaded.assert_not_called()
    window._language_failed.assert_not_called()
    callback(SimpleNamespace(call_finish=Mock(
        return_value=SimpleNamespace(unpack=lambda: ('de',)))), object())
    window._language_loaded.assert_called_once_with('de')
    window._stack.set_sensitive.assert_not_called()


def test_kiosk_language_save_targets_child_and_ignores_reply_after_switch():
    window = SimpleNamespace(_preview=False, _estimate_closed=False, _bus_call=Mock(),
                             _child_overlay=False, _language_revision=1,
                             _language_target_uid=1001)
    success, failure = Mock(), Mock()
    RequestWindow._save_language(window, 'de', success, failure)
    method, parameters, signature, callback = window._bus_call.call_args.args
    assert (method, parameters.unpack(), signature) == ('SetChildLanguage', (1001, 'de'), '(s)')
    window._language_revision += 1
    callback(SimpleNamespace(call_finish=Mock(
        return_value=SimpleNamespace(unpack=lambda: ('de',)))), object())
    success.assert_not_called()
    failure.assert_not_called()


def test_unchanged_language_does_not_relabel_widgets():
    window = SimpleNamespace(_applied_language='de', _show_error=Mock())
    with patch('oh_no_parent_control_kiosk.main.context_for') as context:
        assert RequestWindow._apply_language(window, 'de')
        context.assert_not_called()
        assert RequestWindow._apply_language(window, 'fr')
        context.return_value.apply.assert_called_once_with('fr')
    assert window._applied_language == 'fr'


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


def test_estimate_diagnostics_retain_operands_but_exclude_stale_replies_and_identity(caplog):
    caplog.set_level("INFO")
    window = estimate_window()
    window._request_content.time_estimate_selection.return_value = (1234567, 300)
    window._refresh_time_estimate()
    window._estimate_revision += 1
    reply(window, seconds=9999)
    assert not caplog.records
    reply(window, seconds=1200)
    payload = decode(caplog.records[-1].onpc_payload)
    assert payload["event"] == "kiosk.estimate-calculated"
    assert payload["fields"] == {
        "daily": 900, "grant": 0, "additional": 300, "calculated": 1200,
        "overlay": False,
    }
    assert "1234567" not in caplog.text
    assert "9999" not in caplog.text


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
    form._status.set_label.assert_called_once_with(expected)


@pytest.mark.parametrize("seconds, expected", (
    (0, "0m"), (-1, "0m"), (6, "0m 6s"), (65, "1m 5s"),
    (59 * 60, "59m"), (60 * 60, "1h"), (77 * 60, "1h 17m"),
    (2 * 60 * 60, "2h"), (2 * 60 * 60 + 5, "2h 5s"),
    (90 * 60 + 30, "1h 30m 30s"), (24 * 60 * 60, "24h"),
))
def test_shared_duration_format_preserves_precision_and_omits_zero_minutes(seconds, expected):
    assert format_duration(seconds) == expected
    assert _time_estimate_label(seconds) == f"Estimated time remaining if approved: {expected}"
