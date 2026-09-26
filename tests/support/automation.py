"""Public AT-SPI ID lookup and semantic interaction; no selector fallbacks."""

from tests.e2e.accessible_ui import (
    AccessibleUI,
    UiError,
    owned_applications,
    owned_surface_id,
    public_automation_id,
    public_action_name,
)


class AutomationError(RuntimeError):
    pass


class Automation:
    def __init__(self, api, root, *, query_errors=(), owner_pids=None, application_ids=None,
                 application_owners=None, application_owner_history=None,
                 complete_read_wait=None):
        self.api = api
        self.root = root
        self.query_errors = query_errors
        self.owner_pids = owner_pids
        self.application_ids = application_ids
        self.application_owners = application_owners
        self.application_owner_history = application_owner_history
        self.complete_read_wait = complete_read_wait
        self._reader = AccessibleUI(api, root=lambda: self.root(), include_text_children=True)

    @property
    def input_uncertain(self):
        return self._reader.input_uncertain

    @input_uncertain.setter
    def input_uncertain(self, value):
        self._reader.input_uncertain = value

    @property
    def reader(self):
        # Fixture ownership callbacks can change as previews start and stop.
        # Keep the host facade's existing configuration API, with one engine.
        for attribute in ('query_errors', 'owner_pids', 'application_ids',
                          'application_owners', 'application_owner_history'):
            setattr(self._reader, attribute, getattr(self, attribute))
        return self._reader

    def nodes(self, root=None, *, strict=False, protected_ids=(), snapshot=None,
              identities=None):
        """Use the same traversal and completeness rules as installed tests."""
        yield from self.reader.nodes(root, strict=strict, protected_ids=protected_ids,
                                     snapshot=snapshot, identities=identities)

    def find_all(self, identity):
        """Return every fresh match so callers can assert surface cardinality."""
        reader = self.reader

        def read():
            try:
                with reader.observation():
                    if owned_applications(identity) or identity.startswith("child-"):
                        target = reader.snapshot_owned_target(identity, showing=False)
                        return [] if target is None else [target]
                    # Generic fixture IDs retain explicit cardinality checks,
                    # but an incomplete tree still cannot authorize input.
                    nodes, _edges, identities, _facts = reader.read_snapshot()
                    return [node for node in nodes if identities[node] == identity]
            except self.query_errors as error:
                # A node can disappear during a complete AT-SPI traversal.
                # Discard the snapshot and let the bounded read wait retry it.
                raise AutomationError("automation:incomplete-tree") from error
            except UiError as error:
                raise AutomationError(str(error).replace("ui:", "automation:").replace(
                    "ambiguous-automation-id", "ambiguous-id")) from error

        if self.complete_read_wait is None:
            return read()
        result = None

        def capture_complete_read():
            nonlocal result
            result = read()
            return True

        self.complete_read_wait(capture_complete_read,
                                f"complete public tree for {identity}")
        if result is None:
            raise AutomationError("automation:complete-read-wait-returned")
        return result

    def absent(self, identity, *, within):
        """Complete fresh exclusion anchored by a positive public surface ID."""
        try:
            return self.reader.absent_id(identity, within=within)
        except UiError as error:
            raise AutomationError(str(error).replace("ui:", "automation:")) from error

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
        if self.input_uncertain:
            raise AutomationError("automation:uncertain-input")
        node = self.target(identity)
        states = node.get_state_set()
        if states.contains(self.api.StateType.DEFUNCT):
            raise AutomationError("automation:defunct:" + identity)
        if not states.contains(self.api.StateType.SENSITIVE):
            raise AutomationError("automation:disabled:" + identity)
        surface = owned_surface_id(identity)
        if (surface is not None and not identity.startswith("child-")
                and node.get_attributes().get("toolkit") != "WebKitGTK"):
            self.activate(surface, action_name="focus." + identity)
            # An accepted action does not prove which control received focus.
            # Keep uncertainty latched if reacquisition itself raises.
            self.input_uncertain = True
        else:
            node = self.reveal(identity)
            component = node.get_component_iface()
            self.input_uncertain = True
            if component is None or not component.grab_focus():
                raise AutomationError("automation:focus-refused:" + identity)
        node = self.target(identity)
        states = node.get_state_set()
        if states.contains(self.api.StateType.DEFUNCT) or not all(states.contains(state) for state in (
                self.api.StateType.FOCUSED, self.api.StateType.SHOWING,
                self.api.StateType.VISIBLE, self.api.StateType.SENSITIVE)):
            self.input_uncertain = True
            raise AutomationError("automation:focus-unconfirmed:" + identity)
        self.input_uncertain = False
        return node

    def reveal(self, identity):
        node = self.target(identity)
        states = node.get_state_set()
        if states.contains(self.api.StateType.DEFUNCT):
            raise AutomationError("automation:defunct:" + identity)
        if not states.contains(self.api.StateType.SHOWING):
            surface = owned_surface_id(identity)
            if (surface is not None and not identity.startswith("child-")
                    and node.get_attributes().get("toolkit") != "WebKitGTK"):
                self.focus(identity)
            else:
                component = node.get_component_iface()
                if component is None or not component.scroll_to(self.api.ScrollType.ANYWHERE):
                    raise AutomationError("automation:reveal-refused:" + identity)
        node = self.target(identity)
        states = node.get_state_set()
        if states.contains(self.api.StateType.DEFUNCT) or not all(states.contains(state) for state in (
                self.api.StateType.SHOWING, self.api.StateType.VISIBLE)):
            raise AutomationError("automation:unreachable:" + identity)
        return node

    def activate(self, identity, *, action_name=None):
        if self.input_uncertain:
            raise AutomationError("automation:uncertain-input")
        # Resolve ownership, ambiguity and recipient from one complete fresh
        # snapshot, then invoke the public action directly. SHOWING is a
        # viewport/rendering state and cannot turn clipping into a requirement
        # to scroll or focus before activation; VISIBLE is the application's
        # public hidden/shown state.
        node = self.target(identity)
        states = node.get_state_set()
        if not states.contains(self.api.StateType.VISIBLE):
            raise AutomationError("automation:hidden:" + identity)
        if not states.contains(self.api.StateType.SENSITIVE):
            raise AutomationError("automation:disabled:" + identity)
        if states.contains(self.api.StateType.DEFUNCT):
            raise AutomationError("automation:defunct:" + identity)
        try:
            self.reader._invoke_target(node, action_name)
        except UiError as error:
            code = str(error).replace('ui:', 'automation:')
            if code in ('automation:missing-action', 'automation:missing-or-ambiguous-action'):
                code = 'automation:ambiguous-action'
            raise AutomationError(code + ':' + identity) from error
