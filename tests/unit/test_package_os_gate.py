"""Package admission depends on native prerequisites, not release identity."""

import pytest

from tests.support.package_scripts import Machine


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
@pytest.mark.parametrize('action', ['install', 'upgrade'])
@pytest.mark.parametrize('release', [
    'ID=ubuntu\nVERSION_ID="24.04"\n',
    'ID=debian\nVERSION_ID="13"\n',
    'ID=linuxmint\nID_LIKE=ubuntu\n',
    'ID=fedora\nVERSION_ID=45\nVARIANT_ID=server\n',
    'ID=opensuse-tumbleweed\nVERSION_ID=rolling\n',
    None,
])
def test_package_proceeds_without_distro_or_version_gate(tmp_path, distribution, action, release):
    machine = Machine(tmp_path, distribution)
    if release is None:
        (machine.root / "etc/os-release").unlink()
    else:
        machine.write("etc/os-release", release)
    machine.write('usr/lib/os-release', 'ID=unknown\nVERSION_ID=invalid\n')
    if action == "upgrade":
        machine.baseline()
    result = machine.run("preinst", action)
    assert result.returncode == 0, result.stderr
    assert (machine.root / "var/lib/oh-no-parent-control/migration-in-progress").exists()


def test_rpm_preflight_preserves_existing_pam_restrictions(tmp_path):
    machine = Machine(tmp_path, 'fedora')
    machine.write('etc/os-release', 'ID=fedora\nVERSION_ID=45\n')
    machine.write('test-bin/authselect', '#!/bin/sh\necho "local without-nullok"\n').chmod(0o755)
    result = machine.run('preinst', 'install')
    assert result.returncode != 0
    assert 'current PAM profile disallows the passwordless kiosk; preserving it' in result.stderr
    assert machine.commands == ''
    assert list((machine.root / 'var/lib/oh-no-parent-control').iterdir()) == []


def test_abort_upgrade_is_available_without_os_identity(tmp_path):
    machine = Machine(tmp_path)
    (machine.root / 'etc/os-release').unlink()
    result = machine.run("preinst", "abort-upgrade")
    assert result.returncode == 0, result.stderr
    assert machine.commands == ""
