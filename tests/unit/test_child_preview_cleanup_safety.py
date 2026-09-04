import contextlib
import os
import pathlib
import shlex
import signal
import subprocess
import tempfile
import time
import unittest


ROOT = pathlib.Path(__file__).parents[2]
ORCHESTRATION = ROOT / "child" / "preview-orchestration.sh"
LIFECYCLE_RUNNER = ROOT / "tests" / "ui" / "run-child-shell-lifecycle"


class ChildPreviewCleanupSafetyTests(unittest.TestCase):
    def run_orchestration(self, script, *, timeout=10, environment=None):
        return subprocess.run(
            ["bash", "-c", script],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )

    @contextlib.contextmanager
    def helper_process(
        self, *, runtime_directory, ignore_sigterm=False, new_session=True
    ):
        environment = {**os.environ, "XDG_RUNTIME_DIR": str(runtime_directory)}
        with tempfile.TemporaryDirectory(prefix="onpc-helper-ready-") as temporary:
            ready_path = pathlib.Path(temporary) / "ready"
            if ignore_sigterm:
                command = [
                    "bash",
                    "-c",
                    'trap "" TERM; : >"$1"; while :; do sleep 60; done',
                    "onpc-owned-helper",
                    str(ready_path),
                ]
            else:
                command = [
                    "bash",
                    "-c",
                    ': >"$1"; exec sleep 60',
                    "onpc-owned-helper",
                    str(ready_path),
                ]
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=environment,
                start_new_session=new_session,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                deadline = time.monotonic() + 2
                while not ready_path.exists() and process.poll() is None:
                    if time.monotonic() >= deadline:
                        self.fail("Controlled preview helper did not become ready")
                    time.sleep(0.01)
                self.assertIsNone(process.poll(), "Controlled preview helper exited early")
                yield process
            finally:
                if process.poll() is None:
                    try:
                        if new_session:
                            os.killpg(process.pid, signal.SIGKILL)
                        else:
                            process.kill()
                    except ProcessLookupError:
                        pass
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.fail(f"Controlled preview helper {process.pid} leaked")

    def cleanup_spy_script(self, *, preview_root, runtime_setup, signal_log, fallback_log):
        return f"""
            source {shlex.quote(str(ORCHESTRATION))}
            onpc_preview_configure child {shlex.quote(str(preview_root))}
            {runtime_setup}
            kill() {{ printf '%s\\n' "$*" >>{shlex.quote(str(signal_log))}; return 0; }}
            onpc_preview_stop_runtime_helpers() {{
                printf '%s\\n' called >>{shlex.quote(str(fallback_log))}
                return 1
            }}
            onpc_preview_cleanup || true
        """

    def assert_no_cleanup_signal_or_fallback(self, signal_log, fallback_log):
        self.assertFalse(
            signal_log.exists(),
            f"Cleanup attempted a signal: {signal_log.read_text() if signal_log.exists() else ''}",
        )
        self.assertFalse(
            fallback_log.exists(),
            "Cleanup attempted ambient process discovery",
        )

    def test_cleanup_contains_no_ambient_runtime_process_discovery(self):
        source = ORCHESTRATION.read_text()
        lifecycle_test = (
            ROOT / "tests" / "ui" / "test_child_shell_lifecycle.py"
        ).read_text()

        self.assertNotIn("/proc/[0-9]*/environ", source)
        self.assertNotIn("onpc_preview_runtime_helper_pids", source)
        self.assertNotIn("onpc_preview_stop_runtime_helpers", source)
        self.assertNotIn('Path("/proc").glob', lifecycle_test)
        self.assertNotIn("XDG_RUNTIME_DIR=", lifecycle_test)

    def test_cleanup_after_configuration_signals_nothing_for_unsafe_runtimes(self):
        runtime_setups = {
            "unset": "unset XDG_RUNTIME_DIR",
            "empty": "export XDG_RUNTIME_DIR=''",
            "host": f"export XDG_RUNTIME_DIR=/run/user/{os.getuid()}",
        }
        for case, runtime_setup in runtime_setups.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory(
                dir="/tmp", prefix="onpc-cleanup-safety-"
            ) as temporary:
                case_root = pathlib.Path(temporary)
                preview_root = case_root / "preview"
                preview_root.mkdir()
                signal_log = case_root / "signal.log"
                fallback_log = case_root / "fallback.log"
                result = self.run_orchestration(
                    self.cleanup_spy_script(
                        preview_root=preview_root,
                        runtime_setup=runtime_setup,
                        signal_log=signal_log,
                        fallback_log=fallback_log,
                    )
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assert_no_cleanup_signal_or_fallback(signal_log, fallback_log)

    def test_dependency_failure_before_environment_preparation_signals_nothing(self):
        with tempfile.TemporaryDirectory(
            dir="/tmp", prefix="onpc-dependency-failure-"
        ) as temporary:
            case_root = pathlib.Path(temporary)
            preview_root = case_root / "preview"
            preview_root.mkdir()
            signal_log = case_root / "signal.log"
            fallback_log = case_root / "fallback.log"
            script = f"""
                set -e
                source {shlex.quote(str(ORCHESTRATION))}
                onpc_preview_configure child {shlex.quote(str(preview_root))}
                kill() {{ printf '%s\\n' "$*" >>{shlex.quote(str(signal_log))}; return 0; }}
                onpc_preview_stop_runtime_helpers() {{
                    printf '%s\\n' called >>{shlex.quote(str(fallback_log))}
                    return 1
                }}
                cleanup() {{
                    local status=$?
                    trap - EXIT HUP INT TERM
                    onpc_preview_cleanup || status=1
                    exit "$status"
                }}
                trap cleanup EXIT HUP INT TERM
                onpc_preview_require_lifecycle_dependencies() {{ return 23; }}
                onpc_preview_require_lifecycle_dependencies
            """
            result = self.run_orchestration(script)

            self.assertEqual(result.returncode, 23, result.stderr)
            self.assert_no_cleanup_signal_or_fallback(signal_log, fallback_log)

    def test_version_failure_before_environment_preparation_signals_nothing(self):
        with tempfile.TemporaryDirectory(
            dir="/tmp", prefix="onpc-version-failure-"
        ) as temporary:
            case_root = pathlib.Path(temporary)
            preview_root = case_root / "preview"
            preview_root.mkdir()
            signal_log = case_root / "signal.log"
            fallback_log = case_root / "fallback.log"
            script = f"""
                set -e
                source {shlex.quote(str(ORCHESTRATION))}
                onpc_preview_configure child {shlex.quote(str(preview_root))}
                kill() {{ printf '%s\\n' "$*" >>{shlex.quote(str(signal_log))}; return 0; }}
                onpc_preview_stop_runtime_helpers() {{
                    printf '%s\\n' called >>{shlex.quote(str(fallback_log))}
                    return 1
                }}
                cleanup() {{
                    local status=$?
                    trap - EXIT HUP INT TERM
                    onpc_preview_cleanup || status=1
                    exit "$status"
                }}
                trap cleanup EXIT HUP INT TERM
                gnome-shell() {{ printf '%s\\n' 'GNOME Shell 49.9'; }}
                onpc_preview_require_supported_shell_version
            """
            result = self.run_orchestration(script)

            self.assertEqual(result.returncode, 1, result.stderr)
            self.assert_no_cleanup_signal_or_fallback(signal_log, fallback_log)

    def test_preparation_failure_stops_only_an_already_recorded_child(self):
        with tempfile.TemporaryDirectory(
            dir="/tmp", prefix="onpc-preparation-failure-"
        ) as temporary:
            preview_root = pathlib.Path(temporary)
            runtime_directory = preview_root / "runtime"
            with self.helper_process(runtime_directory=runtime_directory) as owned:
                with self.helper_process(runtime_directory=runtime_directory) as unrelated:
                    script = f"""
                        set -e
                        source {shlex.quote(str(ORCHESTRATION))}
                        onpc_preview_configure child {shlex.quote(str(preview_root))}
                        onpc_preview_bus_pid={owned.pid}
                        onpc_preview_record_owned_process "$onpc_preview_bus_pid" \
                            onpc_preview_bus_start_time 'private session bus'
                        onpc_preview_prepare_environment() {{ return 41; }}
                        preparation_status=0
                        onpc_preview_prepare_environment || preparation_status=$?
                        onpc_preview_cleanup
                        test "$preparation_status" -eq 41
                    """
                    result = self.run_orchestration(script)

                    self.assertEqual(result.returncode, 0, result.stderr)
                    owned.wait(timeout=2)
                    self.assertIsNone(
                        unrelated.poll(),
                        "Cleanup signalled an unrelated process sharing its runtime",
                    )

    def test_unrelated_process_with_same_runtime_survives_owned_cleanup(self):
        with tempfile.TemporaryDirectory(
            dir="/tmp", prefix="onpc-shared-runtime-"
        ) as temporary:
            preview_root = pathlib.Path(temporary)
            runtime_directory = preview_root / "runtime"
            with self.helper_process(runtime_directory=runtime_directory) as owned:
                with self.helper_process(runtime_directory=runtime_directory) as unrelated:
                    script = f"""
                        set -e
                        source {shlex.quote(str(ORCHESTRATION))}
                        onpc_preview_configure child {shlex.quote(str(preview_root))}
                        export XDG_RUNTIME_DIR={shlex.quote(str(runtime_directory))}
                        onpc_preview_shell_pid={owned.pid}
                        onpc_preview_record_owned_process "$onpc_preview_shell_pid" \
                            onpc_preview_shell_start_time 'GNOME Shell'
                        onpc_preview_cleanup
                    """
                    result = self.run_orchestration(script)

                    self.assertEqual(result.returncode, 0, result.stderr)
                    owned.wait(timeout=2)
                    self.assertIsNone(
                        unrelated.poll(),
                        "Cleanup inferred ownership from the shared runtime directory",
                    )

    def test_all_explicitly_recorded_service_groups_terminate(self):
        slots = (
            ("shell", "GNOME Shell"),
            ("devkit", "Mutter Devkit"),
            ("bus", "private session bus"),
            ("registry", "AT-SPI registry"),
            ("pipewire", "private PipeWire"),
        )
        with tempfile.TemporaryDirectory(
            dir="/tmp", prefix="onpc-owned-services-"
        ) as temporary, contextlib.ExitStack() as stack:
            preview_root = pathlib.Path(temporary)
            runtime_directory = preview_root / "runtime"
            processes = {
                slot: stack.enter_context(
                    self.helper_process(runtime_directory=runtime_directory)
                )
                for slot, _label in slots
            }
            assignments = []
            for slot, label in slots:
                assignments.extend(
                    (
                        f"onpc_preview_{slot}_pid={processes[slot].pid}",
                        f"onpc_preview_record_owned_process \"$onpc_preview_{slot}_pid\" "
                        f"onpc_preview_{slot}_start_time {shlex.quote(label)}",
                    )
                )
            script = f"""
                set -e
                source {shlex.quote(str(ORCHESTRATION))}
                onpc_preview_configure child {shlex.quote(str(preview_root))}
                {'; '.join(assignments)}
                onpc_preview_cleanup
            """
            result = self.run_orchestration(script)

            self.assertEqual(result.returncode, 0, result.stderr)
            for slot, process in processes.items():
                process.wait(timeout=2)
                self.assertIsNotNone(process.returncode, f"Owned {slot} process leaked")

    def test_cleanup_is_bounded_when_owned_child_ignores_sigterm(self):
        with tempfile.TemporaryDirectory(
            dir="/tmp", prefix="onpc-stubborn-helper-"
        ) as temporary:
            preview_root = pathlib.Path(temporary)
            runtime_directory = preview_root / "runtime"
            with self.helper_process(
                runtime_directory=runtime_directory, ignore_sigterm=True
            ) as owned:
                script = f"""
                    set -e
                    source {shlex.quote(str(ORCHESTRATION))}
                    onpc_preview_configure child {shlex.quote(str(preview_root))}
                    onpc_preview_stop_attempts=3
                    onpc_preview_stop_interval=0.02
                    onpc_preview_shell_pid={owned.pid}
                    onpc_preview_record_owned_process "$onpc_preview_shell_pid" \
                        onpc_preview_shell_start_time 'GNOME Shell'
                    onpc_preview_cleanup
                """
                started = time.monotonic()
                result = self.run_orchestration(script)
                elapsed = time.monotonic() - started

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertLess(elapsed, 2, "Cleanup exceeded its bounded shutdown window")
                self.assertIn("escalating to SIGKILL", result.stderr)
                owned.wait(timeout=2)

    def test_mismatched_recorded_identity_fails_closed_without_signalling(self):
        with tempfile.TemporaryDirectory(
            dir="/tmp", prefix="onpc-mismatched-helper-"
        ) as temporary:
            preview_root = pathlib.Path(temporary)
            runtime_directory = preview_root / "runtime"
            with self.helper_process(runtime_directory=runtime_directory) as unrelated:
                script = f"""
                    source {shlex.quote(str(ORCHESTRATION))}
                    onpc_preview_configure child {shlex.quote(str(preview_root))}
                    onpc_preview_shell_pid={unrelated.pid}
                    onpc_preview_shell_start_time=invalid
                    onpc_preview_stop_shell
                """
                result = self.run_orchestration(script)

                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("recorded leader identity no longer matches", result.stderr)
                self.assertIsNone(unrelated.poll(), "Identity mismatch signalled a process")

    def test_recorded_child_without_its_own_group_is_stopped_only_by_pid(self):
        with tempfile.TemporaryDirectory(
            dir="/tmp", prefix="onpc-direct-pid-helper-"
        ) as temporary:
            preview_root = pathlib.Path(temporary)
            runtime_directory = preview_root / "runtime"
            with self.helper_process(
                runtime_directory=runtime_directory, new_session=False
            ) as owned:
                script = f"""
                    set -e
                    source {shlex.quote(str(ORCHESTRATION))}
                    onpc_preview_configure child {shlex.quote(str(preview_root))}
                    onpc_preview_stop_attempts=3
                    onpc_preview_stop_interval=0.02
                    onpc_preview_bus_pid={owned.pid}
                    registration_status=0
                    onpc_preview_record_owned_process "$onpc_preview_bus_pid" \
                        onpc_preview_bus_start_time 'private session bus' \
                        2 0.01 || registration_status=$?
                    onpc_preview_stop_private_services
                    test "$registration_status" -eq 1
                """
                result = self.run_orchestration(script)

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("by PID", result.stderr)
                owned.wait(timeout=2)

    def test_lifecycle_runner_uses_only_the_owned_cleanup_boundary(self):
        runner = LIFECYCLE_RUNNER.read_text()

        configure = runner.index("onpc_preview_configure")
        trap = runner.index("trap cleanup EXIT HUP INT TERM")
        dependencies = runner.index("onpc_preview_require_lifecycle_dependencies")
        version = runner.index("onpc_preview_require_supported_shell_version")
        preparation = runner.index("onpc_preview_prepare_environment")
        self.assertLess(configure, trap)
        self.assertLess(trap, dependencies)
        self.assertLess(dependencies, version)
        self.assertLess(version, preparation)
        self.assertNotIn("onpc_preview_stop_runtime_helpers", runner)


if __name__ == "__main__":
    unittest.main()
