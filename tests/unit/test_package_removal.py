"""Execute maintainer scripts against a temporary filesystem and fake services.

No real account, service, process, or system path is changed by these tests.
"""

import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]


class Machine:
    def __init__(self, root):
        self.root = root
        for path in ("etc/fapolicyd/rules.d", "run/systemd/system",
                     "var/lib/oh-no-parent-control", "usr/sbin", "var/mail"):
            (root / path).mkdir(parents=True, exist_ok=True)
        self.write("usr/sbin/fagenrules", """#!/bin/sh
set -e
printf '%s\\n' fagenrules >> "$AUDIT_ROOT/commands"
cat "$AUDIT_ROOT"/etc/fapolicyd/rules.d/*.rules > "$AUDIT_ROOT/etc/fapolicyd/compiled.rules"
""")
        (root / "usr/sbin/fagenrules").chmod(0o755)
        self.write("usr/sbin/fapolicyd-cli", """#!/bin/sh
printf '%s\\n' 'fapolicyd-cli --reload-rules' >> "$AUDIT_ROOT/commands"
""").chmod(0o755)
        self.write("usr/libexec/oh-no-parent-control-uninstall", """#!/bin/sh
printf '%s\\n' "uninstall $*" >> "$AUDIT_ROOT/commands"
exit "${UNINSTALL_FAILURE:-0}"
""").chmod(0o755)
        self.write("test-bin/mountpoint", """#!/bin/sh
test -n "$MOUNTED_PATH" && test "$2" = "$MOUNTED_PATH"
""").chmod(0o755)

    def write(self, path, text=""):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        return target

    def baseline(self, *, active=False, enabled=False, rules=None):
        self.write("var/lib/oh-no-parent-control/fapolicyd-before-install/complete")
        if active:
            self.write("var/lib/oh-no-parent-control/fapolicyd-before-install/active")
        if enabled:
            self.write("var/lib/oh-no-parent-control/fapolicyd-before-install/enabled")
        if rules is not None:
            self.write("var/lib/oh-no-parent-control/fapolicyd-before-install/compiled.rules", rules)
        self.write("etc/fapolicyd/compiled.rules", "product rules\n")
        self.write("etc/fapolicyd/compiled.rules.prev", "old product rules\n")

    def kiosk(self):
        self.write("var/lib/oh-no-parent-control/package-created-kiosk-uid", "1006\n").chmod(0o600)
        self.write("account")
        self.write("home/oh-no-parent-control/.cache/residue", "left behind")

    def run(self, script, action, **env):
        source = (ROOT / "debian" / script).read_text()
        # Redirect every absolute system prefix, including executable paths.
        for prefix in ("/etc/", "/var/", "/run/", "/home/", "/usr/"):
            source = source.replace(prefix, str(self.root) + prefix)
        for command in ("deb-systemd-invoke", "invoke-rc.d", "pam-auth-update"):
            source = source.replace(command, command.replace("-", "_").replace(".", "_"))
        mocks = r'''
record() { printf '%s\n' "$*" >> "$AUDIT_ROOT/commands"; }
systemctl() {
    record systemctl "$@"
    case "$1" in
        is-active)
            case "$3" in
                user@*) test "${KIOSK_ACTIVE:-0}" = 1 ;;
                *) test "${SERVICE_ACTIVE:-0}" = 1 ;;
            esac ;;
        is-enabled) test "${SERVICE_ENABLED:-0}" = 1 ;;
        is-failed) test "${BROKER_FAILED:-0}" = 1 ;;
        mask) ln -s /dev/null "$AUDIT_ROOT/run/systemd/system/oh-no-parent-control-broker.service" ;;
        unmask) rm "$AUDIT_ROOT/run/systemd/system/oh-no-parent-control-broker.service" ;;
        *) return 0 ;;
    esac
}
deb_systemd_invoke() { record deb-systemd-invoke "$@"; SERVICE_ACTIVE=0; }
invoke_rc_d() { record invoke-rc.d "$@"; }
pam_auth_update() { record pam-auth-update "$@"; }
busctl() { record busctl "$@"; }
getent() {
    if [ -f "$AUDIT_ROOT/account" ]; then
        printf 'oh-no-parent-control:x:1006:1006::%s/home/oh-no-parent-control:/bin/bash\n' "$AUDIT_ROOT"
    elif [ "${UID_REASSIGNED:-0}" = 1 ] && [ "$2" = 1006 ]; then
        printf 'replacement:x:1006:1006::/somewhere:/bin/bash\n'
    else
        return 2
    fi
}
deluser() { record deluser "$@"; rm "$AUDIT_ROOT/account"; }
stat() {
    if [ "$2" = '%u:%a' ]; then printf '0:600\n';
    elif [ "$2" = %u ]; then printf '%s\n' "${HOME_UID:-1006}";
    else command stat "$@"; fi
}
install() {
    # preinst's root-owned directory creation, confined to this fixture.
    record install "$@"
    for last do :; done
    command install -d -m 0700 "$last"
}
'''
        target = self.write("script", "#!/bin/sh\n" + mocks + source)
        return subprocess.run(
            ["/bin/sh", str(target), action], capture_output=True, text=True,
            env={**os.environ, "AUDIT_ROOT": str(self.root),
                 "PATH": str(self.root / "test-bin") + os.pathsep + os.environ["PATH"],
                 **env}, timeout=10,
        )

    @property
    def commands(self):
        path = self.root / "commands"
        return path.read_text() if path.exists() else ""


@pytest.fixture
def machine(tmp_path):
    return Machine(tmp_path)


def test_purge_removes_saved_state_logs_and_empty_policy(machine):
    machine.baseline()
    machine.write("var/lib/oh-no-parent-control/preferences/1001.json", "{}")
    machine.write("var/log/oh-no-parent-control/broker/day.log", "redacted fixture")
    machine.write("etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules", "product")
    result = machine.run("postrm", "purge")
    assert result.returncode == 0, result.stderr
    assert not (machine.root / "var/lib/oh-no-parent-control").exists()
    assert not (machine.root / "var/log/oh-no-parent-control").exists()
    assert not (machine.root / "etc/fapolicyd/compiled.rules").exists()
    assert not (machine.root / "etc/fapolicyd/compiled.rules.prev").exists()
    assert "deb-systemd-invoke stop fapolicyd.service" in machine.commands
    assert "systemctl disable fapolicyd.service" in machine.commands
    assert machine.commands.index("systemctl daemon-reload") < machine.commands.index("stop fapolicyd.service")


def test_remove_retains_preferences_until_later_purge(machine):
    path = machine.write("var/lib/oh-no-parent-control/preferences/1001.json", "{}")
    assert machine.run("postrm", "remove").returncode == 0
    assert path.exists()
    assert machine.run("postrm", "purge").returncode == 0
    assert not path.exists()
    assert machine.run("postrm", "purge").returncode == 0


def test_restores_preexisting_compiled_policy_and_service(machine):
    machine.baseline(active=True, enabled=True, rules="administrator policy\n")
    result = machine.run("postrm", "remove")
    assert result.returncode == 0, result.stderr
    assert (machine.root / "etc/fapolicyd/compiled.rules").read_text() == "administrator policy\n"
    assert "fapolicyd-cli --reload-rules" in machine.commands
    assert "stop fapolicyd" not in machine.commands
    assert "disable fapolicyd" not in machine.commands


def test_preserves_other_rule_sources_added_after_install(machine):
    machine.baseline()
    machine.write("etc/fapolicyd/rules.d/10-admin.rules", "administrator policy\n")
    result = machine.run("postrm", "remove")
    assert result.returncode == 0, result.stderr
    assert (machine.root / "etc/fapolicyd/compiled.rules").read_text() == "administrator policy\n"
    assert "stop fapolicyd" not in machine.commands
    assert "disable fapolicyd" not in machine.commands


def test_kiosk_home_is_removed_even_when_deluser_leaves_it(machine):
    machine.kiosk()
    result = machine.run("postrm", "remove")
    assert result.returncode == 0, result.stderr
    assert not (machine.root / "home/oh-no-parent-control").exists()
    assert not (machine.root / "account").exists()
    assert "terminate-user" not in machine.commands
    assert machine.commands.index("UncacheUser") < machine.commands.index("deluser")


def test_kiosk_removal_retry_without_passwd_entry(machine):
    machine.kiosk()
    (machine.root / "account").unlink()
    result = machine.run("postrm", "remove")
    assert result.returncode == 0, result.stderr
    assert not (machine.root / "home/oh-no-parent-control").exists()


@pytest.mark.parametrize("script", ["prerm", "postrm"])
def test_active_kiosk_refuses_removal_without_signalling_processes(machine, script):
    machine.kiosk()
    result = machine.run(script, "remove", KIOSK_ACTIVE="1")
    assert result.returncode != 0
    assert "log out" in result.stderr
    assert (machine.root / "account").exists()
    assert "deluser" not in machine.commands
    assert "terminate" not in machine.commands


def test_reassigned_uid_preserves_home_and_marker(machine):
    machine.kiosk()
    (machine.root / "account").unlink()
    result = machine.run("postrm", "purge", UID_REASSIGNED="1")
    assert result.returncode != 0
    assert (machine.root / "home/oh-no-parent-control/.cache/residue").exists()
    assert (machine.root / "var/lib/oh-no-parent-control/package-created-kiosk-uid").exists()


def test_changed_home_owner_is_preserved(machine):
    machine.kiosk()
    result = machine.run("postrm", "remove", HOME_UID="2000")
    assert result.returncode != 0
    assert (machine.root / "account").exists()


def test_purge_does_not_follow_saved_state_symlink(machine):
    outside = machine.write("unrelated/keep", "keep")
    (machine.root / "var/lib/oh-no-parent-control/linked").symlink_to(outside.parent)
    assert machine.run("postrm", "purge").returncode == 0
    assert outside.read_text() == "keep"


def test_purge_refuses_substituted_log_directory(machine):
    outside = machine.write("unrelated/keep", "keep")
    (machine.root / "var/log").mkdir()
    (machine.root / "var/log/oh-no-parent-control").symlink_to(outside.parent)
    result = machine.run("postrm", "purge")
    assert result.returncode != 0
    assert outside.read_text() == "keep"


def test_removal_clears_only_its_mask_and_failed_unit(machine):
    machine.write("var/lib/oh-no-parent-control/uninstall-broker-mask")
    mask = machine.root / "run/systemd/system/oh-no-parent-control-broker.service"
    mask.symlink_to("/dev/null")
    result = machine.run("postrm", "remove", BROKER_FAILED="1")
    assert result.returncode == 0, result.stderr
    assert not mask.is_symlink()
    assert "reset-failed oh-no-parent-control-broker.service" in machine.commands


def test_administrator_mask_is_preserved(machine):
    mask = machine.root / "run/systemd/system/oh-no-parent-control-broker.service"
    mask.symlink_to("/dev/null")
    result = machine.run("postrm", "remove")
    assert result.returncode == 0, result.stderr
    assert mask.is_symlink()


def test_prerm_masks_before_stopping_and_clearing_enforcement(machine):
    result = machine.run("prerm", "remove")
    assert result.returncode == 0, result.stderr
    commands = machine.commands
    assert commands.index("systemctl mask") < commands.index("deb-systemd-invoke stop")
    assert commands.index("deb-systemd-invoke stop") < commands.index("uninstall --remove")
    assert (machine.root / "var/lib/oh-no-parent-control/uninstall-broker-mask").exists()


def test_failed_remove_keeps_guard_until_verified_rollback(machine):
    result = machine.run("prerm", "remove", UNINSTALL_FAILURE="1")
    assert result.returncode != 0
    mask = machine.root / "run/systemd/system/oh-no-parent-control-broker.service"
    assert mask.is_symlink()
    result = machine.run("postinst", "abort-remove", UNINSTALL_FAILURE="1")
    assert result.returncode != 0
    assert mask.is_symlink()
    result = machine.run("postinst", "abort-remove")
    assert result.returncode == 0, result.stderr
    assert not mask.is_symlink()
    assert machine.commands.index("uninstall --restore") < machine.commands.index("systemctl unmask")


def test_runtime_override_refuses_removal(machine):
    machine.write("run/systemd/system/oh-no-parent-control-broker.service", "admin override")
    result = machine.run("prerm", "remove")
    assert result.returncode != 0
    assert "runtime unit override" in result.stderr
    assert "uninstall --remove" not in machine.commands


def test_first_install_captures_original_policy_once(machine):
    machine.write("etc/fapolicyd/compiled.rules", "original policy")
    machine.write("etc/fapolicyd/compiled.rules.prev", "original backup")
    result = machine.run("preinst", "install", SERVICE_ACTIVE="1", SERVICE_ENABLED="1")
    assert result.returncode == 0, result.stderr
    baseline = machine.root / "var/lib/oh-no-parent-control/fapolicyd-before-install"
    assert (baseline / "compiled.rules").read_text() == "original policy"
    assert (baseline / "compiled.rules.prev").read_text() == "original backup"
    assert (baseline / "active").exists()
    assert (baseline / "enabled").exists()
    machine.write("etc/fapolicyd/compiled.rules", "product policy")
    result = machine.run("preinst", "upgrade")
    assert result.returncode == 0, result.stderr
    assert (baseline / "compiled.rules").read_text() == "original policy"


def test_failed_policy_reload_keeps_baseline_for_retry(machine):
    machine.baseline(active=True, enabled=True, rules="original policy")
    machine.write("usr/sbin/fapolicyd-cli", "#!/bin/sh\nexit 1\n").chmod(0o755)
    result = machine.run("postrm", "remove")
    assert result.returncode != 0
    assert (machine.root / "var/lib/oh-no-parent-control/fapolicyd-before-install/complete").exists()


def test_purge_refuses_nested_bind_mount_before_deleting_any_content(machine):
    path = machine.write("var/lib/oh-no-parent-control/preferences/1001.json", "{}")
    result = machine.run("postrm", "purge", MOUNTED_PATH=str(path.parent))
    assert result.returncode != 0
    assert "mounted directory" in result.stderr
    assert path.read_text() == "{}"
