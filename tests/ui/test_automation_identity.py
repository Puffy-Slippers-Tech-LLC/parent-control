"""Qualify production IDs through the public accessibility connection."""

import pytest

from tests.e2e.accessible_ui import public_automation_id
from tests.support.automation_ids import audit_product_controls

pytestmark = pytest.mark.ui


@pytest.mark.parametrize("launcher", ["kiosk_preview", "child_overlay_preview"])
def test_request_ids_are_public_and_unique(
        launch_ui, automation, wait_for_accessible_state, launcher):
    launch_ui(launcher, wait_for_application=False)
    ui = automation
    wait_for_accessible_state(lambda: ui.find("kiosk-request-window") is not None,
                              "request surface publishes its automation ID")
    for identity in ("kiosk-request-submit", "kiosk-request-cancel",
                     "kiosk-duration-0", "kiosk-duration-custom",
                     "kiosk-duration-300", "kiosk-menu-button",
                     "kiosk-request-status"):
        assert ui.target(identity).get_accessible_id() == identity
    wait_for_accessible_state(lambda: audit_product_controls(ui, "kiosk-request-window"),
                              "complete request ID inventory")


def test_station_selected_uids_drive_the_public_guest_projection(
        launch_ui, automation, wait_for_accessible_state):
    from gi.repository import Atspi, GLib
    from tests.e2e.accessible_ui import AccessibleUI, CHILD, EXISTING_CHILD, PARENT, OTHER_PARENT

    launch_ui("kiosk_preview", wait_for_application=False)
    ui = automation
    wait_for_accessible_state(lambda: ui.showing("kiosk-approver-selector"), "request ready")
    ui.activate("kiosk-approver-selector")
    wait_for_accessible_state(
        lambda: ui.find("kiosk-approver-choice-1010") is not None,
        "approver choice is published",
    )
    ui.activate("kiosk-approver-choice-1010")
    wait_for_accessible_state(lambda: ui.showing("kiosk-approver-selected-1010"), "selected approver UID")
    ui.activate("kiosk-child-selector")
    wait_for_accessible_state(
        lambda: ui.find("kiosk-child-choice-1002") is not None,
        "child choice is published",
    )
    ui.activate("kiosk-child-choice-1002")
    wait_for_accessible_state(lambda: ui.showing("kiosk-child-selected-1002"), "selected child UID")
    wait_for_accessible_state(lambda: ui.showing("kiosk-screen-limit-notice"), "disabled child loaded")
    reader = AccessibleUI(Atspi, timeout=20, query_errors=(GLib.Error,),
                          dispatch=lambda: GLib.MainContext.default().iteration(False),
                          application_ids=launch_ui.application_ids,
                          application_owners=launch_ui.application_owners,
                          fixture_uids={CHILD: 1001, EXISTING_CHILD: 1002,
                                        PARENT: 1000, OTHER_PARENT: 1010})
    result = reader.kiosk_request_form()
    assert result['child'] == 'existing-fixture-child'
    assert result['approver'] == 'other-fixture-parent'
    assert result['duration_seconds'] == 1800
    assert result['request_enabled'] is False
    # REQUEST04 uses the same installed reader and public actions; each
    # selection validates the complete offered UID set before committing.
    result = reader.select_kiosk_account('child', CHILD, expected=(CHILD, EXISTING_CHILD))
    assert result['child'] == 'fixture-child'
    assert result['request_enabled'] is True
    result = reader.select_kiosk_account('approver', PARENT, expected=(PARENT, OTHER_PARENT))
    assert result['approver'] == 'fixture-parent'
    independent = reader.kiosk_request_form(enabled=True)
    assert independent == result


def test_parent_feedback_and_about_publish_public_ids(
        launch_ui, automation, wait_for_accessible_state):
    launch_ui("parent_component_preview", wait_for_application=False)
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi
    ui = automation
    wait_for_accessible_state(lambda: ui.find("parent-feedback-button") is not None,
                              "parent controls publish IDs")
    for identity in ("parent-window", "parent-menu-button",
                     "parent-child-selector", "parent-screen-limit-toggle"):
        assert ui.target(identity).get_accessible_id() == identity
    wait_for_accessible_state(lambda: audit_product_controls(ui, "parent-window"),
                              "complete Parent ID inventory")
    ui.activate("parent-feedback-button")
    wait_for_accessible_state(lambda: ui.find("feedback-dialog") is not None,
                              "feedback dialog publishes its ID")
    owners = [relation.get_target(index)
              for relation in ui.target("feedback-dialog").get_relation_set()
              if relation.get_relation_type() == Atspi.RelationType.CONTROLLED_BY
              for index in range(relation.get_n_targets())]
    assert owners == [ui.target("parent-window")]
    for identity in ("feedback-dialog", "feedback-webview", "feedback-send",
                     "feedback-close", "feedback-toggle-logs", "feedback-content"):
        assert ui.target(identity).get_accessible_id() == identity
    wait_for_accessible_state(lambda: ui.find("feedback-editor-input") is not None,
                              "rich editor publishes its input ID")
    from tests.e2e.accessible_ui import AccessibleUI
    guest_reader = AccessibleUI(Atspi, application_ids=launch_ui.application_ids,
                                application_owners=launch_ui.application_owners)
    for identity in ("feedback-editor-input", "feedback-format-bold",
                     "feedback-format-style", "feedback-format-link"):
        node = ui.target(identity)
        attributes = node.get_attributes()
        assert attributes["toolkit"] == "WebKitGTK"
        assert attributes["id"] == identity
        assert guest_reader.find_id(identity, root=ui.target("feedback-webview")) == node
    wait_for_accessible_state(lambda: audit_product_controls(ui, "feedback-dialog"),
                              "complete feedback ID inventory")
    ui.activate("feedback-close")
    wait_for_accessible_state(
        lambda: ui.absent("feedback-dialog", within="parent-window"),
        "feedback dialog closes",
    )
    assert not [relation.get_target(index)
                for relation in ui.target("parent-window").get_relation_set()
                if relation.get_relation_type() == Atspi.RelationType.CONTROLLER_FOR
                for index in range(relation.get_n_targets())
                if public_automation_id(relation.get_target(index)) == "feedback-dialog"]
    ui.activate("parent-menu-button", action_name="menu.popup")
    wait_for_accessible_state(lambda: ui.find("parent-menu-about") is not None,
                              "About menu item publishes its ID")
    ui.activate("parent-menu-about")
    wait_for_accessible_state(lambda: ui.find("about-dialog") is not None,
                              "About dialog publishes its ID")
    assert [relation.get_target(index)
            for relation in ui.target("about-dialog").get_relation_set()
            if relation.get_relation_type() == Atspi.RelationType.CONTROLLED_BY
            for index in range(relation.get_n_targets())] == [ui.target("parent-window")]
    for identity in ("about-version", "about-license-value",
                     "about-legal-notices-value", "about-integration-notice"):
        assert ui.target(identity).get_accessible_id() == identity
    wait_for_accessible_state(lambda: audit_product_controls(ui, "about-dialog"),
                              "complete About ID inventory")
