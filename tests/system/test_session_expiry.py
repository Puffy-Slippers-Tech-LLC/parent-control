"""Real GDM expiry and live GNOME recovery in the guarded installed guest."""

import pytest

pytestmark = [pytest.mark.system, pytest.mark.guest_mutating]


def test_kiosk_expiry_graphical_runtime(record_testsuite_property):
    from system_graphical_expiry import verify
    verify(record_testsuite_property)
