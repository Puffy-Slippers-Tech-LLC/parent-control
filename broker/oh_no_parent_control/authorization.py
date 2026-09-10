"""Interactive Polkit checks cancelled when their requesting session goes away.

Each check runs in its broker worker's own GLib context. Authorization replies
and lifecycle signals are serialized there; no thread can approve a check after
that context has marked it cancelled. The broker retains its transaction lock
until this adapter has finished local cancellation and attempted remote cleanup.
"""

import logging

from gi.repository import Gio, GLib

from .adapters import (
    DBUS_NAME, DBUS_PATH, DBUS_INTERFACE,
    LOGIN_NAME, LOGIN_PATH, LOGIN_MANAGER_INTERFACE, LOGIN_SESSION_INTERFACE,
    PROPERTIES_INTERFACE, _call,
)

LOG = logging.getLogger("oh-no-parent-control.authorization")
LIFECYCLE_TIMEOUT_MS = 5_000
LOGIN_USER_INTERFACE = "org.freedesktop.login1.User"
POLKIT_NAME = "org.freedesktop.PolicyKit1"
POLKIT_PATH = "/org/freedesktop/PolicyKit1/Authority"
POLKIT_INTERFACE = "org.freedesktop.PolicyKit1.Authority"
REQUEST_ACTION_IDS = {
    "child": "tech.puffyslippers.com.ohnoparentcontrol.child.request-own-access",
    "kiosk": "tech.puffyslippers.com.ohnoparentcontrol.kiosk.request-access",
}


class PolkitAuthorizer:
    def __init__(self, connection):
        self.connection = connection

    def check(self, request_kind, sender, correlation_id, target_label,
              approver_username, requested_duration, allow_soft_blocked_apps):
        try:
            action_id = REQUEST_ACTION_IDS[request_kind]
        except KeyError as error:
            raise ValueError("invalid authorization request kind") from error
        parameters = GLib.Variant("((sa{sv})sa{ss}us)", (
            ("system-bus-name", {"name": GLib.Variant("s", sender)}),
            action_id,
            {
                "target-account": target_label,
                "approver-user": approver_username,
                "requested-duration": requested_duration,
                "soft-blocked-apps": (
                    " and allow soft blocked apps" if allow_soft_blocked_apps else ""
                ),
            },
            1,  # AllowUserInteraction; no retained authorization.
            f"oh-no-parent-control-{correlation_id}",
        ))
        return _PendingAuthorization(
            self.connection, sender, correlation_id, parameters,
        ).run()


class _PendingAuthorization:
    def __init__(self, connection, sender, correlation_id, parameters):
        self.connection = connection
        self.sender = sender
        self.correlation_id = correlation_id
        self.parameters = parameters
        self.context = GLib.MainContext.new()
        self.loop = GLib.MainLoop.new(self.context, False)
        self.cancellable = Gio.Cancellable()
        self.subscriptions = []
        self.session_path = None
        self.started = False
        self.auth_done = False
        self.cancel_done = False
        self.cancel_reason = None
        self.outcome = "denied"

    def _read(self, name, path, interface, method, parameters, signature):
        return _call(self.connection, name, path, interface, method, parameters,
                     signature, LIFECYCLE_TIMEOUT_MS).unpack()

    def _subscribe(self, name, interface, signal, path, arg0, callback):
        self.subscriptions.append(self.connection.signal_subscribe(
            name, interface, signal, path, arg0, Gio.DBusSignalFlags.NONE, callback,
        ))

    def _session_for_caller(self):
        pid, = self._read(DBUS_NAME, DBUS_PATH, DBUS_INTERFACE,
                          "GetConnectionUnixProcessID",
                          GLib.Variant("(s)", (self.sender,)), "(u)")
        try:
            path, = self._read(LOGIN_NAME, LOGIN_PATH, LOGIN_MANAGER_INTERFACE,
                               "GetSessionByPID", GLib.Variant("(u)", (pid,)), "(o)")
            return path
        except GLib.Error as error:
            if Gio.dbus_error_get_remote_error(error) != (
                    "org.freedesktop.login1.NoSessionForPID"):
                raise

        # GNOME and kiosk apps may be user services outside a session scope.
        # Match Polkit's documented systemd session resolution: the process's
        # owning user manager supplies its primary graphical Display session.
        # Do not select another arbitrary session by UID or scan processes.
        try:
            user_path, = self._read(
                LOGIN_NAME, LOGIN_PATH, LOGIN_MANAGER_INTERFACE,
                "GetUserByPID", GLib.Variant("(u)", (pid,)), "(o)",
            )
        except GLib.Error as error:
            if Gio.dbus_error_get_remote_error(error) == (
                    "org.freedesktop.login1.NoUserForPID"):
                return None  # Sessionless callers can use a bus-registered agent.
            raise
        display, = self._read(
            LOGIN_NAME, user_path, PROPERTIES_INTERFACE, "Get",
            GLib.Variant("(ss)", (LOGIN_USER_INTERFACE, "Display")), "(v)",
        )
        session_id, path = display
        return path if session_id else None

    def _session_unavailable(self):
        properties, = self._read(
            LOGIN_NAME, self.session_path, PROPERTIES_INTERFACE, "GetAll",
            GLib.Variant("(s)", (LOGIN_SESSION_INTERFACE,)), "(a{sv})",
        )
        # Missing or malformed lifecycle state must not leave an unobservable
        # authorization holding the transaction lock.
        if (type(properties.get("LockedHint")) is not bool or
                type(properties.get("Active")) is not bool or
                properties.get("State") not in {"opening", "online", "active", "closing"}):
            return "session-state-unavailable"
        return self._unavailable_reason(properties)

    @staticmethod
    def _unavailable_reason(properties):
        if properties.get("LockedHint") is True:
            return "session-locked"
        if properties.get("Active") is False:
            return "session-inactive"
        if properties.get("State") == "closing":
            return "session-closing"
        return None

    def run(self):
        self.context.push_thread_default()
        try:
            self._subscribe(DBUS_NAME, DBUS_INTERFACE, "NameOwnerChanged",
                            DBUS_PATH, self.sender, self._owner_changed)
            self._subscribe(DBUS_NAME, DBUS_INTERFACE, "NameOwnerChanged",
                            DBUS_PATH, LOGIN_NAME, self._owner_changed)
            self.session_path = self._session_for_caller()
            if self.session_path is not None:
                self._subscribe(LOGIN_NAME, PROPERTIES_INTERFACE, "PropertiesChanged",
                                self.session_path, LOGIN_SESSION_INTERFACE,
                                self._session_changed)
                self._subscribe(LOGIN_NAME, LOGIN_SESSION_INTERFACE, "Lock",
                                self.session_path, None, self._session_lock)
                self._subscribe(LOGIN_NAME, LOGIN_MANAGER_INTERFACE, "SessionRemoved",
                                LOGIN_PATH, None, self._session_removed)
                # Subscribe before reading, so a lock between discovery and
                # the initial snapshot cannot be missed.
                try:
                    reason = self._session_unavailable()
                except GLib.Error:
                    reason = "session-state-unavailable"
                if reason:
                    self._cancel(reason)
                    return self.outcome
            # Dispatch any lifecycle events queued during the initial reads
            # before launching a password prompt.
            while self.context.pending():
                self.context.iteration(False)
            if self.cancel_reason:
                return self.outcome
            self.started = True
            self.connection.call(
                POLKIT_NAME, POLKIT_PATH, POLKIT_INTERFACE, "CheckAuthorization",
                self.parameters, GLib.VariantType.new("((bba{ss}))"),
                Gio.DBusCallFlags.NONE, GLib.MAXINT, self.cancellable,
                self._authorization_finished,
            )
            self.loop.run()
            return self.outcome
        except GLib.Error as error:
            if Gio.dbus_error_get_remote_error(error) == "org.freedesktop.DBus.Error.NameHasNoOwner":
                self._cancel("caller-disconnected")
            else:
                LOG.warning("request=%s authorization outcome=backend-failed error_type=%s",
                            self.correlation_id, type(error).__name__)
            return self.outcome
        finally:
            for subscription in self.subscriptions:
                self.connection.signal_unsubscribe(subscription)
            self.context.pop_thread_default()

    def _owner_changed(self, _connection, _sender, _path, _interface, _signal,
                       parameters):
        name, old_owner, new_owner = parameters.unpack()
        if old_owner and old_owner != new_owner:
            self._cancel("caller-disconnected" if name == self.sender
                         else "session-monitor-unavailable")

    def _session_changed(self, _connection, _sender, _path, _interface, _signal,
                         parameters):
        _interface_name, changed, invalidated = parameters.unpack()
        reason = self._unavailable_reason(changed)
        if not reason and {"LockedHint", "Active", "State"}.intersection(invalidated):
            try:
                reason = self._session_unavailable()
            except GLib.Error:
                reason = "session-state-unavailable"
        if reason:
            self._cancel(reason)

    def _session_lock(self, *_args):
        self._cancel("session-locked")

    def _session_removed(self, _connection, _sender, _path, _interface, _signal,
                         parameters):
        _session_id, path = parameters.unpack()
        if path == self.session_path:
            self._cancel("session-removed")

    def _cancel(self, reason):
        if self.cancel_reason or self.auth_done:
            return
        self.cancel_reason = reason
        self.outcome = "cancelled"
        LOG.info("request=%s authorization outcome=cancelled reason=%s silent=True",
                 self.correlation_id, reason)
        if not self.started:
            return
        # Use the SAME connection and cancellation ID as CheckAuthorization.
        # GIO cancellation alone only abandons our local wait, leaving Polkit's
        # prompt alive. Queue remote cancellation first, then finish locally.
        self.connection.call(
            POLKIT_NAME, POLKIT_PATH, POLKIT_INTERFACE, "CancelCheckAuthorization",
            GLib.Variant("(s)", (f"oh-no-parent-control-{self.correlation_id}",)),
            GLib.VariantType.new("()"), Gio.DBusCallFlags.NONE,
            LIFECYCLE_TIMEOUT_MS, None, self._cancellation_finished,
        )
        self.cancellable.cancel()

    def _authorization_finished(self, connection, result):
        self.auth_done = True
        try:
            authorized, challenge, _details = connection.call_finish(result).unpack()[0]
            if not self.cancel_reason:
                self.outcome = "approved" if authorized else (
                    "cancelled" if challenge else "denied")
        except GLib.Error as error:
            if not self.cancel_reason:
                LOG.warning("request=%s authorization outcome=backend-failed error_type=%s",
                            self.correlation_id, type(error).__name__)
        self._finish_if_ready()

    def _cancellation_finished(self, connection, result):
        self.cancel_done = True
        try:
            connection.call_finish(result)
            LOG.info("request=%s authorization cancel-check outcome=accepted",
                     self.correlation_id)
        except GLib.Error as error:
            # Completion may have raced cancellation, or the authority may
            # have gone away. Never revive the cancelled grant or retain its
            # transaction lock; log the failed remote cleanup without PII.
            LOG.warning("request=%s authorization cancel-check outcome=failed error_type=%s",
                        self.correlation_id, type(error).__name__)
        self._finish_if_ready()

    def _finish_if_ready(self):
        if self.auth_done and (not self.cancel_reason or self.cancel_done):
            self.loop.quit()
