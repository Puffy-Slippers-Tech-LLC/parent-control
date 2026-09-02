import json
import os
import tempfile
import unittest
from pathlib import Path

from oh_no_parent_control.data_migration import (
    MigrationError,
    PREFERENCE_MIGRATIONS,
    migrate_all_state,
    migrate_document,
    migrate_preferences,
)
from oh_no_parent_control.preferences import default_preferences, validate_preferences


class DataMigrationTests(unittest.TestCase):
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
        self.assertEqual(migrated["version"], 3)
        self.assertEqual(migrated["apps"]["lunar.desktop"]["patterns"], [])
        self.assertFalse(migrated["apps"]["lunar.desktop"]["user_saved_match_rule"])

    def test_v2_pattern_is_migrated_as_a_user_saved_match_rule(self):
        value = default_preferences()
        value["version"] = 2
        value["apps"] = {
            "lunar.desktop": {
                "state": "conditional",
                "targets": ["/home/child/Applications/Lunar-3.7.17.AppImage"],
                "patterns": ["/home/child/Applications/Lunar-*.AppImage"],
            },
        }

        migrated, changed = migrate_document(
            value, current_version=3, migrations=PREFERENCE_MIGRATIONS,
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
