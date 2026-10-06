"""Public request-station Cancel and Escape qualification contracts."""
from tools.test_storage import named_input

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui
from accessible_ui import KIOSK_APPLICATION, UiError
from tests.support.accessible_ui import Node, ui_for
from tests.support.paths import ROOT
from tests.support.perl import run_perl


def exit_form():
    cancel = Node('Cancel request', 'push button', identity='kiosk-request-cancel')
    form = Node(identity='kiosk-request-form', children=[cancel])
    window = Node(identity='kiosk-request-window', children=[form])

    def focus_cancel(_index):
        cancel.states.add('focused')
        return True
    window.action = SimpleNamespace(
        get_n_actions=lambda: 1,
        get_action_name=lambda _index: 'focus.kiosk-request-cancel',
        do_action=Mock(side_effect=focus_cancel),
    )
    application = Node(role='application', identity=KIOSK_APPLICATION, children=[window])
    return ui_for(Node(role='desktop frame', children=[application])), cancel


def greeter(*, password=False, product=False):
    parent = Node('Jamie (Parent)', 'push button')
    station = Node('Oh No! Parent Control', 'push button')
    children = [parent, station]
    if password:
        children = [Node('Jamie (Parent)', 'label'),
                    Node('Password', 'password text')]
    shell = Node('GNOME Shell', 'application', children=children)
    roots = [shell]
    if product:
        roots.append(Node(role='application', identity=KIOSK_APPLICATION, children=[
            Node(identity='kiosk-request-window', children=[
                Node(identity='kiosk-request-form')])]))
    return ui_for(Node(role='desktop frame', children=roots))


def test_cancel_activates_the_fresh_owned_control_once():
    ui, cancel = exit_form()
    ui.nodes = Mock(wraps=ui.nodes)
    assert ui.run('kiosk-request-cancel', '') == {
        'operation': 'kiosk-request-cancel', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider'}
    cancel.action.do_action.assert_called_once_with(0)
    cancel.parent.parent.action.do_action.assert_not_called()
    assert ui.nodes.call_count == 1


def test_exit_target_uses_one_complete_fresh_tree_per_observation():
    ui, cancel = exit_form()
    ui.nodes = Mock(wraps=ui.nodes)
    assert ui.kiosk_exit_target() is cancel
    assert ui.nodes.call_count == 1
    assert ui.nodes.call_args.kwargs['strict'] is True
    cancel.states.discard('sensitive')
    with pytest.raises(UiError):
        ui.kiosk_exit_target()
    assert ui.nodes.call_count == 2


EXIT_INPUTS = ('kiosk-request-cancel', 'kiosk-request-escape-ready',
               'overlay-request-cancel', 'overlay-request-escape-ready')


def exit_input_form(monkeypatch, operation):
    ui, cancel = exit_form()
    if operation.startswith('overlay-'):
        monkeypatch.setattr(accessible_ui.pwd, 'getpwnam',
                            lambda _: SimpleNamespace(pw_uid=1001))
        monkeypatch.setattr(accessible_ui.os, 'getuid', lambda: 1001)
        monkeypatch.setattr(accessible_ui.os, 'geteuid', lambda: 1001)
        monkeypatch.setattr(accessible_ui, 'require_active_launch_session', Mock())
        ui.api.get_desktop(0).children[0].identity = accessible_ui.CHILD_APPLICATION
    return ui, cancel


def add_unrelated_stale_leaf(ui):
    desktop = ui.api.get_desktop(0)
    unrelated = Node(role='application', children=[
        Node(states=('defunct',))])
    unrelated.parent = desktop
    desktop.children.append(unrelated)
    return unrelated


@pytest.mark.parametrize('operation', EXIT_INPUTS)
def test_exit_accepts_readable_unrelated_stale_leaf(monkeypatch, operation):
    ui, cancel = exit_input_form(monkeypatch, operation)
    add_unrelated_stale_leaf(ui)
    ui.nodes = Mock(wraps=ui.nodes)
    ui.run(operation, '')
    if operation.endswith('cancel'):
        cancel.action.do_action.assert_called_once_with(0)
        cancel.parent.parent.action.do_action.assert_not_called()
        assert ui.nodes.call_count == 1
    else:
        cancel.action.do_action.assert_not_called()
        cancel.parent.parent.action.do_action.assert_not_called()
        cancel.parent.parent.close.assert_called_once_with()


@pytest.mark.parametrize('operation', EXIT_INPUTS)
@pytest.mark.parametrize('scope', ['desktop', 'application', 'window', 'form',
                                  'cancel', 'anonymous-descendant', 'sibling-window'])
def test_exit_refuses_stale_root_or_any_owned_application_node(
        monkeypatch, operation, scope):
    ui, cancel = exit_input_form(monkeypatch, operation)
    desktop = ui.api.get_desktop(0)
    application = desktop.children[0]
    window = cancel.parent.parent
    nodes = {'desktop': desktop, 'application': application, 'window': window,
             'form': cancel.parent, 'cancel': cancel}
    if scope not in nodes:
        target = Node()
        target.parent = application if scope == 'sibling-window' else cancel.parent
        target.parent.children.append(target)
    else:
        target = nodes[scope]
    target.states.add('defunct')
    with pytest.raises(UiError, match='stale-request-form'):
        ui.run(operation, '')
    cancel.action.do_action.assert_not_called()
    window.action.do_action.assert_not_called()


@pytest.mark.parametrize('operation', EXIT_INPUTS)
@pytest.mark.parametrize('fault', ['missing-child', 'query-error'])
def test_exit_refuses_incomplete_unrelated_subtree(monkeypatch, operation, fault):
    ui, cancel = exit_input_form(monkeypatch, operation)
    unrelated = add_unrelated_stale_leaf(ui)
    if fault == 'missing-child':
        unrelated.children.append(None)
    else:
        unrelated.get_child_count = Mock(side_effect=RuntimeError('query failed'))
        ui.query_errors = (RuntimeError,)
    with pytest.raises((UiError, RuntimeError)):
        ui.run(operation, '')
    cancel.action.do_action.assert_not_called()
    cancel.parent.parent.action.do_action.assert_not_called()


@pytest.mark.parametrize('operation', EXIT_INPUTS)
@pytest.mark.parametrize('prompt', ['authentication', 'unknown', 'ambiguous'])
def test_exit_still_checks_all_desktop_prompts_with_unrelated_stale_leaf(
        monkeypatch, operation, prompt):
    ui, cancel = exit_input_form(monkeypatch, operation)
    add_unrelated_stale_leaf(ui)
    desktop = ui.api.get_desktop(0)
    for _ in range(2 if prompt == 'ambiguous' else 1):
        surface = Node('Authentication Required' if prompt == 'authentication' else
                       'External modal', 'dialog',
                       children=[Node('', 'password text')] if prompt == 'authentication' else [],
                       states=('showing', 'visible', 'sensitive', 'modal'))
        application = Node('PolicyKit Authentication Agent' if prompt == 'authentication' else
                           'External application', 'application', children=[surface])
        application.parent = desktop
        desktop.children.append(application)
    with pytest.raises(UiError, match='ambiguous-system-prompt' if prompt == 'ambiguous' else
                       'system-prompt-refused'):
        ui.run(operation, '')
    cancel.action.do_action.assert_not_called()
    cancel.parent.parent.action.do_action.assert_not_called()


def test_cancel_refused_action_is_never_replayed():
    ui, cancel = exit_form()
    cancel.action.do_action.return_value = False
    with pytest.raises(UiError, match='action-refused'):
        ui.run('kiosk-request-cancel', '')
    assert ui.input_uncertain
    with pytest.raises(UiError, match='uncertain-input'):
        ui.run('kiosk-request-cancel', '')
    cancel.action.do_action.assert_called_once_with(0)


def test_cancel_refuses_ambiguous_public_actions():
    ui, cancel = exit_form()
    cancel.action.get_n_actions = lambda: 2
    with pytest.raises(UiError, match='missing-or-ambiguous-action'):
        ui.run('kiosk-request-cancel', '')
    cancel.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['wrong-surface', 'duplicate-application', 'incomplete'])
def test_exit_snapshot_preserves_scope_ambiguity_and_completeness_guards(fault):
    ui, cancel = exit_form()
    desktop = ui.api.get_desktop(0)
    application = desktop.children[0]
    if fault == 'wrong-surface':
        cancel.parent.children = []
        cancel.parent = application
        application.children.append(cancel)
    elif fault == 'duplicate-application':
        duplicate = Node(role='application', identity=KIOSK_APPLICATION)
        duplicate.parent = desktop
        desktop.children.append(duplicate)
    else:
        application.children.append(None)
    with pytest.raises(UiError):
        ui.kiosk_exit_target()
    cancel.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['Failed', 'Timeout', 'OwnerChanged'])
def test_surface_close_failure_latches_without_replay(fault):
    from common.oh_no_parent_control_ui.application_ui_client import UIClientError
    ui, cancel = exit_form()
    ui.timeout = 0
    window = cancel.parent.parent
    window.close.side_effect = UIClientError(fault, uncertain=True)
    with pytest.raises(UIClientError):
        ui.run('kiosk-request-escape-ready', '')
    cancel.action.do_action.assert_not_called()
    assert ui.input_uncertain
    with pytest.raises(UiError, match='uncertain-input'):
        ui.run('kiosk-request-escape-ready', '')
    window.close.assert_called_once_with()


def test_surface_close_uses_the_owned_api_without_focus_or_cancel_activation():
    ui, cancel = exit_form()
    ui.nodes = Mock(wraps=ui.nodes)
    assert ui.run('kiosk-request-escape-ready', '') == {
        'operation': 'kiosk-request-escape-ready', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider'}
    cancel.parent.parent.action.do_action.assert_not_called()
    cancel.parent.parent.close.assert_called_once_with()
    cancel.component.grab_focus.assert_not_called()
    cancel.action.do_action.assert_not_called()
    assert not ui.input_uncertain


@pytest.mark.parametrize('operation', ['kiosk-request-cancel', 'kiosk-request-escape-ready'])
@pytest.mark.parametrize('fault', ['hidden', 'disabled', 'duplicate', 'stale', 'wrong-owner'])
def test_exit_input_refuses_unusable_ambiguous_stale_or_wrong_owned_targets(operation, fault):
    ui, cancel = exit_form()
    if fault == 'hidden':
        cancel.states.discard('showing')
    elif fault == 'disabled':
        cancel.states.discard('sensitive')
    elif fault == 'duplicate':
        cancel.parent.children.append(Node(identity='kiosk-request-cancel'))
    elif fault == 'stale':
        cancel.states.add('defunct')
    else:
        ui.application_owners = lambda: {KIOSK_APPLICATION: ()}
    with pytest.raises(UiError):
        ui.run(operation, '')
    cancel.action.do_action.assert_not_called()


@pytest.mark.parametrize('operation', ['kiosk-request-cancel', 'kiosk-request-escape-ready'])
def test_exit_input_refuses_an_active_authentication_prompt(operation):
    ui, cancel = exit_form()
    kiosk = ui.api.get_desktop(0).children[0]
    prompt_cancel = Node('Cancel', 'push button')
    prompt = Node('Authentication Required', 'dialog', children=[
        Node('', 'password text'), prompt_cancel],
        states=('showing', 'visible', 'sensitive', 'modal'))
    external = Node('PolicyKit Authentication Agent', 'application', children=[prompt])
    ui.api.get_desktop(0).children = [kiosk, external]
    kiosk.parent = ui.api.get_desktop(0)
    external.parent = ui.api.get_desktop(0)
    with pytest.raises(UiError, match='system-prompt-refused:station:mate-polkit'):
        ui.run(operation, '')
    cancel.action.do_action.assert_not_called()
    prompt_cancel.action.do_action.assert_not_called()


def test_return_observation_requires_form_disappearance_and_usable_greeter():
    ui = greeter()
    assert ui.run('gdm-station-returned', '') == {
        'operation': 'gdm-station-returned', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider'}
    assert all(not node.component.grab_focus.called for node in ui.nodes(strict=True))


@pytest.mark.parametrize('fault', ['password', 'product'])
def test_return_observation_refuses_prompt_or_remaining_product_surface(fault):
    with pytest.raises(UiError):
        greeter(password=fault == 'password', product=fault == 'product').run(
            'gdm-station-returned', '')


def test_request_exit_qualification_reuses_the_prepared_app_snapshot():
    import check_e2e_request_exit as check
    from parent_setup_qualification import RequestExitQualification

    assert check.ASSETS == named_input()
    context = type('Context', (), {})()
    RequestExitQualification.journey(context, lambda *_: None)
    # The prepared snapshot follows the app release, not the release at which
    # this qualification test was introduced.
    version = json.loads((ROOT / 'data/app.json').read_bytes())['version']
    assert context.installed_snapshot == f'onpc-v{version}'


@pytest.mark.parametrize('operation', accessible_ui.KIOSK_EXIT_OPERATIONS)
def test_exit_observer_uses_the_station_account_bus_without_waiting_for_services(
        monkeypatch, operation):
    def forbidden(*_args, **_kwargs):
        pytest.fail('request-station exit must use the station session bus')

    monkeypatch.setattr(accessible_ui, 'session_environment', forbidden)
    assert accessible_ui.observation_environment(
        SimpleNamespace(pw_uid=1234), operation) == {
            'XDG_RUNTIME_DIR': '/run/user/1234',
            'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/run/user/1234/bus',
        }


RUN = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub reset_consoles { push @main::events, ['reset'] }
sub select_console { push @main::events, ['console', $_[0]] }
sub send_key { push @main::events, ['key', $_[0]] }
sub record_info { push @main::events, ['stage', $_[0]] }
sub console { bless {}, 'Console' }
sub power { push @main::events, ['power', $_[0]] }
sub check_shutdown { 1 }
package Console;
sub disable { push @main::events, ['disable'] }
package main;
require onpc_request_exit;
my $ok = eval {
    onpc_request_exit::run(sub {
        my ($stage) = @_;
        push @events, ['exchange', $stage];
        return {ui_focused => 1} if $stage =~ /(?:greeter|station-list|focused)\z/;
        return {station_destination => 'default-request-form'} if $stage =~ /station-branch\z/;
        return {observed => $stage};
    });
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''


def test_worker_uses_direct_station_entries_for_cancel_and_escape():
    result = json.loads(run_perl(RUN).stdout)
    assert result['ok']
    exchanges = [event[1] for event in result['events'] if event[0] == 'exchange']
    expected_route = lambda route: [
        route + '-station-list', route + '-station-focused', route + '-station-branch',
        route + '-request-form',
    ]
    assert exchanges == [
        *expected_route('cancel'), 'cancel-action', 'cancel-returned',
        *expected_route('escape'), 'escape-ready', 'escape-returned',
    ]
    assert [event[1] for event in result['events'] if event[0] == 'key'] == [
        'ret', 'ret']
    assert result['events'][-3:] == [
        ['disable'], ['power', 'off'], ['stage', 'shutdown']]


def test_request_exit_is_the_fixed_argument_free_integration_selector():
    source = (ROOT / 'tests/integration/check_e2e_request_exit.py').read_text()
    assert "ASSETS = named_input()" in source
    assert 'request_exit=True' in source
    assert 'sys.argv' not in source


def test_shared_daily_station_preparation_stops_before_later_stages_on_failure():
    # Uses the existing private Perl/double resource profile; no live resources.
    from request_flow import daily_station_entry
    expected = ['limit-enabled', 'save-enabled', 'allowance-15-select',
                'allowance-15-read', 'time-explanation-read', 'switch-user',
                'gdm-switched', 'station-list', 'station-focused', 'station-branch']
    assert list(daily_station_entry()) == expected
    changed = daily_station_entry()
    changed.clear()
    assert list(daily_station_entry()) == expected
    script = r'''
use strict; use warnings; use JSON::PP;
BEGIN {$INC{'testapi.pm'}=1;}
package testapi; sub record_info {} sub send_key {} sub type_string {}
package main;
use onpc_request_flow; use onpc_journey;
my $stop = shift @ARGV;
my @events;
no warnings 'redefine';
*onpc_gdm::enter_station = sub {
    my ($j, $prefix) = @_;
    die 'wrong-entry' unless $prefix eq '';
    $j->seen($_) for ('station-list', 'station-focused', 'station-branch');
};
my $j = onpc_journey->new(prefix => 'independent-station', review => 0,
    exchange => sub {push @events, $_[0]; die 'refused' if $_[0] eq $stop;
                     return {observed => $_[0]};});
my $ok = eval {onpc_request_flow::daily_station_entry($j); 1;} ? 1 : 0;
print encode_json({ok => $ok, events => \@events});
'''
    for stop in ('', *expected):
        value = json.loads(run_perl(script, stop).stdout)
        assert value == {'ok': int(not stop), 'events':
                         expected[:expected.index(stop) + 1] if stop else expected}
