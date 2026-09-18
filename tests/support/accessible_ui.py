"""Shared public accessibility tree doubles for functional adapter unit tests."""

from types import SimpleNamespace
from unittest.mock import Mock

from accessible_ui import AccessibleUI


class Node:
    def __init__(self, name='', role='frame', children=(), states=('showing', 'visible', 'sensitive'),
                 appearance=None):
        self.name, self.role, self.children = name, role, list(children)
        self.parent = None
        for child in self.children:
            child.parent = self
        self.states = set(states)
        self.appearance = appearance  # Decoration and positions are not selectors.
        self.action = SimpleNamespace(get_n_actions=lambda: 1, get_action_name=lambda _: 'click',
                                      do_action=Mock(return_value=True))

    def clear_cache_single(self): pass
    def get_role_name(self): return self.role
    def get_name(self): return self.name
    def get_child_count(self): return len(self.children)
    def get_child_at_index(self, index): return self.children[index]
    def get_parent(self): return self.parent
    def get_state_set(self): return SimpleNamespace(contains=lambda state: state in self.states)
    def get_action_iface(self): return self.action


def ui_for(root):
    return AccessibleUI(SimpleNamespace(get_desktop=lambda _: root, Action=SimpleNamespace(
        get_n_actions=lambda action: action.get_n_actions(),
        get_action_name=lambda action, index: action.get_action_name(index),
        do_action=lambda action, index: action.do_action(index)), StateType=SimpleNamespace(
        SHOWING='showing', VISIBLE='visible', SENSITIVE='sensitive', DEFUNCT='defunct',
        FOCUSED='focused', SELECTED='selected', CHECKED='checked', EDITABLE='editable', MODAL='modal',
        ACTIVE='active'),
        CoordType=SimpleNamespace(SCREEN='screen')), timeout=0)
