"""One real package removal/reboot/reinstall history in the guarded guest."""

import os

import pytest

from system_removal import remove, removed_rebooted, reinstalled_rebooted

pytestmark = [pytest.mark.system, pytest.mark.guest_mutating]


def test_remove_reboot_reinstall(record_testsuite_property):
    phase = os.environ['ONPC_SYSTEM_PHASE']
    {'removal': remove, 'removed-rebooted': removed_rebooted,
     'reinstalled-rebooted': reinstalled_rebooted}[phase](record_testsuite_property)
