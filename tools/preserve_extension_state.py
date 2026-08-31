#!/usr/bin/python3
"""Preserve the installer's GNOME extension switch across the required reboot."""

from __future__ import annotations

import argparse
import json
import os
import pwd
import subprocess
import tempfile
from pathlib import Path


DEFAULT_STATE = Path("/var/lib/oh-no-parent-control/extension-state-restore.json")
SCHEMA = "org.gnome.shell"
KEY = "disable-user-extensions"


def _account(uid: int):
    account = pwd.getpwuid(uid)
    home = Path(account.pw_dir).resolve()
    if (uid == 0 or not home.is_absolute() or home == Path("/") or
            home.parent != Path("/home") or not home.is_dir() or
            home.stat().st_uid != uid):
        raise RuntimeError("installer account has an unsafe home directory")
    return account


def _gsettings(account, operation: str, value: str | None = None) -> str:
    environment = {
        "HOME": account.pw_dir,
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LOGNAME": account.pw_name,
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "USER": account.pw_name,
    }
    arguments = ["dbus-run-session", "--", "gsettings", operation, SCHEMA, KEY]
    if value is not None:
        arguments.append(value)
    result = subprocess.run(
        arguments, check=True, text=True, capture_output=True, env=environment,
        user=account.pw_uid, group=account.pw_gid, extra_groups=(),
    )
    return result.stdout.strip()


def _write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(state, output, sort_keys=True)
            output.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def schedule(uid: int, path: Path = DEFAULT_STATE) -> None:
    account = _account(uid)
    value = _gsettings(account, "get")
    if value not in {"true", "false"}:
        raise RuntimeError("GNOME returned an invalid extension switch value")
    _write_state(path, {"version": 1, "uid": uid, "disabled": value == "true"})


def restore(path: Path = DEFAULT_STATE) -> None:
    if not path.exists():
        return
    state = json.loads(path.read_text(encoding="utf-8"))
    if (set(state) != {"version", "uid", "disabled"} or state["version"] != 1 or
            type(state["uid"]) is not int or type(state["disabled"]) is not bool):
        raise RuntimeError("invalid GNOME extension restore state")
    account = _account(state["uid"])
    _gsettings(account, "set", "true" if state["disabled"] else "false")
    path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--schedule-uid", type=int)
    actions.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    if args.restore:
        restore()
    else:
        schedule(args.schedule_uid)


if __name__ == "__main__":
    main()
