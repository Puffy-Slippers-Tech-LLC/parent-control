"""Real Gio dispatch tests on python-dbusmock's private buses."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import pwd
import subprocess
import threading
from datetime import datetime, timezone

import pytest
from gi.repository import Gio, GLib

from oh_no_parent_control.core import (
    AccessDenied,
    BackendFailure,
    BrokerError,
    Busy,
    InvalidRequest,
    RateLimited,
    RollbackFailure,
    UserAccount,
)
from oh_no_parent_control.preferences import default_preferences
from oh_no_parent_control.extension_manager import ExtensionManager, UUID
from oh_no_parent_control.extension_monitor import ExtensionMonitor
from oh_no_parent_control import child_bus
from oh_no_parent_control.service import (
    BUS_NAME,
    INTERFACE,
    OBJECT_PATH,
    Service,
    ServiceDependencies,
)


from tests.support.dbus import (
    DBUS_NAME, DBUS_PATH, DBUS_INTERFACE, CALL_TIMEOUT_MS,
    open_bus, begin_call, spin_until, call, private_service,
)


def test_child_extension_monitor_recovers_public_signals_and_reports_failure_once(dbusmock_system, dbusmock_session):
    """Exercise actual Gio signal callbacks on the monitor's private context."""
    from unittest import mock
    from tests.support.broker import Accounts, Preferences, make_broker

    server, system = open_bus(dbusmock_session.address), open_bus(dbusmock_system.address)
    values = {"state": 1, "enabled": True, "configured": True, "errors": []}
    node = Gio.DBusNodeInfo.new_for_xml('''<node><interface name="org.gnome.Shell.Extensions">
      <method name="GetExtensionInfo"><arg type="s" direction="in"/><arg type="a{sv}" direction="out"/></method>
      <method name="GetExtensionErrors"><arg type="s" direction="in"/><arg type="as" direction="out"/></method>
      <property name="UserExtensionsEnabled" type="b" access="read"/>
      <signal name="ExtensionStateChanged"><arg type="s"/><arg type="a{sv}"/></signal>
    </interface></node>''')

    def method(_connection, _sender, _path, _interface, name, parameters, invocation):
        assert parameters.unpack() == (UUID,)
        if name == "GetExtensionErrors":
            invocation.return_value(GLib.Variant("(as)", (values["errors"],)))
            return
        invocation.return_value(GLib.Variant("(a{sv})", ({
            "state": GLib.Variant("d", values["state"]),
            "enabled": GLib.Variant("b", values["configured"]),
            "error": GLib.Variant("s", "")},)))

    identifier = server.register_object_with_closures2("/org/gnome/Shell", node.interfaces[0], method,
        lambda *_args: GLib.Variant("b", values["enabled"]), None)

    def name(method_name, signature, arguments):
        return server.call_sync(DBUS_NAME, DBUS_PATH, DBUS_INTERFACE, method_name,
            GLib.Variant(signature, arguments), None, Gio.DBusCallFlags.NONE, CALL_TIMEOUT_MS, None)

    def signal_state():
        server.emit_signal(None, "/org/gnome/Shell", "org.gnome.Shell.Extensions", "ExtensionStateChanged",
            GLib.Variant("(sa{sv})", (UUID, {"state": GLib.Variant("d", values["state"])})))

    name("RequestName", "(su)", ("org.gnome.Shell", 0))
    accounts, preferences = Accounts(), Preferences()
    preferences.values[1001]["parent_control_enabled"] = True
    # One child on this private bus; no host session or product action is used.
    accounts.users = {1001: accounts.users[1001]}
    manager = ExtensionManager()
    activations, reports = [], []

    def enable(uid, enabled, *, recover_global_switch):
        activations.append((uid, enabled, recover_global_switch))
        values.update(state=1, enabled=True, configured=True)

    monitor = None
    account = pwd.getpwuid(os.getuid())
    popen = subprocess.Popen

    def private_helper(*args, **kwargs):
        # This unprivileged host test keeps its own credentials. Production's
        # credential-drop arguments are covered in the transport unit owner;
        # real cross-UID authentication belongs to installed acceptance.
        assert kwargs.pop("user") == account.pw_uid
        assert kwargs.pop("group") == account.pw_gid
        assert kwargs.pop("extra_groups") == ()
        return popen(*args, **kwargs)

    try:
        with (mock.patch.object(manager, "session_bus_address", return_value=dbusmock_session.address),
              mock.patch.object(manager, "_account", return_value=(account, None)),
              mock.patch.object(child_bus, "HELPER_PATH", str(Path(child_bus.__file__).resolve())),
              mock.patch.object(child_bus.subprocess, "Popen", side_effect=private_helper),
              mock.patch.object(manager, "set_enabled", side_effect=enable),
              mock.patch.object(manager, "report_failure", side_effect=reports.append)):
            monitor = ExtensionMonitor(make_broker(accounts=accounts, preferences=preferences), manager, system)
            spin_until(lambda: 1001 in monitor.watches and monitor.watches[1001].shell_present)
            connection = monitor.watches[1001].connection
            identity = connection.call_sync(DBUS_NAME, DBUS_PATH, DBUS_INTERFACE,
                "GetConnectionUnixUser", GLib.Variant("(s)", (connection.get_unique_name(),)),
                GLib.VariantType.new("(u)"), Gio.DBusCallFlags.NONE, CALL_TIMEOUT_MS, None)
            assert identity.unpack() == (account.pw_uid,)
            values["state"] = 2
            for _ in range(20):
                signal_state()
            spin_until(lambda: len(activations) == 1)
            assert activations == [(1001, True, True)]
            values["enabled"] = False
            server.emit_signal(None, "/org/gnome/Shell", "org.freedesktop.DBus.Properties", "PropertiesChanged",
                GLib.Variant("(sa{sv}as)", ("org.gnome.Shell.Extensions",
                    {"UserExtensionsEnabled": GLib.Variant("b", False)}, [])))
            spin_until(lambda: len(activations) == 2)
            # A quick ordinary logout after recovery is not an extension error.
            name("ReleaseName", "(s)", ("org.gnome.Shell",))
            spin_until(lambda: not monitor.watches[1001].shell_present)
            # During async import GNOME exposes ERROR with no error history.
            # The replacement Shell must finish loading without a report.
            values["state"] = 3
            name("RequestName", "(su)", ("org.gnome.Shell", 0))
            spin_until(lambda: monitor.watches[1001].failures > 0)
            assert monitor.watches[1001].healthy_since == 0
            failures = monitor.watches[1001].failures
            values["state"] = 6
            signal_state()
            spin_until(lambda: monitor.watches[1001].failures > failures)
            assert reports == []
            assert not monitor.watches[1001].failed
            values["state"] = 1
            signal_state()
            spin_until(lambda: monitor.watches[1001].failures == 0)
            assert reports == []
            assert len(activations) == 2
            preferences.values[1001]["parent_control_enabled"] = False
            values["state"] = 2
            checked = monitor.watches[1001].next_check
            signal_state()
            spin_until(lambda: monitor.watches[1001].next_check > checked)
            assert len(activations) == 2
            preferences.values[1001]["parent_control_enabled"] = True
            # A never-loaded individually disabled extension remains
            # INITIALIZED even though the global extensions switch is on.
            values.update(state=6, configured=False)
            signal_state()
            spin_until(lambda: len(activations) == 3)
            values["state"] = 3
            # A recorded exception is real even when its message is empty.
            values["errors"] = [""]
            signal_state()
            spin_until(lambda: reports == [1001])
            values["state"] = 2
            checked = monitor.watches[1001].next_check
            for _ in range(20):
                signal_state()
            spin_until(lambda: monitor.watches[1001].next_check > checked)
            assert len(activations) == 3
            assert reports == [1001]
            # Actual NameOwnerChanged delivery, including its callback arity.
            name("ReleaseName", "(s)", ("org.gnome.Shell",))
            spin_until(lambda: not monitor.watches[1001].shell_present)
            values["state"] = 1
            name("RequestName", "(su)", ("org.gnome.Shell", 0))
            spin_until(lambda: monitor.watches[1001].shell_present)
            monitor.close()
            assert not monitor._thread.is_alive()
            assert monitor.watches[1001].connection is None
            monitor = None
            instant = ExtensionMonitor(make_broker(accounts=accounts, preferences=preferences), manager, system)
            instant.close()
            assert not instant._thread.is_alive()
    finally:
        if monitor is not None:
            monitor.close()
        server.unregister_object(identifier)
        server.close_sync(None)
        system.close_sync(None)


def test_monitor_shutdown_drains_removed_watch_hello_after_delayed_completion(dbusmock_system):
    """Removed child watches retain their native Gio cleanup owner at shutdown."""
    import socket
    import time
    from types import SimpleNamespace
    from unittest import mock

    system = open_bus(dbusmock_system.address)
    transport, peer = socket.socketpair()
    broker, manager = mock.Mock(), mock.Mock()
    uids = [1001]
    broker.extension_watch_uids.side_effect = lambda: uids[:]
    manager.session_bus_address.return_value = "unix:path=/unused"
    manager._account.return_value = (SimpleNamespace(pw_uid=1001, pw_gid=1001), None)
    attempts, completions = [], []

    def stalled_connection(account, address, context, callback):
        attempt = child_bus.connect_child_bus(account, address, context, callback, timeout=10)
        attempts.append(attempt)
        attempt.process = mock.Mock()
        attempt.process.poll.return_value = 0
        attempt.guardian = socket.socket(fileno=os.dup(transport.fileno()))
        native = Gio.Socket.new_from_fd(os.dup(transport.fileno()))
        attempt.stream = native.connection_factory_create_connection()
        attempt._hello_pending = True

        def delayed(gio_source, result, *_args):
            source = GLib.timeout_source_new(1200)

            def complete(*_args):
                attempt._connected(gio_source, result)
                completions.append(True)
                return GLib.SOURCE_REMOVE

            source.set_callback(complete)
            source.attach(context)

        Gio.DBusConnection.new(attempt.stream, None, Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None, attempt.cancellable, delayed)
        return attempt

    monitor = None
    try:
        with mock.patch("oh_no_parent_control.extension_monitor.connect_child_bus", side_effect=stalled_connection):
            monitor = ExtensionMonitor(broker, manager, system)
            spin_until(lambda: attempts and attempts[0]._hello_pending)
            uids.clear()
            monitor._later(0, monitor._refresh)
            spin_until(lambda: not monitor.watches)
            assert attempts[0].pending
            assert len(monitor._attempts) == 1
            started = time.monotonic()
            monitor.close()
            assert time.monotonic() - started >= 1
            assert not monitor._thread.is_alive()
            assert completions == [True]
            assert not attempts[0].pending
            assert attempts[0].stream is None
            assert monitor._attempts == {}
            manager.set_enabled.assert_not_called()
            manager.report_failure.assert_not_called()
            broker.reconcile_enabled_child.assert_not_called()
    finally:
        if monitor is not None:
            monitor.close()
        transport.close()
        peer.close()
        system.close_sync(None)


def test_service_composition_receives_injected_adapters_and_clocks(private_service):
    harness = private_service
    args = harness.factory_arguments["args"]
    kwargs = harness.factory_arguments["kwargs"]

    assert args[2] is harness.accounts
    assert kwargs["monotonic"]() == 12.5
    assert kwargs["now"]() == datetime(2026, 9, 3, tzinfo=timezone.utc)
    assert harness.accounts.sync_count == 1


def test_every_public_method_uses_real_dbus_signatures_and_serialization(private_service):
    client = private_service.client
    preferences_json = json.dumps(default_preferences())
    cases = (
        ("GetOwnLanguage", None, "(s)", ("fr",)),
        ("SetOwnLanguage", GLib.Variant("(s)", ("de",)), "(s)", ("de",)),
        ("GetChildLanguage", GLib.Variant("(u)", (1100,)), "(s)", ("fr",)),
        ("SetChildLanguage", GLib.Variant("(us)", (1100, "de")), "(s)", ("de",)),
        ("ListManagedUsers", None, "(a(uss))", ([(1100, "[Child user]", "/icon.png")],)),
        ("ListApprovers", None, "(a(uss))", ([(1200, "[Administrator]", "/admin.png")],)),
        ("GetOwnAccount", None, "(uss)", (1100, "[Child user]", "/icon.png")),
        ("RequestAccess", GLib.Variant("(uuub)", (1100, 1200, 300, False)),
         "(ss)", ("kiosk-correlation", "approved")),
        ("RequestOwnAccess", GLib.Variant("(uub)", (1200, 300, True)),
         "(ssu)", ("child-correlation", "approved", 300)),
        ("GetPreferences", GLib.Variant("(u)", (1100,)), "(s)", None),
        ("ListApplications", GLib.Variant("(u)", (1100,)), "(a(ssssasas))",
         ([("example.desktop", "Example", "Fixture application", "example",
            ["/usr/bin/example"], ["/usr/bin/example-*"])],)),
        ("GetTimeStatus", GLib.Variant("(uu)", (1100, 30)), "(uuuu)",
         (120, 60, 30, 150)),
        ("CalculateRemainingTime", GLib.Variant("(uuuu)", (1100, 120, 60, 30)),
         "(u)", (150,)),
        ("CalculateOwnRemainingTime", GLib.Variant("(u)", (120,)), "(u)", (120,)),
        ("CalculateOwnDeadline", GLib.Variant("(tt)", (1_800_000_000_000_000, 0)),
         "(t)", (132_500_000,)),
        ("PrepareOwnSession", None, "(b)", (True,)),
        ("SetPreferences", GLib.Variant("(us)", (1100, preferences_json)),
         "(s)", None),
        ("UpdateRequestPreferences",
         GLib.Variant("(usdbu)", (1100, "300", 0.5, False, 1200)),
         "(s)", None),
        ("UpdateRequestPreferencesWithUnit",
         GLib.Variant("(usdbus)", (1100, "custom", 90.0, False, 1200, "hours")),
         "(s)", None),
        ("SetRequestMuted", GLib.Variant("(usb)", (1100, "child", True)),
         "(s)", None),
        ("SetParentControl", GLib.Variant("(ubu)", (1100, True, 60)),
         "(s)", None),
        ("RevokeOneTimeGrant", GLib.Variant("(u)", (1100,)), "()", ()),
        ("LogEvent", GLib.Variant("(sss)", ("child", "INFO",
         '{"v":1,"event":"child.enabled","fields":{},"operation":0}')),
         "()", ()),
    )

    for method, parameters, reply_signature, expected in cases:
        result = call(client, method, parameters, reply_signature)
        assert result.get_type_string() == reply_signature
        unpacked = result.unpack()
        if method == "GetPreferences":
            assert json.loads(unpacked[0]) == default_preferences()
        elif method in {
            "SetPreferences", "UpdateRequestPreferences", "UpdateRequestPreferencesWithUnit", "SetRequestMuted",
            "SetParentControl",
        }:
            assert isinstance(json.loads(unpacked[0]), dict)
        else:
            assert unpacked == expected

    forwarded_log = (
        private_service.writer.root / "child" / "2026-09-03.events"
    ).read_text(encoding="utf-8")
    assert '"event":"child.enabled"' in forwarded_log
    assert '"uid"' not in forwarded_log
    assert '"source_uid"' not in forwarded_log


def test_deadline_dispatch_uses_bus_credentials_and_preserves_microseconds(private_service):
    native, timer = 1_800_000_000_123_456, 1_800_000_030_654_321
    result = call(private_service.client, "CalculateOwnDeadline",
                  GLib.Variant("(tt)", (native, timer)), "(t)")
    assert result.unpack() == (132_500_000,)
    assert ("calculate_own_deadline", (os.getuid(), native, timer)) in private_service.broker.calls
    private_service.broker.behaviors["calculate_own_deadline"] = AccessDenied("ineligible caller")
    with pytest.raises(GLib.Error) as refused:
        call(private_service.client, "CalculateOwnDeadline", GLib.Variant("(tt)", (0, 0)), "(t)")
    assert Gio.dbus_error_get_remote_error(refused.value) == AccessDenied.dbus_name


def test_malformed_json_unknown_methods_and_worker_failures_are_public_errors(
        private_service, caplog):
    client = private_service.client
    caplog.set_level(logging.INFO)
    secret = "alice /home/alice/private request-secret"

    with pytest.raises(GLib.Error) as malformed:
        call(
            client,
            "SetPreferences",
            GLib.Variant("(us)", (1100, '{"leak":"' + secret)),
            "(s)",
        )
    assert Gio.dbus_error_get_remote_error(malformed.value) == (
        f"{BUS_NAME}.Error.InvalidRequest"
    )
    assert malformed.value.message.endswith("preferences are not valid JSON")

    with pytest.raises(GLib.Error) as unknown:
        call(client, "MethodThatDoesNotExist")
    assert Gio.dbus_error_get_remote_error(unknown.value) == (
        "org.freedesktop.DBus.Error.UnknownMethod"
    )

    private_service.broker.behaviors["request_access"] = RuntimeError(secret)
    with pytest.raises(GLib.Error) as failed:
        call(
            client,
            "RequestAccess",
            GLib.Variant("(uuub)", (1100, 1200, 300, False)),
            "(ss)",
        )
    assert Gio.dbus_error_get_remote_error(failed.value) == f"{BUS_NAME}.Error.Failed"
    assert failed.value.message.endswith("service failure")

    private_service.broker.behaviors["request_access"] = InvalidRequest("request rejected")
    with pytest.raises(GLib.Error) as denied:
        call(
            client,
            "RequestAccess",
            GLib.Variant("(uuub)", (1100, 1200, 300, False)),
            "(ss)",
        )
    assert Gio.dbus_error_get_remote_error(denied.value) == (
        f"{BUS_NAME}.Error.InvalidRequest"
    )
    assert denied.value.message.endswith("request rejected")

    records = "\n".join(record.getMessage() for record in caplog.records)
    assert "stage=dispatch" in records
    assert "outcome=failed error_type=RuntimeError" in records
    assert "outcome=denied error_type=InvalidRequest" in records
    for forbidden in ("1100", "1200", "alice", "/home/alice/private", "request-secret"):
        assert forbidden not in records


@pytest.mark.parametrize(
    ("error_type", "message"),
    (
        (BrokerError, "broker operation failed"),
        (InvalidRequest, "request is invalid"),
        (AccessDenied, "request is denied"),
        (Busy, "broker is busy"),
        (RateLimited, "request is rate limited"),
        (BackendFailure, "backend operation failed"),
        (RollbackFailure, "rollback verification failed"),
    ),
)
def test_every_public_broker_error_preserves_name_and_safe_text(
        private_service, error_type, message):
    private_service.broker.behaviors["list_managed_users"] = error_type(message)

    with pytest.raises(GLib.Error) as caught:
        call(private_service.client, "ListManagedUsers", None, "(a(uss))")

    assert Gio.dbus_error_get_remote_error(caught.value) == error_type.dbus_name
    assert caught.value.message.endswith(message)


@pytest.mark.parametrize(
    ("behavior", "method", "parameters", "reply_signature"),
    (
        ("request_access", "RequestAccess",
         GLib.Variant("(uuub)", (1100, 1200, 300, False)), "(ss)"),
        ("request_own_access", "RequestOwnAccess",
         GLib.Variant("(uub)", (1200, 300, False)), "(ssu)"),
        ("prepare_own_session", "PrepareOwnSession", None, "(b)"),
    ),
)
def test_each_async_worker_translates_unexpected_exceptions(
        private_service, behavior, method, parameters, reply_signature):
    private_service.broker.behaviors[behavior] = RuntimeError("private worker detail")

    with pytest.raises(GLib.Error) as caught:
        call(private_service.client, method, parameters, reply_signature)

    assert Gio.dbus_error_get_remote_error(caught.value) == f"{BUS_NAME}.Error.Failed"
    assert caught.value.message.endswith("service failure")
    assert "private worker detail" not in caught.value.message


def test_request_workers_dispatch_concurrently(private_service):
    gate = threading.Event()
    lock = threading.Lock()
    active = 0
    maximum_active = 0

    def blocked_request(*_args):
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        gate.wait(3)
        with lock:
            active -= 1
        return "correlation", "approved"

    private_service.broker.behaviors["request_access"] = blocked_request
    arguments = GLib.Variant("(uuub)", (1100, 1200, 300, False))
    first = begin_call(private_service.client, "RequestAccess", arguments, "(ss)")
    second = begin_call(private_service.client, "RequestAccess", arguments, "(ss)")
    spin_until(lambda: maximum_active == 2)
    gate.set()
    spin_until(lambda: first["done"] and second["done"])

    assert first["result"].unpack() == ("correlation", "approved")
    assert second["result"].unpack() == ("correlation", "approved")
    assert maximum_active == 2


def test_client_cancellation_does_not_stall_service(private_service):
    started = threading.Event()
    gate = threading.Event()

    def blocked_request(*_args):
        started.set()
        gate.wait(3)
        return "correlation", "approved", 300

    private_service.broker.behaviors["request_own_access"] = blocked_request
    cancellable = Gio.Cancellable()
    state = begin_call(
        private_service.client,
        "RequestOwnAccess",
        GLib.Variant("(uub)", (1200, 300, False)),
        "(ssu)",
        cancellable,
    )
    spin_until(started.is_set)
    cancellable.cancel()
    gate.set()
    spin_until(lambda: state["done"])

    assert state["error"].matches(Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED)
    private_service.broker.behaviors.pop("request_own_access")
    assert call(private_service.client, "GetOwnAccount", None, "(uss)").unpack()[0] == 1100


def test_caller_disappearance_is_observable_and_service_survives(private_service):
    transient = open_bus(private_service.system_bus.address)
    started = threading.Event()
    gate = threading.Event()
    alive = []

    def request_with_liveness(_uid, sender, *_args):
        started.set()
        gate.wait(3)
        alive.append(private_service.factory_arguments["kwargs"]["caller_alive"](sender))
        return "correlation", "approved"

    private_service.broker.behaviors["request_access"] = request_with_liveness
    begin_call(
        transient,
        "RequestAccess",
        GLib.Variant("(uuub)", (1100, 1200, 300, False)),
        "(ss)",
    )
    spin_until(started.is_set)
    transient.close_sync(None)
    gate.set()
    spin_until(lambda: bool(alive))

    assert alive == [False]
    private_service.broker.behaviors.pop("request_access")
    assert call(private_service.client, "ListManagedUsers", None, "(a(uss))")


def test_session_and_test_system_buses_are_private_and_isolated(private_service):
    system_address = private_service.system_bus.address
    session_address = private_service.session_bus.address
    assert system_address == os.environ["DBUS_SYSTEM_BUS_ADDRESS"]
    assert session_address == os.environ["DBUS_SESSION_BUS_ADDRESS"]
    assert system_address != session_address

    session_connection = open_bus(session_address)
    try:
        reply = session_connection.call_sync(
            DBUS_NAME,
            DBUS_PATH,
            DBUS_INTERFACE,
            "NameHasOwner",
            GLib.Variant("(s)", (BUS_NAME,)),
            GLib.VariantType.new("(b)"),
            Gio.DBusCallFlags.NONE,
            CALL_TIMEOUT_MS,
            None,
        )
        assert reply.unpack() == (False,)
    finally:
        session_connection.close_sync(None)
