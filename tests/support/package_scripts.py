"""Unprivileged maintainer-script machines with explicit service/account doubles.

Both configuration and removal execute real scripts against temporary files.
Their differing command models stay explicit; they share path relocation.
"""

import os
from pathlib import Path
import subprocess

import pytest
from tests.support.paths import ROOT
from tests.support.shell import relocate_system_paths

REBOOT_NOTICE = "*** REBOOT REQUIRED: reboot before using the kiosk session. ***"


class Machine:
    def __init__(self, root):
        self.root = root
        self.write("etc/os-release", 'ID=ubuntu\nVERSION_ID="26.04"\n')
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
        source = relocate_system_paths(source, self.root)
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


@pytest.fixture
def package_machine(tmp_path):
    state = tmp_path / "var/lib/oh-no-parent-control"
    state.mkdir(parents=True)
    (tmp_path / "run/systemd/system").mkdir(parents=True)
    for name in ("migration-in-progress", "package-activation-pending",
                 "previous-package-activation.json"):
        (state / name).touch()

    (state / "package-created-kiosk-uid").write_text("1006\n")
    for name in ("gdm-presession", "99-oh-no-parent-control-allow.rules"):
        path = tmp_path / "usr/share/oh-no-parent-control" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("product integration\n")
    (tmp_path / "etc/pam.d").mkdir(parents=True)

    # Every executable used by postinst is either this stub or a filesystem
    # utility operating on the rewritten paths. PATH contains no host service
    # or account-management commands.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "stub"
    stub.write_text(r'''#!/bin/sh
name=${0##*/}
printf '%s\n' "$name $*" >> "$AUDIT_ROOT/commands"
case "$name" in
    getent)
        printf 'oh-no-parent-control:x:1006:1006::%s/home/oh-no-parent-control:/bin/bash\n' "$AUDIT_ROOT"
        ;;
    stat) printf '0:600\n' ;;
    debconf-communicate) printf '%s\n' "${PAM_PROFILES:-0 unix, malcontent}" ;;
    pam-auth-update)
        if [ "${PAM_LOCAL_CHANGES:-0}" != 1 ]; then
            printf 'auth required pam_oh_no_parent_control.so\n' > "$AUDIT_ROOT/etc/pam.d/common-auth"
            printf 'account required pam_exec.so %s/usr/libexec/oh-no-parent-control-login-check\n' "$AUDIT_ROOT" > "$AUDIT_ROOT/etc/pam.d/common-account"
        fi
        ;;
    install)
        directory=
        mode=0755
        while [ "$#" -gt 0 ]; do
            case "$1" in
                -d) directory=-d; shift ;;
                -o|-g) shift 2 ;;
                -m) mode="$2"; shift 2 ;;
                *) break ;;
            esac
        done
        exec /usr/bin/install ${directory:+"$directory"} -m "$mode" "$@"
        ;;
    id) printf '1006\n' ;;
    policy-rc.d) exit "${POLICY_STATUS:-0}" ;;
    oh-no-parent-control-migrate-state) exit "${MIGRATION_STATUS:-0}" ;;
    oh-no-parent-control-package-activation) printf '%s\n' "$IMPACTS" ;;
    notify-reboot-required)
        test "$DPKG_MAINTSCRIPT_PACKAGE" = oh-no-parent-control || exit 91
        test "${NOTIFIER_STATUS:-0}" = 0 || exit "$NOTIFIER_STATUS"
        if [ "${NOTIFIER_DEFER:-0}" != 1 ]; then
            printf '*** System restart required ***\n' > "$AUDIT_ROOT/run/reboot-required"
            printf '%s\n' "$DPKG_MAINTSCRIPT_PACKAGE" >> "$AUDIT_ROOT/run/reboot-required.pkgs"
        fi
        ;;
    systemctl)
        case "$*" in
            '--system start oh-no-parent-control-broker.service'|\
            '--system restart oh-no-parent-control-broker.service')
                test ! -e "$AUDIT_ROOT/var/lib/oh-no-parent-control/migration-in-progress" || exit 90
                exit "${BROKER_STATUS:-0}"
                ;;
        esac
        ;;
    deb-systemd-invoke)
        # Reproduce the installed helper's behavior for an inactive static unit.
        case "$*" in
            *oh-no-parent-control-broker.service*)
                printf 'inactive static unit skipped\n' >&2
                ;;
        esac
        ;;
    chown|chmod|systemd-sysusers|invoke-rc.d|usermod|passwd|runuser|\
    oh-no-parent-control-provision) ;;
    *) exit 99 ;;
esac
''')
    stub.chmod(0o755)
    for name in ("getent", "id", "systemctl", "deb-systemd-invoke", "install",
                 "chown", "chmod", "systemd-sysusers", "invoke-rc.d", "pam-auth-update",
                 "stat", "debconf-communicate", "usermod", "passwd", "runuser"):
        (bin_dir / name).symlink_to(stub)
    for name in ("rm", "touch", "grep", "cut", "cat", "cmp"):
        (bin_dir / name).symlink_to(Path("/usr/bin") / name)
    for name in ("migrate-state", "provision", "package-activation"):
        target = tmp_path / f"usr/libexec/oh-no-parent-control-{name}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(stub)
    notice = tmp_path / "usr/libexec/oh-no-parent-control-package-notice"
    notice.write_text(
        (ROOT / "tools/package_notice").read_text().replace("/run/", str(tmp_path) + "/run/")
    )
    notice.chmod(0o755)
    policy = tmp_path / "usr/sbin/policy-rc.d"
    policy.parent.mkdir(parents=True)
    policy.symlink_to(stub)
    notifier = tmp_path / "usr/share/update-notifier/notify-reboot-required"
    notifier.parent.mkdir(parents=True)
    notifier.symlink_to(stub)

    source = (ROOT / "debian/postinst").read_text()
    source = relocate_system_paths(source, tmp_path)
    script = tmp_path / "postinst"
    script.write_text(source)

    def run(combine_output=False, **env):
        result = subprocess.run(
            ["/bin/sh", str(script), "configure"],
            env={"PATH": str(bin_dir), "AUDIT_ROOT": str(tmp_path),
                 "IMPACTS": "process-restart", **env},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if combine_output else subprocess.PIPE,
            text=True, timeout=10,
        )
        if result.returncode != 0:
            assert "PASS:" not in result.stdout
            assert REBOOT_NOTICE not in (result.stderr or result.stdout)
        return result

    return tmp_path, state, run
