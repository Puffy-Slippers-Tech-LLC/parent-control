"""Real D-Bus lifecycle/cancellation with the production authorizer and broker.

Only logind/Polkit replies and account storage are doubles. The original
requester and agent service stay alive throughout lockout and kiosk recovery.
Agent-startup cases reuse these private buses and joined worker threads;
retry timers belong to each worker context and are destroyed before teardown.
No real agent, host session, shared socket or new storage owner is introduced.
"""

from contextlib import ExitStack, contextmanager
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
from oh_no_parent_control.core import BackendFailure, Busy, RateLimited
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
        self.display = ("child", SESSION)
        self.snapshot_error = False
        self.resolve_error = False
        self.cancel_mode = "cancel"
        self.on_snapshot = None
        self.on_check = None

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
                GLib.Variant("(so)", ("", "/") if self.no_display else self.display),
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
            if self.on_check:
                self.on_check()
        elif method == "CancelCheckAuthorization":
            cancellation_id, = parameters.unpack()
            original = next(item for item in self.checks
                            if item["parameters"][4] == cancellation_id and not item["done"])
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

    def change_display(self, display, *, invalidated=False):
        self.display = display
        self.connection.emit_signal(None, USER, PROPERTIES_INTERFACE, "PropertiesChanged",
                                    GLib.Variant("(sa{sv}as)", (
                                        authorization.LOGIN_USER_INTERFACE,
                                        {} if invalidated else {"Display": GLib.Variant("(so)", display)},
                                        ["Display"] if invalidated else [],
                                    )))

    def reply(self, item=None, *, authorized=False, challenge=False, details=None, error=False):
        item = self.checks[-1] if item is None else item
        item["done"] = True
        if error:
            item["invocation"].return_dbus_error(
                "org.freedesktop.PolicyKit1.Error.Failed", "private error")
        else:
            item["invocation"].return_value(GLib.Variant(
                "((bba{ss}))", ((authorized, challenge, details or {}),)))


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

        def start(surface="child", connection=None, *, duration=300, allow_soft=True):
            connection = connection or (caller if surface == "child" else kiosk)
            state = {"done": False}

            def run():
                try:
                    if surface == "child":
                        state["result"] = broker.request_own_access(
                            1001, connection.get_unique_name(), 1003, duration, allow_soft)
                    else:
                        state["result"] = broker.request_access(
                            991, connection.get_unique_name(), 1001, 1003, duration, allow_soft)
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
    baseline = (lifecycle.accounts.limit_type, lifecycle.accounts.daily_limit,
                lifecycle.accounts.filter, lifecycle.accounts.extension)
    pending = lifecycle.start(surface)
    spin_until(lambda: lifecycle.authorities.checks)
    subject, action, details, flags, _cancel_id = lifecycle.authorities.checks[0]["parameters"]
    expected_sender = lifecycle.caller if surface == "child" else lifecycle.kiosk
    assert subject == ("system-bus-name", {"name": expected_sender.get_unique_name()})
    assert action == f"tech.puffyslippers.com.ohnoparentcontrol.{surface}.request-" + (
        "own-access" if surface == "child" else "access")
    assert flags == 1
    assert details == {"target-account": "Child", "approver-user": "admin",
                       "polkit.message": "Grant access to $(target-account)\nfor 5 minutes\n\n✓ Soft-blocked apps allowed"}
    lifecycle.authorities.reply(authorized=outcome == "approved",
                                details={"polkit.dismissed": "true"} if outcome == "cancelled" else {},
                                error=outcome == "agent-lost")
    spin_until(lambda: pending["done"])
    assert pending["result"][1] == ("denied" if outcome == "agent-lost" else outcome)
    assert lifecycle.authorities.cancellations == []
    if outcome == "approved":
        assert lifecycle.accounts.filter == (False, ("org.example.Game",))
        assert lifecycle.accounts.extension[1] == 300
        assert sum(event[0] == "set_extension" for event in lifecycle.accounts.events) == 1
    else:
        assert lifecycle.accounts.events == []
        assert (lifecycle.accounts.limit_type, lifecycle.accounts.daily_limit,
                lifecycle.accounts.filter, lifecycle.accounts.extension) == baseline
        # A refusal must leave both the transaction slot and success cooldown
        # available for a genuinely new check on the same requesting surface.
        fresh = lifecycle.start(surface)
        spin_until(lambda: len(lifecycle.authorities.checks) == 2)
        assert (lifecycle.authorities.checks[0]["parameters"][4] !=
                lifecycle.authorities.checks[1]["parameters"][4])
        lifecycle.authorities.reply(authorized=True)
        spin_until(lambda: fresh["done"])
        assert fresh["result"][1] == "approved"
        assert sum(event[0] == "set_extension" for event in lifecycle.accounts.events) == 1


@pytest.mark.parametrize("surface", ("child", "kiosk"))
@pytest.mark.parametrize("details, expected", [
    ({"polkit.dismissed": "true"}, "cancelled"),
    ({"polkit.dismissed": "1"}, "cancelled"),
    ({"polkit.dismissed": ""}, "denied"),
    ({"unrelated": "true"}, "denied"),
    ({}, "denied"),
])
def test_dismissal_detail_not_challenge_controls_silent_return(
        lifecycle, monkeypatch, surface, details, expected):
    # Private bus and existing owned worker only; no new shared resource.
    # A challenge indicates authentication is still possible, not dismissal.
    # Isolate final result classification; startup waiting is covered below.
    monkeypatch.setattr(authorization, "AGENT_STARTUP_GRACE_MS", 0)
    pending = lifecycle.start(surface)
    spin_until(lambda: lifecycle.authorities.checks)
    lifecycle.authorities.reply(challenge=True, details=details)
    spin_until(lambda: pending["done"])
    assert pending["result"][1] == expected
    assert lifecycle.accounts.events == []
    assert lifecycle.authorities.cancellations == []


@pytest.mark.parametrize("outcome", ("approved", "denied", "cancelled"))
def test_kiosk_waits_for_agent_then_preserves_terminal_authentication_result(lifecycle, outcome):
    authority = lifecycle.authorities
    pending = lifecycle.start("kiosk")
    spin_until(lambda: len(authority.checks) == 1)
    authority.reply(challenge=True)
    spin_until(lambda: len(authority.checks) == 2)
    assert not pending["done"]
    assert authority.checks[0]["parameters"] == authority.checks[1]["parameters"]
    with pytest.raises(Busy):
        lifecycle.broker.request_access(991, lifecycle.kiosk.get_unique_name(),
                                        1001, 1003, 300, True)
    authority.reply(authorized=outcome == "approved",
                    details={"polkit.dismissed": "true"} if outcome == "cancelled" else {})
    spin_until(lambda: pending["done"])
    assert pending["result"][1] == outcome
    assert len(authority.checks) == 2
    assert authority.cancellations == []
    if outcome != "approved":
        assert lifecycle.accounts.events == []


def test_kiosk_agent_startup_wait_is_bounded(lifecycle, monkeypatch):
    monkeypatch.setattr(authorization, "AGENT_STARTUP_GRACE_MS", 60)
    monkeypatch.setattr(authorization, "AGENT_RETRY_MS", 10)
    authority = lifecycle.authorities
    authority.on_check = lambda: authority.reply(challenge=True)
    pending = lifecycle.start("kiosk")
    spin_until(lambda: pending["done"])
    assert pending["result"][1] == "denied"
    assert 1 <= len(authority.checks) <= 7
    assert lifecycle.accounts.events == []
    assert authority.cancellations == []


@pytest.mark.parametrize("trigger", ("locked", "disconnect"))
def test_kiosk_agent_wait_cancels_before_another_challenge(lifecycle, monkeypatch, trigger):
    monkeypatch.setattr(authorization, "AGENT_RETRY_MS", 1000)
    authority = lifecycle.authorities
    pending = lifecycle.start("kiosk")
    spin_until(lambda: len(authority.checks) == 1)
    authority.reply(challenge=True)
    if trigger == "locked":
        authority.change({"LockedHint": True})
    else:
        close_connection(lifecycle.kiosk)
    spin_until(lambda: pending["done"])
    assert pending["result"][1] == "cancelled"
    assert len(authority.checks) == 1
    assert lifecycle.accounts.events == []
    assert authority.cancellations == []


def test_kiosk_lock_cancels_active_challenge_after_agent_retry(lifecycle):
    authority = lifecycle.authorities
    pending = lifecycle.start("kiosk")
    spin_until(lambda: len(authority.checks) == 1)
    authority.reply(challenge=True)
    spin_until(lambda: len(authority.checks) == 2)
    authority.change({"LockedHint": True})
    spin_until(lambda: pending["done"])
    assert pending["result"][1] == "cancelled"
    assert len(authority.cancellations) == 1
    assert all(item["done"] for item in authority.checks)
    assert lifecycle.accounts.events == []


@pytest.mark.parametrize("surface", ("child", "kiosk"))
@pytest.mark.parametrize("no_display", (False, True))
def test_sessionless_agent_can_authenticate_and_disconnect_still_cancels(
        lifecycle, surface, no_display):
    lifecycle.authorities.sessionless = not no_display
    lifecycle.authorities.fallback = no_display
    lifecycle.authorities.no_display = no_display
    pending = lifecycle.start(surface)
    spin_until(lambda: lifecycle.authorities.checks)
    close_connection(lifecycle.caller if surface == "child" else lifecycle.kiosk)
    spin_until(lambda: pending["done"])
    assert pending["result"][1] == "cancelled"
    if surface == "child":
        assert pending["result"][2] == 0
    assert len(lifecycle.authorities.cancellations) == 1
    assert lifecycle.accounts.events == []


@contextmanager
def pause_operation(monkeypatch, adapter, method, *, at_call=1):
    """Pause one existing owned worker; always release it before fixture cleanup."""
    entered, release = threading.Event(), threading.Event()
    original = getattr(adapter, method)
    calls = 0

    def paused(*args):
        nonlocal calls
        value = original(*args)
        calls += 1
        if calls == at_call:
            entered.set()
            assert release.wait(5), "test did not release its broker operation"
        return value

    monkeypatch.setattr(adapter, method, paused)
    try:
        yield entered, release
    finally:
        release.set()


@pytest.mark.parametrize("surface", ("child", "kiosk"))
@pytest.mark.parametrize("duration, stage", [
    (300, "usage"),
    *((duration, stage) for duration in (0, 300) for stage in (
        "preflight", "get_limit_type", "get_daily_limit", "get_filter", "get_extension",
    )),
])
def test_postauthentication_departure_through_last_snapshot_cancels_without_effects(
        lifecycle, monkeypatch, surface, duration, stage):
    authority = lifecycle.authorities
    adapter = (lifecycle.broker._timer_usage if stage == "usage" else
               lifecycle.broker._running_apps if stage == "preflight" else lifecycle.accounts)
    method = "query_usage_as" if stage == "usage" else stage
    at_call = 2 if stage == "get_extension" and duration else 1
    with pause_operation(monkeypatch, adapter, method, at_call=at_call) as (entered, release):
        pending = lifecycle.start(surface, duration=duration, allow_soft=False)
        spin_until(lambda: len(authority.checks) == 1)
        authority.reply(authorized=True)
        spin_until(entered.is_set)
        # Both transitions precede the final authoritative read. Even an
        # already-active returned session must not revive the earlier approval.
        authority.change({"Active": False})
        authority.change({"Active": True})
        release.set()
        spin_until(lambda: pending["done"])
    assert pending["result"][1] == "cancelled"
    assert not any(event[0].startswith("set_") for event in lifecycle.accounts.events)
    assert not any(call[0] == "terminate" for call in lifecycle.broker._running_apps.calls)
    assert authority.cancellations == []  # Authentication already completed.
    fresh = lifecycle.start(surface, duration=duration, allow_soft=False)
    spin_until(lambda: len(authority.checks) == 2)
    assert authority.checks[0]["parameters"][4] != authority.checks[1]["parameters"][4]
    authority.reply(authorized=True)
    spin_until(lambda: fresh["done"])
    assert fresh["result"][1] == "approved"
    assert pending["result"][0] != fresh["result"][0]
    assert sum(event[0] == "set_extension" for event in lifecycle.accounts.events) == 1


@pytest.mark.parametrize("surface", ("child", "kiosk"))
def test_postauthentication_disconnect_cannot_apply_approval(lifecycle, monkeypatch, surface):
    authority = lifecycle.authorities
    with pause_operation(monkeypatch, lifecycle.broker._timer_usage, "query_usage_as") as (entered, release):
        pending = lifecycle.start(surface)
        spin_until(lambda: authority.checks)
        authority.reply(authorized=True)
        spin_until(entered.is_set)
        close_connection(lifecycle.caller if surface == "child" else lifecycle.kiosk)
        release.set()
        spin_until(lambda: pending["done"])
    assert pending["result"][1] == "cancelled"
    assert not any(event[0].startswith("set_") for event in lifecycle.accounts.events)
    assert authority.cancellations == []


@pytest.mark.parametrize("surface", ("child", "kiosk"))
@pytest.mark.parametrize("trigger", ("display-replaced", "display-invalidated", "display-restored",
                                     "snapshot-error", "monitor-lost", "lock-at-final-read"))
def test_final_admission_keeps_original_session_and_fails_closed(
        lifecycle, monkeypatch, surface, trigger):
    authority = lifecycle.authorities
    authority.fallback = True
    with pause_operation(monkeypatch, lifecycle.broker._timer_usage, "query_usage_as") as (entered, release):
        pending = lifecycle.start(surface)
        spin_until(lambda: authority.checks)
        authority.reply(authorized=True)
        spin_until(entered.is_set)
        if trigger.startswith("display"):
            authority.change_display(("other", OTHER_SESSION), invalidated=trigger == "display-invalidated")
            if trigger == "display-restored":
                authority.change_display(("child", SESSION))
        elif trigger == "snapshot-error":
            authority.snapshot_error = True
        elif trigger == "lock-at-final-read":
            # GetAll captures an active snapshot and then publishes a lock.
            authority.on_snapshot = lambda: authority.change({"LockedHint": True})
        else:
            lifecycle.server.call_sync(
                DBUS_NAME, DBUS_PATH, DBUS_INTERFACE, "ReleaseName",
                GLib.Variant("(s)", (LOGIN_NAME,)), GLib.VariantType.new("(u)"),
                Gio.DBusCallFlags.NONE, 3000, None)
        release.set()
        spin_until(lambda: pending["done"])
    assert pending["result"][1] == "cancelled"
    assert not any(event[0].startswith("set_") for event in lifecycle.accounts.events)
    assert authority.cancellations == []


@pytest.mark.parametrize("surface", ("child", "kiosk"))
@pytest.mark.parametrize("fail_extension", (False, True))
def test_admitted_request_completes_once_or_rolls_back_after_departure(
        lifecycle, monkeypatch, surface, fail_extension):
    authority = lifecycle.authorities
    old_extension = lifecycle.accounts.extension
    lifecycle.accounts.fail_extension = fail_extension
    lifecycle.broker._running_apps.terminated = 1
    with pause_operation(monkeypatch, lifecycle.accounts, "set_daily_limit") as (entered, release):
        pending = lifecycle.start(surface, allow_soft=False)
        spin_until(lambda: authority.checks)
        authority.reply(authorized=True)
        spin_until(entered.is_set)  # The first policy write has been admitted.
        authority.change({"LockedHint": True})
        release.set()
        spin_until(lambda: pending["done"])
    assert lifecycle.accounts.filter == (False, ("/usr/bin/game", "org.example.Game"))
    assert authority.cancellations == []
    if fail_extension:
        assert isinstance(pending["error"], BackendFailure)
        assert lifecycle.accounts.extension == old_extension
        assert lifecycle.broker._last_request == {}
    else:
        assert pending["result"][1] == "approved"
        assert sum(event[0] == "set_extension" for event in lifecycle.accounts.events) == 1
        with pytest.raises(RateLimited):
            if surface == "child":
                lifecycle.broker.request_own_access(1001, lifecycle.caller.get_unique_name(),
                                                  1003, 300, True)
            else:
                lifecycle.broker.request_access(991, lifecycle.kiosk.get_unique_name(),
                                               1001, 1003, 300, True)


@pytest.mark.parametrize("surface", ("child", "kiosk"))
@pytest.mark.parametrize("no_display", (False, True))
def test_sessionless_approval_retains_bus_agent_compatibility(lifecycle, surface, no_display):
    lifecycle.authorities.sessionless = not no_display
    lifecycle.authorities.fallback = no_display
    lifecycle.authorities.no_display = no_display
    pending = lifecycle.start(surface)
    spin_until(lambda: lifecycle.authorities.checks)
    lifecycle.authorities.reply(authorized=True)
    spin_until(lambda: pending["done"])
    assert pending["result"][1] == "approved"
    if surface == "child":
        assert pending["result"][2] == 300
    assert lifecycle.accounts.extension[1] == 300
    assert sum(event[0] == "set_extension" for event in lifecycle.accounts.events) == 1
