"""Semantic smoke coverage for each GTK preview surface."""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.ui


def _assert_preview_controls(application, wait_for_accessible_node, capture_ui_snapshot,
                             collect_application_logs, log_path, controls, snapshot_name):
    snapshot = capture_ui_snapshot(application, snapshot_name)
    assert snapshot.read_text(encoding="utf-8")
    for label, role in controls:
        try:
            wait_for_accessible_node(application, label, role)
        except AssertionError as error:
            raise AssertionError(
                f"{error}\nApplication log:\n{collect_application_logs(log_path)}",
            ) from error


def test_parent_preview_smoke(launch_ui, wait_for_accessible_node,
                              capture_ui_snapshot, collect_application_logs):
    application, log_path = launch_ui("parent_preview")
    # The selected person's name is intentionally the DropDown's AT-SPI name;
    # assert its stable, purpose-based label relation instead.
    wait_for_accessible_node(application, "Child account", "combo box", labelled=True)
    _assert_preview_controls(
        application, wait_for_accessible_node, capture_ui_snapshot,
        collect_application_logs, log_path,
        (
            ("Screen time limit", "switch"),
            ("Daily Time Allowance", "combo box"),
            ("Revoke one-time access", "button"),
        ),
        "parent-preview",
    )


@pytest.mark.parametrize(
    ("overlay", "surface"),
    ((False, "kiosk"), (True, "child-overlay")),
)
def test_shared_request_preview_smoke(launch_ui, wait_for_accessible_node,
                                      capture_ui_snapshot, collect_application_logs,
                                      overlay, surface):
    launcher = "child_overlay_preview" if overlay else "kiosk_preview"
    application, log_path = launch_ui(launcher)
    _assert_preview_controls(
        application, wait_for_accessible_node, capture_ui_snapshot,
        collect_application_logs, log_path,
        (
            ("Child account", "button"),
            ("Approving parent", "button"),
            ("Allow soft blocked apps", "switch"),
            ("REQUEST", "button"),
            ("CANCEL", "button"),
        ),
        f"{surface}-preview",
    )
