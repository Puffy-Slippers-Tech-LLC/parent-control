"""Execute only in the guarded VM via make check-system, never on the host."""

import json
from pathlib import Path

import pytest

import system_guest as guest

pytestmark = [pytest.mark.system, pytest.mark.guest_mutating]


@pytest.fixture(autouse=True)
def require_isolated_guest():
    guest.guard()
    guest.enable_diagnostics()


def test_installed_package():
    guest.installed()


def test_first_install_requests_reboot():
    assert Path('/run/reboot-required').is_file()
    assert 'oh-no-parent-control' in Path('/run/reboot-required.pkgs').read_text().splitlines()


def test_reboot_applies_installation():
    before = json.loads((guest.PAYLOAD / 'before.json').read_text())
    assert before['boot_id'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    path = Path('/run/reboot-required.pkgs')
    assert not path.exists() or 'oh-no-parent-control' not in path.read_text().splitlines()
