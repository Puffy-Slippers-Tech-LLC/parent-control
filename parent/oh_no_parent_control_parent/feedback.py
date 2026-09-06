"""Parent feedback submission with optional, reviewable diagnostic logs."""

from __future__ import annotations

from dataclasses import replace
import logging
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
from common.oh_no_parent_control_ui.accessibility import describe_control

LOG = logging.getLogger("oh-no-parent-control-parent")
PRIVACY_URL = "https://tech.puffyslippers.com/oh-no-parent-control/privacy/"


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
    """Keep drafts and immutable retries in memory for this parent-app session."""

    def __init__(self, parent):
        super().__init__(title="Send Feedback", transient_for=parent, modal=True,
                         destroy_with_parent=True, default_width=660,
                         default_height=840, css_classes=["feedback-dialog"])
        self._busy = False
        self._submission = None
        self._logs = None
        self._cancelled = threading.Event()
        self._receipt_id = None
        self._user_attachments = []
        self._attachment_rows = []
        self.connect("close-request", self._hide_draft)
        application = parent.get_application()
        if application is not None:
            application.connect("shutdown", lambda *_: self._cancelled.set())
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar(
            title_widget=Adw.WindowTitle(title="Send Feedback"),
            css_classes=["feedback-header"],
        ))
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                          margin_start=28, margin_end=28,
                          margin_top=8, margin_bottom=28)
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
            label="Share a problem, suggestion, or idea.",
            xalign=0, wrap=True, css_classes=["feedback-subtitle"],
        ))
        introduction.append(heading)
        content.append(introduction)

        message_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                                vexpand=True, margin_bottom=2)
        message = RichTextEditor(self._choose_attachments)
        self._message = message
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
                         "Add your email address if you would like a reply.")
        reply_group.append(reply_field)
        reply_group.append(Gtk.Label(
            label="Add your email if you’d like a reply. Otherwise, your feedback is anonymous.",
            xalign=0, wrap=True, css_classes=["feedback-reply-hint"],
        ))
        content.append(reply_group)

        attachments = Adw.PreferencesGroup(title="Attachments (optional)",
                                           css_classes=["feedback-attachments"])
        self._attachments_group = attachments
        self._add_attachment_button = Gtk.Button(
            valign=Gtk.Align.CENTER, css_classes=["feedback-add-files"],
        )
        add_files_content = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        add_files_content.append(_feedback_icon("attachment", 20))
        add_files_content.append(Gtk.Label(label="Add files"))
        self._add_attachment_button.set_child(add_files_content)
        describe_control(self._add_attachment_button, "Add files",
                         "Attach up to 5 files to your feedback.")
        self._add_attachment_button.connect("clicked", self._choose_attachments)
        attachments.set_header_suffix(self._add_attachment_button)
        self._attachment = Adw.ActionRow(
            title="diagnostic-logs.zip",
            subtitle="Latest 3 log dates · ZIP archive",
        )
        self._attachment.add_prefix(_feedback_icon("archive", 26))
        self._attachment_button = Gtk.Button(
            child=_feedback_icon("trash", 22, "#7650ff"), tooltip_text="Remove logs",
            valign=Gtk.Align.CENTER,
            css_classes=["flat", "feedback-attachment-button"],
        )
        self._include_logs = True
        self._attachment_button.connect("clicked", self._toggle_attachment)
        attachment_actions = Gtk.Box(spacing=4, valign=Gtk.Align.CENTER)
        self._download_button = Gtk.Button(
            child=_feedback_icon("download", 22, "#7650ff"),
            css_classes=["flat", "feedback-attachment-button"],
            tooltip_text="Save compressed logs to examine them before sending",
        )
        describe_control(self._download_button, "Download",
                         "Save a ZIP of diagnostic logs from the latest 3 log dates.")
        self._download_button.connect("clicked", self._download_logs)
        attachment_actions.append(self._download_button)
        attachment_actions.append(self._attachment_button)
        self._attachment.add_suffix(attachment_actions)
        self._update_attachment_accessibility()
        attachments.add(self._attachment)
        content.append(attachments)

        footer = Gtk.Box(spacing=16, margin_top=14, valign=Gtk.Align.END)
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
        )
        privacy_link.connect("activate-link", self._show_log_privacy)
        privacy_notice.append(privacy_link)
        footer.append(privacy_notice)
        self._status = Gtk.Label(
            xalign=0, wrap=True, selectable=True, visible=False,
        )
        self._status.connect(
            "notify::label",
            lambda label, _property: label.set_visible(bool(label.get_label())),
        )
        content.append(self._status)
        self._without_logs = Gtk.Button(label="Send without logs", visible=False)
        self._without_logs.connect("clicked", self._send_without_logs)
        content.append(self._without_logs)
        actions = Gtk.Box(spacing=10, halign=Gtk.Align.END, valign=Gtk.Align.CENTER)
        cancel = Gtk.Button(label="Close", css_classes=["feedback-close"])
        cancel.connect("clicked", lambda *_: self.close())
        actions.append(cancel)
        self._send_button = Gtk.Button(
            label="Send Feedback", sensitive=transport.SENDING_ENABLED,
            css_classes=["suggested-action", "feedback-send"],
        )
        self._send_button.connect("clicked", self._send)
        actions.append(self._send_button)
        footer.append(actions)
        content.append(footer)
        # Keep the complete form and its actions in the window allocation.
        # Only the expanding rich-text editor scrolls its contents.
        toolbar.set_content(content)
        self.set_content(toolbar)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._key_pressed)
        self.add_controller(keys)
        message.grab_editor_focus()

    def _show_log_privacy(self, *_args):
        dialog = Adw.AlertDialog.new(
            "Feedback privacy",
            transport.RETENTION_DISCLOSURE + "\n\nDiagnostic logs do not collect "
            "personally identifiable information (PII), such as account names, email "
            "addresses, or file contents. Review files and logs before sending.",
        )
        portal_link = Gtk.LinkButton(
            uri=PRIVACY_URL,
            label="View full privacy notice",
            halign=Gtk.Align.CENTER,
        )
        describe_control(
            portal_link,
            "View full privacy notice",
            "Open the Oh No! Parent Control privacy notice in your browser.",
        )
        dialog.set_extra_child(portal_link)
        dialog.add_response("close", "Close")
        dialog.set_default_response("close")
        dialog.set_close_response("close")
        dialog.present(self)
        return True

    def _hide_draft(self, *_args):
        # Closing the dialog keeps the draft and any pending retry in this app.
        self.set_visible(False)
        return True

    def _set_busy(self, busy):
        self._busy = busy
        for widget in (self._message, self._reply, self._attachment_button,
                       self._download_button, self._add_attachment_button,
                       self._without_logs, *self._attachment_rows):
            widget.set_sensitive(not busy)
        self._send_button.set_sensitive(not busy and transport.SENDING_ENABLED)

    def _send(self, _button):
        if self._busy or not transport.SENDING_ENABLED:
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
        )
        self._without_logs.set_visible(False)
        self._set_busy(True)
        self._send_button.set_label("Send Feedback")
        self._status.set_label("Preparing feedback… You may close this dialog; retries continue while the app is open.")
        include_logs = self._include_logs
        submission = self._submission
        cached_logs = self._logs
        def work():
            logs = cached_logs
            if include_logs and logs is None:
                try:
                    logs = collect_logs()
                except (OSError, ValueError) as error:
                    LOG.warning("feedback logs unavailable error_type=%s", type(error).__name__)
                    GLib.idle_add(self._submission_done, transport.Result("logs_unavailable"), submission)
                    return
            frozen = replace(submission, logs=logs if include_logs else None)
            GLib.idle_add(self._submission_progress,
                          "Sending feedback… You may close this dialog; retries continue while the app is open.")
            result = transport.submit(
                frozen, self._cancelled,
                lambda text: GLib.idle_add(self._submission_progress, text),
            )
            GLib.idle_add(self._submission_done, result, frozen)

        threading.Thread(target=work, daemon=True).start()

    def _submission_progress(self, text):
        self._status.set_label(text)
        return GLib.SOURCE_REMOVE

    def _submission_done(self, result, submission):
        self._submission = submission
        if submission.logs is not None:
            self._logs = submission.logs
        self._set_busy(False)
        LOG.info("feedback submission finished outcome=%s", result.kind)
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
        if result.kind == "success":
            self._receipt_id = result.receipt_id
            self._message.clear()
            self._reply.set_text("")
            self._clear_user_attachments()
            self._submission = None
            self._logs = None
        return GLib.SOURCE_REMOVE

    def _send_without_logs(self, _button):
        if self._include_logs:
            self._toggle_attachment(None)
        self._send(None)

    def _toggle_attachment(self, _button):
        self._include_logs = not self._include_logs
        self._attachment.set_title(
            "diagnostic-logs.zip" if self._include_logs else "No logs attached",
        )
        self._attachment.set_subtitle(
            "Latest 3 log dates · ZIP archive"
            if self._include_logs else "Your feedback can be sent without logs.",
        )
        if self._include_logs:
            self._attachment_button.set_child(_feedback_icon("trash", 22, "#7650ff"))
        else:
            self._attachment_button.set_label("Add logs")
        self._attachment_button.set_tooltip_text("Remove logs" if self._include_logs else "Add logs")
        self._download_button.set_visible(self._include_logs)
        self._update_attachment_accessibility()

    def _update_attachment_accessibility(self):
        describe_control(
            self._attachment_button,
            "Remove" if self._include_logs else "Add logs",
            "Choose whether to include compressed diagnostic logs from the latest 3 log dates with your feedback.",
        )

    def _choose_attachments(self, _button=None):
        if self._busy:
            return
        chooser = Gtk.FileDialog(title="Add feedback attachments")
        chooser.open_multiple(self, None, self._attachments_selected)

    def _attachments_selected(self, chooser, result):
        try:
            selected = chooser.open_multiple_finish(result)
        except GLib.Error as error:
            if not error.matches(Gtk.dialog_error_quark(), Gtk.DialogError.DISMISSED):
                LOG.warning("feedback attachment chooser failed error_type=%s",
                            type(error).__name__)
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
        LOG.info("feedback attachment read started file_count=%d", len(files))

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
                LOG.warning("feedback attachment read failed error_type=%s",
                            type(error).__name__)
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
            LOG.warning("feedback attachment read failed error_type=attachment_validation")
            self._status.set_label(error)
            return GLib.SOURCE_REMOVE
        for attachment in attachments:
            self._user_attachments.append(attachment)
            row = Adw.ActionRow(
                title=attachment.name,
                subtitle=self._format_size(len(attachment.data)),
            )
            row.add_prefix(Gtk.Image(icon_name="mail-attachment-symbolic"))
            remove = Gtk.Button(
                icon_name="user-trash-symbolic", tooltip_text="Remove attachment",
                valign=Gtk.Align.CENTER,
                css_classes=["flat", "feedback-attachment-button"],
            )
            describe_control(remove, f"Remove {attachment.name}",
                             "Remove this file from the feedback.")
            remove.connect("clicked", self._remove_user_attachment, attachment, row)
            row.add_suffix(remove)
            self._attachment_rows.append(row)
            self._attachments_group.add(row)
        LOG.info("feedback attachments ready added_count=%d total_count=%d",
                 len(attachments), len(self._user_attachments))
        self._status.set_label(
            f"{len(self._user_attachments)} file attachment"
            f"{'s' if len(self._user_attachments) != 1 else ''} ready.",
        )
        return GLib.SOURCE_REMOVE

    def _remove_user_attachment(self, _button, attachment, row):
        self._user_attachments.remove(attachment)
        self._attachment_rows.remove(row)
        self._attachments_group.remove(row)
        LOG.info("feedback attachment removed remaining_count=%d",
                 len(self._user_attachments))

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
        self._set_busy(True)
        self._attachment.set_subtitle("Preparing compressed logs…")
        LOG.info("diagnostic download preparation started")

        def collect():
            try:
                data = collect_logs()
            except (OSError, ValueError) as error:
                LOG.warning("diagnostic download preparation failed error_type=%s",
                            type(error).__name__)
                GLib.idle_add(self._download_done,
                              "Could not prepare logs. They may be unavailable or exceed 16 MB.")
            else:
                GLib.idle_add(self._choose_download, data)

        threading.Thread(target=collect, daemon=True).start()

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
                LOG.warning("diagnostic download chooser failed error_type=%s",
                            type(error).__name__)
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
            LOG.warning("diagnostic download save failed error_type=%s",
                        type(error).__name__)
            self._download_done("Could not save logs. Try another location.")
        else:
            LOG.info("diagnostic download saved")
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
