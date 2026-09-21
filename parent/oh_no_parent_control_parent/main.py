"""Administrator-facing GTK 4/libadwaita parent-control application."""

from __future__ import annotations

import argparse
import hashlib
from common.oh_no_parent_control_ui.diagnostic_events import get_logger, error_code
from common.oh_no_parent_control_ui.diagnostic_events import configure_console, log_version
import os
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from common.oh_no_parent_control_ui.about import (
    AboutDialog, app_name, branding_asset_path, open_help,
)
from common.oh_no_parent_control_ui.accessibility import (
    add_dialog_button,
    add_identified_window_controls,
    describe_control,
    set_automation_id,
)
from common.oh_no_parent_control_ui.duration import format_duration
from common.oh_no_parent_control_ui.app_policy import replacement_policy_ids
from common.oh_no_parent_control_ui.feedback import FeedbackDialog
from common.oh_no_parent_control_ui.errors import (
    ErrorHandler, GENERIC_TITLE, GENERIC_DETAIL, install_exception_hooks,
    show_startup_error,
)
from common.oh_no_parent_control_ui.user_icon import parse_listed_user

from .client import BrokerClient, configure_logging, management_access_denied

LOG = get_logger("parent")
APPLICATION_ICON_NAME = "com.puffyslippers.OhNoParentControl"
STATES = (
    {
        "id": "allowed",
        "label": "Always Allowed",
        "icon": "emblem-ok-symbolic",
        "css": "policy-allowed",
    },
    {
        "id": "permanent",
        "label": "Hard Blocked",
        "icon": "window-close-symbolic",
        "css": "policy-hard-blocked",
    },
    {
        "id": "conditional",
        "label": "Soft Blocked",
        "icon": "dialog-warning-symbolic",
        "css": "policy-soft-blocked",
    },
)
# The app-list selector and legend present blocked states from softer to harder.
# Keep STATES unchanged because its order is also used by access-rule filters.
APP_LIST_STATES = (STATES[0], STATES[2], STATES[1])
MATCH_RULES = (
    {
        "id": "pattern",
        "label": "Pattern Match",
        "glyph": "***",
        "css": "match-rule-pattern",
        "description": "Matches versioned filenames using a wildcard.",
    },
    {
        "id": "precise",
        "label": "Precise execution path",
        "glyph": "ABC",
        "css": "match-rule-precise",
        "description": "Matches only this exact executable path.",
    },
)
MAX_DAILY_LIMIT_MINUTES = 24 * 60
MAX_CUSTOM_DAILY_LIMIT_MINUTES = MAX_DAILY_LIMIT_MINUTES - 1
DAILY_LIMIT_PRESETS = (0, 15, 30, 45, *range(60, MAX_DAILY_LIMIT_MINUTES, 30))
CUSTOM_DAILY_LIMIT_INDEX = len(DAILY_LIMIT_PRESETS)
CONTENT_MAX_WIDTH = 1046
# The major surfaces use a 24 px horizontal margin on either side.  Start the
# window at that natural content width rather than showing a wide empty gutter
# around the clamped column.
DEFAULT_WINDOW_WIDTH = CONTENT_MAX_WIDTH + 2 * 24
TIME_STATUS_RETRY_DELAY_SECONDS = 1
MAX_TIME_STATUS_RETRIES = 3
ACCOUNT_REFRESH_SECONDS = 5
CUSTOM_DAILY_LIMIT_SAVE_DELAY_MS = 350
# Building every app row on the GTK thread in one burst freezes the window.
# Yield between small batches so the App Limits tab can switch immediately
# and the loading mask can keep animating.
CATALOG_ROW_BATCH_SIZE = 8

def _minutes_label(minutes):
    return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"


def _daily_limit_label(minutes):
    """Format the compact set of daily allowance menu choices."""
    if minutes < 60:
        return _minutes_label(minutes)
    hours = minutes / 60
    return f"{hours:g} hour" if hours == 1 else f"{hours:g} hours"


def _daily_limit_selection(minutes):
    """Return the menu index for a stored allowance and whether it is custom."""
    try:
        return DAILY_LIMIT_PRESETS.index(minutes), False
    except ValueError:
        return CUSTOM_DAILY_LIMIT_INDEX, True


def _time_status_subtitle(status):
    grant = format_duration(status["one_time_grant_remaining_seconds"])
    daily = format_duration(status["daily_allowance_remaining_seconds"])
    remaining = format_duration(status["calculated_active_extension_seconds"])
    return (
        f"Daily allowance remaining: <b>{daily}</b>\n"
        f"One-time grant remaining: <b>{grant}</b>\n"
        f"<b>Remaining time: {remaining}</b> — the larger of the two amounts."
    )


def _app_automation_key(app_id):
    """Return a stable, non-identifying ID fragment for a launcher identity."""
    return hashlib.sha256(app_id.encode("utf-8")).hexdigest()[:16]


class DailyLimitPopover(Gtk.Popover):
    """Keep the scrollable allowance menu beside its button on short windows."""

    _height_limit = None

    def prepare(self, button):
        # MenuButton calls this before presenting the native popup, including
        # subsequent opens after a window resize or a page scroll. Constrain
        # the complete popup (arrow, CSS, fixed footer and scrolling choices)
        # before the compositor places it; compositor resizing alone can put
        # an oversized popup at the screen edge with its arrow detached.
        root = button.get_root()
        valid, bounds = button.compute_bounds(root)
        if not valid or root.get_height() <= 0:
            return
        above = bounds.get_y()
        below = root.get_height() - bounds.get_y() - bounds.get_height()
        self._height_limit = max(0, int(max(above, below)) - 8)
        self.set_position(Gtk.PositionType.TOP if above > below else Gtk.PositionType.BOTTOM)
        self.queue_resize()
        LOG.debug(
            "parent.001",
            side=self.get_position().value_nick,
            available_height=self._height_limit,
        )

    def do_measure(self, orientation, for_size):
        minimum, natural, minimum_baseline, natural_baseline = Gtk.Popover.do_measure(
            self, orientation, for_size,
        )
        if orientation == Gtk.Orientation.VERTICAL and self._height_limit is not None:
            natural = max(minimum, min(natural, self._height_limit))
        return minimum, natural, minimum_baseline, natural_baseline


class ParentAccountSelector(Gtk.MenuButton):
    """ID-addressable child selector without GTK's anonymous list rows."""

    def __init__(self, on_selected):
        super().__init__(
            hexpand=True, valign=Gtk.Align.CENTER,
            css_classes=["account-picker"],
        )
        self._on_selected = on_selected
        self._users = ()
        self._selected = Gtk.INVALID_LIST_POSITION
        self._choices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        choices_scroll = Gtk.ScrolledWindow(
            child=self._choices, propagate_natural_height=True,
            max_content_height=420, hscrollbar_policy=Gtk.PolicyType.NEVER,
        )
        set_automation_id(choices_scroll, "parent-child-choices")
        popover = Gtk.Popover(child=choices_scroll)
        set_automation_id(popover, "parent-child-popover")
        self.set_popover(popover)
        self._show_selection()

    @staticmethod
    def _content(label, icon_file, automation_id):
        row = Gtk.Box(spacing=14, valign=Gtk.Align.CENTER)
        set_automation_id(row, automation_id)
        avatar = Adw.Avatar(
            size=50, show_initials=True, text=label,
            css_classes=["account-avatar"],
        )
        texture = None
        if icon_file:
            try:
                texture = Gdk.Texture.new_from_filename(icon_file)
            except GLib.Error:
                pass
        avatar.set_custom_image(texture)
        row.append(avatar)
        row.append(Gtk.Label(
            label=label, xalign=0, hexpand=True, ellipsize=3,
            css_classes=["account-name"],
        ))
        return row

    def set_users(self, users, selected):
        users = tuple(users)
        if len({uid for uid, _label, _icon in users}) != len(users):
            raise ValueError("child selector requires unique account UIDs")
        self._users = users
        while child := self._choices.get_first_child():
            self._choices.remove(child)
        focus_actions = Gio.SimpleActionGroup()
        for index, (uid, label, icon_file) in enumerate(users):
            choice = Gtk.Button(
                child=self._content(
                    label, icon_file, f"parent-child-choice-{uid}-content",
                ),
                css_classes=["parent-account-choice"],
            )
            describe_control(
                choice, f"Child account: {label}",
                f"Manage screen time and app policy for {label}.",
                automation_id=f"parent-child-choice-{uid}",
            )
            target = choice.weak_ref()
            focus_action = Gio.SimpleAction.new(f"focus-{uid}", None)

            def focus(_action, _parameter, target=target):
                button = target()
                if (button is not None and button.is_sensitive() and button.is_visible()
                        and button.get_mapped() and button.get_root() is not None
                        and button.get_root().is_active()):
                    button.grab_focus()

            focus_action.connect("activate", focus)
            focus_actions.add_action(focus_action)
            choice.connect("clicked", self._choose, index)
            self._choices.append(choice)
        # GtkMenuButton exposes inserted actions through its public AT-SPI
        # Action interface. UID-scoped focus actions let automation focus an
        # identified choice without deriving keyboard input from list order.
        self.insert_action_group("child", focus_actions)
        self._selected = (
            selected if users and 0 <= selected < len(users)
            else Gtk.INVALID_LIST_POSITION
        )
        self._show_selection()

    def get_selected(self):
        return self._selected

    def _choose(self, _button, selected):
        if selected == self._selected:
            self.popdown()
            return
        self._selected = selected
        self._show_selection()
        self.popdown()
        self._on_selected()

    def _show_selection(self):
        if self._selected < len(self._users):
            uid, label, icon_file = self._users[self._selected]
            content = self._content(
                label, icon_file, f"parent-child-selected-{uid}",
            )
            description = f"Selected child: {label}."
        else:
            content = Gtk.Label(label="(None)", xalign=0, hexpand=True)
            set_automation_id(content, "parent-child-selected-none")
            description = "No child account is selected."
        self.set_child(content)
        describe_control(self, "Selected child", description)


class ParentWindow(Adw.ApplicationWindow):
    def __init__(self, application, *, client_factory=BrokerClient):
        super().__init__(application=application, title=app_name())
        set_automation_id(self, "parent-window")
        # The application ID ends in ``.Parent``, but the shared installed
        # desktop icon uses the product-wide name.
        self.set_icon_name(APPLICATION_ICON_NAME)
        self.set_default_size(DEFAULT_WINDOW_WIDTH, 1168)
        # Both pages scroll; let shorter logical displays shrink the window
        # instead of forcing its lower controls off-screen.
        self.set_size_request(820, -1)
        self._client = client_factory()
        self._users = []
        self._users_loaded_once = False
        self._users_loading = False
        self._user_discovery_error_reported = False
        self._policy_warnings_loading = False
        self._policy_warnings_closed = False
        self._policy_warning_query_failed = False
        self._reported_policy_warnings = {}
        self._preferences = None
        self._rows = []
        self._loading = False
        self._save_in_progress = False
        self._pending_saves = []
        self._restore_preferences_uid = None
        self._custom_daily_limit_save_id = 0
        self._time_status_loading = False
        self._time_status_refresh_pending = False
        self._time_status_retry_id = 0
        self._time_status_retry_count = 0
        self._remaining_time_seconds = None
        self._app_catalog = None
        self._app_catalog_uid = None
        self._apps_loading = False
        self._apps_load_uid = None
        self._apps_load_generation = 0
        self._apps_table_ready = False
        self._catalog_building = False
        self._catalog_build_generation = 0
        self._pending_catalog_apps = []
        self._app_limits_visible = False
        self._match_rule_filters = {rule["id"] for rule in MATCH_RULES}
        self._access_rule_filters = {state["id"] for state in STATES}
        self._build()
        self._time_status_refresh_id = GLib.timeout_add_seconds(
            30, self._refresh_time_status,
        )
        self._account_refresh_id = GLib.timeout_add_seconds(
            ACCOUNT_REFRESH_SECONDS, self._refresh_users,
        )
        self.connect("close-request", self._close_requested)
        LOG.info("parent.002", app_count=len(self._rows))
        GLib.idle_add(self._load_users)

    def _build(self):
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar(css_classes=["parent-header"])
        # Let the title shift when the trailing actions need more room, so the
        # feedback button does not force it into a narrow symmetric allocation.
        header.set_centering_policy(Adw.CenteringPolicy.LOOSE)
        add_identified_window_controls(header, "parent-window-controls")
        # Use a title-bar-specific raster at its native display size. Shrinking
        # the detailed 512 px launcher artwork here makes its fine neon edges
        # visibly soft, while the pre-rendered asset stays crisp at 48 px.
        title_brand = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
            valign=Gtk.Align.CENTER,
            css_classes=["parent-title-brand"],
        )
        title_logo = Gtk.Image.new_from_file(
            str(branding_asset_path("app_logo_titlebar.png")),
        )
        title_logo.set_pixel_size(48)
        title_logo.update_property(
            [Gtk.AccessibleProperty.LABEL], [f"{app_name()} logo"],
        )
        title_brand.append(title_logo)
        title_brand.append(Adw.WindowTitle(
            title=app_name(), css_classes=["parent-window-title"],
        ))
        header.set_title_widget(title_brand)
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, width_request=190)
        popover = Gtk.Popover(child=menu, css_classes=["parent-menu-popover"])
        # Explicit buttons expose the same accessible labels as their visible
        # text, including on GTK versions with unnamed model-menu items.
        def activate_menu_item(_button, callback):
            popover.popdown()
            callback()

        for identity, label, callback in (
            ("help", "Help", open_help),
            ("about", "About", self._show_about),
        ):
            item = Gtk.Button(child=Gtk.Label(label=label, xalign=0),
                              css_classes=["parent-menu-item"])
            describe_control(item, label, label,
                             automation_id=f"parent-menu-{identity}")
            item.connect("clicked", activate_menu_item, callback)
            menu.append(item)
        # Explicit circular dots keep the heavier ellipsis consistent across
        # icon themes and display scales.
        dots = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3,
                       halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        for _ in range(3):
            dots.append(Gtk.Box(css_classes=["parent-menu-dot"]))
        self._menu_button = Gtk.MenuButton(
            child=dots,
            valign=Gtk.Align.CENTER,
            popover=popover,
            tooltip_text="Menu",
            css_classes=["parent-header-menu"],
        )
        describe_control(
            self._menu_button, "Parent app menu",
            "Open help and view product information.",
            automation_id="parent-menu-button",
        )
        # Keep native window actions and the desktop's decoration layout, with
        # the application menu immediately before the window controls.
        header_actions = Gtk.Box(spacing=4, valign=Gtk.Align.CENTER)
        feedback_content = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)
        feedback_content.append(Gtk.Image(
            icon_name="chat-message-new-symbolic", pixel_size=20,
        ))
        feedback_content.append(Gtk.Label(label="Feedback"))
        feedback_button = Gtk.Button(
            child=feedback_content, css_classes=["parent-header-feedback"],
            valign=Gtk.Align.CENTER,
        )
        describe_control(feedback_button, "Feedback", "Send feedback about the app.",
                         automation_id="parent-feedback-button")
        feedback_button.connect("clicked", lambda _button: self._show_feedback())
        header_actions.append(feedback_button)
        header_actions.append(self._menu_button)
        header.pack_end(header_actions)
        toolbar.add_top_bar(header)
        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["preferences-page"],
        )
        toolbar.set_content(content)
        self._policy_warning = Gtk.Label(
            wrap=True, xalign=0, visible=False,
            margin_start=18, margin_end=18, margin_top=8, margin_bottom=8,
            css_classes=["warning"],
        )
        set_automation_id(self._policy_warning, "parent-policy-warning")
        toolbar.add_top_bar(self._policy_warning)
        self._toasts = Adw.ToastOverlay(child=toolbar)
        self.set_content(self._toasts)

        # The selected child applies to both tabs. Keep the picker outside the
        # stack and use the same clamp as the tab bar and both page cards so
        # every major surface shares one visual column.
        account_section = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            hexpand=True,
            css_classes=["account-section"],
        )
        account_label = Gtk.Label(
            label="Child account", xalign=0, css_classes=["section-title"],
        )
        account_section.append(account_label)
        account_actions = Gtk.Box(
            hexpand=True,
            css_classes=["account-actions"],
        )
        self._account = ParentAccountSelector(self._account_changed)
        describe_control(
            self._account, "Selected child",
            "Choose the child whose screen time and app policy are displayed.",
            automation_id="parent-child-selector",
        )
        # A DropDown's visible selection is its AT-SPI name.  Connect the
        # enduring section label as well, so assistive technology identifies
        # the control's purpose independently of the selected child.
        account_label.set_mnemonic_widget(self._account)
        account_actions.append(self._account)
        account_actions.append(Gtk.Separator(
            orientation=Gtk.Orientation.VERTICAL,
            valign=Gtk.Align.CENTER,
            css_classes=["account-actions-separator"],
        ))
        revoke_content = Gtk.Box(
            spacing=16, valign=Gtk.Align.CENTER,
            css_classes=["revoke-grant-content"],
        )
        revoke_icon = Gtk.Image(
            icon_name="action-unavailable-symbolic", pixel_size=40,
            css_classes=["revoke-grant-icon"],
        )
        revoke_content.append(revoke_icon)
        revoke_labels = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=3,
            valign=Gtk.Align.CENTER, hexpand=True,
        )
        revoke_labels.append(Gtk.Label(
            label="Revoke one-time grant", xalign=0,
            css_classes=["revoke-grant-title"],
        ))
        self._revoke_description = Gtk.Label(
            label="Revokes one-time screen time and app access grants.",
            xalign=0, wrap=True, width_request=270, max_width_chars=36,
            css_classes=["revoke-grant-description"],
        )
        revoke_labels.append(self._revoke_description)
        revoke_content.append(revoke_labels)
        revoke_content.append(Gtk.Label(
            label="Revoke", valign=Gtk.Align.CENTER,
            css_classes=["revoke-grant-action"],
        ))
        self._revoke = Gtk.Button(
            child=revoke_content, valign=Gtk.Align.FILL,
            width_request=320, css_classes=["revoke-grant-button"],
            sensitive=False,
        )
        describe_control(
            self._revoke, "Revoke one-time access",
            "Remove the selected child's active one-time grant after confirmation.",
            automation_id="parent-revoke-button",
        )
        self._revoke.connect("clicked", self._confirm_revoke)
        account_actions.append(self._revoke)
        account_section.append(account_actions)
        self._no_users_message = Gtk.Label(
            label="No interactive non-administrator account was found.",
            xalign=0, wrap=True, visible=False,
            css_classes=["account-empty-message"],
        )
        set_automation_id(self._no_users_message, "parent-no-users-message")
        account_section.append(self._no_users_message)
        content.append(Adw.Clamp(
            child=account_section,
            maximum_size=CONTENT_MAX_WIDTH,
            tightening_threshold=CONTENT_MAX_WIDTH,
            css_classes=["account-clamp"],
        ))

        pages = Adw.ViewStack(vexpand=True)
        self._pages = pages
        switcher = Gtk.Box(
            homogeneous=True, hexpand=True,
            css_classes=["main-view-switcher"],
        )
        first_page_button = None
        for page_name, label, icon_name in (
            ("screen-limits", "Screen Limits", "alarm-symbolic"),
            ("app-limits", "App Limits", "view-grid-symbolic"),
        ):
            button = Gtk.ToggleButton(
                child=Gtk.Box(spacing=8, halign=Gtk.Align.CENTER),
                hexpand=True,
            )
            button.get_child().append(Gtk.Image(icon_name=icon_name))
            button.get_child().append(Gtk.Label(label=label))
            describe_control(
                button, label, f"Show the {label} page.",
                automation_id=f"parent-page-{page_name}",
            )
            if first_page_button is None:
                first_page_button = button
                button.set_active(True)
            else:
                button.set_group(first_page_button)
            button.connect(
                "toggled",
                lambda control, name=page_name: (
                    pages.set_visible_child_name(name) if control.get_active() else None
                ),
            )
            switcher.append(button)
        content.append(Adw.Clamp(
            child=switcher,
            maximum_size=CONTENT_MAX_WIDTH,
            tightening_threshold=CONTENT_MAX_WIDTH,
            css_classes=["switcher-clamp"],
        ))
        content.append(pages)

        screen_limits_page = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            css_classes=["limits-page"],
        )
        set_automation_id(screen_limits_page, "parent-screen-limits-page")
        pages.add_titled_with_icon(
            screen_limits_page, "screen-limits", "Screen Limits", "alarm-symbolic",
        )

        screen_limits = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["screen-limits-card"],
        )
        screen_limit_rows = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.NONE,
            css_classes=["screen-limit-rows"],
        )
        control_row = Adw.ActionRow(
            title="Screen Time Limit",
            subtitle="Turn on / off screen time limit",
            css_classes=["screen-limit-toggle-row"],
        )
        control_row.add_prefix(self._setting_icon("alarm-symbolic"))
        self._enabled = Gtk.Switch(
            valign=Gtk.Align.CENTER,
            sensitive=False,
            css_classes=["screen-limit-switch"],
        )
        describe_control(
            self._enabled, "Screen time limit",
            "Enable or disable daily screen-time control for the selected child.",
            automation_id="parent-screen-limit-toggle",
        )
        self._enabled.connect("notify::active", self._enabled_changed)
        control_row.add_suffix(self._enabled)
        screen_limit_rows.append(control_row)
        daily_limit_row = Adw.ActionRow(
            title="Daily Time Allowance",
            css_classes=["daily-limit-row"],
        )
        daily_limit_row.add_prefix(self._setting_icon("x-office-calendar-symbolic"))
        # Expose each choice as a named button in a Gtk.Popover. Gtk.DropDown
        # presents a combo-box role here but no AT-SPI selection or action
        # interface, which prevents assistive technology from selecting a
        # daily allowance.
        self._daily_limit_selected = 0
        self._daily_limit_choices = []
        self._daily_limit = Gtk.MenuButton(
            label=_daily_limit_label(0),
            css_classes=["daily-limit-button"],
        )
        self._daily_limit.set_sensitive(False)
        self._daily_limit.set_valign(Gtk.Align.CENTER)
        describe_control(
            self._daily_limit, "Daily time allowance",
            "Choose the selected child's daily screen-time allowance.",
            automation_id="parent-daily-limit-selector",
        )
        allowance_popover = self._daily_limit_popover()
        self._daily_limit.set_popover(allowance_popover)
        self._daily_limit.set_create_popup_func(allowance_popover.prepare)
        daily_limit_row.add_suffix(self._daily_limit)
        screen_limit_rows.append(daily_limit_row)
        self._custom_daily_limit = Adw.ActionRow(
            title="Custom daily allowance",
            subtitle="Enter a whole number from 0 to 1439.",
            visible=False,
            css_classes=["custom-daily-limit-row"],
        )
        self._custom_daily_limit_entry = Gtk.Entry(
            text="30",
            input_purpose=Gtk.InputPurpose.DIGITS,
            width_chars=5,
            max_width_chars=5,
            valign=Gtk.Align.CENTER,
        )
        describe_control(
            self._custom_daily_limit_entry, "Custom daily allowance",
            "Enter a whole number of minutes from zero through 1439.",
            automation_id="parent-custom-daily-limit",
        )
        self._custom_daily_limit_entry.connect(
            "activate", self._custom_daily_limit_changed,
        )
        self._custom_daily_limit_entry.connect(
            "changed", self._custom_daily_limit_text_changed,
        )
        custom_daily_limit_focus = Gtk.EventControllerFocus.new()
        custom_daily_limit_focus.connect("leave", self._custom_daily_limit_changed)
        self._custom_daily_limit_entry.add_controller(custom_daily_limit_focus)
        self._custom_daily_limit.add_suffix(self._custom_daily_limit_entry)
        self._custom_daily_limit.add_suffix(Gtk.Label(label="minutes"))
        screen_limit_rows.append(self._custom_daily_limit)
        self._time_status = Adw.ExpanderRow(
            title="Today's Remaining Time",
            subtitle="Time left for today",
            expanded=True,
            css_classes=["time-status-row"],
        )
        describe_control(
            self._time_status, "Today's remaining time",
            "Expand or collapse the daily and one-time remaining-time calculation.",
            automation_id="parent-time-status",
        )
        self._time_status.add_prefix(self._setting_icon("hourglass-symbolic"))
        self._time_status_value = Gtk.Label(
            label="Loading…", valign=Gtk.Align.CENTER,
            css_classes=["remaining-time-value"],
        )
        set_automation_id(self._time_status_value, "parent-time-remaining")
        self._time_status.add_suffix(self._time_status_value)
        self._time_status.add_row(self._time_calculation_panel())
        screen_limit_rows.append(self._time_status)
        screen_limits.append(screen_limit_rows)

        screen_limits_page.set_child(Adw.Clamp(
            child=screen_limits,
            maximum_size=CONTENT_MAX_WIDTH,
            tightening_threshold=CONTENT_MAX_WIDTH,
            css_classes=["screen-limits-clamp"],
        ))

        app_limits_page = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            css_classes=["app-limits-page"],
        )
        set_automation_id(app_limits_page, "parent-app-limits-page")
        pages.add_titled_with_icon(
            app_limits_page, "app-limits", "App Limits", "view-grid-symbolic",
        )

        app_limits = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["app-limits-card"],
        )
        app_limits.append(self._legend_card())
        app_limits.append(Gtk.Separator(
            orientation=Gtk.Orientation.HORIZONTAL,
            css_classes=["app-limits-divider"],
        ))

        apps_section = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["apps-section"],
        )
        search_row = Gtk.Box(
            spacing=18, css_classes=["apps-panel-header"],
        )
        search_labels = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            hexpand=True, valign=Gtk.Align.CENTER,
        )
        search_labels.append(Gtk.Label(
            label="Installed apps", xalign=0,
            css_classes=["apps-panel-title"],
        ))
        search_labels.append(Gtk.Label(
            label="Desktop, AppImage, Flatpak, Snap, and system launchers",
            xalign=0, wrap=True,
            css_classes=["apps-panel-subtitle"],
        ))
        search_row.append(search_labels)
        self._search = Gtk.SearchEntry(
            placeholder_text="Search installed apps", valign=Gtk.Align.CENTER,
            width_chars=32, css_classes=["apps-search"],
        )
        describe_control(
            self._search, "Search installed apps",
            "Filter the selected child's available applications.",
            automation_id="parent-app-search",
        )
        self._search.connect("search-changed", self._filter)
        self._search.set_sensitive(False)
        search_row.append(self._search)
        apps_section.append(search_row)

        apps = Adw.PreferencesGroup(css_classes=["apps-panel"])
        self._apps_group = apps
        # PreferencesGroup places non-row widgets after its list. Keep the
        # headings in an ActionRow so they remain directly above app rows.
        # The trailing headings are overlaid on inert copies of the controls
        # below. This makes their columns use the same measurements as every
        # app row instead of letting the heading text determine the width.
        headers = Adw.ActionRow(css_classes=["app-policy-columns"])
        headers.add_prefix(Gtk.Label(label="Icon", xalign=0, hexpand=False,
                                     css_classes=["app-policy-column-header",
                                                  "app-policy-icon-header"]))
        headers.set_title("App Name &amp; Detail")
        headers.add_suffix(self._policy_column_heading(
            "Match Rule", self._match_rule_slot(), "match-rule-header",
            MATCH_RULES, self._match_rule_filters, self._match_rule_filter_icon,
            identity="match-rule"))
        headers.add_suffix(self._policy_column_heading(
            "Access Rule", self._policy_selector_slot(), "access-rule-header",
            STATES, self._access_rule_filters, self._access_rule_filter_icon,
            identity="access-rule"))
        apps.add(headers)
        self._app_rows = []
        apps_overlay = Gtk.Overlay(
            hexpand=True, vexpand=True, css_classes=["apps-table-overlay"],
        )
        apps_overlay.set_child(apps)
        loading_mask = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            hexpand=True, vexpand=True, visible=False, can_target=True,
            halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
            css_classes=["apps-loading-mask"],
        )
        loading_content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=14,
            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
            css_classes=["apps-loading-content"],
        )
        self._apps_loading_spinner = Gtk.Spinner(
            spinning=False, width_request=28, height_request=28,
            css_classes=["apps-loading-spinner"],
        )
        loading_content.append(self._apps_loading_spinner)
        loading_content.append(Gtk.Label(
            label="Loading installed apps…",
            css_classes=["apps-loading-label"],
        ))
        loading_center = Gtk.CenterBox(hexpand=True, vexpand=True)
        loading_center.set_center_widget(loading_content)
        loading_mask.append(loading_center)
        apps_overlay.add_overlay(loading_mask)
        self._apps_loading_mask = loading_mask
        apps_section.append(apps_overlay)
        app_limits.append(apps_section)
        app_limits_page.set_child(Adw.Clamp(
            child=app_limits,
            maximum_size=CONTENT_MAX_WIDTH,
            tightening_threshold=CONTENT_MAX_WIDTH,
            css_classes=["app-limits-clamp"],
        ))
        self._pages.connect("notify::visible-child-name", self._visible_page_changed)

    @staticmethod
    def _setting_icon(icon_name):
        container = Gtk.CenterBox(
            valign=Gtk.Align.CENTER,
            css_classes=["setting-icon"],
        )
        container.set_center_widget(Gtk.Image(
            icon_name=icon_name,
            pixel_size=22,
            valign=Gtk.Align.CENTER,
        ))
        return container

    def _time_calculation_panel(self):
        panel = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=8,
            css_classes=["calculation-panel"],
        )
        heading = Gtk.Box(spacing=10)
        heading.append(Gtk.Image(
            icon_name="accessories-calculator-symbolic", pixel_size=18,
            css_classes=["calculation-icon"],
        ))
        heading.append(Gtk.Label(
            label="How it's calculated", xalign=0, hexpand=True,
            css_classes=["calculation-title"],
        ))
        collapse = Gtk.Button(
            icon_name="go-up-symbolic",
            tooltip_text="Hide calculation",
            css_classes=["calculation-collapse"],
        )
        describe_control(
            collapse, "Hide remaining-time calculation",
            "Collapse the remaining-time calculation details.",
            automation_id="parent-time-calculation-collapse",
        )
        collapse.connect(
            "clicked", lambda *_args: self._time_status.set_expanded(False),
        )
        heading.append(collapse)
        panel.append(heading)

        self._time_explanation = Gtk.Label(
            label="—", xalign=0, wrap=True, use_markup=True,
            css_classes=["calculation-formula"],
        )
        set_automation_id(self._time_explanation, "parent-time-explanation")
        panel.append(self._time_explanation)
        return panel

    def _policy_column_heading(self, label, slot, css_class, items, selected,
                               icon_factory, *, identity):
        """Overlay a filter heading on a measurement-matched, inert policy control."""
        overlay = Gtk.Overlay(css_classes=["app-policy-heading", css_class])
        overlay.set_child(slot)
        trigger = Gtk.MenuButton(
            tooltip_text=f"Filter by {label}",
            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
            css_classes=["app-policy-filter"],
        )
        describe_control(
            trigger, f"Filter {label}",
            f"Choose which {label.casefold()} values are shown in the app list.",
            automation_id=f"parent-filter-{identity}",
        )
        trigger_content = Gtk.Box(
            spacing=4, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
        )
        trigger_content.append(Gtk.Label(
            label=label, css_classes=["app-policy-column-header"],
        ))
        trigger_content.append(Gtk.Image(
            icon_name="pan-down-symbolic", pixel_size=12,
            css_classes=["app-policy-filter-chevron"],
        ))
        trigger.set_child(trigger_content)
        popover = Gtk.Popover(
            autohide=True, has_arrow=True,
            css_classes=["app-policy-filter-popover"],
        )
        menu = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=2,
            css_classes=["app-policy-filter-menu"],
        )
        for item in items:
            choice = Gtk.CheckButton(
                active=item["id"] in selected,
                css_classes=["app-policy-filter-item"],
            )
            content = Gtk.Box(spacing=10, valign=Gtk.Align.CENTER)
            content.append(icon_factory(item))
            content.append(Gtk.Label(
                label=item["label"], xalign=0, hexpand=True,
                css_classes=["app-policy-filter-item-label"],
            ))
            choice.set_child(content)
            describe_control(
                choice, item["label"],
                f"Show apps with this {label.casefold()}.",
                automation_id=f"parent-filter-{identity}-{item['id']}",
            )
            choice.connect(
                "toggled", self._column_filter_toggled, item["id"], selected,
                trigger, items,
            )
            menu.append(choice)
        filter_scroll = Gtk.ScrolledWindow(
            child=menu, propagate_natural_height=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
        )
        set_automation_id(
            filter_scroll,
            f"parent-filter-{identity}-choices",
        )
        popover.set_child(filter_scroll)
        # MenuButton owns popup positioning, keyboard activation and teardown.
        trigger.set_popover(popover)
        overlay.add_overlay(trigger)
        overlay.set_measure_overlay(trigger, False)
        overlay.set_clip_overlay(trigger, False)
        return overlay

    def _column_filter_toggled(self, button, item_id, selected, trigger, items):
        if button.get_active():
            selected.add(item_id)
        else:
            selected.discard(item_id)
        if selected != {item["id"] for item in items}:
            trigger.add_css_class("filtered")
        else:
            trigger.remove_css_class("filtered")
        self._filter()

    def _match_rule_filter_icon(self, item):
        return Gtk.Button(
            can_focus=False, can_target=False,
            css_classes=[
                "match-rule-button", "policy-choice", "policy-legend-icon",
                item["css"],
            ],
            child=self._match_rule_image(item),
        )

    @staticmethod
    def _access_rule_filter_icon(item):
        return Gtk.ToggleButton(
            active=True, can_focus=False, can_target=False,
            css_classes=["policy-choice", "policy-legend-icon", item["css"]],
            child=Gtk.Image(icon_name=item["icon"], pixel_size=19),
        )

    @staticmethod
    def _match_rule_slot():
        cell = Gtk.Box(
            width_request=92, halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER, css_classes=["match-rule-cell"],
        )
        cell.append(Gtk.Button(
            sensitive=False, can_focus=False, can_target=False, opacity=0,
            css_classes=["match-rule-button"],
        ))
        return cell

    @staticmethod
    def _policy_selector_slot():
        selector = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=3,
            opacity=0, css_classes=["policy-selector"],
        )
        for state in APP_LIST_STATES:
            selector.append(Gtk.ToggleButton(
                sensitive=False, can_focus=False, can_target=False,
                css_classes=["policy-choice", state["css"]],
            ))
        return selector

    def _legend_card(self):
        card = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["policy-legend"],
        )

        header_content = Gtk.Box(spacing=16, valign=Gtk.Align.CENTER)
        book = Gtk.CenterBox(
            valign=Gtk.Align.CENTER,
            css_classes=["policy-legend-book"],
        )
        book.set_center_widget(Gtk.Image(
            icon_name="accessories-dictionary-symbolic", pixel_size=22,
        ))
        header_content.append(book)

        labels = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True,
            valign=Gtk.Align.CENTER,
        )
        labels.append(Gtk.Label(
            label="Legend", xalign=0, css_classes=["policy-legend-title"],
        ))
        subtitle = Gtk.Label(
            label="Quick reference for access and match rules",
            xalign=0, wrap=True, css_classes=["policy-legend-subtitle"],
        )
        labels.append(subtitle)
        header_content.append(labels)
        chevron = Gtk.Image(icon_name="go-down-symbolic", pixel_size=20)
        header_content.append(chevron)

        header = Gtk.ToggleButton(
            active=False,
            tooltip_text="Show legend",
            css_classes=["policy-legend-header"],
            child=header_content,
        )
        describe_control(
            header, "Policy legend",
            "Expand or collapse the app access and match-rule legend.",
            automation_id="parent-legend-toggle",
        )
        card.append(header)

        # Measure both columns at their allocated widths. A horizontal Box
        # can retain the wrapped labels' narrow-width height after its children
        # receive more space, leaving a large empty area below the legend.
        sections = Gtk.Grid(css_classes=["policy-legend-sections"])
        set_automation_id(sections, "parent-legend-content")
        sections.attach(self._legend_section(
            "App Access (What happens)", APP_LIST_STATES, {
                "allowed": "App can always be used",
                "permanent": "App is completely blocked and can only be allowed by admins",
                "conditional": "App is blocked and can be granted one-time extension per child request if time limit is enabled",
            }, access=True,
        ), 0, 0, 1, 1)
        sections.attach(Gtk.Separator(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["policy-legend-divider"],
        ), 1, 0, 1, 1)
        sections.attach(self._legend_section(
            "Match Rule (How apps are matched)", MATCH_RULES, {
                "pattern": "Matches by pattern\n to cover exec path with changing version numbers (e.g., Lunar Client-*-ow_*.AppImage)",
                "precise": "Matches exact app path\n(e.g., /usr/bin/firefox)",
            }, access=False,
        ), 2, 0, 1, 1)

        revealer = Gtk.Revealer(
            transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
            transition_duration=180,
            reveal_child=False,
            child=sections,
        )
        card.append(revealer)
        header.connect(
            "toggled", self._legend_toggled,
            revealer, subtitle, chevron, card,
        )
        return card

    def _legend_section(self, title, items, descriptions, *, access):
        section = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            hexpand=True,
            css_classes=["policy-legend-section"],
        )
        section.append(Gtk.Label(
            label=title, xalign=0, wrap=True,
            css_classes=["policy-legend-section-title"],
        ))
        rows = Gtk.Grid(
            row_spacing=12, column_spacing=16,
            css_classes=["policy-legend-rows"],
        )
        for row, item in enumerate(items):
            if access:
                icon = Gtk.ToggleButton(
                    active=True, can_focus=False, can_target=False,
                    valign=Gtk.Align.CENTER,
                    css_classes=[
                        "policy-choice", "policy-legend-icon", item["css"],
                    ],
                    child=Gtk.Image(icon_name=item["icon"], pixel_size=19),
                )
            else:
                icon = Gtk.Button(
                    can_focus=False, can_target=False, valign=Gtk.Align.CENTER,
                    css_classes=[
                        "match-rule-button", "policy-choice",
                        "policy-legend-icon", item["css"],
                    ],
                    child=self._match_rule_image(item),
                )
            rows.attach(icon, 0, row, 1, 1)
            rows.attach(Gtk.Label(
                label=item["label"], xalign=0, wrap=True, max_width_chars=22,
                css_classes=["policy-legend-item-title"],
            ), 1, row, 1, 1)
            rows.attach(Gtk.Label(
                label=descriptions[item["id"]], xalign=0, wrap=True,
                max_width_chars=22, hexpand=True,
                css_classes=["policy-legend-description"],
            ), 2, row, 1, 1)
        section.append(rows)
        return section

    @staticmethod
    def _legend_toggled(button, revealer, subtitle, chevron, card):
        expanded = button.get_active()
        revealer.set_reveal_child(expanded)
        subtitle.set_label(
            "Understanding access rules and match rules"
            if expanded else "Quick reference for access and match rules"
        )
        chevron.set_from_icon_name(
            "go-up-symbolic" if expanded else "go-down-symbolic",
        )
        button.set_tooltip_text("Hide legend" if expanded else "Show legend")
        if expanded:
            card.add_css_class("expanded")
        else:
            card.remove_css_class("expanded")

    def _show_about(self, *_args):
        AboutDialog(self).present()

    def _show_feedback(self, *_args):
        if not getattr(self, "_feedback_dialog", None):
            self._feedback_dialog = FeedbackDialog(self)
        self._feedback_dialog.present()

    def _show_error(self, error, detail=GENERIC_DETAIL, *, on_close=None):
        self._toast(detail)
        if not getattr(self, "_errors", None):
            self._errors = ErrorHandler(self, "Parent App")
        self._errors.handle(error, GENERIC_TITLE, detail, on_close=on_close)

    def _clear_catalog_rows(self):
        for row in self._app_rows:
            self._apps_group.remove(row)
        self._rows = []
        self._app_rows = []

    def _add_app_row(self, app):
        automation_key = _app_automation_key(app["id"])
        row = Adw.ActionRow(
            title=app["name"], subtitle=app["description"] or app["id"],
            css_classes=["app-policy-row"],
        )
        set_automation_id(row, f"parent-app-{automation_key}")
        row.app = app
        row.search_text = f'{app["name"]} {app["description"]} {app["id"]}'.casefold()
        if app["icon"]:
            try:
                icon = Gio.Icon.new_for_string(app["icon"])
            except GLib.Error:
                icon = None
            if icon is not None:
                icon_cell = Gtk.Box(
                    width_request=80, halign=Gtk.Align.CENTER,
                    valign=Gtk.Align.CENTER,
                    css_classes=["app-icon-cell"],
                )
                icon_cell.append(Gtk.Image(gicon=icon, pixel_size=36))
                row.add_prefix(icon_cell)
        row.policy_buttons = {}
        row.match_rule_button = Gtk.Button(
            tooltip_text="Edit match rule", valign=Gtk.Align.CENTER,
            css_classes=["match-rule-button"],
        )
        describe_control(
            row.match_rule_button, f"{app['name']} match rule",
            "Choose whether this application's saved rule matches an exact path or versioned filename pattern.",
            automation_id=f"parent-app-{automation_key}-match-rule",
        )
        row.match_rule_button.connect("clicked", self._edit_match_rule, row)
        match_rule_cell = Gtk.Box(
            width_request=92, halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER, css_classes=["match-rule-cell"],
        )
        match_rule_cell.append(row.match_rule_button)
        row.add_suffix(match_rule_cell)
        selector = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=3,
            valign=Gtk.Align.CENTER, css_classes=["policy-selector"],
        )
        first_button = None
        for state in APP_LIST_STATES:
            button = Gtk.ToggleButton(
                tooltip_text=state["label"],
                css_classes=["policy-choice", state["css"]],
                child=Gtk.Image(icon_name=state["icon"], pixel_size=19),
                valign=Gtk.Align.CENTER,
            )
            describe_control(
                button, f"{app['name']} access rule: {state['label']}",
                f"Set the selected child's access rule for {app['name']} to {state['label']}.",
                automation_id=f"parent-app-{automation_key}-access-{state['id']}",
            )
            if first_button is None:
                first_button = button
            else:
                button.set_group(first_button)
            button.connect("toggled", self._policy_changed)
            row.policy_buttons[state["id"]] = button
            selector.append(button)
        row.add_suffix(selector)
        row.match_rule = None
        row.user_saved_match_rule = False
        self._update_match_rule_icon(row)
        self._apps_group.add(row)
        self._rows.append(row)
        self._app_rows.append(row)

    def _set_catalog(self, applications):
        self._clear_catalog_rows()
        self._pending_catalog_apps = list(applications)
        self._catalog_building = True
        self._apps_table_ready = False
        self._catalog_build_generation = self._apps_load_generation
        self._update_apps_loading_ui()
        GLib.idle_add(self._append_catalog_batch)

    def _append_catalog_batch(self):
        if self._catalog_build_generation != self._apps_load_generation:
            self._catalog_building = False
            return GLib.SOURCE_REMOVE
        batch = self._pending_catalog_apps[:CATALOG_ROW_BATCH_SIZE]
        self._pending_catalog_apps = self._pending_catalog_apps[CATALOG_ROW_BATCH_SIZE:]
        for app in batch:
            self._add_app_row(app)
        if self._pending_catalog_apps:
            return GLib.SOURCE_CONTINUE
        self._catalog_building = False
        self._apps_table_ready = True
        self._apply_app_policies()
        self._filter(self._search)
        self._update_apps_loading_ui()
        self._set_apps_sensitive(self._preferences is not None)
        LOG.info("parent.003", row_count=len(self._rows))
        return GLib.SOURCE_REMOVE

    def _run(self, operation, success, failure=None):
        def done(value=None, error=None):
            try:
                if error is not None:
                    raise error
                success(value)
            except Exception as caught:
                if failure is not None:
                    failure(caught)
                    return
                LOG.warning("parent.004", error_type=error_code(caught))
                self._show_error(caught)
                self._loading = True
                if self._preferences is not None:
                    self._enabled.set_active(bool(
                        self._preferences.get("parent_control_enabled")
                    ))
                    self._set_daily_limit_value(
                        self._preferences.get("daily_time_limit_minutes", 0)
                    )
                self._loading = False
                self._set_apps_sensitive(self._preferences is not None)

        def worker():
            try:
                value = operation()
                GLib.idle_add(done, value, None)
            except Exception as error:
                GLib.idle_add(done, None, error)

        threading.Thread(target=worker, daemon=True).start()

    def _load_users(self):
        if self._users_loading:
            return GLib.SOURCE_REMOVE
        self._users_loading = True
        LOG.info("parent.005")
        self._run(self._client.list_users, self._users_loaded, self._users_failed)
        return GLib.SOURCE_REMOVE

    def _users_failed(self, error):
        """Fail closed before exposing a parent-management surface."""
        self._users_loading = False
        if self._users_loaded_once and not management_access_denied(error):
            # Keep an already-authorized window usable during a transient
            # discovery outage. Each operation still authorizes at the broker.
            if not self._user_discovery_error_reported:
                self._user_discovery_error_reported = True
                self._show_error(error, "Child accounts could not be refreshed. Retrying automatically.")
            return
        LOG.warning("parent.006", error_type=error_code(error))
        self.get_content().set_sensitive(False)
        self._show_error(error, "The Parent App could not load. Please try again later.",
                         on_close=self.get_application().quit)

    def _users_loaded(self, users):
        loaded = [parse_listed_user(user) for user in users]
        self._users_loading = False
        self._user_discovery_error_reported = False
        if self._users_loaded_once and loaded == self._users:
            return
        previous_uid = self._selected_uid()
        self._users_loaded_once = True
        self._users = loaded
        LOG.info("parent.007", count=len(self._users))
        selected = next((index for index, user in enumerate(self._users)
                         if user[0] == previous_uid), 0)
        selection_changed = previous_uid is None or not any(
            user[0] == previous_uid for user in self._users
        )
        if self._users and selection_changed:
            # Kick off the selected child's catalog before the account picker
            # model is rebuilt so App Limits work does not wait on UI setup.
            self._ensure_apps_load(self._users[0][0])
        self._account.set_users(self._users, selected)

        self._no_users_message.set_visible(not self._users)
        if self._users and selection_changed:
            self._load_selected()
        else:
            if not self._users:
                self._toast("No interactive non-admin users were found")

    def _selected_uid(self):
        index = self._account.get_selected()
        return self._users[index][0] if index < len(self._users) else None

    def _account_changed(self, *_args):
        if self._users:
            self._load_selected()

    def _load_selected(self):
        uid = self._selected_uid()
        if uid is None:
            return
        self._policy_warning.set_visible(False)
        self._load_policy_warnings()
        selected = self._account.get_selected()
        child_name = self._users[selected][1].split(maxsplit=1)[0]
        self._revoke_description.set_label(
            f"Revokes one-time screen time and app access grants granted to {child_name}."
        )
        self._loading = True
        # Do not carry a previous child's grant state into this selection while
        # its authoritative time status is still loading.
        self._remaining_time_seconds = None
        self._time_status_value.set_label("Loading…")
        self._time_explanation.set_label("—")
        LOG.info("parent.008")
        self._set_apps_sensitive(False)
        # Start the application catalog immediately on a background thread so
        # Screen Limits is not blocked, and App Limits can paint as soon as
        # the tab is opened.
        self._ensure_apps_load(uid)
        self._run(
            lambda: self._client.get_preferences(uid),
            lambda preferences: self._preferences_for(uid, preferences),
        )

    def _ensure_apps_load(self, uid):
        if uid is None:
            return
        if self._apps_loading and self._apps_load_uid == uid:
            return
        self._apps_load_generation += 1
        generation = self._apps_load_generation
        self._apps_load_uid = uid
        self._app_catalog = None
        self._app_catalog_uid = None
        self._apps_loading = True
        self._apps_table_ready = False
        self._catalog_building = False
        self._pending_catalog_apps = []
        self._clear_catalog_rows()
        self._update_apps_loading_ui()
        LOG.info("parent.009")
        self._run(
            lambda: self._client.list_apps(uid),
            lambda applications: self._apps_loaded(uid, generation, applications),
            lambda error: self._apps_failed(uid, generation, error),
        )

    def _apps_loaded(self, uid, generation, applications):
        if generation != self._apps_load_generation or uid != self._selected_uid():
            return
        self._apps_loading = False
        self._app_catalog = applications
        self._app_catalog_uid = uid
        LOG.info("parent.010", app_count=len(applications))
        self._update_apps_loading_ui()
        self._maybe_populate_app_table()

    def _apps_failed(self, uid, generation, error):
        if generation != self._apps_load_generation or uid != self._selected_uid():
            return
        self._apps_loading = False
        LOG.warning("parent.011", error_type=error_code(error))
        self._show_error(error, "Installed apps could not be loaded. Please try again later.")
        self._app_catalog = []
        self._app_catalog_uid = uid
        self._update_apps_loading_ui()
        self._maybe_populate_app_table()

    def _visible_page_changed(self, *_args):
        self._app_limits_visible = self._pages.get_visible_child_name() == "app-limits"
        self._update_apps_loading_ui()
        if self._app_limits_visible:
            GLib.idle_add(self._maybe_populate_app_table)

    def _maybe_populate_app_table(self):
        if not self._app_limits_visible or self._app_catalog is None:
            return GLib.SOURCE_REMOVE
        if self._apps_table_ready or self._catalog_building:
            return GLib.SOURCE_REMOVE
        self._set_catalog(self._app_catalog)
        return GLib.SOURCE_REMOVE

    def _apps_mask_should_show(self):
        return bool(
            getattr(self, "_app_limits_visible", False) and (
                getattr(self, "_apps_loading", False)
                or getattr(self, "_catalog_building", False)
                or not getattr(self, "_apps_table_ready", True)
                or getattr(self, "_preferences", None) is None
            )
        )

    def _update_apps_loading_ui(self):
        mask = getattr(self, "_apps_loading_mask", None)
        if mask is None:
            return
        show = self._apps_mask_should_show()
        mask.set_visible(show)
        spinner = getattr(self, "_apps_loading_spinner", None)
        if spinner is not None:
            spinner.set_spinning(show)

    def _preferences_for(self, uid, preferences):
        if uid != self._selected_uid():
            return
        self._preferences_loaded(preferences)

    def _apply_app_policies(self):
        preferences = getattr(self, "_preferences", None)
        if preferences is None:
            return
        applications = getattr(self, "_app_catalog", None)
        if applications is None:
            applications = [row.app for row in self._rows]
        replacements = replacement_policy_ids(preferences["apps"], applications)
        was_loading = self._loading
        self._loading = True
        try:
            for row in self._rows:
                row.saved_policy_id = replacements.get(row.app["id"], row.app["id"])
                policy = preferences["apps"].get(row.saved_policy_id, {})
                state = policy.get("state", "allowed")
                row.policy_buttons[state].set_active(True)
                row.user_saved_match_rule = policy.get("user_saved_match_rule", False)
                row.match_rule = (policy.get("patterns") or [None])[0]
                if row.match_rule is None and row.user_saved_match_rule:
                    row.match_rule = self._default_match_rule(row)
                self._update_match_rule_icon(row)
        finally:
            self._loading = was_loading

    def _preferences_loaded(self, preferences):
        self._preferences = preferences
        self._enabled.set_active(preferences["parent_control_enabled"])
        self._set_daily_limit_value(preferences["daily_time_limit_minutes"])
        self._apply_app_policies()
        self._filter()
        self._loading = False
        self._set_apps_sensitive(True)
        self._update_apps_loading_ui()
        LOG.info(
            "parent.012",
            enabled=preferences["parent_control_enabled"],
            policy_count=len(preferences["apps"]),
        )
        self._load_time_status()

    def _load_time_status(self, *, retry=False):
        uid = self._selected_uid()
        if uid is None:
            return
        if self._time_status_loading:
            self._time_status_refresh_pending = True
            return
        if not retry:
            self._cancel_time_status_retry()
            self._time_status_retry_count = 0
        self._time_status_loading = True
        self._run(
            lambda: self._client.get_time_status(uid),
            lambda value: self._time_status_loaded(uid, value),
            lambda error: self._time_status_failed(uid, error),
        )

    def _time_status_loaded(self, uid, status):
        self._time_status_loading = False
        self._cancel_time_status_retry()
        self._time_status_retry_count = 0
        if uid != self._selected_uid():
            self._time_status_refresh_pending = False
            self._load_time_status()
            return
        self._remaining_time_seconds = max(
            0, int(status["calculated_active_extension_seconds"]),
        )
        self._time_status_value.set_label(
            format_duration(status["calculated_active_extension_seconds"])
        )
        self._time_explanation.set_label(_time_status_subtitle(status))
        LOG.info(
            "parent.013",
            daily=status["daily_allowance_remaining_seconds"],
            grant=status["one_time_grant_remaining_seconds"],
            additional=status["additional_one_time_grant_seconds"],
            calculated=status["calculated_active_extension_seconds"],
        )
        self._set_apps_sensitive(True)
        self._load_pending_time_status_refresh()

    def _time_status_failed(self, uid, error):
        self._time_status_loading = False
        if uid != self._selected_uid():
            self._time_status_refresh_pending = False
            self._load_time_status()
            return
        LOG.warning("parent.014", error_type=error_code(error))
        if self._time_status_refresh_pending:
            self._time_status_refresh_pending = False
            self._load_time_status()
            return
        if self._time_status_retry_count < MAX_TIME_STATUS_RETRIES:
            self._time_status_retry_count += 1
            self._time_status_retry_id = GLib.timeout_add_seconds(
                TIME_STATUS_RETRY_DELAY_SECONDS, self._retry_time_status,
            )
            return
        self._time_status_value.set_label("Unavailable")
        self._time_explanation.set_label("—")
        self._show_error(error, "Remaining time could not be loaded. Please try again later.")

    def _retry_time_status(self):
        self._time_status_retry_id = 0
        self._load_time_status(retry=True)
        return GLib.SOURCE_REMOVE

    def _cancel_time_status_retry(self):
        if self._time_status_retry_id:
            GLib.source_remove(self._time_status_retry_id)
            self._time_status_retry_id = 0

    def _load_pending_time_status_refresh(self):
        if not self._time_status_refresh_pending:
            return
        self._time_status_refresh_pending = False
        self._load_time_status()

    def _refresh_time_status(self):
        if self._selected_uid() is not None:
            self._load_time_status()
            self._load_policy_warnings()
        return GLib.SOURCE_CONTINUE

    def _load_policy_warnings(self):
        uid = self._selected_uid()
        if uid is None or self._policy_warnings_loading or self._policy_warnings_closed:
            return
        self._policy_warnings_loading = True
        self._run(
            lambda: self._client.get_policy_warnings(uid),
            lambda affected: self._policy_warnings_loaded(uid, affected),
            lambda error: self._policy_warnings_failed(uid, error),
        )

    def _policy_warnings_loaded(self, uid, affected):
        self._policy_warnings_loading = False
        if self._policy_warnings_closed:
            return
        if uid != self._selected_uid():
            self._load_policy_warnings()
            return
        self._policy_warning_query_failed = False
        affected = tuple(sorted(set(affected)))
        previous = self._reported_policy_warnings.get(uid, ())
        self._reported_policy_warnings[uid] = affected
        self._policy_warning.set_visible(bool(affected))
        if not affected:
            return
        names = {app["id"]: app["name"] for app in self._app_catalog or ()}
        apps = ", ".join(names.get(app_id, app_id or "another application") for app_id in affected)
        detail = (
            "Some app limits could not be applied. Affected apps or updated versions "
            "may be unrestricted. Other controls remain available, and saved rules "
            "will be retried automatically."
        )
        # App identities are displayed locally, never included in automatic
        # diagnostic events or the error-report draft.
        self._policy_warning.set_label(f"{detail}\nAffected apps: {apps}")
        if affected != previous:
            self._show_error(RuntimeError("application rules unavailable"), detail)

    def _policy_warnings_failed(self, uid, error):
        self._policy_warnings_loading = False
        if self._policy_warnings_closed:
            return
        if uid != self._selected_uid():
            self._load_policy_warnings()
            return
        self._policy_warning.set_label("App limit status is unavailable. Retrying automatically.")
        self._policy_warning.set_visible(True)
        if not self._policy_warning_query_failed:
            self._policy_warning_query_failed = True
            self._show_error(error, "App limit status could not be checked. Other controls remain available.")

    def _refresh_users(self):
        self._load_users()
        return GLib.SOURCE_CONTINUE

    def _close_requested(self, *_args):
        self._policy_warnings_closed = True
        self._cancel_time_status_retry()
        self._cancel_custom_daily_limit_save()
        if self._time_status_refresh_id:
            GLib.source_remove(self._time_status_refresh_id)
            self._time_status_refresh_id = 0
        if self._account_refresh_id:
            GLib.source_remove(self._account_refresh_id)
            self._account_refresh_id = 0
        return False

    def _set_apps_sensitive(self, sensitive):
        idle = not self._loading and not getattr(self, "_save_in_progress", False)
        sensitive = bool(sensitive and idle and self._selected_uid() is not None)
        self._account.set_sensitive(idle)
        self._revoke.set_sensitive(
            idle and self._selected_uid() is not None and
            getattr(self, "_remaining_time_seconds", None) is not None and
            self._remaining_time_seconds > 0
        )
        self._enabled.set_sensitive(idle and self._selected_uid() is not None)
        self._daily_limit.set_sensitive(
            idle and self._selected_uid() is not None and
            self._enabled.get_active()
        )
        if hasattr(self, "_custom_daily_limit"):
            self._custom_daily_limit.set_sensitive(
                idle and self._selected_uid() is not None and
                self._enabled.get_active()
            )
        table_ready = getattr(self, "_apps_table_ready", True)
        self._apps_group.set_sensitive(sensitive and table_ready)
        search = getattr(self, "_search", None)
        if search is not None:
            search.set_sensitive(sensitive and table_ready)

    def _confirm_revoke(self, *_args):
        selected = self._account.get_selected()
        if selected >= len(self._users):
            return
        child_name = self._users[selected][1]
        dialog = Gtk.Dialog(
            transient_for=self, modal=True, title="Revoke one-time grant?",
        )
        set_automation_id(dialog, "parent-revoke-dialog")
        header = Gtk.HeaderBar()
        add_identified_window_controls(header, "parent-revoke-window-controls")
        dialog.set_titlebar(header)
        warning = Gtk.Label(
            label=("This will revoke one-time screen time and access to soft blocked apps "
                   f"granted to {child_name}, close their running blocked apps, and "
                   "lock their desktop when no time remains. "
                   "Their remaining daily time allowance is not impacted."),
            wrap=True, max_width_chars=72, xalign=0,
            margin_top=18, margin_bottom=18,
            margin_start=18, margin_end=18,
        )
        warning.set_natural_wrap_mode(Gtk.NaturalWrapMode.WORD)
        set_automation_id(warning, "parent-revoke-warning")
        dialog.get_content_area().append(warning)
        add_dialog_button(
            dialog, "Cancel", Gtk.ResponseType.CANCEL, "parent-revoke-cancel",
            description="Keep the current one-time grant.",
        )
        add_dialog_button(
            dialog, "Revoke grant", Gtk.ResponseType.OK, "parent-revoke-confirm",
            description="Revoke the selected child's one-time grant.",
            css_class="destructive-action",
        )
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        dialog.connect("response", self._revoke_response)
        dialog.present()

    def _revoke_response(self, dialog, response):
        dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return
        uid = self._selected_uid()
        if uid is None:
            return
        self._loading = True
        self._set_apps_sensitive(False)
        self._run(
            lambda: self._client.revoke_one_time_grant(uid),
            lambda _value: self._revoke_succeeded(uid),
            lambda error: self._save_failed(uid, "one-time grant", error),
        )

    def _revoke_succeeded(self, uid):
        if uid != self._selected_uid():
            return
        self._loading = False
        self._set_apps_sensitive(True)
        self._toast("One-time grant revoked")
        self._load_time_status()

    def _enabled_changed(self, switch, _param):
        if self._loading or self._selected_uid() is None:
            return
        self._daily_limit.set_sensitive(switch.get_active())
        self._save_parent_control(switch.get_active())

    def _daily_limit_popover(self):
        choices = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["daily-limit-menu"],
        )
        for index, minutes in enumerate(DAILY_LIMIT_PRESETS):
            choice = self._daily_limit_choice(
                _daily_limit_label(minutes), index,
            )
            describe_control(
                choice, _daily_limit_label(minutes),
                f"Set the selected child's daily allowance to {_daily_limit_label(minutes)}.",
                automation_id=f"parent-daily-limit-{minutes}",
            )
            choices.append(choice)
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, width_request=300)
        choices_scroll = Gtk.ScrolledWindow(
            child=choices,
            # DailyLimitPopover caps the whole popup to the available space;
            # keep the choices shrinkable while the custom action stays fixed.
            propagate_natural_height=True,
            max_content_height=378,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
        )
        set_automation_id(choices_scroll, "parent-daily-limit-choices")
        menu.append(choices_scroll)
        menu.append(Gtk.Separator(css_classes=["daily-limit-separator"]))
        custom = self._daily_limit_choice(
            "Custom amount…", CUSTOM_DAILY_LIMIT_INDEX,
            icon_name="emblem-system-symbolic",
        )
        describe_control(
            custom, "Custom amount",
            "Enter a custom daily allowance in minutes.",
            automation_id="parent-daily-limit-custom",
        )
        menu.append(custom)
        self._update_daily_limit_choice_styles()
        return DailyLimitPopover(
            child=menu,
            css_classes=["daily-limit-popover"],
        )

    def _daily_limit_choice(self, label, index, *, icon_name=None):
        content = Gtk.Box(spacing=14)
        if icon_name:
            marker = Gtk.Image(
                icon_name=icon_name,
                pixel_size=22,
                valign=Gtk.Align.CENTER,
                css_classes=["daily-limit-custom-icon"],
            )
        else:
            marker = Gtk.Box(
                valign=Gtk.Align.CENTER,
                halign=Gtk.Align.CENTER,
                css_classes=["daily-limit-radio"],
            )
        content.append(marker)
        content.append(Gtk.Label(
            label=label,
            xalign=0,
            hexpand=True,
            css_classes=["daily-limit-choice-label"],
        ))
        choice = Gtk.Button(
            child=content,
            hexpand=True,
            css_classes=["daily-limit-choice"],
        )
        choice.connect("clicked", self._daily_limit_changed, index)
        self._daily_limit_choices.append((choice, marker, index))
        return choice

    def _update_daily_limit_choice_styles(self):
        for choice, marker, index in self._daily_limit_choices:
            selected = index == self._daily_limit_selected
            if selected:
                choice.add_css_class("selected")
                marker.add_css_class("selected")
            else:
                choice.remove_css_class("selected")
                marker.remove_css_class("selected")

    def _daily_limit_changed(self, _button, selected):
        if self._loading or self._selected_uid() is None:
            return
        self._daily_limit_selected = selected
        is_custom = selected == CUSTOM_DAILY_LIMIT_INDEX
        self._daily_limit.set_label("Custom value" if is_custom else _daily_limit_label(
            DAILY_LIMIT_PRESETS[selected],
        ))
        self._update_daily_limit_choice_styles()
        self._custom_daily_limit.set_visible(is_custom)
        self._daily_limit.popdown()
        if is_custom:
            self._custom_daily_limit_entry.grab_focus()
            return
        self._save_parent_control(self._enabled.get_active())

    def _custom_daily_limit_changed(self, *_args):
        self._cancel_custom_daily_limit_save()
        if self._loading or self._selected_uid() is None:
            return False
        text = self._custom_daily_limit_entry.get_text().strip()
        if not text.isdecimal() or not 0 <= int(text) <= MAX_CUSTOM_DAILY_LIMIT_MINUTES:
            self._custom_daily_limit_entry.add_css_class("error")
            self._custom_daily_limit.set_subtitle(
                "Enter a whole number from 0 to 1439."
            )
            return False
        self._custom_daily_limit_entry.remove_css_class("error")
        self._custom_daily_limit.set_subtitle("Enter a whole number from 0 to 1439.")
        self._save_parent_control(self._enabled.get_active())
        return False

    def _custom_daily_limit_text_changed(self, *_args):
        """Debounce custom-value edits before persisting the complete number."""
        self._cancel_custom_daily_limit_save()
        if self._loading or self._selected_uid() is None:
            return
        self._custom_daily_limit_save_id = GLib.timeout_add(
            CUSTOM_DAILY_LIMIT_SAVE_DELAY_MS, self._save_debounced_custom_daily_limit,
        )

    def _save_debounced_custom_daily_limit(self):
        self._custom_daily_limit_save_id = 0
        self._custom_daily_limit_changed()
        return GLib.SOURCE_REMOVE

    def _cancel_custom_daily_limit_save(self):
        if self._custom_daily_limit_save_id:
            GLib.source_remove(self._custom_daily_limit_save_id)
            self._custom_daily_limit_save_id = 0

    def _set_daily_limit_value(self, minutes):
        """Load a saved value into either a preset or the Custom value row."""
        selected, is_custom = _daily_limit_selection(minutes)
        self._daily_limit_selected = selected
        self._daily_limit.set_label("Custom value" if is_custom else _daily_limit_label(minutes))
        self._update_daily_limit_choice_styles()
        self._custom_daily_limit.set_visible(is_custom)
        if is_custom:
            self._custom_daily_limit_entry.set_text(str(minutes))

    def _daily_limit_minutes(self):
        if self._daily_limit_selected != CUSTOM_DAILY_LIMIT_INDEX:
            return DAILY_LIMIT_PRESETS[self._daily_limit_selected]
        text = self._custom_daily_limit_entry.get_text().strip()
        if text.isdecimal() and 0 <= int(text) <= MAX_CUSTOM_DAILY_LIMIT_MINUTES:
            return int(text)
        # Invalid custom input is never saved; retain the last valid value.
        return self._preferences.get("daily_time_limit_minutes", 30)

    def _save_parent_control(self, enabled):
        uid = self._selected_uid()
        daily_limit_minutes = self._daily_limit_minutes()
        self._queue_save("parent-control", uid, enabled, daily_limit_minutes)

    def _start_parent_control_save(self, uid, enabled, daily_limit_minutes):
        LOG.info("parent.015", enabled=enabled, daily_limit_minutes=daily_limit_minutes)
        self._run(
            lambda: self._client.set_parent_control(
                uid, enabled, daily_limit_minutes,
            ),
            lambda preferences: self._save_succeeded(
                uid, preferences, refresh_time_status=True,
            ),
            lambda error: self._save_failed(uid, "screen-time settings", error),
        )

    def _policy_changed(self, button):
        if button.get_active() and not self._loading:
            self._save_app_policy()
            self._filter()

    @staticmethod
    def _canonical_match_rule(row, rule):
        """Return an absolute same-directory rule from editor input."""
        rule = rule.strip()
        if not rule or rule.startswith("/") or "/" in rule:
            return rule
        directories = {
            os.path.dirname(os.path.realpath(target))
            for target in row.app["targets"] if target.startswith("/")
        }
        if len(directories) != 1:
            return rule
        return os.path.join(directories.pop(), rule)

    def _default_match_rule(self, row):
        suggestions = row.app.get("suggested_patterns", [])
        return suggestions[0] if suggestions else row.app["targets"][0]

    @staticmethod
    def _is_pattern(rule):
        return "*" in rule or "?" in rule

    def _update_match_rule_icon(self, row):
        rule = row.match_rule or self._default_match_rule(row)
        match = MATCH_RULES[0] if self._is_pattern(rule) else MATCH_RULES[1]
        row.match_rule_button.set_css_classes(
            ["match-rule-button", "policy-choice", match["css"]]
        )
        row.match_rule_button.set_child(self._match_rule_image(match))
        row.match_rule_button.set_tooltip_text(match["label"])

    @staticmethod
    def _match_rule_image(match):
        return Gtk.Label(
            label=match["glyph"],
            css_classes=["match-rule-icon", match["css"]],
        )

    def _edit_match_rule(self, _button, row):
        dialog = Gtk.Dialog(transient_for=self, modal=True, title="Edit Match Rule")
        set_automation_id(dialog, "parent-match-rule-dialog")
        header = Gtk.HeaderBar()
        add_identified_window_controls(header, "parent-match-rule-window-controls")
        dialog.set_titlebar(header)
        add_dialog_button(
            dialog, "Cancel", Gtk.ResponseType.CANCEL, "parent-match-rule-cancel",
        )
        add_dialog_button(
            dialog, "Reset to Default", Gtk.ResponseType.APPLY,
            "parent-match-rule-reset",
        )
        add_dialog_button(
            dialog, "Save", Gtk.ResponseType.OK, "parent-match-rule-save",
        )
        dialog.set_default_response(Gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(18)
        content.set_margin_bottom(18)
        content.set_margin_start(18)
        content.set_margin_end(18)
        content.append(Gtk.Label(
            label="Use an exact execution path, or include * for a versioned filename pattern.",
            wrap=True, xalign=0,
        ))
        entry = Gtk.Entry(hexpand=True, width_chars=54,
                          text=row.match_rule or self._default_match_rule(row))
        describe_control(
            entry, "Application match rule",
            "Enter an exact execution path or a versioned filename pattern.",
            automation_id="parent-match-rule-entry",
        )
        content.append(entry)

        def response(_dialog, response_id):
            if response_id == Gtk.ResponseType.OK:
                rule = self._canonical_match_rule(row, entry.get_text())
                if not rule:
                    self._toast("A match rule is required")
                    return
                if not self._is_pattern(rule) and rule not in row.app["targets"]:
                    self._toast("A precise match must be this app's execution path")
                    return
                row.match_rule = rule
                # Saving the detected default is not an override. A value only
                # becomes user-saved once it differs from that default.
                row.user_saved_match_rule = rule != self._default_match_rule(row)
                self._update_match_rule_icon(row)
                self._save_app_policy()
                self._filter()
            elif response_id == Gtk.ResponseType.APPLY:
                row.match_rule = self._default_match_rule(row)
                row.user_saved_match_rule = False
                self._update_match_rule_icon(row)
                self._save_app_policy()
                self._filter()
            dialog.destroy()

        dialog.connect("response", response)
        dialog.present()

    def _app_policy_value(self):
        value = dict(self._preferences)
        # SetPreferences retains the enabled state, but it persists the daily
        # limit. Take it from the current control so queued policy changes do
        # not reintroduce an earlier limit after a screen-time edit.
        value["daily_time_limit_minutes"] = self._daily_limit_minutes()
        # Preserve saved policies for launchers which have disappeared since
        # the account was last managed. Replacing the visible rows below is
        # therefore the only change made by this save.
        visible_ids = {row.app["id"] for row in self._rows}
        visible_ids.update(getattr(row, "saved_policy_id", row.app["id"]) for row in self._rows)
        value["apps"] = {
            app_id: policy for app_id, policy in self._preferences["apps"].items()
            if app_id not in visible_ids
        }
        for row in self._rows:
            state = next(
                state["id"] for state in STATES
                if row.policy_buttons[state["id"]].get_active()
            )
            # An explicit match-rule selection is retained even if access is
            # currently allowed, so it is ready when the app is blocked later.
            if state != "allowed" or row.user_saved_match_rule:
                rule = row.match_rule if row.user_saved_match_rule else self._default_match_rule(row)
                value["apps"][row.app["id"]] = {
                    "state": state, "targets": row.app["targets"],
                    "patterns": [rule] if self._is_pattern(rule) else [],
                    "user_saved_match_rule": row.user_saved_match_rule,
                }
        return value

    def _save_app_policy(self):
        if not self._preferences or self._selected_uid() is None:
            return
        value = self._app_policy_value()
        uid = self._selected_uid()
        self._queue_save("app-policy", uid, value)

    def _start_app_policy_save(self, uid, value):
        LOG.info("parent.016", policy_count=len(value["apps"]))
        self._run(
            lambda: self._client.set_preferences(uid, value),
            lambda preferences: self._save_succeeded(uid, preferences),
            lambda error: self._save_failed(uid, "app access", error),
        )

    def _queue_save(self, kind, uid, *arguments):
        save = (kind, uid, arguments)
        if self._save_in_progress:
            # Saves share one preference record. Run them in interaction order
            # so a completed request can never overwrite a newer UI change.
            self._pending_saves.append(save)
            return
        self._start_save(save)

    def _start_save(self, save):
        kind, uid, arguments = save
        self._save_in_progress = True
        # A preference document is written as one record.  Freeze controls
        # that can change it until this write has an authoritative outcome.
        # This prevents a second click from racing the saved snapshot.
        self._set_apps_sensitive(False)
        if kind == "app-policy":
            self._start_app_policy_save(uid, *arguments)
        else:
            self._start_parent_control_save(uid, *arguments)

    def _save_succeeded(self, uid, preferences, *, refresh_time_status=False):
        self._save_in_progress = False
        if uid == self._selected_uid():
            # The controls already show this policy. Updating them again makes
            # every row animate, which is perceived as a flash.
            self._preferences = preferences
        LOG.info("parent.017")
        self._load_policy_warnings()
        if refresh_time_status:
            self._load_time_status()
        self._start_next_save()
        if not self._save_in_progress and hasattr(self, "_set_apps_sensitive"):
            self._set_apps_sensitive(True)

    def _save_failed(self, uid, setting, error):
        self._save_in_progress = False
        LOG.warning("parent.018", setting=setting, error_type=error_code(error))
        self._show_error(error, f"Could not save {setting}. Please try again later.")
        if uid == self._selected_uid():
            self._restore_preferences_uid = uid
        self._start_next_save()
        if not self._save_in_progress and hasattr(self, "_set_apps_sensitive"):
            self._set_apps_sensitive(True)

    def _start_next_save(self):
        if self._pending_saves:
            self._start_save(self._pending_saves.pop(0))
        elif self._restore_preferences_uid is not None:
            restore_uid = self._restore_preferences_uid
            self._restore_preferences_uid = None
            if restore_uid == self._selected_uid() and self._preferences is not None:
                self._loading = True
                self._preferences_loaded(self._preferences)

    def _toast(self, title):
        self._toasts.add_toast(Adw.Toast(title=title))

    def _row_match_rule_id(self, row):
        rule = row.match_rule or self._default_match_rule(row)
        return MATCH_RULES[0]["id"] if self._is_pattern(rule) else MATCH_RULES[1]["id"]

    @staticmethod
    def _row_access_rule_id(row):
        for state in STATES:
            if row.policy_buttons[state["id"]].get_active():
                return state["id"]
        return STATES[0]["id"]

    def _row_matches_filters(self, row, query):
        if query and query not in row.search_text:
            return False
        if self._row_match_rule_id(row) not in self._match_rule_filters:
            return False
        return self._row_access_rule_id(row) in self._access_rule_filters

    def _filter(self, *_args):
        query = self._search.get_text().strip().casefold()
        for row in self._rows:
            row.set_visible(self._row_matches_filters(row, query))


class Application(Adw.Application):
    def __init__(self, *, preview=False, client_factory=None, startup_error=None):
        super().__init__(application_id="com.puffyslippers.OhNoParentControl.Parent")
        self._startup_error = startup_error
        install_exception_hooks(self, "Parent App")
        self._preview = preview
        # Component tests inject a scripted broker through the same constructor
        # seam used by the preview.  Production continues to construct only the
        # system-D-Bus client below, so this does not create a test-only broker
        # path or weaken the broker's caller authorization boundary.
        if preview and client_factory is None:
            from .preview_data import PreviewBrokerClient

            client_factory = PreviewBrokerClient
        self._client_factory = client_factory or BrokerClient
        self._css_provider = None
        self._preview_monitor = None
        self._preview_reload_source_id = None
        self._preview_changed_paths = set()

    @staticmethod
    def _asset_path(name):
        return Path(__file__).with_name(name)

    def _load_stylesheet(self):
        self._css_provider.load_from_path(str(self._asset_path("style.css")))

    def _watch_preview_files(self):
        if self._preview_monitor is not None:
            return
        directory = Gio.File.new_for_path(str(Path(__file__).parent))
        self._preview_monitor = directory.monitor_directory(
            Gio.FileMonitorFlags.WATCH_MOVES, None,
        )
        self._preview_monitor.connect("changed", self._preview_file_changed)

    def _preview_file_changed(self, _monitor, file, other_file, event_type):
        if event_type not in {
            Gio.FileMonitorEvent.CHANGED,
            Gio.FileMonitorEvent.CREATED,
            Gio.FileMonitorEvent.MOVED_IN,
        }:
            return
        changed = {Path(file.get_path() or "")}
        if other_file is not None:
            changed.add(Path(other_file.get_path() or ""))
        relevant = {
            path for path in changed
            if path.name == "style.css" or path.suffix == ".py"
        }
        if not relevant:
            return
        self._preview_changed_paths.update(relevant)
        if self._preview_reload_source_id is None:
            self._preview_reload_source_id = GLib.timeout_add(150, self._reload_preview)

    def _reload_preview(self):
        self._preview_reload_source_id = None
        changed_paths = self._preview_changed_paths
        self._preview_changed_paths = set()
        if any(path.name == "style.css" for path in changed_paths):
            self._load_stylesheet()
            LOG.info("parent.019")
        if any(path.suffix == ".py" for path in changed_paths):
            LOG.info("parent.020")
            os.execv(sys.executable, sys.orig_argv)
        return GLib.SOURCE_REMOVE

    def do_activate(self):
        if self._startup_error is not None:
            if management_access_denied(self._startup_error):
                self._show_management_denied()
                return
            show_startup_error(self, "Parent App", self._startup_error)
            return
        window = self.get_active_window() or ParentWindow(
            self, client_factory=self._client_factory,
        )
        self._ensure_stylesheet(window)
        if self._preview:
            self._watch_preview_files()
        window.present()

    def _ensure_stylesheet(self, window):
        if self._css_provider is None:
            self._css_provider = Gtk.CssProvider()
            self._load_stylesheet()
            Gtk.StyleContext.add_provider_for_display(
                window.get_display(), self._css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def _show_management_denied(self):
        """Explain an explicit broker refusal without creating management UI."""
        window = self.get_active_window()
        if window is None:
            window = Adw.ApplicationWindow(application=self,
                title="Administrator access required", default_width=820,
                default_height=320, css_classes=["management-denied"])
            set_automation_id(window, "parent-access-denied-window")
            self._ensure_stylesheet(window)
            toolbar = Adw.ToolbarView()
            header = Adw.HeaderBar()
            add_identified_window_controls(
                header, "parent-access-denied-window-controls",
            )
            toolbar.add_top_bar(header)
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=32,
                margin_top=32, margin_bottom=24, margin_start=24, margin_end=32)
            message = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24,
                vexpand=True, valign=Gtk.Align.CENTER)
            logo = Gtk.Image.new_from_file(str(branding_asset_path("app_logo.png")))
            logo.set_pixel_size(96)
            logo.set_valign(Gtk.Align.CENTER)
            message.append(logo)
            message.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL,
                css_classes=["management-denied-divider"]))
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                hexpand=True, valign=Gtk.Align.CENTER)
            brand = Gtk.Label(label=app_name(), xalign=0, wrap=True,
                margin_bottom=6, css_classes=["management-denied-brand"])
            set_automation_id(brand, "parent-access-denied-brand")
            text.append(brand)
            heading = Gtk.Label(label="Administrator Required", xalign=0,
                wrap=True, css_classes=["management-denied-title"])
            set_automation_id(heading, "parent-access-denied-heading")
            text.append(heading)
            explanation = Gtk.Label(
                label="Only an administrator can manage parental controls.\n"
                      "Sign in with an administrator account to open the Parent App.",
                xalign=0, wrap=True, css_classes=["management-denied-message"])
            set_automation_id(explanation, "parent-access-denied-message")
            explanation.update_property([Gtk.AccessibleProperty.LABEL], [
                "Only an administrator can manage parental controls. "
                "Sign in with an administrator account to open the Parent App."])
            text.append(explanation)
            message.append(text)
            content.append(message)
            close = Gtk.Button(label="Close", halign=Gtk.Align.END,
                css_classes=["management-denied-close"])
            describe_control(
                close, "Close",
                "Close the administrator-required notice.",
                automation_id="parent-access-denied-close",
            )
            close.connect("clicked", lambda *_: self.quit())
            content.append(close)
            toolbar.set_content(content)
            window.set_content(toolbar)
            window.set_default_widget(close)
        window.present()


def _can_start(client_factory=BrokerClient, on_error=None):
    # Do this before creating a GTK window so manually invoking the launcher
    # does not expose the Parent App to a standard account.  ListManagedUsers
    # is deliberately broker-authorized and therefore uses the same
    # AccountsService role source as all management operations.
    try:
        client_factory().list_users()
    except Exception as error:
        if on_error is not None:
            on_error(error)
        return False
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    preview_available = Path(__file__).with_name("preview_data.py").is_file()
    parser.add_argument(
        "--preview", action="store_true",
        help=("render the parent UI with fixture data and no privileged services"
              if preview_available else argparse.SUPPRESS),
    )
    args = parser.parse_args(argv)
    if args.preview and not preview_available:
        parser.error("--preview is only available from the development checkout")
    if not args.preview:
        configure_logging()
    else:
        configure_console()
    startup_errors = []
    if not args.preview and not _can_start(on_error=startup_errors.append):
        LOG.warning("parent.021")
    log_version()
    LOG.info("parent.022")
    return Application(preview=args.preview,
                       startup_error=startup_errors[0] if startup_errors else None).run([sys.argv[0]])


if __name__ == "__main__":
    from common.oh_no_parent_control_ui.diagnostic_events import run_cli
    raise SystemExit(run_cli(main))
