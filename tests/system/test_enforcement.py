"""Installed launch assertions; execute only through the guarded VM controller."""

import pytest

from system_enforcement import (
    native_policy_transition, native_probe_lifecycle, native_probe_storage_lifecycle,
    observe_catalog, provision_catalog, provision_native,
)

pytestmark = [pytest.mark.system, pytest.mark.guest_mutating]


@pytest.fixture(scope='module')
def native_accounts():
    return provision_native()


def test_native_command_policy_is_uid_scoped(native_accounts, record_testsuite_property):
    native_policy_transition(native_accounts, record_testsuite_property)


def test_native_probe_systemd_lifecycle(record_testsuite_property):
    # One continuous scenario also proves a settled refusal permits a fresh
    # independent generation; retain each stage's distinct evidence.
    for stage, refuse in (('success', False), ('refusal', True), ('after-refusal', False)):
        def record(key, value):
            record_testsuite_property(f'{key}.{stage}', value)
        native_probe_lifecycle(record, refuse_admission=refuse)


def test_native_probe_broker_storage_lifecycle(record_testsuite_property):
    native_probe_storage_lifecycle(record_testsuite_property)


def test_native_probe_broker_service_sandbox(record_testsuite_property):
    from system_probe_sandbox import native_probe_broker_sandbox
    native_probe_broker_sandbox(record_testsuite_property)


def test_native_probe_permanent_sender_loss(record_testsuite_property):
    for stage, lose in (('lost-sender', True), ('fresh-after-loss', False)):
        def record(key, value):
            record_testsuite_property(f'{key}.{stage}', value)
        native_probe_lifecycle(record, lose_sender=lose)


def test_native_whitespace_policy_is_uid_scoped(record_testsuite_property):
    accounts = provision_native('whitespace')
    native_policy_transition(accounts, record_testsuite_property, variant='whitespace')


def test_native_future_pattern_is_uid_scoped(record_testsuite_property):
    accounts = provision_native('pattern')
    native_policy_transition(accounts, record_testsuite_property, variant='pattern')


def test_native_missing_launcher_retains_policy(record_testsuite_property):
    accounts = provision_native('retention')
    native_policy_transition(accounts, record_testsuite_property, variant='retention')


def test_native_catalog_is_selected_child_scoped(native_accounts, record_testsuite_property):
    provision_catalog(native_accounts)
    observe_catalog(native_accounts, record_testsuite_property)


def test_kiosk_expiry_installed_runtime(record_testsuite_property):
    from system_session_expiry import verify_offline_recovery, verify_pam_scope
    verify_offline_recovery(record_testsuite_property)
    for service in ('gdm-password', 'gdm-autologin', 'login', 'sshd'):
        verify_pam_scope(service, record_testsuite_property)
