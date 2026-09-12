"""Bounded transport for the packaged execution canary, not a policy receipt.

Systemd owns the child before exec completes. We never stop, kill, reset or
restart a unit by name: cleanup releases only our bus client's reference and
observes collection. This adapter is not yet connected to policy activation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import logging
import secrets
import threading
import time

from gi.repository import Gio, GLib

from .adapters import (
    DBUS_INTERFACE, DBUS_NAME, DBUS_PATH, PROPERTIES_INTERFACE,
    SYSTEMD_MANAGER_INTERFACE, SYSTEMD_NAME, SYSTEMD_PATH, _call,
)

PROBE = "/usr/libexec/oh-no-parent-control-execution-policy-probe"
PROBE_EXECUTED = 23
UNIT_INTERFACE = "org.freedesktop.systemd1.Unit"
SERVICE_INTERFACE = "org.freedesktop.systemd1.Service"
LOG = logging.getLogger("oh-no-parent-control.execution-probe")
CALL_MS = 1000
OBSERVE_SECONDS = 15
CLEANUP_SECONDS = 3
POLL_SECONDS = 0.05
NO_UNIT = "org.freedesktop.systemd1.NoSuchUnit"
UNIT_EXISTS = "org.freedesktop.systemd1.UnitExists"
NOT_REFERENCED = "org.freedesktop.systemd1.NotReferenced"


@dataclass(frozen=True)
class ProbeCreateReply:
    """Retained call result, never a process or reference-cleanup receipt."""

    outcome: str
    job: str = ""


class ProbeBusClient:
    """Single-use, independently owned Gio client with bounded lifecycle waits.

    The trusted caller supplies a bus address, never a shared connection. Keep
    this object until close() returns True: cancellation is a request, not proof
    of completion. Late constructor/close callbacks remain on its private main
    context and are collected by subsequent close() calls. No broker callbacks
    are dispatched here and no thread or process is spawned by this adapter.
    ExecutionProbe retains this owner until both unit and client cleanup settle.
    """

    def __init__(self):
        self._context = GLib.MainContext.new()
        self._operation = threading.Lock()
        self._started = False
        self._closing = False
        self._pending = None
        self._cancel = None
        self._connection = None
        self._create_started = False
        self._create_pending = False
        self._create_reply = None

    @property
    def create_reply(self):
        """None means no collected reply; a transport error remains uncertain."""
        return self._create_reply

    def _created(self, connection, result, _data):
        try:
            job = connection.call_finish(result).unpack()[0]
            self._create_reply = ProbeCreateReply("replied", job)
        except GLib.Error as error:
            outcome = "collision" if _error_name(error) == UNIT_EXISTS else "uncertain"
            self._create_reply = ProbeCreateReply(outcome)
            LOG.info("execution probe create reply outcome=%s", outcome)
        finally:
            self._create_pending = False

    def start_create(self, owner, unit, description):
        """Submit one fixed canary; collect its reply separately without replay.

        The caller must retain this client AND its unit-evidence coordinates.
        No timeout/cancellation discards the eventual job reply. Local polling
        stays bounded; a permanently missing reply remains an owned resource.
        """
        if not isinstance(owner, str) or not owner.startswith(":"):
            raise ValueError("probe creation requires a unique manager owner")
        if not self._operation.acquire(blocking=False):
            raise RuntimeError("execution probe client operation already running")
        try:
            if self.connection is None or self._create_started:
                raise RuntimeError("probe creation unavailable or already submitted")
            parameters = GLib.Variant("(ssa(sv)a(sa(sv)))", (
                unit, "fail", _properties(description), []))
            self._context.push_thread_default()
            try:
                self._create_started = True
                self._create_pending = True
                try:
                    self._connection.call(
                        owner, SYSTEMD_PATH, SYSTEMD_MANAGER_INTERFACE,
                        "StartTransientUnit", parameters, GLib.VariantType.new("(o)"),
                        Gio.DBusCallFlags.NONE, GLib.MAXINT, None, self._created, None)
                except (TypeError, ValueError):
                    self._create_pending = False
                    self._create_reply = ProbeCreateReply("uncertain")
                    raise
            finally:
                self._context.pop_thread_default()
        finally:
            self._operation.release()

    def poll_create(self):
        """Collect a late reply within one cleanup deadline; never cancel it."""
        if not self._operation.acquire(blocking=False):
            raise RuntimeError("execution probe client operation already running")
        try:
            self._context.push_thread_default()
            try:
                deadline = time.monotonic() + CLEANUP_SECONDS
                while self._create_pending and time.monotonic() < deadline:
                    if not self._context.iteration(False):
                        time.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))
                return self._create_reply
            finally:
                self._context.pop_thread_default()
        finally:
            self._operation.release()

    @property
    def connection(self):
        """Usable only after a successful open and before any close request."""
        if self._closing or self._pending is not None:
            return None
        return self._connection

    @property
    def cleanup_complete(self):
        return (self._closing and self._pending is None and not self._create_pending and
                (self._connection is None or self._connection.is_closed()))

    def _opened(self, _source, result, _data):
        try:
            # Retain even a success delivered after timeout/cancellation.
            self._connection = Gio.DBusConnection.new_for_address_finish(result)
            self._connection.set_exit_on_close(False)
        except GLib.Error:
            LOG.info("execution probe client open failed")
        finally:
            self._pending = None
            self._cancel = None

    def _closed(self, connection, result, _data):
        try:
            connection.close_finish(result)
        except GLib.Error:
            LOG.info("execution probe client close failed")
        finally:
            self._pending = None
            self._cancel = None

    def _start_close(self):
        self._cancel = Gio.Cancellable()
        self._pending = "close"
        try:
            self._connection.close(self._cancel, self._closed, None)
        except (TypeError, ValueError):
            self._pending = None
            self._cancel = None
            raise

    def _wait(self, deadline):
        while self._pending is not None and time.monotonic() < deadline:
            # One iteration per deadline check: even a busy context is bounded.
            if not self._context.iteration(False):
                time.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))

    def open(self, address):
        """Connect once; False requires close(), including after cancellation."""
        # This Linux system-bus client must not invoke D-Bus autolaunch or try
        # remote/fallback transports whose lifetimes we do not own.
        if not isinstance(address, str) or not address.startswith("unix:") or ";" in address:
            raise ValueError("execution probe requires one Unix bus address")
        if not self._operation.acquire(blocking=False):
            raise RuntimeError("execution probe client operation already running")
        try:
            if self._started or self._closing:
                raise RuntimeError("execution probe client is single-use")
            self._started = True
            ready = False
            self._context.push_thread_default()
            try:
                self._cancel = Gio.Cancellable()
                self._pending = "open"
                deadline = time.monotonic() + CLEANUP_SECONDS
                try:
                    Gio.DBusConnection.new_for_address(
                        address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT |
                        Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
                        None, self._cancel, self._opened, None)
                except (TypeError, ValueError):
                    self._pending = None
                    self._cancel = None
                    raise
                self._wait(deadline)
                ready = (self._pending is None and self._connection is not None
                         and not self._connection.is_closed())
                return ready
            finally:
                if not ready:
                    self._closing = True
                if self._pending is not None:
                    self._cancel.cancel()
                self._context.pop_thread_default()
        finally:
            self._operation.release()

    def close(self):
        """Bounded collection/closure; False retains ownership for recovery.

        Connection closure is not a systemd job or process-cleanup receipt.
        Never flush here: a cancelled attempt need not deliver queued messages.
        """
        if not self._operation.acquire(blocking=False):
            raise RuntimeError("execution probe client operation already running")
        try:
            if self._create_pending:
                # Disconnection would discard the reply and may release AddRef
                # before terminal evidence is copied. Keep the sender usable.
                LOG.info("execution probe client retained pending create reply")
                return False
            self._closing = True
            self._context.push_thread_default()
            try:
                deadline = time.monotonic() + CLEANUP_SECONDS
                if self._pending == "open":
                    self._cancel.cancel()
                self._wait(deadline)
                if (self._pending is None and self._connection is not None
                        and not self._connection.is_closed()
                        and time.monotonic() < deadline):
                    self._start_close()
                    self._wait(deadline)
                return self.cleanup_complete
            finally:
                if self._pending is not None:
                    self._cancel.cancel()
                self._context.pop_thread_default()
        finally:
            self._operation.release()


@dataclass(frozen=True)
class ProbeResult:
    """Safe evidence/recovery coordinates; no user data or raw D-Bus errors."""

    unit: str
    manager: str = ""
    create_outcome: str = "not-submitted"
    job: str = ""
    invocation: str = ""
    outcome: str = "transport-failed"
    service_result: str = ""
    exit_code: int = 0
    exit_status: int = 0
    terminal_observed: bool = False
    reference_released: bool = False
    client_closed: bool = False
    cleanup_complete: bool = False

    @property
    def executed(self):
        # Reserved for original-invocation evidence. Current snapshots can
        # establish only identity-unproven terminal status, never this outcome.
        return self.outcome == "executed" and self.cleanup_complete


def _error_name(error):
    return Gio.dbus_error_get_remote_error(error)


def _properties(description):
    # AddRef pins even fast failures until evidence is copied. UnrefUnit drops
    # only the sending connection's reference; CollectMode then permits GC.
    values = {
        "Description": ("s", description),
        "AddRef": ("b", True),
        "CollectMode": ("s", "inactive-or-failed"),
        "Type": ("s", "exec"),
        "Restart": ("s", "no"),
        "RemainAfterExit": ("b", False),
        "StopWhenUnneeded": ("b", False),
        "TimeoutStartUSec": ("t", 2_000_000),
        "RuntimeMaxUSec": ("t", 2_000_000),
        "TimeoutStopUSec": ("t", 2_000_000),
        "JobTimeoutUSec": ("t", 4_000_000),
        "KillMode": ("s", "control-group"),
        "SendSIGKILL": ("b", True),
        "StandardInput": ("s", "null"),
        "StandardOutput": ("s", "null"),
        "StandardError": ("s", "null"),
        "User": ("s", "0"),
        "Group": ("s", "0"),
        "ExecStart": ("a(sasb)", [(PROBE, [PROBE], False)]),
    }
    return [(name, GLib.Variant(signature, value))
            for name, (signature, value) in values.items()]


class ExecutionProbe:
    """One fixed canary over an owned sender, with a shared read-only observer.

    Retain one adapter for the lifetime of its connection. An unsettled call
    blocks another create; recover() observes that same attempt without replay.
    A timeout bounds observation, not proof that an uninterruptible task died.
    No unit-name lookup ever authorizes a process signal.
    """

    def __init__(self, connection):
        self.connection = connection
        self._operation = threading.Lock()
        self._pending = None
        self._description = ""
        self._client = None
        self._settled = True

    @property
    def pending(self):
        """Immutable recovery coordinates, retained until cleanup is proven."""
        return self._pending

    def _request(self, owner, path, interface, method, args, signature, deadline,
                 *, connection=None):
        remaining_ms = int((deadline - time.monotonic()) * 1000)
        if remaining_ms <= 0:
            raise TimeoutError("probe observation deadline")
        return _call(self.connection if connection is None else connection,
                     owner, path, interface, method, args,
                     signature, timeout=min(CALL_MS, remaining_ms)).unpack()[0]

    def _manager(self, owner, method, args, signature, deadline):
        return self._request(owner, SYSTEMD_PATH, SYSTEMD_MANAGER_INTERFACE,
                             method, args, signature, deadline)

    def _sender(self):
        connection = self._client.connection
        if connection is None:
            raise TimeoutError("probe sender unavailable")
        return connection

    def _finish_client(self, result):
        # Keep the sender available to release a late dispatch's AddRef while
        # unit settlement is uncertain. Disconnect is not a qualified substitute.
        if self._settled:
            closed = self._client.close()
            result = replace(result, client_closed=closed, cleanup_complete=closed)
            if closed:
                self._client = None
        self._pending = None if result.cleanup_complete else result
        LOG.info("execution probe cleanup unit_settled=%s client_closed=%s",
                 self._settled, result.client_closed)
        return result

    def _collect_create(self, result, *, preserve_outcome):
        """Copy one retained creation reply without settling the unit itself."""
        reply = self._client.poll_create()
        if reply is None:
            return result, True
        result = replace(result, create_outcome=reply.outcome, job=reply.job)
        if preserve_outcome:
            return result, reply.outcome != "collision"
        if reply.outcome == "collision":
            return replace(result, outcome="collision"), False
        if reply.outcome == "uncertain":
            result = replace(result, outcome="create-uncertain")
        return result, True

    def _snapshot(self, result, description, deadline):
        path = self._manager(result.manager, "GetUnit",
                             GLib.Variant("(s)", (result.unit,)), "(o)", deadline)

        def properties(interface):
            return self._request(result.manager, path, PROPERTIES_INTERFACE,
                                 "GetAll", GLib.Variant("(s)", (interface,)),
                                 "(a{sv})", deadline)

        before = properties(UNIT_INTERFACE)
        service = properties(SERVICE_INTERFACE)
        after = properties(UNIT_INTERFACE)
        # Bracket the service read; a restart invalidates the entire operation.
        keys = ("Id", "Description", "Transient")
        if any(before.get(key) != after.get(key) for key in keys):
            raise ValueError("probe identity changed during collection")
        if (after.get("Id") != result.unit or
                after.get("Description") != description or
                after.get("Transient") is not True):
            raise ValueError("probe unit replaced")
        invocation = bytes(after["InvocationID"])
        if len(invocation) != 16:
            raise ValueError("invalid probe invocation")
        invocation = invocation.hex() if any(invocation) else ""
        if result.invocation and result.invocation != invocation:
            raise ValueError("probe invocation replaced")
        previous_invocation = bytes(before["InvocationID"])
        if previous_invocation != bytes(after["InvocationID"]) and any(previous_invocation):
            raise ValueError("probe invocation changed during collection")
        result = replace(result, invocation=invocation)
        if any(before[key] != after[key] for key in ("InvocationID", "ActiveState", "Job")):
            # A normal start/exit can span these reads. Bind the identity but
            # wait for a stable terminal snapshot rather than mix observations.
            return result
        if (after["ActiveState"] not in {"inactive", "failed"} or
                after["Job"][0] != 0 or not invocation):
            return result
        if service["MainPID"] != 0 or service["ControlPID"] != 0:
            return result
        commands = service["ExecStart"]
        if (len(commands) != 1 or tuple(commands[0][:3]) != (PROBE, [PROBE], False)):
            raise ValueError("probe command changed")
        code, status = service["ExecMainCode"], service["ExecMainStatus"]
        backend_result = service["Result"]
        if backend_result not in {"success", "exit-code", "signal", "core-dump",
                                  "timeout", "resources", "protocol", "oom-kill"}:
            backend_result = "other"
        execution_observed = (code == 1 and status == PROBE_EXECUTED and
                              backend_result == "exit-code" and
                              0 < service["ExecMainStartTimestampMonotonic"] <
                              service["ExecMainExitTimestampMonotonic"])
        # The returned job is not an immutable invocation witness: systemd can
        # merge a restart and re-run the same job ID. Before our first read,
        # that can overwrite InvocationID and status without changing metadata.
        # Retain the observation for diagnostics/reference cleanup, but do not
        # certify that the originally submitted canary produced this status.
        return replace(result, terminal_observed=True, exit_code=code,
                       exit_status=status, service_result=backend_result,
                       outcome="identity-unproven" if execution_observed else "execution-failed")

    def run(self):
        if not self._operation.acquire(blocking=False):
            raise RuntimeError("execution probe operation already running")
        try:
            if self._pending is not None:
                raise RuntimeError("execution probe cleanup must be recovered")
            return self._run()
        finally:
            self._operation.release()

    def _run(self):
        token = secrets.token_hex(16)
        result = ProbeResult(unit=f"onpc-execution-probe-{token}.service")
        description = f"ONPC execution probe {token}"
        self._description = description
        submitted = False
        self._settled = True
        self._client = ProbeBusClient()
        self._pending = result
        try:
            # SYSTEM resolution uses the public Gio system-bus configuration;
            # ProbeBusClient still refuses remote/fallback/autolaunch transports.
            address = Gio.dbus_address_get_for_bus_sync(Gio.BusType.SYSTEM, None)
            if not self._client.open(address):
                raise ValueError("probe sender unavailable")
            deadline = time.monotonic() + OBSERVE_SECONDS
            bus_ids = [self._request(
                DBUS_NAME, DBUS_PATH, DBUS_INTERFACE, "GetId",
                GLib.Variant("()", ()), "(s)", deadline, connection=connection)
                for connection in (self.connection, self._client.connection)]
            if not bus_ids[0] or bus_ids[0] != bus_ids[1]:
                raise ValueError("probe observer and sender buses differ")
            owner = self._request(DBUS_NAME, DBUS_PATH, DBUS_INTERFACE,
                                  "GetNameOwner", GLib.Variant("(s)", (SYSTEMD_NAME,)),
                                  "(s)", deadline)
            if not owner.startswith(":"):
                raise ValueError("invalid manager owner")
            result = replace(result, manager=owner)
            submitted = True
            self._settled = False
            # Retain coordinates before dispatch, including interruption paths.
            result = replace(result, create_outcome="pending")
            self._pending = result
            self._client.start_create(owner, result.unit, description)

            while submitted and time.monotonic() < deadline:
                result, submitted = self._collect_create(result, preserve_outcome=False)
                self._pending = result
                if not submitted:
                    break
                try:
                    result = self._snapshot(result, description, deadline)
                except GLib.Error as error:
                    if _error_name(error) == NO_UNIT:
                        # One bounded retained-reply poll has already completed.
                        # Absence cannot settle dispatch, and recovery owns any
                        # later reply/unit without extending the initial wait.
                        break
                    else:
                        raise
                if result.terminal_observed:
                    break
                time.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))
            if submitted and not result.terminal_observed:
                if result.outcome != "create-uncertain":
                    result = replace(result, outcome="observation-timeout")
            elif submitted and result.create_outcome == "uncertain":
                result = replace(result, outcome="create-uncertain")
        except (GLib.Error, TimeoutError, ValueError, KeyError, TypeError, OverflowError):
            if result.outcome != "create-uncertain":
                result = replace(result, outcome="observation-failed" if submitted else "transport-failed")
        finally:
            self._pending = result
            if submitted:
                result = self._release(result)
                self._settled = result.cleanup_complete
            else:
                self._settled = True
            # Retain terminal/unit collection evidence before a close that may
            # be interrupted or complete only during a later recover().
            result = replace(result, cleanup_complete=False)
            self._pending = result
            result = self._finish_client(result)
        LOG.info("execution probe outcome=%s cleanup_complete=%s",
                 result.outcome, result.cleanup_complete)
        return result

    def recover(self):
        """Bounded cleanup of the retained attempt; never creates or signals.

        Absence before terminal evidence leaves the attempt pending. The caller
        must retain this adapter and retry recovery when the manager is available;
        it must not replace the adapter or its still-live bus connection.
        """
        if not self._operation.acquire(blocking=False):
            raise RuntimeError("execution probe operation already running")
        try:
            result = self._pending
            if result is None:
                return None
            # Cleanup recovery cannot retroactively acknowledge a failed call.
            outcome = "recovered-cleanup" if result.outcome == "executed" else result.outcome
            deadline = time.monotonic() + CLEANUP_SECONDS
            try:
                if result.create_outcome == "pending":
                    result, unit_may_exist = self._collect_create(
                        result, preserve_outcome=True)
                    self._pending = result
                    if not unit_may_exist:
                        self._settled = True
                while (not self._settled and not result.terminal_observed
                       and time.monotonic() < deadline):
                    try:
                        result = self._snapshot(result, self._description, deadline)
                    except GLib.Error as error:
                        if _error_name(error) != NO_UNIT:
                            raise
                    if not result.terminal_observed:
                        time.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))
            except (GLib.Error, TimeoutError, ValueError, KeyError, TypeError, OverflowError):
                pass
            finally:
                result = replace(result, outcome=outcome)
                self._pending = result
                if not self._settled:
                    result = self._release(result)
                    self._settled = result.cleanup_complete
                result = replace(result, cleanup_complete=False)
                self._pending = result
                result = self._finish_client(result)
            LOG.info("execution probe recovery outcome=%s cleanup_complete=%s",
                     result.outcome, result.cleanup_complete)
            return result
        finally:
            self._operation.release()

    def _release(self, result):
        # Keep AddRef until terminal evidence has been copied. Releasing after
        # absence can race a late create; releasing a running unit can let GC
        # discard its eventual exit before recover() observes it. Both lose the
        # evidence required to settle this attempt, even with the sender open.
        if result.create_outcome == "pending" or not result.terminal_observed:
            LOG.info(
                "execution probe reference retained create_collected=%s terminal_evidence=%s",
                result.create_outcome != "pending", result.terminal_observed)
            return result
        deadline = time.monotonic() + CLEANUP_SECONDS
        try:
            # () has no first tuple item; use the shared finite transport directly.
            try:
                _call(self._sender(), result.manager, SYSTEMD_PATH,
                      SYSTEMD_MANAGER_INTERFACE, "UnrefUnit",
                      GLib.Variant("(s)", (result.unit,)), "()", timeout=CALL_MS)
            except GLib.Error as error:
                # A lost release reply can precede collection. These replies
                # establish current reference absence, not create settlement.
                if _error_name(error) not in {NO_UNIT, NOT_REFERENCED}:
                    raise
            result = replace(result, reference_released=True)
            while time.monotonic() < deadline:
                try:
                    self._manager(result.manager, "GetUnit",
                                  GLib.Variant("(s)", (result.unit,)), "(o)", deadline)
                except GLib.Error as error:
                    if _error_name(error) == NO_UNIT:
                        # Absence after an ambiguous create alone is insufficient:
                        # its dispatch might still be pending. Require terminal evidence.
                        return replace(result, cleanup_complete=result.terminal_observed)
                    raise
                time.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))
        except (GLib.Error, TimeoutError):
            pass
        return result
