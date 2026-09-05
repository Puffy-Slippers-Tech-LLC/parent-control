"""Feedback contract tests: mocked delivery never sends support email."""

from dataclasses import replace
from email.parser import BytesParser
from email.policy import default
from unittest.mock import Mock
import uuid

import pytest
import requests

from parent.oh_no_parent_control_parent import feedback_transport as ft


@pytest.fixture
def report():
    return ft.Submission.create(
        "Private feedback 😀", "reply@example.com", "1.2",
        "<p><strong>Private feedback 😀</strong></p>",
        [
            ft.Attachment.create("private-note.txt", b"private attachment one", "text/plain"),
            ft.Attachment.create("image.png", b"private attachment two", "image/png"),
        ],
    )


def response(status, body=None, headers=None):
    result = Mock(status_code=status, headers=headers or {})
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    result.json.return_value = body
    return result


def install_response(monkeypatch, result):
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    session.post.return_value = result
    monkeypatch.setattr(ft.requests, "Session", lambda: session)
    return session


@pytest.mark.parametrize("logs", [None, b"PK\x03\x04frozen zip"])
def test_multipart_encoding_and_private_logging(monkeypatch, report, logs, caplog):
    report = replace(report, logs=logs)
    session = install_response(monkeypatch, response(202, {"ok": True, "receiptId": report.key}))
    with caplog.at_level("INFO", logger=ft.LOG.name):
        assert ft.send_once(report) == ft.Result("success", report.key)
    args, kwargs = session.post.call_args
    assert args == (ft.ENDPOINT,)
    assert kwargs["timeout"] >= 30
    assert kwargs["allow_redirects"] is False
    assert session.trust_env is False
    assert kwargs["headers"] == {"Idempotency-Key": report.key}
    prepared = requests.Request("POST", args[0], files=kwargs["files"], headers=kwargs["headers"]).prepare()
    mime = BytesParser(policy=default).parsebytes(
        ("Content-Type: " + prepared.headers["Content-Type"] + "\r\n\r\n").encode() + prepared.body)
    parts = list(mime.iter_parts())
    by_name = {}
    for part in parts:
        by_name.setdefault(part.get_param("name", header="content-disposition"), []).append(part)
    assert set(by_name) == {"message", "messageHtml", "replyEmail", "appVersion", "attachments"} | ({"logs"} if logs else set())
    assert len(by_name["attachments"]) == 2
    assert by_name["message"][0].get_filename() is None
    assert by_name["message"][0].get_payload(decode=True).decode() == report.message
    assert by_name["messageHtml"][0].get_payload(decode=True).decode() == report.message_html
    assert [part.get_filename() for part in by_name["attachments"]] == [
        "private-note.txt", "image.png",
    ]
    assert [part.get_payload(decode=True) for part in by_name["attachments"]] == [
        b"private attachment one", b"private attachment two",
    ]
    if logs:
        assert by_name["logs"][0].get_payload(decode=True) == logs
    for private in (report.message, report.message_html, report.reply_email,
                    report.key, "private-note.txt"):
        assert private not in caplog.text


@pytest.mark.parametrize("status,body,kind", [
    (202, {"ok": True}, "success"), (200, {"ok": True}, "failed"),
    (202, {"ok": 1}, "retry"), (202, [], "retry"), (202, None, "retry"),
    (409, None, "expired"), (413, None, "oversized"), (422, None, "failed"),
    (302, None, "failed"), (502, None, "retry"), (503, None, "retry"),
])
def test_response_contract(monkeypatch, report, status, body, kind):
    install_response(monkeypatch, response(status, body))
    assert ft.send_once(report).kind == kind


def test_non_json_rate_limit_and_network_error(monkeypatch, report):
    result = response(429, headers={"Retry-After": "75"})
    result.json.side_effect = ValueError("private response")
    session = install_response(monkeypatch, result)
    assert ft.send_once(report) == ft.Result("retry", retry_after=75)
    session.post.side_effect = requests.Timeout("private details")
    assert ft.send_once(report).kind == "retry"


@pytest.mark.parametrize("message,valid", [(" ", False), ("a\0b", False), ("😀" * 2500, True), ("😀" * 2501, False), ("a" * 5000 + " ", False)])
def test_utf16_validation(message, valid):
    assert (ft.validation_error(message, "", "1.2") is None) == valid


def test_formatted_html_utf16_validation():
    assert ft.validation_error("hello", "", "1.2", "😀" * 25_000) is None
    assert ft.validation_error("hello", "", "1.2", "😀" * 25_001)
    assert ft.validation_error("hello", "", "1.2", "<p>bad\0</p>")


@pytest.mark.parametrize(
    "name,expected",
    [
        ("/private/path/report.txt", "report.txt"),
        (r"C:\\private\\path\\report.txt", "report.txt"),
        (" spaced.txt ", "spaced.txt"),
    ],
)
def test_attachment_keeps_only_safe_basename(name, expected):
    attachment = ft.Attachment.create(name, bytearray(b"content"))
    assert attachment.name == expected
    assert attachment.data == b"content"


@pytest.mark.parametrize("name", ["", ".", "..", "bad\nname", "x" * 181])
def test_attachment_rejects_unsafe_filename(name):
    with pytest.raises(ValueError):
        ft.Attachment.create(name, b"content")


def test_attachment_rejects_unsafe_content_type():
    attachment = ft.Attachment.create(
        "report.bin", b"content", "text/plain\r\nX-Private: value",
    )
    assert attachment.content_type == "application/octet-stream"


def test_transport_rejects_bypassed_unsafe_attachment_constructor():
    attachment = ft.Attachment("private/path.txt", b"content", "text/plain\r\nX: value")
    assert ft.attachments_error([attachment]) == "One or more attachments are invalid."


def test_attachment_limits():
    small = ft.Attachment.create("small.bin", b"x")
    large = ft.Attachment.create("large.bin", b"x" * (ft.MAX_ATTACHMENT_BYTES + 1))
    assert ft.attachments_error([small] * (ft.MAX_ATTACHMENT_COUNT + 1))
    assert ft.attachments_error([large]) == "Each attachment must be 5 MB or smaller."
    four_mb = ft.Attachment.create("four.bin", b"x" * (4 * 1024 * 1024))
    assert ft.attachments_error([four_mb, four_mb], b"x") == (
        "Attachments and diagnostic logs must total 8 MB or less."
    )


def test_key_and_validation(report):
    timestamp, token = report.key.split(".", 1)
    assert int(timestamp) > 0
    assert str(uuid.UUID(token, version=4)) == token
    assert ft.validation_error("hello", "Name <reply@example.com>", "1.2")
    assert ft.validation_error("hello", "", "a" * 65)
    with pytest.raises(ValueError):
        ft.Submission.create("", "", "1.2")


class Clock:
    def __init__(self, now):
        self.now = now
        self.delays = []
    def is_set(self):
        return False
    def wait(self, delay):
        self.delays.append(delay)
        self.now += delay
        return False


def test_retries_freeze_report_and_honor_backoff(report):
    report = replace(report, logs=b"ZIP immutable")
    clock = Clock(report.expires_at - 900)
    send = Mock(side_effect=[ft.Result("retry"), ft.Result("retry", retry_after=80), ft.Result("success")])
    assert ft.submit(report, clock, Mock(), send=send, now=lambda: clock.now, jitter=lambda *_: 0).kind == "success"
    assert clock.delays == [5, 80]
    assert all(call.args[0] is report for call in send.call_args_list)
    assert report.attachments[0].data == b"private attachment one"


@pytest.mark.parametrize("result", [ft.Result("expired"), ft.Result("retry", retry_after=901)])
def test_expiration_never_replaces_key(report, result):
    clock = Clock(report.expires_at - 900)
    send = Mock(return_value=result)
    assert ft.submit(report, clock, Mock(), send=send, now=lambda: clock.now).kind == "expired"
    assert send.call_count == 1
    assert clock.delays == []
    clock.now = report.expires_at
    send.reset_mock()
    assert ft.submit(report, clock, Mock(), send=send, now=lambda: clock.now).kind == "expired"
    send.assert_not_called()


def test_disabled_and_oversized_do_not_connect(monkeypatch, report):
    session = Mock()
    monkeypatch.setattr(ft.requests, "Session", session)
    assert ft.send_once(replace(report, logs=b"x" * (ft.MAX_LOG_BYTES + 1))).kind == "oversized"
    oversized = ft.Attachment.create(
        "oversized.bin", b"x" * (ft.MAX_ATTACHMENT_BYTES + 1),
    )
    assert ft.send_once(replace(report, attachments=(oversized,))).kind == "oversized"
    monkeypatch.setattr(ft, "SENDING_ENABLED", False)
    assert ft.send_once(report).kind == "disabled"
    session.assert_not_called()
