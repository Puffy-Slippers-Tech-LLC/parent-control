"""Administrator-facing GTK 4/libadwaita parent-control application."""

from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gio, GLib, Gtk

from .catalog import list_apps
from .client import BrokerClient, configure_logging

LOG = logging.getLogger("oh-no-parent-control-parent")
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
MAX_DAILY_LIMIT_MINUTES = 24 * 60


def _minutes_label(minutes):
    return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"


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
    def __init__(self, application):
        super().__init__(application=application, title="Oh No! Parent Control")
        self.set_default_size(920, 760)
        self._client = BrokerClient()
        self._users = []
        self._preferences = None
        self._rows = []
        self._loading = False
        self._save_in_progress = False
        self._pending_saves = []
        self._restore_preferences_uid = None
        self._time_status_loading = False
        self._build()
        self._time_status_refresh_id = GLib.timeout_add_seconds(
            30, self._refresh_time_status,
        )
        self.connect("close-request", self._close_requested)
        LOG.info("window initialized app_count=%d", len(self._rows))
        GLib.idle_add(self._load_users)

    def _build(self):
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(
            title="Oh No! Parent Control",
        ))
        toolbar.add_top_bar(header)
        page = Adw.PreferencesPage(css_classes=["preferences-page"])
        toolbar.set_content(page)
        self._toasts = Adw.ToastOverlay(child=toolbar)
        self.set_content(self._toasts)

        accounts = Adw.PreferencesGroup(title="Child account")
        account_row = Adw.ActionRow(title="Account")
        self._account = Gtk.DropDown(model=Gtk.StringList.new([]), hexpand=True)
        self._account_changed_handler = self._account.connect(
            "notify::selected", self._account_changed
        )
        account_row.add_suffix(self._account)
        accounts.add(account_row)
        page.add(accounts)

        screen_limits = Adw.PreferencesGroup(title="Screen Limits")
        control_row = Adw.ActionRow(
            title="Screen Time Limit",
            subtitle="Reminders and other hints when the daily time limit is reached",
        )
        self._enabled = Gtk.Switch(valign=Gtk.Align.CENTER, sensitive=False)
        self._enabled.connect("notify::active", self._enabled_changed)
        control_row.add_suffix(self._enabled)
        screen_limits.add(control_row)
        self._daily_limit = Adw.ComboRow(
            title="Daily Time Limit",
            model=Gtk.StringList.new([
                _minutes_label(minutes)
                for minutes in range(MAX_DAILY_LIMIT_MINUTES + 1)
            ]),
            sensitive=False,
        )
        self._daily_limit.connect("notify::selected", self._daily_limit_changed)
        screen_limits.add(self._daily_limit)
        self._time_status = Adw.ActionRow(
            title="Today's Remaining Time",
            subtitle_lines=3,
            subtitle=(
                "Formula: max(Daily allowance remaining, One-time grant remaining) "
                "+ Additional one-time grant\nLoading today's values…"
            ),
        )
        screen_limits.add(self._time_status)
        page.add(screen_limits)

        legend = Adw.PreferencesGroup(
            title="App access legend", css_classes=["policy-legend"],
        )
        legend_row = Gtk.Grid(
            column_homogeneous=True, column_spacing=12,
            css_classes=["policy-legend-row"],
        )
        legend_items = (
            (STATES[0], None),
            (STATES[1], "Can only be unblocked by admins"),
            (STATES[2], "Can be toggled in one-off extensions"),
        )
        for index, (state, subtitle) in enumerate(legend_items):
            column = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                hexpand=True, valign=Gtk.Align.CENTER,
                css_classes=["policy-legend-column"],
            )
            column.append(Gtk.ToggleButton(
                active=True, can_focus=False, can_target=False,
                css_classes=[
                    "policy-choice", "policy-legend-icon", state["css"],
                ],
                child=Gtk.Image(icon_name=state["icon"], pixel_size=19),
                valign=Gtk.Align.CENTER,
            ))
            text = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                hexpand=True, valign=Gtk.Align.CENTER,
            )
            text.append(Gtk.Label(
                label=state["label"], xalign=0,
                css_classes=["policy-legend-title"],
            ))
            if subtitle:
                text.append(Gtk.Label(
                    label=subtitle, xalign=0, wrap=True,
                    css_classes=["policy-legend-description"],
                ))
            column.append(text)
            legend_row.attach(column, index, 0, 1, 1)
        legend.add(legend_row)
        page.add(legend)

        apps = Adw.PreferencesGroup(css_classes=["apps-panel"])
        self._apps_group = apps
        search_row = Adw.ActionRow(
            title="Installed apps",
            subtitle="Desktop, AppImage, Flatpak, Snap, and system launchers",
            css_classes=["apps-panel-header"],
        )
        self._search = Gtk.SearchEntry(
            placeholder_text="Search installed apps", valign=Gtk.Align.CENTER,
            width_chars=25, css_classes=["apps-search"],
        )
        self._search.connect("search-changed", self._filter)
        search_row.add_suffix(self._search)
        apps.add(search_row)
        for app in list_apps():
            row = Adw.ActionRow(
                title=app["name"], subtitle=app["description"] or app["id"],
                css_classes=["app-policy-row"],
            )
            row.app = app
            row.search_text = f'{app["name"]} {app["description"]} {app["id"]}'.casefold()
            if app["icon"]:
                row.add_prefix(Gtk.Image(gicon=app["icon"], pixel_size=32))
            row.policy_buttons = {}
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
                if first_button is None:
                    first_button = button
                else:
                    button.set_group(first_button)
                button.connect("toggled", self._policy_changed)
                row.policy_buttons[state["id"]] = button
                selector.append(button)
            row.add_suffix(selector)
            apps.add(row)
            self._rows.append(row)
        page.add(apps)

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
                LOG.warning("broker operation failed: %s", caught)
                self._toast(f"Could not complete the change: {caught}")
                self._loading = True
                if self._preferences is not None:
                    self._enabled.set_active(bool(
                        self._preferences.get("parent_control_enabled")
                    ))
                    self._daily_limit.set_selected(
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
        self._run(self._client.list_users, self._users_loaded)
        return GLib.SOURCE_REMOVE

    def _users_loaded(self, users):
        self._users = list(users)
        LOG.info("managed-user discovery completed count=%d", len(self._users))
        self._account.handler_block(self._account_changed_handler)
        try:
            self._account.set_model(Gtk.StringList.new(
                [label for _uid, label in self._users]
            ))
            if self._users:
                self._account.set_selected(0)
        finally:
            self._account.handler_unblock(self._account_changed_handler)

        if self._users:
            self._load_selected()
        else:
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
        self._loading = True
        self._time_status.set_subtitle(
            "Formula: max(Daily allowance remaining, One-time grant remaining) "
            "+ Additional one-time grant\nLoading today's values…"
        )
        LOG.info("preferences load started target_uid=%d", uid)
        self._set_apps_sensitive(False)
        self._run(lambda: self._client.get_preferences(uid),
                  lambda value: self._preferences_for(uid, value))

    def _preferences_for(self, uid, preferences):
        if uid != self._selected_uid():
            return
        self._preferences_loaded(preferences)

    def _preferences_loaded(self, preferences):
        self._preferences = preferences
        self._enabled.set_active(preferences["parent_control_enabled"])
        self._daily_limit.set_selected(preferences["daily_time_limit_minutes"])
        for row in self._rows:
            state = preferences["apps"].get(row.app["id"], {}).get("state", "allowed")
            row.policy_buttons[state].set_active(True)
        self._loading = False
        self._set_apps_sensitive(True)
        LOG.info("preferences loaded target_uid=%d enabled=%s policy_count=%d",
                 self._selected_uid(), preferences["parent_control_enabled"],
                 len(preferences["apps"]))
        self._load_time_status()

    def _load_time_status(self):
        uid = self._selected_uid()
        if uid is None or self._time_status_loading:
            return
        self._time_status_loading = True
        self._run(
            lambda: self._client.get_time_status(uid),
            lambda value: self._time_status_loaded(uid, value),
            lambda error: self._time_status_failed(uid, error),
        )

    def _time_status_loaded(self, uid, status):
        self._time_status_loading = False
        if uid != self._selected_uid():
            self._load_time_status()
            return
        self._time_status.set_subtitle(_time_status_subtitle(status))
        LOG.info(
            "remaining time loaded target_uid=%d daily=%d grant=%d additional=%d calculated=%d",
            uid,
            status["daily_allowance_remaining_seconds"],
            status["one_time_grant_remaining_seconds"],
            status["additional_one_time_grant_seconds"],
            status["calculated_active_extension_seconds"],
        )

    def _time_status_failed(self, uid, error):
        self._time_status_loading = False
        if uid != self._selected_uid():
            self._load_time_status()
            return
        LOG.warning("remaining-time load failed target_uid=%d: %s", uid, error)
        self._time_status.set_subtitle(
            "Formula: max(Daily allowance remaining, One-time grant remaining) "
            "+ Additional one-time grant\nToday's values are unavailable."
        )

    def _refresh_time_status(self):
        if self._selected_uid() is not None:
            self._load_time_status()
        return GLib.SOURCE_CONTINUE

    def _close_requested(self, *_args):
        if self._time_status_refresh_id:
            GLib.source_remove(self._time_status_refresh_id)
            self._time_status_refresh_id = 0
        return False

    def _set_apps_sensitive(self, sensitive):
        sensitive = bool(
            sensitive and not self._loading and self._selected_uid() is not None
        )
        self._account.set_sensitive(not self._loading)
        self._enabled.set_sensitive(not self._loading and self._selected_uid() is not None)
        self._daily_limit.set_sensitive(
            not self._loading and self._selected_uid() is not None and
            self._enabled.get_active()
        )
        self._apps_group.set_sensitive(sensitive)

    def _enabled_changed(self, switch, _param):
        if self._loading or self._selected_uid() is None:
            return
        self._daily_limit.set_sensitive(switch.get_active())
        self._save_parent_control(switch.get_active())

    def _daily_limit_changed(self, row, _param):
        if self._loading or self._selected_uid() is None:
            return
        self._save_parent_control(self._enabled.get_active())

    def _save_parent_control(self, enabled):
        uid = self._selected_uid()
        daily_limit_minutes = self._daily_limit.get_selected()
        self._queue_save("parent-control", uid, enabled, daily_limit_minutes)

    def _start_parent_control_save(self, uid, enabled, daily_limit_minutes):
        LOG.info(
            "parent-control change started target_uid=%d enabled=%s daily_limit_minutes=%d",
            uid, enabled, daily_limit_minutes,
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

    def _app_policy_value(self):
        value = dict(self._preferences)
        # SetPreferences retains the enabled state, but it persists the daily
        # limit. Take it from the current control so queued policy changes do
        # not reintroduce an earlier limit after a screen-time edit.
        value["daily_time_limit_minutes"] = self._daily_limit.get_selected()
        value["apps"] = {}
        for row in self._rows:
            state = next(
                state["id"] for state in STATES
                if row.policy_buttons[state["id"]].get_active()
            )
            if state != "allowed":
                value["apps"][row.app["id"]] = {
                    "state": state, "targets": row.app["targets"],
                }
        return value

    def _save_app_policy(self):
        if not self._preferences or self._selected_uid() is None:
            return
        value = self._app_policy_value()
        uid = self._selected_uid()
        self._queue_save("app-policy", uid, value)

    def _start_app_policy_save(self, uid, value):
        LOG.info("app-policy auto-save started target_uid=%d policy_count=%d",
                 uid, len(value["apps"]))
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
        LOG.info("preference auto-save completed target_uid=%d", uid)
        if refresh_time_status:
            self._load_time_status()
        self._start_next_save()

    def _save_failed(self, uid, setting, error):
        self._save_in_progress = False
        LOG.warning("preference auto-save failed target_uid=%d setting=%s: %s",
                    uid, setting, error)
        self._toast(f"Could not save {setting}: {error}")
        if uid == self._selected_uid():
            self._restore_preferences_uid = uid
        self._start_next_save()

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

    def _filter(self, entry):
        query = entry.get_text().strip().casefold()
        for row in self._rows:
            row.set_visible(not query or query in row.search_text)


class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.puffyslippers.OhNoParentControl.Parent")
        self._css_provider = None

    def do_activate(self):
        window = self.get_active_window() or ParentWindow(self)
        if self._css_provider is None:
            self._css_provider = Gtk.CssProvider()
            self._css_provider.load_from_path(str(Path(__file__).with_name("style.css")))
            Gtk.StyleContext.add_provider_for_display(
                window.get_display(), self._css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
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


def main():
    configure_logging()
    if not _can_start():
        LOG.warning("parent app launch denied or broker unavailable")
        return 1
    LOG.info("parent app starting")
    return Application().run(sys.argv)
