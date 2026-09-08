import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from oh_no_parent_control.execution_policy import (
    ExecutionPolicyError, FapolicydPolicy,
)


class ExecutionPolicyTests(unittest.TestCase):
    def test_native_targets_are_denied_for_only_the_managed_uid(self):
        rules = FapolicydPolicy.render({
            1001: ("/usr/bin/game", "app/org.example.Game/x86_64/stable"),
        })

        self.assertIn(
            "deny_syslog perm=execute uid=1001 : path=/usr/bin/game", rules,
        )
        self.assertNotIn("org.example.Game", rules)

    def test_path_with_spaces_uses_stable_executable_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            appimage = Path(temporary) / "Lunar Client.AppImage"
            appimage.write_bytes(b"lunar")

            rules = FapolicydPolicy.render({1001: (str(appimage),)})

        self.assertIn(
            "deny_syslog perm=execute uid=1001 : "
            "sha256hash=9738b6bf3ae32f433b04b1c3687ac8fec5bf4383b44086c7fb09c5e2a81991cf",
            rules,
        )
        self.assertNotIn("Lunar Client", rules)

    def test_missing_saved_target_does_not_prevent_policy_activation(self):
        rules = FapolicydPolicy.render({
            1001: ("/home/child/Missing Game.AppImage", "/usr/bin/game"),
        })

        self.assertNotIn("Missing", rules)
        self.assertIn("path=/usr/bin/game", rules)

    def test_pattern_guards_future_matching_updates_and_preserves_existing_nonmatches(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            lunar = directory / "Lunar Client-3.7.17.AppImage"
            prism = directory / "PrismLauncher.AppImage"
            lunar.write_bytes(b"lunar")
            prism.write_bytes(b"prism")
            lunar.chmod(0o755)
            prism.chmod(0o755)

            rules = FapolicydPolicy.render(
                {1001: (str(lunar),)}, {1001: (f"{directory}/Lunar Client-*.AppImage",)},
            )

        self.assertIn("sha256hash=", rules)
        self.assertIn(f"allow perm=execute uid=1001 : path={prism}", rules)
        self.assertIn(f"deny_syslog perm=execute uid=1001 : dir={directory}/", rules)
        self.assertLess(rules.index("sha256hash="), rules.index(f"dir={directory}/"))

    def test_reconcile_atomically_writes_and_loads_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            rules_path = Path(temporary) / "89-oh-no-parent-control.rules"
            policy = FapolicydPolicy(rules_path)
            completed = SimpleNamespace(returncode=0, stdout="", stderr="")
            with mock.patch(
                    "oh_no_parent_control.execution_policy.subprocess.run",
                    return_value=completed) as run:
                policy.reconcile({1001: ("/usr/bin/game",)})

            self.assertIn("uid=1001", rules_path.read_text(encoding="utf-8"))
            self.assertEqual([call.args[0] for call in run.call_args_list], [
                ("/usr/sbin/fagenrules",),
                ("/usr/sbin/fapolicyd-cli", "--reload-rules"),
            ])

    def test_failed_reload_restores_previous_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            rules_path = Path(temporary) / "89-oh-no-parent-control.rules"
            rules_path.write_text("old\n", encoding="utf-8")
            policy = FapolicydPolicy(rules_path)
            outcomes = [
                SimpleNamespace(returncode=1, stdout="", stderr="bad"),
                SimpleNamespace(returncode=0, stdout="", stderr=""),
                SimpleNamespace(returncode=0, stdout="", stderr=""),
            ]
            with mock.patch(
                    "oh_no_parent_control.execution_policy.subprocess.run",
                    side_effect=outcomes), self.assertRaises(ExecutionPolicyError):
                policy.reconcile({1001: ("/usr/bin/game",)})

            self.assertEqual(rules_path.read_text(encoding="utf-8"), "old\n")

    def test_remove_deletes_rules_and_loads_the_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            rules_path = Path(temporary) / "89-oh-no-parent-control.rules"
            rules_path.write_text("old\n", encoding="utf-8")
            policy = FapolicydPolicy(rules_path)
            completed = SimpleNamespace(returncode=0, stdout="", stderr="")
            with mock.patch(
                    "oh_no_parent_control.execution_policy.subprocess.run",
                    return_value=completed) as run:
                policy.remove()

            self.assertFalse(rules_path.exists())
            self.assertEqual([call.args[0] for call in run.call_args_list], [
                ("/usr/sbin/fagenrules",),
                ("/usr/sbin/fapolicyd-cli", "--reload-rules"),
            ])

    def test_failed_remove_reload_restores_previous_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            rules_path = Path(temporary) / "89-oh-no-parent-control.rules"
            rules_path.write_text("old\n", encoding="utf-8")
            policy = FapolicydPolicy(rules_path)
            outcomes = [
                SimpleNamespace(returncode=1, stdout="", stderr="bad"),
                SimpleNamespace(returncode=0, stdout="", stderr=""),
                SimpleNamespace(returncode=0, stdout="", stderr=""),
            ]
            with mock.patch(
                    "oh_no_parent_control.execution_policy.subprocess.run",
                    side_effect=outcomes), self.assertRaises(ExecutionPolicyError):
                policy.remove()

            self.assertEqual(rules_path.read_text(encoding="utf-8"), "old\n")

    def test_notification_failure_recompiles_restored_rules_before_notifying(self):
        for operation in ("reconcile", "remove"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temporary:
                rules_path = Path(temporary) / "89-oh-no-parent-control.rules"
                rules_path.write_text("old\n", encoding="utf-8")
                policy = FapolicydPolicy(rules_path)
                seen = []

                def run(command, **kwargs):
                    seen.append((command, rules_path.read_bytes() if rules_path.exists() else None))
                    return SimpleNamespace(returncode=1 if len(seen) == 2 else 0)

                with mock.patch("oh_no_parent_control.execution_policy.subprocess.run", side_effect=run):
                    with self.assertRaisesRegex(ExecutionPolicyError, "could not reload"):
                        if operation == "reconcile":
                            policy.reconcile({1001: ("/usr/bin/game",)})
                        else:
                            policy.remove()
                self.assertEqual(len(seen), 4)
                self.assertEqual(seen[2:], [
                    (("/usr/sbin/fagenrules",), b"old\n"),
                    (("/usr/sbin/fapolicyd-cli", "--reload-rules"), b"old\n"),
                ])

    def test_compile_failure_never_notifies_candidate(self):
        policy = FapolicydPolicy()
        with mock.patch("oh_no_parent_control.execution_policy.subprocess.run",
                        return_value=SimpleNamespace(returncode=1)) as run:
            with self.assertRaises(ExecutionPolicyError):
                policy._reload()
        self.assertEqual([call.args[0] for call in run.call_args_list], [
            ("/usr/sbin/fagenrules",),
        ])

    def test_reload_command_errors_are_bounded_and_do_not_log_output(self):
        import subprocess

        for error in (OSError("private-output"), subprocess.TimeoutExpired("private-command", 15)):
            with self.subTest(error=type(error).__name__):
                policy = FapolicydPolicy()
                with mock.patch("oh_no_parent_control.execution_policy.subprocess.run",
                                side_effect=error) as run:
                    with self.assertLogs("oh-no-parent-control.execution-policy", level="ERROR") as logs:
                        with self.assertRaises(ExecutionPolicyError):
                            policy._reload()
                self.assertEqual(run.call_args.kwargs["timeout"], 15)
                self.assertNotIn("private-", " ".join(logs.output))


if __name__ == "__main__":
    unittest.main()
