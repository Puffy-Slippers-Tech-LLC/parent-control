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

    def test_reconcile_atomically_writes_and_loads_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            rules_path = Path(temporary) / "89-oh-no-parent-control.rules"
            policy = FapolicydPolicy(rules_path, ("fagenrules", "--load"))
            completed = SimpleNamespace(returncode=0, stdout="", stderr="")
            with mock.patch(
                    "oh_no_parent_control.execution_policy.subprocess.run",
                    return_value=completed) as run:
                policy.reconcile({1001: ("/usr/bin/game",)})

            self.assertIn("uid=1001", rules_path.read_text(encoding="utf-8"))
            self.assertEqual(run.call_args.args[0], ("fagenrules", "--load"))

    def test_failed_reload_restores_previous_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            rules_path = Path(temporary) / "89-oh-no-parent-control.rules"
            rules_path.write_text("old\n", encoding="utf-8")
            policy = FapolicydPolicy(rules_path)
            outcomes = [
                SimpleNamespace(returncode=1, stdout="", stderr="bad"),
                SimpleNamespace(returncode=0, stdout="", stderr=""),
            ]
            with mock.patch(
                    "oh_no_parent_control.execution_policy.subprocess.run",
                    side_effect=outcomes), self.assertRaises(ExecutionPolicyError):
                policy.reconcile({1001: ("/usr/bin/game",)})

            self.assertEqual(rules_path.read_text(encoding="utf-8"), "old\n")


if __name__ == "__main__":
    unittest.main()
