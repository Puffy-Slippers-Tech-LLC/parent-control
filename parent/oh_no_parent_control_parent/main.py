"""Administrator-facing GTK 4/libadwaita parent-control application."""

from __future__ import annotations

from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.translation_widgets import (
    localized, set_text, accessible_text, context_for,
)

import argparse
import hashlib
import math
from common.oh_no_parent_control_ui.diagnostic_events import get_logger, error_code
from common.oh_no_parent_control_ui.diagnostic_events import configure_console, log_version
import os
import re
import sys
import threading
import time
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
from common.oh_no_parent_control_ui.duration import format_duration, parse_duration_minutes
from common.oh_no_parent_control_ui.application_ui import ApplicationUI, bind_ui
from common.oh_no_parent_control_ui.app_policy import replacement_policy_ids
from common.oh_no_parent_control_ui.feedback import FeedbackDialog
from common.oh_no_parent_control_ui.errors import (
    ErrorHandler, GENERIC_TITLE, GENERIC_DETAIL, install_exception_hooks,
    show_startup_error, show_update_required,
)
from common.oh_no_parent_control_ui.user_icon import parse_listed_user

from .client import BrokerClient, configure_logging, management_access_denied, broker_reboot_required
from .language_dialog import LanguageDialog
from .whats_new_dialog import WhatsNewDialog

LOG = get_logger("parent")
APPLICATION_ICON_NAME = "com.puffyslippers.OhNoParentControl"
ACCESSIBILITY_INTERFACE = "com.puffyslippers.OhNoParentControl.Accessibility1"
ACCESSIBILITY_XML = f"""<node>
  <interface name="{ACCESSIBILITY_INTERFACE}">
    <method name="GetNativeSurfaceTransform">
      <arg name="surface_id" type="s" direction="in"/>
      <arg name="x" type="d" direction="out"/>
      <arg name="y" type="d" direction="out"/>
    </method>
  </interface>
</node>"""
STATES = (
    {
        "id": "allowed",
        "label": m.ALWAYS_ALLOWED,
        "icon": "emblem-ok-symbolic",
        "css": "policy-allowed",
    },
    {
        "id": "permanent",
        "label": m.HARD_BLOCKED,
        "icon": "window-close-symbolic",
        "css": "policy-hard-blocked",
    },
    {
        "id": "conditional",
        "label": m.SOFT_BLOCKED,
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
        "label": m.PATTERN_MATCH,
        "glyph": "***",
        "css": "match-rule-pattern",
        "description": m.MATCHES_VERSIONED_FILENAMES_USING_A_WILDCARD,
    },
    {
        "id": "precise",
        "label": m.PRECISE_EXECUTION_PATH,
        "glyph": "ABC",
        "css": "match-rule-precise",
        "description": m.MATCHES_ONLY_THIS_EXACT_EXECUTABLE_PATH,
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
    return m.minute_count(minutes)


def _daily_limit_label(minutes):
    """Format the compact set of daily allowance menu choices."""
    if minutes < 60:
        return _minutes_label(minutes)
    hours = minutes / 60
    return m.hour_count(hours)


def _daily_limit_selection(minutes):
    """Return the menu index for a stored allowance and whether it is custom."""
    try:
        return DAILY_LIMIT_PRESETS.index(minutes), False
    except ValueError:
        return CUSTOM_DAILY_LIMIT_INDEX, True


def _daily_limit_keyboard_selection(text):
    """Resolve explicit minute/hour input to an offered preset, never round."""
    minutes = parse_duration_minutes(text)
    if minutes not in DAILY_LIMIT_PRESETS:
        return None
    return DAILY_LIMIT_PRESETS.index(minutes)


def _time_status_subtitle(status):
    grant = format_duration(status["one_time_grant_remaining_seconds"])
    daily = format_duration(status["daily_allowance_remaining_seconds"])
    remaining = format_duration(status["calculated_active_extension_seconds"])
    return (
        m.DAILY_ALLOWANCE_REMAINING_B_DAILY_S_B_ONE_TIME_GRANT_REMAINING_B % {'daily': daily, 'grant': grant, 'remaining': remaining}
    )


def _app_automation_key(app_id):
    """Return a stable, non-identifying ID fragment for a launcher identity."""
    return hashlib.sha256(app_id.encode("utf-8")).hexdigest()[:16]


class DailyLimitSelector(Gtk.MenuButton):
    """Keep keyboard focus on the identified selector rather than its toggle."""

    def do_grab_focus(self):
        return Gtk.Widget.do_grab_focus(self)

    def do_focus(self, direction):
        popover = self.get_popover()
        if popover is not None and popover.get_visible():
            return popover.child_focus(direction)
        # One tab stop for the public selector, without an extra anonymous
        # toggle stop. The popup retains GTK's ordinary focus traversal.
        return False if self.has_focus() else self.grab_focus()


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
        self._choice_buttons = {}
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
        self.set_create_popup_func(self._prepare_popover)
        self._show_selection()

        bind_ui(self, get_value=self._ui_value, set_value=self._ui_select,
                choices=lambda: [str(uid) for uid, _label, _icon in self._users])

    def _ui_value(self):
        return str(self._users[self._selected][0]) if self._selected < len(self._users) else ""

    def _ui_select(self, value):
        if not isinstance(value, str) or value not in self._choice_buttons:
            raise ValueError("unknown child account UID")
        self._choice_buttons[value].emit("clicked")

    def _prepare_popover(self, _button):
        # Ellipsized account labels have a tiny minimum width. Size the menu
        # from the visible selector on every open, including after a resize.
        self.get_popover().set_size_request(self.get_width(), -1)

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
        name = localized(Gtk.Label,
            label=label, xalign=0, hexpand=True, ellipsize=3,
            css_classes=["account-name"],
        )
        row.append(name)
        # This account identity exposes the actual name label. Generic box
        # text also collects the avatar's decorative initials when no image
        # is available, making identity readback depend on the account icon.
        bind_ui(row, get_text=name.get_text)
        return row

    def set_users(self, users, selected):
        users = tuple(users)
        if len({uid for uid, _label, _icon in users}) != len(users):
            raise ValueError("child selector requires unique account UIDs")
        self._users = users
        self._choice_buttons = {}
        while child := self._choices.get_first_child():
            self._choices.remove(child)
        focus_actions = Gio.SimpleActionGroup()
        for index, (uid, label, icon_file) in enumerate(users):
            choice = localized(Gtk.Button, 
                child=self._content(
                    label, icon_file, f"parent-child-choice-{uid}-content",
                ),
                css_classes=["parent-account-choice"],
            )
            describe_control(
                choice, m.CHILD_ACCOUNT_LABEL_S % {'label': label},
                m.MANAGE_SCREEN_TIME_AND_APP_POLICY_FOR_LABEL_S % {'label': label},
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
            self._choice_buttons[str(uid)] = choice
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
            description = m.SELECTED_CHILD_LABEL_S % {'label': label}
        else:
            content = localized(Gtk.Label, label=m.NONE, xalign=0, hexpand=True)
            set_automation_id(content, "parent-child-selected-none")
            description = m.NO_CHILD_ACCOUNT_IS_SELECTED
        self.set_child(content)
        describe_control(self, m.SELECTED_CHILD, description)


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
        self._own_language = None
        self._applied_language = None
        context_for(self)
        self._language_dialog = None
        self._language_loading = False
        self._language_requested = False
        self._language_ready = False
        self._whats_new_record = None
        self._whats_new_loading = False
        self._whats_new_loaded_once = False
        self._whats_new_dialog = None
        self._whats_new_auto_attempted = False
        self._whats_new_wait_id = 0
        self._closed = False
        self._fatal_discovery_error = False
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
        self._active_save = None
        self._pending_saves = []
        self._restore_preferences_uid = None
        self._custom_daily_limit_save_id = 0
        self._time_status_loading = False
        self._time_status_refresh_pending = False
        self._time_status_retry_id = 0
        self._time_status_retry_count = 0
        self._remaining_time_seconds = None
        self._has_running_soft_blocked_apps = False
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
        self._content_built = False
        self._time_status_refresh_id = 0
        self._account_refresh_id = 0
        self._toasts = Adw.ToastOverlay()
        overlay = Gtk.Overlay(child=self._toasts)
        self._language_shade = Gtk.Revealer(
            can_target=False,
            transition_type=Gtk.RevealerTransitionType.CROSSFADE,
            transition_duration=180,
            child=Gtk.Box(css_classes=["parent-language-shade"]),
        )
        overlay.add_overlay(self._language_shade)
        self.set_content(overlay)
        self.connect("close-request", self._close_requested)
        GLib.idle_add(self._load_language)

    def _finish_startup(self):
        if self._content_built or self._closed:
            return GLib.SOURCE_REMOVE
        self._build()
        self._content_built = True
        self._time_status_refresh_id = GLib.timeout_add_seconds(
            30, self._refresh_time_status,
        )
        self._account_refresh_id = GLib.timeout_add_seconds(
            ACCOUNT_REFRESH_SECONDS, self._refresh_users,
        )
        LOG.info("parent.002", app_count=len(self._rows))
        self._load_users()
        self._load_whats_new()
        return GLib.SOURCE_REMOVE

    def _language_dialog_mapped(self, dialog):
        self._language_shade.set_reveal_child(True)
        if self._content_built:
            return
        # Mapping alone precedes painting. Yield through the chooser's first
        # frame before constructing management widgets behind the modal.
        clock = dialog.get_frame_clock()

        def painted(clock):
            clock.disconnect(handler)
            GLib.idle_add(self._finish_startup)

        handler = clock.connect("after-paint", painted)

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
        accessible_text(title_logo, 
            [Gtk.AccessibleProperty.LABEL], [m.APP_NAME_S_LOGO % {'app_name': app_name()}],
        )
        title_brand.append(title_logo)
        title_brand.append(localized(Adw.WindowTitle, 
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

        menu_items = {}
        for identity, label, callback in (
            ("preferences", m.PREFERENCES, self._show_preferences),
            ("help", m.HELP, open_help),
            ("whats-new", m.WHATS_NEW, self._show_whats_new),
            ("about", m.ABOUT, self._show_about),
        ):
            item = localized(Gtk.Button, child=localized(Gtk.Label, label=label, xalign=0),
                              css_classes=["parent-menu-item"])
            describe_control(item, label, label,
                             automation_id=f"parent-menu-{identity}")
            item.connect("clicked", activate_menu_item, callback)
            menu.append(item)
            menu_items[identity] = item
        self._whats_new_menu_item = menu_items['whats-new']
        self._whats_new_menu_item.set_visible(False)
        # Explicit circular dots keep the heavier ellipsis consistent across
        # icon themes and display scales.
        dots = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3,
                       halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        for _ in range(3):
            dots.append(Gtk.Box(css_classes=["parent-menu-dot"]))
        self._menu_button = localized(Gtk.MenuButton, 
            child=dots,
            valign=Gtk.Align.CENTER,
            popover=popover,
            tooltip_text=m.MENU,
            css_classes=["parent-header-menu"],
        )
        describe_control(
            self._menu_button, m.PARENT_APP_MENU,
            m.OPEN_PREFERENCES_HELP_AND_PRODUCT_INFORMATION,
            automation_id="parent-menu-button",
        )
        def choose_menu(value):
            if not isinstance(value, str) or value not in menu_items:
                raise ValueError("unknown Parent menu command")
            item = menu_items[value]
            if not item.get_visible() or not item.is_sensitive():
                raise ValueError("Parent menu command is unavailable")
            item.emit("clicked")
        bind_ui(self._menu_button, set_value=choose_menu,
                choices=lambda: [identity for identity, item in menu_items.items()
                                 if item.get_visible()])
        # Keep native window actions and the desktop's decoration layout, with
        # the application menu immediately before the window controls.
        header_actions = Gtk.Box(spacing=4, valign=Gtk.Align.CENTER)
        feedback_content = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)
        feedback_content.append(Gtk.Image(
            icon_name="chat-message-new-symbolic", pixel_size=20,
        ))
        feedback_content.append(localized(Gtk.Label, label=m.FEEDBACK))
        feedback_button = localized(Gtk.Button, 
            child=feedback_content, css_classes=["parent-header-feedback"],
            valign=Gtk.Align.CENTER,
        )
        describe_control(feedback_button, m.FEEDBACK, m.SEND_FEEDBACK_ABOUT_THE_APP,
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
        self._language_readiness = content
        set_automation_id(content, "parent-language-loading")
        toolbar.set_content(content)
        self._policy_warning = localized(Gtk.Label, 
            wrap=True, xalign=0, visible=False,
            margin_start=18, margin_end=18, margin_top=8, margin_bottom=8,
            css_classes=["warning"],
        )
        set_automation_id(self._policy_warning, "parent-policy-warning")
        toolbar.add_top_bar(self._policy_warning)
        self._toasts.set_child(toolbar)

        # The selected child applies to both tabs. Keep the picker outside the
        # stack and use the same clamp as the tab bar and both page cards so
        # every major surface shares one visual column.
        account_section = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            hexpand=True,
            css_classes=["account-section"],
        )
        account_label = localized(Gtk.Label, 
            label=m.CHILD_ACCOUNT, xalign=0, css_classes=["section-title"],
        )
        account_section.append(account_label)
        account_actions = Gtk.Box(
            hexpand=True,
            css_classes=["account-actions"],
        )
        self._account = ParentAccountSelector(self._account_changed)
        describe_control(
            self._account, m.SELECTED_CHILD,
            m.CHOOSE_THE_CHILD_WHOSE_SCREEN_TIME_AND_APP_POLICY_ARE_DISPLAYED,
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
        revoke_labels.append(localized(Gtk.Label, 
            label=m.REVOKE_ONE_TIME_GRANT_2, xalign=0,
            css_classes=["revoke-grant-title"],
        ))
        self._revoke_description = localized(Gtk.Label, 
            label=m.REVOKES_ONE_TIME_SCREEN_TIME_AND_APP_ACCESS_GRANTS,
            xalign=0, wrap=True, width_request=270, max_width_chars=36,
            css_classes=["revoke-grant-description"],
        )
        revoke_labels.append(self._revoke_description)
        revoke_content.append(revoke_labels)
        revoke_content.append(localized(Gtk.Label, 
            label=m.REVOKE, valign=Gtk.Align.CENTER,
            css_classes=["revoke-grant-action"],
        ))
        self._revoke = localized(Gtk.Button, 
            child=revoke_content, valign=Gtk.Align.FILL,
            width_request=320, css_classes=["revoke-grant-button"],
            sensitive=False,
        )
        describe_control(
            self._revoke, m.REVOKE_ONE_TIME_ACCESS,
            m.REMOVE_THE_SELECTED_CHILD_S_ACTIVE_ONE_TIME_GRANT_AFTER_CONFIRMA,
            automation_id="parent-revoke-button",
        )
        self._revoke.connect("clicked", self._confirm_revoke)
        account_actions.append(self._revoke)
        account_section.append(account_actions)
        self._no_users_message = localized(Gtk.Label, 
            label=m.NO_INTERACTIVE_NON_ADMINISTRATOR_ACCOUNT_WAS_FOUND,
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
        set_automation_id(pages, "parent-pages")
        page_buttons = {}
        switcher = Gtk.Box(
            homogeneous=True, hexpand=True,
            css_classes=["main-view-switcher"],
        )
        first_page_button = None
        for page_name, label, icon_name in (
            ("screen-limits", m.SCREEN_LIMITS, "alarm-symbolic"),
            ("app-limits", m.APP_LIMITS, "view-grid-symbolic"),
        ):
            button = localized(Gtk.ToggleButton, 
                child=Gtk.Box(spacing=8, halign=Gtk.Align.CENTER),
                hexpand=True,
            )
            button.get_child().append(Gtk.Image(icon_name=icon_name))
            button.get_child().append(localized(Gtk.Label, label=label))
            describe_control(
                button, label, m.SHOW_THE_LABEL_S_PAGE % {'label': label},
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
            page_buttons[page_name] = button
        def select_page(value):
            if not isinstance(value, str) or value not in page_buttons:
                raise ValueError("unknown Parent page")
            page_buttons[value].set_active(True)
        bind_ui(pages, get_value=pages.get_visible_child_name,
                set_value=select_page, choices=lambda: list(page_buttons))
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
            screen_limits_page, "screen-limits", m.SCREEN_LIMITS, "alarm-symbolic",
        )

        screen_limits = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["screen-limits-card"],
        )
        screen_limit_rows = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.NONE,
            css_classes=["screen-limit-rows"],
        )
        control_row = localized(Adw.ActionRow, 
            title=m.SCREEN_TIME_LIMIT_2,
            subtitle=m.TURN_ON_OFF_SCREEN_TIME_LIMIT,
            css_classes=["screen-limit-toggle-row"],
        )
        control_row.add_prefix(self._setting_icon("alarm-symbolic"))
        self._enabled = Gtk.Switch(
            valign=Gtk.Align.CENTER,
            sensitive=False,
            css_classes=["screen-limit-switch"],
        )
        describe_control(
            self._enabled, m.SCREEN_TIME_LIMIT,
            m.ENABLE_OR_DISABLE_DAILY_SCREEN_TIME_CONTROL_FOR_THE_SELECTED_CHI,
            automation_id="parent-screen-limit-toggle",
        )
        self._enabled.connect("notify::active", self._enabled_changed)
        control_row.add_suffix(self._enabled)
        screen_limit_rows.append(control_row)
        daily_limit_row = localized(Adw.ActionRow, 
            title=m.DAILY_TIME_ALLOWANCE_2,
            css_classes=["daily-limit-row"],
        )
        daily_limit_row.add_prefix(self._setting_icon("x-office-calendar-symbolic"))
        set_automation_id(daily_limit_row, "parent-daily-limit-row")
        # Expose each choice as a named button in a Gtk.Popover. Gtk.DropDown
        # presents a combo-box role here but no AT-SPI selection or action
        # interface, which prevents assistive technology from selecting a
        # daily allowance.
        self._daily_limit_selected = 0
        self._daily_limit_keyboard_text = ""
        self._daily_limit_keyboard_index = None
        self._daily_limit_choices = []
        self._daily_limit = localized(DailyLimitSelector,
            label=_daily_limit_label(0),
            focusable=True,
            css_classes=["daily-limit-button"],
        )
        self._daily_limit.set_sensitive(False)
        self._daily_limit.set_valign(Gtk.Align.CENTER)
        describe_control(
            self._daily_limit, m.DAILY_TIME_ALLOWANCE,
            m.CHOOSE_THE_SELECTED_CHILD_S_DAILY_SCREEN_TIME_ALLOWANCE,
            automation_id="parent-daily-limit-selector",
        )
        allowance_popover = self._daily_limit_popover()
        self._daily_limit.set_popover(allowance_popover)
        self._daily_limit.set_create_popup_func(allowance_popover.prepare)
        bind_ui(self._daily_limit, get_value=self._ui_daily_limit_value,
                set_value=self._ui_select_daily_limit,
                set_text=self._ui_select_daily_limit,
                choices=lambda: [f"{minutes}m" for minutes in DAILY_LIMIT_PRESETS] + ["custom"],
                aliases=("parent-daily-limit",))
        for widget in (self._daily_limit, allowance_popover):
            keys = Gtk.EventControllerKey.new()
            keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            keys.connect("key-pressed", self._daily_limit_key_pressed)
            widget.add_controller(keys)
        focus = Gtk.EventControllerFocus.new()
        focus.connect("leave", self._clear_daily_limit_keyboard)
        self._daily_limit.add_controller(focus)
        allowance_popover.connect("closed", self._clear_daily_limit_keyboard)
        daily_limit_row.add_suffix(self._daily_limit)
        screen_limit_rows.append(daily_limit_row)
        self._custom_daily_limit = localized(Adw.ActionRow, 
            title=m.CUSTOM_DAILY_ALLOWANCE,
            subtitle=m.ENTER_A_WHOLE_NUMBER_FROM_0_TO_1439,
            visible=False,
            css_classes=["custom-daily-limit-row"],
        )
        self._custom_daily_limit_entry = localized(Gtk.Entry, 
            text="30",
            input_purpose=Gtk.InputPurpose.DIGITS,
            width_chars=5,
            max_width_chars=5,
            valign=Gtk.Align.CENTER,
        )
        describe_control(
            self._custom_daily_limit_entry, m.CUSTOM_DAILY_ALLOWANCE,
            m.ENTER_A_WHOLE_NUMBER_OF_MINUTES_FROM_ZERO_THROUGH_1439,
            automation_id="parent-custom-daily-limit",
        )
        bind_ui(self._custom_daily_limit_entry,
                set_text=self._ui_set_custom_daily_limit_text,
                set_value=self._ui_set_custom_daily_limit_text)
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
        self._custom_daily_limit.add_suffix(localized(Gtk.Label, label=m.MINUTES))
        screen_limit_rows.append(self._custom_daily_limit)
        self._time_status = localized(Adw.ExpanderRow, 
            title=m.TODAY_S_REMAINING_TIME_2,
            subtitle=m.TIME_LEFT_FOR_TODAY,
            expanded=True,
            css_classes=["time-status-row"],
        )
        describe_control(
            self._time_status, m.TODAY_S_REMAINING_TIME,
            m.EXPAND_OR_COLLAPSE_THE_DAILY_AND_ONE_TIME_REMAINING_TIME_CALCULA,
            automation_id="parent-time-status",
        )
        def set_time_expanded(value):
            if type(value) is not bool:
                raise ValueError("remaining-time expansion requires a boolean")
            self._time_status.set_expanded(value)
        bind_ui(self._time_status, get_value=self._time_status.get_expanded,
                set_value=set_time_expanded)
        self._time_status.add_prefix(self._setting_icon("hourglass-symbolic"))
        self._time_status_value = localized(Gtk.Label, 
            label=m.LOADING, valign=Gtk.Align.CENTER,
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
            app_limits_page, "app-limits", m.APP_LIMITS, "view-grid-symbolic",
        )

        app_limits = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["app-limits-card"],
        )

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
        search_labels.append(localized(Gtk.Label, 
            label=m.INSTALLED_APPS, xalign=0,
            css_classes=["apps-panel-title"],
        ))
        search_labels.append(localized(Gtk.Label, 
            label=m.DESKTOP_APPIMAGE_FLATPAK_SNAP_AND_SYSTEM_LAUNCHERS,
            xalign=0, wrap=True,
            css_classes=["apps-panel-subtitle"],
        ))
        search_row.append(search_labels)
        self._search = localized(Gtk.SearchEntry, 
            placeholder_text=m.SEARCH_INSTALLED_APPS, valign=Gtk.Align.CENTER,
            width_chars=32, css_classes=["apps-search"],
        )
        describe_control(
            self._search, m.SEARCH_INSTALLED_APPS,
            m.FILTER_THE_SELECTED_CHILD_S_AVAILABLE_APPLICATIONS,
            automation_id="parent-app-search",
        )
        self._search.connect("search-changed", self._filter)
        self._search.set_sensitive(False)
        search_row.append(self._search)
        search_row.append(self._legend_button())
        apps_section.append(search_row)

        apps = localized(Adw.PreferencesGroup, css_classes=["apps-panel"])
        set_automation_id(apps, "parent-app-rows")
        self._apps_group = apps
        # PreferencesGroup places non-row widgets after its list. Keep the
        # headings in an ActionRow so they remain directly above app rows.
        # Each column measures both its translated heading and row controls.
        # Shared size groups keep every row aligned as the language changes.
        self._match_column_size = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        self._access_column_size = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        headers = localized(Adw.ActionRow, css_classes=["app-policy-columns"])
        headers.add_prefix(localized(Gtk.Label, label=m.ICON, xalign=0, hexpand=False,
                                     css_classes=["app-policy-column-header",
                                                  "app-policy-icon-header"]))
        set_text(headers, 'title', m.APP_NAME_AMP_DETAIL)
        headers.add_suffix(self._policy_column_heading(
            m.MATCH_RULE, self._match_rule_slot(), "match-rule-header",
            MATCH_RULES, self._match_rule_filters, self._match_rule_filter_icon,
            identity="match-rule", column_size=self._match_column_size))
        headers.add_suffix(self._policy_column_heading(
            m.ACCESS_RULE, self._policy_selector_slot(), "access-rule-header",
            STATES, self._access_rule_filters, self._access_rule_filter_icon,
            identity="access-rule", column_size=self._access_column_size))
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
        loading_content.append(localized(Gtk.Label, 
            label=m.LOADING_INSTALLED_APPS,
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
        heading.append(localized(Gtk.Label, 
            label=m.HOW_IT_S_CALCULATED, xalign=0, hexpand=True,
            css_classes=["calculation-title"],
        ))
        collapse = localized(Gtk.Button, 
            icon_name="go-up-symbolic",
            tooltip_text=m.HIDE_CALCULATION,
            css_classes=["calculation-collapse"],
        )
        describe_control(
            collapse, m.HIDE_REMAINING_TIME_CALCULATION,
            m.COLLAPSE_THE_REMAINING_TIME_CALCULATION_DETAILS,
            automation_id="parent-time-calculation-collapse",
        )
        collapse.connect(
            "clicked", lambda *_args: self._time_status.set_expanded(False),
        )
        heading.append(collapse)
        panel.append(heading)

        self._time_explanation = localized(Gtk.Label, 
            label="—", xalign=0, wrap=True, use_markup=True,
            css_classes=["calculation-formula"],
        )
        set_automation_id(self._time_explanation, "parent-time-explanation")
        panel.append(self._time_explanation)
        return panel

    def _policy_column_heading(self, label, slot, css_class, items, selected,
                               icon_factory, *, identity, column_size):
        """Size a column to fit both its filter heading and policy controls."""
        overlay = Gtk.Overlay(css_classes=["app-policy-heading", css_class])
        overlay.set_child(slot)
        trigger = localized(Gtk.MenuButton, 
            tooltip_text=m.FILTER_BY_LABEL_S % {'label': label},
            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
            css_classes=["app-policy-filter"],
        )
        describe_control(
            trigger, m.FILTER_LABEL_S % {'label': label},
            m.FILTER_DESCRIPTION,
            automation_id=f"parent-filter-{identity}",
        )
        trigger_content = Gtk.Box(
            spacing=4, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
        )
        trigger_content.append(localized(Gtk.Label, 
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
        filter_buttons = {}
        for item in items:
            choice = localized(Gtk.CheckButton, 
                active=item["id"] in selected,
                css_classes=["app-policy-filter-item"],
            )
            content = Gtk.Box(spacing=10, valign=Gtk.Align.CENTER)
            content.append(icon_factory(item))
            content.append(localized(Gtk.Label, 
                label=item["label"], xalign=0, hexpand=True,
                css_classes=["app-policy-filter-item-label"],
            ))
            choice.set_child(content)
            describe_control(
                choice, item["label"],
                m.SHOW_APPS_RULE,
                automation_id=f"parent-filter-{identity}-{item['id']}",
            )
            choice.connect(
                "toggled", self._column_filter_toggled, item["id"], selected,
                trigger, items,
            )
            menu.append(choice)
            filter_buttons[item["id"]] = choice
        def set_filter(value):
            if (not isinstance(value, list) or any(not isinstance(item, str) for item in value)
                    or len(set(value)) != len(value) or not set(value) <= set(filter_buttons)):
                raise ValueError("filter requires a list of distinct category IDs")
            for identity, button in filter_buttons.items():
                button.set_active(identity in value)
        bind_ui(trigger, get_value=lambda: [item["id"] for item in items
                                           if item["id"] in selected],
                set_value=set_filter, choices=lambda: list(filter_buttons))
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
        overlay.set_measure_overlay(trigger, True)
        column_size.add_widget(overlay)
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
        return localized(Gtk.Button, 
            can_focus=False, can_target=False,
            css_classes=[
                "match-rule-button", "policy-choice", "policy-legend-icon",
                item["css"],
            ],
            child=self._match_rule_image(item),
        )

    @staticmethod
    def _access_rule_filter_icon(item):
        return localized(Gtk.ToggleButton, 
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
        cell.append(localized(Gtk.Button, 
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
            selector.append(localized(Gtk.ToggleButton, 
                sensitive=False, can_focus=False, can_target=False,
                css_classes=["policy-choice", state["css"]],
            ))
        return selector

    def _legend_button(self):
        button = localized(Gtk.ToggleButton,
            active=False, icon_name="dialog-information-symbolic",
            tooltip_text=m.SHOW_LEGEND, valign=Gtk.Align.CENTER,
            css_classes=["policy-legend-toggle"],
        )
        describe_control(
            button, m.POLICY_LEGEND,
            m.EXPAND_OR_COLLAPSE_THE_APP_ACCESS_AND_MATCH_RULE_LEGEND,
            automation_id="parent-legend-toggle",
        )
        popover = Gtk.Popover(
            position=Gtk.PositionType.BOTTOM, halign=Gtk.Align.END,
            autohide=True, has_arrow=True,
            css_classes=["policy-legend-popover"],
        )
        popover.set_parent(button)
        self._legend_popover = popover
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
        labels.append(localized(Gtk.Label, 
            label=m.LEGEND, xalign=0, css_classes=["policy-legend-title"],
        ))
        subtitle = localized(Gtk.Label, 
            label=m.UNDERSTANDING_ACCESS_RULES_AND_MATCH_RULES,
            xalign=0, wrap=True, css_classes=["policy-legend-subtitle"],
        )
        labels.append(subtitle)
        header_content.append(labels)
        close = localized(Gtk.Button,
            icon_name="window-close-symbolic", tooltip_text=m.CLOSE,
            valign=Gtk.Align.START, css_classes=["flat", "policy-legend-close"],
        )
        describe_control(
            close, m.CLOSE, m.HIDE_LEGEND,
            automation_id="parent-legend-close",
        )
        close.connect("clicked", lambda *_: button.set_active(False))
        header_content.append(close)
        header_content.add_css_class("policy-legend-header")
        card.append(header_content)

        # Measure both columns at their allocated widths. A horizontal Box
        # can retain the wrapped labels' narrow-width height after its children
        # receive more space, leaving a large empty area below the legend.
        sections = Gtk.Grid(css_classes=["policy-legend-sections"])
        set_automation_id(sections, "parent-legend-content")
        sections.attach(self._legend_section(
            m.APP_ACCESS_WHAT_HAPPENS, APP_LIST_STATES, {
                "allowed": m.APP_CAN_ALWAYS_BE_USED,
                "permanent": m.APP_IS_COMPLETELY_BLOCKED_AND_CAN_ONLY_BE_ALLOWED_BY_ADMINS,
                "conditional": m.APP_IS_BLOCKED_AND_CAN_BE_GRANTED_ONE_TIME_EXTENSION_PER_CHILD_R,
            }, access=True,
        ), 0, 0, 1, 1)
        sections.attach(Gtk.Separator(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["policy-legend-divider"],
        ), 1, 0, 1, 1)
        sections.attach(self._legend_section(
            m.MATCH_RULE_HOW_APPS_ARE_MATCHED, MATCH_RULES, {
                "pattern": m.MATCHES_BY_PATTERN_TO_COVER_EXEC_PATH_WITH_CHANGING_VERSION_NUMB,
                "precise": m.MATCHES_EXACT_APP_PATH_E_G_USR_BIN_FIREFOX,
            }, access=False,
        ), 2, 0, 1, 1)

        card.append(sections)
        popover.set_child(card)
        button.connect("toggled", self._legend_toggled, popover)
        popover.connect("closed", lambda *_: button.set_active(False))
        # Keep the disclosure's existing boolean value/activation API. The
        # popover remains in the same App Limits subtree. GTK dismisses it on
        # an outside click, and the closed signal resets the disclosure.
        button.connect("unmap", lambda *_: button.set_active(False))
        return button

    def _legend_section(self, title, items, descriptions, *, access):
        section = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            hexpand=True,
            css_classes=["policy-legend-section"],
        )
        section.append(localized(Gtk.Label, 
            label=title, xalign=0, wrap=True,
            css_classes=["policy-legend-section-title"],
        ))
        rows = Gtk.Grid(
            row_spacing=12, column_spacing=16,
            css_classes=["policy-legend-rows"],
        )
        for row, item in enumerate(items):
            if access:
                icon = localized(Gtk.ToggleButton, 
                    active=True, can_focus=False, can_target=False,
                    valign=Gtk.Align.CENTER,
                    css_classes=[
                        "policy-choice", "policy-legend-icon", item["css"],
                    ],
                    child=Gtk.Image(icon_name=item["icon"], pixel_size=19),
                )
            else:
                icon = localized(Gtk.Button, 
                    can_focus=False, can_target=False, valign=Gtk.Align.CENTER,
                    css_classes=[
                        "match-rule-button", "policy-choice",
                        "policy-legend-icon", item["css"],
                    ],
                    child=self._match_rule_image(item),
                )
            rows.attach(icon, 0, row, 1, 1)
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3,
                           hexpand=True, valign=Gtk.Align.CENTER)
            text.append(localized(Gtk.Label,
                label=item["label"], xalign=0, wrap=True, max_width_chars=22,
                css_classes=["policy-legend-item-title"],
            ))
            text.append(localized(Gtk.Label,
                label=descriptions[item["id"]], xalign=0, wrap=True,
                max_width_chars=22, hexpand=True,
                css_classes=["policy-legend-description"],
            ))
            rows.attach(text, 1, row, 1, 1)
        section.append(rows)
        return section

    @staticmethod
    def _legend_toggled(button, popover):
        expanded = button.get_active()
        set_text(button, 'tooltip-text', m.HIDE_LEGEND if expanded else m.SHOW_LEGEND)
        if expanded:
            popover.popup()
        else:
            popover.popdown()

    def _show_about(self, *_args):
        AboutDialog(self).present()

    def _load_whats_new(self):
        if self._whats_new_loading or self._whats_new_loaded_once or self._closed:
            return
        self._whats_new_loading = True
        self._run(self._client.get_own_whats_new, self._whats_new_loaded,
                  self._whats_new_failed)

    def _whats_new_failed(self, error):
        self._whats_new_loading = False
        if self._closed or self._fatal_discovery_error:
            return
        # Optional release information must not replace language setup or
        # disable policy controls. The same private event records API failures.
        LOG.warning('parent.004', error_type=error_code(error))
        self._toast(GENERIC_DETAIL)

    def _whats_new_loaded(self, value):
        self._whats_new_loading = False
        if self._closed or self._fatal_discovery_error:
            return
        records = value['records']
        # The broker owns current-version and audience selection. Refuse a
        # mismatching reply rather than rendering old or child-only notes.
        self._whats_new_record = next((record for record in records
            if record['ProductVersion'] == value['product_version']
            and record['record_id'] == value['product_version'] + ':Parent'), None)
        self._whats_new_loaded_once = True
        self._whats_new_menu_item.set_visible(self._whats_new_record is not None)
        self._try_auto_whats_new()

    def _try_auto_whats_new(self):
        if self._whats_new_wait_id:
            GLib.source_remove(self._whats_new_wait_id)
            self._whats_new_wait_id = 0
        record = self._whats_new_record
        if (self._closed or self._fatal_discovery_error or not record
                or not record['auto_show'] or self._whats_new_auto_attempted):
            return GLib.SOURCE_REMOVE
        if not self._language_ready or not self._users_loaded_once:
            return GLib.SOURCE_REMOVE
        if (self._language_loading or self._language_dialog is not None
                or self._whats_new_modal_blocked()):
            def retry():
                self._whats_new_wait_id = 0
                return self._try_auto_whats_new()
            self._whats_new_wait_id = GLib.timeout_add(250, retry)
            return GLib.SOURCE_REMOVE
        self._show_whats_new()
        return GLib.SOURCE_REMOVE

    def _whats_new_modal_blocked(self):
        if self.get_dialogs().get_n_items():
            return True
        # Shared About/Feedback windows may inherit ownership only through
        # their transient chain rather than joining Gtk.Application.windows.
        windows = Gtk.Window.get_toplevels()
        for index in range(windows.get_n_items()):
            window = windows.get_item(index)
            if not window.get_visible() or not window.get_modal():
                continue
            parent = window.get_transient_for()
            visited = set()
            while parent is not None and parent not in visited:
                if parent is self:
                    return True
                visited.add(parent)
                parent = parent.get_transient_for()
        return False

    def _show_whats_new(self, *_args):
        if (self._closed or self._fatal_discovery_error or not self._language_ready
                or self._language_dialog is not None or not self._whats_new_record):
            return
        if self._whats_new_dialog is None:
            record = self._whats_new_record
            self._whats_new_dialog = WhatsNewDialog(
                self, record, lambda displayed: self._whats_new_closed(record, displayed))
            self._whats_new_dialog.connect(
                'map', lambda *_args: self._language_shade.set_reveal_child(True))
            self._whats_new_dialog.connect(
                'unmap', lambda *_args: self._language_shade.set_reveal_child(False))
        self._whats_new_dialog.present()
        self._whats_new_auto_attempted = True

    def _whats_new_closed(self, record, displayed):
        self._whats_new_dialog = None
        if self._closed or self._fatal_discovery_error:
            return
        if displayed:
            self._run(lambda: self._client.acknowledge_own_whats_new(record['ProductVersion']),
                      self._whats_new_loaded, self._whats_new_failed)
        self._load_policy_warnings()

    def _load_language(self):
        if self._language_loading or self._closed or self._fatal_discovery_error:
            return GLib.SOURCE_REMOVE
        self._language_loading = True
        self._run(self._client.get_own_language, self._language_loaded, self._language_failed)
        return GLib.SOURCE_REMOVE

    def _language_loaded(self, language):
        self._language_loading = False
        if self._closed or self._fatal_discovery_error:
            return
        self._own_language = language
        if not self._apply_language(language):
            self._finish_startup()
            self._language_shade.set_reveal_child(False)
            return
        if not language or self._language_requested:
            self._open_language_dialog()
        else:
            self._finish_startup()
            self._language_shade.set_reveal_child(False)
            set_automation_id(self._language_readiness, "parent-language-ready")
            self._language_ready = True
            self._try_auto_whats_new()

    def _language_failed(self, error):
        self._language_loading = False
        if not self._closed and not self._fatal_discovery_error:
            self._finish_startup()
            self._language_shade.set_reveal_child(False)
            self._show_error(error, m.YOUR_LANGUAGE_PREFERENCE_COULD_NOT_BE_LOADED_OPEN_PREFERENCES_TO)
            # The error report owns dismissal; release notes wait behind it
            # and then inherit the existing session-default context.
            self._language_ready = True
            GLib.idle_add(self._try_auto_whats_new)

    def _show_preferences(self, *_args):
        if self._closed or self._fatal_discovery_error:
            return
        self._language_requested = True
        self._load_language()

    def _open_language_dialog(self):
        if self._language_dialog is None:
            self._language_dialog = LanguageDialog(
                self, self._own_language, self._save_language, self._language_saved,
                self._language_cancelled)
            self._language_dialog.connect(
                "map", self._language_dialog_mapped)
            self._language_dialog.connect(
                "unmap", lambda *_args: self._language_shade.set_reveal_child(False))
        self._language_dialog.present()

    def _language_cancelled(self):
        self._language_dialog = None
        self._language_requested = False
        self._finish_startup()
        set_automation_id(self._language_readiness, "parent-language-ready")
        self._language_ready = True
        # Cancel destroys the chooser after this callback returns.
        GLib.idle_add(self._try_auto_whats_new)
        self._load_policy_warnings()

    def _save_language(self, language, success, failure):
        def saved(value):
            if not self._closed and not self._fatal_discovery_error:
                success(value)

        def failed(error):
            LOG.warning("parent.004", error_type=error_code(error))
            if not self._closed and not self._fatal_discovery_error:
                failure(error)

        self._run(lambda: self._client.set_own_language(language), saved, failed)

    def _language_saved(self, language):
        self._own_language = language
        self._language_dialog = None
        self._language_requested = False
        if not self._apply_language(language):
            return
        self._finish_startup()
        set_automation_id(self._language_readiness, "parent-language-ready")
        self._language_ready = True
        GLib.idle_add(self._try_auto_whats_new)
        self._load_policy_warnings()

    def _apply_language(self, language):
        # Preferences refreshes storage on every visit. An unchanged language
        # needs no relabeling of the existing management controls or dialogs.
        if self._applied_language == language:
            return True
        try:
            context_for(self).apply(language)
        except (OSError, ValueError) as error:
            self._show_error(error)
            return False
        self._applied_language = language
        if getattr(self, "_app_catalog", None) is not None or getattr(self, "_apps_loading", False):
            # Reload the one shared catalogue after changing the parent's language.
            # Supersede any response started with the previous language.
            self._apps_loading = False
            self._ensure_apps_load(self._selected_uid())
        return True

    def _show_feedback(self, *_args):
        if not getattr(self, "_feedback_dialog", None):
            self._feedback_dialog = FeedbackDialog(self)
        self._feedback_dialog.present()

    def _show_error(self, error, detail=GENERIC_DETAIL, *, on_close=None):
        if broker_reboot_required(error):
            show_update_required(self, on_close=self.close)
            return
        self._toast(detail)
        if not getattr(self, "_errors", None):
            self._errors = ErrorHandler(self, "Parent App")
        self._errors.handle(error, GENERIC_TITLE, detail, on_close=on_close)

    def _clear_catalog_rows(self):
        for row in self._app_rows:
            self._match_column_size.remove_widget(row.match_rule_cell)
            self._access_column_size.remove_widget(row.policy_selector)
            self._apps_group.remove(row)
        self._rows = []
        self._app_rows = []

    def _add_app_row(self, app):
        automation_key = _app_automation_key(app["id"])
        row = localized(Adw.ActionRow, 
            title=app["name"], subtitle=app["description"] or app["id"],
            css_classes=["app-policy-row"],
        )
        set_automation_id(row, f"parent-app-{automation_key}")
        row.app = app
        bind_ui(row, get_value=lambda: row.app["id"])
        row.search_text = f'{app["name"]} {app["description"]} {app["id"]}'.casefold()
        icon_cell = Gtk.Box(
            width_request=80, halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER, css_classes=["app-icon-cell"],
        )
        icon_cell.append(self._application_icon(app, f"parent-app-{automation_key}-icon"))
        row.add_prefix(icon_cell)
        row.policy_buttons = {}
        row.match_rule_button = localized(Gtk.Button, 
            tooltip_text=m.EDIT_MATCH_RULE, valign=Gtk.Align.CENTER,
            css_classes=["match-rule-button"],
        )
        describe_control(
            row.match_rule_button, m.APP_NAME_S_MATCH_RULE % {'app_name': app['name']},
            m.CHOOSE_WHETHER_THIS_APPLICATION_S_SAVED_RULE_MATCHES_AN_EXACT_PA,
            automation_id=f"parent-app-{automation_key}-match-rule",
        )
        row.match_rule_button.connect("clicked", self._edit_match_rule, row)
        bind_ui(row.match_rule_button,
                get_value=lambda: row.match_rule or self._default_match_rule(row))
        match_rule_cell = Gtk.Box(
            width_request=92, halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER, css_classes=["match-rule-cell"],
        )
        match_rule_cell.append(row.match_rule_button)
        row.match_rule_cell = match_rule_cell
        self._match_column_size.add_widget(match_rule_cell)
        row.add_suffix(match_rule_cell)
        selector = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=3,
            valign=Gtk.Align.CENTER, css_classes=["policy-selector"],
        )
        first_button = None
        for state in APP_LIST_STATES:
            button = localized(Gtk.ToggleButton, 
                tooltip_text=state["label"],
                css_classes=["policy-choice", state["css"]],
                child=Gtk.Image(icon_name=state["icon"], pixel_size=19),
                valign=Gtk.Align.CENTER,
            )
            describe_control(
                button, m.APP_NAME_S_ACCESS_RULE_STATE_LABEL_S % {'app_name': app['name'], 'state_label': state['label']},
                m.SET_THE_SELECTED_CHILD_S_ACCESS_RULE_FOR_APP_NAME_S_TO_STATE_LAB % {'app_name': app['name'], 'state_label': state['label']},
                automation_id=f"parent-app-{automation_key}-access-{state['id']}",
            )
            if first_button is None:
                first_button = button
            else:
                button.set_group(first_button)
            button.connect("toggled", self._policy_changed)
            row.policy_buttons[state["id"]] = button
            selector.append(button)
        row.policy_selector = selector
        set_automation_id(selector, f"parent-app-{automation_key}-access")
        def set_access(value):
            if not isinstance(value, str) or value not in row.policy_buttons:
                raise ValueError("unknown app access rule")
            button = row.policy_buttons[value]
            if not button.is_sensitive():
                raise ValueError("app access rule is unavailable")
            button.set_active(True)
        bind_ui(selector, get_value=lambda: next((identity for identity, button
                                                in row.policy_buttons.items()
                                                if button.get_active()), ""),
                set_value=set_access, choices=lambda: list(row.policy_buttons))
        self._access_column_size.add_widget(selector)
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
        if self._users_loading or self._fatal_discovery_error:
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
                self._show_error(error, m.CHILD_ACCOUNTS_COULD_NOT_BE_REFRESHED_RETRYING_AUTOMATICALLY)
            return
        LOG.warning("parent.006", error_type=error_code(error))
        self._fatal_discovery_error = True
        if self._whats_new_dialog is not None:
            self._whats_new_dialog.destroy()
            self._whats_new_dialog = None
        # Account discovery is fatal here. Replace setup rather than leaving
        # two competing modals, and ignore outstanding language replies.
        if self._language_dialog is not None:
            self._language_dialog.destroy()
            self._language_dialog = None
        self._language_requested = False
        self._language_shade.set_reveal_child(False)
        self.get_content().set_sensitive(False)
        self._show_error(error, m.THE_PARENT_APP_COULD_NOT_LOAD_PLEASE_TRY_AGAIN_LATER,
                         on_close=self.get_application().quit)

    def _users_loaded(self, users):
        loaded = [parse_listed_user(user) for user in users]
        self._users_loading = False
        self._user_discovery_error_reported = False
        if self._users_loaded_once and loaded == self._users:
            return
        previous_uid = self._selected_uid()
        self._users_loaded_once = True
        GLib.idle_add(self._try_auto_whats_new)
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
                self._toast(m.NO_INTERACTIVE_NON_ADMIN_USERS_WERE_FOUND)

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
        set_text(self._revoke_description, 'label', m.REVOKES_ONE_TIME_SCREEN_TIME_AND_APP_ACCESS_GRANTS_GRANTED_TO_CH % {'child_name': child_name}
        )
        self._loading = True
        # Do not carry a previous child's grant state into this selection while
        # its authoritative time status is still loading.
        self._remaining_time_seconds = None
        self._has_running_soft_blocked_apps = False
        set_text(self._time_status_value, 'label', m.LOADING)
        set_text(self._time_explanation, 'label', "—")
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
        self._show_error(error, m.INSTALLED_APPS_COULD_NOT_BE_LOADED_PLEASE_TRY_AGAIN_LATER)
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
        self._has_running_soft_blocked_apps = status.get("has_running_soft_blocked_apps", False)
        set_text(self._time_status_value, 'label', format_duration(status["calculated_active_extension_seconds"])
        )
        set_text(self._time_explanation, 'label', _time_status_subtitle(status))
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
        set_text(self._time_status_value, 'label', m.UNAVAILABLE)
        set_text(self._time_explanation, 'label', "—")
        self._show_error(error, m.REMAINING_TIME_COULD_NOT_BE_LOADED_PLEASE_TRY_AGAIN_LATER)

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
        report_ready = (self._language_dialog is None
                        and getattr(self, '_whats_new_dialog', None) is None)
        # Management loads behind the startup chooser. Keep the warning visible,
        # but do not open a competing modal or mark it reported until setup has
        # finished. Save and Cancel refresh the current warning set afterward.
        if report_ready or not affected:
            self._reported_policy_warnings[uid] = affected
        self._policy_warning.set_visible(bool(affected))
        if not affected:
            return
        names = {app["id"]: app["name"] for app in self._app_catalog or ()}
        apps = ", ".join(names.get(app_id, app_id or m.ANOTHER_APPLICATION) for app_id in affected)
        detail = (
            m.SOME_APP_LIMITS_COULD_NOT_BE_APPLIED_AFFECTED_APPS_OR_UPDATED_VE
        )
        # App identities are displayed locally, never included in automatic
        # diagnostic events or the error-report draft.
        set_text(self._policy_warning, 'label', m.DETAIL_S_AFFECTED_APPS_APPS_S % {'detail': detail, 'apps': apps})
        if affected != previous and report_ready:
            self._show_error(RuntimeError("application rules unavailable"), detail)

    def _policy_warnings_failed(self, uid, error):
        self._policy_warnings_loading = False
        if self._policy_warnings_closed:
            return
        if uid != self._selected_uid():
            self._load_policy_warnings()
            return
        set_text(self._policy_warning, 'label', m.APP_LIMIT_STATUS_IS_UNAVAILABLE_RETRYING_AUTOMATICALLY)
        self._policy_warning.set_visible(True)
        if (not self._policy_warning_query_failed and self._language_dialog is None
                and getattr(self, '_whats_new_dialog', None) is None):
            self._policy_warning_query_failed = True
            self._show_error(error, m.APP_LIMIT_STATUS_COULD_NOT_BE_CHECKED_OTHER_CONTROLS_REMAIN_AVAI)

    def _refresh_users(self):
        self._load_users()
        return GLib.SOURCE_CONTINUE

    def _close_requested(self, *_args):
        self._closed = True
        legend = getattr(self, "_legend_popover", None)
        if legend is not None and legend.get_parent() is not None:
            legend.popdown()
            legend.unparent()
        if self._whats_new_wait_id:
            GLib.source_remove(self._whats_new_wait_id)
            self._whats_new_wait_id = 0
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
            getattr(self, "_app_catalog", []) is not None and
            getattr(self, "_remaining_time_seconds", None) is not None and
            (self._remaining_time_seconds > 0 or
             getattr(self, "_has_running_soft_blocked_apps", False))
        )
        self._enabled.set_sensitive(idle and self._selected_uid() is not None)
        active_save = getattr(self, "_active_save", None)
        custom_save = (active_save is not None and
                       active_save[:2] == ("custom-allowance", self._selected_uid()))
        # Focus leave can commit the custom draft during a menu-button click.
        # Keep the picker enabled so that click can finish opening its popover;
        # a subsequent preset selection uses the same serialized save queue.
        self._daily_limit.set_sensitive(
            not self._loading and (idle or custom_save) and
            self._selected_uid() is not None and
            self._enabled.get_active()
        )
        if hasattr(self, "_custom_daily_limit"):
            self._custom_daily_limit.set_sensitive(
                not self._loading and (idle or custom_save) and
                self._selected_uid() is not None and
                self._enabled.get_active()
            )
        table_ready = getattr(self, "_apps_table_ready", True)
        self._apps_group.set_sensitive(sensitive and table_ready)
        search = getattr(self, "_search", None)
        if search is not None:
            search.set_sensitive(sensitive and table_ready)

    def _confirm_revoke(self, *_args):
        uid = self._selected_uid()
        if uid is None or self._loading or self._save_in_progress or self._app_catalog is None:
            return
        self._loading = True
        self._set_apps_sensitive(False)
        self._run(
            lambda: self._client.list_running_soft_blocked_apps(uid),
            lambda applications: self._show_revoke_dialog(uid, applications),
        )

    def _application_icon(self, app, automation_id):
        try:
            icon = Gio.Icon.new_for_string(app["icon"] or "application-x-executable")
        except GLib.Error:
            icon = Gio.ThemedIcon.new("application-x-executable")
        image = Gtk.Image(gicon=icon, pixel_size=36)
        set_automation_id(image, automation_id)
        bind_ui(image, get_value=lambda: app["icon"])
        return image

    def _show_revoke_dialog(self, uid, applications):
        if self._closed:
            return
        self._loading = False
        self._set_apps_sensitive(True)
        if uid != self._selected_uid():
            return
        selected = self._account.get_selected()
        if selected >= len(self._users):
            return
        child_name = self._users[selected][1]
        dialog = localized(Gtk.Dialog, 
            transient_for=self, modal=True, title=m.REVOKE_ONE_TIME_GRANT,
        )
        set_automation_id(dialog, "parent-revoke-dialog")
        header = Gtk.HeaderBar()
        add_identified_window_controls(header, "parent-revoke-window-controls")
        dialog.set_titlebar(header)
        warning = localized(Gtk.Label, 
            label=(m.THIS_WILL_REVOKE_ONE_TIME_SCREEN_TIME_AND_ACCESS_TO_SOFT_BLOCKED % {'child_name': child_name}),
            wrap=True, max_width_chars=72, xalign=0,
            margin_top=18, margin_bottom=18,
            margin_start=18, margin_end=18,
        )
        warning.set_natural_wrap_mode(Gtk.NaturalWrapMode.WORD)
        set_automation_id(warning, "parent-revoke-warning")
        dialog.get_content_area().append(warning)
        replacements = replacement_policy_ids(self._preferences["apps"], self._app_catalog)
        running = set(applications)
        apps = [app for app in self._app_catalog
                if replacements.get(app["id"], app["id"]) in running]
        if apps:
            heading = localized(
                Gtk.Label, label=m.THESE_RUNNING_SOFT_BLOCKED_APPS_WILL_BE_CLOSED,
                wrap=True, max_width_chars=72, xalign=0,
                margin_start=18, margin_end=18, margin_bottom=8,
            )
            set_automation_id(heading, "parent-revoke-apps-heading")
            dialog.get_content_area().append(heading)
            app_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                               margin_start=18, margin_end=18, margin_bottom=18)
            set_automation_id(app_list, "parent-revoke-apps")
            bind_ui(app_list, get_value=lambda: [app["id"] for app in apps])
            for app in apps:
                identity = f"parent-revoke-app-{_app_automation_key(app['id'])}"
                row = Gtk.Box(spacing=8)
                bullet = Gtk.Label(label="•")
                set_automation_id(bullet, identity + "-bullet")
                row.append(bullet)
                row.append(self._application_icon(app, identity + "-icon"))
                name = Gtk.Label(label=app["name"], xalign=0, wrap=True,
                                 max_width_chars=60, hexpand=True)
                set_automation_id(name, identity)
                row.append(name)
                app_list.append(row)
            scroll = Gtk.ScrolledWindow(
                hscrollbar_policy=Gtk.PolicyType.NEVER,
                propagate_natural_height=True, max_content_height=240,
            )
            scroll.set_child(app_list)
            dialog.get_content_area().append(scroll)
        add_dialog_button(
            dialog, m.CANCEL, Gtk.ResponseType.CANCEL, "parent-revoke-cancel",
            description=m.KEEP_THE_CURRENT_ONE_TIME_GRANT,
        )
        add_dialog_button(
            dialog, m.REVOKE_GRANT, Gtk.ResponseType.OK, "parent-revoke-confirm",
            description=m.REVOKE_THE_SELECTED_CHILD_S_ONE_TIME_GRANT,
            css_class="destructive-action",
        )
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        dialog.connect("response", self._revoke_response, uid)
        dialog.present()

    def _revoke_response(self, dialog, response, uid):
        dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return
        if uid != self._selected_uid():
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
        self._toast(m.ONE_TIME_GRANT_REVOKED)
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
                m.SET_THE_SELECTED_CHILD_S_DAILY_ALLOWANCE_TO_DAILY_LIMIT_LABEL_MI % {'daily_limit_label_minutes': _daily_limit_label(minutes)},
                automation_id=f"parent-daily-limit-{minutes}",
            )
            choices.append(choice)
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, width_request=300)
        self._daily_limit_viewport = Gtk.Viewport(child=choices)
        choices_scroll = Gtk.ScrolledWindow(
            child=self._daily_limit_viewport,
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
            m.CUSTOM_AMOUNT, CUSTOM_DAILY_LIMIT_INDEX,
            icon_name="emblem-system-symbolic",
        )
        describe_control(
            custom, m.CUSTOM_AMOUNT_2,
            m.ENTER_A_CUSTOM_DAILY_ALLOWANCE_IN_MINUTES,
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
        content.append(localized(Gtk.Label, 
            label=label,
            xalign=0,
            hexpand=True,
            css_classes=["daily-limit-choice-label"],
        ))
        choice = localized(Gtk.Button, 
            child=content,
            hexpand=True,
            css_classes=["daily-limit-choice"],
        )
        choice.connect("clicked", self._daily_limit_changed, index)
        self._daily_limit_choices.append((choice, marker, index))
        return choice

    def _update_daily_limit_choice_styles(self):
        displayed = self._daily_limit_keyboard_index
        if displayed is None:
            displayed = self._daily_limit_selected
        for choice, marker, index in self._daily_limit_choices:
            selected = index == displayed
            label = (m.CUSTOM_AMOUNT_2 if index == CUSTOM_DAILY_LIMIT_INDEX
                     else _daily_limit_label(DAILY_LIMIT_PRESETS[index]))
            accessible_text(choice, 
                [Gtk.AccessibleProperty.DESCRIPTION],
                [(m.SELECTED_DAILY_ALLOWANCE_DESCRIPTION if selected else m.DAILY_ALLOWANCE_DESCRIPTION)
                 % {'duration': label}],
            )
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
        self._clear_daily_limit_keyboard()
        is_custom = selected == CUSTOM_DAILY_LIMIT_INDEX
        set_text(self._daily_limit, 'label', m.CUSTOM_VALUE if is_custom else _daily_limit_label(
            DAILY_LIMIT_PRESETS[selected],
        ))
        self._update_daily_limit_choice_styles()
        self._custom_daily_limit.set_visible(is_custom)
        self._daily_limit.popdown()
        if is_custom:
            self._custom_daily_limit_entry.grab_focus()
            return
        self._save_parent_control(self._enabled.get_active())

    def _ui_daily_limit_value(self):
        if self._daily_limit_selected == CUSTOM_DAILY_LIMIT_INDEX:
            return "custom"
        return f"{DAILY_LIMIT_PRESETS[self._daily_limit_selected]}m"

    def _ui_select_daily_limit(self, value):
        if not isinstance(value, str) or not 1 <= len(value) <= 16:
            raise ValueError("unknown daily allowance choice")
        index = (CUSTOM_DAILY_LIMIT_INDEX if value == "custom"
                 else _daily_limit_keyboard_selection(value))
        if index is None:
            raise ValueError("unknown daily allowance choice")
        for choice, _marker, choice_index in self._daily_limit_choices:
            if choice_index == index:
                choice.emit("clicked")
                return

    def _ui_set_custom_daily_limit_text(self, text):
        if not isinstance(text, str) or "\x00" in text:
            raise ValueError("custom daily allowance requires text")
        minutes = parse_duration_minutes(text)
        self._custom_daily_limit_entry.set_text(str(minutes) if minutes is not None else text)

    def _clear_daily_limit_keyboard(self, *_args):
        self._daily_limit_keyboard_text = ""
        self._daily_limit_keyboard_index = None
        self._update_daily_limit_choice_styles()
        selected = self._daily_limit_selected
        set_text(self._daily_limit, 'label', m.CUSTOM_VALUE if selected == CUSTOM_DAILY_LIMIT_INDEX
                 else _daily_limit_label(DAILY_LIMIT_PRESETS[selected]))
        accessible_text(self._daily_limit, [Gtk.AccessibleProperty.DESCRIPTION],
                        [m.CHOOSE_THE_SELECTED_CHILD_S_DAILY_SCREEN_TIME_ALLOWANCE])

    def _daily_limit_key_pressed(self, _controller, keyval, _keycode, state):
        """Buffer only within the selector; custom-entry input has its own owner."""
        if (self._loading or self._selected_uid() is None or
                not self._daily_limit.is_sensitive() or
                not self._enabled.get_active() or
                state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK |
                         Gdk.ModifierType.SUPER_MASK)):
            return False
        if keyval in (Gdk.KEY_c, Gdk.KEY_C):
            self._daily_limit_keyboard_text = ""
            self._daily_limit_keyboard_index = CUSTOM_DAILY_LIMIT_INDEX
            self._show_daily_limit_keyboard_choice()
            return True
        if keyval == Gdk.KEY_Escape:
            self._clear_daily_limit_keyboard()
            self._daily_limit.popdown()
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if self._daily_limit_keyboard_index is not None:
                self._daily_limit_changed(None, self._daily_limit_keyboard_index)
                return True
            if self._daily_limit_keyboard_text:
                return True
            # A focused popup choice keeps its normal Enter activation.
            if not self._daily_limit.get_popover().get_visible():
                self._daily_limit.popup()
                return True
            return False
        if keyval == Gdk.KEY_space and not self._daily_limit.get_popover().get_visible():
            self._daily_limit.popup()
            return True
        if keyval in (Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_KP_Up, Gdk.KEY_KP_Down):
            index = self._daily_limit_keyboard_index
            if index is None:
                index = self._daily_limit_selected
            step = -1 if keyval in (Gdk.KEY_Up, Gdk.KEY_KP_Up) else 1
            self._daily_limit_keyboard_index = max(0, min(CUSTOM_DAILY_LIMIT_INDEX, index + step))
            self._daily_limit_keyboard_text = ""
            self._show_daily_limit_keyboard_choice()
            return True
        character = chr(Gdk.keyval_to_unicode(keyval)).lower()
        if keyval == Gdk.KEY_BackSpace:
            text = self._daily_limit_keyboard_text[:-1]
        elif character in "0123456789.mh":
            text = (self._daily_limit_keyboard_text + character)[:16]
        else:
            return False
        self._daily_limit_keyboard_text = text
        self._daily_limit_keyboard_index = _daily_limit_keyboard_selection(text)
        if self._daily_limit_keyboard_index is not None:
            self._daily_limit_keyboard_text = ""
        self._show_daily_limit_keyboard_choice()
        return True

    def _show_daily_limit_keyboard_choice(self):
        """Display an offered option without changing the committed allowance."""
        self._update_daily_limit_choice_styles()
        index = self._daily_limit_keyboard_index
        if index is None:
            index = self._daily_limit_selected
        label = (m.CUSTOM_VALUE if index == CUSTOM_DAILY_LIMIT_INDEX
                 else _daily_limit_label(DAILY_LIMIT_PRESETS[index]))
        set_text(self._daily_limit, 'label', label)
        accessible_text(self._daily_limit, [Gtk.AccessibleProperty.DESCRIPTION],
                        [m.CHOOSE_THE_SELECTED_CHILD_S_DAILY_SCREEN_TIME_ALLOWANCE
                         if self._daily_limit_keyboard_index is None else
                         m.DAILY_ALLOWANCE_DESCRIPTION % {'duration': label}])
        self._scroll_daily_limit_keyboard_choice()

    def _scroll_daily_limit_keyboard_choice(self):
        index = self._daily_limit_keyboard_index
        # Custom is the fixed footer, outside the scrolling preset list.
        if (index is None or index == CUSTOM_DAILY_LIMIT_INDEX or
                not self._daily_limit_viewport.get_mapped()):
            return
        for choice, _marker, choice_index in self._daily_limit_choices:
            if choice_index == index:
                self._daily_limit_viewport.scroll_to(choice, None)
                return

    def _custom_daily_limit_changed(self, *_args):
        self._cancel_custom_daily_limit_save()
        if (self._loading or self._selected_uid() is None or
                self._daily_limit_selected != CUSTOM_DAILY_LIMIT_INDEX or
                not self._enabled.get_active()):
            return False
        text = self._custom_daily_limit_entry.get_text().strip()
        if not text.isdecimal() or not 0 <= int(text) <= MAX_CUSTOM_DAILY_LIMIT_MINUTES:
            self._custom_daily_limit_entry.add_css_class("error")
            accessible_text(self._custom_daily_limit_entry, 
                [Gtk.AccessibleProperty.DESCRIPTION],
                [m.INVALID_DAILY_ALLOWANCE_ENTER_A_WHOLE_NUMBER_FROM_0_TO_1439],
            )
            set_text(self._custom_daily_limit, 'subtitle', m.ENTER_A_WHOLE_NUMBER_FROM_0_TO_1439
            )
            return False
        self._custom_daily_limit_entry.remove_css_class("error")
        accessible_text(self._custom_daily_limit_entry, 
            [Gtk.AccessibleProperty.DESCRIPTION],
            [m.ENTER_A_WHOLE_NUMBER_OF_MINUTES_FROM_ZERO_THROUGH_1439],
        )
        set_text(self._custom_daily_limit, 'subtitle', m.ENTER_A_WHOLE_NUMBER_FROM_0_TO_1439)
        self._save_parent_control(self._enabled.get_active(), custom=True)
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
        """Restore the selected child's saved allowance, including its editor."""
        selected, is_custom = _daily_limit_selection(minutes)
        self._daily_limit_selected = selected
        self._clear_daily_limit_keyboard()
        set_text(self._daily_limit, 'label', m.CUSTOM_VALUE if is_custom else _daily_limit_label(minutes))
        self._update_daily_limit_choice_styles()
        self._custom_daily_limit.set_visible(is_custom)
        # Preference loads replace abandoned drafts even when the saved value
        # selects a preset. Successful autosaves do not use this load path, so
        # ongoing typing keeps its text, focus and caret.
        set_text(self._custom_daily_limit_entry, 'text', str(minutes))
        self._custom_daily_limit_entry.remove_css_class("error")
        accessible_text(self._custom_daily_limit_entry, 
            [Gtk.AccessibleProperty.DESCRIPTION],
            [m.ENTER_A_WHOLE_NUMBER_OF_MINUTES_FROM_ZERO_THROUGH_1439],
        )

    def _daily_limit_minutes(self):
        if self._daily_limit_selected != CUSTOM_DAILY_LIMIT_INDEX:
            return DAILY_LIMIT_PRESETS[self._daily_limit_selected]
        text = self._custom_daily_limit_entry.get_text().strip()
        if text.isdecimal() and 0 <= int(text) <= MAX_CUSTOM_DAILY_LIMIT_MINUTES:
            return int(text)
        # Invalid custom input is never saved; retain the last valid value.
        return self._preferences.get("daily_time_limit_minutes", 30)

    def _save_parent_control(self, enabled, *, custom=False):
        uid = self._selected_uid()
        daily_limit_minutes = self._daily_limit_minutes()
        kind = "custom-allowance" if custom else "parent-control"
        if custom:
            # Enter, focus leave and debounce can all commit the same draft.
            # Compare against the last outstanding write, not an older saved
            # value: typing back to that older value must still be queued.
            outstanding = (self._pending_saves[-1] if self._pending_saves
                           else self._active_save)
            if outstanding is not None:
                if outstanding == (kind, uid, (enabled, daily_limit_minutes)):
                    return
            elif (self._preferences is not None and
                  self._preferences["parent_control_enabled"] == enabled and
                  self._preferences["daily_time_limit_minutes"] == daily_limit_minutes):
                return
        self._queue_save(kind, uid, enabled, daily_limit_minutes)

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
        value = self._match_rule_image(match)
        set_automation_id(
            value, f"parent-app-{_app_automation_key(row.app['id'])}-match-{match['id']}",
        )
        row.match_rule_button.set_child(value)
        set_text(row.match_rule_button, 'tooltip-text', match["label"])
        describe_control(row.match_rule_button, m.ROW_APP_NAME_S_MATCH_RULE % {'row_app_name': row.app['name']},
                         m.CURRENT_MATCH_RULE_RULE_S % {'rule': rule})

    @staticmethod
    def _match_rule_image(match):
        return localized(Gtk.Label, 
            label=match["glyph"],
            css_classes=["match-rule-icon", match["css"]],
        )

    def _edit_match_rule(self, _button, row):
        dialog = localized(Gtk.Dialog, transient_for=self, modal=True, title=m.EDIT_MATCH_RULE_2)
        set_automation_id(dialog, "parent-match-rule-dialog")
        header = Gtk.HeaderBar()
        add_identified_window_controls(header, "parent-match-rule-window-controls")
        dialog.set_titlebar(header)
        add_dialog_button(
            dialog, m.CANCEL, Gtk.ResponseType.CANCEL, "parent-match-rule-cancel",
        )
        add_dialog_button(
            dialog, m.RESET_TO_DEFAULT, Gtk.ResponseType.APPLY,
            "parent-match-rule-reset",
        )
        add_dialog_button(
            dialog, m.SAVE, Gtk.ResponseType.OK, "parent-match-rule-save",
        )
        dialog.set_default_response(Gtk.ResponseType.OK)
        content = dialog.get_content_area()
        set_automation_id(content, f"parent-match-rule-app-{_app_automation_key(row.app['id'])}")
        content.set_spacing(12)
        content.set_margin_top(18)
        content.set_margin_bottom(18)
        content.set_margin_start(18)
        content.set_margin_end(18)
        content.append(localized(Gtk.Label, 
            label=m.USE_AN_EXACT_EXECUTION_PATH_OR_INCLUDE_FOR_A_VERSIONED_FILENAME,
            wrap=True, xalign=0,
        ))
        entry = localized(Gtk.Entry, hexpand=True, width_chars=54,
                          text=row.match_rule or self._default_match_rule(row))
        describe_control(
            entry, m.APPLICATION_MATCH_RULE,
            m.ENTER_AN_EXACT_EXECUTION_PATH_OR_A_VERSIONED_FILENAME_PATTERN,
            automation_id="parent-match-rule-entry",
        )
        content.append(entry)
        entry.connect("changed", lambda widget: describe_control(
            widget, m.APPLICATION_MATCH_RULE,
            m.ENTER_AN_EXACT_EXECUTION_PATH_OR_A_VERSIONED_FILENAME_PATTERN,
        ))

        def response(_dialog, response_id):
            if response_id == Gtk.ResponseType.OK:
                rule = self._canonical_match_rule(row, entry.get_text())
                if not rule:
                    describe_control(entry, m.APPLICATION_MATCH_RULE, m.A_MATCH_RULE_IS_REQUIRED)
                    self._toast(m.A_MATCH_RULE_IS_REQUIRED)
                    return
                if not self._is_pattern(rule) and rule not in row.app["targets"]:
                    describe_control(entry, m.APPLICATION_MATCH_RULE,
                                     m.A_PRECISE_MATCH_MUST_BE_THIS_APP_S_EXECUTION_PATH)
                    self._toast(m.A_PRECISE_MATCH_MUST_BE_THIS_APP_S_EXECUTION_PATH)
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
        self._active_save = save
        # Freeze conflicting controls while writing the shared record. Custom
        # typing keeps its editor and caret; later commits use this same queue.
        self._set_apps_sensitive(False)
        if kind == "app-policy":
            self._start_app_policy_save(uid, *arguments)
        else:
            self._start_parent_control_save(uid, *arguments)

    def _save_succeeded(self, uid, preferences, *, refresh_time_status=False):
        self._save_in_progress = False
        self._active_save = None
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
        self._active_save = None
        LOG.warning("parent.018", setting=setting, error_type=error_code(error))
        message = {
            'one-time grant': m.SAVE_GRANT_FAILED,
            'screen-time settings': m.SAVE_SCREEN_TIME_FAILED,
            'app access': m.SAVE_APP_ACCESS_FAILED,
        }.get(setting, m.SOMETHING_WENT_WRONG)
        self._show_error(error, message)
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
        self._toasts.add_toast(localized(Adw.Toast, title=title, translation_owner=self))

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
    def __init__(self, *, preview=False, client_factory=None, startup_error=None,
                 check_startup=False):
        super().__init__(application_id="com.puffyslippers.OhNoParentControl.Parent")
        self._startup_error = startup_error
        self._startup_checked = not check_startup or startup_error is not None
        self._startup_window = None
        self._startup_cancelled = False
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
        self._accessibility_registration_id = 0
        self._application_ui = ApplicationUI(self)

    def do_dbus_register(self, connection, object_path):
        if not Adw.Application.do_dbus_register(self, connection, object_path):
            return False
        info = Gio.DBusNodeInfo.new_for_xml(ACCESSIBILITY_XML)
        self._accessibility_registration_id = connection.register_object(
            object_path, info.interfaces[0], self._accessibility_method_call,
            None, None,
        )
        self._application_ui.register(connection, object_path)
        return True

    def do_dbus_unregister(self, connection, object_path):
        try:
            self._application_ui.unregister(connection)
            if self._accessibility_registration_id:
                connection.unregister_object(self._accessibility_registration_id)
                self._accessibility_registration_id = 0
        finally:
            Adw.Application.do_dbus_unregister(self, connection, object_path)

    def _native_surface_transform(self, surface_id):
        # Resolve only our public native Parent surface. No selected account,
        # policy state, control coordinates or input actions cross this API.
        if surface_id != "parent-window":
            raise ValueError("Unsupported native surface")
        windows = [window for window in self.get_windows()
                   if Gtk.Buildable.get_buildable_id(window) == surface_id]
        if len(windows) != 1:
            raise ValueError("Native surface is missing or ambiguous")
        window = windows[0]
        # Popup dismissal queues window-system requests. Finish those requests
        # before another connection binds Mutter's focused window; GTK's active
        # toplevel state alone also holds while a popup owns native focus.
        window.get_display().sync()
        current = [candidate for candidate in self.get_windows()
                   if Gtk.Buildable.get_buildable_id(candidate) == surface_id]
        if len(current) != 1 or current[0] is not window:
            raise ValueError("Native surface changed during synchronization")
        if (not window.get_mapped() or not window.get_visible()
                or not window.is_active() or Gtk.Native.get_surface(window) is None):
            raise ValueError("Native surface is unavailable")
        # Read anew for every request; decorations can change with window state.
        x, y = Gtk.Native.get_surface_transform(window)
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Native surface transform is unavailable")
        return x, y

    def _accessibility_method_call(self, _connection, _sender, _object_path,
                                   _interface_name, method_name, parameters, invocation):
        if method_name != "GetNativeSurfaceTransform":
            invocation.return_dbus_error(
                "org.freedesktop.DBus.Error.UnknownMethod", "Unknown method",
            )
            return
        try:
            surface_id, = parameters.unpack()
            transform = self._native_surface_transform(surface_id)
        except (ValueError, TypeError, GLib.Error):
            invocation.return_dbus_error(
                ACCESSIBILITY_INTERFACE + ".SurfaceUnavailable",
                "Native surface transform is unavailable",
            )
            return
        invocation.return_value(GLib.Variant("(dd)", transform))

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
        if not self._startup_checked:
            self._check_startup()
            return
        if self._startup_error is not None:
            if broker_reboot_required(self._startup_error):
                self._show_reboot_required()
                return
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

    def _startup_notice(self, identity, title, detail=None, *, loading=False):
        window = localized(Adw.ApplicationWindow, application=self, title=app_name(),
                           default_width=560, default_height=300)
        set_automation_id(window, identity)
        self._ensure_stylesheet(window)
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        add_identified_window_controls(header, identity + '-window-controls')
        toolbar.add_top_bar(header)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20,
                         margin_top=24, margin_bottom=24, margin_start=24, margin_end=24)
        if loading:
            content.append(Adw.Spinner(height_request=32, halign=Gtk.Align.CENTER))
        heading = localized(Gtk.Label, label=title, wrap=True, css_classes=['title-2'])
        set_automation_id(heading, identity + '-heading')
        content.append(heading)
        if detail is not None:
            explanation = localized(Gtk.Label, label=detail, wrap=True, vexpand=True)
            set_automation_id(explanation, identity + '-message')
            content.append(explanation)
        actions = Gtk.Box(spacing=12, halign=Gtk.Align.END, valign=Gtk.Align.END, vexpand=True)
        close = localized(Gtk.Button, label=m.CLOSE)
        set_automation_id(close, identity + '-close')
        close.connect('clicked', lambda *_: window.close())
        actions.append(close)
        content.append(actions)
        toolbar.set_content(content)
        window.set_content(toolbar)
        window.set_default_widget(close)
        return window, actions

    def _check_startup(self):
        if self._startup_window is not None:
            self._startup_window.present()
            return
        window, _actions = self._startup_notice('parent-startup-window', m.LOADING, loading=True)
        self._startup_window = window
        window.connect('close-request', self._startup_closed)
        window.present()

        def check():
            errors = []
            _can_start(self._client_factory, errors.append)
            GLib.idle_add(self._startup_finished, errors[0] if errors else None)

        try:
            threading.Thread(target=check, daemon=True, name='parent-startup').start()
        except Exception as error:
            self._startup_finished(error)

    def _startup_closed(self, *_args):
        self._startup_cancelled = True
        return False

    def _startup_finished(self, error):
        if self._startup_cancelled:
            return GLib.SOURCE_REMOVE
        self._startup_checked = True
        self._startup_error = error
        # Keep the application alive while replacing its only window. Closing
        # the loading window manually never permits a late reply to reopen it.
        self.hold()
        try:
            self._startup_window.destroy()
            self._startup_window = None
            self.do_activate()
        finally:
            self.release()
        return GLib.SOURCE_REMOVE

    def _show_reboot_required(self):
        show_update_required(application=self, on_close=self.quit)

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
            window = localized(Adw.ApplicationWindow, application=self,
                title=m.ADMINISTRATOR_ACCESS_REQUIRED, default_width=820,
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
            brand = localized(Gtk.Label, label=app_name(), xalign=0, wrap=True,
                margin_bottom=6, css_classes=["management-denied-brand"])
            set_automation_id(brand, "parent-access-denied-brand")
            text.append(brand)
            heading = localized(Gtk.Label, label=m.ADMINISTRATOR_REQUIRED, xalign=0,
                wrap=True, css_classes=["management-denied-title"])
            set_automation_id(heading, "parent-access-denied-heading")
            text.append(heading)
            explanation = localized(Gtk.Label, 
                label=m.ONLY_AN_ADMINISTRATOR_CAN_MANAGE_PARENTAL_CONTROLS_SIGN_IN_WITH,
                xalign=0, wrap=True, css_classes=["management-denied-message"])
            set_automation_id(explanation, "parent-access-denied-message")
            accessible_text(explanation, [Gtk.AccessibleProperty.LABEL], [
                m.ONLY_AN_ADMINISTRATOR_CAN_MANAGE_PARENTAL_CONTROLS_SIGN_IN_WITH_2])
            text.append(explanation)
            message.append(text)
            content.append(message)
            close = localized(Gtk.Button, label=m.CLOSE, halign=Gtk.Align.END,
                css_classes=["management-denied-close"])
            describe_control(
                close, m.CLOSE,
                m.CLOSE_THE_ADMINISTRATOR_REQUIRED_NOTICE,
                automation_id="parent-access-denied-close",
            )
            close.connect("clicked", lambda *_: self.quit())
            content.append(close)
            toolbar.set_content(content)
            window.set_content(toolbar)
            window.set_default_widget(close)
        window.present()


def _can_start(client_factory=BrokerClient, on_error=None):
    # Do this before creating management controls so manually invoking the
    # launcher does not expose them to a standard account. ListManagedUsers
    # is deliberately broker-authorized and therefore uses the same
    # AccountsService role source as all management operations.
    started = time.monotonic()
    LOG.info("parent.startup-check", outcome="started", elapsed_ms=0)
    try:
        client_factory().list_users()
    except Exception as error:
        outcome = ("reboot-required" if broker_reboot_required(error) else
                   "access-denied" if management_access_denied(error) else "unavailable")
        LOG.warning("parent.startup-check", outcome=outcome,
                    elapsed_ms=min(2**31 - 1, max(0, int((time.monotonic() - started) * 1000))))
        if on_error is not None:
            on_error(error)
        return False
    LOG.info("parent.startup-check", outcome="ready",
             elapsed_ms=min(2**31 - 1, max(0, int((time.monotonic() - started) * 1000))))
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
    log_version()
    LOG.info("parent.022")
    return Application(preview=args.preview, check_startup=not args.preview).run([sys.argv[0]])


if __name__ == "__main__":
    from common.oh_no_parent_control_ui.diagnostic_events import run_cli
    raise SystemExit(run_cli(main))
