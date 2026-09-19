"""Exercise collection lifecycle without a display, email, or real diagnostics."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from common.oh_no_parent_control_ui import feedback
from common.oh_no_parent_control_ui.feedback_transport import Attachment


@pytest.fixture
def dialog(monkeypatch):
    jobs, callbacks = [], []
    # Exercise the lifecycle with widget doubles even in a displayless build.
    monkeypatch.setattr(feedback, "_feedback_icon", Mock())
    monkeypatch.setattr(feedback.threading, "Thread",
                        lambda *, target, daemon: SimpleNamespace(start=lambda: jobs.append(target)))
    monkeypatch.setattr(feedback.GLib, "idle_add", lambda fn, *args: callbacks.append((fn, args)))
    monkeypatch.setattr(feedback, "collect_logs", Mock(return_value=b"validated snapshot"))
    monkeypatch.setattr(feedback, "app_version", lambda: "1.2")
    monkeypatch.setattr(feedback.transport, "SENDING_ENABLED", True)
    instance = SimpleNamespace(
        _busy=False, _collecting=False, _collection_failed=False, _disposed=False,
        _include_logs=True, _logs=None, _kiosk_session=False, _on_close=None,
        _attachment_rows=[], _user_attachments=[], _subject="", _cancelled=Mock(),
        get_visible=Mock(return_value=True), _choose_download=Mock(),
        _submission_progress=Mock(), _submission_done=Mock(),
        _update_attachment_accessibility=Mock(),
    )
    for name in ("message", "reply", "collection_row", "collection_spinner", "attachment",
                 "attachment_button", "download_button", "add_attachment_button",
                 "without_logs", "retry_logs", "send_button", "close_button", "status"):
        setattr(instance, "_" + name, Mock())
    instance._message.plain_text = "My feedback draft"
    instance._message.html = "<p>My feedback draft</p>"
    instance._reply.get_text.return_value = ""
    for name in ("_visibility_changed", "_start_collection", "_collection_done", "_set_busy",
                 "_render_attachment", "_toggle_attachment", "_send", "_sending_hint", "_download_logs"):
        method = getattr(feedback.FeedbackDialog, name)
        setattr(instance, name, method.__get__(instance))
    instance.jobs, instance.callbacks = jobs, callbacks
    return instance


def finish_collection(dialog):
    dialog.jobs.pop(0)()
    callback, args = dialog.callbacks.pop(0)
    callback(*args)


def test_attachment_automation_keys_are_stable_and_never_duplicate():
    first = Attachment.create("same.txt", b"same bytes")
    second = Attachment.create("same.txt", b"same bytes")
    other = Attachment.create("other.txt", b"other bytes")
    first_key = feedback._attachment_automation_key(first, set())
    assert feedback._attachment_automation_key(first, set()) == first_key
    assert feedback._attachment_automation_key(second, {first_key}) == f"{first_key}-2"
    assert feedback._attachment_automation_key(other, {first_key}) != first_key


def test_open_collects_before_send_without_blocking_editor(dialog):
    dialog._visibility_changed()
    assert dialog._collecting
    assert len(dialog.jobs) == 1
    dialog._collection_row.set_visible.assert_called_with(True)
    dialog._send_button.set_sensitive.assert_called_with(False)
    dialog._message.set_sensitive.assert_called_with(True)
    dialog._reply.set_sensitive.assert_called_with(True)
    dialog._close_button.set_label.assert_called_with("Close")
    dialog._send(None)
    assert len(dialog.jobs) == 1  # The guarded send cannot create a submission.
    finish_collection(dialog)
    assert not dialog._collecting
    assert dialog._logs == b"validated snapshot"
    dialog._collection_row.set_visible.assert_called_with(False)
    dialog._attachment.set_title.assert_called_with("diagnostic-logs.zip")
    dialog._send_button.set_sensitive.assert_called_with(True)
    assert dialog._message.plain_text == "My feedback draft"


def test_download_and_send_use_the_reviewed_snapshot(dialog, monkeypatch):
    submitted = []
    monkeypatch.setattr(feedback.transport, "submit", lambda value, *_: submitted.append(value) or Mock())
    dialog._start_collection()
    finish_collection(dialog)
    dialog._download_logs(None)
    dialog._choose_download.assert_called_once_with(b"validated snapshot")
    dialog._set_busy(False)
    dialog._send(None)
    dialog.jobs.pop(0)()
    assert submitted[0].logs == b"validated snapshot"
    assert submitted[0].message == "My feedback draft"
    feedback.collect_logs.assert_called_once()


def test_failure_resolves_animation_and_requires_retry_or_explicit_opt_out(dialog):
    feedback.collect_logs.side_effect = OSError("private-person@example.test")
    dialog._start_collection()
    finish_collection(dialog)
    assert dialog._collection_failed and not dialog._collecting
    dialog._retry_logs.set_visible.assert_called_with(True)
    dialog._without_logs.set_visible.assert_called_with(True)
    dialog._send_button.set_sensitive.assert_called_with(False)
    assert "private-person" not in str(dialog._status.set_label.call_args)
    dialog._toggle_attachment(None)
    dialog._send_button.set_sensitive.assert_called_with(True)
    assert not dialog._include_logs
    feedback.collect_logs.side_effect = None
    dialog._toggle_attachment(None)
    assert dialog._collecting
    finish_collection(dialog)
    dialog._send_button.set_sensitive.assert_called_with(True)


def test_reopening_during_collection_keeps_one_worker_then_refreshes_next_open(dialog):
    dialog._visibility_changed()
    dialog.get_visible.return_value = False
    dialog._visibility_changed()
    dialog.get_visible.return_value = True
    dialog._visibility_changed()
    assert len(dialog.jobs) == 1
    finish_collection(dialog)
    dialog.get_visible.return_value = False
    dialog._visibility_changed()
    dialog.get_visible.return_value = True
    dialog._visibility_changed()
    assert dialog._logs is None and len(dialog.jobs) == 1
    dialog._send_button.set_sensitive.assert_called_with(False)


def test_reopening_during_submission_preserves_frozen_snapshot(dialog):
    dialog._logs = b"submitted snapshot"
    dialog._busy = True
    dialog._visibility_changed()
    assert not dialog.jobs
    assert dialog._logs == b"submitted snapshot"


def test_late_collection_completion_does_not_touch_destroyed_widgets(dialog):
    dialog._start_collection()
    dialog._disposed = True
    dialog._attachment.reset_mock()
    dialog._send_button.reset_mock()
    finish_collection(dialog)
    assert not dialog._attachment.mock_calls
    assert not dialog._send_button.mock_calls


def test_kiosk_collection_cannot_reveal_download_and_error_close_is_correct(dialog):
    dialog._kiosk_session = True
    dialog._on_close = Mock()
    dialog._start_collection()
    dialog._close_button.set_label.assert_called_with("Close")
    finish_collection(dialog)
    dialog._download_button.set_visible.assert_called_with(False)
    dialog._download_logs(None)
    dialog._choose_download.assert_not_called()


def test_worker_start_failure_restores_retry_state(dialog, monkeypatch):
    monkeypatch.setattr(feedback.threading, "Thread", Mock(side_effect=RuntimeError("private")))
    dialog._start_collection()
    assert not dialog._collecting
    assert dialog._collection_failed
    dialog._retry_logs.set_visible.assert_called_with(True)
