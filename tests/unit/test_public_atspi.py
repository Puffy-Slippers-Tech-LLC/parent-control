"""Fresh public bulk traversal and uncached input guards; no real bus or files."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.e2e.public_atspi import PublicAtspi, IncompleteTree, PREFIX, ROOT, NULL


@pytest.mark.parametrize('fault', ['', 'sender', 'path', 'signature', 'large', 'value',
                                  'register', 'cancel'])
def test_checked_event_subscription_is_scoped_bounded_and_owned(fault):
    # Pure mocked connection and local GVariant/context; no bus connection,
    # threads, processes or shared resources. Existing unit scheduling applies.
    from gi.repository import GLib
    api, _, rpc, _, node = fixture_bus()
    connection = Mock()
    api._connection = connection
    connection.signal_subscribe.return_value = 7
    events = []
    rpc.side_effect = RuntimeError('registration failed') if fault == 'register' else None
    try:
        with api.checked_events(node, lambda value, error: events.append((value, error))):
            callback = connection.signal_subscribe.call_args.args[-1]
            value = GLib.Variant('(siiva{sv})', ('checked', 2 if fault == 'value' else 1,
                       0, GLib.Variant('s', 'x' * 5000 if fault == 'large' else ''), {}))
            if fault == 'signature': value = GLib.Variant('(s)', ('checked',))
            callback(connection, ':1.999' if fault == 'sender' else node.bus,
                     '/foreign' if fault == 'path' else node.path,
                     PREFIX + 'Event.Object', 'StateChanged', value)
            if fault == 'cancel': raise KeyboardInterrupt()
    except (RuntimeError, KeyboardInterrupt):
        assert fault in ('register', 'cancel')
    connection.signal_unsubscribe.assert_called_once_with(7)
    if fault != 'register':
        assert rpc.call_args.args[3:] == ('DeregisterEvent', 'ss',
                                         ('object:state-changed:checked', node.bus))
        if fault in ('', 'cancel'):
            assert events == [(True, None)]
        else:
            assert events[0][0] is None and isinstance(events[0][1], ValueError)


def test_multi_state_subscription_pins_every_endpoint_and_cleans_up():
    from gi.repository import GLib
    api, _, rpc, _, toggle = fixture_bus()
    rpc.side_effect = None
    api._connection = Mock()
    api._connection.signal_subscribe.side_effect = (7, 8)
    endpoints = {(toggle.bus, toggle.path, 'checked'): 'toggle',
                 (toggle.bus, toggle.path, 'sensitive'): 'toggle'}
    events = []
    with api.state_events(endpoints, lambda *args: events.append(args)):
        callback = api._connection.signal_subscribe.call_args.args[-1]
        signal = GLib.Variant('(siiva{sv})', ('sensitive', 0, 0,
                                             GLib.Variant('s', ''), {}))
        callback(api._connection, toggle.bus, toggle.path,
                 PREFIX + 'Event.Object', 'StateChanged', signal)
        callback(api._connection, ':1.999', toggle.path,
                 PREFIX + 'Event.Object', 'StateChanged', signal)
    assert events[0] == ('toggle', 'sensitive', False, None)
    assert events[1][:3] == (None, None, None)
    assert isinstance(events[1][3], ValueError)
    assert [call.args[3] for call in rpc.call_args_list].count('RegisterEvent') == 2
    assert [call.args[3] for call in rpc.call_args_list].count('DeregisterEvent') == 2
    assert api._connection.signal_unsubscribe.call_count == 2


def test_application_state_subscription_pins_owner_and_cleans_up():
    from gi.repository import GLib
    api, _, rpc, _, _ = fixture_bus()
    rpc.side_effect = None
    api._connection = Mock()
    api._connection.signal_subscribe.side_effect = (7, 8)
    events = []
    with api.application_state_events(':1.10', lambda *args: events.append(args)):
        callback = api._connection.signal_subscribe.call_args.args[-1]
        signal = GLib.Variant('(siiva{sv})', ('visible', 1, 0,
                                             GLib.Variant('s', ''), {}))
        callback(api._connection, ':1.10', '/dynamic',
                 PREFIX + 'Event.Object', 'StateChanged', signal)
        callback(api._connection, ':1.11', '/dynamic',
                 PREFIX + 'Event.Object', 'StateChanged', signal)
    assert events[0] == ('/dynamic', 'visible', True, None)
    assert events[1][:3] == (None, None, None)
    assert isinstance(events[1][3], ValueError)
    assert [call.args[3] for call in rpc.call_args_list].count('RegisterEvent') == 2
    assert [call.args[3] for call in rpc.call_args_list].count('DeregisterEvent') == 2
    assert api._connection.signal_unsubscribe.call_count == 2


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


def test_text_range_cursor_and_selection_reads_are_live_public_calls():
    api, _, rpc, _, node = fixture_bus()
    rpc.side_effect = [0, 1, (0, 9), ({'weight': '700'}, 0, 9), 23]
    assert node.get_caret_offset() == 0
    assert node.get_n_selections() == 1
    selected = node.get_selection(0)
    assert (selected.start_offset, selected.end_offset) == (0, 9)
    assert node.get_attribute_run(0, True) == ({'weight': '700'}, 0, 9)
    assert node.get_caret_offset() == 23
    assert [(call.args[2], call.args[3], call.args[4], call.args[5])
            for call in rpc.call_args_list] == [
        ('org.freedesktop.DBus.Properties', 'Get', 'ss', (PREFIX + 'Text', 'CaretOffset')),
        (PREFIX + 'Text', 'GetNSelections', '', ()),
        (PREFIX + 'Text', 'GetSelection', 'i', (0,)),
        (PREFIX + 'Text', 'GetAttributeRun', 'ib', (0, True)),
        ('org.freedesktop.DBus.Properties', 'Get', 'ss', (PREFIX + 'Text', 'CaretOffset')),
    ]


def test_set_selection_uses_public_text_interface_once():
    api, _, rpc, _, node = fixture_bus()
    rpc.side_effect = None
    rpc.return_value = True
    assert node.set_selection(0, 0, 149) is True
    rpc.assert_called_once_with(node.bus, node.path, PREFIX + 'Text', 'SetSelection',
                                'iii', (0, 0, 149))


def test_hyperlink_reads_use_public_interface_without_activation():
    _, _, rpc, _, node = fixture_bus()
    rpc.side_effect = [[PREFIX + 'Hyperlink'], 1, 0, 1, True, 'https://example.com/feedback']
    assert node.get_hyperlink() is node
    assert node.get_n_anchors() == 1
    assert node.get_start_index() == 0
    assert node.get_end_index() == 1
    assert node.is_valid() is True
    assert node.get_uri(0) == 'https://example.com/feedback'
    assert [(call.args[2], call.args[3], call.args[4], call.args[5])
            for call in rpc.call_args_list] == [
        (PREFIX + 'Accessible', 'GetInterfaces', '', ()),
        ('org.freedesktop.DBus.Properties', 'Get', 'ss', (PREFIX + 'Hyperlink', 'NAnchors')),
        ('org.freedesktop.DBus.Properties', 'Get', 'ss', (PREFIX + 'Hyperlink', 'StartIndex')),
        ('org.freedesktop.DBus.Properties', 'Get', 'ss', (PREFIX + 'Hyperlink', 'EndIndex')),
        (PREFIX + 'Hyperlink', 'IsValid', '', ()),
        (PREFIX + 'Hyperlink', 'GetURI', 'i', (0,)),
    ]


def test_link_attributes_are_read_in_link_local_text_coordinates():
    _, _, rpc, _, node = fixture_bus()
    attrs = {'weight': '700', 'style': 'italic', 'underline': 'single', 'strikethrough': 'true'}
    rpc.side_effect = [[PREFIX + 'Text'], 5, 'Plain', (attrs, 0, 5)]
    text = node.get_text_iface()
    assert text.get_character_count() == 5
    assert text.get_text(0, 5) == 'Plain'
    assert text.get_attribute_run(2, True) == (attrs, 0, 5)
    assert [(call.args[3], call.args[4], call.args[5]) for call in rpc.call_args_list] == [
        ('GetInterfaces', '', ()), ('Get', 'ss', (PREFIX + 'Text', 'CharacterCount')),
        ('GetText', 'ii', (0, 5)), ('GetAttributeRun', 'ib', (2, True))]


def test_file_selection_uses_public_interface_and_returns_owned_reference():
    api, _, rpc, _, node = fixture_bus()
    rpc.side_effect = [[PREFIX + 'Selection'], 1, (node.bus, node.path), True]
    assert node.get_selection_iface() is node
    assert api.Selection.get_n_selected_children(node) == 1
    assert api.Selection.get_selected_child(node, 0) is node
    assert api.Selection.select_child(node, 1) is True
    assert [(call.args[3], call.args[4], call.args[5]) for call in rpc.call_args_list] == [
        ('GetInterfaces', '', ()), ('Get', 'ss', (PREFIX + 'Selection', 'NSelectedChildren')),
        ('GetSelectedChild', 'i', (0,)), ('SelectChild', 'i', (1,))]


def test_chooser_preparation_uses_public_editable_text_and_select_all():
    api, _, rpc, _, node = fixture_bus()
    rpc.side_effect = [[PREFIX + 'EditableText'], True, True]
    assert node.get_editable_text_iface() is node
    assert api.EditableText.set_text_contents(node, '/synthetic files/') is True
    assert api.Selection.select_all(node) is True
    assert [(call.args[2], call.args[3], call.args[4], call.args[5])
            for call in rpc.call_args_list] == [
        (PREFIX + 'Accessible', 'GetInterfaces', '', ()),
        (PREFIX + 'EditableText', 'SetTextContents', 's', ('/synthetic files/',)),
        (PREFIX + 'Selection', 'SelectAll', '', ()),
    ]


def test_scalar_character_read_does_not_use_nul_forbidden_dbus_strings():
    _, _, rpc, _, node = fixture_bus()
    rpc.side_effect = [97, 0, 98]
    assert [node.get_character_at_offset(offset) for offset in range(3)] == [97, 0, 98]
    assert [(call.args[3], call.args[4], call.args[5]) for call in rpc.call_args_list] == [
        ('GetCharacterAtOffset', 'i', (offset,)) for offset in range(3)]


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


def test_async_batch_drains_ready_replies_without_poll_sleeps(monkeypatch):
    from gi.repository import GLib
    from tests.e2e import public_atspi
    api = PublicAtspi(SimpleNamespace())
    callbacks = []
    def schedule(index):
        context, callback = callbacks[index]
        source = GLib.idle_source_new()
        def complete(*_):
            callback(api._connection, index, index)
            return False
        source.set_callback(complete)
        source.attach(context)

    class Connection:
        def call(self, bus, path, interface, method, parameters, reply_type,
                 flags, timeout, cancellable, callback, index):
            callbacks.append((GLib.MainContext.get_thread_default(), callback))
            if index == 0:
                schedule(0)

        def call_finish(self, index):
            assert len(callbacks) == 3
            if index < 2:
                schedule(index + 1)
            return GLib.Variant('(s)', (str(index),))

    api._connection = Connection()
    sleep = Mock(side_effect=AssertionError('slept with a reply already ready'))
    monkeypatch.setattr(public_atspi.time, 'sleep', sleep)
    assert api.read_many([(':1.1', '/node', PREFIX + 'Accessible',
                           'GetAttributes', '', ())] * 3) == ['0', '1', '2']
    sleep.assert_not_called()


def test_identity_and_name_pipeline_keeps_rpc_bound_and_alignment():
    api, items, rpc, app, _button = fixture_bus()
    original = rpc.side_effect
    def call(*args):
        if args[3] == 'GetAttributes':
            return {'id': args[1]}
        if args[3] == 'Get' and args[5][1] == 'AccessibleId':
            return 'id:' + args[1]
        if args[3] == 'Get' and args[5][1] == 'Name':
            return 'name:' + args[1]
        if args[3] == 'GetRole':
            return 1 if int(args[1].removeprefix('/leaf')) % 2 else 2
        if args[3] == 'GetState':
            return [1 << 24, 1 << int(args[1].removeprefix('/leaf'))]
        return original(*args)
    rpc.side_effect = call
    api.read_many = Mock(wraps=api.read_many)
    nodes = [api.node((':1.10', f'/leaf{index}')) for index in range(32)]
    # Mixed cache coverage gives different query strides. A batch boundary can
    # split one node's replies; no role, name or state may shift to its sibling.
    for index, node in enumerate(nodes):
        if index % 2:
            continue
        items.append([(node.bus, node.path), (app.bus, ROOT), (app.bus, ROOT),
                      -1, 0, [], 'cached name', 2, '', [1 << 24, 1 << index]])
    with api.snapshot():
        api.prepare_nodes(nodes, names=True)
        assert [len(c.args[0]) for c in api.read_many.call_args_list] == [64, 64]
        queries = [query for batch in api.read_many.call_args_list for query in batch.args[0]]
        assert sum(query[3] == 'GetRole' for query in queries) == 16
        assert sum(query[3] == 'GetState' for query in queries) == 16
        before = rpc.call_count
        for index, node in enumerate(nodes):
            assert node.get_attributes() == {'id': node.path}
            assert node.get_accessible_id() == 'id:' + node.path
            assert node.snapshot_name() == 'name:' + node.path
            assert node.get_role_name() == ('application' if index % 2 else 'push button')
            states = node.snapshot_state_set()
            assert states.contains(24)
            assert states.contains(32 + index)
            assert not states.contains(32 + (index + 1) % 32)
        assert rpc.call_count == before


@pytest.mark.parametrize('fault', ['', 'role', 'state', 'state-shape'])
def test_missing_cache_facts_share_pipeline_but_never_supply_input_state(fault):
    api, items, rpc, _app, button = fixture_bus()
    items.pop()  # The live button has no provider cache entry.
    current = [1 << 24, 0]
    original = rpc.side_effect

    def call(*args):
        if args[3] == 'GetAttributes':
            return {'toolkit': 'gtk'}
        if args[3] == 'Get' and args[5][1] == 'AccessibleId':
            return 'button'
        if args[3] == 'GetRole':
            if fault == 'role':
                raise IncompleteTree('role unavailable')
            return 2
        if args[3] == 'GetState':
            if fault == 'state':
                raise IncompleteTree('state unavailable')
            return [0] if fault == 'state-shape' else list(current)
        return original(*args)

    rpc.side_effect = call
    api.read_many = Mock(wraps=api.read_many)
    with api.snapshot():
        api.prepare_nodes([button], names=True)
        assert len(api.read_many.call_args_list) == 1
        before = rpc.call_count
        if fault == 'role':
            with pytest.raises(IncompleteTree, match='role unavailable'):
                button.get_role_name()
        else:
            assert button.get_role_name() == 'push button'
        if fault in ('state', 'state-shape'):
            with pytest.raises(IncompleteTree, match='state unavailable|incomplete-state'):
                button.snapshot_state_set()
        else:
            assert button.snapshot_state_set().contains(24)
        assert rpc.call_count == before
        if not fault:
            current[:] = [0, 0]
            assert not button.get_state_set().contains(24)
            assert button.snapshot_state_set().contains(24)
            outer = api._states
            with api.snapshot():
                api.prepare_nodes([button], names=True)
                assert not button.snapshot_state_set().contains(24)
            assert api._states is outer
            assert button.snapshot_state_set().contains(24)
            with api.snapshot():
                api.invalidate_snapshot()
            assert api._states is None
            assert not button.snapshot_state_set().contains(24)
    assert api._states is None
    if not fault:
        assert not button.snapshot_state_set().contains(24)


@pytest.mark.parametrize('missing_cache', [False, True])
def test_breadth_batches_preserve_traversal_order_and_never_query_protected_children(missing_cache):
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
    if missing_cache:
        items.clear()
    def call(bus, path, interface, method, signature, args):
        if method == 'GetItems':
            return items
        if method == 'GetAttributes':
            return {'toolkit': 'gtk'}
        if method == 'GetRole':
            return 1 if path == ROOT else 2
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


def test_bulk_structure_is_scoped_but_result_names_and_action_states_are_live():
    api, items, rpc, app, button = fixture_bus()
    with api.snapshot():
        assert button.snapshot_state_set().contains(24)
        assert not button.get_state_set().contains(24)
        assert button.get_name() == 'Live'
        assert app.get_child_count() == 1  # GTK's bulk root count is zero.
        assert app.get_child_at_index(0) is button
        assert button.get_child_count() == 0
        assert button.get_role_name() == 'push button'
    assert not button.get_state_set().contains(24)
    assert button.get_name() == 'Live'
    items[1][6] = 'Changed'
    with api.snapshot():
        assert button.get_name() == 'Live'
    assert sum(call.args[3] == 'GetItems' for call in rpc.call_args_list) == 2


@pytest.mark.parametrize('fault', [False, True])
def test_snapshot_names_pipeline_live_queries_but_never_cache_public_results(fault):
    api, items, rpc, app, button = fixture_bus()
    current = ['fresh name']
    original = rpc.side_effect
    def call(*args):
        if args[3] == 'GetAttributes':
            return {'toolkit': 'gtk'}
        if args[3] == 'Get' and args[5][1] == 'AccessibleId':
            return args[1]
        if args[3] == 'Get' and args[5][1] == 'Name':
            if fault:
                raise IncompleteTree('name unavailable')
            return current[0]
        return original(*args)
    rpc.side_effect = call
    api.read_many = Mock(wraps=api.read_many)
    with api.snapshot():
        api.prepare_tree(app, descend=lambda _: True, names=True)
        before = rpc.call_count
        if fault:
            with pytest.raises(IncompleteTree, match='name unavailable'):
                button.snapshot_name()
        else:
            assert button.snapshot_name() == 'fresh name'
            assert rpc.call_count == before  # no serialized per-node Name RPC
            current[0] = 'changed result'
            assert button.get_name() == 'changed result'
            assert button.snapshot_name() == 'fresh name'
            api.invalidate_snapshot()
            assert button.snapshot_name() == 'changed result'
    assert all(len(c.args[0]) <= 32 for c in api.read_many.call_args_list)
    assert any(q[3:] == ('Get', 'ss', (PREFIX + 'Accessible', 'Name'))
               for c in api.read_many.call_args_list for q in c.args[0])
    if not fault:
        assert button.snapshot_name() == 'changed result'
        with api.snapshot():
            api.prepare_tree(app, descend=lambda _: True, names=True)
            assert button.snapshot_name() == 'changed result'


def test_batched_names_never_read_protected_descendants_or_survive_nested_invalidation():
    api, _items, rpc, app, button = fixture_bus()
    original = rpc.side_effect
    def call(*args):
        if args[3] == 'GetAttributes':
            return {'toolkit': 'gtk'}
        if args[3] == 'Get' and args[5][1] == 'AccessibleId':
            return args[1]
        return original(*args)
    rpc.side_effect = call
    with api.snapshot():
        api.prepare_tree(app, descend=lambda _: False, names=True)
        assert not any(c.args[1] == button.path for c in rpc.call_args_list)
        outer = api._names
        with api.snapshot():
            api.prepare_tree(button, descend=lambda _: False, names=True)
            assert api._names is not outer
        assert api._names is outer
        with api.snapshot():
            api.invalidate_snapshot()
        assert api._names is None
    assert api._names is None


@pytest.mark.parametrize('fault', ['lost-callback', 'callback-interrupt'])
def test_async_batch_cannot_lose_cancellation_or_wait_forever(monkeypatch, fault):
    # Private GLib context and connection double; no real bus, display or
    # subprocess. The deadline is advanced locally rather than sleeping.
    from gi.repository import GLib
    from tests.e2e import public_atspi
    api = PublicAtspi(SimpleNamespace())
    cancelled = []

    class Connection:
        def call(self, bus, path, interface, method, parameters, reply_type,
                 flags, timeout, cancellable, callback, index):
            cancelled.append(cancellable)
            if fault == 'callback-interrupt':
                source = GLib.idle_source_new()
                source.set_callback(lambda *_: callback(self, index, index) or False)
                source.attach(GLib.MainContext.get_thread_default())

        def call_finish(self, result):
            raise KeyboardInterrupt('interrupt inside GI callback')

    api._connection = Connection()
    previous = GLib.MainContext.get_thread_default()
    now = iter([0, 1, 4])
    monkeypatch.setattr(public_atspi.time, 'monotonic', lambda: next(now))
    expected = KeyboardInterrupt if fault == 'callback-interrupt' else IncompleteTree
    with pytest.raises(expected, match='interrupt inside|batch-timeout'):
        api.read_many([(':1.1', '/node', PREFIX + 'Accessible', 'GetAttributes', '', ())])
    assert GLib.MainContext.get_thread_default() == previous
    assert cancelled[0].is_cancelled()


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


@pytest.mark.parametrize('cached_child', [False, True])
def test_matching_bulk_slots_cannot_hide_a_lazy_replacement_child(cached_child):
    api, items, rpc, _app, button = fixture_bus()
    old = (button.bus, '/old-child')
    new = (button.bus, '/replacement')
    items[1][4] = int(cached_child)
    # GTK can retain the now-hidden child at index zero while the replacement
    # has no cache record yet. Its cached states need not expose that hiding.
    if cached_child:
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
        assert button.get_name() == 'Live'
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
            assert button.get_name() == 'Live'
        assert (api._records, api._children) == outer
        with api.snapshot():
            assert button.get_name() == 'Live'
            api.invalidate_snapshot()
            assert button.get_name() == 'Live'
        assert button.get_name() == 'Live'
    items[1][6] = 'Changed'
    with api.snapshot():
        assert button.get_name() == 'Live'


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
