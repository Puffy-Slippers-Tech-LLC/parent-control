"""Real Gio dispatch tests on python-dbusmock's private buses."""

from __future__ import annotations

import json
import logging
import os
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
