import tempfile
import unittest
import json
import pytest
from pathlib import Path
from unittest import mock

from oh_no_parent_control.preferences import (
    PreferenceStore, PreferencesError, blocked_patterns, blocked_targets, default_preferences,
    validate_preferences, validate_language, validate_notifications, default_notifications,
    DEFAULT_TIME_GRANT_PRESETS, validate_time_grant_presets, time_grant_choices,
)


def test_time_grant_preset_crud_sorting_and_preservation(tmp_path):
    store = PreferenceStore(tmp_path)
    assert store.load(1001)["personal"]["time_grant_presets"] == list(DEFAULT_TIME_GRANT_PRESETS)
    assert not list(tmp_path.iterdir())
    path = tmp_path / "1001.json"
    path.write_text(json.dumps({"version": 4, "personal": {"language": "fr"}}))
    assert store.load(1001)["personal"]["time_grant_presets"] == list(DEFAULT_TIME_GRANT_PRESETS)
    assert store.update_time_grant_presets(1001, [7200, 6, 123, 86400]) == [6, 123, 7200, 86400]
    assert set(json.loads(path.read_text())) == {"version", "personal"}
    stale = store.load(1001)
    store.update_time_grant_presets(1001, [123, 60])
    stale["daily_time_limit_minutes"] = 42
    store.save(1001, stale)
    store.update_request(1001, "123", 0.1, True)
    before = store.load(1001)
    store.update_time_grant_presets(1001, [])
    store.update_language(1001, "de")
    store.update_notifications(1001, {"show_in_fullscreen": False, "reminders": []})
    restarted = PreferenceStore(tmp_path)
    saved = restarted.load(1001)
    assert saved["personal"]["time_grant_presets"] == []
    assert saved["daily_time_limit_minutes"] == 42
    assert saved["request"] == before["request"]
    assert saved["apps"] == before["apps"]
    assert restarted.load(1002)["personal"]["time_grant_presets"] == list(DEFAULT_TIME_GRANT_PRESETS)
    assert path.stat().st_mode & 0o777 == 0o600
    assert time_grant_choices([]) == ("0", "custom")
    assert time_grant_choices([7200, 6, 123]) == ("6", "123", "7200", "0", "custom")


@pytest.mark.parametrize("presets", [
    None, {}, "300", [0], ["custom"], [None], [True], [5], [86401],
    [1.5], [300.0], ["300"], [60, 60], list(range(6, 71)), [[]],
])
def test_invalid_time_grant_presets_preserve_saved_bytes(tmp_path, presets):
    store = PreferenceStore(tmp_path)
    store.update_time_grant_presets(1001, [60])
    path = tmp_path / "1001.json"
    before = path.read_bytes()
    with pytest.raises(PreferencesError):
        store.update_time_grant_presets(1001, presets)
    assert path.read_bytes() == before


def test_time_grant_presets_atomic_failure_and_corrupt_data(tmp_path):
    store = PreferenceStore(tmp_path)
    store.update_time_grant_presets(1001, [60])
    path = tmp_path / "1001.json"
    before = path.read_bytes()
    with mock.patch("oh_no_parent_control.preferences.os.replace", side_effect=OSError):
        with pytest.raises(OSError):
            store.update_time_grant_presets(1001, [])
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]
    for content in ('{', '{"version": 5, "personal": {"language": ""}}',
                    '{"version": 4, "personal": {"language": "", "time_grant_presets": [0]}}'):
        path.write_text(content)
        with pytest.raises(PreferencesError):
            store.update_time_grant_presets(1001, [])
        assert path.read_text() == content


def test_time_grant_presets_accept_exactly_64_and_reject_65(tmp_path):
    store = PreferenceStore(tmp_path)
    presets = list(range(6, 70))
    assert store.update_time_grant_presets(1001, list(reversed(presets))) == presets
    assert PreferenceStore(tmp_path).load(1001)["personal"]["time_grant_presets"] == presets
    before = (tmp_path / "1001.json").read_bytes()
    with pytest.raises(PreferencesError):
        store.update_time_grant_presets(1001, [*presets, 70])
    assert (tmp_path / "1001.json").read_bytes() == before


@pytest.mark.parametrize("selected", ["123", "6", "86400", "0", "custom"])
def test_remembered_time_grant_duration_survives_preset_deletion(selected):
    value = default_preferences()
    value["personal"]["time_grant_presets"] = []
    value["request"]["last_selected_duration"] = selected
    assert validate_preferences(value)["request"]["last_selected_duration"] == selected


class PreferenceTests(unittest.TestCase):
    def test_notification_crud_persists_isolated_and_preserves_policy_and_language(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            store = PreferenceStore(Path(directory))
            self.assertEqual(store.load(1001)["personal"]["notifications"], default_notifications())
            self.assertEqual(list(Path(directory).iterdir()), [])
            # Older v4 records receive compatible optional defaults on read.
            path = Path(directory) / "1001.json"
            path.write_text(json.dumps({"version": 4, "personal": {"language": "fr"}}))
            stale = store.load(1001)
            settings = {"show_in_fullscreen": False, "reminders": [
                {"id": "save-work", "value": 15, "unit": "second", "text": "  Save <work>!  "},
                {"id": "finish", "value": 15, "unit": "minute", "text": "\t\n\u2003"},
            ]}
            saved = store.update_notifications(1001, settings)
            self.assertEqual(saved["reminders"][1]["text"], "")
            self.assertEqual(saved["reminders"][0]["text"], "  Save <work>!  ")
            self.assertEqual(store.load(1001)["personal"]["language"], "fr")
            self.assertEqual(set(json.loads(path.read_text())), {"version", "personal"})
            # Stale policy commits and rollback share this path.
            stale["daily_time_limit_minutes"] = 42
            store.save(1001, stale)
            store.update_language(1001, "de")
            self.assertEqual(store.load(1001)["personal"]["notifications"], saved)
            settings["reminders"] = [{**saved["reminders"][0], "value": 20}]
            store.update_notifications(1001, settings)
            settings["reminders"] = []
            store.update_notifications(1001, settings)
            restarted = PreferenceStore(Path(directory))
            self.assertEqual(restarted.load(1001)["personal"]["notifications"], settings)
            self.assertEqual(restarted.load(1001)["daily_time_limit_minutes"], 42)
            self.assertEqual(restarted.load(1002)["personal"]["notifications"], default_notifications())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_notifications_reject_malformed_values_and_preserve_existing_bytes(self):
        import json
        base = default_notifications()
        record = base["reminders"][0]
        omitted_text = {key: value for key, value in record.items() if key != "text"}
        self.assertEqual(validate_notifications({**base, "reminders": [omitted_text]})["reminders"][0], record)
        invalid = [None, {}, {**base, "show_in_fullscreen": 1}, {**base, "reminders": {}},
                   {**base, "reminders": [record] * 65}, {**base, "reminders": [record, record]}]
        invalid.extend({**base, "reminders": [{**record, key: value}]} for key, value in (
            ("id", "../x"), ("id", ""), ("id", "x" * 65), ("value", True),
            ("value", 0), ("value", 2 ** 32), ("value", 1.5), ("unit", "hour"),
            ("unit", []), ("text", None), ("text", "x" * 4097), ("text", "\x00"),
            ("text", "\ud800")))
        with tempfile.TemporaryDirectory() as directory:
            store = PreferenceStore(Path(directory))
            store.update_notifications(1001, base)
            path = Path(directory) / "1001.json"
            before = path.read_bytes()
            for value in invalid:
                with self.subTest(value=value), self.assertRaises(PreferencesError):
                    store.update_notifications(1001, value)
                self.assertEqual(path.read_bytes(), before)
            with mock.patch("oh_no_parent_control.preferences.os.replace", side_effect=OSError):
                with self.assertRaises(OSError):
                    store.update_notifications(1001, {**base, "reminders": []})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual([p.name for p in Path(directory).iterdir()], ["1001.json"])
            for content in ('{', json.dumps({"version": 5, "personal": {"language": ""}})):
                path.write_text(content)
                with self.assertRaises(PreferencesError):
                    store.update_notifications(1001, base)
                self.assertEqual(path.read_text(), content)

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
                             {"version": 4, "personal": {**default_preferences()["personal"], "language": "fr"}})
            self.assertEqual(store.load(1001),
                             {**default_preferences(), "personal": {**default_preferences()["personal"], "language": "fr"}})
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
        for selected in ("5", "86401", "0123", "12.3", "rest", "", None, [], True, 123):
            with self.subTest(selected=selected), self.assertRaises(PreferencesError):
                value = default_preferences()
                value["request"]["last_selected_duration"] = selected
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
