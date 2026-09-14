"""Bounded transport for the packaged execution canary, not a policy receipt.

Systemd owns the child before exec completes. We never stop, kill, reset or
restart a unit by name: cleanup releases only our bus client's reference and
observes collection. This adapter is not yet connected to policy activation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from common.oh_no_parent_control_ui.diagnostic_events import get_logger, error_code
import secrets
import re
import threading
import time

from gi.repository import Gio, GLib

from .adapters import (
    DBUS_INTERFACE, DBUS_NAME, DBUS_PATH, PROPERTIES_INTERFACE,
    SYSTEMD_MANAGER_INTERFACE, SYSTEMD_NAME, SYSTEMD_PATH, _call,
)
from .probe_channel import AdmissionBinding, PeerHello, ProbeChannel, ChannelRefused, TIMEOUT
from .probe_generation import ProbeGeneration, GenerationIdentity, GenerationRefused

PROBE = "/usr/libexec/oh-no-parent-control-execution-policy-probe"
PROBE_GATE = "/usr/libexec/oh-no-parent-control-execution-probe-gate"
PROBE_EXECUTED = 23
UNIT_INTERFACE = "org.freedesktop.systemd1.Unit"
SERVICE_INTERFACE = "org.freedesktop.systemd1.Service"
LOG = get_logger("execution-probe")
CALL_MS = 1000
OBSERVE_SECONDS = 15
CLEANUP_SECONDS = 3
POLL_SECONDS = 0.05
NO_UNIT = "org.freedesktop.systemd1.NoSuchUnit"
UNIT_EXISTS = "org.freedesktop.systemd1.UnitExists"
NOT_REFERENCED = "org.freedesktop.systemd1.NotReferenced"
CREATE_ERROR_NAMES = frozenset({
    UNIT_EXISTS,
    "org.freedesktop.DBus.Error.AccessDenied",
    "org.freedesktop.DBus.Error.AuthFailed",
    "org.freedesktop.DBus.Error.InteractiveAuthorizationRequired",
    "org.freedesktop.DBus.Error.InvalidArgs",
    "org.freedesktop.DBus.Error.UnknownProperty",
    "org.freedesktop.DBus.Error.PropertyReadOnly",
    "org.freedesktop.DBus.Error.UnknownMethod",
    "org.freedesktop.DBus.Error.NoReply",
    "org.freedesktop.DBus.Error.Disconnected",
    "org.freedesktop.DBus.Error.Timeout",
    "org.freedesktop.DBus.Error.LimitsExceeded",
})


@dataclass(frozen=True)
class ProbeCreateReply:
    """Retained call result, never a process or reference-cleanup receipt."""

    outcome: str
    job: str = ""
    error_name: str = ""


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
            name = _error_name(error)
            outcome = "collision" if name == UNIT_EXISTS else "uncertain"
            # A name helps diagnose installed API/authorization failures, but
            # arbitrary remote names and messages can contain private data.
            # This is diagnostic only: even a known error cannot settle create.
            self._create_reply = ProbeCreateReply(
                outcome, error_name=name if name in CREATE_ERROR_NAMES else "other")
            LOG.info("execution-probe.001", outcome=outcome)
        finally:
            self._create_pending = False

    def start_create(self, owner, unit, description, *, token=None):
        """Submit the fixed canary or token-bound gate, without replay.

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
                unit, "fail", _properties(description, token=token), []))
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

    def poll_create(self, *, deadline=None):
        """Collect within the caller's deadline or cleanup budget; never cancel."""
        if not self._operation.acquire(blocking=False):
            raise RuntimeError("execution probe client operation already running")
        try:
            self._context.push_thread_default()
            try:
                deadline = (time.monotonic() + CLEANUP_SECONDS if deadline is None
                            else min(deadline, time.monotonic() + CLEANUP_SECONDS))
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
            LOG.info("execution-probe.002")
        finally:
            self._pending = None
            self._cancel = None

    def _closed(self, connection, result, _data):
        try:
            connection.close_finish(result)
        except GLib.Error:
            LOG.info("execution-probe.003")
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
                LOG.info("execution-probe.004")
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
    create_error_name: str = ""
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
    generation: GenerationIdentity | None = None
    admission: AdmissionBinding | None = None
    channel_result: str = ""
    native_verified: bool = False
    job_timeout_usec: int = 0

    @property
    def executed(self):
        # Reserved for original-invocation evidence. Current snapshots can
        # establish only identity-unproven terminal status, never this outcome.
        return self.outcome == "executed" and self.cleanup_complete


def _error_name(error):
    return Gio.dbus_error_get_remote_error(error)


def _properties(description, *, token=None):
    # AddRef pins even fast failures until evidence is copied. UnrefUnit drops
    # only the sending connection's reference; CollectMode then permits GC.
    if token is not None and (not isinstance(token, str) or
            re.fullmatch(r"[0-9a-f]{32}", token) is None or token == "0" * 32):
        raise ValueError("invalid probe generation token")
    command = (PROBE, [PROBE], False) if token is None else (PROBE_GATE, [PROBE_GATE, token], False)
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
        # The packaged prefix drop-in supplies JobTimeoutSec=4s. The systemd
        # 259 transient D-Bus setter falls through to PropertyReadOnly.
        # Read back the effective value before admission and at collection.
        "KillMode": ("s", "control-group"),
        "SendSIGKILL": ("b", True),
        "StandardInput": ("s", "null"),
        "StandardOutput": ("s", "null"),
        "StandardError": ("s", "null"),
        "User": ("s", "0"),
        "Group": ("s", "0"),
        "ExecStart": ("a(sasb)", [command]),
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
        self._generation = None
        self._channel = None

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
        if self._channel is not None and self._channel.result is not None:
            # collect() can be interrupted after retaining a valid frame but
            # before returning it. Preserve that observation without promotion.
            result = replace(result, channel_result=self._channel.result)
            self._pending = result
        # Closing the sole endpoint aborts any unadmitted gate. Never reopen it
        # in recovery. Its filesystem cleanup can fail independently of the unit.
        if self._channel is not None and self._channel.close():
            self._channel = None
        # Keep the sender available to release a late dispatch's AddRef while
        # unit settlement is uncertain. Disconnect is not a qualified substitute.
        if self._settled and self._client is not None:
            closed = self._client.close()
            result = replace(result, client_closed=closed)
            self._pending = result
            if closed:
                self._client = None
        settled = self._settled and result.client_closed and self._channel is None
        if settled and self._generation is not None:
            if self._generation.close(settled=True):
                self._generation = None
        result = replace(result, cleanup_complete=settled and self._generation is None)
        self._pending = None if result.cleanup_complete else result
        LOG.info(
            "execution-probe.005",
            unit_settled=self._settled,
            client_closed=result.client_closed,
        )
        return result

    def _collect_create(self, result, *, preserve_outcome, deadline=None):
        """Copy one retained creation reply without settling the unit itself."""
        reply = (self._client.poll_create() if deadline is None else
                 self._client.poll_create(deadline=deadline))
        if reply is None:
            return result, True
        result = replace(result, create_outcome=reply.outcome, job=reply.job,
                         create_error_name=reply.error_name)
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
        timeout = after.get("JobTimeoutUSec", 0)
        timeout_verified = (before.get("JobTimeoutUSec") == timeout == 4_000_000)
        result = replace(result, invocation=invocation, job_timeout_usec=timeout)
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
        expected = ((PROBE, [PROBE], False) if result.generation is None else
                    (PROBE_GATE, [PROBE_GATE, result.generation.token], False))
        if (len(commands) != 1 or tuple(commands[0][:3]) != expected):
            raise ValueError("probe command changed")
        code, status = service["ExecMainCode"], service["ExecMainStatus"]
        backend_result = service["Result"]
        if backend_result not in {"success", "exit-code", "signal", "core-dump",
                                  "timeout", "resources", "protocol", "oom-kill"}:
            backend_result = "other"
        execution_observed = (timeout_verified and code == 1 and status == PROBE_EXECUTED and
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

    def _admission_binding(self, result, token, peer, deadline):
        """Authenticate a selected waiting gate; never send or settle anything.

        The native generation run path calls this while holding _operation,
        after retaining the create reply and selecting exactly one channel peer.
        It must pin the immutable generation, retain the returned binding BEFORE
        admit(), and compare terminal evidence with it. This read-only boundary
        alone cannot enable positive results on the existing fixed-canary path.
        """
        if (not isinstance(token, str) or re.fullmatch(r"[0-9a-f]{32}", token) is None
                or token == "0" * 32):
            raise ValueError("invalid probe generation token")
        if (self._pending != result or self._client is None or
                self._client.connection is None or
                self._client.create_reply != ProbeCreateReply("replied", result.job) or
                result.create_outcome != "replied" or
                re.fullmatch(r"/org/freedesktop/systemd1/job/[1-9][0-9]*", result.job) is None or
                not result.manager.startswith(":") or
                result.unit != f"onpc-execution-probe-{token}.service" or
                self._description != f"ONPC execution probe {token}" or
                result.terminal_observed or result.reference_released):
            raise ValueError("probe creation identity unavailable")
        if (not isinstance(peer, PeerHello) or type(peer.pid) is not int or
                not 0 < peer.pid <= 0xFFFFFFFF or peer.uid != 0 or peer.gid != 0 or
                not isinstance(peer.invocation, str) or
                re.fullmatch(r"[0-9a-f]{32}", peer.invocation) is None or
                peer.invocation == "0" * 32 or
                (result.invocation and result.invocation != peer.invocation)):
            raise ValueError("probe peer identity unavailable")

        def manager_unchanged():
            owner = self._request(
                DBUS_NAME, DBUS_PATH, DBUS_INTERFACE, "GetNameOwner",
                GLib.Variant("(s)", (SYSTEMD_NAME,)), "(s)", deadline)
            if owner != result.manager:
                raise ValueError("probe manager replaced")

        manager_unchanged()
        path = self._manager(result.manager, "GetUnit",
                             GLib.Variant("(s)", (result.unit,)), "(o)", deadline)

        def properties(interface):
            return self._request(result.manager, path, PROPERTIES_INTERFACE,
                                 "GetAll", GLib.Variant("(s)", (interface,)),
                                 "(a{sv})", deadline)

        # The peer owns the endpoint across exec. These snapshots authenticate
        # its waiting invocation, not the historical first invocation of a job.
        # Re-reading both interfaces also rejects observed PID/command changes.
        before_unit = properties(UNIT_INTERFACE)
        before_service = properties(SERVICE_INTERFACE)
        peer_path = self._manager(result.manager, "GetUnitByPID",
                                  GLib.Variant("(u)", (peer.pid,)), "(o)", deadline)
        service = properties(SERVICE_INTERFACE)
        unit = properties(UNIT_INTERFACE)
        manager_unchanged()
        unit_keys = ("Id", "Description", "Transient", "InvocationID", "ActiveState", "Job")
        if (before_unit.get("JobTimeoutUSec") != 4_000_000 or
                unit.get("JobTimeoutUSec") != 4_000_000):
            raise ValueError("probe queue timeout unavailable or overridden")
        service_keys = ("MainPID", "ControlPID", "ExecStart", "Type", "Restart",
                        "User", "Group", "Environment", "EnvironmentFiles",
                        "PassEnvironment", "UnsetEnvironment", "ExecCondition",
                        "ExecStartPre", "ExecStartPost")
        if (peer_path != path or
                any(before_unit[key] != unit[key] for key in unit_keys) or
                any(before_service[key] != service[key] for key in service_keys)):
            raise ValueError("probe gate changed during admission")
        invocation = bytes(unit["InvocationID"])
        if (unit["Id"] != result.unit or unit["Description"] != self._description or
                unit["Transient"] is not True or
                unit["ActiveState"] not in {"activating", "active"} or
                invocation != bytes.fromhex(peer.invocation) or
                service["MainPID"] != peer.pid or service["ControlPID"] != 0):
            raise ValueError("probe gate identity mismatch")
        # A Type=exec start job may already have completed while the gate waits.
        # A retained reply authenticates creation; a live job, if any, must match.
        # Never treat that job ID as an immutable invocation identity.
        job_id = int(result.job.rsplit("/", 1)[1])
        if tuple(unit["Job"]) not in {(0, "/"), (job_id, result.job)}:
            raise ValueError("probe job replaced")
        commands = service["ExecStart"]
        if (len(commands) != 1 or
                tuple(commands[0][:3]) != (PROBE_GATE, [PROBE_GATE, token], False) or
                service["Type"] != "exec" or service["Restart"] != "no" or
                service["User"] != "0" or service["Group"] != "0" or
                any(service[key] != [] for key in service_keys[7:])):
            raise ValueError("probe gate command changed")
        return AdmissionBinding(peer, result.manager, result.unit, result.job)

    def run(self):
        return self._start(native=False)

    def run_native(self):
        """Exercise retained native admission; not yet a policy receipt.

        This explicit qualification path needs provisioned fixed payloads/root.
        Ordinary run() and the boot canary retain their existing behavior.
        """
        return self._start(native=True)

    def _start(self, *, native):
        if not self._operation.acquire(blocking=False):
            raise RuntimeError("execution probe operation already running")
        try:
            if self._pending is not None:
                raise RuntimeError("execution probe cleanup must be recovered")
            return self._run(native=native)
        finally:
            self._operation.release()

    def _run(self, *, native=False):
        token = secrets.token_hex(16)
        result = ProbeResult(unit=f"onpc-execution-probe-{token}.service")
        description = f"ONPC execution probe {token}"
        self._description = description
        submitted = False
        self._settled = True
        self._client = ProbeBusClient()
        self._pending = result
        try:
            if native:
                # Retain each owner before any operation that can partially
                # create resources or be interrupted.
                self._generation = ProbeGeneration()
                identity = self._generation.prepare()
                token = identity.token
                description = f"ONPC execution probe {token}"
                self._description = description
                result = replace(result, unit=f"onpc-execution-probe-{token}.service",
                                 generation=identity)
                self._pending = result
                self._channel = ProbeChannel()
                self._channel.open(identity.directory)
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
            if native:
                # Start before dispatch, so reply polling cannot spend the
                # gate's entire two-second wait and then start a fresh budget.
                admission_deadline = time.monotonic() + TIMEOUT
                self._client.start_create(owner, result.unit, description, token=token)
                result, submitted = self._collect_create(
                    result, preserve_outcome=False, deadline=admission_deadline)
                self._pending = result
                if submitted and result.create_outcome == "replied":
                    peer = self._channel.select(deadline=admission_deadline)
                    binding = self._admission_binding(result, token, peer, admission_deadline)
                    self._generation.verify()
                    result = replace(result, admission=binding, invocation=peer.invocation)
                    self._pending = result
                    self._channel.admit(binding)
                    result = replace(result, channel_result=self._channel.collect())
                    self._pending = result
            else:
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
                    if native:
                        self._generation.verify()
                        owner = self._request(
                            DBUS_NAME, DBUS_PATH, DBUS_INTERFACE, "GetNameOwner",
                            GLib.Variant("(s)", (SYSTEMD_NAME,)), "(s)", deadline)
                        if owner != result.manager:
                            raise ValueError("probe manager replaced after admission")
                        verified = (result.admission is not None and
                                    result.channel_result == "executed" and
                                    result.invocation == result.admission.peer.invocation and
                                    result.outcome == "identity-unproven")
                        result = replace(result, native_verified=verified,
                                         outcome="identity-unproven" if verified else "execution-failed")
                    break
                time.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))
            if submitted and not result.terminal_observed:
                if result.outcome != "create-uncertain":
                    result = replace(result, outcome="observation-timeout")
            elif submitted and result.create_outcome == "uncertain":
                result = replace(result, outcome="create-uncertain")
        except (GLib.Error, TimeoutError, ValueError, KeyError, TypeError, OverflowError,
                OSError, ChannelRefused, GenerationRefused):
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
        LOG.info(
            "execution-probe.006",
            outcome=result.outcome,
            cleanup_complete=result.cleanup_complete,
        )
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
            LOG.info(
                "execution-probe.007",
                outcome=result.outcome,
                cleanup_complete=result.cleanup_complete,
            )
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
                "execution-probe.008",
                create_collected=result.create_outcome != "pending",
                terminal_evidence=result.terminal_observed,
            )
            return result
        deadline = time.monotonic() + CLEANUP_SECONDS
        try:
            sender = self._sender()
            if sender.is_closed():
                return self._collect_after_sender_loss(result, sender, deadline)
            # () has no first tuple item; use the shared finite transport directly.
            try:
                _call(sender, result.manager, SYSTEMD_PATH,
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

    def _collect_after_sender_loss(self, result, sender, deadline):
        """Observe settlement after involuntary loss; never disconnect to force it.

        The caller has already copied terminal evidence. A collected successful
        create reply is also required: sender loss cannot settle delayed dispatch.
        Reads use only the surviving observer and the original unique manager.
        """
        name = sender.get_unique_name()
        if result.create_outcome != "replied" or not name or not name.startswith(":"):
            return result
        while time.monotonic() < deadline:
            owner = self._request(
                DBUS_NAME, DBUS_PATH, DBUS_INTERFACE, "GetNameOwner",
                GLib.Variant("(s)", (SYSTEMD_NAME,)), "(s)", deadline)
            if owner != result.manager:
                return result
            present = self._request(
                DBUS_NAME, DBUS_PATH, DBUS_INTERFACE, "NameHasOwner",
                GLib.Variant("(s)", (name,)), "(b)", deadline)
            if not present:
                try:
                    self._manager(result.manager, "GetUnit",
                                  GLib.Variant("(s)", (result.unit,)), "(o)", deadline)
                except GLib.Error as error:
                    if _error_name(error) != NO_UNIT:
                        raise
                    return replace(result, reference_released=True, cleanup_complete=True)
            time.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))
        return result
