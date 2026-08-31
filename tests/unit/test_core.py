import threading
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from oh_no_parent_control.config import validate
from oh_no_parent_control.core import (
    AccessDenied, BackendFailure, Broker, Busy, RateLimited, RollbackFailure,
    seconds_until_local_midnight,
)
from test_config import valid_config


class Authorizer:
    def __init__(self, outcome="approved", callback=None):
        self.outcome = outcome
        self.calls = []
        self.callback = callback

    def check(self, sender, correlation_id):
        self.calls.append((sender, correlation_id))
        if self.callback:
            self.callback()
        return self.outcome


class Accounts:
    def __init__(self):
        self.filter = (False, ("old.App",))
        self.extension = (1, 2)
        self.events = []
        self.fail_extension = False
        self.fail_rollback = False

    def get_filter(self, uid):
        self.events.append(("get_filter", uid))
        return self.filter

    def set_filter(self, uid, value):
        self.events.append(("set_filter", uid, value))
        if self.fail_rollback and value == (False, ("old.App",)):
            raise RuntimeError("rollback failed")
        self.filter = value

    def get_extension(self, uid):
        self.events.append(("get_extension", uid))
        return self.extension

    def set_extension(self, uid, value):
        self.events.append(("set_extension", uid, value))
        if self.fail_extension:
            raise RuntimeError("failed")
        self.extension = value


def make_broker(authorizer=None, accounts=None, clock=None, alive=lambda _s: True):
    config = validate(valid_config())
    return Broker(lambda: config, authorizer or Authorizer(), accounts or Accounts(),
                  monotonic=clock or (lambda: 100),
                  now=lambda: datetime(2026, 8, 30, 10, tzinfo=ZoneInfo("America/Los_Angeles")),
                  caller_alive=alive)


class CoreTests(unittest.TestCase):
    def test_options_are_safe_and_shortest_first(self):
        options = make_broker().get_options(991)
        self.assertEqual(options.child_label, "Child")
        self.assertEqual(options.durations[0][0], "short")
        self.assertEqual(options.filter_profiles[0], ("", "No filter change"))

    def test_wrong_caller_denied(self):
        with self.assertRaises(AccessDenied):
            make_broker().get_options(1001)

    def test_denial_makes_no_writes_and_one_check(self):
        auth, accounts = Authorizer("denied"), Accounts()
        result = make_broker(auth, accounts).request_access(991, ":1.2", "short", "school")
        self.assertEqual(result[1], "denied")
        self.assertEqual(len(auth.calls), 1)
        self.assertEqual(accounts.events, [])

    def test_disconnected_caller_makes_no_writes(self):
        accounts = Accounts()
        result = make_broker(accounts=accounts, alive=lambda _s: False).request_access(
            991, ":1.2", "short", ""
        )
        self.assertEqual(result[1], "denied")
        self.assertEqual(accounts.events, [])

    def test_time_only_does_not_read_or_write_filter(self):
        accounts = Accounts()
        result = make_broker(accounts=accounts).request_access(991, ":1.2", "short", "")
        self.assertEqual(result[1], "approved")
        self.assertFalse(any("filter" in event[0] for event in accounts.events))

    def test_filter_precedes_extension_and_readback(self):
        accounts = Accounts()
        make_broker(accounts=accounts).request_access(991, ":1.2", "short", "school")
        names = [event[0] for event in accounts.events]
        self.assertLess(names.index("set_filter"), names.index("set_extension"))
        self.assertEqual(accounts.filter, (False, ("org.example.Game", "/usr/bin/game")))
        self.assertEqual(accounts.extension[1], 900)

    def test_extension_failure_rolls_filter_back(self):
        accounts = Accounts()
        accounts.fail_extension = True
        with self.assertRaises(BackendFailure):
            make_broker(accounts=accounts).request_access(991, ":1.2", "short", "school")
        self.assertEqual(accounts.filter, (False, ("old.App",)))

    def test_rollback_failure_is_escalated(self):
        accounts = Accounts()
        accounts.fail_extension = accounts.fail_rollback = True
        with self.assertRaises(RollbackFailure):
            make_broker(accounts=accounts).request_access(991, ":1.2", "short", "school")

    def test_rate_limit(self):
        broker = make_broker(clock=lambda: 100)
        broker.request_access(991, ":1.2", "short", "")
        with self.assertRaises(RateLimited):
            broker.request_access(991, ":1.3", "short", "")

    def test_concurrent_request_is_busy(self):
        entered, release = threading.Event(), threading.Event()
        auth = Authorizer(callback=lambda: (entered.set(), release.wait(2)))
        broker = make_broker(authorizer=auth)
        thread = threading.Thread(target=lambda: broker.request_access(991, ":1.2", "short", ""))
        thread.start()
        self.assertTrue(entered.wait(1))
        with self.assertRaises(Busy):
            broker.request_access(991, ":1.3", "short", "")
        release.set()
        thread.join()

    def test_local_midnight_dst_boundaries(self):
        zone = ZoneInfo("America/Los_Angeles")
        self.assertEqual(seconds_until_local_midnight(datetime(2026, 3, 7, 0, tzinfo=zone)), 86400)
        self.assertEqual(seconds_until_local_midnight(datetime(2026, 3, 8, 0, tzinfo=zone)), 23 * 3600)
        self.assertEqual(seconds_until_local_midnight(datetime(2026, 11, 1, 0, tzinfo=zone)), 25 * 3600)


if __name__ == "__main__":
    unittest.main()
