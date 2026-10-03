"""Reports preserve diagnostics locally and require explicit user submission."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from common.oh_no_parent_control_ui.errors import ErrorHandler, ErrorReport, install_exception_hooks
from common.oh_no_parent_control_ui import feedback_transport as transport
from oh_no_parent_control_kiosk.main import RequestWindow


@pytest.mark.parametrize('failure', (None, 'connect', 'dispatch', 'reply'))
def test_reboot_uses_unprivileged_async_logind_and_reports_failure(monkeypatch, failure):
    from gi.repository import Gio
    from common.oh_no_parent_control_ui.errors import request_reboot
    connection, done = Mock(), Mock()
    error = PermissionError('private detail')
    connect = Mock()
    monkeypatch.setattr(Gio, 'bus_get', connect)
    monkeypatch.setattr(Gio, 'bus_get_finish', Mock(
        return_value=connection, side_effect=error if failure == 'connect' else None))
    connection.call.side_effect = error if failure == 'dispatch' else None
    connection.call_finish.side_effect = error if failure == 'reply' else None
    request_reboot(done)
    assert connect.call_args.args[:2] == (Gio.BusType.SYSTEM, None)
    done.assert_not_called()
    connect.call_args.args[2](None, object())
    if failure not in ('connect', 'dispatch'):
        args = connection.call.call_args.args
        assert args[:4] == ('org.freedesktop.login1', '/org/freedesktop/login1',
                            'org.freedesktop.login1.Manager', 'Reboot')
        assert args[4].unpack() == (True,)
        assert args[6:9] == (Gio.DBusCallFlags.NONE, 120_000, None)
        done.assert_not_called()
        args[9](connection, object())
    done.assert_called_once_with(error if failure else None)
    connection.call_sync.assert_not_called()


@pytest.mark.parametrize('standalone', (False, True))
def test_update_dialog_default_close_red_reboot_coalescing_and_failure(monkeypatch, standalone):
    from gi.repository import Gtk
    from common.oh_no_parent_control_ui import errors, accessibility, translation_widgets
    parent = SimpleNamespace()
    dialog, message, status = Mock(), Mock(), Mock()
    widgets = iter((dialog, message, status))
    localized = Mock(side_effect=lambda *args, **kwargs: next(widgets))
    monkeypatch.setattr(translation_widgets, 'localized', localized)
    monkeypatch.setattr(translation_widgets, 'set_text', Mock())
    monkeypatch.setattr(Gtk, 'HeaderBar', Mock())
    monkeypatch.setattr(accessibility, 'set_automation_id', Mock())
    monkeypatch.setattr(accessibility, 'add_identified_window_controls', Mock())
    close, reboot = Mock(), Mock()
    buttons = Mock(side_effect=(close, reboot))
    monkeypatch.setattr(accessibility, 'add_dialog_button', buttons)
    request, dismissed = Mock(), Mock()
    monkeypatch.setattr(errors, 'request_reboot', request)
    options = {'application': parent} if standalone else {'parent': parent}
    assert errors.show_update_required(**options, on_close=dismissed) is dialog
    assert localized.call_args_list[0].kwargs['modal'] is True
    assert localized.call_args_list[0].kwargs['transient_for'] is (None if standalone else parent)
    if standalone:
        assert localized.call_args_list[0].kwargs['application'] is parent
    assert buttons.call_args.kwargs['css_class'] == 'destructive-action'
    dialog.set_default_response.assert_called_once_with(Gtk.ResponseType.CLOSE)
    callbacks = {call.args[0]: call.args[1] for call in dialog.connect.call_args_list}
    assert errors.show_update_required(**options) is dialog
    assert localized.call_count == 3
    request.assert_not_called()
    callbacks['response'](dialog, Gtk.ResponseType.ACCEPT)
    callbacks['response'](dialog, Gtk.ResponseType.ACCEPT)
    request.assert_called_once()
    assert callbacks['close-request']() is True
    reboot.set_sensitive.assert_called_with(False)
    dialog.destroy.assert_not_called()
    request.call_args.args[0](PermissionError('private detail'))
    reboot.set_sensitive.assert_called_with(True)
    assert callbacks['close-request']() is False
    status.set_visible.assert_called_with(True)
    dismissed.assert_not_called()
    callbacks['response'](dialog, Gtk.ResponseType.CLOSE)
    dialog.destroy.assert_called_once()
    dismissed.assert_called_once()
    assert parent._update_required_dialog is None


@pytest.mark.parametrize('overlay', (False, True))
def test_reboot_result_does_not_become_generic_error_on_late_failure(monkeypatch, overlay):
    from gi.repository import Gio
    from common.oh_no_parent_control_ui import messages as m
    import oh_no_parent_control_kiosk.main as kiosk
    monkeypatch.setattr(kiosk, 'set_text', Mock())
    modal = Mock()
    monkeypatch.setattr(kiosk, 'show_update_required', modal)
    window = SimpleNamespace(_child_overlay=overlay, _stack=Mock(), _result_action=Mock(),
                             _show_result=Mock(), _errors=Mock(), _estimate_closed=False)
    window._show_error = lambda error: RequestWindow._show_error(window, error)
    error = Gio.DBusError.new_for_dbus_error(
        'com.puffyslippers.OhNoParentControl1.Error.RebootRequired', 'private detail')
    window._show_error(error)
    RequestWindow._language_failed(window, RuntimeError('late unavailable'))
    assert window._reboot_required is True
    assert modal.call_count == 2
    window._show_result.assert_called_with(m.RESTART_REQUIRED, m.RESTART_FOR_PROPER_OPERATION)
    window._stack.set_sensitive.assert_called_with(True)
    window._errors.capture.assert_not_called()


@pytest.mark.parametrize("component", ("Kiosk App", "Child App", "Parent App"))
def test_error_report_component_copy_and_exception_chain(component, caplog):
    cause = ValueError("internal /private/path user@example.test")
    error = RuntimeError("operation failed")
    error.__cause__ = cause
    handler = ErrorHandler(None, component)
    report = handler.capture(error, "Request unavailable", "Please try again later.")
    assert report.subject == f"[Oh No! Parent Control] [{component}] Error Report"
    assert "Error categories: RuntimeError, ValueError" in report.message
    assert "user@example.test" not in repr(report)
    assert "/private/path" not in repr(report)
    assert "operation failed" not in repr(report)
    assert "user@example.test" not in caplog.text
    assert "/private/path" not in caplog.text
    assert "operation failed" not in caplog.text
    assert "RuntimeError" in caplog.text


def test_large_exception_is_a_valid_editable_report():
    report = ErrorReport.capture("Child App", RuntimeError("😀\0" * 5000))
    assert "RuntimeError" in report.message
    assert "😀" not in report.message
    assert transport.validation_error(report.message, "", "1.0") is None
    assert len(report.message.encode("utf-16-le")) // 2 < 4500


def test_report_coalesces_failures_without_overwriting_draft():
    dialogs = []

    def factory(parent, **kwargs):
        dialog = SimpleNamespace(parent=parent, kwargs=kwargs, present=Mock(), destroy=Mock())
        dialogs.append(dialog)
        return dialog

    handler = ErrorHandler(object(), "Kiosk App", dialog_factory=factory)
    done = Mock()
    first = handler.handle(RuntimeError("first"), on_close=done)
    second = handler.handle(RuntimeError("second"))
    assert first is second
    assert len(dialogs) == 1
    assert first.kwargs["kiosk_session"] is True
    assert first.kwargs["report"].internal == "RuntimeError"
    assert "first" not in first.kwargs["report"].message
    done.assert_not_called()
    first.kwargs["on_close"]()
    done.assert_called_once()
    first.destroy.assert_called_once()
    handler.handle(RuntimeError("third"))
    assert len(dialogs) == 2


@pytest.mark.parametrize("enabled", (True, False))
def test_result_exit_reviews_only_when_toggle_is_enabled(enabled):
    report = ErrorReport.capture("Kiosk App", RuntimeError("test"))
    window = SimpleNamespace(
        _error_report=report, _report_error=Mock(get_active=Mock(return_value=enabled)),
        _errors=Mock(), _cancel=Mock(),
    )
    RequestWindow._result_dismissed(window)
    if enabled:
        window._errors.present.assert_called_once_with(report, on_close=window._cancel)
        window._cancel.assert_not_called()
    else:
        window._errors.present.assert_not_called()
        window._cancel.assert_called_once()


@pytest.mark.parametrize("component", ("Kiosk App", "Child App", "Parent App"))
def test_report_subject_is_in_frozen_multipart_submission(component, monkeypatch):
    report = ErrorReport.capture(component, RuntimeError("error"))
    submission = transport.Submission.create(report.message, "", "1.0", subject=report.subject)
    response = Mock(status_code=202, json=Mock(return_value={"ok": True}))
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock()
    session = Mock(post=Mock(return_value=response))
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock()
    monkeypatch.setattr(transport.requests, "Session", lambda: session)
    assert transport.send_once(submission).kind == "success"
    assert ("title", (None, report.subject)) in session.post.call_args.kwargs["files"]


def test_transport_rejects_header_injection():
    with pytest.raises(ValueError, match="title"):
        transport.Submission.create("message", "", "1.0", subject="bad\r\nBcc: x@y.test")


def test_uncaught_callbacks_and_threads_share_main_loop_handler_and_stop_at_shutdown(monkeypatch):
    import sys
    import threading
    from gi.repository import GLib

    callbacks = []
    monkeypatch.setattr(GLib, "idle_add", lambda *args: callbacks.append(args))
    previous = sys.excepthook
    previous_thread = threading.excepthook
    window = SimpleNamespace(_show_error=Mock())
    application = Mock(get_windows=Mock(return_value=[window]))
    install_exception_hooks(application, "Parent App")
    shutdown = application.connect.call_args.args[1]
    error = RuntimeError("private internal details")
    try:
        sys.excepthook(type(error), error, None)
        threading.excepthook(SimpleNamespace(exc_type=type(error), exc_value=error, exc_traceback=None))
        assert len(callbacks) == 1
        callback, captured = callbacks.pop()
        callback(captured)
        window._show_error.assert_called_once_with(error)
        thread_hook = threading.excepthook
        shutdown()
        assert sys.excepthook is previous
        assert threading.excepthook is previous_thread
        thread_hook(SimpleNamespace(exc_type=type(error), exc_value=error, exc_traceback=None))
        assert callbacks == []
    finally:
        shutdown()


def test_syntax_errors_do_not_copy_source_lines_into_report():
    error = SyntaxError("invalid syntax", ("example.py", 1, 1, 'secret = "private-token"'))
    report = ErrorReport.capture("Parent App", error)
    assert "Error categories: other" in report.message
    assert "invalid syntax" not in report.message
    assert "private-token" not in report.message
