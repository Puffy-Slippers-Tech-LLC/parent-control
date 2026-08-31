"""Install and enable the child extension for one local account."""

from __future__ import annotations

import ast
import logging
import os
import pwd
import shutil
import subprocess
import tempfile
from pathlib import Path

UUID = "oh-no-parent-control@tech.puffyslippers.com"
SCHEMA = "org.gnome.shell"
KEY = "enabled-extensions"
LOG = logging.getLogger("oh-no-parent-control")


class ExtensionManager:
    def __init__(self, source=Path("/usr/lib/oh-no-parent-control/child/extension")):
        self.source = Path(source)

    @staticmethod
    def _account(uid):
        account = pwd.getpwuid(uid)
        home = Path(account.pw_dir).resolve()
        if (uid == 0 or not home.is_absolute() or home == Path("/") or
                home.parent != Path("/home")):
            raise RuntimeError("child account has an unsafe home directory")
        return account, home

    @staticmethod
    def _run_as(account, *arguments):
        environment = {
            "HOME": account.pw_dir,
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "LOGNAME": account.pw_name,
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "USER": account.pw_name,
        }
        try:
            return subprocess.run(
                ["dbus-run-session", "--", *arguments], check=True, text=True,
                capture_output=True, env=environment, user=account.pw_uid,
                group=account.pw_gid, extra_groups=(),
            )
        except (OSError, subprocess.SubprocessError) as error:
            detail = " ".join((getattr(error, "stderr", "") or "").split())[:500]
            LOG.error("child settings command failed for uid=%d: %s",
                      account.pw_uid, detail or type(error).__name__)
            raise RuntimeError("child GNOME settings are unavailable") from error

    def _enabled(self, account):
        result = self._run_as(account, "gsettings", "get", SCHEMA, KEY)
        value = ast.literal_eval(result.stdout.strip().removeprefix("@as "))
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise RuntimeError("GNOME returned an invalid extension list")
        return value

    def _set_enabled(self, account, values):
        self._run_as(account, "gsettings", "set", SCHEMA, KEY, repr(values))

    def set_enabled(self, uid: int, enabled: bool) -> None:
        account, home = self._account(uid)
        if home.is_symlink() or home.stat().st_uid != uid:
            raise RuntimeError("child home directory has unsafe ownership")
        base = home
        for component in (".local", "share", "gnome-shell", "extensions"):
            candidate = base / component
            if candidate.is_symlink():
                raise RuntimeError("child extension path contains a symbolic link")
            if candidate.exists():
                if not candidate.is_dir() or candidate.stat().st_uid != uid:
                    raise RuntimeError("child extension path has unsafe ownership")
            elif enabled:
                candidate.mkdir(mode=0o700)
                os.chown(candidate, uid, account.pw_gid)
            base = candidate
        target = base / UUID
        if target.is_symlink():
            raise RuntimeError("child extension path is a symbolic link")
        if enabled:
            if not self.source.is_dir():
                raise RuntimeError("installed extension payload is unavailable")
            temporary = Path(tempfile.mkdtemp(prefix=f".{UUID}.", dir=base))
            try:
                shutil.copytree(self.source, temporary, dirs_exist_ok=True)
                for root, directories, files in os.walk(temporary):
                    os.chown(root, uid, account.pw_gid)
                    for name in directories + files:
                        os.chown(Path(root) / name, uid, account.pw_gid)
                if target.exists():
                    shutil.rmtree(target)
                os.replace(temporary, target)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)
            try:
                values = self._enabled(account)
                if UUID not in values:
                    self._set_enabled(account, [*values, UUID])
            except Exception:
                if target.is_dir():
                    shutil.rmtree(target)
                raise
        else:
            values = self._enabled(account)
            if UUID in values:
                self._set_enabled(account, [value for value in values if value != UUID])
            if target.is_dir():
                shutil.rmtree(target)
