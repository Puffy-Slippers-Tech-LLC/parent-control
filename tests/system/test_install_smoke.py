"""Execute only in the guarded VM via make check-system, never on the host."""

import json
import os
from pathlib import Path

import pytest

import system_guest as guest

pytestmark = [pytest.mark.system, pytest.mark.guest_mutating]


@pytest.fixture(autouse=True)
def require_isolated_guest():
    guest.guard()
    guest.enable_diagnostics()


def test_installed_package():
    phase = os.environ['ONPC_SYSTEM_PHASE']
    assert phase in ('installed', 'rebooted')
    guest.installed(reboot_required=phase == 'installed')


def test_first_install_requests_reboot():
    assert guest.reboot_requested()


def test_reboot_applies_installation():
    before = json.loads((guest.PAYLOAD / 'before.json').read_text())
    assert before['boot_id'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert guest.reboot_cleared()
