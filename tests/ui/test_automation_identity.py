"""Qualify production IDs through the public accessibility connection."""

import re

import pytest

from tests.e2e.accessible_ui import public_automation_id

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
        if node is None or node in seen:
            continue
        seen.add(node)
        node.clear_cache_single()
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
    audit_product_controls(ui, "kiosk-request-window")


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
    audit_product_controls(ui, "parent-window")
    ui.activate("parent-feedback-button")
    wait_for_accessible_state(lambda: ui.find("feedback-dialog") is not None,
                              "feedback dialog publishes its ID")
    for identity in ("feedback-dialog", "feedback-webview", "feedback-send",
                     "feedback-close", "feedback-toggle-logs", "feedback-content"):
        assert ui.target(identity).get_accessible_id() == identity
    wait_for_accessible_state(lambda: ui.find("feedback-editor-input") is not None,
                              "rich editor publishes its input ID")
    from tests.e2e.accessible_ui import AccessibleUI
    guest_reader = AccessibleUI(Atspi)
    for identity in ("feedback-editor-input", "feedback-format-bold",
                     "feedback-format-style", "feedback-format-link"):
        node = ui.target(identity)
        attributes = node.get_attributes()
        assert attributes["toolkit"] == "WebKitGTK"
        assert attributes["id"] == identity
        assert guest_reader.find_id(identity, root=ui.target("feedback-webview")) == node
    audit_product_controls(ui, "feedback-dialog")
    ui.activate("feedback-close")
    wait_for_accessible_state(
        lambda: (ui.find("feedback-dialog") is None
                 or not ui.state("feedback-dialog", Atspi.StateType.SHOWING)),
        "feedback dialog closes",
    )
    ui.activate("parent-menu-button", action_name="menu.popup")
    wait_for_accessible_state(lambda: ui.find("parent-menu-about") is not None,
                              "About menu item publishes its ID")
    ui.activate("parent-menu-about")
    wait_for_accessible_state(lambda: ui.find("about-dialog") is not None,
                              "About dialog publishes its ID")
    for identity in ("about-version", "about-license-value",
                     "about-legal-notices-value", "about-integration-notice"):
        assert ui.target(identity).get_accessible_id() == identity
    audit_product_controls(ui, "about-dialog")
