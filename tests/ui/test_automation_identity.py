"""Qualify production IDs through the public accessibility connection."""

import re

import pytest

from tests.e2e.accessible_ui import UiError, public_automation_id

pytestmark = pytest.mark.ui


_CONTROL_ROLES = frozenset({
    "button", "push button", "toggle button", "check box", "combo box",
    "entry", "password text", "link", "scroll bar", "slider",
})
_COMPOUND_ROLES = _CONTROL_ROLES | frozenset({"scroll pane"})
_TOOLKIT_WINDOW_ACTIONS = frozenset({"Close", "Minimize", "Maximize", "Restore"})
_PRESENTATION_ROLES = frozenset({"label", "image", "panel", "grouping"})
_EMBEDDED_TOOLKIT_SURFACES = frozenset({"feedback-webview"})
_PRODUCT_ID = re.compile(
    r"(?:about|error-report|feedback|kiosk|parent|preview-screen|preview-viewer|startup-error)-"
    r"[a-z0-9]+(?:-[a-z0-9]+)*\Z"
)


def _product_automation_id(node):
    """Return only IDs owned by the product's semantic public namespaces."""
    identity = public_automation_id(node)
    return identity if _PRODUCT_ID.fullmatch(identity) else ""


def audit_product_controls(ui, surface_identity):
    """Reject actionable product nodes without IDs below one public surface.

    An identified compound control may contain anonymous toolkit implementation
    nodes. Window-decoration actions are likewise GTK-owned. Neither exception
    covers a product button placed directly in an identified window or panel.
    """
    root = ui.target(surface_identity)
    pending = [(root, None, None)]
    seen = set()
    identities = {}
    missing = []
    while pending:
        node, owner_identity, owner_role = pending.pop()
        if node is None:
            raise UiError("ui:incomplete-tree")
        if node in seen:
            continue
        seen.add(node)
        node.clear_cache_single()
        if (node.get_attributes() is None
                or node.get_state_set().contains(ui.api.StateType.DEFUNCT)):
            raise UiError("ui:incomplete-tree")
        identity = _product_automation_id(node)
        role = node.get_role_name()
        if identity:
            assert identity not in identities or identities[identity] is node, (
                f"duplicate public ID {identity} below {surface_identity}"
            )
            identities[identity] = node
        action = node.get_action_iface()
        # GTK may publish a generic Action interface on presentation nodes.
        # Their semantic role remains non-interactive; actual controls and
        # custom actionable roles still require product IDs.
        actionable = (role not in _PRESENTATION_ROLES
                      and action is not None and action.get_n_actions() > 0)
        if (actionable or role in _CONTROL_ROLES) and not identity:
            name = node.get_name() or ""
            toolkit_child = (owner_identity is not None
                             and (owner_role in _COMPOUND_ROLES
                                  or owner_identity in _EMBEDDED_TOOLKIT_SURFACES))
            window_decoration = name in _TOOLKIT_WINDOW_ACTIONS
            if not toolkit_child and not window_decoration:
                missing.append((role, name, owner_identity))
        next_identity = identity or owner_identity
        next_role = role if identity else owner_role
        pending.extend(
            (node.get_child_at_index(index), next_identity, next_role)
            for index in range(node.get_child_count())
        )
    assert not missing, f"product controls without public IDs: {missing}"
    return identities


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
    ui.activate("kiosk-approver-choice-1010")
    wait_for_accessible_state(lambda: ui.showing("kiosk-approver-selected-1010"), "selected approver UID")
    ui.activate("kiosk-child-selector")
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
