"""Shared, owner-pinned Application UI observations for previews and E2E.

Only the public UIClient facade communicates with product processes. The small
node projection lets existing result assertions share one implementation with
external-provider assertions; it is not an AT-SPI input or discovery adapter.
Every input resolves the live element, and failed mutations are never replayed.
"""

from types import SimpleNamespace

from common.oh_no_parent_control_ui.application_ui_client import (
    UIClient, UIClientError, UIElement,
)


ENDPOINTS = {
    'parent': 'com.puffyslippers.OhNoParentControl.Parent',
    'kiosk': 'com.puffyslippers.OhNoParentControl',
    'child-request': 'com.puffyslippers.OhNoParentControl.ChildRequest',
    'child-panel': 'com.puffyslippers.OhNoParentControl.ChildUI',
}
PRODUCT_APPLICATIONS = frozenset(ENDPOINTS.values())


def is_product_node(node):
    return isinstance(node, ApplicationNode)


def utf16_length(text):
    return len(text.encode('utf-16-le')) // 2


def utf16_index(text, offset):
    """Translate a public Quill offset, refusing a split surrogate pair."""
    if type(offset) is not int or offset < 0:
        raise UIClientError('InvalidResponse')
    units = 0
    for index, char in enumerate(text):
        if units == offset:
            return index
        units += utf16_length(char)
    if units == offset:
        return len(text)
    raise UIClientError('InvalidResponse')


class ApplicationUI:
    """Discover finite product endpoints and retain each unique process owner.

    Explicit ``clients`` also supports launch-owned non-unique error reporters.
    A caller must deliberately replace this catalog (or call forget after its
    owned process exits) when an application restarts.
    """

    def __init__(self, api=None, *, clients=None, connection=None, endpoints=None):
        self.api = api
        self.connection = connection
        self.clients = dict(clients or {})
        self.explicit_clients = clients is not None
        self.endpoints = endpoints

    def forget(self, frontend):
        self.clients.pop(frontend, None)

    def client(self, frontend):
        if frontend not in self.clients:
            self.clients[frontend] = UIClient(frontend, connection=self.connection)
        return self.clients[frontend]

    def _available(self):
        if self.explicit_clients:
            return list(self.clients)
        from gi.repository import Gio, GLib
        if self.connection is None:
            self.connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        names, = self.connection.call_sync(
            'org.freedesktop.DBus', '/org/freedesktop/DBus',
            'org.freedesktop.DBus', 'ListNames', None, GLib.VariantType.new('(as)'),
            Gio.DBusCallFlags.NONE, 15000, None).unpack()
        return [frontend for frontend, name in ENDPOINTS.items() if name in names]

    def applications(self, *, owner_pids=None, application_owners=None,
                     application_ids=None):
        owners = application_owners() if callable(application_owners) else application_owners
        pids = owner_pids() if callable(owner_pids) else owner_pids
        allowed = application_ids() if callable(application_ids) else application_ids
        result, seen = [], set()
        available = self._available()
        receipts = self.endpoints() if callable(self.endpoints) else self.endpoints
        for receipt in receipts or ():
            if (type(receipt) is not dict or set(receipt) != {
                    'application_id', 'owner', 'object_path', 'pid'}
                    or receipt['application_id'] not in PRODUCT_APPLICATIONS
                    or type(receipt['pid']) is not int or receipt['pid'] <= 0):
                raise UIClientError('Denied')
            key = (receipt['application_id'], receipt['owner'], receipt['object_path'])
            if key not in self.clients:
                self.clients[key] = UIClient(receipt['application_id'],
                    owner=receipt['owner'], object_path=receipt['object_path'],
                    connection=self.connection)
            if self.clients[key].pid != receipt['pid']:
                raise UIClientError('Denied')
            available.append(key)
        for frontend in available:
            name = ENDPOINTS.get(frontend) if isinstance(frontend, str) else frontend[0]
            if allowed is not None and name is not None and name not in allowed:
                continue
            client = self.client(frontend)
            identity = (client.owner, client.object_path)
            if identity in seen:
                continue
            seen.add(identity)
            if pids is not None and client.pid not in pids:
                raise UIClientError('Denied')
            if owners is not None and client.pid not in owners.get(client.application_id, ()):
                raise UIClientError('Denied')
            result.append(self._application(client))
        return result

    def _application(self, client):
        application = ApplicationNode(self, client, None, {
            'id': client.application_id, 'type': 'application', 'role': 'application',
            'visible': True, 'enabled': True, 'operations': [],
        })
        surfaces = client.listSurfaces()
        by_surface = {}
        for surface in surfaces:
            identity = surface['id']
            inventory = client.inventory(identity)
            by_id = {item['id']: ApplicationNode(self, client, identity, item,
                                               application=application)
                     for item in inventory}
            if identity not in by_id:
                raise UIClientError('InvalidResponse')
            root = by_id[identity]
            root.surface_metadata = surface
            by_surface[identity] = root
            for element_id, node in by_id.items():
                if element_id == identity:
                    continue
                parent_id = node.metadata.get('parent_id') or identity
                parent = by_id.get(parent_id)
                if parent is None or parent is node:
                    raise UIClientError('InvalidResponse')
                node.parent = parent
                parent.children.append(node)
            # A malformed provider must not hide a cycle or detached subtree.
            stack, seen = [root], set()
            while stack:
                node = stack.pop()
                if node in seen:
                    raise UIClientError('InvalidResponse')
                seen.add(node)
                stack.extend(node.children)
            if len(seen) != len(by_id):
                raise UIClientError('InvalidResponse')
            application.children.append(root)
            root.parent = application
        for root in by_surface.values():
            parent_id = root.surface_metadata.get('parent_id')
            if parent_id is not None:
                if parent_id not in by_surface:
                    raise UIClientError('InvalidResponse')
                root.controller = by_surface[parent_id]
        return application

    def find_all(self, identity, **ownership):
        matches = []
        stack = self.applications(**ownership)
        while stack:
            node = stack.pop()
            if node.identity == identity:
                matches.append(node)
            stack.extend(node.children)
        if len(matches) > 1:
            raise UIClientError('Unavailable')
        return matches

    def getElementById(self, identity, **ownership):
        matches = self.find_all(identity, **ownership)
        if not matches:
            raise UIClientError('Unavailable')
        return matches[0]

    def refresh(self, node, *, owner_pids=None, application_owners=None,
                application_ids=None):
        """Reacquire the original process and surface without global discovery."""
        if not isinstance(node, ApplicationNode) or node.catalog is not self:
            raise UIClientError('Denied')
        owners = application_owners() if callable(application_owners) else application_owners
        pids = owner_pids() if callable(owner_pids) else owner_pids
        allowed = application_ids() if callable(application_ids) else application_ids
        client = node.client
        if ((pids is not None and client.pid not in pids)
                or (allowed is not None and client.application_id not in allowed)
                or (owners is not None and client.pid not in owners.get(client.application_id, ()))):
            raise UIClientError('Denied')
        # listSurfaces and inventory revalidate the client's original bus owner.
        stack = [self._application(client)]
        while stack:
            current = stack.pop()
            if (current.identity == node.identity and current.surface_id == node.surface_id
                    and current.bus == node.bus and current.path == node.path):
                return current
            stack.extend(current.children)
        raise UIClientError('Unavailable')


class ApplicationNode:
    """Read projection of a stable, scoped API element, with fresh UI inputs."""

    def __init__(self, catalog, client, surface_id, metadata, *, application=None):
        self.catalog, self.client = catalog, client
        self.surface_id, self.identity = surface_id, metadata['id']
        self.metadata = dict(metadata)
        self.application = application or self
        self.element = (UIElement(client, surface_id, self.identity)
                        if surface_id is not None else None)
        self.ui_element = self.element
        self.parent = None
        self.controller = None
        self.children = []
        self.surface_metadata = {}
        self._snapshot = None
        self.bus = client.owner
        # A stable logical reference, never an AT-SPI object or routing path.
        self.path = client.object_path + '/' + (surface_id or 'application').replace('-', '_') + '/' + self.identity.replace('-', '_').replace('.', '_')

    def __eq__(self, other):
        return isinstance(other, ApplicationNode) and (self.bus, self.path) == (other.bus, other.path)

    def __hash__(self):
        return hash((self.bus, self.path))

    def snapshot(self):
        if self.element is None:
            return self.metadata
        if self._snapshot is None:
            self._snapshot = self.element.snapshot()
        return self._snapshot

    @property
    def value(self):
        return self.element.value

    @property
    def text(self):
        return self.element.text

    @property
    def choices(self):
        return self.element.choices

    def setValue(self, value):
        self._snapshot = None
        self.element.setValue(value)

    def setText(self, text):
        self._snapshot = None
        self.element.setText(text)

    def activate(self):
        self._snapshot = None
        self.element.activate()

    def close(self):
        self._snapshot = None
        self.element.close()

    def getValue(self):
        return self.value

    def getText(self):
        return self.text

    def getChoices(self):
        return self.choices

    def get_accessible_id(self):
        return self.identity

    def get_attributes(self):
        return {'toolkit': 'ApplicationUI', 'id': self.identity}

    def get_name(self):
        data = self.snapshot()
        return data.get('name') or data.get('text', '')

    snapshot_name = get_name

    def get_description(self):
        return self.snapshot().get('description', '')

    def get_role_name(self):
        role = self.snapshot().get('role', '') or self.metadata.get('type', '')
        return {'checkbox': 'check box', 'check-box': 'check box', 'radio': 'radio button',
                'textbox': 'entry', 'text-box': 'entry', 'button': 'push button',
                'switch': 'toggle button', 'combobox': 'combo box', 'combo-box': 'combo box',
                'listitem': 'list item', 'list-item': 'list item',
                'tablist': 'page tab list', 'tab-list': 'page tab list',
                'tab': 'page tab', 'menuitem': 'menu item', 'menu-item': 'menu item',
                'menu-item-checkbox': 'check menu item',
                'menu-item-radio': 'radio menu item'}.get(role, role)

    def get_state_set(self):
        data = self.snapshot()
        values = set()
        if data.get('visible'):
            values.update(('VISIBLE', 'SHOWING'))
        if data.get('enabled'):
            values.add('SENSITIVE')
        if self.surface_metadata.get('modal'):
            values.add('MODAL')
        if data.get('value') is True:
            values.update(('CHECKED', 'PRESSED', 'SELECTED', 'EXPANDED'))
        if 'setText' in data.get('operations', ()):
            values.add('EDITABLE')
        api = self.catalog.api
        def contains(state):
            if api is not None:
                return any(getattr(api.StateType, value, object()) == state for value in values)
            return str(state).upper() in values
        return SimpleNamespace(contains=contains)

    snapshot_state_set = get_state_set

    def get_child_count(self):
        return len(self.children)

    def get_child_at_index(self, index):
        return self.children[index]

    def get_parent(self):
        return self.parent

    def get_application(self):
        return self.application

    def get_process_id(self):
        return self.client.pid

    def get_relation_set(self):
        if self.controller is None:
            return []
        api = self.catalog.api
        relation = (api.RelationType.CONTROLLED_BY if api is not None else 'controlled-by')
        return [SimpleNamespace(get_relation_type=lambda: relation,
                                get_n_targets=lambda: 1,
                                get_target=lambda index: self.controller if index == 0 else None)]

    def clear_cache_single(self):
        # A projection belongs to one immutable read boundary. New observations
        # reconstruct it; do not mix snapshots during a single tree traversal.
        pass

    def get_action_iface(self):
        return self if 'activate' in self.snapshot().get('operations', ()) else None

    def get_n_actions(self):
        return 1 if self.get_action_iface() is not None else 0

    def get_action_name(self, index):
        if index != 0 or self.get_n_actions() != 1:
            raise UIClientError('Unsupported')
        return 'activate'

    def do_action(self, index):
        self.get_action_name(index)
        self.activate()
        return True

    def get_text_iface(self):
        return self if 'getText' in self.snapshot().get('operations', ()) else None

    def get_component_iface(self):
        return None

    def get_character_count(self):
        return len(self.text)

    def get_text(self, start, end):
        text = self.text
        return text[start:] if end == -1 else text[start:end]

    def get_character_at_offset(self, offset):
        return ord(self.text[offset])

    def get_attribute_run(self, offset, include_defaults=True):
        """Project the public document's format runs in Python text offsets."""
        text = self.text
        if type(offset) is not int or not 0 <= offset <= len(text):
            raise UIClientError('InvalidArgument')
        document = self.document()
        if type(document) is not dict or type(document.get('ops')) is not list:
            raise UIClientError('InvalidResponse')
        start = 0
        for operation in document['ops']:
            inserted = operation.get('insert')
            if type(inserted) is not str:
                raise UIClientError('InvalidResponse')
            end = start + len(inserted)
            if start <= offset < end:
                attributes = operation.get('attributes', {})
                if type(attributes) is not dict:
                    raise UIClientError('InvalidResponse')
                normalized = {'weight': '700' if attributes.get('bold') else '400',
                              'style': 'italic' if attributes.get('italic') else 'normal',
                              'underline': 'single' if attributes.get('underline') else 'none',
                              'strikethrough': 'true' if attributes.get('strike') else 'false'}
                return normalized, start, min(end, len(text))
            start = end
        raise UIClientError('InvalidResponse')

    def _selection(self):
        if self.identity not in ('feedback-editor-input', 'feedback-webview'):
            raise UIClientError('Unsupported')
        selected = self.client.getValue('feedback-editor-selection', surface_id=self.surface_id)
        text = self.text
        return (utf16_index(text, selected['index']),
                utf16_index(text, selected['index'] + selected['length']))

    def get_n_selections(self):
        start, end = self._selection()
        return int(start != end)

    def get_selection(self, index):
        if index != 0:
            raise UIClientError('InvalidArgument')
        start, end = self._selection()
        return SimpleNamespace(start_offset=start, end_offset=end)

    def get_caret_offset(self):
        return self._selection()[1]

    def document(self):
        return self.client.getValue('feedback-editor-document', surface_id=self.surface_id)
