"""Shared feedback submission with optional, reviewable diagnostic logs."""

from __future__ import annotations

from dataclasses import replace
from common.oh_no_parent_control_ui.diagnostic_events import get_logger, error_code
import hashlib
from pathlib import Path
import threading

import gi

gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from .diagnostics import collect_logs
from . import feedback_transport as transport
from .rich_text_editor import RichTextEditor
from common.oh_no_parent_control_ui.about import app_version
from common.oh_no_parent_control_ui.accessibility import (
    add_dialog_button,
    add_identified_window_controls,
    describe_control,
    set_automation_id,
)

LOG = get_logger("feedback")
PRIVACY_URL = "https://tech.puffyslippers.com/oh-no-parent-control/privacy/"


def _non_kiosk_automation_id(kiosk_session: bool, identity: str):
    """Do not publish identities for controls unavailable in the kiosk."""
    return None if kiosk_session else identity


def _attachment_automation_key(attachment, existing_keys):
    """Return one stable, non-identifying key that is unique in this dialog."""
    base = hashlib.sha256(
        attachment.name.encode("utf-8") + b"\0" + attachment.data,
    ).hexdigest()[:16]
    key = base
    suffix = 2
    while key in existing_keys:
        key = f"{base}-{suffix}"
        suffix += 1
    return key


def _feedback_icon(name, size, color="#343437"):
    """Use consistent outline artwork regardless of the desktop icon theme."""
    paths = {
        "mail": '<rect x="3" y="5" width="26" height="22" rx="2"/>'
                '<path d="m4 8 12 9L28 8"/>',
        "attachment": '<path d="m12 19 9-9a4 4 0 0 1 6 6L15 28a7 7 0 0 1-10-10L17 6'
                      'a5 5 0 0 1 7 7L12 25a2 2 0 0 1-3-3l11-11"/>',
        "archive": '<rect x="5" y="2" width="23" height="28" rx="3"/>'
                   '<path d="M14 2v5h4v4h-4v4h4v4h-4v7h5v-6M22 20h3m-3 4h3"/>',
        "download": '<path d="M13 3h6v12h4l-7 11-7-11h4ZM6 30h20"/>',
        "trash": '<path d="M4 7h24M12 7V3h8v4M7 7l1 22h16l1-22'
                 'M12 12v12m4-12v12m4-12v12"/>',
        "privacy": '<path d="m16 2 12 5v9c0 7-7 12-12 15C11 28 4 23 4 16V7Z"/>'
                   '<path d="m10 16 4 4 8-9"/>',
    }
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" '
           f'viewBox="0 0 32 32" fill="none" stroke="{color}" stroke-width="2.2" '
           f'stroke-linecap="round" stroke-linejoin="round">{paths[name]}</svg>')
    return Gtk.Image(gicon=Gio.BytesIcon.new(GLib.Bytes.new(svg.encode("utf-8"))),
                     pixel_size=size)


class FeedbackDialog(Adw.Window):
    """Keep drafts and immutable retries in memory for this app session."""

    def __init__(self, parent, *, kiosk_session=False, report=None, on_close=None):
        super().__init__(title="Send Feedback", transient_for=parent, modal=True,
                         destroy_with_parent=True, default_width=660,
                         default_height=840, css_classes=["feedback-dialog"])
        set_automation_id(self, "feedback-dialog")
        self._kiosk_session = kiosk_session
        self._report = report
        self._on_close = on_close
        self._subject = report.subject if report else ""
        self._css_provider = Gtk.CssProvider()
        self._css_provider.load_from_path(str(Path(__file__).with_name("feedback.css")))
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), self._css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1,
        )
        self.connect("destroy", self._destroyed)
        self._busy = False
        self._collecting = False
        self._collection_failed = False
        self._disposed = False
        self._submission = None
        self._logs = None
        self._cancelled = threading.Event()
        self._receipt_id = None
        self._success_dialog = None
        self._user_attachments = []
        self._attachment_rows = []
        self.connect("close-request", self._hide_draft)
        application = parent.get_application()
        if application is not None:
            application.connect("shutdown", lambda *_: self._cancelled.set())
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar(
            title_widget=Adw.WindowTitle(title="Send Feedback"),
            css_classes=["feedback-header"],
        )
        add_identified_window_controls(header, "feedback-window-controls")
        toolbar.add_top_bar(header)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                          margin_start=28, margin_end=28,
                          margin_top=8, margin_bottom=8)
        introduction = Gtk.Box(spacing=18, margin_bottom=8)
        hero_icon = _feedback_icon("mail", 38, "#6740ef")
        hero_icon.set_valign(Gtk.Align.CENTER)
        hero_icon.add_css_class("feedback-icon")
        introduction.append(hero_icon)
        heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4,
                          valign=Gtk.Align.CENTER, hexpand=True)
        heading.append(Gtk.Label(label="Help us make things better", xalign=0,
                                 wrap=True, css_classes=["feedback-title"]))
        heading.append(Gtk.Label(
            label=("Review the error details below before sending."
                   if report else "Share a problem, suggestion, or idea."),
            xalign=0, wrap=True, css_classes=["feedback-subtitle"],
        ))
        introduction.append(heading)
        content.append(introduction)

        message_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                                vexpand=True, margin_bottom=2)
        message = RichTextEditor(None if kiosk_session else self._choose_attachments)
        set_automation_id(message, "feedback-editor-container")
        self._message = message
        if report:
            message.set_text(report.message)
        message_group.append(message)
        content.append(message_group)

        reply_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                              css_classes=["feedback-reply"])
        reply = Gtk.Entry(placeholder_text="you@example.com", hexpand=True,
                          has_frame=False)
        reply_header = Gtk.Box(spacing=12)
        reply_header.append(Gtk.Label(
            label="Reply email (optional)", xalign=0, hexpand=True,
            mnemonic_widget=reply, css_classes=["feedback-section-title"],
        ))
        anonymous = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER,
                            css_classes=["feedback-anonymous-badge"])
        anonymous.append(_feedback_icon("privacy", 18, "#8866ff"))
        anonymous.append(Gtk.Label(label="Anonymous by default"))
        reply_header.append(anonymous)
        reply_group.append(reply_header)
        reply_field = Gtk.Box(spacing=16, css_classes=["feedback-reply-field"])
        reply_field.append(_feedback_icon("mail", 20))
        reply_field.append(reply)
        self._reply = reply
        reply.set_input_purpose(Gtk.InputPurpose.EMAIL)
        describe_control(reply, "Reply email (optional)",
                         "Add your email address if you would like a reply.",
                         automation_id="feedback-reply-email")
        reply_group.append(reply_field)
        reply_group.append(Gtk.Label(
            label="Add your email if you’d like a reply. Otherwise, your feedback is anonymous.",
            xalign=0, wrap=True, css_classes=["feedback-reply-hint"],
        ))
        content.append(reply_group)

        attachments = Adw.PreferencesGroup(title="Attachments (optional)",
                                           css_classes=["feedback-attachments"])
        self._attachments_group = attachments
        self._collection_row = Adw.ActionRow(
            title="Collecting diagnostic information...", visible=False,
        )
        set_automation_id(self._collection_row, "feedback-collection-status")
        # Adw.Spinner keeps essential progress moving when desktop animations
        # are disabled. Mapping the collection row controls its lifecycle.
        self._collection_spinner = Adw.Spinner(
            valign=Gtk.Align.CENTER, width_request=24, height_request=24,
            css_classes=["feedback-collection-spinner"],
        )
        self._collection_row.add_prefix(self._collection_spinner)
        attachments.add(self._collection_row)
        self._add_attachment_button = Gtk.Button(
            valign=Gtk.Align.CENTER, css_classes=["feedback-add-files"],
        )
        add_files_content = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        add_files_content.append(_feedback_icon("attachment", 20))
        add_files_content.append(Gtk.Label(label="Add files"))
        self._add_attachment_button.set_child(add_files_content)
        describe_control(self._add_attachment_button, "Add files",
                         "Attach up to 5 files to your feedback.",
                         automation_id=_non_kiosk_automation_id(
                             kiosk_session, "feedback-add-files"))
        self._add_attachment_button.connect("clicked", self._choose_attachments)
        attachments.set_header_suffix(self._add_attachment_button)
        self._add_attachment_button.set_visible(not kiosk_session)
        self._attachment = Adw.ActionRow(
            title="diagnostic-logs.zip",
            subtitle="Latest 3 log dates · ZIP archive",
        )
        set_automation_id(self._attachment, "feedback-logs-row")
        self._attachment.add_prefix(_feedback_icon("archive", 26))
        self._attachment_button = Gtk.Button(
            child=_feedback_icon("trash", 22, "#7650ff"), tooltip_text="Remove logs",
            valign=Gtk.Align.CENTER,
            css_classes=["flat", "feedback-attachment-button"],
        )
        self._include_logs = True
        self._attachment_button.connect("clicked", self._toggle_attachment)
        attachment_actions = Gtk.Box(spacing=4, valign=Gtk.Align.CENTER)
        self._retry_logs = Gtk.Button(label="Retry collection", visible=False,
                                     valign=Gtk.Align.CENTER)
        describe_control(
            self._retry_logs, "Retry diagnostic collection",
            "Try collecting the diagnostic attachment again.",
            automation_id="feedback-retry-logs",
        )
        self._retry_logs.connect("clicked", self._start_collection)
        attachment_actions.append(self._retry_logs)
        self._download_button = Gtk.Button(
            child=_feedback_icon("download", 22, "#7650ff"),
            css_classes=["flat", "feedback-attachment-button"],
            tooltip_text="Save compressed logs to examine them before sending",
        )
        describe_control(self._download_button, "Download",
                         "Save a ZIP containing a readable diagnostic report and validated technical events.",
                         automation_id=_non_kiosk_automation_id(
                             kiosk_session, "feedback-download-logs"))
        self._download_button.connect("clicked", self._download_logs)
        self._download_button.set_visible(not kiosk_session)
        attachment_actions.append(self._download_button)
        attachment_actions.append(self._attachment_button)
        self._attachment.add_suffix(attachment_actions)
        self._update_attachment_accessibility()
        attachments.add(self._attachment)
        content.append(attachments)

        footer = Gtk.Box(spacing=16, margin_top=14, margin_bottom=28,
                         margin_start=28, margin_end=28, valign=Gtk.Align.END)
        privacy_notice = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=6,
            hexpand=True, valign=Gtk.Align.CENTER,
        )
        privacy_link = Gtk.LinkButton(
            uri=PRIVACY_URL, halign=Gtk.Align.START,
            css_classes=["feedback-privacy-link"],
        )
        privacy_content = Gtk.Box(spacing=6)
        privacy_content.append(_feedback_icon("privacy", 18, "#7650ff"))
        privacy_content.append(Gtk.Label(label="Privacy", use_underline=False))
        privacy_link.set_child(privacy_content)
        describe_control(
            privacy_link,
            "Privacy",
            "Show privacy information about feedback and attachments.",
            automation_id="feedback-privacy-link",
        )
        privacy_link.connect("activate-link", self._show_log_privacy)
        privacy_notice.append(privacy_link)
        footer.append(privacy_notice)
        self._status = Gtk.Label(
            xalign=0, wrap=True, selectable=True, visible=False,
        )
        set_automation_id(self._status, "feedback-status")
        self._status.connect(
            "notify::label",
            lambda label, _property: label.set_visible(bool(label.get_label())),
        )
        content.append(self._status)
        self._without_logs = Gtk.Button(label="Send without logs", visible=False)
        describe_control(
            self._without_logs, "Send without logs",
            "Send the feedback without the diagnostic attachment.",
            automation_id="feedback-send-without-logs",
        )
        self._without_logs.connect("clicked", self._send_without_logs)
        content.append(self._without_logs)
        actions = Gtk.Box(spacing=10, halign=Gtk.Align.END, valign=Gtk.Align.CENTER)
        cancel = Gtk.Button(label="Close", css_classes=["feedback-close"])
        describe_control(
            cancel, "Close",
            "Close the feedback form while preserving the draft in this app.",
            automation_id="feedback-close",
        )
        self._close_button = cancel
        cancel.connect("clicked", lambda *_: self.close())
        actions.append(cancel)
        self._send_button = Gtk.Button(
            label="Send Feedback", sensitive=transport.SENDING_ENABLED,
            css_classes=["suggested-action", "feedback-send"],
        )
        describe_control(
            self._send_button, "Send Feedback",
            "Submit the feedback and selected attachments.",
            automation_id="feedback-send",
        )
        self._send_button.connect("clicked", self._send)
        actions.append(self._send_button)
        footer.append(actions)
        # Extra attachments and status messages may outgrow a short display.
        # Let the form scroll while keeping Close and Send always available.
        content_scroll = Gtk.ScrolledWindow(
            child=content, hscrollbar_policy=Gtk.PolicyType.NEVER,
            propagate_natural_height=True, vexpand=True, focusable=True,
        )
        set_automation_id(content_scroll, "feedback-content")
        toolbar.set_content(content_scroll)
        toolbar.add_bottom_bar(footer)
        self.set_content(toolbar)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._key_pressed)
        self.add_controller(keys)
        self.connect("notify::visible", self._visibility_changed)
        message.grab_editor_focus()

    def _visibility_changed(self, *_args):
        if self.get_visible() and not self._busy and self._include_logs:
            self._start_collection()

    def _start_collection(self, *_args):
        if self._disposed or self._busy or self._collecting or not self._include_logs:
            return
        self._collecting = True
        self._collection_failed = False
        self._logs = None
        self._without_logs.set_visible(False)
        self._retry_logs.set_visible(False)
        self._attachment.set_visible(False)
        self._collection_row.set_visible(True)
        self._set_busy(self._busy)
        LOG.info("feedback.collection-started")

        def collect():
            try:
                data = collect_logs()
            except Exception as error:
                # The worker must always resolve the pending UI state. Neither
                # the log nor the user-facing failure includes exception text.
                LOG.warning("feedback.collection-failed", error_type=error_code(error))
                GLib.idle_add(self._collection_done, None)
            else:
                GLib.idle_add(self._collection_done, data)

        try:
            threading.Thread(target=collect, daemon=True).start()
        except Exception as error:
            LOG.warning("feedback.collection-failed", error_type=error_code(error))
            self._collection_done(None)

    def _collection_done(self, data):
        if self._disposed:
            return GLib.SOURCE_REMOVE
        self._collecting = False
        self._logs = data
        self._collection_failed = data is None
        self._collection_row.set_visible(False)
        self._attachment.set_visible(True)
        self._render_attachment()
        self._set_busy(self._busy)
        if data is None:
            self._status.set_label(
                "Logs could not be prepared. You can send this feedback without the attachment.",
            )
        else:
            self._status.set_label("")
            LOG.info("feedback.collection-ready", bytes=len(data))
        return GLib.SOURCE_REMOVE

    def _show_log_privacy(self, *_args):
        privacy_text = (
            transport.RETENTION_DISCLOSURE + "\n\nDiagnostic logs do not collect "
            "account names, email addresses, file contents, raw system journals, or "
            "exception messages. Automatic diagnostics contain validated technical "
            "events, health checks, and system information: OS and dependency versions, "
            "timezone, session type, and aggregate account counts. Names and custom "
            "version text are omitted or irreversibly replaced; identities are never hashed. "
            "Your own feedback, reply email, and selected "
            "files are separate and may contain personal information. Review them "
            "before sending."
        )
        dialog = Gtk.Dialog(
            title="Feedback privacy", transient_for=self, modal=True,
        )
        set_automation_id(dialog, "feedback-privacy-dialog")
        header = Gtk.HeaderBar()
        add_identified_window_controls(header, "feedback-privacy-window-controls")
        dialog.set_titlebar(header)
        privacy_content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12,
            margin_top=18, margin_bottom=18, margin_start=18, margin_end=18,
        )
        privacy_body = Gtk.Label(label=privacy_text, wrap=True, xalign=0)
        set_automation_id(privacy_body, "feedback-privacy-text")
        privacy_content.append(privacy_body)
        portal_link = Gtk.LinkButton(
            uri=PRIVACY_URL,
            label="View full privacy notice",
            halign=Gtk.Align.CENTER,
        )
        describe_control(
            portal_link,
            "View full privacy notice",
            "Open the Oh No! Parent Control privacy notice in your browser.",
            automation_id=_non_kiosk_automation_id(
                self._kiosk_session, "feedback-full-privacy-link"),
        )
        privacy_content.append(portal_link)
        dialog.get_content_area().append(privacy_content)
        portal_link.set_visible(not self._kiosk_session)
        add_dialog_button(
            dialog, "Close", Gtk.ResponseType.CLOSE, "feedback-privacy-close",
            description="Close the feedback privacy information.",
        )
        dialog.set_default_response(Gtk.ResponseType.CLOSE)
        dialog.connect("response", lambda current, _response: current.destroy())
        dialog.present()
        return True

    def _hide_draft(self, *_args):
        self._clear_success_dialog()
        if self._busy and self._on_close is not None:
            # The button explicitly says Stop sending and close in this state.
            self._cancelled.set()
        # Closing the dialog keeps the draft and any pending retry in this app.
        self.set_visible(False)
        if self._on_close is not None:
            callback, self._on_close = self._on_close, None
            callback()
        return True

    def _destroyed(self, *_args):
        self._disposed = True
        self._clear_success_dialog()
        self._cancelled.set()
        Gtk.StyleContext.remove_provider_for_display(self.get_display(), self._css_provider)

    def _set_busy(self, busy):
        self._busy = busy
        close_label = (
            "Stop sending and close"
            if busy and self._on_close is not None else "Close"
        )
        self._close_button.set_label(close_label)
        describe_control(
            self._close_button, close_label,
            "Stop the pending report and close it."
            if busy and self._on_close is not None
            else "Close the feedback form while preserving the draft in this app.",
        )
        for widget in (self._message, self._reply, *self._attachment_rows):
            widget.set_sensitive(not busy)
        for widget in (self._attachment_button, self._download_button,
                       self._add_attachment_button, self._without_logs, self._retry_logs):
            widget.set_sensitive(not busy and not self._collecting)
        self._send_button.set_sensitive(
            not busy and not self._collecting and transport.SENDING_ENABLED
            and (not self._include_logs or self._logs is not None),
        )

    def _send(self, _button):
        if (self._busy or self._collecting or not transport.SENDING_ENABLED
                or (self._include_logs and self._logs is None)):
            return
        message = self._message.plain_text
        message_html = self._message.html
        reply = self._reply.get_text().strip()
        version = app_version()
        error = transport.validation_error(message, reply, version, message_html)
        error = error or transport.attachments_error(self._user_attachments)
        if error:
            self._status.set_label(error)
            return
        # A new key is generated only in response to this explicit Send action.
        self._submission = transport.Submission.create(
            message, reply, version, message_html, self._user_attachments,
            subject=self._subject,
        )
        self._without_logs.set_visible(False)
        self._set_busy(True)
        self._send_button.set_label("Send Feedback")
        describe_control(
            self._send_button, "Send Feedback",
            "Submit the feedback and selected attachments.",
        )
        self._status.set_label("Preparing feedback… " + self._sending_hint())
        include_logs = self._include_logs
        submission = self._submission
        cached_logs = self._logs
        def work():
            logs = cached_logs
            frozen = replace(submission, logs=logs if include_logs else None)
            GLib.idle_add(self._submission_progress,
                          "Sending feedback… " + self._sending_hint())
            result = transport.submit(
                frozen, self._cancelled,
                lambda text: GLib.idle_add(self._submission_progress, text),
            )
            GLib.idle_add(self._submission_done, result, frozen)

        threading.Thread(target=work, daemon=True).start()

    def _sending_hint(self):
        if self._on_close is not None:
            return "You can stop sending and close this report."
        return "You may close this dialog; retries continue while the app is open."

    def _submission_progress(self, text):
        self._status.set_label(text)
        return GLib.SOURCE_REMOVE

    def _submission_done(self, result, submission):
        self._submission = submission
        if submission.logs is not None:
            self._logs = submission.logs
        self._set_busy(False)
        LOG.info("feedback.002", outcome=result.kind)
        messages = {
            "success": "Feedback submitted.",
            "expired": "This submission can no longer be retried within its retry window. The previous attempt may have succeeded. Sending again may submit a duplicate.",
            "oversized": "The attachments are too large. Remove files or logs and try again.",
            "logs_unavailable": "Logs could not be prepared. You can send this feedback without the attachment.",
            "failed": "Feedback was not accepted. Your draft is preserved. Check your feedback and reply address before sending again.",
            "cancelled": "Submission stopped. Your draft is preserved. The previous attempt may have succeeded.",
            "disabled": "Sending is not available yet. Your draft is preserved.",
        }
        self._status.set_label(messages[result.kind])
        self._without_logs.set_visible(result.kind in ("oversized", "logs_unavailable") and self._include_logs)
        if result.kind in ("expired", "cancelled"):
            self._send_button.set_label("Submit again (may duplicate)")
            describe_control(
                self._send_button, "Submit again (may duplicate)",
                "Submit the preserved feedback again when the earlier result is uncertain.",
            )
        if result.kind == "success":
            self._receipt_id = result.receipt_id
            self._message.clear()
            self._reply.set_text("")
            self._clear_user_attachments()
            self._submission = None
            self._logs = None
            if self.get_visible():
                self._show_success_dialog(has_reply_email=bool(submission.reply_email))
        return GLib.SOURCE_REMOVE

    def _show_success_dialog(self, *, has_reply_email):
        self._clear_success_dialog()
        body = (
            "Your feedback was sent successfully. We appreciate your help making "
            "the app better."
        )
        if has_reply_email:
            body += (
                "\n\nWe may contact you at the email address you provided "
                "if we have any follow-up questions."
            )
        dialog = Gtk.Dialog(
            title="Thank you for your feedback!",
            transient_for=self.get_transient_for(), modal=True,
        )
        set_automation_id(dialog, "feedback-success-dialog")
        header = Gtk.HeaderBar()
        add_identified_window_controls(header, "feedback-success-window-controls")
        dialog.set_titlebar(header)
        body_label = Gtk.Label(
            label=body, wrap=True, xalign=0,
            margin_top=18, margin_bottom=18, margin_start=18, margin_end=18,
        )
        set_automation_id(body_label, "feedback-success-text")
        dialog.get_content_area().append(body_label)
        self._success_dialog = dialog
        add_dialog_button(
            dialog, "Close", Gtk.ResponseType.CLOSE, "feedback-success-close",
            description="Close the feedback confirmation.",
            css_class="suggested-action",
        )
        dialog.set_default_response(Gtk.ResponseType.CLOSE)
        dialog.connect("response", self._success_closed)
        # Hide the editor immediately, but defer error-report exit callbacks
        # until the user has dismissed the confirmation on the owning window.
        self.set_visible(False)
        dialog.present()

    def _success_closed(self, dialog, _response):
        if self._success_dialog is dialog:
            self._success_dialog = None
            dialog.destroy()
            self.close()

    def _clear_success_dialog(self):
        if self._success_dialog is not None:
            dialog, self._success_dialog = self._success_dialog, None
            dialog.destroy()

    def _send_without_logs(self, _button):
        if self._include_logs:
            self._toggle_attachment(None)
        self._send(None)

    def _toggle_attachment(self, _button):
        if self._busy or self._collecting:
            return
        self._include_logs = not self._include_logs
        self._render_attachment()
        self._set_busy(self._busy)
        if self._include_logs and self._logs is None:
            self._start_collection()

    def _render_attachment(self):
        failed = self._include_logs and self._collection_failed
        self._attachment.set_title(
            "Diagnostics unavailable" if failed else
            "diagnostic-logs.zip" if self._include_logs else "No logs attached",
        )
        self._attachment.set_subtitle(
            "Retry collection or send without diagnostics." if failed else
            "Latest 3 log dates · System information · ZIP archive"
            if self._include_logs else "Your feedback can be sent without logs.",
        )
        if self._include_logs:
            self._attachment_button.set_child(_feedback_icon("trash", 22, "#7650ff"))
        else:
            self._attachment_button.set_label("Add logs")
        self._attachment_button.set_tooltip_text("Remove logs" if self._include_logs else "Add logs")
        self._download_button.set_visible(self._include_logs and not failed and not self._kiosk_session)
        self._retry_logs.set_visible(failed)
        self._without_logs.set_visible(failed)
        self._update_attachment_accessibility()

    def _update_attachment_accessibility(self):
        describe_control(
            self._attachment_button,
            "Remove" if self._include_logs else "Add logs",
            "Include a diagnostic report with validated technical events and health checks. Personal information is excluded from this report.",
            automation_id="feedback-toggle-logs",
        )

    def _choose_attachments(self, _button=None):
        if self._busy or self._collecting or self._kiosk_session:
            return
        chooser = Gtk.FileDialog(title="Add feedback attachments")
        chooser.open_multiple(self, None, self._attachments_selected)

    def _attachments_selected(self, chooser, result):
        try:
            selected = chooser.open_multiple_finish(result)
        except GLib.Error as error:
            if not error.matches(Gtk.dialog_error_quark(), Gtk.DialogError.DISMISSED):
                LOG.warning("feedback.003", error_type=error_code(error))
                self._status.set_label("Could not choose attachments. Try again.")
            return
        files = [selected.get_item(index) for index in range(selected.get_n_items())]
        if not files:
            return
        if len(self._user_attachments) + len(files) > transport.MAX_ATTACHMENT_COUNT:
            self._status.set_label(
                f"Attach at most {transport.MAX_ATTACHMENT_COUNT} files.",
            )
            return
        self._set_busy(True)
        self._status.set_label("Reading attachments…")
        LOG.info("feedback.004", file_count=len(files))

        def load():
            loaded = []
            try:
                for selected_file in files:
                    info = selected_file.query_info(
                        "standard::display-name,standard::content-type,standard::size",
                        Gio.FileQueryInfoFlags.NONE, None,
                    )
                    if info.get_size() > transport.MAX_ATTACHMENT_BYTES:
                        raise ValueError("Each attachment must be 5 MB or smaller.")
                    content, _etag = selected_file.load_bytes(None)
                    content_type = info.get_content_type()
                    loaded.append(transport.Attachment.create(
                        info.get_display_name(), bytes(content.get_data()),
                        Gio.content_type_get_mime_type(content_type)
                        if content_type else None,
                    ))
                error = transport.attachments_error(
                    [*self._user_attachments, *loaded], self._logs,
                )
                if error:
                    raise ValueError(error)
            except ValueError as error:
                GLib.idle_add(self._attachments_loaded, None, str(error))
            except (GLib.Error, OSError) as error:
                LOG.warning("feedback.005", error_type=error_code(error))
                GLib.idle_add(
                    self._attachments_loaded, None,
                    "Could not read one or more attachments. Try different files.",
                )
            else:
                GLib.idle_add(self._attachments_loaded, loaded, None)

        threading.Thread(target=load, daemon=True).start()

    def _attachments_loaded(self, attachments, error):
        self._set_busy(False)
        if error:
            LOG.warning("feedback.006")
            self._status.set_label(error)
            return GLib.SOURCE_REMOVE
        for attachment in attachments:
            self._user_attachments.append(attachment)
            attachment_key = _attachment_automation_key(
                attachment,
                {row.automation_key for row in self._attachment_rows},
            )
            row = Adw.ActionRow(
                title=attachment.name,
                subtitle=self._format_size(len(attachment.data)),
            )
            row.automation_key = attachment_key
            set_automation_id(row, f"feedback-attachment-{attachment_key}")
            row.add_prefix(Gtk.Image(icon_name="mail-attachment-symbolic"))
            remove = Gtk.Button(
                icon_name="user-trash-symbolic", tooltip_text="Remove attachment",
                valign=Gtk.Align.CENTER,
                css_classes=["flat", "feedback-attachment-button"],
            )
            describe_control(
                remove, f"Remove {attachment.name}",
                "Remove this file from the feedback.",
                automation_id=f"feedback-remove-attachment-{attachment_key}",
            )
            remove.connect("clicked", self._remove_user_attachment, attachment, row)
            row.add_suffix(remove)
            self._attachment_rows.append(row)
            self._attachments_group.add(row)
        LOG.info(
            "feedback.007",
            added_count=len(attachments),
            total_count=len(self._user_attachments),
        )
        self._status.set_label(
            f"{len(self._user_attachments)} file attachment"
            f"{'s' if len(self._user_attachments) != 1 else ''} ready.",
        )
        return GLib.SOURCE_REMOVE

    def _remove_user_attachment(self, _button, attachment, row):
        self._user_attachments.remove(attachment)
        self._attachment_rows.remove(row)
        self._attachments_group.remove(row)
        LOG.info("feedback.008", remaining_count=len(self._user_attachments))

    def _clear_user_attachments(self):
        for row in self._attachment_rows:
            self._attachments_group.remove(row)
        self._attachment_rows.clear()
        self._user_attachments.clear()

    @staticmethod
    def _format_size(size):
        if size < 1024:
            return f"{size} bytes"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    def _download_logs(self, _button):
        if self._busy or self._collecting or self._kiosk_session or self._logs is None:
            return
        self._set_busy(True)
        LOG.info("feedback.009")
        self._choose_download(self._logs)

    def _choose_download(self, data):
        self._logs = data
        if not self.get_visible():
            self._download_done("Logs ready to review")
            return GLib.SOURCE_REMOVE
        chooser = Gtk.FileDialog(title="Download diagnostic logs",
                                 initial_name="diagnostic-logs.zip")
        chooser.save(self, None, self._download_selected, data)
        return GLib.SOURCE_REMOVE

    def _download_selected(self, chooser, result, data):
        try:
            destination = chooser.save_finish(result)
        except GLib.Error as error:
            if error.matches(Gtk.dialog_error_quark(), Gtk.DialogError.DISMISSED):
                self._download_done("Latest 3 log dates · ZIP archive")
            else:
                LOG.warning("feedback.011", error_type=error_code(error))
                self._download_done("Could not choose a download location. Try again.")
            return
        destination.replace_contents_bytes_async(
            GLib.Bytes.new(data), None, False,
            Gio.FileCreateFlags.PRIVATE | Gio.FileCreateFlags.REPLACE_DESTINATION,
            None, self._download_saved,
        )

    def _download_saved(self, destination, result):
        try:
            destination.replace_contents_finish(result)
        except GLib.Error as error:
            LOG.warning("feedback.012", error_type=error_code(error))
            self._download_done("Could not save logs. Try another location.")
        else:
            LOG.info("feedback.013")
            self._download_done("Downloaded · Ready to examine")

    def _download_done(self, subtitle):
        self._set_busy(False)
        self._attachment.set_subtitle(subtitle)
        return GLib.SOURCE_REMOVE

    def _key_pressed(self, _controller, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False
