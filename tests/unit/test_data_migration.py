import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from oh_no_parent_control.data_migration import (
    MigrationError,
    PREFERENCE_MIGRATIONS,
    migrate_all_state,
    migrate_document,
    migrate_preferences,
    migrate_preferences_v3_to_v4,
)
from oh_no_parent_control.preferences import FORMAT_VERSION, PreferenceStore, default_preferences, validate_preferences


class DataMigrationTests(unittest.TestCase):
    def test_time_grant_presets_survive_upgrade_retries_including_empty_list(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "preferences"
            store = PreferenceStore(directory)
            for presets in ([123, 60], []):
                store.update_time_grant_presets(1001, presets)
                path = directory / "1001.json"
                before = path.read_bytes()
                self.assertEqual(migrate_preferences(directory), 0)
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(PreferenceStore(directory).load(1001)["personal"]["time_grant_presets"],
                                 sorted(presets))

    def test_v3_to_v4_preserves_every_existing_choice_and_is_pure(self):
        legacy = default_preferences()
        legacy["version"] = 3
        del legacy["personal"]
        legacy["parent_control_enabled"] = True
        legacy["daily_time_limit_minutes"] = 1440
        legacy["request"].update({
            "last_selected_duration": "custom", "last_custom_minutes": 12.5,
            "allow_soft_blocked_apps": True, "last_selected_approver_uid": 1003,
            "child_muted": False, "kiosk_muted": False,
        })
        legacy["apps"] = {
            "game.desktop": {"state": "permanent", "targets": ["/usr/bin/game"],
                             "patterns": [], "user_saved_match_rule": True},
        }
        before = json.dumps(legacy, sort_keys=True)
        migrated = migrate_preferences_v3_to_v4(legacy)
        self.assertEqual(migrated, {**legacy, "version": 4, "personal": {"language": ""}})
        self.assertEqual(validate_preferences(migrated),
                         {**migrated, "personal": default_preferences()["personal"]})
        self.assertEqual(json.dumps(legacy, sort_keys=True), before)

    def test_v3_missing_optional_fields_uses_existing_defaults_after_upgrade(self):
        legacy = default_preferences()
        legacy["version"] = 3
        del legacy["personal"]
        del legacy["daily_time_limit_minutes"]
        for key in ("last_selected_approver_uid", "kiosk_muted", "child_muted"):
            del legacy["request"][key]
        migrated, changed = migrate_document(
            legacy, current_version=FORMAT_VERSION, migrations=PREFERENCE_MIGRATIONS,
            validator=validate_preferences,
        )
        self.assertTrue(changed)
        self.assertEqual(migrated, default_preferences())

    def test_unified_upgrade_retries_after_interruption_and_includes_root_uid(self):
        from oh_no_parent_control import data_migration
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "preferences"
            directory.mkdir(mode=0o700)
            legacy = default_preferences()
            legacy["version"] = 3
            del legacy["personal"]
            for uid in (0, 1001):
                path = directory / f"{uid}.json"
                path.write_text(json.dumps(legacy), encoding="utf-8")
                path.chmod(0o600)
            original = data_migration._atomic_write

            def interrupt_second(path, value, file_stat):
                if path.name == "1001.json":
                    raise MigrationError("interrupted second record")
                original(path, value, file_stat)

            with mock.patch.object(data_migration, "_atomic_write", side_effect=interrupt_second):
                with self.assertRaises(MigrationError):
                    migrate_preferences(directory)
            first_bytes = (directory / "0.json").read_bytes()
            self.assertEqual(json.loads(first_bytes)["version"], 4)
            self.assertEqual(json.loads((directory / "1001.json").read_bytes()), legacy)
            self.assertEqual(migrate_preferences(directory), 1)
            self.assertEqual((directory / "0.json").read_bytes(), first_bytes)
            store = PreferenceStore(directory)
            store.update_language(0, "en")
            store.update_language(1001, "fr")
            saved_bytes = (directory / "1001.json").read_bytes()
            self.assertEqual(migrate_preferences(directory), 0)
            self.assertEqual((directory / "1001.json").read_bytes(), saved_bytes)

    def test_invalid_v3_or_future_data_is_preserved_on_upgrade_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "preferences"
            directory.mkdir(mode=0o700)
            legacy = default_preferences()
            legacy["version"] = 3
            del legacy["personal"]
            invalid = (
                {"version": 3},
                {**legacy, "daily_time_limit_minutes": 1441},
                {**legacy, "personal": {"language": "fr"}},
                {**legacy, "version": 5},
            )
            path = directory / "1001.json"
            for value in invalid:
                path.write_text(json.dumps(value), encoding="utf-8")
                path.chmod(0o600)
                before = path.read_bytes()
                with self.assertRaises(MigrationError):
                    migrate_preferences(directory)
                self.assertEqual(path.read_bytes(), before)

    def test_document_migrations_run_in_order(self):
        calls = []

        def one_to_two(value):
            calls.append(1)
            return {**value, "version": 2, "two": True}

        def two_to_three(value):
            calls.append(2)
            return {**value, "version": 3, "three": value["two"]}

        migrated, changed = migrate_document(
            {"version": 1},
            current_version=3,
            migrations={1: one_to_two, 2: two_to_three},
            validator=lambda value: value,
        )

        self.assertTrue(changed)
        self.assertEqual(calls, [1, 2])
        self.assertEqual(migrated, {
            "version": 3, "two": True, "three": True,
        })

    def test_current_document_is_validated_without_rewrite(self):
        source = {"version": 1}
        migrated, changed = migrate_document(
            source,
            current_version=1,
            migrations={},
            validator=lambda value: value,
        )

        self.assertFalse(changed)
        self.assertIs(migrated, source)

    def test_unknown_future_schema_and_missing_step_fail_closed(self):
        with self.assertRaisesRegex(MigrationError, "newer than supported"):
            migrate_document(
                {"version": 3}, current_version=2, migrations={},
                validator=lambda value: value,
            )
        with self.assertRaisesRegex(MigrationError, "no migration"):
            migrate_document(
                {"version": 1}, current_version=2, migrations={},
                validator=lambda value: value,
            )

    def test_step_must_return_new_object_at_exact_next_version(self):
        value = {"version": 1}
        with self.assertRaisesRegex(MigrationError, "new object"):
            migrate_document(
                value, current_version=2, migrations={1: lambda _value: value},
                validator=lambda candidate: candidate,
            )
        with self.assertRaisesRegex(MigrationError, "schema 2"):
            migrate_document(
                value, current_version=2,
                migrations={1: lambda _value: {"version": 3}},
                validator=lambda candidate: candidate,
            )

    def test_preferences_are_atomically_migrated_and_retry_is_noop(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "preferences"
            directory.mkdir(mode=0o700)
            record = directory / "1001.json"
            record.write_text('{"version": 1, "name": "saved"}\n', encoding="utf-8")
            record.chmod(0o600)

            def one_to_two(value):
                return {**value, "version": 2, "enabled": True}

            validator = lambda value: value
            arguments = {
                "current_version": 2,
                "migrations": {1: one_to_two},
                "validator": validator,
            }
            self.assertEqual(migrate_preferences(directory, **arguments), 1)
            self.assertEqual(json.loads(record.read_text(encoding="utf-8")), {
                "enabled": True, "name": "saved", "version": 2,
            })
            self.assertEqual(record.stat().st_mode & 0o777, 0o600)
            contents = record.read_bytes()

            self.assertEqual(migrate_preferences(directory, **arguments), 0)
            self.assertEqual(record.read_bytes(), contents)

    def test_current_real_preferences_are_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "preferences"
            directory.mkdir(mode=0o700)
            record = directory / "1001.json"
            record.write_text(
                json.dumps(default_preferences()) + "\n", encoding="utf-8",
            )
            record.chmod(0o600)

            self.assertEqual(migrate_preferences(directory), 0)

    def test_v1_preferences_gain_empty_patterns_without_changing_blocks(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "preferences"
            directory.mkdir(mode=0o700)
            record = directory / "1001.json"
            value = default_preferences()
            value["version"] = 1
            del value["personal"]
            value["apps"] = {
                "lunar.desktop": {
                    "state": "conditional",
                    "targets": ["/home/child/Applications/Lunar Client-3.7.17.AppImage"],
                },
            }
            record.write_text(json.dumps(value), encoding="utf-8")
            record.chmod(0o600)

            self.assertEqual(migrate_preferences(directory), 1)
            migrated = json.loads(record.read_text(encoding="utf-8"))
        self.assertEqual(migrated["version"], FORMAT_VERSION)
        self.assertEqual(migrated["personal"], default_preferences()["personal"])
        self.assertEqual(migrated["apps"]["lunar.desktop"]["patterns"], [])
        self.assertFalse(migrated["apps"]["lunar.desktop"]["user_saved_match_rule"])

    def test_v2_pattern_is_migrated_as_a_user_saved_match_rule(self):
        value = default_preferences()
        value["version"] = 2
        del value["personal"]
        value["apps"] = {
            "lunar.desktop": {
                "state": "conditional",
                "targets": ["/home/child/Applications/Lunar-3.7.17.AppImage"],
                "patterns": ["/home/child/Applications/Lunar-*.AppImage"],
            },
        }

        migrated, changed = migrate_document(
            value, current_version=FORMAT_VERSION, migrations=PREFERENCE_MIGRATIONS,
            validator=validate_preferences,
        )

        self.assertTrue(changed)
        self.assertTrue(migrated["apps"]["lunar.desktop"]["user_saved_match_rule"])

    def test_duplicate_keys_and_unsafe_records_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "preferences"
            directory.mkdir(mode=0o700)
            duplicate = directory / "1001.json"
            duplicate.write_text('{"version": 1, "version": 1}\n', encoding="utf-8")
            duplicate.chmod(0o600)
            with self.assertRaisesRegex(MigrationError, "duplicate JSON key"):
                migrate_preferences(directory)

            duplicate.unlink()
            unsafe = directory / "1002.json"
            unsafe.write_text(json.dumps(default_preferences()), encoding="utf-8")
            unsafe.chmod(0o644)
            with self.assertRaisesRegex(MigrationError, "unsafe permissions"):
                migrate_preferences(directory)

    def test_symlink_and_invalid_json_record_name_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "preferences"
            directory.mkdir(mode=0o700)
            target = Path(temporary) / "target"
            target.write_text(json.dumps(default_preferences()), encoding="utf-8")
            target.chmod(0o600)
            (directory / "1001.json").symlink_to(target)
            with self.assertRaisesRegex(MigrationError, "not a regular file"):
                migrate_preferences(directory)

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "preferences"
            directory.mkdir(mode=0o700)
            (directory / "not-a-uid.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(MigrationError, "invalid preference record name"):
                migrate_preferences(directory)

    def test_state_directory_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            real = root / "real"
            real.mkdir(mode=0o700)
            link = root / "state"
            link.symlink_to(real, target_is_directory=True)

            with self.assertRaisesRegex(MigrationError, "unsafe ownership or permissions"):
                migrate_all_state(link)


if __name__ == "__main__":
    unittest.main()
