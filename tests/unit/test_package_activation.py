import json
import runpy
import subprocess
import tempfile
import unittest
from pathlib import Path

_activation = runpy.run_path(str(Path(__file__).resolve().parents[2] / "debian/package_activation.py"))
activation_for = _activation["activation_for"]
changed_impacts = _activation["changed_impacts"]
generate = _activation["generate"]


def test_make_generates_activation_manifest_from_relocated_debian_helper(tmp_path):
    root = Path(__file__).resolve().parents[2]
    broker = tmp_path / 'usr/libexec/oh-no-parent-control-broker'
    broker.parent.mkdir(parents=True)
    broker.write_text('staged broker fixture')
    subprocess.run(['make', '--no-print-directory', '_generate-package-activation-manifest',
                    f'DESTDIR={tmp_path}'], cwd=root, check=True, capture_output=True, text=True)
    manifest = json.loads((tmp_path / 'usr/share/oh-no-parent-control/package-activation.json').read_text())
    assert manifest['files'] == [{
        'path': 'usr/libexec/oh-no-parent-control-broker',
        'sha256': _activation['file_digest'](broker),
        'activation': 'process-restart',
    }]


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

    def test_app_termination_adapter_activates_with_broker_restart(self):
        self.assertEqual(
            activation_for(
                "usr/lib/oh-no-parent-control/broker/"
                "oh_no_parent_control/app_termination.py"
            ),
            "process-restart",
        )

    def test_broker_service_change_activates_with_broker_restart(self):
        self.assertEqual(
            activation_for(
                "usr/lib/systemd/system/oh-no-parent-control-broker.service"
            ),
            "process-restart",
        )

    def test_migration_runner_activates_during_postinst(self):
        self.assertEqual(
            activation_for("usr/libexec/oh-no-parent-control-migrate-state"),
            "none",
        )

    def test_uninstall_only_code_needs_no_installed_update_activation(self):
        for path in (
            "usr/libexec/oh-no-parent-control-uninstall",
            "etc/apt/apt.conf.d/99zz-oh-no-parent-control-reboot-notice",
            "usr/lib/oh-no-parent-control/broker/oh_no_parent_control/uninstall.py",
        ):
            with self.subTest(path=path):
                self.assertEqual(activation_for(path), "none")

    def test_package_completion_notice_activates_on_invocation(self):
        for path in (
            "usr/libexec/oh-no-parent-control-package-notice",
            "etc/dpkg/dpkg.cfg.d/99-oh-no-parent-control-notice",
        ):
            with self.subTest(path=path):
                self.assertEqual(activation_for(path), "none")

    def test_execution_rule_change_reloads_with_broker_restart(self):
        self.assertEqual(activation_for("usr/share/oh-no-parent-control/99-oh-no-parent-control-allow.rules"), "process-restart")
        self.assertEqual(
            activation_for(
                "etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules"
            ),
            "process-restart",
        )

    def test_polkit_action_change_is_loaded_without_restart(self):
        self.assertEqual(
            activation_for(
                "usr/share/polkit-1/actions/"
                "tech.puffyslippers.com.ohnoparentcontrol.child.request-own-access.policy"
            ),
            "none",
        )

    def test_desktop_icon_change_activates_at_the_next_session(self):
        self.assertEqual(
            activation_for(
                "usr/share/icons/hicolor/512x512/apps/"
                "com.puffyslippers.OhNoParentControl.png"
            ),
            "session-renewal",
        )

    def test_account_logo_is_reapplied_by_provisioning(self):
        self.assertEqual(
            activation_for(
                "usr/share/oh-no-parent-control/kiosk_account_icon.png"
            ),
            "none",
        )

    def test_parent_titlebar_logo_needs_no_session_restart(self):
        self.assertEqual(
            activation_for(
                "usr/share/oh-no-parent-control/app_logo_titlebar.png"
            ),
            "none",
        )

    def test_session_payload_change_does_not_signal_reboot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            extension = (
                root / "usr/share/gnome-shell/extensions/"
                "oh-no-parent-control@tech.puffyslippers.com/extension.js"
            )
            extension.parent.mkdir(parents=True)
            extension.write_text("first", encoding="utf-8")
            old = self._manifest(root, "old.json")
            extension.write_text("second", encoding="utf-8")
            new = self._manifest(root, "new.json")

            self.assertEqual(changed_impacts(old, new), ["session-renewal"])

    def test_pam_policy_and_runtime_cap_modules_require_reboot(self):
        self.assertEqual(
            activation_for(
                "usr/libexec/oh-no-parent-control-session-limit-check"
            ),
            "reboot",
        )
        self.assertEqual(
            activation_for("usr/libexec/oh-no-parent-control-login-check"),
            "reboot",
        )
        self.assertEqual(
            activation_for(
                "usr/lib/x86_64-linux-gnu/security/pam_oh_no_parent_control.so"
            ),
            "reboot",
        )

    def test_login_stack_change_requires_reboot(self):
        self.assertEqual(activation_for("usr/share/oh-no-parent-control/gdm-presession"), "reboot")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pam = root / "usr/share/pam-configs/oh-no-parent-control-session-limits"
            pam.parent.mkdir(parents=True)
            pam.write_text("first", encoding="utf-8")
            old = self._manifest(root, "old.json")
            pam.write_text("second", encoding="utf-8")
            new = self._manifest(root, "new.json")

            self.assertEqual(changed_impacts(old, new), ["reboot"])

    def test_execution_readiness_gate_requires_reboot(self):
        self.assertEqual(
            activation_for(
                "usr/lib/systemd/system/display-manager.service.d/"
                "oh-no-parent-control.conf"
            ),
            "reboot",
        )
        self.assertEqual(
            activation_for(
                "usr/libexec/oh-no-parent-control-execution-policy-ready"
            ),
            "reboot",
        )

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
