"""System session helpers preserve fixture identity and never navigate menus."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import session_control as control
from accessible_ui import OPERATIONS, UiError
from tests.support.accessible_ui import Node, ui_for
from tests.support.perl import run_perl


def props(uid='1000', *, active='yes', locked='no', kind='user', remote='no', seat='seat0'):
    return {'User': uid, 'Active': active, 'LockedHint': locked, 'Class': kind,
            'Remote': remote, 'Seat': seat, 'Type': 'wayland'}


@pytest.mark.parametrize('fault', ['wrong-owner', 'remote', 'wrong-seat', 'greeter',
                                   'wrong-lock-state', 'multiple-active', 'multiple-owned', 'missing'])
@pytest.mark.parametrize('locked', [False, True])
def test_source_refuses_wrong_or_ambiguous_sessions(fault, locked):
    source = props(locked='yes' if locked else 'no')
    current = {'7': source}
    if fault == 'wrong-owner':
        source['User'] = '1001'
    elif fault == 'remote':
        source['Remote'] = 'yes'
    elif fault == 'wrong-seat':
        source['Seat'] = 'seat1'
    elif fault == 'greeter':
        source['Class'] = 'greeter'
    elif fault == 'wrong-lock-state':
        source['LockedHint'] = 'no' if locked else 'yes'
    elif fault == 'multiple-active':
        current['8'] = props('1001')
    elif fault == 'multiple-owned':
        current['8'] = props(active='no')
    else:
        current.clear()
    with pytest.raises(control.SessionError):
        control.source_session(current, 1000, locked=locked)


def test_source_and_independent_results_distinguish_logout_lock_and_switch():
    assert control.source_session({'7': props()}, 1000) == '7'
    assert control.source_session({'7': props(locked='yes')}, 1000, locked=True) == '7'
    greeter = props('120', kind='greeter')
    switched = {'7': props(active='no', locked='yes'), '8': greeter}
    assert control.destination(switched, '7', 1000, 'switch-user')
    assert control.destination(switched, '7', 1000, 'return-greeter')
    assert not control.destination({'7': props(locked='yes')}, '7', 1000, 'return-greeter')
    assert not control.destination({'7': props(active='no'), '8': greeter},
                                   '7', 1000, 'return-greeter')
    assert not control.destination(switched, '7', 1000, 'logout')
    assert control.destination({'8': greeter}, '7', 1000, 'logout')
    assert not control.destination({'7': props()}, '7', 1000, 'lock')
    assert control.destination({'7': props(locked='yes')}, '7', 1000, 'lock')
    for action in ('switch-user', 'return-greeter'):
        with pytest.raises(control.SessionError, match='source-lost'):
            control.destination({'8': greeter}, '7', 1000, action)
        with pytest.raises(control.SessionError, match='source-replaced'):
            control.destination({'7': props('1001'), '8': greeter}, '7', 1000, action)


def test_logout_is_one_direct_command_without_force_or_a_shell(monkeypatch):
    call = Mock()
    monkeypatch.setattr(control, 'call', call)
    control.submit('logout')
    call.assert_called_once_with(['/usr/bin/gnome-session-quit', '--logout', '--no-prompt'])
    call.reset_mock()
    call.side_effect = TimeoutError
    with pytest.raises(TimeoutError):
        control.submit('logout')
    assert call.call_count == 1


@pytest.mark.parametrize('action', ['switch-user', 'return-greeter'])
def test_greeter_command_locks_only_an_unlocked_source_and_never_retries(monkeypatch, action):
    events = []
    gdm = SimpleNamespace(goto_login_session_sync=Mock())
    monkeypatch.setitem(__import__('sys').modules, 'gi', SimpleNamespace(require_version=Mock()))
    monkeypatch.setitem(__import__('sys').modules, 'gi.repository', SimpleNamespace(Gdm=gdm))
    monkeypatch.setattr(control, 'call', lambda argv: events.append(argv))
    control.submit(action)
    if action == 'switch-user':
        assert events[0] == [
            '/usr/bin/gdbus', 'call', '--session', '--dest', 'org.gnome.ScreenSaver',
            '--object-path', '/org/gnome/ScreenSaver', '--method', 'org.gnome.ScreenSaver.Lock']
    assert len(events) == (2 if action == 'switch-user' else 1)
    assert events[-1][:8] == [
        '/usr/bin/systemd-run', '--user', '--quiet', '--collect', '--wait',
        '--pipe', '--service-type=exec', '/usr/bin/python3']
    assert events[-1][8:10] == ['-I', '-c']
    assert 'Gdm.goto_login_session_sync(None)' in events[-1][-1]
    gdm.goto_login_session_sync.assert_not_called()
    events.clear()
    def fail(_):
        events.append('failed-command')
        raise TimeoutError
    monkeypatch.setattr(control, 'call', fail)
    with pytest.raises(TimeoutError):
        control.submit(action)
    assert events == ['failed-command']


@pytest.mark.parametrize('binding', ['root-logout', 'parent-reboot', 'parent-logout;id', ''])
def test_unregistered_commands_refuse_before_session_lookup(monkeypatch, binding):
    read = Mock()
    monkeypatch.setattr(control, 'sessions', read)
    with pytest.raises(control.SessionError, match='binding'):
        control.execute(binding)
    read.assert_not_called()


@pytest.mark.parametrize('fault', ['initial-owner', 'changed-source', 'initial-lock', 'changed-lock'])
@pytest.mark.parametrize('binding', ['parent-logout', 'standard-return-greeter'])
def test_execute_checks_ownership_and_lock_state_again_after_dropping_privileges(
        monkeypatch, fault, binding):
    role, action = control.BINDINGS[binding]
    locked = 'yes' if action == 'return-greeter' else 'no'
    wrong_lock = 'no' if locked == 'yes' else 'yes'
    account = SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name=control.ACCOUNTS[role])
    monkeypatch.setattr(control.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(control.pwd, 'getpwnam', lambda _: account)
    monkeypatch.setattr(control, 'environment', lambda _: {})
    monkeypatch.setattr(control.os, 'environ', {})
    for name in ('initgroups', 'setgid', 'setuid'):
        monkeypatch.setattr(control.os, name, Mock())
    monkeypatch.setattr(control, 'sessions', Mock(side_effect=[
        {'7': props('1001' if fault == 'initial-owner' else '1000',
                    locked=wrong_lock if fault == 'initial-lock' else locked)},
        {'8' if fault == 'changed-source' else '7':
            props(locked=wrong_lock if fault == 'changed-lock' else locked)},
    ]))
    submit = Mock()
    monkeypatch.setattr(control, 'submit', submit)
    with pytest.raises(control.SessionError):
        control.execute(binding)
    submit.assert_not_called()


@pytest.mark.parametrize('operation', ['session-menu-toggle', 'session-menu-power',
                                       'session-menu', 'switch-user', 'logout', 'logout-confirm'])
def test_removed_shell_gui_operations_cannot_execute(operation):
    assert operation not in OPERATIONS
    ui = ui_for(Node())
    with pytest.raises(UiError, match='operation'):
        ui.run(operation, '')


@pytest.mark.parametrize('binding', ['parent-logout', 'standard-switch-user',
                                    'parent-return-greeter', 'standard-return-greeter'])
def test_controller_requires_command_result_over_guarded_transport(binding):
    role, action = control.BINDINGS[binding]
    expected = {'operation': binding, 'outcome': 'passed', 'interface': 'system session',
                'source_retained': action != 'logout', 'destination': 'greeter'}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(expected).encode()))
    assert control.observe(transport, binding) == expected
    assert transport.call.call_args.args[0] == ['/usr/bin/python3', '-I', '-', binding]
    assert transport.call.call_args.kwargs['input'] == __import__('pathlib').Path(control.__file__).read_bytes()
    transport.call.return_value = b'{}'
    with pytest.raises(control.SessionError, match='response'):
        control.observe(transport, binding)


LEAF = r'''
use strict;
use warnings;
use JSON::PP;
our ($block, $fault) = @ARGV;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
package main;
require onpc_desktop_session;
my $journey = onpc_journey->new(prefix => 'unit', review => 0, exchange => sub {
    push @events, ['seen', $_[0]];
    return {};
});
my $desktop = $journey->seen('desktop');
$desktop = {} if $fault eq 'stale';
@events = ();
my $ok = eval {
    if ($block eq 'switch_user') {
        onpc_desktop_session::switch_user($journey, $desktop);
        onpc_desktop_session::switch_user($journey, $desktop) if $fault eq 'replay';
    } else {
        onpc_desktop_session::log_out($journey, $desktop);
        onpc_desktop_session::log_out($journey, $desktop) if $fault eq 'replay';
    }
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''


@pytest.mark.parametrize('block', ['switch_user', 'log_out'])
@pytest.mark.parametrize('fault', ['', 'stale', 'replay'])
def test_session_workers_consume_fresh_desktop_proofs_once(block, fault):
    result = json.loads(run_perl(LEAF, block, fault).stdout)
    assert result['ok'] == (not fault)
    expected = ([['seen', 'switch-user'], ['seen', 'gdm-switched']] if block == 'switch_user'
                else [['seen', 'logout'], ['seen', 'gdm-logged-out']])
    assert result['events'] == ([] if fault == 'stale' else expected)


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
