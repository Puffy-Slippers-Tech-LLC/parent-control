"""Functional GUI selection tolerates decoration but refuses unusable controls."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from accessible_ui import AccessibleUI, UiError
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
        SHOWING='showing', VISIBLE='visible', SENSITIVE='sensitive', DEFUNCT='defunct')), timeout=0)


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


def test_dead_unrelated_subtree_does_not_hide_live_control():
    dead = Node('dead')
    dead.get_name = Mock(side_effect=LookupError('disconnected'))
    button = Node('About', 'button')
    ui = ui_for(Node(children=[dead, button]))
    ui.query_errors = (LookupError,)
    assert ui.target('About', ('button',)) is button


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


@pytest.mark.parametrize('keys,valid', [
    (['home'], True), (['home', 'down', 'down'], True),
    ([], False), (['down'], False), (['home', 'ret'], False),
    (['home', 'alt-f4'], False), (['home'] + ['down'] * 32, False),
])
def test_guest_list_navigation_is_bounded_to_customer_arrow_keys(keys, valid):
    result = {'operation': 'child-picker-opened', 'outcome': 'passed', 'interface': 'AT-SPI',
              'navigation': keys}
    session = UiObservations(SimpleNamespace(call=Mock(return_value=json.dumps(result).encode())))
    if valid:
        assert session.observe('child-picker-opened')['navigation'] == keys
    else:
        with pytest.raises(EvidenceError, match='ui:navigation'):
            session.observe('child-picker-opened')


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
