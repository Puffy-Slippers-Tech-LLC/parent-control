"""Session menu, Switch User and confirmed Log Out stay on public controls."""

import json
from types import SimpleNamespace

import pytest

from accessible_ui import SESSION_ACTION_NAMES, SESSION_POINTER_OPERATIONS, UiError
from tests.support.accessible_ui import Node, ui_for
from tests.support.perl import run_perl


def pointer_box(x, y, width, height):
    return SimpleNamespace(
        get_extents=lambda _: SimpleNamespace(x=x, y=y, width=width, height=height))


POINTS = {
    'system': {'x': 1220, 'y': 20},
    'power': {'x': 1180, 'y': 52},
    'switch': {'x': 1180, 'y': 84},
    'logout': {'x': 1180, 'y': 108},
    'confirm': {'x': 680, 'y': 416},
}


def session_desktop(*, system_open=False, power_open=False, actions=True, confirm=False):
    activities = Node('Activities', 'button')
    system = Node('System', 'menu')
    system.get_component_iface = lambda: pointer_box(1200, 8, 40, 24)
    power = Node('Power Off Menu', 'push button')
    power.get_component_iface = lambda: pointer_box(1100, 40, 160, 24)
    switch = Node('Switch User…', 'menu item')
    switch.get_component_iface = lambda: pointer_box(1080, 72, 200, 24)
    logout = Node('Log Out…', 'menu item')
    logout.get_component_iface = lambda: pointer_box(1080, 96, 200, 24)
    confirm_button = Node('Log Out', 'push button')
    confirm_button.get_component_iface = lambda: pointer_box(600, 400, 160, 32)
    for node in (power, switch, logout, confirm_button):
        node.states.clear()
    if system_open:
        power.states.update(('showing', 'visible', 'sensitive'))
    if power_open and actions:
        switch.states.update(('showing', 'visible', 'sensitive'))
        logout.states.update(('showing', 'visible', 'sensitive'))
    if confirm:
        confirm_button.states.update(('showing', 'visible', 'sensitive'))
    children = [activities, system, power, switch, logout]
    if confirm:
        children.append(confirm_button)
    return ui_for(Node(role='desktop frame', children=children)), system, power, switch, logout, confirm_button


@pytest.mark.parametrize('fault', [None, 'no-desktop', 'no-system'])
def test_session_menu_toggle_returns_pointer_without_an_atk_action(fault):
    ui, system, power, switch, logout, _ = session_desktop()
    if fault == 'no-desktop':
        ui.api.get_desktop(0).children[:] = [system, power, switch, logout]
    if fault == 'no-system':
        ui.api.get_desktop(0).children.remove(system)
    if fault:
        with pytest.raises(UiError):
            ui.session_menu_toggle()
        return
    assert ui.session_menu_toggle() == {'x': 1220, 'y': 20}
    assert system.action.do_action.call_count == 0
    assert power.action.do_action.call_count == 0


@pytest.mark.parametrize('fault', [None, 'closed'])
def test_session_menu_power_returns_pointer_without_an_atk_action(fault):
    ui, system, power, switch, logout, _ = session_desktop(system_open=fault is None)
    if fault:
        with pytest.raises(UiError):
            ui.session_menu_power()
        return
    assert ui.session_menu_power() == POINTS['power']
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
def test_session_action_points_at_only_the_named_open_item(action, fault):
    ui, _, _, switch, logout, confirm = session_desktop(system_open=True, power_open=True)
    if fault == 'closed':
        switch.states.clear()
        logout.states.clear()
    if fault == 'three-dots':
        switch.name = 'Switch User...'
    if action not in SESSION_ACTION_NAMES or fault:
        with pytest.raises(UiError):
            ui.choose_session_action(action)
        assert switch.action.do_action.call_count == 0
        assert logout.action.do_action.call_count == 0
        return
    assert ui.choose_session_action(action) == POINTS['switch' if action == 'switch-user' else 'logout']
    assert switch.action.do_action.call_count == 0
    assert logout.action.do_action.call_count == 0
    assert confirm.action.do_action.call_count == 0


@pytest.mark.parametrize('fault', [None, 'menu-only', 'missing'])
def test_logout_confirm_points_at_the_dialog_button_not_the_ellipsis_item(fault):
    ui, _, _, switch, logout, confirm = session_desktop(
        system_open=True, power_open=True, confirm=fault != 'missing')
    if fault == 'menu-only':
        confirm.states.clear()
    if fault:
        with pytest.raises(UiError):
            ui.logout_confirm()
        assert confirm.action.do_action.call_count == 0
    else:
        assert ui.logout_confirm() == POINTS['confirm']
        assert confirm.action.do_action.call_count == 0
    assert switch.action.do_action.call_count == 0
    assert logout.action.do_action.call_count == 0


def test_session_action_follows_a_public_label_to_the_menu_item():
    activities = Node('Activities', 'button')
    system = Node('System', 'menu')
    system.get_component_iface = lambda: pointer_box(1200, 8, 40, 24)
    item = Node('', 'menu item')
    item.get_component_iface = lambda: pointer_box(1080, 72, 200, 24)
    label = Node('Switch User…', 'label')
    item.children = [label]
    label.parent = item
    logout = Node('Log Out…', 'menu item')
    logout.get_component_iface = lambda: pointer_box(1080, 96, 200, 24)
    ui = ui_for(Node(role='desktop frame', children=[activities, system, item, logout]))
    assert ui.choose_session_action('switch-user') == POINTS['switch']
    assert item.action.do_action.call_count == 0
    assert label.action.do_action.call_count == 0


def test_session_power_pointer_uses_the_smaller_showing_glyph():
    ui, _, power, *_ = session_desktop(system_open=True)
    icon = Node('', 'icon')
    icon.get_component_iface = lambda: pointer_box(1224, 48, 24, 24)
    power.children = [icon]
    icon.parent = power
    assert ui.session_menu_power() == {'x': 1236, 'y': 60}
    assert power.action.do_action.call_count == 0


@pytest.mark.parametrize('operation', [
    'session-menu-toggle', 'session-menu-power', 'session-menu',
    'switch-user', 'logout', 'logout-confirm',
])
def test_run_dispatches_session_operations(operation):
    ui, *_ = session_desktop(system_open=True, power_open=True, confirm=True)
    result = ui.run(operation, '')
    expected = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
    if operation in SESSION_POINTER_OPERATIONS:
        expected['pointer'] = POINTS[{
            'session-menu-toggle': 'system', 'session-menu-power': 'power',
            'switch-user': 'switch', 'logout': 'logout', 'logout-confirm': 'confirm',
        }[operation]]
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
    return {ui_pointer => {x => 1200, y => 20}} if $_[0] eq 'session-menu-toggle';
    return {ui_pointer => {x => 1180, y => 52}} if $_[0] eq 'session-menu-power';
    return {ui_pointer => {x => 1180, y => 84}} if $_[0] eq 'switch-user';
    return {ui_pointer => {x => 1180, y => 108}} if $_[0] eq 'logout';
    return {ui_pointer => {x => 680, y => 416}} if $_[0] eq 'logout-confirm';
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
                                   ['pointer', 1200, 20], ['click', 'left'],
                                   ['seen', 'session-menu-power'],
                                   ['pointer', 1180, 52], ['click', 'left'],
                                   ['seen', 'session-menu']]
    elif block == 'switch_user':
        assert result['events'] == [['seen', 'switch-user'],
                                   ['pointer', 1180, 84], ['click', 'left'],
                                   ['seen', 'gdm-switched']]
    else:
        assert result['events'] == [['seen', 'logout'],
                                   ['pointer', 1180, 108], ['click', 'left'],
                                   ['seen', 'logout-confirm'],
                                   ['pointer', 680, 416], ['click', 'left'],
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
        return {ui_keys => ['home', 'down']} if $_[0] =~ /(?:greeter|list)$/;
        return {ui_pointer => {x => 1200, y => 20}} if $_[0] eq 'session-menu-toggle';
        return {ui_pointer => {x => 1180, y => 52}} if $_[0] eq 'session-menu-power';
        return {ui_pointer => {x => 1180, y => 84}} if $_[0] eq 'switch-user';
        return {ui_pointer => {x => 1180, y => 108}} if $_[0] eq 'logout';
        return {ui_pointer => {x => 680, y => 416}} if $_[0] eq 'logout-confirm';
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
