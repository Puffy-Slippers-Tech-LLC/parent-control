import importlib.util
import subprocess
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INTEGRATION = ROOT / "tests/integration"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = load("h50_harness", INTEGRATION / "harness.py")
guard = load("h50_guard", INTEGRATION / "guest/guard.py")
redact = load("h50_redact", INTEGRATION / "guest/redact.py")
verify_packages = load(
    "h50_verify_packages", INTEGRATION / "guest/verify_packages.py"
)


class IntegrationHarnessTests(unittest.TestCase):
    def test_vm_names_are_narrow_and_explicit(self):
        self.assertEqual(
            harness.validate_vm_name("onpc-h50-clean-20260901"),
            "onpc-h50-clean-20260901",
        )
        for value in (
            "ubuntu", "onpc-h50-", "onpc-h50-UPPER", "onpc-h50-a/../b",
            "onpc-h50-a_unsafe", "onpc-h50-a-",
        ):
            with self.subTest(value=value), self.assertRaises(harness.HarnessError):
                harness.validate_vm_name(value)

    def test_destroy_identity_binds_name_token_and_exact_two_images(self):
        metadata = {
            "name": "onpc-h50-clean",
            "token": "a" * 32,
            "description": harness.DESCRIPTION_PREFIX + "a" * 32,
            "disk": "/var/lib/libvirt/images/onpc-h50-clean.qcow2",
            "seed": "/var/lib/libvirt/images/onpc-h50-clean-seed.iso",
        }
        xml = f"""<domain>
          <name>{metadata['name']}</name>
          <description>{metadata['description']}</description>
          <devices>
            <disk><source file="{metadata['disk']}"/></disk>
            <disk><source file="{metadata['seed']}"/></disk>
          </devices>
        </domain>"""
        self.assertEqual(
            harness._validate_domain_for_destroy(metadata, xml),
            {Path(metadata["disk"]), Path(metadata["seed"])},
        )
        with self.assertRaises(harness.HarnessError):
            harness._validate_domain_for_destroy(
                metadata, xml.replace(metadata["description"], "some-other-vm")
            )
        with self.assertRaises(harness.HarnessError):
            harness._validate_domain_for_destroy(
                metadata,
                xml.replace("</devices>", '<disk><source file="/dev/sda"/></disk></devices>'),
            )

    def test_cloud_init_creates_only_the_vm_admin_and_root_owned_marker(self):
        user_data, meta_data, network_data = harness._cloud_init(
            "onpc-h50-clean", "b" * 32, "ssh-ed25519 AAAAtest integration"
        )
        self.assertIn("name: onpc-admin", user_data)
        self.assertIn("uid: 2000", user_data)
        self.assertNotIn("onpc-child", user_data)
        self.assertIn("permissions: '0600'", user_data)
        self.assertIn("oh-no-parent-control-integration", user_data)
        self.assertIn("optional: false", network_data)
        self.assertIn("onpc-h50-clean", meta_data)

    def test_ssh_places_the_quoted_command_after_the_destination(self):
        metadata = {
            "ssh_private_key": "/state/key",
            "known_hosts": "/state/known-hosts",
            "ip_address": "192.0.2.10",
        }
        with mock.patch.object(harness, "_run") as run:
            harness._ssh(metadata, ["sudo", "cat", "/etc/os-release"])
        command = run.call_args.args[0]
        destination = command.index("onpc-admin@192.0.2.10")
        self.assertEqual(command[destination + 1], "sudo cat /etc/os-release")
        self.assertNotEqual(command[destination + 1], "--")

    def test_guest_marker_schema_is_exact(self):
        value = {
            "purpose": "oh-no-parent-control-integration",
            "name": "onpc-h50-clean",
            "token": "c" * 32,
            "ubuntu_version": "26.04",
        }
        self.assertEqual(guard.validate_marker_document(value, value["name"]), value)
        for changed in (
            {**value, "name": "onpc-h50-other"},
            {**value, "ubuntu_version": "24.04"},
            {**value, "extra": True},
        ):
            with self.assertRaises(guard.GuardError):
                guard.validate_marker_document(changed, value["name"])

    def test_guest_guard_refuses_this_unmarked_development_context(self):
        result = subprocess.run(
            [str(INTEGRATION / "guest/guard.py"), "onpc-h50-guard-test"],
            check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("integration guard:", result.stderr)

    def test_every_guest_command_guards_before_mutation(self):
        for name in ("setup", "run", "verify", "collect"):
            contents = (INTEGRATION / "guest" / name).read_text(encoding="utf-8")
            guard_call = contents.index('"$SCRIPT_DIR/guard.py" "$VM_NAME"')
            mutation_candidates = [
                contents.find(token) for token in (
                    "apt-get ", "useradd ", "make -C ", 'install -d ',
                    "busctl --system call", "pamtester ",
                ) if contents.find(token) >= 0
            ]
            self.assertTrue(mutation_candidates, name)
            self.assertLess(guard_call, min(mutation_candidates), name)

    def test_guest_shell_scripts_have_valid_syntax(self):
        for name in ("setup", "run", "verify", "collect"):
            result = subprocess.run(
                ["bash", "-n", str(INTEGRATION / "guest" / name)],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_supported_package_matrix_is_complete_and_exact(self):
        versions = verify_packages.expected_versions(
            INTEGRATION / "expected-packages.tsv"
        )
        self.assertEqual(
            set(versions),
            {
                "ubuntu-desktop", "gnome-shell", "accountsservice", "malcontent",
                "fapolicyd", "flatpak", "libpam0g", "libpam-malcontent",
            },
        )
        self.assertTrue(all(version and version != "latest" for version in versions.values()))

    def test_artifact_redaction_removes_tokens_passwords_and_keys(self):
        token = "d" * 32
        source = (
            f"token={token}\npassword: hunter2\n"
            "Authorization: Bearer abc.def\nssh-ed25519 AAAAsecret comment\n"
        )
        result = redact.redact_text(source, token)
        for secret in (token, "hunter2", "abc.def", "AAAAsecret"):
            self.assertNotIn(secret, result)
        self.assertIn("<redacted", result)

    def test_real_installer_and_required_artifacts_are_wired(self):
        run_script = (INTEGRATION / "guest/run").read_text(encoding="utf-8")
        collect_script = (INTEGRATION / "guest/collect").read_text(encoding="utf-8")
        self.assertIn('make -C "$CHECKOUT" check', run_script)
        self.assertIn('"$CHECKOUT/install.sh"', run_script)
        self.assertNotIn("_install-product-files", run_script)
        for artifact in (
            "service-status.txt", "dbus-replies.txt", "fapolicyd-rules.txt",
            "login-results.txt", "product-logs", "service-journal.txt",
        ):
            self.assertIn(artifact, collect_script)


if __name__ == "__main__":
    unittest.main()
