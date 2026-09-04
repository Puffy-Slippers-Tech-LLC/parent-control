"""Administrator-facing GTK 4/libadwaita parent-control application."""

from __future__ import annotations

import argparse
import copy
import logging
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
from common.oh_no_parent_control_ui.accessibility import describe_control
from common.oh_no_parent_control_ui.user_icon import parse_listed_user
from common.oh_no_parent_control_ui.test_identities import preview_users

from .client import BrokerClient, configure_logging

LOG = logging.getLogger("oh-no-parent-control-parent")
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
CUSTOM_DAILY_LIMIT_SAVE_DELAY_MS = 350
# Building every app row on the GTK thread in one burst freezes the window.
# Yield between small batches so the App Limits tab can switch immediately
# and the loading mask can keep animating.
CATALOG_ROW_BATCH_SIZE = 8
PREVIEW_USERS = preview_users("child")
PREVIEW_THUNDERBIRD_ICON = str(Path(__file__).with_name("thunderbird-default128.png"))
PREVIEW_PREFERENCES = {
    1001: {
        "parent_control_enabled": True,
        "daily_time_limit_minutes": 90,
        "apps": {
            "thunderbird_thunderbird.desktop": {
                "state": "allowed",
                "targets": ["/snap/bin/thunderbird"],
                "patterns": ["ABC"],
                "user_saved_match_rule": True,
            },
            "lunarclient.desktop": {
                "state": "permanent",
                "targets": ["/home/riley/Applications/Lunar Client-3.8.0.AppImage"],
                "patterns": ["/home/riley/Applications/Lunar Client-*.AppImage"],
                "user_saved_match_rule": True,
            },
            "com.mojang.Minecraft.desktop": {
                "state": "conditional",
                "targets": ["app/com.mojang.Minecraft/x86_64/stable"],
                "patterns": [],
                "user_saved_match_rule": False,
            },
        },
        "request": {},
    },
    1002: {
        "parent_control_enabled": False,
        "daily_time_limit_minutes": 60,
        "apps": {},
        "request": {},
    },
}
PREVIEW_APPS = (
    {
        "id": "thunderbird_thunderbird.desktop",
        "name": "Thunderbird",
        "description": "Email and calendar",
        "icon": PREVIEW_THUNDERBIRD_ICON,
        "targets": ["/snap/bin/thunderbird"],
        "suggested_patterns": ["ABC"],
    },
    {
        "id": "lunarclient.desktop",
        "name": "Lunar Client",
        "description": "Play Minecraft",
        "icon": "lunar-client",
        "targets": ["/home/riley/Applications/Lunar Client-3.8.0.AppImage"],
        "suggested_patterns": ["/home/riley/Applications/Lunar Client-*.AppImage"],
    },
    {
        "id": "com.mojang.Minecraft.desktop",
        "name": "Minecraft",
        "description": "Play Minecraft",
        "icon": "com.mojang.Minecraft",
        "targets": ["app/com.mojang.Minecraft/x86_64/stable"],
        "suggested_patterns": [],
    },
)


class PreviewBrokerClient:
    """In-memory representative data for GUI work without system services."""

    def __init__(self):
        self._preferences = copy.deepcopy(PREVIEW_PREFERENCES)

    def list_users(self):
        return PREVIEW_USERS

    def get_preferences(self, uid):
        return copy.deepcopy(self._preferences[uid])

    def list_apps(self, _uid):
        return copy.deepcopy(PREVIEW_APPS)

    def get_time_status(self, _uid):
        return {
            "daily_allowance_remaining_seconds": 47 * 60,
            "one_time_grant_remaining_seconds": 15 * 60,
            "additional_one_time_grant_seconds": 0,
            "calculated_active_extension_seconds": 47 * 60,
        }

    def set_preferences(self, uid, value):
        self._preferences[uid] = copy.deepcopy(value)
        return self.get_preferences(uid)

    def set_parent_control(self, uid, enabled, daily_limit_minutes):
        preferences = self._preferences[uid]
        preferences["parent_control_enabled"] = enabled
        preferences["daily_time_limit_minutes"] = daily_limit_minutes
        return self.get_preferences(uid)

    def revoke_one_time_grant(self, _uid):
        return None


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


def _duration_label(seconds):
    seconds = max(0, int(seconds))
    minutes, remaining_seconds = divmod(seconds, 60)
    if remaining_seconds:
        return f"{minutes}m {remaining_seconds}s"
    return f"{minutes}m"


def _time_status_subtitle(status):
    daily = _duration_label(status["daily_allowance_remaining_seconds"])
    grant = _duration_label(status["one_time_grant_remaining_seconds"])
    additional = _duration_label(status["additional_one_time_grant_seconds"])
    calculated = _duration_label(status["calculated_active_extension_seconds"])
    return (
        "Formula: max(Daily allowance remaining, One-time grant remaining) "
        "+ Additional one-time grant\n"
        f"Daily allowance remaining: {daily}  •  One-time grant remaining: {grant}  •  "
        f"Additional one-time grant: {additional}\n"
        f"Calculated ActiveExtension: max({daily}, {grant}) + {additional} = {calculated}"
    )


class ParentWindow(Adw.ApplicationWindow):
    def __init__(self, application, *, client_factory=BrokerClient):
        super().__init__(application=application, title=app_name())
        # The application ID ends in ``.Parent``, but the shared installed
        # desktop icon uses the product-wide name.
        self.set_icon_name(APPLICATION_ICON_NAME)
        self.set_default_size(DEFAULT_WINDOW_WIDTH, 1168)
        self.set_size_request(820, 700)
        self._client = client_factory()
        self._users = []
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
        self.connect("close-request", self._close_requested)
        LOG.info("window initialized app_count=%d", len(self._rows))
        GLib.idle_add(self._load_users)

    def _build(self):
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar(css_classes=["parent-header"])
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
        menu = Gio.Menu()
        menu.append("Help", "win.help")
        menu.append("About", "win.about")
        action_group = Gio.SimpleActionGroup()
        self.insert_action_group("win", action_group)
        help_action = Gio.SimpleAction.new("help", None)
        help_action.connect("activate", lambda *_args: open_help())
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._show_about)
        action_group.add_action(help_action)
        action_group.add_action(about_action)
        # ``view-more-symbolic`` is the standard GNOME vertical-ellipsis icon.
        # Keep the button on the window so it remains visible and is easy to
        # exercise from UI tests.
        self._menu_button = Gtk.MenuButton(
            icon_name="view-more-symbolic",
            menu_model=menu,
            tooltip_text="Menu",
        )
        describe_control(
            self._menu_button, "Parent app menu",
            "Open help and product information.",
        )
        header.pack_end(self._menu_button)
        toolbar.add_top_bar(header)
        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["preferences-page"],
        )
        toolbar.set_content(content)
        self._toasts = Adw.ToastOverlay(child=toolbar)
        self.set_content(self._toasts)

        # The selected child applies to both tabs. Keep the picker outside the
        # stack and use the same clamp as the tab bar and both page cards so
        # every major surface shares one visual column.
        account_section = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=18,
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
        self._account = Gtk.DropDown(
            model=Gtk.StringList.new([]), hexpand=True,
            css_classes=["account-picker"],
        )
        describe_control(
            self._account, "Selected child",
            "Choose the child whose screen time and app policy are displayed.",
        )
        # A DropDown's visible selection is its AT-SPI name.  Connect the
        # enduring section label as well, so assistive technology identifies
        # the control's purpose independently of the selected child.
        account_label.set_mnemonic_widget(self._account)
        self._account.set_factory(self._account_factory())
        self._account.set_list_factory(self._account_factory())
        self._account_changed_handler = self._account.connect(
            "notify::selected", self._account_changed
        )
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
        self._revoke = Gtk.Button(
            child=revoke_content, valign=Gtk.Align.FILL,
            width_request=320, css_classes=["revoke-grant-button"],
            sensitive=False,
        )
        describe_control(
            self._revoke, "Revoke one-time access",
            "Remove the selected child's active one-time grant after confirmation.",
        )
        self._revoke.connect("clicked", self._confirm_revoke)
        account_actions.append(self._revoke)
        account_section.append(account_actions)
        self._no_users_message = Gtk.Label(
            label="No interactive non-administrator account was found.",
            xalign=0, wrap=True, visible=False,
            css_classes=["account-empty-message"],
        )
        account_section.append(self._no_users_message)
        content.append(Adw.Clamp(
            child=account_section,
            maximum_size=CONTENT_MAX_WIDTH,
            tightening_threshold=CONTENT_MAX_WIDTH,
            css_classes=["account-clamp"],
        ))

        pages = Adw.ViewStack(vexpand=True)
        self._pages = pages
        switcher = Adw.ViewSwitcher(
            stack=pages,
            policy=Adw.ViewSwitcherPolicy.WIDE,
            hexpand=True,
            css_classes=["main-view-switcher"],
        )
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
        pages.add_titled_with_icon(
            screen_limits_page, "screen-limits", "Screen Limits", "alarm-symbolic",
        )

        screen_limits = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["screen-limits-card"],
        )
        card_header = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=2,
            css_classes=["screen-limits-card-header"],
        )
        card_header.append(Gtk.Label(
            label="Screen Limits",
            xalign=0,
            css_classes=["screen-limits-title"],
        ))
        self._screen_limits_description = Gtk.Label(
            label="Manage how much screen time this child can have each day.",
            xalign=0,
            wrap=True,
            css_classes=["screen-limits-description"],
        )
        card_header.append(self._screen_limits_description)
        screen_limits.append(card_header)

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
        self._daily_limit = Gtk.MenuButton(label=_daily_limit_label(0))
        self._daily_limit.set_sensitive(False)
        self._daily_limit.set_valign(Gtk.Align.CENTER)
        describe_control(
            self._daily_limit, "Daily time allowance",
            "Choose the selected child's daily screen-time allowance.",
        )
        self._daily_limit.set_popover(self._daily_limit_popover())
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
        self._time_status.add_prefix(self._setting_icon("hourglass-symbolic"))
        self._time_status_value = Gtk.Label(
            label="Loading…", valign=Gtk.Align.CENTER,
            css_classes=["remaining-time-value"],
        )
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
        pages.add_titled_with_icon(
            app_limits_page, "app-limits", "App Limits", "view-grid-symbolic",
        )

        app_limits = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["app-limits-card"],
        )
        app_limits_header = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=3,
            css_classes=["app-limits-card-header"],
        )
        app_limits_header.append(Gtk.Label(
            label="App Limits", xalign=0,
            css_classes=["app-limits-title"],
        ))
        self._app_limits_description = Gtk.Label(
            label="Manage which apps this child can use and how they are accessed.",
            xalign=0, wrap=True,
            css_classes=["app-limits-description"],
        )
        app_limits_header.append(self._app_limits_description)
        app_limits.append(app_limits_header)

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
            MATCH_RULES, self._match_rule_filters, self._match_rule_filter_icon))
        headers.add_suffix(self._policy_column_heading(
            "Access Rule", self._policy_selector_slot(), "access-rule-header",
            STATES, self._access_rule_filters, self._access_rule_filter_icon))
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

    def _account_factory(self):
        factory = Gtk.SignalListItemFactory()

        def setup(_factory, item):
            row = Gtk.Box(spacing=14, valign=Gtk.Align.CENTER)
            row.append(Adw.Avatar(
                size=50, show_initials=True, css_classes=["account-avatar"],
            ))
            row.append(Gtk.Label(
                xalign=0, hexpand=True, ellipsize=3,
                css_classes=["account-name"],
            ))
            item.set_child(row)

        def bind(_factory, item):
            row = item.get_child()
            avatar = row.get_first_child()
            name = item.get_item().get_string()
            row.get_last_child().set_label(name)
            avatar.set_text(name)
            icon_file = ""
            position = item.get_position()
            if position < len(self._users):
                icon_file = self._users[position][2]
            texture = None
            if icon_file:
                try:
                    texture = Gdk.Texture.new_from_filename(icon_file)
                except GLib.Error:
                    texture = None
            avatar.set_custom_image(texture)

        factory.connect("setup", setup)
        factory.connect("bind", bind)
        return factory

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
        collapse.connect(
            "clicked", lambda *_args: self._time_status.set_expanded(False),
        )
        heading.append(collapse)
        panel.append(heading)

        formula = Gtk.Label(xalign=0, wrap=True, css_classes=["calculation-formula"])
        formula.set_markup(
            "<b>Formula:</b> max(Daily allowance remaining, One-time grant remaining) "
            "\n+ Additional one-time grant"
        )
        panel.append(formula)

        equation = Gtk.Box(spacing=8, css_classes=["calculation-equation"])
        self._time_operand_values = []

        def operand(label):
            column = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=6,
                hexpand=True,
                homogeneous=True,
            )
            column.append(Gtk.Label(
                label=label, justify=Gtk.Justification.CENTER,
                css_classes=["equation-label"],
            ))
            value = Gtk.Label(label="—", css_classes=["equation-value"])
            column.append(value)
            self._time_operand_values.append(value)
            return column

        maximum = Gtk.Box(
            spacing=8, hexpand=True, css_classes=["equation-maximum"],
        )
        maximum.append(Gtk.Label(
            label="max(", css_classes=["equation-function"],
        ))
        maximum.append(operand("Daily allowance remaining"))
        maximum.append(Gtk.Label(
            label=",", css_classes=["equation-separator"],
        ))
        maximum.append(operand("One-time grant remaining"))
        maximum.append(Gtk.Label(
            label=")", css_classes=["equation-function"],
        ))
        equation.append(maximum)
        equation.append(Gtk.Label(label="+", css_classes=["equation-operator"]))
        equation.append(operand("Additional one-time grant"))
        equation.append(Gtk.Label(label="=", css_classes=["equation-operator"]))
        equation.append(operand("Calculated ActiveExtension"))
        panel.append(equation)
        return panel

    def _policy_column_heading(self, label, slot, css_class, items, selected,
                               icon_factory):
        """Overlay a filter heading on a measurement-matched, inert policy control."""
        overlay = Gtk.Overlay(css_classes=["app-policy-heading", css_class])
        overlay.set_child(slot)
        trigger = Gtk.Button(
            tooltip_text=f"Filter by {label}",
            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
            css_classes=["app-policy-filter"],
        )
        describe_control(
            trigger, f"Filter {label}",
            f"Choose which {label.casefold()} values are shown in the app list.",
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
        popover.set_parent(trigger)
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
            choice.connect(
                "toggled", self._column_filter_toggled, item["id"], selected,
                trigger, items,
            )
            menu.append(choice)
        popover.set_child(menu)
        trigger.connect("clicked", lambda *_args: popover.popup())
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
        for state in STATES:
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
        card.append(header)

        sections = Gtk.Box(css_classes=["policy-legend-sections"])
        sections.append(self._legend_section(
            "App Access (What happens)", STATES, {
                "allowed": "App can always be used",
                "permanent": "App is completely blocked and can only be allowed by admins",
                "conditional": "App is blocked and can be granted one-time extension per child request if time limit is enabled",
            }, access=True,
        ))
        sections.append(Gtk.Separator(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["policy-legend-divider"],
        ))
        sections.append(self._legend_section(
            "Match Rule (How apps are matched)", MATCH_RULES, {
                "pattern": "Matches by pattern\n to cover exec path with changing version numbers (e.g., Lunar Client-*-ow_*.AppImage)",
                "precise": "Matches exact app path\n(e.g., /usr/bin/firefox)",
            }, access=False,
        ))

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
                label=item["label"], xalign=0, wrap=True, width_chars=22,
                css_classes=["policy-legend-item-title"],
            ), 1, row, 1, 1)
            rows.attach(Gtk.Label(
                label=descriptions[item["id"]], xalign=0, wrap=True,
                width_chars=22, hexpand=True,
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

    def _clear_catalog_rows(self):
        for row in self._app_rows:
            self._apps_group.remove(row)
        self._rows = []
        self._app_rows = []

    def _add_app_row(self, app):
        row = Adw.ActionRow(
            title=app["name"], subtitle=app["description"] or app["id"],
            css_classes=["app-policy-row"],
        )
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
        for state in STATES:
            button = Gtk.ToggleButton(
                tooltip_text=state["label"],
                css_classes=["policy-choice", state["css"]],
                child=Gtk.Image(icon_name=state["icon"], pixel_size=19),
                valign=Gtk.Align.CENTER,
            )
            describe_control(
                button, f"{app['name']} access rule: {state['label']}",
                f"Set the selected child's access rule for {app['name']} to {state['label']}.",
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
        LOG.info(
            "application table ready target=[Child user] row_count=%d",
            len(self._rows),
        )
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
                LOG.warning("broker operation failed error_type=%s", type(caught).__name__)
                self._toast(f"Could not complete the change: {caught}")
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
        LOG.info("managed-user discovery started")
        self._run(self._client.list_users, self._users_loaded, self._users_failed)
        return GLib.SOURCE_REMOVE

    def _users_failed(self, error):
        """Fail closed before exposing a parent-management surface."""
        LOG.warning(
            "managed-user discovery failed; closing management window error_type=%s",
            type(error).__name__,
        )
        self.close()
        self.get_application().quit()

    def _users_loaded(self, users):
        self._users = [parse_listed_user(user) for user in users]
        LOG.info("managed-user discovery completed count=%d", len(self._users))
        if self._users:
            # Kick off the selected child's catalog before the account picker
            # model is rebuilt so App Limits work does not wait on UI setup.
            self._ensure_apps_load(self._users[0][0])
        self._account.handler_block(self._account_changed_handler)
        try:
            self._account.set_model(Gtk.StringList.new(
                [label for _uid, label, _icon in self._users]
            ))
            if self._users:
                self._account.set_selected(0)
        finally:
            self._account.handler_unblock(self._account_changed_handler)

        if self._users:
            self._load_selected()
        else:
            self._no_users_message.set_visible(True)
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
        selected = self._account.get_selected()
        child_name = self._users[selected][1].split(maxsplit=1)[0]
        self._screen_limits_description.set_label(
            f"Manage how much screen time {child_name} can have each day."
        )
        self._app_limits_description.set_label(
            f"Manage which apps {child_name} can use and how they are accessed."
        )
        self._revoke_description.set_label(
            f"Revokes one-time screen time and app access grants granted to {child_name}."
        )
        self._loading = True
        # Do not carry a previous child's grant state into this selection while
        # its authoritative time status is still loading.
        self._remaining_time_seconds = None
        self._time_status_value.set_label("Loading…")
        for value in self._time_operand_values:
            value.set_label("—")
        LOG.info("preferences load started target=[Child user]")
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
        LOG.info("application catalog load started target=[Child user]")
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
        LOG.info(
            "application catalog loaded target=[Child user] app_count=%d",
            len(applications),
        )
        self._update_apps_loading_ui()
        self._maybe_populate_app_table()

    def _apps_failed(self, uid, generation, error):
        if generation != self._apps_load_generation or uid != self._selected_uid():
            return
        self._apps_loading = False
        LOG.warning("application catalog load failed target=[Child user] error_type=%s",
                    type(error).__name__)
        self._toast(f"Could not load installed apps: {error}")
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
        was_loading = self._loading
        self._loading = True
        try:
            for row in self._rows:
                state = preferences["apps"].get(row.app["id"], {}).get("state", "allowed")
                row.policy_buttons[state].set_active(True)
                policy = preferences["apps"].get(row.app["id"], {})
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
        LOG.info("preferences loaded target=[Child user] enabled=%s policy_count=%d",
                 preferences["parent_control_enabled"],
                 len(preferences["apps"]))
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
        durations = (
            _duration_label(status["daily_allowance_remaining_seconds"]),
            _duration_label(status["one_time_grant_remaining_seconds"]),
            _duration_label(status["additional_one_time_grant_seconds"]),
            _duration_label(status["calculated_active_extension_seconds"]),
        )
        self._time_status_value.set_label(
            _minutes_label(max(0, status["calculated_active_extension_seconds"] // 60))
        )
        for label, duration in zip(self._time_operand_values, durations):
            label.set_label(duration)
        LOG.info(
            "remaining time loaded target=[Child user] daily=%d grant=%d additional=%d calculated=%d",
            status["daily_allowance_remaining_seconds"],
            status["one_time_grant_remaining_seconds"],
            status["additional_one_time_grant_seconds"],
            status["calculated_active_extension_seconds"],
        )
        self._set_apps_sensitive(True)
        self._load_pending_time_status_refresh()

    def _time_status_failed(self, uid, error):
        self._time_status_loading = False
        if uid != self._selected_uid():
            self._time_status_refresh_pending = False
            self._load_time_status()
            return
        LOG.warning("remaining-time load failed target=[Child user] error_type=%s",
                    type(error).__name__)
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
        for value in self._time_operand_values:
            value.set_label("—")

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
        return GLib.SOURCE_CONTINUE

    def _close_requested(self, *_args):
        self._cancel_time_status_retry()
        self._cancel_custom_daily_limit_save()
        if self._time_status_refresh_id:
            GLib.source_remove(self._time_status_refresh_id)
            self._time_status_refresh_id = 0
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
        dialog = Adw.MessageDialog.new(
            self, "Revoke one-time grant?",
            "This will revoke one-time screen time and access to soft blocked apps "
            f"granted to {child_name}, close their running blocked apps, and "
            "lock their desktop when no time remains. "
            "Their remaining daily time allowance is not impacted.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("revoke", "Revoke grant")
        dialog.set_response_appearance("revoke", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._revoke_response)
        dialog.present()

    def _revoke_response(self, _dialog, response):
        if response != "revoke":
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
        choices = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        for index, minutes in enumerate(DAILY_LIMIT_PRESETS):
            choice = Gtk.Button(label=_daily_limit_label(minutes), hexpand=True)
            describe_control(
                choice, _daily_limit_label(minutes),
                f"Set the selected child's daily allowance to {_daily_limit_label(minutes)}.",
            )
            choice.connect("clicked", self._daily_limit_changed, index)
            choices.append(choice)
        custom = Gtk.Button(label="Custom value", hexpand=True)
        describe_control(custom, "Custom value", "Enter a custom daily allowance in minutes.")
        custom.connect("clicked", self._daily_limit_changed, CUSTOM_DAILY_LIMIT_INDEX)
        choices.append(custom)
        return Gtk.Popover(child=Gtk.ScrolledWindow(
            child=choices, min_content_height=360, min_content_width=220,
        ))

    def _daily_limit_changed(self, _button, selected):
        if self._loading or self._selected_uid() is None:
            return
        self._daily_limit_selected = selected
        is_custom = selected == CUSTOM_DAILY_LIMIT_INDEX
        self._daily_limit.set_label("Custom value" if is_custom else _daily_limit_label(
            DAILY_LIMIT_PRESETS[selected],
        ))
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
        LOG.info(
            "parent-control change started target=[Child user] enabled=%s daily_limit_minutes=%d",
            enabled, daily_limit_minutes,
        )
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
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Reset to Default", Gtk.ResponseType.APPLY)
        dialog.add_button("Save", Gtk.ResponseType.OK)
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
        LOG.info("app-policy auto-save started target=[Child user] policy_count=%d",
                 len(value["apps"]))
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
        LOG.info("preference auto-save completed target=[Child user]")
        if refresh_time_status:
            self._load_time_status()
        self._start_next_save()
        if not self._save_in_progress and hasattr(self, "_set_apps_sensitive"):
            self._set_apps_sensitive(True)

    def _save_failed(self, uid, setting, error):
        self._save_in_progress = False
        LOG.warning("preference auto-save failed target=[Child user] setting=%s error_type=%s",
                    setting, type(error).__name__)
        self._toast(f"Could not save {setting}: {error}")
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
    def __init__(self, *, preview=False, client_factory=None):
        super().__init__(application_id="com.puffyslippers.OhNoParentControl.Parent")
        self._preview = preview
        # Component tests inject a scripted broker through the same constructor
        # seam used by the preview.  Production continues to construct only the
        # system-D-Bus client below, so this does not create a test-only broker
        # path or weaken the broker's caller authorization boundary.
        self._client_factory = client_factory or (
            PreviewBrokerClient if preview else BrokerClient
        )
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
            LOG.info("preview stylesheet reloaded")
        if any(path.suffix == ".py" for path in changed_paths):
            LOG.info("preview source changed; relaunching")
            os.execv(sys.executable, sys.orig_argv)
        return GLib.SOURCE_REMOVE

    def do_activate(self):
        window = self.get_active_window() or ParentWindow(
            self, client_factory=self._client_factory,
        )
        if self._css_provider is None:
            self._css_provider = Gtk.CssProvider()
            self._load_stylesheet()
            Gtk.StyleContext.add_provider_for_display(
                window.get_display(), self._css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
        if self._preview:
            self._watch_preview_files()
        window.present()


def _can_start(client_factory=BrokerClient):
    # Do this before creating a GTK window so manually invoking the launcher
    # does not expose the Parent App to a standard account.  ListManagedUsers
    # is deliberately broker-authorized and therefore uses the same
    # AccountsService role source as all management operations.
    try:
        client_factory().list_users()
    except Exception:
        return False
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preview", action="store_true",
        help="render the parent UI with fixture data and no privileged services",
    )
    args = parser.parse_args(argv)
    if not args.preview:
        configure_logging()
    else:
        logging.basicConfig(level=logging.INFO)
    if not args.preview and not _can_start():
        LOG.warning("parent app launch denied or broker unavailable")
        return 1
    LOG.info("parent app starting")
    return Application(preview=args.preview).run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
