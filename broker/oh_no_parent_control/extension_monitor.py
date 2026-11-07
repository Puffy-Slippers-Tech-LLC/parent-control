"""Coalesced recovery hints from eligible children's public GNOME interfaces.

One private GLib loop owns every connection, timeout and reconciliation. Child
bus data is untrusted; only Broker's locked policy revalidation permits an
activation or a report. No user signal starts a new thread or subprocess.
"""

from dataclasses import dataclass, field
import threading
import time

from gi.repository import Gio, GLib

from common.oh_no_parent_control_ui.diagnostic_events import get_logger, operation_scope, record_exception
from .child_bus import connect_child_bus
from .core import Busy
from .extension_manager import ChildExtensionFailed, UUID, _load_error_fields

SHELL = "org.gnome.Shell"
PATH = "/org/gnome/Shell"
INTERFACE = "org.gnome.Shell.Extensions"
PROPERTIES = "org.freedesktop.DBus.Properties"
DBUS = "org.freedesktop.DBus"
LOG = get_logger("extension-manager")
DEBOUNCE_SECONDS = 0.1
MAX_BACKOFF_LEVEL = 7
MAX_BACKOFF_SECONDS = 30
# GNOME keeps its startup crash-protection marker for sixty seconds.
RECOVERY_GUARD_SECONDS = 60


class _ChangingState(Exception):
    pass


def _backoff_seconds(level):
    return min(MAX_BACKOFF_SECONDS, 0.5 * 2 ** max(0, min(MAX_BACKOFF_LEVEL, level) - 1))


def _record_owner(present, reason):
    try:
        LOG.info("extension-manager.monitor-owner", present=present, reason=reason)
    except Exception:
        pass  # Observation must never change recovery or admission.


def _record(watch, emit):
    try:
        if watch.diagnostics is not None:
            watch.diagnostics.append(emit)
        else:
            emit()
    except Exception:
        pass


@dataclass
class _Watch:
    uid: int
    connection: object = None
    subscriptions: list = field(default_factory=list)
    closed_handler: object = None
    source: object = None
    connecting: object = None
    shell_present: bool = False
    failures: int = 0
    next_check: float = 0
    failed: bool = False
    reported: bool = False
    report_pending: bool = False
    fault_generation: int = 0
    failure_time: float = 0
    last_recovery: float = 0
    recovery_interrupted: bool = False
    observed_state: tuple | None = None
    observed_selection: tuple | None = None
    diagnostic_decision: tuple | None = None
    hint: str = "initial"
    diagnostics: list | None = None
    probe_stage: str = "none"


class ExtensionMonitor:
    def __init__(self, broker, manager, system_connection):
        self.broker, self.manager = broker, manager
        self.system_connection = system_connection
        self.watches = {}
        # A removed watch can still own a cancelled Hello or an unreaped
        # helper. Keep those attempts alive independently until completion.
        self._attempts = {}
        self._system_signals = []
        self._refresh_source = None
        self._stopped = threading.Event()
        self._context = GLib.MainContext.new()
        self._loop = GLib.MainLoop.new(self._context, False)
        self._thread = threading.Thread(target=self._run, name="broker-extension-monitor", daemon=True)
        self._thread.start()

    def _later(self, delay, callback):
        source = GLib.timeout_source_new(max(1, int(delay * 1000)))
        source.set_callback(lambda *_args: (callback(), GLib.SOURCE_REMOVE)[1])
        source.attach(self._context)
        return source

    def _run(self):
        self._context.push_thread_default()
        try:
            for sender, interface, path in (
                    ("org.freedesktop.login1", "org.freedesktop.login1.Manager", "/org/freedesktop/login1"),
                    ("org.freedesktop.Accounts", "org.freedesktop.Accounts", "/org/freedesktop/Accounts"),
                    ("org.freedesktop.Accounts", PROPERTIES, None)):
                self._system_signals.append(self.system_connection.signal_subscribe(
                    sender, interface, None, path, None, Gio.DBusSignalFlags.NONE,
                    self._lifecycle_changed))
            self._refresh_source = self._later(0, self._refresh)
            self._loop.run()
        finally:
            if self._refresh_source is not None:
                self._refresh_source.destroy()
            for watch in self.watches.values():
                self._disconnect(watch)
            # Cancel interrupts pending Hello via its socket. Dispatch its
            # completion before dropping the context, so Gio releases its own
            # stream without a concurrent close from the monitor.
            for attempt in tuple(self._attempts):
                attempt.cancel()
            # close() bounds the caller's join, while this existing worker
            # retains the context and cleanup ownership as long as needed.
            while self._attempts:
                self._context.iteration(True)
            for identifier in self._system_signals:
                self.system_connection.signal_unsubscribe(identifier)
            self._context.pop_thread_default()

    def close(self):
        self._stopped.set()
        # A queued quit also works if close races the worker's first run().
        self._later(0, self._loop.quit)
        self._context.wakeup()
        # Existing AccountsService reads can outlive service shutdown. They
        # cannot perform later effects: the action and every command check the
        # stop event. Do not hold up broker exit on an unresponsive OS service.
        self._thread.join(timeout=8)

    def recovered(self, uid):
        """Rearm after a successful, authorized explicit recovery.

        Called while the broker still holds its recovery transaction lock,
        which also orders confirmed faults. Snapshot here; mutate only on the
        owning context, without erasing a later fault or a replacement watch.
        """
        if self._stopped.is_set():
            return
        watch = self.watches.get(uid)
        if watch is None:
            return
        generation = watch.fault_generation

        def rearm():
            if self._stopped.is_set():
                return
            if (self.watches.get(uid) is watch and
                    watch.fault_generation == generation):
                watch.failed = False
                self._schedule(watch, hint="explicit-recovery")

        self._later(0, rearm)
        self._context.wakeup()

    def _lifecycle_changed(self, *_args):
        if not self._stopped.is_set() and self._refresh_source is None:
            self._refresh_source = self._later(DEBOUNCE_SECONDS, self._refresh)

    def _refresh(self):
        self._refresh_source = None
        if self._stopped.is_set():
            return
        try:
            uids = set(self.broker.extension_watch_uids())
        except Exception as error:
            record_exception(error)
            self._refresh_source = self._later(5, self._refresh)
            return
        for uid in set(self.watches) - uids:
            self._disconnect(self.watches.pop(uid))
        for uid in uids:
            watch = self.watches.setdefault(uid, _Watch(uid))
            # A trusted lifecycle hint permits a fresh connection attempt
            # without waiting for an unavailable bus's accumulated backoff.
            if watch.connection is None:
                watch.failures = 0
            self._schedule(watch, hint="lifecycle")

    def _schedule(self, watch, delay=DEBOUNCE_SECONDS, *, hint="retry"):
        if self._stopped.is_set() or watch.source is not None:
            return
        watch.hint = hint
        delay = max(delay, watch.next_check - time.monotonic())

        def check():
            watch.source = None
            self._check(watch)

        watch.source = self._later(delay, check)

    def _retry(self, watch):
        # Cap the delay and counter, never the lifetime of eligible recovery.
        watch.failures = min(MAX_BACKOFF_LEVEL, watch.failures + 1)
        watch.next_check = time.monotonic() + _backoff_seconds(watch.failures)
        self._schedule(watch)

    def _connect(self, watch):
        if watch.connecting is not None:
            return
        if watch.uid in self._attempts.values():
            self._retry(watch)
            return
        address = self.manager.session_bus_address(watch.uid)
        if address is None:
            self._retry(watch)
            return
        account, _home = self.manager._account(watch.uid)

        def connected(connection, error):
            self._attempts.pop(attempt, None)
            if watch.connecting is not attempt:
                if connection is not None:
                    connection.close(None, None, None)
                return
            watch.connecting = None
            try:
                if error is not None:
                    raise error
                if self._stopped.is_set() or self.watches.get(watch.uid) is not watch:
                    connection.close(None, None, None)
                    return
                if address != self.manager.session_bus_address(watch.uid):
                    connection.close(None, None, None)
                    self._retry(watch)
                    return
                watch.connection = connection
                watch.closed_handler = connection.connect("closed", lambda *_args: self._bus_closed(watch))
                for interface, member, path, arg0 in (
                        (INTERFACE, "ExtensionStateChanged", PATH, UUID),
                        (PROPERTIES, "PropertiesChanged", PATH, INTERFACE)):
                    watch.subscriptions.append(connection.signal_subscribe(
                        SHELL, interface, member, path, arg0, Gio.DBusSignalFlags.NONE,
                        lambda *_args, hint=("extension-signal" if interface == INTERFACE else "properties-signal"):
                            self._signal(watch, hint, _args[5])))
                watch.subscriptions.append(connection.signal_subscribe(
                    DBUS, DBUS, "NameOwnerChanged", "/org/freedesktop/DBus", SHELL,
                    Gio.DBusSignalFlags.NONE,
                    lambda _connection, _sender, _path, _interface, _member, parameters:
                        self._shell_changed(watch, parameters)))
                watch.shell_present = self._call(watch, DBUS, "/org/freedesktop/DBus", DBUS,
                    "NameHasOwner", GLib.Variant("(s)", (SHELL,)), "(b)")[0]
                _record_owner(watch.shell_present, "connected")
                watch.failures = 0
                self._schedule(watch, hint="connected")
            except Exception as error:
                if watch.connection is not None:
                    self._disconnect(watch)
                elif connection is not None:
                    connection.close(None, None, None)
                if not self._stopped.is_set():
                    record_exception(error)
                self._retry(watch)

        attempt = connect_child_bus(account, address, self._context, connected)
        watch.connecting = attempt
        self._attempts[attempt] = watch.uid

    def _disconnect(self, watch):
        if watch.source is not None:
            watch.source.destroy()
            watch.source = None
        if watch.connecting is not None:
            attempt, watch.connecting = watch.connecting, None
            attempt.cancel()
        if watch.connection is not None:
            connection, watch.connection = watch.connection, None
            for identifier in watch.subscriptions:
                connection.signal_unsubscribe(identifier)
            watch.subscriptions.clear()
            if watch.closed_handler is not None:
                connection.disconnect(watch.closed_handler)
                watch.closed_handler = None
            connection.close(None, None, None)
        watch.shell_present = False

    def _bus_closed(self, watch):
        # The bus can disappear before delivering Shell's owner-loss signal.
        if (watch.shell_present and watch.last_recovery and
                time.monotonic() - watch.last_recovery < RECOVERY_GUARD_SECONDS):
            watch.recovery_interrupted = True
        self._disconnect(watch)
        self._retry(watch)
        _record_owner(False, "bus-closed")

    def _shell_changed(self, watch, parameters):
        if parameters.get_type_string() != "(sss)":
            return
        _name, old, new = parameters.unpack()
        if old and watch.last_recovery and time.monotonic() - watch.last_recovery < RECOVERY_GUARD_SECONDS:
            # This can be an ordinary logout. Only retain a conservative hold
            # if the next Shell also has its global crash-protection switch off;
            # owner loss never establishes an extension error to report.
            watch.recovery_interrupted = True
        watch.shell_present = bool(new)
        watch.failures = 0
        # The child controls Shell's bus name too. Owner churn must not move
        # an already pending observation/retry ahead of its rate limit.
        if new:
            self._schedule(watch, hint="owner-changed")
        _record_owner(bool(new), "owner-changed")

    @staticmethod
    def _call(watch, destination, path, interface, method, parameters, signature):
        reply = watch.connection.call_sync(destination, path, interface, method, parameters,
            GLib.VariantType.new(signature), Gio.DBusCallFlags.NO_AUTO_START, 1000, None)
        if reply.get_size() > 65536:
            raise ValueError("oversized child session reply")
        return reply.unpack()

    def _signal(self, watch, hint, parameters):
        self._schedule(watch, hint=hint)
        # Capture the public switch signal before coalesced recovery can replace
        # its value. Never retain arbitrary changed properties or sender data.
        try:
            if (hint != "properties-signal" or parameters.get_size() > 65536 or
                    parameters.get_type_string() != "(sa{sv}as)"):
                return
            interface, changed, _invalidated = parameters.unpack()
            value = changed.get("UserExtensionsEnabled")
            if interface == INTERFACE and type(value) is bool:
                LOG.info("extension-manager.switch-signal", global_enabled=value)
        except Exception:
            pass

    @staticmethod
    def _fault(watch):
        watch.fault_generation += 1
        if not watch.failed:
            if time.monotonic() - watch.failure_time >= 60:
                watch.reported = False
            watch.failure_time = time.monotonic()
        watch.failed = True
        watch.report_pending = not watch.reported

    def _report(self, watch):
        if not watch.reported:
            self.manager.report_failure(watch.uid)
            watch.reported = True
        watch.report_pending = False

    def _observe(self, watch):
        watch.probe_stage = "extension-info"
        info, = self._call(watch, SHELL, PATH, INTERFACE, "GetExtensionInfo",
                           GLib.Variant("(s)", (UUID,)), "(a{sv})")
        watch.probe_stage = "global-switch"
        enabled, = self._call(watch, SHELL, PATH, PROPERTIES, "Get",
                             GLib.Variant("(ss)", (INTERFACE, "UserExtensionsEnabled")), "(v)")
        watch.probe_stage = "validate-state"
        state = info.get("state")
        if type(enabled) is not bool or type(state) not in (int, float) or state not in {1, 2, 3, 4, 6, 7, 8}:
            raise ValueError("invalid child extension state")
        if state == 3:
            # GNOME sets ERROR before awaiting the extension's import. Only
            # its public error history distinguishes that loading sentinel
            # from a real failure, including an exception with empty text.
            watch.probe_stage = "extension-errors"
            errors, = self._call(watch, SHELL, PATH, INTERFACE, "GetExtensionErrors",
                                GLib.Variant("(s)", (UUID,)), "(as)")
            if not errors:
                raise _ChangingState()
        return info, enabled

    def _reconcile(self, watch, info, enabled):
        if self._stopped.is_set():
            return
        state = info["state"]
        now = time.monotonic()
        # GNOME's public enabled detail is the effective selection after the
        # global switch and both lists, not an attribution to a settings writer.
        value = info.get("enabled")
        selected = ("true" if value else "false") if type(value) is bool else "unknown"
        selection = (enabled, selected)
        if selection != watch.observed_selection:
            previous = watch.observed_selection
            change = ("first-observation" if previous is None else
                      "global-and-selection" if previous[0] != enabled and previous[1] != selected else
                      "global-switch" if previous[0] != enabled else "product-selection")
            _record(watch, lambda previous=previous: LOG.info("extension-manager.monitor-selection", change=change,
                previous_global=("unknown" if previous is None else "true" if previous[0] else "false"),
                global_enabled=enabled, previous_selected="unknown" if previous is None else previous[1],
                selected=selected, state=int(state)))
            watch.observed_selection = selection
        observed = (state, enabled)
        if observed != watch.observed_state:
            previous = watch.observed_state
            # Only the already validated public state number and switch survive.
            try:
                hint = watch.hint
                _record(watch, lambda: LOG.info("extension-manager.monitor-state",
                    previous_state=int(previous[0]) if previous else 0,
                    state=int(state), global_enabled=enabled, hint=hint))
            except Exception:
                pass
            watch.observed_state = observed
        if state == 3:
            fields = _load_error_fields(info)
            LOG.error("extension-manager.load-state", state=fields["state"],
                      asset=fields["asset"], reason=fields["reason"])
            self._fault(watch)
        elif state == 1 and enabled:
            watch.failed = False
        if watch.failed:
            self._decision(watch, "confirmed-failure", "report")
            self._report(watch)
            return
        self._recover(watch, info, enabled, now)
        # Reporting must not consume the command budget before renewed
        # enforcement. Keep the old error report pending even after recovery.
        if watch.report_pending:
            self._report(watch)

    def _recover(self, watch, info, enabled, now):
        if watch.recovery_interrupted:
            if not enabled:
                self._decision(watch, "interrupted-recovery", "wait")
                return
            watch.recovery_interrupted = False
        # INITIALIZED also describes an individually disabled extension that
        # Shell has never loaded. Only wait if it is still configured enabled
        # (or that public detail is unavailable), rather than disabling recovery
        # for the stable configured-disabled state.
        state = info["state"]
        if state in {7, 8} or state == 6 and enabled and info.get("enabled") is not False:
            self._decision(watch, "changing-state", "wait")
            raise _ChangingState()
        if state != 1 or not enabled:
            # Repeated disablement in a running Shell is tampering. Successful
            # restoration must not delay the next recovery; only failures retry
            # with backoff. Retain this timestamp for Shell crash protection.
            watch.last_recovery = now
            reason = "global-disabled" if not enabled else "extension-inactive"
            started = now
            self._decision(watch, reason, "started")
            try:
                self.manager.set_enabled(watch.uid, True, recover_global_switch=True)
            except ChildExtensionFailed:
                self._decision(watch, reason, "failed", started=started)
                self._fault(watch)
                self._report(watch)
                return
            except Exception:
                self._decision(watch, reason, "failed", started=started)
                raise
            self._decision(watch, reason, "accepted", started=started)
        else:
            self._decision(watch, "healthy", "unchanged")

    @staticmethod
    def _decision(watch, reason, outcome, *, delay_ms=0, started=None):
        try:
            key = (reason, outcome)
            if key == watch.diagnostic_decision:
                return
            watch.diagnostic_decision = key
            elapsed = 0 if started is None else min(2147483647, max(0, int((time.monotonic() - started) * 1000)))
            _record(watch, lambda: LOG.info("extension-manager.monitor-decision", reason=reason,
                outcome=outcome, delay_ms=delay_ms, elapsed_ms=elapsed))
        except Exception:
            pass

    @operation_scope
    def _check(self, watch):
        if self._stopped.is_set() or self.watches.get(watch.uid) is not watch:
            return
        # Emit new observations after policy/command-budget scopes and retry
        # scheduling finish. Slow diagnostic storage cannot change those decisions.
        watch.diagnostics = []
        watch.probe_stage = "none"
        try:
            if watch.connection is None:
                self._connect(watch)
                return
            if not watch.shell_present:
                return
            # At most two probes per second even under a user signal flood.
            watch.next_check = time.monotonic() + 0.5
            revision = self.broker.extension_reconciliation_revision()
            if self.broker.extension_reconciliation_busy():
                raise Busy("another request is already in progress")
            # User-controlled reply latency never holds the policy lock.
            # These observations authorize nothing; the locked callback below
            # reloads the current account/roles/preferences before any effect.
            info, user_extensions_enabled = self._observe(watch)
            watch.probe_stage = "none"
            with self.manager.command_budget(3, self._stopped):
                enabled = self.broker.reconcile_enabled_child(watch.uid,
                    lambda: self._reconcile(watch, info, user_extensions_enabled),
                    expected_revision=revision)
            if not enabled:
                self._decision(watch, "policy-ineligible", "unchanged")
                watch.failed = watch.reported = watch.report_pending = False
                watch.last_recovery = 0
                watch.recovery_interrupted = False
            watch.failures = 0
        except _ChangingState:
            self._decision(watch, "changing-state", "wait")
            self._retry(watch)
        except Busy:
            self._decision(watch, "broker-busy", "wait", delay_ms=500)
            # Polkit can hold the transaction lock indefinitely. A failed
            # try-lock performs no account/session probes and must remain
            # pending until that transaction completes.
            watch.next_check = time.monotonic() + 0.5
            self._schedule(watch)
        except Exception as error:
            stage = watch.probe_stage
            if stage != "none":
                _record(watch, lambda: LOG.warning("extension-manager.probe-failed", stage=stage))
            LOG.warning("extension-manager.load-observation", outcome="unavailable")
            record_exception(error)
            self._retry(watch)
        finally:
            pending, watch.diagnostics = watch.diagnostics, None
            for emit in pending:
                _record(watch, emit)
