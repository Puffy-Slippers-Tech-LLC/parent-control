"""Kiosk routing policy and real PAM transactions, without a live login or bus."""

import configparser
import json
import os
import shlex
import subprocess

import pytest

from tests.support.paths import ROOT


SELECTED_RUNTIME = ROOT / 'data'


def _selected_config(relative):
    settings = configparser.ConfigParser(interpolation=None)
    settings.read(SELECTED_RUNTIME / relative)
    return settings


def test_selected_session_preserves_release_identity_and_kiosk_selection():
    desktop = _selected_config('wayland-sessions/oh-no-parent-control.desktop')['Desktop Entry']
    assert shlex.split(desktop['Exec']) == [
        'gnome-session', '--session', 'oh-no-parent-control']
    assert desktop['TryExec'] == 'gnome-session'
    assert desktop['DesktopNames'] == 'GNOME-Kiosk;GNOME;'
    assert desktop['X-GDM-SessionRegisters'] == 'false'
    assert desktop['X-GDM-CanRunHeadless'] == 'true'
    session = _selected_config('gnome-session/sessions/oh-no-parent-control.session')
    assert dict(session['GNOME Session']) == {
        'name': 'Oh No! Parent Control Kiosk', 'kiosk': 'true'}


def test_selected_target_owns_only_the_dedicated_session_composition():
    target = SELECTED_RUNTIME / (
        'systemd/user/gnome-session@oh-no-parent-control.target.d/session.conf')
    settings = {}
    for line in target.read_text().splitlines():
        key, separator, value = line.partition('=')
        if separator:
            settings.setdefault(key, set()).update(value.split())
    assert settings == {
        'Requires': {'org.gnome.Kiosk.target', 'oh-no-parent-control-app.service'},
        'Wants': {'oh-no-parent-control-notifications.service',
                  'oh-no-parent-control-polkit-agent.service'},
        'After': {'oh-no-parent-control-polkit-agent.service',
                  'update-notifier-crash.path', 'update-notifier-crash.service'},
        'Conflicts': {'update-notifier-crash.path', 'update-notifier-crash.service'},
    }


def test_selected_app_keeps_current_form_and_session_shutdown_ownership():
    source = SELECTED_RUNTIME / 'systemd/user/oh-no-parent-control-app.service'
    app = configparser.ConfigParser(strict=False, interpolation=None)
    app.read(source)
    assert app['Unit']['BindsTo'] == 'gnome-session.target'
    ordered_after = {unit for line in source.read_text().splitlines()
                     if line.startswith('After=') for unit in line.partition('=')[2].split()}
    assert ordered_after == {'gnome-session.target', 'org.gnome.Kiosk@wayland.service',
                             'oh-no-parent-control-notifications.service'}
    assert app['Unit']['OnSuccess'] == 'gnome-session-shutdown.target'
    assert app['Unit']['OnFailure'] == 'gnome-session-shutdown.target'
    assert app['Unit']['OnFailureJobMode'] == 'replace-irreversibly'
    assert app['Service']['Type'] == 'simple'
    assert app['Service']['Restart'] == 'no'
    assert shlex.split(app['Service']['ExecStart']) == ['/usr/bin/oh-no-parent-control']
    # This is the current shared form's isolated entry, including KioskLogout;
    # no release frontend or native confinement launcher is substituted.
    assert (ROOT / 'kiosk/oh-no-parent-control').read_text().splitlines()[0] == (
        '#!/usr/bin/python3 -I')


def test_selected_agent_preserves_main_vendor_and_locale_restart_interface():
    relative = 'systemd/user/oh-no-parent-control-polkit-agent.service'
    agent = _selected_config(relative)
    assert agent['Service']['EnvironmentFile'] == '-%t/oh-no-parent-control/polkit-agent.env'
    assert agent['Service']['Type'] == 'simple'
    assert shlex.split(agent['Service']['ExecStart']) == [
        '/usr/libexec/polkit-mate-authentication-agent-1']
    assert agent['Service']['Restart'] == 'on-failure'


def test_selected_notifications_keep_tagged_current_provider_without_native_wrappers():
    notifications = _selected_config('systemd/user/oh-no-parent-control-notifications.service')
    assert notifications['Unit']['BindsTo'] == 'org.gnome.Kiosk@wayland.service'
    assert notifications['Unit']['PartOf'] == 'gnome-session@oh-no-parent-control.target'
    assert notifications['Unit']['After'] == 'org.gnome.Kiosk@wayland.service'
    assert notifications['Service']['Type'] == 'dbus'
    assert notifications['Service']['BusName'] == 'org.freedesktop.Notifications'
    assert shlex.split(notifications['Service']['ExecStart']) == [
        '/usr/bin/python3', '-I', '/usr/bin/gnome-service-client',
        '--tag=gnome-kiosk-notification', '--', '/usr/bin/python3', '-I',
        '/usr/lib/oh-no-parent-control/kiosk/oh_no_parent_control_kiosk/notifications.py',
    ]
    assert notifications['Service']['Restart'] == 'on-failure'


def test_selected_runtime_has_complete_production_package_source_selection():
    result = subprocess.run(
        ['make', '--no-print-directory', 'package-source-files'], cwd=ROOT,
        check=True, capture_output=True, text=True, timeout=30)
    selected = set(result.stdout.splitlines())
    assert not any(path.is_file() for path in (ROOT / 'data/kiosk-runtime-unselected').rglob('*'))
    assert not any(path.startswith('data/kiosk-runtime-unselected/') for path in selected)
    assert {
        'data/wayland-sessions/oh-no-parent-control.desktop',
        'data/gnome-session/sessions/oh-no-parent-control.session',
        'data/systemd/user/gnome-session@oh-no-parent-control.target.d/session.conf',
        'data/systemd/user/oh-no-parent-control-app.service',
        'data/systemd/user/oh-no-parent-control-polkit-agent.service',
        'data/systemd/user/oh-no-parent-control-notifications.service',
        'kiosk/oh-no-parent-control',
        'kiosk/oh_no_parent_control_kiosk/notifications.py',
        'kiosk/oh_no_parent_control_kiosk/session_logout.py',
        'tools/provision.py',
        'tools/pam_oh_no_parent_control.c',
        'tools/oh-no-parent-control-login-check',
        'tools/oh-no-parent-control-kiosk-lifecycle',
        'packaging/lifecycle_migration.py',
        'packaging/distro_pam.py',
    } <= selected


@pytest.fixture(scope="module")
def session_entry(tmp_path_factory):
    directory = tmp_path_factory.mktemp("onpc-kiosk-session")
    target = directory / "session"
    entry = directory / "entry"
    target.write_text('#!/usr/bin/python3 -I\nimport json, os, sys\n'
                      'print(json.dumps([sys.argv[1:], dict(os.environ)]))\n')
    target.chmod(0o700)
    subprocess.run([
        "cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
        f'-DGNOME_SESSION_PATH="{target}"', "-o", str(entry),
        str(ROOT / "tools/kiosk_session.c"),
    ], check=True, capture_output=True, text=True, timeout=30)
    return entry


def test_session_entry_fixes_command_and_removes_startup_injection(session_entry, tmp_path):
    environment = dict(os.environ, HOME=str(tmp_path), LANG="fr_FR.UTF-8",
                       XDG_RUNTIME_DIR="/run/user/12345", SHELL="/bin/bash",
                       PYTHONPATH=str(tmp_path), GJS_PATH=str(tmp_path),
                       GTK_MODULES="injected", GIO_EXTRA_MODULES=str(tmp_path),
                       XDG_CONFIG_HOME=str(tmp_path), XDG_DATA_HOME=str(tmp_path),
                       XDG_SESSION_TYPE="x11", XDG_CURRENT_DESKTOP="ubuntu:GNOME",
                       BASH_ENV=str(tmp_path / "startup"))
    result = subprocess.run([str(session_entry)], env=environment, cwd=tmp_path,
                            check=True, capture_output=True, text=True, timeout=5)
    arguments, observed = json.loads(result.stdout)
    assert arguments == ["--no-reexec", "--session=oh-no-parent-control"]
    assert observed["HOME"] == str(tmp_path)
    assert observed["LANG"] == "fr_FR.UTF-8"
    assert observed["XDG_RUNTIME_DIR"] == "/run/user/12345"
    assert observed["SHELL"] == "/usr/sbin/nologin"
    assert observed["XDG_SESSION_TYPE"] == "wayland"
    assert observed["XDG_CURRENT_DESKTOP"] == "GNOME-Kiosk:GNOME"
    for name in ("PYTHONPATH", "GJS_PATH", "GTK_MODULES", "GIO_EXTRA_MODULES",
                 "XDG_CONFIG_HOME", "XDG_DATA_HOME", "BASH_ENV"):
        assert name not in observed


def test_session_entry_rejects_alternate_arguments_without_executing(session_entry):
    result = subprocess.run([str(session_entry), "--session=ubuntu"],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode != 0
    assert result.stdout == ""
    assert result.stderr == "onpc.kiosk session startup outcome=failed\n"


@pytest.fixture(scope="module")
def wellbeing_entry(tmp_path_factory):
    directory = tmp_path_factory.mktemp("onpc-wellbeing-entry")
    identity = directory / "identity.c"
    entry = directory / "entry"
    # Exercise the production native dispatch/sanitization without requiring
    # a kiosk account, live GJS process or mutation of host settings. The exec
    # observer records the exact argv and inherited environment at the boundary.
    identity.write_text('''#define _GNU_SOURCE
#include <pwd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
extern char **environ;
struct passwd *__wrap_getpwnam(const char *name) {
    static struct passwd account;
    if (strcmp(name, "oh-no-parent-control") != 0)
        _exit(2);
    account.pw_uid = getuid() + (strcmp(getenv("TEST_IDENTITY"), "ordinary") == 0);
    return &account;
}
int __wrap_execv(const char *path, char *const argv[]) {
    puts(path);
    for (size_t i = 0; argv[i] != NULL; i++)
        puts(argv[i]);
    puts("");
    for (size_t i = 0; environ[i] != NULL; i++)
        puts(environ[i]);
    exit(0);
}
''')
    subprocess.run([
        "cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
        '-DKIOSK_LAUNCH_ROLE="wellbeing"', "-Wl,--wrap=getpwnam",
        "-Wl,--wrap=execv", "-o", str(entry), str(identity),
        str(ROOT / "tools/kiosk_session.c"),
    ], check=True, capture_output=True, text=True, timeout=30)
    return entry


@pytest.mark.parametrize("identity", ["ordinary", "kiosk"])
def test_wellbeing_entry_preserves_ordinary_settings_environment(wellbeing_entry, tmp_path, identity):
    settings = {
        "DCONF_PROFILE": str(tmp_path / "profile"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "GSETTINGS_BACKEND": "dconf",
        "GJS_PATH": str(tmp_path / "modules"),
    }
    environment = dict(os.environ, TEST_IDENTITY=identity, **settings)
    result = subprocess.run([str(wellbeing_entry)], env=environment,
                            check=True, capture_output=True, text=True, timeout=5)
    command, inherited = result.stdout.split("\n\n", 1)
    assert command.splitlines() == [
        "/usr/bin/gjs", "/usr/bin/gjs", "-m",
        "/usr/share/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com/wellbeingService.js",
    ]
    observed = dict(line.split("=", 1) for line in inherited.splitlines())
    for name, value in settings.items():
        if identity == "ordinary":
            assert observed[name] == value
        else:
            assert name not in observed


def test_selected_pam_entry_ignores_python_startup_environment(tmp_path):
    entry = tmp_path / "login-check"
    entry.write_bytes((ROOT / "tools/oh-no-parent-control-login-check").read_bytes())
    # Package staging installs this source as an executable; the checkout
    # source itself deliberately has no executable mode bit.
    entry.chmod(0o700)
    marker = tmp_path / "startup-executed"
    (tmp_path / "sitecustomize.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    environment = dict(os.environ, PYTHONPATH=str(tmp_path),
                       PAM_USER="ordinary-private-account", PAM_SERVICE="sshd")
    result = subprocess.run(
        [str(entry)],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0
    assert not marker.exists()


@pytest.fixture(scope='module')
def native_boundary_callback(tmp_path_factory):
    """Compile the complete production PAM boundary around private observers.

    Native mount/identity mechanics are exercised by native_mount_binding in
    test_kiosk_confinement. This fixture checks their caller's propagation and
    logging without a privileged PAM stack, host lock or namespace operation.
    """
    directory = tmp_path_factory.mktemp('onpc-native-boundary-callback')
    header = (ROOT / 'tools/kiosk_confinement.h').read_text()
    declarations = header[header.index('/* The namespace, filesystem and every mount below it belong'):].split(
        '\nstruct kiosk_record {', 1)[0]
    # Exercise the actual PAM-owned transaction and callback. Only the composed
    # startup/recovery/close mechanics are doubled below; the ownership transfer,
    # repeated-call guard, lock close and diagnostic propagation are production.
    callback = '#define KIOSK_TRANSACTION_DATA' + header.split(
        '#define KIOSK_TRANSACTION_DATA', 1)[1]
    source = directory / 'callback.c'
    source.write_text(r'''
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <syslog.h>
#include <unistd.h>
#include <security/pam_modules.h>
#define KIOSK_ACCOUNT_NAME "private-account-canary"
#define KIOSK_CONFINEMENT_LOCK "private-lock-canary"
#define KIOSK_CONFINEMENT_RUNTIME "private-runtime-canary"
static const char *fixture_service, *fixture_fault;
static int discard, cleanup_calls;
static unsigned log_attempts;
static void *transaction_data;
static void (*transaction_cleanup)(pam_handle_t *, void *, int);
static void fixture_log(pam_handle_t *handle, int priority, const char *format, ...) {
    (void) handle; (void) priority;
    log_attempts++;
    if (!discard) {
        va_list arguments; va_start(arguments, format);
        vprintf(format, arguments); putchar('\n'); va_end(arguments);
    }
    errno = EPIPE;
}
#define pam_syslog fixture_log
''' + declarations + r'''
static int fixture_user(pam_handle_t *handle, const char **user, const char *prompt) {
    (void) handle; (void) prompt; *user = KIOSK_ACCOUNT_NAME; return PAM_SUCCESS;
}
static int fixture_item(const pam_handle_t *handle, int item, const void **value) {
    (void) handle; if (item != PAM_SERVICE) exit(2);
    *value = fixture_service; return PAM_SUCCESS;
}
static int kiosk_admission(pam_handle_t *handle, const char *user) {
    (void) handle; (void) user; puts("admission"); return PAM_SUCCESS;
}
static int kiosk_admission_fd(pam_handle_t *handle) { (void) handle; return 8; }
static int kiosk_lock_identity(int fd, const char *path, uid_t owner) {
    if (fd != 7 || strcmp(path, KIOSK_CONFINEMENT_LOCK) || owner != 0) exit(2);
    puts("lock-verified"); return 0;
}
static int kiosk_private_lock_open(const char *path, uid_t owner, int nonblock) {
    if (strcmp(path, KIOSK_CONFINEMENT_LOCK) != 0 || owner != 0 || nonblock != 0) exit(2);
    puts("lock-open"); return 7;
}
static int fixture_fstat(int fd, struct stat *info) {
    if (fd != 7) exit(2);
    memset(info, 0, sizeof(*info)); info->st_mode = S_IFREG | 0600;
    info->st_nlink = 1; return 0;
}
static int fixture_flock(int fd, int operation) {
    if (fd != 7 || operation != (LOCK_EX | LOCK_NB)) exit(2);
    puts("lock-held"); return 0;
}
static int setup_kiosk_view(struct kiosk_view *view) {
    memset(view, 0, sizeof(*view)); view->root = -1; puts("setup");
    if (strcmp(fixture_fault, "namespace") == 0) {
        errno = EPERM;
        return kiosk_os_failure(&view->failure, "namespace", "namespace", 1) ? -1 : 0;
    }
    return 0;
}
static int prepare_kiosk_confinement(const char *role, int lock, int admission) {
    if ((strcmp(role, "manager") != 0 && strcmp(role, "gate") != 0) || lock != 7 || admission != 8) exit(2);
    puts("prepare"); return 0;
}
static int bind_kiosk_executables(char *backend, size_t size, const char *role, struct kiosk_view *view) {
    (void) role; puts("bind");
    if (strcmp(fixture_fault, "none") != 0) {
        kiosk_failure(&view->failure, "bind", "mount", EIO); return -1;
    }
    if (size < sizeof("apparmor")) exit(2);
    strcpy(backend, "apparmor"); return 0;
}
static int cleanup_kiosk_view(struct kiosk_view *view, int keep_clone) {
    if (keep_clone) exit(2);
    puts("cleanup");
    /* Preserve the first cleanup failure as diagnostic evidence. The PAM
     * transaction's explicit recovery then resolves this same private owner
     * before lock close; no second admission or replacement owner is created. */
    if (strcmp(fixture_fault, "cleanup") == 0 && cleanup_calls++ == 0) {
        kiosk_failure(&view->cleanup_failure, "detach", "detach", EBUSY); return -1;
    }
    return 0;
}
static int fixture_environment(pam_handle_t *handle, const char *value) {
    (void) handle;
    if (strcmp(value, "SYSTEMD_UNIT_PATH=/usr/share/oh-no-parent-control/confinement/user-units:") != 0) exit(2);
    puts("environment"); return PAM_SUCCESS;
}
static int fixture_prctl(int option, ...) {
    if (option != PR_CAP_AMBIENT) exit(2);
    puts("ambient"); return 0;
}
static int apply_kiosk_mac(const char *backend, const char *role) {
    (void) role; if (strcmp(backend, "apparmor") != 0) exit(2);
    puts("mac"); return 0;
}
static int fixture_close(int fd) { if (fd != 7) exit(2); puts("lock-close"); return 0; }
static int fixture_get_data(const pam_handle_t *handle, const char *name, const void **data) {
    (void) handle;
    if (strcmp(name, "oh-no-parent-control.kiosk-transaction")) exit(2);
    *data = transaction_data;
    return transaction_data ? PAM_SUCCESS : PAM_NO_MODULE_DATA;
}
static int fixture_set_data(pam_handle_t *handle, const char *name, void *data,
    void (*cleanup)(pam_handle_t *, void *, int)) {
    (void) handle;
    if (strcmp(name, "oh-no-parent-control.kiosk-transaction") || transaction_data || !data || !cleanup) exit(2);
    transaction_data = data; transaction_cleanup = cleanup;
    return PAM_SUCCESS;
}
static int kiosk_pin_now(uint64_t *now) { *now = 1000000U; return 0; }
struct kiosk_fresh_startup {
    struct kiosk_view view;
    struct kiosk_failure failure, cleanup_failure;
    int armed;
    uint64_t deadline;
    const char *stage;
};
struct kiosk_retained_startup { struct kiosk_fresh_startup common; };
static void kiosk_retained_startup_init(struct kiosk_retained_startup *gate) {
    memset(gate, 0, sizeof(*gate)); gate->common.view.root = -1;
}
static int fixture_startup(struct kiosk_fresh_startup *s, pam_handle_t *handle,
    int lock, int admission, uint64_t deadline, const char *role) {
    if (lock != 7 || admission != 8 || deadline != 61000000U) exit(2);
    s->deadline = deadline; s->stage = "runtime";
    if (setup_kiosk_view(&s->view)) goto refused;
    if (prepare_kiosk_confinement(role, lock, admission)) exit(2);
    s->stage = "realization";
    char backend[32];
    if (bind_kiosk_executables(backend, sizeof(backend), role, &s->view)) goto refused;
    if (!strcmp(role, "manager") && fixture_environment(handle,
        "SYSTEMD_UNIT_PATH=/usr/share/oh-no-parent-control/confinement/user-units:") != PAM_SUCCESS) exit(2);
    if (fixture_prctl(PR_CAP_AMBIENT) || kiosk_lock_identity(lock, KIOSK_CONFINEMENT_LOCK, 0) ||
        apply_kiosk_mac(backend, role)) exit(2);
    s->armed = 1; s->stage = "armed";
    return 0;
refused:
    s->failure = s->view.failure;
    (void) cleanup_kiosk_view(&s->view, 0);
    s->cleanup_failure = s->view.cleanup_failure;
    return -1;
}
static int kiosk_fresh_startup_until(struct kiosk_fresh_startup *s, pam_handle_t *handle,
    int lock, int admission, uint64_t deadline) {
    return fixture_startup(s, handle, lock, admission, deadline, "manager");
}
static int kiosk_retained_startup_until(struct kiosk_retained_startup *gate, pam_handle_t *handle,
    int lock, int admission, uint64_t deadline) {
    return fixture_startup(&gate->common, handle, lock, admission, deadline, "gate");
}
static int kiosk_fresh_recover_until(struct kiosk_fresh_startup *s, uint64_t deadline) {
    if (deadline != 6000000U || s->deadline != 61000000U) exit(2);
    return cleanup_kiosk_view(&s->view, 0);
}
static int kiosk_retained_recover_until(struct kiosk_retained_startup *gate, uint64_t deadline) {
    return kiosk_fresh_recover_until(&gate->common, deadline);
}
static int kiosk_fresh_close(struct kiosk_fresh_startup *s) { (void) s; return 0; }
static int kiosk_retained_close(struct kiosk_retained_startup *gate) {
    return kiosk_fresh_close(&gate->common);
}
#define pam_get_user fixture_user
#define pam_get_item fixture_item
#define pam_get_data fixture_get_data
#define pam_set_data fixture_set_data
#define geteuid() 0
#define fstat fixture_fstat
#define flock fixture_flock
#define close fixture_close
''' + callback + r'''
int main(int argc, char **argv) {
    if (argc != 4) return 2;
    fixture_service = argv[1]; fixture_fault = argv[2]; discard = strcmp(argv[3], "discard") == 0;
    int result = kiosk_confinement(NULL);
    if (!transaction_data || !transaction_cleanup) return 2;
    transaction_cleanup(NULL, transaction_data, result);
    transaction_data = NULL;
    printf("result:%d\nlog-attempts:%u\n", result, log_attempts);
    return 0;
}
''')
    executable = directory / 'callback'
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-o',
                    str(executable), str(source)], check=True, capture_output=True, text=True, timeout=30)
    return executable


@pytest.mark.parametrize('service,role', [('systemd-user', 'manager'), ('gdm-password', 'gate')])
@pytest.mark.parametrize('fault', ['none', 'namespace', 'bind', 'cleanup'])
def test_native_boundary_pam_result_survives_diagnostic_failure(native_boundary_callback, service, role, fault):
    def invoke(mode):
        result = subprocess.run([str(native_boundary_callback), service, fault, mode],
                                check=True, capture_output=True, text=True, timeout=5)
        return result.stdout.splitlines()
    captured, discarded = invoke('capture'), invoke('discard')
    expected_result = 'result:0' if fault == 'none' else 'result:14'  # PAM_SESSION_ERR
    assert expected_result in captured and expected_result in discarded
    # All effects of the actual PAM caller remain identical if logging drops
    # every record and changes errno. The final result is checked separately
    # from both the producer's reason and its existing stage-only marker.
    assert [line for line in captured if not line.startswith('onpc.')] == discarded
    assert captured.index('lock-held') < captured.index('setup')
    assert captured.index('lock-held') < captured.index('lock-verified') < captured.index('setup')
    if fault == 'none':
        assert captured.index('ambient') < max(index for index, line in enumerate(captured)
                                                if line == 'lock-verified') < captured.index('mac')
    assert captured.index('lock-close') < captured.index(expected_result)
    native = [line for line in captured if line.startswith('onpc.pam kiosk native-view ')]
    if fault == 'none':
        assert native == []
        assert 'mac' in captured
        assert 'onpc.pam kiosk execution-boundary outcome=armed stage=armed' in captured
    else:
        assert 'mac' not in captured and 'ambient' not in captured
        stage, reason, error = ('namespace', 'namespace', 1) if fault == 'namespace' else ('bind', 'mount', 5)
        expected = [f'onpc.pam kiosk native-view outcome=denied role={role} '
                    f'stage={stage} reason={reason} errno={error}']
        if fault == 'cleanup':
            expected.append(f'onpc.pam kiosk native-view outcome=cleanup-failed role={role} '
                            'stage=detach reason=detach errno=16')
        assert native == expected
        outer_stage = 'runtime' if fault == 'namespace' else 'realization'
        assert f'onpc.pam kiosk execution-boundary outcome=denied stage={outer_stage}' in captured
    assert 'private-account-canary' not in '\n'.join(native)
    assert 'private-lock-canary' not in '\n'.join(native)
