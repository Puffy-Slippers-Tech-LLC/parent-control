"""GTK counterpart of the Shell request form, using the shared choices."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from common.oh_no_parent_control_ui.about import app_name, branding_asset_path


def _load_options():
    adjacent = Path(__file__).with_name("request-options.json")
    path = adjacent if adjacent.exists() else Path(__file__).parents[2] / "child" / "request-options.json"
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


class GatewayDropDown(Gtk.Box):
    """An in-form account selector that remains on the gateway plane.

    GTK's stock drop-down presents its choices in a popover surface.  That surface is
    outside the request form's snapshot, so it cannot inherit the form's 3D
    gateway transform.  Keeping the choice list here makes both the trigger
    and its expanded content descendants of the transformed form.
    """

    def __init__(self, on_selected=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._on_selected = on_selected
        self._selected = Gtk.INVALID_LIST_POSITION
        self._labels = ()

        self._trigger = Gtk.Button()
        self._trigger.add_css_class("oh-no-parent-control-account-selector")
        trigger_content = Gtk.Box(spacing=8)
        self._selected_label = Gtk.Label(xalign=0, hexpand=True)
        trigger_content.append(self._selected_label)
        trigger_content.append(Gtk.Image.new_from_icon_name("pan-down-symbolic"))
        self._trigger.set_child(trigger_content)
        self._trigger.connect("clicked", self._toggle_choices)
        self.append(self._trigger)

        self._choices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._choices.add_css_class("oh-no-parent-control-account-choices")
        self._choices.set_visible(False)
        self.append(self._choices)

    def set_items(self, labels):
        self._labels = tuple(labels)
        self._selected = Gtk.INVALID_LIST_POSITION
        self._selected_label.set_text("")
        while child := self._choices.get_first_child():
            self._choices.remove(child)
        for index, label in enumerate(self._labels):
            choice = Gtk.Button(label=label, halign=Gtk.Align.FILL)
            choice.add_css_class("oh-no-parent-control-account-choice")
            choice.connect("clicked", self._choose, index)
            self._choices.append(choice)
        self._choices.set_visible(False)

    def set_selected(self, index):
        if index >= len(self._labels):
            raise ValueError("selector index is out of range")
        if index == self._selected:
            return
        self._selected = index
        self._selected_label.set_text(self._labels[index])
        if self._on_selected is not None:
            self._on_selected()

    def get_selected(self):
        return self._selected

    def _toggle_choices(self, *_args):
        self._choices.set_visible(not self._choices.get_visible())

    def _choose(self, _button, index):
        self.set_selected(index)
        self._choices.set_visible(False)


class RequestContent(Gtk.Box):
    """Reusable request-time form used as the kiosk's primary content."""

    def __init__(self, on_request, on_cancel, on_account_selected=None):
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
        self._approver_uids = []
        self._approver_labels = []
        self._accounts_loaded = False
        self._approvers_loaded = False
        self._ready = False
        self._controls_enabled = True
        self._screen_time_limit_enabled = None
        self._on_account_selected = on_account_selected

        self.append(self._header())
        self._status = Gtk.Label(label="Loading request details…", wrap=True)
        self._status.add_css_class("oh-no-parent-control-status")

        account_selectors = Gtk.Grid(column_spacing=8, row_spacing=16)
        account_selectors.add_css_class("oh-no-parent-control-account-row")
        account_selectors.attach(Gtk.Label(label="Child", xalign=0), 0, 0, 1, 1)
        self._accounts = GatewayDropDown(self._account_changed)
        self._accounts.set_hexpand(True)
        account_selectors.attach(self._accounts, 1, 0, 1, 1)

        account_selectors.attach(Gtk.Label(label="Approver", xalign=0), 0, 1, 1, 1)
        self._approvers = GatewayDropDown()
        self._approvers.set_hexpand(True)
        account_selectors.attach(self._approvers, 1, 1, 1, 1)
        self.append(account_selectors)

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
        self.append(self._status)

    @staticmethod
    def _header():
        header = Gtk.Box(spacing=13)
        header.add_css_class("oh-no-parent-control-header")
        icon = Gtk.Image.new_from_file(
            str(branding_asset_path("app_logo.png")),
        )
        # Match the combined title/subtitle block so the artwork spans from
        # the title's top edge to the subtitle's bottom edge.
        icon.set_pixel_size(52)
        icon.set_valign(Gtk.Align.CENTER)
        icon.add_css_class("oh-no-parent-control-header-icon")
        header.append(icon)
        copy = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=3,
            valign=Gtk.Align.CENTER,
        )
        title = Gtk.Label(label=app_name(), xalign=0)
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
        self._accounts_loaded = False
        self._approvers_loaded = False
        self._ready = False
        self._screen_time_limit_enabled = None
        self._update_controls()
        self._status.remove_css_class("oh-no-parent-control-error")
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
        self._accounts.set_items(self._account_labels)
        self._accounts_loaded = True
        if parsed:
            self._accounts.set_selected(0)
        self._update_ready()

    def set_approvers(self, users):
        """Replace the selector with current local interactive administrators."""
        parsed = []
        for uid, label in users:
            if type(uid) is not int or not isinstance(label, str) or not label.strip():
                raise ValueError("broker returned an invalid approver")
            parsed.append((uid, label.strip()))
        self._approver_uids = [uid for uid, _label in parsed]
        self._approver_labels = [label for _uid, label in parsed]
        self._approvers.set_items(self._approver_labels)
        self._approvers_loaded = True
        if parsed:
            self._approvers.set_selected(0)
        self._update_ready()

    def _update_ready(self):
        self._ready = (
            self._accounts_loaded and self._approvers_loaded and
            bool(self._account_uids) and bool(self._approver_uids)
        )
        if not self._accounts_loaded or not self._approvers_loaded:
            self._status.set_text("Loading accounts…")
        elif not self._account_uids:
            self._status.set_text(
                "No local standard accounts are available. Create one, then reopen this screen."
            )
        elif not self._approver_uids:
            self._status.set_text(
                "No local interactive administrator accounts are available."
            )
        elif self._screen_time_limit_enabled is False:
            self._status.set_text(
                "Screen time limit is not enabled in the parent app."
            )
        else:
            self._status.set_text("Choose the account and approving administrator")
        if self._screen_time_limit_enabled is False:
            self._status.add_css_class("oh-no-parent-control-error")
        else:
            self._status.remove_css_class("oh-no-parent-control-error")
        self._update_controls()

    def _account_changed(self, *_args):
        index = self._accounts.get_selected()
        if (self._accounts_loaded and index < len(self._account_uids) and
                self._on_account_selected is not None):
            self._screen_time_limit_enabled = None
            self._update_ready()
            self._on_account_selected(self._account_uids[index])

    def set_preferences(self, preferences):
        self._screen_time_limit_enabled = (
            preferences.get("parent_control_enabled") is True
        )
        request = preferences.get("request", {})
        selected_value = request.get("last_selected_duration", str(DEFAULT_DURATION_SECONDS))
        selected_seconds = None if selected_value == "custom" else int(selected_value)
        selected = next(
            (button for button in self._duration_buttons
             if button.duration_seconds == selected_seconds), None,
        )
        if selected is None:
            selected = next(button for button in self._duration_buttons
                            if button.duration_seconds == DEFAULT_DURATION_SECONDS)
        selected.set_active(True)
        self._custom_row.set_visible(selected.duration_seconds is None)
        custom = request.get("last_custom_minutes", MIN_CUSTOM_MINUTES)
        self._custom_entry.set_text(str(custom))
        self._allow_soft.set_active(bool(request.get("allow_soft_blocked_apps", False)))
        self._update_ready()

    def is_selected_account(self, target_uid):
        """Whether an asynchronous response still belongs to the selected child."""
        index = self._accounts.get_selected()
        return (
            index < len(self._account_uids) and
            self._account_uids[index] == target_uid
        )

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
        approver_index = self._approvers.get_selected()
        if approver_index >= len(self._approver_uids):
            raise ValueError("Select an approving administrator")
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
            self._approver_uids[approver_index], seconds,
            self._allow_soft.get_active(),
        )

    def selected_preferences(self):
        selected = next(
            (button for button in self._duration_buttons if button.get_active()), None
        )
        if selected is None:
            raise ValueError("no duration selected")
        selected_value = "custom" if selected.duration_seconds is None else str(
            selected.duration_seconds
        )
        text = self._custom_entry.get_text().strip()
        custom = float(text) if NUMBER_RE.fullmatch(text) else MIN_CUSTOM_MINUTES
        return selected_value, custom, self._allow_soft.get_active()

    def show_validation_error(self, message):
        self._status.set_text(message)
        self._status.add_css_class("oh-no-parent-control-error")
        self._status.set_visible(True)

    def clear_validation_error(self):
        """Restore the normal request-form status after a silent cancellation."""
        self._status.remove_css_class("oh-no-parent-control-error")
        self._update_ready()

    def set_controls_sensitive(self, enabled):
        self._controls_enabled = enabled
        self._update_controls()

    def _update_controls(self):
        """Apply request availability while always preserving the exit path."""
        request_available = (
            self._controls_enabled and self._ready and
            self._screen_time_limit_enabled is True
        )
        self._request.set_sensitive(request_available)
        self._cancel.set_sensitive(self._controls_enabled)
        self._accounts.set_sensitive(self._controls_enabled)
        self._custom_entry.set_sensitive(request_available)
        self._allow_soft.set_sensitive(request_available)
        self._approvers.set_sensitive(request_available)
        for button in self._duration_buttons:
            button.set_sensitive(request_available)
