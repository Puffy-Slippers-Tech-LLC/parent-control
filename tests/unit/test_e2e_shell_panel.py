"""Overlay entry guards and immutable readback with private synthetic trees."""

from dataclasses import FrozenInstanceError
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui as a
import check_e2e_shell_panel as check
from journey_blocks import overlay_entry
from parent_setup_qualification import ShellPanelQualification
from private_artifacts import EvidenceError
from shell_panel import PLAN
from tests.support.accessible_ui import Node, ui_for
from tests.support.e2e_kiosk import request_form
from tests.support.perl import run_perl
from ui_observations import UiObservations, RequestObservation


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
    child.description = 'Selected child account: ' + a.CHILD + '.'
    child.children[0].identity = 'kiosk-child-selected-1001'
    return ui, application, form, child


def panel(monkeypatch):
    child_session(monkeypatch)
    button = Node('Request time', 'push button', identity='child-request-button')
    indicator = Node(identity='child-screen-time-indicator', children=[button])
    shell = Node('gnome-shell', 'application', children=[
        Node('Activities', 'toggle button'), indicator])
    indicator.get_application = Mock(return_value=shell)
    root = Node(role='desktop frame', children=[shell])
    return ui_for(root), root, shell, button


@pytest.mark.parametrize('fault', ['', 'unlocked', 'wrong-child', 'duplicate-form', 'foreign-form',
    'wrong-application', 'expanded', 'defunct', 'missing', 'wrong-duration', 'mute', 'incomplete'])
def test_fixed_overlay_reader_refuses_unsafe_or_incomplete_forms(monkeypatch, fault):
    ui, application, form, child = overlay(monkeypatch)
    if fault == 'unlocked': child.states.add('sensitive')
    if fault == 'wrong-child':
        child.children[0].identity = 'kiosk-child-selected-1002'
        child.description = 'Selected child account: ' + a.EXISTING_CHILD + '.'
    if fault == 'duplicate-form':
        form.children.append(Node(identity='kiosk-request-form'))
    if fault == 'foreign-form':
        application.children.append(Node(identity='kiosk-request-form'))
    if fault == 'wrong-application': application.identity = a.KIOSK_APPLICATION
    if fault == 'expanded': form.children.append(Node(identity='kiosk-child-choice-1001'))
    if fault == 'defunct': child.states.add('defunct')
    if fault == 'missing': form.children.remove(child)
    if fault == 'wrong-duration': ui.find_id('kiosk-duration-1800').states.remove('pressed')
    if fault == 'mute': form.children.append(Node(identity='kiosk-mute-button'))
    if fault == 'incomplete': form.children.append(None)
    if fault:
        with pytest.raises(a.UiError): ui.run('overlay-request-form', '')
    else:
        observed = RequestObservation.from_request(ui.run('overlay-request-form', '')['request'],
                                                  operation='overlay-request-form')
        assert observed.surface == 'child-overlay' and observed.child == 'fixture-child'
        assert observed.approver == 'other-fixture-parent'
        assert observed.form_count == 1 and not observed.child_selector_enabled
        with pytest.raises(FrozenInstanceError): observed.child = 'changed'
    child.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'wrong-owner', 'duplicate', 'hidden', 'disabled',
                                   'prompt', 'wrong-account', 'defunct', 'incomplete', 'uncertain'])
def test_panel_launch_requires_owned_unlocked_child_and_never_replays(monkeypatch, fault):
    ui, root, shell, button = panel(monkeypatch)
    if fault == 'wrong-owner': shell.name = 'foreign-app'
    if fault == 'duplicate': shell.children.append(Node(identity='child-request-button'))
    if fault == 'hidden': button.states.discard('visible')
    if fault == 'disabled': button.states.discard('sensitive')
    if fault == 'prompt': ui.system_prompt_kind = Mock(return_value='keyring')
    if fault == 'wrong-account': monkeypatch.setattr(a.os, 'getuid', lambda: 1002)
    if fault == 'defunct': button.states.add('defunct')
    if fault == 'incomplete': shell.children.append(None)
    if fault == 'uncertain': button.action.do_action.side_effect = TimeoutError()
    if fault:
        with pytest.raises((a.UiError, TimeoutError)): ui.run('overlay-panel-launch', '')
        assert button.action.do_action.call_count == (1 if fault == 'uncertain' else 0)
    else:
        ui.run('overlay-panel-ready', '')
        button.action.do_action.assert_not_called()
        ui.run('overlay-panel-launch', '')
        button.action.do_action.assert_called_once()
    if fault in ('', 'uncertain'):
        with pytest.raises(a.UiError, match='uncertain-input'): ui.run('overlay-panel-launch', '')
        assert button.action.do_action.call_count == 1


@pytest.mark.parametrize('operation', ['child-command-launch', *sorted(a.OVERLAY_OPERATIONS)])
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


@pytest.mark.parametrize('fault', ['', 'child', 'surface', 'count', 'selector', 'controls', 'extra'])
def test_real_controller_decoder_retains_strict_immutable_projection(monkeypatch, fault):
    ui, _, _, _ = overlay(monkeypatch)
    result = ui.run('overlay-request-form', '')
    fields = result['request']
    if fault == 'child': fields['child'] = 'existing-fixture-child'
    if fault == 'surface': fields['surface'] = 'kiosk'
    if fault == 'count': fields['form_count'] = 2
    if fault == 'selector': fields['child_selector_enabled'] = True
    if fault == 'controls': fields['request_enabled'] = False
    if fault == 'extra': fields['private'] = 'canary'
    def call(*_args, on_output, **_kwargs):
        raw = (json.dumps(result) + '\n').encode()
        on_output(raw)
        return raw
    transport = SimpleNamespace(call=call, commands=SimpleNamespace(progress=None))
    observer = UiObservations(transport)
    if fault:
        with pytest.raises((EvidenceError, a.UiError)): observer.observe('overlay-request-form')
    else:
        value = observer.observe('overlay-request-form')['request']
        immutable = RequestObservation.from_request(value, operation='overlay-request-form')
        value['child'] = 'changed'
        assert immutable.child == 'fixture-child'


def test_overlay_reader_diagnostics_pass_through_real_controller(monkeypatch, capsys):
    ui, _, _, _ = overlay(monkeypatch)
    result = ui.run('overlay-request-form', '')
    diagnostics = capsys.readouterr().out.encode()
    # Enough progress to reproduce the live reply-size failure, with arbitrary
    # transport chunks and no prompt callback to select the stream parser.
    raw = diagnostics + (json.dumps(result) + '\n').encode()
    assert len(raw) > 2048
    def call(*_args, on_output, timeout, **_kwargs):
        assert timeout == 120
        for start in range(0, len(raw), 17):
            on_output(raw[start:start + 17])
        return raw
    transport = SimpleNamespace(call=call, commands=SimpleNamespace(progress=None))
    observed = UiObservations(transport).observe('overlay-request-form')
    assert RequestObservation.from_request(observed['request'],
        operation='overlay-request-form').child == 'fixture-child'
    assert capsys.readouterr().err.encode() == diagnostics
    assert transport.commands.progress is None


def test_overlay_closed_requires_complete_absence_and_desktop(monkeypatch):
    ui, _, shell, _ = panel(monkeypatch)
    ui.run('overlay-desktop', '')
    shell.children.append(Node(identity='kiosk-request-form'))
    with pytest.raises(a.UiError): ui.run('overlay-desktop', '')


def test_delayed_overlay_read_uses_the_existing_deadline(monkeypatch):
    ui, application, _, _ = overlay(monkeypatch)
    ui.timeout = 1
    ui.api.get_desktop = Mock(side_effect=[Node(role='desktop frame'), application])
    result = ui.run('overlay-request-form', '')
    assert result['request']['form_count'] == 1
    assert ui.api.get_desktop.call_count == 2


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


def test_fixed_selector_registration_and_snapshot_envelope(monkeypatch):
    calls = []
    monkeypatch.setattr(check, 'smoke', lambda **kw: calls.append(kw) or 0)
    assert check.main() == 0 and calls[0]['challenge_profile'] == 'shell-panel'
    context = SimpleNamespace()
    journey = ShellPanelQualification.journey(context, Mock())
    assert journey.plan is PLAN and context.installed_snapshot.startswith('onpc-v')
    assert all(tag[3:] in a.OPERATIONS for tag in PLAN.screen_tags.values() if tag.startswith('ui:'))


@pytest.mark.parametrize('route', ['command', 'panel'])
@pytest.mark.parametrize('fault', ['', 'launch', 'form'])
def test_shared_overlay_fragment_independent_caller_and_failure_stop(route, fault):
    screens = overlay_entry('another-caller', route)
    program = r'''
use strict; use warnings; use JSON::PP;
our @stages; our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi; sub record_info { }
package main; require onpc_request_flow;
my $declared = decode_json(shift @ARGV); my $route = shift @ARGV;
my $j = onpc_journey->new(prefix => 'independent', review => 0, exchange => sub {
    my ($stage) = @_; push @stages, $stage;
    die 'refusal' if $stage eq "another-caller-$fault";
    return {observed => $stage};
});
$j->declare_invocations($declared);
my $ok = eval { onpc_request_flow::overlay_entry($j, 'another-caller', $route); 1 };
print encode_json({ok => $ok ? 1 : 0, stages => \@stages});
'''
    result = json.loads(run_perl(program, fault, json.dumps(list(screens)), route).stdout)
    expected = list(screens)
    if fault: expected = expected[:expected.index('another-caller-' + fault) + 1]
    assert result['stages'] == expected and bool(result['ok']) == (not fault)
