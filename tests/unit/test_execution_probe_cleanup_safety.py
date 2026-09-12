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
        args = parameters.unpack()
        self.calls.append((destination, method, args, timeout))
        assert 0 < timeout <= probe.CALL_MS
        assert flags == Gio.DBusCallFlags.NONE
        assert cancellable is None
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


@pytest.fixture
def environment(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(probe.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(probe.time, "sleep", clock.sleep)
    manager = Manager()
    return manager, clock


def test_fast_exit_evidence_is_retained_before_collection(environment):
    manager, _ = environment
    result = probe.ExecutionProbe(manager).run()
    assert result.executed and result.cleanup_complete and result.reference_released
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
    assert [call[1] for call in manager.calls] == ["GetNameOwner", "StartTransientUnit"]


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
    assert result.reference_released


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
    assert result.reference_released and manager.unit is not None
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
    assert result.executed and reads == 4


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
    assert manager.reference  # A reference appeared after the first release.
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
    assert recovered.outcome == "recovered-cleanup" and adapter.pending is None
    assert original.outcome == "executed" and not original.cleanup_complete


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
    assert result.executed and adapter.pending is None
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
