"""Functional GUI selection tolerates decoration but refuses unusable controls."""

import json
import copy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui
from accessible_ui import (KIOSK_SESSION_OPERATIONS, PARENT_APPLICATION, UiError,
                           greeter_account, session_environment)
from private_artifacts import EvidenceError
from ui_observations import UiObservations
from tests.support.accessible_ui import Node, TEST_PROMPT_CONTRACTS, ui_for


GDM_CONTROLS = {
    'account-list': 'test-gdm-account-list',
    'account-choice::parent': 'test-gdm-account-parent',
    'account-choice::other-parent': 'test-gdm-account-other-parent',
    'account-choice::child': 'test-gdm-account-child',
    'account-choice::other-child': 'test-gdm-account-other-child',
    'account-choice::station': 'test-gdm-account-station',
    'selected-recipient': 'test-gdm-recipient',
    'password': 'test-gdm-password',
    'submit': 'test-gdm-submit', 'cancel': 'test-gdm-cancel',
    'session-chooser': 'test-gdm-session-chooser',
    'session-choice::<provider-session-id>': 'test-gdm-session-choice',
}
GDM_CONTRACTS = {'gdm': {'application_id': 'test-gdm-application', 'surfaces': {
    'greeter': ('test-gdm-greeter', GDM_CONTROLS)}, 'blocked_consumers': ()}}
KEYRING_CONTROLS = {
    'recipient': 'test-keyring-recipient', 'secret': 'test-keyring-secret',
    'confirm': 'test-keyring-confirm', 'cancel': 'test-keyring-cancel',
}
KEYRING_CONTRACTS = {'gcr-keyring-prompter': {
    'application_id': 'test-keyring-application', 'surfaces': {
        'keyring': ('test-keyring-dialog', KEYRING_CONTROLS)}, 'blocked_consumers': ()},
    'gnome-shell-polkit-agent': {
        'application_id': 'test-polkit-application', 'surfaces': {
            'polkit': ('test-polkit-dialog', {
                'recipient': 'test-polkit-recipient', 'secret': 'test-polkit-secret',
                'confirm': 'test-polkit-confirm', 'cancel': 'test-polkit-cancel'})},
        'blocked_consumers': ()}}

SEARCH_CONTROLS = {
    'search': 'test-shell-search', 'result::parent': 'test-shell-parent-result',
    'web-suggestion::parent': 'test-shell-web-suggestion',
}
SEARCH_CONTRACTS = copy.deepcopy(TEST_PROMPT_CONTRACTS)
SEARCH_CONTRACTS['gnome-shell'] = {
    'application_id': 'test-shell-application',
    'surfaces': {'app-grid': ('test-shell-app-grid', SEARCH_CONTROLS)},
    'blocked_consumers': (),
}
DOCUMENT_CONTROLS = {'content': 'test-viewer-content', 'close': 'test-viewer-close'}
DOCUMENT_CONTRACTS = copy.deepcopy(TEST_PROMPT_CONTRACTS)
DOCUMENT_CONTRACTS['document-viewer'] = {
    'application_id': 'test-viewer-application',
    'surfaces': {'license-document': ('test-viewer-license', DOCUMENT_CONTROLS)},
    'blocked_consumers': (),
}


@pytest.mark.parametrize('standard', [False, True])
@pytest.mark.parametrize('fault', [None, 'session', 'desktop', 'prompt', 'submission'])
def test_direct_parent_command_requires_safe_entry_and_never_replays(monkeypatch, standard, fault):
    ui = ui_for(Node())
    session = Mock(side_effect=UiError('session') if fault == 'session' else None)
    monkeypatch.setattr(accessible_ui, 'require_active_launch_session', session)
    ui.desktop_result = Mock(side_effect=UiError('desktop') if fault == 'desktop' else None)
    ui.handle_system_prompt = Mock(side_effect=UiError('prompt') if fault == 'prompt' else None)
    submit = Mock(side_effect=TimeoutError() if fault == 'submission' else None)
    monkeypatch.setattr(accessible_ui.subprocess, 'run', submit)
    if fault:
        with pytest.raises((UiError, TimeoutError)):
            ui.launch_parent_command(standard=standard)
    else:
        ui.launch_parent_command(standard=standard)
    if fault not in ('session', 'desktop', 'prompt'):
        submit.assert_called_once_with([
            '/usr/bin/systemd-run', '--user', '--quiet', '--collect',
            '--service-type=exec', '/usr/bin/oh-no-parent-control-parent',
        ], stdin=accessible_ui.subprocess.DEVNULL, capture_output=True, check=True, timeout=15)
        with pytest.raises(UiError, match='uncertain-input'):
            ui.launch_parent_command(standard=standard)
        assert submit.call_count == 1
    else:
        submit.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'session', 'desktop', 'prompt', 'submission'])
def test_direct_child_command_requires_safe_entry_and_never_replays(monkeypatch, fault):
    ui = ui_for(Node())
    session = Mock(side_effect=UiError('session') if fault == 'session' else None)
    monkeypatch.setattr(accessible_ui, 'require_active_launch_session', session)
    ui.desktop_result = Mock(side_effect=UiError('desktop') if fault == 'desktop' else None)
    ui.handle_system_prompt = Mock(side_effect=UiError('prompt') if fault == 'prompt' else None)
    submit = Mock(side_effect=TimeoutError() if fault == 'submission' else None)
    monkeypatch.setattr(accessible_ui.subprocess, 'run', submit)
    if fault:
        with pytest.raises((UiError, TimeoutError)):
            ui.run('child-command-launch', '')
    else:
        assert ui.run('child-command-launch', '') == {
            'operation': 'child-command-launch', 'outcome': 'passed', 'interface': 'AT-SPI'}
    if fault not in ('session', 'desktop', 'prompt'):
        submit.assert_called_once_with([
            '/usr/bin/systemd-run', '--user', '--quiet', '--collect',
            '--service-type=exec', '/usr/bin/oh-no-parent-control-child',
        ], stdin=accessible_ui.subprocess.DEVNULL, capture_output=True, check=True, timeout=15)
        with pytest.raises(UiError, match='uncertain-input'):
            ui.run('child-command-launch', '')
        assert submit.call_count == 1
    else:
        submit.assert_not_called()
    if fault != 'session':
        ui.desktop_result.assert_called_once_with(accessible_ui.EXISTING_CHILD, 'success')


@pytest.mark.parametrize('fault', [None, 'root', 'wrong-euid', 'foreign-user', 'remote',
                                   'inactive', 'wrong-seat', 'tty', 'duplicate', 'missing'])
def test_direct_parent_launch_requires_one_active_local_graphical_user(monkeypatch, fault):
    monkeypatch.setattr(accessible_ui.os, 'getuid', lambda: 0 if fault == 'root' else 1001)
    monkeypatch.setattr(accessible_ui.os, 'geteuid', lambda: 0 if fault in ('root', 'wrong-euid') else 1001)
    props = {'User': '1001', 'Active': 'yes', 'Remote': 'no', 'Class': 'user',
             'Type': 'wayland', 'Seat': 'seat0'}
    for kind, key, value in [('foreign-user', 'User', '1002'), ('remote', 'Remote', 'yes'),
                             ('inactive', 'Active', 'no'), ('wrong-seat', 'Seat', 'seat1'),
                             ('tty', 'Type', 'tty')]:
        if fault == kind:
            props[key] = value
    def call(argv, **kwargs):
        if argv[1] == 'list-sessions':
            value = '' if fault == 'missing' else '1 1001 fixture seat0\n'
            if fault == 'duplicate':
                value += '2 1001 fixture seat0\n'
        else:
            value = '\n'.join(key + '=' + value for key, value in props.items())
        return SimpleNamespace(stdout=value)
    monkeypatch.setattr(accessible_ui.subprocess, 'run', call)
    if fault:
        with pytest.raises(UiError):
            accessible_ui.require_active_launch_session()
    else:
        accessible_ui.require_active_launch_session()


@pytest.mark.parametrize('fault', [None, 'denial', 'management', 'stale', 'incomplete'])
def test_direct_denial_close_requires_complete_absence_and_public_desktop(fault):
    root = Node(children=[Node(identity='parent-access-denied-window')]
                if fault == 'denial' else [Node(identity='parent-window')]
                if fault == 'management' else [Node(states=('defunct',))]
                if fault == 'stale' else [])
    ui = ui_for(root)
    ui.desktop_result = Mock()
    if fault == 'incomplete':
        root.get_child_count = Mock(side_effect=LookupError())
    if fault in ('stale', 'incomplete'):
        with pytest.raises((UiError, LookupError)):
            ui.parent_denial_closed()
    else:
        assert ui.parent_denial_closed() == (fault is None)
    ui.desktop_result.assert_called_once_with(accessible_ui.EXISTING_CHILD, 'success')


def parent_toggle_ui(*, states=('showing', 'visible', 'sensitive')):
    toggle = Node('Screen time limit', 'switch', states=states,
                  identity='parent-screen-limit-toggle')
    root = Node('Oh No! Parent Control', identity='parent-window', children=[toggle])
    return ui_for(root), root, toggle


def parent_save_ui(*, enabled=True, controls_enabled=True, child_uid=1001):
    control_states = ['showing', 'visible']
    if controls_enabled:
        control_states.append('sensitive')
    toggle_states = [*control_states, *(['checked'] if enabled else [])]
    allowance_states = [
        'showing', 'visible',
        *(['sensitive'] if enabled and controls_enabled else []),
    ]
    selected = Node(
        '', 'panel', identity=f'parent-child-selected-{child_uid}',
        children=[Node('Riley (Child)', 'label')])
    picker = Node(
        'Selected child', 'button', states=control_states,
        identity='parent-child-selector', children=[selected])
    toggle = Node(
        'Screen time limit', 'switch', states=toggle_states,
        identity='parent-screen-limit-toggle')
    allowance = Node(
        '30 minutes', 'button', states=allowance_states,
        identity='parent-daily-limit-selector')
    root = Node(
        'Oh No! Parent Control', identity='parent-window',
        children=[picker, toggle, allowance])
    return ui_for(root), root, picker, toggle, allowance


def test_owned_lookup_reads_each_subtree_once_and_reacquires_after_transition():
    ui, root, toggle = parent_toggle_ui()
    toggle.get_attributes = Mock(wraps=toggle.get_attributes)
    toggle.get_accessible_id = Mock(wraps=toggle.get_accessible_id)
    original_nodes = ui.nodes
    ui.nodes = Mock(wraps=original_nodes)
    assert ui.find_id('parent-screen-limit-toggle', root=root) is toggle
    assert ui.nodes.call_count == 1
    toggle.get_attributes.assert_called_once_with()
    toggle.get_accessible_id.assert_called_once_with()
    replacement = Node(identity='parent-screen-limit-toggle')
    root.children[:] = [replacement]
    replacement.parent = root
    ui.nodes.reset_mock()
    assert ui.find_id('parent-screen-limit-toggle', root=root) is replacement
    assert ui.nodes.call_count == 1


def test_explicit_toggle_activates_once_and_reads_a_fresh_result():
    ui, root, toggle = parent_toggle_ui()
    ui.nodes = Mock(wraps=ui.nodes)
    toggle.get_accessible_id = Mock(wraps=toggle.get_accessible_id)
    replacement = Node('Screen time limit', 'switch',
                       states=('showing', 'visible', 'sensitive', 'checked'),
                       identity='parent-screen-limit-toggle')

    def activate(_index):
        root.children[:] = [replacement]
        replacement.parent = root
        return True

    toggle.action.do_action.side_effect = activate
    assert ui.set_toggle('parent-screen-limit-toggle', True, root=root) == {
        'state': True, 'activated': True}
    toggle.action.do_action.assert_called_once_with(0)
    # One complete observation before input, one fresh observation afterward;
    # prompt/ownership/target checks share each observation's captured IDs.
    assert ui.nodes.call_count == 2
    toggle.get_accessible_id.assert_called_once_with()


def test_explicit_toggle_already_current_reads_disabled_setting_without_input():
    ui, root, toggle = parent_toggle_ui(states=('showing', 'visible'))
    assert ui.set_toggle('parent-screen-limit-toggle', False, root=root) == {
        'state': False, 'activated': False}
    toggle.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['hidden', 'missing', 'wrong-control'])
def test_explicit_toggle_refuses_unqualified_or_hidden_input(fault):
    states = ('sensitive',) if fault == 'hidden' else ('showing', 'visible', 'sensitive')
    ui, root, toggle = parent_toggle_ui(states=states)
    if fault == 'missing':
        root.children.clear()
    identity = 'parent-legend-toggle' if fault == 'wrong-control' else toggle.identity
    with pytest.raises(UiError, match='ui:(?:toggle-binding|unusable-target)'):
        ui.set_toggle(identity, True, root=root)
    toggle.action.do_action.assert_not_called()


@pytest.mark.parametrize('retained', [True, False])
def test_hidden_toggle_qualification_handles_retained_or_omitted_stack_pages(retained):
    ui, root, toggle = parent_toggle_ui()
    ui.parent = Mock(return_value=root)

    def page(identity):
        if identity == 'parent-page-app-limits':
            toggle.states.discard('visible')
            if not retained:
                root.children.clear()
        else:
            assert identity == 'parent-page-screen-limits'
            toggle.states.add('visible')
            root.children[:] = [toggle]

    ui.activate_id = Mock(side_effect=page)
    assert ui.parent_toggle_operation('parent-toggle-hidden-refused') == {
        'refusal': 'hidden-control', 'state': False}
    toggle.action.do_action.assert_not_called()


def test_explicit_toggle_never_replays_an_uncertain_or_unobserved_action():
    ui, root, toggle = parent_toggle_ui()
    with pytest.raises(UiError, match='ui:timeout:toggle-state'):
        ui.set_toggle('parent-screen-limit-toggle', True, root=root)
    toggle.action.do_action.assert_called_once_with(0)


@pytest.mark.parametrize('enabled', [True, False])
def test_parent_save_snapshot_requires_terminal_control_states(enabled):
    ui, _root, _picker, _toggle, _allowance = parent_save_ui(enabled=enabled)
    assert ui.parent_save_snapshot(accessible_ui.CHILD, enabled) == {
        'child': 'fixture-child', 'result': 'saved', 'limit_enabled': enabled,
        'child_selector_enabled': True, 'toggle_enabled': True,
        'allowance_enabled': enabled,
    }


def test_parent_save_snapshot_refuses_the_wrong_child_without_input():
    ui, _root, _picker, toggle, _allowance = parent_save_ui()
    with pytest.raises(UiError, match='ui:wrong-child'):
        ui.parent_save_snapshot(accessible_ui.EXISTING_CHILD, True)
    assert ui.parent_save_operation('parent-save-wrong-child-refused') == {
        'refusal': 'wrong-child'}
    toggle.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'wrong-label', 'missing-label', 'duplicate-label',
                                  'label-outside-selection', 'wrong-uid'])
def test_parent_save_verifies_uid_and_nested_label_in_one_snapshot(fault):
    ui, _root, picker, toggle, _allowance = parent_save_ui()
    selected = picker.children[0]
    label = selected.children[0]
    if fault == 'wrong-label':
        label.name = accessible_ui.EXISTING_CHILD
    elif fault == 'missing-label':
        selected.children.clear()
    elif fault == 'duplicate-label':
        duplicate = Node(accessible_ui.CHILD, 'label')
        duplicate.parent = selected
        selected.children.append(duplicate)
    elif fault == 'label-outside-selection':
        selected.children.clear()
        label.parent = picker
        picker.children.append(label)
    elif fault == 'wrong-uid':
        selected.identity = 'parent-child-selected-1002'
    ui.nodes = Mock(wraps=ui.nodes)
    if fault:
        with pytest.raises(UiError, match='ui:wrong-child'):
            ui.parent_save_snapshot(accessible_ui.CHILD, True)
    else:
        assert ui.parent_save_snapshot(accessible_ui.CHILD, True)['result'] == 'saved'
    assert ui.nodes.call_count == 1
    toggle.action.do_action.assert_not_called()


@pytest.mark.parametrize('identity', [
    'feedback-dialog', 'error-report-unavailable-dialog',
])
def test_parent_save_snapshot_refuses_a_visible_error_report_from_the_same_snapshot(identity):
    ui, root, _picker, toggle, _allowance = parent_save_ui()
    report = Node('Error report', 'dialog', identity=identity)
    application = root.parent
    application.children.append(report)
    report.parent = application
    ui.nodes = Mock(wraps=ui.nodes)

    with pytest.raises(UiError, match='ui:parent-save-error-report'):
        ui.parent_save_snapshot(accessible_ui.CHILD, True)

    assert ui.nodes.call_count == 1
    toggle.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['saving', 'duplicate', 'stale'])
def test_parent_save_snapshot_refuses_incomplete_or_unsettled_results(fault):
    ui, root, picker, toggle, _allowance = parent_save_ui(
        controls_enabled=fault != 'saving')
    if fault == 'duplicate':
        duplicate = Node(
            'Screen time limit', 'switch',
            states=('showing', 'visible', 'sensitive', 'checked'),
            identity='parent-screen-limit-toggle')
        duplicate.parent = root
        root.children.append(duplicate)
    elif fault == 'stale':
        picker.states.add('defunct')
    with pytest.raises(UiError):
        ui.parent_save_snapshot(accessible_ui.CHILD, True)
    toggle.action.do_action.assert_not_called()


@pytest.mark.parametrize('operation', [
    'parent-toggle-enabled', 'parent-toggle-disabled', 'parent-toggle-current',
    'parent-toggle-wrong-refused', 'parent-toggle-hidden-refused',
])
def test_toggle_observation_accepts_only_its_fixed_sanitized_result(operation):
    from accessible_ui import TOGGLE_OPERATIONS
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI',
              'toggle': TOGGLE_OPERATIONS[operation]}
    session = UiObservations(SimpleNamespace(call=Mock(
        return_value=(json.dumps(result) + '\n').encode())))
    assert session.observe(operation)['toggle'] == TOGGLE_OPERATIONS[operation]
    result['toggle'] = {'state': True, 'activated': False}
    session.transport.call.return_value = (json.dumps(result) + '\n').encode()
    with pytest.raises(EvidenceError, match='ui:toggle-response'):
        session.observe(operation)


@pytest.mark.parametrize('operation', accessible_ui.PARENT_SAVE_OPERATIONS)
def test_parent_save_observation_accepts_only_its_fixed_sanitized_result(operation):
    expected = accessible_ui.PARENT_SAVE_OPERATIONS[operation]
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI',
              'save': expected}
    session = UiObservations(SimpleNamespace(call=Mock(
        return_value=(json.dumps(result) + '\n').encode())))
    assert session.observe(operation)['save'] == expected
    result['save'] = {'result': 'saved'}
    session.transport.call.return_value = (json.dumps(result) + '\n').encode()
    with pytest.raises(EvidenceError, match='ui:parent-save-response'):
        session.observe(operation)


def search_ui(surface, *, outside=()):
    surface.identity = 'test-shell-app-grid'
    application = Node(identity='test-shell-application', children=[surface])
    return ui_for(Node(children=[*outside, application]), provider_contracts=SEARCH_CONTRACTS)


def queried_search_ui(*results):
    field = Node('Oh No! Parent Control', 'entry', identity=SEARCH_CONTROLS['search'],
                 states=('showing', 'visible', 'sensitive', 'editable'))
    field.get_text_iface = lambda: field
    ui = search_ui(Node(children=[field, *results]))
    ui.api.Text = SimpleNamespace(get_character_count=lambda node: len(node.name),
                                  get_text=lambda node, start, end: node.name[start:end])
    return ui


def document_ui(product_root, *, document=None):
    children = [Node(identity=PARENT_APPLICATION, children=[product_root])]
    if document is not None:
        document.identity = DOCUMENT_CONTROLS['content']
        close = Node('Close', 'push button', identity=DOCUMENT_CONTROLS['close'])
        surface = Node(identity='test-viewer-license', children=[document, close],
                       states=('showing', 'visible', 'sensitive', 'active'))
        children.append(Node(identity='test-viewer-application', children=[surface]))
    return ui_for(Node(children=children), provider_contracts=DOCUMENT_CONTRACTS)


def action_ui(root, identity):
    """Give generic action tests explicit provider/application/surface ownership."""
    contracts = copy.deepcopy(TEST_PROMPT_CONTRACTS)
    contracts['action-fixture'] = {'application_id': 'test-action-application',
        'surfaces': {'main': ('test-action-surface', {'action': identity})}}
    return ui_for(Node(identity='test-action-application', children=[
        Node(identity='test-action-surface', children=[root])]), provider_contracts=contracts)


@pytest.mark.parametrize('fault', ['missing-id', 'unregistered', 'wrong-owner', 'duplicate', 'stale'])
@pytest.mark.parametrize('named', [False, True])
def test_actions_reacquire_public_provider_ownership_before_input(fault, named):
    button = Node(identity='test-action')
    ui = action_ui(button, 'test-action')
    surface = ui.api.get_desktop(0).children[0]
    if fault == 'missing-id':
        button.identity = ''
    elif fault == 'unregistered':
        button.identity = 'unregistered'
    elif fault == 'wrong-owner':
        surface.children.clear()
        ui.api.get_desktop(0).children.append(button)
    elif fault == 'duplicate':
        surface.children.append(Node(identity='test-action'))
    else:
        surface.children[:] = [Node(identity='test-action')]
    with pytest.raises(UiError):
        ui.activate_named(button, 'click') if named else ui.activate(button)
    button.action.do_action.assert_not_called()


@pytest.mark.parametrize('operation', ['search', 'greeter'])
@pytest.mark.parametrize('failure', ['exception', 'refused', 'unobserved'])
def test_provider_focus_is_not_replayed_after_uncertain_result(operation, failure):
    if operation == 'search':
        node = Node(identity=SEARCH_CONTROLS['search'])
        ui = search_ui(Node(children=[node]))
        focus = ui.focus_search_field
    else:
        node = gdm_row('Jamie (Parent)', 'account-choice::parent')
        ui = gdm_ui(rows=[node])
        focus = lambda: ui.greeter_navigation('Jamie (Parent)')
    node.component.grab_focus.side_effect = (
        LookupError('uncertain') if failure == 'exception' else None)
    node.component.grab_focus.return_value = failure != 'refused'
    with pytest.raises((UiError, LookupError)):
        focus()
    with pytest.raises(UiError, match='uncertain-input'):
        focus()
    node.component.grab_focus.assert_called_once_with()


def gdm_ui(*, rows=(), recipient=None, field=None, list_showing=True):
    account_list = Node(identity=GDM_CONTROLS['account-list'], children=rows,
                        states=('showing', 'visible', 'sensitive') if list_showing
                        else ('visible', 'sensitive'))
    children = [account_list]
    if recipient is not None:
        recipient.identity = GDM_CONTROLS['selected-recipient']
        children.append(recipient)
    if field is not None:
        field.identity = GDM_CONTROLS['password']
        children.append(field)
    surface = Node(identity='test-gdm-greeter', children=children)
    application = Node(identity='test-gdm-application', children=[surface])
    ui = ui_for(application, provider_contracts=GDM_CONTRACTS)
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: 0,
                                  get_text=Mock(side_effect=AssertionError('password text read')))
    return ui


def gdm_row(name, identity, *, focused=False, showing=True):
    states = {'visible', 'sensitive'}
    if showing: states.add('showing')
    if focused: states.add('focused')
    return Node(name, 'push button', identity=GDM_CONTROLS[identity], states=states)


def semantic_gdm_ui(*, rows=(), recipient=None, field=None, applications=()):
    children = list(rows)
    if recipient is not None:
        children.append(recipient)
    if field is not None:
        children.append(field)
    shell = Node('GNOME Shell', 'application', children=children)
    root = Node(role='desktop frame', children=[shell, *applications])
    ui = ui_for(root)
    ui.api.Text = SimpleNamespace(
        get_character_count=Mock(side_effect=AssertionError('password length read')),
        get_text=Mock(side_effect=AssertionError('password text read')),
    )
    return ui, shell


def semantic_gdm_rows(*, focused=None, other=False, standard=False):
    parent = Node('Jamie (Parent)', 'push button')
    station = Node('Oh No! Parent Control', 'push button')
    if focused == 'parent': parent.states.add('focused')
    if focused == 'station': station.states.add('focused')
    if not other and not standard:
        return parent, station
    rows = [parent]
    other_parent = Node('Casey (Parent)', 'push button')
    if focused == 'other-parent': other_parent.states.add('focused')
    if other:
        rows.append(other_parent)
    standard_user = Node('Jordan (Child)', 'push button')
    if focused == 'standard': standard_user.states.add('focused')
    if standard:
        rows.append(standard_user)
    return (*rows, station)


def keyring_ui(*, fault=None, root_children=()):
    recipient = Node('Login keyring', 'label', identity=KEYRING_CONTROLS['recipient'])
    secret = Node('', 'password text', identity=KEYRING_CONTROLS['secret'],
                  states=('showing', 'visible', 'sensitive', 'focused'))
    secret.get_text_iface = lambda: secret
    confirm = Node('Unlock', 'push button', identity=KEYRING_CONTROLS['confirm'])
    cancel = Node('Cancel', 'push button', identity=KEYRING_CONTROLS['cancel'])
    controls = {'recipient': recipient, 'secret': secret, 'confirm': confirm, 'cancel': cancel}
    if fault == 'disabled': cancel.states.remove('sensitive')
    if fault == 'hidden': cancel.states.remove('showing')
    if fault == 'unfocused': secret.states.remove('focused')
    if fault == 'unmasked': secret.role = 'text'
    children = [control for name, control in controls.items() if fault != 'missing-' + name]
    dialog = Node(identity='test-keyring-dialog', children=children)
    application = Node(identity='test-keyring-application', children=[dialog])
    root = Node(role='desktop frame', children=[*root_children, application])
    ui = ui_for(root, provider_contracts=KEYRING_CONTRACTS)
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: 1 if fault == 'nonempty' else 0,
                                  get_text=Mock(side_effect=AssertionError('secret read')))
    return ui, dialog, controls


def semantic_keyring_ui(*, fault=None):
    field = Node('', 'password text', states=('showing', 'visible', 'sensitive', 'focused'))
    field.get_text_iface = lambda: field
    field.get_child_count = Mock(side_effect=AssertionError('secret traversed'))
    cancel = Node('Cancel', 'push button')
    controls = [field, cancel]
    if fault == 'duplicate-cancel': controls.append(Node('Cancel', 'push button'))
    if fault == 'unfocused': field.states.remove('focused')
    if fault == 'hidden': cancel.states.remove('showing')
    if fault == 'disabled': cancel.states.remove('sensitive')
    if fault == 'unmasked': field.role = 'text'
    dialog = Node('Unlock Login Keyring', 'dialog', children=controls)
    dialogs = [dialog]
    if fault == 'extra-modal': dialogs.append(Node('Unexpected', 'dialog'))
    owner = Node('gcr Prompter', 'application', children=dialogs,
                 states=('defunct',) if fault == 'stale-owner' else ())
    if fault == 'wrong-owner': owner.name = 'Unknown Agent'
    if fault == 'wrong-dialog': dialog.name = 'Authentication Required'
    shell = Node('GNOME Shell', 'application', children=[Node('Activities', 'toggle button')])
    root = Node(role='desktop frame', children=[shell, owner])
    ui = ui_for(root, provider_contracts={})
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: 1 if fault == 'nonempty' else 0,
                                  get_text=Mock(side_effect=AssertionError('secret read')))
    return ui, root, owner, field, cancel


@pytest.mark.parametrize('fault', ['duplicate-cancel', 'extra-modal', 'unfocused', 'hidden', 'disabled',
                                   'unmasked', 'wrong-owner', 'stale-owner', 'wrong-dialog', 'nonempty'])
def test_semantic_keyring_cancel_refuses_unsafe_target_without_input(fault):
    ui, _root, _owner, field, cancel = semantic_keyring_ui(fault=fault)
    with pytest.raises(UiError):
        ui.keyring_cancel_target()
    cancel.action.do_action.assert_not_called()
    field.get_child_count.assert_not_called()
    ui.api.Text.get_text.assert_not_called()


def test_semantic_keyring_cancel_requires_a_real_visible_prompt():
    ui, root, owner, _field, cancel = semantic_keyring_ui()
    root.children.remove(owner)
    ui.standard_shell_desktop = Mock()
    with pytest.raises(UiError, match='timeout:keyring-prompt'):
        ui.cancel_keyring_prompt()
    cancel.action.do_action.assert_not_called()
    ui.standard_shell_desktop.assert_not_called()


def test_semantic_keyring_cancel_observes_disappearance_before_desktop():
    ui, root, owner, field, cancel = semantic_keyring_ui()
    cancel.action.do_action.side_effect = lambda _: root.children.remove(owner) or True
    ui.standard_shell_desktop = Mock(return_value=True)
    ui.cancel_keyring_prompt()
    cancel.action.do_action.assert_called_once_with(0)
    ui.standard_shell_desktop.assert_called_once_with(no_prompt=True)
    field.get_child_count.assert_not_called()
    ui.api.Text.get_text.assert_not_called()


@pytest.mark.parametrize('same_provider', [False, True])
def test_semantic_keyring_cancel_refuses_replacement_without_replay(same_provider):
    ui, root, owner, _field, cancel = semantic_keyring_ui()
    replacement = Node('gcr Prompter' if same_provider else 'Unknown Agent',
                       'application', children=[
        Node('Unlock Login Keyring' if same_provider else 'Authentication Required',
             'dialog', children=[Node('', 'password text')])])
    def replace(_index):
        root.children.remove(owner)
        replacement.parent = root
        root.children.append(replacement)
        return True
    cancel.action.do_action.side_effect = replace
    ui.standard_shell_desktop = Mock()
    with pytest.raises(UiError, match='keyring-prompt-replaced'):
        ui.cancel_keyring_prompt()
    cancel.action.do_action.assert_called_once_with(0)
    ui.standard_shell_desktop.assert_not_called()


def test_semantic_keyring_cancel_refuses_incomplete_absence():
    ui, root, owner, _field, cancel = semantic_keyring_ui()
    def incomplete(_index):
        root.children.remove(owner)
        root.children.append(None)
        return True
    cancel.action.do_action.side_effect = incomplete
    ui.standard_shell_desktop = Mock()
    with pytest.raises(UiError, match='timeout:keyring-dismissed'):
        ui.cancel_keyring_prompt()
    cancel.action.do_action.assert_called_once_with(0)
    ui.standard_shell_desktop.assert_not_called()


def test_semantic_keyring_cancel_refuses_queued_prompt_during_desktop_readback():
    ui, root, owner, _field, cancel = semantic_keyring_ui()
    cancel.action.do_action.side_effect = lambda _: root.children.remove(owner) or True
    original = ui.system_prompt_kind
    reads = 0
    def observe(**kwargs):
        nonlocal reads
        reads += 1
        # Initial challenge, observed disappearance, then a queued challenge
        # arrives before the independent desktop observation can succeed.
        if reads == 3:
            return 'keyring'
        return original(**kwargs)
    ui.system_prompt_kind = observe
    with pytest.raises(UiError, match='fresh-desktop-prompt'):
        ui.cancel_keyring_prompt()
    cancel.action.do_action.assert_called_once_with(0)


def test_semantic_keyring_cancel_latches_uncertain_action():
    ui, _root, _owner, _field, cancel = semantic_keyring_ui()
    cancel.action.do_action.return_value = False
    ui.standard_shell_desktop = Mock()
    with pytest.raises(UiError, match='action-refused'):
        ui.cancel_keyring_prompt()
    assert ui.input_uncertain
    with pytest.raises(UiError, match='uncertain-input'):
        ui.cancel_keyring_prompt()
    cancel.action.do_action.assert_called_once_with(0)
    ui.standard_shell_desktop.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'wrong-account', 'no-prompt', 'unfocused', 'list-remains'])
def test_gdm_selection_requires_independent_identity_prompt_and_focus(fault):
    recipient = Node('Other Parent' if fault == 'wrong-account' else 'Jamie (Parent)', 'label')
    field = Node('Password', 'password text', states=('showing', 'visible', 'sensitive', 'focused'))
    field.get_text_iface = Mock(side_effect=AssertionError('password read'))
    field.get_child_count = Mock(side_effect=AssertionError('password traversed'))
    if fault == 'unfocused': field.states.remove('focused')
    ui = gdm_ui(recipient=recipient, field=None if fault == 'no-prompt' else field,
                list_showing=fault == 'list-remains')
    if fault:
        with pytest.raises((UiError, LookupError)):
            ui.run('gdm-select-parent', '')
    else:
        assert ui.run('gdm-select-parent', '')['outcome'] == 'passed'
    field.get_text_iface.assert_not_called()
    field.get_child_count.assert_not_called()


@pytest.mark.parametrize('index', [0, 1, 3])
def test_gdm_navigation_uses_target_id_not_public_order_and_independently_requires_focus(index):
    button = gdm_row('Jamie (Parent)', 'account-choice::parent')
    rows = [Node('unrelated-' + str(value), 'push button', identity='unrelated-' + str(value))
            for value in range(3)]
    rows.insert(index, button)
    ui = gdm_ui(rows=rows)
    assert ui.run('gdm-list', '')['focused'] is True
    assert button.component.grab_focus.call_count == 1
    assert ui.run('gdm-focused', '')['outcome'] == 'passed'
    assert all(row.action.do_action.call_count == 0 for row in rows)


def test_gdm_nonsecret_adapter_focuses_unique_ordinary_and_station_rows():
    parent, station = semantic_gdm_rows()
    ui, _shell = semantic_gdm_ui(rows=[station, Node('Decoration', 'label'), parent])
    assert ui.run('gdm-list', '')['focused'] is True
    assert ui.run('gdm-focused', '')['outcome'] == 'passed'
    assert ui.run('gdm-station-list', '')['focused'] is True
    assert ui.run('gdm-station-focused', '')['outcome'] == 'passed'
    parent.action.do_action.assert_not_called()
    station.action.do_action.assert_not_called()


def test_gdm_product_free_adapter_focuses_declared_parent_without_station():
    parent, _station = semantic_gdm_rows()
    ui, _shell = semantic_gdm_ui(rows=[parent])
    assert ui.run('gdm-product-free-list', '')['focused'] is True
    assert ui.run('gdm-product-free-focused', '')['outcome'] == 'passed'
    parent.component.grab_focus.assert_called_once_with()
    parent.action.do_action.assert_not_called()


def test_gdm_product_free_and_installed_bindings_reject_the_opposite_fixture_shape():
    parent, station = semantic_gdm_rows()
    product_free, _shell = semantic_gdm_ui(rows=[parent, station])
    with pytest.raises(UiError, match='gdm-account-cardinality'):
        product_free.run('gdm-product-free-list', '')
    parent.component.grab_focus.assert_not_called()

    parent, _station = semantic_gdm_rows()
    installed, _shell = semantic_gdm_ui(rows=[parent])
    with pytest.raises(UiError, match='gdm-account-cardinality'):
        installed.run('gdm-list', '')
    parent.component.grab_focus.assert_not_called()


def test_gdm_nonsecret_adapter_focuses_the_prepared_wrong_account_by_identity():
    parent, other_parent, station = semantic_gdm_rows(other=True)
    ui, _shell = semantic_gdm_ui(rows=[station, parent, other_parent])
    assert ui.run('gdm-other-list', '')['focused'] is True
    assert ui.run('gdm-other-focused', '')['outcome'] == 'passed'
    other_parent.component.grab_focus.assert_called_once_with()
    parent.component.grab_focus.assert_not_called()
    station.component.grab_focus.assert_not_called()


def test_gdm_nonsecret_adapter_rejects_a_duplicate_prepared_wrong_account():
    parent, other_parent, station = semantic_gdm_rows(other=True)
    ui, _shell = semantic_gdm_ui(rows=[
        parent, other_parent, Node('Casey (Parent)', 'push button'), station])
    with pytest.raises(UiError, match='gdm-account-cardinality'):
        ui.run('gdm-other-list', '')
    other_parent.component.grab_focus.assert_not_called()


def test_gdm_nonsecret_adapter_resolves_and_deduplicates_provider_label_descendants():
    parent_label = Node('Jamie (Parent)', 'label')
    parent = Node('', 'push button', children=[parent_label])
    station_name = Node('Oh No! Parent Control', 'label')
    station_username = Node('oh-no-parent-control', 'label')
    hidden_station_name = Node(
        'Oh No! Parent Control', 'label', states=('visible', 'sensitive'))
    station = Node('', 'push button', children=[
        station_name, station_username, hidden_station_name])
    ui, _shell = semantic_gdm_ui(rows=[station, parent])

    assert ui.run('gdm-list', '')['focused'] is True
    assert ui.run('gdm-focused', '')['outcome'] == 'passed'
    assert ui.run('gdm-station-list', '')['focused'] is True
    assert ui.run('gdm-station-focused', '')['outcome'] == 'passed'
    parent.component.grab_focus.assert_called_once_with()
    station.component.grab_focus.assert_called_once_with()
    for label in (parent_label, station_name, station_username, hidden_station_name):
        label.component.grab_focus.assert_not_called()
        label.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['wrong-owner', 'duplicate-owner', 'duplicate-parent',
                                   'duplicate-station', 'defunct'])
def test_gdm_nonsecret_adapter_rejects_wrong_or_ambiguous_ownership(fault):
    parent, station = semantic_gdm_rows()
    applications = []
    rows = [parent, station]
    if fault == 'wrong-owner':
        rows = []
        applications.append(Node('Unrelated', 'application', children=[parent, station]))
    elif fault == 'duplicate-owner':
        applications.append(Node('gnome-shell', 'application'))
    elif fault == 'duplicate-parent':
        rows.append(Node('Jamie (Parent)', 'push button'))
    elif fault == 'duplicate-station':
        rows.append(Node('oh-no-parent-control', 'push button'))
    else:
        station.states.add('defunct')
    ui, _shell = semantic_gdm_ui(rows=rows, applications=applications)
    with pytest.raises(UiError):
        ui.run('gdm-list', '')
    parent.component.grab_focus.assert_not_called()
    station.component.grab_focus.assert_not_called()


@pytest.mark.parametrize(('fault', 'category', 'matching_nodes', 'matching_rows',
                          'role', 'showing', 'hidden', 'provider_owner', 'other_owner'), [
    ('missing', 'ordinary', 0, 0, None, 0, 0, 0, 0),
    ('duplicate', 'ordinary', 2, 2, 'push button', 2, 0, 2, 0),
    ('hidden', 'ordinary', 1, 0, 'push button', 0, 1, 1, 0),
    ('wrong-role', 'ordinary', 1, 0, 'label', 1, 0, 1, 0),
    ('wrong-owner', 'ordinary', 1, 0, 'push button', 1, 0, 0, 1),
])
def test_gdm_account_cardinality_diagnostic_is_sanitized_and_distinguishes_faults(
        fault, category, matching_nodes, matching_rows, role, showing, hidden,
        provider_owner, other_owner, capsys):
    parent, station = semantic_gdm_rows()
    rows = [parent, station]
    applications = []
    if fault == 'missing':
        rows.remove(parent)
    elif fault == 'duplicate':
        rows.append(Node('Jamie (Parent)', 'push button'))
    elif fault == 'hidden':
        parent.states.remove('showing')
    elif fault == 'wrong-role':
        parent.role = 'label'
    else:
        rows.remove(parent)
        applications.append(Node('Unrelated', 'application', children=[parent]))
    ui, _shell = semantic_gdm_ui(rows=rows, applications=applications)

    with pytest.raises(UiError, match='gdm-account-cardinality'):
        ui.run('gdm-list', '')

    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 1
    diagnostic = json.loads(lines[0])
    assert diagnostic['event'] == 'gdm-account-observation'
    assert diagnostic['owner'] == {'role': 'application', 'showing': True}
    observed = diagnostic['matches'][category]
    assert observed['matching_nodes'] == matching_nodes
    assert observed['matching_rows'] == matching_rows
    assert observed['roles'] == ({} if role is None else {role: matching_nodes})
    assert observed['visibility'] == {'showing': showing, 'hidden': hidden}
    assert observed['ownership'] == {
        'provider-owner': provider_owner, 'other-owner': other_owner}
    assert 'Jamie' not in lines[0]
    assert 'Oh No!' not in lines[0]
    parent.component.grab_focus.assert_not_called()
    station.component.grab_focus.assert_not_called()


def test_gdm_nonsecret_adapter_refuses_stale_focus_without_replay():
    parent, station = semantic_gdm_rows()
    ui, shell = semantic_gdm_ui(rows=[parent, station])

    def replace_after_focus():
        replacement = Node('Jamie (Parent)', 'push button',
                           states=('showing', 'visible', 'sensitive', 'focused'))
        shell.children[0] = replacement
        replacement.parent = shell
        return True

    parent.component.grab_focus.side_effect = replace_after_focus
    with pytest.raises(UiError, match='gdm-stale-focus'):
        ui.run('gdm-list', '')
    parent.component.grab_focus.assert_called_once_with()
    assert ui.input_uncertain is True


def test_gdm_product_free_adapter_refuses_stale_focus_without_replay():
    parent, _station = semantic_gdm_rows()
    ui, shell = semantic_gdm_ui(rows=[parent])

    def replace_after_focus():
        replacement = Node('Jamie (Parent)', 'push button',
                           states=('showing', 'visible', 'sensitive', 'focused'))
        shell.children[0] = replacement
        replacement.parent = shell
        return True

    parent.component.grab_focus.side_effect = replace_after_focus
    with pytest.raises(UiError, match='gdm-stale-focus'):
        ui.run('gdm-product-free-list', '')
    parent.component.grab_focus.assert_called_once_with()
    assert ui.input_uncertain is True


@pytest.mark.parametrize('operation', [
    'gdm-list', 'gdm-select-parent', 'gdm-navigation-returned',
    'gdm-dismissed', 'gdm-returned',
    'gdm-product-free-list', 'gdm-product-free-select-parent',
    'gdm-product-free-returned',
    'gdm-station-wrong-entry-refused',
])
def test_gdm_nonsecret_adapter_rejects_list_and_prompt_overlap(operation):
    parent, station = semantic_gdm_rows()
    recipient = Node('Jamie (Parent)', 'label')
    field = Node('Password', 'password text',
                 states=('showing', 'visible', 'sensitive', 'focused'))
    field.get_child_count = Mock(side_effect=AssertionError('password traversed'))
    field.get_text_iface = Mock(side_effect=AssertionError('password read'))
    ui, _shell = semantic_gdm_ui(
        rows=[parent, station], recipient=recipient, field=field)
    with pytest.raises(UiError, match='gdm-list-prompt-overlap'):
        ui.run(operation, '')
    field.get_child_count.assert_not_called()
    field.get_text_iface.assert_not_called()
    ui.api.Text.get_text.assert_not_called()


@pytest.mark.parametrize('operation', [
    'gdm-navigation-returned', 'gdm-dismissed', 'gdm-returned',
])
def test_gdm_nonsecret_prompt_and_returned_list_never_read_or_submit_a_secret(operation):
    recipient = Node('Jamie (Parent)', 'label')
    field = Node('Password', 'password text',
                 states=('showing', 'visible', 'sensitive', 'focused'))
    field.get_child_count = Mock(side_effect=AssertionError('password traversed'))
    field.get_text_iface = Mock(side_effect=AssertionError('password read'))
    ui, shell = semantic_gdm_ui(recipient=recipient, field=field)
    assert ui.run('gdm-select-parent', '')['outcome'] == 'passed'
    field.get_child_count.assert_not_called()
    field.get_text_iface.assert_not_called()
    field.action.do_action.assert_not_called()
    ui.api.Text.get_character_count.assert_not_called()
    ui.api.Text.get_text.assert_not_called()

    parent, station = semantic_gdm_rows()
    shell.children = [parent, station]
    parent.parent = shell
    station.parent = shell
    assert ui.run(operation, '')['outcome'] == 'passed'
    parent.component.grab_focus.assert_not_called()


def test_gdm_product_free_prompt_and_return_never_read_or_submit_a_secret():
    recipient = Node('Jamie (Parent)', 'label')
    field = Node('Password', 'password text',
                 states=('showing', 'visible', 'sensitive', 'focused'))
    field.get_child_count = Mock(side_effect=AssertionError('password traversed'))
    field.get_text_iface = Mock(side_effect=AssertionError('password read'))
    ui, shell = semantic_gdm_ui(recipient=recipient, field=field)
    assert ui.run('gdm-product-free-select-parent', '')['outcome'] == 'passed'
    field.get_child_count.assert_not_called()
    field.get_text_iface.assert_not_called()
    field.action.do_action.assert_not_called()
    ui.api.Text.get_character_count.assert_not_called()
    ui.api.Text.get_text.assert_not_called()

    parent, _station = semantic_gdm_rows()
    shell.children = [parent]
    parent.parent = shell
    assert ui.run('gdm-product-free-returned', '')['outcome'] == 'passed'
    parent.component.grab_focus.assert_not_called()


@pytest.mark.parametrize('operation', [
    'gdm-parent-recipient', 'gdm-parent-recipient-rechecked',
    'gdm-standard-recipient', 'gdm-standard-recipient-rechecked',
])
@pytest.mark.parametrize('fault', [
    None, 'wrong-recipient', 'duplicate-recipient', 'missing-field', 'duplicate-field',
    'unfocused', 'hidden', 'disabled', 'nonempty', 'unmasked', 'list-visible',
])
def test_semantic_gdm_recipient_requires_one_bound_identity_and_empty_masked_focus(
        operation, fault):
    expected = (accessible_ui.EXISTING_CHILD
                if operation.startswith('gdm-standard-') else accessible_ui.PARENT)
    recipient = Node(
        'Casey (Parent)' if fault == 'wrong-recipient' else expected, 'label')
    field = Node('Password', 'text' if fault == 'unmasked' else 'password text',
                 states=('showing', 'visible', 'sensitive', 'focused'))
    if fault in ('unfocused', 'hidden', 'disabled'):
        field.states.remove({
            'unfocused': 'focused', 'hidden': 'showing', 'disabled': 'sensitive'}[fault])
    field.get_text_iface = lambda: field
    field.get_child_count = Mock(side_effect=AssertionError('password traversed'))
    rows = []
    if fault == 'list-visible':
        rows = list(semantic_gdm_rows())
    ui, shell = semantic_gdm_ui(
        rows=rows, recipient=recipient,
        field=None if fault == 'missing-field' else field)
    if fault == 'duplicate-recipient':
        duplicate = Node(expected, 'label')
        duplicate.parent = shell
        shell.children.append(duplicate)
    if fault == 'duplicate-field':
        duplicate = Node('Other password', 'password text')
        duplicate.parent = shell
        shell.children.append(duplicate)
    ui.api.Text = SimpleNamespace(
        get_character_count=Mock(return_value=1 if fault == 'nonempty' else 0),
        get_text=Mock(side_effect=AssertionError('password text read')),
    )
    if fault is None:
        assert ui.run(operation, '')['outcome'] == 'passed'
    else:
        with pytest.raises(UiError):
            ui.run(operation, '')
    ui.api.Text.get_text.assert_not_called()
    field.get_child_count.assert_not_called()


@pytest.mark.parametrize('operation', [
    'gdm-wrong-recipient-refused', 'gdm-standard-wrong-recipient-refused'])
def test_semantic_wrong_prompt_proves_other_parent_and_refuses_intended_account(operation):
    recipient = Node('Casey (Parent)', 'label')
    field = Node('Password', 'password text',
                 states=('showing', 'visible', 'sensitive', 'focused'))
    field.get_text_iface = lambda: field
    field.get_child_count = Mock(side_effect=AssertionError('password traversed'))
    ui, _shell = semantic_gdm_ui(recipient=recipient, field=field)
    ui.api.Text = SimpleNamespace(
        get_character_count=Mock(return_value=0),
        get_text=Mock(side_effect=AssertionError('password text read')),
    )
    assert ui.run(operation, '')['outcome'] == 'passed'
    ui.api.Text.get_text.assert_not_called()
    field.get_child_count.assert_not_called()


def test_semantic_standard_gdm_route_focuses_only_the_declared_account():
    parent, standard, station = semantic_gdm_rows(standard=True)
    ui, _shell = semantic_gdm_ui(rows=[station, parent, standard])
    assert ui.run('gdm-standard-list', '')['focused'] is True
    assert ui.run('gdm-standard-focused', '')['outcome'] == 'passed'
    standard.component.grab_focus.assert_called_once_with()
    parent.component.grab_focus.assert_not_called()
    station.component.grab_focus.assert_not_called()
    for row in (parent, standard, station):
        row.action.do_action.assert_not_called()


def test_semantic_standard_gdm_route_rejects_duplicate_account_without_input():
    parent, standard, station = semantic_gdm_rows(standard=True)
    ui, _shell = semantic_gdm_ui(rows=[
        parent, standard, Node('Jordan (Child)', 'push button'), station])
    with pytest.raises(UiError, match='gdm-account-cardinality'):
        ui.run('gdm-standard-list', '')
    standard.component.grab_focus.assert_not_called()


def test_partial_gdm_provider_mapping_blocks_before_tree_discovery():
    ui = ui_for(Node(), provider_contracts=GDM_CONTRACTS)
    _surface, controls = ui.provider_contracts['gdm']['surfaces']['greeter']
    controls['submit'] = None
    ui.api.get_desktop = Mock(side_effect=AssertionError('tree read'))
    with pytest.raises(UiError, match='unqualified-provider-control'):
        ui.run('gdm-list', '')
    ui.api.get_desktop.assert_not_called()


@pytest.mark.parametrize('operation', ['gdm-list', 'gdm-dismissed', 'gdm-returned'])
def test_gdm_account_label_cannot_hide_an_undismissed_prompt(operation):
    row = gdm_row('Jamie (Parent)', 'account-choice::parent')
    field = Node('Password', 'password text')
    ui = gdm_ui(rows=[row], field=field)
    with pytest.raises(UiError, match='gdm-prompt-dismissed'):
        ui.run(operation, '')


@pytest.mark.parametrize('fault', ['stale-tree', 'defunct', 'missing-root'])
@pytest.mark.parametrize('surface', ['list', 'prompt'])
def test_gdm_absence_requires_complete_fresh_positive_surface(fault, surface):
    positive = (gdm_row('Jamie (Parent)', 'account-choice::parent') if surface == 'list'
                else Node('Jamie (Parent)', 'label'))
    unrelated = Node('private-canary')
    if fault == 'stale-tree':
        unrelated.get_child_count = Mock(side_effect=LookupError('private-canary'))
    if fault == 'defunct': unrelated.states.add('defunct')
    ui = (gdm_ui(rows=[positive, unrelated]) if surface == 'list'
          else gdm_ui(recipient=positive, field=Node('Password', 'password text'),
                      list_showing=False))
    if surface == 'prompt':
        ui.api.get_desktop(0).children[0].children[0].children.append(unrelated)
    ui.query_errors = (LookupError,)
    if fault == 'missing-root': ui.api.get_desktop = lambda _: None
    with pytest.raises(UiError):
        ui.observe_absence('greeter', 'password' if surface == 'list' else 'account',
                          name='Jamie (Parent)', mode='snapshot')


def test_greeter_collection_order_path_is_retired_before_tree_access():
    ui = ui_for(Node())
    ui.api.get_desktop = Mock(side_effect=AssertionError('tree read'))
    from accessible_ui import GREETER_IDENTITIES
    with pytest.raises(UiError, match='collection-binding'):
        ui.choice_order(Node(), identities=GREETER_IDENTITIES, maximum=32,
                        cardinality=(1, 32), projection='greeter-account-order')
    ui.api.get_desktop.assert_not_called()


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
    clock = [0.0]
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(accessible_ui.time, 'sleep', lambda delay: clock.__setitem__(0, clock[0] + delay))
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
        if fault in ('duplicate', 'root'):
            assert clock[0] == 0
    else:
        assert greeter_account() is account
        lookup.assert_called_once_with(61234)


@pytest.mark.parametrize('becomes_ready', [True, False])
def test_greeter_discovery_waits_for_boot_readiness_with_a_deadline(monkeypatch, becomes_ready):
    import accessible_ui
    clock = [0.0]
    reads = []
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(accessible_ui.time, 'sleep', lambda delay: clock.__setitem__(0, clock[0] + delay))
    def call(argv, **kwargs):
        assert 0 < kwargs['timeout'] <= 5
        if argv[1] == 'list-sessions':
            reads.append(clock[0])
            return SimpleNamespace(stdout='c1 private-name\n' if becomes_ready and clock[0] >= 30 else '')
        return SimpleNamespace(stdout='Class=greeter\nActive=yes\nRemote=no\nType=wayland\nSeat=seat0\nUser=61234')
    monkeypatch.setattr(accessible_ui.subprocess, 'run', call)
    account = SimpleNamespace(pw_uid=61234)
    lookup = Mock(return_value=account)
    monkeypatch.setattr(accessible_ui.pwd, 'getpwuid', lookup)
    if becomes_ready:
        assert greeter_account() is account
        lookup.assert_called_once_with(61234)
        assert reads[0] == 0 and reads[-1] >= 30
    else:
        with pytest.raises(UiError, match='ui:timeout:greeter-identity'):
            greeter_account()
        lookup.assert_not_called()
        assert 300 <= clock[0] < 300.2


def test_greeter_discovery_does_not_retry_failed_session_reads(monkeypatch):
    import accessible_ui
    error = accessible_ui.subprocess.CalledProcessError(1, '/usr/bin/loginctl')
    call = Mock(side_effect=error)
    sleep = Mock()
    monkeypatch.setattr(accessible_ui.subprocess, 'run', call)
    monkeypatch.setattr(accessible_ui.time, 'sleep', sleep)
    with pytest.raises(accessible_ui.subprocess.CalledProcessError):
        greeter_account()
    call.assert_called_once()
    sleep.assert_not_called()


@pytest.mark.parametrize('operation,timeout', [
    ('gdm-other-list', 390), ('desktop', 90), ('kiosk-request-form', 120),
    ('kiosk-request-cancel', 120), ('kiosk-request-escape-ready', 120),
])
@pytest.mark.parametrize('streamed', [True, False])
def test_ui_transport_allows_greeter_boot_wait_inside_worker_deadline(operation, timeout, streamed):
    commands = SimpleNamespace(progress=None)
    def call(argv, **kwargs):
        assert kwargs['timeout'] == timeout < 420
        if streamed or operation in KIOSK_SESSION_OPERATIONS:
            kwargs['on_output'](b'{}\n')
        return b'{}'
    transport = SimpleNamespace(commands=commands, call=Mock(side_effect=call))
    ui = UiObservations(transport, system_prompt=Mock() if streamed else None)
    assert ui.call(['fixed-program'], operation) == (b'{}', [])
    transport.call.assert_called_once()


def test_greeter_reply_through_real_transport_and_command_stream(monkeypatch, tmp_path):
    import os
    import owned_commands
    import vm_transport
    import watch_activity

    result = {'interface': 'AT-SPI', 'focused': True,
              'operation': 'gdm-other-list', 'outcome': 'passed'}
    raw = (json.dumps(result) + '\n').encode()
    commands = owned_commands.Commands()
    commands.directory = tmp_path
    transcript = watch_activity.Transcript()
    monkeypatch.setattr(watch_activity, 'current', lambda: transcript)
    def spawn(argv, **kwargs):
        kwargs['stdout'].write(raw)
        kwargs['stdout'].flush()
        kwargs['stderr'].write(b'User has no time limits enabled\n')
        kwargs['stderr'].flush()
        return SimpleNamespace(pid=123, returncode=0, communicate=Mock())
    monkeypatch.setattr(owned_commands.subprocess, 'Popen', spawn)
    # A real disposable descriptor exercises close without owning a process.
    monkeypatch.setattr(owned_commands.os, 'pidfd_open', lambda _: os.open('/dev/null', os.O_RDONLY))
    transport = vm_transport.Transport({'directory': str(tmp_path), 'hostname': 'fixture.invalid',
        'run': 'a' * 32, 'domain_uuid': 'b' * 32}, commands, guard=Mock())
    prompt = Mock()
    assert UiObservations(transport, system_prompt=prompt).observe('gdm-other-list') == result
    prompt.assert_not_called()
    assert commands.progress is None
    assert (tmp_path / 'command-0001.txt').read_bytes() == raw
    assert 'focused' not in transcript.text


@pytest.mark.parametrize('appearance', [
    {'x': 30, 'y': 90, 'font': 'default', 'color': 'blue', 'scale': 1},
    {'x': 811, 'y': 213, 'font': 'different', 'color': 'purple', 'scale': 2.5},
    {'x': 4, 'y': 1, 'font': 'large', 'width': 511, 'misaligned': True},
])
def test_usable_target_is_independent_of_appearance(appearance):
    button = Node('About', 'button', appearance=appearance, identity='test-about')
    ui = action_ui(Node(children=[Node('Help', 'button'), button]), 'test-about')
    ui.activate_provider('action-fixture', 'main', 'action')
    button.action.do_action.assert_called_once_with(0)


def test_public_action_invokes_clipped_id_target_without_focus_or_scroll():
    button = Node('About', 'button', states=('visible', 'sensitive'),
                  identity='parent-menu-about')
    window = Node(identity='parent-window', children=[button])
    ui = ui_for(window)
    public_tree = ui.api.get_desktop(0)
    pending = [public_tree]
    nodes = []
    while pending:
        node = pending.pop()
        nodes.append(node)
        pending.extend(node.children)
    for node in nodes:
        node.get_child_count = Mock(wraps=node.get_child_count)

    ui.activate_id('parent-menu-about')

    for node in nodes:
        node.get_child_count.assert_called_once_with()
    button.component.scroll_to.assert_not_called()
    button.component.grab_focus.assert_not_called()
    button.action.do_action.assert_called_once_with(0)


def test_owned_id_never_routes_through_plural_lookup():
    button = Node('About', 'button', identity='parent-menu-about')
    ui = ui_for(Node(identity='parent-window', children=[button]))
    with pytest.raises(UiError, match='owned-id-requires-direct-lookup'):
        ui.find_all_ids('parent-menu-about')
    assert ui.find_id('parent-menu-about') is button


def test_child_lookup_never_discovers_uid_from_a_matching_label():
    from accessible_ui import CHILD, NEW_CHILD
    wrong_uid = Node('', 'button', identity='parent-child-choice-1003',
                     children=[Node(CHILD, 'label')])
    target = Node('', 'button', identity='parent-child-choice-1001',
                  children=[Node(NEW_CHILD, 'label')])
    root = Node(identity='parent-window', children=[wrong_uid, target])
    ui = ui_for(root)
    with pytest.raises(UiError, match='child-label'):
        ui.child_id_control(CHILD, 'parent-child-choice-', root=root, showing=True)
    target.children[0].name = CHILD
    assert ui.child_id_control(CHILD, 'parent-child-choice-', root=root, showing=True) is target
    root.children = [wrong_uid]
    assert ui.child_id_control(CHILD, 'parent-child-choice-', root=root, showing=True) is None
    wrong_uid.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['hidden', 'disabled', 'wrong-name', 'ambiguous', 'refused'])
def test_unusable_or_wrong_control_cannot_pass(fault):
    button = Node('About', 'button', identity='test-about')
    root = Node(children=[button])
    if fault == 'hidden': button.states.remove('visible')
    if fault == 'disabled': button.states.remove('sensitive')
    if fault == 'wrong-name': button.identity = 'test-help'
    if fault == 'ambiguous': root.children.append(Node('About', 'button', identity='test-about'))
    if fault == 'refused': button.action.do_action.return_value = False
    ui = action_ui(root, 'test-about')
    with pytest.raises(UiError):
        ui.activate_provider('action-fixture', 'main', 'action')


def test_successful_action_without_expected_result_still_fails():
    button = Node('Selected child', 'combo box', identity='test-selector')
    ui = action_ui(Node(children=[button]), 'test-selector')
    ui.activate(button)
    with pytest.raises(UiError, match='timeout'):
        ui.id_target('parent-child-choice-1001')


def test_stale_queries_retry_but_actions_are_never_replayed():
    button = Node('About', 'button', identity='test-about')
    ui = action_ui(button, 'test-about')
    ui.timeout = .5
    ui.query_errors = (LookupError,)
    button.get_accessible_id = Mock(side_effect=[LookupError('stale')] + ['test-about'] * 100)
    ui.activate_provider('action-fixture', 'main', 'action')
    button.action.do_action.assert_called_once_with(0)
    button.action.do_action.side_effect = LookupError('uncertain delivery')
    with pytest.raises(LookupError):
        ui.activate_provider('action-fixture', 'main', 'action')
    assert button.action.do_action.call_count == 2


def test_legacy_name_and_role_selector_refuses_before_tree_discovery():
    root = Node('copyright\n   no warranty', 'label')
    root.get_child_count = Mock(side_effect=AssertionError('tree traversed'))
    with pytest.raises(UiError, match='legacy-selector-refused'):
        ui_for(root).target('copyright no warranty', ('label',))
    root.get_child_count.assert_not_called()


def test_disabled_setting_can_be_read_but_cannot_authorize_input():
    control = Node('Daily time allowance', 'button', states=('showing', 'visible'),
                   identity='test-daily-limit-selector')
    ui = action_ui(control, 'test-daily-limit-selector')
    assert ui.id_target('test-daily-limit-selector') is control
    with pytest.raises(UiError, match='unusable-target'):
        ui.activate(control)
    control.action.do_action.assert_not_called()


def test_prompt_recognition_does_not_require_complete_provider_id_contracts():
    ui = ui_for(Node(role='desktop frame'), qualify_prompts=False)
    ui.prompt_enabled = True
    ui.prompt_session = 'desktop'
    assert ui.system_prompt_kind() is None
    ui.handle_system_prompt()


def test_unqualified_desktop_provider_blocks_before_tree_discovery_or_input():
    ui = ui_for(Node(), qualify_prompts=False)
    # Partial provider IDs cannot silently fall back to the semantic adapter.
    ui.provider_contracts['document-viewer']['application_id'] = 'partial-viewer'
    ui.api.get_desktop = Mock(side_effect=AssertionError('tree read'))
    with pytest.raises(UiError, match='^ui:unqualified-provider-surface$'):
        ui.open_license()
    ui.api.get_desktop.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'duplicate-owner', 'wrong-owner',
                                 'duplicate-field', 'hidden-field', 'incomplete'])
def test_shell_search_adapter_scopes_unique_editable_field_to_owner(fault):
    field = Node('Search', 'text', states=('showing', 'visible', 'sensitive', 'editable'))
    field.get_text_iface = lambda: field
    shell = Node('gnome-shell', 'application', children=[field])
    root = Node(role='desktop frame', children=[shell])
    if fault == 'duplicate-owner':
        second = Node('GNOME Shell', 'application')
        second.parent = root
        root.children.append(second)
    elif fault == 'wrong-owner':
        shell.name = 'other application'
    elif fault == 'duplicate-field':
        second = Node('Search', 'text', states=('showing', 'visible', 'sensitive', 'editable'))
        second.parent = shell
        shell.children.append(second)
    elif fault == 'hidden-field':
        field.states.remove('showing')
    ui = ui_for(root)
    if fault == 'incomplete':
        shell.children.append(None)
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: 0, get_text=lambda *_: '')
    if fault in ('duplicate-owner', 'duplicate-field', 'incomplete'):
        with pytest.raises(UiError):
            ui.search_query('')
    else:
        assert ui.search_query('') is (fault is None)
    field.component.grab_focus.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'open', 'wrong-result', 'incomplete'])
def test_parent_search_closure_requires_complete_absence(fault):
    child = Node(role='frame', identity=(
        'parent-access-denied-window' if fault == 'wrong-result' else 'parent-window'))
    root = Node(role='desktop frame', children=[child] if fault in ('open', 'wrong-result') else [])
    ui = ui_for(root)
    ui.standard_shell_desktop = Mock()
    if fault == 'incomplete':
        root.children.append(None)
        with pytest.raises(UiError):
            ui.parent_search_closed()
    else:
        assert ui.parent_search_closed() is (fault is None)


def test_shell_search_launcher_requires_one_owned_exact_result():
    launcher = Node('Oh No! Parent Control', 'button')
    unrelated = Node('Oh No! Parent Control', 'button')
    shell = Node('gnome-shell', 'application', children=[launcher])
    other = Node('other application', 'application', children=[unrelated])
    root = Node(role='desktop frame', children=[shell, other])
    ui = ui_for(root)
    assert ui.launchable_result(accessible_ui.PRODUCT) is launcher
    launcher.states.remove('showing')
    assert ui.launchable_result(accessible_ui.PRODUCT) is None
    launcher.states.add('showing')
    duplicate = Node('Oh No! Parent Control', 'button')
    duplicate.parent = shell
    shell.children.append(duplicate)
    with pytest.raises(UiError, match='shell-result-ambiguous'):
        ui.launchable_result(accessible_ui.PRODUCT)
    launcher.component.grab_focus.assert_not_called()
    unrelated.component.grab_focus.assert_not_called()


def test_shell_search_first_character_and_wrong_result_use_exact_live_query():
    field = Node('Search', 'text', states=('showing', 'visible', 'sensitive', 'editable'))
    field.get_text_iface = lambda: field
    launcher = Node('Oh No! Parent Control', 'button')
    shell = Node('gnome-shell', 'application', children=[field, launcher])
    ui = ui_for(Node(role='desktop frame', children=[shell]))
    query = {'value': 'O'}
    ui.api.Text = SimpleNamespace(
        get_character_count=lambda _: len(query['value']),
        get_text=lambda *_: query['value'])
    assert ui.run('shell-search-started', '')['outcome'] == 'passed'
    with pytest.raises(UiError, match='ui:search-query'):
        ui.run('shell-search-wrong-result-refused', '')
    query['value'] = accessible_ui.PRODUCT
    assert ui.run('shell-search-wrong-result-refused', '')['outcome'] == 'passed'
    launcher.component.grab_focus.assert_not_called()


def test_shell_search_dismissal_refuses_visible_or_incomplete_field():
    field = Node('Search', 'text', states=('showing', 'visible', 'sensitive', 'editable'))
    shell = Node('gnome-shell', 'application', children=[field])
    ui = ui_for(Node(role='desktop frame', children=[shell]))
    ui.standard_shell_desktop = Mock(return_value=True)
    with pytest.raises(UiError, match='ui:search-not-dismissed'):
        ui.run('shell-search-dismissed', '')
    field.states.remove('showing')
    assert ui.run('shell-search-dismissed', '')['outcome'] == 'passed'
    shell.children.append(None)
    with pytest.raises(UiError, match='ui:incomplete-tree'):
        ui.run('shell-search-dismissed', '')


@pytest.mark.parametrize('fault', [None, 'duplicate-owner', 'wrong-owner', 'duplicate-panel',
                                 'hidden', 'stale', 'incomplete'])
def test_standard_desktop_requires_unique_live_shell_panel(fault):
    panel = Node('Activities', 'toggle button')
    shell = Node('gnome-shell', 'application', children=[panel])
    root = Node(role='desktop frame', children=[shell])
    if fault == 'duplicate-owner':
        other = Node('gnome-shell', 'application')
        other.parent = root
        root.children.append(other)
    if fault == 'wrong-owner':
        shell.name = 'unrelated'
    if fault == 'duplicate-panel':
        other = Node('Activities', 'toggle button')
        other.parent = shell
        shell.children.append(other)
    if fault == 'hidden':
        panel.states.remove('showing')
    if fault == 'stale':
        panel.states.add('defunct')
    ui = ui_for(root)
    if fault == 'incomplete':
        shell.children.append(None)
    if fault:
        with pytest.raises(UiError):
            ui.desktop_result(accessible_ui.EXISTING_CHILD, 'success')
    else:
        assert ui.desktop_result(accessible_ui.EXISTING_CHILD, 'success') is panel
    panel.action.do_action.assert_not_called()


def test_fresh_parent_desktop_uses_bound_shell_and_refuses_a_keyring_modal():
    panel = Node('Activities', 'toggle button')
    shell = Node('gnome-shell', 'application', children=[panel])
    prompt_ui, controls = semantic_prompt('keyring')
    prompt = prompt_ui.api.get_desktop(0).children[0]
    root = Node(role='desktop frame', children=[shell, prompt])
    ui = ui_for(root, qualify_prompts=False)
    assert ui.desktop_result(accessible_ui.PARENT, 'success') is panel
    with pytest.raises(UiError, match='fresh-desktop-prompt'):
        ui.run('fresh-parent-desktop', '')
    for control in controls:
        control.action.do_action.assert_not_called()


@pytest.mark.parametrize('operation', ['fresh-parent-desktop', 'fresh-standard-desktop'])
def test_fresh_desktop_requires_sustained_positive_shell_without_a_prompt(monkeypatch, operation):
    from itertools import count
    panel = Node('Activities', 'toggle button')
    shell = Node('gnome-shell', 'application', children=[panel])
    ui = ui_for(Node(role='desktop frame', children=[shell]), qualify_prompts=False)
    ui.timeout = 10
    clock = count(0, 0.25)
    monkeypatch.setattr(accessible_ui, 'time', SimpleNamespace(
        monotonic=lambda: next(clock), sleep=lambda _: None))
    assert ui.run(operation, '')['outcome'] == 'passed'
    panel.action.do_action.assert_not_called()


def test_dead_unrelated_subtree_does_not_hide_live_control():
    dead = Node('dead')
    dead.get_name = Mock(side_effect=LookupError('disconnected'))
    button = Node('About', 'button', identity='test-about')
    ui = ui_for(Node(children=[dead, button]))
    ui.query_errors = (LookupError,)
    assert ui.id_target('test-about') is button


def test_duplicate_tree_paths_are_one_id_but_distinct_id_matches_are_ambiguous():
    button = Node('Search installed apps', 'entry', identity='test-search-input')
    ui = ui_for(Node(children=[Node(children=[button]), Node(children=[button])]))
    assert ui.id_target('test-search-input') is button
    with pytest.raises(UiError, match='ambiguous-automation-id'):
        ui_for(Node(children=[button, Node(button.name, 'entry',
                                           identity='test-search-input')])).id_target('test-search-input')


@pytest.mark.parametrize('nested', [False, True])
def test_search_result_supports_named_buttons_and_their_public_labels(nested):
    label = Node('Oh No! Parent Control', 'label')
    button = Node('' if nested else label.name, 'push button',
                  children=[Node(children=[label])] if nested else [],
                  identity=SEARCH_CONTROLS['result::parent'])
    ui = queried_search_ui(button)
    assert ui.launchable_result(label.name) is button
    assert ui.run('app-grid', '1.1')['outcome'] == 'passed'


def test_search_text_without_a_launchable_control_is_not_a_result():
    ui = queried_search_ui(Node('Oh No! Parent Control', 'label'))
    with pytest.raises(UiError, match='search-result'):
        ui.run('app-grid', '1.1')


@pytest.mark.parametrize('failure', ['exception', 'refused', 'unobserved'])
def test_search_launcher_requires_observed_focus_without_replay(failure):
    button = Node('Oh No! Parent Control', 'button', identity=SEARCH_CONTROLS['result::parent'])
    ui = queried_search_ui(button)
    button.component.grab_focus.side_effect = (
        LookupError('uncertain') if failure == 'exception' else None)
    button.component.grab_focus.return_value = failure != 'refused'
    with pytest.raises((UiError, LookupError)):
        ui.focus_search_result()
    with pytest.raises(UiError, match='uncertain-input'):
        ui.focus_search_result()
    button.component.grab_focus.assert_called_once_with()


@pytest.mark.parametrize('fault', [None, 'hidden', 'missing', 'wrong-text', 'other-window',
                                  'selected-child', 'missing-picker', 'missing-placeholder', 'ambiguous',
                                  'stale-picker', 'defunct-picker-child', 'hidden-placeholder'])
@pytest.mark.parametrize('entry', ['checkpoint', 'independent-block'])
def test_empty_parent_requires_readable_explanation_and_no_selected_child(fault, entry):
    from accessible_ui import PRODUCT
    explanation = Node('No interactive\n non-administrator account was found.', 'label',
                       appearance={'scale': 2.5, 'font': 'huge', 'misaligned': True})
    explanation.identity = 'parent-no-users-message'
    placeholder = Node('(None)', 'label', identity='parent-child-selected-none')
    picker = Node('', 'button', children=[placeholder],
                  states=('showing', 'visible'), identity='parent-child-selector')
    root = Node(PRODUCT, children=[explanation, picker], identity='parent-window')
    if fault == 'hidden': explanation.states.remove('showing')
    if fault == 'missing': root.children.remove(explanation)
    if fault == 'wrong-text': explanation.name = 'Loading accounts'
    if fault == 'other-window': root.name = 'Unrelated application'
    if fault == 'selected-child': picker.children.append(Node('Jordan (Child)', 'label'))
    if fault == 'missing-picker': root.children.remove(picker)
    if fault == 'missing-placeholder': picker.children.clear()
    if fault == 'ambiguous':
        root.children.append(Node(explanation.name, 'label', identity='parent-no-users-message'))
    if fault == 'hidden-placeholder': picker.children[0].states.remove('showing')
    if fault in ('stale-picker', 'defunct-picker-child'):
        stale = Node('private-canary')
        if fault == 'stale-picker':
            stale.get_child_count = Mock(side_effect=LookupError('private-canary'))
        else:
            stale.states.add('defunct')
        picker.children.append(stale)
    ui = ui_for(root)
    ui.query_errors = (LookupError,)
    def observe():
        return ui.parent_empty() if entry == 'independent-block' else ui.run('parent-empty', '')
    if fault:
        with pytest.raises(UiError): observe()
    elif entry == 'independent-block':
        assert observe() is None
    else:
        assert observe() == {
            'operation': 'parent-empty', 'outcome': 'passed', 'interface': 'AT-SPI'}
    picker.action.do_action.assert_not_called()


def test_empty_parent_waits_for_fresh_state_without_replaying_input():
    from accessible_ui import PRODUCT
    root = Node(PRODUCT, identity='parent-window', children=[
        Node('', 'button', identity='parent-child-selector', children=[
            Node('(None)', 'label', identity='parent-child-selected-none')]),
        Node('No interactive non-administrator account was found.', 'label',
             identity='parent-no-users-message')])
    ui = ui_for(root)
    ui.timeout = .5
    original = ui.find_id
    calls = []
    def delayed(*args, **kwargs):
        calls.append(args)
        parent_reads = calls.count(('parent-window',))
        return None if args == ('parent-window',) and parent_reads == 1 else original(*args, **kwargs)
    ui.find_id = delayed
    assert ui.run('parent-empty', '')['outcome'] == 'passed'
    assert calls.count(('parent-window',)) == 2


@pytest.mark.parametrize('operation', ['license-closed', 'parent-returned'])
def test_return_waits_for_the_window_to_finish_closing(operation):
    from accessible_ui import PRODUCT
    closing, destination = (('LICENSE', 'About') if operation == 'license-closed' else ('About', PRODUCT))
    old = Node(closing, identity='about-dialog' if closing == 'About' else '')
    underlying = Node(destination, identity='parent-window' if destination == PRODUCT else 'about-dialog')
    root = Node(children=[old, underlying], identity='parent-window' if operation == 'license-closed' else '')
    if operation == 'license-closed':
        old.identity = 'test-viewer-license'
        close = Node(identity=DOCUMENT_CONTROLS['close'])
        old.children.append(close)
        close.parent = old
        application = Node(identity='test-viewer-application', children=[old])
        root.children.remove(old)
        application.parent = root
        root.children.append(application)
        ui = document_ui(root)
    else:
        ui = ui_for(root)
    ui.timeout = .5
    observations = []
    def dispatch():
        container = old.parent.children
        observations.append(old in container)
        if len(observations) == 2:
            container.remove(old)
        return False
    ui.dispatch = dispatch
    ui.settings = Mock(return_value={'child': 'fixture-child'})
    assert ui.run(operation, '1.1')['outcome'] == 'passed'
    assert observations == [True, True]


@pytest.mark.parametrize('fault', [None, 'wrong-document', 'hidden', 'password'])
def test_license_reads_the_text_interface_and_requires_actual_visible_content(fault):
    link = Node('GNU General Public License v3.0', 'link', identity='about-license-value')
    document = Node('', 'password text' if fault == 'password' else 'text')
    if fault == 'hidden': document.states.remove('showing')
    document.get_text_iface = lambda: document
    document.get_text = Mock(side_effect=AssertionError('wrong Accessible interface'))
    root = Node(identity='parent-window', children=[
        Node('About', 'frame', children=[link], identity='about-dialog')])
    ui = document_ui(root, document=document)
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


@pytest.mark.parametrize('fault', [None, 'inactive', 'hidden', 'missing', 'duplicate'])
@pytest.mark.parametrize('window', ['license', 'about'])
def test_keyboard_close_requires_a_fresh_active_unique_window(window, fault):
    node = Node('LICENSE' if window == 'license' else 'About', states=(
        'showing', 'visible', 'sensitive', 'active'),
        identity='about-dialog' if window == 'about' else '')
    if fault == 'inactive': node.states.remove('active')
    if fault == 'hidden': node.states.remove('showing')
    nodes = [] if fault == 'missing' else [node]
    if window == 'about' and fault == 'duplicate':
        nodes.append(Node('About', identity='about-dialog'))
    if window == 'license':
        product = Node(identity='parent-window', children=[Node(identity='about-dialog')])
        ui = document_ui(product, document=Node(role='text'))
        surface = ui.find_id('test-viewer-license', showing=False)
        if fault == 'inactive': surface.states.remove('active')
        if fault == 'hidden': surface.states.remove('showing')
        if fault == 'missing':
            surface.parent.children.remove(surface)
        if fault == 'duplicate':
            duplicate = Node(identity='test-viewer-license')
            duplicate.parent = surface.parent
            surface.parent.children.append(duplicate)
    else:
        ui = ui_for(Node(identity='parent-window', children=nodes))
    if fault:
        with pytest.raises(UiError): ui.window_ready_to_close(window)
    else:
        ui.window_ready_to_close(window)
    node.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'still-open', 'missing-destination', 'stale', 'defunct'])
def test_closed_window_requires_complete_reads_and_recognized_destination(fault):
    about = Node('About', identity='about-dialog')
    product = Node(identity='parent-window', children=[] if fault == 'missing-destination' else [about])
    ui = document_ui(product, document=Node(role='text') if fault == 'still-open' else None)
    if fault == 'defunct': about.states.add('defunct')
    if fault == 'stale': about.get_child_count = Mock(side_effect=LookupError('stale'))
    ui.query_errors = (LookupError,)
    if fault:
        with pytest.raises(UiError): ui.window_closed('license', 'about')
    else:
        ui.window_closed('license', 'about')


@pytest.mark.parametrize('fault', ['projection', 'bound', 'masked', 'hidden', 'oversized'])
def test_document_projection_rejects_unregistered_or_unsafe_reads(fault):
    node = Node(role='password text' if fault == 'masked' else 'text')
    if fault == 'hidden': node.states.remove('showing')
    node.get_text_iface = Mock(return_value=node)
    ui = document_ui(Node(identity='parent-window', children=[Node(identity='about-dialog')]),
                     document=node)
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: 2000,
        get_text=Mock(return_value='x' * 1025))
    with pytest.raises(UiError):
        ui.read_document(node, 'unknown' if fault == 'projection' else 'gpl-heading',
                         maximum=2048 if fault == 'bound' else 1024)
    if fault != 'oversized':
        node.get_text_iface.assert_not_called()
        ui.api.Text.get_text.assert_not_called()


def semantic_license_ui():
    link = Node(identity='about-license-value', role='link')
    about = Node(identity='about-dialog', children=[link],
                 states=('showing', 'visible', 'sensitive', 'active'))
    product = Node(identity=PARENT_APPLICATION,
                   children=[Node(identity='parent-window', children=[about])])
    content = Node(identity='view', role='text')
    content.get_text_iface = Mock(return_value=content)
    window = Node(children=[content], states=('showing', 'visible', 'sensitive', 'active'))
    owner = Node('gnome-text-editor', 'application', children=[window])
    desktop = Node(children=[product, owner])
    ui = ui_for(desktop)
    text = 'GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n' + 'x' * 2000
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: len(text),
        get_text=Mock(side_effect=lambda _node, start, end: text[start:end]))
    return ui, desktop, owner, window, content, about, link


@pytest.mark.parametrize('fault', [None, 'wrong-owner', 'wrong-id', 'duplicate-owner',
    'duplicate-window', 'duplicate-document', 'hidden', 'masked', 'inactive',
    'foreign-process', 'incomplete', 'wrong-document', 'oversized', 'prompt'])
def test_semantic_license_requires_unique_owned_public_document_and_bounded_content(fault):
    ui, desktop, owner, window, content, about, link = semantic_license_ui()
    if fault == 'wrong-owner': owner.name = 'unrelated-editor'
    if fault == 'wrong-id': content.identity = 'unrelated-document'
    if fault == 'duplicate-owner': desktop.children.append(Node('gnome-text-editor', 'application'))
    if fault == 'duplicate-window': owner.children.append(Node())
    if fault == 'duplicate-document': window.children.append(Node(identity='view', role='text'))
    if fault == 'hidden': content.states.remove('showing')
    if fault == 'masked': content.role = 'password text'
    if fault == 'inactive': window.states.remove('active')
    if fault == 'foreign-process': content.get_process_id = lambda: 999
    if fault == 'incomplete': owner.children.append(None)
    if fault == 'wrong-document': ui.api.Text.get_text = Mock(return_value='another document')
    if fault == 'oversized': ui.api.Text.get_text = Mock(return_value='x' * 1025)
    if fault == 'prompt': ui.handle_system_prompt = Mock(side_effect=UiError('ui:system-prompt'))
    if fault:
        with pytest.raises(UiError): ui.license_content()
        with pytest.raises(UiError): ui.window_ready_to_close('license')
    else:
        assert ui.license_content()
        ui.window_ready_to_close('license')
        assert all(call.args == (content, 0, 1024)
                   for call in ui.api.Text.get_text.call_args_list)
    if fault not in (None, 'wrong-document', 'oversized'):
        ui.api.Text.get_text.assert_not_called()
    link.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'already-open', 'uncertain', 'missing-result'])
def test_semantic_license_link_launches_once_and_observes_result(fault):
    ui, desktop, owner, window, content, about, link = semantic_license_ui()
    if fault != 'already-open': desktop.children.remove(owner)
    def launch(_index):
        if fault == 'uncertain': raise RuntimeError('uncertain action')
        if fault != 'missing-result': desktop.children.append(owner)
        return True
    link.action.do_action.side_effect = launch
    if fault:
        with pytest.raises((UiError, RuntimeError)): ui.open_license()
    else:
        ui.open_license()
        assert ui.api.Text.get_text.called
    assert link.action.do_action.call_count == (0 if fault == 'already-open' else 1)


@pytest.mark.parametrize('fault', [None, 'still-open', 'missing-about', 'inactive-about', 'incomplete'])
def test_semantic_license_close_requires_fresh_absence_and_active_owned_about(fault):
    ui, desktop, owner, window, content, about, link = semantic_license_ui()
    if fault != 'still-open': owner.children.clear()
    if fault == 'missing-about': about.identity = ''
    if fault == 'inactive-about': about.states.remove('active')
    if fault == 'incomplete': owner.children.append(None)
    if fault:
        with pytest.raises(UiError): ui.window_closed('license', 'about')
    else:
        ui.window_closed('license', 'about')


@pytest.mark.parametrize('kind', ['unrelated', 'empty', 'ambiguous'])
@pytest.mark.parametrize('fault', [None, 'wrong-content', 'wrong-window-count'])
def test_license_fixture_requires_exact_public_text_and_window_count(kind, fault):
    ui, desktop, owner, window, content, about, link = semantic_license_ui()
    if kind == 'ambiguous':
        owner.children.append(Node(states=('showing', 'visible', 'sensitive')))
    value = '' if kind == 'empty' else 'ONPC E2E synthetic ' + kind + ' document'
    if fault == 'wrong-content':
        value += 'unexpected'
    if fault == 'wrong-window-count':
        owner.children.append(Node())
    ui.api.Text.get_character_count = lambda _: len(value)
    ui.api.Text.get_text = Mock(return_value=value)
    if fault:
        with pytest.raises(UiError, match='ui:license-fixture-'):
            ui.license_fixture_windows(kind)
    else:
        assert ui.license_fixture_windows(kind) == (window, content)


@pytest.mark.parametrize('projection,label', [
    ('about-product', 'Oh No! Parent Control'), ('about-version', 'Version 1.1'),
    ('about-footer', '© 2026 Puffy Slippers Tech LLC\nGPL-3.0-only · No warranty.'),
])
def test_about_text_projections_require_the_exact_showing_label(projection, label):
    node = Node(label, 'label', identity={'about-product': 'about-product-name',
        'about-version': 'about-version', 'about-footer': 'about-copyright'}[projection])
    ui = ui_for(Node(identity='parent-window', children=[Node(identity='about-dialog', children=[node])]))
    assert ui.read_label(ui.api.get_desktop(0), projection, maximum=80, expected='1.1')
    node.states.remove('showing')
    with pytest.raises(UiError):
        ui.read_label(ui.api.get_desktop(0), projection, maximum=80, expected='1.1')


@pytest.mark.parametrize('operation', ['gdm-list', 'gdm-other-list'])
@pytest.mark.parametrize('focused,valid', [(True, True), (False, False), (1, False), (None, False)])
def test_guest_list_selection_requires_id_resolved_semantic_focus(focused, valid, operation):
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI',
              'focused': focused}
    session = UiObservations(SimpleNamespace(call=Mock(return_value=json.dumps(result).encode())))
    if valid:
        assert session.observe(operation)['focused'] is True
    else:
        with pytest.raises(EvidenceError, match='ui:response'):
            session.observe(operation)


@pytest.mark.parametrize('operation', [
    'child-picker-opened', 'discovery-child-picker-opened',
    'new-child-picker-opened', 'existing-child-picker-opened',
])
@pytest.mark.parametrize('focused,valid', [(True, True), (False, False), (1, False)])
def test_child_picker_reply_requires_id_resolved_focus(operation, focused, valid):
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI',
              'focused': focused}
    session = UiObservations(SimpleNamespace(call=Mock(return_value=json.dumps(result).encode())))
    if valid:
        assert session.observe(operation)['focused'] is True
    else:
        with pytest.raises(EvidenceError, match='ui:response'):
            session.observe(operation)


def test_password_widget_contents_are_never_traversed():
    secret = Node('secret', 'password text', children=[Node('must not read')])
    secret.get_child_count = Mock(side_effect=AssertionError('secret traversed'))
    assert list(ui_for(secret).nodes()) == [secret]


@pytest.mark.parametrize('fault', [None, 'changed-child', 'unreviewed-text'])
def test_return_exports_only_sanitized_settings_without_hidden_prior_selection(fault):
    settings = {'child': 'fixture-child', 'limit_enabled': False, 'allowance': ['30 minutes']}
    def response(operation, values):
        return json.dumps({'operation': operation, 'outcome': 'passed',
                           'interface': 'AT-SPI', 'settings': values}).encode()
    transport = SimpleNamespace(call=Mock(return_value=response('parent-selected', settings)))
    session = UiObservations(transport)
    returned = dict(settings)
    if fault == 'changed-child': returned['child'] = 'another-child'
    if fault == 'unreviewed-text': returned['allowance'] = ['private unexpected data']
    operation = 'parent-returned'
    transport.call.return_value = response(operation, returned)
    if fault:
        with pytest.raises(EvidenceError): session.observe(operation)
    else:
        assert session.observe(operation)['settings'] == settings


@pytest.mark.parametrize('fault', [None, 'missing', 'wrong-highlight', 'hidden', 'disabled',
                                  'wrong-selection', 'popup-remains'])
def test_dynamic_child_requires_expansion_highlight_and_independent_selection(fault):
    from accessible_ui import PRODUCT, CHILD, NEW_CHILD
    selected = Node(CHILD, 'label', identity='parent-child-selected-1001')
    picker = Node('', 'button', children=[selected], identity='parent-child-selector')
    allowance = Node('Daily time allowance', 'button', children=[Node('30 minutes', 'label')],
                     states=('showing', 'visible'), identity='parent-daily-limit-selector')
    root = Node(PRODUCT, identity='parent-window', children=[picker,
        Node('Screen time limit', 'switch', identity='parent-screen-limit-toggle'), allowance,
        Node("Today's Remaining Time", 'label', identity='parent-time-status')])
    row = Node('', 'button', children=[Node(NEW_CHILD, 'label')],
               identity='parent-child-choice-1003')
    first = Node('', 'button', children=[Node(CHILD, 'label')],
                 identity='parent-child-choice-1001')
    listing = Node('', 'panel', children=[first, row], identity='parent-child-choices')
    popover = Node('', 'panel', children=[listing], identity='parent-child-popover')
    def expand(_index):
        if fault != 'missing':
            root.children.append(popover)
            popover.parent = root
        return True
    picker.action.get_n_actions = lambda: 3
    picker.action.get_action_name = lambda index: (
        'menu.popup', 'child.focus-1001', 'child.focus-1003')[index]
    def selector_action(index):
        if index == 0:
            return expand(index)
        (first if index == 1 else row).states.add('focused')
        return True
    picker.action.do_action.side_effect = selector_action
    ui = ui_for(root)
    if fault == 'disabled': row.states.remove('sensitive')
    if fault == 'hidden': row.children[0].states.remove('showing')
    if fault in ('missing', 'disabled', 'hidden'):
        with pytest.raises(UiError): ui.run('new-child-picker-opened', '')
    else:
        assert ui.run('new-child-picker-opened', '')['focused'] is True
        if fault == 'wrong-highlight':
            row.states.remove('focused')
            first.states.add('focused')
        if fault == 'wrong-highlight':
            with pytest.raises(UiError, match='choice-highlight'):
                ui.run('new-child-choice-highlighted', '')
        else:
            ui.run('new-child-choice-highlighted', '')
            if fault != 'popup-remains': root.children.remove(popover)
            if fault != 'wrong-selection':
                selected.name = NEW_CHILD
                selected.identity = 'parent-child-selected-1003'
            if fault:
                with pytest.raises(UiError): ui.run('new-child-selected', '')
            else:
                assert ui.run('new-child-selected', '')['settings'] == {
                    'child': 'new-fixture-child', 'limit_enabled': False, 'allowance': ['30 minutes']}
    expected_actions = [(0,)] if fault in ('missing', 'hidden', 'disabled') else [(0,), (2,)]
    assert [item.args for item in picker.action.do_action.call_args_list[:2]] == expected_actions


@pytest.mark.parametrize('fault', [None, 'new-identity', 'new-replay', 'new-return-changed',
                                  'existing-return-changed', 'private-text'])
def test_discovery_controller_keeps_child_settings_separate_and_private(fault):
    from installed_journey import InstalledJourney
    from parent_discovery import PLAN
    existing = {'child': 'existing-fixture-child', 'limit_enabled': False, 'allowance': ['0 minutes']}
    new = {'child': 'new-fixture-child', 'limit_enabled': False, 'allowance': ['1 hour']}
    transport = SimpleNamespace(call=Mock())
    session = UiObservations(transport)
    journey = InstalledJourney(SimpleNamespace(), Mock(), PLAN, actions={'create-account': Mock()})
    def observe(operation, settings):
        transport.call.return_value = json.dumps({'operation': operation, 'outcome': 'passed',
            'interface': 'AT-SPI', 'settings': settings}).encode()
        result = session.observe(operation)
        stage = next(stage for stage, tag in PLAN.screen_tags.items() if tag == 'ui:' + operation)
        journey.check_settings(stage, {'ui': result})
        return result
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
    from installed_journey import InstalledJourney
    from parent_discovery import PLAN
    result = {'operation': 'discovery-selected', 'outcome': 'passed', 'interface': 'AT-SPI',
              'settings': {'child': 'existing-fixture-child', 'limit_enabled': enabled,
                           'allowance': allowance}}
    session = UiObservations(SimpleNamespace(call=Mock(return_value=json.dumps(result).encode())))
    journey = InstalledJourney(SimpleNamespace(), Mock(), PLAN, actions={'create-account': Mock()})
    with pytest.raises(EvidenceError, match='settings-changed'):
        journey.check_settings('parent-selected', {'ui': session.observe('discovery-selected')})


def test_settings_comparison_is_immutable_and_independent_of_selection_history():
    from ui_observations import SettingsObservation, compare_settings
    values = {'child': 'new-fixture-child', 'limit_enabled': True, 'allowance': ['1 hour']}
    earlier = SettingsObservation.from_settings(values)
    assert compare_settings(SettingsObservation.from_settings(values), earlier)['outcome'] == 'passed'
    values['allowance'][0] = '2 hours'
    assert earlier.allowance == ('1 hour',)
    with pytest.raises(EvidenceError, match='settings-changed:allowance'):
        compare_settings(SettingsObservation.from_settings(values), earlier)


@pytest.mark.parametrize('fault', [None, 'duplicate', 'stale', 'bound', 'unknown-target'])
def test_child_collection_uses_an_independent_current_list(fault):
    from accessible_ui import CHILD_IDENTITIES, CHILD, NEW_CHILD
    rows = [Node('', 'list item', identity='parent-child-choice-1003',
                 children=[Node(NEW_CHILD, 'label')]),
            Node('', 'list item', identity='parent-child-choice-1001',
                 children=[Node(CHILD, 'label')])]
    if fault == 'duplicate':
        rows.append(Node('', 'list item', identity='parent-child-choice-1003',
                         children=[Node(NEW_CHILD, 'label')]))
    if fault == 'stale': rows[1].states.add('defunct')
    root = Node('', 'list box', identity='parent-child-choices', children=rows)
    ui = ui_for(Node(identity='parent-window', children=[root]))
    def collect():
        return ui.choice_order(root, identities={} if fault == 'unknown-target' else CHILD_IDENTITIES,
            maximum=1 if fault == 'bound' else 32, cardinality=(1, 1 if fault == 'bound' else 32),
            projection='child-picker-order')
    if fault:
        with pytest.raises(UiError): collect()
    else:
        assert collect() == ('new-fixture-child', 'fixture-child')


def test_closed_picker_cannot_hide_a_persistently_stale_subtree(monkeypatch):
    from accessible_ui import PRODUCT, NEW_CHILD
    stale = Node('private-canary', states=('defunct',))
    picker = Node('', 'button', identity='parent-child-selector', children=[
        Node(NEW_CHILD, 'label', identity='parent-child-selected-1003')])
    ui = ui_for(Node(PRODUCT, identity='parent-window', children=[picker, stale]))
    ui.timeout = 1
    monkeypatch.setattr('accessible_ui.time.sleep', lambda _seconds: None)
    clock = iter((0, 0, 2))
    monkeypatch.setattr('accessible_ui.time.monotonic', lambda: next(clock))
    with pytest.raises(UiError, match='stale-picker'):
        ui.selected_child(NEW_CHILD)
    assert len(ui.incomplete_observations) == 2


def test_closed_picker_retries_a_transient_stale_subtree_without_input(monkeypatch):
    from accessible_ui import PRODUCT, NEW_CHILD
    stale = Node('private-canary', states=('defunct',))
    picker = Node('', 'button', identity='parent-child-selector', children=[
        Node(NEW_CHILD, 'label', identity='parent-child-selected-1003')])
    root = Node(PRODUCT, identity='parent-window', children=[picker, stale])
    ui = ui_for(root)
    ui.timeout = 1
    monkeypatch.setattr('accessible_ui.time.sleep', lambda _seconds: None)
    expected = {'child': NEW_CHILD}
    ui.settings = Mock(return_value=expected)
    original_has_state = ui.has_state
    stale_reads = 0

    def has_state(node, state):
        nonlocal stale_reads
        value = original_has_state(node, state)
        if node is stale and state == ui.api.StateType.DEFUNCT and value:
            stale_reads += 1
            root.children.remove(stale)
        return value

    ui.has_state = has_state
    assert ui.selected_child(NEW_CHILD) == expected
    assert stale_reads == 1
    assert ui.incomplete_observations == [
        {'checkpoint': 'picker-close', 'notes': []}]
    picker.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'missing-id', 'wrong-uid', 'wrong-label'])
def test_child_collection_uses_uid_identity_with_nested_content(fault):
    from accessible_ui import CHILD, CHILD_IDENTITIES
    content = Node('', identity='parent-child-choice-1001-content', children=[
        Node(CHILD if fault != 'wrong-label' else 'Other child', 'label')])
    choice = Node('', 'push button', identity=(
        '' if fault == 'missing-id' else 'parent-child-choice-9999'
        if fault == 'wrong-uid' else 'parent-child-choice-1001'), children=[content])
    root = Node(identity='parent-child-choices', children=[choice])
    ui = ui_for(Node(identity='parent-window', children=[root]))
    def collect():
        return ui.choice_order(root, identities=CHILD_IDENTITIES, maximum=32,
                               cardinality=(1, 32), projection='child-picker-order')
    if fault:
        with pytest.raises(UiError):
            collect()
    else:
        assert collect() == ('fixture-child',)


def test_child_collection_allows_not_yet_created_fixture_but_refuses_unregistered_rows():
    from accessible_ui import CHILD, CHILD_IDENTITIES
    choice = Node('', 'button', identity='parent-child-choice-1001', children=[Node(CHILD, 'label')])
    choices = Node(identity='parent-child-choices', children=[choice])
    ui = ui_for(Node(identity='parent-window', children=[choices]))
    ui.fixture_uids = {CHILD: 1001}
    def collect():
        return ui.choice_order(choices, identities=CHILD_IDENTITIES, maximum=32,
                               cardinality=(1, 32), projection='child-picker-order')
    assert collect() == ('fixture-child',)
    choices.children.append(Node('Private unrelated account', identity='parent-child-choice-4000'))
    with pytest.raises(UiError, match='unregistered-child-choice'):
        collect()


@pytest.mark.parametrize('fault', ['unidentified', 'wrong-owner', 'wrong-uid'])
def test_already_focused_nodes_do_not_bypass_picker_identity(fault):
    from accessible_ui import CHILD
    choice = Node(CHILD, 'button', identity='parent-child-choice-1001',
                  states=('showing', 'visible', 'sensitive', 'focused'))
    root = Node(identity='parent-window', children=[choice] if fault != 'wrong-owner' else [])
    if fault == 'unidentified': choice.identity = ''
    if fault == 'wrong-uid': choice.identity = 'kiosk-child-choice-1001'
    ui = ui_for(root)
    with pytest.raises(UiError):
        ui.focus(choice)
    choice.action.do_action.assert_not_called()


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
    ui = gdm_ui(recipient=label, field=field, list_showing=fault == 'list-visible')
    surface = ui.api.get_desktop(0).children[0].children[0]
    if fault == 'ambiguous':
        duplicate = Node('Other password', 'password text',
                         identity=GDM_CONTROLS['password'])
        duplicate.parent = surface
        surface.children.append(duplicate)
    if fault == 'other-label':
        other = Node(OTHER_PARENT, 'label', identity='unrelated-label')
        other.parent = surface
        surface.children.append(other)
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: 1 if fault == 'nonempty' else 0,
                                 get_text=Mock(side_effect=AssertionError('password text read')))
    if fault and fault != 'other-label':
        with pytest.raises(UiError): ui.run(operation, '')
    else:
        assert ui.run(operation, '')['outcome'] == 'passed'
    ui.api.Text.get_text.assert_not_called()
    field.get_child_count.assert_not_called()


def test_live_wrong_account_prompt_explicitly_refuses_parent_recipient():
    from accessible_ui import PARENT, OTHER_PARENT
    field = Node('Password', 'password text', states=('showing', 'visible', 'sensitive', 'focused'))
    field.get_text_iface = lambda: field
    ui = gdm_ui(recipient=Node(OTHER_PARENT, 'label'), field=field, list_showing=False)
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: 0)
    assert ui.run('gdm-wrong-recipient-refused', '')['outcome'] == 'passed'
    assert not ui.password_recipient(PARENT)


@pytest.mark.parametrize('fault', [None, 'skip-wrong', 'skip-first', 'replay', 'intervening-state'])
@pytest.mark.parametrize('standard', [False, True])
def test_controller_requires_fresh_recipient_recheck_without_wrong_account_detour(fault, standard):
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
    'delayed-launcher', 'labelled-result', 'disabled-suggestion', 'unrelated-description',
    'defunct-subtree', 'transient-stale'])
def test_standard_search_requires_query_web_result_and_stable_complete_absence(monkeypatch, fault):
    import accessible_ui
    product = accessible_ui.PRODUCT
    field = Node(product, 'text', identity=SEARCH_CONTROLS['search'])
    field.states.add('editable')
    field.value = 'wrong query' if fault == 'wrong-query' else product
    field.get_text_iface = lambda: field
    description = Node('Search "' + product + '" on the web', 'label')
    suggestion = Node('Search online', 'push button', children=[description],
                      identity=SEARCH_CONTROLS['web-suggestion::parent'])
    overview = Node('Overview', 'panel', children=[field, suggestion],
                    appearance={'scale': 2.5, 'font': 'ugly', 'misaligned': True})
    outside = []
    if fault == 'defunct-subtree': outside.append(Node('private-canary', states=('defunct',)))
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
    if fault == 'launcher': overview.children.append(Node(
        product, 'push button', identity=SEARCH_CONTROLS['result::parent']))
    if fault == 'unnamed-launcher':
        overview.children.append(Node('', 'push button', children=[Node(product, 'label')],
                                      identity=SEARCH_CONTROLS['result::parent']))
    if fault == 'management': outside.append(Node(product, 'frame', identity='parent-window'))
    if fault == 'stale-subtree':
        stale = Node('private-canary')
        stale.get_child_count = Mock(side_effect=LookupError('private-canary'))
        overview.children.append(stale)
    ui = search_ui(overview, outside=outside)
    root = ui.api.get_desktop(0)
    if fault == 'missing-overview': overview.identity = ''
    ui.query_errors = (LookupError,)
    ui.timeout = 5
    ui.api.Text = SimpleNamespace(get_character_count=lambda text: len(text.value),
                                 get_text=lambda text, start, end: text.value[start:end])
    now = [0.0]
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: now[0])
    def tick(seconds):
        now[0] += seconds
        if fault == 'transient-stale':
            root.states = {'defunct'} if 1 <= now[0] < 2 else {'showing', 'visible'}
        if fault == 'delayed-launcher' and now[0] >= 1:
            child = Node(product, 'push button', identity=SEARCH_CONTROLS['result::parent'])
            child.parent = overview
            overview.children.append(child)
    monkeypatch.setattr(accessible_ui.time, 'sleep', tick)
    if fault not in (None, 'labelled-result', 'transient-stale'):
        expected = ('system-prompt-observation-failed' if fault == 'stale-subtree'
                    else 'standard-parent-unavailable')
        with pytest.raises(UiError, match=expected):
            ui.run('standard-parent-unavailable', '')
    else:
        assert ui.run('standard-parent-unavailable', '') == {
            'operation': 'standard-parent-unavailable', 'outcome': 'passed', 'interface': 'AT-SPI'}
        assert now[0] >= 2
        if fault == 'transient-stale': assert now[0] >= 4
    suggestion.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'wrong-query', 'missing-description',
    'unrelated-description', 'launcher', 'disabled-launcher', 'management',
    'duplicate-suggestion', 'wrong-description', 'hidden-description',
    'disabled-suggestion', 'duplicate-field', 'wrong-owner', 'duplicate-owner',
    'incomplete-tree', 'delayed-launcher', 'transient-query', 'transient-description',
    'transient-incomplete', 'transient-defunct'])
def test_shell_search_adapter_proves_web_suggestion_and_stable_launcher_absence(
        monkeypatch, fault):
    product = accessible_ui.PRODUCT
    field = Node(product, 'text', states=('showing', 'visible', 'sensitive', 'editable'))
    field.value = 'Other query' if fault == 'wrong-query' else product
    field.get_text_iface = lambda: field
    description = Node('Search "' + product + '" on the web', 'label')
    suggestion = Node('Search online', 'push button', children=[description])
    overview = Node('Overview', 'panel', children=[field, suggestion])
    shell = Node('gnome-shell', 'application', children=[overview])
    desktop = Node(children=[shell])
    if fault == 'missing-description': suggestion.children.clear()
    if fault == 'wrong-description': description.name = 'Search for another product'
    if fault == 'hidden-description': description.states.remove('showing')
    if fault == 'disabled-suggestion': suggestion.states.remove('sensitive')
    if fault == 'wrong-owner': shell.name = 'unrelated application'
    if fault == 'duplicate-owner': desktop.children.append(Node('gnome-shell', 'application'))
    if fault == 'duplicate-field': overview.children.append(Node(
        'Search', 'text', states=('showing', 'visible', 'sensitive', 'editable')))
    if fault == 'unrelated-description':
        suggestion.children.clear()
        overview.children.append(description)
    if fault == 'launcher': overview.children.append(Node(product, 'push button'))
    if fault == 'disabled-launcher':
        overview.children.append(Node(product, 'push button', states=('showing', 'visible')))
    if fault == 'management': desktop.children.append(Node(identity='parent-window'))
    if fault == 'duplicate-suggestion':
        overview.children.append(Node('Search online', 'push button', children=[
            Node(description.name, 'label')]))
    ui = ui_for(desktop)
    # Absence reads the query from this same complete snapshot, never a second
    # field/tree whose result could conceal replacement of the original field.
    ui.search_query = Mock(side_effect=AssertionError('mixed search snapshots'))
    if fault == 'incomplete-tree': overview.children.append(None)
    ui.query_errors = (LookupError,)
    ui.timeout = 5
    ui.api.Text = SimpleNamespace(get_character_count=lambda text: len(text.value),
                                  get_text=lambda text, start, end: text.value[start:end])
    now = [0.0]
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: now[0])
    def tick(seconds):
        now[0] += seconds
        if fault == 'delayed-launcher' and now[0] >= 1:
            overview.children.append(Node(product, 'push button'))
        if fault == 'transient-query':
            field.value = 'O' if 1 <= now[0] < 2 else product
        if fault == 'transient-description':
            description.name = ('Other result' if 1 <= now[0] < 2 else
                                'Search "' + product + '" on the web')
        if fault == 'transient-incomplete':
            overview.children = [field, suggestion] + ([None] if 1 <= now[0] < 2 else [])
        if fault == 'transient-defunct':
            desktop.states = {'defunct'} if 1 <= now[0] < 2 else {'showing', 'visible'}
    monkeypatch.setattr(accessible_ui.time, 'sleep', tick)
    if fault not in (None, 'transient-query', 'transient-description',
                    'transient-incomplete', 'transient-defunct'):
        with pytest.raises(UiError):
            ui.run('standard-parent-unavailable', '')
    else:
        assert ui.run('standard-parent-unavailable', '') == {
            'operation': 'standard-parent-unavailable', 'outcome': 'passed',
            'interface': 'AT-SPI'}
        assert now[0] >= 2
        if fault: assert now[0] >= 4
    suggestion.action.do_action.assert_not_called()


@pytest.mark.parametrize('operation', ['standard-desktop', 'standard-app-grid', 'standard-search-entered',
                                      'standard-parent-unavailable'])
def test_standard_controller_rejects_private_text_and_wrong_operation(operation):
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(result).encode()))
    assert UiObservations(transport).observe(operation) == result
    result['private'] = 'private-canary'
    transport.call.return_value = json.dumps(result).encode()
    with pytest.raises(EvidenceError, match='response'):
        UiObservations(transport).observe(operation)


@pytest.mark.parametrize('fault', [None, 'hidden', 'disabled', 'noneditable', 'nonempty'])
def test_standard_typeahead_requires_visible_enabled_editable_empty_search(fault):
    field = Node('', 'text', identity=SEARCH_CONTROLS['search'])
    field.states.add('editable')
    field.get_text_iface = lambda: field
    if fault == 'hidden': field.states.remove('showing')
    if fault == 'disabled': field.states.remove('sensitive')
    if fault == 'noneditable': field.states.remove('editable')
    ui = search_ui(Node('Overview', 'panel', children=[field]))
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: 1 if fault == 'nonempty' else 0,
                                 get_text=lambda *_: '')
    if fault:
        with pytest.raises((UiError, LookupError)): ui.run('standard-app-grid', '')
    else:
        assert ui.run('standard-app-grid', '')['outcome'] == 'passed'
    field.action.do_action.assert_not_called()


@pytest.mark.parametrize('value', ['', 'wrong', 'O'])
def test_typeahead_requires_actual_first_character_before_remaining_input(value):
    field = Node('', 'text', states=('showing', 'visible', 'sensitive', 'editable'),
                 identity=SEARCH_CONTROLS['search'])
    field.get_text_iface = lambda: field
    ui = search_ui(Node('Overview', 'panel', children=[field]))
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: len(value), get_text=lambda *_: value)
    if value == 'O':
        assert ui.run('standard-search-started', '')['outcome'] == 'passed'
    else:
        with pytest.raises(UiError, match='standard-search-started'):
            ui.run('standard-search-started', '')


@pytest.mark.parametrize('value', ['', 'O', 'Oh No! Parent Control', 'Oh No! Parent Controls'])
def test_full_query_checkpoint_reads_exact_value_before_result(value):
    from accessible_ui import PRODUCT
    field = Node('', 'text', states=('showing', 'visible', 'sensitive', 'editable'),
                 identity=SEARCH_CONTROLS['search'])
    field.get_text_iface = lambda: field
    ui = search_ui(Node('Overview', 'panel', children=[field]))
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: len(value), get_text=lambda *_: value)
    if value == PRODUCT:
        assert ui.run('standard-search-entered', '')['outcome'] == 'passed'
    else:
        with pytest.raises(UiError, match='standard-search-entered'):
            ui.run('standard-search-entered', '')


@pytest.mark.parametrize('fault', ['', 'masked', 'hidden', 'unregistered', 'bound', 'too-long'])
def test_text_projection_uses_independent_field_and_never_reads_masked_or_unbounded_text(fault):
    from accessible_ui import PRODUCT
    field = Node('', 'password text' if fault == 'masked' else 'text',
                 states=('visible', 'editable') if fault == 'hidden' else ('showing', 'visible', 'editable'),
                 identity=SEARCH_CONTROLS['search'])
    field.get_text_iface = Mock(return_value=field)
    ui = search_ui(Node(children=[field]))
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: 10000 if fault == 'too-long' else len(PRODUCT),
                                 get_text=Mock(return_value=PRODUCT))
    def read():
        return ui.read_label(field, 'search-query', expected='private-canary' if fault == 'unregistered'
                             else PRODUCT, maximum=1 if fault == 'bound' else 80)
    if fault == 'too-long':
        assert not read()
        ui.api.Text.get_text.assert_not_called()
    elif fault:
        with pytest.raises(UiError): read()
        field.get_text_iface.assert_not_called()
    else:
        assert read()
        ui.api.Text.get_text.assert_called_once_with(field, 0, len(PRODUCT))


def test_accessibility_wait_delivers_pending_events_before_fresh_read():
    field = Node('', 'text')
    ui = ui_for(field)
    ui.dispatch = Mock(side_effect=lambda: field.states.add('focused'))
    assert ui.wait(lambda: ui.has_state(field, ui.api.StateType.FOCUSED), 'focus')
    ui.dispatch.assert_called_once_with()


@pytest.mark.parametrize('outcome', ['complete', 'persistent', 'duplicate', 'wrong-owner'])
def test_incomplete_transition_discards_the_read_without_replaying_input(monkeypatch, outcome):
    button = Node('About', 'button', identity='parent-menu-about')
    root = Node(identity='parent-window', children=[button])
    ui = ui_for(root)
    ui.activate(button)
    reads = []

    def child(index):
        reads.append(index)
        if len(reads) == 1:
            if outcome == 'duplicate':
                root.children.append(Node(identity='parent-menu-about'))
            elif outcome == 'wrong-owner':
                ui.owner_pids = lambda: {999}
            return None
        return None if outcome == 'persistent' else root.children[index]

    root.get_child_at_index = child
    ui.timeout = 1
    monkeypatch.setattr('accessible_ui.time.sleep', lambda _seconds: None)
    clock = iter((0, 0, 2))
    monkeypatch.setattr('accessible_ui.time.monotonic', lambda: next(clock))
    if outcome == 'complete':
        assert ui.id_target('parent-menu-about') is button
    else:
        expected = {'persistent': 'timeout:automation-id', 'duplicate': 'ambiguous-automation-id',
                    'wrong-owner': 'wrong-owner'}[outcome]
        with pytest.raises(UiError, match=expected) as caught:
            ui.id_target('parent-menu-about')
        if outcome == 'persistent':
            assert str(caught.value.__cause__) == 'ui:incomplete-tree'
    assert ui.incomplete_observations[0] == {
        'checkpoint': 'automation-id',
        'notes': ['Null child under public automation-id: parent-window'],
    }
    button.action.do_action.assert_called_once_with(0)


def test_event_storm_cannot_prevent_bounded_predicate_or_replay_action():
    button = Node('About', 'button', identity='test-about')
    ui = action_ui(button, 'test-about')
    ui.dispatch = Mock(return_value=True)
    ui.activate(button)
    with pytest.raises(UiError, match='timeout:missing-result'):
        ui.wait(lambda: False, 'missing-result')
    assert ui.dispatch.call_count == 32
    button.action.do_action.assert_called_once_with(0)


def test_search_field_excludes_noneditable_text_and_requires_editable_state():
    field = Node('', 'text', states=('showing', 'visible', 'sensitive', 'editable'),
                 identity=SEARCH_CONTROLS['search'])
    field.get_text_iface = lambda: field
    label_text = Node('Other text', 'text')
    label_text.get_text_iface = Mock(side_effect=AssertionError('noneditable text read'))
    ui = search_ui(Node('Overview', 'panel', children=[field, label_text]))
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: 0, get_text=lambda *_: '')
    assert ui.search_query('')
    field.states.remove('editable')
    assert not ui.search_query('')
    label_text.get_text_iface.assert_not_called()


@pytest.mark.parametrize('focused', [False, True])
def test_search_checkpoint_semantically_focuses_the_id_target(focused):
    field = Node('', 'text', states=('showing', 'visible', 'sensitive', 'editable'),
                 identity=SEARCH_CONTROLS['search'])
    if focused: field.states.add('focused')
    field.get_text_iface = lambda: field
    ui = search_ui(Node('Overview', 'panel', children=[field]))
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: 0, get_text=lambda *_: '')
    assert ui.run('standard-search-focused', '')['outcome'] == 'passed'
    field.component.grab_focus.assert_called_once_with()


@pytest.mark.parametrize('point', [{'x': -1, 'y': 2}, {'x': True, 'y': 2},
                                 {'x': 3.5, 'y': 2}, {'x': 3, 'y': 2, 'private': 'canary'}])
def test_retired_pointer_reply_is_rejected(point):
    result = {'operation': 'standard-app-grid', 'outcome': 'passed', 'interface': 'AT-SPI', 'pointer': point}
    with pytest.raises(EvidenceError, match='response'):
        UiObservations(SimpleNamespace(call=Mock(return_value=json.dumps(result).encode()))).observe('standard-app-grid')


def test_search_failure_diagnostic_redacts_window_names_and_text():
    field = Node('private-canary', 'text', identity=SEARCH_CONTROLS['search'])
    result = search_ui(Node(children=[field])).search_diagnostic()
    assert 'private' not in json.dumps(result)
    assert result == {'provider_surface': 'identified', 'identified_controls': ['search']}


@pytest.mark.parametrize('fault', [None, 'disabled', 'hidden', 'unfocused', 'unmasked',
                                  'nonempty',
                                  'missing-recipient', 'missing-secret', 'missing-confirm',
                                  'missing-cancel'])
def test_only_id_scoped_focused_keyring_prompt_authorizes_semantic_cancel(fault):
    ui, _dialog, controls = keyring_ui(fault=fault)
    if fault:
        with pytest.raises(UiError):
            ui.system_prompt_control()
    else:
        assert ui.system_prompt_control() is controls['cancel']
    for control in controls.values():
        control.action.do_action.assert_not_called()


def test_unqualified_or_wrong_owner_keyring_ids_block_without_actions():
    ui, _dialog, controls = keyring_ui()
    ui.provider_contracts['gcr-keyring-prompter']['application_id'] = None
    ui.api.get_desktop = Mock(side_effect=AssertionError('tree read'))
    with pytest.raises(UiError, match='unqualified-provider-application'):
        ui.system_prompt_control()
    ui.api.get_desktop.assert_not_called()
    for control in controls.values():
        control.action.do_action.assert_not_called()

    wrong = Node(identity='wrong-application', children=[
        Node(identity='test-keyring-dialog', children=list(controls.values()))])
    blocked = ui_for(wrong, provider_contracts=KEYRING_CONTRACTS)
    assert blocked.system_prompt_control() is None
    for control in controls.values():
        control.action.do_action.assert_not_called()


def test_id_qualified_polkit_prompt_blocks_keyring_middleware_without_input():
    ui, _dialog, keyring_controls = keyring_ui()
    polkit_controls = [Node(identity='test-polkit-' + name)
                       for name in ('recipient', 'secret', 'confirm', 'cancel')]
    polkit = Node(identity='test-polkit-application', children=[
        Node(identity='test-polkit-dialog', children=polkit_controls)])
    root = ui.api.get_desktop(0)
    polkit.parent = root
    root.children.append(polkit)
    with pytest.raises(UiError, match='unsupported-system-prompt'):
        ui.system_prompt_control()
    for control in (*keyring_controls.values(), *polkit_controls):
        control.action.do_action.assert_not_called()


@pytest.mark.parametrize('keys', [[], ['esc'], ['ret'], ['esc', 'esc'], 'esc', None, ['home']])
def test_system_prompt_checkpoint_cannot_authorize_unobserved_keyboard_input(keys):
    result = {'operation': 'standard-system-prompt', 'outcome': 'passed', 'interface': 'AT-SPI',
              'navigation': keys}
    session = UiObservations(SimpleNamespace(call=Mock(return_value=json.dumps(result).encode())))
    with pytest.raises(EvidenceError, match='response'):
        session.observe('standard-system-prompt')


def semantic_prompt(kind, *, count=1, incomplete=False):
    names = {
        'mate-polkit': ('PolicyKit Authentication Agent', 'Authentication Required'),
        'shell-polkit': ('GNOME Shell', 'Authentication Required'),
        'keyring': ('gcr-prompter', 'Unlock Login Keyring'),
        'unknown': ('Unregistered authentication agent', 'Password Required'),
    }
    application_name, title = names[kind]
    dialogs = []
    controls = []
    for _ in range(count):
        cancel = Node('Cancel', 'push button')
        children = [cancel]
        if kind != 'unknown':
            children.insert(0, Node('', 'password text'))
        dialog = Node(title, 'dialog', children=children,
                      states=('showing', 'visible', 'sensitive', 'modal'))
        dialogs.append(dialog)
        controls.extend(children)
    application = Node(application_name, 'application', children=dialogs)
    ui = ui_for(Node(role='desktop frame', children=[application]), qualify_prompts=False)
    if incomplete:
        application.children.append(None)
    return ui, controls


@pytest.mark.parametrize('session', ['station', 'desktop'])
@pytest.mark.parametrize('kind', ['mate-polkit', 'shell-polkit', 'keyring', 'unknown'])
def test_session_prompt_classifier_distinguishes_and_refuses_without_input(session, kind):
    ui, controls = semantic_prompt(kind)
    ui.prompt_enabled = True
    ui.prompt_session = session
    assert ui.system_prompt_kind() == kind
    with pytest.raises(UiError, match=f'system-prompt-refused:{session}:{kind}'):
        ui.handle_system_prompt()
    for control in controls:
        control.action.do_action.assert_not_called()


def test_system_prompt_classification_uses_one_complete_snapshot_without_rereads():
    ui, _controls = semantic_prompt('keyring')
    pending = [ui.api.get_desktop(0)]
    nodes = []
    while pending:
        node = pending.pop()
        nodes.append(node)
        pending.extend(node.children)
    getters = ('get_attributes', 'get_accessible_id', 'get_role_name',
               'get_name', 'get_state_set')
    for node in nodes:
        for getter in getters:
            setattr(node, getter, Mock(wraps=getattr(node, getter)))

    assert ui.system_prompt_kind() == 'keyring'

    for node in nodes:
        for getter in getters:
            getattr(node, getter).assert_called_once_with()


def test_system_prompt_observation_keeps_owned_subtrees_complete():
    owned_child = Node(identity='parent-window')
    owned_child.get_role_name = Mock(wraps=owned_child.get_role_name)
    owned = Node(role='application', identity=PARENT_APPLICATION,
                 children=[owned_child])
    external_ui, _controls = semantic_prompt('keyring')
    external = external_ui.api.get_desktop(0).children[0]
    ui = ui_for(Node(role='desktop frame', children=[owned, external]),
                qualify_prompts=False)

    assert ui.system_prompt_kind() == 'keyring'
    owned_child.get_role_name.assert_called_once_with()


@pytest.mark.parametrize('fault', ['ambiguous', 'incomplete'])
def test_system_prompt_ambiguous_or_incomplete_observation_blocks_without_input(fault):
    ui, controls = semantic_prompt('keyring', count=2 if fault == 'ambiguous' else 1,
                                   incomplete=fault == 'incomplete')
    ui.prompt_enabled = True
    ui.prompt_session = 'desktop'
    expected = 'ambiguous-system-prompt' if fault == 'ambiguous' else 'incomplete-tree'
    with pytest.raises(UiError, match=expected):
        ui.handle_system_prompt()
    for control in controls:
        control.action.do_action.assert_not_called()


def test_wrong_owner_prompt_surface_is_unknown_and_never_acted_on():
    ui, dialog, controls = keyring_ui()
    application = ui.api.get_desktop(0).children[-1]
    application.identity = 'wrong-application'
    application.name = 'Unregistered authentication agent'
    application.role = 'application'
    dialog.name = 'Password Required'
    dialog.role = 'dialog'
    dialog.states.add('modal')
    ui.prompt_enabled = True
    ui.prompt_session = 'desktop'
    with pytest.raises(UiError, match='system-prompt-refused:desktop:unknown'):
        ui.handle_system_prompt()
    for control in controls.values():
        control.action.do_action.assert_not_called()


def test_gdm_never_uses_desktop_prompt_handler():
    ui = gdm_ui(rows=[gdm_row('Jamie (Parent)', 'account-choice::parent')])
    ui.system_prompt_kind = Mock(side_effect=AssertionError('GDM must not inspect prompts'))
    ui.run('gdm-list', '')
    ui.system_prompt_kind.assert_not_called()


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
    with pytest.raises(EvidenceError, match='prompt-coordinate-route-refused'):
        session.observe(operation)
    handler.assert_not_called()
    assert commands.progress is previous
