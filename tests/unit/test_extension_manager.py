import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from oh_no_parent_control.extension_manager import (
    DISABLED_KEY, ENABLED_KEY, UUID, ExtensionManager,
)


class ExtensionManagerTests(unittest.TestCase):
    def setUp(self):
        self.account = SimpleNamespace(
            pw_uid=1001, pw_gid=1001, pw_name="child", pw_dir="/home/child",
        )
        self.runtime = tempfile.TemporaryDirectory()
        self.manager = ExtensionManager(runtime_root=Path(self.runtime.name) / "missing")

    def tearDown(self):
        self.runtime.cleanup()

    @mock.patch("oh_no_parent_control.extension_manager.subprocess.run")
    def test_settings_command_drops_privileges_without_pam(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout="[]\n", stderr="")

        self.manager._run_as(self.account, "gsettings", "get", "schema", "key")

        arguments, = run.call_args.args
        self.assertEqual(arguments, [
            "dbus-run-session", "--", "gsettings", "get", "schema", "key",
        ])
        self.assertEqual(run.call_args.kwargs["user"], 1001)
        self.assertEqual(run.call_args.kwargs["group"], 1001)
        self.assertEqual(run.call_args.kwargs["extra_groups"], ())
        self.assertEqual(run.call_args.kwargs["timeout"], 10)
        self.assertEqual(run.call_args.kwargs["env"]["HOME"], "/home/child")
        self.assertNotIn("DBUS_SESSION_BUS_ADDRESS", run.call_args.kwargs["env"])

    @mock.patch("oh_no_parent_control.extension_manager.subprocess.run")
    def test_settings_failure_is_reported_as_extension_error(self, run):
        run.side_effect = subprocess.CalledProcessError(
            1, ["dbus-run-session"], stderr="session bus failed",
        )

        with self.assertLogs("oh-no-parent-control", "ERROR") as logs:
            with self.assertRaisesRegex(RuntimeError, "GNOME interface is unavailable"):
                self.manager._run_as(
                    self.account, "gsettings", "get", "schema", "key"
                )

        self.assertIn("error_type=CalledProcessError", logs.output[-1])
        self.assertNotIn("session bus failed", logs.output[-1])

    def test_shell_availability_uses_standard_bus_name_ownership(self):
        result = subprocess.CompletedProcess(
            [], 0, stdout="(true,)\n", stderr="",
        )
        manager = ExtensionManager()
        with (
            mock.patch.object(
                manager, "_session_transport", return_value="live-session"
            ),
            mock.patch.object(manager, "_run_command", return_value=result) as run,
        ):
            self.assertTrue(manager._shell_is_available(self.account))

        _, arguments = run.call_args.args
        self.assertIn("org.freedesktop.DBus.NameHasOwner", arguments)
        self.assertEqual(arguments[-1], "org.gnome.Shell.Extensions")
        self.assertTrue(run.call_args.kwargs["require_live"])

    def test_shell_is_not_available_without_a_live_user_bus(self):
        with (
            mock.patch.object(
                self.manager, "_session_transport", return_value="offline"
            ),
            mock.patch.object(self.manager, "_run_command") as run,
        ):
            self.assertFalse(self.manager._shell_is_available(self.account))
        run.assert_not_called()

    @mock.patch("oh_no_parent_control.extension_manager.subprocess.run")
    def test_settings_command_notifies_an_existing_user_session(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout="[]\n", stderr="")
        account = SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="child",
            pw_dir="/home/child",
        )
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / str(account.pw_uid)
            runtime.mkdir()
            (runtime / "bus").touch()
            manager = ExtensionManager(runtime_root=Path(directory))
            with mock.patch(
                    "oh_no_parent_control.extension_manager.stat.S_ISSOCK",
                    return_value=True):
                manager._run_as(account, "gsettings", "get", "schema", "key")

        arguments, = run.call_args.args
        self.assertEqual(arguments, ["gsettings", "get", "schema", "key"])
        self.assertEqual(
            run.call_args.kwargs["env"]["DBUS_SESSION_BUS_ADDRESS"],
            f"unix:path={runtime}/bus",
        )
        self.assertEqual(
            run.call_args.kwargs["env"]["XDG_RUNTIME_DIR"], str(runtime),
        )

    def test_packaged_extension_requires_root_owned_regular_entry_points(self):
        with tempfile.TemporaryDirectory() as directory:
            installation = Path(directory)
            (installation / "metadata.json").write_text("{}", encoding="utf-8")
            (installation / "extension.js").write_text("", encoding="utf-8")
            manager = ExtensionManager(
                installation=installation,
                installation_owner=os.getuid(),
            )

            manager._verify_installation()

            (installation / "extension.js").unlink()
            with self.assertRaisesRegex(RuntimeError, "payload is unavailable"):
                manager._verify_installation()

    def test_enable_clears_explicit_disable_and_verifies_both_lists(self):
        account = SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="child",
            pw_dir="unused",
        )
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            manager = ExtensionManager(
                runtime_root=Path(directory) / "missing-runtime"
            )
            with (
                mock.patch.object(manager, "_account", return_value=(account, home)),
                mock.patch.object(manager, "_verify_installation"),
                mock.patch.object(
                    manager, "_list",
                    side_effect=[
                        ["existing@example.com"],
                        [UUID, "disabled@example.com"],
                        ["existing@example.com", UUID],
                        ["disabled@example.com"],
                    ],
                ),
                mock.patch.object(manager, "_boolean", return_value=False),
                mock.patch.object(manager, "_set_list") as set_list,
            ):
                manager.set_enabled(account.pw_uid, True)

        self.assertEqual(set_list.call_args_list, [
            mock.call(account, DISABLED_KEY, ["disabled@example.com"]),
            mock.call(account, ENABLED_KEY, ["existing@example.com", UUID]),
        ])

    def test_live_enable_uses_gnome_cli_and_verifies_runtime_state(self):
        account = SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="child",
            pw_dir="unused",
        )
        with tempfile.TemporaryDirectory() as directory:
            manager = ExtensionManager(
                runtime_root=Path(directory) / "missing-runtime"
            )
            with (
                mock.patch.object(
                    manager, "_account", return_value=(account, Path(directory))
                ),
                mock.patch.object(manager, "_verify_installation"),
                mock.patch.object(
                    manager, "_list", side_effect=[[], [UUID], [UUID], []]
                ),
                mock.patch.object(manager, "_boolean", return_value=False),
                mock.patch.object(manager, "_shell_is_available", return_value=True),
                mock.patch.object(
                    manager, "_runtime_state",
                    side_effect=[(False, False), (True, True)],
                ),
                mock.patch.object(manager, "_run_command") as run,
                mock.patch.object(manager, "_set_list") as set_list,
            ):
                manager.set_enabled(account.pw_uid, True)

        run.assert_called_once_with(
            account,
            ("gnome-extensions", "enable", "--quiet", UUID),
            require_live=True,
        )
        set_list.assert_not_called()

    def test_live_disable_uses_gnome_cli_and_verifies_inactive_state(self):
        account = SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="child",
            pw_dir="unused",
        )
        with tempfile.TemporaryDirectory() as directory:
            manager = ExtensionManager()
            with (
                mock.patch.object(
                    manager, "_account", return_value=(account, Path(directory))
                ),
                mock.patch.object(manager, "_verify_installation") as verify,
                mock.patch.object(
                    manager, "_list", side_effect=[[UUID], [], [], [UUID]]
                ),
                mock.patch.object(manager, "_shell_is_available", return_value=True),
                mock.patch.object(
                    manager, "_runtime_state",
                    side_effect=[(True, True), (False, False)],
                ),
                mock.patch.object(manager, "_run_command") as run,
                mock.patch.object(manager, "_set_list") as set_list,
            ):
                manager.set_enabled(account.pw_uid, False)

        run.assert_called_once_with(
            account,
            ("gnome-extensions", "disable", "--quiet", UUID),
            require_live=True,
        )
        verify.assert_not_called()
        set_list.assert_not_called()

    def test_live_enable_rejects_inactive_extension_and_rolls_back(self):
        account = SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="child",
            pw_dir="unused",
        )
        with tempfile.TemporaryDirectory() as directory:
            manager = ExtensionManager(
                runtime_root=Path(directory) / "missing-runtime"
            )
            with (
                mock.patch.object(
                    manager, "_account", return_value=(account, Path(directory))
                ),
                mock.patch.object(manager, "_verify_installation"),
                mock.patch.object(
                    manager, "_list", side_effect=[[], [], [], []]
                ),
                mock.patch.object(manager, "_boolean", return_value=False),
                mock.patch.object(manager, "_shell_is_available", return_value=True),
                mock.patch.object(
                    manager, "_runtime_state",
                    side_effect=[(False, False), (True, False), (False, False)],
                ),
                mock.patch.object(manager, "_run_command"),
                mock.patch.object(manager, "_set_list") as set_list,
            ):
                with self.assertRaisesRegex(
                        RuntimeError, "runtime verification failed"):
                    manager.set_enabled(account.pw_uid, True)

        self.assertEqual(set_list.call_args_list, [
            mock.call(account, ENABLED_KEY, []),
            mock.call(account, DISABLED_KEY, []),
        ])

    @mock.patch("oh_no_parent_control.extension_manager.subprocess.run")
    def test_runtime_state_uses_cli_configured_and_active_filters(self, run):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, stdout=f"{UUID}\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout=f"{UUID}\n", stderr=""),
        ]
        manager = ExtensionManager()
        with mock.patch.object(
                manager, "_command",
                side_effect=lambda _account, arguments: (
                    list(arguments), {}, "live-session"
                )):
            self.assertEqual(manager._runtime_state(self.account), (True, True))

        self.assertEqual(run.call_args_list[0].args[0], [
            "gnome-extensions", "list", "--enabled", "--quiet",
        ])
        self.assertEqual(run.call_args_list[1].args[0], [
            "gnome-extensions", "list", "--active", "--quiet",
        ])

    def test_global_extension_switch_fails_before_activation_writes(self):
        account = SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="child",
            pw_dir="unused",
        )
        with tempfile.TemporaryDirectory() as directory:
            manager = ExtensionManager(
                runtime_root=Path(directory) / "missing-runtime"
            )
            with (
                mock.patch.object(
                    manager, "_account", return_value=(account, Path(directory))
                ),
                mock.patch.object(manager, "_verify_installation"),
                mock.patch.object(manager, "_list", side_effect=[[], []]),
                mock.patch.object(manager, "_boolean", return_value=True),
                mock.patch.object(manager, "_set_list") as set_list,
            ):
                with self.assertRaisesRegex(
                        RuntimeError, "user extensions are disabled"):
                    manager.set_enabled(account.pw_uid, True)

        set_list.assert_not_called()

    def test_disable_does_not_require_the_packaged_payload(self):
        account = SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="child",
            pw_dir="unused",
        )
        with tempfile.TemporaryDirectory() as directory:
            manager = ExtensionManager(
                runtime_root=Path(directory) / "missing-runtime"
            )
            with (
                mock.patch.object(
                    manager, "_account", return_value=(account, Path(directory))
                ),
                mock.patch.object(manager, "_verify_installation") as verify,
                mock.patch.object(
                    manager, "_list",
                    side_effect=[[UUID], [UUID], [], []],
                ),
                mock.patch.object(manager, "_set_list") as set_list,
            ):
                manager.set_enabled(account.pw_uid, False)

        verify.assert_not_called()
        self.assertEqual(set_list.call_args_list, [
            mock.call(account, ENABLED_KEY, []),
            mock.call(account, DISABLED_KEY, []),
        ])

    def test_activation_readback_failure_restores_original_settings(self):
        account = SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="child",
            pw_dir="unused",
        )
        with tempfile.TemporaryDirectory() as directory:
            manager = ExtensionManager(
                runtime_root=Path(directory) / "missing-runtime"
            )
            with (
                mock.patch.object(
                    manager, "_account", return_value=(account, Path(directory))
                ),
                mock.patch.object(manager, "_verify_installation"),
                mock.patch.object(
                    manager, "_list", side_effect=[[], [], [], [], []]
                ),
                mock.patch.object(manager, "_boolean", return_value=False),
                mock.patch.object(manager, "_set_list") as set_list,
            ):
                with self.assertRaisesRegex(
                        RuntimeError, "activation verification failed"):
                    manager.set_enabled(account.pw_uid, True)

        self.assertEqual(set_list.call_args_list, [
            mock.call(account, ENABLED_KEY, [UUID]),
            mock.call(account, ENABLED_KEY, []),
            mock.call(account, DISABLED_KEY, []),
        ])


if __name__ == "__main__":
    unittest.main()
