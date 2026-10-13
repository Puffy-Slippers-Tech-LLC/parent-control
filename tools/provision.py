#!/usr/bin/python3 -I
"""Provision the immutable kiosk UID and account-specific system-bus policy."""

import argparse
from contextlib import contextmanager
import grp
import hashlib
import json
import os
import pwd
import re
import shlex
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ADMIN_GROUPS = {"sudo", "adm", "wheel"}
# Dedicated 128-pixel artwork leaves room for the login screen's circular crop.
KIOSK_ICON_FILE = "/usr/share/oh-no-parent-control/kiosk_account_icon.png"
KIOSK_USER = "oh-no-parent-control"
KIOSK_OWNERSHIP = Path("/var/lib/oh-no-parent-control/package-created-kiosk-uid")
KIOSK_CACHE_DIRECTORY = Path("/var/lib/AccountsService/users")
_ACCOUNT_OWNER_UID = 0
_ACCOUNT_OWNER_GID = 0
_ACCOUNT_FILESYSTEM_ROOT = Path("/")
# This is an owned adapter for the reviewed 23.13.9 key-file schema, not a
# generic AccountsService editor. A new upstream schema needs qualification.
ACCOUNTS_SERVICE_CACHE_VERSION = "accounts-daemon 23.13.9"
FEDORA_ACCOUNTS_SERVICE_VERSION = "accounts-daemon 26.03.0"
FEDORA_ACCOUNTS_SERVICE_PACKAGE = "accountsservice 23.13.9-16.fc44"
ACCOUNTS_SERVICE_BINARIES = (Path("/usr/lib/accountsservice/accounts-daemon"),
                            Path("/usr/libexec/accounts-daemon"))
_ACCOUNT_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"}
_VISIBILITY_SLOT = ".onpc-kiosk-visibility-v1"
_VISIBILITY_TRANSACTION = "user.oh-no-parent-control.visibility-v1"


@contextmanager
def _account_directory(path):
    """Pin every root-owned directory without following substituted links."""
    relative = path.relative_to(_ACCOUNT_FILESYSTEM_ROOT)
    descriptor = os.open(_ACCOUNT_FILESYSTEM_ROOT, os.O_RDONLY | os.O_DIRECTORY |
                         os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        root = os.fstat(descriptor)
        if (root.st_uid != _ACCOUNT_OWNER_UID or root.st_mode & 0o002 or
                (root.st_mode & 0o020 and root.st_gid != _ACCOUNT_OWNER_GID)):
            fail("unsafe AccountsService integration directory")
        for component in relative.parts:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY |
                            os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
            info = os.fstat(descriptor)
            if (info.st_uid != _ACCOUNT_OWNER_UID or info.st_mode & 0o002 or
                    (info.st_mode & 0o020 and info.st_gid != _ACCOUNT_OWNER_GID)):
                fail("unsafe AccountsService integration directory")
        yield descriptor
    finally:
        os.close(descriptor)


def _account_file(directory, name):
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC |
                         os.O_NONBLOCK, dir_fd=directory)
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != _ACCOUNT_OWNER_UID or
                info.st_nlink != 1 or info.st_mode & 0o022 or info.st_size > 1024 * 1024):
            fail("unsafe AccountsService integration file")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            contents = stream.read(1024 * 1024 + 1)
        if len(contents) > 1024 * 1024:
            fail("AccountsService integration file exceeds its bound")
        attributes = {name: os.getxattr(descriptor, name) for name in os.listxattr(descriptor)}
        return info, contents, attributes
    finally:
        os.close(descriptor)


def _kiosk_cache_visibility(contents):
    """Locate one boolean without serializing or discarding other metadata."""
    try:
        text = contents.decode("utf-8")
    except UnicodeError:
        fail("unsupported AccountsService cache encoding")
    if "\x00" in text:
        fail("unsupported AccountsService cache syntax")
    section = None
    user_sections = 0
    matches = []
    offset = 0
    insertion = None
    for line in contents.splitlines(keepends=True):
        stripped = line.strip()
        if not stripped or stripped.startswith(b"#"):
            offset += len(line)
            continue
        group = re.fullmatch(rb"\[([^\]\r\n]+)\]", stripped)
        if group:
            if section == b"User" and insertion is None:
                insertion = offset
            section = group[1]
            if section == b"User":
                user_sections += 1
        elif section == b"User":
            key, separator, value = line.partition(b"=")
            if separator and key.strip() == b"SystemAccount":
                boolean = value.strip()
                if boolean not in (b"true", b"false"):
                    fail("unsupported AccountsService classification")
                start = offset + len(key) + 1 + len(value) - len(value.lstrip())
                matches.append((start, start + len(boolean), boolean == b"false"))
        offset += len(line)
    if user_sections != 1 or len(matches) > 1:
        fail("ambiguous AccountsService classification")
    if matches:
        return matches[0]
    return insertion if insertion is not None else len(contents), None, False


def _kiosk_cache_is_visible():
    with _account_directory(KIOSK_CACHE_DIRECTORY) as directory:
        _, contents, attributes = _account_file(directory, KIOSK_USER)
        pending = os.path.lexists(KIOSK_CACHE_DIRECTORY / _VISIBILITY_SLOT)
    return (_kiosk_cache_visibility(contents)[2] and
            _VISIBILITY_TRANSACTION not in attributes and not pending)


def _visibility_metadata(info, attributes):
    metadata = [info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode),
                {name: value.hex() for name, value in attributes.items()
                 if name != _VISIBILITY_TRANSACTION}]
    return hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest()


def _visibility_transaction(value):
    try:
        record = json.loads(value)
    except (ValueError, UnicodeError):
        fail("invalid kiosk classification transaction")
    if (not isinstance(record, dict) or set(record) != {
            "version", "uid", "device", "inode", "before", "after", "metadata"} or
            type(record["version"]) is not int or record["version"] != 1 or
            any(type(record[key]) is not int or record[key] < 0
                for key in ("uid", "device", "inode")) or
            any(not isinstance(record[key], str) or not re.fullmatch(r"[0-9a-f]{64}", record[key])
                for key in ("before", "after", "metadata"))):
        fail("invalid kiosk classification transaction")
    return record


def _verify_accounts_service_cache_version(binary):
    result = subprocess.run([str(binary), "--version"], check=True,
                            stdout=subprocess.PIPE, text=True, timeout=30, env=_ACCOUNT_ENV)
    version = result.stdout.strip()
    if version == ACCOUNTS_SERVICE_CACHE_VERSION:
        return
    if version == FEDORA_ACCOUNTS_SERVICE_VERSION:
        # Fedora's %autosetup -S git causes the 23.13.9 generator to derive
        # its runtime version from the build commit's date. Admit only the
        # source-reviewed F44 package rather than treating that date as ABI.
        result = subprocess.run([
            "rpm", "-q", "--qf", "%{NAME} %{VERSION}-%{RELEASE}\n", "accountsservice",
        ], check=True, stdout=subprocess.PIPE, text=True, timeout=30, env=_ACCOUNT_ENV)
        if result.stdout.strip() == FEDORA_ACCOUNTS_SERVICE_PACKAGE:
            return
    fail("unsupported AccountsService cache version")


def _recover_visibility_transaction(directory, user):
    """Recover only the exact fixed slot or committed marker we created."""
    info, contents, attributes = _account_file(directory, KIOSK_USER)
    marker = attributes.get(_VISIBILITY_TRANSACTION)
    if marker is not None:
        record = _visibility_transaction(marker)
        if (record["uid"] != user.pw_uid or record["after"] != hashlib.sha256(contents).hexdigest() or
                record["metadata"] != _visibility_metadata(info, attributes)):
            fail("changed committed kiosk classification transaction")
        descriptor = os.open(KIOSK_USER, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                             dir_fd=directory)
        try:
            current = os.fstat(descriptor)
            if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                fail("replaced committed kiosk classification transaction")
            os.removexattr(descriptor, _VISIBILITY_TRANSACTION)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    try:
        pending, data, pending_attributes = _account_file(directory, _VISIBILITY_SLOT)
    except FileNotFoundError:
        return
    marker = pending_attributes.get(_VISIBILITY_TRANSACTION)
    if marker is None:
        fail("unowned kiosk classification transaction slot")
    record = _visibility_transaction(marker)
    if (record["uid"] != user.pw_uid or
            (record["device"], record["inode"]) != (info.st_dev, info.st_ino) or
            record["before"] != hashlib.sha256(contents).hexdigest() or
            record["after"] != hashlib.sha256(data).hexdigest() or
            record["metadata"] != _visibility_metadata(info, attributes) or
            record["metadata"] != _visibility_metadata(pending, pending_attributes)):
        fail("changed kiosk classification transaction slot")
    current = os.stat(_VISIBILITY_SLOT, dir_fd=directory, follow_symlinks=False)
    if (current.st_dev, current.st_ino) != (pending.st_dev, pending.st_ino):
        fail("replaced kiosk classification transaction slot")
    os.unlink(_VISIBILITY_SLOT, dir_fd=directory)
    os.fsync(directory)


def repair_kiosk_visibility():
    """Migrate only the package-owned account before AccountsService starts.

    The systemd start-pre boundary supplies quiescence: the old daemon has
    exited and D-Bus activation joins this same start job. Atomic replacement
    makes interruption/retry and reboot recover without a temporary mask or a
    second metadata copy. The service ignores refusal so ordinary accounts keep
    working; provisioning independently verifies kiosk visibility and refuses.
    """
    try:
        with _account_directory(KIOSK_OWNERSHIP.parent) as directory:
            ownership, marker, _ = _account_file(directory, KIOSK_OWNERSHIP.name)
    except FileNotFoundError:
        return
    user = account(KIOSK_USER, "kiosk")
    if (stat.S_IMODE(ownership.st_mode) != 0o600 or
            marker != f"{user.pw_uid}\n".encode() or user.pw_dir != "/home/oh-no-parent-control"):
        fail("kiosk classification ownership changed")
    with _account_directory(KIOSK_CACHE_DIRECTORY) as directory:
        try:
            info, before, attributes = _account_file(directory, KIOSK_USER)
        except FileNotFoundError:
            return
        start, end, visible = _kiosk_cache_visibility(before)
        pending = os.path.lexists(KIOSK_CACHE_DIRECTORY / _VISIBILITY_SLOT)
        if visible and _VISIBILITY_TRANSACTION not in attributes and not pending:
            return
        result = subprocess.run([
            "systemctl", "show", "--property=ActiveState,SubState,MainPID",
            "accounts-daemon.service",
        ], check=True, stdout=subprocess.PIPE, text=True, timeout=30, env=_ACCOUNT_ENV)
        state = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        if state != {"ActiveState": "activating", "SubState": "start-pre", "MainPID": "0"}:
            fail("kiosk classification repair requires the AccountsService start boundary")
        binaries = [path for path in ACCOUNTS_SERVICE_BINARIES if path.is_file()]
        if len(binaries) != 1:
            fail("unsupported AccountsService executable layout")
        _verify_accounts_service_cache_version(binaries[0])
        _recover_visibility_transaction(directory, user)
        info, before, attributes = _account_file(directory, KIOSK_USER)
        start, end, visible = _kiosk_cache_visibility(before)
        if visible:
            return
        if end is None:
            separator = b"" if start == 0 or before[start - 1:start] == b"\n" else b"\n"
            after = before[:start] + separator + b"SystemAccount=false\n" + before[start:]
        else:
            after = before[:start] + b"false" + before[end:]
        record = json.dumps({"version": 1, "uid": user.pw_uid,
                             "device": info.st_dev, "inode": info.st_ino,
                             "before": hashlib.sha256(before).hexdigest(),
                             "after": hashlib.sha256(after).hexdigest(),
                             "metadata": _visibility_metadata(info, attributes)}, sort_keys=True).encode()
        # An unlinked inode cannot leave residue if its writer is interrupted.
        # Publish the one fixed slot only after its ownership marker and bytes
        # are complete. Every later retry verifies that marker against source.
        descriptor = os.open(".", os.O_RDWR | os.O_TMPFILE | os.O_CLOEXEC,
                             0o600, dir_fd=directory)
        published = False
        committed = False
        try:
            os.fchown(descriptor, info.st_uid, info.st_gid)
            os.fchmod(descriptor, stat.S_IMODE(info.st_mode))
            for name, value in attributes.items():
                os.setxattr(descriptor, name, value)
            os.setxattr(descriptor, _VISIBILITY_TRANSACTION, record)
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(after)
                stream.flush()
                os.fsync(descriptor)
            current, contents, current_attributes = _account_file(directory, KIOSK_USER)
            if (current.st_dev, current.st_ino, contents, current_attributes,
                    _visibility_metadata(current, current_attributes)) != (
                    info.st_dev, info.st_ino, before, attributes, _visibility_metadata(info, attributes)):
                fail("AccountsService cache changed during classification repair")
            os.link(f"/proc/self/fd/{descriptor}", _VISIBILITY_SLOT,
                    dst_dir_fd=directory, follow_symlinks=True)
            published = True
            os.fsync(directory)
            os.replace(_VISIBILITY_SLOT, KIOSK_USER, src_dir_fd=directory, dst_dir_fd=directory)
            committed = True
            os.fsync(directory)
            os.removexattr(descriptor, _VISIBILITY_TRANSACTION)
            os.fsync(descriptor)
            saved, contents, saved_attributes = _account_file(directory, KIOSK_USER)
            if (contents, saved.st_uid, saved.st_gid, stat.S_IMODE(saved.st_mode), saved_attributes) != (
                    after, info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode), attributes):
                fail("AccountsService classification persistence failed verification")
        finally:
            try:
                if published and not committed:
                    current = os.stat(_VISIBILITY_SLOT, dir_fd=directory, follow_symlinks=False)
                    temporary = os.fstat(descriptor)
                    if (current.st_dev, current.st_ino) != (temporary.st_dev, temporary.st_ino):
                        fail("replaced kiosk classification transaction during cleanup")
                    os.unlink(_VISIBILITY_SLOT, dir_fd=directory)
                    os.fsync(directory)
            finally:
                os.close(descriptor)
    print("Migrated [Kiosk user] durable visibility (cache adapter v1)", file=sys.stderr)


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


def accounts_service_set_icon_file(user, icon_file=KIOSK_ICON_FILE, user_path=None, *, preserve_existing=True):
    """Set the default artwork without replacing a retained account's icon."""
    user_path = user_path or accounts_service_user_path(user)
    result = subprocess.run([
        "busctl", "--system", "get-property", "org.freedesktop.Accounts",
        user_path, "org.freedesktop.Accounts.User", "IconFile",
    ], check=True, stdout=subprocess.PIPE, text=True)
    fields = shlex.split(result.stdout)
    if len(fields) != 2 or fields[0] != "s":
        fail("AccountsService returned invalid kiosk artwork metadata")
    # SetIconFile always serializes AccountsService's entire [User] group,
    # including for an unchanged value. Avoid that unnecessary metadata write.
    if fields[1] == icon_file or (preserve_existing and fields[1]):
        return
    subprocess.run([
        "busctl", "--system", "call", "org.freedesktop.Accounts",
        user_path,
        "org.freedesktop.Accounts.User", "SetIconFile", "s", icon_file,
    ], check=True)


def accounts_service_cache_kiosk(user, user_path):
    """Cache fresh state or restart through the owned retained-state adapter."""
    result = subprocess.run([
        "busctl", "--system", "get-property", "org.freedesktop.Accounts",
        user_path, "org.freedesktop.Accounts.User", "SystemAccount", "Saved",
    ], check=True, stdout=subprocess.PIPE, text=True)
    fields = shlex.split(result.stdout)
    if fields == ["b", "false", "b", "true"]:
        # Older interrupted CacheUser calls can leave only the live object
        # visible. Verify durable state before accepting a retained account.
        if _kiosk_cache_is_visible():
            return False
    elif fields not in (["b", "true", "b", "true"], ["b", "true", "b", "false"],
                        ["b", "false", "b", "false"]):
        fail("AccountsService returned invalid kiosk visibility")
    if fields[-1] == "true":
        # The packaged start-pre hook is the only writer of retained cache
        # classification. systemd prevents D-Bus activation racing this edit.
        for arguments in (("daemon-reload",), ("restart", "accounts-daemon.service")):
            subprocess.run(["systemctl", *arguments], check=True, timeout=60, env=_ACCOUNT_ENV)
    else:
        result = subprocess.run([
            "busctl", "--system", "call", "org.freedesktop.Accounts",
            "/org/freedesktop/Accounts", "org.freedesktop.Accounts",
            "CacheUser", "s", user.pw_name,
        ], check=True, stdout=subprocess.PIPE, text=True)
        if shlex.split(result.stdout) != ["o", user_path]:
            fail("AccountsService returned an invalid cached kiosk object")
    result = subprocess.run([
        "busctl", "--system", "get-property", "org.freedesktop.Accounts",
        user_path, "org.freedesktop.Accounts.User", "SystemAccount", "Saved",
    ], check=True, stdout=subprocess.PIPE, text=True)
    if shlex.split(result.stdout) != ["b", "false", "b", "true"]:
        fail("AccountsService failed kiosk cache verification")
    if not _kiosk_cache_is_visible():
        fail("AccountsService failed durable kiosk cache verification")
    return fields[-1] == "false"


def accounts_service_set_kiosk_session(user_path):
    """Set and verify both public routing properties, including the transport."""
    read_command = [
        "busctl", "--system", "get-property", "org.freedesktop.Accounts",
        user_path, "org.freedesktop.Accounts.User", "Session", "SessionType", "SystemAccount",
    ]
    expected = ["s", "oh-no-parent-control", "s", "wayland", "b", "false"]
    result = subprocess.run(read_command, check=True, stdout=subprocess.PIPE, text=True)
    if shlex.split(result.stdout) == expected:
        return
    for method, value in (("SetSession", "oh-no-parent-control"),
                          ("SetSessionType", "wayland")):
        subprocess.run([
            "busctl", "--system", "call", "org.freedesktop.Accounts",
            user_path, "org.freedesktop.Accounts.User", method, "s", value,
        ], check=True)
    result = subprocess.run(read_command, check=True, stdout=subprocess.PIPE, text=True)
    if shlex.split(result.stdout) != expected:
        fail("kiosk session routing failed verification")
    print("Verified [Kiosk user] session=dedicated type=wayland", file=sys.stderr)


def accounts_service_provision_kiosk(user):
    """Apply required kiosk properties while retaining unrelated saved data."""
    print("Resolving AccountsService object for [Kiosk user]", file=sys.stderr)
    user_path = accounts_service_user_path(user)
    fresh = accounts_service_cache_kiosk(user, user_path)
    print("Applying AccountsService properties for [Kiosk user]", file=sys.stderr)
    accounts_service_set_icon_file(user, user_path=user_path, preserve_existing=not fresh)
    result = subprocess.run([
        "busctl", "--system", "get-property", "org.freedesktop.Accounts",
        user_path, "com.endlessm.ParentalControls.SessionLimits", "LimitType",
    ], check=True, stdout=subprocess.PIPE, text=True)
    fields = shlex.split(result.stdout)
    if len(fields) != 2 or fields[0] != "u" or not fields[1].isascii() or not fields[1].isdigit():
        fail("AccountsService returned invalid kiosk time-limit metadata")
    if fields != ["u", "0"]:
        subprocess.run([
            "busctl", "--system", "set-property", "org.freedesktop.Accounts", user_path,
            "com.endlessm.ParentalControls.SessionLimits", "LimitType", "u", "0",
        ], check=True)
    accounts_service_set_kiosk_session(user_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kiosk-user")
    parser.add_argument("--prefix", default="/")
    parser.add_argument("--check-account", action="store_true")
    parser.add_argument("--repair-kiosk-visibility", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0:
        fail("must run as root")
    if args.repair_kiosk_visibility:
        if args.kiosk_user or args.check_account or args.prefix != "/":
            parser.error("classification repair accepts no provisioning options")
        repair_kiosk_visibility()
        return 0
    if not args.kiosk_user:
        parser.error("--kiosk-user is required for provisioning")
    kiosk = account(args.kiosk_user, "kiosk")
    if kiosk.pw_dir != "/home/oh-no-parent-control":
        fail("kiosk home does not match the reserved path")
    home = Path(args.prefix) / kiosk.pw_dir.lstrip("/")
    if home.is_symlink() or not home.is_dir() or home.stat().st_uid != kiosk.pw_uid:
        fail("kiosk home has unsafe ownership")
    if args.check_account:
        print("Validated package kiosk identity [Kiosk user]", file=sys.stderr)
        return 0

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
        accounts_service_provision_kiosk(kiosk)
    print("Provisioned [Kiosk user]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
