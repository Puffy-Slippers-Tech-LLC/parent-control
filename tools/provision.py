#!/usr/bin/python3
"""Provision immutable UIDs and the account-specific system-bus policy."""

import argparse
import grp
import json
import os
import pwd
import subprocess
import sys
import tempfile
from pathlib import Path

ADMIN_GROUPS = {"sudo", "adm"}


def fail(message):
    raise SystemExit(f"provision: {message}")


def account(name, role):
    try:
        entry = pwd.getpwnam(name)
    except KeyError:
        fail(f"{role} account does not exist: {name}")
    if entry.pw_uid == 0:
        fail(f"{role} account must not be root")
    memberships = {
        group.gr_name for group in grp.getgrall()
        if entry.pw_name in group.gr_mem or group.gr_gid == entry.pw_gid
    }
    forbidden = memberships & ADMIN_GROUPS
    if forbidden:
        fail(f"{role} account is administrative ({', '.join(sorted(forbidden))})")
    return entry


def atomic_write(path, contents, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.chown(temporary, 0, 0)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kiosk-user", required=True)
    parser.add_argument("--child-user", required=True)
    parser.add_argument("--prefix", default="/")
    parser.add_argument("--confinement-verified", action="store_true",
                        help="attest that the mandatory target-VM confinement gate passed")
    args = parser.parse_args()
    if os.geteuid() != 0:
        fail("must run as root")
    if not args.confinement_verified:
        fail("refusing to provision until --confinement-verified is supplied after the target-VM gate")
    kiosk = account(args.kiosk_user, "kiosk")
    child = account(args.child_user, "child")
    if kiosk.pw_uid == child.pw_uid:
        fail("kiosk and child accounts must differ")
    if child.pw_uid < 1000:
        fail("child account must be a non-system user")

    prefix = Path(args.prefix)
    example = prefix / "usr/share/oh-no-parent-control/config.example.json"
    policy_template = prefix / "usr/share/oh-no-parent-control/com.puffyslippers.OhNoParentControl1.conf.in"
    try:
        config = json.loads(example.read_text(encoding="utf-8"))
        policy = policy_template.read_text(encoding="utf-8")
    except OSError as error:
        fail(f"installed template unavailable: {error}")
    config["kiosk_uid"] = kiosk.pw_uid
    config["child_uid"] = child.pw_uid
    config["child_label"] = child.pw_gecos.split(",", 1)[0] or child.pw_name
    sys.path.insert(0, str(prefix / "usr/lib/oh-no-parent-control/broker"))
    try:
        from oh_no_parent_control.config import validate
        validate(config)
    except (ImportError, ValueError) as error:
        fail(f"generated configuration failed validation: {error}")
    config_path = prefix / "etc/oh-no-parent-control/config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    os.chown(config_path.parent, 0, 0)
    os.chmod(config_path.parent, 0o755)
    atomic_write(config_path, json.dumps(config, indent=2) + "\n", 0o600)
    policy_path = prefix / "usr/share/dbus-1/system.d/com.puffyslippers.OhNoParentControl1.conf"
    atomic_write(policy_path, policy.replace("@KIOSK_USER@", kiosk.pw_name), 0o644)

    if prefix == Path("/"):
        subprocess.run([
            "busctl", "--system", "set-property", "org.freedesktop.Accounts",
            f"/org/freedesktop/Accounts/User{kiosk.pw_uid}",
            "com.endlessm.ParentalControls.SessionLimits", "LimitType", "u", "0",
        ], check=True)
        subprocess.run([
            "busctl", "--system", "call", "org.freedesktop.Accounts",
            f"/org/freedesktop/Accounts/User{kiosk.pw_uid}",
            "org.freedesktop.Accounts.User", "SetSession", "s", "oh-no-parent-control",
        ], check=True)
        subprocess.run(["systemctl", "reload", "dbus.service"], check=True)
    print(f"Provisioned kiosk UID {kiosk.pw_uid} for child UID {child.pw_uid}")
    print("The Session property selects a default only; retain the separately verified confinement control.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
