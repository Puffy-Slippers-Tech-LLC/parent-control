"""Public AT-SPI bus client shared by previews and installed UI automation.

GetItems supplies fresh structural facts for one traversal, never action state.
No provider-private endpoints, event-cache freshness assumptions or P2P sockets.
The small facade covers the interfaces used by the shared automation engine.
"""

from contextlib import contextmanager
import os
from types import SimpleNamespace
from weakref import WeakValueDictionary


PREFIX = 'org.a11y.atspi.'
ROOT = '/org/a11y/atspi/accessible/root'
NULL = '/org/a11y/atspi/null'
LIMIT = 6000


class IncompleteTree(RuntimeError):
    pass


class PublicAtspi:
    # This module-like facade delegates enums, not its identity. Otherwise an
    # AccessibleUI given an existing facade sees gi.repository.Atspi and wraps
    # it again, splitting scoped node identities across two connections.
    __name__ = 'public_atspi'
    read_errors = (IncompleteTree,)

    def __init__(self, native, *, call=None):
        self.native = native
        self._call_override = call
        self._connection = None
        self._registry_owner = None
        self._nodes = WeakValueDictionary()
        self._records = None
        self._children = {}
        self._prepared = None
        self._generation = 0
        self.Action = BusNode
        self.Text = BusNode

    def __getattr__(self, name):
        return getattr(self.native, name)

    def call(self, bus, path, interface, method, signature='', args=()):
        if self._call_override is not None:
            return self._call_override(bus, path, interface, method, signature, args)
        from gi.repository import Gio, GLib
        if self._connection is None:
            # Gio.bus_get_sync caches a process-wide connection even after a
            # preview switches to its private session. Connect explicitly to
            # the caller's current session, never an earlier desktop bus.
            address = os.environ.get('AT_SPI_BUS_ADDRESS')
            if not address:
                session_address = os.environ.get('DBUS_SESSION_BUS_ADDRESS')
                if not session_address:
                    raise ValueError('public-atspi:session-address')
                session = Gio.DBusConnection.new_for_address_sync(
                    session_address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT |
                    Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
                session.set_exit_on_close(False)
                try:
                    address = session.call_sync(
                        'org.a11y.Bus', '/org/a11y/bus', 'org.a11y.Bus', 'GetAddress',
                        None, GLib.VariantType.new('(s)'), Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]
                finally:
                    session.close_sync(None)
            self._connection = Gio.DBusConnection.new_for_address_sync(
                address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT |
                Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
            self._connection.set_exit_on_close(False)
        try:
            value = self._connection.call_sync(
                bus, path, interface, method,
                GLib.Variant('(' + signature + ')', args) if signature else None,
                None, Gio.DBusCallFlags.NONE, 2000, None).unpack()
        except GLib.Error as error:
            # Preserve the error type for unsupported-interface fallback and
            # transient read retries. Only fixed query names enter diagnostics.
            error.add_note('public-atspi-query:' + interface + ':' + method +
                           (':' + args[1] if method == 'Get' else '') +
                           (':root' if path == ROOT else ':object'))
            raise
        return value[0] if len(value) == 1 else value

    def reset(self):
        self._nodes.clear()
        self._registry_owner = None
        self.invalidate_snapshot()
        if self._connection is not None:
            self._connection.close_sync(None)
            self._connection = None

    def invalidate_snapshot(self):
        self._generation += 1
        self._records = None
        self._children.clear()
        self._prepared = None

    def reference(self, reference):
        bus, path = reference
        if path == NULL:
            return ('', NULL)
        # Embedded WebKit roots advertise a well-known bus name while their
        # cache and descendants use its unique owner. Pin each reference to
        # that owner, never retain an alias that can move to another process.
        if bus != 'org.a11y.atspi.Registry' and not bus.startswith(':'):
            bus = self.call('org.freedesktop.DBus', '/org/freedesktop/DBus',
                            'org.freedesktop.DBus', 'GetNameOwner', 's', (bus,))
        if bus == self._registry_owner:
            bus = 'org.a11y.atspi.Registry'
        return bus, path

    def node(self, reference):
        key = bus, path = self.reference(reference)
        if path == NULL:
            return None
        node = self._nodes.get(key)
        if node is None:
            node = BusNode(self, bus, path)
            self._nodes[key] = node
        return node

    def get_desktop(self, index):
        if index != 0:
            raise ValueError('public-atspi:desktop')
        if self._registry_owner is None:
            self._registry_owner = self.call(
                'org.freedesktop.DBus', '/org/freedesktop/DBus',
                'org.freedesktop.DBus', 'GetNameOwner', 's', ('org.a11y.atspi.Registry',))
        return self.node(('org.a11y.atspi.Registry', ROOT))

    @contextmanager
    def snapshot(self):
        previous = self._records, self._children, self._prepared
        generation = self._generation
        self._records = {}
        self._children = {}
        self._prepared = {}
        try:
            yield
        finally:
            if generation == self._generation:
                self._records, self._children, self._prepared = previous
            else:
                self._records, self._children, self._prepared = None, {}, None

    def read_many(self, queries):
        """Pipeline at most 64 read-only RPCs, draining every reply before return.

        A private main context avoids dispatching application callbacks (and
        hence input) during a traversal. Errors remain attached to their query;
        consuming an incomplete node still fails through the normal reader.
        """
        if len(queries) > 64:
            raise ValueError('public-atspi:batch-bound')
        if self._call_override is not None:
            results = []
            for query in queries:
                try:
                    results.append(self.call(*query))
                except Exception as error:
                    results.append(error)
            return results
        from gi.repository import Gio, GLib
        # prepare_nodes has already obtained fresh bulk records, establishing
        # this instance's connection through the ordinary scoped route.
        context = GLib.MainContext.new()
        results = [None] * len(queries)
        remaining = len(queries)

        def finished(connection, result, index):
            nonlocal remaining
            try:
                value = connection.call_finish(result).unpack()
                results[index] = value[0] if len(value) == 1 else value
            except Exception as error:
                results[index] = error
            finally:
                remaining -= 1

        context.push_thread_default()
        try:
            for index, (bus, path, interface, method, signature, args) in enumerate(queries):
                try:
                    self._connection.call(
                        bus, path, interface, method,
                        GLib.Variant('(' + signature + ')', args) if signature else None,
                        None, Gio.DBusCallFlags.NONE, 2000, None, finished, index)
                except Exception as error:
                    results[index] = error
                    remaining -= 1
            while remaining:
                context.iteration(True)
        finally:
            context.pop_thread_default()
        return results

    def prepare_nodes(self, nodes, *, descend=None):
        """Read identities of already discovered siblings in bounded batches.

        Never enumerate speculative descendants or read text. The traversal
        still decides whether each node may expose children after resolving its
        role and protected identity. Values exist only inside this snapshot;
        input guards outside it continue querying the provider directly.
        """
        if self._prepared is None:
            return
        nodes = list(dict.fromkeys(node for node in nodes if node is not None))[:32]
        queries, keys = [], []
        for node in nodes:
            key = (node.bus, node.path)
            if key in self._prepared or node.bus == 'org.a11y.atspi.Registry':
                continue
            self.record(node)
            keys.append(key)
            queries.extend([
                (node.bus, node.path, PREFIX + 'Accessible', 'GetAttributes', '', ()),
                (node.bus, node.path, 'org.freedesktop.DBus.Properties', 'Get',
                 'ss', (PREFIX + 'Accessible', 'AccessibleId')),
            ])
        values = self.read_many(queries) if queries else []
        for index, key in enumerate(keys):
            self._prepared[key] = values[index * 2:index * 2 + 2]
        if descend is None:
            return
        queries, targets = [], []
        for node in nodes:
            key = (node.bus, node.path)
            if key in self._children or node.bus == 'org.a11y.atspi.Registry':
                continue
            if not descend(node):
                continue
            targets.append(node)
            queries.extend([
                (node.bus, node.path, 'org.freedesktop.DBus.Properties', 'Get',
                 'ss', (PREFIX + 'Accessible', 'ChildCount')),
                (node.bus, node.path, PREFIX + 'Accessible', 'GetChildren', '', ()),
            ])
        values = self.read_many(queries) if queries else []
        for index, node in enumerate(targets):
            count, children = values[index * 2:index * 2 + 2]
            if isinstance(count, Exception):
                raise count
            if isinstance(children, Exception):
                raise children
            self._children[(node.bus, node.path)] = node.validate_children(count, children)

    def prepared(self, node, index, fallback):
        values = (self._prepared or {}).get((node.bus, node.path))
        if values is None:
            return fallback()
        if index == len(values):
            values.append(fallback())
        value = values[index]
        if isinstance(value, Exception):
            raise value
        return value

    def prepare_tree(self, root, *, descend, checkpoint=None):
        """Discover breadth first so separate branches can share an RPC batch.

        Consumers still iterate in their original order. Every edge is counted
        and validated before its children join the next frontier, and traversal
        exclusions are applied before issuing any child query.
        """
        pending, seen = [root], set()
        discovered = 1
        while pending:
            following = []
            for offset in range(0, len(pending), 32):
                if checkpoint is not None:
                    checkpoint()
                batch = []
                for node in pending[offset:offset + 32]:
                    if node is None:
                        raise IncompleteTree('public-atspi:incomplete-tree')
                    if node not in seen:
                        seen.add(node)
                        batch.append(node)
                if len(seen) > LIMIT:
                    raise ValueError('public-atspi:tree-bound')
                self.prepare_nodes(batch, descend=descend)
                for node in batch:
                    if descend(node):
                        children = node.children()
                        discovered += len(children)
                        if discovered > LIMIT:
                            raise ValueError('public-atspi:tree-bound')
                        following.extend(self.node(ref) for ref in children)
            pending = following

    def record(self, node):
        if self._records is None or node.bus == 'org.a11y.atspi.Registry':
            return None
        if node.bus not in self._records:
            # Unsupported caches use the same fresh per-node public queries.
            try:
                items = self.call(node.bus, '/org/a11y/atspi/cache', PREFIX + 'Cache', 'GetItems')
            except Exception as error:
                from gi.repository import Gio, GLib
                if not isinstance(error, GLib.Error) or Gio.DBusError.get_remote_error(error) not in (
                        'org.freedesktop.DBus.Error.UnknownMethod',
                        'org.freedesktop.DBus.Error.UnknownInterface',
                        'org.freedesktop.DBus.Error.UnknownObject'):
                    raise
                items = []
            records = {}
            indices = {}
            embedded_application = None
            if len(items) > LIMIT:
                raise ValueError('public-atspi:tree-bound')
            for item in items:
                if len(item) != 10:
                    # The legacy signature lacks child counts. Read live.
                    records = {}
                    indices = {}
                    break
                ref, app, parent, index, count, interfaces, name, role, description, states = item
                ref, app, parent = map(self.reference, (ref, app, parent))
                if ref[0] != node.bus:
                    raise ValueError('public-atspi:cache-owner:object')
                if app != (node.bus, ROOT):
                    # A WebKit process belongs to the embedding GTK app. Bulk
                    # data cannot establish this cross-process ownership;
                    # independently confirm its public application reference.
                    if embedded_application is None:
                        embedded_application = self.reference(
                            node.call('Accessible', 'GetApplication'))
                    if app[1] == NULL or app != embedded_application:
                        raise ValueError('public-atspi:cache-owner:application')
                if ref in records:
                    raise ValueError('public-atspi:cache-owner:duplicate')
                records[ref] = (count, name, role, states)
                indices.setdefault(parent, {}).setdefault(index, []).append(ref)
            for ref, (count, _name, _role, _states) in records.items():
                # GetItems can retain a hidden object at the same index as an
                # as-yet-unrealized replacement. Even contiguous, unique slots
                # matching ChildCount therefore do not prove the current edges.
                # Enumerate non-leaves live. Bulk zero counts can establish
                # leaves only without contradictory cached child records;
                # GTK's application root count is always read live as well.
                if ref[1] != ROOT and count == 0 and not indices.get(ref):
                    self._children[ref] = ()
            self._records[node.bus] = records
        return self._records[node.bus].get((node.bus, node.path))


class BusNode:
    def __init__(self, api, bus, path):
        self.api, self.bus, self.path = api, bus, path

    def call(self, interface, method, signature='', args=()):
        return self.api.call(self.bus, self.path, PREFIX + interface, method, signature, args)

    def property(self, name, interface='Accessible'):
        return self.api.call(self.bus, self.path, 'org.freedesktop.DBus.Properties',
                             'Get', 'ss', (PREFIX + interface, name))

    def clear_cache_single(self):
        # There is no event cache. Bulk records are owned by snapshot(), and
        # normal state, identity and interface reads always go to the provider.
        pass

    def get_attributes(self):
        return self.api.prepared(self, 0, lambda: self.call('Accessible', 'GetAttributes'))

    def get_accessible_id(self):
        if self.bus == 'org.a11y.atspi.Registry' and self.path == ROOT:
            # libatspi's synthetic desktop has no application/control ID;
            # the registry does not implement the AccessibleId property.
            return ''
        return self.api.prepared(self, 1, lambda: self.property('AccessibleId'))

    def get_name(self):
        record = self.api.record(self)
        return record[1] if record is not None else self.property('Name')

    def get_description(self):
        return self.property('Description')

    def get_role_name(self):
        record = self.api.record(self)
        role = (record[2] if record is not None else
                self.api.prepared(self, 2, lambda: self.call('Accessible', 'GetRole')))
        if role != int(self.api.Role.EXTENDED):
            return self.api.role_get_name(role)
        return self.call('Accessible', 'GetRoleName')

    def get_state_set(self):
        return self.states(self.call('Accessible', 'GetState'))

    @staticmethod
    def states(words):
        if len(words) != 2:
            raise IncompleteTree('public-atspi:incomplete-state')
        bits = sum(int(word) << (32 * index) for index, word in enumerate(words))
        return SimpleNamespace(contains=lambda state: bool(bits & (1 << int(state))))

    def snapshot_state_set(self):
        # Only the traversal asks for bulk facts. Even if a caller pauses its
        # node iterator, public input guards still use get_state_set() above.
        record = self.api.record(self)
        words = record[3] if record is not None else self.call('Accessible', 'GetState')
        return self.states(words)

    def children(self):
        self.api.record(self)
        key = (self.bus, self.path)
        if key in self.api._children:
            return self.api._children[key]
        count = self.property('ChildCount')
        children = self.validate_children(count, self.call('Accessible', 'GetChildren'))
        if self.api._records is not None:
            self.api._children[key] = children
        return children

    def validate_children(self, count, children):
        if not 0 <= count <= LIMIT:
            raise IncompleteTree('public-atspi:incomplete-tree')
        if len(children) != count or any(ref[1] == NULL for ref in children):
            raise IncompleteTree('public-atspi:incomplete-tree')
        children = tuple(self.api.reference(ref) for ref in children)
        if len(set(children)) != len(children):
            raise IncompleteTree('public-atspi:incomplete-tree')
        return children

    def get_child_count(self):
        return len(self.children())

    def get_child_at_index(self, index):
        return self.api.node(self.children()[index])

    def get_parent(self):
        return self.api.node(self.property('Parent'))

    def get_application(self):
        return self.api.node(self.call('Accessible', 'GetApplication'))

    def get_process_id(self):
        return self.api.call('org.freedesktop.DBus', '/org/freedesktop/DBus',
                             'org.freedesktop.DBus', 'GetConnectionUnixProcessID', 's', (self.bus,))

    def get_relation_set(self):
        return [SimpleNamespace(get_relation_type=lambda kind=kind: kind,
                                get_n_targets=lambda refs=refs: len(refs),
                                get_target=lambda index, refs=refs: self.api.node(refs[index]))
                for kind, refs in self.call('Accessible', 'GetRelationSet')]

    def interface(self, name):
        return self if PREFIX + name in self.call('Accessible', 'GetInterfaces') else None

    def get_action_iface(self):
        return self.interface('Action')

    def get_text_iface(self):
        return self.interface('Text')

    def get_component_iface(self):
        return self.interface('Component')

    def get_n_actions(self):
        return self.property('NActions', 'Action')

    def get_action_name(self, index):
        return self.call('Action', 'GetName', 'i', (index,))

    def do_action(self, index):
        return self.call('Action', 'DoAction', 'i', (index,))

    def get_character_count(self):
        return self.property('CharacterCount', 'Text')

    def get_text(self, start, end):
        return self.call('Text', 'GetText', 'ii', (start, end))

    def get_attribute_run(self, offset, defaults):
        return self.call('Text', 'GetAttributeRun', 'ib', (offset, defaults))

    def grab_focus(self):
        return self.call('Component', 'GrabFocus')

    def scroll_to(self, kind):
        return self.call('Component', 'ScrollTo', 'u', (int(kind),))
