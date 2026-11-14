"""Native GNOME monitor recovery in the guarded installed guest."""

import pytest
from system_assertions import validation_stage

pytestmark = [pytest.mark.system, pytest.mark.guest_mutating]


def test_child_extension_monitor_native_recovery(record_testsuite_property, capfd):
    """Five finite recovery stages share the prepared monitor desktop and cleanup."""
    from system_extension_monitor import verify, verify_lifecycle, verify_failure_reporting
    from system_extension_monitor import renew_child_desktop, request_parent_desktop
    from system_extension_parent import verify as verify_parent
    from system_extension_kiosk import verify as verify_kiosk

    # Keep each stage's desktop preconditions as well as its observers and
    # assertions. Parent entry locks the child and belongs after its histories.
    for stage, check in (
            ('native-monitor-recovery', verify),
            ('session-and-broker-lifecycle', verify_lifecycle),
            ('failure-reporting-and-bus-loss', verify_failure_reporting),
            ('parent-controls-recovery', verify_parent),
            ('kiosk-approval-recovery', verify_kiosk)):
        with validation_stage('extension-validation', stage):
            if stage in ('failure-reporting-and-bus-loss', 'parent-controls-recovery'):
                renew_child_desktop()
            if stage == 'parent-controls-recovery':
                # The fixed request must reach the host while pytest is live.
                with capfd.disabled():
                    request_parent_desktop()
            check(record_testsuite_property)


def test_child_extension_login_unlock_recovery(record_testsuite_property):
    from system_extension_login import verify
    verify(record_testsuite_property)
