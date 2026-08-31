"""GIO adapters for Polkit, AccountsService, and caller identity."""

from __future__ import annotations

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

DBUS_NAME = "org.freedesktop.DBus"
DBUS_PATH = "/org/freedesktop/DBus"
DBUS_INTERFACE = "org.freedesktop.DBus"
POLKIT_NAME = "org.freedesktop.PolicyKit1"
POLKIT_PATH = "/org/freedesktop/PolicyKit1/Authority"
POLKIT_INTERFACE = "org.freedesktop.PolicyKit1.Authority"
ACTION_ID = "com.puffyslippers.OhNoParentControl1.request-access"
ACCOUNTS_NAME = "org.freedesktop.Accounts"
ACCOUNTS_PATH = "/org/freedesktop/Accounts"
ACCOUNTS_INTERFACE = "org.freedesktop.Accounts"
PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
SESSION_LIMITS_INTERFACE = "com.endlessm.ParentalControls.SessionLimits"
APP_FILTER_INTERFACE = "com.endlessm.ParentalControls.AppFilter"
CALL_TIMEOUT_MS = 30_000
AUTH_TIMEOUT_MS = 180_000


def _call(connection, name, path, interface, method, parameters, reply_type,
          timeout=CALL_TIMEOUT_MS):
    return connection.call_sync(
        name, path, interface, method, parameters,
        GLib.VariantType.new(reply_type), Gio.DBusCallFlags.NONE, timeout, None,
    )


class CallerCredentials:
    def __init__(self, connection):
        self.connection = connection

    def uid(self, sender: str) -> int:
        reply = _call(
            self.connection, DBUS_NAME, DBUS_PATH, DBUS_INTERFACE,
            "GetConnectionUnixUser", GLib.Variant("(s)", (sender,)), "(u)",
        )
        return reply.unpack()[0]

    def alive(self, sender: str) -> bool:
        try:
            reply = _call(
                self.connection, DBUS_NAME, DBUS_PATH, DBUS_INTERFACE,
                "NameHasOwner", GLib.Variant("(s)", (sender,)), "(b)",
            )
            return reply.unpack()[0]
        except GLib.Error:
            return False


class PolkitAuthorizer:
    def __init__(self, connection):
        self.connection = connection

    def check(self, sender: str, correlation_id: str) -> str:
        subject = (
            "system-bus-name",
            {"name": GLib.Variant("s", sender)},
        )
        details = {"polkit.message": "Authorize additional time and the selected app restrictions"}
        try:
            reply = _call(
                self.connection, POLKIT_NAME, POLKIT_PATH, POLKIT_INTERFACE,
                "CheckAuthorization",
                GLib.Variant("((sa{sv})sa{ss}us)", (
                    subject, ACTION_ID, details,
                    1,  # AllowUserInteraction
                    f"oh-no-parent-control-{correlation_id}",
                )),
                "((bba{ss}))", AUTH_TIMEOUT_MS,
            )
        except GLib.Error:
            # Cancellation, timeout, and authority/agent loss all fail closed.
            return "denied"
        authorized, challenge, _details = reply.unpack()[0]
        if authorized:
            return "approved"
        return "cancelled" if challenge else "denied"


class AccountsService:
    def __init__(self, connection):
        self.connection = connection

    def _user_path(self, uid: int) -> str:
        reply = _call(
            self.connection, ACCOUNTS_NAME, ACCOUNTS_PATH, ACCOUNTS_INTERFACE,
            "FindUserById", GLib.Variant("(x)", (uid,)), "(o)",
        )
        path = reply.unpack()[0]
        if path != f"/org/freedesktop/Accounts/User{uid}":
            raise RuntimeError("AccountsService returned an unexpected user object")
        return path

    def _get(self, uid: int, interface: str, prop: str):
        reply = _call(
            self.connection, ACCOUNTS_NAME, self._user_path(uid), PROPERTIES_INTERFACE,
            "Get", GLib.Variant("(ss)", (interface, prop)), "(v)",
        )
        return reply.unpack()[0]

    def _set(self, uid: int, interface: str, prop: str, value: GLib.Variant):
        _call(
            self.connection, ACCOUNTS_NAME, self._user_path(uid), PROPERTIES_INTERFACE,
            "Set", GLib.Variant("(ssv)", (interface, prop, value)), "()",
        )

    def get_filter(self, child_uid: int) -> tuple[bool, tuple[str, ...]]:
        allowlist, targets = self._get(child_uid, APP_FILTER_INTERFACE, "AppFilter")
        return bool(allowlist), tuple(targets)

    def set_filter(self, child_uid: int, value: tuple[bool, tuple[str, ...]]) -> None:
        allowlist, targets = value
        self._set(child_uid, APP_FILTER_INTERFACE, "AppFilter",
                  GLib.Variant("(bas)", (allowlist, list(targets))))

    def get_extension(self, child_uid: int) -> tuple[int, int]:
        grant_time, duration = self._get(
            child_uid, SESSION_LIMITS_INTERFACE, "ActiveExtension"
        )
        return grant_time, duration

    def set_extension(self, child_uid: int, value: tuple[int, int]) -> None:
        self._set(child_uid, SESSION_LIMITS_INTERFACE, "ActiveExtension",
                  GLib.Variant("(tu)", value))
