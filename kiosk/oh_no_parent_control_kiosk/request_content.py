"""Shared GTK request form used by the kiosk session and child overlay."""

from __future__ import annotations

from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.translation_widgets import (
    localized, set_text, accessible_text, context_for, fixed_direction,
)

import json
import math
import re
import time
from dataclasses import dataclass, replace
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk, Pango

from common.oh_no_parent_control_ui.accessibility import describe_control, set_automation_id
from common.oh_no_parent_control_ui.application_ui import bind_ui
from common.oh_no_parent_control_ui.user_icon import apply_gtk_user_icon, parse_listed_user
from .chrome import (
    POINTER, SHIELD, ArmoredBox, ArmoredButton,
    MetalBoard, MetalPanel, PixelIcon, PlateTab,
)
from broker.oh_no_parent_control.preferences import (
    DEFAULT_TIME_GRANT_PRESETS, MIN_CUSTOM_MINUTES, MAX_CUSTOM_MINUTES,
    time_grant_choices,
)
from common.oh_no_parent_control_ui.duration import format_duration
from .duration_controls import duration_range_message


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
def _duration_label(seconds):
    if seconds is None:
        return m.CUSTOM_VALUE
    if seconds == 0:
        return m.REST_OF_DAY
    if seconds % 3600 == 0:
        return m.hour_count(seconds // 3600)
    if seconds % 60 == 0:
        return m.minute_count(seconds // 60)
    return format_duration(seconds)


DURATIONS = tuple((_duration_label(None if value == 'custom' else int(value)),
                   None if value == 'custom' else int(value))
                  for value in time_grant_choices(list(DEFAULT_TIME_GRANT_PRESETS)))
DEFAULT_DURATION_SECONDS = OPTIONS["default_duration_seconds"]
NUMBER_RE = re.compile(r"^(?:\d+(?:\.\d+)?|\.\d+)$")
# Keep only two rows visible and page with matching chevrons when more exist.
VISIBLE_ACCOUNT_CHOICES = 2


@dataclass(frozen=True)
class GrantView:
    """Display values from one status read for the selected child."""

    daily_seconds: int = 0
    running_mode: str = "none"
    running_seconds: int = 0  # Approved time beyond today's daily time.
    saved_seconds: int = 0
    running_end: int = 0
    requested_seconds: int = 0
    immediate_estimate: int = 0
    deferred_estimate: int = 0
    revision: int = 0
    evaluated_at: int = 0


GRANT_STATUS_TEXT = {
    "loading": m.LOADING_TIME_STATUS,
    "unavailable": m.TIME_STATUS_UNAVAILABLE,
    "busy": m.TIME_CONTROLS_BUSY,
    "recovery": m.TIME_STATUS_UNAVAILABLE,
    "pending": m.UPDATING_APPROVED_TIME,
    "disabled": m.SCREEN_LIMIT_IS_NOT_ENABLED_IN_PARENT_APP,
    "empty": m.NO_APPROVED_TIME,
}


class GatewayDropDown(Gtk.Box):
    """An in-form account selector that remains on the gateway plane.

    GTK's stock drop-down presents its choices in a popover surface.  That surface is
    outside the request form's snapshot, so it cannot inherit the form's 3D
    gateway transform. Overlay the choices on the form in that same snapshot.
    """

    def __init__(self, automation_namespace, automation_label, on_selected=None, *,
                 overlay, before_open):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        if (type(automation_namespace) is not str
                or not re.fullmatch(r"[a-z][a-z0-9-]*", automation_namespace)):
            raise ValueError("invalid account selector automation namespace")
        if not isinstance(automation_label, str) or not automation_label:
            raise ValueError("account selector accessibility label is required")
        self._automation_namespace = automation_namespace
        self._automation_label = automation_label
        self._on_selected = on_selected
        self._before_open = before_open
        self._selected = Gtk.INVALID_LIST_POSITION
        self._items = ()
        self._item_identities = ()
        self._choice_buttons = []
        self._scroll_offset = 0

        self._trigger = localized(Gtk.Button, )
        self._describe_trigger()
        self._trigger.add_css_class("oh-no-parent-control-account-selector")
        trigger_content = Gtk.Box(spacing=8)
        self.account_icon = Gtk.Image()
        apply_gtk_user_icon(self.account_icon, "", pixel_size=52)
        self._selected_icon = Gtk.Image()
        self._selected_icon.add_css_class("oh-no-parent-control-account-avatar")
        apply_gtk_user_icon(self._selected_icon, "")
        trigger_content.append(self._selected_icon)
        self._selected_label = localized(Gtk.Label, 
            xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END,
            max_width_chars=22,
        )
        set_automation_id(self._selected_label, self._automation_id("selected-none"))
        trigger_content.append(self._selected_label)
        self._trigger_arrow = Gtk.Image.new_from_icon_name("pan-down-symbolic")
        trigger_content.append(self._trigger_arrow)
        self._trigger.set_child(trigger_content)
        self._trigger.connect("clicked", self._toggle_choices)
        bind_ui(self._trigger, get_value=self._ui_value, set_value=self._ui_select,
                choices=lambda: [str(identity) for identity in self._item_identities])
        self.append(self._trigger)

        self._choices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        set_automation_id(self._choices, self._automation_id("choices"))
        self._choices.add_css_class("oh-no-parent-control-account-choices")
        self._choices.set_visible(False)
        self._scroll_up = self._scroll_button("pan-up-symbolic", -1)
        self._choice_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._scroll_down = self._scroll_button("pan-down-symbolic", 1)
        self._choices.append(self._scroll_up)
        self._choices.append(self._choice_list)
        self._choices.append(self._scroll_down)
        overlay.add_overlay(self._choices)
        overlay.connect("get-child-position", self._position_choices)
        self.connect("unmap", lambda _selector: self.collapse())
        wheel = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        wheel.connect("scroll", self._wheel_scroll)
        self._choices.add_controller(wheel)

    def _position_choices(self, overlay, child, allocation):
        if child is not self._choices:
            return False
        valid, bounds = self._trigger.compute_bounds(overlay.get_child())
        if not valid:
            return False
        allocation.x = int(bounds.get_x())
        allocation.y = int(bounds.get_y() + bounds.get_height()) + 4
        allocation.width = int(bounds.get_width())
        allocation.height = child.measure(Gtk.Orientation.VERTICAL, allocation.width)[1]
        return True

    def _scroll_button(self, icon_name, delta):
        button = localized(Gtk.Button, halign=Gtk.Align.FILL)
        direction = "up" if delta < 0 else "down"
        describe_control(
            button, m.MORE_ACCOUNT_CHOICES,
            m.MORE_ACCOUNT_CHOICES_DESCRIPTION,
            automation_id=self._automation_id(f"scroll-{direction}"),
        )
        button.add_css_class("oh-no-parent-control-account-choice")
        button.add_css_class("oh-no-parent-control-account-scroll")
        button.set_child(Gtk.Image.new_from_icon_name(icon_name))
        button.connect("clicked", self._nudge_scroll, delta)
        return button

    def _ui_value(self):
        return (str(self._item_identities[self._selected])
                if self._selected < len(self._item_identities) else "")

    def _ui_select(self, value):
        for index, identity in enumerate(self._item_identities):
            if value == str(identity):
                self._choice_buttons[index].emit("clicked")
                return
        raise ValueError("unknown account UID")

    def set_items(self, items, *, identities):
        self._items = tuple(items)
        self._item_identities = tuple(identities)
        if (len(self._item_identities) != len(self._items)
                or len(set(self._item_identities)) != len(self._item_identities)):
            raise ValueError("selector requires one unique identity per account")
        self.collapse()
        self._selected = Gtk.INVALID_LIST_POSITION
        self._scroll_offset = 0
        set_text(self._selected_label, 'label', "")
        set_automation_id(self._selected_label, self._automation_id("selected-none"))
        self._describe_trigger()
        apply_gtk_user_icon(self._selected_icon, "")
        apply_gtk_user_icon(self.account_icon, "", pixel_size=self.account_icon.get_pixel_size())
        self._choice_buttons = []
        while child := self._choice_list.get_first_child():
            self._choice_list.remove(child)
        for index, (label, icon_file) in enumerate(self._items):
            choice = localized(Gtk.Button, halign=Gtk.Align.FILL)
            describe_control(
                choice, m.ABOUT_DETAIL_LABEL % {'label': self._automation_label, 'value': label},
                m.SELECT_ACCOUNT_NAME % {'name': label},
                automation_id=self._automation_id(
                    f"choice-{self._item_identities[index]}"
                ),
            )
            choice.add_css_class("oh-no-parent-control-account-choice")
            content = Gtk.Box(spacing=8)
            icon = Gtk.Image()
            icon.add_css_class("oh-no-parent-control-account-avatar")
            apply_gtk_user_icon(icon, icon_file)
            content.append(icon)
            content.append(localized(Gtk.Label, 
                label=label, xalign=0, hexpand=True,
                ellipsize=Pango.EllipsizeMode.END, max_width_chars=22,
            ))
            choice.set_child(content)
            choice.connect("clicked", self._choose, index)
            self._choice_list.append(choice)
            self._choice_buttons.append(choice)
        self._set_expanded(False)

    def _automation_id(self, suffix):
        return f"kiosk-{self._automation_namespace}-{suffix}"

    def _describe_trigger(self, selected_label=None):
        description = (
            m.SELECTED_ACCOUNT % {'name': selected_label}
            if selected_label else m.CHOOSE_ACCOUNT
        )
        describe_control(
            self._trigger, self._automation_label, description,
            automation_id=self._automation_id("selector"),
        )

    def set_selected(self, index):
        if index >= len(self._items):
            raise ValueError("selector index is out of range")
        if index == self._selected:
            return
        self._selected = index
        label, icon_file = self._items[index]
        set_text(self._selected_label, 'label', label)
        set_automation_id(self._selected_label, self._automation_id(
            f"selected-{self._item_identities[index]}"))
        self._describe_trigger(label)
        apply_gtk_user_icon(self._selected_icon, icon_file)
        apply_gtk_user_icon(self.account_icon, icon_file, pixel_size=self.account_icon.get_pixel_size())
        if self._on_selected is not None:
            self._on_selected()

    def get_selected(self):
        return self._selected

    def set_interaction_enabled(self, enabled):
        """Keep the selector and its exposed trigger accessibility state aligned."""
        self.set_sensitive(enabled)
        self._trigger.set_sensitive(enabled)

    def _toggle_choices(self, *_args):
        if not self._trigger.is_sensitive() or not self._choice_buttons:
            return
        if not self.collapse():
            self._before_open()
            self._set_expanded(True)

    def collapse(self):
        if not self._choices.get_visible():
            return False
        root = self.get_root()
        focus = root.get_focus() if root is not None else None
        self._set_expanded(False)
        if focus is not None and focus.is_ancestor(self._choices):
            self._trigger.grab_focus()
        return True

    def dismiss_unless_target(self, target):
        if not self._choices.get_visible():
            return
        if target is not None and any(
            target is widget or target.is_ancestor(widget) for widget in (self, self._choices)
        ):
            return
        self.collapse()

    def _choose(self, _button, index):
        self.collapse()
        self.set_selected(index)

    def _set_expanded(self, expanded):
        self._choices.set_visible(expanded)
        self._trigger_arrow.set_from_icon_name(
            "pan-up-symbolic" if expanded else "pan-down-symbolic",
        )
        if expanded:
            self._reveal_selected()
        self._refresh_choice_window()
        # Give keyboard users an entry point while keeping pointer opens from
        # scrolling the viewport to the selected option.
        if expanded and self._trigger.has_visible_focus():
            focus_index = (
                self._scroll_offset if self._selected == Gtk.INVALID_LIST_POSITION
                else self._selected
            )
            self._choice_buttons[focus_index].grab_focus()

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
                 lock_child_selector=False, on_values_changed=None, selection_store=None):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=2,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        self.add_css_class("oh-no-parent-control-content")
        self.add_css_class("oh-no-parent-control-dialog")
        set_automation_id(self, "kiosk-request-form")
        self._duration_buttons = []
        self._account_details = []
        self._account_icon_width = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        self._account_caption_width = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        self._narrow_layout = None
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
        self._time_estimate = None
        self._validation_error = None
        self._grant_state = "unavailable"
        self._grant_view = None
        self._grant_feedback = None
        self._grant_actions = {}
        self._lock_dialog = None
        self._tabs = {}
        self._lock_child_selector = lock_child_selector
        self._selection_store = selection_store
        self._on_account_selected = on_account_selected
        self._on_values_changed = on_values_changed
        self._suppress_values_changed = False
        self._pending_approver_uid = 0
        self._kiosk_muted = True
        self._child_muted = True

        # Keep floating choices in this same snapshot so the gateway applies
        # its yaw to both the form and menu. Overlay children never size the form.
        self._form_overlay = Gtk.Overlay()
        set_automation_id(self._form_overlay, "kiosk-request-form-overlay")
        self._body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._form_overlay.set_child(self._body)
        self.append(self._form_overlay)
        self._body.append(self._build_tab_bar())
        self._status = localized(Gtk.Label, 
            label=m.LOADING_REQUEST_DETAILS,
            wrap=True,
            hexpand=True,
            xalign=0,
            yalign=0.5,
            valign=Gtk.Align.CENTER,
        )
        set_automation_id(self._status, "kiosk-request-status")
        # Bound wrap at measure time so the footer grows with the caption
        # instead of clipping a second line against min-height.
        self._status.set_natural_wrap_mode(Gtk.NaturalWrapMode.WORD)
        self._status.set_max_width_chars(26)
        self._status.set_overflow(Gtk.Overflow.VISIBLE)
        self._status.add_css_class("oh-no-parent-control-status")

        self._accounts = GatewayDropDown(
            "child", m.CHILD_ACCOUNT, self._account_changed,
            overlay=self._form_overlay, before_open=self.dismiss_account_choices,
        )
        self._accounts.set_hexpand(True)
        child_selector = self._account_row(m.CHILD, self._accounts, identity="child")
        self._body.append(child_selector)
        # Measure both pages so switching tabs keeps the footer in place.
        self._pages = Gtk.Stack()
        self._body.append(self._pages)

        self._request_form = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=5,
        )
        set_automation_id(self._request_form, "kiosk-request-options")
        self._approvers = GatewayDropDown(
            "approver", m.APPROVING_PARENT, self._approver_changed,
            overlay=self._form_overlay, before_open=self.dismiss_account_choices,
        )
        outside_click = Gtk.GestureClick(
            button=Gdk.BUTTON_PRIMARY, propagation_phase=Gtk.PropagationPhase.CAPTURE,
        )
        outside_click.connect("pressed", self._dismiss_account_choices_on_click)
        self._form_overlay.add_controller(outside_click)
        self._approvers.set_hexpand(True)
        approver_selector = self._account_row(
            m.APPROVER, self._approvers, identity="approver",
        )
        self._request_form.append(approver_selector)

        self._choices = MetalPanel(
            orientation=Gtk.Orientation.VERTICAL, spacing=0, panel_kind="well",
            hexpand=True,
        )
        set_automation_id(self._choices, "kiosk-duration-panel")
        self._choices.add_css_class("oh-no-parent-control-choices")
        self._choices.set_margin_start(10)
        self._choices.set_margin_end(10)
        self._duration_box = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE, homogeneous=False,
            min_children_per_line=1, max_children_per_line=2,
            column_spacing=4, row_spacing=2, hexpand=True,
        )
        set_automation_id(self._duration_box, "kiosk-duration-choices")
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
        bind_ui(self._duration_box, get_value=self._ui_duration_value,
                set_value=self._ui_select_duration,
                choices=lambda: ["custom" if b.duration_seconds is None else str(b.duration_seconds)
                                 for b in self._duration_buttons],
                aliases=("kiosk-duration",))

        self._custom_row = Gtk.Box(spacing=8, halign=Gtk.Align.FILL)
        self._custom_row.set_margin_start(
            self._choices.get_margin_start() + self._duration_box.get_margin_start())
        self._custom_row.set_margin_end(
            self._choices.get_margin_end() + self._duration_box.get_margin_end())
        set_automation_id(self._custom_row, "kiosk-custom-duration-row")
        self._custom_row.add_css_class("oh-no-parent-control-custom-row")
        self._custom_entry = localized(Gtk.Entry, 
            text=str(MIN_CUSTOM_MINUTES),
            input_purpose=Gtk.InputPurpose.NUMBER,
            width_chars=4,
            hexpand=True,
            halign=Gtk.Align.FILL,
        )
        describe_control(
            self._custom_entry, m.CUSTOM_VALUE,
            m.ENTER_A_REQUESTED_DURATION_FROM_0_1_THROUGH_1440_MINUTES,
            automation_id="kiosk-custom-duration",
        )
        self._custom_entry.add_css_class("oh-no-parent-control-custom-entry")
        self._custom_row.append(self._custom_entry)
        self._custom_unit = "minutes"
        # Reserve the radios' measured caption/indicator widths at the right
        # edge of the duration buttons; the entry receives all remaining width.
        self._unit_selector = Gtk.Box(spacing=12, valign=Gtk.Align.CENTER,
                                      hexpand=False, halign=Gtk.Align.END)
        describe_control(self._unit_selector, m.CUSTOM_VALUE, m.CUSTOM_VALUE,
                         automation_id="kiosk-custom-duration-units")
        self._unit_buttons = {}
        for unit, caption in (("minutes", m.MINUTES), ("hours", m.HOURS)):
            choice = Gtk.CheckButton()
            # Keep unit captions whole; _layout_custom_row stacks controls
            # when their measured widths do not fit, including translations.
            choice.set_child(localized(Gtk.Label, label=caption, xalign=0))
            if self._unit_buttons:
                choice.set_group(self._unit_buttons["minutes"])
            describe_control(choice, caption, caption,
                             automation_id=f"kiosk-custom-duration-unit-{unit}")
            choice.connect("toggled", self._custom_unit_toggled, unit)
            self._unit_buttons[unit] = choice
            self._unit_selector.append(choice)
        self._unit_buttons["minutes"].set_active(True)
        bind_ui(self._unit_selector, get_value=lambda: self._custom_unit,
                set_value=self._select_custom_unit,
                get_text=lambda: self._unit_buttons[self._custom_unit].get_child().get_text(),
                choices=lambda: ["minutes", "hours"])
        self._custom_row.append(self._unit_selector)
        self._custom_row.set_visible(False)
        self._request_form.append(self._custom_row)

        filter_row = localized(Gtk.Button, hexpand=True)
        describe_control(
            filter_row, m.ALLOW_SOFT_BLOCKED_APPS,
            m.CHOOSE_WHETHER_THIS_REQUEST_TEMPORARILY_ALLOWS_SOFT_BLOCKED_APPS,
            automation_id="kiosk-soft-apps-row",
        )
        filter_row.add_css_class("oh-no-parent-control-app-filter-toggle")
        filter_row.set_margin_start(10)
        filter_row.set_margin_end(10)
        filter_inner = Gtk.Box(spacing=6)
        set_automation_id(filter_inner, "kiosk-soft-apps-content")
        filter_icon = PixelIcon(
            SHIELD, display_size=20, label="",
        )
        set_automation_id(filter_icon, "kiosk-soft-apps-icon")
        filter_icon.add_css_class("oh-no-parent-control-filter-icon")
        filter_inner.append(filter_icon)
        filter_label = localized(Gtk.Label, 
            label=m.ALLOW_SOFT_BLOCKED_APPS, xalign=0, hexpand=True,
            valign=Gtk.Align.CENTER, wrap=True, max_width_chars=24,
        )
        set_automation_id(filter_label, "kiosk-soft-apps-label")
        filter_label.add_css_class("oh-no-parent-control-app-filter-label")
        filter_inner.append(filter_label)
        self._allow_soft = Gtk.Switch(valign=Gtk.Align.CENTER)
        describe_control(
            self._allow_soft, m.ALLOW_SOFT_BLOCKED_APPS,
            m.CHOOSE_WHETHER_THIS_REQUEST_TEMPORARILY_ALLOWS_SOFT_BLOCKED_APPS,
            automation_id="kiosk-soft-apps-toggle",
        )
        self._allow_soft.set_can_target(False)
        self._allow_soft.connect("notify::active", self._emit_values_changed)
        filter_label.set_mnemonic_widget(self._allow_soft)
        filter_inner.append(self._allow_soft)
        filter_row.set_child(filter_inner)
        filter_row.connect("clicked", self._toggle_allow_soft)
        self._filter_row = filter_row
        self._request_form.append(filter_row)

        actions = Gtk.Box(spacing=6, margin_start=10, margin_end=10)
        fixed_direction(actions, Gtk.TextDirection.LTR)
        set_automation_id(actions, "kiosk-request-actions")
        actions.add_css_class("oh-no-parent-control-actions")
        self._request = localized(
            Gtk.Button, hexpand=True,
            child=localized(Gtk.Label, label=m.REQUEST_USE_NOW, wrap=True,
                            wrap_mode=Pango.WrapMode.WORD_CHAR, justify=Gtk.Justification.CENTER),
        )
        describe_control(
            self._request, m.REQUEST_USE_NOW,
            m.SUBMIT_THE_SELECTED_DURATION_AND_APP_ACCESS_CHOICE_FOR_APPROVAL,
            automation_id="kiosk-request-submit",
        )
        self._request.add_css_class("oh-no-parent-control-request-button")
        self._request.set_sensitive(False)
        self._request.connect("clicked", on_request)
        self._request_actions = Gtk.Stack(hexpand=True)
        self._request_actions.add_named(self._build_request_split(), "request")
        self._request_actions.add_named(self._build_approved_actions(), "approved")
        actions_frame = ArmoredBox(hexpand=True, armor_kind="cancel")
        actions_frame.add_css_class("oh-no-parent-control-request-split")
        actions_frame.append(self._request_actions)

        self._screen_limit_overlay = Gtk.Overlay()
        set_automation_id(self._screen_limit_overlay, "kiosk-screen-limit-overlay")
        self._screen_limit_overlay.set_child(self._request_form)
        self._screen_limit_notice = localized(Gtk.Label, 
            label=m.SCREEN_LIMIT_IS_NOT_ENABLED_IN_PARENT_APP,
            wrap=True,
            justify=Gtk.Justification.CENTER,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.FILL,
        )
        set_automation_id(self._screen_limit_notice, "kiosk-screen-limit-notice")
        self._screen_limit_notice.add_css_class("oh-no-parent-control-screen-limit-notice")
        self._screen_limit_overlay.add_overlay(self._screen_limit_notice)
        self._pages.add_named(self._screen_limit_overlay, "request")
        self._pages.add_named(self._build_approved_page(), "approved")

        self._cancel = localized(ArmoredButton, 
            label=m.CANCEL_2,
            css_classes=["oh-no-parent-control-cancel-button"],
        )
        describe_control(
            self._cancel, m.CANCEL_REQUEST,
            m.CLOSE_THIS_REQUEST_SCREEN_WITHOUT_REQUESTING_ADDITIONAL_TIME,
            automation_id="kiosk-request-cancel",
        )
        self._cancel.connect("clicked", on_cancel)
        actions.append(self._cancel)
        actions.append(actions_frame)
        self._body.append(actions)
        status_row = MetalPanel(
            orientation=Gtk.Orientation.VERTICAL,
            hexpand=True,
            panel_kind="footer",
        )
        set_automation_id(status_row, "kiosk-request-status-panel")
        status_row.add_css_class("oh-no-parent-control-status-row")
        status_row.set_overflow(Gtk.Overflow.VISIBLE)
        status_inner = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            hexpand=True,
            valign=Gtk.Align.CENTER,
        )
        set_automation_id(status_inner, "kiosk-request-status-content")
        status_inner.add_css_class("oh-no-parent-control-status-inner")
        status_inner.set_overflow(Gtk.Overflow.VISIBLE)
        status_inner.append(self._status)
        self._already_saved = self._approved_label("kiosk-request-already-saved", xalign=0)
        self._already_saved.add_css_class("oh-no-parent-control-status")
        status_inner.append(self._already_saved)
        self._request_retry = self._action_button(m.TRY_AGAIN, "kiosk-request-retry",
                                                   lambda *_: self._run_grant_action("retry"))
        self._request_retry.set_halign(Gtk.Align.START)
        status_inner.append(self._request_retry)
        status_row.append(status_inner)
        self._status_pages = Gtk.Stack()
        self._status_pages.add_named(status_row, "request")
        self._status_pages.add_named(Gtk.Box(), "approved")
        self._body.append(self._status_pages)
        self._pages.set_visible_child_name("request")
        self._sync_tabs()
        self._update_controls()
        self._custom_entry.connect("changed", self._emit_values_changed)
        self._custom_entry.connect("activate", self._submit_custom_duration)

    def _submit_custom_duration(self, _entry):
        if self._request.is_sensitive():
            self._request.emit("clicked")

    def _build_tab_bar(self):
        self._tab_bar = Gtk.Box(homogeneous=True, css_classes=["plate-tabs", "request-tabs"],
                                accessible_role=Gtk.AccessibleRole.TAB_LIST)
        set_automation_id(self._tab_bar, "kiosk-request-tabs")
        bind_ui(self._tab_bar, get_value=lambda: self._pages.get_visible_child_name(),
                set_value=self.select_tab, choices=lambda: list(self._tabs))
        for name, caption in (("request", m.REQUEST_TIME), ("approved", m.APPROVED_TIME)):
            button = PlateTab(hexpand=True, accessible_role=Gtk.AccessibleRole.TAB)
            button.set_child(localized(Gtk.Label, label=caption, wrap=True,
                                       justify=Gtk.Justification.CENTER,
                                       margin_start=12, margin_end=12,
                                       margin_top=7, margin_bottom=7))
            describe_control(button, caption, caption, automation_id=f"kiosk-tab-{name}")
            if name == "approved":
                button.set_group(self._tabs["request"])
            button.connect("toggled", self._tab_toggled, name)
            self._tabs[name] = button
            self._tab_bar.append(button)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._tab_key_pressed)
        self._tab_bar.add_controller(keys)
        return self._tab_bar

    def _tab_toggled(self, button, name):
        if button.get_active():
            self.select_tab(name)

    def select_tab(self, name):
        if not isinstance(name, str) or name not in self._tabs:
            raise ValueError("unknown request tab")
        if name == self._pages.get_visible_child_name():
            return
        self.dismiss_request_menu()
        self.dismiss_account_choices()
        self._pages.set_visible_child_name(name)
        self._sync_tabs()

    def _sync_tabs(self):
        active = self._pages.get_visible_child_name()
        self._tabs[active].set_active(True)
        for name, button in self._tabs.items():
            button.update_state([Gtk.AccessibleState.SELECTED], [name == active])
        self._request_actions.set_visible_child_name(active)
        self._status_pages.set_visible_child_name(active)

    def _tab_key_pressed(self, _controller, keyval, _keycode, modifiers):
        if modifiers & Gtk.accelerator_get_default_mod_mask():
            return False
        names = list(self._tabs)
        if keyval in (Gdk.KEY_Left, Gdk.KEY_Right):
            name = next(name for name in names if name != self._pages.get_visible_child_name())
        elif keyval in (Gdk.KEY_Home, Gdk.KEY_End):
            name = names[0 if keyval == Gdk.KEY_Home else -1]
        else:
            return False
        self.select_tab(name)
        self._tabs[name].grab_focus()
        return True

    @staticmethod
    def _action_button(caption, identity, clicked, *, primary=True):
        button = ArmoredButton(armor_kind="request" if primary else "cancel")
        button.set_child(localized(Gtk.Label, label=caption, wrap=True,
                                   wrap_mode=Pango.WrapMode.WORD_CHAR,
                                   justify=Gtk.Justification.CENTER))
        button.add_css_class("oh-no-parent-control-request-button" if primary
                             else "oh-no-parent-control-cancel-button")
        set_automation_id(button, identity)
        button.connect("clicked", clicked)
        return button

    @staticmethod
    def _approved_label(identity, message="", *, xalign=0.5):
        label = localized(Gtk.Label, label=message, wrap=True, xalign=xalign,
                          wrap_mode=Pango.WrapMode.WORD_CHAR,
                          justify=Gtk.Justification.CENTER if xalign == 0.5 else Gtk.Justification.LEFT)
        set_automation_id(label, identity)
        return label

    def _build_request_split(self):
        split = Gtk.Box(spacing=3)
        split.append(self._request)
        self._request_menu = self._footer_menu("kiosk-request-menu")
        split.append(self._request_menu)
        items = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._save_for_later = self._action_button(
            m.REQUEST_SAVE_FOR_LATER, "kiosk-request-save-for-later",
            self._save_requested, primary=False)
        self._save_hint = self._approved_label("kiosk-request-save-hint")
        self._save_hint.set_max_width_chars(25)
        items.append(self._save_for_later)
        items.append(self._save_hint)
        self._request_menu.get_popover().set_child(items)
        return split

    def _build_approved_actions(self):
        self._approved_primary = Gtk.Stack(hexpand=True)
        self._request_more = self._footer_button(
            m.REQUEST_MORE_TIME, "request-more", self._return_to_request)
        self._pause = self._footer_button(m.PAUSE_TIMER, "pause", self._pause_requested)
        self._use_saved = self._footer_button(
            m.USE_SAVED_TIME, "use-saved", lambda *_: self._run_grant_action("use_saved"))
        self._retry = self._footer_button(
            m.TRY_AGAIN, "retry", lambda *_: self._run_grant_action("retry"))

        split = Gtk.Box(spacing=3)
        split.append(self._approved_primary)
        self._approved_menu = self._footer_menu("kiosk-approved-menu")
        self._pause_option = self._action_button(
            m.PAUSE_TIMER, "kiosk-approved-menu-pause", self._pause_requested, primary=False)
        self._approved_menu.get_popover().set_child(self._pause_option)
        split.append(self._approved_menu)
        return split

    def _footer_button(self, caption, name, clicked):
        button = localized(
            Gtk.Button,
            child=localized(Gtk.Label, label=caption, wrap=True,
                            wrap_mode=Pango.WrapMode.WORD_CHAR, justify=Gtk.Justification.CENTER),
        )
        set_automation_id(button, f"kiosk-approved-{name}")
        button.add_css_class("oh-no-parent-control-request-button")
        button.connect("clicked", clicked)
        self._approved_primary.add_named(button, name)
        return button

    def _footer_menu(self, identity):
        popover = Gtk.Popover(autohide=True, position=Gtk.PositionType.BOTTOM)
        set_automation_id(popover, f"{identity}-popover")
        menu = Gtk.MenuButton(popover=popover, icon_name="pan-down-symbolic")
        menu.add_css_class("oh-no-parent-control-request-menu")
        describe_control(menu, m.MORE_REQUEST_OPTIONS, m.MORE_REQUEST_OPTIONS,
                         automation_id=identity)
        bind_ui(menu, get_value=popover.get_visible,
                set_value=lambda opened: self._set_request_menu_open(menu, opened))
        return menu

    @staticmethod
    def _set_request_menu_open(menu, opened):
        if type(opened) is not bool:
            raise ValueError("request menu state requires a boolean")
        if opened:
            menu.popup()
        else:
            menu.popdown()

    def dismiss_request_menu(self):
        for menu in (self._request_menu, self._approved_menu):
            if menu.get_popover().get_visible():
                menu.popdown()
                return True
        return False

    def dismiss_account_choices(self):
        return self._accounts.collapse() or self._approvers.collapse()

    def _dismiss_account_choices_on_click(self, _gesture, _press_count, x, y):
        target = self._form_overlay.pick(x, y, Gtk.PickFlags.DEFAULT)
        self._accounts.dismiss_unless_target(target)
        self._approvers.dismiss_unless_target(target)

    def _build_approved_page(self):
        page = MetalPanel(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                          panel_kind="well", vexpand=False)
        set_automation_id(page, "kiosk-approved-page")
        page.set_margin_start(10)
        page.set_margin_end(10)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                       vexpand=True, valign=Gtk.Align.CENTER,
                       margin_start=12, margin_end=12, margin_top=12, margin_bottom=12)
        page.append(body)
        self._approved_status = self._approved_label("kiosk-approved-status")
        bind_ui(self._approved_status, get_value=self._approved_display_state)
        self._approved_status.set_margin_top(4)
        body.append(self._approved_status)
        self._approved_feedback = self._approved_label("kiosk-approved-feedback")
        self._approved_feedback.add_css_class("oh-no-parent-control-error")
        body.append(self._approved_feedback)

        self._running_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self._running_status = self._approved_label("kiosk-approved-running-status")
        self._running_balance = self._balance_label("running", "running_seconds")
        self._pause_hint = self._approved_label("kiosk-approved-pause-hint",
                                               m.SAVE_REMAINING_TIME_FOR_LATER)
        for widget in (self._running_status, self._running_balance, self._pause_hint):
            self._running_row.append(widget)
        body.append(self._running_row)
        self._daily_balance = self._balance_label("daily", "daily_seconds")
        body.append(self._daily_balance)

        self._saved_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self._saved_row.append(self._approved_label("kiosk-approved-saved-title", m.SAVED_FOR_LATER))
        self._saved_balance = self._balance_label("saved", "saved_seconds")
        self._saved_row.append(self._saved_balance)
        hint = m.ADD_IT_TO_YOUR_TIME_NOW if self._lock_child_selector else m.START_TIMER_AND_RETURN_TO_SIGN_IN
        self._saved_row.append(self._approved_label("kiosk-approved-saved-hint", hint))
        body.append(self._saved_row)
        return page

    def _return_to_request(self, _button):
        self.select_tab("request")
        self._tabs["request"].grab_focus()

    def _balance_label(self, name, field):
        label = self._approved_label(f"kiosk-approved-{name}")
        if name != "daily":
            label.add_css_class("oh-no-parent-control-approved-balance")
        bind_ui(label, get_value=lambda: getattr(self._displayed_grant(), field, None))
        return label

    def set_grant_actions(self, *, save_for_later, pause, use_saved, retry):
        """Attach the window's action handlers to this view."""
        self._grant_actions = dict(save_for_later=save_for_later, pause=pause,
                                   use_saved=use_saved, retry=retry)
        self._update_controls()

    def set_grant_status(self, state, status=None):
        """Render a status update already bound to the current account by the caller."""
        if state == "ready":
            if not isinstance(status, GrantView):
                raise ValueError("ready time status requires a snapshot")
        elif state not in {"loading", "unavailable", "busy", "recovery", "pending"} or status is not None:
            raise ValueError("invalid time status")
        self._grant_state = state
        self._grant_view = status
        self._update_controls()
        self._update_status()

    def _approved_display_state(self):
        if self._screen_time_limit_enabled is False:
            return "disabled"
        if not self._controls_enabled:
            return "pending"
        if self._screen_time_limit_enabled is None:
            return "unavailable" if self._accounts_loaded and not self._account_uids else "loading"
        if self._grant_state == "ready":
            view = self._displayed_grant()
            if view.running_mode == "none" and not view.saved_seconds:
                return "empty"
        return self._grant_state

    def _displayed_grant(self):
        if (self._controls_enabled and self._screen_time_limit_enabled is True
                and self._grant_state == "ready"):
            view = self._grant_view
            if not view.evaluated_at:
                return view
            now = max(view.evaluated_at, int(time.time()))
            elapsed = now - view.evaluated_at
            daily = max(0, view.daily_seconds - elapsed) if self._lock_child_selector else view.daily_seconds
            running = max(0, view.running_end - now)
            return replace(view, daily_seconds=daily, running_seconds=max(0, running - daily),
                           running_mode=view.running_mode if running else "none")
        return None

    def grant_revision(self):
        return self._grant_view.revision if self._displayed_grant() is not None else None

    def tick_grant_view(self):
        if self._grant_view is not None:
            self._render_approved()
        return GLib.SOURCE_CONTINUE

    def set_grant_feedback(self, message):
        self._grant_feedback = message
        set_text(self._approved_feedback, "label", message or "")
        self._approved_feedback.set_visible(bool(message))
        self._update_status()

    def _render_approved(self):
        state = self._approved_display_state()
        view = self._displayed_grant()
        set_text(self._approved_status, "label", GRANT_STATUS_TEXT.get(state, ""))
        self._approved_status.set_visible(state != "ready")

        running = view is not None and view.running_mode != "none"
        fixed = running and view.running_mode == "fixed"
        can_pause = fixed and view.running_seconds > 0
        saved = view is not None and view.saved_seconds > 0
        daily = view is not None and view.daily_seconds > 0
        self._running_row.set_visible(running)
        self._running_balance.set_visible(can_pause)
        self._daily_balance.set_visible(daily)
        self._saved_row.set_visible(saved)
        self._pause_hint.set_visible(can_pause)

        running_status = ""
        if fixed:
            running_status = m.TIMER_RUNNING if can_pause else m.COVERED_BY_DAILY_TIME
        elif running:
            deadline = GLib.DateTime.new_from_unix_local(view.running_end)
            running_status = m.APPROVED_UNTIL % {"time": deadline.format("%H:%M")}
        set_text(self._running_status, "label", running_status)
        set_text(self._running_balance, "label", format_duration(view.running_seconds) if can_pause else "")
        set_text(self._saved_balance, "label", format_duration(view.saved_seconds) if saved else "")
        set_text(self._daily_balance, "label", m.TODAYS_DAILY_TIME % {
            "duration": format_duration(view.daily_seconds)} if daily else "")
        if saved:
            set_text(self._use_saved.get_child(), "label", m.ADD_SAVED_TIME_TO_TIMER if running else m.USE_SAVED_TIME)
        self._render_approved_actions(state, can_pause, saved)

    def _render_approved_actions(self, state, can_pause, saved):
        retry = state in {"busy", "unavailable", "recovery"}
        can_retry = bool(self._grant_actions.get("retry") and self._account_uids)
        self._retry.set_sensitive(retry and can_retry)
        self._request_retry.set_sensitive(can_retry)
        self._request_retry.set_visible(retry)
        self._use_saved.set_sensitive(bool(saved and self._grant_actions.get("use_saved")))
        pause_available = bool(can_pause and self._grant_actions.get("pause"))
        self._pause.set_sensitive(pause_available)
        self._approved_menu.set_sensitive(pause_available)
        show_pause_menu = saved and can_pause
        if not show_pause_menu:
            self._approved_menu.popdown()
        if state == "pending":
            return
        self._approved_menu.set_visible(show_pause_menu)

        primary = "request-more"
        if saved:
            primary = "use-saved"
        elif can_pause:
            primary = "pause"
        elif retry:
            primary = "retry"
        self._approved_primary.set_visible_child_name(primary)

    def _run_grant_action(self, name):
        action = self._grant_actions.get(name)
        if action is not None:
            action()

    def _save_requested(self, _button):
        self.dismiss_request_menu()
        try:
            _uid, _child, _approver, seconds, _soft = self.selected()
        except ValueError as error:
            self.show_validation_error(error.args[0])
            return
        view = self._displayed_grant()
        if not seconds or view is None:
            return
        if self._lock_child_selector and view.running_mode == "fixed":
            self._confirm_lock("save_for_later", view.deferred_estimate, view.revision)
        else:
            self._run_grant_action("save_for_later")

    def _pause_requested(self, _button):
        self.dismiss_request_menu()
        view = self._displayed_grant()
        if view is None or view.running_mode != "fixed" or view.running_seconds <= 0:
            return
        if self._lock_child_selector:
            self._confirm_lock("pause", view.saved_seconds + view.running_seconds, view.revision)
        else:
            self._run_grant_action("pause")

    def _confirm_lock(self, action, seconds, revision):
        if self._lock_dialog is not None:
            return
        saving = action == "save_for_later"
        account = self.selected_child_account()
        title = m.SAVE_AND_LOCK_QUESTION if saving else m.PAUSE_AND_LOCK_QUESTION
        dialog = Gtk.Window(transient_for=self.get_root(), modal=True,
                            decorated=False, destroy_with_parent=True)
        self._lock_dialog = dialog
        set_automation_id(dialog, "kiosk-lock-confirmation")
        set_text(dialog, "title", title)
        dialog.add_css_class("oh-no-parent-control-language-dialog")
        dialog.set_default_size(360, -1)
        board = MetalBoard(orientation=Gtk.Orientation.VERTICAL)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                          margin_start=18, margin_end=18, margin_top=18, margin_bottom=18)
        heading = self._approved_label("kiosk-lock-title", title)
        heading.add_css_class("oh-no-parent-control-page-title")
        content.append(heading)
        detail = self._approved_label("kiosk-lock-body", m.LOCK_CONFIRMATION_BODY % {
            "duration": format_duration(seconds)}, xalign=0)
        detail.set_max_width_chars(38)
        content.append(detail)

        def close(*_args):
            self._lock_dialog = None
            dialog.destroy()
            return True

        def confirm(_button):
            close()
            source = self._save_for_later if saving else self._pause
            if (source.is_sensitive() and account == self.selected_child_account()
                    and revision == self.grant_revision()):
                self._run_grant_action(action)
            elif self.grant_revision() is not None:
                self.set_grant_feedback(m.TIME_STATUS_CHANGED)

        actions = Gtk.Box(spacing=6, homogeneous=True)
        cancel = self._action_button(m.CANCEL, "kiosk-lock-cancel", close, primary=False)
        actions.append(cancel)
        actions.append(self._action_button(m.CONTINUE if saving else m.PAUSE_AND_LOCK,
                                          "kiosk-lock-confirm", confirm))
        content.append(actions)
        board.append(content)
        dialog.set_child(board)
        dialog.set_default_widget(cancel)
        dialog.set_focus(cancel)
        bind_ui(dialog, activate=lambda: dialog.emit("activate-default"))
        dialog.connect("close-request", close)
        keys = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", lambda _keys, keyval, *_: close() if keyval == Gdk.KEY_Escape else False)
        dialog.add_controller(keys)
        dialog.present()

    def _account_row(self, caption, dropdown, *, identity):
        row = MetalPanel(spacing=0, panel_kind="metal", hexpand=True)
        set_automation_id(row, f"kiosk-{identity}-account-row")
        row.add_css_class("oh-no-parent-control-account-row")
        row.set_margin_start(10)
        row.set_margin_end(10)
        # MetalPanel chrome has no layout cost, so CSS padding on the plate
        # shrinks the painted face. Child margins keep labels off the bevel.
        inner = Gtk.Box(spacing=8, hexpand=True)
        set_automation_id(inner, f"kiosk-{identity}-account-content")
        inner.add_css_class("oh-no-parent-control-account-row-inner")
        inner.set_margin_top(4)
        inner.set_margin_end(12)
        inner.set_margin_bottom(4)
        inner.set_margin_start(10)
        icon = dropdown.account_icon
        set_automation_id(icon, f"kiosk-{identity}-account-icon")
        icon.add_css_class("oh-no-parent-control-role-icon")
        icon.set_valign(Gtk.Align.CENTER)
        apply_gtk_user_icon(icon, "", pixel_size=24)
        self._account_icon_width.add_widget(icon)
        inner.append(icon)
        detail = Gtk.Box(
            spacing=12, hexpand=True,
        )
        set_automation_id(detail, f"kiosk-{identity}-account-detail")
        detail.set_valign(Gtk.Align.CENTER)
        label = localized(Gtk.Label, label=caption, xalign=0)
        set_automation_id(label, f"kiosk-{identity}-account-caption")
        label.add_css_class("oh-no-parent-control-account-caption")
        label.set_valign(Gtk.Align.CENTER)
        label.set_vexpand(False)
        self._account_caption_width.add_widget(label)
        detail.append(label)
        dropdown.set_valign(Gtk.Align.CENTER)
        detail.append(dropdown)
        self._account_details.append(detail)
        inner.append(detail)
        row.append(inner)
        return row

    def set_layout_width(self, width):
        """Stack account captions on narrow displays to keep names readable."""
        self._layout_custom_row(width)
        columns = 2 if width >= 300 else 1
        self._duration_box.set_min_children_per_line(columns)
        self._duration_box.set_max_children_per_line(columns)
        narrow = width < 300
        for dropdown in (self._accounts, self._approvers):
            dropdown.account_icon.set_visible(not narrow)
            # Keep one avatar when the row is compact, preserving name space.
            dropdown._selected_icon.set_visible(narrow or width >= 400)
        if narrow == self._narrow_layout:
            return
        self._narrow_layout = narrow
        for detail in self._account_details:
            detail.set_orientation(
                Gtk.Orientation.VERTICAL if narrow else Gtk.Orientation.HORIZONTAL,
            )
            detail.set_spacing(2 if narrow else 6)

    def _layout_custom_row(self, width):
        # Measure the current translations with GTK's actual font, indicator
        # and spacing. Character counts cannot predict shaped label widths.
        style = self.get_style_context()
        padding, border = style.get_padding(), style.get_border()
        available = max(1, width - padding.left - padding.right
                        - border.left - border.right
                        - self._custom_row.get_margin_start()
                        - self._custom_row.get_margin_end())
        unit_width = sum(button.measure(Gtk.Orientation.HORIZONTAL, -1)[1]
                         for button in self._unit_buttons.values())
        unit_width += self._unit_selector.get_spacing()
        entry_width = self._custom_entry.measure(Gtk.Orientation.HORIZONTAL, -1)[0]
        self._custom_row.set_orientation(
            Gtk.Orientation.HORIZONTAL
            if entry_width + self._custom_row.get_spacing() + unit_width <= available
            else Gtk.Orientation.VERTICAL)
        self._unit_selector.set_orientation(
            Gtk.Orientation.HORIZONTAL if unit_width <= available
            else Gtk.Orientation.VERTICAL)

    def _build_duration_choices(self, durations=DURATIONS):
        group = None
        for label, seconds in durations:
            identity = "custom" if seconds is None else str(seconds)
            button = localized(Gtk.ToggleButton, hexpand=True)
            button.duration_seconds = seconds
            describe_control(
                button, m.REQUEST_LABEL_S % {'label': label},
                m.SELECT_LABEL_S_AS_THE_REQUESTED_EXTRA_SCREEN_TIME_DURATION % {'label': label},
                automation_id=f"kiosk-duration-{identity}",
            )
            button.add_css_class("oh-no-parent-control-choice")
            overlay = Gtk.Overlay()
            # The selected pointer reaches the longest caption. A display-only
            # space gives Custom value a small gap without moving other rows or
            # changing the label used by accessibility and request state.
            display_label = " " + label if seconds is None else label
            option_label = localized(Gtk.Label, 
                label=display_label, hexpand=True, wrap=True, max_width_chars=12,
                justify=Gtk.Justification.CENTER,
            )
            set_automation_id(option_label, f"kiosk-duration-label-{identity}")
            overlay.set_child(option_label)
            set_automation_id(overlay, f"kiosk-duration-option-{identity}")
            pointer = PixelIcon(POINTER, display_size=14, label="")
            set_automation_id(pointer, f"kiosk-duration-pointer-{identity}")
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
            bind_ui(button, set_value=lambda value, button=button: self._ui_set_duration_button(
                button, value))
            self._duration_box.append(button)
            self._duration_buttons.append(button)
            if seconds == DEFAULT_DURATION_SECONDS:
                button.set_active(True)

    def set_loading(self):
        self._accounts_loaded = False
        self._approvers_loaded = False
        self._ready = False
        self._screen_time_limit_enabled = None
        self._grant_state = "unavailable"
        self._grant_view = None
        self._update_controls()
        self._validation_error = None
        self._time_estimate = None
        self._update_status()

    def set_accounts(self, users):
        """Replace the selector with the broker's current eligible accounts."""
        parsed = [parse_listed_user(user) for user in users]
        self._account_uids = [uid for uid, _label, _icon in parsed]
        self._account_labels = [label for _uid, label, _icon in parsed]
        self._account_icons = [icon for _uid, _label, icon in parsed]
        self._accounts.set_items(list(zip(self._account_labels, self._account_icons)),
                                 identities=self._account_uids)
        self._accounts_loaded = True
        if parsed:
            remembered = (self._selection_store.preferred("child_uid")
                          if self._selection_store and not self._lock_child_selector else 0)
            self._accounts.set_selected(
                self._account_uids.index(remembered) if remembered in self._account_uids else 0,
            )
        self._update_ready()

    def set_approvers(self, users):
        """Replace the selector with current local interactive administrators."""
        parsed = [parse_listed_user(user) for user in users]
        self._approver_uids = [uid for uid, _label, _icon in parsed]
        self._approver_labels = [label for _uid, label, _icon in parsed]
        self._approver_icons = [icon for _uid, _label, icon in parsed]
        self._approvers.set_items(list(zip(self._approver_labels, self._approver_icons)),
                                  identities=self._approver_uids)
        self._approvers_loaded = True
        self._restore_approver()
        self._update_ready()

    def _update_ready(self):
        self._ready = (
            self._accounts_loaded and self._approvers_loaded and
            bool(self._account_uids) and bool(self._approver_uids)
        )
        self._update_status()
        self._update_controls()

    def _update_status(self):
        saved_message = ""
        save_hint = ""
        if not self._accounts_loaded or not self._approvers_loaded:
            message = m.LOADING_ACCOUNTS
        elif not self._account_uids:
            message = m.NO_LOCAL_STANDARD_ACCOUNTS_ARE_AVAILABLE_CREATE_ONE_THEN_REOPEN
        elif not self._approver_uids:
            message = m.NO_LOCAL_INTERACTIVE_ADMINISTRATOR_ACCOUNTS_ARE_AVAILABLE
        elif self._screen_time_limit_enabled is None:
            message = m.LOADING_REQUEST_DETAILS
        elif self._screen_time_limit_enabled is False:
            message = m.SCREEN_LIMIT_IS_NOT_ENABLED_IN_PARENT_APP
        elif not self._controls_enabled:
            message = (m.UPDATING_APPROVED_TIME if self._grant_state == "pending"
                       else m.WAITING_FOR_APPROVAL)
        elif self._grant_state in {"busy", "pending", "recovery"}:
            message = GRANT_STATUS_TEXT[self._grant_state]
        elif self._validation_error:
            message = self._validation_error
        elif self._grant_feedback:
            message = self._grant_feedback
        else:
            try:
                _uid, _child, _approver, seconds, _soft = self.selected()
            except ValueError as error:
                message = error.args[0]
            else:
                message = self._time_estimate
                if message is None and self._grant_state == "loading":
                    message = m.LOADING_TIME_STATUS
                view = self._grant_view
                if view is not None:
                    if view.saved_seconds:
                        saved_message = m.ALREADY_SAVED % {"duration": format_duration(view.saved_seconds)}
                    if seconds and seconds == view.requested_seconds:
                        if view.immediate_estimate:
                            message = m.ESTIMATED_REMAINING_TIME_FORMAT_DURATION_SECONDS_S % {
                                "format_duration_seconds": format_duration(view.immediate_estimate)}
                        save_hint = (m.SAVED_IF_APPROVED % {"duration": format_duration(view.deferred_estimate)}
                                     if view.deferred_estimate else m.REQUEST_UNAVAILABLE)
                    elif seconds:
                        save_hint = m.LOADING_TIME_STATUS
        if self._ui_duration_value() == "0":
            save_hint = m.REST_OF_DAY_CANNOT_BE_SAVED
        elif self._validation_error is None and self._grant_state == "unavailable":
            save_hint = m.TIME_STATUS_UNAVAILABLE
        if message is None:
            message = m.ESTIMATED_REMAINING_TIME_FORMAT_DURATION_SECONDS_S % {
                'format_duration_seconds': '',
            }
        set_text(self._status, 'label', message)
        set_text(self._already_saved, "label", saved_message)
        self._already_saved.set_visible(bool(saved_message))
        set_text(self._save_hint, "label", save_hint)
        self._save_hint.set_visible(bool(save_hint))
        if self._validation_error and message == self._validation_error:
            self._status.add_css_class("oh-no-parent-control-error")
        else:
            self._status.remove_css_class("oh-no-parent-control-error")

    def time_estimate_selection(self):
        """Return a valid, enabled request's identity and duration, or None."""
        if self._screen_time_limit_enabled is not True:
            return None
        try:
            uid, _label, _approver, seconds, _soft = self.selected()
        except ValueError:
            return None
        return uid, seconds

    def grant_status_selection(self):
        if self._screen_time_limit_enabled is not True:
            return None
        account = self.selected_child_account()
        if account is None:
            return None
        estimate = self.time_estimate_selection()
        return account[0], estimate[1] if estimate is not None else 0

    def set_time_estimate(self, message):
        self._time_estimate = message
        self._update_status()

    def _account_changed(self, *_args):
        index = self._accounts.get_selected()
        if (self._accounts_loaded and index < len(self._account_uids)
                and self._selection_store and not self._lock_child_selector):
            self._selection_store.remember("child_uid", self._account_uids[index])
        if self._accounts_loaded and index < len(self._account_uids):
            self._screen_time_limit_enabled = None
            self._validation_error = None
            self._time_estimate = None
            self._grant_state = "unavailable"
            self._grant_view = None
            self.set_grant_feedback(None)
            self._update_ready()
            if self._on_account_selected is not None:
                self._on_account_selected(self._account_uids[index])

    def _toggle_allow_soft(self, _button):
        if not self._allow_soft.get_sensitive():
            return
        self._allow_soft.set_active(not self._allow_soft.get_active())

    def _approver_changed(self, *_args):
        if not self._suppress_values_changed and self._selection_store:
            uid = self.selected_approver_uid()
            if uid:
                self._selection_store.remember("approver_uid", uid)
        self._emit_values_changed()

    def _emit_values_changed(self, *_args):
        if self._suppress_values_changed:
            return
        self._validation_error = None
        if self._grant_feedback:
            self.set_grant_feedback(None)
        self._update_save_control()
        self._update_status()
        if self._on_values_changed is not None:
            self._on_values_changed()

    def muted_for_surface(self, surface):
        return self._child_muted if surface == "child" else self._kiosk_muted

    def selected_approver_uid(self):
        index = self._approvers.get_selected()
        if index >= len(self._approver_uids):
            return 0
        return self._approver_uids[index]

    def selected_child_account(self):
        index = self._accounts.get_selected()
        if index >= len(self._account_uids):
            return None
        return (self._account_uids[index], self._account_labels[index],
                self._account_icons[index])

    def _restore_approver(self):
        if not self._approvers_loaded or not self._approver_uids:
            return
        self._suppress_values_changed = True
        try:
            preferred = (self._selection_store.preferred("approver_uid")
                         if self._selection_store else self._pending_approver_uid)
            if preferred in self._approver_uids:
                self._approvers.set_selected(
                    self._approver_uids.index(preferred),
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
            self._select_custom_unit(request.get("last_custom_unit", "minutes"))
            selected_value = request.get("last_selected_duration", str(DEFAULT_DURATION_SECONDS))
            self.set_time_grant_presets(preferences.get('personal', {}).get(
                'time_grant_presets', list(DEFAULT_TIME_GRANT_PRESETS)), selected_value=selected_value)
            selected_seconds = None if selected_value == "custom" else int(selected_value)
            selected = next(
                (button for button in self._duration_buttons
                 if button.duration_seconds == selected_seconds), None,
            )
            if selected is None:
                selected = next(button for button in self._duration_buttons
                                if button.duration_seconds is None)
            selected.set_active(True)
            self._custom_row.set_visible(selected.duration_seconds is None)
            custom = (selected_seconds / 60 if selected_seconds not in (None, 0)
                      and selected.duration_seconds is None else
                      request.get("last_custom_minutes", MIN_CUSTOM_MINUTES))
            if self._custom_unit == "hours":
                custom /= 60
            if isinstance(custom, float) and custom.is_integer():
                custom = int(custom)
            set_text(self._custom_entry, 'text', str(custom))
            self._allow_soft.set_active(bool(request.get("allow_soft_blocked_apps", False)))
            self._pending_approver_uid = request.get("last_selected_approver_uid", 0)
            self._kiosk_muted = bool(request.get("kiosk_muted", True))
            self._child_muted = bool(request.get("child_muted", True))
            self._restore_approver()
            self._update_ready()
        finally:
            self._suppress_values_changed = False

    def set_time_grant_presets(self, presets, *, selected_value=None):
        """Rebuild from backend choices, retaining an unsaved request exactly."""
        selected_value = selected_value or self._ui_duration_value()
        values = time_grant_choices(presets)
        # A deleted remembered preset remains a valid request. Represent it in
        # Custom value rather than silently changing the requested duration.
        missing = selected_value is not None and selected_value not in values
        suppressed = self._suppress_values_changed
        self._suppress_values_changed = True
        try:
            for button in self._duration_buttons:
                self._duration_box.remove(button.get_parent())
            self._duration_buttons.clear()
            self._build_duration_choices(tuple(
                (_duration_label(None if value == 'custom' else int(value)),
                 None if value == 'custom' else int(value)) for value in values))
            selected = 'custom' if missing else selected_value
            if selected is None:
                selected = str(DEFAULT_DURATION_SECONDS) if str(DEFAULT_DURATION_SECONDS) in values else 'custom'
            next(button for button in self._duration_buttons
                 if ('custom' if button.duration_seconds is None else str(button.duration_seconds))
                 == selected).set_active(True)
            if missing:
                divisor = 3600 if self._custom_unit == "hours" else 60
                self._custom_entry.set_text(str(int(selected_value) / divisor))
            self._custom_row.set_visible(selected == 'custom')
            self._update_controls()
        finally:
            self._suppress_values_changed = suppressed

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

    def _ui_duration_value(self):
        for button in self._duration_buttons:
            if button.get_active():
                return "custom" if button.duration_seconds is None else str(button.duration_seconds)
        return ""

    def _ui_select_duration(self, value):
        for button in self._duration_buttons:
            identity = "custom" if button.duration_seconds is None else str(button.duration_seconds)
            if value == identity:
                if not button.is_sensitive():
                    raise ValueError("request duration is unavailable")
                if not button.get_active():
                    button.emit("clicked")
                return
        raise ValueError("unknown request duration")

    @staticmethod
    def _ui_set_duration_button(button, value):
        if type(value) is not bool:
            raise ValueError("duration choice requires a boolean")
        if value != button.get_active():
            if not value:
                raise ValueError("select another duration instead of clearing the active choice")
            button.emit("clicked")

    def custom_unit(self):
        return self._custom_unit

    def _custom_unit_toggled(self, button, unit):
        if button.get_active() and self._custom_unit != unit:
            self._custom_unit = unit
            self._emit_values_changed()

    def _select_custom_unit(self, unit):
        if unit not in {"minutes", "hours"}:
            raise ValueError("unknown custom duration unit")
        self._unit_buttons[unit].set_active(True)

    def selected(self):
        account_index = self._accounts.get_selected()
        if not self._ready or account_index >= len(self._account_uids):
            raise ValueError(m.SELECT_ACCOUNT)
        approver_index = self._approvers.get_selected()
        if approver_index >= len(self._approver_uids):
            raise ValueError(m.SELECT_ADMINISTRATOR)
        selected = next(
            (button for button in self._duration_buttons if button.get_active()), None
        )
        if selected is None:
            raise ValueError(m.SELECT_DURATION)
        seconds = selected.duration_seconds
        if seconds is None:
            text = self._custom_entry.get_text().strip()
            minutes = float(text) if NUMBER_RE.fullmatch(text) else math.nan
            if self._custom_unit == "hours":
                minutes *= 60
            if not math.isfinite(minutes) or not MIN_CUSTOM_MINUTES <= minutes <= MAX_CUSTOM_MINUTES:
                raise ValueError(
                    duration_range_message(MIN_CUSTOM_MINUTES * 60, MAX_CUSTOM_MINUTES * 60,
                                           self._custom_unit) if self._custom_unit == 'hours' else
                    m.INVALID_REQUEST_MINUTES % {'minimum': MIN_CUSTOM_MINUTES, 'maximum': MAX_CUSTOM_MINUTES}
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
            raise ValueError(m.SELECT_DURATION)
        selected_value = "custom" if selected.duration_seconds is None else str(
            selected.duration_seconds
        )
        text = self._custom_entry.get_text().strip()
        custom = float(text) if NUMBER_RE.fullmatch(text) else MIN_CUSTOM_MINUTES
        if self._custom_unit == "hours" and NUMBER_RE.fullmatch(text):
            custom *= 60
        return selected_value, custom, self._allow_soft.get_active()

    def show_validation_error(self, message):
        self._validation_error = message
        self._update_status()

    def clear_validation_error(self):
        """Restore the normal request-form status after a silent cancellation."""
        self._validation_error = None
        self._update_ready()

    def set_controls_sensitive(self, enabled):
        self._controls_enabled = enabled
        self._update_controls()
        self._update_status()

    def can_cancel(self):
        return self._cancel.is_sensitive()

    def _update_save_control(self):
        choice = self.time_estimate_selection()
        view = self._grant_view
        save_allowed = (self._request.get_sensitive() and self._grant_state == "ready"
                        and self._ui_duration_value() != "0" and self._grant_actions.get("save_for_later")
                        and (choice is None or (
                            choice[1] == view.requested_seconds and view.deferred_estimate > 0)))
        self._save_for_later.set_sensitive(bool(save_allowed))

    def _update_controls(self):
        """Apply request availability while always preserving the exit path."""
        navigation = self._controls_enabled and self._grant_state not in {"busy", "pending"}
        request_available = (
            self._controls_enabled and self._ready and
            self._screen_time_limit_enabled is True and
            self._grant_state not in {"busy", "pending", "recovery"}
        )
        self._request.set_sensitive(request_available)
        self._request_menu.set_sensitive(request_available)
        self._request_more.set_sensitive(navigation and self._screen_time_limit_enabled is True)
        if not request_available:
            self._request_menu.popdown()
        self._cancel.set_sensitive(self._controls_enabled and self._grant_state != "pending")
        self._tab_bar.set_sensitive(navigation)
        for button in self._tabs.values():
            button.set_sensitive(navigation)
        accounts_enabled = navigation and not self._lock_child_selector
        self._accounts.set_interaction_enabled(accounts_enabled)
        # Expose the effective locked state on the actionable descendant too.
        # AT-SPI reports a widget's own state rather than inferring sensitivity
        # from a disabled ancestor, so disabling only the selector container
        # made the child-overlay trigger appear interactive to assistive tools.
        if not accounts_enabled:
            self._accounts.collapse()
        self._custom_entry.set_sensitive(request_available)
        self._unit_selector.set_sensitive(request_available)
        self._allow_soft.set_sensitive(request_available)
        self._filter_row.set_sensitive(request_available)
        self._approvers.set_sensitive(request_available)
        if not request_available:
            self._approvers.collapse()
        for button in self._duration_buttons:
            button.set_sensitive(request_available)
        self._screen_limit_notice.set_visible(
            self._screen_time_limit_enabled is False
        )
        self._update_save_control()
        self._render_approved()
