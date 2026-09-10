"""Exercise the real preinst with release files and effects confined to a fixture."""

import pytest

from tests.support.package_scripts import machine


@pytest.mark.parametrize("action", ["install", "upgrade"])
@pytest.mark.parametrize("release,reason", [
    ('ID=debian\nVERSION_ID="28.04"\n', "not Ubuntu"),
    ('ID=linuxmint\nID_LIKE=ubuntu\nVERSION_ID="28.04"\n', "not Ubuntu"),
    ('ID=ubuntu\nVERSION_ID="24.04"\n', "Please upgrade Ubuntu"),
    ('ID=ubuntu\nVERSION_ID="26.03"\n', "Please upgrade Ubuntu"),
    ('ID=ubuntu\n', "could not be verified"),
    ('ID=ubuntu\nVERSION_ID="rolling"\n', "could not be verified"),
    ('ID=ubuntu\nVERSION_ID="26.04extra"\n', "could not be verified"),
    ('VERSION_ID="26.04"\n', "not Ubuntu"),
    ('', "not Ubuntu"),
    (None, "could not be identified"),
])
def test_unsupported_os_rejected_before_effects(machine, action, release, reason):
    if release is None:
        (machine.root / "etc/os-release").unlink()
    else:
        machine.write("etc/os-release", release)
    result = machine.run("preinst", action, ID="ubuntu", VERSION_ID="28.04")
    assert result.returncode != 0
    assert "requires Ubuntu 26.04 or newer" in result.stderr
    assert reason in result.stderr
    assert machine.commands == ""
    assert list((machine.root / "var/lib/oh-no-parent-control").iterdir()) == []
    assert not (machine.root / "etc/dpkg").exists()


@pytest.mark.parametrize("action", ["install", "upgrade"])
@pytest.mark.parametrize("version", ["26.04", "26.10", "28.04", "30.04"])
def test_supported_os_proceeds(machine, action, version):
    machine.write("etc/os-release", f'ID=ubuntu\nVERSION_ID="{version}"\n')
    if action == "upgrade":
        machine.baseline()
    result = machine.run("preinst", action)
    assert result.returncode == 0, result.stderr
    assert (machine.root / "var/lib/oh-no-parent-control/migration-in-progress").exists()


def test_release_fallback_and_etc_precedence(machine):
    machine.write("usr/lib/os-release", 'ID=ubuntu\nVERSION_ID="26.04"\n')
    machine.write("etc/os-release", 'ID=debian\nVERSION_ID="13"\n')
    assert machine.run("preinst", "install").returncode != 0
    assert machine.commands == ""
    (machine.root / "etc/os-release").unlink()
    result = machine.run("preinst", "install")
    assert result.returncode == 0, result.stderr


def test_abort_upgrade_is_not_blocked_on_unsupported_os(machine):
    machine.write("etc/os-release", 'ID=debian\n')
    result = machine.run("preinst", "abort-upgrade")
    assert result.returncode == 0, result.stderr
    assert machine.commands == ""
