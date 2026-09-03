"""Real Gio dispatch tests on python-dbusmock's private buses."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from gi.repository import Gio, GLib

from oh_no_parent_control.adapters import CallerCredentials
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
from oh_no_parent_control.logs import DailyLogWriter
from oh_no_parent_control.preferences import default_preferences
from oh_no_parent_control.service import (
    BUS_NAME,
    INTERFACE,
    OBJECT_PATH,
    Service,
    ServiceDependencies,
)


DBUS_NAME = "org.freedesktop.DBus"
DBUS_PATH = "/org/freedesktop/DBus"
DBUS_INTERFACE = "org.freedesktop.DBus"
CONNECTION_FLAGS = (
    Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
    | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION
)
CALL_TIMEOUT_MS = 3_000


def open_bus(address):
    return Gio.DBusConnection.new_for_address_sync(
        address, CONNECTION_FLAGS, None, None,
    )


def request_name(connection):
    reply = connection.call_sync(
        DBUS_NAME,
        DBUS_PATH,
        DBUS_INTERFACE,
        "RequestName",
        GLib.Variant("(su)", (BUS_NAME, 0)),
        GLib.VariantType.new("(u)"),
        Gio.DBusCallFlags.NONE,
        CALL_TIMEOUT_MS,
        None,
    )
    assert reply.unpack() == (1,)


def release_name(connection):
    connection.call_sync(
        DBUS_NAME,
        DBUS_PATH,
        DBUS_INTERFACE,
        "ReleaseName",
        GLib.Variant("(s)", (BUS_NAME,)),
        GLib.VariantType.new("(u)"),
        Gio.DBusCallFlags.NONE,
        CALL_TIMEOUT_MS,
        None,
    )


def begin_call(connection, method, parameters=None, reply_signature=None,
               cancellable=None):
    state = {"done": False}

    def completed(source, result, _user_data):
        try:
            state["result"] = source.call_finish(result)
        except GLib.Error as error:
            state["error"] = error
        finally:
            state["done"] = True

    connection.call(
        BUS_NAME,
        OBJECT_PATH,
        INTERFACE,
        method,
        parameters,
        GLib.VariantType.new(reply_signature) if reply_signature else None,
        Gio.DBusCallFlags.NONE,
        CALL_TIMEOUT_MS,
        cancellable,
        completed,
        None,
    )
    return state


def spin_until(predicate, timeout=3):
    context = GLib.MainContext.default()
    deadline = time.monotonic() + timeout
    while not predicate():
        while context.pending():
            context.iteration(False)
        if time.monotonic() >= deadline:
            raise AssertionError("timed out waiting for GLib event")
        time.sleep(0.001)


def call(connection, method, parameters=None, reply_signature=None):
    state = begin_call(connection, method, parameters, reply_signature)
    spin_until(lambda: state["done"])
    if "error" in state:
        raise state["error"]
    return state["result"]


class RecordingAccounts:
    def __init__(self):
        self.sync_count = 0

    def sync_execution_policy(self):
        self.sync_count += 1


class RecordingBroker:
    def __init__(self):
        self.behaviors = {}
        self.calls = []
        self.preferences = default_preferences()

    def _invoke(self, name, default, *args):
        self.calls.append((name, args))
        behavior = self.behaviors.get(name, default)
        if isinstance(behavior, BaseException):
            raise behavior
        return behavior(*args) if callable(behavior) else behavior

    def refresh_enabled_extensions(self):
        return self._invoke("refresh_enabled_extensions", (),)

    def clear_live_session_runtime_caps(self):
        return self._invoke("clear_live_session_runtime_caps", (),)

    def list_managed_users(self, caller_uid):
        return self._invoke(
            "list_managed_users",
            (UserAccount(1100, "child", "[Child user]", False, False, True,
                         icon_file="/icon.png"),),
            caller_uid,
        )

    def list_approvers(self, caller_uid):
        return self._invoke(
            "list_approvers",
            (UserAccount(1200, "admin", "[Administrator]", True, False, True,
                         icon_file="/admin.png"),),
            caller_uid,
        )

    def get_own_account(self, caller_uid):
        return self._invoke(
            "get_own_account",
            UserAccount(1100, "child", "[Child user]", False, False, True,
                        icon_file="/icon.png"),
            caller_uid,
        )

    def request_access(self, *args):
        return self._invoke("request_access", ("kiosk-correlation", "approved"), *args)

    def request_own_access(self, *args):
        return self._invoke(
            "request_own_access", ("child-correlation", "approved", 300), *args,
        )

    def get_preferences(self, *args):
        return self._invoke("get_preferences", self.preferences, *args)

    def list_applications(self, *args):
        return self._invoke("list_applications", ({
            "id": "example.desktop",
            "name": "Example",
            "description": "Fixture application",
            "icon": "example",
            "targets": ("/usr/bin/example",),
            "suggested_patterns": ("/usr/bin/example-*",),
        },), *args)

    def get_time_status(self, *args):
        return self._invoke("get_time_status", SimpleNamespace(
            daily_allowance_remaining_seconds=120,
            one_time_grant_remaining_seconds=60,
            additional_one_time_grant_seconds=30,
            calculated_active_extension_seconds=150,
        ), *args)

    def calculate_remaining_time(self, *args):
        return self._invoke("calculate_remaining_time", 150, *args)

    def calculate_own_remaining_time(self, *args):
        return self._invoke("calculate_own_remaining_time", 120, *args)

    def prepare_own_session(self, *args):
        return self._invoke("prepare_own_session", True, *args)

    def set_preferences(self, *args):
        return self._invoke("set_preferences", {"saved": "preferences"}, *args)

    def update_request_preferences(self, *args):
        return self._invoke("update_request_preferences", {"saved": "request"}, *args)

    def set_request_muted(self, *args):
        return self._invoke("set_request_muted", {"saved": "muted"}, *args)

    def set_parent_control(self, *args):
        return self._invoke("set_parent_control", {"saved": "parent-control"}, *args)

    def revoke_one_time_grant(self, *args):
        return self._invoke("revoke_one_time_grant", None, *args)

    def authorize_log_component(self, *args):
        return self._invoke("authorize_log_component", None, *args)


@pytest.fixture
def private_service(dbusmock_system, dbusmock_session, tmp_path):
    server = open_bus(dbusmock_system.address)
    request_name(server)
    broker = RecordingBroker()
    accounts = RecordingAccounts()
    factory_arguments = {}

    def broker_factory(*args, **kwargs):
        factory_arguments["args"] = args
        factory_arguments["kwargs"] = kwargs
        return broker

    dependencies = ServiceDependencies(
        credentials=CallerCredentials(server),
        accounts=accounts,
        config_loader=lambda: object(),
        authorizer=object(),
        preferences=object(),
        extensions=object(),
        timer_usage=object(),
        application_catalog=lambda _user: (),
        running_apps=object(),
        monotonic=lambda: 12.5,
        now=lambda: datetime(2026, 9, 3, tzinfo=timezone.utc),
        broker_factory=broker_factory,
        policy_rescan_interval_seconds=None,
    )
    writer = DailyLogWriter(tmp_path / "logs", now=dependencies.now)
    service = Service(server, writer, dependencies=dependencies)
    service.register()
    client = open_bus(dbusmock_system.address)
    harness = SimpleNamespace(
        server=server,
        client=client,
        service=service,
        broker=broker,
        accounts=accounts,
        factory_arguments=factory_arguments,
        writer=writer,
        system_bus=dbusmock_system,
        session_bus=dbusmock_session,
    )
    try:
        yield harness
    finally:
        if not client.is_closed():
            client.close_sync(None)
        service.close()
        release_name(server)
        server.close_sync(None)


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
        ("PrepareOwnSession", None, "(b)", (True,)),
        ("SetPreferences", GLib.Variant("(us)", (1100, preferences_json)),
         "(s)", None),
        ("UpdateRequestPreferences",
         GLib.Variant("(usdbu)", (1100, "300", 0.5, False, 1200)),
         "(s)", None),
        ("SetRequestMuted", GLib.Variant("(usb)", (1100, "child", True)),
         "(s)", None),
        ("SetParentControl", GLib.Variant("(ubu)", (1100, True, 60)),
         "(s)", None),
        ("RevokeOneTimeGrant", GLib.Variant("(u)", (1100,)), "()", ()),
        ("LogEvent", GLib.Variant("(sss)", ("child", "INFO", "safe event")),
         "()", ()),
    )

    for method, parameters, reply_signature, expected in cases:
        result = call(client, method, parameters, reply_signature)
        assert result.get_type_string() == reply_signature
        unpacked = result.unpack()
        if method == "GetPreferences":
            assert json.loads(unpacked[0]) == default_preferences()
        elif method in {
            "SetPreferences", "UpdateRequestPreferences", "SetRequestMuted",
            "SetParentControl",
        }:
            assert isinstance(json.loads(unpacked[0]), dict)
        else:
            assert unpacked == expected

    forwarded_log = (
        private_service.writer.root / "child" / "2026-09-03.log"
    ).read_text(encoding="utf-8")
    assert "safe event" in forwarded_log
    assert str(os.getuid()) not in forwarded_log


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
