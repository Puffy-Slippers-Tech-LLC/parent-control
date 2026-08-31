import json
import os
import stat
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

from oh_no_parent_control.config import ConfigurationError, load, validate, validate_target


def valid_config():
    return {
        "version": 1,
        "kiosk_uid": 991,
        "child_uid": 1001,
        "child_label": "Child",
        "durations": {
            "short": {"label": "15 minutes", "seconds": 900},
            "today": {"label": "Rest of today", "seconds": "local-midnight"},
        },
        "app_filter_profiles": {
            "school": {"label": "School", "blocked_targets": ["org.example.Game", "/usr/bin/game"]}
        },
        "minimum_request_interval_seconds": 5,
    }


class ConfigTests(unittest.TestCase):
    def test_valid(self):
        config = validate(valid_config())
        self.assertEqual(config.child_uid, 1001)
        self.assertEqual(config.app_filter_profiles["school"].blocked_targets[0], "org.example.Game")

    def test_unknown_keys_rejected_at_each_level(self):
        for mutate in (
            lambda c: c.update(extra=True),
            lambda c: c["durations"]["short"].update(extra=True),
            lambda c: c["app_filter_profiles"]["school"].update(extra=True),
        ):
            value = valid_config()
            mutate(value)
            with self.assertRaises(ConfigurationError):
                validate(value)

    def test_uid_rules(self):
        for kiosk, child in ((0, 1001), (1001, 1001), (991, 999), (991, 0)):
            value = valid_config()
            value["kiosk_uid"], value["child_uid"] = kiosk, child
            with self.assertRaises(ConfigurationError):
                validate(value)

    def test_malformed_choices(self):
        mutations = (
            lambda c: c.update(durations={}),
            lambda c: c["durations"]["short"].update(seconds=0),
            lambda c: c["durations"].update({"Bad ID": {"label": "x", "seconds": 1}}),
            lambda c: c["app_filter_profiles"]["school"].update(blocked_targets=["bad"]),
            lambda c: c["app_filter_profiles"]["school"].update(blocked_targets=["/a/../b"]),
            lambda c: c.update(minimum_request_interval_seconds=0),
        )
        for mutate in mutations:
            value = valid_config()
            mutate(value)
            with self.assertRaises(ConfigurationError):
                validate(value)

    def test_target_forms(self):
        self.assertEqual(validate_target("org.example.App"), "org.example.App")
        self.assertEqual(validate_target("/usr/bin/example"), "/usr/bin/example")
        for value in ("example", "../bin/x", "relative/path", "/", "/a/../b", ""):
            with self.assertRaises(ConfigurationError):
                validate_target(value)

    def test_duplicate_json_key(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as stream:
            stream.write('{"version":1,"version":1}')
            path = stream.name
        try:
            with self.assertRaisesRegex(ConfigurationError, "duplicate key"):
                load(path, require_secure_file=False)
        finally:
            os.unlink(path)

    def test_secure_file_checks_owner_and_mode(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as stream:
            json.dump(valid_config(), stream)
            path = stream.name
        try:
            parent = SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
            file_info = SimpleNamespace(st_mode=stat.S_IFREG | 0o622, st_uid=0)
            with mock.patch("pathlib.Path.stat", return_value=parent), \
                    mock.patch("os.fstat", return_value=file_info):
                with self.assertRaises(ConfigurationError):
                    load(path)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
