"""Small synchronous client used by the administrator UI."""

import json
import logging
from datetime import datetime

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

BUS_NAME = "com.puffyslippers.OhNoParentControl1"
OBJECT_PATH = "/com/puffyslippers/OhNoParentControl1"
INTERFACE = BUS_NAME
TIMER_NAME = "org.freedesktop.MalcontentTimer1"
TIMER_PATH = "/org/freedesktop/MalcontentTimer1"
TIMER_PARENT_INTERFACE = "org.freedesktop.MalcontentTimer1.Parent"
ACCOUNTS_NAME = "org.freedesktop.Accounts"
PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
SESSION_LIMITS_INTERFACE = "com.endlessm.ParentalControls.SessionLimits"


class BrokerClient:
    def __init__(self, connection=None, *, now=lambda: datetime.now().astimezone()):
        self.connection = connection or Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self._now = now

    def _call(self, method, parameters, signature):
        result = self.connection.call_sync(
            BUS_NAME, OBJECT_PATH, INTERFACE, method, parameters,
            GLib.VariantType.new(signature), Gio.DBusCallFlags.NONE, 120_000, None,
        )
        return result.unpack()

    def list_users(self):
        users, = self._call("ListManagedUsers", None, "(a(us))")
        return users

    def get_preferences(self, uid):
        encoded, = self._call("GetPreferences", GLib.Variant("(u)", (uid,)), "(s)")
        return json.loads(encoded)

    def list_apps(self, uid):
        applications, = self._call(
            "ListApplications", GLib.Variant("(u)", (uid,)), "(a(ssssasas))",
        )
        return [
            {"id": app_id, "name": name, "description": description,
             "icon": icon, "targets": list(targets),
             "suggested_patterns": list(patterns)}
            for app_id, name, description, icon, targets, patterns in applications
        ]

    def get_time_status(self, uid, additional_seconds=0):
        # Malcontent deliberately authorizes QueryUsage against the real parent
        # account which owns this D-Bus connection. A root broker is not a
        # Malcontent parent and therefore cannot proxy this particular read.
        usage_reply = self.connection.call_sync(
            TIMER_NAME, TIMER_PATH, TIMER_PARENT_INTERFACE, "QueryUsage",
            GLib.Variant("(uss)", (uid, "login-session", "")),
            GLib.VariantType.new("(a(tt))"), Gio.DBusCallFlags.NONE, 30_000, None,
        )
        usage_entries, = usage_reply.unpack()
        preferences = self.get_preferences(uid)
        extension_reply = self.connection.call_sync(
            ACCOUNTS_NAME, f"/org/freedesktop/Accounts/User{uid}",
            PROPERTIES_INTERFACE, "Get",
            GLib.Variant("(ss)", (SESSION_LIMITS_INTERFACE, "ActiveExtension")),
            GLib.VariantType.new("(v)"), Gio.DBusCallFlags.NONE, 30_000, None,
        )
        grant_time, grant_duration = extension_reply.unpack()[0]

        now = self._now()
        now_seconds = int(now.timestamp())
        start_of_today = datetime.combine(
            now.date(), datetime.min.time(), tzinfo=now.tzinfo,
        )
        start_of_today_seconds = int(start_of_today.timestamp())
        intervals = []
        for start, end in usage_entries:
            if (type(start) is not int or type(end) is not int or
                    start < 0 or end < start):
                raise ValueError("Malcontent returned an invalid usage interval")
            clipped_start = max(start, start_of_today_seconds)
            clipped_end = min(end, now_seconds)
            if clipped_end > clipped_start:
                intervals.append((clipped_start, clipped_end))
        used_today = 0
        merged_end = 0
        for start, end in sorted(intervals):
            if start >= merged_end:
                used_today += end - start
            elif end > merged_end:
                used_today += end - merged_end
            merged_end = max(merged_end, end)

        daily_limit_seconds = (
            preferences["daily_time_limit_minutes"] * 60
            if preferences["parent_control_enabled"] else 0
        )
        daily = max(0, daily_limit_seconds - used_today)
        grant = max(0, grant_time + grant_duration - now_seconds)
        calculated, = self._call(
            "CalculateRemainingTime",
            GLib.Variant("(uuuu)", (uid, daily, grant, additional_seconds)),
            "(u)",
        )
        return {
            "daily_allowance_remaining_seconds": daily,
            "one_time_grant_remaining_seconds": grant,
            "additional_one_time_grant_seconds": additional_seconds,
            "calculated_active_extension_seconds": calculated,
        }

    def set_preferences(self, uid, value):
        encoded, = self._call(
            "SetPreferences", GLib.Variant("(us)", (uid, json.dumps(value))), "(s)",
        )
        return json.loads(encoded)

    def set_parent_control(self, uid, enabled, daily_limit_minutes):
        encoded, = self._call(
            "SetParentControl",
            GLib.Variant("(ubu)", (uid, enabled, daily_limit_minutes)), "(s)",
        )
        return json.loads(encoded)

    def revoke_one_time_grant(self, uid):
        self._call("RevokeOneTimeGrant", GLib.Variant("(u)", (uid,)), "()")

    def log_event(self, level, message):
        self.connection.call(
            BUS_NAME, OBJECT_PATH, INTERFACE, "LogEvent",
            GLib.Variant("(sss)", ("parent", level, message)),
            GLib.VariantType.new("()"), Gio.DBusCallFlags.NONE, 5_000, None, None,
        )


class BrokerLogHandler(logging.Handler):
    """Forward parent-app records to the broker-owned daily log."""

    def __init__(self):
        super().__init__()
        self._client = None

    def emit(self, record):
        try:
            if self._client is None:
                self._client = BrokerClient()
            self._client.log_event(record.levelname, self.format(record))
        except Exception:
            # Logging must never prevent the management UI from opening.
            self._client = None


def configure_logging():
    handler = BrokerLogHandler()
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
