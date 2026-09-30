import contextlib
import os
import pathlib
import shlex
import signal
import select
import sys
import json
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock, call

import pytest


ROOT = pathlib.Path(__file__).parents[2]
ORCHESTRATION = ROOT / "child" / "preview-orchestration.sh"
LIFECYCLE_RUNNER = ROOT / "tests" / "ui" / "run-child-shell-lifecycle"


@pytest.mark.parametrize('failed', [False, True])
def test_shell_socket_runtime_is_short_and_outlives_owned_cleanup(tmp_path, monkeypatch, failed):
    import socket
    from tests.support import child_shell_owner
    from types import SimpleNamespace

    artifact = tmp_path / ('long-checkout-path-' * 8) / 'retained-artifacts'
    artifact.mkdir(parents=True)
    evidence = artifact / 'preserved.log'
    evidence.write_text('retain failure evidence')
    environment = {'ONPC_CHILD_SHELL_ARTIFACT_DIR': str(artifact),
                   'ONPC_CHILD_SHELL_RUNTIME_DIR': str(artifact / 'untrusted-runtime')}
    runtimes = []

    def execute(_command, *, env, timeout, **kwargs):
        actual = env
        runtime = pathlib.Path(actual['ONPC_CHILD_SHELL_RUNTIME_DIR'])
        runtimes.append(runtime)
        assert actual['ONPC_CHILD_SHELL_ARTIFACT_DIR'] == str(artifact)
        assert runtime != artifact / 'untrusted-runtime'
        assert runtime.stat().st_mode & 0o777 == 0o700
        assert timeout == 17
        # Exercise the actual AF_UNIX limit, independent of checkout depth.
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(runtime / 'session-bus'))
        assert runtime.exists()  # The runner still owns its service teardown.
        if failed:
            raise RuntimeError('owned cleanup finished after failure')
        return 'finished'

    @contextlib.contextmanager
    def installed(self, **kwargs):
        yield SimpleNamespace(run=execute)
    monkeypatch.setattr(child_shell_owner.Control, 'installed', installed)
    monkeypatch.setattr(child_shell_owner, 'reap_owned_descendants', lambda: None)
    if failed:
        with pytest.raises(RuntimeError, match='owned cleanup finished'):
            child_shell_owner.run_owned(ROOT, environment, timeout=17, kill_after=1)
    else:
        assert child_shell_owner.run_owned(ROOT, environment, timeout=17, kill_after=1) == 'finished'
    assert len(runtimes) == 1 and not runtimes[0].exists()
    assert evidence.read_text() == 'retain failure evidence'
    assert environment['ONPC_CHILD_SHELL_RUNTIME_DIR'] == str(artifact / 'untrusted-runtime')


@pytest.mark.parametrize('cause', ['cancel', 'worker-killed', 'deadline', 'quiet-exit'])
def test_shell_guardian_reaps_detached_services_even_after_worker_death(tmp_path, monkeypatch, cause):
    from regression_process import Control

    ready, descendant_ready = tmp_path / 'ready.json', tmp_path / 'descendant-ready'
    fixture = tmp_path / 'runner.py'
    fixture.write_text(f'''import json,os,signal,subprocess,sys,time
signal.signal(signal.SIGINT, signal.SIG_IGN)
signal.signal(signal.SIGTERM, signal.SIG_IGN)
child = subprocess.Popen([sys.executable, '-c',
    "import pathlib,signal,time; signal.signal(signal.SIGINT, signal.SIG_IGN); "
    "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
    "pathlib.Path({str(descendant_ready)!r}).touch(); time.sleep(30)"],
    start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
while not os.path.exists({str(descendant_ready)!r}):
    time.sleep(.01)
with open({str(ready)!r}, 'w') as output:
    json.dump({{'runner': os.getpid(), 'descendant': child.pid,
        'runtime': os.environ['ONPC_CHILD_SHELL_RUNTIME_DIR']}}, output)
print('owned stdout', flush=True)
print('owned stderr', file=sys.stderr, flush=True)
{'os._exit(0)' if cause == 'quiet-exit' else 'time.sleep(30)'}
''')
    runner = tmp_path / 'tests/ui/run-child-shell-lifecycle'
    runner.parent.mkdir(parents=True)
    runner.write_text('exec ' + shlex.quote(sys.executable) + ' ' + shlex.quote(str(fixture)) + '\n')
    code = f'''import os,sys
sys.path.insert(0, {str(ROOT)!r})
from pathlib import Path
from tests.support import child_shell
child_shell.ROOT = Path({str(tmp_path)!r})
child_shell.KILL_AFTER = .2
result = child_shell.run_child_shell(os.environ.copy(), timeout={.2 if cause == 'deadline' else 5})
assert 'owned stdout' in result.stdout and 'owned stderr' not in result.stdout, result
assert 'owned stderr' in result.stderr and 'owned stdout' not in result.stderr, result
sys.exit(result.returncode)
'''
    sentinel = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    sentinel_fd = os.pidfd_open(sentinel.pid)
    children, receipts, observations = [], {}, bytearray()
    popen = subprocess.Popen
    def record(*args, **kwargs):
        child = popen(*args, **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(subprocess, 'Popen', record)
    control = Control()
    captured = None
    def tick():
        nonlocal captured
        if captured is None and ready.exists():
            try:
                captured = json.loads(ready.read_text())
            except json.JSONDecodeError:
                return
            for role in ('runner', 'descendant'):
                try:
                    receipts[role] = os.pidfd_open(captured[role])
                except ProcessLookupError:
                    pass  # Already reaped after a successful, fast exit.
            if cause == 'cancel':
                control.stop()
            elif cause == 'worker-killed':
                descriptor = os.pidfd_open(children[0].pid)
                try:
                    signal.pidfd_send_signal(descriptor, signal.SIGKILL)
                finally:
                    os.close(descriptor)
    try:
        status = control.run([sys.executable, '-c', code], cwd=ROOT, env=os.environ.copy(),
                             output=observations.extend, tick=tick, timeout=10, kill_after=1)
        assert status == {'cancel': 130, 'worker-killed': 137, 'deadline': 137, 'quiet-exit': 0}[cause], observations.decode()
        assert captured is not None and sentinel.poll() is None
        for role, descriptor in receipts.items():
            poller = select.poll()
            poller.register(descriptor, select.POLLIN)
            assert poller.poll(3000), f'{role} survived guarded Shell cleanup'
        # The independent owner keeps this allocation until its entire tree
        # is reaped, even when the pytest worker has already disappeared.
        deadline = time.monotonic() + 3
        while pathlib.Path(captured['runtime']).exists() and time.monotonic() < deadline:
            time.sleep(.01)
        assert not pathlib.Path(captured['runtime']).exists()
    finally:
        for descriptor in receipts.values():
            try:
                signal.pidfd_send_signal(descriptor, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.close(descriptor)
        signal.pidfd_send_signal(sentinel_fd, signal.SIGKILL)
        sentinel.wait(timeout=5)
        os.close(sentinel_fd)


@pytest.mark.parametrize('fault', ['foreign-child', 'pidfd-refused'])
def test_shell_adoption_requires_kernel_parenthood_before_any_signal(monkeypatch, fault):
    from tests.support import child_shell_owner
    children = Mock(read_text=Mock(side_effect=['101', '']))
    monkeypatch.setattr(child_shell_owner, 'Path', lambda path: children)
    wait = Mock(return_value=None,
                side_effect=ChildProcessError('foreign child') if fault == 'foreign-child' else None)
    pin, kill, reap = Mock(side_effect=OSError('descriptor pressure')), Mock(), Mock()
    monkeypatch.setattr(child_shell_owner.os, 'waitid', wait)
    monkeypatch.setattr(child_shell_owner.os, 'pidfd_open', pin)
    monkeypatch.setattr(child_shell_owner.os, 'kill', kill)
    monkeypatch.setattr(child_shell_owner.os, 'waitpid', reap)
    order = Mock()
    for name, mocked in [('wait', wait), ('pin', pin), ('kill', kill), ('reap', reap)]:
        order.attach_mock(mocked, name)
    if fault == 'foreign-child':
        with pytest.raises(ChildProcessError, match='foreign child'):
            child_shell_owner.reap_owned_descendants()
        pin.assert_not_called()
        kill.assert_not_called()
        reap.assert_not_called()
    else:
        child_shell_owner.reap_owned_descendants()
        assert order.mock_calls == [
            call.wait(os.P_PID, 101, os.WEXITED | os.WNOHANG | os.WNOWAIT),
            call.pin(101), call.kill(101, signal.SIGKILL), call.reap(101, 0)]


@pytest.mark.parametrize('state', ['exited', 'exit-during-signal', 'live-refusal'])
@pytest.mark.parametrize('pidfd_available', [False, True])
def test_shell_adoption_reaps_exited_children_without_overriding_live_signal_refusal(
        monkeypatch, state, pidfd_available):
    from tests.support import child_shell_owner
    children = Mock(read_text=Mock(side_effect=['101', '']))
    monkeypatch.setattr(child_shell_owner, 'Path', lambda path: children)
    receipt = object()
    wait = Mock(side_effect=[receipt] if state == 'exited' else
                [None, receipt if state == 'exit-during-signal' else None])
    monkeypatch.setattr(child_shell_owner.os, 'waitid', wait)
    pin = Mock(return_value=17, side_effect=None if pidfd_available else OSError('FD pressure'))
    monkeypatch.setattr(child_shell_owner.os, 'pidfd_open', pin)
    direct, pinned = Mock(side_effect=PermissionError('signal refused')), Mock(side_effect=PermissionError('signal refused'))
    monkeypatch.setattr(child_shell_owner.os, 'kill', direct)
    monkeypatch.setattr(child_shell_owner.signal, 'pidfd_send_signal', pinned)
    close, reap = Mock(), Mock()
    monkeypatch.setattr(child_shell_owner.os, 'close', close)
    monkeypatch.setattr(child_shell_owner.os, 'waitpid', reap)
    if state == 'live-refusal':
        with pytest.raises(PermissionError, match='signal refused'):
            child_shell_owner.reap_owned_descendants()
        reap.assert_not_called()
    else:
        child_shell_owner.reap_owned_descendants()
        reap.assert_called_once_with(101, 0)
    if state == 'exited':
        pin.assert_not_called()
        direct.assert_not_called()
        pinned.assert_not_called()
        close.assert_not_called()
    elif pidfd_available:
        pinned.assert_called_once_with(17, signal.SIGKILL)
        close.assert_called_once_with(17)
        direct.assert_not_called()
    else:
        direct.assert_called_once_with(101, signal.SIGKILL)
        pinned.assert_not_called()
        close.assert_not_called()


def test_shell_runtime_is_preserved_when_descendant_cleanup_refuses(tmp_path, monkeypatch):
    from tests.support import child_shell_owner
    from types import SimpleNamespace
    runtime = tmp_path / 'runtime'
    runtime.mkdir(mode=0o700)
    monkeypatch.setattr(child_shell_owner, 'runtime_allocation', lambda *args, **kwargs: runtime)
    @contextlib.contextmanager
    def installed(self, **kwargs):
        yield SimpleNamespace(run=lambda *args, **kwargs: 0)
    monkeypatch.setattr(child_shell_owner.Control, 'installed', installed)
    monkeypatch.setattr(child_shell_owner, 'reap_owned_descendants',
                        Mock(side_effect=OSError('cleanup refused')))
    remove = Mock()
    monkeypatch.setattr(child_shell_owner, 'remove', remove)
    with pytest.raises(OSError, match='cleanup refused'):
        child_shell_owner.run_owned(ROOT, {}, timeout=1, kill_after=1)
    assert runtime.is_dir()
    remove.assert_not_called()


def test_shell_guardian_launch_failure_closes_both_lifetime_pipe_ends(monkeypatch):
    from tests.support import child_shell
    pipes = []
    pipe = os.pipe
    def record():
        descriptors = pipe()
        pipes.append(descriptors)
        return descriptors
    monkeypatch.setattr(child_shell.os, 'pipe', record)
    monkeypatch.setattr(child_shell.subprocess, 'Popen', Mock(side_effect=OSError('launch refused')))
    with pytest.raises(OSError, match='launch refused'):
        child_shell.run_child_shell(os.environ.copy(), timeout=1)
    assert len(pipes) == 1
    for descriptor in pipes[0]:
        with pytest.raises(OSError):
            os.fstat(descriptor)


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
        lifecycle_test += (ROOT / "tests/support/child_shell.py").read_text()

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
            ("wireplumber", "private WirePlumber"),
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
