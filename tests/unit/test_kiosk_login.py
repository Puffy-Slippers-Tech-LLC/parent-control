"""Kiosk routing policy and real PAM transactions, without a live login or bus."""

import configparser
import json
import os
import shlex
import subprocess

import pytest

from tests.support.paths import ROOT
from tools.test_storage import scratch_descriptors


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
    ], check=True, capture_output=True, text=True, timeout=30,
        pass_fds=scratch_descriptors())
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
                            check=True, capture_output=True, text=True, timeout=5,
                            pass_fds=scratch_descriptors())
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
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=5,
        pass_fds=scratch_descriptors())
    assert result.returncode == 0
    assert not marker.exists()
