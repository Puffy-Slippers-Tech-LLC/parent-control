"""Functional smoke coverage for each GTK preview surface through public IDs."""

from __future__ import annotations

import hashlib
import json

import pytest
from tests.support.automation_ids import audit_product_controls
from tests.support.events import read_events
from tests.support.gui_blocks import select_allowance


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
    select_allowance(ui, (45,))
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
    wait_for_accessible_state(
        lambda: ui.absent("feedback-dialog", within="parent-window"),
        "the unchanged policy warning does not reopen the error report",
    )
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
    assert set(ui.getChoices("parent-child-selector")) == {'1001', '1002'}
    ui.setValue("parent-child-selector", "1002")
    wait_for_accessible_state(lambda: ui.showing("parent-child-selected-1002"),
                              "selected child is published by UID")
    assert ui.target("parent-child-selector").get_accessible_id() == "parent-child-selector"



def test_parent_daily_allowance_custom_then_preset_saves(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    events = tmp_path / "allowance-events.jsonl"
    ui = start_parent(launch_ui, automation, wait_for_accessible_state, events_path=events)
    wait_parent_ready(ui, wait_for_accessible_state)
    select_allowance(ui, ('custom',))
    ui.setText("parent-custom-daily-limit", "91")
    wait_parent_ready(ui, wait_for_accessible_state)
    select_allowance(ui, (45,))
    assert [record["daily_limit_minutes"] for record in read_events(events)
            if record["event"] == "set_parent_control"][-2:] == [91, 45]


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
    evidence = {}
    for identity in ("parent-child-selector", "parent-screen-limit-toggle", "parent-revoke-button"):
        node = ui.target(identity)
        snapshot = node.element.snapshot()
        evidence[identity] = {key: snapshot[key] for key in (
            'id', 'surface_id', 'parent_id', 'visible', 'enabled')}
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


def test_parent_zero_balance_keeps_revoke_unavailable_with_limits_on_and_off(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    path = tmp_path / 'zero-balance-events.jsonl'
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      scenario='zero-total', events_path=path)
    wait_parent_ready(ui, wait_for_accessible_state)
    wait_for_accessible_state(lambda: ui.text('parent-time-remaining') == '0m',
                              'the zero balance is loaded')
    assert ui.state('parent-screen-limit-toggle', ui.api.StateType.CHECKED)
    assert not ui.state('parent-revoke-button', ui.api.StateType.SENSITIVE)
    ui.activate('parent-screen-limit-toggle')
    wait_for_accessible_state(
        lambda: not ui.state('parent-screen-limit-toggle', ui.api.StateType.CHECKED)
                and ui.state('parent-screen-limit-toggle', ui.api.StateType.SENSITIVE),
        'the disabled screen limit saves')
    assert not ui.state('parent-revoke-button', ui.api.StateType.SENSITIVE)
    saves = [record for record in read_events(path) if record['event'] == 'set_parent_control']
    assert saves == [{'daily_limit_minutes': 0, 'enabled': False,
                      'event': 'set_parent_control', 'uid': 1001}]
    assert not any(record['event'] == 'revoke_one_time_grant' for record in read_events(path))


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


def test_parent_representative_daily_presets_through_installed_reader(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    from gi.repository import GLib
    from tests.e2e.accessible_ui import AccessibleUI, CHILD
    from tests.support.gui_blocks import select_allowance
    from tests.e2e.allowance_values import REPRESENTATIVE_PRESETS

    path = tmp_path / "daily-presets.jsonl"
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      events_path=path)
    wait_parent_ready(ui, wait_for_accessible_state)
    reader = AccessibleUI(
        ui.api, timeout=10, query_errors=ui.query_errors,
        owner_pids=ui.owner_pids, application_ids=ui.application_ids,
        application_owners=ui.application_owners,
        application_owner_history=ui.application_owner_history,
        fixture_uids={CHILD: 1001},
        dispatch=lambda: GLib.MainContext.default().iteration(False),
    )
    for minutes in (15, *REPRESENTATIVE_PRESETS, 15):
        select_allowance(reader, (minutes,), child=CHILD)
        assert reader.allowance_preset(CHILD, minutes, action='read') == {
            'minutes': minutes, 'saved': True}
        wait_for_accessible_state(
            lambda: [record['daily_limit_minutes'] for record in read_events(path)
                     if record['event'] == 'set_parent_control'][-1:] == [minutes],
            f"preset {minutes} independently committed")



def test_parent_daily_preset_and_custom_limit_autosave(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    from gi.repository import GLib
    from tests.e2e.accessible_ui import AccessibleUI, CHILD
    path = tmp_path / "daily-limit-events.jsonl"
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      scenario="custom-limit", events_path=path)
    wait_parent_ready(ui, wait_for_accessible_state)
    ui.setText("parent-custom-daily-limit", "74")
    wait_for_accessible_state(
        lambda: any(record["event"] == "set_parent_control"
                    and record["daily_limit_minutes"] == 74
                    for record in read_events(path)),
        "custom allowance saves",
    )
    select_allowance(ui, (45,))
    wait_for_accessible_state(
        lambda: any(record["event"] == "set_parent_control"
                    and record["daily_limit_minutes"] == 45
                    for record in read_events(path)),
        "preset allowance saves",
    )
    reader = AccessibleUI(
        ui.api, timeout=10, query_errors=ui.query_errors,
        owner_pids=ui.owner_pids, application_ids=ui.application_ids,
        application_owners=ui.application_owners,
        application_owner_history=ui.application_owner_history,
        fixture_uids={CHILD: 1001},
        dispatch=lambda: GLib.MainContext.default().iteration(False),
    )
    for minutes in (0, 15):
        for action in ('select', 'read'):
            assert reader.allowance_preset(CHILD, minutes, action=action) == {
                'minutes': minutes, 'saved': True}
        wait_for_accessible_state(
            lambda: any(record["event"] == "set_parent_control"
                        and record["daily_limit_minutes"] == minutes
                        for record in read_events(path)), "ordinary preset saves")
    # Exercise zero and the ordinary validation action; recovery below checks
    # the minimum positive value and maximum without ordinary-value repeats.
    for minutes, activate in ((0, False), (2, True)):
        reader.custom_allowance(CHILD, minutes, action='open')
        ui.setText('parent-custom-daily-limit', str(minutes))
        if activate:
            ui.activate('parent-custom-daily-limit')
        wait_for_accessible_state(
            lambda: any(record['event'] == 'set_parent_control'
                        and record['daily_limit_minutes'] == minutes
                        for record in read_events(path)), 'custom commit saves')
        reader.custom_allowance(CHILD, minutes, action='saved')
        assert reader.settings(CHILD)['allowance'] == [str(minutes) + ' minutes']
        reader.custom_allowance(CHILD, minutes, action='reopen-current')

    # Match the live boundary-to-invalid transition after reopening the editor.
    reader.allowance_preset(CHILD, 15, action='select')
    reader.allowance_preset(CHILD, 15, action='read')
    reader.custom_allowance(CHILD, 15, action='open')
    from tests.e2e.allowance_values import INVALID, INVALID_DESCRIPTION
    for binding, value in INVALID.items():
        ui.setText('parent-custom-daily-limit', value)
        assert reader.invalid_allowance(binding) == {'binding': binding, 'validation': 'rejected'}
        assert ui.target('parent-custom-daily-limit').get_description() == INVALID_DESCRIPTION
        saves = [record for record in read_events(path) if record['event'] == 'set_parent_control']
        assert saves[-1]['daily_limit_minutes'] == 15
    ui.setText('parent-custom-daily-limit', '1')
    reader.custom_allowance(CHILD, 1, action='saved')
    assert ui.target('parent-custom-daily-limit').get_description() == (
        'Enter a whole number of minutes from zero through 1439.')
    # Verify the maximum as a complete edit, without testing caret behavior
    # during intermediate autosaves.
    ui.setText('parent-custom-daily-limit', '1439')
    reader.custom_allowance(CHILD, 1439, action='saved')
    assert reader.settings(CHILD)['allowance'] == ['1439 minutes']


def test_parent_rejected_custom_allowance_reloads_saved_value(
        launch_ui, automation, wait_for_accessible_state):
    from gi.repository import GLib
    from tests.e2e.accessible_ui import AccessibleUI, CHILD

    ui = start_parent(launch_ui, automation, wait_for_accessible_state)
    wait_parent_ready(ui, wait_for_accessible_state)
    reader = AccessibleUI(
        ui.api, timeout=10, query_errors=ui.query_errors,
        owner_pids=ui.owner_pids, application_ids=ui.application_ids,
        application_owners=ui.application_owners,
        application_owner_history=ui.application_owner_history,
        fixture_uids={CHILD: 1001},
        dispatch=lambda: GLib.MainContext.default().iteration(False),
    )
    reader.allowance_preset(CHILD, 15, action='select')
    reader.custom_allowance(CHILD, 15, action='open')
    ui.setText('parent-custom-daily-limit', '')
    assert reader.invalid_allowance('empty') == {'binding': 'empty', 'validation': 'rejected'}

    # Match Task 040a's public reload: visit the other child and return before
    # reading the saved preset and reopening its custom editor.
    for uid in (1002, 1001):
        ui.setValue('parent-child-selector', str(uid))
        wait_for_accessible_state(lambda: ui.showing(f'parent-child-selected-{uid}'),
                                  'selected child changes')
        wait_parent_ready(ui, wait_for_accessible_state)
    reader.allowance_preset(CHILD, 15, action='read')
    reader.custom_allowance(CHILD, 15, action='open')
    assert ui.content('parent-custom-daily-limit', maximum=16) == '15'
    assert ui.target('parent-custom-daily-limit').get_description() == (
        'Enter a whole number of minutes from zero through 1439.')


def test_catalogue_text_binding_replacement_clear_and_wrong_child(
        launch_ui, automation, wait_for_accessible_state):
    from gi.repository import GLib
    from tests.e2e.accessible_ui import AccessibleUI, CHILD, EXISTING_CHILD, UiError
    ui = start_parent(launch_ui, automation, wait_for_accessible_state)
    wait_parent_ready(ui, wait_for_accessible_state)
    reader = AccessibleUI(ui.api, timeout=10, query_errors=ui.query_errors,
        owner_pids=ui.owner_pids, application_ids=ui.application_ids,
        application_owners=ui.application_owners,
        application_owner_history=ui.application_owner_history,
        fixture_uids={CHILD: 1001, EXISTING_CHILD: 1002},
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    reader.parent_page(CHILD, 'App Limits')
    original = reader.app_rows(CHILD)
    with pytest.raises(UiError, match='wrong-child'):
        reader.set_text('parent-app-search', 'Calculator', child=EXISTING_CHILD)
    for binding in ('catalogue-name', 'catalogue-absent', 'catalogue-clear'):
        from tests.e2e.accessible_ui import TEXT_VALUES
        reader.set_text('parent-app-search', TEXT_VALUES[binding][1], child=CHILD)
        # Retry only the complete public observation, never the mutation.
        assert reader.wait(
            lambda: reader.read_synthetic_text(binding, child=CHILD),
            'catalogue-exact-text',
        )['exact']
        wait_for_accessible_state(lambda: reader.app_rows(CHILD) == (
            original if binding == 'catalogue-clear' else ()), 'complete search result')
    reader.parent_page(CHILD, 'Screen Limits')
    # Inactive pages cannot receive product input.
    with pytest.raises(UiError, match='text-entry|text-disabled|app-row-page'):
        reader.set_text('parent-app-search', '', child=CHILD)


@pytest.mark.parametrize('binding,masks', (
    ('catalogue-name', ((3, 7),)),
    ('catalogue-description', ((3, 7),)),
    ('catalogue-identifier', ((3, 7), (1, 1), (2, 6))),
    ('catalogue-clear', ((3, 7), (0, 7), (3, 0), (1, 7), (2, 7),
                         (3, 1), (3, 2), (3, 4))),
    ('catalogue-absent', ((3, 7),)),
))
def test_catalogue_query_and_representative_filter_results(
        launch_ui, automation, wait_for_accessible_state, tmp_path, binding, masks):
    from gi.repository import GLib
    from tests.e2e.accessible_ui import AccessibleUI, CHILD, EXISTING_CHILD, UiError
    from tests.e2e.native_fixtures import expected_rows, catalogue_rows
    from tests.support.gui_blocks import run_block
    events = tmp_path / 'catalogue-events.jsonl'
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      scenario='catalogue', events_path=events)
    wait_parent_ready(ui, wait_for_accessible_state)
    ui.setValue('parent-child-selector', '1002')
    wait_for_accessible_state(lambda: ui.showing('parent-child-selected-1002'), 'Jordan selected')
    reader = AccessibleUI(ui.api, timeout=20, query_errors=ui.query_errors,
        owner_pids=ui.owner_pids, application_ids=ui.application_ids,
        application_owners=ui.application_owners,
        application_owner_history=ui.application_owner_history,
        fixture_uids={CHILD: 1001, EXISTING_CHILD: 1002},
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    reader.parent_page(EXISTING_CHILD, 'App Limits')
    initial = tuple((identity, {'H': 'permanent', 'S': 'conditional'}.get(role, access), match)
        for identity, access, match in expected_rows()
        for role in ('A', 'H', 'S', 'N')
        if identity == 'parent-app-' + hashlib.sha256(
            f'com.puffyslippers.ONPCTest.{role}.desktop'.encode()).hexdigest()[:16])
    assert reader.app_rows(EXISTING_CHILD) == initial
    with pytest.raises(UiError, match='wrong-child'):
        reader.catalogue_filter(CHILD, 'match-rule', 2, 'open')
    run_block(reader, 'replace', binding, child='existing')
    # Cover each category, empty filters and combined predicates without
    # multiplying every search query by every possible filter permutation.
    for match_mask, access_mask in masks:
        run_block(reader, 'filter', 'match-rule', str(match_mask),
                  f'filter-match-rule-{match_mask}', child='existing')
        run_block(reader, 'filter', 'access-rule', str(access_mask),
                  f'filter-access-rule-{access_mask}', child='existing')
        expected = catalogue_rows(binding, initial, match_mask=match_mask, access_mask=access_mask)
        wait_for_accessible_state(lambda: reader.app_rows(EXISTING_CHILD) == expected,
                                  'exact query/filter result including empty results')
    for kind, mask in (('match-rule', 3), ('access-rule', 7)):
        run_block(reader, 'filter', kind, str(mask), f'filter-{kind}-{mask}', child='existing')
    run_block(reader, 'replace', 'catalogue-clear', child='existing')
    wait_for_accessible_state(lambda: reader.app_rows(EXISTING_CHILD) == initial,
                              'complete unchanged policies after clear')
    assert not any(record['event'] in ('set_preferences', 'set_parent_control')
                   for record in read_events(events))
    reader.parent_page(EXISTING_CHILD, 'Screen Limits')
    with pytest.raises(UiError, match='text-entry|text-disabled|app-row-page'):
        reader.catalogue_filter(EXISTING_CHILD, 'match-rule', 2, 'open')


def test_public_policy_legend_full_read_and_unchanged_choices(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    from gi.repository import GLib
    from tests.e2e.accessible_ui import AccessibleUI, CHILD, EXISTING_CHILD, UiError
    events = tmp_path / 'legend-events.jsonl'
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      scenario='catalogue', events_path=events)
    wait_parent_ready(ui, wait_for_accessible_state)
    ui.setValue('parent-child-selector', '1002')
    wait_for_accessible_state(lambda: ui.showing('parent-child-selected-1002'), 'Jordan selected')
    reader = AccessibleUI(ui.api, timeout=20, query_errors=ui.query_errors,
        owner_pids=ui.owner_pids, application_ids=ui.application_ids,
        application_owners=ui.application_owners,
        application_owner_history=ui.application_owner_history,
        fixture_uids={CHILD: 1001, EXISTING_CHILD: 1002},
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    reader.parent_page(EXISTING_CHILD, 'App Limits')
    initial = reader.app_rows(EXISTING_CHILD)
    with pytest.raises(UiError, match='legend-child'):
        reader.expand_policy_legend(CHILD)
    reader.parent_page(EXISTING_CHILD, 'Screen Limits')
    with pytest.raises(UiError, match='legend-target|legend-page'):
        reader.expand_policy_legend(EXISTING_CHILD)
    reader.parent_page(EXISTING_CHILD, 'App Limits')
    expanded = reader.run('policy-legend-expand', '')['legend']
    assert expanded['activated'] is True
    read = reader.run('policy-legend-read', '')['legend']
    assert read == {key: value for key, value in expanded.items() if key != 'activated'}
    assert len(read['rules']) == 5 and len(read['headings']) == 2
    assert reader.app_rows(EXISTING_CHILD) == initial
    assert not any(record['event'] in ('set_preferences', 'set_parent_control')
                   for record in read_events(events))


def test_app_access_choices_save_and_independent_readback(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    from gi.repository import GLib
    from tests.e2e.accessible_ui import AccessibleUI, CHILD, EXISTING_CHILD, MATCH_APP, ACCESS_CHOICES
    from tests.support.gui_blocks import run_block
    events = tmp_path / 'access-events.jsonl'
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      scenario='catalogue', events_path=events)
    wait_parent_ready(ui, wait_for_accessible_state)
    ui.setValue('parent-child-selector', '1002')
    wait_for_accessible_state(lambda: ui.showing('parent-child-selected-1002'), 'Jordan selected')
    reader = AccessibleUI(ui.api, timeout=30, query_errors=ui.query_errors,
        owner_pids=ui.owner_pids, application_ids=ui.application_ids,
        application_owners=ui.application_owners,
        application_owner_history=ui.application_owner_history,
        fixture_uids={CHILD: 1001, EXISTING_CHILD: 1002},
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    reader.parent_page(EXISTING_CHILD, 'App Limits')
    assert reader.run('access-wrong-row', '', child='existing')['access'] == {'refusal': 'wrong-row'}
    reader.open_match_rule(EXISTING_CHILD, MATCH_APP)
    assert reader.run('access-disabled', '', child='existing')['access'] == {'refusal': 'disabled'}
    reader.respond_match_rule(EXISTING_CHILD, MATCH_APP, 'cancel')
    for choice in ACCESS_CHOICES:
        result = run_block(reader, 'access-choice', 'access-' + choice, 'access-row', child='existing')
        assert result['access-row']['access'] == {'app': MATCH_APP, 'choice': choice}
    reader.parent_page(EXISTING_CHILD, 'Screen Limits')
    reader.parent_page(EXISTING_CHILD, 'App Limits')
    assert reader.read_app_access(EXISTING_CHILD, MATCH_APP) == {
        'app': MATCH_APP, 'choice': choice}
    records = [record for record in read_events(events) if record['event'] == 'set_preferences']
    assert len(records) == 2  # The initially selected Allowed choice causes no write.


def test_policy_composite_filtered_and_independent_entry(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    import json
    from gi.repository import GLib
    from tests.e2e.accessible_ui import AccessibleUI, CHILD, EXISTING_CHILD, MATCH_APP, MATCH_RULES
    from tests.e2e.policy_edits import policy_edit
    from tests.support.gui_blocks import run_block
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      scenario='catalogue', events_path=tmp_path / 'policy-events.jsonl')
    wait_parent_ready(ui, wait_for_accessible_state)
    ui.setValue('parent-child-selector', '1002')
    wait_for_accessible_state(lambda: ui.showing('parent-child-selected-1002'), 'Jordan selected')
    reader = AccessibleUI(ui.api, timeout=30, query_errors=ui.query_errors,
        owner_pids=ui.owner_pids, application_ids=ui.application_ids,
        application_owners=ui.application_owners,
        application_owner_history=ui.application_owner_history,
        fixture_uids={CHILD: 1001, EXISTING_CHILD: 1002},
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    for index, (draft, access, filters) in enumerate((
        ('match-wildcard-appimages', 'permanent', (('match-rule', 3), ('access-rule', 7))),
        ('match-precise', 'conditional', ()),
    )):
        reader.parent_page(EXISTING_CHILD, 'App Limits')
        prefix = 'independent-' + str(index)
        screens = policy_edit(MATCH_APP, draft, access, prefix, filters=filters)
        result = run_block(reader, 'edit-policy', MATCH_APP, draft, access, prefix,
                           json.dumps(filters), operations=screens,
                           child_bindings={stage: 'existing' for stage, operation in screens.items()
                                           if operation != 'ui:catalogue-identifier-rows'})
        expected_match = {'app': MATCH_APP, 'rule': MATCH_RULES[2 if index == 0 else 0]}
        expected_access = {'app': MATCH_APP, 'choice': access}
        assert result[prefix + '-final-match']['match'] == expected_match
        assert result[prefix + '-access']['access'] == expected_access
        reader.parent_page(EXISTING_CHILD, 'Screen Limits')
        reader.parent_page(EXISTING_CHILD, 'App Limits')
        assert reader.read_match_rule(EXISTING_CHILD, MATCH_APP) == expected_match
        assert reader.read_app_access(EXISTING_CHILD, MATCH_APP) == expected_access


@pytest.mark.parametrize('binding', ('match-precise', 'match-precise-basename',
                                    'match-wildcard', 'match-wildcard-basename'))
def test_match_editor_valid_save_cancel_matrix(
        launch_ui, automation, wait_for_accessible_state, tmp_path, binding):
    from gi.repository import GLib
    from tests.e2e.accessible_ui import AccessibleUI, CHILD, EXISTING_CHILD, MATCH_APP, MATCH_RULES, UiError
    from tests.support.gui_blocks import run_block
    events = tmp_path / 'match-events.jsonl'
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      scenario='catalogue', events_path=events)
    wait_parent_ready(ui, wait_for_accessible_state)
    ui.setValue('parent-child-selector', '1002')
    wait_for_accessible_state(lambda: ui.showing('parent-child-selected-1002'), 'Jordan selected')
    reader = AccessibleUI(ui.api, timeout=30, query_errors=ui.query_errors,
        owner_pids=ui.owner_pids, application_ids=ui.application_ids,
        application_owners=ui.application_owners,
        application_owner_history=ui.application_owner_history,
        fixture_uids={CHILD: 1001, EXISTING_CHILD: 1002},
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    reader.parent_page(EXISTING_CHILD, 'App Limits')
    original = reader.read_match_rule(EXISTING_CHILD, MATCH_APP)
    with pytest.raises(UiError, match='match-child'):
        reader.open_match_rule(CHILD, MATCH_APP)
    run_block(reader, 'match-editor', 'match-open', 'match-read', child='existing')
    assert reader.run('match-wrong-app', '', child='existing')['match'] == {'refusal': 'wrong-app'}
    assert reader.run('match-ambiguous', '', child='existing')['match'] == {'refusal': 'ambiguous'}
    run_block(reader, 'replace', binding, child='existing')
    cancelled = run_block(reader, 'match-response', 'match-cancel', 'match-row', child='existing')
    assert cancelled['match-row']['match'] == original
    assert not any(record['event'] == 'set_preferences' for record in read_events(events))
    # Supply an independently open editor, then call the same public read leaf.
    reader.open_match_rule(EXISTING_CHILD, MATCH_APP)
    assert reader.run('match-read', '', child='existing')['match'] == original
    run_block(reader, 'replace', binding, child='existing')
    saved = run_block(reader, 'match-response', 'match-save', 'match-row', child='existing')
    expected = MATCH_RULES[1 if 'wildcard' in binding else 0]
    assert saved['match-row']['match'] == {'app': MATCH_APP, 'rule': expected}
    reader.open_match_rule(EXISTING_CHILD, MATCH_APP)
    assert reader.read_match_rule(EXISTING_CHILD, MATCH_APP, editor=True)['rule'] == expected
    reader.respond_match_rule(EXISTING_CHILD, MATCH_APP, 'cancel')


@pytest.mark.parametrize('old_binding,response', (
    ('match-precise', 'cancel'), ('match-wildcard', 'reset'),
))
def test_match_editor_invalid_drafts_cancel_or_reset(
        launch_ui, automation, wait_for_accessible_state, tmp_path, old_binding, response):
    from gi.repository import GLib
    from tests.e2e.accessible_ui import AccessibleUI, CHILD, EXISTING_CHILD, MATCH_APP, MATCH_RULES, MATCH_INVALID
    from tests.support.gui_blocks import run_block
    events = tmp_path / 'match-invalid-events.jsonl'
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      scenario='catalogue', events_path=events)
    wait_parent_ready(ui, wait_for_accessible_state)
    ui.setValue('parent-child-selector', '1002')
    wait_for_accessible_state(lambda: ui.showing('parent-child-selected-1002'), 'Jordan selected')
    reader = AccessibleUI(ui.api, timeout=30, query_errors=ui.query_errors,
        owner_pids=ui.owner_pids, application_ids=ui.application_ids,
        application_owners=ui.application_owners,
        application_owner_history=ui.application_owner_history,
        fixture_uids={CHILD: 1001, EXISTING_CHILD: 1002},
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    reader.parent_page(EXISTING_CHILD, 'App Limits')
    run_block(reader, 'match-editor', 'match-open', 'match-read', child='existing')
    run_block(reader, 'replace', old_binding, child='existing')
    run_block(reader, 'match-response', 'match-save', 'match-row', child='existing')
    old = reader.read_match_rule(EXISTING_CHILD, MATCH_APP)
    for invalid, message in MATCH_INVALID.items():
        run_block(reader, 'match-editor', 'match-open', 'match-read', child='existing')
        before = sum(record['event'] == 'set_preferences' for record in read_events(events))
        run_block(reader, 'replace', 'match-invalid-' + invalid, child='existing')
        assert reader.run('match-invalid-' + invalid, '', child='existing')['match'] == {
            'invalid': invalid, 'message': message}
        assert sum(record['event'] == 'set_preferences' for record in read_events(events)) == before
        # The refusal retains the exact draft and editor; exit uses one normal response.
        result = run_block(reader, 'match-response', 'match-' + response, 'match-row', child='existing')
        expected = old if response == 'cancel' else {'app': MATCH_APP, 'rule': MATCH_RULES[0]}
        assert result['match-row']['match'] == expected
        reader.open_match_rule(EXISTING_CHILD, MATCH_APP)
        assert reader.read_match_rule(EXISTING_CHILD, MATCH_APP, editor=True) == expected
        if response == 'reset':
            writes = [record for record in read_events(events) if record['event'] == 'set_preferences']
            assert len(writes) == before + 1  # Reset saved immediately, with no Save input.
            run_block(reader, 'replace', old_binding, child='existing')
            run_block(reader, 'match-response', 'match-save', 'match-row', child='existing')
        else:
            assert sum(record['event'] == 'set_preferences' for record in read_events(events)) == before
            reader.respond_match_rule(EXISTING_CHILD, MATCH_APP, 'cancel')


@pytest.mark.parametrize('confirmed_binding', ('match-precise', 'match-wildcard'))
def test_rejected_parent_rule_report_review_and_confirmed_policy(
        launch_ui, automation, wait_for_accessible_state, tmp_path, confirmed_binding):
    from gi.repository import GLib
    from tests.e2e.accessible_ui import AccessibleUI, CHILD, EXISTING_CHILD, MATCH_APP
    from tests.e2e.parent_reports import report_review, report_close
    from tests.support.gui_blocks import run_block
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      scenario='rejected-rule', events_path=tmp_path / 'report-events.jsonl')
    wait_parent_ready(ui, wait_for_accessible_state)
    ui.setValue('parent-child-selector', '1002')
    wait_for_accessible_state(lambda: ui.showing('parent-child-selected-1002'), 'Jordan selected')
    reader = AccessibleUI(ui.api, timeout=30, query_errors=ui.query_errors,
        owner_pids=ui.owner_pids, application_ids=ui.application_ids,
        application_owners=ui.application_owners,
        application_owner_history=ui.application_owner_history,
        fixture_uids={CHILD: 1001, EXISTING_CHILD: 1002},
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    reader.parent_page(EXISTING_CHILD, 'App Limits')
    assert reader.parent_report_operation('parent-report-refused') == {'refusal': 'absent'}
    run_block(reader, 'match-editor', 'match-open', 'match-read', child='existing')
    run_block(reader, 'replace', confirmed_binding, child='existing')
    run_block(reader, 'match-response', 'match-save', 'match-row', child='existing')
    before = reader.read_match_rule(EXISTING_CHILD, MATCH_APP)
    for prefix in ('review', 'independent'):
        run_block(reader, 'match-editor', 'match-open', 'match-read', child='existing')
        run_block(reader, 'replace', 'match-rejected-directory', child='existing')
        assert reader.respond_match_rule(EXISTING_CHILD, MATCH_APP, 'rejected') == {'closed': 'rejected'}
        result = run_block(reader, 'report-review', prefix, operations=report_review(prefix))
        assert result[prefix + '-report']['feedback']['draft'] == 'parent-rule-error'
        assert result[prefix + '-actions']['feedback'] == result[prefix + '-feedback-privacy-returned']['feedback']
        assert reader.read_match_rule(EXISTING_CHILD, MATCH_APP) == before
    run_block(reader, 'match-editor', 'match-open', 'match-read', child='existing')
    run_block(reader, 'replace', 'match-rejected-directory', child='existing')
    assert reader.respond_match_rule(EXISTING_CHILD, MATCH_APP, 'rejected') == {'closed': 'rejected'}
    result = run_block(reader, 'report-close', 'decline', operations=report_close('decline'))
    assert result['decline-report']['feedback']['draft'] == 'parent-rule-error'
    assert reader.read_match_rule(EXISTING_CHILD, MATCH_APP) == before
    assert all(record['event'] != 'feedback_post'
               for record in read_events(tmp_path / 'report-events.jsonl'))


def test_parent_app_search_rule_edit_and_revocation_confirmation(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    path = tmp_path / "app-events.jsonl"
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      events_path=path)
    wait_parent_ready(ui, wait_for_accessible_state)
    ui.activate("parent-page-app-limits")
    wait_for_accessible_state(
        lambda: (search := ui.find("parent-app-search")) is not None
        and search.get_state_set().contains(ui.api.StateType.SENSITIVE),
        "app catalogue loads",
    )
    ui.setText("parent-app-search", "thunderbird")
    key = hashlib.sha256(b"thunderbird_thunderbird.desktop").hexdigest()[:16]
    wait_for_accessible_state(lambda: ui.showing(f"parent-app-{key}"),
                              "matching app remains visible")
    ui.activate(f"parent-app-{key}-match-rule")
    wait_for_accessible_state(lambda: ui.showing("parent-match-rule-dialog"),
                              "match-rule dialog opens")
    assert audit_product_controls(ui, "parent-match-rule-dialog")
    ui.setText("parent-match-rule-entry", "/snap/bin/thunderbird")
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
    commands = set(ui.getChoices('kiosk-menu-button'))
    assert {'about', 'change-screens'} <= commands
    assert ('help' in commands) is overlay
    ui.setValue('kiosk-menu-button', 'change-screens')
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
    from gi.repository import GLib
    from tests.e2e.accessible_ui import AccessibleUI, CHILD, EXISTING_CHILD, UiError
    ui = start_parent(launch_ui, automation, wait_for_accessible_state,
                      scenario=scenario)
    wait_for_accessible_state(lambda: ui.text("parent-time-explanation") == expected,
                              "remaining-time explanation is public")
    reader = AccessibleUI(
        ui.api, timeout=10, query_errors=ui.query_errors,
        owner_pids=ui.owner_pids, application_ids=ui.application_ids,
        application_owners=ui.application_owners,
        application_owner_history=ui.application_owner_history,
        fixture_uids={CHILD: 1001, EXISTING_CHILD: 1002},
        dispatch=lambda: GLib.MainContext.default().iteration(False),
    )
    ui.activate("parent-time-calculation-collapse")
    wait_for_accessible_state(lambda: not ui.showing("parent-time-explanation"),
                              "collapsed explanation is not showing")
    with pytest.raises(UiError, match='ui:time-collapsed'):
        reader.time_explanation(CHILD)
    ui.setValue("parent-time-status", True)
    wait_for_accessible_state(lambda: ui.showing("parent-time-explanation"),
                              "explicit expansion shows the explanation")
    with pytest.raises(UiError, match='ui:wrong-child'):
        reader.time_explanation(EXISTING_CHILD)
    first = reader.time_explanation(CHILD)
    ui.activate("parent-time-calculation-collapse")
    wait_for_accessible_state(lambda: not ui.showing("parent-time-explanation"),
                              "PARENT09 starts independently collapsed")
    with pytest.raises(UiError, match='ui:wrong-child'):
        reader.reach_time_explanation(EXISTING_CHILD)
    assert not ui.showing("parent-time-explanation")
    reached = reader.reach_time_explanation(CHILD)
    balances = {'normal': [2820, 900, 2820], 'grant-only': [0, 900, 900],
                'exact-hours': [0, 7200, 7200], 'daily-exhausted': [0, 900, 900]}
    for result in (first, reached):
        assert [result[key]['seconds'] for key in ('daily', 'one_time', 'total')] == balances[scenario]
        assert result['expanded'] is True
    assert reached['observed_monotonic_ns'] > first['observed_monotonic_ns']
    assert ui.showing("parent-time-explanation")
    assert ui.text("parent-time-explanation") == expected
