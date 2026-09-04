#!/usr/bin/python3
"""Provision the immutable kiosk UID and account-specific system-bus policy."""

import argparse
import grp
import json
import os
import pwd
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ADMIN_GROUPS = {"sudo", "adm"}
# The shared logo is also within AccountsService's 128-pixel icon limit.
KIOSK_ICON_FILE = "/usr/share/oh-no-parent-control/app_logo.png"


def fail(message):
    raise SystemExit(f"provision: {message}")


def account(name, role):
    try:
        entry = pwd.getpwnam(name)
    except KeyError:
        fail(f"{role} account does not exist: [user]")
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


def accounts_service_user_path(user):
    """Resolve and load an NSS account through the AccountsService manager."""
    result = subprocess.run([
        "busctl", "--system", "call", "org.freedesktop.Accounts",
        "/org/freedesktop/Accounts", "org.freedesktop.Accounts",
        "FindUserById", "x", str(user.pw_uid),
    ], check=True, stdout=subprocess.PIPE, text=True)
    fields = shlex.split(result.stdout)
    expected_path = f"/org/freedesktop/Accounts/User{user.pw_uid}"
    if fields != ["o", expected_path]:
        fail("AccountsService returned an invalid object for [user]")
    return expected_path


def accounts_service_language(user, user_path=None):
    user_path = user_path or accounts_service_user_path(user)
    result = subprocess.run([
        "busctl", "--system", "get-property", "org.freedesktop.Accounts",
        user_path,
        "org.freedesktop.Accounts.User", "Language",
    ], check=True, stdout=subprocess.PIPE, text=True)
    fields = shlex.split(result.stdout)
    if len(fields) != 2 or fields[0] != "s":
        fail("AccountsService returned an invalid language for [user]")
    return fields[1]


def accounts_service_set_icon_file(user, icon_file=KIOSK_ICON_FILE, user_path=None):
    """Make the kiosk account use the product's AccountsService-safe artwork."""
    user_path = user_path or accounts_service_user_path(user)
    subprocess.run([
        "busctl", "--system", "call", "org.freedesktop.Accounts",
        user_path,
        "org.freedesktop.Accounts.User", "SetIconFile", "s", icon_file,
    ], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kiosk-user", required=True)
    parser.add_argument("--language-source-user")
    parser.add_argument("--prefix", default="/")
    args = parser.parse_args()
    if os.geteuid() != 0:
        fail("must run as root")
    kiosk = account(args.kiosk_user, "kiosk")

    prefix = Path(args.prefix)
    example = prefix / "usr/share/oh-no-parent-control/config.example.json"
    policy_template = prefix / "usr/share/oh-no-parent-control/com.puffyslippers.OhNoParentControl1.conf.in"
    try:
        config = json.loads(example.read_text(encoding="utf-8"))
        policy = policy_template.read_text(encoding="utf-8")
    except OSError as error:
        fail(f"installed template unavailable: {error}")
    config["kiosk_uid"] = kiosk.pw_uid
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
        print("Resolving AccountsService object for [Kiosk user]", file=sys.stderr)
        kiosk_path = accounts_service_user_path(kiosk)
        print("Applying AccountsService properties for [Kiosk user]", file=sys.stderr)
        accounts_service_set_icon_file(kiosk, user_path=kiosk_path)
        language = ""
        if args.language_source_user:
            try:
                language_source = pwd.getpwnam(args.language_source_user)
            except KeyError:
                fail("language source account does not exist: [user]")
            if language_source.pw_uid == 0:
                fail("language source account must not be root")
            language = accounts_service_language(language_source)
        # AccountsService rejects an empty SetLanguage value on current
        # Ubuntu releases.  An empty source language means "use the machine
        # default", which is already the account's state, so leave it alone.
        if language:
            subprocess.run([
                "busctl", "--system", "call", "org.freedesktop.Accounts",
                kiosk_path,
                "org.freedesktop.Accounts.User", "SetLanguage", "s", language,
            ], check=True)
        subprocess.run([
            "busctl", "--system", "set-property", "org.freedesktop.Accounts",
            kiosk_path,
            "com.endlessm.ParentalControls.SessionLimits", "LimitType", "u", "0",
        ], check=True)
        subprocess.run([
            "busctl", "--system", "call", "org.freedesktop.Accounts",
            kiosk_path,
            "org.freedesktop.Accounts.User", "SetSession", "s", "oh-no-parent-control",
        ], check=True)
    print("Provisioned [Kiosk user]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
