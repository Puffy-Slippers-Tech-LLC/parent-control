"""GIO adapters for Polkit, AccountsService, and caller identity."""

from __future__ import annotations

import pwd

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

from .core import UserAccount

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
TIMER_NAME = "org.freedesktop.MalcontentTimer1"
TIMER_PATH = "/org/freedesktop/MalcontentTimer1"
TIMER_PARENT_INTERFACE = "org.freedesktop.MalcontentTimer1.Parent"
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

    def check(self, sender: str, correlation_id: str, target_label: str) -> str:
        subject = (
            "system-bus-name",
            {"name": GLib.Variant("s", sender)},
        )
        details = {"target-account": target_label}
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

    def _account_from_path(self, path: str) -> UserAccount:
        reply = _call(
            self.connection, ACCOUNTS_NAME, path, PROPERTIES_INTERFACE,
            "GetAll", GLib.Variant("(s)", (ACCOUNTS_INTERFACE + ".User",)), "(a{sv})",
        )
        properties = reply.unpack()[0]
        uid = properties["Uid"]
        expected_path = f"/org/freedesktop/Accounts/User{uid}"
        if path != expected_path:
            raise RuntimeError("AccountsService returned an unexpected user object")
        username = properties.get("UserName", "")
        real_name = " ".join(properties.get("RealName", "").split())[:120]
        label = real_name or username or str(uid)
        return UserAccount(
            uid=uid,
            username=username,
            label=label,
            is_admin=properties.get("AccountType", 0) != 0,
            is_system=properties.get("SystemAccount", True),
            is_local=properties.get("LocalAccount", False),
        )

    def list_users(self) -> tuple[UserAccount, ...]:
        # ListCachedUsers is explicitly non-exhaustive. Enumerate current NSS
        # identities so a newly created local account appears before first
        # login, then use AccountsService as the authority for account type.
        noninteractive_shells = {"", "/bin/false", "/usr/bin/false",
                                 "/sbin/nologin", "/usr/sbin/nologin"}
        uids = sorted({entry.pw_uid for entry in pwd.getpwall()
                       if 1000 <= entry.pw_uid <= (1 << 32) - 1 and
                       getattr(entry, "pw_shell", "/bin/sh") not in noninteractive_shells})
        users = []
        for uid in uids:
            try:
                users.append(self.get_user(uid))
            except GLib.Error:
                # The account may have been deleted during enumeration.
                continue
        return tuple(users)

    def get_user(self, uid: int) -> UserAccount:
        return self._account_from_path(self._user_path(uid))

    def _set(self, uid: int, interface: str, prop: str, value: GLib.Variant):
        _call(
            self.connection, ACCOUNTS_NAME, self._user_path(uid), PROPERTIES_INTERFACE,
            "Set", GLib.Variant("(ssv)", (interface, prop, value)), "()",
        )

    def get_filter(self, target_uid: int) -> tuple[bool, tuple[str, ...]]:
        allowlist, targets = self._get(target_uid, APP_FILTER_INTERFACE, "AppFilter")
        return bool(allowlist), tuple(targets)

    def set_filter(self, target_uid: int, value: tuple[bool, tuple[str, ...]]) -> None:
        allowlist, targets = value
        self._set(target_uid, APP_FILTER_INTERFACE, "AppFilter",
                  GLib.Variant("(bas)", (allowlist, list(targets))))

    def get_extension(self, target_uid: int) -> tuple[int, int]:
        grant_time, duration = self._get(
            target_uid, SESSION_LIMITS_INTERFACE, "ActiveExtension"
        )
        return grant_time, duration

    def set_extension(self, target_uid: int, value: tuple[int, int]) -> None:
        self._set(target_uid, SESSION_LIMITS_INTERFACE, "ActiveExtension",
                  GLib.Variant("(tu)", value))

    def get_limit_type(self, uid: int) -> int:
        return self._get(uid, SESSION_LIMITS_INTERFACE, "LimitType")

    def set_limit_type(self, uid: int, value: int) -> None:
        self._set(uid, SESSION_LIMITS_INTERFACE, "LimitType", GLib.Variant("u", value))

    def get_daily_limit(self, uid: int) -> int:
        return self._get(uid, SESSION_LIMITS_INTERFACE, "DailyLimit")

    def set_daily_limit(self, uid: int, value: int) -> None:
        self._set(uid, SESSION_LIMITS_INTERFACE, "DailyLimit", GLib.Variant("u", value))


class TimerUsage:
    def __init__(self, connection):
        self.connection = connection

    def query_usage(self, uid: int) -> tuple[tuple[int, int], ...]:
        reply = _call(
            self.connection, TIMER_NAME, TIMER_PATH, TIMER_PARENT_INTERFACE,
            "QueryUsage", GLib.Variant("(uss)", (uid, "login-session", "")),
            "(a(tt))",
        )
        return tuple(tuple(interval) for interval in reply.unpack()[0])
