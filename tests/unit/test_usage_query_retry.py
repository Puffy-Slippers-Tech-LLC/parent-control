"""The real helper tolerates daemon-owner loss without retrying denial."""

from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from unittest.mock import Mock

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


@pytest.mark.parametrize("name", ("NoReply", "NameHasNoOwner", "ServiceUnknown"))
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
