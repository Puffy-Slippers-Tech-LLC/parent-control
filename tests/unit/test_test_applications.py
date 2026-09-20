"""Host-safe verification for deterministic application-test fixtures."""

from tests.support.modules import load_module
import os
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


from tests.support.paths import ROOT
FIXTURES = ROOT / "tests/fixtures/build_test_applications.py"
fixtures = load_module('onpc_test_applications', FIXTURES)


class TestApplicationFixtures(unittest.TestCase):
    def test_missing_prerequisite_reports_setup_without_installing_or_building(self):
        with patch.object(fixtures.shutil, 'which', side_effect=lambda name: None if name == 'snap' else '/usr/bin/' + name), \
                patch.object(fixtures, '_run') as run, \
                patch.object(fixtures, '_require_empty_output') as create:
            with self.assertRaisesRegex(fixtures.FixtureError, r'snap; run ./setup.sh --dependencies-only'):
                fixtures.build(Path('/tmp/onpc-not-created'))
            run.assert_not_called()
            create.assert_not_called()

    def test_build_verify_and_launch_native_in_an_isolated_temporary_directory(self):
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
            self.assertGreater((output / "onpc-test-application.flatpak").stat().st_size, 0)
            self.assertTrue((output / "flatpak-repository").is_dir())
            self.assertTrue((output / 'onpc-test-application.snap').is_file())
            metadata = subprocess.run(['unsquashfs', '-cat',
                str(output / 'onpc-test-application.snap'), 'meta/snap.yaml'],
                check=True, text=True, capture_output=True).stdout
            self.assertIn('confinement: strict', metadata)
            self.assertIn('base: core26', metadata)
            self.assertIn('desktop-legacy', metadata)
            runtime = output / 'flatpak-runtime-build/usr'
            self.assertTrue((runtime / 'bin/python3').is_file())
            self.assertTrue((runtime / 'share/X11/xkb/rules/evdev').is_file())
            self.assertTrue(list(runtime.rglob('Gtk-4.0.typelib')))
            self.assertFalse(json.loads(targets)['gui']['installed_qualified'])
            self.assertTrue((output / 'game/onpc-test-application').is_file())
            one_shot = subprocess.run([str(output / 'mechanical/onpc-test-application')],
                check=True, text=True, capture_output=True, timeout=5)
            self.assertEqual(one_shot.stdout, 'ONPC_TEST_APPLICATION_READY\n')
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
            repeat = Path(temporary) / 'repeat'
            fixtures.build(repeat)
            self.assertEqual(
                json.loads((output / 'SHA256SUMS.json').read_text()),
                json.loads((repeat / 'SHA256SUMS.json').read_text()),
                'Repeated builds must preserve every stable native/Snap/Flatpak runtime payload byte',
            )
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

    def test_verify_requires_the_complete_payload_inventory(self):
        with tempfile.TemporaryDirectory(prefix="onpc-test-fixtures-") as temporary:
            output = Path(temporary)
            stable = output / "mechanical/onpc-test-application"
            stable.parent.mkdir()
            stable.write_bytes(b"fixture")
            for relative in fixtures.VOLATILE_FILES:
                path = output / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"container")
            fixtures._write_manifest(output)
            fixtures.verify(output)

            (output / "unlisted").write_bytes(b"not attested")
            with self.assertRaisesRegex(fixtures.FixtureError, "complete payload"):
                fixtures.verify(output)
            (output / "unlisted").unlink()

            manifest_path = output / "SHA256SUMS.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["files"]["mechanical/onpc-test-application"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(fixtures.FixtureError, "complete payload"):
                fixtures.verify(output)


if __name__ == "__main__":
    unittest.main()
