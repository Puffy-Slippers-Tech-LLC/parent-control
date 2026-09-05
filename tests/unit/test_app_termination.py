import os
import signal
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from oh_no_parent_control.app_termination import (
    AppTerminationError, RunningAppTerminator, _native_targets,
    _snap_security_labels,
)


class RunningAppTerminatorTests(unittest.TestCase):
    @staticmethod
    def _scope(uid, unit):
        return (f"0::/user.slice/user-{uid}.slice/user@{uid}.service/"
                f"app.slice/{unit}\n")

    @staticmethod
    def _process(proc_root: Path, pid: int, uid: int, executable: str,
                 security_label: str | None = None, *, parent: int = 1,
                 started: int = 100, cgroup: str = ""):
        directory = proc_root / str(pid)
        directory.mkdir()
        (directory / "status").write_text(
            f"Name:\tapp\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n",
            encoding="ascii",
        )
        (directory / "exe").symlink_to(executable)
        (directory / "stat").write_text(
            f"{pid} (app) S {parent} " + "0 " * 17 + f"{started}\n",
            encoding="ascii",
        )
        (directory / "cgroup").write_text(cgroup, encoding="utf-8")
        if security_label is not None:
            (directory / "attr").mkdir()
            (directory / "attr/current").write_text(
                f"{security_label} (enforce)\n", encoding="ascii",
            )

    def test_native_matching_is_limited_to_the_approved_child_uid(self):
        with tempfile.TemporaryDirectory() as directory:
            proc_root = Path(directory)
            self._process(proc_root, 101, os.getuid(), "/usr/bin/game")
            self._process(proc_root, 202, os.getuid() + 1, "/usr/bin/game")
            self._process(proc_root, 303, os.getuid(), "/usr/bin/game-v2")
            self._process(proc_root, 404, os.getuid(), "/usr/bin/game-dir/other")
            # A process which exits after pidfd_open may lose its proc files.
            # That race is not an ownership-verification failure.
            (proc_root / "505").mkdir()
            terminator = RunningAppTerminator(proc_root=proc_root)
            opened = []

            def pidfd_open(pid, _flags):
                descriptor = os.open("/dev/null", os.O_RDONLY)
                opened.append((pid, descriptor))
                return descriptor

            terminator._pidfd_open = pidfd_open
            matches = terminator._matching_native_processes(
                os.getuid(), ("/usr/bin/game",), ("/usr/bin/game-*",),
            )
            try:
                self.assertEqual(sorted(pid for pid, _pidfd in matches), [101, 303])
            finally:
                for _pid, descriptor in matches:
                    os.close(descriptor)
                matched_fds = {descriptor for _pid, descriptor in matches}
                for _pid, descriptor in opened:
                    if descriptor not in matched_fds:
                        # Nonmatching process descriptors are closed by the adapter.
                        with self.assertRaises(OSError):
                            os.fstat(descriptor)

    def test_snap_matching_uses_kernel_label_and_selected_child_uid(self):
        with tempfile.TemporaryDirectory() as directory:
            proc_root = Path(directory)
            child_uid = os.getuid()
            self._process(
                proc_root, 101, child_uid,
                "/snap/thunderbird/812/usr/lib/thunderbird/thunderbird",
                "snap.thunderbird.thunderbird",
            )
            self._process(
                proc_root, 202, child_uid + 1,
                "/snap/thunderbird/812/usr/lib/thunderbird/thunderbird",
                "snap.thunderbird.thunderbird",
            )
            self._process(
                proc_root, 303, child_uid,
                "/snap/firefox/999/usr/lib/firefox/firefox",
                "snap.firefox.firefox",
            )
            terminator = RunningAppTerminator(proc_root=proc_root)
            opened = []

            def pidfd_open(pid, _flags):
                descriptor = os.open("/dev/null", os.O_RDONLY)
                opened.append(descriptor)
                return descriptor

            terminator._pidfd_open = pidfd_open
            matches = terminator._matching_native_processes(
                child_uid, (), (), ("snap.thunderbird.thunderbird",),
            )
            try:
                self.assertEqual([pid for pid, _pidfd in matches], [101])
            finally:
                for _pid, descriptor in matches:
                    os.close(descriptor)
                matched_fds = {descriptor for _pid, descriptor in matches}
                for descriptor in opened:
                    if descriptor not in matched_fds:
                        with self.assertRaises(OSError):
                            os.fstat(descriptor)

    def test_snap_command_projects_to_app_label_not_native_executable(self):
        self.assertEqual(_native_targets(("/snap/bin/thunderbird",)), ())
        self.assertEqual(
            _snap_security_labels(("/snap/bin/thunderbird",)),
            ("snap.thunderbird.thunderbird",),
        )
        self.assertEqual(
            _snap_security_labels(("/snap/bin/example_app.viewer",)),
            ("snap.example_app.viewer",),
        )

    def test_desktop_scope_matches_steam_runtime_and_game_after_launcher_exec(self):
        with tempfile.TemporaryDirectory() as directory:
            proc_root = Path(directory)
            uid = os.getuid()
            steam_scope = self._scope(uid, "app-gnome-steam-101.scope")
            self._process(proc_root, 101, uid, "/usr/bin/bash", cgroup=steam_scope)
            self._process(proc_root, 102, uid, "/home/child/Steam/ubuntu12_32/steam",
                          parent=101, cgroup=steam_scope)
            # A game reparented inside the same application scope still belongs
            # to Steam, even though its executable and immediate parent differ.
            self._process(proc_root, 103, uid, "/opt/proton/wine64",
                          cgroup=steam_scope)
            self._process(proc_root, 104, uid + 1, "/opt/proton/wine64",
                          cgroup=steam_scope)
            self._process(proc_root, 105, uid, "/usr/bin/bash",
                          cgroup=self._scope(uid, "app-gnome-terminal-105.scope"))
            terminator = RunningAppTerminator(proc_root=proc_root)
            terminator._pidfd_open = lambda _pid, _flags: os.open("/dev/null", os.O_RDONLY)
            matches = terminator._matching_native_processes(
                uid, ("/usr/lib/steam/bin_steam.sh",), (), (), ("steam",),
            )
            try:
                self.assertEqual({pid for pid, _fd in matches}, {101, 102, 103})
            finally:
                for _pid, fd in matches:
                    os.close(fd)

    def test_appimage_descendants_follow_launcher_across_runtime_scope_change(self):
        with tempfile.TemporaryDirectory() as directory:
            proc_root = Path(directory)
            uid = os.getuid()
            app_id = "appimagekit_123-Lunar_Client"
            launcher_scope = self._scope(
                uid, r"app-gnome-appimagekit_123\x2dLunar_Client-101.scope",
            )
            self._process(proc_root, 101, uid, "/opt/appimagelauncher/binfmt-bypass",
                          started=100, cgroup=launcher_scope)
            self._process(proc_root, 102, uid, "/tmp/.mount_Lunar/client",
                          parent=101, started=101,
                          cgroup=self._scope(uid, "app-org.chromium.Chromium-102.scope"))
            self._process(proc_root, 103, uid, "/opt/java/bin/java",
                          parent=102, started=102)
            # Unrelated Electron application and another account's process.
            self._process(proc_root, 104, uid, "/tmp/.mount_Other/client")
            self._process(proc_root, 105, uid + 1, "/opt/java/bin/java", parent=102)
            # A stale PPid must not attach a process to a reused parent PID.
            self._process(proc_root, 106, uid, "/usr/bin/other", parent=101, started=99)
            terminator = RunningAppTerminator(proc_root=proc_root)
            terminator._pidfd_open = lambda _pid, _flags: os.open("/dev/null", os.O_RDONLY)
            with self.assertLogs("oh-no-parent-control.app-termination", level="INFO") as logs:
                matches = terminator._matching_native_processes(
                    uid, ("/home/child/Applications/Lunar.AppImage",), (), (), (app_id,),
                )
            try:
                self.assertEqual([pid for pid, _fd in matches], [103, 102, 101])
                self.assertIn("direct_match_count=1 descendant_match_count=2", logs.output[0])
                self.assertNotIn("Lunar", str(logs.output))
                self.assertNotIn("/home/", str(logs.output))
            finally:
                for _pid, fd in matches:
                    os.close(fd)

    def test_application_scope_requires_exact_identity_and_child_manager(self):
        matching = RunningAppTerminator._matches_application_scope
        for unit in ("app-gnome-steam-123.scope", "app-steam-abc.scope",
                     "app-steam.service", "app-gnome-steam@abc.service"):
            with self.subTest(unit=unit):
                self.assertTrue(matching(self._scope(1001, unit), 1001, ("steam",)))
        for scope in (
            self._scope(1002, "app-gnome-steam-123.scope"),
            self._scope(1001, "app-gnome-steam-other-123.scope"),
            self._scope(1001, "app-gnome-steamcmd-123.scope"),
            self._scope(1001, "app-gnome-steam.scope"),
            "0::/user.slice/user-1001.slice/session-1.scope\n",
        ):
            with self.subTest(scope=scope):
                self.assertFalse(matching(scope, 1001, ("steam",)))

    def test_catalog_maps_only_blocked_native_targets_and_patterns(self):
        catalog = mock.Mock(return_value=(
            {"id": "steam.desktop", "targets": ("/usr/lib/steam/bin_steam.sh",)},
            {"id": "lunar.desktop", "targets": ("/apps/Lunar-2.AppImage",)},
            {"id": "other.desktop", "targets": ("/apps/Other.AppImage",)},
            {"id": "flatpak.desktop", "targets": ("app/org.example.Game/x86_64/stable",)},
        ))
        terminator = RunningAppTerminator(application_catalog=catalog)
        self.assertEqual(terminator._application_ids(
            1001, ("/usr/lib/steam/bin_steam.sh", "app/org.example.Game/x86_64/stable"),
            ("/apps/Lunar-*.AppImage",),
        ), ("lunar", "steam"))
        catalog.assert_called_once_with(1001)

    def test_catalog_failure_is_redacted_and_prevents_signaling(self):
        terminator = RunningAppTerminator(
            application_catalog=mock.Mock(side_effect=RuntimeError("private account data")),
        )
        terminator._pidfd_send_signal = mock.Mock()
        with mock.patch.object(terminator, "_identity"), \
                self.assertRaisesRegex(AppTerminationError, "^application identity discovery failed$"):
            terminator.terminate(1001, ("/usr/bin/game",), ())
        terminator._pidfd_send_signal.assert_not_called()

    def test_termination_discovers_scope_and_descendants_before_signaling(self):
        with tempfile.TemporaryDirectory() as directory:
            proc_root = Path(directory)
            uid = os.getuid()
            # Same kernel clock tick: ordering must follow ancestry rather
            # than assuming each child has a strictly later start time.
            self._process(proc_root, 101, uid, "/usr/bin/bash",
                          cgroup=self._scope(uid, "app-gnome-game-101.scope"))
            self._process(proc_root, 102, uid, "/opt/runtime/game", parent=101)
            self._process(proc_root, 103, uid, "/usr/bin/allowed")
            terminator = RunningAppTerminator(
                proc_root=proc_root,
                application_catalog=lambda _uid: (
                    {"id": "game.desktop", "targets": ("/opt/launcher.sh",)},
                ),
            )
            descriptors = {}
            signaled = []

            def pin(pid, _flags):
                descriptor = os.open("/dev/null", os.O_RDONLY)
                descriptors[descriptor] = pid
                return descriptor

            def send(descriptor, sig, _info, _flags):
                self.assertEqual(sig, signal.SIGKILL)
                pid = descriptors[descriptor]
                signaled.append(pid)
                # Simulate only these explicitly constructed fake processes
                # exiting. No real process is ever signaled by this regression.
                (proc_root / str(pid) / "status").unlink()

            terminator._pidfd_open = pin
            terminator._pidfd_send_signal = send
            with mock.patch.object(terminator, "_identity"), \
                    mock.patch.object(terminator, "_wait_for_exit"):
                count = terminator.terminate(uid, ("/opt/launcher.sh",), ())
            self.assertEqual(count, 2)
            self.assertEqual(signaled, [102, 101])
            self.assertTrue((proc_root / "103" / "status").exists())

    def test_invalid_scope_closes_all_pinned_descriptors(self):
        with tempfile.TemporaryDirectory() as directory:
            proc_root = Path(directory)
            uid = os.getuid()
            self._process(proc_root, 101, uid, "/usr/bin/game")
            self._process(proc_root, 102, uid, "/usr/bin/other")
            (proc_root / "102" / "cgroup").write_bytes(b"\xff")
            terminator = RunningAppTerminator(proc_root=proc_root)
            descriptors = []

            def pin(_pid, _flags):
                descriptor = os.open("/dev/null", os.O_RDONLY)
                descriptors.append(descriptor)
                return descriptor

            terminator._pidfd_open = pin
            with self.assertRaisesRegex(AppTerminationError, "scope is unavailable"):
                terminator._matching_native_processes(
                    uid, ("/usr/bin/game",), (), (), ("game",),
                )
            for descriptor in descriptors:
                with self.assertRaises(OSError):
                    os.fstat(descriptor)

    def test_stat_lineage_handles_spaces_and_parentheses_in_process_name(self):
        with tempfile.TemporaryDirectory() as directory:
            stat = Path(directory) / "stat"
            stat.write_text("123 (an app) (name)) S 99 " + "0 " * 17 + "456\n")
            self.assertEqual(RunningAppTerminator._process_lineage(stat), (99, 456))

    def test_native_termination_uses_pidfd_sigkill_and_verifies_exit(self):
        descriptor = os.open("/dev/null", os.O_RDONLY)
        terminator = RunningAppTerminator()
        terminator._pidfd_send_signal = mock.Mock()
        with mock.patch.object(
                terminator, "_matching_native_processes",
                side_effect=[[(101, descriptor)], []],
        ):
            count = terminator._terminate_native(
                os.getuid(), ("/usr/bin/game",), (),
            )

        self.assertEqual(count, 1)
        terminator._pidfd_send_signal.assert_called_once_with(
            descriptor, signal.SIGKILL, None, 0,
        )
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_preflight_rejects_missing_pidfd_support_for_native_apps(self):
        identity = SimpleNamespace(pw_uid=1001, pw_gid=1001, pw_dir="/home/child")
        terminator = RunningAppTerminator()
        terminator._pidfd_open = None
        with mock.patch(
                "oh_no_parent_control.app_termination.pwd.getpwuid",
                return_value=identity,
        ), self.assertRaisesRegex(AppTerminationError, "pidfd"):
            terminator.preflight(1001, ("/usr/bin/game",), ())

    def test_flatpak_kill_is_instance_scoped_and_runs_as_approved_child(self):
        identity = SimpleNamespace(pw_uid=1001, pw_gid=1101, pw_dir="/home/child")
        listings = iter((
            "Instance Application Arch Branch\n"
            "111 org.example.Game x86_64 stable\n"
            "222 org.example.Other x86_64 stable\n",
            "222 org.example.Other x86_64 stable\n",
        ))

        def run(command, **kwargs):
            if command[1] == "ps":
                kwargs["stdout"].write(next(listings).encode("utf-8"))
            return SimpleNamespace(returncode=0)

        with tempfile.TemporaryDirectory() as runtime_directory, \
                mock.patch(
                    "oh_no_parent_control.app_termination.subprocess.run",
                    side_effect=run,
                ) as subprocess_run:
            (Path(runtime_directory) / "1001" / ".flatpak").mkdir(parents=True)
            terminator = RunningAppTerminator(runtime_root=Path(runtime_directory))
            count = terminator._terminate_flatpaks(
                identity, ("app/org.example.Game/x86_64/stable",),
            )

        self.assertEqual(count, 1)
        commands = [call.args[0] for call in subprocess_run.call_args_list]
        self.assertEqual(commands, [
            [
                "/usr/bin/flatpak", "ps",
                "--columns=instance:full,application:full,arch:full,branch:full",
            ],
            ["/usr/bin/flatpak", "kill", "111"],
            [
                "/usr/bin/flatpak", "ps",
                "--columns=instance:full,application:full,arch:full,branch:full",
            ],
        ])
        for call in subprocess_run.call_args_list:
            self.assertEqual(call.kwargs["user"], 1001)
            self.assertEqual(call.kwargs["group"], 1101)
            self.assertEqual(call.kwargs["extra_groups"], ())
            self.assertEqual(
                call.kwargs["env"]["XDG_RUNTIME_DIR"],
                str(Path(runtime_directory) / "1001"),
            )
            self.assertFalse(call.kwargs["shell"])

    def test_flatpak_listing_failure_does_not_attempt_a_kill(self):
        identity = SimpleNamespace(pw_uid=1001, pw_gid=1101, pw_dir="/home/child")

        def run(_command, **_kwargs):
            return SimpleNamespace(returncode=1)

        with tempfile.TemporaryDirectory() as runtime_directory, \
                mock.patch(
                    "oh_no_parent_control.app_termination.subprocess.run",
                    side_effect=run,
                ) as subprocess_run, \
                self.assertRaisesRegex(AppTerminationError, "discovery"):
            (Path(runtime_directory) / "1001" / ".flatpak").mkdir(parents=True)
            terminator = RunningAppTerminator(runtime_root=Path(runtime_directory))
            terminator._terminate_flatpaks(identity, ("org.example.Game",))

        self.assertEqual(len(subprocess_run.call_args_list), 1)


if __name__ == "__main__":
    unittest.main()
