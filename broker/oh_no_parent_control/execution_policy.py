"""Mirror Malcontent executable blocklists into the kernel execution policy."""

from __future__ import annotations

import hashlib
import fnmatch
from common.oh_no_parent_control_ui.diagnostic_events import get_logger, error_code
import os
import stat
import subprocess
import tempfile
import threading
from pathlib import Path

LOG = get_logger("execution-policy")

# fapolicyd classifies ELF objects itself, including PIE runtimes, rather than
# relying on filename extensions or libmagic's AppImage classification. Include
# shared-library and malformed ELF classifications so those cannot escape the
# read guard. Ordinary documents in a wildcard directory remain readable.
ELF_OBJECT_TYPES = "application/x-executable,application/x-sharedlib,application/x-bad-elf"


class ExecutionPolicyError(RuntimeError):
    """The execution policy could not be generated or activated safely."""


class FapolicydPolicy:
    """Maintain the product-owned fapolicyd deny rules.

    Malcontent filters launchers in GNOME Shell, but callers which open a
    trusted ``.desktop`` file directly bypass that UI check.  fapolicyd's
    execute permission event closes that second launch path. Opening a blocked
    program must also be denied: AppImageLauncher reads the original file and
    executes a patched in-memory runtime instead of executing that file.
    """

    def __init__(
            self,
            rules_path: Path = Path(
                "/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules"
            ),
            reload_command=("/usr/sbin/fapolicyd-cli", "--reload-rules"),
            compile_command=("/usr/sbin/fagenrules",), *,
            tolerate_rule_errors=False):
        self._rules_path = rules_path
        self._reload_command = tuple(reload_command)
        self._compile_command = tuple(compile_command)
        self._lock = threading.Lock()
        # Disk equality alone cannot establish even successful notification:
        # an earlier process or failed rollback may have left stale live rules.
        # This is only a command-success cache, not a daemon acknowledgement.
        self._last_notified_contents: bytes | None = None
        self._tolerate_rule_errors = tolerate_rule_errors
        self._rule_issues: tuple[tuple[int, str, str], ...] = ()

    @property
    def rule_issues(self):
        """Private rule identities for the last successfully notified policy."""
        with self._lock:
            return self._rule_issues

    def validate(self, filters, patterns):
        # Use the eventual write's isolation policy without publishing warnings
        # for a candidate that was never committed.
        self.render(filters, patterns, issues=[] if self._tolerate_rule_errors else None)

    @staticmethod
    def _digest(path: str) -> str:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
        except FileNotFoundError:
            raise
        except OSError as error:
            raise ExecutionPolicyError(f"blocked executable is unavailable: {path}") from error
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise ExecutionPolicyError(f"blocked executable is not a regular file: {path}")
            digest = hashlib.sha256()
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            after = os.fstat(descriptor)
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                    after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                raise ExecutionPolicyError(f"blocked executable changed while hashing: {path}")
            return digest.hexdigest()
        finally:
            os.close(descriptor)

    @classmethod
    def _object_clause(cls, target: str) -> str:
        # fapolicyd 1.3 splits rules on whitespace and commas and offers no
        # quoting for path= values.  Use the executable identity for those
        # valid filesystem names instead of emitting a rule which cannot parse.
        if any(character.isspace() for character in target) or "," in target:
            return f"sha256hash={cls._digest(target)}"
        return f"path={target}"

    @staticmethod
    def _safe_directory(directory: str) -> None:
        if (not directory.startswith("/") or any(character.isspace() for character in directory)
                or any(character in directory for character in ',"\\\x00\r\n')):
            raise ExecutionPolicyError("pattern directory cannot be represented safely")

    @staticmethod
    def _has_elf_header(path: str) -> bool:
        # Only needed for non-executable files whose names cannot be represented
        # in an exception. Text/images need no open exception to an ELF guard;
        # non-executable ELF libraries do. Never follow a replaced symlink or
        # block on a substituted FIFO while inspecting an untrusted directory.
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ExecutionPolicyError("guarded directory entry is not a regular file")
            return os.read(descriptor, 4) == b"\x7fELF"
        finally:
            os.close(descriptor)

    @classmethod
    def _pattern_rules(cls, uid: int, patterns: tuple[str, ...], blocked: set[str]) -> list[str]:
        """Compile basename globs into exact exceptions plus one directory guard."""
        grouped: dict[str, list[str]] = {}
        for pattern in patterns:
            directory, _separator, basename = pattern.rpartition("/")
            directory = directory or "/"
            cls._safe_directory(directory)
            if not basename or not any(character in basename for character in "*?"):
                raise ExecutionPolicyError("invalid execution-policy pattern")
            grouped.setdefault(directory, []).append(basename)
        lines = []
        for directory, basenames in sorted(grouped.items()):
            try:
                entries = list(os.scandir(directory))
            except FileNotFoundError:
                entries = []
            except OSError as error:
                raise ExecutionPolicyError("could not inspect guarded directory") from error
            for entry in sorted(entries, key=lambda item: item.name):
                # Basename patterns intentionally never cross a slash; existing
                # immediate subdirectories are safe prefixes to preserve.
                if entry.is_dir(follow_symlinks=False):
                    child = f"{directory.rstrip('/')}/{entry.name}/"
                    cls._safe_directory(child)
                    lines.append(f"allow perm=execute uid={uid} : dir={child}")
                    lines.append(f"allow perm=open uid={uid} : dir={child}")
                elif entry.is_file(follow_symlinks=False):
                    # Concrete denials were emitted above. They need no
                    # exception to the directory guard, even when their name
                    # no longer matches a saved version wildcard.
                    if entry.path in blocked:
                        continue
                    if not any(fnmatch.fnmatchcase(entry.name, pattern) for pattern in basenames):
                        executable = os.access(entry.path, os.X_OK)
                        if any(character.isspace() for character in entry.path) or "," in entry.path:
                            if executable or cls._has_elf_header(entry.path):
                                raise ExecutionPolicyError("existing nonmatching executable cannot be represented")
                            continue
                        if executable:
                            lines.append(f"allow perm=execute uid={uid} : path={entry.path}")
                        # Include non-executable nonmatches: the read guard also
                        # sees ELF libraries and images before chmod +x.
                        lines.append(f"allow perm=open uid={uid} : path={entry.path}")
            prefix = directory.rstrip("/") + "/"
            lines.append(f"deny_syslog perm=execute uid={uid} : dir={prefix}")
            lines.append(f"deny_syslog perm=open uid={uid} : dir={prefix} ftype={ELF_OBJECT_TYPES}")
        return lines

    @classmethod
    def render(cls, filters: dict[int, tuple[str, ...]],
               patterns: dict[int, tuple[str, ...]] | None = None, *,
               issues: list[tuple[int, str, str]] | None = None) -> str:
        lines = [
            "# Generated by Oh No! Parent Control. Do not edit.",
        ]
        patterns = patterns or {}
        for uid in sorted(set(filters) | set(patterns)):
            if type(uid) is not int or not 0 < uid <= (1 << 32) - 1:
                raise ExecutionPolicyError("invalid execution-policy UID")
            targets = set(filters.get(uid, ()))
            # Concrete blocks precede every allowance, including allowances
            # from enclosing directories. Keep them if a wildcard group fails.
            for target in sorted(targets):
                # Flatpak refs are enforced by Malcontent/Flatpak. fapolicyd
                # rules apply only to native executable paths.
                if not target.startswith("/"):
                    continue
                try:
                    clause = cls._object_clause(target)
                except FileNotFoundError:
                    # Saved policies intentionally survive uninstalled apps.
                    # A missing object cannot execute and therefore needs no
                    # current kernel rule.
                    continue
                except (ExecutionPolicyError, OSError):
                    if issues is None:
                        raise
                    issues.append((uid, "target", target))
                    continue
                lines.append(
                    f"deny_syslog perm=execute uid={uid} : {clause}"
                )
                lines.append(
                    f"deny_syslog perm=open uid={uid} : {clause}"
                )
            grouped: dict[str, list[str]] = {}
            for pattern in patterns.get(uid, ()):
                grouped.setdefault(pattern.rpartition("/")[0] or "/", []).append(pattern)
            # A directory guard and its exceptions are indivisible. Never keep
            # partial allowances or a blanket denial from a failed group.
            # Specific guards precede enclosing-directory allowances.
            for directory in sorted(grouped, key=lambda path: (-path.count("/"), path)):
                group = tuple(grouped[directory])
                try:
                    lines.extend(cls._pattern_rules(uid, group, targets))
                except (ExecutionPolicyError, OSError):
                    if issues is None:
                        raise
                    issues.extend((uid, "pattern", pattern) for pattern in group)
        return "\n".join(lines) + "\n"

    def reconcile(self, filters: dict[int, tuple[str, ...]],
                  patterns: dict[int, tuple[str, ...]] | None = None) -> None:
        LOG.info("execution-policy.001", account_count=len(filters))
        with self._lock:
            issues = [] if self._tolerate_rule_errors else None
            contents = self.render(filters, patterns, issues=issues).encode("utf-8")
            previous = None
            try:
                previous = self._rules_path.read_bytes()
            except FileNotFoundError:
                pass
            except OSError as error:
                raise ExecutionPolicyError("could not read current execution policy") from error

            if previous == contents and self._last_notified_contents == contents:
                self._record_rule_issues(issues)
                LOG.info("execution-policy.002")
                return

            self._last_notified_contents = None
            LOG.info("execution-policy.003")
            self._replace(contents)
            try:
                LOG.info("execution-policy.004")
                self._reload()
            except Exception as error:
                LOG.error("execution-policy.005", error_type=error_code(error))
                try:
                    if previous is None:
                        self._rules_path.unlink(missing_ok=True)
                    else:
                        self._replace(previous)
                    self._reload()
                    self._last_notified_contents = previous
                except Exception as rollback_error:
                    LOG.error("execution-policy.006", error_type=error_code(rollback_error))
                    raise ExecutionPolicyError(
                        "execution-policy rollback could not be activated"
                    ) from rollback_error
                if isinstance(error, ExecutionPolicyError):
                    raise
                raise ExecutionPolicyError("execution policy could not be activated") from error
            self._last_notified_contents = contents
            self._record_rule_issues(issues)
            LOG.info("execution-policy.007")

    def _record_rule_issues(self, issues):
        self._rule_issues = tuple(issues or ())
        if self._rule_issues:
            # Identities stay local; automatic diagnostics contain counts only.
            LOG.error("execution-policy.rules-omitted", rule_count=len(self._rule_issues))

    def remove(self) -> None:
        """Remove the product rule file and activate that absence safely."""
        with self._lock:
            try:
                previous = self._rules_path.read_bytes()
            except FileNotFoundError:
                previous = None
            except OSError as error:
                raise ExecutionPolicyError(
                    "could not read current execution policy"
                ) from error

            LOG.info("execution-policy.008", had_rule_file=previous is not None)
            self._last_notified_contents = None
            try:
                self._rules_path.unlink(missing_ok=True)
                self._reload()
            except Exception as error:
                LOG.error("execution-policy.009", error_type=error_code(error))
                if previous is not None:
                    try:
                        self._replace(previous)
                        self._reload()
                        self._last_notified_contents = previous
                    except Exception as rollback_error:
                        LOG.error("execution-policy.010", error_type=error_code(rollback_error))
                        raise ExecutionPolicyError(
                            "execution-policy removal rollback could not be activated"
                        ) from rollback_error
                if isinstance(error, ExecutionPolicyError):
                    raise
                raise ExecutionPolicyError(
                    "execution policy removal could not be activated"
                ) from error
            LOG.info("execution-policy.011")

    def _replace(self, contents: bytes) -> None:
        try:
            self._rules_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            descriptor, temporary = tempfile.mkstemp(
                prefix=f".{self._rules_path.name}.", dir=self._rules_path.parent,
            )
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(contents)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(temporary, 0o644)
                os.replace(temporary, self._rules_path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        except OSError as error:
            raise ExecutionPolicyError("could not write execution policy") from error

    def _reload(self) -> None:
        # fagenrules --load sends SIGHUP, which also refreshes the trust DB.
        # Repeated policy saves must not queue behind a package database scan.
        # Compile first, then use the public rules-only notification. Neither
        # command's exit status is an acknowledgement of daemon activation.
        for stage, command in (
                ("compile", self._compile_command),
                ("notify", self._reload_command)):
            LOG.info("execution-policy.012", stage=stage)
            self._run_reload_command(command, stage)

    @staticmethod
    def _run_reload_command(command: tuple[str, ...], stage: str) -> None:
        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=15,
                text=True,
            )
        except (OSError, subprocess.SubprocessError) as error:
            LOG.error("execution-policy.013", stage=stage, error_type=error_code(error))
            raise ExecutionPolicyError("could not reload execution policy") from error
        if completed.returncode != 0:
            LOG.error("execution-policy.014", stage=stage, returncode=completed.returncode)
            raise ExecutionPolicyError("could not reload execution policy")
