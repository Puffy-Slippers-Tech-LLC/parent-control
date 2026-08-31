import tempfile
import unittest
from pathlib import Path

from oh_no_parent_control.preferences import (
    PreferenceStore, PreferencesError, blocked_targets, default_preferences,
    validate_preferences,
)


class PreferenceTests(unittest.TestCase):
    def test_store_round_trip_is_per_child(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PreferenceStore(Path(directory))
            first = default_preferences()
            first["request"]["last_selected_duration"] = "custom"
            first["request"]["last_custom_minutes"] = 12.5
            store.save(1001, first)
            self.assertEqual(store.load(1001)["request"]["last_custom_minutes"], 12.5)
            self.assertEqual(store.load(1002), default_preferences())

    def test_three_state_policy_computes_filters(self):
        value = default_preferences()
        value["apps"] = {
            "hard.desktop": {"state": "permanent", "targets": ["/usr/bin/hard"]},
            "soft.desktop": {"state": "conditional", "targets": ["org.example.Soft"]},
        }
        value = validate_preferences(value)
        self.assertEqual(blocked_targets(value, False), ("/usr/bin/hard", "org.example.Soft"))
        self.assertEqual(blocked_targets(value, True), ("/usr/bin/hard",))

    def test_invalid_request_value_is_rejected(self):
        value = default_preferences()
        value["request"]["last_selected_duration"] = "123"
        with self.assertRaises(PreferencesError):
            validate_preferences(value)


if __name__ == "__main__":
    unittest.main()
