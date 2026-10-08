"""Mirror Malcontent executable blocklists into the kernel execution policy."""

from __future__ import annotations

import hashlib
import fnmatch
import json
from common.oh_no_parent_control_ui.diagnostic_events import get_logger, error_code, record_exception
import os
import platform
import stat
import subprocess
import tempfile
import threading
from pathlib import Path
from .dependency_diagnostics import notification_error_reason

LOG = get_logger("execution-policy")

# fapolicyd classifies ELF objects itself, including PIE runtimes, rather than
# relying on filename extensions or libmagic's AppImage classification. Include
# shared-library and malformed ELF classifications so those cannot escape the
# read guard. Ordinary documents in a wildcard directory remain readable.
ELF_OBJECT_TYPES = "application/x-executable,application/x-sharedlib,application/x-bad-elf"


class ExecutionPolicyError(RuntimeError):
    """The execution policy could not be generated or activated safely."""


def _read_policy_mode_file(path: Path, *, mode: int, limit=4096) -> bytes | None:
    """Read a bounded root-owned mode record without accepting substitutions."""
    try:
        for ancestor in reversed(path.parents):
            info = ancestor.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                raise ExecutionPolicyError('original execution policy has unsafe ancestry')
        # Inspect the opened object before reading it. A substituted FIFO must
        # fail the regular-file check without waiting for a writer at open().
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise ExecutionPolicyError('could not read original execution policy mode') from error
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != mode or info.st_size > limit):
            raise ExecutionPolicyError('original execution policy mode was substituted')
        value = stream.read(limit + 1)
        if len(value) > limit:
            raise ExecutionPolicyError('original execution policy mode exceeds limit')
        return value


def originally_permissive_policy() -> bool:
    """Select early wildcard groups only from the committed Fedora receipt.

    No receipt preserves the usual deny-only early layer, including Ubuntu.
    The transaction must have proved an absent or inactive stock dependency
    policy and installed its exact owned fallback before committing this mode.
    """
    raw = _read_policy_mode_file(
        Path('/var/lib/oh-no-parent-control/fedora-execution-policy.json'), mode=0o600)
    if raw is None:
        return False
    try:
        record = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExecutionPolicyError('original execution policy mode is invalid') from error
    if (not isinstance(record, dict) or set(record) != {
            'purpose', 'basis', 'active', 'enabled', 'permissive'} or
            record['purpose'] != 'onpc-fedora-original-execution-policy-v1' or
            record['basis'] not in ('absent', 'dependency', 'preserve') or
            any(type(record[key]) is not bool for key in ('active', 'enabled', 'permissive'))):
        raise ExecutionPolicyError('original execution policy mode is invalid')
    if ((record['basis'] != 'preserve' and (record['active'] or record['enabled']))
            or (record['permissive'] and record['basis'] == 'preserve')):
        raise ExecutionPolicyError('original execution policy mode conflicts with enforced policy')
    if not record['permissive']:
        return False
    release = platform.freedesktop_os_release()
    if (release.get('ID'), release.get('VERSION_ID'), release.get('VARIANT_ID')) != (
            'fedora', '44', 'workstation'):
        raise ExecutionPolicyError('original execution policy mode belongs to another distribution')
    fallback = _read_policy_mode_file(
        Path('/etc/fapolicyd/rules.d/02-oh-no-parent-control-original-allow.rules'), mode=0o644)
    witness = _read_policy_mode_file(
        Path('/var/lib/oh-no-parent-control/installed-fapolicyd-original-policy'), mode=0o600)
    payload = _read_policy_mode_file(
        Path('/usr/share/oh-no-parent-control/99-oh-no-parent-control-allow.rules'), mode=0o644)
    if fallback is None or fallback != witness or fallback != payload:
        raise ExecutionPolicyError('original execution policy fallback is not owned')
    return True


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
            tolerate_rule_errors=False, early_pattern_guards=False):
        self._rules_path = rules_path
        # Exact child denials must precede distribution-wide trusted-file
        # allowances. Full wildcard groups can move early only for a proven
        # originally unrestricted policy; otherwise their exceptions remain
        # behind administrator/distribution language and library denials.
        self._early_rules_path = rules_path.with_name('01-oh-no-parent-control-deny.rules')
        self._early_pattern_guards = early_pattern_guards
        self._reload_command = tuple(reload_command)
        self._compile_command = tuple(compile_command)
        self._lock = threading.Lock()
        # Disk equality alone cannot establish even successful notification:
        # an earlier process or failed rollback may have left stale live rules.
        # This is only a command-success cache, not a daemon acknowledgement.
        self._last_notified_contents: tuple[bytes | None, bytes | None] | None = None
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
        self._render_layers(filters, patterns,
                            issues=[] if self._tolerate_rule_errors else None,
                            early_pattern_guards=self._early_pattern_guards)

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
        return cls._render_layers(filters, patterns, issues=issues)[1]

    @classmethod
    def _render_layers(cls, filters, patterns=None, *, issues=None, early_pattern_guards=False):
        lines = [
            "# Generated by Oh No! Parent Control. Do not edit.",
        ]
        early = list(lines)
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
                denials = [f"deny_syslog perm=execute uid={uid} : {clause}",
                           f"deny_syslog perm=open uid={uid} : {clause}"]
                early.extend(denials)
                lines.extend(denials)
            grouped: dict[str, list[str]] = {}
            for pattern in patterns.get(uid, ()):
                grouped.setdefault(pattern.rpartition("/")[0] or "/", []).append(pattern)
            # A directory guard and its exceptions are indivisible. Never keep
            # partial allowances or a blanket denial from a failed group.
            # Specific guards precede enclosing-directory allowances.
            for directory in sorted(grouped, key=lambda path: (-path.count("/"), path)):
                group = tuple(grouped[directory])
                try:
                    rules = cls._pattern_rules(uid, group, targets)
                    lines.extend(rules)
                    if early_pattern_guards:
                        early.extend(rules)
                except (ExecutionPolicyError, OSError):
                    if issues is None:
                        raise
                    issues.extend((uid, "pattern", pattern) for pattern in group)
        return "\n".join(early) + "\n", "\n".join(lines) + "\n"

    def _read_layers(self):
        contents = []
        for path in (self._early_rules_path, self._rules_path):
            try:
                if path.is_symlink():
                    raise ExecutionPolicyError('execution policy path was substituted')
                contents.append(path.read_bytes())
            except FileNotFoundError:
                contents.append(None)
            except OSError as error:
                raise ExecutionPolicyError('could not read current execution policy') from error
        if contents[0] is not None and not contents[0].startswith(
                b'# Generated by Oh No! Parent Control. Do not edit.\n'):
            raise ExecutionPolicyError('early execution policy path is not product-owned')
        return tuple(contents)

    def _write_layers(self, contents):
        for path, data in zip((self._early_rules_path, self._rules_path), contents):
            if data is None:
                path.unlink(missing_ok=True)
            else:
                self._replace(data, path=path)

    def reconcile(self, filters: dict[int, tuple[str, ...]],
                  patterns: dict[int, tuple[str, ...]] | None = None) -> None:
        LOG.info("execution-policy.001", account_count=len(filters))
        with self._lock:
            issues = [] if self._tolerate_rule_errors else None
            contents = tuple(value.encode('utf-8') for value in
                             self._render_layers(filters, patterns, issues=issues,
                                                 early_pattern_guards=self._early_pattern_guards))
            previous = self._read_layers()

            if previous == contents and self._last_notified_contents == contents:
                self._record_rule_issues(issues)
                LOG.info("execution-policy.002")
                return

            self._last_notified_contents = None
            LOG.info("execution-policy.003")
            try:
                self._write_layers(contents)
                LOG.info("execution-policy.004")
                self._reload()
            except Exception as error:
                LOG.error("execution-policy.005", error_type=error_code(error))
                record_exception(error)
                try:
                    self._write_layers(previous)
                    self._reload()
                    self._last_notified_contents = previous
                except Exception as rollback_error:
                    LOG.error("execution-policy.006", error_type=error_code(rollback_error))
                    record_exception(rollback_error)
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
            previous = self._read_layers()

            LOG.info("execution-policy.008", had_rule_file=any(value is not None for value in previous))
            self._last_notified_contents = None
            try:
                self._write_layers((None, None))
                self._reload()
            except Exception as error:
                LOG.error("execution-policy.009", error_type=error_code(error))
                record_exception(error)
                if any(value is not None for value in previous):
                    try:
                        self._write_layers(previous)
                        self._reload()
                        self._last_notified_contents = previous
                    except Exception as rollback_error:
                        LOG.error("execution-policy.010", error_type=error_code(rollback_error))
                        record_exception(rollback_error)
                        raise ExecutionPolicyError(
                            "execution-policy removal rollback could not be activated"
                        ) from rollback_error
                if isinstance(error, ExecutionPolicyError):
                    raise
                raise ExecutionPolicyError(
                    "execution policy removal could not be activated"
                ) from error
            LOG.info("execution-policy.011")

    def _replace(self, contents: bytes, *, path: Path | None = None) -> None:
        path = self._rules_path if path is None else path
        try:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            descriptor, temporary = tempfile.mkstemp(
                prefix=f".{path.name}.", dir=path.parent,
            )
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(contents)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(temporary, 0o644)
                os.replace(temporary, path)
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
                env={**os.environ, "LC_ALL": "C"},
            )
        except (OSError, subprocess.SubprocessError) as error:
            LOG.error("execution-policy.013", stage=stage, error_type=error_code(error))
            raise ExecutionPolicyError("could not reload execution policy") from error
        if completed.returncode != 0:
            LOG.error("execution-policy.014", stage=stage, returncode=completed.returncode)
            LOG.error("execution-policy.command-failure", stage=stage,
                      reason=notification_error_reason(getattr(completed, "stderr", None))
                      if stage == "notify" else "other")
            raise ExecutionPolicyError("could not reload execution policy")
