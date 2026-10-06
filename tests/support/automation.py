"""Shared Application UI inputs and provider-scoped fixture observations."""

from common.oh_no_parent_control_ui.application_ui_client import UIClientError
from tests.support.application_ui import is_product_node

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
                 application_ui_endpoints=None, complete_read_wait=None):
        self.api = api
        self.root = root
        self.query_errors = query_errors
        self.owner_pids = owner_pids
        self.application_ids = application_ids
        self.application_owners = application_owners
        self.application_owner_history = application_owner_history
        self.application_ui_endpoints = application_ui_endpoints
        self.complete_read_wait = complete_read_wait
        from tests.e2e.public_atspi import PublicAtspi
        # Real previews share the installed catalog; synthetic unit roots keep
        # their deliberately supplied in-memory provider tree.
        real_api = isinstance(api, PublicAtspi) or getattr(api, '__name__', '') == 'gi.repository.Atspi'
        reader_root = None if real_api else lambda: self.root()
        self._reader = AccessibleUI(api, root=reader_root, include_text_children=True)
        if real_api:
            self.api = self._reader.api

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
                          'application_owners', 'application_owner_history',
                          'application_ui_endpoints'):
            setattr(self._reader, attribute, getattr(self, attribute))
        return self._reader

    def nodes(self, root=None, *, strict=False, protected_ids=(), snapshot=None,
              identities=None):
        """Use the same traversal and completeness rules as installed tests."""
        yield from self.reader.nodes(root, strict=strict, protected_ids=protected_ids,
                                     snapshot=snapshot, identities=identities)

    def complete_parent_language_setup(self):
        self.complete_language_setup('parent')

    def complete_request_language_setup(self):
        self.complete_language_setup('kiosk')

    def complete_language_setup(self, surface):
        """Use the installed worker's guarded first-run Continue helper."""
        try:
            self.reader.complete_language_setup(surface)
        except UiError as error:
            raise AutomationError(str(error).replace("ui:", "automation:")) from error

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
        try:
            states = node.get_state_set()
        except self.query_errors as error:
            # Layout changes can retire the public object after ID lookup.
            # A failed state query proves neither visibility nor absence;
            # discard this read so the bounded wait reacquires the ID.
            self.reader.invalidate_observation()
            raise AutomationError("automation:incomplete-tree") from error
        return (states.contains(self.api.StateType.SHOWING)
                and states.contains(self.api.StateType.VISIBLE)
                and not states.contains(self.api.StateType.DEFUNCT))

    def text(self, identity):
        """Read the public label after resolving the element by ID."""
        return self.target(identity).get_name()

    def content(self, identity, *, maximum=65536):
        """Read bounded public text from an ID-selected accessible."""
        node = self.target(identity)
        if is_product_node(node):
            value = node.getText()
            if len(value) > maximum:
                raise AutomationError("automation:text-bound:" + identity)
            return value
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
        """Resolve product edit readiness, or focus an external fixture recipient.

        Application UI operations address the control directly. Legacy shared
        recipes may retain this preparation call, but it makes no focus claim.
        """
        if self.input_uncertain:
            raise AutomationError("automation:uncertain-input")
        node = self.target(identity)
        if is_product_node(node):
            snapshot = node.element.snapshot()
            if not snapshot['visible'] or not snapshot['enabled']:
                raise AutomationError("automation:unavailable:" + identity)
            return node
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
        if is_product_node(node):
            if not node.element.visible:
                raise AutomationError("automation:hidden:" + identity)
            return node
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
        if is_product_node(node):
            if action_name not in (None, 'menu.popup', 'button.activate', 'check.toggle',
                                   'switch.toggle', 'row.activate', 'activate', 'click', 'press'):
                raise AutomationError("automation:unsupported-action:" + identity)
            return self._product_input(node, "activate")
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

    def _product_input(self, node, operation, *arguments):
        if self.input_uncertain:
            raise AutomationError("automation:uncertain-input")
        self.reader.invalidate_observation()
        try:
            return getattr(node, operation)(*arguments)
        except UIClientError as error:
            self.input_uncertain = error.uncertain
            raise AutomationError("automation:application-ui:" + error.code) from error

    def getValue(self, identity):
        return self.target(identity).getValue()

    def setValue(self, identity, value):
        return self._product_input(self.target(identity), "setValue", value)

    def getText(self, identity):
        return self.target(identity).getText()

    def setText(self, identity, text):
        return self._product_input(self.target(identity), "setText", text)

    def getChoices(self, identity):
        return self.target(identity).getChoices()

    def close(self, identity):
        return self._product_input(self.target(identity), "close")

    def reconstruct(self, frontend):
        """Deliberately discard an exited launch's pinned client before reopen."""
        catalog = self.reader.application_ui
        client = catalog.clients.get(frontend)
        if client is not None and self.owner_pids is not None and client.pid in self.owner_pids():
            raise AutomationError('automation:previous-owner-still-running')
        catalog.forget(frontend)
        self.reader.invalidate_observation()
