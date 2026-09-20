"""Shared public accessibility tree doubles for functional adapter unit tests."""

from types import SimpleNamespace
from unittest.mock import Mock

from accessible_ui import AccessibleUI, PARENT_APPLICATION, KIOSK_APPLICATION, owned_applications


class Node:
    def __init__(self, name='', role='frame', children=(), states=('showing', 'visible', 'sensitive'),
                 appearance=None, identity='', description=''):
        self.name, self.role, self.children = name, role, list(children)
        self.identity = identity
        self.description = description
        self.parent = None
        for child in self.children:
            child.parent = self
        self.states = set(states)
        self.appearance = appearance  # Decoration and positions are not selectors.
        self.action = SimpleNamespace(get_n_actions=lambda: 1, get_action_name=lambda _: 'click',
                                      do_action=Mock(return_value=True))
        def grab_focus():
            self.states.add('focused')
            return True
        self.component = SimpleNamespace(
            grab_focus=Mock(side_effect=grab_focus),
            scroll_to=Mock(return_value=True),
        )

    def clear_cache_single(self): pass
    def get_role_name(self): return self.role
    def get_name(self): return self.name
    def get_accessible_id(self): return self.identity
    def get_attributes(self): return {}
    def get_description(self): return self.description
    def get_child_count(self): return len(self.children)
    def get_child_at_index(self, index): return self.children[index]
    def get_parent(self): return self.parent
    def get_state_set(self): return SimpleNamespace(contains=lambda state: state in self.states)
    def get_action_iface(self): return self.action
    def get_component_iface(self): return self.component
    def get_process_id(self): return 100
    def get_relation_set(self): return getattr(self, 'relations', ())


def product_tree(root):
    """Give owned-control doubles the same public application boundary as GTK."""
    pending = [root]
    identities = []
    seen = set()
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        seen.add(node)
        identities.append(node.identity)
        pending.extend(node.children)
    if not any(owned_applications(identity) for identity in identities):
        return root
    if any(identity in (PARENT_APPLICATION, KIOSK_APPLICATION) for identity in identities):
        return root
    app_id = KIOSK_APPLICATION if any(identity.startswith('kiosk-') for identity in identities) else PARENT_APPLICATION
    application = Node(identity=app_id, children=[root])
    # Separate toplevel fixture dialogs explicitly declare their transient
    # owner. Missing-owner regressions construct their own applications.
    primary = next((node for node in seen if node.identity in (
        'parent-window', 'kiosk-request-window', 'startup-error-window')), None)
    if primary is not None:
        for node in seen:
            if node.identity.endswith('-dialog'):
                parent = next((item for item in seen if item.identity == 'feedback-dialog'), primary) if node.identity == 'feedback-privacy-dialog' else primary
                node.relations = [SimpleNamespace(
                    get_relation_type=lambda: 'controlled-by', get_n_targets=lambda: 1,
                    get_target=lambda _index, parent=parent: parent)]
    application.get_process_id = getattr(primary or root, 'get_process_id', lambda: 100)
    return application


def ui_for(root):
    root = product_tree(root)
    return AccessibleUI(SimpleNamespace(get_desktop=lambda _: root, Action=SimpleNamespace(
        get_n_actions=lambda action: action.get_n_actions(),
        get_action_name=lambda action, index: action.get_action_name(index),
        do_action=lambda action, index: action.do_action(index)), StateType=SimpleNamespace(
        SHOWING='showing', VISIBLE='visible', SENSITIVE='sensitive', DEFUNCT='defunct',
        FOCUSED='focused', SELECTED='selected', CHECKED='checked', PRESSED='pressed', EDITABLE='editable', MODAL='modal',
        ACTIVE='active'),
        RelationType=SimpleNamespace(CONTROLLED_BY='controlled-by'),
        CoordType=SimpleNamespace(SCREEN='screen'),
        ScrollType=SimpleNamespace(ANYWHERE='anywhere')), timeout=0,
        fixture_uids={'Riley (Child)': 1001, 'Jordan (Child)': 1002, 'Morgan (Child)': 1003,
                      'Jamie (Parent)': 1000, 'Casey (Parent)': 1010})
