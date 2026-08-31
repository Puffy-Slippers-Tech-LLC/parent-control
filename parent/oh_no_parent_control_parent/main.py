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
from .client import BrokerClient

LOG = logging.getLogger("oh-no-parent-control-parent")
STATES = (
    ("allowed", "Always Allowed"),
    ("permanent", "Hard Blocked"),
    ("conditional", "Soft Blocked"),
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
        self._build()
        GLib.idle_add(self._load_users)

    def _build(self):
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(
            title="Oh No! Parent Control", subtitle="Manage a child account",
        ))
        toolbar.add_top_bar(header)
        page = Adw.PreferencesPage()
        toolbar.set_content(page)
        self._toasts = Adw.ToastOverlay(child=toolbar)
        self.set_content(self._toasts)

        accounts = Adw.PreferencesGroup(title="Child account")
        account_row = Adw.ActionRow(title="Account")
        self._account = Gtk.DropDown(model=Gtk.StringList.new([]), hexpand=True)
        self._account.connect("notify::selected", self._account_changed)
        account_row.add_suffix(self._account)
        accounts.add(account_row)
        control_row = Adw.ActionRow(
            title="Parent Control",
            subtitle="Install and enable the child extension for this account",
        )
        self._enabled = Gtk.Switch(valign=Gtk.Align.CENTER, sensitive=False)
        self._enabled.connect("notify::active", self._enabled_changed)
        control_row.add_suffix(self._enabled)
        accounts.add(control_row)
        page.add(accounts)

        apps = Adw.PreferencesGroup(
            title="App access",
            description="Always allowed, hard blocked, or soft blocked for extra-time requests.",
        )
        self._apps_group = apps
        search_row = Adw.ActionRow(title="Installed apps")
        self._search = Gtk.SearchEntry(placeholder_text="Search apps", width_chars=24)
        self._search.connect("search-changed", self._filter)
        search_row.add_suffix(self._search)
        apps.add(search_row)
        for app in list_apps():
            row = Adw.ActionRow(title=app["name"], subtitle=app["description"])
            row.app = app
            row.search_text = f'{app["name"]} {app["description"]} {app["id"]}'.casefold()
            if app["icon"]:
                row.add_prefix(Gtk.Image(gicon=app["icon"], pixel_size=32))
            row.selector = Gtk.DropDown(model=Gtk.StringList.new(
                [label for _state, label in STATES]
            ))
            row.selector.connect("notify::selected", self._policy_changed)
            row.add_suffix(row.selector)
            apps.add(row)
            self._rows.append(row)
        page.add(apps)

        actions = Adw.PreferencesGroup()
        save_row = Adw.ActionRow(
            title="Save app access",
            subtitle="Changes apply to the selected child’s shared preferences.",
        )
        self._save = Gtk.Button(
            label="Save Changes", css_classes=["suggested-action"],
            valign=Gtk.Align.CENTER, sensitive=False,
        )
        self._save.connect("clicked", self._save_clicked)
        save_row.add_suffix(self._save)
        actions.add(save_row)
        page.add(actions)

    def _run(self, operation, success):
        def done(value=None, error=None):
            try:
                if error is not None:
                    raise error
                success(value)
            except Exception as caught:
                LOG.warning("broker operation failed: %s", caught)
                self._toast(f"Could not complete the change: {caught}")
                self._loading = False
                self._set_apps_sensitive(bool(
                    self._preferences and
                    self._preferences.get("parent_control_enabled")
                ))

        def worker():
            try:
                value = operation()
                GLib.idle_add(done, value, None)
            except Exception as error:
                GLib.idle_add(done, None, error)

        threading.Thread(target=worker, daemon=True).start()

    def _load_users(self):
        self._run(self._client.list_users, self._users_loaded)
        return GLib.SOURCE_REMOVE

    def _users_loaded(self, users):
        self._users = list(users)
        self._account.set_model(Gtk.StringList.new([label for _uid, label in self._users]))
        if self._users:
            self._account.set_selected(0)
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
        for row in self._rows:
            state = preferences["apps"].get(row.app["id"], {}).get("state", "allowed")
            row.selector.set_selected(next(
                index for index, (value, _label) in enumerate(STATES) if value == state
            ))
        self._loading = False
        self._set_apps_sensitive(preferences["parent_control_enabled"])
        self._save.set_sensitive(False)

    def _set_apps_sensitive(self, sensitive):
        self._account.set_sensitive(not self._loading)
        self._enabled.set_sensitive(not self._loading and self._selected_uid() is not None)
        self._apps_group.set_sensitive(sensitive)

    def _enabled_changed(self, switch, _param):
        if self._loading or self._selected_uid() is None:
            return
        enabled, uid = switch.get_active(), self._selected_uid()
        self._loading = True
        self._set_apps_sensitive(False)
        self._run(lambda: self._client.set_parent_control(uid, enabled),
                  self._preferences_loaded)

    def _policy_changed(self, *_args):
        if not self._loading:
            self._save.set_sensitive(True)

    def _save_clicked(self, *_args):
        if not self._preferences or self._selected_uid() is None:
            return
        value = dict(self._preferences)
        value["apps"] = {}
        for row in self._rows:
            state = STATES[row.selector.get_selected()][0]
            if state != "allowed":
                value["apps"][row.app["id"]] = {
                    "state": state, "targets": row.app["targets"],
                }
        uid = self._selected_uid()
        self._loading = True
        self._save.set_sensitive(False)
        self._run(lambda: self._client.set_preferences(uid, value), self._saved)

    def _saved(self, preferences):
        self._preferences_loaded(preferences)
        self._toast("App access saved")

    def _toast(self, title):
        self._toasts.add_toast(Adw.Toast(title=title))

    def _filter(self, entry):
        query = entry.get_text().strip().casefold()
        for row in self._rows:
            row.set_visible(not query or query in row.search_text)


class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.puffyslippers.OhNoParentControl.Parent")

    def do_activate(self):
        (self.get_active_window() or ParentWindow(self)).present()


def main():
    logging.basicConfig(level=logging.INFO)
    return Application().run(sys.argv)
