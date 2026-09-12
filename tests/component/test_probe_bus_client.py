"""Real Gio client isolation and cancellation; no host system-bus access."""

from concurrent.futures import ThreadPoolExecutor
import socket
import time

from gi.repository import Gio, GLib
import pytest

from oh_no_parent_control import execution_probe
from oh_no_parent_control.execution_probe import ExecutionProbe, ProbeBusClient
from tests.support.dbus import DBUS_NAME, DBUS_PATH, DBUS_INTERFACE, open_bus, spin_until


def has_owner(observer, name):
    return observer.call_sync(
        DBUS_NAME, DBUS_PATH, DBUS_INTERFACE, "NameHasOwner",
        GLib.Variant("(s)", (name,)), GLib.VariantType.new("(b)"),
        0, 1000, None).unpack()[0]


def finish_close(client):
    deadline = time.monotonic() + 5
    while not client.close():
        assert time.monotonic() < deadline, "private client cleanup did not complete"


@pytest.mark.parametrize("reply", ["success", "collision", "error"])
def test_late_create_reply_is_retained_on_real_owned_connection(
        dbusmock_system, monkeypatch, caplog, reply):
    # Hold a real method invocation, without launching a unit or another worker.
    server = open_bus(dbusmock_system.address)
    observer = open_bus(dbusmock_system.address)
    client = ProbeBusClient()
    invocations = []
    info = Gio.DBusNodeInfo.new_for_xml(
        '<node><interface name="org.freedesktop.systemd1.Manager">'
        '<method name="StartTransientUnit"><arg type="s" direction="in"/>'
        '<arg type="s" direction="in"/><arg type="a(sv)" direction="in"/>'
        '<arg type="a(sa(sv))" direction="in"/>'
        '<arg type="o" direction="out"/></method></interface></node>')
    registration = 0
    try:
        registration = server.register_object_with_closures2(
            execution_probe.SYSTEMD_PATH, info.interfaces[0],
            lambda _c, _s, _p, _i, _m, _a, invocation: invocations.append(invocation),
            None, None)
        assert client.open(dbusmock_system.address)
        name = client.connection.get_unique_name()
        monkeypatch.setattr(execution_probe, "CLEANUP_SECONDS", 0.05)
        client.start_create(server.get_unique_name(), "onpc-test.service", "ONPC test")
        spin_until(lambda: bool(invocations))
        assert client.poll_create() is None
        assert not client.close() and has_owner(observer, name)
        assert client.connection is not None and not client.cleanup_complete
        invocation = invocations.pop()
        if reply == "success":
            invocation.return_value(GLib.Variant("(o)", ("/org/freedesktop/systemd1/job/42",)))
        else:
            invocation.return_dbus_error(
                execution_probe.UNIT_EXISTS if reply == "collision" else "org.test.Error",
                "secret payload")
        deadline = time.monotonic() + 3
        with caplog.at_level("INFO"):
            while client.poll_create() is None:
                assert time.monotonic() < deadline
        result = client.create_reply
        assert result.outcome == {"success": "replied", "collision": "collision",
                                  "error": "uncertain"}[reply]
        assert bool(result.job) == (reply == "success")
        assert "secret payload" not in caplog.text
        finish_close(client)
        spin_until(lambda: not has_owner(observer, name))
        assert has_owner(observer, observer.get_unique_name())
    finally:
        for invocation in invocations:
            invocation.return_dbus_error("org.test.Cleanup", "test cleanup")
        # Only test-owned connections exist; closing the fake manager completes
        # any outstanding call with an error if an assertion interrupted delivery.
        if registration:
            server.unregister_object(registration)
        server.close_sync(None)
        deadline = time.monotonic() + 3
        while client._create_pending:
            client.poll_create()
            assert time.monotonic() < deadline
        finish_close(client)
        observer.close_sync(None)


def test_execution_probe_collects_collision_reply_before_closing_owned_sender(
        dbusmock_system, monkeypatch):
    server = open_bus(dbusmock_system.address)
    observer = open_bus(dbusmock_system.address)
    clients = []
    registration = 0

    class RecordedClient(ProbeBusClient):
        def __init__(self):
            super().__init__()
            clients.append(self)

    info = Gio.DBusNodeInfo.new_for_xml(
        '<node><interface name="org.freedesktop.systemd1.Manager">'
        '<method name="StartTransientUnit"><arg type="s" direction="in"/>'
        '<arg type="s" direction="in"/><arg type="a(sv)" direction="in"/>'
        '<arg type="a(sa(sv))" direction="in"/>'
        '<arg type="o" direction="out"/></method></interface></node>')
    try:
        server.call_sync(
            DBUS_NAME, DBUS_PATH, DBUS_INTERFACE, "RequestName",
            GLib.Variant("(su)", (execution_probe.SYSTEMD_NAME, 0)),
            GLib.VariantType.new("(u)"), Gio.DBusCallFlags.NONE, 3000, None)
        registration = server.register_object_with_closures2(
            execution_probe.SYSTEMD_PATH, info.interfaces[0],
            lambda _c, _s, _p, _i, _m, _a, invocation:
            invocation.return_dbus_error(execution_probe.UNIT_EXISTS, "occupied"),
            None, None)
        monkeypatch.setenv("DBUS_SYSTEM_BUS_ADDRESS", dbusmock_system.address)
        monkeypatch.setattr(execution_probe, "ProbeBusClient", RecordedClient)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(ExecutionProbe(observer).run)
            spin_until(future.done)
            result = future.result()
        assert result.outcome == result.create_outcome == "collision"
        assert result.cleanup_complete and result.client_closed and not result.job
        assert clients[0].cleanup_complete and not observer.is_closed()
    finally:
        if registration:
            server.unregister_object(registration)
        for client in clients:
            finish_close(client)
        server.close_sync(None)
        observer.close_sync(None)


def test_owned_connection_disappears_without_closing_observer(dbusmock_system):
    observer = open_bus(dbusmock_system.address)
    client = ProbeBusClient()
    try:
        assert client.open(dbusmock_system.address)
        name = client.connection.get_unique_name()
        assert name != observer.get_unique_name() and has_owner(observer, name)
        finish_close(client)
        deadline = time.monotonic() + 3
        while has_owner(observer, name):
            assert time.monotonic() < deadline
            time.sleep(0.01)
        assert has_owner(observer, observer.get_unique_name())
        assert client.cleanup_complete and not observer.is_closed()
    finally:
        finish_close(client)
        observer.close_sync(None)


def test_connection_refusal_finishes_without_exposing_address(tmp_path, caplog):
    client = ProbeBusClient()
    address = f"unix:path={tmp_path / 'absent.sock'}"
    try:
        with caplog.at_level("INFO"):
            assert not client.open(address)
            finish_close(client)
        assert str(tmp_path) not in caplog.text and client.cleanup_complete
    finally:
        finish_close(client)


def test_stalled_authentication_is_cancelled_and_socket_is_closed(tmp_path, monkeypatch):
    # Explicitly own the listening/accepted sockets; never discover a process.
    from oh_no_parent_control import execution_probe
    monkeypatch.setattr(execution_probe, "CLEANUP_SECONDS", 0.15)
    address = tmp_path / "silent.sock"
    client = ProbeBusClient()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(address))
        listener.listen(1)
        listener.settimeout(3)
        try:
            started = time.monotonic()
            assert not client.open(f"unix:path={address}")
            assert time.monotonic() - started < 2
            with listener.accept()[0] as peer:
                peer.settimeout(3)
                finish_close(client)
                # Authentication bytes may precede EOF; retain no payload.
                while peer.recv(4096):
                    pass
            assert client.cleanup_complete
        finally:
            finish_close(client)


@pytest.mark.parametrize("failure", ["missing-manager", "wrong-bus", "refused-socket"])
def test_probe_pre_dispatch_failure_closes_owned_client_and_preserves_observer(
        dbusmock_system, dbusmock_session, tmp_path, monkeypatch, failure):
    observer = open_bus(dbusmock_system.address)
    names = []
    clients = []

    class RecordedClient(ProbeBusClient):
        def __init__(self):
            super().__init__()
            clients.append(self)

        def open(self, address):
            ready = super().open(address)
            if ready:
                names.append(self.connection.get_unique_name())
                assert self.connection != observer
            return ready

    address = dbusmock_system.address
    if failure == "wrong-bus":
        address = dbusmock_session.address
    elif failure == "refused-socket":
        address = f"unix:path={tmp_path / 'absent-probe.sock'}"
    # Exercise the real public SYSTEM address resolver against an isolated bus.
    monkeypatch.setenv("DBUS_SYSTEM_BUS_ADDRESS", address)
    monkeypatch.setattr(execution_probe, "ProbeBusClient", RecordedClient)
    sender_observer = open_bus(address) if failure == "wrong-bus" else observer
    adapter = ExecutionProbe(observer)
    try:
        result = adapter.run()
        assert result.outcome == "transport-failed" and not result.executed
        assert result.cleanup_complete and result.client_closed
        assert not result.manager and not result.job and not result.reference_released
        assert adapter.pending is None and clients[0].cleanup_complete
        deadline = time.monotonic() + 3
        while any(has_owner(sender_observer, name) for name in names):
            assert time.monotonic() < deadline
            time.sleep(0.01)
        assert has_owner(observer, observer.get_unique_name()) and not observer.is_closed()
    finally:
        for client in clients:
            finish_close(client)
        if sender_observer != observer:
            sender_observer.close_sync(None)
        observer.close_sync(None)
