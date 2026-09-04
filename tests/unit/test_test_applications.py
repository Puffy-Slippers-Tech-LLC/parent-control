"""Host-safe verification for deterministic application-test fixtures."""

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/build_test_applications.py"
spec = importlib.util.spec_from_file_location("onpc_test_applications", FIXTURES)
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class TestApplicationFixtures(unittest.TestCase):
    def test_build_verify_launch_and_terminate_in_an_isolated_temporary_directory(self):
        real_home = Path.home()
        protected_paths = (
            real_home / ".local/share/flatpak",
            real_home / ".config/flatpak",
            Path("/var/lib/flatpak"),
        )
        before = {path: path.exists() for path in protected_paths}
        with tempfile.TemporaryDirectory(prefix="onpc-test-fixtures-") as temporary:
            output = Path(temporary) / "payload"
            fixtures.build(output)
            fixtures.verify(output)
            flatpak_environment = fixtures._flatpak_environment(output)
            for variable in ("HOME", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR"):
                self.assertTrue(Path(flatpak_environment[variable]).is_relative_to(output))
            self.assertNotEqual(flatpak_environment["HOME"], os.environ.get("HOME"))
            targets = (output / "fixture-targets.json").read_text(encoding="utf-8")
            self.assertIn("Lunar Client-*.AppImage", targets)
            self.assertTrue((output / "onpc-test-application.flatpak").is_file())
            self.assertTrue((output / "flatpak-repository").is_dir())
            self.assertTrue(
                (output / "image-root/usr/share/applications/"
                 "com.puffyslippers.ONPCTest.System.desktop").is_file()
            )
            self.assertTrue(
                (output / "image-root/home/onpc-child/.local/share/applications/"
                 "com.puffyslippers.ONPCTest.Child.desktop").is_file()
            )
            native = output / "native/onpc-test-application"
            native_process = fixtures.launch_native(native, os.geteuid())
            self.addCleanup(fixtures.terminate, native_process)
            self.assertEqual(
                fixtures.report_process_identity(native_process),
                {"pid": native_process.pid, "uid": os.geteuid()},
            )
            fixtures.terminate(native_process)
            flatpak_process = fixtures.launch_flatpak(output, os.geteuid())
            self.addCleanup(fixtures.terminate, flatpak_process)
            self.assertEqual(
                fixtures.report_process_identity(flatpak_process),
                {"pid": flatpak_process.pid, "uid": os.geteuid()},
            )
            fixtures.terminate(flatpak_process)
        self.assertEqual(before, {path: path.exists() for path in protected_paths})

    def test_builder_refuses_nonempty_or_broad_output_locations(self):
        with tempfile.TemporaryDirectory(prefix="onpc-test-fixtures-") as temporary:
            output = Path(temporary)
            (output / "existing").write_text("fixture", encoding="utf-8")
            with self.assertRaises(fixtures.FixtureError):
                fixtures._require_empty_output(output)
        with self.assertRaises(fixtures.FixtureError):
            fixtures._require_empty_output(Path("/"))
        with self.assertRaises(fixtures.FixtureError):
            fixtures._require_empty_output(ROOT / "artifacts/test-fixtures")


if __name__ == "__main__":
    unittest.main()
