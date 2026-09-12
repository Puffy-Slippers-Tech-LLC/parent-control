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
class ProbeResult:
    """Safe evidence/recovery coordinates; no user data or raw D-Bus errors."""

    unit: str
    manager: str = ""
    job: str = ""
    invocation: str = ""
    outcome: str = "transport-failed"
    service_result: str = ""
    exit_code: int = 0
    exit_status: int = 0
    terminal_observed: bool = False
    reference_released: bool = False
    cleanup_complete: bool = False

    @property
    def executed(self):
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
    """One fixed canary per call over an existing system-bus connection.

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

    @property
    def pending(self):
        """Immutable recovery coordinates, retained until cleanup is proven."""
        return self._pending

    def _request(self, owner, path, interface, method, args, signature, deadline):
        remaining_ms = int((deadline - time.monotonic()) * 1000)
        if remaining_ms <= 0:
            raise TimeoutError("probe observation deadline")
        return _call(self.connection, owner, path, interface, method, args,
                     signature, timeout=min(CALL_MS, remaining_ms)).unpack()[0]

    def _manager(self, owner, method, args, signature, deadline):
        return self._request(owner, SYSTEMD_PATH, SYSTEMD_MANAGER_INTERFACE,
                             method, args, signature, deadline)

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
        executed = (code == 1 and status == PROBE_EXECUTED and
                    backend_result == "exit-code" and
                    0 < service["ExecMainStartTimestampMonotonic"] <
                    service["ExecMainExitTimestampMonotonic"])
        return replace(result, terminal_observed=True, exit_code=code,
                       exit_status=status, service_result=backend_result,
                       outcome="executed" if executed else "execution-failed")

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
        deadline = time.monotonic() + OBSERVE_SECONDS
        submitted = False
        create_replied = False
        try:
            owner = self._request(DBUS_NAME, DBUS_PATH, DBUS_INTERFACE,
                                  "GetNameOwner", GLib.Variant("(s)", (SYSTEMD_NAME,)),
                                  "(s)", deadline)
            if not owner.startswith(":"):
                raise ValueError("invalid manager owner")
            result = replace(result, manager=owner)
            submitted = True
            # Retain coordinates before dispatch, including interruption paths.
            self._pending = result
            try:
                job = self._manager(owner, "StartTransientUnit",
                                    GLib.Variant("(ssa(sv)a(sa(sv)))", (
                                        result.unit, "fail", _properties(description), [])),
                                    "(o)", deadline)
                create_replied = True
                result = replace(result, job=job)
            except GLib.Error as error:
                if _error_name(error) == UNIT_EXISTS:
                    submitted = False
                    self._pending = None
                    return replace(result, outcome="collision", cleanup_complete=True)
                # Even an error can follow partial creation. Never retry create.
                result = replace(result, outcome="create-uncertain")

            while time.monotonic() < deadline:
                result = self._snapshot(result, description, deadline)
                if result.terminal_observed:
                    break
                time.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))
            if not result.terminal_observed:
                result = replace(result, outcome="observation-timeout")
            elif not create_replied:
                result = replace(result, outcome="create-uncertain")
        except (GLib.Error, TimeoutError, ValueError, KeyError, TypeError, OverflowError):
            if result.outcome != "create-uncertain":
                result = replace(result, outcome="observation-failed" if submitted else "transport-failed")
        finally:
            if submitted:
                self._pending = result
                result = self._release(result)
                self._pending = None if result.cleanup_complete else result
        if not submitted:
            result = replace(result, cleanup_complete=True)
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
                while not result.terminal_observed and time.monotonic() < deadline:
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
                result = self._release(result)
                self._pending = None if result.cleanup_complete else result
            LOG.info("execution probe recovery outcome=%s cleanup_complete=%s",
                     result.outcome, result.cleanup_complete)
            return result
        finally:
            self._operation.release()

    def _release(self, result):
        deadline = time.monotonic() + CLEANUP_SECONDS
        try:
            # () has no first tuple item; use the shared finite transport directly.
            try:
                _call(self.connection, result.manager, SYSTEMD_PATH,
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
