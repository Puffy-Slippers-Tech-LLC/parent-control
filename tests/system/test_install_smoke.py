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


def test_previous_package_policy_preservation(record_testsuite_property):
    from system_previous_upgrade import prepare, verify_updated, verify_reboot
    phase = os.environ['ONPC_SYSTEM_PHASE']
    guest.require(phase in ('previous-policy', 'installed', 'rebooted'),
                  'previous-upgrade:test-phase')
    {'previous-policy': prepare, 'installed': verify_updated, 'rebooted': verify_reboot}[
        phase](record_testsuite_property)


def test_trusted_native_upgrade_fixtures(record_testsuite_property):
    from system_trusted_fixtures import qualify
    guest.require(os.environ['ONPC_SYSTEM_PHASE'] == 'trusted-fixtures',
                  'trusted-fixtures:test-phase')
    qualify(record_testsuite_property)


def test_first_configuration_interruption_retry(record_testsuite_property):
    from system_first_configure import exercise, verify_reboot
    {'first-configure': exercise, 'first-configure-rebooted': verify_reboot}[
        os.environ['ONPC_SYSTEM_PHASE']](record_testsuite_property)


@pytest.mark.parametrize('variant', ['plain', 'distro-profile', 'administrator-override',
                                   'pending-vendor'])
def test_pam_environment_installation_variants(variant, record_testsuite_property):
    from system_pam_variants import exercise, verify_reboot, remove, verify_removed_reboot
    phase = os.environ['ONPC_SYSTEM_PHASE']
    if phase == f'pam-{variant}':
        exercise(record_testsuite_property, variant)
    elif phase == f'pam-{variant}-rebooted':
        verify_reboot(record_testsuite_property, variant)
    elif phase == f'pam-{variant}-configured-rebooted':
        remove(record_testsuite_property, variant)
    else:
        guest.require(phase == f'pam-{variant}-removed-rebooted', 'pam-variants:test-phase')
        verify_removed_reboot(record_testsuite_property, variant)


def test_kiosk_account_classification_survives_reboot(record_testsuite_property):
    from system_kiosk_accounts import exercise, verify_reboot
    from system_kiosk_admission import verify as verify_admission, verify_gates
    from system_kiosk_confinement import verify_session_composition

    phase = os.environ['ONPC_SYSTEM_PHASE']
    guest.require(phase in ('installed', 'rebooted'), 'kiosk-accounts:test-phase')
    pending = phase == 'installed'
    rules_before = guest.execution_rule_state() if pending else None
    guest.installed(reboot_required=pending)
    if pending:
        guest.require(guest.reboot_requested(), 'kiosk-accounts:reboot-not-requested')
        # Routing mutations precede the retained-metadata witness. Subsequent
        # gate observations must preserve the exact cache saved for reboot.
        verify_admission(record_testsuite_property)
    else:
        guest.require(guest.reboot_cleared(), 'kiosk-accounts:reboot-request-retained')
    action = exercise if phase == 'installed' else verify_reboot
    action(record_testsuite_property)
    verify_gates(record_testsuite_property)
    verify_session_composition(record_testsuite_property)
    if pending:
        guest.verify_reboot_gate()
        guest.require(guest.execution_rule_state() == rules_before,
                      'kiosk-accounts:policy-changed-before-reboot')
