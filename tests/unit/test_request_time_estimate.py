"""Asynchronous request-window preferences and estimates without a display."""

from types import SimpleNamespace
import os
import subprocess
from unittest.mock import Mock, patch

import pytest

from common.oh_no_parent_control_ui.duration import format_duration
from common.oh_no_parent_control_ui.diagnostic_events import decode
from oh_no_parent_control_kiosk.main import RequestWindow, _time_estimate_label
from oh_no_parent_control_kiosk.model import RequestState
from oh_no_parent_control_kiosk.request_content import RequestContent
from tests.support.objects import bind_methods
from oh_no_parent_control_kiosk.agent_locale import KioskAgentLocale, agent_environment, UNIT
from oh_no_parent_control_kiosk.session_logout import KioskLogout


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
        _request_revision=0,
        _estimate_in_flight=False, _estimate_debounce_id=0,
        _state=SimpleNamespace(in_flight=False),
        _stack=SimpleNamespace(get_visible_child_name=lambda: "request"),
        _preview=False, _child_overlay=False, _bus_call=Mock(),
        _errors=Mock(),
    ), RequestWindow, (
        "_refresh_time_estimate", "_time_estimate_done", "_finish_time_estimate",
    ))


@pytest.fixture
def estimate_scheduler(monkeypatch):
    pending, delays = {}, []

    def add(delay, callback):
        delays.append(delay)
        source = len(delays)
        pending[source] = callback
        return source

    def fire():
        assert len(pending) == 1
        source, callback = next(iter(pending.items()))
        del pending[source]
        return callback()

    monkeypatch.setattr('oh_no_parent_control_kiosk.main.GLib.timeout_add', add)
    monkeypatch.setattr('oh_no_parent_control_kiosk.main.GLib.source_remove',
                        lambda source: pending.pop(source, None))
    return SimpleNamespace(pending=pending, delays=delays, fire=fire)


def scheduled_estimate_window(overlay=False):
    window = bind_methods(estimate_window(), RequestWindow, (
        '_queue_time_estimate', '_time_estimate_debounced', '_form_values_changed',
        '_preferences_done', '_approvers_done', '_on_destroy'))
    window._child_overlay = overlay
    window._persist_form_values = Mock()
    return window


@pytest.mark.parametrize('overlay', (False, True))
@pytest.mark.parametrize('approvers_first', (False, True))
@pytest.mark.parametrize('together', (False, True))
def test_settled_load_queries_once_after_both_inputs(
        estimate_scheduler, overlay, approvers_first, together):
    window = scheduled_estimate_window(overlay)
    form, loaded = window._request_content, set()
    form.time_estimate_selection.side_effect = lambda: (
        (1001, 75) if loaded == {'preferences', 'approvers'} else None)
    form.set_preferences = Mock(side_effect=lambda _value: loaded.add('preferences'))
    form.set_approvers = Mock(side_effect=lambda _value: loaded.add('approvers'))
    form.is_selected_account = Mock(return_value=True)
    form.muted_for_surface = Mock(return_value=True)
    window._apply_mute = Mock()
    window._mute_surface = Mock(return_value='child' if overlay else 'kiosk')
    window._log_duration_selection = Mock()
    window._show_error = Mock()
    connection = SimpleNamespace(call_finish=lambda value: SimpleNamespace(unpack=lambda: value))
    loads = [
        lambda: window._preferences_done(1001, connection, ('{"parent_control_enabled":true}',)),
        lambda: window._approvers_done(connection, (((1000, '[Parent user]', ''),),)),
    ]
    if approvers_first:
        loads.reverse()
    loads[0]()
    if not together:
        estimate_scheduler.fire()
    window._bus_call.assert_not_called()
    loads[1]()
    assert estimate_scheduler.delays == [0, 0]
    estimate_scheduler.fire()
    window._bus_call.assert_called_once()
    assert window._bus_call.call_args.args[0] == 'GetTimeStatus'
    assert window._bus_call.call_args.args[1].unpack() == (1001, 75)
    window._show_error.assert_not_called()


@pytest.mark.parametrize('overlay', (False, True))
def test_edit_replaces_settled_dispatch_with_typing_debounce(estimate_scheduler, overlay):
    window = scheduled_estimate_window(overlay)
    window._queue_time_estimate(settled=True)
    window._request_content.time_estimate_selection.return_value = (1001, 600)
    window._form_values_changed()
    assert estimate_scheduler.delays == [0, 250]
    window._bus_call.assert_not_called()
    estimate_scheduler.fire()
    window._bus_call.assert_called_once()
    assert window._bus_call.call_args.args[1].unpack() == (1001, 600)
    window._persist_form_values.assert_called_once()


@pytest.mark.parametrize('overlay', (False, True))
@pytest.mark.parametrize('dispatch_first', (False, True))
@pytest.mark.parametrize('error', (None, RuntimeError('private backend details')))
def test_settled_load_coalesces_old_in_flight_reply(
        estimate_scheduler, overlay, dispatch_first, error):
    window = scheduled_estimate_window(overlay)
    window._refresh_time_estimate()
    window._request_content.time_estimate_selection.return_value = (1002, 600)
    window._queue_time_estimate(settled=True)
    window._request_content.set_time_estimate.reset_mock()
    if dispatch_first:
        estimate_scheduler.fire()
    reply(window, error=error)
    if not dispatch_first:
        estimate_scheduler.fire()
    assert window._bus_call.call_count == 2
    assert window._bus_call.call_args.args[1].unpack() == (1002, 600)
    window._request_content.set_time_estimate.assert_not_called()
    window._errors.handle.assert_not_called()
    reply(window, seconds=1800)
    window._request_content.set_time_estimate.assert_called_once_with(
        'Estimated remaining time: 30m')


@pytest.mark.parametrize('error', (None, RuntimeError('private backend details')))
def test_destroy_cancels_settled_dispatch_and_late_reply(estimate_scheduler, error):
    window = scheduled_estimate_window()
    window._refresh_time_estimate()
    window._queue_time_estimate(settled=True)
    callback = next(iter(estimate_scheduler.pending.values()))
    window._startup_clock_handler = window._estimate_refresh_id = 0
    window._whats_new = Mock()
    window._agent_locale = window._session_logout = window._thunder = None
    window._cancel_success_dismiss = Mock()
    window._on_destroy()
    assert not estimate_scheduler.pending
    assert window._estimate_debounce_id == 0
    window._request_content.set_time_estimate.reset_mock()
    reply(window, error=error)
    callback()
    assert window._bus_call.call_count == 1
    window._request_content.set_time_estimate.assert_not_called()
    window._errors.handle.assert_not_called()


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


@pytest.mark.parametrize('available,basic', [
    (('C', 'C.utf8', 'POSIX'), 'C.utf8'),
    (('C', 'C.UTF-8', 'POSIX'), 'C.UTF-8'),
    (('C', 'POSIX'), 'C'),
])
def test_agent_locale_uses_source_text_on_basic_locale_hosts(available, basic):
    import os
    before = dict(os.environ)
    assert agent_environment('zh-Hans', 'zh_CN.UTF-8', available) == (
        f'LANG={basic}\nLANGUAGE=C\nLC_ALL={basic}\n')
    assert dict(os.environ) == before


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
def test_agent_failed_locale_change_invalidates_previously_applied_settings(tmp_path, failure, caplog):
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
        from common.oh_no_parent_control_ui.diagnostic_events import decode
        observations = [decode(record.onpc_payload) for record in caplog.records]
        assert any(value['event'] == 'kiosk.agent-preparation-failed' and value['fields'] == {
            'stage': 'timeout' if failure == 'timeout' else 'job-result'} for value in observations)
        if failure == 'failed':
            assert any(value['event'] == 'kiosk.agent-job-failed' and value['fields'] == {
                'result': 'failed'} for value in observations)
        assert str(tmp_path) not in caplog.text
        assert 'zh-Hans' not in caplog.text
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


def request_window(overlay=False):
    form = Mock()
    form.selected.return_value = (1001, '[Child user]', 1000, 300, False)
    form.selected_preferences.return_value = ('300', 5.0, False)
    form.custom_unit.return_value = 'minutes'
    return bind_methods(SimpleNamespace(
        _preview=False, _child_overlay=overlay, _estimate_closed=False,
        _state=RequestState(), _request_revision=0, _request_stage=None,
        _pending_request=None, _request_content=form,
        _agent_locale=Mock(), _applied_language='zh-Hans', _desktop_language='zh_CN.UTF-8',
        _bus_call=Mock(), _log_duration_selection=Mock(), _set_request_controls=Mock(),
        _show_error=Mock(), _show_result=Mock(), _show_child_success=Mock(),
        _schedule_success_logout=Mock(), _queue_time_estimate=Mock(), _stack=Mock(),
        _startup_clock_handler=0, _whats_new=Mock(), _session_logout=None,
        _estimate_debounce_id=0, _estimate_refresh_id=0,
        _cancel_success_dismiss=Mock(), _thunder=None,
    ), RequestWindow, (
        '_request_access', '_request_is_current', '_preferences_saved', '_agent_prepared',
        '_request_done', '_present_request_outcome', '_request_failed', '_finish_request', '_on_destroy',
    ))


def finish_request_call(callback, *, values=(), error=None):
    connection = SimpleNamespace(call_finish=Mock(
        side_effect=error, return_value=SimpleNamespace(unpack=lambda: values)))
    callback(connection, object())
    return connection


def prepare_request(window):
    window._request_access()
    saved = window._bus_call.call_args.args[3]
    finish_request_call(saved)
    if not window._child_overlay:
        window._agent_locale.prepare.call_args.args[2](None)
    return window._bus_call.call_args.args[3]


def test_kiosk_request_waits_for_agent_locale_and_failure_is_terminal():
    window = request_window()
    window._request_access()
    saved = window._bus_call.call_args.args[3]
    finish_request_call(saved)
    language, desktop, callback = window._agent_locale.prepare.call_args.args
    assert (language, desktop) == ('zh-Hans', 'zh_CN.UTF-8')
    assert window._bus_call.call_count == 1
    callback(RuntimeError('restart failed'))
    assert not window._state.in_flight
    window._show_error.assert_called_once()
    callback(None)
    assert window._bus_call.call_count == 1
    assert window._pending_request is None
    # Retry is a new explicit request, never a revival of the failed one.
    prepare_request(window)
    assert window._state.in_flight
    assert window._bus_call.call_args.args[0] == 'RequestAccess'
    calls = window._bus_call.call_count
    callback(None)
    callback(RuntimeError('old preparation failure'))
    assert window._state.in_flight
    assert window._bus_call.call_count == calls


@pytest.mark.parametrize('error,result', [
    (subprocess.CalledProcessError(1, ['/usr/bin/locale', '-a']), 'done'),
    (subprocess.TimeoutExpired(['/usr/bin/locale', '-a'], 5), 'done'),
    (FileNotFoundError('locale unavailable'), 'done'),
    (subprocess.CalledProcessError(1, ['/usr/bin/locale', '-a']), 'failed'),
])
def test_locale_discovery_failure_preserves_real_agent_and_request(
        tmp_path, error, result, caplog):
    window = request_window()
    agent = window._agent_locale = KioskAgentLocale()
    bus = Mock()
    before = dict(os.environ)
    with (patch('oh_no_parent_control_kiosk.agent_locale.subprocess.run', side_effect=error) as inventory,
          patch('oh_no_parent_control_kiosk.agent_locale.GLib.get_user_runtime_dir', return_value=str(tmp_path)),
          patch('oh_no_parent_control_kiosk.agent_locale.Gio.bus_get_sync', return_value=bus),
          patch('oh_no_parent_control_kiosk.agent_locale.GLib.timeout_add_seconds', return_value=42),
          patch('oh_no_parent_control_kiosk.agent_locale.GLib.source_remove')):
        window._request_access()
        finish_request_call(window._bus_call.call_args.args[3])
        inventory.assert_called_once_with(['/usr/bin/locale', '-a'], check=True,
                                          capture_output=True, text=True, timeout=5)
        assert agent._locales is None
        assert (tmp_path / 'oh-no-parent-control/polkit-agent.env').read_text() == (
            'LANG=C\nLANGUAGE=C\nLC_ALL=C\n')
        assert bus.call.call_args.args[3] == 'RestartUnit'
        assert window._bus_call.call_count == 1
        agent._completed(result)
        if result == 'done':
            assert window._bus_call.call_args.args[0] == 'RequestAccess'
            assert window._bus_call.call_args.args[1].unpack() == (1001, 1000, 300, False)
            window._show_error.assert_not_called()
        else:
            assert window._bus_call.call_count == 1
            window._show_error.assert_called_once()
            assert not window._state.in_flight
        assert (window._applied_language, window._desktop_language) == ('zh-Hans', 'zh_CN.UTF-8')
        assert dict(os.environ) == before
        observations = [decode(record.onpc_payload) for record in caplog.records]
        assert any(value['event'] == 'kiosk.agent-preparation-failed'
                   and value['fields'] == {'stage': 'locale-discovery'}
                   for value in observations)
        # The failure is not a permanent empty inventory: restored discovery
        # prepares the selected language and still waits for the required job.
        inventory.side_effect = None
        inventory.return_value = SimpleNamespace(stdout='C\nC.utf8\nzh_CN.utf8\n')
        done = Mock()
        agent.prepare('zh-Hans', 'zh_CN.UTF-8', done)
        assert inventory.call_count == 2
        assert 'LANGUAGE=zh_CN\n' in (tmp_path / 'oh-no-parent-control/polkit-agent.env').read_text()
        done.assert_not_called()
        agent._completed('done')
        done.assert_called_once_with(None)
        agent.close()


@pytest.mark.parametrize('overlay', (False, True))
def test_request_snapshot_and_each_async_stage_are_single_use(overlay):
    window = request_window(overlay)
    window._request_access()
    saved = window._bus_call.call_args.args[3]
    window._request_access()
    assert window._bus_call.call_count == 1
    window._request_content.selected.return_value = (1002, '[Child user]', 1010, 600, True)
    finish_request_call(saved)
    finish_request_call(saved, error=RuntimeError('duplicate save'))
    if not overlay:
        language, desktop, prepared = window._agent_locale.prepare.call_args.args
        assert (language, desktop) == ('zh-Hans', 'zh_CN.UTF-8')
        assert window._bus_call.call_count == 1
        prepared(None)
        prepared(None)
        prepared(RuntimeError('duplicate job'))
    assert window._bus_call.call_count == 2
    method, parameters, signature, completed, timeout = window._bus_call.call_args.args
    assert method == ('RequestOwnAccess' if overlay else 'RequestAccess')
    assert parameters.unpack() == ((1000, 300, False) if overlay else
                                   (1001, 1000, 300, False))
    assert signature == ('(ssu)' if overlay else '(ss)')
    from gi.repository import GLib
    assert timeout == GLib.MAXINT  # Human authentication has no frontend deadline.
    correlation = '11111111-1111-4111-8111-111111111111'
    values = (correlation, 'approved', 300) if overlay else (correlation, 'approved')
    finish_request_call(completed, values=values)
    assert not window._state.in_flight
    assert window._pending_request is None
    assert window._request_stage is None
    finish_request_call(completed, error=RuntimeError('duplicate result'))
    if overlay:
        window._show_child_success.assert_called_once_with()
    else:
        window._show_result.assert_called_once()
        window._schedule_success_logout.assert_called_once_with()
    window._show_error.assert_not_called()
    assert [call.args for call in window._set_request_controls.call_args_list] == [
        (False,), (True,)]


def test_child_language_resolved_during_preferences_save_prepares_current_locale():
    window = request_window()
    # A child switch can finish loading request choices before its language
    # reply arrives. Submission must not freeze the preceding child's locale.
    window._applied_language, window._desktop_language = 'en', ''
    window._request_access()
    saved = window._bus_call.call_args.args[3]
    window._applied_language, window._desktop_language = 'de', 'de_DE.UTF-8'
    finish_request_call(saved)
    language, desktop, prepared = window._agent_locale.prepare.call_args.args
    assert (language, desktop) == ('de', 'de_DE.UTF-8')
    prepared(None)
    assert window._bus_call.call_args.args[0] == 'RequestAccess'
    assert window._bus_call.call_args.args[1].unpack() == (1001, 1000, 300, False)


@pytest.mark.parametrize('overlay', (False, True))
def test_failed_preferences_callback_cannot_restart_approval(overlay):
    window = request_window(overlay)
    window._request_access()
    saved = window._bus_call.call_args.args[3]
    finish_request_call(saved, error=RuntimeError('preferences unavailable'))
    window._show_error.assert_called_once()
    assert not window._state.in_flight
    window._request_access()
    for error in (None, RuntimeError('old preferences failure')):
        stale = finish_request_call(saved, error=error)
        stale.call_finish.assert_not_called()
    assert window._bus_call.call_count == 2
    assert window._request_stage == 'preferences'
    assert window._state.in_flight
    window._agent_locale.prepare.assert_not_called()


@pytest.mark.parametrize('overlay', (False, True))
@pytest.mark.parametrize('outcome', ('denied', 'cancelled', 'failure'))
def test_finished_attempt_cannot_dispatch_or_finish_a_fresh_request(overlay, outcome):
    window = request_window(overlay)
    completed = prepare_request(window)
    if outcome == 'failure':
        finish_request_call(completed, error=RuntimeError('unavailable'))
    else:
        correlation = '11111111-1111-4111-8111-111111111111'
        values = (correlation, outcome, 0) if overlay else (correlation, outcome)
        finish_request_call(completed, values=values)
        if outcome == 'cancelled':
            window._request_content.clear_validation_error.assert_called_once_with()
            window._request_content.show_validation_error.assert_not_called()
            window._show_error.assert_not_called()
    window._request_content.selected.return_value = (1002, '[Child user]', 1010, 600, True)
    window._request_content.selected_preferences.return_value = ('600', 10.0, True)
    window._request_access()
    new_saved = window._bus_call.call_args.args[3]
    controls = window._set_request_controls.call_count
    for error in (None, RuntimeError('late old result')):
        stale = finish_request_call(completed, values=('old', 'approved', 300), error=error)
        stale.call_finish.assert_not_called()
    assert window._state.in_flight
    assert window._pending_request == (1002, 1010, 600, True)
    assert window._request_stage == 'preferences'
    assert window._set_request_controls.call_count == controls
    finish_request_call(new_saved)
    if not overlay:
        window._agent_locale.prepare.call_args.args[2](None)
    correlation = '22222222-2222-4222-8222-222222222222'
    values = (correlation, 'approved', 600) if overlay else (correlation, 'approved')
    finish_request_call(window._bus_call.call_args.args[3], values=values)
    assert not window._state.in_flight
    if overlay:
        window._show_child_success.assert_called_once_with()
    else:
        window._schedule_success_logout.assert_called_once_with()


@pytest.mark.parametrize('overlay,stage', ((False, 'preferences'), (True, 'preferences'),
                                         (False, 'agent'), (False, 'approval'),
                                         (True, 'approval')))
@pytest.mark.parametrize('error', (None, RuntimeError('late request failure')))
def test_destroy_discards_every_pending_request_stage(overlay, stage, error):
    window = request_window(overlay)
    window._request_access()
    callback = window._bus_call.call_args.args[3]
    if stage != 'preferences':
        finish_request_call(callback)
        if not overlay:
            callback = window._agent_locale.prepare.call_args.args[2]
            if stage == 'approval':
                callback(None)
        if stage == 'approval':
            callback = window._bus_call.call_args.args[3]
    window._on_destroy()
    calls, preparations = window._bus_call.call_count, window._agent_locale.prepare.call_count
    controls = window._set_request_controls.call_count
    if stage == 'agent':
        callback(error)
    else:
        stale = finish_request_call(callback, values=('old', 'approved', 300), error=error)
        stale.call_finish.assert_not_called()
    window._request_access()
    assert window._bus_call.call_count == calls
    assert window._agent_locale.prepare.call_count == preparations
    assert window._set_request_controls.call_count == controls
    window._show_result.assert_not_called()
    window._show_child_success.assert_not_called()
    window._schedule_success_logout.assert_not_called()
    window._show_error.assert_not_called()
    assert window._pending_request is None


@pytest.mark.parametrize('finish', ['done', 'failed', 'close'])
def test_request_during_agent_warmup_waits_reuses_or_retries(tmp_path, finish):
    agent = KioskAgentLocale()
    agent._locales = ('en_US.utf8',)
    bus, done = Mock(), Mock()
    with (patch('oh_no_parent_control_kiosk.agent_locale.GLib.get_user_runtime_dir', return_value=str(tmp_path)),
          patch('oh_no_parent_control_kiosk.agent_locale.Gio.bus_get_sync', return_value=bus),
          patch('oh_no_parent_control_kiosk.agent_locale.GLib.timeout_add_seconds', return_value=42),
          patch('oh_no_parent_control_kiosk.agent_locale.GLib.source_remove')):
        agent.warm('en', '')
        agent.prepare('en', '', done)
        done.assert_not_called()
        assert bus.call.call_count == 1
        if finish == 'close':
            late = bus.call.call_args.args[-1]
            agent.close()
            late(bus, object())
            done.assert_not_called()
            assert not agent._queue
        else:
            agent._completed(finish)
            if finish == 'failed':
                done.assert_not_called()
                assert bus.call.call_count == 2
                agent._completed('done')
            else:
                assert bus.call.call_count == 1
            done.assert_called_once_with(None)
        agent.close()


def test_agent_warmup_keeps_latest_language_and_required_request_order(tmp_path):
    agent = KioskAgentLocale()
    agent._locales = ('en_US.utf8',)
    bus, done = Mock(), Mock()
    with (patch('oh_no_parent_control_kiosk.agent_locale.GLib.get_user_runtime_dir', return_value=str(tmp_path)),
          patch('oh_no_parent_control_kiosk.agent_locale.Gio.bus_get_sync', return_value=bus),
          patch('oh_no_parent_control_kiosk.agent_locale.GLib.timeout_add_seconds', return_value=42),
          patch('oh_no_parent_control_kiosk.agent_locale.GLib.source_remove')):
        agent.warm('en', '')
        agent.warm('de', '')
        agent.warm('zh-Hans', '')
        agent.prepare('zh-Hans', '', done)
        agent._completed('done')
        done.assert_not_called()
        assert bus.call.call_count == 2
        assert 'LANGUAGE=zh_CN\n' in (tmp_path / 'oh-no-parent-control/polkit-agent.env').read_text()
        agent._completed('done')
        done.assert_called_once_with(None)
        assert bus.call.call_count == 2
        assert not agent._queue
        agent.close()


@pytest.mark.parametrize('during_completion', (False, True))
def test_agent_close_is_terminal_and_discards_queued_reentrant_preparation(tmp_path, during_completion):
    agent = KioskAgentLocale()
    agent._locales = ('en_US.utf8',)
    bus, done, discarded = Mock(), Mock(), Mock()
    with (patch('oh_no_parent_control_kiosk.agent_locale.GLib.get_user_runtime_dir', return_value=str(tmp_path)),
          patch('oh_no_parent_control_kiosk.agent_locale.Gio.bus_get_sync', return_value=bus),
          patch('oh_no_parent_control_kiosk.agent_locale.GLib.timeout_add_seconds', return_value=42),
          patch('oh_no_parent_control_kiosk.agent_locale.GLib.source_remove')):
        agent.prepare('en', '', done)
        late = bus.call.call_args.args[-1]
        agent.warm('de', '')

        def close_and_reenter(_error=None):
            agent.close()
            agent.prepare('fr', '', discarded)
            agent.warm('zh-Hans', '')

        if during_completion:
            done.side_effect = close_and_reenter
            agent._completed('done')
            done.assert_called_once_with(None)
        else:
            close_and_reenter()
            done.assert_not_called()
        late(bus, object())
        agent._completed('done')
        agent._timed_out()
        assert bus.call.call_count == 1
        bus.call_finish.assert_not_called()
        bus.signal_unsubscribe.assert_called_once()
        assert agent._deadline == agent._subscription == 0
        assert not agent._queue
        discarded.assert_not_called()


def test_previous_agent_deadline_cannot_fail_the_next_locale_job(tmp_path):
    agent = KioskAgentLocale()
    agent._locales = ('en_US.utf8',)
    bus, done = Mock(), Mock()
    with (patch('oh_no_parent_control_kiosk.agent_locale.GLib.get_user_runtime_dir', return_value=str(tmp_path)),
          patch('oh_no_parent_control_kiosk.agent_locale.Gio.bus_get_sync', return_value=bus),
          patch('oh_no_parent_control_kiosk.agent_locale.GLib.timeout_add_seconds', side_effect=(41, 42)) as deadlines,
          patch('oh_no_parent_control_kiosk.agent_locale.GLib.source_remove')):
        agent.warm('en', '')
        expired_previous_job = deadlines.call_args.args[1]
        agent.prepare('de', '', done)
        agent._completed('done')
        assert bus.call.call_count == 2
        expired_previous_job()
        done.assert_not_called()
        assert agent._deadline == 42
        agent._completed('done')
        done.assert_called_once_with(None)
        agent.close()


@pytest.mark.parametrize('blocked', [None, '_preview', '_child_overlay', '_estimate_closed', 'in_flight'])
def test_agent_warmup_is_only_for_idle_installed_station(blocked):
    window = SimpleNamespace(_preview=False, _child_overlay=False, _estimate_closed=False,
        _state=SimpleNamespace(in_flight=False), _agent_locale=Mock(),
        _applied_language='de', _desktop_language='de_DE.UTF-8')
    if blocked == 'in_flight':
        window._state.in_flight = True
    elif blocked:
        setattr(window, blocked, True)
    RequestWindow._warm_authentication(window)
    if blocked:
        window._agent_locale.warm.assert_not_called()
    else:
        window._agent_locale.warm.assert_called_once_with('de', 'de_DE.UTF-8')


def test_kiosk_logout_acknowledges_session_protocol_before_exiting():
    from gi.repository import GLib
    app, connection = Mock(), Mock()
    app.get_dbus_connection.return_value = connection
    app.get_application_id.return_value = 'com.example.Station'
    logout = KioskLogout(app)
    with (patch('oh_no_parent_control_kiosk.session_logout.GLib.timeout_add', return_value=42),
          patch('oh_no_parent_control_kiosk.session_logout.GLib.source_remove')):
        logout.begin()
        logout.begin()
        assert connection.call.call_count == 1
        assert connection.call.call_args.args[3] == 'RegisterClient'
        connection.call_finish.return_value = GLib.Variant('(o)', ('/client/station',))
        connection.call.call_args.args[-1](connection, object())
        assert connection.call.call_args.args[3:5] == ('Logout', GLib.Variant('(u)', (2,)))
        app.quit.assert_not_called()
        for signal in ('QueryEndSession', 'EndSession'):
            logout._signal(connection, None, None, None, signal, None)
            args = connection.call.call_args.args
            assert args[1:4] == ('/client/station', 'org.gnome.SessionManager.ClientPrivate',
                                 'EndSessionResponse')
            assert args[4].unpack() == (True, '')
            app.quit.assert_not_called()
        logout._signal(connection, None, None, None, 'Stop', None)
        logout._signal(connection, None, None, None, 'Stop', None)
        app.quit.assert_called_once()
        connection.signal_unsubscribe.assert_called_once()


@pytest.mark.parametrize('during_registration', [False, True])
def test_kiosk_logout_prepares_without_exiting_and_keeps_click_deadline(during_registration):
    from gi.repository import GLib
    app, connection = Mock(), Mock()
    app.get_dbus_connection.return_value = connection
    app.get_application_id.return_value = 'com.example.Station'
    logout = KioskLogout(app)
    with (patch('oh_no_parent_control_kiosk.session_logout.GLib.timeout_add', return_value=42) as deadline,
          patch('oh_no_parent_control_kiosk.session_logout.GLib.source_remove')):
        logout.prepare()
        logout.prepare()
        assert connection.call.call_count == 1
        assert connection.call.call_args.args[3] == 'RegisterClient'
        registered = connection.call.call_args.args[-1]
        app.quit.assert_not_called()
        deadline.assert_not_called()
        if during_registration:
            logout.begin()
            assert connection.call.call_count == 1
        connection.call_finish.return_value = GLib.Variant('(o)', ('/client/station',))
        registered(connection, object())
        if not during_registration:
            assert connection.call.call_count == 1
            logout._signal(connection, None, None, None, 'CancelEndSession', None)
            app.quit.assert_not_called()
            logout.begin()
        deadline.assert_called_once_with(750, logout._expired)
        assert connection.call.call_count == 2
        assert connection.call.call_args.args[3] == 'Logout'
        app.quit.assert_not_called()
        logout._expired()
        app.quit.assert_called_once()


@pytest.mark.parametrize('failure', ['missing-bus', 'register', 'logout', 'timeout', 'closed'])
def test_kiosk_logout_falls_back_once_and_ignores_late_replies(failure, caplog):
    from gi.repository import GLib
    app, connection = Mock(), Mock()
    app.get_dbus_connection.return_value = None if failure == 'missing-bus' else connection
    app.get_application_id.return_value = 'com.example.Station'
    logout = KioskLogout(app)
    with (patch('oh_no_parent_control_kiosk.session_logout.GLib.timeout_add', return_value=42),
          patch('oh_no_parent_control_kiosk.session_logout.GLib.source_remove')):
        logout.begin()
        if failure != 'missing-bus':
            registered = connection.call.call_args.args[-1]
            if failure == 'closed':
                logout.close()
            elif failure == 'timeout':
                logout._expired()
            elif failure == 'register':
                connection.call_finish.side_effect = RuntimeError('PRIVATE unavailable')
                registered(connection, object())
            else:
                connection.call_finish.return_value = GLib.Variant('(o)', ('/client/station',))
                registered(connection, object())
                connection.call_finish.side_effect = RuntimeError('PRIVATE unavailable')
                connection.call.call_args.args[-1](connection, object())
            connection.call_finish.reset_mock()
            registered(connection, object())
            connection.call_finish.assert_not_called()
        assert app.quit.call_count == (0 if failure == 'closed' else 1)
        from common.oh_no_parent_control_ui.diagnostic_events import decode
        observations = [decode(record.onpc_payload)['fields'] for record in caplog.records
                        if decode(record.onpc_payload)['event'] == 'kiosk.logout-fallback']
        expected = {
            'missing-bus': ('connection', 'unavailable'), 'register': ('register-reply', 'failed'),
            'logout': ('logout-reply', 'failed'), 'timeout': ('deadline', 'timeout'),
        }
        assert observations == ([] if failure == 'closed' else [dict(
            stage=expected[failure][0], outcome=expected[failure][1], requested=True)])
        assert 'PRIVATE' not in caplog.text
        assert '/client/station' not in caplog.text
        logout.close()


@pytest.mark.parametrize('stage', ['register-dispatch', 'response-dispatch', 'response-reply'])
def test_kiosk_logout_dispatch_and_acknowledgement_failures_keep_transport_cause(stage, caplog):
    from gi.repository import Gio, GLib
    from common.oh_no_parent_control_ui.diagnostic_events import decode

    app, connection = Mock(), Mock()
    app.get_dbus_connection.return_value = connection
    app.get_application_id.return_value = 'PRIVATE-app'
    logout = KioskLogout(app)
    error = Gio.DBusError.new_for_dbus_error('org.freedesktop.DBus.Error.NoReply', 'PRIVATE session')
    with (patch('oh_no_parent_control_kiosk.session_logout.GLib.timeout_add', return_value=42),
          patch('oh_no_parent_control_kiosk.session_logout.GLib.source_remove')):
        if stage == 'register-dispatch':
            connection.call.side_effect = error
        logout.begin()
        if stage != 'register-dispatch':
            connection.call_finish.return_value = GLib.Variant('(o)', ('/PRIVATE/client',))
            connection.call.call_args.args[-1](connection, object())
            if stage == 'response-dispatch':
                connection.call.side_effect = error
            logout._signal(connection, None, None, None, 'EndSession', None)
            if stage == 'response-reply':
                connection.call_finish.side_effect = error
                connection.call.call_args.args[-1](connection, object())
        app.quit.assert_called_once()
        observations = [decode(record.onpc_payload) for record in caplog.records]
        assert any(value['event'] == 'kiosk.logout-fallback' and value['fields'] == {
            'stage': stage, 'outcome': 'failed', 'requested': True} for value in observations)
        assert any(value['event'] == 'runtime.failure-gio' and value['fields']['category'] == 'no-reply'
                   for value in observations)
        assert 'PRIVATE' not in caplog.text


def test_logout_logging_failure_does_not_prevent_deadline_fallback():
    app = Mock(get_dbus_connection=Mock(return_value=None))
    logout = KioskLogout(app)
    with (patch('oh_no_parent_control_kiosk.session_logout.LOG.warning', side_effect=RuntimeError('PRIVATE')),
          patch('oh_no_parent_control_kiosk.session_logout.GLib.timeout_add', return_value=42),
          patch('oh_no_parent_control_kiosk.session_logout.GLib.source_remove')):
        logout.begin()
        app.quit.assert_called_once()
        logout._expired()
        app.quit.assert_called_once()


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
        "Estimated remaining time: 30m",
    )


def test_periodic_refresh_updates_estimate_and_recovers_after_failure():
    window = estimate_window()
    window._refresh_time_estimate()
    reply(window, error=RuntimeError("private backend details"))
    window._request_content.set_time_estimate.assert_called_with("Time estimate unavailable")
    window._refresh_time_estimate()
    reply(window, seconds=1190)
    window._request_content.set_time_estimate.assert_called_with(
        "Estimated remaining time: 19m 50s",
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
    ({}, "Estimated remaining time: 35m"),
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
    form.set_time_estimate("Estimated remaining time: 35m")
    form._status.set_label.assert_called_once_with(expected)


@pytest.mark.parametrize("seconds, expected", (
    (0, "0m"), (-1, "0m"), (6, "0m 6s"), (65, "1m 5s"),
    (59 * 60, "59m"), (60 * 60, "1h"), (77 * 60, "1h 17m"),
    (2 * 60 * 60, "2h"), (2 * 60 * 60 + 5, "2h 5s"),
    (90 * 60 + 30, "1h 30m 30s"), (24 * 60 * 60, "24h"),
))
def test_shared_duration_format_preserves_precision_and_omits_zero_minutes(seconds, expected):
    assert format_duration(seconds) == expected
    assert _time_estimate_label(seconds) == f"Estimated remaining time: {expected}"


def test_pending_estimate_keeps_label_with_blank_value_until_result():
    form = bind_methods(SimpleNamespace(
        _accounts_loaded=True, _approvers_loaded=True, _account_uids=[1001],
        _approver_uids=[1000], _screen_time_limit_enabled=True,
        _validation_error=None, _controls_enabled=True,
        selected=Mock(return_value=(1001, "Child", 1000, 300, False)),
        _status=Mock(),
    ), RequestContent, ("set_time_estimate", "_update_status"))
    form.set_time_estimate(None)
    form._status.set_label.assert_called_with("Estimated remaining time: ")
    form.set_time_estimate(None)
    form._status.set_label.assert_called_with("Estimated remaining time: ")
    form.set_time_estimate(_time_estimate_label(4620))
    form._status.set_label.assert_called_with("Estimated remaining time: 1h 17m")
    assert all(call.args[0].startswith("Estimated remaining time: ")
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
def test_preview_release_notes_use_checkout_when_older_product_is_installed(
        overlay, tmp_path, monkeypatch):
    from common.oh_no_parent_control_ui import about
    from common.oh_no_parent_control_ui.release_markdown import markdown_blocks
    from common.oh_no_parent_control_ui.whats_new import load_whats_new_translations, translate_content

    source = tmp_path / 'source'
    source.mkdir()
    (source / 'app.json').write_text('{"version": "1.5"}', encoding='utf-8')
    (source / 'whats-new-child.toml').write_text(
        "version = 1\n[[records]]\nProductVersion = '1.5'\nContent = '''\n"
        "## New features\n- **Remaining time reminders:** Customize reminders.\n"
        "- **Request Time Form**: Customize preset times.\n'''\n", encoding='utf-8')
    installed = tmp_path / 'installed'
    installed.mkdir()
    (installed / 'app.json').write_text('{"version": "1.4"}', encoding='utf-8')
    (installed / 'whats-new-child.toml').write_text(
        "version = 1\n[[records]]\nProductVersion = '1.4'\n"
        "Content = 'Older installed notes'\n", encoding='utf-8')
    monkeypatch.setattr(about, '_INSTALLED_DATA_DIR', installed)
    monkeypatch.setattr(about, '_SOURCE_DATA_DIR', source)
    presenter = release_presenter(overlay)
    presenter.window._preview = True
    presenter.window._interactive_preview = False
    presenter.select_child(1001)

    assert presenter.record is not None
    assert presenter.record['ProductVersion'] == '1.5'
    translations = load_whats_new_translations('1.5', 'en')
    blocks = markdown_blocks(translate_content(presenter.record, translations))
    notes = '\n'.join(markup for kind, markup in blocks if kind == 'list')
    assert 'Remaining time reminders:' in notes
    assert 'Request Time Form' in notes
    presenter.window._bus_call.assert_not_called()


def test_branding_uses_installed_assets_when_checkout_data_is_absent(tmp_path, monkeypatch):
    from common.oh_no_parent_control_ui import about

    installed = tmp_path / 'installed'
    installed.mkdir()
    monkeypatch.setattr(about, '_INSTALLED_DATA_DIR', installed)
    monkeypatch.setattr(about, '_SOURCE_DATA_DIR', tmp_path / 'absent')
    assert about.branding_asset_path('app.json') == installed / 'app.json'


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
