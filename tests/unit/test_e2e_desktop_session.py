"""System session helpers preserve fixture identity and never navigate menus."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import session_control as control
from accessible_ui import OPERATIONS, UiError
from tests.support.accessible_ui import Node, ui_for
from tests.support.desktop_session import RUN_PROBE, props
from tests.support.perl import run_perl


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


@pytest.mark.parametrize('binding', ['root-logout', 'parent-reboot', 'parent-logout;id',
                                    'standard-continuous-activity', ''])
def test_unregistered_commands_refuse_before_session_lookup(monkeypatch, binding):
    read = Mock()
    monkeypatch.setattr(control, 'sessions', read)
    with pytest.raises(control.SessionError, match='binding'):
        control.execute(binding)
    read.assert_not_called()


@pytest.mark.parametrize('fault', ['initial-owner', 'changed-source', 'initial-lock', 'changed-lock'])
@pytest.mark.parametrize('binding', ['parent-switch-user', 'parent-logout',
                                    'standard-return-greeter', 'parent-continuous-activity'])
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
    prepare = Mock()
    monkeypatch.setattr(control, 'prepare_continuous_activity', prepare)
    with pytest.raises(control.SessionError):
        control.execute(binding)
    submit.assert_not_called()
    prepare.assert_not_called()


@pytest.mark.parametrize('previous', [0, 300, 4294967295])
def test_continuous_activity_disables_only_idle_blanking_and_reads_back(monkeypatch, previous):
    call = Mock(side_effect=[f'uint32 {previous}\n', '', 'uint32 0\n'])
    monkeypatch.setattr(control, 'call', call)
    assert control.prepare_continuous_activity() == previous
    assert [item.args[0] for item in call.call_args_list] == [
        ['/usr/bin/gsettings', 'get', 'org.gnome.desktop.session', 'idle-delay'],
        ['/usr/bin/gsettings', 'set', 'org.gnome.desktop.session', 'idle-delay', 'uint32 0'],
        ['/usr/bin/gsettings', 'get', 'org.gnome.desktop.session', 'idle-delay'],
    ]


@pytest.mark.parametrize('responses,calls,exception', [
    (['300'], 1, control.SessionError),
    (['uint32 4294967296'], 1, control.SessionError),
    (['uint32 300', TimeoutError()], 2, TimeoutError),
    (['uint32 300', '', 'uint32 300'], 3, control.SessionError),
])
def test_continuous_activity_refuses_bad_values_and_never_replays(monkeypatch, responses, calls, exception):
    command = Mock(side_effect=responses)
    monkeypatch.setattr(control, 'call', command)
    with pytest.raises(exception):
        control.prepare_continuous_activity()
    assert command.call_count == calls


@pytest.mark.parametrize('source_changed', [False, True])
def test_continuous_activity_belongs_to_the_bound_unprivileged_parent(monkeypatch, source_changed):
    account = SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name=control.ACCOUNTS['parent'])
    identity = [0]
    monkeypatch.setattr(control.os, 'geteuid', lambda: identity[0])
    monkeypatch.setattr(control.pwd, 'getpwnam', lambda _: account)
    monkeypatch.setattr(control, 'environment', lambda _: {'fixture': 'parent'})
    monkeypatch.setattr(control.os, 'environ', {})
    monkeypatch.setattr(control.os, 'initgroups', Mock())
    monkeypatch.setattr(control.os, 'setgid', Mock())
    monkeypatch.setattr(control.os, 'setuid', lambda uid: identity.__setitem__(0, uid))
    monkeypatch.setattr(control, 'sessions', Mock(side_effect=[
        {'7': props()}, {'7': props()}, {'8' if source_changed else '7': props()}]))
    def prepare():
        assert identity[0] == 1000
        assert control.os.environ == {'fixture': 'parent'}
        return 300
    operation = Mock(side_effect=prepare)
    monkeypatch.setattr(control, 'prepare_continuous_activity', operation)
    if source_changed:
        with pytest.raises(control.SessionError, match='source-changed'):
            control.execute('parent-continuous-activity')
    else:
        assert control.execute('parent-continuous-activity') == {
            'operation': 'parent-continuous-activity', 'outcome': 'passed',
            'interface': 'system session', 'idle_delay_seconds': 0,
            'previous_idle_delay_seconds': 300}
    operation.assert_called_once_with()


@pytest.mark.parametrize('fault', [None, 'enabled', 'boolean', 'missing', 'out-of-range'])
def test_continuous_activity_controller_requires_exact_readback(monkeypatch, fault):
    result = {'operation': 'parent-continuous-activity', 'outcome': 'passed',
              'interface': 'system session', 'idle_delay_seconds': 0,
              'previous_idle_delay_seconds': 300}
    if fault == 'enabled': result['idle_delay_seconds'] = 300
    if fault == 'boolean': result['idle_delay_seconds'] = False
    if fault == 'missing': del result['previous_idle_delay_seconds']
    if fault == 'out-of-range': result['previous_idle_delay_seconds'] = 4294967296
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(result).encode()))
    if fault:
        with pytest.raises(control.SessionError, match='response'):
            control.observe(transport, 'parent-continuous-activity')
    else:
        assert control.observe(transport, 'parent-continuous-activity') == result
    transport.call.assert_called_once()
    assert transport.call.call_args.args[0] == [
        '/usr/bin/python3', '-I', '-', 'parent-continuous-activity']


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


def test_session_qualification_uses_installed_snapshot_and_separate_attempts():
    import check_e2e_desktop_session as check
    from parent_setup_qualification import (DesktopLogoutQualification,
                                            DesktopSwitchQualification, KioskEntryQualification)

    for qualification, mode in ((DesktopLogoutQualification, 'desktop_session_logout'),
                                (DesktopSwitchQualification, 'desktop_session_switch')):
        assert issubclass(qualification, KioskEntryQualification)
        context = SimpleNamespace()
        journey = qualification.journey(context, Mock())
        assert context.installed_snapshot == 'onpc-v1.1'
        assert journey.plan.worker_mode == mode

    calls = []
    original = check.smoke
    try:
        check.smoke = lambda **kwargs: calls.append(kwargs) or 0
        assert check.main() == 0
    finally:
        check.smoke = original
    assert calls == [
        {'assets': check.ASSETS, 'provision_credentials': True,
         'desktop_session_logout': True},
        {'assets': check.ASSETS, 'provision_credentials': True,
         'desktop_session_switch': True},
    ]

    calls.clear()
    check.smoke = lambda **kwargs: calls.append(kwargs) or 1
    try:
        assert check.main() == 1
    finally:
        check.smoke = original
    assert calls == [{'assets': check.ASSETS, 'provision_credentials': True,
                      'desktop_session_logout': True}]
