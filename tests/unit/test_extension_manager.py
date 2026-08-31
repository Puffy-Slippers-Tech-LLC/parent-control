import subprocess
import unittest
from types import SimpleNamespace
from unittest import mock

from oh_no_parent_control.extension_manager import ExtensionManager


class ExtensionManagerTests(unittest.TestCase):
    def setUp(self):
        self.account = SimpleNamespace(
            pw_uid=1001, pw_gid=1001, pw_name="child", pw_dir="/home/child",
        )

    @mock.patch("oh_no_parent_control.extension_manager.subprocess.run")
    def test_settings_command_drops_privileges_without_pam(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout="[]\n", stderr="")

        ExtensionManager._run_as(self.account, "gsettings", "get", "schema", "key")

        arguments, = run.call_args.args
        self.assertEqual(arguments, [
            "dbus-run-session", "--", "gsettings", "get", "schema", "key",
        ])
        self.assertEqual(run.call_args.kwargs["user"], 1001)
        self.assertEqual(run.call_args.kwargs["group"], 1001)
        self.assertEqual(run.call_args.kwargs["extra_groups"], ())
        self.assertEqual(run.call_args.kwargs["env"]["HOME"], "/home/child")
        self.assertNotIn("DBUS_SESSION_BUS_ADDRESS", run.call_args.kwargs["env"])

    @mock.patch("oh_no_parent_control.extension_manager.subprocess.run")
    def test_settings_failure_is_reported_as_extension_error(self, run):
        run.side_effect = subprocess.CalledProcessError(
            1, ["dbus-run-session"], stderr="session bus failed",
        )

        with self.assertLogs("oh-no-parent-control", "ERROR") as logs:
            with self.assertRaisesRegex(RuntimeError, "GNOME settings are unavailable"):
                ExtensionManager._run_as(self.account, "gsettings", "get", "schema", "key")

        self.assertIn("session bus failed", logs.output[0])


if __name__ == "__main__":
    unittest.main()
