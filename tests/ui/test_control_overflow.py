"""Functional reachability at supported scales through public automation IDs."""

import hashlib

import pytest
from tests.support.events import read_events
from tests.support.gui_blocks import select_allowance
from tests.e2e.accessible_ui import EXISTING_CHILD
from tests.support.feedback import feedback_editor


pytestmark = pytest.mark.ui


def open_parent(launch_ui, ui, wait, *, environment=None):
    launch_ui(
        "parent_component_preview",
        environment_overrides=environment,
        wait_for_application=False,
    )
    wait(lambda: ui.find("parent-window") is not None, "Parent publishes its window ID")
    wait(lambda: ui.state("parent-screen-limit-toggle", ui.api.StateType.SENSITIVE),
         "Parent controls load")


# Catalogue integrity is exhaustive in test_localization; these UI samples
# exercise retained work across Latin, CJK, RTL and complex-script changes.
@pytest.mark.parametrize('language', ['de', 'zh-Hans', 'he', 'ta'])
@pytest.mark.parametrize('dpi_scale', [1.25])
def test_language_switch_preserves_parent_selection_numeric_draft_and_filters(
        launch_ui, automation, wait_for_accessible_state, request_display_scale,
        dpi_scale, language):
    from tests.support.keyboard import key_combo, type_text, press_key
    from tests.support.localization_review import switch_language, review_frame
    ui, wait = automation, wait_for_accessible_state
    open_parent(launch_ui, ui, wait)
    ui.setValue('parent-child-selector', '1002')
    wait(lambda: ui.showing('parent-child-selected-1002'), 'second child selected')
    wait(lambda: ui.state('parent-screen-limit-toggle', ui.api.StateType.SENSITIVE),
         'second child controls finish loading')
    if not ui.state('parent-screen-limit-toggle', ui.api.StateType.CHECKED):
        ui.activate('parent-screen-limit-toggle')
    wait(lambda: ui.state('parent-daily-limit-selector', ui.api.StateType.SENSITIVE),
         'second child preferences finish loading')
    select_allowance(ui, ('custom',), child=EXISTING_CHILD)
    wait(lambda: ui.showing('parent-custom-daily-limit'), 'custom editor is available')
    ui.setText('parent-custom-daily-limit', '')
    wait(lambda: ui.content('parent-custom-daily-limit') == '', 'unsaved empty draft')
    switch_language(ui, wait, 'parent', language)
    assert ui.showing('parent-child-selected-1002')
    assert ui.content('parent-custom-daily-limit') == ''
    review_frame('parent-screen-' + language)
    ui.activate('parent-page-app-limits')
    wait(lambda: ui.find('parent-app-search') is not None
         and ui.state('parent-app-search', ui.api.StateType.SENSITIVE), 'catalogue ready')
    ui.setText('parent-app-search', 'minecraft')
    wait(lambda: len(ui.reader.app_rows(EXISTING_CHILD)) == 2, 'search returns matching apps')
    expected_rows = tuple(row for row in ui.reader.app_rows(EXISTING_CHILD)
                          if row[2] == 'pattern')
    assert len(expected_rows) == 1
    review_frame('parent-apps-' + language)
    ui.setValue('parent-filter-match-rule', ['pattern'])
    wait(lambda: ui.reader.app_rows(EXISTING_CHILD) == expected_rows, 'filter changes matching apps')
    # A second switch checks existing translated bindings without recreating data.
    switch_language(ui, wait, 'parent', 'ja')
    assert ui.showing('parent-child-selected-1002')
    assert ui.content('parent-app-search') == 'minecraft'
    assert ui.reader.app_rows(EXISTING_CHILD) == expected_rows
    review_frame('parent-apps-' + language + '-to-ja')


@pytest.mark.parametrize("dpi_scale", (1.25,))
def test_parent_allowance_choices_remain_semantically_reachable(
        launch_ui, automation, wait_for_accessible_state, request_display_scale,
        dpi_scale, tmp_path):
    events = tmp_path / "events.jsonl"
    ui = automation
    open_parent(
        launch_ui, ui, wait_for_accessible_state,
        environment={"ONPC_PARENT_COMPONENT_EVENTS_PATH": str(events)},
    )
    select_allowance(ui, (1410,))
    wait_for_accessible_state(
        lambda: any(event["event"] == "set_parent_control"
                    and event["daily_limit_minutes"] == 1410
                    for event in read_events(events)),
        "last allowance choice saves",
    )
    select_allowance(ui, ('custom',))
    wait_for_accessible_state(lambda: ui.showing("parent-custom-daily-limit"),
                              "custom editor opens")
    assert ui.state("parent-custom-daily-limit", ui.api.StateType.SENSITIVE)


@pytest.mark.parametrize("dpi_scale", (1.25,))
def test_parent_policy_legend_remains_reachable(
        launch_ui, automation, wait_for_accessible_state, request_display_scale,
        dpi_scale):
    ui = automation
    open_parent(launch_ui, ui, wait_for_accessible_state)
    ui.activate("parent-page-app-limits")
    wait_for_accessible_state(lambda: ui.find("parent-app-search") is not None
                              and ui.state("parent-app-search", ui.api.StateType.SENSITIVE),
                              "app catalogue loads")
    ui.activate("parent-legend-toggle")
    wait_for_accessible_state(lambda: ui.showing("parent-legend-content"),
                              "policy explanation is available")


@pytest.mark.parametrize("dpi_scale", (1.25,))
def test_feedback_editor_and_actions_remain_reachable(
        launch_ui, automation, wait_for_accessible_state, request_display_scale,
        dpi_scale):
    ui = automation
    open_parent(
        launch_ui, ui, wait_for_accessible_state,
        environment={"ONPC_PARENT_COMPONENT_SCENARIO": "feedback-attachments"},
    )
    ui.activate("parent-feedback-button")
    wait_for_accessible_state(lambda: ui.showing("feedback-dialog"),
                              "feedback opens")
    editor = feedback_editor(ui, wait_for_accessible_state)
    ui.setValue("feedback-format-style", "heading-2")
    wait_for_accessible_state(
        lambda: any(operation.get('attributes', {}).get('header') == 2
                    for operation in ui.getValue('feedback-editor-document')['ops']),
        "editor exposes Heading 2",
    )
    key = hashlib.sha256(b"sample-4.txt\0test attachment").hexdigest()[:16]
    ui.activate(f"feedback-remove-attachment-{key}")
    wait_for_accessible_state(
        lambda: ui.absent(f"feedback-attachment-{key}", within="feedback-dialog"),
        "last attachment is removed",
    )
    ui.activate("feedback-close")
    wait_for_accessible_state(lambda: ui.absent("feedback-dialog", within="parent-window"),
                              "feedback closes")


@pytest.mark.parametrize("dpi_scale", (1.25,))
@pytest.mark.parametrize("launcher,menu", (
    ("parent_component_preview", "parent-menu-button"),
    ("kiosk_preview", "kiosk-menu-button"),
    ("child_overlay_preview", "kiosk-menu-button"),
))
def test_about_content_remains_semantically_reachable(
        launch_ui, automation, wait_for_accessible_state, request_display_scale,
        dpi_scale, launcher, menu):
    launch_ui(launcher, wait_for_application=False)
    ui = automation
    wait_for_accessible_state(lambda: ui.find(menu) is not None,
                              "application menu publishes its ID")
    ui.setValue(menu, "about")
    wait_for_accessible_state(lambda: ui.showing("about-dialog"), "About opens")
    ui.reveal("about-copyright")
    assert ui.text("about-copyright") == (
        "© 2026 Puffy Slippers Tech LLC\nGPL-3.0-only · No warranty."
    )
