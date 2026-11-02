"""Native GNOME monitor recovery in the guarded installed guest."""

import pytest

pytestmark = [pytest.mark.system, pytest.mark.guest_mutating]


def test_child_extension_monitor_native_recovery(record_testsuite_property):
    from system_extension_monitor import verify
    verify(record_testsuite_property)


def test_child_extension_monitor_session_lifecycle(record_testsuite_property):
    from system_extension_monitor import verify_lifecycle
    verify_lifecycle(record_testsuite_property)


def test_child_extension_failure_reporting(record_testsuite_property):
    from system_extension_monitor import verify_failure_reporting
    verify_failure_reporting(record_testsuite_property)


def test_child_extension_parent_recovery(record_testsuite_property):
    from system_extension_parent import verify
    verify(record_testsuite_property)


def test_child_extension_kiosk_recovery(record_testsuite_property):
    from system_extension_kiosk import verify
    verify(record_testsuite_property)
