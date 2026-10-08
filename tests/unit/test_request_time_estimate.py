"""Asynchronous request-window preferences and estimates without a display."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from common.oh_no_parent_control_ui.duration import format_duration
from common.oh_no_parent_control_ui.diagnostic_events import decode
from oh_no_parent_control_kiosk.main import RequestWindow, _time_estimate_label
from oh_no_parent_control_kiosk.request_content import RequestContent
from tests.support.objects import bind_methods
from oh_no_parent_control_kiosk.agent_locale import KioskAgentLocale, agent_environment, UNIT


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
        _apply_language=Mock(return_value=True), _stack=Mock())
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
        _child_overlay=True, _language_revision=0, _own_language=None,
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
    assert (method, parameters.unpack(), signature) == ('GetChildLanguageContext', (1001,), '(ss)')
    old_callback(SimpleNamespace(call_finish=Mock(side_effect=error,
        return_value=SimpleNamespace(unpack=lambda: ('fr',)))), object())
    window._language_loaded.assert_not_called()
    window._language_failed.assert_not_called()
    callback(SimpleNamespace(call_finish=Mock(
        return_value=SimpleNamespace(unpack=lambda: ('de', 'zh_CN.UTF-8')))), object())
    window._language_loaded.assert_called_once_with('de')
    assert window._desktop_language == 'zh_CN.UTF-8'
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
    window = SimpleNamespace(_applied_language='de', _show_error=Mock(), _child_overlay=True)
    with patch('oh_no_parent_control_kiosk.main.context_for') as context:
        assert RequestWindow._apply_language(window, 'de')
        context.assert_not_called()
        assert RequestWindow._apply_language(window, 'fr')
        context.return_value.apply.assert_called_once_with('fr')
    assert window._applied_language == 'fr'


@pytest.mark.parametrize('saved,desktop,expected', [
    ('', 'zh_CN.UTF-8', 'zh-Hans'), ('', 'zh_TW.UTF-8', 'zh-Hant'),
    ('', 'de_DE.UTF-8', 'de'), ('fr', 'zh_CN.UTF-8', 'fr'),
    ('', 'unsupported', 'en'),
])
def test_kiosk_language_defaults_to_selected_child_desktop(saved, desktop, expected):
    window = SimpleNamespace(_applied_language=None, _show_error=Mock(),
                             _child_overlay=False, _desktop_language=desktop)
    with patch('oh_no_parent_control_kiosk.main.context_for') as context:
        assert RequestWindow._apply_language(window, saved)
        context.return_value.apply.assert_called_once_with(expected)
    assert window._applied_language == expected


def test_reboot_notice_waits_for_child_language_and_skips_first_run_chooser():
    from gi.repository import Gio
    error = Gio.DBusError.new_for_dbus_error(
        'com.puffyslippers.OhNoParentControl1.Error.RebootRequired', 'upgrade')
    window = bind_methods(SimpleNamespace(
        _startup_language_pending=True, _child_overlay=False,
        _estimate_closed=False, _language_load_failed=False,
        _stack=Mock(), _show_result=Mock(), _open_language_dialog=Mock(),
        _language_dialog=None,
        _apply_language=Mock(return_value=True),
    ), RequestWindow, ('_show_error', '_language_loaded'))
    with patch('oh_no_parent_control_kiosk.main.show_update_required') as notice:
        window._show_error(error)
        window._show_result.assert_not_called()
        notice.assert_not_called()
        window._language_loaded('')
        window._apply_language.assert_called_once_with('')
        notice.assert_called_once_with(window)
        window._open_language_dialog.assert_not_called()


@pytest.mark.parametrize('language,desktop,native,registration', [
    ('zh-Hans', 'zh_CN.UTF-8', 'zh_CN', 'zh_CN.UTF-8'),
    ('zh-Hant', 'zh_TW.UTF-8', 'zh_TW', 'zh_TW.UTF-8'),
    ('de', 'zh_CN.UTF-8', 'de', 'de_DE.UTF-8'),
    ('pt-BR', '', 'pt_BR', 'pt_BR.UTF-8'),
    ('zh-Hans', 'zh_CN.UTF-8\nOTHER=value', 'zh_CN', 'zh_CN.UTF-8'),
])
def test_agent_locale_is_process_scoped_and_maps_native_catalogues(
        language, desktop, native, registration):
    import os
    before = dict(os.environ)
    assert agent_environment(language, desktop, ('C.utf8', 'en_US.utf8')) == (
        f'LANG={registration}\nLANGUAGE={native}\nLC_ALL=en_US.utf8\n')
    assert dict(os.environ) == before


def test_agent_locale_refuses_c_only_hosts_without_starting_approval():
    with pytest.raises(RuntimeError, match='installed UTF-8 message locale'):
        agent_environment('zh-Hans', 'zh_CN.UTF-8', ('C', 'C.utf8', 'POSIX'))


def test_agent_deadline_ignores_late_restart_reply_after_close(tmp_path):
    from gi.repository import GLib
    agent = KioskAgentLocale()
    agent._locales = ('en_US.utf8',)
    bus, done = Mock(), Mock()
    with (patch('oh_no_parent_control_kiosk.agent_locale.GLib.get_user_runtime_dir', return_value=str(tmp_path)),
          patch('oh_no_parent_control_kiosk.agent_locale.Gio.bus_get_sync', return_value=bus),
          patch('oh_no_parent_control_kiosk.agent_locale.GLib.timeout_add_seconds', return_value=42)):
        agent.prepare('zh-Hans', 'zh_CN.UTF-8', done)
        callback = bus.call.call_args.args[-1]
        agent._timed_out()
        assert isinstance(done.call_args.args[0], TimeoutError)
        bus.call_finish.return_value = GLib.Variant('(o)', ('/job/late',))
        callback(bus, object())
        bus.call_finish.assert_not_called()
        assert done.call_count == 1
        assert agent._applied is None
        bus.signal_unsubscribe.assert_called_once()


@pytest.mark.parametrize('failure', ('failed', 'timeout'))
def test_agent_failed_locale_change_invalidates_previously_applied_settings(tmp_path, failure):
    agent = KioskAgentLocale()
    agent._locales = ('en_US.utf8',)
    agent._applied = agent_environment('en', '', agent._locales)
    bus, done = Mock(), Mock()
    with (patch('oh_no_parent_control_kiosk.agent_locale.GLib.get_user_runtime_dir', return_value=str(tmp_path)),
          patch('oh_no_parent_control_kiosk.agent_locale.Gio.bus_get_sync', return_value=bus),
          patch('oh_no_parent_control_kiosk.agent_locale.GLib.timeout_add_seconds', return_value=42),
          patch('oh_no_parent_control_kiosk.agent_locale.GLib.source_remove')):
        agent.prepare('zh-Hans', '', done)
        if failure == 'timeout':
            agent._timed_out()
        else:
            agent._completed('failed')
        assert done.call_args.args[0] is not None
        bus.reset_mock()
        agent.prepare('en', '', done)
        assert bus.call.call_args.args[3] == 'RestartUnit'
        agent.close()


@pytest.mark.parametrize('early,result', [(False, 'done'), (True, 'done'), (False, 'failed')])
def test_agent_restart_waits_for_matching_systemd_job(tmp_path, early, result):
    from gi.repository import GLib
    agent = KioskAgentLocale()
    agent._locales = ('en_US.utf8', 'zh_CN.utf8')
    bus, done = Mock(), Mock()
    with (patch('oh_no_parent_control_kiosk.agent_locale.GLib.get_user_runtime_dir', return_value=str(tmp_path)),
          patch('oh_no_parent_control_kiosk.agent_locale.Gio.bus_get_sync', return_value=bus),
          patch('oh_no_parent_control_kiosk.agent_locale.GLib.timeout_add_seconds', return_value=42),
          patch('oh_no_parent_control_kiosk.agent_locale.GLib.source_remove') as remove):
        agent.prepare('zh-Hans', 'zh_CN.UTF-8', done)
        assert (tmp_path / 'oh-no-parent-control/polkit-agent.env').read_text() == agent_environment('zh-Hans', 'zh_CN.UTF-8', agent._locales)
        assert (tmp_path / 'oh-no-parent-control/polkit-agent.env').stat().st_mode & 0o777 == 0o600
        done.assert_not_called()
        args = bus.call.call_args.args
        assert args[3] == 'RestartUnit' and args[4].unpack() == (UNIT, 'replace')
        signal = lambda job, value: agent._job_removed(None, None, None, None, None,
            GLib.Variant('(uoss)', (1, job, UNIT, value)))
        signal('/job/other', 'done')
        if early:
            signal('/job/owned', result)
        bus.call_finish.return_value = GLib.Variant('(o)', ('/job/owned',))
        args[-1](bus, object())
        if not early:
            done.assert_not_called()
            signal('/job/owned', result)
        assert done.call_count == 1
        assert (done.call_args.args[0] is None) == (result == 'done')
        bus.signal_unsubscribe.assert_called_once()
        remove.assert_called_once_with(42)
        if result == 'done':
            bus.reset_mock()
            agent.prepare('zh-Hans', 'zh_CN.UTF-8', done)
            bus.call.assert_not_called()


def test_kiosk_request_waits_for_agent_locale_and_stops_on_failure():
    window = bind_methods(SimpleNamespace(
        _pending_request=(1001, 1000, 300, False), _child_overlay=False,
        _agent_locale=Mock(), _applied_language='zh-Hans', _desktop_language='zh_CN.UTF-8',
        _estimate_closed=False, _bus_call=Mock(), _request_failed=Mock(), _request_done=Mock(),
    ), RequestWindow, ('_preferences_saved', '_agent_prepared'))
    connection = Mock()
    window._preferences_saved(connection, object())
    window._bus_call.assert_not_called()
    language, desktop, callback = window._agent_locale.prepare.call_args.args
    assert (language, desktop) == ('zh-Hans', 'zh_CN.UTF-8')
    callback(RuntimeError('restart failed'))
    window._bus_call.assert_not_called()
    window._request_failed.assert_called_once()
    callback(None)
    assert window._bus_call.call_args.args[0] == 'RequestAccess'


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


def test_pending_estimate_keeps_label_with_blank_value_until_result():
    form = bind_methods(SimpleNamespace(
        _accounts_loaded=True, _approvers_loaded=True, _account_uids=[1001],
        _approver_uids=[1000], _screen_time_limit_enabled=True,
        _validation_error=None, _controls_enabled=True,
        selected=Mock(return_value=(1001, "Child", 1000, 300, False)),
        _status=Mock(),
    ), RequestContent, ("set_time_estimate", "_update_status"))
    form.set_time_estimate(None)
    form._status.set_label.assert_called_with("Estimated time remaining if approved: ")
    form.set_time_estimate(None)
    form._status.set_label.assert_called_with("Estimated time remaining if approved: ")
    form.set_time_estimate(_time_estimate_label(4620))
    form._status.set_label.assert_called_with("Estimated time remaining if approved: 1h 17m")
    assert all(call.args[0].startswith("Estimated time remaining if approved: ")
               for call in form._status.set_label.call_args_list)


def release_presenter(overlay):
    from oh_no_parent_control_kiosk.whats_new import WhatsNewPresenter
    window = SimpleNamespace(
        _preview=False, _child_overlay=overlay, _bus_call=Mock(),
        _language_ready=True, _language_loading=False, _language_dialog=None,
        _state=SimpleNamespace(in_flight=False),
        _stack=SimpleNamespace(get_visible_child_name=lambda: 'request'))
    presenter = WhatsNewPresenter(window)
    presenter.menu_item = Mock()
    presenter._modal_blocked = Mock(return_value=False)
    return presenter


def release_reply(presenter, *, auto=True, version='1.4', audience='Child', error=None):
    import json
    record = {'record_id': version + ':' + audience, 'ProductVersion': version,
              'Content': '## Updates', 'auto_show': auto}
    connection = SimpleNamespace(call_finish=Mock(
        side_effect=error, return_value=SimpleNamespace(unpack=lambda: (json.dumps({
            'product_version': '1.4', 'records': [record]}),))))
    presenter.window._bus_call.call_args.args[3](connection, object())


@pytest.mark.parametrize('overlay', (False, True))
def test_child_release_notes_acknowledge_only_displayed_close_on_matching_api(overlay):
    presenter = release_presenter(overlay)
    with patch('oh_no_parent_control_kiosk.whats_new.WhatsNewDialog') as dialog:
        presenter.select_child(1001)
        method, parameters, signature, _callback = presenter.window._bus_call.call_args.args
        assert method == ('GetOwnWhatsNew' if overlay else 'GetChildWhatsNew')
        assert parameters.unpack() == (() if overlay else (1001,))
        assert signature == '(s)'
        release_reply(presenter)
        assert dialog.call_count == 1
        closed = dialog.call_args.args[2]
        assert presenter.window._bus_call.call_count == 1
        closed(False)
        assert presenter.window._bus_call.call_count == 1
        closed(True)
        method, parameters, _signature, _callback = presenter.window._bus_call.call_args.args
        assert method == ('AcknowledgeOwnWhatsNew' if overlay else 'AcknowledgeChildWhatsNew')
        assert parameters.unpack() == (('1.4',) if overlay else (1001, '1.4'))
        release_reply(presenter, auto=False)
        presenter.try_auto()
        assert dialog.call_count == 1
        presenter.show()
        assert dialog.call_count == 2


@pytest.mark.parametrize('blocker', ('language', 'chooser', 'modal', 'busy', 'result', 'reboot'))
def test_release_notes_defer_for_language_modals_and_request_results(blocker):
    presenter = release_presenter(False)
    presenter.record = {'auto_show': True}
    if blocker == 'language':
        presenter.window._language_ready = False
    elif blocker == 'chooser':
        presenter.window._language_dialog = object()
    elif blocker == 'modal':
        presenter._modal_blocked.return_value = True
    elif blocker == 'busy':
        presenter.window._state.in_flight = True
    elif blocker == 'result':
        presenter.window._stack.get_visible_child_name = lambda: 'result'
    else:
        presenter.window._reboot_required = True
    with (patch('oh_no_parent_control_kiosk.whats_new.GLib.timeout_add', return_value=7),
          patch('oh_no_parent_control_kiosk.whats_new.GLib.source_remove'),
          patch('oh_no_parent_control_kiosk.whats_new.WhatsNewDialog') as dialog):
        presenter.try_auto()
        dialog.assert_not_called()
        assert presenter.wait_id == 7
        presenter.close()
        assert presenter.wait_id == 0


@pytest.mark.parametrize('late', ('read', 'close', 'acknowledgement', 'shutdown'))
def test_child_release_notes_discard_superseded_account_callbacks(late):
    presenter = release_presenter(False)
    with (patch('oh_no_parent_control_kiosk.whats_new.WhatsNewDialog') as dialog,
          patch('oh_no_parent_control_kiosk.whats_new.GLib.timeout_add', return_value=7),
          patch('oh_no_parent_control_kiosk.whats_new.GLib.source_remove')):
        presenter.select_child(1001)
        old = presenter.window._bus_call.call_args.args[3]
        if late != 'read':
            release_reply(presenter)
            old = dialog.call_args.args[2]
            if late == 'acknowledgement':
                old(True)
                old = presenter.window._bus_call.call_args.args[3]
        presenter.select_child(1002)
        count = presenter.window._bus_call.call_count
        if late == 'shutdown':
            presenter.close()
        if late in ('close', 'shutdown'):
            old(True)
        else:
            connection = Mock()
            old(connection, object())
            connection.call_finish.assert_not_called()
        assert presenter.window._bus_call.call_count == count
        assert presenter.record is None


@pytest.mark.parametrize('version,audience', [('1.3', 'Child'), ('1.4', 'Parent')])
def test_child_release_notes_refuse_old_and_parent_records(version, audience):
    presenter = release_presenter(True)
    presenter.select_child(1001)
    release_reply(presenter, version=version, audience=audience)
    assert presenter.record is None
    presenter.menu_item.set_visible.assert_called_with(False)


def test_release_note_failure_preserves_request_and_manual_acknowledgement_retry():
    presenter = release_presenter(True)
    presenter.select_child(1001)
    release_reply(presenter, error=RuntimeError('private detail'))
    assert presenter.record is None
    assert presenter.window._language_ready
    with patch('oh_no_parent_control_kiosk.whats_new.WhatsNewDialog') as dialog:
        release_reply(presenter)
        dialog.call_args.args[2](True)
        release_reply(presenter, error=RuntimeError('private detail'))
        assert presenter.record['auto_show']
        presenter.show()
        dialog.call_args.args[2](True)
        release_reply(presenter, auto=False)
        assert not presenter.record['auto_show']


def test_manual_release_notes_can_reopen_from_request_result():
    presenter = release_presenter(False)
    presenter.window._stack.get_visible_child_name = lambda: 'result'
    presenter.select_child(1001)
    release_reply(presenter, auto=False)
    with patch('oh_no_parent_control_kiosk.whats_new.WhatsNewDialog') as dialog:
        presenter.show()
        dialog.assert_called_once()


def test_kiosk_markdown_keeps_link_labels_without_external_actions():
    from common.oh_no_parent_control_ui.release_markdown import markdown_blocks
    assert markdown_blocks('**[Read more](https://example.com)**', links_enabled=False) == [
        ('paragraph', '<b>Read more</b>')]
