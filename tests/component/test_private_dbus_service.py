"""Real Gio dispatch tests on python-dbusmock's private buses."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import pwd
import subprocess
import threading
from contextlib import ExitStack
from dataclasses import replace
from datetime import datetime, timezone
from unittest import mock

import pytest
from gi.repository import Gio, GLib

from oh_no_parent_control.core import (
    AccessDenied,
    AccountMissing,
    BackendFailure,
    Broker,
    BrokerError,
    Busy,
    DesktopInUse,
    InvalidRequest,
    RecoveryPending,
    RollbackFailure,
    SessionState,
    Stale,
    UserAccount,
)
from oh_no_parent_control.config import validate
from oh_no_parent_control.grant_store import (
    MAX_SAVED_SECONDS, FixedGrant, GrantRecord, GrantStore, PauseIntent, SavedBalance,
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
    open_bus, begin_call, spin_until, call, private_service, broker_service, close_connection,
)
from tests.support.broker import Accounts, Authorizer, Extensions, Preferences, RunningApps, TimerUsage
from tests.support.configuration import valid_config


GRANT_STATUS_REPLY = "(ttuuuuuustuu)"
CHILD_UID = 1001
OTHER_CHILD_UID = 1002
ADMIN_UID = 1003
KIOSK_UID = 991


class SavedTimeAccounts(Accounts):
    def sync_execution_policy(self):
        pass

    def get_user(self, uid):
        try:
            return super().get_user(uid)
        except KeyError as error:
            raise AccountMissing("fixture account is unavailable") from error

    def get_extension(self, uid, *, deadline=None):
        return super().get_extension(uid)

    def set_extension(self, uid, value, *, deadline=None, wall_deadline=None):
        super().set_extension(uid, value)


class SavedTimeUsage(TimerUsage):
    def query_usage(self, uid, *, timeout_seconds=None):
        return super().query_usage(uid)


@pytest.fixture
def saved_time_bus(dbusmock_system, dbusmock_session, tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    store = GrantStore(tmp_path / "grants")
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    accounts, preferences, usage = SavedTimeAccounts(), Preferences(), SavedTimeUsage()
    accounts.extension, accounts.daily_limit = (0, 0), 120
    preferences.values[CHILD_UID].update(parent_control_enabled=True, daily_time_limit_minutes=2)
    configuration = validate(valid_config())
    identities = {}
    sessions = {
        uid: SessionState(f"/org/freedesktop/login1/session/{uid}", str(uid), uid,
                          remote=False, active=True, locked=False, state="active",
                          kind="wayland", started_monotonic=1)
        for uid in (CHILD_UID, KIOSK_UID)
    }
    session_adapter = mock.Mock(spec=("resolve", "for_user"))
    session_adapter.resolve.side_effect = lambda sender, **_bounds: sessions.get(identities[sender])
    session_adapter.for_user.side_effect = lambda uid, **_bounds: (sessions[uid],) if uid in sessions else ()
    authorizer = Authorizer(resolve_session=session_adapter.resolve)

    def configure(dependencies):
        real_uid = dependencies.credentials.uid

        def fixture_uid(sender):
            # The daemon still verifies the caller. Unprivileged connections
            # share the host UID, so assign test roles to their actual bus names.
            assert real_uid(sender) == os.getuid()
            return identities[sender]

        monkeypatch.setattr(dependencies.credentials, "uid", fixture_uid)
        return replace(dependencies, broker_factory=Broker, accounts=accounts,
                       config_loader=lambda: configuration, authorizer=authorizer,
                       preferences=preferences, extensions=Extensions(), timer_usage=usage,
                       running_apps=RunningApps(), grant_store=store, sessions=session_adapter,
                       now=lambda: now)

    with (broker_service(dbusmock_system, dbusmock_session, tmp_path,
                         configure_dependencies=configure) as harness,
          ExitStack() as connections):
        clients = {CHILD_UID: harness.client}
        identities[harness.client.get_unique_name()] = CHILD_UID

        def client_for(uid):
            if uid not in clients:
                connection = open_bus(harness.system_bus.address)
                connections.callback(close_connection, connection)
                clients[uid] = connection
                identities[connection.get_unique_name()] = uid
            return clients[uid]

        harness.client_for = client_for
        harness.store = store
        harness.preferences = preferences
        harness.authorizer = authorizer
        harness.sessions = sessions
        harness.usage = usage
        harness.epoch = int(now.timestamp())
        yield harness


def grant_status(client, target_uid=CHILD_UID, requested_seconds=0):
    return call(client, "GetGrantStatus", GLib.Variant("(uu)", (target_uid, requested_seconds)),
                GRANT_STATUS_REPLY).unpack()


def deferred_arguments(target_uid=CHILD_UID, duration=300, revision=0):
    return GLib.Variant("(uuubt)", (target_uid, ADMIN_UID, duration, False, revision))


def saved_time_mutations(target_uid, revision=0):
    arguments = GLib.Variant("(ut)", (target_uid, revision))
    return (("RequestDeferredAccess", deferred_arguments(target_uid, revision=revision), "(sss)"),
            ("PauseGrant", arguments, "()"), ("UseSavedTime", arguments, "()"))


def assert_bus_refusal(client, method, parameters, reply_signature, error_name):
    with pytest.raises(GLib.Error) as caught:
        call(client, method, parameters, reply_signature)
    assert Gio.dbus_error_get_remote_error(caught.value) == error_name, method


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
        with (mock.patch.object(manager, "session_bus_endpoint", return_value=(account, dbusmock_session.address)),
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
            assert len(activations) == 2
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
    manager.session_bus_endpoint.return_value = (
        SimpleNamespace(pw_uid=1001, pw_gid=1001), "unix:path=/unused")
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


@pytest.mark.parametrize(("caller_uid", "target_uid", "read_error", "write_error"), (
    pytest.param(CHILD_UID, OTHER_CHILD_UID, AccessDenied, AccessDenied, id="other-child"),
    pytest.param(ADMIN_UID, CHILD_UID, None, AccessDenied, id="administrator"),
    pytest.param(0, CHILD_UID, None, AccessDenied, id="root"),
    pytest.param(1004, CHILD_UID, AccessDenied, AccessDenied, id="unrelated"),
    pytest.param(KIOSK_UID, ADMIN_UID, AccessDenied, AccessDenied, id="ineligible-target"),
    pytest.param(KIOSK_UID, 4242, InvalidRequest, InvalidRequest, id="missing-target"),
    pytest.param(CHILD_UID, 4242, AccessDenied, AccessDenied, id="private-target"),
))
def test_saved_time_roles_are_bound_to_bus_senders(saved_time_bus, caller_uid, target_uid,
                                                   read_error, write_error):
    state = saved_time_bus
    client = state.client_for(caller_uid)
    if read_error:
        assert_bus_refusal(client, "GetGrantStatus", GLib.Variant("(uu)", (target_uid, 0)),
                           GRANT_STATUS_REPLY, read_error.dbus_name)
    else:
        assert grant_status(client, target_uid) == (
            0, state.epoch, 120, 0, 0, 0, 120, 120, "none", 0, 0, 0,
        )
    for method, parameters, reply_signature in saved_time_mutations(target_uid):
        assert_bus_refusal(client, method, parameters, reply_signature, write_error.dbus_name)
    assert state.authorizer.calls == []


def test_status_distinguishes_caller_lookup_failure_from_nonadministrator_denial(saved_time_bus):
    state = saved_time_bus
    parameters = GLib.Variant("(uu)", (CHILD_UID, 0))
    get_user = state.accounts.get_user

    def lookup_caller(uid):
        if uid == ADMIN_UID:
            raise OSError("fixture account lookup unavailable")
        return get_user(uid)

    with mock.patch.object(state.accounts, "get_user", side_effect=lookup_caller) as lookup:
        assert_bus_refusal(state.client_for(ADMIN_UID), "GetGrantStatus", parameters,
                           GRANT_STATUS_REPLY, BackendFailure.dbus_name)
        assert_bus_refusal(state.client_for(OTHER_CHILD_UID), "GetGrantStatus", parameters,
                           GRANT_STATUS_REPLY, AccessDenied.dbus_name)
    assert lookup.call_args_list == [mock.call(ADMIN_UID), mock.call(OTHER_CHILD_UID)]


def test_saved_time_rejects_invalid_payloads_and_full_width_stale_revisions(saved_time_bus):
    state = saved_time_bus
    kiosk = state.client_for(KIOSK_UID)
    assert_bus_refusal(kiosk, "PauseGrant", GLib.Variant("(uu)", (CHILD_UID, 0)), "()",
                       "org.freedesktop.DBus.Error.InvalidArgs")
    assert_bus_refusal(kiosk, "GetGrantStatus", GLib.Variant("(uu)", (CHILD_UID, 2**32 - 1)),
                       GRANT_STATUS_REPLY, InvalidRequest.dbus_name)
    assert_bus_refusal(kiosk, "RequestDeferredAccess", deferred_arguments(duration=0),
                       "(sss)", InvalidRequest.dbus_name)
    for method, parameters, reply_signature in saved_time_mutations(CHILD_UID, revision=2**32):
        assert_bus_refusal(kiosk, method, parameters, reply_signature, Stale.dbus_name)
    assert grant_status(kiosk)[0] == 0
    assert state.authorizer.calls == []


def test_saved_time_cross_client_revision_race_and_legacy_desktop_status(saved_time_bus):
    state = saved_time_bus
    child, kiosk = state.client, state.client_for(KIOSK_UID)
    starting = grant_status(child, requested_seconds=300)
    assert starting == (0, state.epoch, 120, 0, 0, 0, 120, 120, "none", 0, 420, 300)
    assert grant_status(kiosk, requested_seconds=300) == starting

    correlation_id, result, pause_error = call(
        child, "RequestDeferredAccess", deferred_arguments(revision=starting[0]), "(sss)",
    ).unpack()
    assert correlation_id
    assert (result, pause_error) == ("saved", "")
    assert state.authorizer.calls[0][:3] == ("child", child.get_unique_name(), correlation_id)
    state.sessions[CHILD_UID] = replace(state.sessions[CHILD_UID], active=False, locked=True)

    # Both clients observed the original revision before the first commit.
    assert_bus_refusal(kiosk, "UseSavedTime", GLib.Variant("(ut)", (CHILD_UID, starting[0])),
                       "()", Stale.dbus_name)
    saved = grant_status(kiosk)
    assert saved[0] != starting[0]
    assert saved[1:] == (state.epoch, 120, 0, 0, 300, 120, 420, "none", 0, 0, 0)
    legacy_arguments = GLib.Variant("(uu)", (CHILD_UID, 60))
    assert call(child, "GetTimeStatus", legacy_arguments, "(uuuu)").unpack() == (120, 0, 60, 180)

    assert call(kiosk, "UseSavedTime", GLib.Variant("(ut)", (CHILD_UID, saved[0])), "()").unpack() == ()
    running = grant_status(child)
    assert running[0] != saved[0]
    assert running[1:] == (state.epoch, 120, 420, 300, 0, 420, 420, "fixed", state.epoch + 420, 0, 0)
    assert call(child, "GetTimeStatus", legacy_arguments, "(uuuu)").unpack() == (120, 420, 60, 480)
    assert call(kiosk, "PauseGrant", GLib.Variant("(ut)", (CHILD_UID, running[0])), "()").unpack() == ()
    paused = grant_status(kiosk)
    assert paused[0] != running[0]
    assert paused[3:5] == (0, 0)
    assert 0 < paused[5] <= running[4]
    assert paused[8:10] == ("none", 0)


def test_foreign_pending_approval_keeps_status_and_mutations_bounded(saved_time_bus):
    state = saved_time_bus
    kiosk = state.client_for(KIOSK_UID)
    state.preferences.values[OTHER_CHILD_UID] = {**default_preferences(), "parent_control_enabled": True}
    entered, release = threading.Event(), threading.Event()

    def wait_for_parent():
        entered.set()
        assert release.wait(5), "parent approval was not released"

    state.authorizer.callback = wait_for_parent
    foreign = begin_call(kiosk, "RequestDeferredAccess", deferred_arguments(OTHER_CHILD_UID), "(sss)")
    try:
        spin_until(entered.is_set)
        assert_bus_refusal(state.client, "GetGrantStatus", GLib.Variant("(uu)", (CHILD_UID, 0)),
                           GRANT_STATUS_REPLY, Busy.dbus_name)
        assert_bus_refusal(state.client, "PauseGrant", GLib.Variant("(ut)", (CHILD_UID, 0)),
                           "()", Busy.dbus_name)
        assert not foreign["done"]
    finally:
        release.set()
        spin_until(lambda: foreign["done"])
    assert foreign["result"].unpack()[1:] == ("saved", "")
    assert state.authorizer.calls[0][:2] == ("kiosk", kiosk.get_unique_name())
    assert grant_status(state.client)[5] == 0
    assert grant_status(kiosk, OTHER_CHILD_UID)[5] == 300


def test_status_worker_capacity_is_reusable_after_usage_failures(saved_time_bus):
    state = saved_time_bus
    kiosk, parent = state.client_for(KIOSK_UID), state.client_for(ADMIN_UID)
    parameters = GLib.Variant("(uu)", (CHILD_UID, 0))
    capacity = 4
    query_usage = state.usage.query_usage

    def run_batch(*, fail):
        entered, release = threading.Event(), threading.Event()
        lock = threading.Lock()
        reads = 0

        def held_usage(uid):
            nonlocal reads
            with lock:
                reads += 1
                if reads == capacity:
                    entered.set()
            assert release.wait(5), "status usage reads were not released"
            if fail:
                raise OSError("fixture usage unavailable")
            return query_usage(uid)

        pending = []
        with mock.patch.object(state.usage, "query_usage", side_effect=held_usage):
            try:
                for _ in range(capacity):
                    pending.append(begin_call(kiosk, "GetGrantStatus", parameters, GRANT_STATUS_REPLY))
                spin_until(entered.is_set)
                if fail:
                    excess = begin_call(parent, "GetGrantStatus", parameters, GRANT_STATUS_REPLY)
                    pending.append(excess)
                    spin_until(lambda: excess["done"])
                    assert Gio.dbus_error_get_remote_error(excess["error"]) == Busy.dbus_name
                assert not any(reply["done"] for reply in pending[:capacity])
            finally:
                release.set()
                spin_until(lambda: all(reply["done"] for reply in pending))
        return pending[:capacity]

    for reply in run_batch(fail=True):
        assert Gio.dbus_error_get_remote_error(reply["error"]) == BackendFailure.dbus_name
    for reply in run_batch(fail=False):
        assert reply["result"].unpack()[1:3] == (state.epoch, 120)


def test_status_worker_capacity_includes_replies_waiting_for_the_main_loop(saved_time_bus):
    state = saved_time_bus
    parameters = GLib.Variant("(uu)", (CHILD_UID, 0))
    idle_add = GLib.idle_add
    send_reply = state.service._send_saved_time_reply
    waiting = []
    calls = []

    def hold_replies(callback, *args, **kwargs):
        if callback == send_reply:
            waiting.append((callback, args, kwargs))
            return
        return idle_add(callback, *args, **kwargs)

    def release_one():
        callback, args, kwargs = waiting.pop(0)
        idle_add(callback, *args, **kwargs)

    def drain():
        while waiting:
            release_one()
        return all(call["done"] for call in calls)

    try:
        with mock.patch.object(GLib, "idle_add", side_effect=hold_replies):
            for _ in range(4):
                calls.append(begin_call(state.client, "GetGrantStatus", parameters, GRANT_STATUS_REPLY))
            spin_until(lambda: len(waiting) == 4)
            assert_bus_refusal(state.client_for(KIOSK_UID), "GetGrantStatus", parameters,
                               GRANT_STATUS_REPLY, Busy.dbus_name)
            release_one()
            spin_until(lambda: any(call["done"] for call in calls))
            calls.append(begin_call(state.client, "GetGrantStatus", parameters, GRANT_STATUS_REPLY))
            spin_until(lambda: len(waiting) == 4)
    finally:
        spin_until(drain)
    assert all(call["result"].unpack()[1:3] == (state.epoch, 120) for call in calls)


def test_status_reports_and_queues_grant_recovery(saved_time_bus, monkeypatch):
    state = saved_time_bus
    source, shortened = (state.epoch - 60, 660), (state.epoch - 60, 60)
    state.accounts.extension = shortened
    pending = state.store.write(GrantRecord(
        CHILD_UID, "child", fixed=FixedGrant(source, False),
        intent=PauseIntent(source, shortened, SavedBalance(300, False)),
    ))
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    recover = state.broker.recover_grant
    attempts = []

    def recover_in_worker(uid):
        attempts.append(uid)
        entered.set()
        try:
            assert release.wait(5), "grant recovery was not released"
            recover(uid)
        finally:
            finished.set()

    monkeypatch.setattr(state.broker, "recover_grant", recover_in_worker)
    parameters = GLib.Variant("(uu)", (CHILD_UID, 0))
    try:
        assert_bus_refusal(state.client, "GetGrantStatus", parameters,
                           GRANT_STATUS_REPLY, RecoveryPending.dbus_name)
        spin_until(entered.is_set)
        assert_bus_refusal(state.client_for(KIOSK_UID), "GetGrantStatus", parameters,
                           GRANT_STATUS_REPLY, RecoveryPending.dbus_name)
        assert state.store.load_record(CHILD_UID) == pending
    finally:
        release.set()
    spin_until(finished.is_set)
    recovered = grant_status(state.client)
    assert recovered[0] != pending.revision
    assert recovered[3:6] == (0, 0, 300)
    assert attempts == [CHILD_UID]


def test_status_rejects_a_changing_snapshot_and_reports_unavailable_usage(saved_time_bus, monkeypatch):
    state = saved_time_bus
    before = state.store.write(GrantRecord(CHILD_UID, "child", saved=SavedBalance(300, False)))
    read_record = state.store.load_record
    changed = None

    def change_after_read(uid):
        nonlocal changed
        record = read_record(uid)
        if uid == CHILD_UID and changed is None:
            assert record == before
            changed = state.store.write(replace(record, saved=SavedBalance(600, False)))
        return record

    parameters = GLib.Variant("(uu)", (CHILD_UID, 0))
    with monkeypatch.context() as patch:
        patch.setattr(state.store, "load_record", change_after_read)
        assert_bus_refusal(state.client, "GetGrantStatus", parameters, GRANT_STATUS_REPLY, Busy.dbus_name)
    fresh = grant_status(state.client)
    assert (fresh[0], fresh[5]) == (changed.revision, 600)
    with mock.patch.object(state.usage, "query_usage", side_effect=OSError("fixture usage unavailable")):
        assert_bus_refusal(state.client, "GetGrantStatus", parameters,
                           GRANT_STATUS_REPLY, BackendFailure.dbus_name)


def test_own_grant_status_uses_one_evaluation_time_during_usage_processing(saved_time_bus, monkeypatch):
    state = saved_time_bus
    started_at, started_monotonic = state.epoch + 60, 1000
    elapsed = 0
    state.accounts.extension = (started_at - 10, 100)
    state.store.write(GrantRecord(CHILD_UID, "child", fixed=FixedGrant(state.accounts.extension, False)))

    def delayed_usage(_uid):
        nonlocal elapsed
        elapsed = 30
        yield (started_at - 20, started_at - 5)

    monkeypatch.setattr(state.broker, "_now", lambda: datetime.fromtimestamp(started_at + elapsed, timezone.utc))
    monkeypatch.setattr(state.broker, "_monotonic", lambda: started_monotonic + elapsed)
    monkeypatch.setattr(state.usage, "query_usage", delayed_usage)
    monkeypatch.setattr(state.usage, "query_native_deadline", lambda _uid: (started_monotonic + 50) * 1_000_000)

    status = grant_status(state.client)
    assert elapsed == 30
    evaluated_at = status[1]
    assert evaluated_at in (started_at, started_at + elapsed)
    evaluation_delay = evaluated_at - started_at
    assert status[2:5] == (50 - evaluation_delay, 90 - evaluation_delay, 40)
    assert status[8:10] == ("fixed", started_at + 90)


def test_deferred_reply_preserves_saved_time_when_a_child_is_using_the_desktop(saved_time_bus):
    state = saved_time_bus
    kiosk = state.client_for(KIOSK_UID)
    state.accounts.extension = (state.epoch - 60, 660)
    before = state.store.write(GrantRecord(CHILD_UID, "child", fixed=FixedGrant(state.accounts.extension, False)))

    reply = call(kiosk, "RequestDeferredAccess", deferred_arguments(revision=before.revision), "(sss)").unpack()

    assert reply[1:] == ("saved_pause_error", DesktopInUse.dbus_name)
    status = grant_status(kiosk, requested_seconds=300)
    assert status[0] != before.revision
    assert status[1:] == (state.epoch, 120, 600, 480, 300, 600, 900, "fixed", state.epoch + 600, 900, 1080)
    assert call(kiosk, "GetTimeStatus", GLib.Variant("(uu)", (CHILD_UID, 60)), "(uuuu)").unpack() == (120, 600, 60, 660)


def test_deferred_approval_keeps_minutes_when_only_the_pause_exceeds_the_saved_limit(saved_time_bus):
    state = saved_time_bus
    kiosk = state.client_for(KIOSK_UID)
    state.sessions[CHILD_UID] = replace(state.sessions[CHILD_UID], active=False, locked=True)
    source = state.accounts.extension = (state.epoch - 60, 660)
    requested = 300
    before = state.store.write(GrantRecord(
        CHILD_UID, "child", fixed=FixedGrant(source, False),
        saved=SavedBalance(MAX_SAVED_SECONDS - requested, False),
    ))

    estimate = grant_status(kiosk, requested_seconds=requested)
    assert estimate[4:6] == (480, MAX_SAVED_SECONDS - requested)
    assert estimate[-1] == MAX_SAVED_SECONDS

    reply = call(kiosk, "RequestDeferredAccess",
                 deferred_arguments(duration=requested, revision=before.revision), "(sss)").unpack()
    assert reply[1:] == ("saved_pause_error", BackendFailure.dbus_name)
    assert state.accounts.extension == source
    saved = grant_status(kiosk, requested_seconds=requested)
    assert saved[0] != before.revision
    assert saved[3:6] == (600, 480, MAX_SAVED_SECONDS)
    assert saved[-2:] == (900, 0)

    assert_bus_refusal(kiosk, "RequestDeferredAccess",
                       deferred_arguments(duration=requested, revision=saved[0]),
                       "(sss)", InvalidRequest.dbus_name)
    assert len(state.authorizer.calls) == 1
    assert grant_status(kiosk, requested_seconds=requested) == saved


def test_disabled_control_allows_reading_status_and_refuses_new_mutations(saved_time_bus):
    state = saved_time_bus
    kiosk = state.client_for(KIOSK_UID)
    assert grant_status(kiosk, OTHER_CHILD_UID) == (0, state.epoch, 0, 0, 0, 0, 0, 0, "none", 0, 0, 0)
    for method, parameters, reply_signature in saved_time_mutations(OTHER_CHILD_UID):
        assert_bus_refusal(kiosk, method, parameters, reply_signature, AccessDenied.dbus_name)
    assert state.authorizer.calls == []
    assert state.store.load_record(OTHER_CHILD_UID) is None


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


def test_deadline_dispatch_continues_while_a_time_transaction_is_pending(private_service):
    entered, release = threading.Event(), threading.Event()

    def pending_request(*_args):
        entered.set()
        assert release.wait(3), "request worker was not released"
        return "correlation", "approved"

    private_service.broker.behaviors["request_access"] = pending_request
    first = begin_call(private_service.client, "RequestAccess",
                       GLib.Variant("(uuub)", (1100, 1200, 300, False)), "(ss)")
    try:
        spin_until(entered.is_set)
        deadline = call(private_service.client, "CalculateOwnDeadline",
                        GLib.Variant("(tt)", (123_000_000, 0)), "(t)")
        assert deadline.unpack() == (132_500_000,)
        assert not first["done"]
    finally:
        release.set()
        spin_until(lambda: first["done"])
    assert first["result"].unpack() == ("correlation", "approved")


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
