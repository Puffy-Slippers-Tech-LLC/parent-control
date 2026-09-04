import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import call, patch

import tools.bump_version as version_tool

from tools.bump_version import (
    VersionError,
    parse_product_version,
    staged_metadata,
    validate_release,
)


ROOT = Path(__file__).resolve().parents[2]


class BumpVersionTests(unittest.TestCase):
    def test_debian_build_always_checks_release_metadata(self):
        rules = (ROOT / "debian/rules").read_text(encoding="utf-8")
        self.assertIn("override_dh_auto_build:\n\t$(MAKE) check-release-version", rules)

    def test_product_version_is_exactly_two_unpadded_numbers(self):
        self.assertEqual(parse_product_version("2.14"), (2, 14))
        for invalid in ("2", "2.14.1", "v2.14", "02.14", "2.014"):
            with self.subTest(invalid=invalid), self.assertRaises(VersionError):
                parse_product_version(invalid)

    def test_any_increasing_major_release_is_allowed(self):
        validate_release((1, 9), (3, 4))

    def test_increasing_minor_release_is_allowed(self):
        validate_release((1, 9), (1, 10))

    def test_release_must_advance(self):
        with self.assertRaisesRegex(VersionError, "greater"):
            validate_release((1, 2), (1, 2))

    def test_staged_metadata_contains_only_the_version(self):
        self.assertEqual(
            staged_metadata("2.0"),
            '{\n  "version": "2.0"\n}\n',
        )

    def test_metadata_rejects_extra_versioning_state(self):
        with TemporaryDirectory() as directory:
            metadata = Path(directory) / "app.json"
            metadata.write_text(
                '{"version": "1.0", "extra": true}\n',
                encoding="utf-8",
            )
            with (
                patch.object(version_tool, "APP_METADATA_PATH", metadata),
                self.assertRaisesRegex(VersionError, "only the product version"),
            ):
                version_tool.read_metadata()

    def test_repository_check_accepts_a_ppa_suffix(self):
        with (
            patch.object(
                version_tool, "read_metadata",
                return_value=({"version": "2.4"}, (2, 4)),
            ),
            patch.object(
                version_tool, "debian_version",
                return_value="2.4+ppa3~ubuntu26.04.1",
            ),
        ):
            version_tool.check_repository()

    def test_repository_check_rejects_mismatched_package_version(self):
        with (
            patch.object(
                version_tool, "read_metadata",
                return_value=({"version": "2.4"}, (2, 4)),
            ),
            patch.object(version_tool, "debian_version", return_value="2.3"),
            self.assertRaisesRegex(VersionError, "must equal the product version"),
        ):
            version_tool.check_repository()

    def test_bump_updates_metadata_and_debian_changelog(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            metadata = root / "app.json"
            metadata.write_text('{"version": "1.0"}\n', encoding="utf-8")
            completed = subprocess.CompletedProcess([], 0)
            with (
                patch.object(version_tool, "ROOT", root),
                patch.object(version_tool, "APP_METADATA_PATH", metadata),
                patch.object(version_tool, "debian_version", return_value="1.0"),
                patch.object(version_tool.subprocess, "run", return_value=completed) as run,
                patch("builtins.print"),
            ):
                version_tool.bump("2.4", "Major release.")

            self.assertEqual(
                json.loads(metadata.read_text(encoding="utf-8")),
                {"version": "2.4"},
            )
            self.assertEqual(
                run.call_args_list,
                [
                    call(
                        ["dpkg", "--compare-versions", "2.4", "gt", "1.0"],
                        cwd=root,
                        check=False,
                    ),
                    call(
                        [
                            "dch", "--newversion", "2.4", "--distribution",
                            "resolute", "Major release.",
                        ],
                        cwd=root,
                        check=True,
                    ),
                ],
            )

    def test_failed_changelog_update_does_not_change_product_version(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            metadata = root / "app.json"
            original = '{"version": "1.0"}\n'
            metadata.write_text(original, encoding="utf-8")
            comparison = subprocess.CompletedProcess([], 0)
            changelog_failure = subprocess.CalledProcessError(1, ["dch"])
            with (
                patch.object(version_tool, "ROOT", root),
                patch.object(version_tool, "APP_METADATA_PATH", metadata),
                patch.object(version_tool, "debian_version", return_value="1.0"),
                patch.object(
                    version_tool.subprocess, "run",
                    side_effect=[comparison, changelog_failure],
                ),
                self.assertRaises(subprocess.CalledProcessError),
            ):
                version_tool.bump("1.1", "Small release.")

            self.assertEqual(metadata.read_text(encoding="utf-8"), original)

    def test_debian_version_rejection_does_not_run_dch_or_change_metadata(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            metadata = root / "app.json"
            original = '{"version": "1.0"}\n'
            metadata.write_text(original, encoding="utf-8")
            rejected = subprocess.CompletedProcess([], 1)
            with (
                patch.object(version_tool, "ROOT", root),
                patch.object(version_tool, "APP_METADATA_PATH", metadata),
                patch.object(version_tool, "debian_version", return_value="1.9"),
                patch.object(
                    version_tool.subprocess, "run", return_value=rejected,
                ) as run,
                self.assertRaisesRegex(VersionError, "Debian package version"),
            ):
                version_tool.bump("1.1", "Small release.")

            self.assertEqual(run.call_count, 1)
            self.assertEqual(metadata.read_text(encoding="utf-8"), original)
