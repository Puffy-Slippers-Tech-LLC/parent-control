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


@pytest.mark.parametrize('variant', ['denial-publication', 'mac-unload', 'account-finalization'])
def test_interrupted_finalization_retry(record_testsuite_property, variant):
    {variant: interrupted_finalization_retry,
     variant + '-retry-rebooted': finalization_retry_rebooted}[
         os.environ['ONPC_SYSTEM_PHASE']](record_testsuite_property, variant)


@pytest.mark.parametrize('variant', ['systemd-user-edit', 'gdm-password-link',
                                    'systemd-user-link', 'gdm-hook-link',
                                    'confinement-record-owner', 'confinement-record-link',
                                    'confinement-record-uid'])
def test_ownership_refusal_retry(record_testsuite_property, variant):
    {variant: ownership_refusal_retry,
     variant + '-retry-rebooted': ownership_retry_rebooted}[
         os.environ['ONPC_SYSTEM_PHASE']](record_testsuite_property, variant)


@pytest.mark.parametrize('variant', ['kiosk-marker-uid', 'home-owner', 'home-link',
                                    'home-mount', 'state-owner', 'state-link', 'state-mount'])
def test_identity_filesystem_refusal_retry(record_testsuite_property, variant):
    {variant: identity_filesystem_refusal_retry,
     variant + '-retry-rebooted': identity_filesystem_retry_rebooted}[
         os.environ['ONPC_SYSTEM_PHASE']](record_testsuite_property, variant)
