"""Activate the packaged child extension for one local account."""

from __future__ import annotations

import ast
import logging
import os
import pwd
import stat
import subprocess
from pathlib import Path

UUID = "oh-no-parent-control@tech.puffyslippers.com"
SCHEMA = "org.gnome.shell"
ENABLED_KEY = "enabled-extensions"
DISABLED_KEY = "disabled-extensions"
DISABLE_ALL_KEY = "disable-user-extensions"
COMMAND_TIMEOUT_SECONDS = 10
LOG = logging.getLogger("oh-no-parent-control")


class ExtensionManager:
    def __init__(
            self,
            installation=Path(
                "/usr/share/gnome-shell/extensions/"
                "oh-no-parent-control@tech.puffyslippers.com"
            ),
            runtime_root=Path("/run/user"),
            *,
            installation_owner=0):
        self.installation = Path(installation)
        self.runtime_root = Path(runtime_root)
        self.installation_owner = installation_owner

    @staticmethod
    def _account(uid):
        account = pwd.getpwuid(uid)
        home = Path(account.pw_dir).resolve()
        if (uid == 0 or not home.is_absolute() or home == Path("/") or
                home.parent != Path("/home")):
            raise RuntimeError("child account has an unsafe home directory")
        return account, home

    def _command(self, account, arguments):
        environment = {
            "HOME": account.pw_dir,
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "LOGNAME": account.pw_name,
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "USER": account.pw_name,
        }
        runtime = self.runtime_root / str(account.pw_uid)
        bus = runtime / "bus"
        try:
            runtime_status = runtime.lstat()
        except FileNotFoundError:
            return ["dbus-run-session", "--", *arguments], environment, "offline"
        if (runtime.is_symlink() or not stat.S_ISDIR(runtime_status.st_mode) or
                runtime_status.st_uid != account.pw_uid):
            raise RuntimeError("child runtime directory is unsafe")
        try:
            bus_status = bus.lstat()
        except FileNotFoundError:
            return ["dbus-run-session", "--", *arguments], environment, "offline"
        if (bus.is_symlink() or not stat.S_ISSOCK(bus_status.st_mode) or
                bus_status.st_uid != account.pw_uid):
            raise RuntimeError("child session bus is unsafe")
        environment.update({
            "DBUS_SESSION_BUS_ADDRESS": f"unix:path={bus}",
            "XDG_RUNTIME_DIR": str(runtime),
        })
        return list(arguments), environment, "live-session"

    def _run_as(self, account, *arguments):
        return self._run_command(account, arguments)

    def _run_command(self, account, arguments, *, require_live=False):
        command, environment, transport = self._command(account, arguments)
        if require_live and transport != "live-session":
            raise RuntimeError("child GNOME session is unavailable")
        operation = arguments[1] if len(arguments) > 1 else "unknown"
        LOG.info(
            "child GNOME command stage=started operation=%s transport=%s",
            operation, transport,
        )
        try:
            result = subprocess.run(
                command, check=True, text=True, capture_output=True,
                env=environment, user=account.pw_uid, group=account.pw_gid,
                extra_groups=(), timeout=COMMAND_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as error:
            LOG.error(
                "child GNOME command outcome=failed operation=%s "
                "transport=%s error_type=%s",
                operation, transport, type(error).__name__,
            )
            raise RuntimeError("child GNOME interface is unavailable") from error
        LOG.info(
            "child GNOME command outcome=accepted operation=%s transport=%s",
            operation, transport,
        )
        return result

    def _session_transport(self, account):
        return self._command(account, ("gsettings",))[2]

    def _shell_is_available(self, account):
        if self._session_transport(account) != "live-session":
            return False
        result = self._run_command(
            account,
            (
                "gdbus", "call", "--session",
                "--dest", "org.freedesktop.DBus",
                "--object-path", "/org/freedesktop/DBus",
                "--method", "org.freedesktop.DBus.NameHasOwner",
                "org.gnome.Shell.Extensions",
            ),
            require_live=True,
        )
        value = result.stdout.strip()
        if value not in {"(true,)", "(false,)"}:
            raise RuntimeError("D-Bus returned an invalid GNOME Shell state")
        return value == "(true,)"

    def _list(self, account, key):
        result = self._run_as(account, "gsettings", "get", SCHEMA, key)
        try:
            value = ast.literal_eval(result.stdout.strip().removeprefix("@as "))
        except (SyntaxError, ValueError) as error:
            raise RuntimeError("GNOME returned an invalid extension list") from error
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise RuntimeError("GNOME returned an invalid extension list")
        return value

    def _boolean(self, account, key):
        result = self._run_as(account, "gsettings", "get", SCHEMA, key)
        value = result.stdout.strip()
        if value not in {"true", "false"}:
            raise RuntimeError("GNOME returned an invalid extension switch")
        return value == "true"

    def _set_list(self, account, key, values):
        self._run_as(account, "gsettings", "set", SCHEMA, key, repr(values))

    def _runtime_uuids(self, account, state):
        result = self._run_command(
            account,
            ("gnome-extensions", "list", f"--{state}", "--quiet"),
            require_live=True,
        )
        return {
            line.strip() for line in result.stdout.splitlines() if line.strip()
        }

    def _runtime_state(self, account):
        configured = UUID in self._runtime_uuids(account, "enabled")
        active = UUID in self._runtime_uuids(account, "active")
        return configured, active

    def _set_offline(self, account, enabled, old_enabled, old_disabled):
        new_enabled = [value for value in old_enabled if value != UUID]
        new_disabled = [value for value in old_disabled if value != UUID]
        if enabled:
            new_enabled.append(UUID)
        writes = (
            ((DISABLED_KEY, new_disabled), (ENABLED_KEY, new_enabled))
            if enabled else
            ((ENABLED_KEY, new_enabled), (DISABLED_KEY, new_disabled))
        )
        for key, values in writes:
            previous = old_enabled if key == ENABLED_KEY else old_disabled
            if values != previous:
                self._set_list(account, key, values)
        if (self._list(account, ENABLED_KEY) != new_enabled or
                self._list(account, DISABLED_KEY) != new_disabled):
            raise RuntimeError("GNOME extension activation verification failed")

    def _set_live(self, account, enabled):
        operation = "enable" if enabled else "disable"
        self._run_command(
            account, ("gnome-extensions", operation, "--quiet", UUID),
            require_live=True,
        )
        configured, active = self._runtime_state(account)
        if configured != enabled or active != enabled:
            raise RuntimeError("GNOME extension runtime verification failed")
        enabled_settings = self._list(account, ENABLED_KEY)
        disabled_settings = self._list(account, DISABLED_KEY)
        if ((UUID in enabled_settings) != enabled or
                (enabled and UUID in disabled_settings)):
            raise RuntimeError("GNOME extension activation verification failed")
        LOG.info(
            "child extension runtime verification outcome=accepted "
            "configured=%s active=%s",
            configured, active,
        )

    def _verify_installation(self):
        try:
            directory_status = self.installation.lstat()
        except FileNotFoundError as error:
            raise RuntimeError("installed extension payload is unavailable") from error
        if (self.installation.is_symlink() or
                not stat.S_ISDIR(directory_status.st_mode) or
                directory_status.st_uid != self.installation_owner):
            raise RuntimeError("installed extension payload is unsafe")
        for name in ("metadata.json", "extension.js"):
            path = self.installation / name
            try:
                file_status = path.lstat()
            except FileNotFoundError as error:
                raise RuntimeError("installed extension payload is unavailable") from error
            if (path.is_symlink() or not stat.S_ISREG(file_status.st_mode) or
                    file_status.st_uid != self.installation_owner):
                raise RuntimeError("installed extension payload is unsafe")

    def set_enabled(self, uid: int, enabled: bool) -> None:
        LOG.info("child extension update stage=started enabled=%s", enabled)
        account, home = self._account(uid)
        if home.is_symlink() or not home.is_dir() or home.stat().st_uid != uid:
            raise RuntimeError("child home directory has unsafe ownership")
        if enabled:
            self._verify_installation()

        old_enabled = self._list(account, ENABLED_KEY)
        old_disabled = self._list(account, DISABLED_KEY)
        if enabled and self._boolean(account, DISABLE_ALL_KEY):
            LOG.error(
                "child extension update outcome=failed enabled=true "
                "reason=user-extensions-disabled"
            )
            raise RuntimeError("GNOME user extensions are disabled")

        shell_available = self._shell_is_available(account)
        old_runtime = self._runtime_state(account) if shell_available else None

        try:
            if shell_available:
                # Use GNOME's supported extension-management interface when a
                # Shell owns it, and confirm that Shell actually activated or
                # deactivated the extension rather than trusting settings only.
                self._set_live(account, enabled)
            else:
                # Persist the desired state for Shell to consume at next login.
                self._set_offline(account, enabled, old_enabled, old_disabled)
        except Exception as error:
            LOG.warning(
                "child extension update stage=rollback enabled=%s error_type=%s",
                enabled, type(error).__name__,
            )
            try:
                self._set_list(account, ENABLED_KEY, old_enabled)
                self._set_list(account, DISABLED_KEY, old_disabled)
                if (self._list(account, ENABLED_KEY) != old_enabled or
                        self._list(account, DISABLED_KEY) != old_disabled):
                    raise RuntimeError("GNOME extension rollback verification failed")
                if (shell_available and self._shell_is_available(account) and
                        self._runtime_state(account) != old_runtime):
                    raise RuntimeError(
                        "GNOME extension runtime rollback verification failed"
                    )
            except Exception as rollback_error:
                LOG.critical(
                    "child extension update outcome=rollback-failed enabled=%s "
                    "error_type=%s",
                    enabled, type(rollback_error).__name__,
                )
                raise RuntimeError(
                    "child GNOME extension rollback could not be verified"
                ) from rollback_error
            raise
        LOG.info("child extension update outcome=accepted enabled=%s", enabled)
