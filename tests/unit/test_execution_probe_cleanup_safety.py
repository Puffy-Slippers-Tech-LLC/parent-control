"""No host services: exercise the probe's ownership and evidence boundary."""

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor

from gi.repository import Gio, GLib
import pytest

from oh_no_parent_control import execution_probe as probe


def dbus_error(name):
    return Gio.DBusError.new_for_dbus_error(name, "[redacted transport detail]")


class Clock:
    now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Manager:
    """Models fast exit, client pinning, GC and asynchronous create failures."""

    def __init__(self):
        self.calls = []
        self.unit = None
        self.service = None
        self.reference = False
        self.create_error = None
        self.create_before_error = True
        self.pending_create = None
        self.unref_error = False
        self.unref_after_error = False
        self.collect = True
        self.hook = lambda method, interface: None
        self.clients = []
        self.sender_calls = []

    def dispatch_create(self, args=None):
        name, mode, properties, aux = args or self.pending_create
        self.pending_create = None
        properties = dict(properties)
        assert mode == "fail" and aux == []
        self.reference = properties["AddRef"]
        self.unit = {
            "Id": name, "Description": properties["Description"],
            "Transient": True, "InvocationID": [1] * 16,
            "ActiveState": "failed", "Job": (0, "/"),
        }
        self.service = {
            "MainPID": 0, "ControlPID": 0, "ExecMainCode": 1,
            "ExecMainStatus": 23, "Result": "exit-code",
            "ExecMainStartTimestampMonotonic": 10,
            "ExecMainExitTimestampMonotonic": 20,
            "ExecStart": [(probe.PROBE, [probe.PROBE], False, 0, 0, 0, 0, 0, 0, 0)],
        }

    def call_sync(self, destination, path, interface, method, parameters,
                  reply_type, flags, timeout, cancellable):
        assert method not in {"StartTransientUnit", "UnrefUnit"}, "observer must never mutate"
        return self.dispatch(destination, path, interface, method, parameters,
                             reply_type, flags, timeout, cancellable)

    def dispatch(self, destination, path, interface, method, parameters,
                 reply_type, flags, timeout, cancellable):
        args = parameters.unpack()
        self.calls.append((destination, method, args, timeout))
        assert 0 < timeout <= probe.CALL_MS
        assert flags == Gio.DBusCallFlags.NONE
        assert cancellable is None
        if method == "GetId":
            return GLib.Variant("(s)", ("test-bus",))
        if method == "GetNameOwner":
            return GLib.Variant("(s)", (":1.50",))
        assert destination == ":1.50"  # Never retarget a replacement manager.
        self.hook(method, args[0] if args else "")
        if method == "StartTransientUnit":
            if self.create_error == probe.UNIT_EXISTS:
                raise dbus_error(self.create_error)
            if self.create_before_error:
                self.dispatch_create(args)
            else:
                self.pending_create = args
            if self.create_error:
                raise dbus_error(self.create_error)
            return GLib.Variant("(o)", ("/org/freedesktop/systemd1/job/42",))
        if method == "GetUnit":
            if self.unit is None:
                raise dbus_error(probe.NO_UNIT)
            return GLib.Variant("(o)", ("/org/freedesktop/systemd1/unit/probe",))
        if method == "GetAll":
            assert self.reference, "terminal evidence must remain pinned"
            data = self.unit if args[0] == probe.UNIT_INTERFACE else self.service
            types = {"Transient": "b", "InvocationID": "ay", "Job": "(uo)",
                     "MainPID": "u", "ControlPID": "u", "ExecMainCode": "i",
                     "ExecMainStatus": "i", "ExecMainStartTimestampMonotonic": "t",
                     "ExecMainExitTimestampMonotonic": "t", "ExecStart": "a(sasbttttuii)"}
            return GLib.Variant("(a{sv})", ({
                key: GLib.Variant(types.get(key, "s"), value)
                for key, value in deepcopy(data).items()},))
        if method == "UnrefUnit":
            if self.unref_error and not self.unref_after_error:
                raise dbus_error("org.freedesktop.DBus.Error.NoReply")
            if self.unit is None:
                raise dbus_error(probe.NO_UNIT)
            if not self.reference:
                raise dbus_error(probe.NOT_REFERENCED)
            self.reference = False
            if self.collect and self.unit["ActiveState"] in {"inactive", "failed"}:
                self.unit = None
            if self.unref_error:
                raise dbus_error("org.freedesktop.DBus.Error.NoReply")
            return GLib.Variant("()", ())
        pytest.fail(f"unexpected mutating operation: {method}")


class Client:
    """Owned sender double; lifecycle callback behavior has separate coverage."""

    def __init__(self, manager):
        self.manager = manager
        self.connection = None
        self.close_calls = 0
        self.close_result = True
        self.open_result = True
        self.close_hook = lambda: None
        self.create_reply = None
        self.create_started = False
        self.deferred_reply = None
        self.hold_reply = False
        self.poll_hook = lambda: None
        manager.clients.append(self)

    def open(self, address):
        assert address == "unix:path=/test-bus"
        if self.open_result:
            self.connection = self
        return self.open_result

    def close(self):
        if self.create_started and self.create_reply is None:
            return False
        self.close_calls += 1
        self.close_hook()
        if self.close_result:
            self.connection = None
        return self.close_result

    def call_sync(self, destination, path, interface, method, parameters,
                  reply_type, flags, timeout, cancellable):
        assert self.connection is self
        assert method in {"GetId", "UnrefUnit"}
        self.manager.sender_calls.append(method)
        return self.manager.dispatch(destination, path, interface, method, parameters,
                                     reply_type, flags, timeout, cancellable)

    def start_create(self, owner, unit, description):
        assert self.connection is self and owner == ":1.50" and not self.create_started
        self.create_started = True
        self.manager.sender_calls.append("StartTransientUnit")
        parameters = GLib.Variant("(ssa(sv)a(sa(sv)))", (
            unit, "fail", probe._properties(description), []))
        try:
            reply = self.manager.dispatch(
                owner, probe.SYSTEMD_PATH, probe.SYSTEMD_MANAGER_INTERFACE,
                "StartTransientUnit", parameters, GLib.VariantType.new("(o)"),
                Gio.DBusCallFlags.NONE, probe.CALL_MS, None)
            retained = probe.ProbeCreateReply("replied", reply.unpack()[0])
        except GLib.Error as error:
            retained = probe.ProbeCreateReply(
                "collision" if probe._error_name(error) == probe.UNIT_EXISTS else "uncertain")
        if self.hold_reply:
            self.deferred_reply = retained
        else:
            self.create_reply = retained

    def poll_create(self):
        self.poll_hook()
        return self.create_reply

    def deliver_create_reply(self):
        assert self.create_reply is None and self.deferred_reply is not None
        self.create_reply, self.deferred_reply = self.deferred_reply, None


@pytest.fixture
def environment(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(probe.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(probe.time, "sleep", clock.sleep)
    manager = Manager()
    monkeypatch.setattr(probe, "ProbeBusClient", lambda: Client(manager))
    def address(bus_type, cancellable):
        assert bus_type == Gio.BusType.SYSTEM and cancellable is None
        return "unix:path=/test-bus"
    monkeypatch.setattr(Gio, "dbus_address_get_for_bus_sync", address)
    return manager, clock


def test_fast_exit_evidence_is_retained_before_collection(environment):
    manager, _ = environment
    result = probe.ExecutionProbe(manager).run()
    assert not result.executed and result.outcome == "identity-unproven"
    assert result.cleanup_complete and result.reference_released
    assert result.create_outcome == "replied"
    assert result.client_closed and manager.clients[0].close_calls == 1
    assert manager.sender_calls == ["GetId", "StartTransientUnit", "UnrefUnit"]
    assert result.job.endswith("/42") and result.invocation == "01" * 16
    assert result.exit_status == 23 and result.terminal_observed
    assert manager.unit is None and not manager.reference
    properties = dict(next(call[2][2] for call in manager.calls if call[1] == "StartTransientUnit"))
    assert properties["ExecStart"] == [(probe.PROBE, [probe.PROBE], False)]
    assert properties["Type"] == "exec" and properties["Restart"] == "no"
    assert properties["CollectMode"] == "inactive-or-failed"
    for name in ("TimeoutStartUSec", "RuntimeMaxUSec", "TimeoutStopUSec", "JobTimeoutUSec"):
        assert 0 < properties[name] <= 4_000_000
    assert properties["KillMode"] == "control-group" and properties["SendSIGKILL"]


@pytest.mark.parametrize("replacement", ["before-first-read", "same-job-rerun"])
def test_original_job_cannot_certify_a_preobserved_replacement(environment, replacement):
    manager, _ = environment
    reads = 0

    def hook(method, interface):
        nonlocal reads
        if method == "GetUnit" and manager.unit is not None:
            # A privileged restart leaves the name, description and command
            # intact. The original invocation has already been overwritten.
            manager.unit["InvocationID"] = [2] * 16
        if method == "GetAll" and interface == probe.UNIT_INTERFACE:
            reads += 1
            if replacement == "same-job-rerun" and reads <= 2:
                # systemd job_install can merge/re-run under the original ID;
                # a restart becomes a start job again after its stop phase.
                manager.unit.update(ActiveState="activating",
                                    Job=(42, "/org/freedesktop/systemd1/job/42"))
            else:
                manager.unit.update(ActiveState="failed", Job=(0, "/"))

    manager.hook = hook
    adapter = probe.ExecutionProbe(manager)
    result = adapter.run()
    assert not result.executed
    assert result.outcome == "identity-unproven"
    assert result.job.endswith("/42") and result.invocation == "02" * 16
    assert result.terminal_observed and result.exit_status == 23
    assert result.cleanup_complete and result.reference_released and result.client_closed
    assert adapter.pending is None and manager.unit is None and not manager.reference


@pytest.mark.parametrize("status,code,service_result", [
    (203, 1, "exit-code"), (9, 2, "signal"), (0, 0, "timeout"),
    (0, 0, "resources"), (0, 1, "success"), (23, 1, "timeout"),
])
def test_exec_failures_are_never_policy_denials(environment, status, code, service_result):
    manager, _ = environment

    def hook(method, _):
        if method == "GetUnit" and manager.reference:
            manager.service.update(ExecMainCode=code, ExecMainStatus=status, Result=service_result)

    manager.hook = hook
    result = probe.ExecutionProbe(manager).run()
    assert result.outcome == "execution-failed" and not result.executed
    assert result.cleanup_complete and result.terminal_observed


def test_lost_create_reply_preserves_failure_even_after_owned_collection(environment):
    manager, _ = environment
    manager.create_error = "org.freedesktop.DBus.Error.NoReply"
    result = probe.ExecutionProbe(manager).run()
    assert result.outcome == "create-uncertain" and not result.executed
    assert result.create_outcome == "uncertain"
    assert result.terminal_observed and result.cleanup_complete
    assert result.job == ""
    assert sum(call[1] == "StartTransientUnit" for call in manager.calls) == 1


def test_late_create_cannot_be_declared_clean_from_absence(environment):
    manager, _ = environment
    manager.create_error = "org.freedesktop.DBus.Error.NoReply"
    manager.create_before_error = False
    result = probe.ExecutionProbe(manager).run()
    assert not result.cleanup_complete and not result.executed
    assert result.unit and result.manager and not result.terminal_observed
    assert sum(call[1] == "StartTransientUnit" for call in manager.calls) == 1


def test_collision_does_not_touch_foreign_reference_or_unit(environment):
    manager, _ = environment
    manager.create_error = probe.UNIT_EXISTS
    result = probe.ExecutionProbe(manager).run()
    assert result.outcome == "collision" and result.cleanup_complete
    assert result.create_outcome == "collision"
    assert [call[1] for call in manager.calls] == ["GetId", "GetId", "GetNameOwner", "StartTransientUnit"]
    assert result.client_closed and manager.clients[0].close_calls == 1


@pytest.mark.parametrize("change", ["description", "invocation", "manager", "missing-evidence", "command"])
def test_replacement_and_collection_fail_closed_without_signals(environment, change):
    manager, _ = environment

    def hook(method, interface):
        if method == "GetAll" and interface == probe.SERVICE_INTERFACE:
            if change == "description":
                manager.unit["Description"] = "foreign"
            elif change == "invocation":
                manager.unit["InvocationID"] = [2] * 16
            elif change == "manager":
                raise dbus_error("org.freedesktop.DBus.Error.NameHasNoOwner")
            elif change == "command":
                manager.service["ExecStart"][0] = ("/foreign", ["/foreign"], False, 0, 0, 0, 0, 0, 0, 0)
            else:
                manager.service.pop("ExecMainStatus", None)

    manager.hook = hook
    result = probe.ExecutionProbe(manager).run()
    assert not result.executed and not result.cleanup_complete
    assert result.outcome == "observation-failed"
    assert not result.reference_released and manager.reference


@pytest.mark.parametrize("phase", ["activating", "active", "deactivating"])
def test_stalled_exec_or_stop_has_finite_observation_and_uncertain_cleanup(environment, phase):
    manager, clock = environment

    def hook(method, _):
        if method == "GetUnit" and manager.reference:
            manager.unit["ActiveState"] = phase
            manager.service["MainPID"] = 123

    manager.hook = hook
    result = probe.ExecutionProbe(manager).run()
    assert result.outcome == "observation-timeout"
    assert not result.executed and not result.cleanup_complete
    assert not result.reference_released and manager.unit is not None and manager.reference
    assert clock.now <= probe.OBSERVE_SECONDS + probe.CLEANUP_SECONDS + 0.01


@pytest.mark.parametrize("failure", ["unref", "gc"])
def test_cleanup_failure_preserves_terminal_evidence_but_prevents_success(environment, failure):
    manager, _ = environment
    manager.unref_error = failure == "unref"
    manager.collect = failure != "gc"
    result = probe.ExecutionProbe(manager).run()
    assert result.terminal_observed and result.exit_status == 23
    assert not result.cleanup_complete and not result.executed
    assert result.reference_released == (failure != "unref")


def test_missing_exit_timestamp_cannot_supply_execution(environment):
    manager, _ = environment

    def hook(method, _):
        if method == "GetUnit" and manager.reference:
            manager.service["ExecMainExitTimestampMonotonic"] = 0

    manager.hook = hook
    result = probe.ExecutionProbe(manager).run()
    assert result.outcome == "execution-failed" and not result.executed


def test_pending_job_prevents_terminal_receipt(environment):
    manager, _ = environment

    def hook(method, _):
        if method == "GetUnit" and manager.reference:
            manager.unit["Job"] = (42, "/org/freedesktop/systemd1/job/42")

    manager.hook = hook
    result = probe.ExecutionProbe(manager).run()
    assert result.outcome == "observation-timeout"
    assert not result.terminal_observed and not result.cleanup_complete


@pytest.mark.parametrize("phase", ["activating", "active", "deactivating"])
def test_late_exit_keeps_evidence_until_recovery(environment, phase):
    manager, _ = environment
    adapter = probe.ExecutionProbe(manager)

    def hook(method, _):
        if method == "GetUnit" and manager.unit is not None:
            manager.unit["ActiveState"] = phase
            manager.service["MainPID"] = 123

    manager.hook = hook
    original = adapter.run()
    assert original.outcome == "observation-timeout" and not original.terminal_observed
    pending = adapter.recover()
    assert pending is adapter.pending and not pending.cleanup_complete
    assert not pending.reference_released and manager.reference
    assert manager.clients[0].close_calls == 0
    manager.hook = lambda method, interface: None
    # Systemd can finish after our observation deadline. Without a client pin,
    # CollectMode permits GC before the next recovery has copied exit evidence.
    manager.unit["ActiveState"] = "failed"
    manager.service["MainPID"] = 0
    if not manager.reference:
        manager.unit = None
    assert manager.unit is not None and manager.reference
    assert not original.reference_released and not original.client_closed
    recovered = adapter.recover()
    assert recovered.terminal_observed and recovered.cleanup_complete
    assert recovered.outcome == original.outcome and not recovered.executed
    assert recovered.reference_released and recovered.client_closed
    assert manager.unit is None and adapter.pending is None
    assert manager.sender_calls.count("StartTransientUnit") == 1
    assert manager.sender_calls.count("UnrefUnit") == 1


def test_create_after_last_absence_keeps_evidence_until_recovery(environment):
    manager, _ = environment
    manager.create_error = "org.freedesktop.DBus.Error.NoReply"
    manager.create_before_error = False
    adapter = probe.ExecutionProbe(manager)

    def hook(method, _):
        if method == "UnrefUnit" and manager.pending_create is not None:
            # Previously this release raced with creation after the last GetUnit
            # absence and collected the canary before any terminal snapshot.
            manager.dispatch_create()

    manager.hook = hook
    original = adapter.run()
    assert original.outcome == "create-uncertain" and not original.terminal_observed
    if manager.pending_create is not None:
        manager.dispatch_create()
    assert manager.unit is not None and manager.reference
    assert not original.reference_released and manager.clients[0].close_calls == 0
    recovered = adapter.recover()
    assert recovered.terminal_observed and recovered.cleanup_complete
    assert recovered.outcome == original.outcome and not recovered.executed
    assert adapter.pending is None and manager.unit is None
    assert manager.sender_calls.count("StartTransientUnit") == 1
    assert manager.sender_calls.count("UnrefUnit") == 1


def test_failed_snapshot_keeps_terminal_evidence_for_later_recovery(environment):
    manager, _ = environment
    adapter = probe.ExecutionProbe(manager)

    def hook(method, interface):
        if method == "GetAll" and interface == probe.SERVICE_INTERFACE:
            raise dbus_error("org.freedesktop.DBus.Error.NoReply")

    manager.hook = hook
    original = adapter.run()
    assert original.outcome == "observation-failed" and not original.terminal_observed
    assert manager.unit is not None and manager.reference
    assert not original.reference_released and manager.clients[0].close_calls == 0
    manager.hook = lambda method, interface: None
    recovered = adapter.recover()
    assert recovered.terminal_observed and recovered.cleanup_complete
    assert recovered.outcome == original.outcome and not recovered.executed
    assert adapter.pending is None and manager.unit is None


def test_ordinary_exit_during_collection_is_observed_again(environment):
    manager, _ = environment
    reads = 0

    def hook(method, interface):
        nonlocal reads
        if method == "GetAll" and interface == probe.UNIT_INTERFACE:
            reads += 1
            manager.unit["ActiveState"] = "active" if reads == 1 else "failed"

    manager.hook = hook
    result = probe.ExecutionProbe(manager).run()
    assert result.outcome == "identity-unproven" and not result.executed and reads == 4


def test_invocation_change_between_polls_invalidates_prior_identity(environment):
    manager, _ = environment
    reads = 0

    def hook(method, interface):
        nonlocal reads
        if method == "GetAll" and interface == probe.UNIT_INTERFACE:
            reads += 1
            manager.unit["ActiveState"] = "active" if reads <= 2 else "failed"
            manager.unit["InvocationID"] = [1 if reads <= 2 else 2] * 16

    manager.hook = hook
    result = probe.ExecutionProbe(manager).run()
    assert result.outcome == "observation-failed" and result.invocation == "01" * 16
    assert not result.executed and not result.cleanup_complete


def test_errors_and_logs_do_not_include_transport_payload(environment, caplog):
    manager, _ = environment
    manager.create_error = "org.freedesktop.DBus.Error.NoReply"
    with caplog.at_level("INFO"):
        result = probe.ExecutionProbe(manager).run()
    assert "redacted transport detail" not in caplog.text + repr(result)


def test_delayed_dispatch_is_recovered_without_another_create(environment):
    manager, clock = environment
    manager.create_error = "org.freedesktop.DBus.Error.NoReply"
    manager.create_before_error = False
    adapter = probe.ExecutionProbe(manager)
    original = adapter.run()
    assert adapter.pending is original and not original.cleanup_complete
    with pytest.raises(RuntimeError, match="must be recovered"):
        adapter.run()
    manager.dispatch_create()
    assert manager.reference  # Late creation pins evidence until recovery observes it.
    recovered = adapter.recover()
    assert recovered.cleanup_complete and recovered.terminal_observed
    assert recovered.outcome == original.outcome == "create-uncertain"
    assert not recovered.executed and not original.cleanup_complete
    assert not manager.reference and manager.unit is None
    assert adapter.pending is None and adapter.recover() is None
    assert sum(call[1] == "StartTransientUnit" for call in manager.calls) == 1
    assert clock.now <= 2 * probe.CLEANUP_SECONDS + 0.01


def test_absent_delayed_create_stays_pending_through_bounded_recovery(environment):
    manager, clock = environment
    manager.create_error = "org.freedesktop.DBus.Error.NoReply"
    manager.create_before_error = False
    adapter = probe.ExecutionProbe(manager)
    adapter.run()
    recovered = adapter.recover()
    assert recovered is adapter.pending and not recovered.cleanup_complete
    assert not recovered.terminal_observed and not recovered.executed
    with pytest.raises(RuntimeError, match="must be recovered"):
        adapter.run()
    assert manager.pending_create is not None
    assert clock.now <= 2 * probe.CLEANUP_SECONDS + 0.01


def test_create_arriving_during_recovery_is_observed_and_released(environment):
    manager, _ = environment
    manager.create_error = "org.freedesktop.DBus.Error.NoReply"
    manager.create_before_error = False
    adapter = probe.ExecutionProbe(manager)
    adapter.run()
    reads = 0

    def hook(method, _):
        nonlocal reads
        if method == "GetUnit":
            reads += 1
            if reads == 2:
                manager.dispatch_create()

    manager.hook = hook
    recovered = adapter.recover()
    assert recovered.cleanup_complete and not recovered.executed
    assert not manager.reference and adapter.pending is None


@pytest.mark.parametrize("collected", [False, True])
def test_lost_unref_reply_recovers_current_absence_without_promoting_success(environment, collected):
    manager, _ = environment
    manager.unref_error = manager.unref_after_error = True
    manager.collect = collected
    adapter = probe.ExecutionProbe(manager)
    original = adapter.run()
    assert original.terminal_observed and not original.executed
    assert adapter.pending is original and not manager.reference
    manager.unref_error = False

    def hook(method, _):
        if method == "GetUnit":
            manager.unit = None  # Asynchronous GC after NotReferenced.

    manager.hook = hook
    recovered = adapter.recover()
    assert recovered.cleanup_complete and not recovered.executed
    assert recovered.outcome == original.outcome == "identity-unproven" and adapter.pending is None
    assert not original.cleanup_complete


@pytest.mark.parametrize("change", ["description", "invocation", "manager"])
def test_recovery_retains_coordinates_when_collection_cannot_be_confirmed(environment, change):
    manager, _ = environment
    adapter = probe.ExecutionProbe(manager)
    manager.collect = False
    original = adapter.run()
    # Retained terminal evidence requires only reference release/collection;
    # replacement remains present and therefore cannot be declared cleaned up.
    if change == "description":
        manager.unit["Description"] = "foreign"
    elif change == "invocation":
        manager.unit["InvocationID"] = [2] * 16
    else:
        def hook(method, _):
            raise dbus_error("org.freedesktop.DBus.Error.NameHasNoOwner")
        manager.hook = hook
    recovered = adapter.recover()
    assert not recovered.cleanup_complete and not recovered.executed
    assert recovered.manager == original.manager and recovered.invocation == original.invocation
    assert adapter.pending is recovered


def test_concurrent_operations_refuse_without_blocking_or_extra_dispatch(environment):
    manager, _ = environment
    adapter = probe.ExecutionProbe(manager)
    with ThreadPoolExecutor(max_workers=1) as executor:
        def hook(method, _):
            if method == "StartTransientUnit":
                for operation in (adapter.run, adapter.recover):
                    with pytest.raises(RuntimeError, match="already running"):
                        executor.submit(operation).result(timeout=2)
        manager.hook = hook
        result = adapter.run()
    assert result.outcome == "identity-unproven" and not result.executed and adapter.pending is None
    assert sum(call[1] == "StartTransientUnit" for call in manager.calls) == 1


def test_interrupted_dispatch_retains_cleanup_coordinates(environment):
    manager, _ = environment
    adapter = probe.ExecutionProbe(manager)

    def hook(method, _):
        if method == "StartTransientUnit":
            raise KeyboardInterrupt

    manager.hook = hook
    with pytest.raises(KeyboardInterrupt):
        adapter.run()
    assert adapter.pending is not None and not adapter.pending.cleanup_complete
    assert adapter.pending.manager == ":1.50"
    with pytest.raises(RuntimeError, match="must be recovered"):
        adapter.run()


def test_delayed_foreign_unit_cannot_supply_recovery_terminal_evidence(environment):
    manager, _ = environment
    manager.create_error = "org.freedesktop.DBus.Error.NoReply"
    manager.create_before_error = False
    adapter = probe.ExecutionProbe(manager)
    adapter.run()
    manager.dispatch_create()
    manager.unit["Description"] = "foreign"
    recovered = adapter.recover()
    assert not recovered.terminal_observed and not recovered.cleanup_complete
    assert not recovered.executed and adapter.pending is recovered


def test_interrupted_release_retains_terminal_evidence_for_recovery(environment):
    manager, _ = environment
    adapter = probe.ExecutionProbe(manager)

    def hook(method, _):
        if method == "UnrefUnit":
            raise KeyboardInterrupt

    manager.hook = hook
    with pytest.raises(KeyboardInterrupt):
        adapter.run()
    assert adapter.pending.terminal_observed and manager.reference
    manager.hook = lambda method, interface: None
    recovered = adapter.recover()
    assert recovered.cleanup_complete and not recovered.executed
    assert adapter.pending is None and not manager.reference


@pytest.mark.parametrize("interrupted", [False, True])
def test_client_close_recovery_preserves_collected_evidence(environment, interrupted):
    manager, _ = environment
    adapter = probe.ExecutionProbe(manager)

    def hook(method, _):
        if method == "StartTransientUnit":
            client = manager.clients[0]
            client.close_result = False
            if interrupted:
                def stop():
                    raise KeyboardInterrupt
                client.close_hook = stop

    manager.hook = hook
    if interrupted:
        with pytest.raises(KeyboardInterrupt):
            adapter.run()
        original = adapter.pending
    else:
        original = adapter.run()
    assert original.terminal_observed and original.reference_released
    assert not original.cleanup_complete and not original.client_closed and not original.executed
    assert manager.unit is None and adapter.pending is original
    with pytest.raises(RuntimeError, match="must be recovered"):
        adapter.run()
    calls = len(manager.calls)
    manager.clients[0].close_result = True
    manager.clients[0].close_hook = lambda: None
    recovered = adapter.recover()
    assert recovered.cleanup_complete and recovered.client_closed
    assert recovered.outcome == original.outcome == "identity-unproven" and not recovered.executed
    assert len(manager.calls) == calls and adapter.pending is None


@pytest.mark.parametrize("failure", ["open", "resolver", "mismatched-bus"])
def test_pre_dispatch_failure_retains_failed_close_without_systemd_calls(environment, monkeypatch, failure):
    manager, _ = environment
    client = Client(manager)
    client.close_result = False
    monkeypatch.setattr(probe, "ProbeBusClient", lambda: client)
    if failure == "open":
        client.open_result = False
    elif failure == "resolver":
        def failed_address(*_args):
            raise dbus_error("org.freedesktop.DBus.Error.Failed")
        monkeypatch.setattr(Gio, "dbus_address_get_for_bus_sync", failed_address)
    else:
        monkeypatch.setattr(client, "call_sync", lambda *_args:
                            GLib.Variant("(s)", ("different-bus",)))
    adapter = probe.ExecutionProbe(manager)
    original = adapter.run()
    assert original.outcome == "transport-failed" and adapter.pending is original
    assert not original.cleanup_complete and not original.client_closed
    assert all(call[1] == "GetId" for call in manager.calls)
    client.close_result = True
    recovered = adapter.recover()
    assert recovered.cleanup_complete and recovered.client_closed and not recovered.executed
    assert recovered.outcome == "transport-failed" and adapter.pending is None


def test_ambiguous_dispatch_retains_sender_until_terminal_collection(environment):
    manager, _ = environment
    manager.create_error = "org.freedesktop.DBus.Error.NoReply"
    manager.create_before_error = False
    adapter = probe.ExecutionProbe(manager)
    original = adapter.run()
    assert not original.client_closed and manager.clients[0].close_calls == 0
    still_pending = adapter.recover()
    assert not still_pending.cleanup_complete and manager.clients[0].close_calls == 0
    manager.dispatch_create()
    recovered = adapter.recover()
    assert recovered.client_closed and recovered.cleanup_complete and not recovered.executed
    assert manager.clients[0].close_calls == 1 and adapter.pending is None


@pytest.mark.parametrize("terminal_outcome", ["identity-unproven", "execution-failed"])
def test_late_job_reply_is_copied_before_release_without_outcome_promotion(
        environment, monkeypatch, terminal_outcome):
    manager, _ = environment
    client = manager.clients
    adapter = probe.ExecutionProbe(manager)

    created = Client(manager)
    created.hold_reply = True
    monkeypatch.setattr(probe, "ProbeBusClient", lambda: created)
    if terminal_outcome == "execution-failed":
        def hook(method, _interface):
            if method == "GetUnit" and manager.service is not None:
                manager.service["ExecMainStatus"] = 203
        manager.hook = hook
    original = adapter.run()
    assert client == [created]
    assert original.outcome == terminal_outcome and original.terminal_observed
    assert original.create_outcome == "pending" and not original.job
    assert not original.reference_released and not original.client_closed
    created.deliver_create_reply()
    recovered = adapter.recover()
    assert recovered.outcome == terminal_outcome and not recovered.executed
    assert recovered.create_outcome == "replied" and recovered.job.endswith("/42")
    assert recovered.reference_released and recovered.client_closed
    assert manager.sender_calls.count("StartTransientUnit") == 1


def test_late_collision_closes_sender_without_unit_inspection_or_promotion(
        environment, monkeypatch):
    manager, _ = environment
    manager.create_error = probe.UNIT_EXISTS
    adapter = probe.ExecutionProbe(manager)
    created = Client(manager)
    created.hold_reply = True
    monkeypatch.setattr(probe, "ProbeBusClient", lambda: created)
    original = adapter.run()
    assert original.outcome == "observation-timeout"
    assert original.create_outcome == "pending" and created.close_calls == 0
    calls = len(manager.calls)
    created.deliver_create_reply()
    recovered = adapter.recover()
    assert recovered.outcome == original.outcome and not recovered.executed
    assert recovered.create_outcome == "collision" and recovered.client_closed
    assert len(manager.calls) == calls and "UnrefUnit" not in manager.sender_calls


def test_interrupted_create_poll_retains_same_request_for_recovery(environment, monkeypatch):
    manager, _ = environment
    adapter = probe.ExecutionProbe(manager)
    created = Client(manager)
    created.hold_reply = True
    interrupted = True

    def interrupt_once():
        nonlocal interrupted
        if interrupted:
            interrupted = False
            raise KeyboardInterrupt

    created.poll_hook = interrupt_once
    monkeypatch.setattr(probe, "ProbeBusClient", lambda: created)
    with pytest.raises(KeyboardInterrupt):
        adapter.run()
    assert adapter.pending.create_outcome == "pending"
    assert not adapter.pending.reference_released and created.close_calls == 0
    created.deliver_create_reply()
    recovered = adapter.recover()
    assert recovered.create_outcome == "replied" and recovered.job.endswith("/42")
    assert recovered.cleanup_complete and not recovered.executed
    assert manager.sender_calls.count("StartTransientUnit") == 1


def test_successive_settled_runs_use_fresh_senders(environment):
    manager, _ = environment
    adapter = probe.ExecutionProbe(manager)
    first, second = adapter.run(), adapter.run()
    assert first.outcome == second.outcome == "identity-unproven"
    assert first.cleanup_complete and second.cleanup_complete and first.unit != second.unit
    assert not first.executed and not second.executed
    assert len(manager.clients) == 2
    assert all(client.connection is None and client.close_calls == 1 for client in manager.clients)


def test_unavailable_sender_never_falls_back_to_observer(environment):
    manager, _ = environment
    manager.collect = False
    adapter = probe.ExecutionProbe(manager)
    adapter.run()
    manager.clients[0].connection = None
    original_calls = len(manager.sender_calls)
    recovered = adapter.recover()
    assert not recovered.cleanup_complete and adapter.pending is recovered
    assert len(manager.sender_calls) == original_calls
