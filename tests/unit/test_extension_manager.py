import ast
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from oh_no_parent_control.extension_manager import (
    DISABLE_ALL_KEY, DISABLED_KEY, ENABLED_KEY, UUID, ExtensionManager,
)


class GnomeRecoveryState:
    """Stateful public-command fake, including GNOME's global disable switch."""

    def __init__(self, *, inactive=False, ignore_switch=False, rollback_failure=False):
        self.values = {
            ENABLED_KEY: ["other-enabled@example.com"],
            DISABLED_KEY: [UUID, "other-disabled@example.com"],
            DISABLE_ALL_KEY: True,
        }
        self.inactive = inactive
        self.ignore_switch = ignore_switch
        self.rollback_failure = rollback_failure
        self.commands = []

    def run(self, _account, arguments, **_kwargs):
        self.commands.append(arguments)
        stdout = ""
        if arguments[:2] == ("gsettings", "get"):
            value = self.values[arguments[3]]
            stdout = str(value).lower() if type(value) is bool else repr(value)
        elif arguments[:2] == ("gsettings", "set"):
            key, value = arguments[3:]
            if key == DISABLE_ALL_KEY:
                if value == "true" and self.rollback_failure:
                    raise RuntimeError("private-command-canary")
                if not self.ignore_switch:
                    self.values[key] = value == "true"
            else:
                self.values[key] = ast.literal_eval(value)
        elif arguments[:2] == ("gnome-extensions", "enable"):
            if UUID in self.values[DISABLED_KEY]:
                self.values[DISABLED_KEY].remove(UUID)
            if UUID not in self.values[ENABLED_KEY]:
                self.values[ENABLED_KEY].append(UUID)
        elif arguments[:2] == ("gnome-extensions", "list"):
            configured = UUID in self.values[ENABLED_KEY]
            active = configured and not self.values[DISABLE_ALL_KEY] and not self.inactive
            if (arguments[2] == "--enabled" and configured or
                    arguments[2] == "--active" and active):
                stdout = UUID + "\n"
        else:
            raise AssertionError("unexpected GNOME command")
        return subprocess.CompletedProcess(arguments, 0, stdout=stdout, stderr="")


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
        self.assertEqual(arguments[-1], "org.gnome.Shell")
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

    def _recover(self, state, *, live, recover_global_switch=True):
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
                mock.patch.object(manager, "_shell_is_available", return_value=live),
                mock.patch.object(manager, "_run_command", side_effect=state.run),
            ):
                manager.set_enabled(account.pw_uid, True,
                                    recover_global_switch=recover_global_switch)

    def test_disabled_global_switch_recovers_live_and_offline(self):
        for live in (False, True):
            with self.subTest(live=live):
                state = GnomeRecoveryState()
                with self.assertLogs("oh-no-parent-control", "INFO") as logs:
                    self._recover(state, live=live)
                self.assertEqual(state.values, {
                    ENABLED_KEY: ["other-enabled@example.com", UUID],
                    DISABLED_KEY: ["other-disabled@example.com"],
                    DISABLE_ALL_KEY: False,
                })
                self.assertTrue(any("recovery outcome=accepted" in row for row in logs.output))

    def test_preference_transaction_does_not_change_global_switch(self):
        state = GnomeRecoveryState()
        with self.assertRaisesRegex(RuntimeError, "user extensions are disabled"):
            self._recover(state, live=True, recover_global_switch=False)
        self.assertTrue(state.values[DISABLE_ALL_KEY])
        self.assertTrue(all(args[1] == "get" for args in state.commands))

    def test_recovery_of_previously_enabled_extension_is_idempotent(self):
        for live in (False, True):
            with self.subTest(live=live):
                state = GnomeRecoveryState()
                state.values[ENABLED_KEY].append(UUID)
                state.values[DISABLED_KEY].remove(UUID)
                self._recover(state, live=live)
                self._recover(state, live=live)
                self.assertFalse(state.values[DISABLE_ALL_KEY])
                self.assertEqual(state.values[ENABLED_KEY].count(UUID), 1)
                switches = [args for args in state.commands
                            if args[:2] == ("gsettings", "set") and args[3] == DISABLE_ALL_KEY]
                self.assertEqual(len(switches), 1)

    def test_failed_recovery_restores_switch_and_individual_extension_choices(self):
        state = GnomeRecoveryState(inactive=True)
        before = {key: value[:] if isinstance(value, list) else value
                  for key, value in state.values.items()}
        with self.assertRaisesRegex(RuntimeError, "runtime verification failed"):
            self._recover(state, live=True)
        self.assertEqual(state.values, before)

    def test_global_switch_recovery_requires_successful_readback(self):
        state = GnomeRecoveryState(ignore_switch=True)
        with self.assertRaisesRegex(RuntimeError, "switch verification failed"):
            self._recover(state, live=False)
        self.assertTrue(state.values[DISABLE_ALL_KEY])
        self.assertNotIn(UUID, state.values[ENABLED_KEY])

    def test_failed_global_switch_rollback_is_reported_without_command_details(self):
        state = GnomeRecoveryState(inactive=True, rollback_failure=True)
        with self.assertLogs("oh-no-parent-control", "WARNING") as logs:
            with self.assertRaisesRegex(RuntimeError, "rollback could not be verified"):
                self._recover(state, live=True)
        self.assertIn("rollback-failed", logs.output[-1])
        self.assertNotIn("private-command-canary", "\n".join(logs.output))
        self.assertNotIn(UUID, state.values[ENABLED_KEY])
        self.assertIn(UUID, state.values[DISABLED_KEY])

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

    def test_remove_clears_both_extension_lists_offline(self):
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
                mock.patch.object(
                    manager, "_list",
                    side_effect=[
                        ["existing@example.com", UUID],
                        [UUID, "disabled@example.com"],
                        ["existing@example.com"],
                        ["disabled@example.com"],
                    ],
                ),
                mock.patch.object(manager, "_set_list") as set_list,
            ):
                manager.remove(account.pw_uid)

        self.assertEqual(set_list.call_args_list, [
            mock.call(account, ENABLED_KEY, ["existing@example.com"]),
            mock.call(account, DISABLED_KEY, ["disabled@example.com"]),
        ])

    def test_remove_does_not_disable_an_already_inactive_live_extension(self):
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
                mock.patch.object(manager, "_shell_is_available", return_value=True),
                mock.patch.object(
                    manager, "_runtime_state",
                    side_effect=[(False, False), (False, False)],
                ),
                mock.patch.object(manager, "_list", side_effect=[[], [], [], []]),
                mock.patch.object(manager, "_set_live") as set_live,
                mock.patch.object(manager, "_set_list") as set_list,
            ):
                manager.remove(account.pw_uid)

        set_live.assert_not_called()
        set_list.assert_not_called()

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
