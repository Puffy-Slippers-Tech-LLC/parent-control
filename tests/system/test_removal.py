"""One real remove/reinstall/purge history in the guarded guest."""

import os

import pytest

from system_removal import (remove, removed_rebooted, reinstalled_rebooted,
                            purged_rebooted, purge_reinstalled_rebooted,
                            aborted_cleanup_rollback_retry, rollback_rearmed_rebooted)

pytestmark = [pytest.mark.system, pytest.mark.guest_mutating]


def test_remove_reboot_reinstall(record_testsuite_property):
    phase = os.environ['ONPC_SYSTEM_PHASE']
    {'removal': remove, 'removed-rebooted': removed_rebooted,
     'reinstalled-rebooted': reinstalled_rebooted, 'purged-rebooted': purged_rebooted,
     'purge-reinstalled-rebooted': purge_reinstalled_rebooted}[phase](record_testsuite_property)


def test_aborted_cleanup_rollback_retry(record_testsuite_property):
    {'rollback': aborted_cleanup_rollback_retry,
     'rollback-rearmed-rebooted': rollback_rearmed_rebooted}[
         os.environ['ONPC_SYSTEM_PHASE']](record_testsuite_property)
