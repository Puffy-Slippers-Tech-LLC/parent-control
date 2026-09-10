"""GIO adapters for Polkit, AccountsService, and caller identity."""

from __future__ import annotations

import json
import logging
import os
import pwd
import re
import subprocess
import tempfile
import threading

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

from .core import UserAccount

DBUS_NAME = "org.freedesktop.DBus"
DBUS_PATH = "/org/freedesktop/DBus"
DBUS_INTERFACE = "org.freedesktop.DBus"
ACCOUNTS_NAME = "org.freedesktop.Accounts"
ACCOUNTS_PATH = "/org/freedesktop/Accounts"
ACCOUNTS_INTERFACE = "org.freedesktop.Accounts"
NONINTERACTIVE_SHELLS = frozenset({"", "/bin/false", "/usr/bin/false",
                                  "/sbin/nologin", "/usr/sbin/nologin"})
PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
SESSION_LIMITS_INTERFACE = "com.endlessm.ParentalControls.SessionLimits"
APP_FILTER_INTERFACE = "com.endlessm.ParentalControls.AppFilter"
TIMER_NAME = "org.freedesktop.MalcontentTimer1"
TIMER_PATH = "/org/freedesktop/MalcontentTimer1"
TIMER_PARENT_INTERFACE = "org.freedesktop.MalcontentTimer1.Parent"
LOGIN_NAME = "org.freedesktop.login1"
LOGIN_PATH = "/org/freedesktop/login1"
LOGIN_MANAGER_INTERFACE = "org.freedesktop.login1.Manager"
LOGIN_SESSION_INTERFACE = "org.freedesktop.login1.Session"
SYSTEMD_NAME = "org.freedesktop.systemd1"
SYSTEMD_PATH = "/org/freedesktop/systemd1"
SYSTEMD_MANAGER_INTERFACE = "org.freedesktop.systemd1.Manager"
SESSION_SCOPE_ID = re.compile(r"^[A-Za-z0-9]+$")
RUNTIME_MAX_USEC_INFINITY = (1 << 64) - 1
CALL_TIMEOUT_MS = 30_000
USAGE_HELPER = "/usr/libexec/oh-no-parent-control-query-usage"
MAX_USAGE_HELPER_OUTPUT_BYTES = 8 * 1024 * 1024
LOG = logging.getLogger("oh-no-parent-control.adapters")


class TimerUsageError(RuntimeError):
    """A redacted failure from the identity-scoped usage query helper."""

    def __init__(self, category: str):
        super().__init__(f"timer usage query failed ({category})")
        self.category = category


def _accounts_icon_file(value) -> str:
    if not isinstance(value, str) or not value.startswith("/") or "\0" in value:
        return ""
    return value


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
        except GLib.Error as error:
            LOG.warning("caller liveness check outcome=failed error_type=%s", type(error).__name__)
            return False


class AccountsService:
    def __init__(self, connection, execution_policy=None, preferences=None):
        self.connection = connection
        self._execution_policy = execution_policy
        self._preferences = preferences
        self._execution_policy_lock = threading.RLock()

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
            is_locked=properties.get("Locked", True),
            icon_file=_accounts_icon_file(properties.get("IconFile", "")),
            is_interactive=properties.get("Shell", "") not in NONINTERACTIVE_SHELLS,
        )

    def list_users(self) -> tuple[UserAccount, ...]:
        # ListCachedUsers is explicitly non-exhaustive. Enumerate current NSS
        # identities so a newly created local account appears before first
        # login, then use AccountsService as the authority for account type.
        uids = sorted({entry.pw_uid for entry in pwd.getpwall()
                       if 1000 <= entry.pw_uid <= (1 << 32) - 1 and
                       getattr(entry, "pw_shell", "") not in NONINTERACTIVE_SHELLS})
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

    def clear_session_runtime_max(self, uid: int) -> tuple[str, ...]:
        """Remove pam_malcontent's systemd kill timer from this user's logins.

        In-session expiry is a screen lock. A later login is still denied by
        PAM when remaining time is zero. Clearing RuntimeMaxUSec prevents a
        login-time snapshot from tearing down a live session after a grant.
        """
        if type(uid) is not int or not 0 < uid <= (1 << 32) - 1:
            return ()
        try:
            reply = _call(
                self.connection, LOGIN_NAME, LOGIN_PATH, LOGIN_MANAGER_INTERFACE,
                "ListSessions", None, "a(susso)",
            )
        except GLib.Error:
            return ()
        cleared = []
        for session_id, session_uid, _user, _seat, path in reply.unpack()[0]:
            if session_uid != uid or not SESSION_SCOPE_ID.fullmatch(session_id):
                continue
            try:
                properties = _call(
                    self.connection, LOGIN_NAME, path, PROPERTIES_INTERFACE,
                    "GetAll", GLib.Variant("(s)", (LOGIN_SESSION_INTERFACE,)),
                    "(a{sv})",
                ).unpack()[0]
            except GLib.Error:
                continue
            service = properties.get("Service")
            if (properties.get("Class") != "user" or
                    properties.get("Type") not in {"wayland", "x11"} or
                    not isinstance(service, str) or not service.startswith("gdm-")):
                continue
            unit = f"session-{session_id}.scope"
            try:
                _call(
                    self.connection, SYSTEMD_NAME, SYSTEMD_PATH,
                    SYSTEMD_MANAGER_INTERFACE, "SetUnitProperties",
                    GLib.Variant("(sba(sv))", (
                        unit, True,
                        [("RuntimeMaxUSec", GLib.Variant("t", RUNTIME_MAX_USEC_INFINITY))],
                    )),
                    "()",
                )
            except GLib.Error:
                continue
            cleared.append(unit)
        return tuple(cleared)

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
        self.sync_execution_policy()

    def sync_execution_policy(self) -> None:
        """Make native execution rules match every current app blocklist."""
        if self._execution_policy is None:
            return
        with self._execution_policy_lock:
            LOG.info("execution-policy sync stage=collect-filters")
            filters = {}
            patterns = {}
            for user in self.list_users():
                allowlist, targets = self.get_filter(user.uid)
                filters[user.uid] = () if allowlist else targets
                if self._preferences is None or allowlist:
                    continue
                try:
                    preferences = self._preferences.load(user.uid)
                    active = []
                    live = set(targets)
                    for entry in preferences["apps"].values():
                        if entry["state"] == "permanent" or (
                                entry["state"] == "conditional" and
                                any(target in live for target in entry["targets"])):
                            active.extend(entry["patterns"])
                    patterns[user.uid] = tuple(sorted(set(active)))
                except Exception as error:
                    raise RuntimeError("could not load wildcard policy") from error
            LOG.info("execution-policy sync stage=reconcile account_count=%d pattern_account_count=%d",
                     len(filters), len(patterns))
            if patterns:
                self._execution_policy.reconcile(filters, patterns)
            else:
                self._execution_policy.reconcile(filters)

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
        # The broker has authorized the target before reaching this adapter.
        # Malcontent rejects root, but permits an account to query its own
        # records. Open the helper's fresh bus connection as that exact child.
        LOG.info("usage query scope=own stage=identity")
        try:
            identity = pwd.getpwuid(uid)
        except KeyError as error:
            raise TimerUsageError("child-unavailable") from error
        return self._query_usage_with_identity(uid, uid, identity.pw_gid)

    def query_usage_as(
            self, uid: int,
            approver: UserAccount) -> tuple[tuple[int, int], ...]:
        """Query through a new bus connection owned by the authenticated approver."""
        LOG.info("usage query scope=approver stage=identity")
        try:
            identity = pwd.getpwuid(approver.uid)
        except KeyError as error:
            raise TimerUsageError("approver-unavailable") from error
        if identity.pw_name != approver.username:
            raise TimerUsageError("approver-identity-changed")
        return self._query_usage_with_identity(uid, approver.uid, identity.pw_gid)

    def _query_usage_with_identity(
            self, uid: int, reader_uid: int,
            reader_gid: int) -> tuple[tuple[int, int], ...]:
        LOG.info("usage helper stage=launch")
        try:
            with tempfile.TemporaryFile() as output:
                result = subprocess.run(
                    [USAGE_HELPER, str(uid)],
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.DEVNULL,
                    timeout=CALL_TIMEOUT_MS / 1000,
                    check=False,
                    shell=False,
                    close_fds=True,
                    cwd="/",
                    env={"LANG": "C.UTF-8"},
                    user=reader_uid,
                    group=reader_gid,
                    extra_groups=(),
                    umask=0o077,
                )
                if result.returncode != 0:
                    category = {
                        64: "invalid-request",
                        69: "backend-unavailable",
                        70: "invalid-backend-reply",
                    }.get(result.returncode, "helper-failed")
                    LOG.warning("usage helper outcome=failed category=%s returncode=%d",
                                category, result.returncode)
                    raise TimerUsageError(category)
                output.flush()
                if os.fstat(output.fileno()).st_size > MAX_USAGE_HELPER_OUTPUT_BYTES:
                    raise TimerUsageError("reply-too-large")
                output.seek(0)
                encoded = output.read(MAX_USAGE_HELPER_OUTPUT_BYTES + 1)
        except subprocess.TimeoutExpired as error:
            LOG.warning("usage helper outcome=timeout")
            raise TimerUsageError("timeout") from error
        except OSError as error:
            LOG.warning("usage helper outcome=unavailable error_type=%s", type(error).__name__)
            raise TimerUsageError("helper-unavailable") from error

        try:
            raw = json.loads(encoded.decode("utf-8", errors="strict"))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise TimerUsageError("invalid-helper-reply") from error
        if not isinstance(raw, list):
            raise TimerUsageError("invalid-helper-reply")

        intervals = []
        for interval in raw:
            if (not isinstance(interval, list) or len(interval) != 2 or
                    any(type(value) is not int or not 0 <= value <= (1 << 64) - 1
                        for value in interval)):
                raise TimerUsageError("invalid-helper-reply")
            intervals.append(tuple(interval))
        LOG.info("usage helper outcome=accepted interval_count=%d", len(intervals))
        return tuple(intervals)
