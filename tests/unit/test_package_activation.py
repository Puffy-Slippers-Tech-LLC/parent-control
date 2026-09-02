import json
import tempfile
import unittest
from pathlib import Path

from tools.package_activation import activation_for, changed_impacts, generate


class PackageActivationTests(unittest.TestCase):
    def _manifest(self, root: Path, name: str) -> Path:
        output = root / name
        generate(root, output)
        return output

    def test_broker_change_restarts_process_without_reboot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            broker = root / "usr/lib/oh-no-parent-control/broker/service.py"
            broker.parent.mkdir(parents=True)
            broker.write_text("first", encoding="utf-8")
            old = self._manifest(root, "old.json")
            broker.write_text("second", encoding="utf-8")
            new = self._manifest(root, "new.json")

            self.assertEqual(changed_impacts(old, new), ["process-restart"])

    def test_migration_runner_activates_during_postinst(self):
        self.assertEqual(
            activation_for("usr/libexec/oh-no-parent-control-migrate-state"),
            "none",
        )

    def test_execution_rule_change_reloads_with_broker_restart(self):
        self.assertEqual(
            activation_for(
                "etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules"
            ),
            "process-restart",
        )

    def test_desktop_icon_change_activates_at_the_next_session(self):
        self.assertEqual(
            activation_for(
                "usr/share/icons/hicolor/512x512/apps/"
                "com.puffyslippers.OhNoParentControl.png"
            ),
            "session-renewal",
        )

    def test_session_payload_change_does_not_signal_reboot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            extension = root / "usr/lib/oh-no-parent-control/child/extension/extension.js"
            extension.parent.mkdir(parents=True)
            extension.write_text("first", encoding="utf-8")
            old = self._manifest(root, "old.json")
            extension.write_text("second", encoding="utf-8")
            new = self._manifest(root, "new.json")

            self.assertEqual(changed_impacts(old, new), ["session-renewal"])

    def test_login_stack_change_requires_reboot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pam = root / "usr/share/pam-configs/oh-no-parent-control-session-limits"
            pam.parent.mkdir(parents=True)
            pam.write_text("first", encoding="utf-8")
            old = self._manifest(root, "old.json")
            pam.write_text("second", encoding="utf-8")
            new = self._manifest(root, "new.json")

            self.assertEqual(changed_impacts(old, new), ["reboot"])

    def test_removed_file_keeps_its_old_activation_requirement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gdm = root / "etc/gdm3/PreSession/Default"
            gdm.parent.mkdir(parents=True)
            gdm.write_text("first", encoding="utf-8")
            old = self._manifest(root, "old.json")
            gdm.unlink()
            new = self._manifest(root, "new.json")

            self.assertEqual(changed_impacts(old, new), ["reboot"])

    def test_no_baseline_is_a_first_installation_reboot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "usr/share/oh-no-parent-control").mkdir(parents=True)
            new = self._manifest(root, "usr/share/oh-no-parent-control/current.json")

            self.assertEqual(changed_impacts(root / "missing.json", new), ["reboot"])

    def test_generated_manifest_contains_hashes_and_activation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "usr/bin/oh-no-parent-control"
            target.parent.mkdir(parents=True)
            target.write_text("launcher", encoding="utf-8")
            manifest = self._manifest(root, "manifest.json")

            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(data["version"], 1)
            self.assertEqual(data["files"][0]["activation"], "none")
            self.assertEqual(len(data["files"][0]["sha256"]), 64)

    def test_includes_limit_generation_to_activation_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tracked = root / "usr/lib/oh-no-parent-control/broker/service.py"
            ignored = root / "usr/bin/oh-no-parent-control"
            tracked.parent.mkdir(parents=True)
            ignored.parent.mkdir(parents=True)
            tracked.write_text("broker", encoding="utf-8")
            ignored.write_text("launcher", encoding="utf-8")

            manifest = root / "manifest.json"
            generate(root, manifest, [Path("usr/lib/oh-no-parent-control/broker")])

            paths = [entry["path"] for entry in json.loads(manifest.read_text())["files"]]
            self.assertEqual(paths, ["usr/lib/oh-no-parent-control/broker/service.py"])


if __name__ == "__main__":
    unittest.main()
