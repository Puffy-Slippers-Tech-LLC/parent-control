"""Activate the packaged child extension for one local account."""

from __future__ import annotations

import ast
from common.oh_no_parent_control_ui.diagnostic_events import get_logger, error_code, record_exception
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
LOG = get_logger("extension-manager")


def _command_diagnostics(arguments):
    # Only fixed executable/key categories cross the privacy boundary. Never
    # include argv values: extension lists may contain private identifiers.
    tool = arguments[0] if arguments else "other"
    key = (arguments[3] if tool == "gsettings" and len(arguments) > 3
           else "none")
    return {
        "tool": tool if tool in {"gsettings", "gnome-extensions", "gdbus"} else "other",
        "key": key if key in {ENABLED_KEY, DISABLED_KEY, DISABLE_ALL_KEY, "none"} else "other",
    }


def _stderr_reason(value):
    # Inspect subprocess text transiently; emit a closed category only. Force
    # the command locale below so upstream warning markers are predictable.
    if not isinstance(value, str) or not value.strip():
        return None
    if "failed to commit changes to dconf" in value:
        if "org.freedesktop.DBus.Error.ServiceUnknown" in value:
            return "dconf-service-missing"
        if "org.freedesktop.DBus.Error.Spawn" in value:
            return "dconf-service-start-failed"
        if "Permission denied" in value or "org.freedesktop.DBus.Error.AccessDenied" in value:
            return "dconf-access-denied"
        if "Read-only file system" in value:
            return "dconf-read-only"
        return "dconf-commit-failed"
    if "Using the 'memory' GSettings backend" in value:
        return "settings-memory-backend"
    if "The key is not writable" in value:
        return "settings-not-writable"
    if "No such schema" in value:
        return "settings-schema-missing"
    if "dconf will not work properly" in value:
        return "dconf-runtime-unavailable"
    return "other"


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
            "LC_MESSAGES": "C",
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
        LOG.info("extension-manager.001", operation=operation, transport=transport)
        context = _command_diagnostics(arguments)
        LOG.info("extension-manager.command", operation=operation, transport=transport,
                 tool=context["tool"], key=context["key"])
        try:
            result = subprocess.run(
                command, check=True, text=True, capture_output=True,
                env=environment, user=account.pw_uid, group=account.pw_gid,
                extra_groups=(), timeout=COMMAND_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as error:
            self._log_stderr(getattr(error, "stderr", None), operation, transport, context)
            LOG.error(
                "extension-manager.002",
                operation=operation,
                transport=transport,
                error_type=error_code(error),
            )
            raise RuntimeError("child GNOME interface is unavailable") from error
        self._log_stderr(result.stderr, operation, transport, context)
        LOG.info("extension-manager.003", operation=operation, transport=transport)
        return result

    @staticmethod
    def _log_stderr(value, operation, transport, context):
        # dbus-run-session can return the child's successful status even when
        # its daemon failed. Preserve that independent cause alongside dconf's
        # commit warning. Match fixed C-locale markers, never export raw stderr.
        if isinstance(value, str) and "dbus-run-session: dbus-daemon exited with code" in value:
            reason = "startup-failed"
            if "Cannot acquire AVC netlink fd: Address family not supported by protocol" in value:
                reason = "selinux-netlink-family-unavailable"
            LOG.error("extension-manager.session-bus-failure", operation=operation,
                      transport=transport, reason=reason, tool=context["tool"], key=context["key"])
        reason = _stderr_reason(value)
        if reason is not None:
            LOG.warning("extension-manager.command-warning", operation=operation,
                        transport=transport, reason=reason, tool=context["tool"], key=context["key"])

    @staticmethod
    def _verify_setting(key, matches, stage):
        if matches:
            LOG.info("extension-manager.setting-verification", key=key, matches=matches, stage=stage)
        else:
            LOG.error("extension-manager.setting-verification", key=key, matches=matches, stage=stage)
        return matches

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
                # The Extensions service is activated on demand by the CLI
                # and proxies to Shell. Its absence does not mean the desktop
                # is offline; probe the owner of the actual Shell instead.
                "org.gnome.Shell",
            ),
            require_live=True,
        )
        value = result.stdout.strip()
        if value not in {"(true,)", "(false,)"}:
            LOG.error("extension-manager.invalid-state", source="shell-owner")
            raise RuntimeError("D-Bus returned an invalid GNOME Shell state")
        LOG.info("extension-manager.004", available=value == "(true,)")
        return value == "(true,)"

    def _list(self, account, key):
        result = self._run_as(account, "gsettings", "get", SCHEMA, key)
        try:
            value = ast.literal_eval(result.stdout.strip().removeprefix("@as "))
        except (SyntaxError, ValueError) as error:
            LOG.error("extension-manager.invalid-state", source=key)
            raise RuntimeError("GNOME returned an invalid extension list") from error
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            LOG.error("extension-manager.invalid-state", source=key)
            raise RuntimeError("GNOME returned an invalid extension list")
        return value

    def _boolean(self, account, key):
        result = self._run_as(account, "gsettings", "get", SCHEMA, key)
        value = result.stdout.strip()
        if value not in {"true", "false"}:
            LOG.error("extension-manager.invalid-state", source=key)
            raise RuntimeError("GNOME returned an invalid extension switch")
        return value == "true"

    def _set_list(self, account, key, values):
        self._run_as(account, "gsettings", "set", SCHEMA, key, repr(values))

    def _set_boolean(self, account, key, value):
        self._run_as(account, "gsettings", "set", SCHEMA, key,
                     "true" if value else "false")
        if not self._verify_setting(key, self._boolean(account, key) == value, "switch"):
            raise RuntimeError("GNOME extension switch verification failed")

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
        if (not self._verify_setting(
                ENABLED_KEY, self._list(account, ENABLED_KEY) == new_enabled, "offline") or
                not self._verify_setting(
                    DISABLED_KEY, self._list(account, DISABLED_KEY) == new_disabled, "offline")):
            raise RuntimeError("GNOME extension activation verification failed")

    def _set_live(self, account, enabled):
        operation = "enable" if enabled else "disable"
        self._run_command(
            account, ("gnome-extensions", operation, "--quiet", UUID),
            require_live=True,
        )
        configured, active = self._runtime_state(account)
        LOG.info("extension-manager.runtime-verification", expected=enabled,
                 configured=configured, active=active)
        if configured != enabled or active != enabled:
            raise RuntimeError("GNOME extension runtime verification failed")
        enabled_settings = self._list(account, ENABLED_KEY)
        disabled_settings = self._list(account, DISABLED_KEY)
        if (not self._verify_setting(
                ENABLED_KEY, (UUID in enabled_settings) == enabled, "live") or
                not self._verify_setting(
                    DISABLED_KEY, not enabled or UUID not in disabled_settings, "live")):
            raise RuntimeError("GNOME extension activation verification failed")
        LOG.info("extension-manager.005", configured=configured, active=active)

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

    def set_enabled(self, uid: int, enabled: bool, *,
                    recover_global_switch: bool = False) -> None:
        LOG.info("extension-manager.006", enabled=enabled)
        account, home = self._account(uid)
        if home.is_symlink() or not home.is_dir() or home.stat().st_uid != uid:
            raise RuntimeError("child home directory has unsafe ownership")
        if enabled:
            self._verify_installation()

        old_enabled = self._list(account, ENABLED_KEY)
        old_disabled = self._list(account, DISABLED_KEY)
        restore_switch = enabled and self._boolean(account, DISABLE_ALL_KEY)
        if restore_switch and not recover_global_switch:
            LOG.error("extension-manager.007")
            raise RuntimeError("GNOME user extensions are disabled")

        shell_available = self._shell_is_available(account)
        LOG.info("extension-manager.activation-context", shell_available=shell_available,
                 recover_global_switch=recover_global_switch, switch_recovery_needed=bool(restore_switch))
        old_runtime = self._runtime_state(account) if shell_available else None

        try:
            if restore_switch:
                # GNOME can set this switch after a failed session startup.
                # Startup reasserts an already saved enablement, without an
                # outer preference transaction that could subsequently fail.
                # The parent-enabled enforcement extension requires it off;
                # preserve individual extension choices and verify recovery.
                LOG.info("extension-manager.008")
                self._set_boolean(account, DISABLE_ALL_KEY, False)
            if shell_available:
                # Use GNOME's supported extension-management interface when a
                # Shell owns it, and confirm that Shell actually activated or
                # deactivated the extension rather than trusting settings only.
                self._set_live(account, enabled)
            else:
                # Persist the desired state for Shell to consume at next login.
                self._set_offline(account, enabled, old_enabled, old_disabled)
        except Exception as error:
            # Preserve the shipped failure location before the broker converts
            # it to BackendFailure; never format private exception details.
            record_exception(error)
            LOG.warning("extension-manager.009", enabled=enabled, error_type=error_code(error))
            try:
                try:
                    if restore_switch:
                        self._set_boolean(account, DISABLE_ALL_KEY, True)
                finally:
                    self._set_list(account, ENABLED_KEY, old_enabled)
                    self._set_list(account, DISABLED_KEY, old_disabled)
                if (not self._verify_setting(
                        ENABLED_KEY, self._list(account, ENABLED_KEY) == old_enabled, "rollback") or
                        not self._verify_setting(
                            DISABLED_KEY, self._list(account, DISABLED_KEY) == old_disabled, "rollback")):
                    raise RuntimeError("GNOME extension rollback verification failed")
                if (shell_available and self._shell_is_available(account) and
                        self._runtime_state(account) != old_runtime):
                    raise RuntimeError(
                        "GNOME extension runtime rollback verification failed"
                    )
            except Exception as rollback_error:
                record_exception(rollback_error)
                LOG.critical(
                    "extension-manager.010",
                    enabled=enabled,
                    error_type=error_code(rollback_error),
                )
                raise RuntimeError(
                    "child GNOME extension rollback could not be verified"
                ) from rollback_error
            raise
        if restore_switch:
            LOG.info("extension-manager.011")
        LOG.info("extension-manager.012", enabled=enabled)

    def remove(self, uid: int) -> None:
        """Disable the product extension and remove its per-user list entries."""
        LOG.info("extension-manager.013")
        account, home = self._account(uid)
        if home.is_symlink() or not home.is_dir() or home.stat().st_uid != uid:
            raise RuntimeError("child home directory has unsafe ownership")

        shell_available = self._shell_is_available(account)
        if shell_available:
            configured, active = self._runtime_state(account)
            if configured or active:
                self._set_live(account, False)

        enabled = self._list(account, ENABLED_KEY)
        disabled = self._list(account, DISABLED_KEY)
        desired_enabled = [value for value in enabled if value != UUID]
        desired_disabled = [value for value in disabled if value != UUID]
        if desired_enabled != enabled:
            self._set_list(account, ENABLED_KEY, desired_enabled)
        if desired_disabled != disabled:
            self._set_list(account, DISABLED_KEY, desired_disabled)
        if (self._list(account, ENABLED_KEY) != desired_enabled or
                self._list(account, DISABLED_KEY) != desired_disabled):
            raise RuntimeError("GNOME extension removal verification failed")
        if shell_available and self._runtime_state(account) != (False, False):
            raise RuntimeError("GNOME extension runtime removal verification failed")
        LOG.info("extension-manager.014")
