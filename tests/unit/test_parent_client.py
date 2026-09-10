import unittest

from gi.repository import Gio, GLib

from parent.oh_no_parent_control_parent.client import (
    BUS_NAME,
    INTERFACE,
    OBJECT_PATH,
    BrokerClient,
)


class FakeConnection:
    """An administrator without retained AccountsService authorization."""

    def __init__(self, status=(1800, 600, 300, 2100), error=None):
        self.status = status
        self.error = error
        self.calls = []

    def call_sync(self, name, path, interface, method, parameters,
                  reply_type, flags, _timeout, _cancellable):
        unpacked = None if parameters is None else parameters.unpack()
        self.calls.append((name, path, interface, method, unpacked,
                           reply_type.dup_string(), flags))
        if name == "org.freedesktop.Accounts":
            raise Gio.DBusError.new_for_dbus_error(
                "org.freedesktop.Accounts.Error.PermissionDenied",
                "Authentication is required",
            )
        if name == "org.freedesktop.MalcontentTimer1" and method == "QueryUsage":
            return GLib.Variant("(a(tt))", ([],))
        if name == BUS_NAME and method == "GetPreferences":
            return GLib.Variant("(s)", (
                '{"parent_control_enabled": true, "daily_time_limit_minutes": 30}',
            ))
        if name == BUS_NAME and method == "GetTimeStatus":
            if self.error is not None:
                raise self.error
            return GLib.Variant("(uuuu)", self.status)
        raise AssertionError(f"unexpected call: {name} {method}")


class ParentClientTests(unittest.TestCase):
    def test_time_status_works_without_accountsservice_authorization(self):
        connection = FakeConnection()

        status = BrokerClient(connection).get_time_status(1001, 300)

        self.assertEqual(status, {
            "daily_allowance_remaining_seconds": 1800,
            "one_time_grant_remaining_seconds": 600,
            "additional_one_time_grant_seconds": 300,
            "calculated_active_extension_seconds": 2100,
        })
        self.assertEqual(connection.calls, [(
            BUS_NAME, OBJECT_PATH, INTERFACE, "GetTimeStatus", (1001, 300),
            "(uuuu)", Gio.DBusCallFlags.NONE,
        )])

    def test_periodic_refresh_uses_current_broker_status_without_adding_time(self):
        connection = FakeConnection(status=(0, 60, 0, 60))
        client = BrokerClient(connection)

        self.assertEqual(client.get_time_status(1001)["calculated_active_extension_seconds"], 60)
        connection.status = (0, 0, 0, 0)
        self.assertEqual(client.get_time_status(1001)["calculated_active_extension_seconds"], 0)
        connection.status = (0, 300, 0, 300)
        self.assertEqual(client.get_time_status(1002)["calculated_active_extension_seconds"], 300)

        self.assertEqual([call[3:5] for call in connection.calls], [
            ("GetTimeStatus", (1001, 0)),
            ("GetTimeStatus", (1001, 0)),
            ("GetTimeStatus", (1002, 0)),
        ])

    def test_broker_failures_reach_ui_without_fabricating_time_or_logging_pii(self):
        for name in ("AccessDenied", "BackendFailure"):
            with self.subTest(error=name):
                error = Gio.DBusError.new_for_dbus_error(
                    f"{BUS_NAME}.Error.{name}", "private-account-detail",
                )
                connection = FakeConnection(error=error)
                with self.assertLogs(
                        "parent.oh_no_parent_control_parent.client", level="WARNING") as logs:
                    with self.assertRaises(GLib.Error) as caught:
                        BrokerClient(connection).get_time_status(1001)

                self.assertIs(caught.exception, error)
                self.assertEqual(len(connection.calls), 1)
                self.assertIn("time-status stage=broker outcome=failed", logs.output[0])
                self.assertNotIn("private-account-detail", "\n".join(logs.output))
                self.assertNotIn("1001", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
