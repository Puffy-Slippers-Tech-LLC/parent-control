"""Versioned, retry-safe migrations for application-owned persistent data."""

from __future__ import annotations

import fcntl
import json
import os
import re
import stat
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .config import UINT32_MAX
from .preferences import FORMAT_VERSION, validate_preferences


STATE_DIRECTORY = Path("/var/lib/oh-no-parent-control")
PREFERENCES_DIRECTORY = STATE_DIRECTORY / "preferences"
MIGRATION_MARKER = STATE_DIRECTORY / "migration-in-progress"
MIGRATION_LOCK = STATE_DIRECTORY / "data-migration.lock"
UID_RECORD_RE = re.compile(r"^([1-9][0-9]*)\.json$")

Migration = Callable[[dict[str, Any]], dict[str, Any]]
Validator = Callable[[object], object]

# Once a migration has shipped it is part of the on-disk compatibility
# contract. Never alter or remove an existing entry; append N -> N + 1 here.
def migrate_preferences_v1_to_v2(raw: dict[str, Any]) -> dict[str, Any]:
    """Add the empty wildcard collection without altering prior policy."""
    migrated = dict(raw)
    migrated["version"] = 2
    migrated["apps"] = {
        desktop_id: {**entry, "patterns": []}
        for desktop_id, entry in raw.get("apps", {}).items()
    }
    return migrated


def migrate_preferences_v2_to_v3(raw: dict[str, Any]) -> dict[str, Any]:
    """Record whether an existing saved pattern is a user match-rule override."""
    migrated = dict(raw)
    migrated["version"] = 3
    migrated["apps"] = {
        desktop_id: {
            **entry,
            # A legacy wildcard could only have been typed into the old editor,
            # so retain it as a user choice. Exact legacy entries use defaults.
            "user_saved_match_rule": bool(entry.get("patterns")),
        }
        for desktop_id, entry in raw.get("apps", {}).items()
    }
    return migrated


PREFERENCE_MIGRATIONS: dict[int, Migration] = {
    1: migrate_preferences_v1_to_v2,
    2: migrate_preferences_v2_to_v3,
}


class MigrationError(RuntimeError):
    """Persistent state cannot be migrated without risking data loss."""


def _object_without_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise MigrationError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def migrate_document(raw: object, *, current_version: int,
                     migrations: Mapping[int, Migration],
                     validator: Validator) -> tuple[object, bool]:
    """Migrate one decoded document and validate its current representation."""
    if not isinstance(raw, dict):
        raise MigrationError("state record must be a JSON object")
    version = raw.get("version")
    if type(version) is not int or version < 1:
        raise MigrationError("state record has an invalid schema version")
    if version > current_version:
        raise MigrationError(
            f"state schema {version} is newer than supported schema {current_version}"
        )

    migrated = raw
    changed = False
    while version < current_version:
        migration = migrations.get(version)
        if migration is None:
            raise MigrationError(
                f"no migration is registered from schema {version}"
            )
        try:
            candidate = migration(migrated)
        except MigrationError:
            raise
        except Exception as error:
            raise MigrationError(
                f"migration from schema {version} failed"
            ) from error
        if not isinstance(candidate, dict) or candidate is migrated:
            raise MigrationError(
                f"migration from schema {version} must return a new object"
            )
        next_version = candidate.get("version")
        if type(next_version) is not int or next_version != version + 1:
            raise MigrationError(
                f"migration from schema {version} did not produce schema {version + 1}"
            )
        migrated = candidate
        version = next_version
        changed = True

    try:
        validated = validator(migrated)
    except Exception as error:
        raise MigrationError(
            f"state schema {current_version} failed current validation"
        ) from error
    return validated, changed


def _read_record(path: Path) -> tuple[object, os.stat_result]:
    try:
        file_stat = path.lstat()
    except OSError as error:
        raise MigrationError(f"cannot inspect {path.name}: {error.strerror}") from error
    if not stat.S_ISREG(file_stat.st_mode):
        raise MigrationError(f"preference record is not a regular file: {path.name}")
    if file_stat.st_uid != os.geteuid():
        raise MigrationError(f"preference record has an unexpected owner: {path.name}")
    if stat.S_IMODE(file_stat.st_mode) != 0o600:
        raise MigrationError(f"preference record has unsafe permissions: {path.name}")

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            opened_stat = os.fstat(stream.fileno())
            if (opened_stat.st_dev, opened_stat.st_ino) != (file_stat.st_dev, file_stat.st_ino):
                raise MigrationError(f"preference record changed while opening: {path.name}")
            return json.load(stream, object_pairs_hook=_object_without_duplicate_keys), file_stat
    except MigrationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise MigrationError(f"cannot read preference record {path.name}") from error


def _atomic_write(path: Path, value: object, file_stat: os.stat_result) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.stem}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        os.fchown(descriptor, file_stat.st_uid, file_stat.st_gid)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_descriptor = os.open(path.parent, directory_flags)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except OSError as error:
        raise MigrationError(f"cannot replace preference record {path.name}") from error
    finally:
        temporary.unlink(missing_ok=True)


def migrate_preferences(directory: Path = PREFERENCES_DIRECTORY, *,
                        current_version: int = FORMAT_VERSION,
                        migrations: Mapping[int, Migration] = PREFERENCE_MIGRATIONS,
                        validator: Validator = validate_preferences) -> int:
    """Migrate all preference records, returning the number rewritten."""
    if not directory.exists():
        return 0
    directory_stat = directory.lstat()
    if not stat.S_ISDIR(directory_stat.st_mode):
        raise MigrationError("preferences path is not a directory")
    if directory_stat.st_uid != os.geteuid() or directory_stat.st_mode & 0o022:
        raise MigrationError("preferences directory has unsafe ownership or permissions")

    records = []
    for path in directory.iterdir():
        match = UID_RECORD_RE.fullmatch(path.name)
        if match is None:
            if path.name.endswith(".json"):
                raise MigrationError(f"invalid preference record name: {path.name}")
            continue
        uid = int(match.group(1))
        if uid > UINT32_MAX:
            raise MigrationError(f"preference UID is out of range: {path.name}")
        records.append((uid, path))

    rewritten = 0
    for _uid, path in sorted(records):
        raw, file_stat = _read_record(path)
        migrated, changed = migrate_document(
            raw,
            current_version=current_version,
            migrations=migrations,
            validator=validator,
        )
        if changed:
            _atomic_write(path, migrated, file_stat)
            rewritten += 1
    return rewritten


def migrate_all_state(state_directory: Path = STATE_DIRECTORY) -> int:
    """Run every registered data-family migration under one process lock."""
    try:
        state_stat = state_directory.lstat()
    except FileNotFoundError:
        state_directory.mkdir(parents=True, mode=0o700)
        state_stat = state_directory.lstat()
    if (not stat.S_ISDIR(state_stat.st_mode) or
            state_stat.st_uid != os.geteuid() or state_stat.st_mode & 0o022):
        raise MigrationError("state directory has unsafe ownership or permissions")
    os.chmod(state_directory, 0o700)
    lock_path = state_directory / MIGRATION_LOCK.name
    lock_flags = (os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) |
                  getattr(os, "O_NOFOLLOW", 0))
    try:
        descriptor = os.open(lock_path, lock_flags, 0o600)
    except OSError as error:
        raise MigrationError("cannot open the data-migration lock") from error
    try:
        lock_stat = os.fstat(descriptor)
        if not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_uid != os.geteuid():
            raise MigrationError("data-migration lock has unsafe ownership")
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        return migrate_preferences(state_directory / "preferences")
    finally:
        os.close(descriptor)


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("oh-no-parent-control-migrate-state: must run as root")
    try:
        migrate_all_state()
    except MigrationError as error:
        raise SystemExit(f"oh-no-parent-control-migrate-state: {error}") from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
