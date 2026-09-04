import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from oh_no_parent_control.uninstall import (
    UninstallCleaner, UninstallCleanupError, managed_uids,
)


class Accounts:
    def __init__(self, uids):
        self.values = {
            uid: {
                "limit_type": 1,
                "daily_limit": 3600,
                "extension": (100, 200),
                "filter": (False, ("/usr/bin/game",)),
            }
            for uid in uids
        }
        self.events = []
        self.fail_uid = None
        self.sync_count = 0

    def _set(self, uid, key, value):
        self.events.append(("set", key, uid, value))
        if uid == self.fail_uid and key == "daily_limit":
            raise RuntimeError("fixture failure")
        self.values[uid][key] = value

    def set_limit_type(self, uid, value):
        self._set(uid, "limit_type", value)

    def set_daily_limit(self, uid, value):
        self._set(uid, "daily_limit", value)

    def set_extension(self, uid, value):
        self._set(uid, "extension", value)

    def set_filter(self, uid, value):
        self._set(uid, "filter", value)

    def get_limit_type(self, uid):
        return self.values[uid]["limit_type"]

    def get_daily_limit(self, uid):
        return self.values[uid]["daily_limit"]

    def get_extension(self, uid):
        return self.values[uid]["extension"]

    def get_filter(self, uid):
        return self.values[uid]["filter"]

    def sync_execution_policy(self):
        self.sync_count += 1


class Extensions:
    def __init__(self):
        self.events = []

    def set_enabled(self, uid, enabled):
        self.events.append((uid, enabled))

    def remove(self, uid):
        self.events.append((uid, "removed"))


class Policy:
    def __init__(self):
        self.remove_count = 0

    def remove(self):
        self.remove_count += 1


class Preferences:
    def __init__(self, enabled=True):
        self.enabled = enabled

    def load(self, _uid):
        return {"parent_control_enabled": self.enabled}


class UninstallTests(unittest.TestCase):
    def test_discovers_only_secure_extant_uid_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "1002.json").write_text("{}", encoding="utf-8")
            (directory / "1001.json").write_text("{}", encoding="utf-8")
            (directory / "deleted-1003.json").write_text("{}", encoding="utf-8")
            (directory / "1002.json").chmod(0o600)
            (directory / "1001.json").chmod(0o600)
            lookup = mock.Mock(side_effect=lambda uid: (
                SimpleNamespace(pw_uid=uid) if uid == 1002 else (_ for _ in ()).throw(KeyError(uid))
            ))

            result = managed_uids(
                directory, required_owner=os.getuid(), account_lookup=lookup,
            )

        self.assertEqual(result, (1002,))

    def test_rejects_an_unsafe_preference_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            record = directory / "1001.json"
            record.write_text("{}", encoding="utf-8")
            record.chmod(0o666)

            with self.assertRaisesRegex(UninstallCleanupError, "ownership is unsafe"):
                managed_uids(
                    directory, required_owner=os.getuid(),
                    account_lookup=lambda uid: SimpleNamespace(pw_uid=uid),
                )

    @mock.patch("oh_no_parent_control.uninstall.os.geteuid", return_value=0)
    def test_clears_and_verifies_every_derived_state(self, _geteuid):
        accounts = Accounts((1001, 1002))
        extensions = Extensions()
        policy = Policy()

        with tempfile.TemporaryDirectory() as temporary:
            snapshot = Path(temporary) / "uninstall-enforcement.json"
            UninstallCleaner(
                accounts, extensions, policy, Preferences(), snapshot,
                snapshot_owner=os.getuid(),
            ).remove((1001, 1002))

            self.assertTrue(snapshot.exists())

        for values in accounts.values.values():
            self.assertEqual(values, {
                "limit_type": 0,
                "daily_limit": 0,
                "extension": (0, 0),
                "filter": (False, ()),
            })
        self.assertEqual(
            extensions.events, [(1001, "removed"), (1002, "removed")],
        )
        self.assertEqual(policy.remove_count, 1)

    @mock.patch("oh_no_parent_control.uninstall.os.geteuid", return_value=0)
    def test_attempts_all_accounts_and_policy_before_reporting_failure(self, _geteuid):
        accounts = Accounts((1001, 1002))
        accounts.fail_uid = 1001
        extensions = Extensions()
        policy = Policy()

        with tempfile.TemporaryDirectory() as temporary, self.assertRaisesRegex(
                UninstallCleanupError, "could not be verified"):
            UninstallCleaner(
                accounts, extensions, policy, Preferences(),
                Path(temporary) / "uninstall-enforcement.json",
                snapshot_owner=os.getuid(),
            ).remove((1001, 1002))

        self.assertIn(("set", "filter", 1002, (False, ())), accounts.events)
        self.assertEqual(policy.remove_count, 1)

    @mock.patch("oh_no_parent_control.uninstall.os.geteuid", return_value=0)
    def test_abort_remove_restores_the_exact_snapshot(self, _geteuid):
        accounts = Accounts((1001,))
        extensions = Extensions()
        policy = Policy()
        with tempfile.TemporaryDirectory() as temporary:
            snapshot = Path(temporary) / "uninstall-enforcement.json"
            cleaner = UninstallCleaner(
                accounts, extensions, policy, Preferences(), snapshot,
                snapshot_owner=os.getuid(),
            )
            cleaner.remove((1001,))
            cleaner.restore()

            self.assertFalse(snapshot.exists())

        self.assertEqual(accounts.values[1001], {
            "limit_type": 1,
            "daily_limit": 3600,
            "extension": (100, 200),
            "filter": (False, ("/usr/bin/game",)),
        })
        self.assertEqual(extensions.events[-1], (1001, True))
        self.assertEqual(accounts.sync_count, 1)


if __name__ == "__main__":
    unittest.main()
