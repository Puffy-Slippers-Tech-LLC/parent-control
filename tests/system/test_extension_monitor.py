"""Native GNOME monitor recovery in the guarded installed guest."""

import pytest

pytestmark = [pytest.mark.system, pytest.mark.guest_mutating]


def test_child_extension_monitor_native_recovery(record_testsuite_property):
    from system_extension_monitor import verify
    verify(record_testsuite_property)
