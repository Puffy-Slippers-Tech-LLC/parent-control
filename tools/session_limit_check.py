#!/usr/bin/python3
"""Tell PAM whether this account check can skip session-time enforcement."""

from __future__ import annotations

import os
import pwd
import sys
import syslog
from enum import IntEnum

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
# The broker's existing usage helper has a 30-second deadline.
TIME_STATUS_TIMEOUT_MS = 35_000
BROKER_NAME = "com.puffyslippers.OhNoParentControl1"
BROKER_PATH = "/com/puffyslippers/OhNoParentControl1"
UINT32_MAX = (1 << 32) - 1
GDM_PASSWORD_SERVICE = "gdm-password"
SYSTEMD_NAME = "org.freedesktop.systemd1"
SYSTEMD_PATH = "/org/freedesktop/systemd1"
SYSTEMD_SERVICE_INTERFACE = "org.freedesktop.systemd1.Service"
SYSTEMD_UNIT_INTERFACE = "org.freedesktop.systemd1.Unit"
STDIO_BRIDGE = "/usr/bin/systemd-stdio-bridge"


class AuthenticationOutcome(IntEnum):
    ALLOWED = 0
    DENIED = 1
    ERROR = 2


def _call(connection, path: str, interface: str, method: str,
          parameters: GLib.Variant, reply_type: str, *, destination=ACCOUNTS_NAME):
    return connection.call_sync(
        destination,
        path,
        interface,
        method,
        parameters,
        GLib.VariantType.new(reply_type),
        Gio.DBusCallFlags.NONE,
        CALL_TIMEOUT_MS,
        None,
    )


def is_systemd_user_bus_bridge(username: str, service: str, connection=None) -> bool:
    """Recognize systemd's administrative user-bus transport, never a login.

    systemctl --user --machine=UID@ uses a transient system service with
    PAMName=login. Its account check must work even after the child's time is
    exhausted. Bind pam_exec's live parent to the system manager's MainPID and
    exact command; PAM environment, process names and unit names prove nothing.
    This does not skip the rest of PAM or the independent kiosk admission gate.
    """
    if (service != "login" or not username or username == "oh-no-parent-control"
            or os.getuid() != 0 or os.geteuid() != 0):
        return False
    parent = os.getppid()
    if parent <= 1:
        return False
    try:
        identity = pwd.getpwnam(username)
        if identity.pw_name != username or not 0 < identity.pw_uid <= UINT32_MAX:
            return False
        if connection is None:
            connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        path = _call(
            connection, SYSTEMD_PATH, SYSTEMD_NAME + ".Manager", "GetUnitByPID",
            GLib.Variant("(u)", (parent,)), "(o)", destination=SYSTEMD_NAME,
        ).unpack()[0]
        unit = _call(
            connection, path, PROPERTIES_INTERFACE, "GetAll",
            GLib.Variant("(s)", (SYSTEMD_UNIT_INTERFACE,)), "(a{sv})",
            destination=SYSTEMD_NAME,
        ).unpack()[0]
        properties = _call(
            connection, path, PROPERTIES_INTERFACE, "GetAll",
            GLib.Variant("(s)", (SYSTEMD_SERVICE_INTERFACE,)), "(a{sv})",
            destination=SYSTEMD_NAME,
        ).unpack()[0]
        commands = properties["ExecStart"]
        return (
            unit["Transient"] is True
            and properties["MainPID"] == parent
            and properties["User"] in (username, str(identity.pw_uid))
            and properties["PAMName"] == "login"
            and len(commands) == 1
            # The native -M.host transport preserves the executable basename
            # in ExecStart. Accept only that exact name or its fixed path.
            and commands[0][0] in (STDIO_BRIDGE, "systemd-stdio-bridge")
            and commands[0][1] in (
                [STDIO_BRIDGE, "--user", "--quiet"],
                ["systemd-stdio-bridge", "--user", "--quiet"],
            )
            and os.getppid() == parent
        )
    except (GLib.Error, OSError, RuntimeError, TypeError, ValueError, KeyError, IndexError):
        return False


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


def authentication_outcome(username: str, service: str, connection=None,
                           now=None) -> AuthenticationOutcome:
    """Classify a GDM login or unlock using Malcontent's supported time check."""
    # Fresh non-GDM logins still pass through pam_malcontent's account hook.
    # Restrict this additional authentication hook to GDM, where unlocking an
    # existing session does not run PAM account management again.
    if service != GDM_PASSWORD_SERVICE:
        return AuthenticationOutcome.ALLOWED
    if not username:
        return AuthenticationOutcome.ERROR
    try:
        identity = pwd.getpwnam(username)
    except KeyError:
        return AuthenticationOutcome.ERROR
    if identity.pw_name != username or not 0 <= identity.pw_uid <= UINT32_MAX:
        return AuthenticationOutcome.ERROR
    # Root must remain a recovery path. The PAM profile separately skips the
    # kiosk account and Ubuntu administrators without consulting this helper.
    if identity.pw_uid == 0:
        return AuthenticationOutcome.ALLOWED

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
        return AuthenticationOutcome.ERROR

    if not (
            type(allowed) is bool and type(remaining) is int and
            type(enabled) is bool and type(extension_active) is bool and
            remaining >= 0):
        return AuthenticationOutcome.ERROR
    if allowed:
        if not enabled or extension_active:
            return AuthenticationOutcome.ALLOWED
        # Malcontent's check takes today's active use as an argument. Zero
        # checks the configured allowance, not whether it has been consumed.
        # Reuse the broker's recorded-use calculation and child-owned query.
        try:
            daily, grant, additional, total = connection.call_sync(
                BROKER_NAME, BROKER_PATH, BROKER_NAME, "GetTimeStatus",
                GLib.Variant("(uu)", (identity.pw_uid, 0)),
                GLib.VariantType.new("(uuuu)"), Gio.DBusCallFlags.NONE,
                TIME_STATUS_TIMEOUT_MS, None,
            ).unpack()
        except (GLib.Error, OSError, RuntimeError, TypeError, ValueError):
            return AuthenticationOutcome.ERROR
        if additional != 0 or total != max(daily, grant):
            return AuthenticationOutcome.ERROR
        return (AuthenticationOutcome.ALLOWED if total > 0
                else AuthenticationOutcome.DENIED)
    if enabled and remaining == 0:
        return AuthenticationOutcome.DENIED
    return AuthenticationOutcome.ERROR


def _log_authentication_outcome(outcome: AuthenticationOutcome) -> None:
    labels = {
        AuthenticationOutcome.ALLOWED: "accepted",
        AuthenticationOutcome.DENIED: "denied-no-time",
        AuthenticationOutcome.ERROR: "denied-check-error",
    }
    syslog.syslog(
        syslog.LOG_INFO if outcome == AuthenticationOutcome.ALLOWED
        else syslog.LOG_WARNING,
        f"onpc.session-limit authentication outcome={labels[outcome]} "
        "target=[Child user]",
    )


def main(arguments=None) -> int:
    arguments = sys.argv[1:] if arguments is None else arguments
    if arguments == ["--authenticate"]:
        outcome = authentication_outcome(
            os.environ.get("PAM_USER", ""), os.environ.get("PAM_SERVICE", ""),
        )
        if os.environ.get("PAM_SERVICE") == GDM_PASSWORD_SERVICE:
            _log_authentication_outcome(outcome)
        return int(outcome)
    if arguments:
        return 1
    # A successful helper result skips only the two product time modules.
    # All other restricted or indeterminate checks retain pam_malcontent.
    username = os.environ.get("PAM_USER", "")
    if is_systemd_user_bus_bridge(username, os.environ.get("PAM_SERVICE", "")):
        return 0
    return 0 if is_confirmed_unrestricted(username) else 1


if __name__ == "__main__":
    raise SystemExit(main())
