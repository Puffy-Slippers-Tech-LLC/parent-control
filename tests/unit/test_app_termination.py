import os
import signal
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from oh_no_parent_control.app_termination import (
    AppTerminationError, RunningAppTerminator,
)


class RunningAppTerminatorTests(unittest.TestCase):
    @staticmethod
    def _process(proc_root: Path, pid: int, uid: int, executable: str):
        directory = proc_root / str(pid)
        directory.mkdir()
        (directory / "status").write_text(
            f"Name:\tapp\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n",
            encoding="ascii",
        )
        (directory / "exe").symlink_to(executable)

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
