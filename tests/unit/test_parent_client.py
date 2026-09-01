import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from gi.repository import GLib

from parent.oh_no_parent_control_parent.client import (
    ACCOUNTS_NAME,
    BUS_NAME,
    TIMER_NAME,
    BrokerClient,
)


class FakeConnection:
    def __init__(self, now):
        self.now = now
        self.calls = []

    def call_sync(self, name, path, interface, method, parameters,
                  _reply_type, _flags, _timeout, _cancellable):
        unpacked = None if parameters is None else parameters.unpack()
        self.calls.append((name, path, interface, method, unpacked))
        start_of_day = datetime.combine(
            self.now.date(), datetime.min.time(), tzinfo=self.now.tzinfo,
        )
        day = int(start_of_day.timestamp())
        if name == TIMER_NAME and method == "QueryUsage":
            return GLib.Variant("(a(tt))", ([
                (day - 60, day + 30),
                (day + 60, day + 120),
                (day + 90, day + 150),
            ],))
        if name == BUS_NAME and method == "GetPreferences":
            encoded = json.dumps({
                "parent_control_enabled": True,
                "daily_time_limit_minutes": 32,
            })
            return GLib.Variant("(s)", (encoded,))
        if name == ACCOUNTS_NAME and method == "Get":
            extension = GLib.Variant("(tu)", (
                int(self.now.timestamp()), 10 * 60,
            ))
            return GLib.Variant("(v)", (extension,))
        if name == BUS_NAME and method == "CalculateRemainingTime":
            _uid, daily, grant, additional = unpacked
            return GLib.Variant("(u)", (max(daily, grant) + additional,))
        raise AssertionError(f"unexpected call: {name} {method}")


class ParentClientTests(unittest.TestCase):
    def test_time_status_reads_usage_as_parent_and_uses_broker_formula(self):
        now = datetime(2026, 8, 31, 10, tzinfo=ZoneInfo("America/Los_Angeles"))
        connection = FakeConnection(now)

        status = BrokerClient(connection, now=lambda: now).get_time_status(1001, 5 * 60)

        # 30 seconds before midnight plus the overlapping 60..150 interval is
        # two minutes used today, leaving 30 minutes of a 32-minute allowance.
        self.assertEqual(status, {
            "daily_allowance_remaining_seconds": 30 * 60,
            "one_time_grant_remaining_seconds": 10 * 60,
            "additional_one_time_grant_seconds": 5 * 60,
            "calculated_active_extension_seconds": 35 * 60,
        })
        timer_call = connection.calls[0]
        self.assertEqual(timer_call[0], TIMER_NAME)
        self.assertEqual(timer_call[3:], (
            "QueryUsage", (1001, "login-session", ""),
        ))
        formula_call = connection.calls[-1]
        self.assertEqual(formula_call[0], BUS_NAME)
        self.assertEqual(formula_call[3:], (
            "CalculateRemainingTime", (1001, 30 * 60, 10 * 60, 5 * 60),
        ))


if __name__ == "__main__":
    unittest.main()
