"""Shared public automation-ID inventory checks for UI tests."""

import re

from tests.e2e.accessible_ui import UiError, public_automation_id


_CONTROL_ROLES = frozenset({
    "button", "push button", "toggle button", "check box", "combo box",
    "entry", "password text", "link", "scroll bar", "slider",
})
_COMPOUND_ROLES = _CONTROL_ROLES | frozenset({"scroll pane"})
_PRESENTATION_ROLES = frozenset({"label", "text", "image", "panel", "grouping"})
_EMBEDDED_TOOLKIT_SURFACES = frozenset({"feedback-webview"})
_OWNED_ID = re.compile(
    r"(?:"
    r"(?:about|child|error-report|feedback|kiosk|parent|preview-screen|preview-viewer|startup-error)-"
    r"[a-z0-9]+(?:-[a-z0-9]+)*"
    r"|(?:e2e|ui)-watch-[a-z0-9]+(?:-[a-z0-9]+)*"
    r"|onpc-fixture-(?:native|flatpak|snap|game)-(?:primary|secondary)"
    r"(?:-[a-z0-9]+)*"
    r")\Z"
)


def _owned_automation_id(node):
    """Return only IDs owned by the repository's public UI namespaces."""
    identity = public_automation_id(node)
    return identity if _OWNED_ID.fullmatch(identity) else ""


def audit_owned_controls(ui, surface_identity, *, root=None):
    """Reject actionable repository-owned nodes without IDs below one surface.

    An identified compound control may contain anonymous toolkit implementation
    nodes. This exception never depends on a node's translated name and cannot
    excuse a product button placed directly in an identified window or panel.
    """
    root = ui.target(surface_identity) if root is None else root
    assert public_automation_id(root) == surface_identity, (
        f"wrong public surface for inventory: {public_automation_id(root)!r}"
    )
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
        identity = _owned_automation_id(node)
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
            toolkit_child = (owner_identity is not None
                             and (owner_role in _COMPOUND_ROLES
                                  or owner_identity in _EMBEDDED_TOOLKIT_SURFACES
                                  or owner_identity.endswith("-window-controls")))
            if not toolkit_child:
                missing.append((role, node.get_name() or "", owner_identity))
        next_identity = identity or owner_identity
        next_role = role if identity else owner_role
        pending.extend(
            (node.get_child_at_index(index), next_identity, next_role)
            for index in range(node.get_child_count())
        )
    assert not missing, f"owned controls without public IDs: {missing}"
    return identities


def audit_product_controls(ui, surface_identity):
    """Compatibility name for the production-owned control inventory."""
    return audit_owned_controls(ui, surface_identity)
