"""Unprivileged maintainer-script machines with explicit service/account doubles.

Both configuration and removal execute real scripts against temporary files.
Their differing command models stay explicit; they share path relocation.
"""

import os
import re
import runpy
import shlex
from pathlib import Path
import subprocess
import sys

import pytest
from tests.support.paths import ROOT
from tests.support.shell import relocate_system_paths

REBOOT_NOTICE = "*** REBOOT REQUIRED: reboot before using the kiosk session. ***"


def script_source(phase, distribution='ubuntu'):
    render = runpy.run_path(str(ROOT / 'packaging/render_lifecycle.py'))['render']
    return render(ROOT, distribution, phase)


def rpm_script_source(path):
    # Model RPM's literal-percent decoding for the isolated command machines.
    # test_rpm_packaging checks every generated callback with RPM's actual
    # macro engine, including runtime %{NAME}/%{name} query formats.
    return path.read_text().replace('%%', '%')


class Machine:
    def __init__(self, root, distribution='ubuntu'):
        self.root = root
        self.distribution = distribution
        self.write("etc/os-release", {
            'ubuntu': 'ID=ubuntu\nVERSION_ID="26.04"\n',
            'fedora': 'ID=fedora\nVERSION_ID=44\nVARIANT_ID=workstation\n',
        }[distribution])
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
printf '%s\\n' "fapolicyd-cli $*" >> "$AUDIT_ROOT/commands"
if [ "$1" = --update ]; then exit "${TRUST_UPDATE_STATUS:-0}"; fi
""").chmod(0o755)
        self.write("usr/libexec/oh-no-parent-control-uninstall", """#!/bin/sh
printf '%s\\n' "uninstall $*" >> "$AUDIT_ROOT/commands"
case "$1" in
    --remove) exit "${REMOVE_FAILURE:-${UNINSTALL_FAILURE:-0}}" ;;
    --restore) exit "${RESTORE_FAILURE:-${UNINSTALL_FAILURE:-0}}" ;;
esac
exit 99
""").chmod(0o755)
        self.write("usr/libexec/oh-no-parent-control-fedora-pam", """#!/bin/sh
printf '%s\\n' "fedora-pam $*" >> "$AUDIT_ROOT/commands"
case "$1" in
    remove) exit "${PAM_REMOVE_FAILURE:-${PAM_FAILURE:-0}}" ;;
    install) exit "${PAM_INSTALL_FAILURE:-${PAM_FAILURE:-0}}" ;;
esac
exit 99
""").chmod(0o755)
        self.write("test-bin/authselect", """#!/bin/sh
case "$1" in current) printf '%s\\n' local;; esac
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

    @property
    def gdm_hook(self):
        return 'etc/gdm/PreSession/Default' if self.distribution == 'fedora' else 'etc/gdm3/PreSession/Default'

    @property
    def service_command(self):
        return 'systemctl' if self.distribution == 'fedora' else 'deb-systemd-invoke'

    @property
    def delete_account(self):
        return 'userdel' if self.distribution == 'fedora' else 'deluser'

    def run(self, script, action, *, distribution=None, **env):
        source = script_source(script, distribution or self.distribution)
        return self.run_source(source, action, **env)

    def run_rpm(self, scriptlet, installed_count, **env):
        renderer = runpy.run_path(str(ROOT / 'packaging/render_lifecycle.py'))
        scripts = self.root / 'rpm-lifecycle'
        renderer['rpm_scripts'](ROOT, scripts)
        # RPM's preun trap invokes the installed abort-remove callback in a
        # separate shell. Give that shell the same isolated command model.
        if scriptlet == 'preun':
            self.prepare_script(script_source('postinst', 'fedora'),
                                'usr/share/oh-no-parent-control/lifecycle/postinst')
        return self.run_source(rpm_script_source(scripts / ('rpm-' + scriptlet)),
                               str(installed_count), **env)

    def prepare_script(self, source, path='script'):
        # The embedded provenance program is covered with its real filesystem
        # and RPM/DNF adapters in test_fedora_execution_policy. This maintainer
        # machine supplies the same explicit command double as service/account
        # commands; it must never execute a host-root Python scriptlet.
        source = re.sub(
            r"/usr/bin/python3 -B - (capture|flags|restore-stock|cleanup) <<'ONPC_FEDORA_EXECUTION_POLICY'\n.*?\nONPC_FEDORA_EXECUTION_POLICY",
            r'fedora_execution_policy \1', source, flags=re.DOTALL)
        source = re.sub(
            r"/usr/bin/python3 -B - <<'ONPC_NATIVE_PURGE_INTENT'\n.*?\nONPC_NATIVE_PURGE_INTENT",
            'native_purge_phase', source, flags=re.DOTALL)
        # Run the real log deletion/identity/mount guards in the private tree.
        # This unprivileged machine models root ownership with its own UID;
        # no production guard, filesystem action or assertion is omitted.
        source = source.replace(
            '/usr/bin/python3 -B - "$@"', 'ONPC_FIXTURE_PYTHON -B - "$@"')
        # Redirect every absolute system prefix, including executable paths.
        source = relocate_system_paths(source, self.root)
        source = source.replace('ONPC_FIXTURE_PYTHON', shlex.quote(sys.executable))
        source = source.replace("_LOG_FILESYSTEM_ROOT = '/'",
                                '_LOG_FILESYSTEM_ROOT = ' + repr(str(self.root)))
        source = source.replace('_LOG_OWNER_UID = 0', '_LOG_OWNER_UID = ' + str(os.getuid()))
        for command in ("deb-systemd-invoke", "invoke-rc.d", "pam-auth-update"):
            source = source.replace(command, command.replace("-", "_").replace(".", "_"))
        mocks = r'''
record() { printf '%s\n' "$*" >> "$AUDIT_ROOT/commands"; }
native_purge_phase() { printf '%s\n' "${RPM_REMOVAL_PHASE:-remove}"; }
fedora_execution_policy() {
    case "$1" in
        restore-stock) printf '%s\n' "${ORIGINAL_STOCK_POLICY:-no}" ;;
        cleanup) rm -f "$AUDIT_ROOT/var/lib/oh-no-parent-control/fedora-execution-policy.json" ;;
        capture|flags) : ;;
        *) return 99 ;;
    esac
}
systemctl() {
    record systemctl "$@"
    case "$1" in
        show)
            test "$*" = 'show --property=ActiveState --value oh-no-parent-control-execution-policy-ready.service' || return 1
            printf '%s\n' "${READINESS_STATE:-inactive}" ;;
        stop)
            if [ "$2" = oh-no-parent-control-execution-policy-ready.service ]; then
                return "${READINESS_STOP_STATUS:-0}"
            fi
            if [ "$2" = fapolicyd.service ]; then SERVICE_ACTIVE=0; fi
            return 0 ;;
        is-active)
            case "$3" in
                user@*) test "${KIOSK_ACTIVE:-0}" = 1 ;;
                oh-no-parent-control-broker.service) test "${BROKER_ACTIVE:-0}" = 1 ;;
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
userdel() { record userdel "$@"; rm "$AUDIT_ROOT/account"; }
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
        return self.write(path, "#!/bin/sh\n" + mocks + source)

    def run_source(self, source, action, **env):
        target = self.prepare_script(source)
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
def package_machine(tmp_path, request):
    distribution = getattr(request, 'param', 'ubuntu')
    state = tmp_path / "var/lib/oh-no-parent-control"
    state.mkdir(parents=True)
    (tmp_path / "run/systemd/system").mkdir(parents=True)
    for name in ("migration-in-progress", "package-activation-pending",
                 "previous-package-activation.json"):
        (state / name).touch()

    (state / "package-created-kiosk-uid").write_text("1006\n")
    for name in ("gdm-presession", "99-oh-no-parent-control-allow.rules", "child-extension.trust"):
        path = tmp_path / "usr/share/oh-no-parent-control" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("product integration\n")
    if distribution == 'fedora':
        name = '00-oh-no-parent-control-canary.rules'
        (tmp_path / 'usr/share/oh-no-parent-control' / name).write_bytes(
            (ROOT / 'data/fapolicyd' / name).read_bytes())
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
    oh-no-parent-control-migrate-state)
        test -f "$AUDIT_ROOT/var/lib/oh-no-parent-control/migration-in-progress" || exit 94
        test ! -f "$AUDIT_ROOT/broker-active" || exit 95
        exit "${MIGRATION_STATUS:-0}"
        ;;
    oh-no-parent-control-package-activation)
        if [ "$*" = prepare-child-trust-backend ]; then printf '%s\n' "${TRUST_BACKEND_ACTION:-none}"; exit 0; fi
        if [ "$*" = complete-child-trust-backend ]; then exit "${TRUST_COMPLETE_STATUS:-0}"; fi
        if [ "$*" = wait-child-trust ]; then exit "${TRUST_READY_STATUS:-0}"; fi
        printf '%s\n' "$IMPACTS" ;;
    oh-no-parent-control-fedora-execution-policy)
        case "$1" in
            eligible) printf '%s\n' "${ORIGINAL_POLICY_ELIGIBLE:-no}" ;;
            commit) exit "${ORIGINAL_POLICY_COMMIT_STATUS:-0}" ;;
            *) exit 99 ;;
        esac ;;
    fagenrules) exit "${RULE_COMPILE_STATUS:-0}" ;;
    fapolicyd-cli)
        if [ "$*" = '--update' ]; then exit "${TRUST_UPDATE_STATUS:-0}"; fi
        test "$*" = '--reload-rules' || exit 99
        test "${RULE_RELOAD_STATUS:-0}" = 0 || exit "$RULE_RELOAD_STATUS"
        test -f "$AUDIT_ROOT/etc/fapolicyd/rules.d/00-oh-no-parent-control-canary.rules" || exit 93
        touch "$AUDIT_ROOT/canary-loaded"
        ;;
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
            'is-active --quiet oh-no-parent-control-broker.service')
                test -f "$AUDIT_ROOT/broker-active"; exit $? ;;
            'stop oh-no-parent-control-broker.service')
                if [ "${BROKER_STOP_REFUSED:-0}" != 1 ]; then rm -f "$AUDIT_ROOT/broker-active"; fi
                ;;
            'is-active --quiet fapolicyd.service')
                if [ -f "$AUDIT_ROOT/fapolicyd-active" ]; then exit 0; fi
                exit "${FAPOLICYD_ACTIVE_STATUS:-0}" ;;
            'start oh-no-parent-control-execution-policy-ready.service')
                test -f "$AUDIT_ROOT/canary-loaded" || exit 92
                exit "${READINESS_STATUS:-0}"
                ;;
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
            'start fapolicyd.service '*)
                if [ "${FAPOLICYD_STARTS:-0}" = 1 ]; then
                    touch "$AUDIT_ROOT/fapolicyd-active"
                fi
                ;;
            'stop oh-no-parent-control-broker.service')
                if [ "${BROKER_STOP_REFUSED:-0}" != 1 ]; then rm -f "$AUDIT_ROOT/broker-active"; fi
                ;;
            *oh-no-parent-control-broker.service*)
                printf 'inactive static unit skipped\n' >&2
                ;;
        esac
        ;;
    restorecon|chown|chmod|systemd-sysusers|invoke-rc.d|usermod|passwd|runuser|\
    oh-no-parent-control-fedora-pam|\
    oh-no-parent-control-provision) ;;
    *) exit 99 ;;
esac
''')
    stub.chmod(0o755)
    for name in ("getent", "id", "systemctl", "deb-systemd-invoke", "install",
                 "chown", "chmod", "systemd-sysusers", "invoke-rc.d", "pam-auth-update",
                 "stat", "debconf-communicate", "usermod", "passwd", "runuser", "restorecon"):
        (bin_dir / name).symlink_to(stub)
    for name in ("rm", "touch", "grep", "cut", "cat", "cmp"):
        (bin_dir / name).symlink_to(Path("/usr/bin") / name)
    for name in ("migrate-state", "provision", "package-activation", "fedora-pam", "fedora-execution-policy"):
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
    for name in ('fagenrules', 'fapolicyd-cli'):
        (tmp_path / 'usr/sbin' / name).symlink_to(stub)
    notifier = tmp_path / "usr/share/update-notifier/notify-reboot-required"
    notifier.parent.mkdir(parents=True)
    notifier.symlink_to(stub)

    source = script_source('postinst', distribution)
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
