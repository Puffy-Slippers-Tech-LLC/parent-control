"""Interactive approvals cancelled until their first policy effect is admitted.

Each check runs in its broker worker's own GLib context. Authorization replies
and lifecycle signals are serialized there. After authentication, synchronous
backend work leaves lifecycle events queued in that context; admission consumes
them and rereads the original caller/session before claiming the first effect.
The broker retains its transaction lock through admission, transaction completion
and any required remote authentication cleanup.
"""

from contextlib import contextmanager

from common.oh_no_parent_control_ui.diagnostic_events import get_logger, error_code

from gi.repository import Gio, GLib

from .adapters import (
    DBUS_NAME, DBUS_PATH, DBUS_INTERFACE,
    LOGIN_NAME, LOGIN_PATH, LOGIN_MANAGER_INTERFACE, LOGIN_SESSION_INTERFACE,
    PROPERTIES_INTERFACE, _call,
)

LOG = get_logger("authorization")
LIFECYCLE_TIMEOUT_MS = 5_000
AGENT_STARTUP_GRACE_MS = 5_000
AGENT_RETRY_MS = 100
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

    @contextmanager
    def check(self, request_kind, sender, correlation_id, target_label,
              approver_username, message):
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
                "polkit.message": message,
            },
            1,  # AllowUserInteraction; no retained authorization.
            f"oh-no-parent-control-{correlation_id}",
        ))
        pending = _PendingAuthorization(
            self.connection, sender, correlation_id, parameters,
            wait_for_agent=request_kind == "kiosk",
        )
        pending.context.push_thread_default()
        try:
            pending.run()
            yield pending
        finally:
            pending.close()
            pending.context.pop_thread_default()


class _PendingAuthorization:
    def __init__(self, connection, sender, correlation_id, parameters, *, wait_for_agent=False):
        self.connection = connection
        self.sender = sender
        self.correlation_id = correlation_id
        self.parameters = parameters
        self.context = GLib.MainContext.new()
        self.loop = GLib.MainLoop.new(self.context, False)
        self.cancellable = Gio.Cancellable()
        self.subscriptions = []
        self.session_path = None
        self.user_path = None
        self.display = None
        self.admitted = False
        self.closed = False
        self.started = False
        self.auth_done = False
        self.cancel_done = False
        self.cancel_reason = None
        self.outcome = "denied"
        self.wait_for_agent = wait_for_agent
        self.agent_deadline = 0
        self.retry_source = None

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
        self.user_path = user_path
        self._subscribe(LOGIN_NAME, PROPERTIES_INTERFACE, "PropertiesChanged",
                        user_path, LOGIN_USER_INTERFACE, self._display_changed)
        self.display = self._read_display()
        session_id, path = self.display
        return path if session_id else None

    def _read_display(self):
        display, = self._read(
            LOGIN_NAME, self.user_path, PROPERTIES_INTERFACE, "Get",
            GLib.Variant("(ss)", (LOGIN_USER_INTERFACE, "Display")), "(v)",
        )
        return display

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
            self._drain_lifecycle()
            if self.cancel_reason:
                return self.outcome
            self.agent_deadline = GLib.get_monotonic_time() + AGENT_STARTUP_GRACE_MS * 1000
            self._start_check()
            self.loop.run()
            return self.outcome
        except GLib.Error as error:
            if Gio.dbus_error_get_remote_error(error) == "org.freedesktop.DBus.Error.NameHasNoOwner":
                self._cancel("caller-disconnected")
            else:
                LOG.warning(
                    "authorization.001",
                    request=self.correlation_id,
                    error_type=error_code(error),
                )
            return self.outcome

    def _drain_lifecycle(self):
        while self.context.pending():
            self.context.iteration(False)

    def admit(self):
        """Claim this checked approval once, in the worker's observed order."""
        if self.closed or self.admitted:
            return False
        self._drain_lifecycle()
        if self.outcome != "approved" or self.cancel_reason:
            return False
        try:
            alive, = self._read(DBUS_NAME, DBUS_PATH, DBUS_INTERFACE, "NameHasOwner",
                                GLib.Variant("(s)", (self.sender,)), "(b)")
            if not alive:
                self._cancel("caller-disconnected")
            if self.user_path is not None and self._read_display() != self.display:
                self._cancel("session-state-unavailable")
            if self.session_path is not None:
                reason = self._session_unavailable()
                if reason:
                    self._cancel(reason)
        except GLib.Error:
            self._cancel("session-state-unavailable")
        # A transition during a read wins even if the final snapshot is active
        # again. Cancellation is monotonic; this check never adopts a new session.
        self._drain_lifecycle()
        if self.cancel_reason:
            return False
        self.admitted = True
        return True

    def close(self):
        self.closed = True
        if self.retry_source is not None:
            self.retry_source.destroy()
            self.retry_source = None
        for subscription in self.subscriptions:
            self.connection.signal_unsubscribe(subscription)
        self.subscriptions.clear()

    def _start_check(self):
        self.started = True
        self.connection.call(
            POLKIT_NAME, POLKIT_PATH, POLKIT_INTERFACE, "CheckAuthorization",
            self.parameters, GLib.VariantType.new("((bba{ss}))"),
            Gio.DBusCallFlags.NONE, GLib.MAXINT, self.cancellable,
            self._authorization_finished,
        )

    def _retry_check(self, *_args):
        self.retry_source = None
        if self.cancel_reason:
            return GLib.SOURCE_REMOVE
        if GLib.get_monotonic_time() >= self.agent_deadline:
            self.auth_done = True
            self._finish_if_ready()
        else:
            self._start_check()
        return GLib.SOURCE_REMOVE

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

    def _display_changed(self, _connection, _sender, _path, _interface, _signal,
                         parameters):
        _interface_name, changed, invalidated = parameters.unpack()
        if "Display" in changed and changed["Display"] != self.display:
            self._cancel("session-state-unavailable")
        elif "Display" in invalidated:
            try:
                if self._read_display() != self.display:
                    self._cancel("session-state-unavailable")
            except GLib.Error:
                self._cancel("session-state-unavailable")

    def _session_removed(self, _connection, _sender, _path, _interface, _signal,
                         parameters):
        _session_id, path = parameters.unpack()
        if path == self.session_path:
            self._cancel("session-removed")

    def _cancel(self, reason):
        if self.cancel_reason or self.admitted or self.closed:
            return
        self.cancel_reason = reason
        self.outcome = "cancelled"
        LOG.info("authorization.002", request=self.correlation_id, reason=reason)
        if not self.started:
            # Between completed unfulfilled challenges there is no remote
            # authorization to cancel, but the worker loop is still running.
            if self.retry_source is not None:
                self.retry_source.destroy()
                self.retry_source = None
            self.loop.quit()
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
        self.started = False
        try:
            authorized, challenge, details = connection.call_finish(result).unpack()[0]
            if not self.cancel_reason:
                # With AllowUserInteraction, Polkit returns an unfulfilled
                # challenge when no agent is registered yet. A completed
                # authentication (including rejection) clears is_challenge.
                # The forked kiosk service can start before registration;
                # retry only this result within a short startup grace period.
                if (self.wait_for_agent and not authorized and challenge
                        and not details.get("polkit.dismissed")
                        and GLib.get_monotonic_time() < self.agent_deadline):
                    self.retry_source = GLib.timeout_source_new(AGENT_RETRY_MS)
                    self.retry_source.set_callback(self._retry_check)
                    self.retry_source.attach(self.context)
                    return
                # PolicyKit reports the agent's Cancel action in this public
                # result detail. is_challenge only means authentication could
                # still authorize the subject; it is not a dismissal result.
                self.outcome = "approved" if authorized else (
                    "cancelled" if details.get("polkit.dismissed") else "denied")
        except GLib.Error as error:
            if not self.cancel_reason:
                LOG.warning(
                    "authorization.001",
                    request=self.correlation_id,
                    error_type=error_code(error),
                )
        self.auth_done = True
        self._finish_if_ready()

    def _cancellation_finished(self, connection, result):
        self.cancel_done = True
        try:
            connection.call_finish(result)
            LOG.info("authorization.003", request=self.correlation_id)
        except GLib.Error as error:
            # Completion may have raced cancellation, or the authority may
            # have gone away. Never revive the cancelled grant or retain its
            # transaction lock; log the failed remote cleanup without PII.
            LOG.warning(
                "authorization.004",
                request=self.correlation_id,
                error_type=error_code(error),
            )
        self._finish_if_ready()

    def _finish_if_ready(self):
        if self.auth_done and (not self.cancel_reason or self.cancel_done):
            self.loop.quit()
