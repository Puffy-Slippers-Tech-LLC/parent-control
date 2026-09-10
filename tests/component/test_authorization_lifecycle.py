"""Real D-Bus lifecycle/cancellation with the production authorizer and broker.

Only logind/Polkit replies and account storage are doubles. The original
requester and agent service stay alive throughout lockout and kiosk recovery.
"""

from contextlib import ExitStack
import logging
import threading
from types import SimpleNamespace

import pytest
from gi.repository import Gio, GLib

from oh_no_parent_control import authorization
from oh_no_parent_control.adapters import (
    CallerCredentials, DBUS_NAME, DBUS_PATH, DBUS_INTERFACE,
    LOGIN_NAME, LOGIN_PATH, LOGIN_MANAGER_INTERFACE, LOGIN_SESSION_INTERFACE,
    PROPERTIES_INTERFACE,
)
from oh_no_parent_control.authorization import (
    PolkitAuthorizer, POLKIT_NAME, POLKIT_PATH, POLKIT_INTERFACE,
)
from oh_no_parent_control.core import Busy
from tests.support.broker import Accounts, Preferences, make_broker
from tests.support.dbus import open_bus, close_connection, spin_until

SESSION = "/org/freedesktop/login1/session/child"
OTHER_SESSION = "/org/freedesktop/login1/session/other"
USER = "/org/freedesktop/login1/user/_1001"
XML = """
<node>
 <interface name="org.freedesktop.login1.Manager">
  <method name="GetSessionByPID"><arg type="u" direction="in"/><arg type="o" direction="out"/></method>
  <method name="GetUserByPID"><arg type="u" direction="in"/><arg type="o" direction="out"/></method>
  <signal name="SessionRemoved"><arg type="s"/><arg type="o"/></signal>
 </interface>
 <interface name="org.freedesktop.DBus.Properties">
  <method name="GetAll"><arg type="s" direction="in"/><arg type="a{sv}" direction="out"/></method>
  <method name="Get"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/></method>
  <signal name="PropertiesChanged"><arg type="s"/><arg type="a{sv}"/><arg type="as"/></signal>
 </interface>
 <interface name="org.freedesktop.login1.Session"><signal name="Lock"/></interface>
 <interface name="org.freedesktop.PolicyKit1.Authority">
  <method name="CheckAuthorization">
   <arg type="(sa{sv})" direction="in"/><arg type="s" direction="in"/>
   <arg type="a{ss}" direction="in"/><arg type="u" direction="in"/>
   <arg type="s" direction="in"/><arg type="(bba{ss})" direction="out"/>
  </method>
  <method name="CancelCheckAuthorization"><arg type="s" direction="in"/></method>
 </interface>
</node>
"""


class Authorities:
    def __init__(self, connection):
        self.connection = connection
        self.checks = []
        self.cancellations = []
        self.properties = {"Active": True, "LockedHint": False, "State": "active"}
        self.fallback = False
        self.sessionless = False
        self.no_display = False
        self.snapshot_error = False
        self.resolve_error = False
        self.cancel_mode = "cancel"
        self.on_snapshot = None

    def dispatch(self, _connection, sender, path, _interface, method, parameters, invocation):
        if method == "GetSessionByPID":
            if self.resolve_error:
                invocation.return_dbus_error("org.freedesktop.DBus.Error.AccessDenied", "private error")
            elif self.fallback or self.sessionless:
                invocation.return_dbus_error("org.freedesktop.login1.NoSessionForPID", "no session")
            else:
                invocation.return_value(GLib.Variant("(o)", (SESSION,)))
        elif method == "GetUserByPID":
            if self.sessionless:
                invocation.return_dbus_error("org.freedesktop.login1.NoUserForPID", "no user")
            else:
                invocation.return_value(GLib.Variant("(o)", (USER,)))
        elif method == "Get":
            assert parameters.unpack() == (authorization.LOGIN_USER_INTERFACE, "Display")
            invocation.return_value(GLib.Variant("(v)", (
                GLib.Variant("(so)", ("", "/") if self.no_display else ("child", SESSION)),
            )))
        elif method == "GetAll":
            assert path == SESSION
            assert parameters.unpack() == (LOGIN_SESSION_INTERFACE,)
            if self.snapshot_error:
                invocation.return_dbus_error("org.freedesktop.DBus.Error.UnknownObject", "gone")
            else:
                snapshot = self.variants(self.properties)
                if self.on_snapshot:
                    self.on_snapshot()
                invocation.return_value(GLib.Variant("(a{sv})", (snapshot,)))
        elif method == "CheckAuthorization":
            self.checks.append({"sender": sender, "parameters": parameters.unpack(),
                                "invocation": invocation, "done": False})
        elif method == "CancelCheckAuthorization":
            cancellation_id, = parameters.unpack()
            original = next(item for item in self.checks
                            if item["parameters"][4] == cancellation_id)
            # Polkit cancellation IDs belong to the authority's caller, not to
            # the subject whose password prompt the caller requested.
            assert sender == original["sender"]
            self.cancellations.append(cancellation_id)
            if self.cancel_mode == "hang":
                return  # Exercise the bounded cleanup wait.
            if self.cancel_mode == "error":
                invocation.return_dbus_error("org.freedesktop.PolicyKit1.Error.Failed", "private error")
                return
            if self.cancel_mode == "approve":
                self.reply(original, authorized=True)
            else:
                original["done"] = True
                original["invocation"].return_dbus_error(
                    "org.freedesktop.PolicyKit1.Error.Cancelled", "cancelled")
            invocation.return_value(GLib.Variant("()", ()))
        else:
            raise AssertionError(method)

    @staticmethod
    def variants(values):
        return {key: GLib.Variant("b" if type(value) is bool else "s", value)
                for key, value in values.items()}

    def change(self, values, *, path=SESSION, invalidated=()):
        if path == SESSION:
            self.properties.update(values)
        self.connection.emit_signal(None, path, PROPERTIES_INTERFACE, "PropertiesChanged",
                                    GLib.Variant("(sa{sv}as)", (
                                        LOGIN_SESSION_INTERFACE, self.variants(values),
                                        list(invalidated),
                                    )))

    def reply(self, item=None, *, authorized=False, challenge=False, error=False):
        item = self.checks[-1] if item is None else item
        item["done"] = True
        if error:
            item["invocation"].return_dbus_error(
                "org.freedesktop.PolicyKit1.Error.Failed", "private error")
        else:
            item["invocation"].return_value(GLib.Variant(
                "((bba{ss}))", ((authorized, challenge, {}),)))


@pytest.fixture
def lifecycle(dbusmock_system):
    with ExitStack() as owned:
        server = open_bus(dbusmock_system.address)
        owned.callback(close_connection, server)
        for name in (LOGIN_NAME, POLKIT_NAME):
            server.call_sync(DBUS_NAME, DBUS_PATH, DBUS_INTERFACE, "RequestName",
                             GLib.Variant("(su)", (name, 0)),
                             GLib.VariantType.new("(u)"), Gio.DBusCallFlags.NONE, 3000, None)
        authorities = Authorities(server)
        node = Gio.DBusNodeInfo.new_for_xml(XML)
        for path, interfaces in (
            (LOGIN_PATH, (LOGIN_MANAGER_INTERFACE,)),
            (SESSION, (PROPERTIES_INTERFACE, LOGIN_SESSION_INTERFACE)),
            (USER, (PROPERTIES_INTERFACE,)),
            (POLKIT_PATH, (POLKIT_INTERFACE,)),
        ):
            for interface in interfaces:
                registration = server.register_object_with_closures2(
                    path, node.lookup_interface(interface), authorities.dispatch, None, None)
                owned.callback(server.unregister_object, registration)
        broker_bus = open_bus(dbusmock_system.address)
        owned.callback(close_connection, broker_bus)
        caller = open_bus(dbusmock_system.address)
        owned.callback(close_connection, caller)
        kiosk = open_bus(dbusmock_system.address)
        owned.callback(close_connection, kiosk)
        accounts, preferences = Accounts(), Preferences()
        preferences.values[1001]["parent_control_enabled"] = True
        broker = make_broker(accounts=accounts, preferences=preferences,
                             authorizer=PolkitAuthorizer(broker_bus),
                             alive=CallerCredentials(broker_bus).alive)
        threads = []

        def start(surface="child", connection=None):
            connection = connection or (caller if surface == "child" else kiosk)
            state = {"done": False}

            def run():
                try:
                    if surface == "child":
                        state["result"] = broker.request_own_access(
                            1001, connection.get_unique_name(), 1003, 300, True)
                    else:
                        state["result"] = broker.request_access(
                            991, connection.get_unique_name(), 1001, 1003, 300, True)
                except Exception as error:
                    state["error"] = error
                finally:
                    state["done"] = True

            thread = threading.Thread(target=run, daemon=True)
            threads.append(thread)
            thread.start()
            return state

        try:
            yield SimpleNamespace(authorities=authorities, broker=broker, accounts=accounts,
                                  caller=caller, kiosk=kiosk, start=start, server=server)
        finally:
            # Release only our own outstanding fake method invocations/threads.
            for item in authorities.checks:
                if not item["done"]:
                    authorities.reply(item, error=True)
            spin_until(lambda: all(not thread.is_alive() for thread in threads), timeout=7)


@pytest.mark.parametrize("fallback", (False, True))
@pytest.mark.parametrize("trigger", ("locked", "inactive", "closing", "lock-signal", "removed"))
def test_lockout_silently_cancels_pending_child_and_kiosk_can_authenticate(
        lifecycle, caplog, fallback, trigger):
    caplog.set_level(logging.INFO)
    authority = lifecycle.authorities
    authority.fallback = fallback
    pending = lifecycle.start()
    spin_until(lambda: len(authority.checks) == 1)
    with pytest.raises(Busy):
        lifecycle.broker.request_access(991, lifecycle.kiosk.get_unique_name(),
                                        1001, 1003, 300, True)
    if trigger == "lock-signal":
        lifecycle.server.emit_signal(None, SESSION, LOGIN_SESSION_INTERFACE, "Lock", None)
    elif trigger == "removed":
        lifecycle.server.emit_signal(None, LOGIN_PATH, LOGIN_MANAGER_INTERFACE, "SessionRemoved",
                                     GLib.Variant("(so)", ("child", SESSION)))
    else:
        authority.change({"locked": {"LockedHint": True}, "inactive": {"Active": False},
                          "closing": {"State": "closing"}}[trigger])
    spin_until(lambda: pending["done"])
    assert pending["result"][1:] == ("cancelled", 0)
    assert authority.cancellations == [authority.checks[0]["parameters"][4]]
    assert lifecycle.accounts.events == []
    assert not lifecycle.caller.is_closed()  # Locked desktop and agent survive.
    # The resolver now represents the foreground kiosk's available session.
    authority.properties.update(Active=True, LockedHint=False, State="active")
    fresh = lifecycle.start("kiosk")
    spin_until(lambda: len(authority.checks) == 2)
    authority.reply(authorized=True)
    spin_until(lambda: fresh["done"])
    assert fresh["result"][1] == "approved"
    assert len([event for event in lifecycle.accounts.events if event[0] == "set_extension"]) == 1
    assert "silent=True" in caplog.text
    assert "cancel-check outcome=accepted" in caplog.text
    for private in ("target-account", "approver-user", lifecycle.caller.get_unique_name(), SESSION):
        assert private not in caplog.text


@pytest.mark.parametrize("surface", ("child", "kiosk"))
def test_caller_disconnect_cancels_without_stopping_agent(lifecycle, surface):
    pending = lifecycle.start(surface)
    spin_until(lambda: lifecycle.authorities.checks)
    close_connection(lifecycle.caller if surface == "child" else lifecycle.kiosk)
    spin_until(lambda: pending["done"])
    assert pending["result"][1] == "cancelled"
    assert len(lifecycle.authorities.cancellations) == 1
    assert lifecycle.accounts.events == []


@pytest.mark.parametrize("cancel_mode", ("approve", "error", "hang"))
def test_cancellation_wins_late_approval_and_cleanup_failure_releases_lock(
        lifecycle, monkeypatch, cancel_mode):
    monkeypatch.setattr(authorization, "LIFECYCLE_TIMEOUT_MS", 250)
    authority = lifecycle.authorities
    authority.cancel_mode = cancel_mode
    pending = lifecycle.start()
    spin_until(lambda: authority.checks)
    authority.change({"LockedHint": True})
    spin_until(lambda: pending["done"])
    assert pending["result"][1:] == ("cancelled", 0)
    assert lifecycle.accounts.events == []
    if cancel_mode != "approve":
        authority.reply(authorized=True)  # A still later result cannot grant time.
    # A new request can obtain the lock even if remote cleanup failed.
    fresh = lifecycle.start("kiosk")
    spin_until(lambda: fresh["done"])
    assert fresh["result"][1] == "cancelled"  # Session is still locked.
    assert lifecycle.accounts.events == []


@pytest.mark.parametrize("state", ({"LockedHint": True}, {"Active": False}, {"State": "closing"}))
def test_unavailable_session_never_opens_prompt(lifecycle, state):
    lifecycle.authorities.properties.update(state)
    pending = lifecycle.start()
    spin_until(lambda: pending["done"])
    assert pending["result"][1:] == ("cancelled", 0)
    assert lifecycle.authorities.checks == []
    assert lifecycle.accounts.events == []


def test_lock_during_initial_snapshot_is_not_missed(lifecycle):
    lifecycle.authorities.on_snapshot = lambda: lifecycle.authorities.change({"LockedHint": True})
    pending = lifecycle.start()
    spin_until(lambda: pending["done"])
    assert pending["result"][1:] == ("cancelled", 0)
    assert lifecycle.accounts.events == []


def test_unrelated_session_cannot_cancel_and_invalidated_lock_is_reloaded(lifecycle):
    authority = lifecycle.authorities
    pending = lifecycle.start()
    spin_until(lambda: authority.checks)
    authority.change({"LockedHint": True}, path=OTHER_SESSION)
    # The relevant invalidation follows the unrelated signal on the same bus.
    authority.properties["LockedHint"] = True
    authority.change({}, invalidated=("LockedHint",))
    spin_until(lambda: pending["done"])
    assert pending["result"][1:] == ("cancelled", 0)
    assert authority.cancellations == [authority.checks[0]["parameters"][4]]


@pytest.mark.parametrize("fault", ("resolve", "snapshot", "missing-property"))
def test_unobservable_session_fails_closed_without_prompt(lifecycle, fault):
    if fault == "resolve":
        lifecycle.authorities.resolve_error = True
    elif fault == "snapshot":
        lifecycle.authorities.snapshot_error = True
    else:
        del lifecycle.authorities.properties["Active"]
    pending = lifecycle.start()
    spin_until(lambda: pending["done"])
    assert pending["result"][1] == ("denied" if fault == "resolve" else "cancelled")
    assert lifecycle.authorities.checks == []
    assert lifecycle.accounts.events == []


@pytest.mark.parametrize("surface", ("child", "kiosk"))
@pytest.mark.parametrize("outcome", ("approved", "denied", "cancelled", "agent-lost"))
def test_authentication_outcomes_and_selected_identity_are_preserved(lifecycle, surface, outcome):
    pending = lifecycle.start(surface)
    spin_until(lambda: lifecycle.authorities.checks)
    subject, action, details, flags, _cancel_id = lifecycle.authorities.checks[0]["parameters"]
    expected_sender = lifecycle.caller if surface == "child" else lifecycle.kiosk
    assert subject == ("system-bus-name", {"name": expected_sender.get_unique_name()})
    assert action == f"tech.puffyslippers.com.ohnoparentcontrol.{surface}.request-" + (
        "own-access" if surface == "child" else "access")
    assert flags == 1
    assert details == {"target-account": "Child", "approver-user": "admin",
                       "requested-duration": "5 minutes", "soft-blocked-apps": " and allow soft blocked apps"}
    lifecycle.authorities.reply(authorized=outcome == "approved", challenge=outcome == "cancelled",
                                error=outcome == "agent-lost")
    spin_until(lambda: pending["done"])
    assert pending["result"][1] == ("denied" if outcome == "agent-lost" else outcome)
    assert lifecycle.authorities.cancellations == []


@pytest.mark.parametrize("no_display", (False, True))
def test_sessionless_agent_can_authenticate_and_disconnect_still_cancels(lifecycle, no_display):
    lifecycle.authorities.sessionless = not no_display
    lifecycle.authorities.fallback = no_display
    lifecycle.authorities.no_display = no_display
    pending = lifecycle.start()
    spin_until(lambda: lifecycle.authorities.checks)
    close_connection(lifecycle.caller)
    spin_until(lambda: pending["done"])
    assert pending["result"][1:] == ("cancelled", 0)
    assert len(lifecycle.authorities.cancellations) == 1
