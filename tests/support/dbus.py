"""Private D-Bus broker harness and recording adapters for component tests."""

from datetime import datetime, timezone
from contextlib import ExitStack, contextmanager
import time
from types import SimpleNamespace

import pytest
from gi.repository import Gio, GLib

from oh_no_parent_control.adapters import CallerCredentials
from oh_no_parent_control.core import UserAccount
from oh_no_parent_control.logs import DailyLogWriter
from oh_no_parent_control.preferences import default_preferences
from oh_no_parent_control.service import (
    BUS_NAME, INTERFACE, OBJECT_PATH, Service, ServiceDependencies,
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


def close_connection(connection):
    if not connection.is_closed():
        connection.close_sync(None)


@contextmanager
def broker_service(dbusmock_system, dbusmock_session, tmp_path):
    """Own each acquired connection/service even when setup stops before yield."""
    with ExitStack() as owned:
        server = open_bus(dbusmock_system.address)
        owned.callback(close_connection, server)
        request_name(server)
        owned.callback(release_name, server)
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
        owned.callback(service.close)
        service.register()
        client = open_bus(dbusmock_system.address)
        owned.callback(close_connection, client)
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
        yield harness


@pytest.fixture
def private_service(dbusmock_system, dbusmock_session, tmp_path):
    with broker_service(dbusmock_system, dbusmock_session, tmp_path) as harness:
        yield harness
