#!/usr/bin/python3
"""Tell PAM whether an account is confirmed to have no session limit."""

from __future__ import annotations

import os
import pwd
import sys
import syslog

import gi

gi.require_version("Gio", "2.0")
gi.require_version("Malcontent", "0")
from gi.repository import Gio, GLib, Malcontent


ACCOUNTS_NAME = "org.freedesktop.Accounts"
ACCOUNTS_PATH = "/org/freedesktop/Accounts"
ACCOUNTS_INTERFACE = "org.freedesktop.Accounts"
PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
SESSION_LIMITS_INTERFACE = "com.endlessm.ParentalControls.SessionLimits"
CALL_TIMEOUT_MS = 3_000
UINT32_MAX = (1 << 32) - 1
GDM_PASSWORD_SERVICE = "gdm-password"


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


def is_authentication_allowed(username: str, service: str, connection=None,
                              now=None) -> bool:
    """Apply Malcontent's supported time check to GDM login and unlock auth."""
    # Fresh non-GDM logins still pass through pam_malcontent's account hook.
    # Restrict this additional authentication hook to GDM, where unlocking an
    # existing session does not run PAM account management again.
    if service != GDM_PASSWORD_SERVICE:
        return True
    if not username:
        return False
    try:
        identity = pwd.getpwnam(username)
    except KeyError:
        return False
    if identity.pw_name != username or not 0 <= identity.pw_uid <= UINT32_MAX:
        return False
    # Root must remain a recovery path. The PAM profile separately skips the
    # kiosk account and Ubuntu administrators without consulting this helper.
    if identity.pw_uid == 0:
        return True

    try:
        if connection is None:
            connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        manager = Malcontent.Manager.new(connection)
        limits = manager.get_session_limits(
            identity.pw_uid, Malcontent.ManagerGetValueFlags.NONE, None,
        )
        if now is None:
            now = GLib.DateTime.new_now_local()
        result = limits.check_time_remaining(now, 0)
        allowed, remaining, enabled, extension_active = result
    except (GLib.Error, OSError, OverflowError, RuntimeError, TypeError, ValueError):
        return False

    return (
        type(allowed) is bool and type(remaining) is int and
        type(enabled) is bool and type(extension_active) is bool and
        remaining >= 0 and allowed
    )


def _log_authentication_outcome(allowed: bool) -> None:
    outcome = "accepted" if allowed else "denied"
    syslog.syslog(
        syslog.LOG_INFO if allowed else syslog.LOG_WARNING,
        f"screen-time authentication outcome={outcome} target=[Child user]",
    )


def main(arguments=None) -> int:
    arguments = sys.argv[1:] if arguments is None else arguments
    if arguments == ["--authenticate"]:
        allowed = is_authentication_allowed(
            os.environ.get("PAM_USER", ""), os.environ.get("PAM_SERVICE", ""),
        )
        if os.environ.get("PAM_SERVICE") == GDM_PASSWORD_SERVICE:
            _log_authentication_outcome(allowed)
        return 0 if allowed else 1
    if arguments:
        return 1
    # A successful helper result skips pam_malcontent. Every restricted or
    # indeterminate result leaves the enforcing module in the account stack.
    return 0 if is_confirmed_unrestricted(os.environ.get("PAM_USER", "")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
