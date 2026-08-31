"""GTK counterpart of the Shell request form, using the shared choices."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


def _load_options():
    adjacent = Path(__file__).with_name("request-options.json")
    path = adjacent if adjacent.exists() else Path(__file__).parents[2] / "request-options.json"
    options = json.loads(
        path.read_text(encoding="utf-8")
    )
    if not options.get("durations"):
        raise ValueError("request-options.json has no durations")
    return options


OPTIONS = _load_options()
DURATIONS = tuple((item["label"], item["seconds"]) for item in OPTIONS["durations"])
DEFAULT_DURATION_SECONDS = OPTIONS["default_duration_seconds"]
MIN_CUSTOM_MINUTES = OPTIONS["minimum_custom_minutes"]
MAX_CUSTOM_MINUTES = OPTIONS["maximum_custom_minutes"]
NUMBER_RE = re.compile(r"^(?:\d+(?:\.\d+)?|\.\d+)$")


class RequestContent(Gtk.Box):
    """Reusable request-time form used as the kiosk's primary content."""

    def __init__(self, on_request, on_cancel, on_refresh):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        self.add_css_class("oh-no-parent-control-content")
        self.add_css_class("oh-no-parent-control-dialog")
        self._duration_buttons = []
        self._account_uids = []
        self._account_labels = []
        self._ready = False

        self.append(self._header())
        self._status = Gtk.Label(label="Loading request details…", wrap=True)
        self._status.add_css_class("oh-no-parent-control-status")
        self.append(self._status)

        account_row = Gtk.Box(spacing=8)
        account_row.add_css_class("oh-no-parent-control-account-row")
        account_row.append(Gtk.Label(label="Account", xalign=0, hexpand=True))
        self._accounts = Gtk.DropDown(model=Gtk.StringList.new([]))
        self._accounts.set_hexpand(True)
        account_row.append(self._accounts)
        self._refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Refresh accounts")
        self._refresh.connect("clicked", on_refresh)
        account_row.append(self._refresh)
        self.append(account_row)

        self._choices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._choices.add_css_class("oh-no-parent-control-choices")
        self.append(self._choices)
        self._build_duration_choices()

        self._custom_row = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        self._custom_row.add_css_class("oh-no-parent-control-custom-row")
        self._custom_entry = Gtk.Entry(
            text=str(MIN_CUSTOM_MINUTES),
            input_purpose=Gtk.InputPurpose.NUMBER,
            width_chars=8,
        )
        self._custom_entry.add_css_class("oh-no-parent-control-custom-entry")
        self._custom_row.append(self._custom_entry)
        self._custom_row.append(Gtk.Label(label="minutes"))
        self._custom_row.set_visible(False)
        self.append(self._custom_row)

        filter_row = Gtk.Box(spacing=12)
        filter_row.add_css_class("oh-no-parent-control-app-filter-toggle")
        filter_label = Gtk.Label(
            label="Allow soft blocked apps", xalign=0, hexpand=True,
            valign=Gtk.Align.CENTER,
        )
        filter_label.add_css_class("oh-no-parent-control-app-filter-label")
        filter_row.append(filter_label)
        self._allow_soft = Gtk.Switch(valign=Gtk.Align.CENTER)
        filter_label.set_mnemonic_widget(self._allow_soft)
        filter_row.append(self._allow_soft)
        self.append(filter_row)

        actions = Gtk.Box(spacing=10, homogeneous=True)
        actions.add_css_class("oh-no-parent-control-actions")
        self._cancel = Gtk.Button(label="Cancel", hexpand=True)
        self._cancel.add_css_class("oh-no-parent-control-cancel-button")
        self._cancel.connect("clicked", on_cancel)
        actions.append(self._cancel)
        self._request = Gtk.Button(label="Request", hexpand=True)
        self._request.add_css_class("oh-no-parent-control-request-button")
        self._request.set_sensitive(False)
        self._request.connect("clicked", on_request)
        actions.append(self._request)
        self.append(actions)

    @staticmethod
    def _header():
        header = Gtk.Box(spacing=13)
        header.add_css_class("oh-no-parent-control-header")
        icon = Gtk.Image.new_from_icon_name("alarm-symbolic")
        icon.set_pixel_size(24)
        icon.add_css_class("oh-no-parent-control-header-icon")
        header.append(icon)
        copy = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=3,
            valign=Gtk.Align.CENTER,
        )
        title = Gtk.Label(label="Oh No! Parent Control", xalign=0)
        title.add_css_class("oh-no-parent-control-title")
        copy.append(title)
        subtitle = Gtk.Label(label="Choose how much extra time you need", xalign=0)
        subtitle.add_css_class("oh-no-parent-control-subtitle")
        copy.append(subtitle)
        header.append(copy)
        return header

    def _build_duration_choices(self):
        group = None
        for label, seconds in DURATIONS:
            button = Gtk.ToggleButton(label=label, hexpand=True)
            button.duration_seconds = seconds
            button.add_css_class("oh-no-parent-control-choice")
            if group is None:
                group = button
            else:
                button.set_group(group)
            button.connect("clicked", self._duration_clicked)
            self._choices.append(button)
            self._duration_buttons.append(button)
            if seconds == DEFAULT_DURATION_SECONDS:
                button.set_active(True)

    def set_loading(self):
        self._ready = False
        self._request.set_sensitive(False)
        self._status.set_text("Loading accounts…")

    def set_accounts(self, users):
        """Replace the selector with the broker's current eligible accounts."""
        parsed = []
        for uid, label in users:
            if type(uid) is not int or not isinstance(label, str) or not label.strip():
                raise ValueError("broker returned an invalid account")
            parsed.append((uid, label.strip()))
        self._account_uids = [uid for uid, _label in parsed]
        self._account_labels = [label for _uid, label in parsed]
        self._accounts.set_model(Gtk.StringList.new(self._account_labels))
        self._ready = bool(parsed)
        if parsed:
            self._accounts.set_selected(0)
            self._status.set_text("Choose the account to manage")
        else:
            self._status.set_text("No local standard accounts are available. Create one, then refresh.")
        self._request.set_sensitive(self._ready)

    def _duration_clicked(self, button):
        if not button.get_active():
            button.set_active(True)
            return
        custom = button.duration_seconds is None
        self._custom_row.set_visible(custom)
        if custom:
            self._custom_entry.grab_focus()
            self._custom_entry.select_region(0, -1)

    def selected(self):
        account_index = self._accounts.get_selected()
        if not self._ready or account_index >= len(self._account_uids):
            raise ValueError("Select an account to manage")
        selected = next(
            (button for button in self._duration_buttons if button.get_active()), None
        )
        if selected is None:
            raise ValueError("no duration selected")
        seconds = selected.duration_seconds
        if seconds is None:
            text = self._custom_entry.get_text().strip()
            minutes = float(text) if NUMBER_RE.fullmatch(text) else math.nan
            if not math.isfinite(minutes) or not MIN_CUSTOM_MINUTES <= minutes <= MAX_CUSTOM_MINUTES:
                raise ValueError(
                    f"Enter a number from {MIN_CUSTOM_MINUTES} to "
                    f"{MAX_CUSTOM_MINUTES} minutes."
                )
            seconds = round(minutes * 60)
        return (
            self._account_uids[account_index], self._account_labels[account_index],
            seconds, self._allow_soft.get_active(),
        )

    def show_validation_error(self, message):
        self._status.set_text(message)
        self._status.add_css_class("oh-no-parent-control-error")
        self._status.set_visible(True)

    def set_controls_sensitive(self, enabled):
        self._request.set_sensitive(enabled and self._ready)
        self._cancel.set_sensitive(enabled)
        self._custom_entry.set_sensitive(enabled)
        self._allow_soft.set_sensitive(enabled)
        self._accounts.set_sensitive(enabled)
        self._refresh.set_sensitive(enabled)
        for button in self._duration_buttons:
            button.set_sensitive(enabled)
