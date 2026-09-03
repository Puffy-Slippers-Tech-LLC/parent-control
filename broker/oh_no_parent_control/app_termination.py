"""Terminate blocked applications owned by one approved child account."""

from __future__ import annotations

import errno
import fnmatch
import os
import pwd
import re
import select
import signal
import subprocess
import tempfile
import time
from pathlib import Path


FLATPAK = "/usr/bin/flatpak"
PROC_ROOT = Path("/proc")
RUNTIME_ROOT = Path("/run/user")
MAX_FLATPAK_OUTPUT_BYTES = 1024 * 1024
FLATPAK_TIMEOUT_SECONDS = 5
PROCESS_EXIT_TIMEOUT_SECONDS = 2
MAX_NATIVE_TERMINATION_PASSES = 4
FLATPAK_INSTANCE_RE = re.compile(r"^[0-9]+$")
FLATPAK_ID_RE = re.compile(
    r"^[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9][A-Za-z0-9_-]*)+$"
)
FLATPAK_COMPONENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class AppTerminationError(RuntimeError):
    """A redacted failure while identifying or terminating child applications."""


def _native_targets(targets: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(target for target in targets if target.startswith("/"))


def _flatpak_targets(targets: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(target for target in targets if not target.startswith("/"))


class RunningAppTerminator:
    """Stop matching processes without ever signaling another account's process."""

    def __init__(self, *, proc_root: Path = PROC_ROOT,
                 runtime_root: Path = RUNTIME_ROOT, flatpak: str = FLATPAK,
                 monotonic=time.monotonic):
        self._proc_root = proc_root
        self._runtime_root = runtime_root
        self._flatpak = flatpak
        self._monotonic = monotonic
        self._pidfd_open = getattr(os, "pidfd_open", None)
        self._pidfd_send_signal = getattr(signal, "pidfd_send_signal", None)

    def preflight(self, target_uid: int, targets: tuple[str, ...],
                  patterns: tuple[str, ...]) -> None:
        """Reject an unsupported termination request before policy is changed."""
        identity = self._identity(target_uid)
        if (_native_targets(targets) or patterns) and (
                self._pidfd_open is None or self._pidfd_send_signal is None):
            raise AppTerminationError("pidfd signaling is unavailable")
        if (_flatpak_targets(targets) and
                self._flatpak_instance_root(identity).is_dir() and
                not os.access(self._flatpak, os.X_OK)):
            raise AppTerminationError("Flatpak is unavailable")

    def terminate(self, target_uid: int, targets: tuple[str, ...],
                  patterns: tuple[str, ...]) -> int:
        """Kill blocked apps for *target_uid* and return the number terminated."""
        self.preflight(target_uid, targets, patterns)
        identity = self._identity(target_uid)
        terminated = self._terminate_flatpaks(
            identity, _flatpak_targets(targets),
        )
        terminated += self._terminate_native(
            target_uid, _native_targets(targets), patterns,
        )
        return terminated

    @staticmethod
    def _identity(target_uid: int):
        if type(target_uid) is not int or not 0 < target_uid <= (1 << 32) - 1:
            raise AppTerminationError("invalid target account")
        try:
            identity = pwd.getpwuid(target_uid)
        except KeyError as error:
            raise AppTerminationError("target account is unavailable") from error
        if identity.pw_uid != target_uid or not os.path.isabs(identity.pw_dir):
            raise AppTerminationError("target account identity changed")
        return identity

    def _matching_native_processes(
            self, target_uid: int, targets: tuple[str, ...],
            patterns: tuple[str, ...]) -> list[tuple[int, int]]:
        matches = []
        try:
            entries = tuple(self._proc_root.iterdir())
        except OSError as error:
            raise AppTerminationError("process list is unavailable") from error
        try:
            for entry in entries:
                if not entry.name.isascii() or not entry.name.isdigit():
                    continue
                pid = int(entry.name)
                if pid <= 0 or pid == os.getpid():
                    continue
                try:
                    pidfd = self._pidfd_open(pid, 0)
                except OSError as error:
                    if error.errno in {errno.ENOENT, errno.ESRCH}:
                        continue
                    raise AppTerminationError("could not pin a child process") from error
                try:
                    if entry.stat(follow_symlinks=False).st_uid != target_uid:
                        os.close(pidfd)
                        continue
                    if self._process_uids(entry / "status") != (target_uid,) * 4:
                        os.close(pidfd)
                        continue
                    executable = os.readlink(entry / "exe")
                    if executable.endswith(" (deleted)"):
                        executable = executable.removesuffix(" (deleted)")
                    if executable not in targets and not any(
                            self._matches_native_pattern(executable, pattern)
                            for pattern in patterns):
                        os.close(pidfd)
                        continue
                except FileNotFoundError:
                    os.close(pidfd)
                    continue
                except OSError as error:
                    os.close(pidfd)
                    if error.errno in {errno.ENOENT, errno.ESRCH}:
                        continue
                    raise AppTerminationError(
                        "could not verify child process ownership"
                    ) from error
                except AppTerminationError:
                    os.close(pidfd)
                    raise
                matches.append((pid, pidfd))
        except Exception:
            for _pid, pidfd in matches:
                os.close(pidfd)
            raise
        return matches

    @staticmethod
    def _matches_native_pattern(executable: str, pattern: str) -> bool:
        executable_directory, executable_name = os.path.split(executable)
        pattern_directory, pattern_name = os.path.split(pattern)
        return (
            executable_directory == pattern_directory and
            fnmatch.fnmatchcase(executable_name, pattern_name)
        )

    @staticmethod
    def _process_uids(status_path: Path) -> tuple[int, int, int, int]:
        try:
            with status_path.open("r", encoding="ascii", errors="strict") as status:
                for line in status:
                    if not line.startswith("Uid:"):
                        continue
                    fields = line.removeprefix("Uid:").split()
                    if len(fields) != 4:
                        break
                    return tuple(int(field, 10) for field in fields)
        except OSError as error:
            if error.errno in {errno.ENOENT, errno.ESRCH}:
                raise
            raise AppTerminationError("process ownership is unavailable") from error
        except (UnicodeError, ValueError) as error:
            raise AppTerminationError("process ownership is unavailable") from error
        raise AppTerminationError("process ownership is unavailable")

    def _terminate_native(self, target_uid: int, targets: tuple[str, ...],
                          patterns: tuple[str, ...]) -> int:
        if not targets and not patterns:
            return 0
        terminated = 0
        for _pass in range(MAX_NATIVE_TERMINATION_PASSES):
            matches = self._matching_native_processes(target_uid, targets, patterns)
            if not matches:
                return terminated
            signaled = []
            try:
                for _pid, pidfd in matches:
                    try:
                        self._pidfd_send_signal(pidfd, signal.SIGKILL, None, 0)
                    except OSError as error:
                        if error.errno == errno.ESRCH:
                            continue
                        raise AppTerminationError(
                            "could not terminate a child process"
                        ) from error
                    signaled.append(pidfd)
                    terminated += 1
                self._wait_for_exit(signaled)
            finally:
                for _pid, pidfd in matches:
                    os.close(pidfd)
        remaining = self._matching_native_processes(target_uid, targets, patterns)
        for _pid, pidfd in remaining:
            os.close(pidfd)
        if remaining:
            raise AppTerminationError("blocked child processes are still running")
        return terminated

    def _wait_for_exit(self, pidfds: list[int]) -> None:
        remaining = set(pidfds)
        deadline = self._monotonic() + PROCESS_EXIT_TIMEOUT_SECONDS
        while remaining:
            timeout = deadline - self._monotonic()
            if timeout <= 0:
                raise AppTerminationError("child process termination timed out")
            try:
                readable, _, _ = select.select(tuple(remaining), (), (), timeout)
            except OSError as error:
                raise AppTerminationError("could not verify child process exit") from error
            if not readable:
                raise AppTerminationError("child process termination timed out")
            remaining.difference_update(readable)

    def _run_flatpak(self, identity, arguments: list[str], *, capture: bool):
        environment = {
            "HOME": identity.pw_dir,
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "XDG_RUNTIME_DIR": str(self._runtime_root / str(identity.pw_uid)),
        }
        try:
            if not capture:
                return subprocess.run(
                    [self._flatpak, *arguments],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=FLATPAK_TIMEOUT_SECONDS,
                    check=False,
                    shell=False,
                    close_fds=True,
                    cwd="/",
                    env=environment,
                    user=identity.pw_uid,
                    group=identity.pw_gid,
                    extra_groups=(),
                    umask=0o077,
                )
            with tempfile.TemporaryFile() as output:
                result = subprocess.run(
                    [self._flatpak, *arguments],
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.DEVNULL,
                    timeout=FLATPAK_TIMEOUT_SECONDS,
                    check=False,
                    shell=False,
                    close_fds=True,
                    cwd="/",
                    env=environment,
                    user=identity.pw_uid,
                    group=identity.pw_gid,
                    extra_groups=(),
                    umask=0o077,
                )
                output.flush()
                if os.fstat(output.fileno()).st_size > MAX_FLATPAK_OUTPUT_BYTES:
                    raise AppTerminationError("Flatpak process list is too large")
                output.seek(0)
                encoded = output.read(MAX_FLATPAK_OUTPUT_BYTES + 1)
                return result, encoded
        except subprocess.TimeoutExpired as error:
            raise AppTerminationError("Flatpak termination timed out") from error
        except OSError as error:
            raise AppTerminationError("Flatpak is unavailable") from error

    def _flatpak_instance_root(self, identity) -> Path:
        return self._runtime_root / str(identity.pw_uid) / ".flatpak"

    def _flatpak_instances(self, identity) -> tuple[tuple[str, str], ...]:
        result, encoded = self._run_flatpak(
            identity,
            [
                "ps",
                "--columns=instance:full,application:full,arch:full,branch:full",
            ],
            capture=True,
        )
        if result.returncode != 0:
            raise AppTerminationError("Flatpak process discovery failed")
        try:
            output = encoded.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise AppTerminationError("Flatpak returned an invalid process list") from error
        instances = []
        for index, line in enumerate(output.splitlines()):
            fields = line.split()
            if not fields:
                continue
            if index == 0 and fields == ["Instance", "Application", "Arch", "Branch"]:
                continue
            if len(fields) != 4 or not FLATPAK_INSTANCE_RE.fullmatch(fields[0]):
                raise AppTerminationError("Flatpak returned an invalid process list")
            instance, application, architecture, branch = fields
            if (not FLATPAK_ID_RE.fullmatch(application) or
                    not FLATPAK_COMPONENT_RE.fullmatch(architecture) or
                    not FLATPAK_COMPONENT_RE.fullmatch(branch)):
                raise AppTerminationError("Flatpak returned an invalid process list")
            instances.append((instance, f"app/{application}/{architecture}/{branch}"))
        return tuple(instances)

    def _terminate_flatpaks(self, identity, targets: tuple[str, ...]) -> int:
        if not targets:
            return 0
        # A missing per-UID Flatpak instance directory proves this UID has no
        # running Flatpak instance, and avoids requiring Flatpak when only a
        # stale saved target remains after the package was removed.
        if not self._flatpak_instance_root(identity).is_dir():
            return 0
        instances = self._flatpak_instances(identity)
        selected = []
        for instance, full_ref in instances:
            application = full_ref.split("/", 3)[1]
            if full_ref in targets or application in targets:
                selected.append(instance)
        for instance in selected:
            result = self._run_flatpak(identity, ["kill", instance], capture=False)
            if result.returncode != 0:
                raise AppTerminationError("Flatpak instance termination failed")
        remaining = {
            instance for instance, full_ref in self._flatpak_instances(identity)
            if full_ref in targets or full_ref.split("/", 3)[1] in targets
        }
        if remaining:
            raise AppTerminationError("blocked Flatpak instances are still running")
        return len(selected)
