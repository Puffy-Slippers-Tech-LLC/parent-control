"""Installed launch assertions; execute only through the guarded VM controller."""

import pytest

from system_enforcement import (
    native_policy_transition, observe_catalog, provision_catalog, provision_native,
)

pytestmark = [pytest.mark.system, pytest.mark.guest_mutating]


@pytest.fixture(scope='module')
def native_accounts():
    return provision_native()


def test_native_command_policy_is_uid_scoped(native_accounts, record_testsuite_property):
    native_policy_transition(native_accounts, record_testsuite_property)


def test_native_catalog_is_selected_child_scoped(native_accounts, record_testsuite_property):
    provision_catalog(native_accounts)
    observe_catalog(native_accounts, record_testsuite_property)
