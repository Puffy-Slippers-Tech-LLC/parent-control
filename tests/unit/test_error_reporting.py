"""Reports preserve diagnostics locally and require explicit user submission."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from common.oh_no_parent_control_ui.errors import ErrorHandler, ErrorReport, install_exception_hooks
from common.oh_no_parent_control_ui import feedback_transport as transport
from oh_no_parent_control_kiosk.main import RequestWindow


@pytest.mark.parametrize("component", ("Kiosk App", "Child App", "Parent App"))
def test_error_report_component_copy_and_exception_chain(component, caplog):
    cause = ValueError("internal /private/path user@example.test")
    error = RuntimeError("operation failed")
    error.__cause__ = cause
    handler = ErrorHandler(None, component)
    report = handler.capture(error, "Request unavailable", "Please try again later.")
    assert report.subject == f"[Oh No! Parent Control] [{component}] Error Report"
    assert report.message == (
        "Request unavailable\nPlease try again later.\n\n--------------------\n\n"
        "RuntimeError: operation failed\nCaused by: ValueError: internal /private/path user@example.test"
    )
    assert "user@example.test" not in caplog.text
    assert "/private/path" not in caplog.text
    assert "operation failed" not in caplog.text
    assert "RuntimeError" in caplog.text


def test_large_exception_is_a_valid_editable_report():
    report = ErrorReport.capture("Child App", RuntimeError("😀\0" * 5000))
    assert "[truncated]" in report.message
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
    assert "first" in first.kwargs["report"].message
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
    assert "SyntaxError: invalid syntax" in report.message
    assert "private-token" not in report.message
