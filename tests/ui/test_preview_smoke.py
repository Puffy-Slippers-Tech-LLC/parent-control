"""Functional smoke coverage for each GTK preview surface through public IDs."""

from __future__ import annotations

import hashlib
import json

import pytest
from tests.support.automation_ids import audit_product_controls
from tests.support.events import read_events


pytestmark = pytest.mark.ui


def start_parent(launch_ui, ui, wait, *, launcher="parent_component_preview",
                 scenario="normal", events_path=None, loading_release=None):
    environment = {"ONPC_PARENT_COMPONENT_SCENARIO": scenario}
    if events_path is not None:
        environment["ONPC_PARENT_COMPONENT_EVENTS_PATH"] = str(events_path)
    if loading_release is not None:
        environment["ONPC_PARENT_COMPONENT_LOADING_RELEASE"] = str(loading_release)
    launch_ui(launcher, environment_overrides=environment, wait_for_application=False)
    wait(lambda: ui.find("parent-window") is not None, "Parent publishes its window ID")
    return ui


def wait_parent_ready(ui, wait):
    wait(lambda: ui.state("parent-screen-limit-toggle", ui.api.StateType.SENSITIVE),
         "Parent screen-time controls load")


def test_parent_reports_partial_app_limits_and_remains_usable(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      scenario="policy-warning", events_path=tmp_path / "policy-events.jsonl")
    wait_for_accessible_state(lambda: ui.showing("feedback-dialog"),
                              "the normal error report opens for the omitted rule")
    ui.activate("feedback-close")
    wait_for_accessible_state(lambda: ui.absent("feedback-dialog", within="parent-window"),
                              "closing the report keeps the Parent window open")
    wait_parent_ready(ui, wait_for_accessible_state)
    assert "may be unrestricted" in ui.text("parent-policy-warning")
    assert "Affected apps:" in ui.text("parent-policy-warning")
    ui.activate("parent-daily-limit-selector")
    wait_for_accessible_state(lambda: ui.showing("parent-daily-limit-45"),
                              "unaffected screen-time settings remain reachable")
    ui.activate("parent-daily-limit-45")
    # The menu button's accessible name is the stable description "Daily time
    # allowance", not its child label. Observe the component's committed value.
    wait_for_accessible_state(
        lambda: any(record["event"] == "set_parent_control"
                    and record["daily_limit_minutes"] == 45
                    for record in read_events(tmp_path / "policy-events.jsonl")),
        "the unaffected daily allowance saves",
    )
    wait_for_accessible_state(
        lambda: ui.state("parent-daily-limit-selector", ui.api.StateType.SENSITIVE),
        "saving completes and controls are usable again",
    )
    ui.activate("parent-screen-limit-toggle")
    wait_for_accessible_state(
        lambda: not ui.state("parent-screen-limit-toggle", ui.api.StateType.CHECKED)
                and ui.state("parent-screen-limit-toggle", ui.api.StateType.SENSITIVE),
        "another setting changes and remains usable after its save",
    )
    assert ui.absent("feedback-dialog", within="parent-window")
    assert "may be unrestricted" in ui.text("parent-policy-warning")


@pytest.mark.parametrize("launcher", ("parent_preview", "parent_component_preview"))
def test_parent_preview_publishes_and_loads_management_controls(
        launch_ui, automation, wait_for_accessible_state, launcher):
    ui = start_parent(launch_ui, automation, wait_for_accessible_state, launcher=launcher)
    wait_parent_ready(ui, wait_for_accessible_state)
    for identity in ("parent-child-selector", "parent-child-selected-1001",
                     "parent-screen-limit-toggle", "parent-daily-limit-selector",
                     "parent-revoke-button"):
        assert ui.target(identity).get_accessible_id() == identity
    ui.activate("parent-child-selector", action_name="menu.popup")
    wait_for_accessible_state(lambda: ui.showing("parent-child-choice-1002"),
                              "child choices are ID-addressable actions")
    ui.activate("parent-child-choice-1002")
    wait_for_accessible_state(lambda: ui.showing("parent-child-selected-1002"),
                              "selected child is published by UID")


def test_parent_daily_allowance_menu_opens_and_selects(
        launch_ui, automation, wait_for_accessible_state):
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      launcher="parent_preview")
    wait_parent_ready(ui, wait_for_accessible_state)
    ui.activate("parent-daily-limit-selector")
    wait_for_accessible_state(lambda: ui.showing("parent-daily-limit-45"),
                              "allowance choices open")
    ui.activate("parent-daily-limit-45")


@pytest.mark.parametrize("scenario", ("denied", "unavailable"))
def test_parent_failed_discovery_disables_management_until_report_closes(
        launch_ui, automation, wait_for_accessible_state, scenario):
    process, _log = launch_ui(
        "parent_component_preview",
        environment_overrides={"ONPC_PARENT_COMPONENT_SCENARIO": scenario},
        wait_for_application=False,
    )
    ui = automation
    wait_for_accessible_state(lambda: ui.showing("feedback-dialog"),
                              "startup feedback opens")
    from tests.e2e.accessible_ui import public_automation_id
    evidence = {}
    for identity in ("parent-child-selector", "parent-screen-limit-toggle", "parent-revoke-button"):
        node = ui.target(identity)
        ancestors = []
        seen = set()
        while node is not None and node not in seen and len(seen) < 32:
            seen.add(node)
            node.clear_cache_single()
            ancestors.append({
                "id": public_automation_id(node),
                "sensitive": node.get_state_set().contains(ui.api.StateType.SENSITIVE),
                "defunct": node.get_state_set().contains(ui.api.StateType.DEFUNCT),
            })
            node = node.get_parent()
        evidence[identity] = ancestors
    diagnostic = _log.with_name("parent-failed-discovery-public-state.json")
    diagnostic.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print("Failed-discovery public states:", diagnostic)
    for identity in ("parent-child-selector", "parent-screen-limit-toggle",
                     "parent-revoke-button"):
        assert not ui.state(identity, ui.api.StateType.SENSITIVE)
    ui.activate("feedback-close")
    assert process.wait(timeout=5) == 0


def test_parent_no_child_message_is_explicit(
        launch_ui, automation, wait_for_accessible_state):
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      scenario="no-users")
    wait_for_accessible_state(lambda: ui.showing("parent-no-users-message"),
                              "empty-account explanation is shown")
    assert ui.text("parent-no-users-message") == (
        "No interactive non-administrator account was found."
    )


def test_parent_loading_state_disables_conflicting_controls(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    events_path = tmp_path / "loading-events.jsonl"
    release = tmp_path / "loading-release"
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      scenario="loading", events_path=events_path, loading_release=release)
    evidence = {
        "events_before_public_read": read_events(events_path),
        "toggle_sensitive": ui.state("parent-screen-limit-toggle", ui.api.StateType.SENSITIVE),
        "allowance_sensitive": ui.state("parent-daily-limit-selector", ui.api.StateType.SENSITIVE),
        "events_after_public_read": read_events(events_path),
    }
    diagnostic = tmp_path / "loading-public-state.json"
    diagnostic.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print("Loading public state:", diagnostic)
    try:
        assert not ui.state("parent-screen-limit-toggle", ui.api.StateType.SENSITIVE)
        assert not ui.state("parent-daily-limit-selector", ui.api.StateType.SENSITIVE)
    finally:
        release.touch()
    wait_parent_ready(ui, wait_for_accessible_state)
    wait_for_accessible_state(
        lambda: ui.state("parent-daily-limit-selector", ui.api.StateType.SENSITIVE),
        "daily allowance loads",
    )


def test_parent_time_status_retries(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    path = tmp_path / "status-events.jsonl"
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      scenario="status-retries", events_path=path)
    wait_for_accessible_state(lambda: ui.text("parent-time-remaining") == "47m",
                              "remaining time loads after retries")
    wait_for_accessible_state(
        lambda: sum(record["event"] == "get_time_status"
                    for record in read_events(path)) == 3,
        "two failed attempts followed by successful retry",
    )


def test_parent_time_status_reports_unavailable(
        launch_ui, automation, wait_for_accessible_state):
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      scenario="status-unavailable")
    wait_for_accessible_state(
        lambda: ui.text("parent-time-remaining") == "Unavailable",
        "unavailable time is public",
    )


@pytest.mark.parametrize("scenario", ("normal", "save-fails"))
def test_parent_screen_time_change_saves_or_restores(
        launch_ui, automation, wait_for_accessible_state, tmp_path, scenario):
    path = tmp_path / f"{scenario}.jsonl"
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      scenario=scenario, events_path=path)
    wait_parent_ready(ui, wait_for_accessible_state)
    assert ui.state("parent-screen-limit-toggle", ui.api.StateType.CHECKED)
    ui.activate("parent-screen-limit-toggle")
    wait_for_accessible_state(
        lambda: any(record["event"] == "set_parent_control"
                    for record in read_events(path)),
        "screen-time change reaches broker",
    )
    if scenario == "normal":
        records = [record for record in read_events(path)
                   if record["event"] == "set_parent_control"]
        assert records == [{"daily_limit_minutes": 90, "enabled": False,
                            "event": "set_parent_control", "uid": 1001}]
    else:
        wait_for_accessible_state(
            lambda: ui.state("parent-screen-limit-toggle", ui.api.StateType.CHECKED),
            "failed save restores confirmed value",
        )


def test_parent_daily_preset_and_custom_limit_autosave(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    from dogtail import rawinput
    path = tmp_path / "daily-limit-events.jsonl"
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      scenario="custom-limit", events_path=path)
    wait_parent_ready(ui, wait_for_accessible_state)
    ui.focus("parent-custom-daily-limit")
    rawinput.keyCombo("<Control>a")
    rawinput.typeText("73")
    wait_for_accessible_state(
        lambda: any(record["event"] == "set_parent_control"
                    and record["daily_limit_minutes"] == 73
                    for record in read_events(path)),
        "custom allowance saves",
    )
    ui.activate("parent-daily-limit-selector")
    wait_for_accessible_state(lambda: ui.showing("parent-daily-limit-45"),
                              "allowance choices open")
    ui.activate("parent-daily-limit-45")
    wait_for_accessible_state(
        lambda: any(record["event"] == "set_parent_control"
                    and record["daily_limit_minutes"] == 45
                    for record in read_events(path)),
        "preset allowance saves",
    )


def test_parent_app_search_rule_edit_and_revocation_confirmation(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    from dogtail import rawinput
    path = tmp_path / "app-events.jsonl"
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      events_path=path)
    wait_parent_ready(ui, wait_for_accessible_state)
    ui.activate("parent-page-app-limits")
    wait_for_accessible_state(lambda: ui.state("parent-app-search", ui.api.StateType.SENSITIVE),
                              "app catalogue loads")
    ui.focus("parent-app-search")
    rawinput.typeText("thunderbird")
    key = hashlib.sha256(b"thunderbird_thunderbird.desktop").hexdigest()[:16]
    wait_for_accessible_state(lambda: ui.showing(f"parent-app-{key}"),
                              "matching app remains visible")
    ui.activate(f"parent-app-{key}-match-rule")
    wait_for_accessible_state(lambda: ui.showing("parent-match-rule-dialog"),
                              "match-rule dialog opens")
    assert audit_product_controls(ui, "parent-match-rule-dialog")
    ui.focus("parent-match-rule-entry")
    rawinput.keyCombo("<Control>a")
    rawinput.typeText("/snap/bin/thunderbird")
    ui.activate("parent-match-rule-save")
    wait_for_accessible_state(
        lambda: any(record["event"] == "set_preferences" for record in read_events(path)),
        "match rule saves",
    )
    ui.activate("parent-page-screen-limits")
    wait_for_accessible_state(lambda: ui.state("parent-revoke-button", ui.api.StateType.SENSITIVE),
                              "revoke action is ready")
    ui.activate("parent-revoke-button")
    wait_for_accessible_state(lambda: ui.showing("parent-revoke-dialog"),
                              "revoke confirmation opens")
    assert audit_product_controls(ui, "parent-revoke-dialog")
    assert "Riley (Child)" in ui.text("parent-revoke-warning")
    ui.activate("parent-revoke-confirm")
    wait_for_accessible_state(
        lambda: any(record["event"] == "revoke_one_time_grant"
                    for record in read_events(path)),
        "confirmed revocation reaches broker",
    )


@pytest.mark.parametrize("overlay", (False, True), ids=("kiosk", "child-overlay"))
def test_shared_request_preview_smoke(
        launch_ui, automation, wait_for_accessible_state, overlay):
    launcher = "child_overlay_preview" if overlay else "kiosk_preview"
    launch_ui(launcher, wait_for_application=False)
    ui = automation
    wait_for_accessible_state(lambda: ui.find("kiosk-request-window") is not None,
                              "request preview publishes IDs")
    for identity in ("kiosk-child-selector", "kiosk-approver-selector",
                     "kiosk-soft-apps-toggle", "kiosk-request-submit",
                     "kiosk-request-cancel", "kiosk-menu-button"):
        assert ui.target(identity).get_accessible_id() == identity
    assert ui.absent("kiosk-mute-button", within="kiosk-request-window")
    ui.activate("kiosk-menu-button", action_name="menu.popup")
    if overlay:
        assert ui.showing("kiosk-menu-item-help")
    assert ui.showing("kiosk-menu-item-about")
    ui.activate("kiosk-menu-item-change-screens")
    wait_for_accessible_state(lambda: ui.showing("preview-screen-dialog"),
                              "screen dialog opens")
    for identity in ("preview-screen-scale", "preview-screen-save",
                     "preview-screen-cancel"):
        assert ui.target(identity).get_accessible_id() == identity
    ui.activate("preview-screen-cancel")


@pytest.mark.parametrize("scenario, expected", (
    ("normal", "Daily allowance remaining: 47m\nOne-time grant remaining: 15m\nRemaining time: 47m — the larger of the two amounts."),
    ("grant-only", "Daily allowance remaining: 0m\nOne-time grant remaining: 15m\nRemaining time: 15m — the larger of the two amounts."),
    ("exact-hours", "Daily allowance remaining: 0m\nOne-time grant remaining: 2h\nRemaining time: 2h — the larger of the two amounts."),
    ("daily-exhausted", "Daily allowance remaining: 0m\nOne-time grant remaining: 15m\nRemaining time: 15m — the larger of the two amounts."),
))
def test_parent_remaining_time_explanation(
        launch_ui, automation, wait_for_accessible_state, scenario, expected):
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      scenario=scenario)
    wait_for_accessible_state(lambda: ui.text("parent-time-explanation") == expected,
                              "remaining-time explanation is public")
