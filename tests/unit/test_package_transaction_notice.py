"""Real APT, isolated package records, and an unprivileged dpkg fixture.

The fixture loads dpkg hook configuration before each invocation, runs the
package's preinst bootstrap during unpack, and executes the packaged notice
helper after configuration/triggers. No host package or service is changed.
"""

import os
from pathlib import Path
import subprocess
import sys

import pytest
from tests.support.terminal import capture
from tests.support.shell import relocate_system_paths


from tests.support.paths import ROOT
PACKAGE = "oh-no-parent-control"
SUCCESS = "PASS: Oh No! Parent Control package configuration completed successfully."
REBOOT = "*** REBOOT REQUIRED: reboot before using the kiosk session. ***"
PENDING = "run/oh-no-parent-control-package-configuration-complete"
HOOK = "etc/dpkg/dpkg.cfg.d/99-oh-no-parent-control-notice"
RED = f"\033[1;31m{REBOOT}\033[0m"
GREEN_SUCCESS = f"\033[1;32m{SUCCESS}\033[0m"


def record(name, state="installed"):
    return (
        f"Package: {name}\nStatus: install ok {state}\n"
        "Priority: optional\nSection: misc\nInstalled-Size: 1\n"
        "Maintainer: Test <test@example.invalid>\nArchitecture: amd64\n"
        "Version: 1.0\nDescription: Package notice fixture\n\n"
    )


@pytest.fixture
def notice_machine(tmp_path):
    for path in ("run", "db", "etc/dpkg/dpkg.cfg.d", "usr/libexec"):
        (tmp_path / path).mkdir(parents=True)
    status = tmp_path / "db/status"
    status.write_text("")
    (tmp_path / "run/reboot-required.pkgs").write_text(PACKAGE + "\n")
    helper = tmp_path / "usr/libexec/oh-no-parent-control-package-notice"
    helper.write_text(
        (ROOT / "tools/package_notice").read_text()
        .replace("/run/", str(tmp_path) + "/run/")
        .replace("dpkg-query -W", f"dpkg-query --admindir={tmp_path / 'db'} -W")
    )
    helper.chmod(0o755)
    # Exercise the exact preinst bootstrap without its account/service work;
    # the complete maintainer script has separate filesystem/service tests.
    bootstrap = (ROOT / "debian/preinst").read_text().split(
        '\nif [ "$1" = install ]', 1
    )[0] + "\nprepare_package_notice\n"
    bootstrap = relocate_system_paths(bootstrap, tmp_path, ("/etc/", "/run/", "/usr/"))
    bootstrap = bootstrap.replace("-o root -g root ", "")
    (tmp_path / "bootstrap").write_text(bootstrap)
    return tmp_path, status, helper




@pytest.mark.parametrize("terminal", [None, "xterm", "dumb"])
def test_install_reboot_notice_is_last_printed_and_red_on_capable_terminal(
        notice_machine, terminal):
    _, _, helper = notice_machine
    result, output = capture([str(helper), "--configured"], os.environ, terminal)
    assert result.returncode == 0, output
    reboot = RED if terminal == "xterm" else REBOOT
    assert output.rstrip().splitlines()[-2:] == [GREEN_SUCCESS, reboot], output
    assert output.count(SUCCESS) == output.count(REBOOT) == 1


@pytest.mark.parametrize("frontend", ["apt", "apt-get"])
@pytest.mark.parametrize("failure", [False, True])
def test_first_apt_install_prints_notice_after_configuration_and_triggers(
        notice_machine, frontend, failure):
    root, status, helper = notice_machine
    assert not (root / HOOK).exists(), "this must model a clean first install"
    for path in ("cache/archives/partial", "state/lists/partial", "log",
                 "apt.conf.d", "sources.list.d"):
        (root / path).mkdir(parents=True)
    debs = []
    for name in (PACKAGE, "gnome-kiosk-script-session"):
        control = root / name / "DEBIAN/control"
        control.parent.mkdir(parents=True)
        control.write_text(record(name).replace("Status: install ok installed\n", ""))
        deb = root / f"{name}.deb"
        subprocess.run(
            ["dpkg-deb", "--build", "--root-owner-group", str(control.parent.parent), str(deb)],
            check=True, capture_output=True, timeout=10,
        )
        debs.append(str(deb))
    for name, state in (("unpacked", "unpacked"), ("configured", "installed")):
        (root / name).write_text(
            record(PACKAGE, state) + record("gnome-kiosk-script-session", state)
        )
    (root / "failed").write_text(
        record(PACKAGE) + record("gnome-kiosk-script-session", "half-configured")
    )
    dpkg = root / "fake-dpkg"
    dpkg.write_text(f"#!{sys.executable}\n" + r'''
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).parent
arguments = sys.argv[1:]
hook = root / "etc/dpkg/dpkg.cfg.d/99-oh-no-parent-control-notice"
# This read intentionally precedes preinst: a running dpkg does not reload
# its configuration, but the next dpkg invocation does.
hooks = hook.read_text().splitlines() if hook.exists() else []
status = root / "db/status"
env = {**os.environ, "DPKG_FRONTEND_LOCKED": "true"}
action = None
failure = False

def report(state):
    if "--status-fd" in arguments:
        fd = int(arguments[arguments.index("--status-fd") + 1])
        for package in ("oh-no-parent-control", "gnome-kiosk-script-session"):
            os.write(fd, f"status: {package}:amd64: {state}\n".encode())

if "--unpack" in arguments:
    action = "unpack"
    subprocess.run(["/bin/sh", str(root / "bootstrap")], check=True, env=env)
    status.write_text((root / "unpacked").read_text())
    report("half-installed")
    report("unpacked")
elif "--configure" in arguments:
    action = "configure"
    report("half-configured")
    print("Setting up oh-no-parent-control (1.0) ...", flush=True)
    subprocess.run([str(root / "usr/libexec/oh-no-parent-control-package-notice"),
                    "--configured"], check=True, env=env)
    print("Setting up gnome-kiosk-script-session (50.0-1) ...", flush=True)
    failure = os.environ["NOTICE_FIXTURE_FAILURE"] == "1"
    status.write_text((root / ("failed" if failure else "configured")).read_text())
    for package in ("hicolor-icon-theme", "gnome-menus", "libc-bin", "man-db", "dbus", "desktop-file-utils"):
        print(f"Processing triggers for {package} ...", flush=True)
    if not failure:
        report("installed")

if action:
    for line in hooks:
        assert line.startswith("post-invoke=")
        subprocess.run(["/bin/sh", "-c", line.removeprefix("post-invoke=")],
                       check=True, env={**env, "DPKG_HOOK_ACTION": action})
sys.exit(1 if failure else 0)
''')
    dpkg.chmod(0o755)
    config = root / "apt.conf"
    config.write_text(
        f'Dir::Etc::Parts "{root / "apt.conf.d"}";\n'
        'Dir::Etc::main "-";\nDir::Etc::sourcelist "/dev/null";\n'
        f'Dir::Etc::sourceparts "{root / "sources.list.d"}";\n'
        f'Dir::State "{root / "state"}";\nDir::State::status "{status}";\n'
        f'Dir::Cache "{root / "cache"}";\nDir::Log "{root / "log"}";\n'
        f'Dir::Bin::dpkg "{dpkg}";\n'
        'APT::Architecture "amd64";\nAPT::Color "false";\n'
        'DPkg::Use-Pty "false";\nDebug::NoLocking "true";\n'
    )
    result = subprocess.run(
        [frontend, "-y", "install", *debs],
        env={**os.environ, "APT_CONFIG": str(config),
             "NOTICE_FIXTURE_FAILURE": "1" if failure else "0"},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=15,
    )
    output = result.stdout
    assert "Setting up gnome-kiosk-script-session" in output, output
    assert "Processing triggers for desktop-file-utils" in output, output
    assert (result.returncode == 0) != failure, output
    if failure:
        assert SUCCESS not in output
        assert REBOOT not in output
    else:
        assert output.splitlines()[-2:] == [GREEN_SUCCESS, REBOOT], output
        assert output.count(SUCCESS) == output.count(REBOOT) == 1
        assert not (root / PENDING).exists()


@pytest.mark.parametrize("state", ["unpacked", "half-configured", "half-installed",
                                 "triggers-pending", "triggers-awaited"])
def test_notice_waits_for_all_configuration_and_trigger_passes(notice_machine, state):
    root, status, helper = notice_machine
    status.write_text(record(PACKAGE) + record("fixture", state))
    pending = root / PENDING
    pending.touch()
    env = {**os.environ, "DPKG_HOOK_ACTION": "configure"}
    command = [str(helper), "--after-dpkg"]
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == ""
    assert pending.exists()
    status.write_text(record(PACKAGE) + record("fixture"))
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert SUCCESS in result.stdout
    assert REBOOT in result.stderr
    assert not pending.exists()
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert result.stdout == result.stderr == "", "later invocations must not repeat PASS"
