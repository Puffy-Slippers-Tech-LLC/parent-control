"""Real GDM expiry and live GNOME recovery in the guarded installed guest."""

import pytest

pytestmark = [pytest.mark.system, pytest.mark.guest_mutating]


def test_kiosk_expiry_graphical_runtime(record_testsuite_property):
    from system_graphical_expiry import verify
    verify(record_testsuite_property)


def test_usage_reader_failure_recovery(record_testsuite_property):
    from system_session_expiry import verify_usage_reader_recovery
    verify_usage_reader_recovery(record_testsuite_property)


def test_foreground_revocation(record_testsuite_property):
    from system_graphical_expiry import verify_foreground_revoke
    verify_foreground_revoke(record_testsuite_property)
