"""Run real APT with an isolated database and a fake, unprivileged dpkg.

No host package, APT configuration, reboot marker or service is changed.
"""

import os

import pytest
from tests.support.terminal import capture


from tests.support.paths import ROOT
NOTICE = "*** REBOOT REQUIRED: reboot to finish removing Oh No! Parent Control. ***"
HOOK = "99zz-oh-no-parent-control-reboot-notice"


@pytest.mark.parametrize("frontend,action", [
    ("apt", "remove"), ("apt-get", "remove"),
    ("apt", "purge"), ("apt-get", "purge"), ("make", "remove"),
])
@pytest.mark.parametrize("terminal", [None, "xterm", "dumb"])
@pytest.mark.parametrize("failure", [False, True])
def test_apt_removal_notice_follows_triggers(tmp_path, frontend, action, terminal, failure):
    """Last printed output is the removal notice; red on a capable terminal."""
    for path in ("cache/archives/partial", "state/lists/partial", "log", "sources.list.d"):
        (tmp_path / path).mkdir(parents=True)
    database = tmp_path / "dpkg"
    database.mkdir()
    status = database / "status"
    record = (
        "Package: oh-no-parent-control\n"
        "Status: install ok installed\n"
        "Priority: optional\nSection: misc\nInstalled-Size: 1\n"
        "Maintainer: Test <test@example.invalid>\n"
        "Architecture: amd64\nVersion: 1.0\nDescription: Test fixture\n\n"
    )
    status.write_text(record)
    marker = tmp_path / "reboot-required.pkgs"
    # A prior install can already have requested a reboot. Failed removal
    # must not turn that into a removal-success reminder.
    marker.write_text("oh-no-parent-control\n")
    parts = tmp_path / "apt.conf.d"
    parts.mkdir()
    hook = parts / HOOK
    hook.write_text(
        (ROOT / "data/apt" / HOOK).read_text()
        .replace("/run/reboot-required.pkgs", str(marker))
        .replace("dpkg-query -W", f"dpkg-query --admindir={database} -W")
    )
    final_status = tmp_path / "final-status"
    final_status.write_text(
        "" if action == "purge" else record.replace(
            "install ok installed", "deinstall ok config-files"
        )
    )
    dpkg = tmp_path / "fake-dpkg"
    dpkg.write_text(
        "#!/bin/sh\n"
        "case $* in\n"
        "  *--pending*) exit 0;;\n"
        "  *--remove*|*--purge*)\n"
        "    echo 'Fixture dpkg removal'\n"
        + ("    exit 1\n" if failure else (
            f"    cp '{final_status}' '{status}'\n"
            f"    printf '%s\\n' oh-no-parent-control > '{marker}'\n"
            + (f"    rm '{hook}'\n" if action == "purge" else "")
            + "    echo 'Processing triggers for desktop-file-utils ...'\n"
            "    echo 'Processing triggers for libc-bin ...'\n"
            "    previous=''\n"
            "    for argument do\n"
            "      if [ \"$previous\" = --status-fd ]; then\n"
            "        for state in half-configured half-installed config-files "
            + ("not-installed " if action == "purge" else "")
            + "; do\n"
            "          printf 'status: oh-no-parent-control:amd64: %s\\n' \"$state\" >&\"$argument\"\n"
            "        done\n"
            "        break\n"
            "      fi\n"
            "      previous=$argument\n"
            "    done\n"
        ))
        + "    ;;\nesac\nexit 0\n"
    )
    dpkg.chmod(0o755)
    config = tmp_path / "apt.conf"
    config.write_text(
        f'Dir::Etc::Parts "{parts}";\n'
        'Dir::Etc::main "-";\n'
        'Dir::Etc::sourcelist "/dev/null";\n'
        f'Dir::Etc::sourceparts "{tmp_path / "sources.list.d"}";\n'
        f'Dir::State "{tmp_path / "state"}";\n'
        f'Dir::State::status "{status}";\n'
        f'Dir::Cache "{tmp_path / "cache"}";\n'
        f'Dir::Log "{tmp_path / "log"}";\n'
        f'Dir::Bin::dpkg "{dpkg}";\n'
        'APT::Architecture "amd64";\n'
        'APT::Color "false";\n'
        'DPkg::Use-Pty "false";\n'
        'Debug::NoLocking "true";\n'
    )
    env = {**os.environ, "APT_CONFIG": str(config), "TERM": terminal or "xterm"}
    command = [frontend, "-y", action, "oh-no-parent-control"]
    if frontend == "make":
        command = [
            "make", "--no-print-directory", "-f", str(ROOT / "Makefile"),
            "uninstalldeb", "APT=apt -y",
        ]
    result, output = capture(command, env, terminal)
    assert "Fixture dpkg removal" in output, output
    if failure:
        assert result.returncode != 0, output
        assert NOTICE not in output
    else:
        assert result.returncode == 0, output
        assert "Processing triggers for libc-bin" in output
        expected = f"\033[1;31m{NOTICE}\033[0m" if terminal == "xterm" else NOTICE
        assert output.rstrip().splitlines()[-1] == expected, output
        assert output.count(NOTICE) == 1
        if action == "purge":
            assert not hook.exists(), "APT must run the already-loaded hook after purge"
