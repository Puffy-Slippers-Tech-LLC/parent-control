"""Public API projection guards, using private in-memory client doubles."""

from copy import deepcopy
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.support.application_ui import ApplicationUI, UIClientError, utf16_index


class Client:
    application_id = 'com.puffyslippers.OhNoParentControl.Parent'
    owner = ':1.42'
    object_path = '/com/puffyslippers/OhNoParentControl/Parent'
    pid = 4242

    def __init__(self):
        self.calls = []
        self.failure = None
        self.elements = {
            'parent-window': self.metadata('parent-window'),
            'parent-screen-limit-toggle': self.metadata(
                'parent-screen-limit-toggle', parent='parent-window', role='switch',
                value=False, operations=['getValue', 'setValue', 'activate']),
        }

    def metadata(self, identity, *, parent=None, role='window', value=None, operations=()):
        return {'id': identity, 'surface_id': 'parent-window',
                'application_id': self.application_id, 'parent_id': parent,
                'type': 'test-control', 'role': role, 'visible': True, 'enabled': True,
                'operations': ['getElementById', *operations], 'value': value}

    def listSurfaces(self):
        return [{'id': 'parent-window', 'application_id': self.application_id,
                 'visible': True, 'enabled': True, 'modal': False, 'parent_id': None}]

    def inventory(self, scope):
        assert scope == 'parent-window'
        return deepcopy(list(self.elements.values()))

    def call(self, scope, identity, operation, arguments=None):
        assert scope == 'parent-window'
        self.calls.append((identity, operation, arguments))
        if self.failure is not None:
            raise self.failure
        current = self.elements[identity]
        if operation == 'getElementById':
            return deepcopy(current)
        if operation == 'getValue':
            return current['value']
        if operation == 'setValue':
            current['value'] = arguments['value']
            return None
        raise AssertionError(operation)


def catalog(client):
    states = SimpleNamespace(**{name: name for name in (
        'VISIBLE', 'SHOWING', 'SENSITIVE', 'FOCUSED', 'ACTIVE', 'CHECKED',
        'PRESSED', 'SELECTED', 'EXPANDED', 'EDITABLE', 'MODAL')})
    return ApplicationUI(SimpleNamespace(StateType=states), clients={'parent': client})


def test_scoped_references_are_fresh_and_never_claim_keyboard_focus():
    client = Client()
    ui = catalog(client)
    first = ui.getElementById('parent-screen-limit-toggle')
    assert first.get_state_set().contains('SENSITIVE')
    assert not first.get_state_set().contains('FOCUSED')
    assert not first.get_state_set().contains('ACTIVE')
    first.setValue(True)
    second = ui.getElementById('parent-screen-limit-toggle')
    assert second == first and second is not first
    assert second.getValue() is True
    assert second.get_state_set().contains('CHECKED')
    assert [call[1] for call in client.calls].count('setValue') == 1
    client.owner = ':1.43'
    assert ui.getElementById('parent-screen-limit-toggle') != first


def test_inventory_observations_defer_unrelated_labels_and_keep_result_reads_fresh():
    from types import MappingProxyType
    client = Client()
    client.elements['parent-screen-limit-toggle']['name'] = 'Screen time limit'
    ui = catalog(client)
    node = ui.getElementById('parent-screen-limit-toggle')
    facts = MappingProxyType(node.observation_facts())
    assert facts['role'] == 'toggle button' and facts['showing'] is True
    assert client.calls == []
    assert facts['name'] == 'Screen time limit'
    assert facts['name'] == 'Screen time limit'
    assert [call[1] for call in client.calls] == ['getElementById']
    with pytest.raises(TypeError):
        facts['showing'] = False
    node.setValue(True)
    client.elements[node.identity]['name'] = 'Updated label'
    assert facts['name'] == 'Screen time limit'
    assert ui.getElementById(node.identity).getValue() is True
    assert [call[1] for call in client.calls] == ['getElementById', 'setValue', 'getValue']


def test_document_observations_refine_host_inventory_before_accepting_visibility():
    client = Client()
    client.elements['parent-screen-limit-toggle'].update(type='document-element', visible=False)
    node = catalog(client).getElementById('parent-screen-limit-toggle')
    node.metadata['visible'] = True  # Host inventory cannot prove alias visibility.
    assert node.observation_facts()['showing'] is False
    assert [call[1] for call in client.calls] == ['getElementById']


def test_character_and_format_reads_share_a_boundary_and_refresh_after_input():
    class EditorClient(Client):
        text = 'a😀b\n'
        document = {'ops': [{'insert': 'a😀', 'attributes': {'bold': True}},
                            {'insert': 'b\n'}]}

        def getValue(self, identity, *, surface_id):
            return self.call(surface_id, identity, 'getValue')

        def call(self, scope, identity, operation, arguments=None):
            assert scope == 'parent-window'
            self.calls.append((identity, operation, arguments))
            if operation == 'getText':
                return self.text
            if operation == 'getValue' and identity == 'feedback-editor-document':
                return deepcopy(self.document)
            if operation == 'setText':
                self.text = arguments['text']
                self.document = {'ops': [{'insert': self.text}]}
                return None
            raise AssertionError((identity, operation))

    client = EditorClient()
    ui = catalog(client)
    node = ui.getElementById('parent-screen-limit-toggle')
    assert node.get_character_count() == 4
    assert ''.join(chr(node.get_character_at_offset(i)) for i in range(4)) == 'a😀b\n'
    for offset, bounds, weight in [(0, (0, 2), '700'), (1, (0, 2), '700'),
                                    (2, (2, 4), '400'), (3, (2, 4), '400')]:
        attributes, start, end = node.get_attribute_run(offset)
        assert (start, end) == bounds and attributes['weight'] == weight
    assert [call[1] for call in client.calls] == ['getText', 'getValue']
    client.text = 'changed'
    assert node.getText() == 'changed'  # Independent result reads remain live.
    assert node.get_text(0, -1) == 'a😀b\n'
    assert ui.getElementById(node.identity).get_character_count() == 7
    node.setText('z\n')
    assert node.get_text(0, -1) == 'z\n'
    assert node.get_attribute_run(0)[1:] == (0, 2)
    with pytest.raises(UIClientError, match='InvalidArgument'):
        node.get_attribute_run(3)
    client.document = {'ops': [{'insert': {'image': 'unsupported'}}]}
    with pytest.raises(UIClientError, match='InvalidResponse'):
        ui.getElementById(node.identity).get_attribute_run(0)


@pytest.mark.parametrize('fault', ['cycle', 'missing-parent', 'wrong-owner', 'wrong-application'])
def test_incomplete_inventory_or_foreign_launch_owner_refuses(fault):
    client = Client()
    ui = catalog(client)
    kwargs = {}
    if fault == 'cycle':
        client.elements['parent-screen-limit-toggle']['parent_id'] = 'parent-screen-limit-toggle'
    elif fault == 'missing-parent':
        client.elements['parent-screen-limit-toggle']['parent_id'] = 'absent'
    elif fault == 'wrong-owner':
        kwargs['owner_pids'] = {99}
    else:
        kwargs['application_owners'] = {client.application_id: {99}}
    with pytest.raises(UIClientError):
        ui.applications(**kwargs)
    assert not any(operation == 'setValue' for _, operation, _ in client.calls)


@pytest.mark.parametrize('fault', [None, 'station-present', 'wrong-owner', 'incomplete', 'uncertain'])
def test_transfer_wrong_surface_refusal_ignores_departed_external_provider(monkeypatch, fault):
    import accessible_ui as a
    client = Client()
    if fault == 'station-present':
        client.application_id = a.KIOSK_APPLICATION
        for metadata in client.elements.values():
            metadata['application_id'] = client.application_id
    elif fault == 'incomplete':
        client.elements.pop('parent-window')
    reader = a.AccessibleUI(SimpleNamespace(), root=Mock(side_effect=RuntimeError('departed-provider')),
        owner_pids={99} if fault == 'wrong-owner' else {client.pid})
    reader.application_ui = catalog(client)
    reader.require_child_overlay_session = Mock()
    if fault == 'uncertain':
        reader.input_uncertain = True
    if fault:
        with pytest.raises((a.UiError, UIClientError)):
            reader.run('transfer-overlay-riley-refused', '')
    else:
        assert reader.run('transfer-overlay-riley-refused', '')['outcome'] == 'passed'
    reader.root.assert_not_called()
    assert client.calls == []  # Refusal never dispatches product input.


def test_uncertain_mutation_is_dispatched_once_without_fallback():
    client = Client()
    node = catalog(client).getElementById('parent-screen-limit-toggle')
    client.failure = UIClientError('Transport', uncertain=True)
    with pytest.raises(UIClientError) as failed:
        node.setValue(True)
    assert failed.value.uncertain
    assert client.calls == [('parent-screen-limit-toggle', 'setValue', {'value': True})]


@pytest.mark.parametrize('role,expected', [
    ('text-box', 'entry'), ('textbox', 'entry'), ('combo-box', 'combo box'),
    ('list-item', 'list item'), ('tab-list', 'page tab list'), ('menu-item', 'menu item'),
])
def test_native_and_document_roles_share_the_result_vocabulary(role, expected):
    client = Client()
    client.elements['parent-screen-limit-toggle']['role'] = role
    assert catalog(client).getElementById('parent-screen-limit-toggle').get_role_name() == expected


def test_inventory_does_not_hide_ambiguous_application_identity():
    first, second = Client(), Client()
    second.owner = ':1.43'
    ui = ApplicationUI(clients={'first': first, 'second': second})
    with pytest.raises(UIClientError):
        ui.getElementById('parent-screen-limit-toggle')


def test_scoped_refresh_keeps_original_owner_when_another_surface_has_same_id():
    first, second = Client(), Client()
    second.owner = ':1.43'
    ui = ApplicationUI(clients={'first': first, 'second': second})
    root = ui.applications()[0]
    second.elements['parent-screen-limit-toggle']['value'] = True
    original = root.children[0].children[0]
    assert ui.refresh(original).getValue() is False
    first.elements['parent-screen-limit-toggle']['value'] = True
    assert ui.refresh(original).getValue() is True
    with pytest.raises(UIClientError):
        ui.refresh(original, owner_pids={99})


@pytest.mark.parametrize('offset,expected', [(0, 0), (1, 1), (3, 2), (4, 3)])
def test_editor_offsets_use_utf16_without_splitting_a_scalar(offset, expected):
    assert utf16_index('a😀b', offset) == expected


def test_editor_offset_refuses_half_a_surrogate_pair():
    with pytest.raises(UIClientError):
        utf16_index('a😀b', 2)


def test_catalog_binds_each_preview_bus_without_reusing_gio_session_cache(monkeypatch):
    connections = [Mock(), Mock()]
    connect = Mock(side_effect=connections)
    gio = SimpleNamespace(
        DBusConnection=SimpleNamespace(new_for_address_sync=connect),
        DBusConnectionFlags=SimpleNamespace(AUTHENTICATION_CLIENT=1, MESSAGE_BUS_CONNECTION=2),
        bus_get_sync=Mock(side_effect=AssertionError('cached session bus is forbidden')),
    )
    monkeypatch.setitem(sys.modules, 'gi.repository', SimpleNamespace(Gio=gio))
    monkeypatch.setenv('DBUS_SESSION_BUS_ADDRESS', 'unix:path=/private/first/bus')
    first = ApplicationUI()
    assert first._connect() is connections[0]
    monkeypatch.setenv('DBUS_SESSION_BUS_ADDRESS', 'unix:path=/private/second/bus')
    second = ApplicationUI()
    assert second._connect() is connections[1]
    assert first._connect() is connections[0]
    assert [call.args[0] for call in connect.call_args_list] == [
        'unix:path=/private/first/bus', 'unix:path=/private/second/bus']
    for ui, connection in zip((first, second), connections):
        connection.set_exit_on_close.assert_called_once_with(False)
        ui.close()
        ui.close()
        connection.close_sync.assert_called_once_with(None)
        with pytest.raises(UIClientError):
            ui._connect()
        with pytest.raises(UIClientError):
            ui.applications()


def test_catalog_requires_explicit_session_address_and_preserves_borrowed_connection(monkeypatch):
    monkeypatch.delenv('DBUS_SESSION_BUS_ADDRESS', raising=False)
    with pytest.raises(UIClientError):
        ApplicationUI()._connect()
    connection = Mock()
    ui = ApplicationUI(connection=connection)
    assert ui._connect() is connection
    ui.close()
    connection.close_sync.assert_not_called()


@pytest.mark.parametrize('role', ['switch', 'checkbox', 'radio', 'button'])
@pytest.mark.parametrize('value', [False, True])
def test_api_boolean_projection_preserves_readback_without_claiming_focus(role, value):
    client = Client()
    client.elements['parent-screen-limit-toggle'].update(role=role, value=value)
    node = catalog(client).getElementById('parent-screen-limit-toggle')
    assert node.getValue() is value
    states = node.get_state_set()
    for state in ('CHECKED', 'PRESSED', 'SELECTED'):
        assert states.contains(state) is value
    for state in ('FOCUSED', 'ACTIVE'):
        assert not states.contains(state)
