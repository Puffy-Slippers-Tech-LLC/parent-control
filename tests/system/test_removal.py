"""One real remove/reinstall/purge history in the guarded guest."""

import os

import pytest

from system_removal import (remove, removed_rebooted, reinstalled_rebooted,
                            purged_rebooted, purge_reinstalled_rebooted,
                            aborted_cleanup_rollback_retry, rollback_rearmed_rebooted,
                            interrupted_finalization_retry, finalization_retry_rebooted,
                            ownership_refusal_retry, ownership_retry_rebooted,
                            identity_filesystem_refusal_retry,
                            identity_filesystem_retry_rebooted,
                            rpm_posterase_recovery, rpm_posterase_reinstalled_rebooted)
from system_removal_ownership import OWNERSHIP_GROUPS
from system_removal_identity import IDENTITY_FILESYSTEM_GROUPS

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


def test_rpm_posterase_recovery(record_testsuite_property):
    {'rpm-posterase': rpm_posterase_recovery,
     'rpm-posterase-reinstalled-rebooted': rpm_posterase_reinstalled_rebooted}[
         os.environ['ONPC_SYSTEM_PHASE']](record_testsuite_property)


@pytest.mark.parametrize('variant', ['denial-publication', 'account-finalization'])
def test_interrupted_finalization_retry(record_testsuite_property, variant):
    {variant: interrupted_finalization_retry,
     variant + '-retry-rebooted': finalization_retry_rebooted}[
         os.environ['ONPC_SYSTEM_PHASE']](record_testsuite_property, variant)


@pytest.mark.parametrize('variant', tuple(OWNERSHIP_GROUPS))
def test_ownership_refusal_retry(record_testsuite_property, variant):
    phase = os.environ['ONPC_SYSTEM_PHASE']
    variants = OWNERSHIP_GROUPS[variant]
    for index, current in enumerate(variants):
        if phase == (current if index == 0 else current + '-reinstalled-rebooted'):
            ownership_refusal_retry(record_testsuite_property, current,
                                    continue_after=variants[index - 1] if index else None)
            return
        if phase == current + '-retry-rebooted':
            ownership_retry_rebooted(record_testsuite_property, current,
                next_variant=variants[index + 1] if index + 1 < len(variants) else None)
            return
    raise AssertionError('ownership:unselected-phase')


@pytest.mark.parametrize('variant', tuple(IDENTITY_FILESYSTEM_GROUPS))
def test_identity_filesystem_refusal_retry(record_testsuite_property, variant):
    phase = os.environ['ONPC_SYSTEM_PHASE']
    variants = IDENTITY_FILESYSTEM_GROUPS[variant]
    for index, current in enumerate(variants):
        if phase == (current if index == 0 else current + '-reinstalled-rebooted'):
            identity_filesystem_refusal_retry(record_testsuite_property, current,
                continue_after=variants[index - 1] if index else None)
            return
        if phase == current + '-retry-rebooted':
            identity_filesystem_retry_rebooted(record_testsuite_property, current,
                next_variant=variants[index + 1] if index + 1 < len(variants) else None)
            return
    raise AssertionError('identity-filesystem:unselected-phase')
