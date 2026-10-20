"""Kiosk routing policy and real PAM transactions, without a live login or bus."""

import configparser
import ctypes
from contextlib import contextmanager
import fcntl
import importlib.machinery
import importlib.util
import json
import multiprocessing
import os
import shlex
import subprocess
import time
from types import SimpleNamespace

import pytest

from tests.support.paths import ROOT


PREPARED_RUNTIME = ROOT / 'data/kiosk-runtime-unselected'


def _prepared_config(relative):
    settings = configparser.ConfigParser(interpolation=None)
    settings.read(PREPARED_RUNTIME / relative)
    return settings


def test_prepared_session_preserves_release_identity_and_kiosk_selection():
    desktop = _prepared_config('wayland-sessions/oh-no-parent-control.desktop')['Desktop Entry']
    assert shlex.split(desktop['Exec']) == [
        'gnome-session', '--session', 'oh-no-parent-control']
    assert desktop['TryExec'] == 'gnome-session'
    assert desktop['DesktopNames'] == 'GNOME-Kiosk;GNOME;'
    assert desktop['X-GDM-SessionRegisters'] == 'false'
    assert desktop['X-GDM-CanRunHeadless'] == 'true'
    session = _prepared_config('gnome-session/sessions/oh-no-parent-control.session')
    assert dict(session['GNOME Session']) == {
        'name': 'Oh No! Parent Control Kiosk', 'kiosk': 'true'}


def test_prepared_target_owns_only_the_dedicated_session_composition():
    target = PREPARED_RUNTIME / (
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


def test_prepared_app_keeps_current_form_and_session_shutdown_ownership():
    source = PREPARED_RUNTIME / 'systemd/user/oh-no-parent-control-app.service'
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


def test_prepared_agent_preserves_main_vendor_and_locale_restart_interface():
    relative = 'systemd/user/oh-no-parent-control-polkit-agent.service'
    agent = _prepared_config(relative)
    active = configparser.ConfigParser(interpolation=None)
    active.read(ROOT / 'data' / relative)
    assert {section: dict(agent[section]) for section in agent.sections()} == {
        section: dict(active[section]) for section in active.sections()}
    assert agent['Service']['EnvironmentFile'] == '-%t/oh-no-parent-control/polkit-agent.env'
    assert agent['Service']['Type'] == 'simple'
    assert shlex.split(agent['Service']['ExecStart']) == [
        '/usr/libexec/polkit-mate-authentication-agent-1']
    assert agent['Service']['Restart'] == 'on-failure'


def test_prepared_notifications_keep_tagged_current_provider_without_native_wrappers():
    notifications = _prepared_config('systemd/user/oh-no-parent-control-notifications.service')
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


def test_prepared_runtime_has_no_production_package_source_selection():
    result = subprocess.run(
        ['make', '--no-print-directory', 'package-source-files'], cwd=ROOT,
        check=True, capture_output=True, text=True, timeout=30)
    selected = set(result.stdout.splitlines())
    prepared = {path.relative_to(ROOT).as_posix()
                for path in PREPARED_RUNTIME.rglob('*') if path.is_file()}
    assert len(prepared) == 6
    assert prepared.isdisjoint(selected)
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


def test_legacy_pam_entry_ignores_python_startup_environment(tmp_path):
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


@pytest.fixture
def routing(monkeypatch):
    loader = importlib.machinery.SourceFileLoader(
        "onpc_kiosk_login", str(ROOT / "tools/oh-no-parent-control-login-check"))
    helper = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(helper)
    state = SimpleNamespace(session=helper.SESSION, transport="wayland", calls=[],
                            records=[], fault=None, no_write=False)
    monkeypatch.setenv("PAM_USER", helper.KIOSK_USER)
    monkeypatch.setenv("PAM_SERVICE", "gdm-password")
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setattr(helper.os, "geteuid", lambda: 0)
    monkeypatch.setattr(helper.pwd, "getpwnam", lambda name: SimpleNamespace(pw_uid=12345))
    monkeypatch.setattr(helper.syslog, "syslog", lambda level, text: state.records.append(text))
    monkeypatch.setattr(helper, "verify_confinement", lambda: None)

    def command(argv, **kwargs):
        assert argv[:4] == ["/usr/bin/busctl", "--system", "--timeout=4",
                            "--allow-interactive-authorization=no"]
        assert kwargs == dict(check=True, capture_output=True, text=True,
                              timeout=5, env=helper.ENVIRONMENT)
        assert argv[5:8] == [helper.BUS, "/org/freedesktop/Accounts/User12345", helper.INTERFACE]
        state.calls.append(argv[4:])
        if state.fault:
            raise state.fault
        if argv[4] == "get-property":
            assert argv[8:] == ["Session", "SessionType"]
            output = f"s {shlex.quote(state.session)}\ns {shlex.quote(state.transport)}\n"
        else:
            assert argv[4] == "call" and argv[9] == "s"
            if not state.no_write:
                if argv[8] == "SetSession":
                    state.session = argv[10]
                elif argv[8] == "SetSessionType":
                    state.transport = argv[10]
                else:
                    pytest.fail("unexpected AccountsService mutation")
            output = ""
        return SimpleNamespace(stdout=output)

    monkeypatch.setattr(helper.subprocess, "run", command)
    return helper, state


def test_valid_preference_checks_do_not_mutate_or_depend_on_gdm_save_timing(routing):
    helper, state = routing
    assert helper.main(["--kiosk-account"]) == 0
    assert state.session == helper.SESSION
    # No GDM save occurs. This verifies a preference, not the next command:
    # the installed first-exec matrix independently requires the MAC denial.
    assert helper.main(["--kiosk-session"]) == 0
    assert all(call[0] == "get-property" for call in state.calls)
    assert "outcome=allowed" in state.records[0]
    assert "outcome=allowed" in state.records[-1]


@pytest.mark.parametrize("selected", ["ubuntu", "gnome", ""])
def test_changed_desktop_preference_is_denied_and_default_restored(routing, selected):
    helper, state = routing
    assert helper.main(["--kiosk-account"]) == 0
    state.session = selected
    assert helper.main(["--kiosk-session"]) == 1
    assert (state.session, state.transport) == (helper.SESSION, "wayland")
    assert "outcome=denied" in state.records[-1]
    assert "recovery=restored" in state.records[-1]


@pytest.mark.parametrize("session,transport", [("ubuntu", ""), ("", "wayland"),
                                               ("oh-no-parent-control", "x11"),
                                               ("oh-no-parent-control-verification-pending", "wayland")])
def test_bad_default_or_aborted_transaction_is_repaired_but_not_admitted(routing, session, transport):
    helper, state = routing
    state.session, state.transport = session, transport
    assert helper.main(["--kiosk-account"]) == 1
    assert (state.session, state.transport) == (helper.SESSION, "wayland")
    assert helper.main(["--kiosk-account"]) == 0


@pytest.mark.parametrize("transport", ["x11", "", "tty"])
def test_actual_transport_is_checked_in_pam_environment(routing, monkeypatch, transport):
    helper, state = routing
    monkeypatch.setenv("XDG_SESSION_TYPE", transport)
    assert helper.main(["--kiosk-session"]) == 1
    assert "outcome=denied" in state.records[-1]


@pytest.mark.parametrize("fault", [OSError("private-identity"),
                                  subprocess.TimeoutExpired("private-identity", 5),
                                  subprocess.CalledProcessError(1, "busctl", stderr="private-identity")])
def test_indeterminate_policy_fails_closed_without_logging_exception_text(routing, fault):
    helper, state = routing
    state.fault = fault
    assert helper.main(["--kiosk-account"]) == 1
    assert "outcome=unavailable" in state.records[-1]
    assert "private-identity" not in " ".join(state.records)


def test_failed_preference_repair_is_denied(routing):
    helper, state = routing
    state.session = "ubuntu"
    state.no_write = True
    assert helper.main(["--kiosk-account"]) == 1
    assert state.session == "ubuntu"
    assert "outcome=denied" in state.records[-1]
    assert "recovery=failed" in state.records[-1]


def test_failed_recovery_and_unknown_metadata_are_logged_as_categories(routing):
    helper, state = routing
    state.session = "private-identity with spaces"
    state.transport = "private-transport"
    state.no_write = True
    assert helper.main(["--kiosk-account"]) == 1
    assert "session=other type=other recovery=failed" in state.records[-1]
    assert "private" not in " ".join(state.records)


@pytest.mark.parametrize("user,service,expected", [
    ("ordinary-private-account", "sshd", 0),
    ("oh-no-parent-control", "systemd-user", 0),
    ("oh-no-parent-control", "sshd", 1),
    ("oh-no-parent-control", "gdm-autologin", 1),
    ("oh-no-parent-control", "gdm-password", 0),
])
def test_service_guard_does_not_query_accounts_service(routing, monkeypatch, user, service, expected):
    helper, state = routing
    monkeypatch.setenv("PAM_USER", user)
    monkeypatch.setenv("PAM_SERVICE", service)
    assert helper.main([]) == expected
    assert state.calls == []


@pytest.mark.parametrize('service', ['gdm-password', 'systemd-user'])
def test_integrity_refusal_precedes_any_routing_query(routing, monkeypatch, service):
    helper, state = routing
    monkeypatch.setenv('PAM_SERVICE', service)
    def refused():
        raise subprocess.CalledProcessError(1, 'private-diagnostic')
    monkeypatch.setattr(helper, 'verify_confinement', refused)
    for arguments in ([], ['--kiosk-integrity'], ['--kiosk-account'], ['--kiosk-session']):
        assert helper.main(arguments) == 1
    assert state.calls == []
    assert all('reason=integration' in entry and 'private' not in entry for entry in state.records)


@pytest.mark.parametrize('service', ['gdm-password', 'systemd-user'])
def test_integrity_success_does_not_change_saved_selection(routing, monkeypatch, service):
    helper, state = routing
    monkeypatch.setenv('PAM_SERVICE', service)
    assert helper.main(['--kiosk-integrity']) == 0
    assert state.calls == []


def test_explicit_checks_require_root(routing, monkeypatch):
    helper, state = routing
    monkeypatch.setattr(helper.os, "geteuid", lambda: 12345)
    assert helper.main(["--kiosk-account"]) == 1
    assert state.calls == []


@pytest.fixture(scope="module")
def native_module(tmp_path_factory):
    directory = tmp_path_factory.mktemp("onpc-kiosk-pam")
    helper = directory / "helper"
    module = directory / "pam-kiosk.so"
    subprocess.run([
        "cc", "-shared", "-fPIC", "-Wall", "-Wextra", "-Werror",
        f'-DLOGIN_CHECK_PATH="{helper}"',
        '-DKIOSK_ACCOUNT_NAME="private-account-canary"',
        f'-DKIOSK_LOGIN_LOCK_PATH="{directory / "lock"}"',
        f"-DKIOSK_LOGIN_LOCK_OWNER={os.getuid()}",
        f'-DKIOSK_ADMISSION_LOCK="{directory / "admission-lock"}"',
        f'-DKIOSK_ADMISSION_DISABLED="{directory / "removing"}"',
        f"-DKIOSK_ADMISSION_LOCK_OWNER={os.getuid()}",
        "-DKIOSK_LOGIN_TIMEOUT_SECONDS=1",
        "-o", str(module), str(ROOT / "tools/pam_oh_no_parent_control.c"), "-lpam",
    ], check=True, capture_output=True, text=True, timeout=30)
    helper.write_text('''#!/usr/bin/python3
import json, os, pathlib, sys, time
directory = pathlib.Path(__file__).parent
with (directory / "calls").open("a") as stream:
    stream.write(json.dumps([sys.argv[1:], {key: os.environ.get(key, "") for key in
        ("PAM_USER", "PAM_SERVICE", "XDG_SESSION_TYPE")}]) + "\\n")
status = int((directory / "status").read_text())
if status == 99:
    time.sleep(10)
if status == 98:
    (directory / "ready").touch()
    deadline = time.monotonic() + 3
    while not (directory / "release").exists() and time.monotonic() < deadline:
        time.sleep(0.01)
sys.exit(status)
''')
    helper.chmod(0o700)
    return module, directory


@pytest.fixture
def native(native_module, tmp_path):
    module, directory = native_module
    (directory / "status").write_text("0")
    (directory / "calls").write_text("")
    for name in ("ready", "release", "removing"):
        (directory / name).unlink(missing_ok=True)
    lock = directory / "lock"
    # All previous PAM handles have ended before fixture cleanup/reuse.
    lock.unlink(missing_ok=True)
    pam = ctypes.CDLL("libpam.so.0")

    class Conversation(ctypes.Structure):
        _fields_ = [("conv", ctypes.c_void_p), ("data", ctypes.c_void_p)]

    pam.pam_start_confdir.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
                                    ctypes.POINTER(Conversation), ctypes.c_char_p,
                                    ctypes.POINTER(ctypes.c_void_p)]
    for name in ("pam_authenticate", "pam_setcred", "pam_acct_mgmt", "pam_open_session", "pam_close_session", "pam_end"):
        getattr(pam, name).argtypes = [ctypes.c_void_p, ctypes.c_int]
    pam.pam_putenv.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

    @contextmanager
    def transaction(user="private-account-canary", service="gdm-password", transport="wayland", account_mode="kiosk", session_mode="kiosk", stack_source=None):
        (tmp_path / service).write_text(
            stack_source if stack_source is not None else
            f"account required {module} {account_mode}\nsession required {module} {session_mode}\n")
        handle = ctypes.c_void_p()
        conversation = Conversation()
        assert pam.pam_start_confdir(service.encode(), user.encode(), ctypes.byref(conversation),
                                    str(tmp_path).encode(), ctypes.byref(handle)) == 0
        try:
            if transport is not None:
                assert pam.pam_putenv(handle, f"XDG_SESSION_TYPE={transport}".encode()) == 0
            yield handle
        finally:
            assert pam.pam_end(handle, 0) == 0

    return SimpleNamespace(pam=pam, transaction=transaction, directory=directory, lock=lock,
                           module=module,
                           admission=directory / 'admission-lock',
                           calls=lambda: [json.loads(line) for line in
                                          (directory / "calls").read_text().splitlines()])


@pytest.mark.parametrize('fallback', ['pam_deny.so', 'pam_permit.so'])
@pytest.mark.parametrize('user', ['private-account-canary', 'ordinary-account-canary'])
def test_manager_credentials_bypass_fallback_only_for_kiosk(native, tmp_path, fallback, user):
    loader = importlib.machinery.SourceFileLoader(
        'onpc_manager_credentials', str(ROOT / 'packaging/kiosk_confinement.py'))
    integration = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(integration)
    stack = integration.MANAGER_CREDENTIALS.replace('pam_oh_no_parent_control.so', str(native.module))
    (tmp_path / 'other').write_text(f'auth required {fallback}\n')
    # Exercise the production control expression through real libpam, with no
    # authentication, matching systemd's credential callback ordering.
    with native.transaction(user=user, service='systemd-user', stack_source=stack) as handle:
        expected = 0 if user == 'private-account-canary' or fallback == 'pam_permit.so' else 17
        for flags in (2, 4, 2 | 0x8000, 4 | 0x8000):
            assert native.pam.pam_setcred(handle, flags) == expected
    with native.transaction(user=user, service='systemd-user', stack_source=stack) as handle:
        status = native.pam.pam_authenticate(handle, 0)
        assert (status == 0) == (user == 'ordinary-account-canary' and fallback == 'pam_permit.so')
    assert native.calls() == []
    assert not native.lock.exists()
    assert not native.admission.exists()


@pytest.mark.parametrize('service,option', [
    ('gdm-password', 'kiosk-manager-credentials'),
    ('systemd-user', 'kiosk-manager-credentials unexpected'),
])
def test_manager_credentials_refuse_wrong_service_or_extra_arguments(native, service, option):
    with native.transaction(service=service, stack_source=f'auth required {native.module} {option}\n') as handle:
        assert native.pam.pam_setcred(handle, 2) != 0
        assert native.pam.pam_authenticate(handle, 0) != 0
    assert native.calls() == []


def test_real_pam_binds_stages_and_passes_only_pam_transport(native, monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "poisoned-process-environment")
    with native.transaction(transport=None) as handle:
        assert native.pam.pam_acct_mgmt(handle, 0) == 0
        assert native.pam.pam_acct_mgmt(handle, 0) == 0
        assert native.pam.pam_open_session(handle, 0) == 0
        assert native.pam.pam_open_session(handle, 0) != 0
    assert [call[0] for call in native.calls()] == [["--kiosk-account"], ["--kiosk-session"]]
    assert native.calls()[1][1] == dict(PAM_USER="private-account-canary",
                                       PAM_SERVICE="gdm-password", XDG_SESSION_TYPE="")


def test_real_pam_rejects_open_without_successful_account_check(native):
    with native.transaction() as handle:
        assert native.pam.pam_open_session(handle, 0) != 0
        (native.directory / "status").write_text("1")
        assert native.pam.pam_acct_mgmt(handle, 0) != 0
        (native.directory / "status").write_text("0")
        assert native.pam.pam_acct_mgmt(handle, 0) != 0
        assert native.pam.pam_open_session(handle, 0) != 0
    assert len(native.calls()) == 1


@pytest.mark.parametrize('service', ['gdm-password', 'systemd-user'])
def test_real_pam_integrity_checks_manager_and_gdm_without_routing_lock(native, service):
    with native.transaction(service=service, account_mode='kiosk-integrity') as handle:
        assert native.pam.pam_acct_mgmt(handle, 0) == 0
        (native.directory / 'status').write_text('1')
        assert native.pam.pam_acct_mgmt(handle, 0) != 0
    assert [call[0] for call in native.calls()] == [['--kiosk-integrity'], ['--kiosk-integrity']]
    assert not native.lock.exists()


@pytest.mark.parametrize('service', ['gdm-password', 'systemd-user'])
def test_pam_removal_lease_spans_root_executor_after_session_open(native, service):
    # No setuid or real login occurs. This is precisely the trusted executor
    # interval which a kiosk UID census cannot see.
    with native.transaction(service=service) as handle:
        assert native.pam.pam_acct_mgmt(handle, 0) == 0
        assert native.pam.pam_open_session(handle, 0) == 0
        with native.admission.open('rb') as removal:
            with pytest.raises(BlockingIOError):
                fcntl.flock(removal, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with native.admission.open('rb') as removal:
        fcntl.flock(removal, fcntl.LOCK_EX | fcntl.LOCK_NB)


@pytest.mark.parametrize('service', ['gdm-password', 'systemd-user'])
def test_removal_excludes_new_pam_admissions_and_durable_marker_survives_unlock(native, service):
    native.admission.touch(mode=0o600, exist_ok=True)
    with native.admission.open('rb') as removal:
        fcntl.flock(removal, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with native.transaction(service=service, account_mode='kiosk-integrity') as handle:
            assert native.pam.pam_acct_mgmt(handle, 0) != 0
        (native.directory / 'removing').write_text('removing\n')
    with native.transaction(service=service, account_mode='kiosk-integrity') as handle:
        assert native.pam.pam_acct_mgmt(handle, 0) != 0
    assert native.calls() == []


@pytest.mark.parametrize('service', ['gdm-password', 'systemd-user'])
@pytest.mark.parametrize('change', ['replace', 'symlink', 'mode', 'hardlink', 'removal'])
def test_retained_pam_lease_rechecks_exact_named_inode_before_reuse(native, service, change):
    original = native.directory / 'saved-admission-inode'
    sibling = native.directory / 'extra-admission-link'
    barrier = native.directory / 'removing'
    with native.transaction(service=service, account_mode='kiosk-integrity') as handle:
        assert native.pam.pam_acct_mgmt(handle, 0) == 0
        identity = native.admission.stat()
        try:
            if change in ('replace', 'symlink'):
                native.admission.rename(original)
                if change == 'replace':
                    native.admission.touch(mode=0o600)
                else:
                    native.admission.symlink_to(original.name)
            elif change == 'mode':
                native.admission.chmod(0o640)
            elif change == 'hardlink':
                os.link(native.admission, sibling)
            else:
                barrier.write_text('removing\n')
            assert native.pam.pam_acct_mgmt(handle, 0) != 0
            assert len(native.calls()) == 1  # Refused before another routing helper.
        finally:
            if change in ('replace', 'symlink'):
                native.admission.unlink()
                original.rename(native.admission)
            elif change == 'mode':
                native.admission.chmod(0o600)
            elif change == 'hardlink':
                sibling.unlink()
            else:
                barrier.unlink()
        restored = native.admission.stat()
        assert (restored.st_dev, restored.st_ino) == (identity.st_dev, identity.st_ino)
        # Restoring this exact owned inode permits a fresh observation. No
        # replacement lock is adopted into the already leased PAM handle.
        assert native.pam.pam_acct_mgmt(handle, 0) == 0


@pytest.mark.parametrize('service', ['gdm-password', 'systemd-user'])
def test_session_admission_denies_even_when_account_callback_was_not_used(native, service):
    native.admission.touch(mode=0o600, exist_ok=True)
    with native.admission.open('rb') as removal:
        fcntl.flock(removal, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with native.transaction(service=service, session_mode='kiosk-admission') as handle:
            # The separate first session guard runs before vendor callbacks.
            assert native.pam.pam_open_session(handle, 0) != 0


def test_session_guard_retains_admission_lease_through_close_until_pam_end(native):
    with native.transaction(session_mode='kiosk-admission') as handle:
        assert native.pam.pam_open_session(handle, 0) == 0
        assert native.pam.pam_close_session(handle, 0) == 0
        with native.admission.open('rb') as removal:
            with pytest.raises(BlockingIOError):
                fcntl.flock(removal, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with native.admission.open('rb') as removal:
        fcntl.flock(removal, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_shared_profile_systemd_session_leases_without_account_callback(native):
    with native.transaction(service='systemd-user') as handle:
        assert native.pam.pam_open_session(handle, 0) == 0
        with native.admission.open('rb') as removal:
            with pytest.raises(BlockingIOError):
                fcntl.flock(removal, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with native.admission.open('rb') as removal:
        fcntl.flock(removal, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with native.transaction(service='systemd-user') as handle:
            assert native.pam.pam_open_session(handle, 0) != 0


@pytest.mark.parametrize('service', ['gdm-password', 'systemd-user'])
@pytest.mark.parametrize('user,allowed', [('oh-no-parent-control', False), ('root', True)])
def test_standalone_removal_pam_denials_preserve_ordinary_account_and_session(native, service, user, allowed):
    spec = importlib.util.spec_from_file_location('removal_gate_source', ROOT / 'packaging/kiosk_confinement.py')
    integration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(integration)
    stack = (integration.REMOVAL_PREFIX +
             'account required pam_permit.so\nsession required pam_permit.so\n')
    with native.transaction(user=user, service=service, stack_source=stack) as handle:
        assert (native.pam.pam_acct_mgmt(handle, 0) == 0) is allowed
        assert (native.pam.pam_open_session(handle, 0) == 0) is allowed
    assert native.calls() == []


def test_real_pam_serializes_logins_and_releases_lock_on_abort(native):
    with native.transaction() as first:
        assert native.pam.pam_acct_mgmt(first, 0) == 0
        with native.transaction() as second:
            assert native.pam.pam_acct_mgmt(second, 0) != 0
            assert native.pam.pam_open_session(second, 0) != 0
    with native.transaction() as retry:
        assert native.pam.pam_acct_mgmt(retry, 0) == 0
        assert native.pam.pam_open_session(retry, 0) == 0


@pytest.mark.parametrize('mask', [0o077, 0o777])
def test_real_pam_initializes_only_new_locks_despite_umask(native, mask):
    native.admission.unlink(missing_ok=True)
    libc = ctypes.CDLL(None)
    libc.setfsuid.argtypes = libc.setfsgid.argtypes = [ctypes.c_uint]
    libc.setfsuid.restype = libc.setfsgid.restype = ctypes.c_uint
    credentials = (os.getresuid(), os.getresgid(), os.getgroups(),
                   libc.setfsuid(0xffffffff), libc.setfsgid(0xffffffff))
    parent = native.directory.stat()
    inherited_gid = parent.st_gid if parent.st_mode & 0o2000 else credentials[4]
    with native.transaction() as handle:
        previous = os.umask(mask)
        try:
            assert native.pam.pam_acct_mgmt(handle, 0) == 0
            assert os.umask(mask) == mask
            assert (os.getresuid(), os.getresgid(), os.getgroups(),
                    libc.setfsuid(0xffffffff), libc.setfsgid(0xffffffff)) == credentials
            for path in (native.lock, native.admission):
                info = path.stat()
                assert info.st_mode & 0o7777 == 0o600
                assert info.st_uid == credentials[3]
                assert info.st_gid == inherited_gid
                assert info.st_nlink == 1
        finally:
            os.umask(previous)


def test_real_pam_reuses_valid_lock_without_changing_metadata(native):
    paths = (native.lock, native.admission)
    for path in paths:
        path.write_bytes(b'unchanged-private-lock')
        path.chmod(0o600)
    before = [path.stat() for path in paths]
    with native.transaction() as handle:
        previous = os.umask(0o777)
        try:
            assert native.pam.pam_acct_mgmt(handle, 0) == 0
            assert os.umask(0o777) == 0o777
        finally:
            os.umask(previous)
    for path, original in zip(paths, before):
        after = path.stat()
        assert (after.st_dev, after.st_ino, after.st_uid, after.st_gid, after.st_mode,
                after.st_nlink, after.st_ctime_ns) == (
                    original.st_dev, original.st_ino, original.st_uid, original.st_gid, original.st_mode,
                    original.st_nlink, original.st_ctime_ns)
        assert path.read_bytes() == b'unchanged-private-lock'


@pytest.mark.parametrize("fault", ["symlink", "mode", "zero-mode", "directory", "hardlink"])
def test_real_pam_refuses_unsafe_lock_paths(native, tmp_path, fault):
    sibling = tmp_path / 'extra-lock-link'
    if fault == "symlink":
        native.lock.symlink_to(native.directory / "status")
    elif fault in ("mode", "zero-mode"):
        native.lock.write_bytes(b'unsafe-mode-lock')
        native.lock.chmod(0 if fault == 'zero-mode' else 0o666)
    elif fault == 'directory':
        native.lock.mkdir()
    else:
        native.lock.write_bytes(b'linked-private-lock')
        native.lock.chmod(0o600)
        os.link(native.lock, sibling)
    before = native.lock.lstat()
    try:
        with native.transaction() as handle:
            assert native.pam.pam_acct_mgmt(handle, 0) != 0
        assert native.calls() == []
        after = native.lock.lstat()
        assert (after.st_dev, after.st_ino, after.st_uid, after.st_gid, after.st_mode,
                after.st_nlink, after.st_ctime_ns) == (
                    before.st_dev, before.st_ino, before.st_uid, before.st_gid, before.st_mode,
                    before.st_nlink, before.st_ctime_ns)
    finally:
        if fault == "directory":
            native.lock.rmdir()
        elif fault == 'hardlink':
            sibling.unlink()
        elif fault == 'zero-mode':
            native.lock.chmod(0o600)


def test_real_pam_bounds_and_reaps_helper_timeout(native):
    (native.directory / "status").write_text("99")
    started = time.monotonic()
    with native.transaction() as handle:
        assert native.pam.pam_acct_mgmt(handle, 0) != 0
        assert native.pam.pam_open_session(handle, 0) != 0
    assert 1 <= time.monotonic() - started < 5
    assert len(native.calls()) == 1


def test_real_pam_denies_session_helper_failure_and_releases_lock(native):
    with native.transaction() as handle:
        assert native.pam.pam_acct_mgmt(handle, 0) == 0
        (native.directory / "status").write_text("1")
        assert native.pam.pam_open_session(handle, 0) != 0
        (native.directory / "status").write_text("0")
        with native.transaction() as retry:
            assert native.pam.pam_acct_mgmt(retry, 0) == 0
            assert native.pam.pam_open_session(retry, 0) == 0


def test_aborted_pam_worker_cannot_unlock_a_still_running_routing_helper(native):
    (native.directory / "status").write_text("98")

    def account_worker():
        # Also exercise a worker with closed stdin: its lock may occupy fd 0
        # and must survive the helper's /dev/null stdio redirection.
        os.close(0)
        with native.transaction() as handle:
            native.pam.pam_acct_mgmt(handle, 0)

    # This is the only signalled process: our explicitly spawned, retained
    # Process identity. The helper exits itself after release or its own bound.
    worker = multiprocessing.get_context("fork").Process(target=account_worker)
    worker.start()
    try:
        deadline = time.monotonic() + 3
        while not (native.directory / "ready").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert (native.directory / "ready").exists()
        worker.kill()
        worker.join(timeout=3)
        assert not worker.is_alive()
        with native.admission.open('rb') as removal:
            with pytest.raises(BlockingIOError):
                fcntl.flock(removal, fcntl.LOCK_EX | fcntl.LOCK_NB)
        (native.directory / "status").write_text("0")
        with native.transaction() as retry:
            assert native.pam.pam_acct_mgmt(retry, 0) != 0
    finally:
        (native.directory / "release").touch()
        if worker.is_alive():
            worker.kill()
        worker.join(timeout=3)

    # Wait for the bounded descendant to exit and release its inherited lock,
    # without signalling it or leaving a child mutating shared fixture state.
    with native.lock.open("rb") as probe:
        deadline = time.monotonic() + 4
        while True:
            try:
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                assert time.monotonic() < deadline
                time.sleep(0.01)
    with native.transaction() as retry:
        assert native.pam.pam_acct_mgmt(retry, 0) == 0
        assert native.pam.pam_open_session(retry, 0) == 0


@pytest.mark.parametrize("user,service,expected", [
    ("private-account-canary", "sshd", False),
    ("private-account-canary", "gdm-autologin", False),
    ("private-account-canary", "polkit-1", False),
    ("private-account-canary", "systemd-user", True),
    ("ordinary-private-account", "gdm-password", True),
    ("ordinary-private-account", "polkit-1", True),
])
def test_real_pam_service_and_identity_scope(native, user, service, expected):
    with native.transaction(user=user, service=service) as handle:
        assert (native.pam.pam_acct_mgmt(handle, 0) == 0) == expected
        assert (native.pam.pam_open_session(handle, 0) == 0) == expected
    assert native.calls() == []


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
