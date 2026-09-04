"""Remove product-derived enforcement before package files disappear."""

from __future__ import annotations

import argparse
import json
import logging
import os
import pwd
import re
import stat
import tempfile
from pathlib import Path

from .config import UINT32_MAX


LOG = logging.getLogger("oh-no-parent-control.uninstall")
PREFERENCES_DIRECTORY = Path("/var/lib/oh-no-parent-control/preferences")
SNAPSHOT_PATH = Path("/var/lib/oh-no-parent-control/uninstall-enforcement.json")
PREFERENCE_NAME = re.compile(r"([1-9][0-9]*)\.json")


class UninstallCleanupError(RuntimeError):
    """Product-derived enforcement could not be completely removed."""


def _validate_snapshot(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != {"version", "accounts"}:
        raise UninstallCleanupError("uninstall snapshot is invalid")
    if value["version"] != 1 or type(value["version"]) is not int:
        raise UninstallCleanupError("uninstall snapshot version is invalid")
    if not isinstance(value["accounts"], list):
        raise UninstallCleanupError("uninstall snapshot accounts are invalid")
    accounts = []
    seen = set()
    for account in value["accounts"]:
        if not isinstance(account, dict) or set(account) != {
                "uid", "extension_enabled", "limit_type", "daily_limit",
                "active_extension", "app_filter"}:
            raise UninstallCleanupError("uninstall snapshot account is invalid")
        uid = account["uid"]
        if type(uid) is not int or not 0 < uid <= UINT32_MAX or uid in seen:
            raise UninstallCleanupError("uninstall snapshot UID is invalid")
        seen.add(uid)
        if type(account["extension_enabled"]) is not bool:
            raise UninstallCleanupError("uninstall snapshot extension state is invalid")
        if (type(account["limit_type"]) is not int or
                not 0 <= account["limit_type"] <= UINT32_MAX or
                type(account["daily_limit"]) is not int or
                not 0 <= account["daily_limit"] <= UINT32_MAX):
            raise UninstallCleanupError("uninstall snapshot time state is invalid")
        active = account["active_extension"]
        if (not isinstance(active, list) or len(active) != 2 or
                type(active[0]) is not int or not 0 <= active[0] < 1 << 64 or
                type(active[1]) is not int or not 0 <= active[1] <= UINT32_MAX):
            raise UninstallCleanupError("uninstall snapshot grant is invalid")
        app_filter = account["app_filter"]
        if (not isinstance(app_filter, list) or len(app_filter) != 2 or
                type(app_filter[0]) is not bool or
                not isinstance(app_filter[1], list) or
                any(not isinstance(target, str) for target in app_filter[1])):
            raise UninstallCleanupError("uninstall snapshot app filter is invalid")
        accounts.append({
            **account,
            "active_extension": tuple(active),
            "app_filter": (app_filter[0], tuple(app_filter[1])),
        })
    return {"version": 1, "accounts": accounts}


def _read_snapshot(path: Path, *, required_owner: int = 0) -> dict | None:
    path = Path(path)
    try:
        status = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise UninstallCleanupError("could not inspect uninstall snapshot") from error
    if (path.is_symlink() or not stat.S_ISREG(status.st_mode) or
            status.st_uid != required_owner or
            stat.S_IMODE(status.st_mode) != 0o600):
        raise UninstallCleanupError("uninstall snapshot ownership is unsafe")
    try:
        return _validate_snapshot(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise UninstallCleanupError("could not read uninstall snapshot") from error


def _write_snapshot(path: Path, value: dict, *, required_owner: int = 0) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    parent_status = path.parent.lstat()
    if (path.parent.is_symlink() or not stat.S_ISDIR(parent_status.st_mode) or
            parent_status.st_uid != required_owner):
        raise UninstallCleanupError("uninstall snapshot directory is unsafe")
    os.chmod(path.parent, 0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(value, output, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except OSError as error:
        raise UninstallCleanupError("could not write uninstall snapshot") from error
    finally:
        temporary.unlink(missing_ok=True)


def managed_uids(
        directory: Path = PREFERENCES_DIRECTORY, *, required_owner: int = 0,
        account_lookup=pwd.getpwuid) -> tuple[int, ...]:
    """Return extant account UIDs named by securely owned preference records."""
    directory = Path(directory)
    try:
        directory_status = directory.lstat()
    except FileNotFoundError:
        LOG.info("uninstall discovery outcome=no-preference-directory")
        return ()
    except OSError as error:
        raise UninstallCleanupError("could not inspect preference directory") from error
    if (directory.is_symlink() or not stat.S_ISDIR(directory_status.st_mode) or
            directory_status.st_uid != required_owner or
            stat.S_IMODE(directory_status.st_mode) != 0o700):
        raise UninstallCleanupError("preference directory ownership is unsafe")

    uids = []
    unavailable = 0
    for path in directory.iterdir():
        match = PREFERENCE_NAME.fullmatch(path.name)
        if match is None:
            continue
        uid = int(match.group(1))
        if uid > UINT32_MAX:
            raise UninstallCleanupError("preference record UID is invalid")
        try:
            record_status = path.lstat()
        except OSError as error:
            raise UninstallCleanupError("could not inspect preference record") from error
        if (path.is_symlink() or not stat.S_ISREG(record_status.st_mode) or
                record_status.st_uid != required_owner or
                stat.S_IMODE(record_status.st_mode) != 0o600):
            raise UninstallCleanupError("preference record ownership is unsafe")
        try:
            account_lookup(uid)
        except KeyError:
            unavailable += 1
            continue
        uids.append(uid)
    result = tuple(sorted(set(uids)))
    LOG.info(
        "uninstall discovery outcome=accepted managed_account_count=%d "
        "unavailable_record_count=%d",
        len(result), unavailable,
    )
    return result


class UninstallCleaner:
    """Best-effort all targets, but reject an unverified final state."""

    def __init__(self, accounts, extensions, execution_policy, preferences,
                 snapshot_path: Path = SNAPSHOT_PATH, *, snapshot_owner: int = 0):
        self._accounts = accounts
        self._extensions = extensions
        self._execution_policy = execution_policy
        self._preferences = preferences
        self._snapshot_path = Path(snapshot_path)
        self._snapshot_owner = snapshot_owner

    def _capture(self, uids: tuple[int, ...]) -> dict:
        accounts = []
        for uid in uids:
            preferences = self._preferences.load(uid)
            allowlist, targets = self._accounts.get_filter(uid)
            active_extension = self._accounts.get_extension(uid)
            accounts.append({
                "uid": uid,
                "extension_enabled": preferences["parent_control_enabled"],
                "limit_type": self._accounts.get_limit_type(uid),
                "daily_limit": self._accounts.get_daily_limit(uid),
                "active_extension": list(active_extension),
                "app_filter": [allowlist, list(targets)],
            })
        return _validate_snapshot({"version": 1, "accounts": accounts})

    def _set_time_state(self, uid: int, limit_type: int, daily_limit: int,
                        active_extension) -> None:
        # Malcontent observes each property write separately. Never publish an
        # active extension with LimitType=0, even briefly or after a failed write.
        self._accounts.set_extension(uid, (0, 0))
        if self._accounts.get_extension(uid) != (0, 0):
            raise UninstallCleanupError("grant clearing verification failed")
        self._accounts.set_daily_limit(uid, daily_limit)
        self._accounts.set_limit_type(uid, limit_type)
        if self._accounts.get_limit_type(uid) != limit_type:
            raise UninstallCleanupError("limit write verification failed")
        if any(active_extension):
            if limit_type == 0:
                raise UninstallCleanupError("cannot restore a grant without a limit")
            self._accounts.set_extension(uid, active_extension)

    def _clear_account(self, uid: int) -> list[Exception]:
        errors = []
        operations = (
            ("extension", lambda: self._extensions.remove(uid)),
            ("time-state", lambda: self._set_time_state(uid, 0, 0, (0, 0))),
            ("app-filter", lambda: self._accounts.set_filter(uid, (False, ()))),
        )
        for operation, callback in operations:
            try:
                callback()
            except Exception as error:
                LOG.error(
                    "uninstall account cleanup outcome=failed operation=%s "
                    "target=[Managed user] error_type=%s",
                    operation, type(error).__name__,
                )
                errors.append(error)

        checks = (
            ("limit-type", lambda: self._accounts.get_limit_type(uid), 0),
            ("daily-limit", lambda: self._accounts.get_daily_limit(uid), 0),
            ("active-extension", lambda: self._accounts.get_extension(uid), (0, 0)),
            ("app-filter", lambda: self._accounts.get_filter(uid), (False, ())),
        )
        for operation, callback, expected in checks:
            try:
                if callback() != expected:
                    raise UninstallCleanupError(
                        f"{operation} cleanup verification failed"
                    )
            except Exception as error:
                LOG.error(
                    "uninstall account verification outcome=failed operation=%s "
                    "target=[Managed user] error_type=%s",
                    operation, type(error).__name__,
                )
                errors.append(error)
        if not errors:
            LOG.info("uninstall account cleanup outcome=accepted target=[Managed user]")
        return errors

    def remove(self, uids: tuple[int, ...]) -> None:
        if os.geteuid() != 0:
            raise UninstallCleanupError("uninstall cleanup must run as root")
        LOG.info(
            "uninstall enforcement cleanup stage=started managed_account_count=%d",
            len(uids),
        )
        snapshot = _read_snapshot(
            self._snapshot_path, required_owner=self._snapshot_owner,
        )
        if snapshot is None:
            try:
                snapshot = self._capture(uids)
                _write_snapshot(
                    self._snapshot_path, snapshot,
                    required_owner=self._snapshot_owner,
                )
            except Exception as error:
                LOG.critical(
                    "uninstall snapshot outcome=failed error_type=%s",
                    type(error).__name__,
                )
                raise UninstallCleanupError(
                    "could not snapshot derived enforcement"
                ) from error
        snapshot_uids = tuple(account["uid"] for account in snapshot["accounts"])
        errors = []
        for uid in snapshot_uids:
            errors.extend(self._clear_account(uid))
        try:
            self._execution_policy.remove()
        except Exception as error:
            LOG.error(
                "uninstall execution-policy cleanup outcome=failed error_type=%s",
                type(error).__name__,
            )
            errors.append(error)
        if errors:
            LOG.critical(
                "uninstall enforcement cleanup outcome=failed failure_count=%d",
                len(errors),
            )
            raise UninstallCleanupError(
                "product-derived enforcement cleanup could not be verified"
            )
        LOG.info("uninstall enforcement cleanup outcome=accepted")

    def restore(self) -> None:
        if os.geteuid() != 0:
            raise UninstallCleanupError("uninstall cleanup must run as root")
        snapshot = _read_snapshot(
            self._snapshot_path, required_owner=self._snapshot_owner,
        )
        if snapshot is None:
            LOG.info("uninstall rollback outcome=no-snapshot")
            return
        LOG.warning(
            "uninstall rollback stage=started managed_account_count=%d",
            len(snapshot["accounts"]),
        )
        errors = []
        for state in snapshot["accounts"]:
            uid = state["uid"]
            operations = (
                ("time-state", lambda: self._set_time_state(
                    uid, state["limit_type"], state["daily_limit"],
                    state["active_extension"])),
                ("app-filter", lambda: self._accounts.set_filter(
                    uid, state["app_filter"])),
                ("extension", lambda: self._extensions.set_enabled(
                    uid, state["extension_enabled"])),
            )
            for operation, callback in operations:
                try:
                    callback()
                except Exception as error:
                    LOG.error(
                        "uninstall rollback outcome=failed operation=%s "
                        "target=[Managed user] error_type=%s",
                        operation, type(error).__name__,
                    )
                    errors.append(error)
            checks = (
                ("limit-type", lambda: self._accounts.get_limit_type(uid),
                 state["limit_type"]),
                ("daily-limit", lambda: self._accounts.get_daily_limit(uid),
                 state["daily_limit"]),
                ("active-extension", lambda: self._accounts.get_extension(uid),
                 state["active_extension"]),
                ("app-filter", lambda: self._accounts.get_filter(uid),
                 state["app_filter"]),
            )
            for operation, callback, expected in checks:
                try:
                    if callback() != expected:
                        raise UninstallCleanupError(
                            f"{operation} rollback verification failed"
                        )
                except Exception as error:
                    LOG.error(
                        "uninstall rollback verification outcome=failed "
                        "operation=%s target=[Managed user] error_type=%s",
                        operation, type(error).__name__,
                    )
                    errors.append(error)
        try:
            self._accounts.sync_execution_policy()
        except Exception as error:
            LOG.error(
                "uninstall rollback outcome=failed operation=execution-policy "
                "error_type=%s", type(error).__name__,
            )
            errors.append(error)
        if errors:
            raise UninstallCleanupError("uninstall rollback could not be verified")
        self._snapshot_path.unlink()
        LOG.info("uninstall rollback outcome=accepted")


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--remove", action="store_true")
    action.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="oh-no-parent-control-uninstall: %(levelname)s: %(message)s",
    )
    if os.geteuid() != 0:
        raise SystemExit("oh-no-parent-control-uninstall: must run as root")

    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio

    from .adapters import AccountsService
    from .execution_policy import FapolicydPolicy
    from .extension_manager import ExtensionManager
    from .preferences import PreferenceStore

    connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    preferences = PreferenceStore()
    execution_policy = FapolicydPolicy()
    accounts = AccountsService(
        connection,
        execution_policy if args.restore else None,
        preferences if args.restore else None,
    )
    cleaner = UninstallCleaner(
        accounts, ExtensionManager(), execution_policy, preferences,
    )
    if args.restore:
        cleaner.restore()
    else:
        cleaner.remove(managed_uids())
    return 0
