"""Contract tests for the Task 13 package and fixture artifact boundary."""

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/build_test_artifacts.py"
spec = importlib.util.spec_from_file_location("build_test_artifacts", MODULE_PATH)
artifacts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(artifacts)


def write_artifact(directory: Path, *, package_bytes: bytes = b"package", fixture_digest: str = "fixture") -> None:
    package = directory / "package/oh-no-parent-control_1_amd64.deb"
    package.parent.mkdir(parents=True)
    package.write_bytes(package_bytes)
    fixtures = directory / "fixtures"
    fixtures.mkdir()
    (fixtures / "SHA256SUMS.json").write_text(
        json.dumps({"algorithm": "sha256", "files": {"payload": fixture_digest}}, sort_keys=True),
        encoding="utf-8",
    )
    (directory / artifacts.MANIFEST_NAME).write_text(
        json.dumps(
            {
                "schema_version": artifacts.SCHEMA_VERSION,
                "source": {"revision": "a" * 40, "digest_sha256": "b" * 64, "file_count": 1},
                "build_inputs": {"source_date_epoch": 1, "architecture": "amd64", "deb_build_options": "nocheck", "package_command": ["dpkg-buildpackage"]},
                "tools": {},
                "artifacts": {
                    "package": {"path": "package/oh-no-parent-control_1_amd64.deb", "sha256": artifacts._sha256(package)},
                    "fixtures": {"path": "fixtures", "digest_manifest": "fixtures/SHA256SUMS.json", "sha256": artifacts._fixture_digest(fixtures)},
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


class TestBuildTestArtifacts(unittest.TestCase):
    def test_output_must_be_empty_and_outside_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            self.assertEqual(artifacts._require_empty_output(output), output)
            (output / "occupied").write_text("x", encoding="utf-8")
            with self.assertRaises(artifacts.ArtifactError):
                artifacts._require_empty_output(output)
        with self.assertRaises(artifacts.ArtifactError):
            artifacts._require_empty_output(ROOT / "artifacts/test-package")

    def test_build_copies_the_recorded_source_to_a_private_tree_and_writes_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            metadata = {
                "source": {"revision": "a" * 40, "digest_sha256": "b" * 64, "file_count": 1},
                "build_inputs": {"source_date_epoch": 1, "architecture": "amd64", "deb_build_options": "nocheck", "package_command": ["dpkg-buildpackage"]},
                "tools": {"flatpak": "Flatpak 1"},
            }

            def fake_run(command, *, cwd=None, environment=None):
                if command == ["dpkg-buildpackage"]:
                    self.assertNotEqual(cwd, ROOT)
                    self.assertTrue((cwd / "README.md").is_file())
                    (cwd.parent / "oh-no-parent-control_1_amd64.deb").write_bytes(b"package")
                elif command[1] == str(artifacts.FIXTURE_BUILDER):
                    fixture_output = Path(command[-1])
                    fixture_output.mkdir()
                    (fixture_output / "SHA256SUMS.json").write_text(
                        json.dumps({"algorithm": "sha256", "files": {"payload": "fixture"}}), encoding="utf-8"
                    )
                return subprocess.CompletedProcess(command, 0, "", "")

            with mock.patch.object(artifacts, "_source_paths", return_value=[Path("README.md")]), \
                 mock.patch.object(artifacts, "_source_digest", return_value="b" * 64), \
                 mock.patch.object(artifacts, "_metadata", return_value=metadata), \
                 mock.patch.object(artifacts, "_run", side_effect=fake_run):
                manifest_path = artifacts.build(output)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["source"], metadata["source"])
            self.assertEqual(manifest["artifacts"]["package"]["path"], "package/oh-no-parent-control_1_amd64.deb")
            self.assertEqual(manifest["artifacts"]["fixtures"]["digest_manifest"], "fixtures/SHA256SUMS.json")

    def test_verify_rejects_tampered_package_and_compare_requires_equal_builds(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first"
            second = Path(temporary) / "second"
            first.mkdir()
            second.mkdir()
            write_artifact(first)
            write_artifact(second)
            with mock.patch.object(artifacts, "_run", return_value=subprocess.CompletedProcess([], 0, "", "")):
                artifacts.compare(first, second)
            package = first / "package/oh-no-parent-control_1_amd64.deb"
            package.write_bytes(b"changed")
            with self.assertRaises(artifacts.ArtifactError):
                artifacts.verify(first)


if __name__ == "__main__":
    unittest.main()
