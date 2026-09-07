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
        self.write("etc/pam.d/common-auth", "auth required pam_unix.so\n")
        for name in ("account", "password", "session", "session-noninteractive"):
            self.write("etc/pam.d/common-" + name, "# fixture PAM stack\n")
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

    def integration(self, name, target, contents="product integration\n"):
        self.write("var/lib/oh-no-parent-control/installed-" + name, contents)
        return self.write(target, contents)

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


def test_preinst_registers_dpkg_notice_before_unpack_and_retries_safely(machine):
    notice = machine.root / "etc/dpkg/dpkg.cfg.d/99-oh-no-parent-control-notice"
    assert not notice.exists()
    result = machine.run("preinst", "install")
    assert result.returncode == 0, result.stderr
    content = notice.read_text()
    assert content.startswith("post-invoke=if [ -x ")
    assert "oh-no-parent-control-package-notice --after-dpkg" in content
    assert notice.stat().st_mode & 0o777 == 0o644
    pending = machine.write("run/oh-no-parent-control-package-configuration-complete")
    result = machine.run("preinst", "install")
    assert result.returncode == 0, result.stderr
    assert notice.read_text() == content
    assert not pending.exists()


@pytest.mark.parametrize("action", ["remove", "purge", "abort-install"])
@pytest.mark.parametrize("modified", [False, True])
def test_notice_cleanup_preserves_administrator_replacements(machine, action, modified):
    assert machine.run("preinst", "install").returncode == 0
    notice = machine.root / "etc/dpkg/dpkg.cfg.d/99-oh-no-parent-control-notice"
    if modified:
        notice.write_text("# administrator replacement\n")
    pending = machine.write("run/oh-no-parent-control-package-configuration-complete")
    result = machine.run("postrm", action)
    assert result.returncode == 0, result.stderr
    assert notice.exists() == modified
    if modified:
        assert notice.read_text() == "# administrator replacement\n"
    assert not pending.exists()


def test_notice_bootstrap_and_cleanup_do_not_follow_substituted_configuration(machine):
    protected = machine.write("administrator-file", "preserved\n")
    notice = machine.root / "etc/dpkg/dpkg.cfg.d/99-oh-no-parent-control-notice"
    notice.parent.mkdir(parents=True)
    notice.symlink_to(protected)
    result = machine.run("preinst", "install")
    assert result.returncode != 0
    assert "refusing substituted package notice configuration" in result.stderr
    result = machine.run("postrm", "abort-install")
    assert result.returncode == 0, result.stderr
    assert notice.is_symlink()
    assert protected.read_text() == "preserved\n"


def test_purge_removes_saved_state_logs_and_empty_policy(machine):
    machine.baseline()
    machine.write("var/lib/oh-no-parent-control/preferences/1001.json", "{}")
    machine.write("var/log/oh-no-parent-control/broker/day.log", "redacted fixture")
    machine.integration("fapolicyd-fallback", "etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules")
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


def test_upgrade_never_claims_product_policy_as_original_baseline(machine):
    machine.write("etc/fapolicyd/compiled.rules", "installed product policy")
    result = machine.run("preinst", "upgrade")
    assert result.returncode != 0
    assert "baseline is missing" in result.stderr
    assert not (machine.root / "var/lib/oh-no-parent-control/fapolicyd-before-install").exists()


@pytest.mark.parametrize("notifier", ["missing", "success", "defer", "fail"])
def test_removal_requests_reboot_without_losing_or_duplicating_requests(machine, notifier):
    if notifier != "missing":
        code = "exit 1" if notifier == "fail" else "exit 0"
        if notifier == "success":
            code = 'printf "%s\\n" "$DPKG_MAINTSCRIPT_PACKAGE" >> "$AUDIT_ROOT/run/reboot-required.pkgs"'
        machine.write("usr/share/update-notifier/notify-reboot-required", "#!/bin/sh\n" + code + "\n").chmod(0o755)
    packages = machine.write("run/reboot-required.pkgs", "linux-base\n")
    for _ in range(2):
        result = machine.run("postrm", "remove")
        assert result.returncode == 0, result.stderr
        assert "REBOOT REQUIRED" not in result.stderr
        assert packages.read_text().splitlines() == ["linux-base", "oh-no-parent-control"]
    assert (machine.root / "run/reboot-required").is_file()
    assert "reboot" not in machine.commands


def test_later_purge_does_not_request_another_reboot(machine):
    result = machine.run("postrm", "purge")
    assert result.returncode == 0, result.stderr
    assert not (machine.root / "run/reboot-required").exists()


def test_owned_integrations_removed_but_later_admin_hook_survives_purge(machine):
    hook = machine.integration("gdm-presession", "etc/gdm3/PreSession/Default")
    fallback = machine.integration("fapolicyd-fallback", "etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules")
    result = machine.run("postrm", "remove")
    assert result.returncode == 0, result.stderr
    assert not hook.exists()
    assert not fallback.exists()
    hook.write_text("administrator's new hook\n")
    result = machine.run("postrm", "purge")
    assert result.returncode == 0, result.stderr
    assert hook.read_text() == "administrator's new hook\n"


@pytest.mark.parametrize("script", ["prerm", "postrm"])
@pytest.mark.parametrize("changed", ["contents", "symlink"])
def test_changed_shared_hook_refuses_removal(machine, script, changed):
    hook = machine.integration("gdm-presession", "etc/gdm3/PreSession/Default")
    if changed == "symlink":
        hook.unlink()
        hook.symlink_to(machine.write("unrelated", "keep"))
    else:
        hook.write_text("administrator hook")
    result = machine.run(script, "remove")
    assert result.returncode != 0
    assert hook.exists()
    assert "uninstall --remove" not in machine.commands


@pytest.mark.parametrize("collision", ["hook", "account", "fallback"])
def test_install_rejects_unowned_resources_before_mutating_state(machine, collision):
    if collision == "hook":
        path = machine.write("etc/gdm3/PreSession/Default", "admin hook")
    elif collision == "fallback":
        path = machine.write("etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules", "admin rule")
    else:
        path = machine.write("account", "admin account")
    original = path.read_text()
    result = machine.run("preinst", "install")
    assert result.returncode != 0
    assert path.read_text() == original
    assert not (machine.root / "var/lib/oh-no-parent-control/migration-in-progress").exists()
    assert not machine.commands


def test_mounted_kiosk_home_is_rejected_before_account_deletion(machine):
    machine.kiosk()
    result = machine.run("postrm", "remove", MOUNTED_PATH=str(machine.root / "home/oh-no-parent-control/.cache"))
    assert result.returncode != 0
    assert (machine.root / "account").exists()
    assert "UncacheUser" not in machine.commands
    assert "deluser" not in machine.commands


@pytest.mark.parametrize("choice,option", [("enabled", "--enable"), ("disabled", "--disable")])
def test_removal_restores_only_original_dependency_pam_choice(machine, choice, option):
    machine.write("var/lib/oh-no-parent-control/malcontent-pam-before-install", choice + "\n")
    result = machine.run("prerm", "remove")
    assert result.returncode == 0, result.stderr
    assert f"{option} malcontent" in machine.commands


def test_local_pam_reference_prevents_removing_its_module(machine):
    path = machine.write("etc/pam.d/common-auth", "auth required pam_oh_no_parent_control.so\n")
    result = machine.run("prerm", "remove")
    assert result.returncode != 0
    assert "PAM references remain" in result.stderr
    assert "pam_oh_no_parent_control.so" in path.read_text()


def test_pam_comments_and_inactive_backups_do_not_block_removal(machine):
    machine.write("etc/pam.d/common-auth", "  # auth required pam_oh_no_parent_control.so\n")
    backup = machine.write("etc/pam.d/common-auth.pam-old", "auth required pam_oh_no_parent_control.so\n")
    result = machine.run("prerm", "remove")
    assert result.returncode == 0, result.stderr
    assert backup.exists()


def test_policy_restore_does_not_follow_compiled_policy_symlink(machine):
    machine.baseline(rules="original policy")
    outside = machine.write("unrelated", "keep")
    target = machine.root / "etc/fapolicyd/compiled.rules"
    target.unlink()
    target.symlink_to(outside)
    result = machine.run("postrm", "remove")
    assert result.returncode != 0
    assert outside.read_text() == "keep"


def test_retry_discards_incomplete_baseline_flags(machine):
    machine.write("var/lib/oh-no-parent-control/fapolicyd-before-install.pending/active")
    machine.write("var/lib/oh-no-parent-control/fapolicyd-before-install.pending/compiled.rules", "stale")
    result = machine.run("preinst", "install")
    assert result.returncode == 0, result.stderr
    baseline = machine.root / "var/lib/oh-no-parent-control/fapolicyd-before-install"
    assert not (baseline / "active").exists()
    assert not (baseline / "compiled.rules").exists()


def test_remove_cleans_transient_state_but_preserves_customer_data(machine):
    machine.write("var/lib/oh-no-parent-control/data-migration.lock")
    machine.write("var/lib/oh-no-parent-control/fapolicyd-before-install.pending/active")
    machine.write("var/lib/oh-no-parent-control/malcontent-pam-before-install", "disabled\n")
    prefs = machine.write("var/lib/oh-no-parent-control/preferences/1001.json", "{}")
    log = machine.write("var/log/oh-no-parent-control/broker/day.log", "fixture")
    result = machine.run("postrm", "remove")
    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in (machine.root / "var/lib/oh-no-parent-control").iterdir()) == ["preferences"]
    assert prefs.exists() and log.exists()


def test_aborted_first_unpack_cleans_only_attempt_bookkeeping(machine):
    prefs = machine.write("var/lib/oh-no-parent-control/preferences/1001.json", "{}")
    policy = machine.write("etc/fapolicyd/compiled.rules", "original policy")
    assert machine.run("preinst", "install").returncode == 0
    result = machine.run("postrm", "abort-install")
    assert result.returncode == 0, result.stderr
    assert policy.read_text() == "original policy"
    assert prefs.read_text() == "{}"
    assert sorted(p.name for p in (machine.root / "var/lib/oh-no-parent-control").iterdir()) == ["preferences"]
    assert "disable fapolicyd" not in machine.commands
