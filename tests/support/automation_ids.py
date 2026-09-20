"""Shared public automation-ID inventory checks for UI tests."""

import re

from tests.e2e.accessible_ui import UiError, public_automation_id


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
