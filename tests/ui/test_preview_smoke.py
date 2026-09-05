"""Semantic smoke coverage for each GTK preview surface."""

from __future__ import annotations

import json

import pytest

from common.oh_no_parent_control_ui.test_identities import preview_users


pytestmark = pytest.mark.ui


def _assert_preview_controls(application, wait_for_accessible_node, capture_ui_snapshot,
                             collect_application_logs, log_path, controls, snapshot_name):
    snapshot = capture_ui_snapshot(application, snapshot_name)
    assert snapshot.read_text(encoding="utf-8")
    for control in controls:
        label, role, *options = control
        try:
            wait_for_accessible_node(application, label, role, labelled=bool(options))
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
            ("Daily time allowance", "button"),
            ("Revoke one-time access", "button"),
        ),
        "parent-preview",
    )


def test_parent_component_scripted_broker_behavior(launch_ui, wait_for_accessible_node,
                                                    capture_ui_snapshot,
                                                    collect_application_logs):
    """The production window consumes injected broker state through its UI."""
    application, log_path = launch_ui(
        "parent_component_preview",
        environment_overrides={"ONPC_PARENT_COMPONENT_SCENARIO": "normal"},
    )
    try:
        wait_for_accessible_node(application, "Child account", "combo box", labelled=True)
        wait_for_accessible_node(application, "Screen time limit", "switch")
        wait_for_accessible_node(
            application, "Daily time allowance", "button",
        )
        wait_for_accessible_node(application, "Revoke one-time access", "button")
    except AssertionError as error:
        snapshot = capture_ui_snapshot(application, "parent-scripted-broker")
        raise AssertionError(
            f"{error}\nSnapshot:\n{snapshot.read_text(encoding='utf-8')}\n"
            f"Application log:\n{collect_application_logs(log_path)}"
        ) from error


@pytest.mark.parametrize("scenario", ("denied", "unavailable"))
def test_parent_denied_or_unavailable_never_exposes_management_window(launch_ui, scenario):
    """A failed authorization/discovery check closes before controls are usable."""
    process, _log_path = launch_ui(
        "parent_component_preview",
        environment_overrides={"ONPC_PARENT_COMPONENT_SCENARIO": scenario},
        wait_for_application=False,
    )
    assert process.wait(timeout=5) == 0


def test_parent_no_child_message_is_explicit(launch_ui, wait_for_accessible_node):
    no_children, _log_path = launch_ui(
        "parent_component_preview",
        environment_overrides={"ONPC_PARENT_COMPONENT_SCENARIO": "no-users"},
    )
    wait_for_accessible_node(
        no_children, "No interactive non-administrator account was found.", "label",
    )


def test_parent_loading_state_disables_conflicting_controls(launch_ui,
                                                             wait_for_accessible_node,
                                                             wait_for_accessible_state):
    loading, _log_path = launch_ui(
        "parent_component_preview",
        environment_overrides={"ONPC_PARENT_COMPONENT_SCENARIO": "loading"},
    )
    enabled = wait_for_accessible_node(loading, "Screen time limit", "switch")
    allowance = wait_for_accessible_node(
        loading, "Daily time allowance", "button",
    )
    assert not enabled.sensitive
    assert not allowance.sensitive
    wait_for_accessible_state(lambda: enabled.sensitive, "loaded screen-time switch")
    wait_for_accessible_state(lambda: allowance.sensitive, "loaded daily allowance")


def test_parent_time_status_retries(launch_ui, wait_for_accessible_node,
                                    wait_for_accessible_state, tmp_path):
    events_path = tmp_path / "status-events.jsonl"
    retrying, _log_path = launch_ui(
        "parent_component_preview",
        environment_overrides={
            "ONPC_PARENT_COMPONENT_SCENARIO": "status-retries",
            "ONPC_PARENT_COMPONENT_EVENTS_PATH": str(events_path),
        },
    )
    wait_for_accessible_node(retrying, "47 minutes")
    wait_for_accessible_state(
        lambda: events_path.exists()
        and sum(json.loads(line)["event"] == "get_time_status"
                for line in events_path.read_text(encoding="utf-8").splitlines()) == 3,
        "two failed status attempts followed by a successful retry",
    )


def test_parent_time_status_reports_unavailable(launch_ui, wait_for_accessible_node):
    unavailable, _log_path = launch_ui(
        "parent_component_preview",
        environment_overrides={"ONPC_PARENT_COMPONENT_SCENARIO": "status-unavailable"},
    )
    wait_for_accessible_node(unavailable, "Unavailable")


def test_parent_screen_time_change_autosaves_and_never_offers_a_grant(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state,
        capture_ui_snapshot, tmp_path):
    events_path = tmp_path / "save-events.jsonl"
    application, _log_path = launch_ui(
        "parent_component_preview",
        environment_overrides={"ONPC_PARENT_COMPONENT_EVENTS_PATH": str(events_path)},
    )
    enabled = wait_for_accessible_node(application, "Screen time limit", "switch")
    assert enabled.checked
    assert enabled.do_action(0)
    wait_for_accessible_state(
        lambda: events_path.exists() and "set_parent_control" in events_path.read_text(),
        "screen-time auto-save",
    )
    records = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    assert [record for record in records if record["event"] == "set_parent_control"] == [{
        "daily_limit_minutes": 90,
        "enabled": False,
        "event": "set_parent_control",
        "uid": 1001,
    }]
    tree = capture_ui_snapshot(application, "parent-no-grant").read_text(encoding="utf-8")
    assert "Grant additional time" not in tree
    assert "Approve time" not in tree


def test_parent_failed_save_restores_visible_value(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state, tmp_path):
    events_path = tmp_path / "failed-save-events.jsonl"
    application, _log_path = launch_ui(
        "parent_component_preview",
        environment_overrides={
            "ONPC_PARENT_COMPONENT_SCENARIO": "save-fails",
            "ONPC_PARENT_COMPONENT_EVENTS_PATH": str(events_path),
        },
    )
    enabled = wait_for_accessible_node(application, "Screen time limit", "switch")
    assert enabled.checked
    assert enabled.do_action(0)
    wait_for_accessible_state(
        lambda: events_path.exists() and "set_parent_control" in events_path.read_text(),
        "failed preference save request",
    )
    wait_for_accessible_state(lambda: enabled.checked, "restored screen-time setting")


def test_parent_daily_preset_and_custom_limit_autosave(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state, tmp_path):
    events_path = tmp_path / "daily-limit-events.jsonl"
    application, _log_path = launch_ui(
        "parent_component_preview",
        environment_overrides={
            "ONPC_PARENT_COMPONENT_SCENARIO": "custom-limit",
            "ONPC_PARENT_COMPONENT_EVENTS_PATH": str(events_path),
        },
    )
    allowance = wait_for_accessible_node(
        application, "Daily time allowance", "button",
    )
    custom = wait_for_accessible_node(application, "Custom daily allowance", "text")
    custom.text = "73"
    wait_for_accessible_state(
        lambda: any(
            record["event"] == "set_parent_control" and
            record["daily_limit_minutes"] == 73
            for record in (json.loads(line) for line in events_path.read_text(
                encoding="utf-8",
            ).splitlines())
        ),
        "custom daily-limit auto-save",
    )
    assert allowance.child(role_name="toggle button", retry=False).do_action(0)
    preset = wait_for_accessible_node(application, "45 minutes", "button")
    assert preset.do_action(0)
    wait_for_accessible_state(
        lambda: any(
            record["event"] == "set_parent_control" and
            record["daily_limit_minutes"] == 45
            for record in (json.loads(line) for line in events_path.read_text(
                encoding="utf-8",
            ).splitlines())
        ),
        "daily preset auto-save",
    )


def test_parent_app_search_rule_edit_and_revocation_confirmation(
        launch_ui, wait_for_accessible_node, wait_for_accessible_state, tmp_path):
    events_path = tmp_path / "app-events.jsonl"
    application, _log_path = launch_ui(
        "parent_component_preview",
        environment_overrides={"ONPC_PARENT_COMPONENT_EVENTS_PATH": str(events_path)},
    )
    app_limits = wait_for_accessible_node(application, "App Limits", "page tab")
    assert app_limits.do_action(0)
    search = wait_for_accessible_node(application, "Search installed apps", "entry")
    search.text = "thunderbird"
    thunderbird = wait_for_accessible_node(application, "Thunderbird")
    assert thunderbird.showing

    match_rule = wait_for_accessible_node(application, "Thunderbird match rule", "button")
    assert match_rule.do_action(0)
    dialog = wait_for_accessible_node(application, "Edit Match Rule", "dialog")
    rule_entry = dialog.child(role_name="text", retry=False)
    rule_entry.text = "/snap/bin/thunderbird"
    save = dialog.child("Save", role_name="button", retry=False)
    assert save.do_action(0)
    wait_for_accessible_state(
        lambda: events_path.exists() and "set_preferences" in events_path.read_text(),
        "match-rule auto-save",
    )

    revoke = wait_for_accessible_node(application, "Revoke one-time access", "button")
    assert revoke.do_action(0)
    confirmation = wait_for_accessible_node(application, "Revoke one-time grant?", "dialog")
    warning = confirmation.child(
        "This will revoke one-time screen time and access to soft blocked apps "
        f"granted to {preview_users('child')[0][1]}, close their running blocked apps, and lock their desktop "
        "when no time remains. Their remaining daily time allowance is not impacted.",
        role_name="label", retry=False,
    )
    assert warning.showing
    assert confirmation.child("Revoke grant", role_name="button", retry=False).do_action(0)
    wait_for_accessible_state(
        lambda: "revoke_one_time_grant" in events_path.read_text(),
        "confirmed one-time-grant revocation",
    )


def test_kiosk_accessibility_tree_is_populated(launch_ui, capture_ui_snapshot):
    """Diagnostic guard: the shared request form must remain visible to AT-SPI."""
    application, _log_path = launch_ui("kiosk_preview")
    tree = capture_ui_snapshot(application, "kiosk-accessibility")
    tree_text = tree.read_text(encoding="utf-8")
    assert "Child account" in tree_text
    assert "Approving parent" in tree_text
    assert "Allow soft blocked apps" in tree_text
    assert "switch: 'Allow soft blocked apps'" in tree_text
    assert "REQUEST" in tree_text
    assert "CANCEL" in tree_text


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
            ("Mute request-screen sound", "button"),
            ("Request-screen menu", "toggle button"),
        ),
        f"{surface}-preview",
    )
    menu = wait_for_accessible_node(
        application, "Request-screen menu", "toggle button",
    )
    assert menu.do_action(0)
    if overlay:
        wait_for_accessible_node(application, "Help", "button")
    wait_for_accessible_node(application, "About", "button")
