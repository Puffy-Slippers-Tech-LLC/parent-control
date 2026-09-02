"""Mirror Malcontent executable blocklists into the kernel execution policy."""

from __future__ import annotations

import hashlib
import fnmatch
import os
import stat
import subprocess
import tempfile
import threading
from pathlib import Path


class ExecutionPolicyError(RuntimeError):
    """The execution policy could not be generated or activated safely."""


class FapolicydPolicy:
    """Maintain the product-owned fapolicyd deny rules.

    Malcontent filters launchers in GNOME Shell, but callers which open a
    trusted ``.desktop`` file directly bypass that UI check.  fapolicyd's
    execute permission event closes that second launch path.
    """

    def __init__(
            self,
            rules_path: Path = Path(
                "/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules"
            ),
            reload_command=("/usr/sbin/fagenrules", "--load")):
        self._rules_path = rules_path
        self._reload_command = tuple(reload_command)
        self._lock = threading.Lock()

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
            # First, concrete blocks win over all directory allowances.
            for target in sorted(blocked):
                if os.path.dirname(os.path.realpath(target)) == directory:
                    try:
                        lines.append(f"deny_syslog perm=execute uid={uid} : {cls._object_clause(target)}")
                    except FileNotFoundError:
                        pass
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
                elif entry.is_file(follow_symlinks=False) and os.access(entry.path, os.X_OK):
                    if not any(fnmatch.fnmatchcase(entry.name, pattern) for pattern in basenames):
                        if any(character.isspace() for character in entry.path) or "," in entry.path:
                            raise ExecutionPolicyError("existing nonmatching executable cannot be represented")
                        lines.append(f"allow perm=execute uid={uid} : path={entry.path}")
            prefix = directory.rstrip("/") + "/"
            lines.append(f"deny_syslog perm=execute uid={uid} : dir={prefix}")
        return lines

    @classmethod
    def render(cls, filters: dict[int, tuple[str, ...]],
               patterns: dict[int, tuple[str, ...]] | None = None) -> str:
        lines = [
            "# Generated by Oh No! Parent Control. Do not edit.",
        ]
        patterns = patterns or {}
        for uid in sorted(set(filters) | set(patterns)):
            if type(uid) is not int or not 0 < uid <= (1 << 32) - 1:
                raise ExecutionPolicyError("invalid execution-policy UID")
            targets = set(filters.get(uid, ()))
            guarded_directories = {
                pattern.rpartition("/")[0] or "/" for pattern in patterns.get(uid, ())
            }
            # Unguarded concrete targets are ordinary exact denies. Guarded
            # ones are emitted first by _pattern_rules to retain precedence.
            for target in sorted(targets):
                # Flatpak refs are enforced by Malcontent/Flatpak. fapolicyd
                # rules apply only to native executable paths.
                if not target.startswith("/"):
                    continue
                if target.startswith("/") and os.path.dirname(os.path.realpath(target)) in guarded_directories:
                    continue
                try:
                    clause = cls._object_clause(target)
                except FileNotFoundError:
                    # Saved policies intentionally survive uninstalled apps.
                    # A missing object cannot execute and therefore needs no
                    # current kernel rule.
                    continue
                lines.append(
                    f"deny_syslog perm=execute uid={uid} : {clause}"
                )
            lines.extend(cls._pattern_rules(uid, tuple(patterns.get(uid, ())), targets))
        return "\n".join(lines) + "\n"

    def reconcile(self, filters: dict[int, tuple[str, ...]],
                  patterns: dict[int, tuple[str, ...]] | None = None) -> None:
        contents = self.render(filters, patterns)
        with self._lock:
            previous = None
            try:
                previous = self._rules_path.read_bytes()
            except FileNotFoundError:
                pass
            except OSError as error:
                raise ExecutionPolicyError("could not read current execution policy") from error

            if previous == contents.encode("utf-8"):
                return

            self._replace(contents.encode("utf-8"))
            try:
                self._reload()
            except Exception as error:
                try:
                    if previous is None:
                        self._rules_path.unlink(missing_ok=True)
                    else:
                        self._replace(previous)
                    self._reload()
                except Exception as rollback_error:
                    raise ExecutionPolicyError(
                        "execution-policy rollback could not be activated"
                    ) from rollback_error
                if isinstance(error, ExecutionPolicyError):
                    raise
                raise ExecutionPolicyError("execution policy could not be activated") from error

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
        try:
            completed = subprocess.run(
                self._reload_command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=15,
                text=True,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise ExecutionPolicyError("could not reload execution policy") from error
        if completed.returncode != 0:
            raise ExecutionPolicyError("could not reload execution policy")
