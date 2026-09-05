"""Terminate blocked applications owned by one approved child account."""

from __future__ import annotations

import errno
import fnmatch
import logging
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
SNAP_COMMAND_DIRS = (Path("/snap/bin"), Path("/var/lib/snapd/snap/bin"))
MAX_FLATPAK_OUTPUT_BYTES = 1024 * 1024
FLATPAK_TIMEOUT_SECONDS = 5
PROCESS_EXIT_TIMEOUT_SECONDS = 2
MAX_NATIVE_TERMINATION_PASSES = 4
LOG = logging.getLogger("oh-no-parent-control.app-termination")
FLATPAK_INSTANCE_RE = re.compile(r"^[0-9]+$")
FLATPAK_ID_RE = re.compile(
    r"^[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9][A-Za-z0-9_-]*)+$"
)
FLATPAK_COMPONENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
SNAP_INSTANCE_RE = re.compile(
    r"^[a-z0-9](?:-?[a-z0-9])*(?:_[a-z0-9](?:-?[a-z0-9])*)?$"
)
SNAP_APP_RE = re.compile(r"^[a-z0-9](?:-?[a-z0-9])*$")


class AppTerminationError(RuntimeError):
    """A redacted failure while identifying or terminating child applications."""


def _native_targets(targets: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        target for target in targets
        if target.startswith("/") and Path(target).parent not in SNAP_COMMAND_DIRS
    )


def _snap_security_labels(targets: tuple[str, ...]) -> tuple[str, ...]:
    """Project public Snap command paths to their kernel security labels."""
    labels = []
    for target in targets:
        command = Path(target)
        if command.parent not in SNAP_COMMAND_DIRS:
            continue
        instance, separator, app = command.name.partition(".")
        if not SNAP_INSTANCE_RE.fullmatch(instance):
            continue
        if not separator:
            # Snap exposes the short command when the app and base snap names
            # are equal. Parallel instances append ``_<instance-key>`` only
            # to the instance portion of the security label.
            app = instance.partition("_")[0]
        if not SNAP_APP_RE.fullmatch(app):
            continue
        labels.append(f"snap.{instance}.{app}")
    return tuple(sorted(set(labels)))


def _flatpak_targets(targets: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(target for target in targets if not target.startswith("/"))


class RunningAppTerminator:
    """Stop matching processes without ever signaling another account's process."""

    def __init__(self, *, proc_root: Path = PROC_ROOT,
                 runtime_root: Path = RUNTIME_ROOT, flatpak: str = FLATPAK,
                 monotonic=time.monotonic, application_catalog=None):
        self._proc_root = proc_root
        self._runtime_root = runtime_root
        self._flatpak = flatpak
        self._monotonic = monotonic
        self._application_catalog = application_catalog
        self._pidfd_open = getattr(os, "pidfd_open", None)
        self._pidfd_send_signal = getattr(signal, "pidfd_send_signal", None)

    def preflight(self, target_uid: int, targets: tuple[str, ...],
                  patterns: tuple[str, ...]) -> None:
        """Reject an unsupported termination request before policy is changed."""
        identity = self._identity(target_uid)
        native_targets = _native_targets(targets)
        snap_labels = _snap_security_labels(targets)
        application_ids = self._application_ids(target_uid, targets, patterns)
        LOG.info(
            "blocked-app termination preflight native_target_count=%d "
            "flatpak_target_count=%d snap_target_count=%d pattern_count=%d "
            "application_id_count=%d",
            len(native_targets), len(_flatpak_targets(targets)),
            len(snap_labels), len(patterns), len(application_ids),
        )
        if (native_targets or snap_labels or patterns) and (
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
        LOG.info("blocked-app termination stage=started")
        terminated = self._terminate_flatpaks(
            identity, _flatpak_targets(targets),
        )
        terminated += self._terminate_native(
            target_uid, _native_targets(targets), patterns,
            _snap_security_labels(targets),
            self._application_ids(target_uid, targets, patterns),
        )
        LOG.info("blocked-app termination outcome=accepted terminated_count=%d", terminated)
        return terminated

    def _application_ids(self, target_uid, targets, patterns) -> tuple[str, ...]:
        """Resolve blocked launch targets to the child's desktop identities.

        Desktop application scopes survive a launcher exec'ing a different
        binary (Steam) or an AppImage mounting its payload. Resolve only native
        targets here; Flatpak and Snap retain their own runtime identities.
        """
        native = _native_targets(targets)
        if self._application_catalog is None or not (native or patterns):
            return ()
        try:
            return tuple(sorted({
                app["id"].removesuffix(".desktop")
                for app in self._application_catalog(target_uid)
                if any(target in native or any(
                    self._matches_native_pattern(target, pattern)
                    for pattern in patterns
                ) for target in app["targets"])
            }))
        except Exception as error:
            raise AppTerminationError("application identity discovery failed") from error

    @staticmethod
    def _unit_escape(value: str) -> str:
        # systemd.unit's string escaping, not its path escaping: desktop IDs
        # contain literal hyphens, which must not become unit separators.
        return "".join(
            chr(byte) if (65 <= byte <= 90 or 97 <= byte <= 122 or
                          48 <= byte <= 57 or byte in b":_.") and
                          not (index == 0 and byte == ord("."))
            else f"\\x{byte:02x}"
            for index, byte in enumerate(value.encode("utf-8"))
        )

    @classmethod
    def _matches_application_scope(cls, cgroup: str, target_uid: int,
                                   application_ids: tuple[str, ...]) -> bool:
        # Accept only application units underneath this child's user manager.
        # Never select a user/session slice or use a desktop ID substring.
        root = (f"0::/user.slice/user-{target_uid}.slice/"
                f"user@{target_uid}.service/app.slice/")
        for line in cgroup.splitlines():
            if not line.startswith(root):
                continue
            unit = line[len(root):].split("/", 1)[0]
            for application_id in application_ids:
                escaped = re.escape(cls._unit_escape(application_id))
                if re.fullmatch(
                    rf"app-(?:gnome-)?{escaped}"
                    rf"(?:-[A-Za-z0-9_]+\.scope|(?:@[A-Za-z0-9_]+)?\.service)",
                    unit,
                ):
                    return True
        return False

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
            patterns: tuple[str, ...],
            snap_security_labels: tuple[str, ...] = (),
            application_ids: tuple[str, ...] = ()) -> list[tuple[int, int]]:
        candidates = {}
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
                    parent_pid, started = self._process_lineage(entry / "stat")
                    executable = os.readlink(entry / "exe")
                    if executable.endswith(" (deleted)"):
                        executable = executable.removesuffix(" (deleted)")
                    native_match = executable in targets or any(
                            self._matches_native_pattern(executable, pattern)
                            for pattern in patterns)
                    snap_match = False
                    if not native_match and snap_security_labels:
                        security_label = self._process_security_label(
                            entry / "attr/current"
                        )
                        snap_match = any(
                            security_label == label or
                            security_label.startswith(f"{label}//")
                            for label in snap_security_labels
                        )
                    scope_match = bool(application_ids) and self._matches_application_scope(
                        (entry / "cgroup").read_text(encoding="utf-8"),
                        target_uid, application_ids,
                    )
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
                except UnicodeError as error:
                    os.close(pidfd)
                    raise AppTerminationError("application scope is unavailable") from error
                candidates[pid] = (pidfd, parent_pid, started,
                                   native_match or snap_match or scope_match)
            selected = {pid for pid, info in candidates.items() if info[3]}
            direct_count = len(selected)
            # Record every descendant before sending any signal: launchers can
            # exit first and reparent their games/helpers to the user manager.
            # Start times reject a parent PID reused after the child was born.
            while True:
                descendants = {
                    pid for pid, (_fd, parent, started, _match) in candidates.items()
                    if parent in selected and candidates[parent][2] <= started
                } - selected
                if not descendants:
                    break
                selected.update(descendants)
            matches = []
            for pid, (pidfd, _parent, _started, _match) in candidates.items():
                if pid in selected:
                    matches.append((pid, pidfd))
            LOG.info(
                "blocked-app discovery target=[Child user] verified_process_count=%d "
                "direct_match_count=%d descendant_match_count=%d",
                len(candidates), direct_count, len(selected) - direct_count,
            )
        except Exception:
            for pidfd, *_rest in candidates.values():
                os.close(pidfd)
            raise
        for pid, (pidfd, *_rest) in candidates.items():
            if pid not in selected:
                os.close(pidfd)
        # Children first reduces the opportunity for a launcher exit to orphan
        # a still-running payload; all identities remain pinned by pidfd.
        def ancestry_depth(pid):
            ancestors = set()
            while pid in selected and pid not in ancestors:
                ancestors.add(pid)
                pid = candidates[pid][1]
            return len(ancestors)

        matches.sort(key=lambda match: ancestry_depth(match[0]), reverse=True)
        return matches

    @staticmethod
    def _process_lineage(stat_path: Path) -> tuple[int, int]:
        try:
            # comm may contain spaces and parentheses. Fields after its final
            # ')' start at state (3); PPid is 4 and starttime is 22.
            fields = stat_path.read_bytes().rsplit(b")", 1)[1].split()
            parent, started = int(fields[1]), int(fields[19])
            if parent < 0 or started < 0:
                raise ValueError
            return parent, started
        except (ValueError, IndexError) as error:
            raise AppTerminationError("process lineage is unavailable") from error

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

    @staticmethod
    def _process_security_label(attribute_path: Path) -> str:
        """Read the kernel-applied AppArmor identity for one Snap process."""
        try:
            value = attribute_path.read_text(
                encoding="ascii", errors="strict"
            ).strip()
        except OSError as error:
            if error.errno in {errno.ENOENT, errno.ESRCH}:
                raise
            raise AppTerminationError(
                "process security identity is unavailable"
            ) from error
        except UnicodeError as error:
            raise AppTerminationError(
                "process security identity is unavailable"
            ) from error
        return value.partition(" ")[0]

    def _terminate_native(self, target_uid: int, targets: tuple[str, ...],
                          patterns: tuple[str, ...],
                          snap_security_labels: tuple[str, ...] = (),
                          application_ids: tuple[str, ...] = ()) -> int:
        if not targets and not patterns and not snap_security_labels and not application_ids:
            return 0
        terminated = 0
        for _pass in range(MAX_NATIVE_TERMINATION_PASSES):
            matches = self._matching_native_processes(
                target_uid, targets, patterns, snap_security_labels, application_ids,
            )
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
        remaining = self._matching_native_processes(
            target_uid, targets, patterns, snap_security_labels, application_ids,
        )
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
