import tempfile
import unittest
from pathlib import Path

from oh_no_parent_control.preferences import (
    PreferenceStore, PreferencesError, blocked_patterns, blocked_targets, default_preferences,
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
            "hard.desktop": {"state": "permanent", "targets": ["/usr/bin/hard"], "patterns": []},
            "soft.desktop": {"state": "conditional", "targets": ["org.example.Soft"], "patterns": []},
        }
        value = validate_preferences(value)
        self.assertEqual(blocked_targets(value, False), ("/usr/bin/hard", "org.example.Soft"))
        self.assertEqual(blocked_targets(value, True), ("/usr/bin/hard",))

    def test_pattern_must_share_its_target_directory_and_follows_soft_state(self):
        value = default_preferences()
        value["apps"] = {
            "lunar.desktop": {
                "state": "conditional",
                "targets": ["/home/child/Applications/Lunar Client-3.7.17.AppImage"],
                "patterns": ["/home/child/Applications/Lunar Client-*.AppImage"],
            },
        }
        normalized = validate_preferences(value)
        self.assertEqual(blocked_patterns(normalized, False), (
            "/home/child/Applications/Lunar Client-*.AppImage",
        ))
        self.assertEqual(blocked_patterns(normalized, True), ())
        value["apps"]["lunar.desktop"]["patterns"] = ["/tmp/Lunar-*.AppImage"]
        with self.assertRaisesRegex(PreferencesError, "share a directory"):
            validate_preferences(value)

    def test_invalid_request_value_is_rejected(self):
        value = default_preferences()
        value["request"]["last_selected_duration"] = "123"
        with self.assertRaises(PreferencesError):
            validate_preferences(value)

    def test_daily_time_limit_is_an_integer_from_zero_to_one_day(self):
        for minutes in (0, 1, 24 * 60):
            with self.subTest(minutes=minutes):
                value = default_preferences()
                value["daily_time_limit_minutes"] = minutes
                self.assertEqual(
                    validate_preferences(value)["daily_time_limit_minutes"], minutes,
                )

        for minutes in (-1, 1441, 1.5, True):
            with self.subTest(minutes=minutes):
                value = default_preferences()
                value["daily_time_limit_minutes"] = minutes
                with self.assertRaises(PreferencesError):
                    validate_preferences(value)

    def test_current_format_without_daily_limit_uses_grant_only_default(self):
        value = default_preferences()
        del value["daily_time_limit_minutes"]

        normalized = validate_preferences(value)

        self.assertEqual(normalized["daily_time_limit_minutes"], 0)

    def test_unknown_preference_key_is_rejected(self):
        value = default_preferences()
        value["unexpected"] = True

        with self.assertRaises(PreferencesError):
            validate_preferences(value)


if __name__ == "__main__":
    unittest.main()
