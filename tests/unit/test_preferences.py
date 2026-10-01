import tempfile
import unittest
from pathlib import Path
from unittest import mock

from oh_no_parent_control.preferences import (
    PreferenceStore, PreferencesError, blocked_patterns, blocked_targets, default_preferences,
    validate_preferences, validate_language,
)


class PreferenceTests(unittest.TestCase):
    def test_language_persists_per_user_and_reset_follows_session(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preferences"
            store = PreferenceStore(path)
            self.assertEqual(store.load(1001)["personal"]["language"], "")
            self.assertFalse(path.exists())
            for uid, language in ((0, "en"), (991, "de"), (1001, "zh-Hans"),
                                  (1003, "pt-BR")):
                self.assertEqual(store.update_language(uid, language), language)
                self.assertEqual(PreferenceStore(path).load(uid)["personal"]["language"], language)
                self.assertEqual((path / f"{uid}.json").stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)
            self.assertEqual(store.load(1002)["personal"]["language"], "")
            store.update_language(1001, "")
            self.assertEqual(PreferenceStore(path).load(1001)["personal"]["language"], "")
            self.assertEqual(store.load(1003)["personal"]["language"], "pt-BR")

    def test_language_rejects_invalid_inputs_before_writing(self):
        for language in (None, True, 1, "../en", "en_US.UTF-8", "en:fr",
                         " en", "en\n", "en--US", "e", "en-" + "a" * 64):
            with self.subTest(language=language), self.assertRaises(PreferencesError):
                validate_language(language)
        with tempfile.TemporaryDirectory() as directory:
            store = PreferenceStore(Path(directory))
            for uid in (-1, True, "1001", 2 ** 32):
                with self.subTest(uid=uid), self.assertRaises(PreferencesError):
                    store.update_language(uid, "en")
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_language_corrupt_or_future_data_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PreferenceStore(Path(directory))
            path = Path(directory) / "1001.json"
            from json import dumps
            current = default_preferences()
            invalid_language = {**current, "personal": {"language": "../fr"}}
            for content in ('{', 'null', dumps({**current, "version": 5}),
                            dumps({**current, "version": True}),
                            dumps(current).replace('"language": ""', '"language": "en", "language": "fr"'),
                            dumps(invalid_language), dumps({**current, "extra": True})):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(PreferencesError):
                    store.load(1001)
                with self.assertRaises(PreferencesError):
                    store.update_language(1001, "en")
                self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_personal_only_records_normalize_defaults_without_claiming_policy(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            store = PreferenceStore(Path(directory))
            store.update_language(1001, "fr")
            path = Path(directory) / "1001.json"
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")),
                             {"version": 4, "personal": {"language": "fr"}})
            self.assertEqual(store.load(1001),
                             {**default_preferences(), "personal": {"language": "fr"}})
            store.save(1001, default_preferences())
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("parent_control_enabled", raw)
            self.assertEqual(raw["personal"]["language"], "fr")

    def test_language_failed_replace_keeps_prior_selection_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PreferenceStore(Path(directory))
            store.update_language(1001, "fr")
            with mock.patch("oh_no_parent_control.preferences.os.replace",
                            side_effect=OSError("write failed")):
                with self.assertRaises(OSError):
                    store.update_language(1001, "de")
            self.assertEqual(store.load(1001)["personal"]["language"], "fr")
            self.assertEqual([p.name for p in Path(directory).iterdir()], ["1001.json"])


    def test_language_and_policy_share_record_and_stale_policy_preserves_personal(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PreferenceStore(Path(directory))
            policy = default_preferences()
            policy["daily_time_limit_minutes"] = 37
            policy["request"]["last_custom_minutes"] = 12.5
            store.save(1001, policy)
            stale = store.load(1001)
            store.update_language(1001, "fr")
            stale["daily_time_limit_minutes"] = 42
            # This is the same common save path used by policy commits/rollback.
            saved = store.save(1001, stale)
            self.assertEqual(saved["personal"]["language"], "fr")
            self.assertEqual(saved["daily_time_limit_minutes"], 42)
            self.assertEqual(saved["request"]["last_custom_minutes"], 12.5)
            store.update_request(1001, "custom", 20, True)
            store.update_request_muted(1001, "child", False)
            self.assertEqual(store.load(1001)["personal"]["language"], "fr")
            self.assertEqual([p.name for p in Path(directory).iterdir()], ["1001.json"])

    def test_language_read_modify_write_serializes_with_policy_save(self):
        import threading
        with tempfile.TemporaryDirectory() as directory:
            store = PreferenceStore(Path(directory))
            stale = store.load(1001)
            stale["daily_time_limit_minutes"] = 42
            entered, release, policy_started = (threading.Event() for _ in range(3))
            original = store._write
            errors = []

            def write(uid, value):
                if value["personal"]["language"] == "fr" and value.get("daily_time_limit_minutes", 0) == 0:
                    entered.set()
                    if not release.wait(5):
                        raise RuntimeError("language write was not released")
                return original(uid, value)

            def run(operation):
                try:
                    operation()
                except Exception as error:
                    errors.append(error)

            def save_policy():
                policy_started.set()
                store.save(1001, stale)

            with mock.patch.object(store, "_write", side_effect=write):
                language = threading.Thread(target=run, args=(lambda: store.update_language(1001, "fr"),))
                policy = threading.Thread(target=run, args=(save_policy,))
                language.start()
                try:
                    self.assertTrue(entered.wait(5))
                    policy.start()
                    self.assertTrue(policy_started.wait(5))
                finally:
                    release.set()
                    language.join(5)
                    if policy.ident is not None:
                        policy.join(5)
                self.assertFalse(language.is_alive())
                self.assertFalse(policy.is_alive())
            self.assertEqual(errors, [])
            saved = store.load(1001)
            self.assertEqual(saved["personal"]["language"], "fr")
            self.assertEqual(saved["daily_time_limit_minutes"], 42)

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
            "hard.desktop": {"state": "permanent", "targets": ["/usr/bin/hard"], "patterns": [], "user_saved_match_rule": False},
            "soft.desktop": {"state": "conditional", "targets": ["org.example.Soft"], "patterns": [], "user_saved_match_rule": False},
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
                "user_saved_match_rule": True,
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

    def test_user_saved_match_rule_is_retained_when_access_is_allowed(self):
        value = default_preferences()
        value["apps"] = {
            "game.desktop": {
                "state": "allowed",
                "targets": ["/usr/bin/game"],
                "patterns": [],
                "user_saved_match_rule": True,
            },
        }

        normalized = validate_preferences(value)

        self.assertTrue(normalized["apps"]["game.desktop"]["user_saved_match_rule"])

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

    def test_current_format_without_request_ui_fields_uses_muted_defaults(self):
        value = default_preferences()
        value["request"] = {
            "last_selected_duration": "1800",
            "last_custom_minutes": 0.1,
            "allow_soft_blocked_apps": False,
        }

        normalized = validate_preferences(value)

        self.assertEqual(normalized["request"]["last_selected_approver_uid"], 0)
        self.assertTrue(normalized["request"]["kiosk_muted"])
        self.assertTrue(normalized["request"]["child_muted"])

    def test_unknown_preference_key_is_rejected(self):
        value = default_preferences()
        value["unexpected"] = True

        with self.assertRaises(PreferencesError):
            validate_preferences(value)


if __name__ == "__main__":
    unittest.main()
