#!/usr/bin/python3 -I
"""Release-based kiosk provisioning with package-owned account identity.

The package lifecycle owns account creation, password deletion and the numeric
UID marker. It must publish that root:0600 marker before calling this entry,
including --check-account, and preserve its ordinary-user/foreign-home guards.
C02c2 must recover old visibility transactions and durably reveal retained
hidden accounts before cutover. This entry neither migrates that cache nor
changes account expiry, PAM, service state or the old admission protocol.
"""

import argparse
import grp
import json
import os
from pathlib import Path
import pwd
import shlex
import stat
import subprocess
import sys
import tempfile


KIOSK_USER = "oh-no-parent-control"
KIOSK_HOME = "/home/oh-no-parent-control"
KIOSK_OWNERSHIP = Path("var/lib/oh-no-parent-control/package-created-kiosk-uid")
KIOSK_ICON_FILE = "/usr/share/oh-no-parent-control/kiosk_account_icon.png"
ADMIN_GROUPS = {"sudo", "adm", "wheel"}
BUS = "org.freedesktop.Accounts"
MANAGER = "/org/freedesktop/Accounts"
USER_INTERFACE = "org.freedesktop.Accounts.User"
LIMIT_INTERFACE = "com.endlessm.ParentalControls.SessionLimits"
ENVIRONMENT = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"}
_OWNER_UID = 0
_OWNER_GID = 0


def fail(message):
    raise SystemExit(f"provision: {message}")


def kiosk_account(prefix):
    """Validate the reserved NSS identity, home and lifecycle's UID ownership."""
    try:
        user = pwd.getpwnam(KIOSK_USER)
    except KeyError:
        fail("kiosk account does not exist: [Kiosk user]")
    if user.pw_name != KIOSK_USER or user.pw_uid <= 0:
        fail("invalid reserved kiosk identity")
    memberships = {group.gr_name for group in grp.getgrall()
                   if user.pw_name in group.gr_mem or group.gr_gid == user.pw_gid}
    if memberships & ADMIN_GROUPS:
        fail("kiosk account is administrative")
    if user.pw_dir != KIOSK_HOME:
        fail("kiosk home does not match the reserved path")
    home = prefix / KIOSK_HOME.lstrip("/")
    if home.is_symlink() or not home.is_dir() or home.stat().st_uid != user.pw_uid:
        fail("kiosk home has unsafe ownership")

    # Pin the caller's ownership record without following a substituted
    # ancestor or final symlink. The marker is never created or repaired here.
    directory = os.open(prefix, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        for component in KIOSK_OWNERSHIP.parts[:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW |
                            os.O_CLOEXEC, dir_fd=directory)
            os.close(directory)
            directory = child
            info = os.fstat(directory)
            if (info.st_uid != _OWNER_UID or info.st_mode & 0o002 or
                    (info.st_mode & 0o020 and info.st_gid != _OWNER_GID)):
                fail("unsafe kiosk ownership directory")
        descriptor = os.open(KIOSK_OWNERSHIP.name, os.O_RDONLY | os.O_NOFOLLOW |
                             os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory)
        try:
            info = os.fstat(descriptor)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != _OWNER_UID or
                    stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1 or
                    info.st_size > 32 or os.read(descriptor, 33) != f"{user.pw_uid}\n".encode()):
                fail("kiosk account no longer matches package ownership")
        finally:
            os.close(descriptor)
    finally:
        os.close(directory)
    return user


def busctl(*arguments):
    return subprocess.run(
        ["/usr/bin/busctl", "--system", "--timeout=30",
         "--allow-interactive-authorization=no", *arguments],
        check=True, capture_output=True, text=True, timeout=35, env=ENVIRONMENT,
    ).stdout


def properties(path, interface, *names):
    return shlex.split(busctl("get-property", BUS, path, interface, *names))


def cache_kiosk(user, path):
    """Cache fresh state; retained classification migration belongs to C02c2."""
    state = properties(path, USER_INTERFACE, "SystemAccount", "Saved")
    if state == ["b", "false", "b", "true"]:
        return False
    if state == ["b", "true", "b", "true"]:
        fail("retained kiosk visibility migration must complete before provisioning")
    if state not in (["b", "true", "b", "false"], ["b", "false", "b", "false"]):
        fail("AccountsService returned invalid kiosk visibility")
    result = shlex.split(busctl("call", BUS, MANAGER, BUS, "CacheUser", "s", user.pw_name))
    if result != ["o", path]:
        fail("AccountsService returned an invalid cached kiosk object")
    if properties(path, USER_INTERFACE, "SystemAccount", "Saved") != ["b", "false", "b", "true"]:
        fail("AccountsService failed kiosk cache verification")
    return True


def provision_icon(path, *, fresh):
    """Preserve custom artwork; optional presentation cannot veto routing."""
    try:
        icon = properties(path, USER_INTERFACE, "IconFile")
        if len(icon) != 2 or icon[0] != "s":
            raise ValueError("invalid artwork metadata")
        if (fresh or not icon[1]) and icon[1] != KIOSK_ICON_FILE:
            busctl("call", BUS, path, USER_INTERFACE, "SetIconFile", "s", KIOSK_ICON_FILE)
    except (OSError, ValueError, subprocess.SubprocessError):
        print("provision: optional kiosk artwork unavailable", file=sys.stderr)


def provision_accounts_service(user):
    """Retain main metadata while setting the release's dedicated session."""
    path = f"{MANAGER}/User{user.pw_uid}"
    if shlex.split(busctl("call", BUS, MANAGER, BUS, "FindUserById", "x", str(user.pw_uid))) != ["o", path]:
        fail("AccountsService returned an invalid object for [Kiosk user]")
    fresh = cache_kiosk(user, path)
    provision_icon(path, fresh=fresh)

    limits = properties(path, LIMIT_INTERFACE, "LimitType")
    if len(limits) != 2 or limits[0] != "u" or not limits[1].isascii() or not limits[1].isdigit():
        fail("AccountsService returned invalid kiosk time-limit metadata")
    if limits != ["u", "0"]:
        busctl("set-property", BUS, path, LIMIT_INTERFACE, "LimitType", "u", "0")
        if properties(path, LIMIT_INTERFACE, "LimitType") != ["u", "0"]:
            fail("kiosk time-limit removal failed verification")

    expected = ["s", KIOSK_USER, "s", "wayland", "b", "false", "b", "true"]
    state = properties(path, USER_INTERFACE, "Session", "SessionType", "SystemAccount", "Saved")
    if state != expected:
        # Each public setter preserves unrelated AccountsService fields. Avoid
        # even these saves for an already-correct retained account.
        for method, value in (("SetSession", KIOSK_USER), ("SetSessionType", "wayland")):
            busctl("call", BUS, path, USER_INTERFACE, method, "s", value)
        if properties(path, USER_INTERFACE, "Session", "SessionType", "SystemAccount", "Saved") != expected:
            fail("kiosk session routing failed verification")


def atomic_write(path, contents, mode):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), mode)
            os.fchown(stream.fileno(), 0, 0)
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def provision_configuration(prefix, user):
    """Keep main's validated broker config and UID-specific system-bus policy."""
    example = prefix / "usr/share/oh-no-parent-control/config.example.json"
    template = prefix / "usr/share/oh-no-parent-control/com.puffyslippers.OhNoParentControl1.conf.in"
    try:
        config = json.loads(example.read_text(encoding="utf-8"))
        policy = template.read_text(encoding="utf-8")
    except OSError as error:
        fail(f"installed template unavailable: {error}")
    config["kiosk_uid"] = user.pw_uid
    sys.path.insert(0, str(prefix / "usr/lib/oh-no-parent-control/broker"))
    try:
        from oh_no_parent_control.config import validate
        validate(config)
    except (ImportError, ValueError) as error:
        fail(f"generated configuration failed validation: {error}")
    finally:
        sys.path.pop(0)
    path = prefix / "etc/oh-no-parent-control/config.json"
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    os.chown(path.parent, 0, 0)
    os.chmod(path.parent, 0o755)
    atomic_write(path, json.dumps(config, indent=2) + "\n", 0o600)
    atomic_write(prefix / "usr/share/dbus-1/system.d/com.puffyslippers.OhNoParentControl1.conf",
                 policy.replace("@KIOSK_USER@", user.pw_name), 0o644)


def main(arguments=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--kiosk-user", required=True, choices=(KIOSK_USER,))
    parser.add_argument("--prefix", default="/")
    parser.add_argument("--check-account", action="store_true")
    args = parser.parse_args(arguments)
    if os.geteuid() != 0:
        fail("must run as root")
    prefix = Path(args.prefix)
    if not prefix.is_absolute():
        parser.error("--prefix must be absolute")
    user = kiosk_account(prefix)
    if args.check_account:
        print("Validated package kiosk identity [Kiosk user]", file=sys.stderr)
        return 0
    provision_configuration(prefix, user)
    if prefix == Path("/"):
        provision_accounts_service(user)
    print("Provisioned [Kiosk user]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
