"""Functional GUI selection tolerates decoration but refuses unusable controls."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from accessible_ui import AccessibleUI, UiError, greeter_account, session_environment
from private_artifacts import EvidenceError
from ui_observations import UiObservations


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
        FOCUSED='focused', SELECTED='selected', CHECKED='checked', EDITABLE='editable', MODAL='modal'),
        CoordType=SimpleNamespace(SCREEN='screen')), timeout=0)


@pytest.mark.parametrize('fault', [None, 'wrong-account', 'no-prompt', 'unfocused', 'list-remains'])
def test_gdm_selection_requires_independent_identity_prompt_and_focus(fault):
    button = Node('Jamie (Parent)', 'push button', appearance={'scale': 2, 'misaligned': True})
    root = Node(children=[Node('Other Parent' if fault == 'wrong-account' else 'Jamie (Parent)', 'label')])
    field = Node('Password', 'password text', states=('showing', 'visible', 'sensitive', 'focused'))
    field.get_text_iface = Mock(side_effect=AssertionError('password read'))
    field.get_child_count = Mock(side_effect=AssertionError('password traversed'))
    if fault != 'no-prompt': root.children.append(field)
    if fault == 'unfocused': field.states.remove('focused')
    if fault == 'list-remains': root.children.append(button)
    ui = ui_for(root)
    if fault:
        with pytest.raises((UiError, LookupError)):
            ui.run('gdm-select-parent', '')
    else:
        assert ui.run('gdm-select-parent', '')['outcome'] == 'passed'
    button.action.do_action.assert_not_called()
    field.get_text_iface.assert_not_called()
    field.get_child_count.assert_not_called()


@pytest.mark.parametrize('index', [0, 1, 3])
def test_gdm_navigation_uses_public_order_and_independently_requires_focus(index):
    button = Node('Jamie (Parent)', 'push button')
    rows = [Node('Other fixture ' + str(number), 'push button') for number in range(3)]
    rows.insert(index, button)
    ui = ui_for(Node(children=rows))
    assert ui.run('gdm-list', '')['navigation'] == ['home'] + ['down'] * index
    with pytest.raises(UiError, match='gdm-account-focus'): ui.run('gdm-focused', '')
    button.states.add('focused')
    assert ui.run('gdm-focused', '')['outcome'] == 'passed'
    button.action.do_action.assert_not_called()


@pytest.mark.parametrize('operation', ['gdm-list', 'gdm-dismissed', 'gdm-returned'])
def test_gdm_account_label_cannot_hide_an_undismissed_prompt(operation):
    ui = ui_for(Node(children=[Node('Jamie (Parent)', 'push button'),
                              Node('Password', 'password text')]))
    with pytest.raises(UiError, match='gdm-prompt-dismissed'):
        ui.run(operation, '')


@pytest.mark.parametrize('fault', [None, 'missing', 'symlink', 'regular', 'wrong-owner'])
def test_public_bus_discovery_is_owned_and_bounded(tmp_path, fault, monkeypatch):
    import os
    import socket
    from pathlib import Path
    account = SimpleNamespace(pw_uid=os.getuid())
    runtime = tmp_path / str(account.pw_uid)
    directory = runtime
    directory.mkdir(parents=True)
    bus = directory / 'bus'
    sockets = []
    try:
        if fault == 'regular': bus.touch()
        elif fault != 'missing':
            connection = socket.socket(socket.AF_UNIX)
            sockets.append(connection)
            connection.bind(str(bus))
        if fault == 'symlink':
            bus.rename(directory / 'original')
            bus.symlink_to(directory / 'original')
        if fault == 'wrong-owner':
            original = Path.lstat
            def wrong_owner(path):
                info = original(path)
                return SimpleNamespace(st_mode=info.st_mode, st_uid=account.pw_uid + 1)
            monkeypatch.setattr(Path, 'lstat', wrong_owner)
        if fault:
            with pytest.raises(UiError):
                session_environment(account, runtime_root=tmp_path, timeout=0)
        else:
            result = session_environment(account, runtime_root=tmp_path, timeout=0)
            key = 'DBUS_SESSION_BUS_ADDRESS'
            assert result == {'XDG_RUNTIME_DIR': str(runtime), key: 'unix:path=' + str(bus)}
    finally:
        for connection in sockets: connection.close()


@pytest.mark.parametrize('fault', [None, 'duplicate', 'remote', 'inactive', 'desktop', 'wrong-seat', 'root'])
def test_greeter_identity_uses_unique_active_local_session_not_legacy_uid(monkeypatch, fault):
    import accessible_ui
    props = {'Class': 'greeter', 'Active': 'yes', 'Remote': 'no', 'Type': 'wayland',
             'Seat': 'seat0', 'User': '61234'}
    if fault == 'remote': props['Remote'] = 'yes'
    if fault == 'inactive': props['Active'] = 'no'
    if fault == 'desktop': props['Class'] = 'user'
    if fault == 'wrong-seat': props['Seat'] = 'seat1'
    if fault == 'root': props['User'] = '0'
    def call(argv, **kwargs):
        assert argv[0] == '/usr/bin/loginctl' and 0 < kwargs['timeout'] <= 5
        if argv[1] == 'list-sessions':
            return SimpleNamespace(stdout='c1 private-name\n' + ('c2 private-name\n' if fault == 'duplicate' else ''))
        return SimpleNamespace(stdout='\n'.join(key + '=' + value for key, value in props.items()))
    monkeypatch.setattr(accessible_ui.subprocess, 'run', call)
    account = SimpleNamespace(pw_uid=61234)
    lookup = Mock(return_value=account)
    monkeypatch.setattr(accessible_ui.pwd, 'getpwuid', lookup)
    if fault:
        with pytest.raises(UiError): greeter_account()
        lookup.assert_not_called()
    else:
        assert greeter_account() is account
        lookup.assert_called_once_with(61234)


@pytest.mark.parametrize('appearance', [
    {'x': 30, 'y': 90, 'font': 'default', 'color': 'blue', 'scale': 1},
    {'x': 811, 'y': 213, 'font': 'different', 'color': 'purple', 'scale': 2.5},
    {'x': 4, 'y': 1, 'font': 'large', 'width': 511, 'misaligned': True},
])
def test_usable_target_is_independent_of_appearance(appearance):
    button = Node('About', 'button', appearance=appearance)
    ui = ui_for(Node(children=[Node('Help', 'button'), button]))
    ui.activate(ui.target('About', ('button',), sensitive=True))
    button.action.do_action.assert_called_once_with(0)


@pytest.mark.parametrize('fault', ['hidden', 'disabled', 'wrong-name', 'ambiguous', 'refused'])
def test_unusable_or_wrong_control_cannot_pass(fault):
    button = Node('About', 'button')
    root = Node(children=[button])
    if fault == 'hidden': button.states.remove('showing')
    if fault == 'disabled': button.states.remove('sensitive')
    if fault == 'wrong-name': button.name = 'Help'
    if fault == 'ambiguous': root.children.append(Node('About', 'button'))
    if fault == 'refused': button.action.do_action.return_value = False
    ui = ui_for(root)
    with pytest.raises(UiError):
        ui.activate(ui.target('About', ('button',), sensitive=True))


def test_successful_action_without_expected_result_still_fails():
    button = Node('Selected child', 'combo box')
    ui = ui_for(Node(children=[button]))
    ui.activate(button)
    with pytest.raises(UiError, match='timeout'):
        ui.target('Riley (Child)', ('list item',))


def test_stale_queries_retry_but_actions_are_never_replayed():
    button = Node('About', 'button')
    ui = ui_for(button)
    ui.timeout = .5
    ui.query_errors = (LookupError,)
    button.get_name = Mock(side_effect=[LookupError('stale'), 'About'])
    ui.activate(ui.target('About', ('button',)))
    button.action.do_action.assert_called_once_with(0)
    button.action.do_action.side_effect = LookupError('uncertain delivery')
    with pytest.raises(LookupError): ui.activate(button)
    assert button.action.do_action.call_count == 2


def test_text_reflow_does_not_change_semantic_selector():
    label = Node('copyright\n   no warranty', 'label')
    assert ui_for(label).target('copyright no warranty', ('label',)) is label


def test_disabled_setting_can_be_read_but_cannot_authorize_input():
    control = Node('Daily time allowance', 'button', states=('showing', 'visible'))
    ui = ui_for(control)
    assert ui.target('Daily time allowance', ('button',)) is control
    with pytest.raises(UiError, match='unusable-target'):
        ui.activate(control)
    control.action.do_action.assert_not_called()


def test_prompt_dismissal_waits_for_absence_even_after_focus_is_lost():
    prompt = Node('Unlock Login Keyring', 'dialog')
    ui = ui_for(Node(role='desktop frame', children=[prompt]))
    with pytest.raises(UiError, match='system-prompt-dismissed'):
        ui.run('standard-app-grid', '')
    prompt.states.remove('showing')
    assert ui.system_prompt_control(qualify=False) is None


def test_dead_unrelated_subtree_does_not_hide_live_control():
    dead = Node('dead')
    dead.get_name = Mock(side_effect=LookupError('disconnected'))
    button = Node('About', 'button')
    ui = ui_for(Node(children=[dead, button]))
    ui.query_errors = (LookupError,)
    assert ui.target('About', ('button',)) is button


def test_duplicate_tree_paths_are_one_control_but_distinct_matches_are_ambiguous():
    button = Node('Search installed apps', 'entry')
    ui = ui_for(Node(children=[Node(children=[button]), Node(children=[button])]))
    assert ui.target(button.name, ('entry',)) is button
    with pytest.raises(UiError, match='ambiguous-target'):
        ui_for(Node(children=[button, Node(button.name, 'entry')])).target(button.name, ('entry',))


@pytest.mark.parametrize('nested', [False, True])
def test_search_result_supports_named_buttons_and_their_public_labels(nested):
    label = Node('Oh No! Parent Control', 'label')
    button = Node('' if nested else label.name, 'push button',
                  children=[Node(children=[label])] if nested else [])
    ui = ui_for(Node(children=[button]))
    assert ui.labelled_button(label.name) is button
    assert ui.run('app-grid', '1.1')['outcome'] == 'passed'


def test_search_text_without_a_launchable_control_is_not_a_result():
    ui = ui_for(Node(children=[Node('Oh No! Parent Control', 'label')]))
    with pytest.raises(UiError, match='labelled-button'):
        ui.run('app-grid', '1.1')


@pytest.mark.parametrize('fault', [None, 'hidden', 'missing', 'wrong-text', 'other-window',
                                  'selected-child', 'missing-picker', 'missing-placeholder', 'ambiguous'])
def test_empty_parent_requires_readable_explanation_and_no_selected_child(fault):
    from accessible_ui import PRODUCT
    explanation = Node('No interactive\n non-administrator account was found.', 'label',
                       appearance={'scale': 2.5, 'font': 'huge', 'misaligned': True})
    picker = Node('', 'combo box', children=[Node('(None)', 'label')],
                  states=('showing', 'visible'))
    root = Node(PRODUCT, children=[explanation, picker])
    if fault == 'hidden': explanation.states.remove('showing')
    if fault == 'missing': root.children.remove(explanation)
    if fault == 'wrong-text': explanation.name = 'Loading accounts'
    if fault == 'other-window': root.name = 'Unrelated application'
    if fault == 'selected-child': picker.children.append(Node('Jordan (Child)', 'label'))
    if fault == 'missing-picker': root.children.remove(picker)
    if fault == 'missing-placeholder': picker.children.clear()
    if fault == 'ambiguous': root.children.append(Node(explanation.name, 'label'))
    ui = ui_for(root)
    if fault:
        with pytest.raises(UiError): ui.run('parent-empty', '')
    else:
        assert ui.run('parent-empty', '') == {
            'operation': 'parent-empty', 'outcome': 'passed', 'interface': 'AT-SPI'}
    picker.action.do_action.assert_not_called()


def test_empty_parent_waits_for_fresh_state_without_replaying_input():
    from accessible_ui import PRODUCT
    root = Node(PRODUCT, children=[Node('', 'combo box', children=[Node('(None)', 'label')]),
        Node('No interactive non-administrator account was found.', 'label')])
    ui = ui_for(root)
    ui.timeout = .5
    original = ui.find
    calls = []
    def delayed(*args, **kwargs):
        calls.append(args)
        return None if len(calls) == 1 else original(*args, **kwargs)
    ui.find = delayed
    assert ui.run('parent-empty', '')['outcome'] == 'passed'
    assert calls.count((PRODUCT, ('frame',))) == 2


@pytest.mark.parametrize('operation', ['about-returned', 'parent-returned'])
def test_return_waits_for_the_window_to_finish_closing(operation):
    ui = ui_for(Node())
    ui.timeout = .5
    ui.find = Mock(side_effect=[Node(), None])
    ui.about = Mock(return_value=Node())
    ui.reveal = Mock()
    ui.settings = Mock(return_value={'child': 'fixture-child'})
    assert ui.run(operation, '1.1')['outcome'] == 'passed'
    assert ui.find.call_count == 2


@pytest.mark.parametrize('fault', [None, 'wrong-document', 'hidden', 'password'])
def test_license_reads_the_text_interface_and_requires_actual_visible_content(fault):
    link = Node('GNU General Public License v3.0', 'link')
    document = Node('', 'password text' if fault == 'password' else 'text')
    if fault == 'hidden': document.states.remove('showing')
    document.get_text_iface = lambda: document
    document.get_text = Mock(side_effect=AssertionError('wrong Accessible interface'))
    root = Node(children=[Node('About', 'frame', children=[link]),
                          Node('LICENSE', 'frame', children=[document])])
    ui = ui_for(root)
    content = ('An unrelated document' if fault == 'wrong-document' else
               'GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n' + 'x' * 2000)
    ui.api.Text = SimpleNamespace(get_character_count=lambda node: len(content),
                                 get_text=Mock(side_effect=lambda node, start, end: content[start:end]))
    if fault:
        with pytest.raises(UiError, match='license-content'):
            ui.run('license', '1.1')
    else:
        result = ui.run('license', '1.1')
        assert result == {'operation': 'license', 'outcome': 'passed', 'interface': 'AT-SPI'}
        ui.api.Text.get_text.assert_called_once_with(document, 0, 1024)
    document.get_text.assert_not_called()
    if fault in ('hidden', 'password'):
        ui.api.Text.get_text.assert_not_called()


@pytest.mark.parametrize('operation', ['child-picker-opened', 'discovery-child-picker-opened', 'new-child-picker-opened',
                                     'existing-child-picker-opened', 'gdm-list', 'gdm-other-list'])
@pytest.mark.parametrize('keys,valid', [
    (['home'], True), (['home', 'down', 'down'], True),
    ([], False), (['down'], False), (['home', 'ret'], False),
    (['home', 'alt-f4'], False), (['home'] + ['down'] * 32, False),
])
def test_guest_list_navigation_is_bounded_to_customer_arrow_keys(keys, valid, operation):
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI',
              'navigation': keys}
    session = UiObservations(SimpleNamespace(call=Mock(return_value=json.dumps(result).encode())))
    if valid:
        assert session.observe(operation)['navigation'] == keys
    else:
        with pytest.raises(EvidenceError, match='ui:navigation'):
            session.observe(operation)


def test_password_widget_contents_are_never_traversed():
    secret = Node('secret', 'password text', children=[Node('must not read')])
    secret.get_child_count = Mock(side_effect=AssertionError('secret traversed'))
    assert list(ui_for(secret).nodes()) == [secret]


@pytest.mark.parametrize('fault', [None, 'changed-child', 'changed-toggle', 'changed-allowance',
                                  'unreviewed-text', 'replay', 'no-selection'])
def test_return_compares_actual_displayed_settings(fault):
    settings = {'child': 'fixture-child', 'limit_enabled': False, 'allowance': ['30 minutes']}
    def response(operation, values):
        return json.dumps({'operation': operation, 'outcome': 'passed',
                           'interface': 'AT-SPI', 'settings': values}).encode()
    transport = SimpleNamespace(call=Mock(return_value=response('parent-selected', settings)))
    session = UiObservations(transport)
    if fault != 'no-selection':
        session.observe('parent-selected')
    returned = dict(settings)
    if fault == 'changed-child': returned['child'] = 'another-child'
    if fault == 'changed-toggle': returned['limit_enabled'] = True
    if fault == 'changed-allowance': returned['allowance'] = ['45 minutes']
    if fault == 'unreviewed-text': returned['allowance'] = ['private unexpected data']
    operation = 'parent-selected' if fault == 'replay' else 'parent-returned'
    transport.call.return_value = response(operation, returned)
    if fault:
        with pytest.raises(EvidenceError): session.observe(operation)
    else:
        assert session.observe(operation)['settings'] == settings


@pytest.mark.parametrize('fault', [None, 'missing', 'wrong-highlight', 'hidden', 'disabled',
                                  'wrong-selection', 'popup-remains'])
def test_dynamic_child_requires_expansion_highlight_and_independent_selection(fault):
    from accessible_ui import PRODUCT, CHILD, NEW_CHILD
    selected = Node(CHILD, 'label')
    toggle = Node('', 'toggle button')
    picker = Node('', 'combo box', children=[selected, toggle])
    allowance = Node('Daily time allowance', 'button', children=[Node('30 minutes', 'label')],
                     states=('showing', 'visible'))
    root = Node(PRODUCT, children=[picker, Node('Screen time limit', 'switch'), allowance,
                                   Node("Today's Remaining Time", 'label')])
    row = Node('', 'list item', children=[Node(NEW_CHILD, 'label')])
    listing = Node('', 'list box', children=[Node('', 'list item', children=[Node(CHILD, 'label')]), row])
    def expand(_index):
        if fault != 'missing': root.children.append(listing)
        return True
    toggle.action.do_action.side_effect = expand
    ui = ui_for(root)
    if fault == 'disabled': row.states.remove('sensitive')
    if fault == 'hidden': row.children[0].states.remove('showing')
    if fault in ('missing', 'disabled', 'hidden'):
        with pytest.raises(UiError): ui.run('new-child-picker-opened', '')
    else:
        assert ui.run('new-child-picker-opened', '')['navigation'] == ['home', 'down']
        (listing.children[0] if fault == 'wrong-highlight' else row).states.add('selected')
        if fault == 'wrong-highlight':
            with pytest.raises(UiError, match='choice-highlight'):
                ui.run('new-child-choice-highlighted', '')
        else:
            ui.run('new-child-choice-highlighted', '')
            if fault != 'popup-remains': root.children.remove(listing)
            if fault != 'wrong-selection': selected.name = NEW_CHILD
            if fault:
                with pytest.raises(UiError): ui.run('new-child-selected', '')
            else:
                assert ui.run('new-child-selected', '')['settings'] == {
                    'child': 'new-fixture-child', 'limit_enabled': False, 'allowance': ['30 minutes']}
    toggle.action.do_action.assert_called_once_with(0)


@pytest.mark.parametrize('fault', [None, 'new-identity', 'new-replay', 'new-return-changed',
                                  'existing-return-changed', 'private-text'])
def test_discovery_controller_keeps_child_settings_separate_and_private(fault):
    existing = {'child': 'existing-fixture-child', 'limit_enabled': False, 'allowance': ['0 minutes']}
    new = {'child': 'new-fixture-child', 'limit_enabled': False, 'allowance': ['1 hour']}
    transport = SimpleNamespace(call=Mock())
    session = UiObservations(transport)
    def observe(operation, settings):
        transport.call.return_value = json.dumps({'operation': operation, 'outcome': 'passed',
            'interface': 'AT-SPI', 'settings': settings}).encode()
        return session.observe(operation)
    observe('discovery-selected', existing)
    observe('discovery-ready', existing)
    if fault == 'new-identity': new['child'] = 'fixture-child'
    if fault == 'private-text': new['allowance'] = ['private child information']
    if fault in ('new-identity', 'private-text'):
        with pytest.raises(EvidenceError): observe('new-child-selected', new)
        return
    observe('new-child-selected', new)
    if fault == 'new-replay':
        with pytest.raises(EvidenceError): observe('new-child-selected', new)
        return
    returned = dict(new)
    if fault == 'new-return-changed': returned['limit_enabled'] = True
    if fault == 'new-return-changed':
        with pytest.raises(EvidenceError): observe('new-child-screen', returned)
        return
    observe('new-child-screen', returned)
    returned = dict(existing)
    if fault == 'existing-return-changed': returned['allowance'] = ['1 hour']
    if fault:
        with pytest.raises(EvidenceError): observe('existing-returned', returned)
    else:
        assert observe('existing-returned', returned)['settings'] == existing


@pytest.mark.parametrize('enabled,allowance', [(True, ['0 minutes']), (False, ['30 minutes'])])
def test_discovery_retains_original_zero_allowance_and_limits_off_expectation(enabled, allowance):
    result = {'operation': 'discovery-selected', 'outcome': 'passed', 'interface': 'AT-SPI',
              'settings': {'child': 'existing-fixture-child', 'limit_enabled': enabled,
                           'allowance': allowance}}
    session = UiObservations(SimpleNamespace(call=Mock(return_value=json.dumps(result).encode())))
    with pytest.raises(EvidenceError, match='initial-settings'):
        session.observe('discovery-selected')


@pytest.mark.parametrize('operation', ['gdm-parent-recipient', 'gdm-parent-recipient-rechecked',
    'gdm-standard-recipient', 'gdm-standard-recipient-rechecked'])
@pytest.mark.parametrize('fault', [None, 'wrong-identity', 'list-visible', 'unfocused', 'unmasked',
                                  'hidden', 'disabled', 'nonempty', 'ambiguous', 'other-label'])
def test_functional_password_recipient_requires_exact_identity_and_empty_masked_focus(operation, fault):
    from accessible_ui import PARENT, OTHER_PARENT, EXISTING_CHILD
    name = EXISTING_CHILD if operation.startswith('gdm-standard-') else PARENT
    label = Node(OTHER_PARENT if fault == 'wrong-identity' else name, 'label')
    field = Node('Password', 'text' if fault == 'unmasked' else 'password text',
                 states=('showing', 'visible', 'sensitive', 'focused'))
    if fault in ('hidden', 'disabled', 'unfocused'):
        field.states.remove({'hidden': 'showing', 'disabled': 'sensitive', 'unfocused': 'focused'}[fault])
    field.get_text_iface = lambda: field
    field.get_child_count = Mock(side_effect=AssertionError('password traversed'))
    root = Node(children=[label, field])
    if fault == 'list-visible': root.children.append(Node(PARENT, 'push button'))
    if fault == 'ambiguous': root.children.append(Node('Other password', 'password text'))
    if fault == 'other-label': root.children.append(Node(OTHER_PARENT, 'label'))
    ui = ui_for(root)
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: 1 if fault == 'nonempty' else 0,
                                 get_text=Mock(side_effect=AssertionError('password text read')))
    if fault:
        with pytest.raises(UiError): ui.run(operation, '')
    else:
        assert ui.run(operation, '')['outcome'] == 'passed'
    ui.api.Text.get_text.assert_not_called()
    field.get_child_count.assert_not_called()


def test_live_wrong_account_prompt_explicitly_refuses_parent_recipient():
    from accessible_ui import PARENT, OTHER_PARENT
    field = Node('Password', 'password text', states=('showing', 'visible', 'sensitive', 'focused'))
    field.get_text_iface = lambda: field
    ui = ui_for(Node(children=[Node(OTHER_PARENT, 'label'), field]))
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: 0)
    assert ui.run('gdm-wrong-recipient-refused', '')['outcome'] == 'passed'
    assert not ui.password_recipient(PARENT)


@pytest.mark.parametrize('fault', [None, 'skip-wrong', 'skip-first', 'replay', 'intervening-state'])
@pytest.mark.parametrize('standard', [False, True])
def test_controller_requires_ordered_wrong_recipient_then_fresh_parent_recheck(fault, standard):
    transport = SimpleNamespace(call=Mock())
    ui = UiObservations(transport)
    def observe(operation):
        if standard:
            operation = {'gdm-wrong-recipient-refused': 'gdm-standard-wrong-recipient-refused',
                         'gdm-focused': 'gdm-standard-focused'}.get(operation, operation)
            operation = operation.replace('gdm-parent-recipient', 'gdm-standard-recipient')
        transport.call.return_value = json.dumps({
            'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}).encode()
        ui.observe(operation)
    if fault != 'skip-wrong':
        observe('gdm-other-focused')
        observe('gdm-wrong-recipient-refused')
    observe('gdm-focused')
    if fault == 'skip-wrong':
        with pytest.raises(EvidenceError, match='recipient-order'): observe('gdm-parent-recipient')
        return
    if fault != 'skip-first': observe('gdm-parent-recipient')
    if fault == 'intervening-state': observe('gdm-focused')
    if fault in ('skip-first', 'intervening-state'):
        with pytest.raises(EvidenceError, match='recipient-order'): observe('gdm-parent-recipient-rechecked')
        return
    observe('gdm-parent-recipient-rechecked')
    if fault == 'replay':
        with pytest.raises(EvidenceError, match='recipient-order'): observe('gdm-parent-recipient-rechecked')


@pytest.mark.parametrize('fault', [None, 'wrong-query', 'missing-field', 'hidden-field',
    'disabled-field', 'missing-overview', 'missing-suggestion', 'hidden-description',
    'wrong-description', 'launcher', 'unnamed-launcher', 'management', 'stale-subtree',
    'delayed-launcher', 'labelled-result', 'disabled-suggestion', 'unrelated-description'])
def test_standard_search_requires_query_web_result_and_stable_complete_absence(monkeypatch, fault):
    import accessible_ui
    product = accessible_ui.PRODUCT
    field = Node(product, 'text')
    field.states.add('editable')
    field.value = 'wrong query' if fault == 'wrong-query' else product
    field.get_text_iface = lambda: field
    description = Node('Search "' + product + '" on the web', 'label')
    suggestion = Node('Search online', 'push button', children=[description])
    overview = Node('Overview', 'panel', children=[field, suggestion],
                    appearance={'scale': 2.5, 'font': 'ugly', 'misaligned': True})
    root = Node(children=[overview])
    if fault == 'missing-field': overview.children.remove(field)
    if fault == 'hidden-field': field.states.remove('showing')
    if fault == 'disabled-field': field.states.remove('sensitive')
    if fault == 'missing-overview': overview.name = 'Unrelated window'
    if fault == 'missing-suggestion': overview.children.remove(suggestion)
    if fault == 'disabled-suggestion': suggestion.states.remove('sensitive')
    if fault == 'labelled-result':
        suggestion.name = ''
        label = Node('Search online', 'label')
        label.parent = suggestion
        suggestion.children.append(label)
    if fault == 'unrelated-description':
        suggestion.children.remove(description)
        overview.children.append(description)
    if fault == 'hidden-description': description.states.remove('showing')
    if fault == 'wrong-description': description.name = 'Search for unrelated information'
    if fault == 'launcher': overview.children.append(Node(product, 'push button'))
    if fault == 'unnamed-launcher':
        overview.children.append(Node('', 'push button', children=[Node(product, 'label')]))
    if fault == 'management': root.children.append(Node(product, 'frame'))
    if fault == 'stale-subtree':
        stale = Node('private-canary')
        stale.get_child_count = Mock(side_effect=LookupError('private-canary'))
        overview.children.append(stale)
    ui = ui_for(root)
    ui.query_errors = (LookupError,)
    ui.timeout = 4
    ui.api.Text = SimpleNamespace(get_character_count=lambda text: len(text.value),
                                 get_text=lambda text, start, end: text.value[start:end])
    now = [0.0]
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: now[0])
    def tick(seconds):
        now[0] += seconds
        if fault == 'delayed-launcher' and now[0] >= 1:
            overview.children.append(Node(product, 'push button'))
    monkeypatch.setattr(accessible_ui.time, 'sleep', tick)
    if fault not in (None, 'labelled-result'):
        with pytest.raises(UiError, match='standard-parent-unavailable'):
            ui.run('standard-parent-unavailable', '')
    else:
        assert ui.run('standard-parent-unavailable', '') == {
            'operation': 'standard-parent-unavailable', 'outcome': 'passed', 'interface': 'AT-SPI'}
        assert now[0] >= 2
    suggestion.action.do_action.assert_not_called()


@pytest.mark.parametrize('operation', ['standard-desktop', 'standard-app-grid',
                                      'standard-parent-unavailable'])
def test_standard_controller_rejects_private_text_and_wrong_operation(operation):
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
    if operation == 'standard-app-grid': result['pointer'] = {'x': 731, 'y': 80}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(result).encode()))
    assert UiObservations(transport).observe(operation) == result
    result['private'] = 'private-canary'
    transport.call.return_value = json.dumps(result).encode()
    with pytest.raises(EvidenceError, match='response'):
        UiObservations(transport).observe(operation)


@pytest.mark.parametrize('fault', [None, 'hidden', 'disabled', 'noneditable', 'nonempty'])
def test_standard_typeahead_requires_visible_enabled_editable_empty_search(fault):
    field = Node('', 'text')
    field.states.add('editable')
    field.get_text_iface = lambda: field
    if fault == 'hidden': field.states.remove('showing')
    if fault == 'disabled': field.states.remove('sensitive')
    if fault == 'noneditable': field.states.remove('editable')
    field.get_component_iface = Mock(return_value=SimpleNamespace(get_extents=lambda _: SimpleNamespace(
        x=100, y=200, width=300, height=50)))
    ui = ui_for(Node(children=[Node('Overview', 'panel', children=[field])]))
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: 1 if fault == 'nonempty' else 0,
                                 get_text=lambda *_: '')
    if fault:
        with pytest.raises((UiError, LookupError)): ui.run('standard-app-grid', '')
    else:
        assert ui.run('standard-app-grid', '')['outcome'] == 'passed'
    assert field.get_component_iface.call_count == (0 if fault else 1)


@pytest.mark.parametrize('value', ['', 'wrong', 'O'])
def test_typeahead_requires_actual_first_character_before_remaining_input(value):
    field = Node('', 'text', states=('showing', 'visible', 'sensitive', 'editable'))
    field.get_text_iface = lambda: field
    ui = ui_for(Node(children=[Node('Overview', 'panel', children=[field])]))
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: len(value), get_text=lambda *_: value)
    if value == 'O':
        assert ui.run('standard-search-started', '')['outcome'] == 'passed'
    else:
        with pytest.raises(UiError, match='standard-search-started'):
            ui.run('standard-search-started', '')


def test_accessibility_wait_delivers_pending_events_before_fresh_read():
    field = Node('', 'text')
    ui = ui_for(field)
    ui.dispatch = Mock(side_effect=lambda: field.states.add('focused'))
    assert ui.wait(lambda: ui.has_state(field, ui.api.StateType.FOCUSED), 'focus')
    ui.dispatch.assert_called_once_with()


def test_event_storm_cannot_prevent_bounded_predicate_or_replay_action():
    button = Node('About', 'button')
    ui = ui_for(button)
    ui.dispatch = Mock(return_value=True)
    ui.activate(button)
    with pytest.raises(UiError, match='timeout:missing-result'):
        ui.wait(lambda: False, 'missing-result')
    assert ui.dispatch.call_count == 32
    button.action.do_action.assert_called_once_with(0)


def test_search_field_excludes_noneditable_text_and_requires_editable_state():
    field = Node('', 'text', states=('showing', 'visible', 'sensitive', 'editable'))
    field.get_text_iface = lambda: field
    label_text = Node('Other text', 'text')
    label_text.get_text_iface = Mock(side_effect=AssertionError('noneditable text read'))
    ui = ui_for(Node(children=[Node('Overview', 'panel', children=[field, label_text])]))
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: 0, get_text=lambda *_: '')
    assert ui.search_query('')
    field.states.remove('editable')
    assert not ui.search_query('')
    label_text.get_text_iface.assert_not_called()


@pytest.mark.parametrize('focused', [False, True])
def test_pointer_input_requires_independent_search_focus(focused):
    field = Node('', 'text', states=('showing', 'visible', 'sensitive', 'editable'))
    if focused: field.states.add('focused')
    field.get_text_iface = lambda: field
    ui = ui_for(Node(children=[Node('Overview', 'panel', children=[field])]))
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: 0, get_text=lambda *_: '')
    if focused:
        assert ui.run('standard-search-focused', '')['outcome'] == 'passed'
    else:
        with pytest.raises(UiError, match='standard-search-focus'):
            ui.run('standard-search-focused', '')


@pytest.mark.parametrize('point', [{'x': -1, 'y': 2}, {'x': True, 'y': 2},
                                 {'x': 3.5, 'y': 2}, {'x': 3, 'y': 2, 'private': 'canary'}])
def test_pointer_reply_rejects_invalid_or_private_fields(point):
    result = {'operation': 'standard-app-grid', 'outcome': 'passed', 'interface': 'AT-SPI', 'pointer': point}
    with pytest.raises(EvidenceError, match='pointer'):
        UiObservations(SimpleNamespace(call=Mock(return_value=json.dumps(result).encode()))).observe('standard-app-grid')


def test_search_failure_diagnostic_redacts_window_names_and_text():
    root = Node(role='desktop frame', children=[Node('private-canary', 'dialog'), Node('Unlock Login Keyring', 'dialog'),
                          Node('private-body', 'text')])
    result = ui_for(root).search_diagnostic()
    assert 'private' not in json.dumps(result)
    assert [window['surface'] for window in result['search_windows']] == ['other', 'keyring']


@pytest.mark.parametrize('fault', [None, 'disabled', 'hidden', 'unfocused', 'unmasked'])
def test_only_identified_focused_keyring_prompt_authorizes_normal_cancel(fault):
    control = Node('Cancel', 'push button')
    password = Node('', 'password text')
    password.states.add('focused')
    dialog = Node('Unlock Login Keyring', 'dialog', children=[control, password])
    if fault == 'disabled': control.states.remove('sensitive')
    if fault == 'hidden': control.states.remove('showing')
    if fault == 'unfocused': password.states.remove('focused')
    if fault == 'unmasked': password.role = 'text'
    ui = ui_for(Node(role='desktop frame', children=[dialog]))
    if fault:
        with pytest.raises(UiError): ui.system_prompt_control()
    else:
        assert ui.system_prompt_control() is control
        with pytest.raises(UiError, match='system-prompt-dismissed'):
            ui.run('standard-app-grid', '')
    control.action.do_action.assert_not_called()


def test_system_prompt_dismissal_cannot_hide_parent_or_unknown_dialog():
    from accessible_ui import PRODUCT
    controls = [Node('Cancel', 'push button'), Node('Cancel', 'push button')]
    ui = ui_for(Node(role='desktop frame', children=[
        Node(PRODUCT, 'frame', children=[controls[0]]),
        Node('Unrecognized dialog', 'dialog', children=[controls[1]])]))
    assert ui.system_prompt_control() is None
    for control in controls: control.action.do_action.assert_not_called()


@pytest.mark.parametrize('description', [
    'The login keyring did not get unlocked when you logged into your computer.',
    'The password you use to log in to your computer no longer matches that of your login keyring.',
])
@pytest.mark.parametrize('missing', [None, 'Authentication required', 'Unlock', 'password'])
def test_shell_keyring_description_requires_complete_public_prompt(description, missing):
    cancel = Node('Cancel', 'push button')
    password = Node('password', 'password text')
    password.states.add('focused')
    password.get_text_iface = Mock(side_effect=AssertionError('never read a password'))
    children = [Node(description, 'label'), Node('Authentication required', 'label'),
                Node('Unlock', 'push button'), password, cancel]
    dialog = Node('', 'dialog', children=[child for child in children if child.name != missing])
    ui = ui_for(Node(role='desktop frame', children=[dialog]))
    if missing:
        with pytest.raises(UiError, match='keyring-prompt-identity'):
            ui.system_prompt_control()
    else:
        assert ui.system_prompt_control() is cancel
        dialog.states.remove('showing')
        for child in children: child.states.discard('showing')
        assert ui.system_prompt_control() is None
    cancel.action.do_action.assert_not_called()
    password.get_text_iface.assert_not_called()


@pytest.mark.parametrize('keys', [[], ['esc'], ['ret'], ['esc', 'esc'], 'esc', None, ['home']])
def test_system_prompt_checkpoint_cannot_authorize_unobserved_keyboard_input(keys):
    result = {'operation': 'standard-system-prompt', 'outcome': 'passed', 'interface': 'AT-SPI',
              'navigation': keys}
    session = UiObservations(SimpleNamespace(call=Mock(return_value=json.dumps(result).encode())))
    with pytest.raises(EvidenceError, match='response'):
        session.observe('standard-system-prompt')


def keyring_dialog():
    cancel = Node('Cancel', 'push button')
    cancel.get_component_iface = lambda: SimpleNamespace(get_extents=lambda _: SimpleNamespace(
        x=100, y=300, width=200, height=60))
    password = Node('', 'password text', states=('showing', 'visible', 'sensitive', 'focused'))
    password.get_text_iface = Mock(side_effect=AssertionError('never read password'))
    return Node('Unlock Login Keyring', 'dialog', children=[cancel, password])


@pytest.mark.parametrize('timing', ['before-operation', 'during-wait', 'after-action'])
def test_shared_prompt_handler_resumes_same_wait_without_replaying_customer_action(timing):
    dialog = keyring_dialog()
    activity = Node('Activities', 'button')
    root = Node(role='desktop frame', children=[activity])
    ui = ui_for(root)
    clicks = []
    def cancel(point):
        clicks.append(point)
        root.children.remove(dialog)
    ui.system_prompt = cancel
    if timing == 'before-operation':
        root.children.append(dialog)
        ui.run('desktop', '')
    else:
        ui.prompt_enabled = True
        if timing == 'after-action':
            activity.action.do_action.side_effect = lambda _: root.children.append(dialog) or True
            ui.activate(activity)
        else:
            def dispatch():
                ui.dispatch = None
                root.children.append(dialog)
            ui.dispatch = dispatch
        assert ui.wait(lambda: dialog not in root.children, 'pending-observation')
    assert clicks == [{'x': 200, 'y': 330}]
    assert activity.action.do_action.call_count == (1 if timing == 'after-action' else 0)
    dialog.children[1].get_text_iface.assert_not_called()


@pytest.mark.parametrize('failure', ['still-visible', 'uncertain-click', 'lost-observation'])
def test_shared_prompt_handler_never_retries_failed_or_uncertain_dismissal(failure):
    dialog = keyring_dialog()
    ui = ui_for(Node(role='desktop frame', children=[dialog]))
    ui.query_errors = (LookupError,)
    def cancel(_):
        if failure == 'uncertain-click':
            raise LookupError('uncertain')
        if failure == 'lost-observation':
            dialog.clear_cache_single = Mock(side_effect=LookupError('stale'))
        # Still visible, even if focus changed during dismissal.
        dialog.children[1].states.discard('focused')
    ui.system_prompt = Mock(side_effect=cancel)
    with pytest.raises(UiError):
        ui.run('standard-system-prompt', '')
    ui.system_prompt.assert_called_once()


def test_gdm_never_uses_desktop_prompt_handler():
    ui = ui_for(Node(children=[Node('Jamie (Parent)', 'push button')]))
    ui.system_prompt = Mock(side_effect=AssertionError('GDM must not dismiss'))
    ui.system_prompt_control = Mock(side_effect=AssertionError('GDM must not inspect keyring'))
    ui.run('gdm-list', '')
    ui.system_prompt.assert_not_called()


@pytest.mark.parametrize('count', [2, 3, 4])
def test_distinct_queued_keyring_dialogs_require_independent_dismissals_and_finite_bound(count):
    dialogs = [keyring_dialog() for _ in range(count)]
    root = Node(role='desktop frame', children=[dialogs[0]])
    ui = ui_for(root)
    clicked = []
    def cancel(_):
        clicked.append(root.children.pop())
        if len(clicked) < count:
            root.children.append(dialogs[len(clicked)])
    ui.system_prompt = cancel
    if count > 3:
        with pytest.raises(UiError, match='system-prompt-limit'):
            ui.run('standard-system-prompt', '')
    else:
        assert ui.run('standard-system-prompt', '')['outcome'] == 'passed'
    assert clicked == dialogs[:3]


def test_second_keyring_dialog_does_not_authorize_reclick_while_first_remains_visible():
    original, replacement = keyring_dialog(), keyring_dialog()
    root = Node(role='desktop frame', children=[original])
    ui = ui_for(root)
    ui.system_prompt = Mock(side_effect=lambda _: root.children.append(replacement))
    with pytest.raises(UiError, match='system-prompt-dismissed'):
        ui.run('standard-system-prompt', '')
    ui.system_prompt.assert_called_once()


@pytest.mark.parametrize('fault', [None, 'bad-point', 'wrong-kind', 'extra-field',
                                 'greeter', 'duplicate-result', 'after-result', 'truncated', 'uncertain'])
def test_streamed_prompt_input_is_narrow_ordered_and_restores_command_parser(fault):
    operation = 'gdm-list' if fault == 'greeter' else 'standard-system-prompt'
    prompt = {'event': 'system-prompt', 'kind': 'login-keyring', 'pointer': {'x': 200, 'y': 330}}
    if fault == 'bad-point': prompt['pointer']['x'] = True
    if fault == 'wrong-kind': prompt['kind'] = 'polkit'
    if fault == 'extra-field': prompt['secret'] = 'must-refuse'
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
    values = [prompt, result]
    if fault == 'duplicate-result': values.append(result)
    if fault == 'after-result': values.reverse()
    raw = b''.join(json.dumps(value).encode() + b'\n' for value in values)
    if fault == 'truncated': raw = raw[:-2]
    previous = Mock()
    commands = SimpleNamespace(progress=previous)
    def call(*_, on_output, **__):
        commands.progress = on_output
        # Exercise arbitrary SSH output chunk boundaries.
        for offset in range(0, len(raw), 13): commands.progress(raw[offset:offset + 13])
        return raw
    def cancel(_):
        assert commands.progress is previous
        if fault == 'uncertain': raise RuntimeError('uncertain pointer')
    handler = Mock(side_effect=cancel)
    session = UiObservations(SimpleNamespace(commands=commands, call=call), system_prompt=handler)
    if fault:
        with pytest.raises((EvidenceError, RuntimeError)):
            session.observe(operation)
    else:
        assert session.observe(operation)['system_prompts'] == [
            {'kind': 'login-keyring', 'action': 'cancel-click'}]
    assert handler.call_count == (0 if fault in ('bad-point', 'wrong-kind', 'extra-field', 'greeter',
                                                'after-result') else 1)
    assert commands.progress is previous
