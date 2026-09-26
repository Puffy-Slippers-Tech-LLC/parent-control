"""Fresh public bulk traversal and uncached input guards; no real bus or files."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.e2e.public_atspi import PublicAtspi, IncompleteTree, PREFIX, ROOT, NULL


def fixture_bus():
    native = SimpleNamespace(Role=SimpleNamespace(EXTENDED=99),
                             role_get_name=lambda role: {1: 'application', 2: 'push button'}[role])
    app = (':1.10', ROOT)
    button = (':1.10', '/button')
    items = [[app, app, ('', NULL), -1, 0, [], 'App', 1, '', [0, 0]],
             [button, app, app, 0, 0, [], 'Button', 2, '', [1 << 24, 0]]]

    def call(bus, path, interface, method, signature, args):
        if method == 'GetItems':
            return items
        if method == 'GetChildren':
            return [button] if path == ROOT else []
        if method == 'GetState':
            return [0, 0]
        if method == 'GetApplication':
            return app
        if method == 'Get':
            return {'Name': 'Live', 'ChildCount': 1 if path == ROOT else 0}[args[1]]
        raise AssertionError((interface, method, args))

    rpc = Mock(side_effect=call)
    api = PublicAtspi(native, call=rpc)
    return api, items, rpc, api.node(app), api.node(button)


def test_shared_reader_facade_is_not_wrapped_again():
    from tests.e2e.accessible_ui import AccessibleUI

    native = SimpleNamespace(__name__='gi.repository.Atspi')
    api = PublicAtspi(native)
    reader = AccessibleUI(api)
    assert reader.api is api
    node = api.node((':1.10', '/scope'))
    assert reader.api.node((':1.10', '/scope')) is node


def test_batched_identities_are_scoped_and_do_not_enumerate_descendants():
    api, _items, rpc, _app, button = fixture_bus()
    original = rpc.side_effect
    def call(*args):
        if args[3] == 'GetAttributes':
            return {'toolkit': 'gtk'}
        if args[3] == 'Get' and args[5][1] == 'AccessibleId':
            return 'field'
        return original(*args)
    rpc.side_effect = call
    with api.snapshot():
        api.prepare_nodes([button, button])
        api.prepare_nodes([button])
        assert button.get_attributes() == {'toolkit': 'gtk'}
        assert button.get_accessible_id() == 'field'
        assert sum(c.args[3] == 'GetAttributes' for c in rpc.call_args_list) == 1
        assert not any(c.args[3] == 'GetChildren' for c in rpc.call_args_list)
        api.invalidate_snapshot()
        assert button.get_accessible_id() == 'field'
    assert button.get_attributes() == {'toolkit': 'gtk'}
    assert sum(c.args[3] == 'GetAttributes' for c in rpc.call_args_list) == 2
    assert sum(c.args[3] == 'Get' for c in rpc.call_args_list) == 2


def test_batch_failure_is_never_accepted_as_an_identity():
    api, _items, rpc, _app, button = fixture_bus()
    original = rpc.side_effect
    def call(*args):
        if args[3] == 'GetAttributes':
            return {'toolkit': 'WebKitGTK', 'id': 'field'}
        if args[3] == 'Get' and args[5][1] == 'AccessibleId':
            raise IncompleteTree('identity-unavailable')
        return original(*args)
    rpc.side_effect = call
    with api.snapshot():
        api.prepare_nodes([button])
        assert button.get_attributes()['id'] == 'field'
        with pytest.raises(IncompleteTree, match='identity-unavailable'):
            button.get_accessible_id()


@pytest.mark.parametrize('protected', [False, True])
@pytest.mark.parametrize('incomplete', [False, True])
def test_batched_edges_are_live_complete_and_respect_traversal_exclusions(protected, incomplete):
    api, items, rpc, app, button = fixture_bus()
    items[1][4] = 1  # Non-leaf bulk edges cannot be trusted.
    original = rpc.side_effect
    def call(*args):
        if args[3] == 'GetAttributes':
            return {'toolkit': 'gtk'}
        if args[3] == 'Get' and args[5][1] == 'AccessibleId':
            return 'field'
        if incomplete and args[1] == '/button' and args[3] == 'GetChildren':
            return [('', NULL)]
        return original(*args)
    rpc.side_effect = call
    with api.snapshot():
        if incomplete and not protected:
            with pytest.raises(IncompleteTree, match='incomplete-tree'):
                api.prepare_nodes([app, button], descend=lambda node: not protected)
        else:
            api.prepare_nodes([app, button], descend=lambda node: not protected)
            if not protected:
                assert app.get_child_at_index(0) is button
                assert button.get_child_count() == 0
    queried = [c.args[1] for c in rpc.call_args_list if c.args[3] == 'GetChildren']
    assert queried == ([] if protected else [ROOT, '/button'])


def test_async_batch_drains_errors_and_uses_only_its_private_context():
    from gi.repository import GLib
    api = PublicAtspi(SimpleNamespace())
    contexts, issued, completed = [], [], []
    class Connection:
        def call(self, bus, path, interface, method, parameters, reply_type,
                 flags, timeout, cancellable, callback, index):
            assert timeout == 2000
            context = GLib.MainContext.get_thread_default()
            contexts.append(context)
            issued.append(index)
            source = GLib.idle_source_new()
            def deliver(*_args):
                callback(self, index, index)
                return False
            source.set_callback(deliver)
            source.attach(context)

        def call_finish(self, index):
            assert issued == [0, 1, 2]  # all requests precede any reply
            completed.append(index)
            if index == 1:
                raise IncompleteTree('missing')
            return GLib.Variant('(s)', (str(index),))
    api._connection = Connection()
    previous = GLib.MainContext.get_thread_default()
    results = api.read_many([(':1.1', '/node', PREFIX + 'Accessible',
                              'GetAttributes', '', ())] * 3)
    assert results[0] == '0' and results[2] == '2'
    assert isinstance(results[1], IncompleteTree)
    assert completed == [0, 1, 2]
    assert len(set(contexts)) == 1 and contexts[0] != previous
    assert GLib.MainContext.get_thread_default() == previous
    with pytest.raises(ValueError, match='batch-bound'):
        api.read_many([None] * 65)


def test_breadth_batches_preserve_traversal_order_and_never_query_protected_children():
    from tests.e2e.accessible_ui import AccessibleUI

    api, items, rpc, app, _button = fixture_bus()
    edges = {ROOT: ['/button', '/protected', '/sibling'],
             '/button': ['/leaf1'], '/sibling': ['/leaf2'],
             '/protected': ['/secret'], '/leaf1': [], '/leaf2': [], '/secret': []}
    items.clear()
    for path, children in edges.items():
        parent = next((p for p, refs in edges.items() if path in refs), NULL)
        items.append([(app.bus, path), (app.bus, ROOT), (app.bus, parent), 0,
                      len(children), [], '', 1 if path == ROOT else 2, '', [0, 0]])
    def call(bus, path, interface, method, signature, args):
        if method == 'GetItems':
            return items
        if method == 'GetAttributes':
            return {'toolkit': 'gtk'}
        if method == 'GetChildren':
            return [(bus, child) for child in edges[path]]
        if method == 'Get':
            return path.lstrip('/') if args[1] == 'AccessibleId' else len(edges[path])
        raise AssertionError((path, method, args))
    rpc.side_effect = call
    api.read_many = Mock(wraps=api.read_many)
    ui = AccessibleUI(api, root=lambda: app)
    nodes = list(ui.nodes(strict=True, protected_ids=('protected',)))
    assert [node.path for node in nodes] == [
        ROOT, '/button', '/leaf1', '/protected', '/sibling', '/leaf2']
    assert not any(c.args[1] == '/secret' for c in rpc.call_args_list)
    assert not any(c.args[1:4] == ('/protected', PREFIX + 'Accessible', 'GetChildren')
                   for c in rpc.call_args_list)
    identity_batches = [[q[1] for q in c.args[0] if q[3] == 'GetAttributes']
                        for c in api.read_many.call_args_list]
    assert [batch for batch in identity_batches if batch] == [
        [ROOT], ['/button', '/protected', '/sibling'], ['/leaf1', '/leaf2']]


def test_bulk_facts_are_fresh_each_traversal_but_action_states_are_always_live():
    api, items, rpc, app, button = fixture_bus()
    with api.snapshot():
        assert button.snapshot_state_set().contains(24)
        assert not button.get_state_set().contains(24)
        assert button.get_name() == 'Button'
        assert app.get_child_count() == 1  # GTK's bulk root count is zero.
        assert app.get_child_at_index(0) is button
        assert button.get_child_count() == 0
        assert button.get_role_name() == 'push button'
    assert not button.get_state_set().contains(24)
    assert button.get_name() == 'Live'
    items[1][6] = 'Changed'
    with api.snapshot():
        assert button.get_name() == 'Changed'
    assert sum(call.args[3] == 'GetItems' for call in rpc.call_args_list) == 2


@pytest.mark.parametrize('fault', ['missing', 'negative', 'duplicate-index', 'extra'])
def test_incomplete_bulk_edges_fall_back_to_counted_live_children(fault):
    api, items, rpc, app, button = fixture_bus()
    child = (button.bus, '/child')
    items[1][4] = 1
    if fault != 'missing':
        items.append([child, items[0][0], items[1][0],
                      -1 if fault == 'negative' else 0, 0, [], '', 2, '', [0, 0]])
    if fault in ('duplicate-index', 'extra'):
        items.append([(button.bus, '/extra'), items[0][0], items[1][0],
                      0 if fault == 'duplicate-index' else 1, 0, [], '', 2, '', [0, 0]])
    with api.snapshot():
        assert button.get_child_count() == 0
    assert any(call.args[1:4] == ('/button', PREFIX + 'Accessible', 'GetChildren')
               for call in rpc.call_args_list)


def test_matching_bulk_slots_cannot_hide_a_lazy_replacement_child():
    api, items, rpc, _app, button = fixture_bus()
    old = (button.bus, '/old-child')
    new = (button.bus, '/replacement')
    items[1][4] = 1
    # GTK can retain the now-hidden child at index zero while the replacement
    # has no cache record yet. Its cached states need not expose that hiding.
    items.append([old, items[0][0], items[1][0], 0, 0, [], 'Old', 2, '', [0, 0]])
    original = rpc.side_effect
    def call(*args):
        if args[1] == '/button':
            if args[3] == 'GetChildren':
                return [new]
            if args[3] == 'Get' and args[5][1] == 'ChildCount':
                return 1
        return original(*args)
    rpc.side_effect = call
    with api.snapshot():
        assert button.get_child_count() == 1
        assert button.get_child_at_index(0) is api.node(new)
    assert sum(call.args[1:4] == ('/button', PREFIX + 'Accessible', 'GetChildren')
               for call in rpc.call_args_list) == 1


@pytest.mark.parametrize('fault', ['null', 'missing', 'negative', 'bound', 'duplicate'])
def test_incomplete_live_children_never_become_a_snapshot(fault):
    api, _items, rpc, app, _button = fixture_bus()
    original = rpc.side_effect
    def call(*args):
        if args[3] == 'GetChildren':
            if fault == 'duplicate':
                return [(':1.10', '/button')] * 2
            return [('', NULL)] if fault == 'null' else []
        if args[3] == 'Get' and args[5][1] == 'ChildCount':
            return {'negative': -1, 'bound': 6001, 'duplicate': 2}.get(fault, 1)
        return original(*args)
    rpc.side_effect = call
    with pytest.raises(IncompleteTree, match='incomplete-tree'):
        with api.snapshot():
            app.get_child_count()
    assert api._records is None and not api._children


@pytest.mark.parametrize('fault', ['owner', 'object-owner', 'application-path', 'duplicate', 'bound'])
def test_untrusted_bulk_records_are_not_accepted(fault):
    api, items, _rpc, _app, button = fixture_bus()
    if fault == 'owner':
        items[1][1] = (':1.99', ROOT)
    elif fault == 'object-owner':
        items[1][0] = (':1.99', '/button')
    elif fault == 'application-path':
        items[1][1] = (':1.10', '/wrong-root')
    elif fault == 'duplicate':
        items.append(items[1])
    else:
        items.extend([items[1]] * 6000)
    with pytest.raises(ValueError, match='cache-owner|tree-bound'):
        with api.snapshot():
            button.get_name()
    assert api._records is None and not api._children


def test_embedded_alias_is_pinned_to_unique_owner_and_application_is_live():
    api, items, rpc, app, button = fixture_bus()
    embedding = (':1.20', ROOT)
    for item in items:
        item[1] = embedding
    original = rpc.side_effect
    def call(*args):
        if args[3] == 'GetNameOwner':
            return ':1.10'
        if args[3] == 'GetApplication':
            return embedding
        return original(*args)
    rpc.side_effect = call
    assert api.node(('org.example.Embedded', ROOT)) is app
    with api.snapshot():
        assert button.get_name() == 'Button'
        assert app.get_child_at_index(0) is button
    assert sum(call.args[3] == 'GetApplication' for call in rpc.call_args_list) == 1
    # Changing the alias never retargets an already selected wrapper.
    rpc.side_effect = lambda *args: ':1.30' if args[3] == 'GetNameOwner' else call(*args)
    assert api.node(('org.example.Embedded', ROOT)) is not app
    assert app.bus == ':1.10'


def test_live_child_aliases_cannot_conceal_duplicate_objects():
    api, _items, rpc, app, _button = fixture_bus()
    original = rpc.side_effect
    def call(*args):
        if args[3] == 'GetNameOwner':
            return ':1.10'
        if args[3] == 'GetChildren':
            return [(':1.10', '/button'), ('org.example.Embedded', '/button')]
        if args[3] == 'Get' and args[5][1] == 'ChildCount':
            return 2
        return original(*args)
    rpc.side_effect = call
    with pytest.raises(IncompleteTree, match='incomplete-tree'):
        app.get_child_count()


def test_unknown_legacy_bulk_shape_uses_live_properties():
    api, items, _rpc, _app, button = fixture_bus()
    items[0].pop()
    with api.snapshot():
        assert button.get_name() == 'Live'


def test_reset_drops_objects_and_closes_only_its_own_connection():
    api, _items, _rpc, _app, button = fixture_bus()
    connection = Mock()
    api._connection = connection
    api.reset()
    connection.close_sync.assert_called_once_with(None)
    assert api.node((button.bus, button.path)) is not button
    assert api._connection is None


@pytest.mark.parametrize('remote', ['UnknownMethod', 'UnknownInterface', 'UnknownObject', 'NoReply'])
def test_bulk_unsupported_falls_back_but_transport_errors_propagate(remote):
    from gi.repository import Gio, GLib
    api, _items, rpc, _app, button = fixture_bus()
    original = rpc.side_effect
    error = Gio.DBusError.new_for_dbus_error('org.freedesktop.DBus.Error.' + remote, 'test')
    def call(*args):
        if args[3] == 'GetItems':
            raise error
        return original(*args)
    rpc.side_effect = call
    with api.snapshot():
        if remote == 'NoReply':
            with pytest.raises(GLib.Error):
                button.get_name()
        else:
            assert button.get_name() == 'Live'
            assert button.get_child_count() == 0
            assert sum(call.args[3] == 'GetItems' for call in rpc.call_args_list) == 1


def test_nested_snapshots_restore_edges_but_never_restore_invalidated_facts():
    api, items, _rpc, app, button = fixture_bus()
    with api.snapshot():
        assert app.get_child_at_index(0) is button
        outer = api._records, api._children
        with api.snapshot():
            assert button.get_name() == 'Button'
        assert (api._records, api._children) == outer
        with api.snapshot():
            assert button.get_name() == 'Button'
            api.invalidate_snapshot()
            assert button.get_name() == 'Live'
        assert button.get_name() == 'Live'
    items[1][6] = 'Changed'
    with api.snapshot():
        assert button.get_name() == 'Changed'


def test_object_identity_is_stable_while_referenced_without_retaining_dead_nodes():
    import gc
    import weakref
    api, _items, _rpc, _app, _button = fixture_bus()
    node = api.node((':1.10', '/temporary'))
    reference = weakref.ref(node)
    assert api.node((':1.10', '/temporary')) is node
    del node
    gc.collect()
    assert reference() is None


def test_registry_unique_reference_is_the_same_desktop_without_an_id_query():
    api, _items, rpc, _app, _button = fixture_bus()
    rpc.return_value = ':1.99'
    rpc.side_effect = None
    desktop = api.get_desktop(0)
    assert api.node((':1.99', ROOT)) is desktop
    assert desktop.get_accessible_id() == ''
    rpc.assert_called_once_with('org.freedesktop.DBus', '/org/freedesktop/DBus',
                               'org.freedesktop.DBus', 'GetNameOwner', 's',
                               ('org.a11y.atspi.Registry',))


def test_application_root_still_requires_its_public_id_property():
    api, _items, rpc, app, _button = fixture_bus()
    rpc.side_effect = None
    rpc.return_value = 'public-app'
    assert app.get_accessible_id() == 'public-app'
    rpc.assert_called_once_with(app.bus, ROOT, 'org.freedesktop.DBus.Properties',
                               'Get', 'ss', (PREFIX + 'Accessible', 'AccessibleId'))


def test_failed_root_property_query_is_not_treated_as_an_absent_id():
    api, _items, rpc, app, _button = fixture_bus()
    rpc.side_effect = RuntimeError('connection lost')
    with pytest.raises(RuntimeError, match='connection lost'):
        app.get_accessible_id()


def test_connection_uses_current_explicit_session_never_gios_cached_desktop(monkeypatch):
    from gi.repository import Gio, GLib
    monkeypatch.delenv('AT_SPI_BUS_ADDRESS', raising=False)
    sessions, buses = [Mock(), Mock()], [Mock(), Mock()]
    for index in range(2):
        sessions[index].call_sync.return_value = GLib.Variant('(s)', ('unix:path=/a11y-' + str(index),))
        buses[index].call_sync.return_value = GLib.Variant('(s)', ('public-app',))
    connect = Mock(side_effect=[sessions[0], buses[0], sessions[1], buses[1]])
    monkeypatch.setattr(Gio.DBusConnection, 'new_for_address_sync', connect)
    monkeypatch.setattr(Gio, 'bus_get_sync', Mock(side_effect=AssertionError('cached desktop')))
    api = PublicAtspi(SimpleNamespace())
    for index in range(2):
        monkeypatch.setenv('DBUS_SESSION_BUS_ADDRESS', 'unix:path=/session-' + str(index))
        assert api.node((':1.10', ROOT)).get_accessible_id() == 'public-app'
        sessions[index].close_sync.assert_called_once_with(None)
        buses[index].close_sync.assert_not_called()
        api.reset()
        buses[index].close_sync.assert_called_once_with(None)
    assert [call.args[0] for call in connect.call_args_list] == [
        'unix:path=/session-0', 'unix:path=/a11y-0',
        'unix:path=/session-1', 'unix:path=/a11y-1']


def test_dbus_error_type_survives_transport_for_fallback_and_retry():
    from gi.repository import Gio, GLib
    api = PublicAtspi(SimpleNamespace())
    error = Gio.DBusError.new_for_dbus_error('org.freedesktop.DBus.Error.UnknownMethod', 'test')
    api._connection = Mock()
    api._connection.call_sync.side_effect = error
    with pytest.raises(GLib.Error) as caught:
        api.call(':1.10', '/org/a11y/atspi/cache', PREFIX + 'Cache', 'GetItems')
    assert caught.value is error
    assert error.__notes__ == ['public-atspi-query:org.a11y.atspi.Cache:GetItems:object']


def test_explicit_accessibility_bus_wins_over_session_discovery(monkeypatch):
    from gi.repository import Gio, GLib
    monkeypatch.setenv('AT_SPI_BUS_ADDRESS', 'unix:path=/private-a11y')
    monkeypatch.setenv('DBUS_SESSION_BUS_ADDRESS', 'unix:path=/different-session')
    connection = Mock()
    connection.call_sync.return_value = GLib.Variant('(s)', ('public-app',))
    connect = Mock(return_value=connection)
    monkeypatch.setattr(Gio.DBusConnection, 'new_for_address_sync', connect)
    api = PublicAtspi(SimpleNamespace())
    assert api.node((':1.10', ROOT)).get_accessible_id() == 'public-app'
    assert connect.call_count == 1
    assert connect.call_args.args[0] == 'unix:path=/private-a11y'
    assert connection.call_sync.call_args.args[3] == 'Get'
