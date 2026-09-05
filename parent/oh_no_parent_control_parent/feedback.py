"""Parent feedback dialog design; collection and delivery are not enabled yet."""

from __future__ import annotations

import gi

gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, Gtk

from common.oh_no_parent_control_ui.accessibility import describe_control


class FeedbackDialog(Adw.Window):
    """An editable design preview with an optional diagnostic attachment.

    No draft is persisted, no logs are read, and no transport is invoked.
    Attachment controls model inclusion until collection/delivery is selected.
    """

    def __init__(self, parent):
        super().__init__(title="Send Feedback", transient_for=parent, modal=True,
                         destroy_with_parent=True, default_width=540,
                         default_height=690, css_classes=["feedback-dialog"])
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar(
            title_widget=Adw.WindowTitle(title="Send Feedback"),
        ))
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20,
                          margin_start=28, margin_end=28,
                          margin_top=12, margin_bottom=24)
        heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        heading.append(Gtk.Image(icon_name="mail-unread-symbolic", pixel_size=32,
                                 halign=Gtk.Align.START,
                                 css_classes=["feedback-icon"]))
        heading.append(Gtk.Label(label="Help us make things better", xalign=0,
                                 wrap=True, css_classes=["title-1"]))
        heading.append(Gtk.Label(
            label="Found a problem or have an idea? We’d love to hear it.",
            xalign=0, wrap=True, css_classes=["dim-label"],
        ))
        content.append(heading)

        message_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        message = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR,
                              top_margin=12, bottom_margin=12,
                              left_margin=14, right_margin=14,
                              accepts_tab=False)
        describe_control(message, "Your feedback",
                         "Describe your idea, or what happened and what you expected.")
        message_label = Gtk.Label(label="Your _feedback", use_underline=True,
                                 mnemonic_widget=message, xalign=0,
                                 css_classes=["heading"])
        message_group.append(message_label)
        message_group.append(Gtk.Label(
            label="Tell us what happened and what you expected, or share your idea.",
            xalign=0, wrap=True, css_classes=["dim-label"],
        ))
        message_group.append(Gtk.ScrolledWindow(
            child=message, min_content_height=150, vexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            css_classes=["feedback-message"],
        ))
        content.append(message_group)

        reply_group = Adw.PreferencesGroup()
        reply = Adw.EntryRow(title="Reply email (optional)")
        reply.set_input_purpose(Gtk.InputPurpose.EMAIL)
        describe_control(reply, "Reply email (optional)",
                         "Add your email address if you would like a reply.")
        reply_group.add(reply)
        content.append(reply_group)

        attachments = Adw.PreferencesGroup(title="Diagnostic logs (optional)")
        self._attachment = Adw.ActionRow(
            title="diagnostic-logs.zip",
            subtitle="Logs from the past 3 days will be compressed and attached automatically.",
        )
        self._attachment.add_prefix(Gtk.Image(icon_name="package-x-generic-symbolic"))
        self._attachment_button = Gtk.Button(
            label="Remove", valign=Gtk.Align.CENTER,
            css_classes=["flat", "feedback-attachment-button"],
        )
        self._include_logs = True
        self._attachment_button.connect("clicked", self._toggle_attachment)
        self._attachment.add_suffix(self._attachment_button)
        self._update_attachment_accessibility()
        attachments.add(self._attachment)
        content.append(attachments)

        content.append(Gtk.Label(
            label="Preview only — sending and log collection are not available yet.",
            xalign=0, wrap=True, css_classes=["dim-label"],
        ))
        actions = Gtk.Box(spacing=12, halign=Gtk.Align.END)
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda *_: self.close())
        actions.append(cancel)
        actions.append(Gtk.Button(
            label="Send Feedback", sensitive=False,
            tooltip_text="Sending is not available yet.",
            css_classes=["suggested-action", "feedback-send"],
        ))
        content.append(actions)
        toolbar.set_content(Gtk.ScrolledWindow(
            child=content, hscrollbar_policy=Gtk.PolicyType.NEVER,
        ))
        self.set_content(toolbar)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._key_pressed)
        self.add_controller(keys)
        message.grab_focus()

    def _toggle_attachment(self, _button):
        self._include_logs = not self._include_logs
        self._attachment.set_title(
            "diagnostic-logs.zip" if self._include_logs else "No logs attached",
        )
        self._attachment.set_subtitle(
            "Logs from the past 3 days will be compressed and attached automatically."
            if self._include_logs else "Your feedback can be sent without logs.",
        )
        self._attachment_button.set_label("Remove" if self._include_logs else "Add logs")
        self._update_attachment_accessibility()

    def _update_attachment_accessibility(self):
        describe_control(
            self._attachment_button,
            "Remove" if self._include_logs else "Add logs",
            "Choose whether to include compressed diagnostic logs from the past 3 days with your feedback.",
        )

    def _key_pressed(self, _controller, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False
