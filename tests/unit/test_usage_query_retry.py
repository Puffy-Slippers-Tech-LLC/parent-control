"""The real helper bounds transient reads and retains terminal failure causes."""

from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from unittest.mock import Mock, call

import pytest
from gi.repository import Gio, GLib

from tests.support.paths import ROOT

loader = SourceFileLoader("onpc_usage_query", str(ROOT / "broker/oh-no-parent-control-query-usage"))
spec = spec_from_loader(loader.name, loader)
helper = module_from_spec(spec)
loader.exec_module(helper)


def dbus_error(name):
    return Gio.DBusError.new_for_dbus_error(
        "org.freedesktop.DBus.Error." + name, "private error details",
    )


@pytest.mark.parametrize("name", ("NoReply", "NameHasNoOwner", "ServiceUnknown", "Timeout", "TimedOut"))
def test_idle_shutdown_reactivates_same_service_and_preserves_query(name):
    connection = Mock()
    connection.call_sync.side_effect = [
        dbus_error(name), GLib.Variant("(a(tt))", ([(10, 20)],)),
    ]
    sleep = Mock()
    assert helper.query_usage(connection, 1001, sleep=sleep) == [(10, 20)]
    sleep.assert_called_once_with(helper.RETRY_DELAY_SECONDS)
    first, retry = connection.call_sync.call_args_list
    assert first.args[:4] == retry.args[:4]
    assert retry.args[4].unpack() == (1001, "login-session", "")
    assert retry.args[7] <= first.args[7] <= helper.CALL_TIMEOUT_MS


@pytest.mark.parametrize("name", ("AccessDenied", "InvalidArgs", "Failed"))
def test_permanent_errors_are_not_retried(name):
    connection = Mock(call_sync=Mock(side_effect=dbus_error(name)))
    sleep = Mock()
    with pytest.raises(GLib.Error):
        helper.query_usage(connection, 1001, sleep=sleep)
    assert connection.call_sync.call_count == 1
    sleep.assert_not_called()


def test_repeated_owner_loss_is_bounded_and_never_returns_empty_usage():
    connection = Mock(call_sync=Mock(side_effect=dbus_error("NoReply")))
    sleep = Mock()
    with pytest.raises(GLib.Error):
        helper.query_usage(connection, 1001, sleep=sleep)
    assert connection.call_sync.call_count == 3
    assert sleep.call_count == 2


def test_timeout_budget_is_shared_by_attempts():
    clock = Mock(side_effect=[0, 0, 25])
    connection = Mock(call_sync=Mock(side_effect=dbus_error("NoReply")))
    sleep = Mock()
    with pytest.raises(GLib.Error):
        helper.query_usage(connection, 1001, monotonic=clock, sleep=sleep)
    assert connection.call_sync.call_count == 1
    sleep.assert_not_called()


def busy_error():
    return Gio.DBusError.new_for_dbus_error(
        "org.freedesktop.MalcontentTimer1.Parent.Error.Busy", "private error details")


def test_busy_database_recovers_with_bounded_backoff_and_identical_query():
    connection = Mock()
    connection.call_sync.side_effect = [
        busy_error(), busy_error(), GLib.Variant("(a(tt))", ([(10, 20)],)),
    ]
    sleep = Mock()
    assert helper.query_usage(connection, 1001, sleep=sleep) == [(10, 20)]
    assert sleep.call_args_list == [call(0.1), call(0.25)]
    first = connection.call_sync.call_args_list[0].args
    for invocation in connection.call_sync.call_args_list:
        args = invocation.args
        assert args[:4] == first[:4]
        assert args[4].get_type_string() == "(uss)"
        assert args[4].unpack() == (1001, "login-session", "")
        assert args[5].dup_string() == "(a(tt))"
        assert args[6] == Gio.DBusCallFlags.NONE


def test_persistent_busy_retains_original_error_after_finite_attempts():
    original = busy_error()
    connection = Mock(call_sync=Mock(side_effect=original))
    sleep = Mock()
    with pytest.raises(GLib.Error) as raised:
        helper.query_usage(connection, 1001, sleep=sleep)
    assert raised.value is original
    assert connection.call_sync.call_count == 6
    assert sleep.call_args_list == [call(delay) for delay in (0.1, 0.25, 0.5, 1.0, 2.0)]


def test_busy_reads_and_waits_share_one_total_budget():
    now = [0]
    original = busy_error()

    def query(*args):
        now[0] += args[7] / 1000
        raise original

    def sleep(delay):
        now[0] += delay

    connection = Mock(call_sync=Mock(side_effect=query))
    with pytest.raises(GLib.Error) as raised:
        helper.query_usage(connection, 1001, monotonic=lambda: now[0], sleep=sleep)
    assert raised.value is original
    assert 24.9 <= now[0] <= 25
    assert connection.call_sync.call_count <= 6
    assert all(0 < args.args[7] <= 5000 for args in connection.call_sync.call_args_list)


def test_overdue_retry_preserves_cause_without_dispatching_after_deadline():
    original = dbus_error("NoReply")
    connection = Mock(call_sync=Mock(side_effect=original))
    sleep = Mock()
    with pytest.raises(GLib.Error) as raised:
        helper.query_usage(connection, 1001, monotonic=Mock(side_effect=[0, 0, 0, 26]), sleep=sleep)
    assert raised.value is original
    assert connection.call_sync.call_count == 1
    sleep.assert_called_once_with(0.2)


def test_budget_expiring_before_first_read_is_a_timeout_not_zero_usage():
    connection = Mock()
    with pytest.raises(GLib.Error) as raised:
        helper.query_usage(connection, 1001, monotonic=Mock(side_effect=[0, 26]))
    assert helper.timer_error_category(raised.value) == "timeout"
    connection.call_sync.assert_not_called()


@pytest.mark.parametrize("error,category", [
    (busy_error(), "busy"), (dbus_error("NoReply"), "no-reply"),
    (dbus_error("NameHasNoOwner"), "no-owner"), (dbus_error("ServiceUnknown"), "service-unknown"),
    (dbus_error("Timeout"), "timeout"), (dbus_error("AccessDenied"), "access-denied"),
    (dbus_error("InvalidArgs"), "invalid-argument"), (dbus_error("Failed"), "failed"),
    (dbus_error("Disconnected"), "disconnected"),
])
def test_terminal_helper_status_preserves_reviewed_cause_without_private_output(
        monkeypatch, capsys, error, category):
    from oh_no_parent_control.adapters import USAGE_HELPER_ERROR_CATEGORIES

    monkeypatch.setattr(helper.os, "geteuid", lambda: 1001)
    monkeypatch.setattr(helper.sys, "argv", ["query-usage", "1001"])
    monkeypatch.setattr(helper.Gio, "bus_get_sync", Mock())
    monkeypatch.setattr(helper, "query_usage", Mock(side_effect=error))
    status = helper.main()
    assert USAGE_HELPER_ERROR_CATEGORIES[status] == category
    assert capsys.readouterr() == ("", "")


def test_helper_and_adapter_exit_status_contract_match():
    from oh_no_parent_control.adapters import USAGE_HELPER_ERROR_CATEGORIES

    assert {status: category for category, status in helper.ERROR_EXIT_CODES.items()} == \
        USAGE_HELPER_ERROR_CATEGORIES


@pytest.mark.parametrize("name", (
    "private.secret.Error.Busy", "org.freedesktop.MalcontentTimer1.Error.Busy",
    "org.freedesktop.MalcontentTimer1.Child.Error.Busy",
    "org.freedesktop.MalcontentTimer1.Child.Error.IdentifyingUser",
    "org.freedesktop.MalcontentTimer1.Parent.Error.IdentifyingUser",
))
def test_unreviewed_or_identity_remote_error_is_not_retried_or_emitted(name, monkeypatch, capsys):
    original = Gio.DBusError.new_for_dbus_error(name, "private error details")
    connection = Mock(call_sync=Mock(side_effect=original))
    sleep = Mock()
    with pytest.raises(GLib.Error) as raised:
        helper.query_usage(connection, 1001, sleep=sleep)
    assert raised.value is original
    assert helper.timer_error_category(raised.value) == "other"
    assert connection.call_sync.call_count == 1
    sleep.assert_not_called()
    monkeypatch.setattr(helper.os, "geteuid", lambda: 1001)
    monkeypatch.setattr(helper.sys, "argv", ["query-usage", "1001"])
    monkeypatch.setattr(helper.Gio, "bus_get_sync", Mock(return_value=connection))
    assert helper.main() == 69
    assert connection.call_sync.call_count == 2
    assert capsys.readouterr() == ("", "")
