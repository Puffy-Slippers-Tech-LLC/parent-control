"""Native GNOME monitor recovery in the guarded installed guest."""

import pytest

pytestmark = [pytest.mark.system, pytest.mark.guest_mutating]


def test_child_extension_monitor_native_recovery(record_testsuite_property):
    """Five finite recovery stages share the prepared monitor desktop and cleanup."""
    from system_extension_monitor import verify, verify_lifecycle, verify_failure_reporting
    from system_extension_parent import verify as verify_parent
    from system_extension_kiosk import verify as verify_kiosk

    # Keep the previous full-phase order and each verifier's fresh observers,
    # native witnesses, bounded waits and scoped restoration unchanged.
    for stage, check in (
            ('native-monitor-recovery', verify),
            ('session-and-broker-lifecycle', verify_lifecycle),
            ('failure-reporting-and-bus-loss', verify_failure_reporting),
            ('parent-controls-recovery', verify_parent),
            ('kiosk-approval-recovery', verify_kiosk)):
        print(f'onpc-system: stage=extension-validation validation={stage} state=started', flush=True)
        try:
            check(record_testsuite_property)
        except Exception as error:
            error.add_note('extension-validation: ' + stage)
            raise
        print(f'onpc-system: stage=extension-validation validation={stage} state=passed', flush=True)


def test_child_extension_login_unlock_recovery(record_testsuite_property):
    from system_extension_login import verify
    verify(record_testsuite_property)
