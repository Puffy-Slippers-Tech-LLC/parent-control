"""Public AT-SPI ID lookup and semantic interaction; no selector fallbacks."""

import warnings

from tests.e2e.accessible_ui import public_automation_id


def public_action_name(api, action, index):
    # libatspi annotates the old get_name symbol as rename-to get_action_name,
    # so GI incorrectly marks the recommended public name itself deprecated.
    # Scope this metadata defect to that one call/message; all other warnings
    # and errors retain the runner's policy.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=r"^Atspi\.Action\.get_action_name is deprecated$",
                                category=DeprecationWarning)
        return api.Action.get_action_name(action, index)


class AutomationError(RuntimeError):
    pass


class Automation:
    def __init__(self, api, root, *, query_errors=()):
        self.api = api
        self.root = root
        self.query_errors = query_errors

    def nodes(self):
        """Traverse the current public tree without retaining stale nodes."""
        pending = [self.root()]
        seen = set()
        while pending:
            node = pending.pop()
            if node is None or node in seen:
                continue
            seen.add(node)
            if len(seen) > 6000:
                raise AutomationError("automation:tree-bound")
            try:
                node.clear_cache_single()
                pending.extend(node.get_child_at_index(i)
                               for i in range(node.get_child_count()))
            except self.query_errors:
                continue
            yield node

    def find_all(self, identity):
        """Return every fresh match so callers can assert surface cardinality."""
        matches = []
        for node in self.nodes():
            try:
                if public_automation_id(node) == identity:
                    matches.append(node)
            except self.query_errors:
                continue
        return matches

    def find(self, identity):
        matches = self.find_all(identity)
        if len(matches) > 1:
            raise AutomationError("automation:ambiguous-id:" + identity)
        return matches[0] if matches else None

    def target(self, identity):
        node = self.find(identity)
        if node is None:
            raise AutomationError("automation:missing-public-id:" + identity)
        return node

    def state(self, identity, state):
        return self.target(identity).get_state_set().contains(state)

    def showing(self, identity):
        node = self.find(identity)
        if node is None:
            return False
        states = node.get_state_set()
        return (states.contains(self.api.StateType.SHOWING)
                and states.contains(self.api.StateType.VISIBLE)
                and not states.contains(self.api.StateType.DEFUNCT))

    def text(self, identity):
        """Read public accessible text after resolving the element by ID."""
        return self.target(identity).get_name()

    def content(self, identity, *, maximum=65536):
        """Read bounded public text from an ID-selected accessible."""
        node = self.target(identity)
        interface = node.get_text_iface()
        if interface is None:
            raise AutomationError("automation:missing-text:" + identity)
        count = interface.get_character_count()
        if type(count) is not int or count < 0 or count > maximum:
            raise AutomationError("automation:text-bound:" + identity)
        # Accessible.get_text() is the deprecated interface getter. GI returns
        # the same Accessible instance for get_text_iface(), so select Text's
        # method explicitly instead of hitting the colliding getter.
        return self.api.Text.get_text(interface, 0, count)

    def focus(self, identity):
        """Move normal keyboard focus only to a published, revealed control."""
        node = self.reveal(identity)
        if not node.get_state_set().contains(self.api.StateType.SENSITIVE):
            raise AutomationError("automation:disabled:" + identity)
        component = node.get_component_iface()
        if component is None or not component.grab_focus():
            raise AutomationError("automation:focus-refused:" + identity)
        node = self.target(identity)
        if not node.get_state_set().contains(self.api.StateType.FOCUSED):
            raise AutomationError("automation:focus-unconfirmed:" + identity)
        return node

    def reveal(self, identity):
        node = self.target(identity)
        states = node.get_state_set()
        if states.contains(self.api.StateType.DEFUNCT):
            raise AutomationError("automation:defunct:" + identity)
        if not states.contains(self.api.StateType.SHOWING):
            component = node.get_component_iface()
            if component is None or not component.scroll_to(self.api.ScrollType.ANYWHERE):
                raise AutomationError("automation:reveal-refused:" + identity)
        node = self.target(identity)
        states = node.get_state_set()
        if not all(states.contains(state) for state in (
                self.api.StateType.SHOWING, self.api.StateType.VISIBLE)):
            raise AutomationError("automation:unreachable:" + identity)
        return node

    def activate(self, identity, *, action_name=None):
        node = self.reveal(identity)
        if not node.get_state_set().contains(self.api.StateType.SENSITIVE):
            raise AutomationError("automation:disabled:" + identity)
        if node.get_state_set().contains(self.api.StateType.DEFUNCT):
            raise AutomationError("automation:defunct:" + identity)
        action = node.get_action_iface()
        if action is None:
            raise AutomationError("automation:ambiguous-action:" + identity)
        count = action.get_n_actions()
        if action_name is None:
            candidates = [0] if count == 1 else []
        else:
            candidates = [index for index in range(count)
                          if public_action_name(self.api, action, index) == action_name]
        if len(candidates) != 1:
            raise AutomationError("automation:ambiguous-action:" + identity)
        # Never retry input: a false result or transport exception can leave
        # its effect uncertain. Consumers independently observe the outcome.
        if not action.do_action(candidates[0]):
            raise AutomationError("automation:action-refused:" + identity)
