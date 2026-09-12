"""Small synchronous client used by the administrator UI."""

import json
import logging
from common.oh_no_parent_control_ui.diagnostic_events import get_logger, error_code
from common.oh_no_parent_control_ui.diagnostic_events import record_payload

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

BUS_NAME = "com.puffyslippers.OhNoParentControl1"
OBJECT_PATH = "/com/puffyslippers/OhNoParentControl1"
INTERFACE = BUS_NAME
LOG = get_logger("parent-client")


class BrokerClient:
    def __init__(self, connection=None):
        self.connection = connection or Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

    def _call(self, method, parameters, signature):
        result = self.connection.call_sync(
            BUS_NAME, OBJECT_PATH, INTERFACE, method, parameters,
            GLib.VariantType.new(signature), Gio.DBusCallFlags.NONE, 120_000, None,
        )
        return result.unpack()

    def list_users(self):
        users, = self._call("ListManagedUsers", None, "(a(uss))")
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
        # AccountsService's cross-account grant read requires separate Polkit
        # authentication. The broker already authorizes the caller and target,
        # reads the grant, and queries usage through the child's own identity.
        # Periodic refresh must not depend on retained Polkit authorization.
        try:
            daily, grant, additional, calculated = self._call(
                "GetTimeStatus", GLib.Variant("(uu)", (uid, additional_seconds)),
                "(uuuu)",
            )
        except Exception as error:
            LOG.warning("parent-client.001", error_type=error_code(error))
            raise
        return {
            "daily_allowance_remaining_seconds": daily,
            "one_time_grant_remaining_seconds": grant,
            "additional_one_time_grant_seconds": additional,
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
            self._client.log_event(record.levelname, record_payload(record))
        except Exception:
            # Logging must never prevent the management UI from opening.
            self._client = None


def configure_logging():
    handler = BrokerLogHandler()
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
