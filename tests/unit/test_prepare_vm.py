import importlib.util
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
PREPARE_PATH = ROOT / "tests/integration/prepare_vm.py"


def load_module():
    spec = importlib.util.spec_from_file_location("onpc_prepare_vm", PREPARE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prepare = load_module()


class GuardRunner:
    def __init__(self, *, virtual="kvm", package=False, service=False):
        self.virtual = virtual
        self.package = package
        self.service = service

    def run(self, command, *, input_text=None, check=True):
        assert input_text is None
        if command[0] == "systemd-detect-virt":
            return subprocess.CompletedProcess(command, 0 if self.virtual else 1, self.virtual + "\n", "")
        if command[0] == "dpkg-query":
            return subprocess.CompletedProcess(command, 0 if self.package else 1, "installed\n" if self.package else "", "")
        if command[0] == "systemctl":
            return subprocess.CompletedProcess(command, 0, "loaded\n" if self.service else "not-found\n", "")
        raise AssertionError(command)


def missing_user(_name):
    raise KeyError


def guest_root(tmp_path, *, version="26.04"):
    (tmp_path / "etc").mkdir(parents=True)
    (tmp_path / "etc/os-release").write_text(
        f'ID=ubuntu\nVERSION_ID="{version}"\n', encoding="utf-8"
    )
    (tmp_path / "etc/machine-id").write_text("a" * 32 + "\n", encoding="ascii")
    (tmp_path / "etc/login.defs").write_text("UID_MIN 1000\n", encoding="utf-8")
    return tmp_path


def test_exact_fixed_identity_map():
    assert prepare.IDENTITIES is prepare.TEST_IDENTITIES
    assert [identity.display_name for identity in prepare.IDENTITIES] == [
        f"{identity.given_name} ({identity.display_role})"
        for identity in prepare.IDENTITIES
    ]


def test_environment_guard_accepts_only_the_fixed_guest_context(tmp_path):
    root = guest_root(tmp_path)
    defaults = dict(
        root=root, checkout=ROOT, cwd=ROOT, runner=GuardRunner(), euid=0,
        hostname="original-test-guest", lookup_user=missing_user,
    )
    value = prepare.validate_environment(**defaults)
    assert value == prepare.GuestIdentity("original-test-guest", "a" * 32, "26.04", "kvm")

    cases = (
        ("guard:root", {"euid": os.getuid() or 1000}),
        ("guard:virtualization", {"runner": GuardRunner(virtual="")}),
        ("guard:checkout", {"cwd": tmp_path}),
    )
    for category, changed in cases:
        with pytest.raises(prepare.PreparationError, match=category):
            prepare.validate_environment(**{**defaults, **changed})

    wrong_release = guest_root(tmp_path / "wrong", version="24.04")
    with pytest.raises(prepare.PreparationError, match="guard:os"):
        prepare.validate_environment(**{**defaults, "root": wrong_release})


@pytest.mark.parametrize("hostname_fails", [False, True])
def test_main_sets_hostname_before_recording_baseline(monkeypatch, hostname_fails):
    commands = []
    records = []

    class HostnameRunner:
        def run(self, command):
            commands.append(command)
            if hostname_fails:
                raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(prepare, "Runner", HostnameRunner)
    monkeypatch.setattr(prepare, "validate_environment", lambda **kwargs:
                        prepare.GuestIdentity("original-test-guest", "a" * 32, "26.04", "kvm"))
    monkeypatch.setattr(prepare, "preflight_accounts", lambda: {})
    monkeypatch.setattr(prepare, "preparation_digest", lambda: "digest")
    monkeypatch.setattr(prepare.getpass, "getpass", lambda prompt: "test-password")
    monkeypatch.setattr(prepare, "reconcile_accounts", lambda *args, **kwargs: [])
    monkeypatch.setattr(prepare, "marker_document", lambda guest, *args: guest)
    monkeypatch.setattr(prepare, "write_marker", lambda path, document: records.append(document))

    assert prepare.main() == (1 if hostname_fails else 0)
    assert commands == [["hostnamectl", "set-hostname", "ubuntu26.04"]]
    if hostname_fails:
        assert records == []
    else:
        assert records[0].hostname == "ubuntu26.04"


def test_checkout_guard_requires_fixed_complete_checkout(tmp_path):
    with pytest.raises(prepare.PreparationError, match="guard:checkout"):
        prepare.validate_checkout(tmp_path, ROOT)
    assert prepare.preparation_digest(ROOT) == prepare.preparation_digest(ROOT)
    assert len(prepare.preparation_digest(ROOT)) == 64


def test_every_installed_product_residue_category_is_refused(tmp_path):
    for category, paths in prepare.RESIDUE_PATHS.items():
        root = tmp_path / category
        target = root / paths[0].removeprefix("/")
        target.parent.mkdir(parents=True)
        target.touch()
        assert prepare.find_residue(root, GuardRunner(), missing_user) == category

    clean = tmp_path / "clean"
    clean.mkdir()
    assert prepare.find_residue(clean, GuardRunner(package=True), missing_user) == "package"
    assert prepare.find_residue(clean, GuardRunner(service=True), missing_user) == "service-session"
    assert prepare.find_residue(clean, GuardRunner(), lambda _name: object()) == "kiosk-account"

    pam = tmp_path / "pam"
    pam_file = pam / "etc/pam.d/common-account"
    pam_file.parent.mkdir(parents=True)
    pam_file.write_text("account required pam_oh_no_parent_control.so\n", encoding="utf-8")
    assert prepare.find_residue(pam, GuardRunner(), missing_user) == "pam-polkit"


def account_entry(name, uid, *, gid=None, home=None):
    return SimpleNamespace(
        pw_name=name,
        pw_uid=uid,
        pw_gid=uid if gid is None else gid,
        pw_dir=str(Path("/home") / name if home is None else home),
        pw_shell="/bin/false",
        pw_gecos="old value",
    )


def test_account_preflight_refuses_system_uid_collision_home_and_ownership(tmp_path):
    root = guest_root(tmp_path)
    names = [item.username for item in prepare.IDENTITIES]

    def lookup(name):
        return account_entry(name, 1100 + names.index(name))

    values = prepare.preflight_accounts(
        root=root, lookup_user=lookup, list_users=lambda: [lookup(name) for name in names]
    )
    assert set(values) == set(names)

    failures = (
        ("account:system-identity", lambda name: account_entry(name, 999)),
        ("account:home", lambda name: account_entry(name, 1200, home="/srv/conflict")),
        ("account:uid-collision", lambda name: account_entry(name, 1200)),
    )
    for category, factory in failures:
        with pytest.raises(prepare.PreparationError, match=category):
            prepare.preflight_accounts(
                root=root,
                lookup_user=lambda name, f=factory: f(name),
                list_users=lambda f=factory: [f(name) for name in names],
            )

    unsafe_home = root / "home" / names[0]
    unsafe_home.parent.mkdir()
    unsafe_home.write_text("not a directory", encoding="utf-8")
    with pytest.raises(prepare.PreparationError, match="account:home-ownership"):
        prepare.preflight_accounts(
            root=root, lookup_user=lookup, list_users=lambda: [lookup(name) for name in names]
        )

    with pytest.raises(prepare.PreparationError, match="account:uid-collision"):
        prepare.preflight_accounts(
            root=root,
            lookup_user=lookup,
            list_users=lambda: [
                *(lookup(name) for name in names),
                account_entry("unrelated-account", 1100),
            ],
        )


def test_idempotent_account_command_construction_is_explicit():
    absent = {item.username: None for item in prepare.IDENTITIES}
    first = prepare.account_commands(absent)
    repeat_state = {
        item.username: prepare.ExistingAccount(item.username, 1100 + index, 1100 + index, Path("/home") / item.username)
        for index, item in enumerate(prepare.IDENTITIES)
    }
    repeated = prepare.account_commands(repeat_state)
    assert sum(command[0] == "useradd" for command in first) == 4
    assert all(command[0] != "useradd" for command in repeated)
    assert sum(command[0] == "usermod" for command in repeated) == 6
    assert sum(command[0] == "gpasswd" for command in repeated) == 4
    assert repeated == prepare.account_commands(repeat_state)


class AccountRunner:
    def __init__(self, entries, *, bad_child=False):
        self.entries = entries
        self.commands = []
        self.inputs = []
        self.bad_child = bad_child

    def run(self, command, *, input_text=None, check=True):
        command = list(command)
        self.commands.append(command)
        if input_text is not None:
            self.inputs.append((command, input_text))
        if command[0] == "gpasswd":
            return subprocess.CompletedProcess(command, 3, "", "not a member")
        if command[0] in {"useradd", "usermod", "install", "chpasswd"}:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[0] == "id":
            username = command[-1]
            identity = next(value for value in prepare.IDENTITIES if value.username == username)
            if identity.role == "administrator":
                groups = f"{username} adm sudo"
            else:
                groups = f"{username} sudo" if self.bad_child else username
            return subprocess.CompletedProcess(command, 0, groups + "\n", "")
        if command[:3] == ["busctl", "--system", "call"]:
            if "CacheUser" in command:
                username = command[-1]
                uid = self.entries[username].pw_uid
                return subprocess.CompletedProcess(command, 0, f'o "/org/freedesktop/Accounts/User{uid}"\n', "")
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:3] == ["busctl", "--system", "get-property"]:
            uid = int(command[4].rsplit("User", 1)[1])
            username = next(name for name, value in self.entries.items() if value.pw_uid == uid)
            identity = next(value for value in prepare.IDENTITIES if value.username == username)
            name = command[-1]
            values = {
                "Uid": ("t", str(uid)),
                "UserName": ("s", username),
                "RealName": ("s", identity.display_name),
                "IconFile": ("s", identity.icon_file),
                "LocalAccount": ("b", "true"),
                "SystemAccount": ("b", "false"),
                "AccountType": ("i", "1" if identity.role == "administrator" else "0"),
                "Locked": ("b", "false"),
                "Shell": ("s", "/bin/bash"),
            }
            signature, value = values[name]
            output = f'{signature} "{value}"\n' if signature == "s" else f"{signature} {value}\n"
            return subprocess.CompletedProcess(command, 0, output, "")
        raise AssertionError(command)


def test_reconciliation_verifies_roles_and_passes_one_shared_secret_only_on_stdin():
    entries = {
        item.username: account_entry(item.username, 1200 + index)
        for index, item in enumerate(prepare.IDENTITIES)
    }
    existing = {
        name: prepare.ExistingAccount(name, entry.pw_uid, entry.pw_gid, Path(entry.pw_dir))
        for name, entry in entries.items()
    }
    runner = AccountRunner(entries)
    secret = "one shared test secret"
    verified = prepare.reconcile_accounts(
        existing, secret, runner=runner, lookup_user=entries.__getitem__,
        list_users=lambda: list(entries.values()),
    )
    assert {value["role"] for value in verified.values()} == {"administrator", "standard"}
    assert len(runner.inputs) == 1
    assert runner.inputs[0][0] == ["chpasswd"]
    lines = runner.inputs[0][1].splitlines()
    assert len(lines) == 4
    assert all(line.endswith(":" + secret) for line in lines)
    assert all(secret not in argument for command in runner.commands for argument in command)
    assert sum("SetAccountType" in command for command in runner.commands) == 4
    assert sum("SetLocked" in command for command in runner.commands) == 4
    assert {command[-1] for command in runner.commands if "SetIconFile" in command} == {identity.icon_file for identity in prepare.IDENTITIES}
    assert sum("SetShell" in command for command in runner.commands) == 4
    assert sum(command[0] == "install" for command in runner.commands) == 4

    with pytest.raises(prepare.PreparationError, match="verify:groups"):
        prepare.reconcile_accounts(
            existing, secret, runner=AccountRunner(entries, bad_child=True),
            lookup_user=entries.__getitem__, list_users=lambda: list(entries.values()),
        )


def valid_marker():
    guest = prepare.GuestIdentity("ubuntu26.04", "b" * 32, "26.04", "kvm")
    accounts = {
        item.username: {"uid": 1300 + index, "role": item.role}
        for index, item in enumerate(prepare.IDENTITIES)
    }
    return prepare.marker_document(guest, accounts, "c" * 64)


def test_marker_schema_is_exact_versioned_and_secret_free():
    document = valid_marker()
    assert set(document) == {
        "schema_version", "purpose", "guest", "preparation_script_sha256", "accounts"
    }
    assert document["schema_version"] == 1
    assert set(document["accounts"]) == {item.username for item in prepare.IDENTITIES}
    serialized = repr(document).lower()
    for forbidden in ("password", "passwd", "secret", "token", "ssh"):
        assert forbidden not in serialized
    with pytest.raises(prepare.PreparationError, match="marker:schema"):
        prepare.validate_marker({**document, "extra": True})
    changed = dict(document)
    changed["accounts"] = dict(document["accounts"])
    changed["accounts"]["onpc-child-riley"] = {"uid": 1300, "role": "standard"}
    with pytest.raises(prepare.PreparationError, match="marker:schema"):
        prepare.validate_marker(changed)


def test_marker_permission_contract_requires_root_owned_0600_regular_file():
    good = os.stat_result((stat.S_IFREG | 0o600, 0, 0, 1, 0, 0, 0, 0, 0, 0))
    prepare.verify_marker_permissions(good)
    for mode, uid, gid in (
        (stat.S_IFREG | 0o640, 0, 0),
        (stat.S_IFDIR | 0o600, 0, 0),
        (stat.S_IFREG | 0o600, 1000, 0),
        (stat.S_IFREG | 0o600, 0, 1000),
    ):
        value = os.stat_result((mode, 0, 0, 1, uid, gid, 0, 0, 0, 0))
        with pytest.raises(prepare.PreparationError, match="marker:permissions"):
            prepare.verify_marker_permissions(value)
