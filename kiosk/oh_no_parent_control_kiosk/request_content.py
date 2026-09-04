"""Shared GTK request form used by the kiosk session and child overlay."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from common.oh_no_parent_control_ui.about import app_name, branding_asset_path
from common.oh_no_parent_control_ui.accessibility import describe_control
from common.oh_no_parent_control_ui.user_icon import apply_gtk_user_icon, parse_listed_user
from .chrome import (
    APPROVER_HEAD, CHILD_HEAD, LOCK, POINTER, SHIELD, ArmoredButton,
    MetalBoard, MetalPanel, PixelIcon,
)


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
# Expanded account lists stay on the gateway plane, so they grow the board.
# Keep only two rows visible and page with matching chevrons when more exist.
VISIBLE_ACCOUNT_CHOICES = 2


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
        self._items = ()
        self._choice_buttons = []
        self._scroll_offset = 0

        self._trigger = Gtk.Button()
        self._trigger.add_css_class("oh-no-parent-control-account-selector")
        trigger_content = Gtk.Box(spacing=8)
        self._selected_icon = Gtk.Image()
        self._selected_icon.add_css_class("oh-no-parent-control-account-avatar")
        apply_gtk_user_icon(self._selected_icon, "")
        trigger_content.append(self._selected_icon)
        self._selected_label = Gtk.Label(xalign=0, hexpand=True)
        trigger_content.append(self._selected_label)
        self._trigger_arrow = Gtk.Image.new_from_icon_name("pan-down-symbolic")
        trigger_content.append(self._trigger_arrow)
        self._trigger.set_child(trigger_content)
        self._trigger.connect("clicked", self._toggle_choices)
        self.append(self._trigger)

        self._choices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._choices.add_css_class("oh-no-parent-control-account-choices")
        self._choices.set_visible(False)
        self._scroll_up = self._scroll_button("pan-up-symbolic", -1)
        self._choice_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._scroll_down = self._scroll_button("pan-down-symbolic", 1)
        self._choices.append(self._scroll_up)
        self._choices.append(self._choice_list)
        self._choices.append(self._scroll_down)
        self.append(self._choices)
        wheel = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        wheel.connect("scroll", self._wheel_scroll)
        self._choices.add_controller(wheel)

    def _scroll_button(self, icon_name, delta):
        button = Gtk.Button(halign=Gtk.Align.FILL)
        button.add_css_class("oh-no-parent-control-account-choice")
        button.add_css_class("oh-no-parent-control-account-scroll")
        button.set_child(Gtk.Image.new_from_icon_name(icon_name))
        button.connect("clicked", self._nudge_scroll, delta)
        return button

    def set_items(self, items):
        self._items = tuple(items)
        self._selected = Gtk.INVALID_LIST_POSITION
        self._scroll_offset = 0
        self._selected_label.set_text("")
        apply_gtk_user_icon(self._selected_icon, "")
        self._choice_buttons = []
        while child := self._choice_list.get_first_child():
            self._choice_list.remove(child)
        for index, (label, icon_file) in enumerate(self._items):
            choice = Gtk.Button(halign=Gtk.Align.FILL)
            choice.add_css_class("oh-no-parent-control-account-choice")
            content = Gtk.Box(spacing=8)
            icon = Gtk.Image()
            icon.add_css_class("oh-no-parent-control-account-avatar")
            apply_gtk_user_icon(icon, icon_file)
            content.append(icon)
            content.append(Gtk.Label(label=label, xalign=0, hexpand=True))
            choice.set_child(content)
            choice.connect("clicked", self._choose, index)
            self._choice_list.append(choice)
            self._choice_buttons.append(choice)
        self._set_expanded(False)

    def set_selected(self, index):
        if index >= len(self._items):
            raise ValueError("selector index is out of range")
        if index == self._selected:
            return
        self._selected = index
        label, icon_file = self._items[index]
        self._selected_label.set_text(label)
        apply_gtk_user_icon(self._selected_icon, icon_file)
        if self._on_selected is not None:
            self._on_selected()

    def get_selected(self):
        return self._selected

    def set_interaction_enabled(self, enabled):
        """Keep the selector and its exposed trigger accessibility state aligned."""
        self.set_sensitive(enabled)
        self._trigger.set_sensitive(enabled)

    def _toggle_choices(self, *_args):
        if not self._trigger.get_sensitive():
            return
        self._set_expanded(not self._choices.get_visible())

    def collapse(self):
        self._set_expanded(False)

    def _choose(self, _button, index):
        self.set_selected(index)
        self._set_expanded(False)

    def _set_expanded(self, expanded):
        self._choices.set_visible(expanded)
        self._trigger_arrow.set_from_icon_name(
            "pan-up-symbolic" if expanded else "pan-down-symbolic",
        )
        if expanded:
            self._reveal_selected()
        self._refresh_choice_window()

    def _max_scroll_offset(self):
        return max(0, len(self._choice_buttons) - VISIBLE_ACCOUNT_CHOICES)

    def _reveal_selected(self):
        if self._selected == Gtk.INVALID_LIST_POSITION:
            return
        if self._selected < self._scroll_offset:
            self._scroll_offset = self._selected
        elif self._selected >= self._scroll_offset + VISIBLE_ACCOUNT_CHOICES:
            self._scroll_offset = self._selected - VISIBLE_ACCOUNT_CHOICES + 1

    def _nudge_scroll(self, _button, delta):
        self._scroll_offset += delta
        self._refresh_choice_window()

    def _wheel_scroll(self, _controller, _dx, dy):
        if dy > 0:
            self._scroll_offset += 1
        elif dy < 0:
            self._scroll_offset -= 1
        else:
            return False
        self._refresh_choice_window()
        return True

    def _refresh_choice_window(self):
        overflow = len(self._choice_buttons) > VISIBLE_ACCOUNT_CHOICES
        self._scroll_offset = min(
            max(0, self._scroll_offset), self._max_scroll_offset(),
        )
        for index, button in enumerate(self._choice_buttons):
            button.set_visible(
                self._scroll_offset <= index < self._scroll_offset + VISIBLE_ACCOUNT_CHOICES
            )
        self._scroll_up.set_visible(overflow)
        self._scroll_down.set_visible(overflow)
        self._scroll_up.set_sensitive(self._scroll_offset > 0)
        self._scroll_down.set_sensitive(self._scroll_offset < self._max_scroll_offset())


class RequestContent(MetalBoard):
    """Reusable request-time form used as the kiosk's primary content."""

    def __init__(self, on_request, on_cancel, on_account_selected=None, *,
                 lock_child_selector=False, on_values_changed=None):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=2,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        self.add_css_class("oh-no-parent-control-content")
        self.add_css_class("oh-no-parent-control-dialog")
        self._duration_buttons = []
        self._account_uids = []
        self._account_labels = []
        self._account_icons = []
        self._approver_uids = []
        self._approver_labels = []
        self._approver_icons = []
        self._accounts_loaded = False
        self._approvers_loaded = False
        self._ready = False
        self._controls_enabled = True
        self._screen_time_limit_enabled = None
        self._lock_child_selector = lock_child_selector
        self._on_account_selected = on_account_selected
        self._on_values_changed = on_values_changed
        self._suppress_values_changed = False
        self._pending_approver_uid = 0
        self._kiosk_muted = False
        self._child_muted = False

        self.append(self._header())
        self._status = Gtk.Label(
            label="Loading request details…",
            wrap=True,
            hexpand=True,
            xalign=0,
            yalign=0.5,
            valign=Gtk.Align.CENTER,
        )
        # Bound wrap at measure time so the footer grows with the caption
        # instead of clipping a second line against min-height.
        self._status.set_natural_wrap_mode(Gtk.NaturalWrapMode.WORD)
        self._status.set_max_width_chars(26)
        self._status.set_overflow(Gtk.Overflow.VISIBLE)
        self._status.add_css_class("oh-no-parent-control-status")

        self._accounts = GatewayDropDown(self._account_changed)
        describe_control(
            self._accounts._trigger, "Child account",
            "Choose the child requesting more time.",
        )
        self._accounts.set_hexpand(True)
        child_selector = self._account_row("Child", CHILD_HEAD, self._accounts)
        self.append(child_selector)

        self._request_form = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=5,
        )
        self._approvers = GatewayDropDown(self._approver_changed)
        describe_control(
            self._approvers._trigger, "Approving parent",
            "Choose the administrator who can approve this request.",
        )
        self._approvers.set_hexpand(True)
        approver_selector = self._account_row(
            "Approver", APPROVER_HEAD, self._approvers,
        )
        self._request_form.append(approver_selector)

        self._choices = MetalPanel(
            orientation=Gtk.Orientation.VERTICAL, spacing=0, panel_kind="well",
            hexpand=True,
        )
        self._choices.add_css_class("oh-no-parent-control-choices")
        self._choices.set_margin_start(10)
        self._choices.set_margin_end(10)
        self._duration_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=0, hexpand=True,
        )
        self._duration_box.add_css_class("oh-no-parent-control-choices-inner")
        # MetalPanel chrome has no layout cost, so CSS padding on the well does
        # not keep rows off the painted rim. Child margins are measured: 4px
        # sides match the well bevel and corner notches so selected/hover bars
        # fill the inner tray without covering the frame.
        self._duration_box.set_margin_top(4)
        self._duration_box.set_margin_bottom(6)
        self._duration_box.set_margin_start(4)
        self._duration_box.set_margin_end(4)
        self._choices.append(self._duration_box)
        self._request_form.append(self._choices)
        self._build_duration_choices()

        self._custom_row = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        self._custom_row.add_css_class("oh-no-parent-control-custom-row")
        self._custom_entry = Gtk.Entry(
            text=str(MIN_CUSTOM_MINUTES),
            input_purpose=Gtk.InputPurpose.NUMBER,
            width_chars=8,
        )
        describe_control(
            self._custom_entry, "Custom duration in minutes",
            "Enter a requested duration from 0.1 through 1440 minutes.",
        )
        self._custom_entry.add_css_class("oh-no-parent-control-custom-entry")
        self._custom_row.append(self._custom_entry)
        self._custom_row.append(Gtk.Label(label="minutes"))
        self._custom_row.set_visible(False)
        self._request_form.append(self._custom_row)

        filter_row = Gtk.Button(hexpand=True)
        describe_control(
            filter_row, "Allow soft blocked apps",
            "Choose whether this request temporarily allows soft blocked apps.",
        )
        filter_row.add_css_class("oh-no-parent-control-app-filter-toggle")
        filter_row.set_margin_start(10)
        filter_row.set_margin_end(10)
        filter_inner = Gtk.Box(spacing=12)
        filter_icon = PixelIcon(
            SHIELD, display_size=20, label="",
        )
        filter_icon.add_css_class("oh-no-parent-control-filter-icon")
        filter_inner.append(filter_icon)
        filter_label = Gtk.Label(
            label="Allow soft blocked apps", xalign=0, hexpand=True,
            valign=Gtk.Align.CENTER,
        )
        filter_label.add_css_class("oh-no-parent-control-app-filter-label")
        filter_inner.append(filter_label)
        self._allow_soft = Gtk.Switch(valign=Gtk.Align.CENTER)
        describe_control(
            self._allow_soft, "Allow soft blocked apps",
            "Choose whether this request temporarily allows soft blocked apps.",
        )
        self._allow_soft.set_can_target(False)
        self._allow_soft.connect("notify::active", self._emit_values_changed)
        filter_label.set_mnemonic_widget(self._allow_soft)
        filter_inner.append(self._allow_soft)
        filter_row.set_child(filter_inner)
        filter_row.connect("clicked", self._toggle_allow_soft)
        self._filter_row = filter_row
        self._request_form.append(filter_row)

        actions = Gtk.Box(spacing=10, homogeneous=True)
        actions.add_css_class("oh-no-parent-control-actions")
        self._request = ArmoredButton(
            label="REQUEST", hexpand=True, armor_kind="request",
        )
        describe_control(
            self._request, "Request access",
            "Submit the selected duration and app access choice for approval.",
        )
        self._request.add_css_class("oh-no-parent-control-request-button")
        self._request.set_margin_start(10)
        self._request.set_margin_end(10)
        self._request.set_sensitive(False)
        self._request.connect("clicked", on_request)
        actions.append(self._request)
        self._request_form.append(actions)

        self._screen_limit_overlay = Gtk.Overlay()
        self._screen_limit_overlay.set_child(self._request_form)
        self._screen_limit_notice = Gtk.Label(
            label="Screen limit is not enabled in Parent App",
            wrap=True,
            justify=Gtk.Justification.CENTER,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.FILL,
        )
        self._screen_limit_notice.add_css_class("oh-no-parent-control-screen-limit-notice")
        self._screen_limit_overlay.add_overlay(self._screen_limit_notice)
        self.append(self._screen_limit_overlay)

        self._cancel = ArmoredButton(
            label="CANCEL", hexpand=True, armor_kind="cancel",
        )
        describe_control(
            self._cancel, "Cancel request",
            "Close this request screen without requesting additional time.",
        )
        self._cancel.add_css_class("oh-no-parent-control-cancel-button")
        self._cancel.set_margin_start(10)
        self._cancel.set_margin_end(10)
        self._cancel.connect("clicked", on_cancel)
        self.append(self._cancel)
        status_row = MetalPanel(
            orientation=Gtk.Orientation.VERTICAL,
            hexpand=True,
            panel_kind="footer",
        )
        status_row.add_css_class("oh-no-parent-control-status-row")
        status_row.set_overflow(Gtk.Overflow.VISIBLE)
        status_inner = Gtk.Box(
            spacing=8,
            hexpand=True,
            valign=Gtk.Align.CENTER,
        )
        status_inner.add_css_class("oh-no-parent-control-status-inner")
        status_inner.set_overflow(Gtk.Overflow.VISIBLE)
        lock = PixelIcon(LOCK, display_size=16, label="")
        lock.set_valign(Gtk.Align.CENTER)
        status_inner.append(lock)
        status_inner.append(self._status)
        status_row.append(status_inner)
        self.append(status_row)

    @staticmethod
    def _header():
        header = MetalPanel(spacing=8, panel_kind="header")
        header.add_css_class("oh-no-parent-control-header")
        icon = Gtk.Image.new_from_file(
            str(branding_asset_path("app_logo.png")),
        )
        # Keep the plate close to the two-line heading without dominating it.
        icon.set_pixel_size(48)
        icon.set_valign(Gtk.Align.CENTER)
        icon.add_css_class("oh-no-parent-control-header-icon")
        plate = Gtk.Box()
        plate.add_css_class("oh-no-parent-control-logo-plate")
        plate.set_valign(Gtk.Align.CENTER)
        plate.append(icon)
        header.append(plate)
        copy = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=1,
            valign=Gtk.Align.CENTER,
            hexpand=True,
        )
        copy.add_css_class("oh-no-parent-control-header-copy")
        for line in RequestContent._title_lines(app_name()):
            title = Gtk.Label(label=line, xalign=0)
            title.add_css_class("oh-no-parent-control-title")
            copy.append(title)
        subtitle = Gtk.Label(
            label="Choose how much extra time you need",
            xalign=0,
            wrap=True,
        )
        subtitle.add_css_class("oh-no-parent-control-subtitle")
        copy.append(subtitle)
        header.append(copy)
        return header

    @staticmethod
    def _title_lines(name):
        """Split the product name into the two-line board heading."""
        if "! " in name:
            lead, rest = name.split("! ", 1)
            return (f"{lead}!".upper(), rest.upper())
        return (name.upper(),)

    @staticmethod
    def _account_row(caption, icon_pixels, dropdown):
        row = MetalPanel(spacing=0, panel_kind="metal", hexpand=True)
        row.add_css_class("oh-no-parent-control-account-row")
        row.set_margin_start(10)
        row.set_margin_end(10)
        # MetalPanel chrome has no layout cost, so CSS padding on the plate
        # shrinks the painted face. Child margins keep labels off the bevel.
        inner = Gtk.Box(spacing=8, hexpand=True)
        inner.add_css_class("oh-no-parent-control-account-row-inner")
        inner.set_margin_top(11)
        inner.set_margin_end(12)
        inner.set_margin_bottom(6)
        inner.set_margin_start(10)
        icon = PixelIcon(icon_pixels, display_size=24, label=caption)
        icon.add_css_class("oh-no-parent-control-role-icon")
        icon.set_valign(Gtk.Align.START)
        icon.set_margin_top(3)
        inner.append(icon)
        detail = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True,
        )
        detail.set_valign(Gtk.Align.START)
        detail.set_margin_top(3)
        label = Gtk.Label(label=caption, xalign=0)
        label.add_css_class("oh-no-parent-control-account-caption")
        label.set_valign(Gtk.Align.START)
        label.set_vexpand(False)
        detail.append(label)
        dropdown.set_valign(Gtk.Align.START)
        detail.append(dropdown)
        inner.append(detail)
        row.append(inner)
        return row

    def _build_duration_choices(self):
        group = None
        for label, seconds in DURATIONS:
            button = Gtk.ToggleButton(hexpand=True)
            button.duration_seconds = seconds
            describe_control(
                button, f"Request {label}",
                f"Select {label} as the requested extra screen time duration.",
            )
            button.add_css_class("oh-no-parent-control-choice")
            overlay = Gtk.Overlay()
            overlay.set_child(Gtk.Label(label=label, hexpand=True))
            pointer = PixelIcon(POINTER, display_size=14, label="")
            pointer.add_css_class("oh-no-parent-control-choice-pointer")
            pointer.set_halign(Gtk.Align.START)
            pointer.set_valign(Gtk.Align.CENTER)
            pointer.set_can_target(False)
            overlay.add_overlay(pointer)
            button.set_child(overlay)
            if group is None:
                group = button
            else:
                button.set_group(group)
            button.connect("clicked", self._duration_clicked)
            self._duration_box.append(button)
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
        parsed = [parse_listed_user(user) for user in users]
        self._account_uids = [uid for uid, _label, _icon in parsed]
        self._account_labels = [label for _uid, label, _icon in parsed]
        self._account_icons = [icon for _uid, _label, icon in parsed]
        self._accounts.set_items(list(zip(self._account_labels, self._account_icons)))
        self._accounts_loaded = True
        if parsed:
            self._accounts.set_selected(0)
        if self._lock_child_selector:
            self._accounts.collapse()
        self._update_ready()

    def set_approvers(self, users):
        """Replace the selector with current local interactive administrators."""
        parsed = [parse_listed_user(user) for user in users]
        self._approver_uids = [uid for uid, _label, _icon in parsed]
        self._approver_labels = [label for _uid, label, _icon in parsed]
        self._approver_icons = [icon for _uid, _label, icon in parsed]
        self._approvers.set_items(list(zip(self._approver_labels, self._approver_icons)))
        self._approvers_loaded = True
        self._restore_approver()
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
        else:
            self._status.set_text("Choose the account and approving administrator")
        self._status.remove_css_class("oh-no-parent-control-error")
        self._update_controls()

    def _account_changed(self, *_args):
        index = self._accounts.get_selected()
        if (self._accounts_loaded and index < len(self._account_uids) and
                self._on_account_selected is not None):
            self._screen_time_limit_enabled = None
            self._update_ready()
            self._on_account_selected(self._account_uids[index])

    def _toggle_allow_soft(self, _button):
        if not self._allow_soft.get_sensitive():
            return
        self._allow_soft.set_active(not self._allow_soft.get_active())

    def _approver_changed(self, *_args):
        self._emit_values_changed()

    def _emit_values_changed(self, *_args):
        if self._suppress_values_changed or self._on_values_changed is None:
            return
        self._on_values_changed()

    def muted_for_surface(self, surface):
        return self._child_muted if surface == "child" else self._kiosk_muted

    def selected_approver_uid(self):
        index = self._approvers.get_selected()
        if index >= len(self._approver_uids):
            return 0
        return self._approver_uids[index]

    def _restore_approver(self):
        if not self._approvers_loaded or not self._approver_uids:
            return
        self._suppress_values_changed = True
        try:
            if self._pending_approver_uid in self._approver_uids:
                self._approvers.set_selected(
                    self._approver_uids.index(self._pending_approver_uid),
                )
            elif self._approvers.get_selected() == Gtk.INVALID_LIST_POSITION:
                self._approvers.set_selected(0)
        finally:
            self._suppress_values_changed = False

    def set_preferences(self, preferences):
        self._suppress_values_changed = True
        try:
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
            self._pending_approver_uid = request.get("last_selected_approver_uid", 0)
            self._kiosk_muted = bool(request.get("kiosk_muted", False))
            self._child_muted = bool(request.get("child_muted", False))
            self._restore_approver()
            self._update_ready()
        finally:
            self._suppress_values_changed = False

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
        self._emit_values_changed()

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
        time_limit_enabled = self._screen_time_limit_enabled is True
        self._request.set_sensitive(request_available)
        self._cancel.set_sensitive(self._controls_enabled)
        accounts_enabled = self._controls_enabled and not self._lock_child_selector
        self._accounts.set_interaction_enabled(accounts_enabled)
        # Expose the effective locked state on the actionable descendant too.
        # AT-SPI reports a widget's own state rather than inferring sensitivity
        # from a disabled ancestor, so disabling only the selector container
        # made the child-overlay trigger appear interactive to assistive tools.
        if self._lock_child_selector:
            self._accounts.collapse()
        self._custom_entry.set_sensitive(request_available and time_limit_enabled)
        self._allow_soft.set_sensitive(request_available)
        self._filter_row.set_sensitive(request_available)
        self._approvers.set_sensitive(request_available)
        for button in self._duration_buttons:
            button.set_sensitive(request_available and time_limit_enabled)
        self._screen_limit_notice.set_visible(
            self._screen_time_limit_enabled is False
        )
