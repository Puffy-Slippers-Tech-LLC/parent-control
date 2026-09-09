"""Immutable feedback submissions and bounded retries; no persistent queue."""

from dataclasses import dataclass
from html import escape
import logging
import mimetypes
import random
import re
import time
import unicodedata
import uuid

import requests

LOG = logging.getLogger("oh-no-parent-control-parent")
ENDPOINT = "https://tech.puffyslippers.com/api/oh-no-parent-control/feedback"
# Production activation authorized after backend deployment.
SENDING_ENABLED = True
RETENTION_DISCLOSURE = (
    "Feedback, reply email addresses, attachments, and diagnostic logs are emailed "
    "to support. Retention depends on our support mailbox and service providers, "
    "including their backup policies. We do not currently guarantee deletion "
    "within a fixed period."
)
MAX_LOG_BYTES = 2_097_152
MAX_MESSAGE_UTF16 = 5_000
MAX_ATTACHMENT_COUNT = 5
MAX_ATTACHMENT_BYTES = 5_242_880
MAX_TOTAL_ATTACHMENT_BYTES = 8_388_608
MAX_HTML_UTF16 = 50_000
RETRY_WINDOW = 15 * 60
TIMEOUT = 30
DEFAULT_TITLE = "[Oh No! Parent Control] App feedback"
MAX_TITLE_UTF16 = 200


def title_error(title):
    if (not isinstance(title, str) or not title.strip()
            or len(title.encode("utf-16-le", errors="surrogatepass")) // 2 > MAX_TITLE_UTF16
            or re.search(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]", title)):
        return "Enter a single-line feedback title of at most 200 characters."
    return None


def validation_error(message, reply_email, version, message_html=""):
    if not message.strip() or "\0" in message:
        return "Enter feedback without NUL characters."
    if len(message.encode("utf-16-le", errors="surrogatepass")) // 2 > MAX_MESSAGE_UTF16:
        return "Feedback must be at most 5,000 UTF-16 characters (some emoji count as two)."
    if "\0" in message_html or len(message_html.encode("utf-16-le", errors="surrogatepass")) // 2 > MAX_HTML_UTF16:
        return "The formatted feedback is too complex. Remove some formatting and try again."
    if reply_email and ("\0" in reply_email or len(reply_email) > 254 or not re.fullmatch(r"[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+", reply_email)):
        return "Enter a bare reply email address, or leave it blank."
    if len(version) > 64 or any(c in version for c in "\r\n\0"):
        return "The app version is invalid. Please update the application."
    return None


@dataclass(frozen=True)
class Attachment:
    """One immutable, in-memory user attachment; local paths are never retained."""

    name: str
    data: bytes
    content_type: str = "application/octet-stream"

    @classmethod
    def create(cls, name, data, content_type=None):
        if not isinstance(name, str):
            raise ValueError("Choose an attachment with a valid filename.")
        # File.name is normally already a basename. Normalize both path
        # separators defensively so a path can never leave the client.
        safe_name = name.replace("\\", "/").rsplit("/", 1)[-1].strip()
        has_control = any(unicodedata.category(char).startswith("C")
                          for char in safe_name)
        if (not safe_name or safe_name in (".", "..") or has_control
                or len(safe_name) > 180):
            raise ValueError("Choose an attachment with a shorter valid filename.")
        if not isinstance(data, bytes):
            data = bytes(data)
        guessed = mimetypes.guess_type(safe_name)[0]
        mime_type = content_type or guessed or "application/octet-stream"
        if not isinstance(mime_type, str) or not re.fullmatch(
                r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+", mime_type):
            mime_type = "application/octet-stream"
        return cls(safe_name, data, mime_type)


def attachments_error(attachments, logs=None):
    if len(attachments) > MAX_ATTACHMENT_COUNT:
        return f"Attach at most {MAX_ATTACHMENT_COUNT} files."
    if any(not isinstance(item, Attachment) for item in attachments):
        return "One or more attachments are invalid."
    for item in attachments:
        invalid_name = (
            not isinstance(item.name, str) or not item.name or item.name in (".", "..")
            or "/" in item.name or "\\" in item.name or len(item.name) > 180
            or any(unicodedata.category(char).startswith("C") for char in item.name)
        )
        invalid_type = not isinstance(item.content_type, str) or not re.fullmatch(
            r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+", item.content_type,
        )
        if invalid_name or invalid_type or not isinstance(item.data, bytes):
            return "One or more attachments are invalid."
    if any(len(item.data) > MAX_ATTACHMENT_BYTES for item in attachments):
        return "Each attachment must be 5 MB or smaller."
    total = sum(len(item.data) for item in attachments) + (len(logs) if logs else 0)
    if total > MAX_TOTAL_ATTACHMENT_BYTES:
        return "Attachments and diagnostic logs must total 8 MB or less."
    return None


@dataclass(frozen=True)
class Submission:
    key: str
    message: str
    reply_email: str
    version: str
    message_html: str = ""
    attachments: tuple[Attachment, ...] = ()
    logs: bytes | None = None
    subject: str = ""

    @classmethod
    def create(cls, message, reply_email, version, message_html="", attachments=(), *, subject=""):
        attachments = tuple(attachments)
        error = validation_error(message, reply_email, version, message_html)
        error = error or attachments_error(attachments)
        error = error or title_error(subject or DEFAULT_TITLE)
        if error:
            raise ValueError(error)
        return cls(f"{int(time.time())}.{uuid.uuid4()}", message, reply_email, version,
                   message_html, attachments, subject=subject)

    @property
    def expires_at(self):
        return int(self.key.split(".", 1)[0]) + RETRY_WINDOW

    @property
    def title(self):
        return self.subject or DEFAULT_TITLE

    def email_bodies(self):
        """Compose product-specific metadata here; the portal adds no content."""
        metadata = (
            f"Receipt: {self.key}",
            f"App version: {self.version or 'not provided'}",
            f"Reply email: {self.reply_email or 'not provided'}",
            f"Attachments: {len(self.attachments)}",
            f"Logs attached: {'yes' if self.logs is not None else 'no'}",
        )
        body = "Oh No! Parent Control feedback\n\n" + "\n".join(metadata) + "\n\n" + self.message
        body_html = (
            "<h1>Oh No! Parent Control feedback</h1><p>"
            + "<br>".join(escape(line) for line in metadata)
            + "</p>" + self.message_html
            if self.message_html else ""
        )
        return body, body_html


@dataclass(frozen=True)
class Result:
    kind: str
    receipt_id: str | None = None
    retry_after: int = 0


def send_once(submission):
    """Use the library's multipart encoder even when there is no attachment."""
    if not SENDING_ENABLED:
        return Result("disabled")
    if submission.logs is not None and len(submission.logs) > MAX_LOG_BYTES:
        return Result("oversized")
    if attachments_error(submission.attachments, submission.logs):
        return Result("oversized")
    if title_error(submission.title):
        return Result("failed")
    body, body_html = submission.email_bodies()
    parts = [("title", (None, submission.title)), ("body", (None, body))]
    if body_html:
        parts.append(("bodyHtml", (None, body_html)))
    if submission.reply_email:
        parts.append(("replyTo", (None, submission.reply_email)))
    for attachment in submission.attachments:
        parts.append(("attachments", (attachment.name, attachment.data,
                                      attachment.content_type)))
    if submission.logs is not None:
        parts.append(("attachments", ("oh-no-parent-control-logs.zip", submission.logs,
                               "application/zip")))
    try:
        with requests.Session() as session:
            # No ambient .netrc credentials; send only to the canonical endpoint.
            session.trust_env = False
            with session.post(ENDPOINT, files=parts,
                              headers={"Idempotency-Key": submission.key},
                              timeout=TIMEOUT, allow_redirects=False) as response:
                status = response.status_code
                LOG.info("feedback response status=%d", status)
                try:
                    body = response.json()
                except ValueError:
                    body = None
                if status == 202 and isinstance(body, dict) and body.get("ok") is True:
                    receipt = body.get("receiptId")
                    return Result("success", receipt if isinstance(receipt, str) else None)
                if status == 409:
                    return Result("expired")
                if status == 413:
                    return Result("oversized")
                if status == 429:
                    value = response.headers.get("Retry-After", "")
                    # Contract specifies seconds; bound parsing without shortening a valid wait.
                    delay = min(int(value), RETRY_WINDOW) if re.fullmatch(r"[0-9]{1,9}", value) else (0 if not value else RETRY_WINDOW)
                    return Result("retry", retry_after=delay)
                if status >= 500 or status in (202, 408):
                    return Result("retry")
                return Result("failed")
    except requests.RequestException as error:
        LOG.warning("feedback network failure error_type=%s", type(error).__name__)
        return Result("retry")


def submit(submission, cancelled, progress, *, send=send_once, now=time.time, jitter=random.uniform):
    """Worker-thread retry loop. Always reuse the frozen report and token."""
    attempt = 0
    while not cancelled.is_set():
        if now() >= submission.expires_at:
            return Result("expired")
        attempt += 1
        LOG.info("feedback attempt started attempt=%d diagnostic_logs=%s attachment_count=%d",
                 attempt, submission.logs is not None, len(submission.attachments))
        result = send(submission)
        if result.kind != "retry":
            return result
        delay = max((5, 15, 60)[min(attempt - 1, 2)] + jitter(0, 3), result.retry_after)
        remaining = submission.expires_at - now()
        if delay >= remaining:
            return Result("expired")
        LOG.info("feedback retry scheduled attempt=%d delay_seconds=%d", attempt, delay)
        progress(f"Could not confirm submission. Retrying in {int(delay) + 1} seconds…")
        if cancelled.wait(delay):
            break
    return Result("cancelled")
