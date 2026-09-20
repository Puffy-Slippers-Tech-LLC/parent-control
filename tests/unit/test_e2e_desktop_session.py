"""Session menu, Switch User and confirmed Log Out stay on public controls."""

import json
import copy

import pytest

from accessible_ui import SESSION_ACTION_NAMES, UiError
from tests.support.accessible_ui import Node, TEST_PROMPT_CONTRACTS, ui_for
from tests.support.perl import run_perl


SHELL_CONTROLS = {
    'desktop': {'desktop': 'test-shell-desktop-control'},
    'panel': {'quick-settings': 'test-shell-quick-settings'},
    'session-menu': {'power': 'test-shell-power', 'switch-user': 'test-shell-switch-user',
                     'log-out': 'test-shell-log-out'},
    'logout-dialog': {'confirm': 'test-shell-log-out-confirm'},
}
SHELL_CONTRACTS = copy.deepcopy(TEST_PROMPT_CONTRACTS)
SHELL_CONTRACTS['gnome-shell'] = {
    'application_id': 'test-shell-application',
    'surfaces': {surface: ('test-shell-' + surface, controls)
                 for surface, controls in SHELL_CONTROLS.items()},
    'blocked_consumers': (),
}


def session_desktop(*, system_open=False, power_open=False, actions=True, confirm=False):
    desktop = Node(identity=SHELL_CONTROLS['desktop']['desktop'])
    system = Node('System', 'menu', identity=SHELL_CONTROLS['panel']['quick-settings'])
    power = Node('Power Off Menu', 'push button', identity=SHELL_CONTROLS['session-menu']['power'])
    switch = Node('Switch User…', 'menu item', identity=SHELL_CONTROLS['session-menu']['switch-user'])
    logout = Node('Log Out…', 'menu item', identity=SHELL_CONTROLS['session-menu']['log-out'])
    confirm_button = Node('Log Out', 'push button', identity=SHELL_CONTROLS['logout-dialog']['confirm'])
    for node in (power, switch, logout, confirm_button):
        node.states.clear()
    if system_open:
        power.states.update(('showing', 'visible', 'sensitive'))
    if power_open and actions:
        switch.states.update(('showing', 'visible', 'sensitive'))
        logout.states.update(('showing', 'visible', 'sensitive'))
    if confirm:
        confirm_button.states.update(('showing', 'visible', 'sensitive'))
    surfaces = [
        Node(identity='test-shell-desktop', children=[desktop]),
        Node(identity='test-shell-panel', children=[system]),
        Node(identity='test-shell-session-menu', children=[power, switch, logout]),
        Node(identity='test-shell-logout-dialog', children=[confirm_button]),
    ]
    application = Node(identity='test-shell-application', children=surfaces)
    return (ui_for(application, provider_contracts=SHELL_CONTRACTS), system, power,
            switch, logout, confirm_button)


@pytest.mark.parametrize('fault', [None, 'no-desktop', 'no-system'])
def test_session_menu_toggle_requires_scoped_ids_without_an_atk_action(fault):
    ui, system, power, switch, logout, _ = session_desktop()
    if fault == 'no-desktop':
        ui.api.get_desktop(0).children[0].children.clear()
    if fault == 'no-system':
        ui.api.get_desktop(0).children[1].children.clear()
    if fault:
        with pytest.raises(UiError):
            ui.session_menu_toggle()
        return
    assert ui.session_menu_toggle() is system
    assert system.action.do_action.call_count == 0
    assert power.action.do_action.call_count == 0


@pytest.mark.parametrize('fault', [None, 'closed', 'disabled'])
def test_session_menu_power_requires_scoped_id_without_an_atk_action(fault):
    ui, system, power, switch, logout, _ = session_desktop(system_open=fault is None)
    if fault == 'disabled':
        power.states.update(('showing', 'visible'))
    if fault:
        with pytest.raises(UiError):
            ui.session_menu_power()
        return
    assert ui.session_menu_power() is power
    assert system.action.do_action.call_count == 0
    assert power.action.do_action.call_count == 0
    assert switch.action.do_action.call_count == 0
    assert logout.action.do_action.call_count == 0


@pytest.mark.parametrize('fault', [None, 'no-switch', 'no-logout'])
def test_session_menu_observes_both_actions_without_activating(fault):
    ui, system, power, switch, logout, _ = session_desktop(
        system_open=True, power_open=True, actions=fault is None)
    if fault == 'no-switch':
        logout.states.update(('showing', 'visible', 'sensitive'))
    if fault == 'no-logout':
        switch.states.update(('showing', 'visible', 'sensitive'))
    if fault:
        with pytest.raises(UiError):
            ui.session_menu()
    else:
        ui.session_menu()
    assert system.action.do_action.call_count == 0
    assert power.action.do_action.call_count == 0
    assert switch.action.do_action.call_count == 0
    assert logout.action.do_action.call_count == 0


@pytest.mark.parametrize('action, fault', [
    ('switch-user', None), ('logout', None),
    ('switch-user', 'closed'), ('logout', 'closed'),
    ('lock', None), ('switch-user', 'three-dots'),
])
def test_session_action_resolves_only_the_registered_open_item(action, fault):
    ui, _, _, switch, logout, confirm = session_desktop(system_open=True, power_open=True)
    if fault == 'closed':
        switch.states.clear()
        logout.states.clear()
    if fault == 'three-dots':
        switch.identity = ''
    if action not in SESSION_ACTION_NAMES or fault:
        with pytest.raises(UiError):
            ui.choose_session_action(action)
        assert switch.action.do_action.call_count == 0
        assert logout.action.do_action.call_count == 0
        return
    assert ui.choose_session_action(action) is (switch if action == 'switch-user' else logout)
    assert switch.action.do_action.call_count == 0
    assert logout.action.do_action.call_count == 0
    assert confirm.action.do_action.call_count == 0


@pytest.mark.parametrize('fault', [None, 'menu-only', 'missing'])
def test_logout_confirm_uses_the_dialog_scope_not_the_menu_item(fault):
    ui, _, _, switch, logout, confirm = session_desktop(
        system_open=True, power_open=True, confirm=fault != 'missing')
    if fault == 'menu-only':
        confirm.states.clear()
    if fault:
        with pytest.raises(UiError):
            ui.logout_confirm()
        assert confirm.action.do_action.call_count == 0
    else:
        assert ui.logout_confirm() is confirm
        assert confirm.action.do_action.call_count == 0
    assert switch.action.do_action.call_count == 0
    assert logout.action.do_action.call_count == 0


def test_session_action_refuses_matching_label_outside_registered_surface():
    ui, _, _, switch, *_ = session_desktop(system_open=True, power_open=True)
    switch.identity = ''
    ui.api.get_desktop(0).children.append(Node('Switch User…', 'menu item'))
    with pytest.raises(UiError):
        ui.choose_session_action('switch-user')


@pytest.mark.parametrize('operation', [
    'session-menu-toggle', 'session-menu-power', 'session-menu',
    'switch-user', 'logout', 'logout-confirm',
])
def test_run_dispatches_session_operations(operation):
    ui, *_ = session_desktop(system_open=True, power_open=True, confirm=True)
    result = ui.run(operation, '')
    expected = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
    assert result == expected


LEAF = r'''
use strict;
use warnings;
use JSON::PP;
our ($block, $fault) = @ARGV;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub record_info { }
sub send_key { push @main::events, ['key', @_]; }
sub mouse_set { push @main::events, ['pointer', @_]; }
sub mouse_click { push @main::events, ['click', $_[0] // 'left']; }
sub console { bless {}, 'Console' }
package Console;
sub mouse_width { 1280 }
sub mouse_height { 800 }
package main;
require onpc_desktop_session;
my $journey = onpc_journey->new(prefix => 'unit', review => 0, exchange => sub {
    push @events, ['seen', $_[0]];
    return {};
});
my $ok = eval {
    if ($block eq 'open_menu') {
        my $desktop = $journey->seen($fault eq 'wrong-desktop' ? 'session-menu' : 'desktop');
        @events = ();
        onpc_desktop_session::open_menu($journey, $desktop);
        onpc_desktop_session::open_menu($journey, $desktop) if $fault eq 'replay';
    } else {
        $journey->seen('desktop');
        my $menu = $fault eq 'stale-menu' ? {} : $journey->seen('session-menu');
        @events = ();
        if ($block eq 'switch_user') {
            onpc_desktop_session::switch_user($journey, $menu);
            onpc_desktop_session::switch_user($journey, $menu) if $fault eq 'replay';
        } else {
            onpc_desktop_session::log_out($journey, $menu);
            onpc_desktop_session::log_out($journey, $menu) if $fault eq 'replay';
        }
    }
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''


@pytest.mark.parametrize('block, fault', [
    ('open_menu', ''),
    ('open_menu', 'wrong-desktop'),
    ('open_menu', 'replay'),
    ('switch_user', ''),
    ('switch_user', 'stale-menu'),
    ('switch_user', 'replay'),
    ('log_out', ''),
    ('log_out', 'stale-menu'),
    ('log_out', 'replay'),
])
def test_session_helpers_consume_fresh_proofs_without_replay(block, fault):
    result = json.loads(run_perl(LEAF, block, fault).stdout)
    assert result['ok'] == (not fault)
    if fault:
        if fault == 'replay':
            assert result['events']
        else:
            assert not result['events']
        return
    if block == 'open_menu':
        assert result['events'] == [['seen', 'session-menu-toggle'],
                                   ['seen', 'session-menu-power'],
                                   ['seen', 'session-menu']]
    elif block == 'switch_user':
        assert result['events'] == [['seen', 'switch-user'],
                                   ['seen', 'gdm-switched']]
    else:
        assert result['events'] == [['seen', 'logout'],
                                   ['seen', 'logout-confirm'],
                                   ['seen', 'gdm-logged-out']]


RUN_PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our $action = $ARGV[0];
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub reset_consoles { }
sub select_console { }
sub get_var { $_[0] eq 'NOVIDEO' ? '1' : $_[1] }
sub get_required_var { 'unit-fixture-value' }
sub type_password { push @main::events, ['secret']; }
sub type_string { push @main::events, ['text', $_[0]]; }
sub send_key { push @main::events, ['key', $_[0]]; }
sub save_screenshot { die 'explicit capture forbidden'; }
sub record_info { }
sub mouse_set { push @main::events, ['pointer', @_]; }
sub mouse_click { push @main::events, ['click', $_[0] // 'left']; }
sub console { bless {}, 'Console' }
sub power { push @main::events, ['power', $_[0]]; }
sub check_shutdown { 1 }
package Console;
sub disable { }
sub mouse_width { 1280 }
sub mouse_height { 800 }
package main;
require onpc_desktop_session;
my $ok = eval {
    onpc_desktop_session::run(sub {
        push @events, ['stage', $_[0]];
        return {observed => $_[0]} if $_[0] =~ /recipient-(?:qualified|rechecked)\z/;
        return {ui_focused => 1} if $_[0] =~ /(?:greeter|list)$/;
        return {observed => $_[0]};
    }, $action);
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''


@pytest.mark.parametrize('action', ['logout', 'switch-user', 'lock'])
def test_complete_worker_matches_the_selected_plan_and_powers_off(action):
    from desktop_session import LOGOUT_PLAN, SWITCH_PLAN
    result = json.loads(run_perl(RUN_PROBE, action).stdout)
    if action == 'lock':
        assert not result['ok']
        assert not result['events']
        return
    assert result['ok']
    plan = LOGOUT_PLAN if action == 'logout' else SWITCH_PLAN
    assert [event[1] for event in result['events'] if event[0] == 'stage'] == list(plan.screen_tags)
    assert result['events'].count(['secret']) == 1
    assert result['events'][-1] == ['power', 'off']


def test_plans_declare_every_stage_and_keep_prefixes_distinct():
    from desktop_session import LOGOUT_PLAN, SWITCH_PLAN
    for plan in (LOGOUT_PLAN, SWITCH_PLAN):
        assert set(plan.phases) == set(plan.stages)
        assert set(plan.advance_after) <= set(plan.screen_tags)
        assert plan.advance_after['desktop'] == 'step-2'
    assert LOGOUT_PLAN.prefix != SWITCH_PLAN.prefix
    assert LOGOUT_PLAN.worker_mode != SWITCH_PLAN.worker_mode
