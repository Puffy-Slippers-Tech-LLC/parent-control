"""Overlay account, target ownership and single-input guards with private trees."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui as a
from tests.support.accessible_ui import Node, ui_for
from tests.support.e2e_kiosk import request_form


def child_session(monkeypatch):
    monkeypatch.setattr(a.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1001))
    monkeypatch.setattr(a.os, 'getuid', lambda: 1001)
    monkeypatch.setattr(a.os, 'geteuid', lambda: 1001)
    monkeypatch.setattr(a, 'require_active_launch_session', Mock())


def overlay(monkeypatch):
    child_session(monkeypatch)
    ui, _ = request_form()
    application = ui.api.get_desktop(0)
    application.identity = a.CHILD_APPLICATION
    form = ui.find_id('kiosk-request-form')
    for node in form.children:
        if node.identity == 'kiosk-screen-limit-notice':
            node.states.discard('showing')
        else:
            node.states.add('sensitive')
    child = ui.find_id('kiosk-child-selector')
    child.states.discard('sensitive')
    child.description = 'Selected account: ' + a.CHILD + '.'
    child.children[0].identity = 'kiosk-child-selected-1001'
    child.value = '1001'
    return ui, application, form, child


def panel(monkeypatch):
    child_session(monkeypatch)
    button = Node('Request time', 'push button', identity='child-request-button')
    button.ui_element = SimpleNamespace()
    button.activate = Mock()
    indicator = Node(identity='child-screen-time-indicator', children=[button])
    application = Node(role='application', identity=a.CHILD_PANEL_APPLICATION, children=[indicator])
    indicator.get_application = Mock(return_value=application)
    shell = Node('gnome-shell', 'application', children=[Node('Activities', 'toggle button')])
    root = Node(role='desktop frame', children=[shell, application])
    return ui_for(root), root, application, button


def test_panel_return_requires_existing_owned_request_form(monkeypatch):
    ui, _, _, button = panel(monkeypatch)
    with pytest.raises(a.UiError):
        ui.run('overlay-panel-overview', '')
    button.activate.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'wrong-owner', 'duplicate', 'hidden', 'disabled',
                                   'prompt', 'wrong-account', 'defunct', 'incomplete', 'uncertain'])
def test_panel_launch_requires_owned_child_target_and_never_replays_uncertain_input(monkeypatch, fault):
    ui, root, application, button = panel(monkeypatch)
    if fault == 'wrong-owner': application.identity = 'foreign-app'
    if fault == 'duplicate': application.children[0].children.append(Node(identity=button.identity))
    if fault == 'hidden': button.states.discard('visible')
    if fault == 'disabled': button.states.discard('sensitive')
    if fault == 'prompt': ui.system_prompt_kind = Mock(return_value='keyring')
    if fault == 'wrong-account': monkeypatch.setattr(a.os, 'getuid', lambda: 1002)
    if fault == 'defunct': button.states.add('defunct')
    if fault == 'incomplete': application.children.append(None)
    if fault == 'uncertain': button.activate.side_effect = TimeoutError()
    if fault:
        with pytest.raises((a.UiError, TimeoutError)):
            ui.run('overlay-panel-launch', '')
        assert button.activate.call_count == (1 if fault == 'uncertain' else 0)
    else:
        ui.run('overlay-panel-ready', '')
        button.activate.assert_not_called()
        ui.run('overlay-panel-launch', '')
        button.activate.assert_called_once_with()
    if fault == 'uncertain':
        with pytest.raises(a.UiError, match='uncertain-input'):
            ui.run('overlay-panel-launch', '')
        button.activate.assert_called_once_with()
    button.component.grab_focus.assert_not_called()
    button.action.do_action.assert_not_called()

@pytest.mark.parametrize('operation', ['child-command-launch', 'overlay-request-form',
                                      'overlay-panel-launch'])
def test_overlay_operations_bind_child_and_refuse_another_account(monkeypatch, operation):
    monkeypatch.setattr(a.sys, 'argv', ['observer', operation, '1.1'])
    monkeypatch.setattr(a.os, 'geteuid', lambda: 0)
    lookup = Mock(side_effect=LookupError('stop before connection'))
    monkeypatch.setattr(a.pwd, 'getpwnam', lookup)
    with pytest.raises(LookupError): a.main()
    lookup.assert_called_once_with(a.CHILD_ACCOUNTS[a.CHILD])
    child_session(monkeypatch)
    monkeypatch.setattr(a.os, 'getuid', lambda: 1002)
    ui = ui_for(Node())
    submit = Mock()
    monkeypatch.setattr(a.subprocess, 'run', submit)
    with pytest.raises(a.UiError, match='overlay-account'): ui.run(operation, '')
    submit.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'station-owner', 'uncertain'])
def test_qualification_cancel_is_owned_and_preserves_uncertain_input(monkeypatch, fault):
    ui, application, _, _ = overlay(monkeypatch)
    cancel = ui.find_id('kiosk-request-cancel')
    if fault == 'station-owner': application.identity = a.KIOSK_APPLICATION
    if fault == 'uncertain': cancel.action.do_action.side_effect = TimeoutError()
    if fault:
        with pytest.raises((a.UiError, TimeoutError)): ui.run('overlay-qualification-cancel', '')
    else:
        ui.run('overlay-qualification-cancel', '')
    assert cancel.action.do_action.call_count == (0 if fault == 'station-owner' else 1)
    if fault == 'uncertain':
        with pytest.raises(a.UiError, match='uncertain-input'): ui.run('overlay-qualification-cancel', '')
        assert cancel.action.do_action.call_count == 1
