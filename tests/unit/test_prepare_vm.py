from tests.support.modules import load_module
import os
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


from tests.support.paths import ROOT
PREPARE_PATH = ROOT / "tests/integration/prepare_vm.py"


prepare = load_module('onpc_test_prepare_vm', PREPARE_PATH)


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


def test_environment_guard_accepts_relocated_checkout_in_product_free_guest(tmp_path):
    root = guest_root(tmp_path)
    checkout = tmp_path / "checkout"
    for relative in prepare.REQUIRED_CHECKOUT_ENTRIES:
        path = checkout / relative
        if relative == ".git":
            path.mkdir(parents=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / relative).read_bytes())
    # Load the fixture's actual preparer so its __file__ ownership check stays
    # intact. Do not require Git metadata in the package build's source tree.
    (checkout / 'config/test-vm.json').write_text(
        '{"name":"another-test-vm","disk_anchor":"/images/base.qcow2"}')
    fixture_prepare = load_module(
        'onpc_fixture_prepare_vm', checkout / 'tests/integration/prepare_vm.py',
    )
    assert fixture_prepare.CHECKOUT == checkout
    assert fixture_prepare.HOSTNAME == 'another-test-vm'
    defaults = dict(
        root=root, checkout=checkout, cwd=checkout, runner=GuardRunner(), euid=0,
        hostname="original-test-guest", lookup_user=missing_user,
    )
    value = fixture_prepare.validate_environment(**defaults)
    assert value == fixture_prepare.GuestIdentity("original-test-guest", "a" * 32, "26.04", "kvm")

    cases = (
        ("guard:root", {"euid": os.getuid() or 1000}),
        ("guard:virtualization", {"runner": GuardRunner(virtual="")}),
        ("guard:checkout", {"cwd": tmp_path}),
    )
    for category, changed in cases:
        with pytest.raises(fixture_prepare.PreparationError, match=category):
            fixture_prepare.validate_environment(**{**defaults, **changed})

    wrong_release = guest_root(tmp_path / "wrong", version="24.04")
    with pytest.raises(fixture_prepare.PreparationError, match="guard:os"):
        fixture_prepare.validate_environment(**{**defaults, "root": wrong_release})


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
    monkeypatch.setattr(prepare, "prepare_test_dependencies", lambda **kwargs: None)
    monkeypatch.setattr(prepare.getpass, "getpass", lambda prompt: "test-password")
    monkeypatch.setattr(prepare, "reconcile_accounts", lambda *args, **kwargs: [])
    monkeypatch.setattr(prepare, "marker_document", lambda guest, *args: guest)
    monkeypatch.setattr(prepare, "write_marker", lambda path, document: records.append(document))

    assert prepare.main() == (1 if hostname_fails else 0)
    assert commands == [["hostnamectl", "set-hostname", prepare.HOSTNAME]]
    if hostname_fails:
        assert records == []
    else:
        assert records[0].hostname == prepare.HOSTNAME


def test_checkout_guard_requires_own_complete_checkout(tmp_path):
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
        if command[0] in {"useradd", "usermod", "install", "chpasswd", "runuser"}:
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
    for identity in prepare.IDENTITIES:
        prefix = ["runuser", "--user", identity.username, "--"]
        config = Path("/home") / identity.username / ".config"
        markers = [config / "gnome-initial-setup-done",
                   config / "gnome-initial-setup/upgrade-26.04-done"]
        assert [*prefix, "touch", "--", *map(str, markers)] in runner.commands
        for marker in markers:
            assert [*prefix, "test", "-f", str(marker)] in runner.commands

    with pytest.raises(prepare.PreparationError, match="verify:groups"):
        prepare.reconcile_accounts(
            existing, secret, runner=AccountRunner(entries, bad_child=True),
            lookup_user=entries.__getitem__, list_users=lambda: list(entries.values()),
        )


def valid_marker():
    guest = prepare.GuestIdentity(prepare.HOSTNAME, "b" * 32, "26.04", "kvm")
    accounts = {
        item.username: {"uid": 1300 + index, "role": item.role}
        for index, item in enumerate(prepare.IDENTITIES)
    }
    return prepare.marker_document(guest, accounts, "c" * 64)


def test_account_reconciliation_repeats_after_creation_without_duplicate_users_or_group_removal(tmp_path):
    root = guest_root(tmp_path)
    entries = {}
    groups = {}

    class StatefulRunner(AccountRunner):
        def run(self, command, **kwargs):
            if command[0] == 'useradd':
                username = command[-1]
                assert username not in entries
                entries[username] = account_entry(username, 1200 + len(entries))
                # Exercise cleanup of inherited administrative memberships.
                groups[username] = {username, 'adm', 'sudo'}
            if command[0] == 'id':
                self.commands.append(command)
                return subprocess.CompletedProcess(command, 0, ' '.join(groups[command[-1]]), '')
            if command[0] == 'gpasswd':
                self.commands.append(command)
                assert kwargs.get('check', True)
                groups[command[2]].remove(command[3])
                return subprocess.CompletedProcess(command, 0, '', '')
            return super().run(command, **kwargs)

    runner = StatefulRunner(entries)
    documents = []
    for attempt in range(2):
        existing = prepare.preflight_accounts(
            root=root, lookup_user=entries.__getitem__, list_users=lambda: list(entries.values()),
        )
        runner.commands.clear()
        verified = prepare.reconcile_accounts(
            existing, 'shared test password', runner=runner,
            lookup_user=entries.__getitem__, list_users=lambda: list(entries.values()),
        )
        documents.append(prepare.marker_document(
            prepare.GuestIdentity(prepare.HOSTNAME, 'a' * 32, '26.04', 'kvm'), verified, 'b' * 64,
        ))
        assert sum(command[0] == 'useradd' for command in runner.commands) == (4 if attempt == 0 else 0)
        assert sum(command[0] == 'gpasswd' for command in runner.commands) == (4 if attempt == 0 else 0)
    assert documents[0] == documents[1]


@pytest.mark.parametrize('failed_command', ['id', 'gpasswd'])
def test_account_group_probe_and_removal_failures_stop_before_password_changes(failed_command):
    entries = {
        item.username: account_entry(item.username, 1200 + index)
        for index, item in enumerate(prepare.IDENTITIES)
    }
    existing = {
        name: prepare.ExistingAccount(name, entry.pw_uid, entry.pw_gid, Path(entry.pw_dir))
        for name, entry in entries.items()
    }

    class FailingRunner(AccountRunner):
        def run(self, command, **kwargs):
            if command[0] == failed_command:
                assert kwargs.get('check', True)
                raise subprocess.CalledProcessError(3, command)
            return super().run(command, **kwargs)

    runner = FailingRunner(entries, bad_child=True)
    with pytest.raises(subprocess.CalledProcessError):
        prepare.reconcile_accounts(existing, 'shared test password', runner=runner,
                                   lookup_user=entries.__getitem__, list_users=lambda: list(entries.values()))
    assert not runner.inputs


def test_marker_schema_is_exact_versioned_and_secret_free():
    document = valid_marker()
    assert set(document) == {
        "schema_version", "purpose", "guest", "preparation_script_sha256", "accounts", "test_dependencies"
    }
    assert document["schema_version"] == 2
    assert document['test_dependencies'] == prepare.guest_tools.VERSIONS
    assert set(document["accounts"]) == {item.username for item in prepare.IDENTITIES}
    serialized = repr(document).lower()
    for forbidden in ("password", "passwd", "secret", "token", "PRIVATE KEY"):
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


def package_status():
    return '\n\n'.join(f'Package: {name}\nStatus: install ok installed\nVersion: {version}\n'
                       for name, version in prepare.guest_tools.VERSIONS.items())


@pytest.mark.parametrize('failure', [None, 'update', 'install', 'verify', 'active'])
def test_dependencies_install_once_retry_without_network_and_stop_on_failure(tmp_path, failure):
    status = tmp_path / 'var/lib/dpkg/status'
    status.parent.mkdir(parents=True)
    status.write_text('Package: bash\nStatus: install ok installed\nVersion: 1\n')
    sources = tmp_path / 'etc/apt/sources.list.d/ubuntu.sources'
    sources.parent.mkdir(parents=True)
    sources.write_text('URIs: http://us.archive.ubuntu.com/ubuntu/\n')
    commands = []

    class DependencyRunner:
        def run(self, command, *, input_text=None, check=True, timeout=120):
            commands.append(command)
            if command[0] == 'debconf-set-selections':
                assert input_text == 'slapd slapd/no_configuration boolean true\n'
            if command[-1] == 'update' and failure == 'update':
                raise subprocess.CalledProcessError(1, command)
            if command[0] == 'env':
                if failure == 'install':
                    raise subprocess.CalledProcessError(1, command)
                if failure != 'verify':
                    status.write_text(package_status())
            if command[:2] == ['systemctl', 'is-active']:
                return subprocess.CompletedProcess(command, 0 if failure == 'active' else 3,
                                                   'active' if failure == 'active' else 'inactive')
            if command[:2] == ['/usr/sbin/sshd', '-T']:
                return subprocess.CompletedProcess(command, 0, 'pubkeyauthentication yes\n'
                    'permitrootlogin prohibit-password\nauthenticationmethods any\n'
                    'authorizedkeysfile .ssh/authorized_keys .ssh/authorized_keys2\n')
            return subprocess.CompletedProcess(command, 0, '')

    runner = DependencyRunner()
    if failure:
        with pytest.raises((prepare.PreparationError, subprocess.CalledProcessError)):
            prepare.prepare_test_dependencies(runner=runner, root=tmp_path)
        assert ['systemctl', 'enable', 'ssh.service'] not in commands
        if failure == 'update':
            assert not any(command[0] == 'env' for command in commands)
    else:
        prepare.prepare_test_dependencies(runner=runner, root=tmp_path)
        assert sum(command[0] == 'env' for command in commands) == 1
        assert commands[-1][:2] == ['/usr/sbin/sshd', '-T']
        assert sources.read_text() == 'URIs: https://archive.ubuntu.com/ubuntu/\n'
        commands.clear()
        prepare.prepare_test_dependencies(runner=runner, root=tmp_path)
        assert not any(command[0] in {'apt-get', 'env', 'debconf-set-selections'} for command in commands)


@pytest.mark.parametrize('path', prepare.guest_tools.DORMANT_PATHS)
def test_dependency_preparation_preserves_existing_directory_configuration(tmp_path, path):
    from unittest.mock import Mock
    configuration = tmp_path / path.lstrip('/')
    configuration.parent.mkdir(parents=True)
    configuration.write_text('unrelated configuration')
    runner = Mock()
    with pytest.raises(prepare.PreparationError, match='configuration-collision'):
        prepare.prepare_test_dependencies(runner=runner, root=tmp_path)
    runner.run.assert_not_called()
    assert configuration.read_text() == 'unrelated configuration'


def test_dependency_failure_prevents_account_changes_and_success_record(monkeypatch):
    from unittest.mock import Mock
    monkeypatch.setattr(prepare, 'validate_environment', Mock())
    monkeypatch.setattr(prepare, 'preflight_accounts', Mock())
    monkeypatch.setattr(prepare, 'preparation_digest', Mock())
    monkeypatch.setattr(prepare, 'prepare_test_dependencies', Mock(side_effect=
                        prepare.PreparationError('guest-tools:failure', 'test failure')))
    accounts, marker, password = Mock(), Mock(), Mock()
    monkeypatch.setattr(prepare, 'reconcile_accounts', accounts)
    monkeypatch.setattr(prepare, 'write_marker', marker)
    monkeypatch.setattr(prepare.getpass, 'getpass', password)
    assert prepare.main() == 1
    accounts.assert_not_called()
    marker.assert_not_called()
    password.assert_not_called()


@pytest.mark.parametrize('change', ['missing', 'wrong-version', 'unconfigured', 'duplicate'])
def test_dependency_inventory_refuses_incomplete_or_ambiguous_status(change):
    status = package_status()
    if change == 'missing':
        status = status.split('\n\n', 1)[1]
    elif change == 'wrong-version':
        status = status.replace(next(iter(prepare.guest_tools.VERSIONS.values())), '0')
    elif change == 'unconfigured':
        status = status.replace('install ok installed', 'install ok unpacked', 1)
    else:
        status += '\n\n' + status.split('\n\n')[0]
    with pytest.raises(ValueError, match='guest-tools:'):
        prepare.guest_tools.verify_packages(status)


def test_dependency_inventory_ignores_description_continuations():
    status = package_status() + '\n\nPackage: unrelated\nDescription: Other package\n Package: openssh-server\n'
    assert prepare.guest_tools.verify_packages(status) == prepare.guest_tools.VERSIONS
