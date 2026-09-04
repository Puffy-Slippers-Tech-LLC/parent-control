#!/usr/bin/python3
"""Guard and prepare the four fixed accounts in the Ubuntu 26.04 source VM."""

from __future__ import annotations

import dataclasses
import getpass
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
from typing import Callable, Sequence


CHECKOUT = Path("/Data/Code/PST/parent-control")
MARKER = Path("/etc/oh-no-parent-control-test-baseline.json")
HOSTNAME = "ubuntu26.04"
UBUNTU_VERSION = "26.04"
MARKER_PURPOSE = "oh-no-parent-control-test-baseline"
MARKER_VERSION = 1
INTERACTIVE_SHELL = "/bin/bash"
FORBIDDEN_CHILD_GROUPS = frozenset({"adm", "sudo"})
KIOSK_USER = "oh-no-parent-control"
SCRIPT_FILES = (
    "tests/integration/prepare-vm",
    "tests/integration/prepare_vm.py",
)


@dataclasses.dataclass(frozen=True)
class Identity:
    label: str
    username: str
    display_name: str
    role: str


IDENTITIES = (
    Identity("[Test parent 1]", "onpc-parent-jamie", "Jamie Parker", "administrator"),
    Identity("[Test parent 2]", "onpc-parent-casey", "Casey Parker", "administrator"),
    Identity("[Test child 1]", "onpc-child-riley", "Riley Parker", "standard"),
    Identity("[Test child 2]", "onpc-child-jordan", "Jordan Parker", "standard"),
)

REQUIRED_CHECKOUT_ENTRIES = (
    ".git",
    "AGENTS.md",
    "Makefile",
    "debian/control",
    "docs/System-Design.md",
    "tests/integration/prepare-vm",
    "tests/integration/prepare_vm.py",
)

# Each installed-state category has its own fail-closed probes so a partial or
# previously removed installation cannot become a baseline accidentally.
RESIDUE_PATHS = {
    "payload": (
        "/usr/bin/oh-no-parent-control",
        "/usr/bin/oh-no-parent-control-parent",
        "/usr/lib/oh-no-parent-control",
        "/usr/libexec/oh-no-parent-control-broker",
        "/usr/libexec/oh-no-parent-control-migrate-state",
        "/usr/libexec/oh-no-parent-control-uninstall",
        "/usr/libexec/oh-no-parent-control-provision",
        "/usr/libexec/oh-no-parent-control-login-check",
        "/usr/libexec/oh-no-parent-control-session-limit-check",
        "/usr/libexec/oh-no-parent-control-clear-session-runtime-max",
        "/usr/libexec/oh-no-parent-control-execution-policy-ready",
        "/usr/libexec/oh-no-parent-control-execution-policy-probe",
        "/usr/libexec/oh-no-parent-control-package-activation",
        "/usr/share/oh-no-parent-control",
        "/usr/share/applications/com.puffyslippers.OhNoParentControl.desktop",
        "/usr/share/applications/com.puffyslippers.OhNoParentControl.Parent.desktop",
        "/usr/share/icons/hicolor/512x512/apps/com.puffyslippers.OhNoParentControl.png",
    ),
    "configuration": ("/etc/oh-no-parent-control",),
    "saved-state": ("/var/lib/oh-no-parent-control",),
    "service-session": (
        "/usr/lib/systemd/system/oh-no-parent-control-broker.service",
        "/usr/lib/systemd/user/oh-no-parent-control-app.service",
        "/usr/lib/systemd/user/oh-no-parent-control-polkit-agent.service",
        "/usr/lib/systemd/user/gnome-session@oh-no-parent-control.target.d",
        "/etc/systemd/system/multi-user.target.wants/oh-no-parent-control-broker.service",
        "/usr/share/dbus-1/system-services/com.puffyslippers.OhNoParentControl1.service",
        "/usr/share/dbus-1/system.d/com.puffyslippers.OhNoParentControl1.conf",
        "/usr/share/dbus-1/interfaces/com.puffyslippers.OhNoParentControl1.xml",
        "/usr/share/gnome-session/sessions/oh-no-parent-control.session",
        "/usr/share/wayland-sessions/oh-no-parent-control.desktop",
    ),
    "pam-polkit": (
        "/usr/share/pam-configs/oh-no-parent-control-session-limits",
        "/usr/share/pam-configs/oh-no-parent-control-kiosk-only",
        "/etc/polkit-1/rules.d/00-oh-no-parent-control-session.rules",
        "/usr/share/polkit-1/actions/tech.puffyslippers.com.ohnoparentcontrol.child.request-own-access.policy",
        "/usr/share/polkit-1/actions/tech.puffyslippers.com.ohnoparentcontrol.kiosk.request-access.policy",
        "/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules",
        "/etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules",
        "/usr/lib/systemd/system/fapolicyd.service.d/oh-no-parent-control-readiness.conf",
        "/usr/lib/systemd/system/display-manager.service.d/oh-no-parent-control.conf",
    ),
    "gnome-extension": (
        "/usr/share/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com",
    ),
    "logs": ("/var/log/oh-no-parent-control",),
}

PAM_FILES_TO_SCAN = (
    "/etc/pam.d/common-account",
    "/etc/pam.d/common-auth",
    "/etc/pam.d/common-session",
    "/etc/gdm3/PreSession/Default",
)


class PreparationError(RuntimeError):
    """A bounded, operator-safe preparation failure."""

    def __init__(self, category: str, message: str):
        super().__init__(f"[{category}] {message}")
        self.category = category


@dataclasses.dataclass(frozen=True)
class GuestIdentity:
    hostname: str
    machine_id: str
    ubuntu_version: str
    virtualization: str


@dataclasses.dataclass(frozen=True)
class ExistingAccount:
    username: str
    uid: int
    gid: int
    home: Path


class Runner:
    """Small injectable subprocess boundary; never records command input."""

    def run(
        self,
        command: Sequence[str],
        *,
        input_text: str | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(command),
            check=check,
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )


def _rooted(root: Path, absolute: str) -> Path:
    return root / absolute.removeprefix("/")


def _read_os_release(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise PreparationError("guard:os", "Ubuntu release identity is unavailable") from error
    for line in lines:
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        try:
            parsed = shlex.split(value, posix=True)
        except ValueError as error:
            raise PreparationError("guard:os", "Ubuntu release identity is malformed") from error
        values[key] = parsed[0] if parsed else ""
    return values


def preparation_digest(checkout: Path = CHECKOUT) -> str:
    digest = hashlib.sha256()
    for relative in SCRIPT_FILES:
        path = checkout / relative
        try:
            contents = path.read_bytes()
        except OSError as error:
            raise PreparationError("guard:checkout", "preparation source is incomplete") from error
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(len(contents).to_bytes(8, "big"))
        digest.update(contents)
    return digest.hexdigest()


def validate_checkout(cwd: Path, checkout: Path = CHECKOUT) -> None:
    if cwd != checkout or cwd.resolve() != checkout:
        raise PreparationError("guard:checkout", "run from the fixed source-VM checkout")
    for relative in REQUIRED_CHECKOUT_ENTRIES:
        path = checkout / relative
        if relative == ".git":
            valid = path.is_dir()
        else:
            valid = path.is_file()
        if not valid:
            raise PreparationError("guard:checkout", "the fixed checkout is incomplete")
    expected_script = checkout / "tests/integration/prepare_vm.py"
    if Path(__file__).resolve() != expected_script:
        raise PreparationError("guard:checkout", "the preparer is not the fixed checkout copy")


def find_residue(root: Path, runner: Runner, lookup_user: Callable[[str], object]) -> str | None:
    package = runner.run(
        ["dpkg-query", "-W", "-f=${db:Status-Status}", "oh-no-parent-control"],
        check=False,
    )
    if package.returncode == 0 and package.stdout.strip() != "not-installed":
        return "package"
    if package.returncode not in {0, 1}:
        raise PreparationError("guard:residue:package", "installed-package state could not be verified")

    for category, paths in RESIDUE_PATHS.items():
        if any(
            _rooted(root, value).exists() or _rooted(root, value).is_symlink()
            for value in paths
        ):
            return category

    for value in PAM_FILES_TO_SCAN:
        path = _rooted(root, value)
        try:
            contents = path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            continue
        except OSError:
            return "pam-polkit"
        if "oh-no-parent-control" in contents or "pam_oh_no_parent_control.so" in contents:
            return "pam-polkit"

    service = runner.run(
        [
            "systemctl", "show", "oh-no-parent-control-broker.service",
            "--property=LoadState", "--value",
        ],
        check=False,
    )
    if service.returncode != 0:
        raise PreparationError("guard:residue:service-session", "installed-service state could not be verified")
    if service.returncode == 0 and service.stdout.strip() not in {"", "not-found"}:
        return "service-session"

    try:
        lookup_user(KIOSK_USER)
    except KeyError:
        pass
    else:
        return "kiosk-account"
    return None


def validate_environment(
    *,
    root: Path = Path("/"),
    checkout: Path = CHECKOUT,
    cwd: Path | None = None,
    runner: Runner | None = None,
    euid: int | None = None,
    hostname: str | None = None,
    lookup_user: Callable[[str], object] = pwd.getpwnam,
) -> GuestIdentity:
    runner = runner or Runner()
    if (os.geteuid() if euid is None else euid) != 0:
        raise PreparationError("guard:root", "enter a root shell before running make prep-vm")

    virtual = runner.run(["systemd-detect-virt", "--vm"], check=False)
    virtualization = virtual.stdout.strip()
    if virtual.returncode != 0 or not virtualization or virtualization == "none":
        raise PreparationError("guard:virtualization", "this command requires the source virtual machine")
    if not re.fullmatch(r"[a-z0-9_-]+", virtualization):
        raise PreparationError("guard:virtualization", "virtual-machine identity is malformed")

    release = _read_os_release(_rooted(root, "/etc/os-release"))
    if release.get("ID") != "ubuntu" or release.get("VERSION_ID") != UBUNTU_VERSION:
        raise PreparationError("guard:os", "this command requires Ubuntu 26.04")

    actual_hostname = hostname if hostname is not None else os.uname().nodename
    validate_checkout(cwd or Path.cwd(), checkout)

    residue = find_residue(root, runner, lookup_user)
    if residue is not None:
        raise PreparationError(f"guard:residue:{residue}", "product installation or residue is present")

    try:
        machine_id = _rooted(root, "/etc/machine-id").read_text(encoding="ascii").strip()
    except OSError as error:
        raise PreparationError("guard:machine-identity", "guest machine identity is unavailable") from error
    if not re.fullmatch(r"[0-9a-f]{32}", machine_id):
        raise PreparationError("guard:machine-identity", "guest machine identity is malformed")

    return GuestIdentity(actual_hostname, machine_id, UBUNTU_VERSION, virtualization)


def _uid_min(root: Path) -> int:
    path = _rooted(root, "/etc/login.defs")
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            fields = line.split()
            if len(fields) >= 2 and fields[0] == "UID_MIN":
                value = int(fields[1])
                if value >= 1000:
                    return value
                break
    except (OSError, ValueError):
        pass
    raise PreparationError("account:uid-policy", "safe local-user UID policy is unavailable")


def preflight_accounts(
    *,
    root: Path = Path("/"),
    lookup_user: Callable[[str], object] = pwd.getpwnam,
    list_users: Callable[[], Sequence[object]] = pwd.getpwall,
) -> dict[str, ExistingAccount | None]:
    minimum_uid = _uid_min(root)
    uid_names: dict[int, set[str]] = {}
    for account in list_users():
        uid_names.setdefault(int(account.pw_uid), set()).add(str(account.pw_name))
    existing: dict[str, ExistingAccount | None] = {}
    seen_uids: set[int] = set()
    for identity in IDENTITIES:
        try:
            entry = lookup_user(identity.username)
        except KeyError:
            existing[identity.username] = None
            continue
        uid = int(entry.pw_uid)
        gid = int(entry.pw_gid)
        expected_home = Path("/home") / identity.username
        if uid < minimum_uid or uid == 0:
            raise PreparationError("account:system-identity", f"{identity.label} conflicts with a system account")
        if Path(entry.pw_dir) != expected_home:
            raise PreparationError("account:home", f"{identity.label} has a conflicting home directory")
        if uid in seen_uids:
            raise PreparationError("account:uid-collision", "fixed test identities share a UID")
        if uid_names.get(uid) != {identity.username}:
            raise PreparationError("account:uid-collision", f"{identity.label} shares a UID with another account")
        seen_uids.add(uid)
        home = _rooted(root, str(expected_home))
        if home.exists() or home.is_symlink():
            info = home.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or info.st_gid != gid:
                raise PreparationError("account:home-ownership", f"{identity.label} has unsafe home ownership")
        existing[identity.username] = ExistingAccount(identity.username, uid, gid, expected_home)
    return existing


def account_commands(existing: dict[str, ExistingAccount | None]) -> list[list[str]]:
    commands: list[list[str]] = []
    for identity in IDENTITIES:
        if existing[identity.username] is None:
            commands.append([
                "useradd", "--create-home", "--user-group", "--comment",
                identity.display_name, "--shell", INTERACTIVE_SHELL, identity.username,
            ])
        commands.append([
            "usermod", "--comment", identity.display_name,
            "--shell", INTERACTIVE_SHELL, identity.username,
        ])
        if identity.role == "administrator":
            commands.append(["usermod", "--append", "--groups", "adm,sudo", identity.username])
        else:
            commands.append(["gpasswd", "--delete", identity.username, "adm"])
            commands.append(["gpasswd", "--delete", identity.username, "sudo"])
    return commands


def _accounts_path(runner: Runner, username: str) -> str:
    result = runner.run([
        "busctl", "--system", "call", "org.freedesktop.Accounts",
        "/org/freedesktop/Accounts", "org.freedesktop.Accounts", "CacheUser", "s", username,
    ])
    fields = shlex.split(result.stdout)
    if len(fields) != 2 or fields[0] != "o" or not re.fullmatch(r"/org/freedesktop/Accounts/User[0-9]+", fields[1]):
        raise PreparationError("account:accounts-service", "AccountsService returned an invalid test-account object")
    return fields[1]


def _set_accounts_property(runner: Runner, path: str, method: str, signature: str, value: str) -> None:
    runner.run([
        "busctl", "--system", "call", "org.freedesktop.Accounts", path,
        "org.freedesktop.Accounts.User", method, signature, value,
    ])


def _get_property(runner: Runner, path: str, name: str, signature: str) -> str:
    result = runner.run([
        "busctl", "--system", "get-property", "org.freedesktop.Accounts", path,
        "org.freedesktop.Accounts.User", name,
    ])
    fields = shlex.split(result.stdout)
    if len(fields) != 2 or fields[0] != signature:
        raise PreparationError("verify:accounts-service", "AccountsService returned a malformed verified property")
    return fields[1]


def _bool(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise PreparationError("verify:accounts-service", "AccountsService returned a malformed boolean")


def reconcile_accounts(
    existing: dict[str, ExistingAccount | None],
    password: str,
    *,
    runner: Runner,
    lookup_user: Callable[[str], object] = pwd.getpwnam,
    list_users: Callable[[], Sequence[object]] = pwd.getpwall,
) -> dict[str, dict[str, int | str]]:
    if not password or ":" in password or "\n" in password or "\x00" in password:
        raise PreparationError("password:format", "the shared password contains an unsupported character")

    for command in account_commands(existing):
        # Deleting a group membership that is already absent is the expected
        # repeat-run state; all other reconciliation commands are strict.
        optional = command[0] == "gpasswd"
        result = runner.run(command, check=not optional)
        if optional and result.returncode not in {0, 3}:
            raise PreparationError("account:groups", "a standard test account group could not be reconciled")

    # The complete preflight has already rejected an existing path with unsafe
    # type or ownership. Numeric ownership avoids putting account data in logs.
    for identity in IDENTITIES:
        entry = lookup_user(identity.username)
        runner.run([
            "install", "-d", "-o", str(entry.pw_uid), "-g", str(entry.pw_gid),
            "-m", "0750", str(Path("/home") / identity.username),
        ])

    password_input = "".join(f"{identity.username}:{password}\n" for identity in IDENTITIES)
    runner.run(["chpasswd"], input_text=password_input)

    verified: dict[str, dict[str, int | str]] = {}
    uid_names: dict[int, set[str]] = {}
    for account in list_users():
        uid_names.setdefault(int(account.pw_uid), set()).add(str(account.pw_name))
    seen_uids: set[int] = set()
    for identity in IDENTITIES:
        entry = lookup_user(identity.username)
        path = _accounts_path(runner, identity.username)
        _set_accounts_property(runner, path, "SetRealName", "s", identity.display_name)
        _set_accounts_property(runner, path, "SetShell", "s", INTERACTIVE_SHELL)
        _set_accounts_property(
            runner, path, "SetAccountType", "i",
            "1" if identity.role == "administrator" else "0",
        )
        _set_accounts_property(runner, path, "SetLocked", "b", "false")

        expected = {
            "Uid": ("t", str(entry.pw_uid)),
            "UserName": ("s", identity.username),
            "RealName": ("s", identity.display_name),
            "LocalAccount": ("b", "true"),
            "SystemAccount": ("b", "false"),
            "AccountType": ("i", "1" if identity.role == "administrator" else "0"),
            "Locked": ("b", "false"),
            "Shell": ("s", INTERACTIVE_SHELL),
        }
        values = {name: _get_property(runner, path, name, sig) for name, (sig, _value) in expected.items()}
        for name, (_signature, wanted) in expected.items():
            if values[name] != wanted:
                raise PreparationError("verify:account", f"{identity.label} failed {name} verification")
        if not _bool(values["LocalAccount"]) or _bool(values["SystemAccount"]) or _bool(values["Locked"]):
            raise PreparationError("verify:account", f"{identity.label} failed role-state verification")

        groups_result = runner.run(["id", "-nG", identity.username])
        groups = set(groups_result.stdout.split())
        if identity.role == "administrator":
            if not {"adm", "sudo"}.issubset(groups):
                raise PreparationError("verify:groups", f"{identity.label} is not a local administrator")
        elif groups & FORBIDDEN_CHILD_GROUPS:
            raise PreparationError("verify:groups", f"{identity.label} retained an administrative group")

        uid = int(entry.pw_uid)
        if uid in seen_uids:
            raise PreparationError("verify:uid-collision", "fixed test identities share a UID")
        if uid_names.get(uid) != {identity.username}:
            raise PreparationError("verify:uid-collision", f"{identity.label} shares a UID with another account")
        seen_uids.add(uid)
        verified[identity.username] = {"uid": uid, "role": identity.role}
        print(f"prep-vm: {identity.label} verified", file=sys.stderr)
    return verified


def marker_document(
    guest: GuestIdentity,
    accounts: dict[str, dict[str, int | str]],
    digest: str,
) -> dict[str, object]:
    expected_users = {identity.username for identity in IDENTITIES}
    if set(accounts) != expected_users or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise PreparationError("marker:schema", "verified preparation data is incomplete")
    document: dict[str, object] = {
        "schema_version": MARKER_VERSION,
        "purpose": MARKER_PURPOSE,
        "guest": {
            "hostname": guest.hostname,
            "machine_id": guest.machine_id,
            "ubuntu_version": guest.ubuntu_version,
            "virtualization": guest.virtualization,
        },
        "preparation_script_sha256": digest,
        "accounts": accounts,
    }
    validate_marker(document)
    return document


def validate_marker(document: dict[str, object]) -> None:
    if set(document) != {"schema_version", "purpose", "guest", "preparation_script_sha256", "accounts"}:
        raise PreparationError("marker:schema", "preparation record has unexpected fields")
    if document["schema_version"] != MARKER_VERSION or document["purpose"] != MARKER_PURPOSE:
        raise PreparationError("marker:schema", "preparation record identity is invalid")
    guest = document["guest"]
    if not isinstance(guest, dict) or set(guest) != {"hostname", "machine_id", "ubuntu_version", "virtualization"}:
        raise PreparationError("marker:schema", "preparation record guest identity is invalid")
    if guest["hostname"] != HOSTNAME or guest["ubuntu_version"] != UBUNTU_VERSION:
        raise PreparationError("marker:schema", "preparation record guest identity is invalid")
    if not isinstance(guest["machine_id"], str) or not re.fullmatch(r"[0-9a-f]{32}", guest["machine_id"]):
        raise PreparationError("marker:schema", "preparation record machine identity is invalid")
    if not isinstance(guest["virtualization"], str) or not re.fullmatch(r"[a-z0-9_-]+", guest["virtualization"]):
        raise PreparationError("marker:schema", "preparation record virtualization identity is invalid")
    digest = document["preparation_script_sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise PreparationError("marker:schema", "preparation record digest is invalid")
    accounts = document["accounts"]
    expected = {identity.username: identity.role for identity in IDENTITIES}
    if not isinstance(accounts, dict) or set(accounts) != set(expected):
        raise PreparationError("marker:schema", "preparation record account map is invalid")
    uids: set[int] = set()
    for username, role in expected.items():
        value = accounts[username]
        if not isinstance(value, dict) or set(value) != {"uid", "role"}:
            raise PreparationError("marker:schema", "preparation record account entry is invalid")
        uid = value["uid"]
        if not isinstance(uid, int) or isinstance(uid, bool) or uid < 1000 or uid in uids or value["role"] != role:
            raise PreparationError("marker:schema", "preparation record account role or UID is invalid")
        uids.add(uid)


def write_marker(path: Path, document: dict[str, object]) -> None:
    validate_marker(document)
    encoded = json.dumps(document, indent=2, sort_keys=True) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.chown(temporary, 0, 0)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    verify_marker_permissions(path.stat())


def verify_marker_permissions(info: os.stat_result) -> None:
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != 0 or info.st_gid != 0:
        raise PreparationError("marker:permissions", "preparation record ownership or mode verification failed")


def main() -> int:
    try:
        print("prep-vm: [stage:guard] validating fixed source guest", file=sys.stderr)
        runner = Runner()
        guest = validate_environment(runner=runner)
        existing = preflight_accounts()
        digest = preparation_digest()
        print("prep-vm: [stage:hostname] setting test guest hostname to ubuntu26.04", file=sys.stderr)
        runner.run(["hostnamectl", "set-hostname", HOSTNAME])
        guest = dataclasses.replace(guest, hostname=HOSTNAME)
        print("prep-vm: [stage:password] enter the shared test-account password once", file=sys.stderr)
        password = getpass.getpass("Shared test-account password: ")
        print("prep-vm: [stage:accounts] reconciling four fixed test identities", file=sys.stderr)
        accounts = reconcile_accounts(existing, password, runner=runner)
        password = ""
        print("prep-vm: [stage:record] writing verified preparation record", file=sys.stderr)
        write_marker(MARKER, marker_document(guest, accounts, digest))
    except (PreparationError, subprocess.SubprocessError, KeyError, OSError) as error:
        if isinstance(error, PreparationError):
            detail = str(error)
        elif isinstance(error, subprocess.SubprocessError):
            detail = "[command:failed] a supported system command failed"
        elif isinstance(error, KeyError):
            detail = "[verify:account] a fixed test identity was unavailable"
        else:
            detail = "[io:failed] a required local operation failed"
        print(f"prep-vm: {detail}", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("prep-vm: [password:input] password entry was interrupted", file=sys.stderr)
        return 1
    finally:
        if "password" in locals():
            password = ""
    print("prep-vm: [outcome:success] accounts-only baseline preparation is verified", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
