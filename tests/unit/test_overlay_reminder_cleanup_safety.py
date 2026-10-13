"""Reminder facade guards use private in-memory public trees; no VM or services."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui as public
from tests.support.accessible_ui import Node, ui_for


DEFAULTS = [
    {'id': 'fifteen-seconds', 'value': 15, 'unit': 'second', 'text': ''},
    {'id': 'one-minute', 'value': 1, 'unit': 'minute', 'text': ''},
    {'id': 'five-minutes', 'value': 5, 'unit': 'minute', 'text': ''},
    {'id': 'ten-minutes', 'value': 10, 'unit': 'minute', 'text': ''},
]


def reminder_tree(records=None, *, opened=True):
    records = deepcopy(DEFAULTS if records is None else records)
    controls = {
        'language-list': Node(identity='language-list', value='en', choices=['en', 'de']),
        'language-continue': Node(identity='language-continue'),
        'language-cancel': Node(identity='language-cancel'),
        'preferences-tabs': Node(identity='preferences-tabs', value='reminders'),
        'reminder-list': Node(identity='reminder-list', value=records),
        'reminder-add': Node(identity='reminder-add'),
        'reminder-show-in-fullscreen': Node(identity='reminder-show-in-fullscreen', value=True),
    }
    dialog = Node(identity='language-dialog', children=controls.values(),
                  states=('showing', 'visible', 'sensitive', 'modal'))
    window = Node(identity='kiosk-request-window', children=[
        Node(identity='kiosk-language-ready'),
        Node(public.CHILD, 'label', identity='kiosk-child-selected-1001'),
        *([dialog] if opened else []),
    ], states=('showing', 'visible', 'sensitive', 'modal'))
    window.bus, window.path = ':1.100', '/request/window'
    ui = ui_for(window)
    application = ui.api.get_desktop(0)
    application.identity = public.CHILD_APPLICATION
    ui.require_child_overlay_session = Mock()
    editor_controls = {}

    def render():
        records.sort(key=lambda row: row['value'] * (60 if row['unit'] == 'minute' else 1))
        controls['reminder-list'].choices = [row['id'] for row in records]
        controls['reminder-show-in-fullscreen'].states.discard('sensitive')
        if records:
            controls['reminder-show-in-fullscreen'].states.add('sensitive')
        dialog.children[:] = [node for node in dialog.children if not
                              getattr(node, 'reminder_row', False)]
        for row in records:
            for action in ('text', 'trigger', 'edit', 'delete'):
                node = Node(row['text'] if action == 'text' else '',
                            identity=f"reminder-{row['id']}-{action}")
                node.parent, node.reminder_row = dialog, True
                if action == 'edit':
                    node.action.do_action.side_effect = lambda _index, row=row: edit(row)
                if action == 'delete':
                    def delete(_index, row=row):
                        records.remove(row)
                        render()
                        return True
                    node.action.do_action.side_effect = delete
                dialog.children.append(node)

    def edit(record=None):
        largest = max(records, key=lambda row: row['value'] *
                      (60 if row['unit'] == 'minute' else 1), default=None)
        initial = record or ({'unit': largest['unit'], 'value': largest['value'] * 2,
                              'text': ''} if largest else {'unit': 'minute', 'value': 1, 'text': ''})
        editor_controls.clear()
        for identity, value in (('reminder-unit', initial['unit']),
                                ('reminder-value', str(initial['value'])),
                                ('reminder-text', initial['text']),
                                ('reminder-editor-save', None)):
            node = Node(identity=identity, value=value)
            if identity in ('reminder-text', 'reminder-value'):
                node.states.add('editable')
            editor_controls[identity] = node
        editor = Node(identity='reminder-editor-dialog', children=editor_controls.values(),
                      states=('showing', 'visible', 'sensitive', 'modal'))
        editor.parent = dialog
        dialog.children.append(editor)

        def save(_index):
            row = {'id': record['id'] if record else 'reminder-created',
                   'value': int(editor_controls['reminder-value'].value),
                   'unit': editor_controls['reminder-unit'].value,
                   'text': editor_controls['reminder-text'].value}
            if record:
                record.update(row)
            else:
                records.append(row)
            dialog.children.remove(editor)
            render()
            return True
        editor_controls['reminder-editor-save'].action.do_action.side_effect = save
        return True

    def close(_index):
        window.children.remove(dialog)
        return True
    controls['reminder-add'].action.do_action.side_effect = lambda _index: edit()
    controls['language-continue'].action.do_action.side_effect = close
    controls['language-cancel'].action.do_action.side_effect = close
    render()
    return SimpleNamespace(ui=ui, application=application, window=window, dialog=dialog,
                           controls=controls, editor=editor_controls, records=records,
                           edit=edit, render=render)


def assert_no_input(tree):
    for node in (*tree.controls.values(), *tree.editor.values(), *tree.dialog.children):
        node.action.do_action.assert_not_called()
        node.setText.assert_not_called()
        node.setValue.assert_not_called()


def bound_operation(tree, operation):
    tree.ui.expected_overlay_reminder_source = tree.ui.overlay_reminder_read()['source']
    return tree.ui.overlay_reminder_operation(operation)


def test_read_is_detached_canonical_and_preserves_literal_body():
    tree = reminder_tree([{'id': 'literal', 'value': 90, 'unit': 'second',
                          'text': 'Save <work> & games!'}])
    result = tree.ui.overlay_reminder_read()
    assert result['records'] == tree.records
    assert result['show_in_fullscreen'] is True
    assert result['fullscreen_enabled'] is True
    assert result['language'] == 'en'
    assert len(result['source']) == 64
    tree.records[0]['text'] = 'later mutation'
    assert result['records'][0]['text'] == 'Save <work> & games!'
    assert_no_input(tree)


@pytest.mark.parametrize('create', [False, True])
@pytest.mark.parametrize('owned_defunct', [False, True])
def test_reminder_staleness_uses_only_the_bound_application(create, owned_defunct):
    tree = reminder_tree()
    retired = Node(role='label', states=('defunct',))
    provider = Node(role='application', identity='org.example.RetiringProvider', children=[retired])
    desktop = Node(role='desktop', children=[tree.application, provider])
    tree.ui.api.get_desktop = lambda _index: desktop
    if owned_defunct:
        tree.controls['language-list'].states.add('defunct')

    def observe():
        return (tree.ui.overlay_reminder_editor(seconds=75, text='Save <work>!')
                if create else tree.ui.overlay_reminder_read())

    if owned_defunct:
        with pytest.raises(public.UiError, match='ui:reminder-stale'): observe()
        assert_no_input(tree)
    else:
        result = observe()
        assert [row for row in result['records'] if row['id'] != 'reminder-created'] == DEFAULTS
        if create:
            tree.controls['reminder-add'].action.do_action.assert_called_once()
        else:
            assert_no_input(tree)
    retired.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', [
    'account', 'station', 'parent', 'wrong-child', 'hidden-child', 'owner', 'stale',
    'duplicate-id', 'duplicate-record', 'bad-choice', 'invalid-record', 'unsorted',
    'busy', 'wrong-tab', 'hidden-list', 'editor', 'foreign-modal', 'literal',
])
def test_invalid_entry_refuses_before_any_mutation(fault):
    tree = reminder_tree()
    if fault == 'account':
        tree.ui.require_child_overlay_session.side_effect = public.UiError('ui:overlay-account')
        tree.ui.read_snapshot = Mock(side_effect=AssertionError('unrelated discovery'))
    if fault in ('station', 'parent'):
        tree.application.identity = (public.KIOSK_APPLICATION if fault == 'station'
                                     else public.PARENT_APPLICATION)
    if fault == 'wrong-child': tree.window.children[1].identity = 'kiosk-child-selected-1002'
    if fault == 'hidden-child': tree.window.children[1].states.discard('showing')
    if fault == 'owner': tree.ui.owner_pids = lambda: {999}
    if fault == 'stale': tree.controls['language-list'].states.add('defunct')
    if fault == 'duplicate-id': tree.dialog.children.append(Node(identity='reminder-list'))
    if fault == 'duplicate-record': tree.records.append(deepcopy(tree.records[-1]))
    if fault == 'bad-choice': tree.controls['reminder-list'].choices = ['substituted']
    if fault == 'invalid-record': tree.records[0]['value'] = True
    if fault == 'unsorted': tree.records.reverse()
    if fault == 'busy': tree.controls['language-continue'].states.discard('sensitive')
    if fault == 'wrong-tab': tree.controls['preferences-tabs'].value = 'language'
    if fault == 'hidden-list': tree.controls['reminder-list'].states.discard('visible')
    if fault == 'editor': tree.edit()
    if fault == 'foreign-modal':
        modal = Node(identity='feedback-dialog', states=('visible', 'showing', 'modal'))
        modal.parent = tree.window
        tree.window.children.append(modal)
    if fault == 'literal': tree.records[0]['text'] = '<escaped> & body'
    with pytest.raises(public.UiError):
        tree.ui.overlay_reminder_delete('fifteen-seconds')
    assert_no_input(tree)


@pytest.mark.parametrize('kwargs', [
    {'seconds': True, 'text': 'finite'}, {'seconds': 0, 'text': 'finite'},
    {'seconds': 2**32, 'text': 'finite'}, {'seconds': 75, 'text': 'x' * 51},
    {'seconds': 75, 'text': '\x00'}, {'seconds': 75, 'text': '\ud800'},
    {'seconds': 75, 'text': 'finite', 'record_id': '../foreign'},
])
def test_invalid_caller_arguments_refuse_before_provider_discovery(kwargs):
    tree = reminder_tree()
    tree.ui.read_snapshot = Mock(side_effect=AssertionError('unrelated discovery'))
    tree.ui.require_child_overlay_session = Mock(side_effect=AssertionError('session discovery'))
    with pytest.raises(public.UiError, match='ui:reminder-editor-binding'):
        tree.ui.overlay_reminder_editor(**kwargs)
    tree.ui.read_snapshot.assert_not_called()
    tree.ui.require_child_overlay_session.assert_not_called()
    assert_no_input(tree)


def test_create_edit_and_delete_preserve_default_rows_and_stored_identity():
    tree = reminder_tree()
    before = tree.ui.overlay_reminder_read()
    created = bound_operation(tree, 'overlay-reminder-create')['reminders']
    custom = tree.ui._reminder_row(created['records'], seconds=75, text='Save <work>!')
    assert custom['id'] == 'reminder-created'
    assert [row for row in created['records'] if row['id'] != custom['id']] == DEFAULTS
    assert before['source'] != created['source']
    edited = bound_operation(tree, 'overlay-reminder-edit')['reminders']
    assert tree.ui._reminder_row(edited['records'], seconds=90,
                                text='Save <work> & games!')['id'] == custom['id']
    deleted = bound_operation(tree, 'overlay-reminder-delete')['reminders']
    assert deleted['records'] == DEFAULTS
    assert deleted['show_in_fullscreen'] is True
    assert deleted['language'] == 'en'
    assert tree.controls['language-continue'].action.do_action.call_count == 0
    assert not tree.ui.input_uncertain


def test_create_overwrites_an_arbitrary_valid_new_editor_seed():
    tree = reminder_tree()
    original = tree.edit

    def open_editor(_index):
        original()
        tree.editor['reminder-unit'].value = 'minute'
        tree.editor['reminder-value'].value = '3'
        tree.editor['reminder-text'].value = 'Initial suggestion'
        return True

    tree.controls['reminder-add'].action.do_action.side_effect = open_editor
    result = bound_operation(tree, 'overlay-reminder-create')['reminders']
    custom = tree.ui._reminder_row(result['records'], seconds=75, text='Save <work>!')
    assert [row for row in result['records'] if row['id'] != custom['id']] == DEFAULTS
    assert not tree.ui.input_uncertain


@pytest.mark.parametrize('fault', ['draft', 'initial-editor', 'lost-setter', 'changed-editor',
                                  'disabled-editor', 'lost-save', 'wrong-saved-id'])
def test_editor_refuses_stale_and_uncertain_input_without_replay(fault):
    tree = reminder_tree()
    original = tree.edit
    existing = tree.records[0] if fault == 'initial-editor' else None
    input_id = f"reminder-{existing['id']}-edit" if existing else 'reminder-add'
    input_control = next(node for node in tree.dialog.children if node.identity == input_id)
    options = {'record_id': existing['id']} if existing else {}

    def open_editor(_index):
        original(existing)
        if fault == 'draft': tree.controls['reminder-show-in-fullscreen'].value = False
        if fault == 'initial-editor': tree.editor['reminder-value'].value = '999'
        if fault == 'lost-setter':
            tree.editor['reminder-unit'].setValue.side_effect = public.UiError('ui:lost-reply')
        if fault == 'changed-editor':
            def change(value):
                tree.editor['reminder-unit'].value = value
                tree.editor['reminder-text'].value = 'substituted editor'
            tree.editor['reminder-unit'].setValue.side_effect = change
        if fault == 'disabled-editor': tree.editor['reminder-value'].states.discard('sensitive')
        if fault == 'lost-save': tree.editor['reminder-editor-save'].action.do_action.return_value = False
        if fault == 'lost-save': tree.editor['reminder-editor-save'].action.do_action.side_effect = None
        if fault == 'wrong-saved-id':
            save = tree.editor['reminder-editor-save'].action.do_action.side_effect
            def wrong(_index):
                save(_index)
                tree.records[-1]['id'] = 'changed'
                tree.records[-1]['value'] = 76
                tree.render()
                return True
            tree.editor['reminder-editor-save'].action.do_action.side_effect = wrong
        return True

    input_control.action.do_action.side_effect = open_editor
    with pytest.raises(public.UiError):
        tree.ui.overlay_reminder_editor(seconds=75, text='Save <work>!', **options)
    assert tree.ui.input_uncertain
    with pytest.raises(public.UiError, match='ui:uncertain-input'):
        tree.ui.overlay_reminder_editor(seconds=75, text='Save <work>!', **options)
    input_control.action.do_action.assert_called_once()
    assert tree.editor['reminder-unit'].setValue.call_count <= 1
    assert tree.editor['reminder-value'].setText.call_count <= 1
    assert tree.editor['reminder-text'].setText.call_count <= 1
    assert tree.editor['reminder-editor-save'].action.do_action.call_count <= 1
    if fault in ('draft', 'initial-editor'):
        tree.editor['reminder-unit'].setValue.assert_not_called()
    if fault in ('draft', 'initial-editor', 'lost-setter', 'changed-editor', 'disabled-editor'):
        tree.editor['reminder-editor-save'].action.do_action.assert_not_called()


def test_delete_all_retains_fullscreen_value_and_disables_empty_switch():
    tree = reminder_tree()
    tree.controls['reminder-show-in-fullscreen'].value = False
    result = bound_operation(tree, 'overlay-reminder-delete-all')['reminders']
    assert result['records'] == []
    assert result['show_in_fullscreen'] is False
    assert result['fullscreen_enabled'] is False
    tree.controls['reminder-show-in-fullscreen'].setValue.assert_not_called()


@pytest.mark.parametrize('save', [True, False])
def test_main_commit_closes_only_the_owned_idle_preferences(save):
    tree = reminder_tree()
    tree.ui.overlay_reminder_commit(save=save)
    identity = 'language-continue' if save else 'language-cancel'
    tree.controls[identity].action.do_action.assert_called_once()
    assert tree.dialog not in tree.window.children
    assert not tree.ui.input_uncertain


@pytest.mark.parametrize('fault', ['busy', 'editor', 'foreign-modal', 'account'])
@pytest.mark.parametrize('save', [True, False])
def test_main_commit_refuses_wrong_busy_or_modal_surface(save, fault):
    tree = reminder_tree()
    if fault == 'busy': tree.controls['language-continue'].states.discard('sensitive')
    if fault == 'editor': tree.edit()
    if fault == 'foreign-modal':
        tree.window.children.append(Node(identity='feedback-dialog', states=('showing', 'visible', 'modal')))
    if fault == 'account':
        tree.ui.require_child_overlay_session.side_effect = public.UiError('ui:overlay-account')
        tree.ui.read_snapshot = Mock(side_effect=AssertionError('unrelated discovery'))
    with pytest.raises(public.UiError): tree.ui.overlay_reminder_commit(save=save)
    assert_no_input(tree)


def test_open_uses_only_one_tab_setter_and_independent_loaded_read():
    tree = reminder_tree(opened=False)
    tree.controls['preferences-tabs'].value = 'language'
    def open_preferences(surface):
        assert surface == 'overlay'
        tree.dialog.parent = tree.window
        tree.window.children.append(tree.dialog)
    tree.ui.open_language_preferences = Mock(side_effect=open_preferences)
    result = tree.ui.overlay_reminder_operation('overlay-reminder-defaults')['reminders']
    assert result['records'] == DEFAULTS
    tree.ui.open_language_preferences.assert_called_once_with('overlay')
    tree.controls['preferences-tabs'].setValue.assert_called_once_with('reminders')
    assert not tree.ui.input_uncertain


@pytest.mark.parametrize('operation', sorted(public.OVERLAY_REMINDER_MUTATIONS))
def test_cross_observer_stale_source_refuses_before_any_input(operation):
    tree = reminder_tree([*DEFAULTS,
        {'id': 'created', 'value': 75, 'unit': 'second', 'text': 'Save <work>!'},
        {'id': 'edited', 'value': 90, 'unit': 'second', 'text': 'Save <work> & games!'},
    ])
    tree.ui.expected_overlay_reminder_source = tree.ui.overlay_reminder_read()['source']
    # The previous observation's owner/draft receipt no longer describes this
    # dialog, even though its row IDs and captions still look usable.
    tree.controls['reminder-show-in-fullscreen'].value = False
    with pytest.raises(public.UiError, match='ui:reminder-stale-draft'):
        tree.ui.overlay_reminder_operation(operation)
    assert_no_input(tree)


@pytest.mark.parametrize('action', ['read', 'create', 'edit', 'delete', 'save', 'cancel'])
def test_optional_source_is_checked_by_actual_shared_helper_before_input(action):
    tree = reminder_tree()
    source = tree.ui.overlay_reminder_read()['source']
    tree.controls['language-list'].value = 'de'
    calls = {
        'read': lambda: tree.ui.overlay_reminder_read(expected_source=source),
        'create': lambda: tree.ui.overlay_reminder_editor(seconds=75, text='Save <work>!',
                                                         expected_source=source),
        'edit': lambda: tree.ui.overlay_reminder_editor(seconds=90, text='Save <work> & games!',
            record_id='fifteen-seconds', expected_source=source),
        'delete': lambda: tree.ui.overlay_reminder_delete('fifteen-seconds', expected_source=source),
        'save': lambda: tree.ui.overlay_reminder_commit(save=True, expected_source=source),
        'cancel': lambda: tree.ui.overlay_reminder_commit(save=False, expected_source=source),
    }
    with pytest.raises(public.UiError, match='ui:reminder-stale-draft'): calls[action]()
    assert_no_input(tree)


@pytest.mark.parametrize('operation', sorted(public.OVERLAY_REMINDER_MUTATIONS))
@pytest.mark.parametrize('source', [None, '', 'A' * 64, 'a' * 63, '_a' * 32])
def test_fixed_mutations_require_source_before_unrelated_discovery(operation, source):
    tree = reminder_tree()
    tree.ui.expected_overlay_reminder_source = source
    tree.ui.read_snapshot = Mock(side_effect=AssertionError('unrelated discovery'))
    tree.ui.require_child_overlay_session = Mock(side_effect=AssertionError('session discovery'))
    with pytest.raises(public.UiError, match='ui:overlay-reminder-binding'):
        tree.ui.overlay_reminder_operation(operation)
    tree.ui.read_snapshot.assert_not_called()
    tree.ui.require_child_overlay_session.assert_not_called()
    assert_no_input(tree)


@pytest.mark.parametrize('operation', sorted(public.OVERLAY_REMINDER_MUTATIONS))
def test_fixed_operations_forward_controller_receipt_to_actual_input_helper(operation):
    tree = reminder_tree()
    source = 'a' * 64
    tree.ui.expected_overlay_reminder_source = source
    initial = {'source': source, 'records': [
        {'id': 'created', 'value': 75, 'unit': 'second', 'text': 'Save <work>!'},
        {'id': 'edited', 'value': 90, 'unit': 'second', 'text': 'Save <work> & games!'},
    ]}
    first, final = {'source': 'b' * 64, 'records': [initial['records'][1]]}, {
        'source': 'c' * 64, 'records': []}
    tree.ui.overlay_reminder_read = Mock(return_value=initial)
    tree.ui.overlay_reminder_editor = Mock(return_value=final)
    tree.ui.overlay_reminder_commit = Mock()
    tree.ui.overlay_reminder_delete = Mock(side_effect=[first, final])
    result = tree.ui.overlay_reminder_operation(operation)
    if operation in ('overlay-reminder-save', 'overlay-reminder-cancel'):
        tree.ui.overlay_reminder_commit.assert_called_once_with(
            save=operation.endswith('-save'), expected_source=source)
        assert result == {}
    elif operation == 'overlay-reminder-create':
        tree.ui.overlay_reminder_editor.assert_called_once_with(
            seconds=75, text='Save <work>!', expected_source=source)
    elif operation == 'overlay-reminder-edit':
        tree.ui.overlay_reminder_read.assert_called_once_with(expected_source=source)
        tree.ui.overlay_reminder_editor.assert_called_once_with(
            seconds=90, text='Save <work> & games!', record_id='created', expected_source=source)
    elif operation == 'overlay-reminder-delete':
        tree.ui.overlay_reminder_read.assert_called_once_with(expected_source=source)
        tree.ui.overlay_reminder_delete.assert_called_once_with('edited', expected_source=source)
    else:
        tree.ui.overlay_reminder_read.assert_called_once_with(expected_source=source)
        assert [(call.args, call.kwargs) for call in tree.ui.overlay_reminder_delete.call_args_list] == [
            (('created',), {'expected_source': source}),
            (('edited',), {'expected_source': first['source']}),
        ]


@pytest.mark.parametrize('arguments', [[], [''], ['', 'invalid'], ['', 'A' * 64]])
def test_standalone_missing_or_malformed_source_refuses_before_identity_lookup(monkeypatch, arguments):
    monkeypatch.setattr(public.sys, 'argv', ['observer', 'overlay-reminder-save', '1.1', *arguments])
    lookup = Mock(side_effect=AssertionError('identity discovery'))
    monkeypatch.setattr(public.os, 'geteuid', lookup)
    with pytest.raises(public.UiError, match='ui:overlay-reminder-binding'): public.main()
    lookup.assert_not_called()


@pytest.mark.parametrize('operation', sorted(public.OVERLAY_REMINDER_MUTATIONS))
def test_standalone_source_is_forwarded_without_becoming_authentication_binding(monkeypatch, capsys, operation):
    source = 'a' * 64
    monkeypatch.setattr(public.sys, 'argv', ['observer', operation, '1.1', '', source])
    monkeypatch.setattr(public, 'Path', Mock(return_value=SimpleNamespace(
        read_bytes=lambda: b'00000000-0000-0000-0000-000000000001\n')))
    account = SimpleNamespace(pw_name='onpc-child-riley', pw_uid=1001, pw_gid=1001, pw_dir='/fixture')
    monkeypatch.setattr(public.pwd, 'getpwnam', Mock(return_value=account))
    monkeypatch.setattr(public.os, 'geteuid', lambda: 0)
    for name in ('initgroups', 'setgid', 'setuid'):
        monkeypatch.setattr(public.os, name, Mock())
    monkeypatch.setattr(public.os, 'environ', {})
    monkeypatch.setattr(public, 'observation_environment', Mock(return_value={}))
    atspi = SimpleNamespace(set_timeout=Mock())
    glib = SimpleNamespace(Error=RuntimeError)
    monkeypatch.setitem(public.sys.modules, 'gi', SimpleNamespace(require_version=Mock()))
    monkeypatch.setitem(public.sys.modules, 'gi.repository', SimpleNamespace(Atspi=atspi, GLib=glib))
    ui = SimpleNamespace(api=SimpleNamespace(), query_errors=(), run=Mock(return_value={'outcome': 'passed'}))
    constructor = Mock(return_value=ui)
    constructor._reminder_source_binding = public.AccessibleUI._reminder_source_binding
    monkeypatch.setattr(public, 'AccessibleUI', constructor)
    public.main()
    assert ui.expected_overlay_reminder_source == source
    assert ui.expected_mate_challenge is None
    ui.run.assert_called_once_with(operation, '1.1', child=None)
    assert json.loads(capsys.readouterr().out)['outcome'] == 'passed'
