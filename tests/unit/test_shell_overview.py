"""Overview transitions wait for state and cannot fall back to the host bus."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.ui import shell_overview


@pytest.mark.parametrize('active', [True, False])
@pytest.mark.parametrize('suffix', ['', ',guid=' + 'a' * 32])
def test_overview_waits_for_observed_state_on_owned_bus(monkeypatch, active, suffix):
    monkeypatch.setenv('ONPC_CHILD_SHELL_ARTIFACT_DIR', '/tmp/onpc-child-owned')
    address = 'unix:path=/tmp/onpc-child-owned/runtime/session-bus' + suffix
    monkeypatch.setenv('DBUS_SESSION_BUS_ADDRESS', address)
    connection = Mock()
    replies = iter([None, SimpleNamespace(unpack=lambda: (not active,)),
                    SimpleNamespace(unpack=lambda: (active,))])
    connection.call_sync.side_effect = lambda *args: next(replies)
    connect = Mock(return_value=connection)
    monkeypatch.setattr(shell_overview.Gio.DBusConnection, 'new_for_address_sync', connect)

    def wait(predicate, description):
        assert 'private Shell' in description
        assert predicate() is False
        assert predicate() is True

    shell_overview.set_overview(active, wait)
    assert connect.call_args.args[0] == address
    calls = connection.call_sync.call_args_list
    assert [call.args[3] for call in calls] == ['Set', 'Get', 'Get']
    assert calls[0].args[4].unpack() == ('org.gnome.Shell', 'OverviewActive', active)
    connection.close_sync.assert_called_once_with(None)


@pytest.mark.parametrize('address', ['unix:path=/run/user/1000/bus',
    'unix:path=/tmp/onpc-child-owned/runtime/session-bus;unix:path=/run/user/1000/bus',
    'unix:path=/tmp/onpc-child-owned/runtime/session-bus,guid=invalid'])
def test_foreign_bus_refused_before_any_connection(monkeypatch, address):
    monkeypatch.setenv('ONPC_CHILD_SHELL_ARTIFACT_DIR', '/tmp/onpc-child-owned')
    monkeypatch.setenv('DBUS_SESSION_BUS_ADDRESS', address)
    connect = Mock()
    monkeypatch.setattr(shell_overview.Gio.DBusConnection, 'new_for_address_sync', connect)
    with pytest.raises(ValueError, match='owned nested-Shell bus'):
        shell_overview.set_overview(True, Mock())
    connect.assert_not_called()


def test_failed_transition_closes_connection_without_retry(monkeypatch):
    monkeypatch.setenv('ONPC_CHILD_SHELL_ARTIFACT_DIR', '/tmp/onpc-child-owned')
    monkeypatch.setenv('DBUS_SESSION_BUS_ADDRESS', 'unix:path=/tmp/onpc-child-owned/runtime/session-bus')
    connection = Mock()
    monkeypatch.setattr(shell_overview.Gio.DBusConnection, 'new_for_address_sync',
                        Mock(return_value=connection))
    with pytest.raises(AssertionError, match='transition failed'):
        shell_overview.set_overview(True, Mock(side_effect=AssertionError('transition failed')))
    connection.call_sync.assert_called_once()
    connection.close_sync.assert_called_once_with(None)
