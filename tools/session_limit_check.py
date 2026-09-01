#!/usr/bin/python3
"""Tell PAM whether an account is confirmed to have no session limit."""

from __future__ import annotations

import os
import pwd

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib


ACCOUNTS_NAME = "org.freedesktop.Accounts"
ACCOUNTS_PATH = "/org/freedesktop/Accounts"
ACCOUNTS_INTERFACE = "org.freedesktop.Accounts"
PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
SESSION_LIMITS_INTERFACE = "com.endlessm.ParentalControls.SessionLimits"
CALL_TIMEOUT_MS = 3_000
UINT32_MAX = (1 << 32) - 1


def _call(connection, path: str, interface: str, method: str,
          parameters: GLib.Variant, reply_type: str):
    return connection.call_sync(
        ACCOUNTS_NAME,
        path,
        interface,
        method,
        parameters,
        GLib.VariantType.new(reply_type),
        Gio.DBusCallFlags.NONE,
        CALL_TIMEOUT_MS,
        None,
    )


def is_confirmed_unrestricted(username: str, connection=None) -> bool:
    """Return true only when AccountsService confirms LimitType is NONE."""
    if not username:
        return False
    try:
        identity = pwd.getpwnam(username)
    except KeyError:
        return False
    if identity.pw_name != username or not 0 < identity.pw_uid <= UINT32_MAX:
        return False

    try:
        if connection is None:
            connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        expected_path = f"/org/freedesktop/Accounts/User{identity.pw_uid}"
        lookup = _call(
            connection,
            ACCOUNTS_PATH,
            ACCOUNTS_INTERFACE,
            "FindUserById",
            GLib.Variant("(x)", (identity.pw_uid,)),
            "(o)",
        )
        if lookup.unpack()[0] != expected_path:
            return False
        reply = _call(
            connection,
            expected_path,
            PROPERTIES_INTERFACE,
            "Get",
            GLib.Variant("(ss)", (SESSION_LIMITS_INTERFACE, "LimitType")),
            "(v)",
        )
        limit_type = reply.unpack()[0]
    except (GLib.Error, OSError, RuntimeError, TypeError, ValueError):
        return False

    return type(limit_type) is int and limit_type == 0


def main() -> int:
    # A successful helper result skips pam_malcontent. Every restricted or
    # indeterminate result leaves the enforcing module in the account stack.
    return 0 if is_confirmed_unrestricted(os.environ.get("PAM_USER", "")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
