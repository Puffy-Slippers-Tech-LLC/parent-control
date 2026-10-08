"""System session helpers preserve fixture identity and never navigate menus."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import session_control as control


from accessible_ui import OPERATIONS, UiError
from tests.support.accessible_ui import Node, ui_for
from tests.support.desktop_session import RUN_PROBE, props
from tests.support.paths import ROOT
from tests.support.perl import run_perl


PACKAGE_FORMAT = control.package_format


@pytest.fixture(autouse=True)
def platform(monkeypatch):
    monkeypatch.setattr(control, 'package_format', lambda: 'deb')


@pytest.mark.parametrize('release,expected', [
    ('ID=ubuntu\nVERSION_ID="26.04"\n', 'deb'),
    ('ID=fedora\nVERSION_ID=44\nVARIANT_ID=workstation\n', 'rpm'),
    ('ID=fedora\nVERSION_ID=44\nVARIANT_ID=server\n', None),
    ('ID=fedora\nVERSION_ID=43\nVARIANT_ID=workstation\n', None),
    ('ID=ubuntu\nVERSION_ID=24.04\n', None),
])
def test_package_platform_comes_from_supported_os_release(monkeypatch, release, expected):
    monkeypatch.setattr(control, 'Path', lambda name: SimpleNamespace(read_text=lambda: release))
    if expected:
        assert PACKAGE_FORMAT() == expected
    else:
        with pytest.raises(control.SessionError, match='package-platform'):
            PACKAGE_FORMAT()


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
@pytest.mark.parametrize('name,rpm_name', [('gdm3', 'gdm'), ('gnome-shell', 'gnome-shell'),
    ('mate-polkit', 'mate-polkit'), ('libgtk-4-1', 'gtk4'), ('gcr', 'gcr4')])
@pytest.mark.parametrize('fault', [False, True])
def test_provider_metadata_queries_correct_package_and_bounds_reply(
        monkeypatch, package_format, name, rpm_name, fault):
    monkeypatch.setattr(control, 'package_format', lambda: package_format)
    query = Mock(return_value='private text\nother' if fault else '0:50.1-1.fc44\n')
    monkeypatch.setattr(control.subprocess, 'check_output', query)
    if fault:
        with pytest.raises(control.SessionError, match='package-version'):
            control.installed_package_version(name)
    else:
        assert control.installed_package_version(name) == '0:50.1-1.fc44'
    assert query.call_args.kwargs == {'text': True, 'timeout': 5}
    assert query.call_args.args[0] == (['/usr/bin/rpm', '-q', '--queryformat',
        '%{EPOCHNUM}:%{VERSION}-%{RELEASE}', rpm_name] if package_format == 'rpm' else
        ['/usr/bin/dpkg-query', '--show', '--showformat=${Version}', name])


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_platform_package_path_and_administrator_group(monkeypatch, package_format):
    monkeypatch.setattr(control, 'package_format', lambda: package_format)
    assert control.administrator_group() == ('wheel' if package_format == 'rpm' else 'sudo')
    for binding in ('previous', 'current'):
        assert str(control.package_path(binding)) == '/var/lib/onpc-e2e-assets/' + (
            'previous/' if binding == 'previous' else '') + 'package.' + package_format


def test_session_readback_does_not_combine_both_sides_of_a_seat_switch(monkeypatch):
    # The source is read before the switch, then GDM after it. There was never
    # more than one active session, but the first sequential scan says otherwise.
    source = props(locked='yes')
    greeter = props('120', active='no', kind='greeter')
    reads = []

    def call(argv):
        if argv[1] == 'list-sessions':
            return '7 1000\n8 120\n'
        identity = argv[2]
        reads.append(identity)
        value = dict(source if identity == '7' else greeter)
        if len(reads) == 1:
            source['Active'] = 'no'
            greeter['Active'] = 'yes'
        return '\n'.join(f'{key}={item}' for key, item in value.items())

    monkeypatch.setattr(control, 'call', call)
    current = control.sessions()
    assert reads == ['7', '8'] * 3
    assert current == {'7': source, '8': greeter}
    assert control.destination(current, '7', 1000, 'switch-user')


def test_stable_multiple_active_sessions_still_refuse(monkeypatch):
    current = {'7': props(locked='yes'), '8': props('120', kind='greeter')}
    scan = Mock(return_value=current)
    monkeypatch.setattr(control, 'session_scan', scan)
    with pytest.raises(control.SessionError, match='ambiguous-destination'):
        control.destination(control.sessions(), '7', 1000, 'switch-user')
    assert scan.call_count == 2


def test_continuously_changing_sessions_refuse_with_bounded_reads(monkeypatch):
    scan = Mock(side_effect=[{'7': props(locked=value)}
                             for value in ('no', 'yes', 'no', 'yes')])
    monkeypatch.setattr(control, 'session_scan', scan)
    with pytest.raises(control.SessionError, match='unstable-observation'):
        control.sessions()
    assert scan.call_count == 4


def test_stabilized_wrong_source_owner_still_refuses(monkeypatch):
    switched = {'7': props('1001', active='no', locked='yes'),
                '8': props('120', kind='greeter')}
    monkeypatch.setattr(control, 'session_scan', Mock(side_effect=[
        {'7': props()}, switched, switched]))
    with pytest.raises(control.SessionError, match='source-replaced'):
        control.destination(control.sessions(), '7', 1000, 'switch-user')


def test_session_scan_errors_are_not_retried_as_transitions(monkeypatch):
    scan = Mock(side_effect=control.SessionError('session:session-properties'))
    monkeypatch.setattr(control, 'session_scan', scan)
    with pytest.raises(control.SessionError, match='session-properties'):
        control.sessions()
    scan.assert_called_once_with()


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


@pytest.mark.parametrize('active,locked', [('yes', 'no'), ('no', 'yes')])
def test_root_maintenance_logout_retains_other_desktops(monkeypatch, active, locked):
    account = SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name='fixture')
    source = props(active=active, locked=locked)
    other = props('1001', active='no' if active == 'yes' else 'yes')
    before = {'7': source, '8': other}
    monkeypatch.setattr(control.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(control.pwd, 'getpwuid', lambda _: account)
    monkeypatch.setattr(control.os, 'getgrouplist', lambda *_: [1000])
    monkeypatch.setattr(control, 'environment', lambda _: {'bound': 'desktop'})
    monkeypatch.setattr(control, 'sessions', Mock(side_effect=[before, before, {'8': other}]))
    run = Mock()
    monkeypatch.setattr(control.subprocess, 'run', run)
    assert control.maintenance_logout(1000, '7') == {
        'operation': 'maintenance-logout', 'outcome': 'passed',
        'source_retained': False, 'other_desktops_retained': True}
    assert run.call_count == 1
    assert run.call_args.args[0] == control.LOGOUT_COMMAND
    assert run.call_args.kwargs['user'] == 1000
    assert run.call_args.kwargs['env'] == {'bound': 'desktop'}
    assert control.os.geteuid() == 0


@pytest.mark.parametrize('fault', ['nonroot', 'owner', 'ambiguous', 'changed', 'uncertain', 'other-lost'])
def test_root_maintenance_logout_refuses_without_fallback(monkeypatch, fault):
    account = SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name='fixture')
    before = {'7': props(active='no', locked='yes'), '8': props('1001')}
    after = {'8': props('1001')}
    if fault == 'owner':
        before['7']['User'] = '1002'
    if fault == 'ambiguous':
        before['9'] = props(active='no')
    monkeypatch.setattr(control.os, 'geteuid', lambda: 1 if fault == 'nonroot' else 0)
    monkeypatch.setattr(control.pwd, 'getpwuid', lambda _: account)
    monkeypatch.setattr(control.os, 'getgrouplist', lambda *_: [1000])
    monkeypatch.setattr(control, 'environment', lambda _: {})
    monkeypatch.setattr(control, 'sessions', Mock(side_effect=[
        before, after if fault == 'changed' else before,
        {} if fault == 'other-lost' else after]))
    run = Mock(side_effect=TimeoutError if fault == 'uncertain' else None)
    monkeypatch.setattr(control.subprocess, 'run', run)
    with pytest.raises((control.SessionError, TimeoutError)):
        control.maintenance_logout(1000, '7')
    assert run.call_count == (1 if fault in ('uncertain', 'other-lost') else 0)


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
                                    'standard-return-greeter', 'parent-continuous-activity',
                                    'child-switch-user'])
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


def test_child_switch_binds_riley_and_observes_the_retained_locked_session(monkeypatch):
    account = SimpleNamespace(pw_uid=1001, pw_gid=1001, pw_name='onpc-child-riley')
    lookup = Mock(return_value=account)
    monkeypatch.setattr(control.pwd, 'getpwnam', lookup)
    monkeypatch.setattr(control.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(control, 'environment', lambda _: {'bound': 'child'})
    monkeypatch.setattr(control.os, 'environ', {})
    identity = {}
    for name in ('initgroups', 'setgid', 'setuid'):
        identity[name] = Mock()
        monkeypatch.setattr(control.os, name, identity[name])
    before = {'7': props('1001')}
    after = {'7': props('1001', active='no', locked='yes'),
             '8': props('120', kind='greeter')}
    scans = Mock(side_effect=[before, before, after])
    monkeypatch.setattr(control, 'sessions', scans)
    submit = Mock()
    monkeypatch.setattr(control, 'submit', submit)
    assert control.execute('child-switch-user') == {
        'operation': 'child-switch-user', 'outcome': 'passed', 'interface': 'system session',
        'source_retained': True, 'destination': 'greeter'}
    lookup.assert_called_once_with('onpc-child-riley')
    identity['initgroups'].assert_called_once_with('onpc-child-riley', 1001)
    identity['setgid'].assert_called_once_with(1001)
    identity['setuid'].assert_called_once_with(1001)
    assert control.os.environ == {'bound': 'child'}
    submit.assert_called_once_with('switch-user')
    assert scans.call_count == 3


def test_continuous_activity_only_verifies_baseline_and_reads_back(monkeypatch):
    call = Mock(side_effect=['uint32 0\n', 'uint32 0\n'])
    monkeypatch.setattr(control, 'call', call)
    assert control.prepare_continuous_activity() == 0
    assert [item.args[0] for item in call.call_args_list] == [
        ['/usr/bin/gsettings', 'get', 'org.gnome.desktop.session', 'idle-delay'],
        ['/usr/bin/gsettings', 'get', 'org.gnome.desktop.session', 'idle-delay'],
    ]


@pytest.mark.parametrize('responses,calls,exception', [
    (['300'], 1, control.SessionError),
    (['uint32 4294967296'], 1, control.SessionError),
    (['uint32 300'], 1, control.SessionError),
    (['uint32 4294967295'], 1, control.SessionError),
    (['uint32 0', TimeoutError()], 2, TimeoutError),
    (['uint32 0', 'uint32 300'], 2, control.SessionError),
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
                                    'parent-return-greeter', 'standard-return-greeter',
                                    'child-switch-user'])
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


@pytest.mark.parametrize('fault', ['', 'stale', 'replay'])
def test_switch_after_parent_work_consumes_the_new_desktop_proof(fault):
    program = LEAF.replace("seen('desktop')", "seen('repeat-desktop')").replace(
        'switch_user($journey, $desktop)', "switch_user($journey, $desktop, 'repeat-desktop')")
    result = json.loads(run_perl(program, 'switch_user', fault).stdout)
    assert result['ok'] == (not fault)
    assert result['events'] == ([] if fault == 'stale' else
        [['seen', 'switch-user'], ['seen', 'gdm-switched']])


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

    # Installed qualification follows the checkout release, not a fixed old snapshot.
    version = json.loads((ROOT / 'data/app.json').read_bytes())['version']
    for qualification, mode in ((DesktopLogoutQualification, 'desktop_session_logout'),
                                (DesktopSwitchQualification, 'desktop_session_switch')):
        assert issubclass(qualification, KioskEntryQualification)
        context = SimpleNamespace()
        journey = qualification.journey(context, Mock())
        assert context.installed_snapshot == 'onpc-v' + version
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


def lock_tree(monkeypatch, entry='curtain'):
    import accessible_ui as a
    window = Node(role='window', states=('showing', 'visible', 'sensitive', 'focused'))
    hint = Node('Click or press a key to unlock', 'label')
    recipient = Node(a.PARENT, 'label')
    field = Node('Password:', 'password text', states=(
        'showing', 'visible', 'sensitive', 'focused', 'editable'))
    field.get_child_count = Mock(side_effect=AssertionError('protected traversal'))
    field.getText = Mock(side_effect=AssertionError('protected text'))
    window.children = [hint] if entry == 'curtain' else [recipient, field]
    if entry == 'challenge': window.states.discard('focused')
    for child in window.children: child.parent = window
    shell = Node('gnome-shell', 'application', children=[window])
    root = Node(role='desktop frame', children=[shell])
    monkeypatch.setattr(a.os, 'getuid', lambda: 1000)
    monkeypatch.setattr(a.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1000))
    monkeypatch.setattr(a, 'Path', lambda _: SimpleNamespace(stat=lambda: SimpleNamespace(st_uid=1000)))
    monkeypatch.setattr(control, 'sessions', lambda: {'7': props(locked='yes')})
    ui = ui_for(root)
    ui.mate_challenge_identity = Mock(return_value='a' * 64)
    ui._shell_provider_metadata = Mock(return_value={
        'version': '50.1', 'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']]})
    return ui, root, shell, window, recipient, field


@pytest.mark.parametrize('entry', ['curtain', 'challenge'])
def test_lock_surface_reads_public_identity_without_secret_input(monkeypatch, entry):
    ui, _, _, _, _, field = lock_tree(monkeypatch, entry)
    result = ui.run('parent-lock-' + entry, '')['lock']
    assert result == {'entry': entry, 'owner': 'fixture-parent', 'locked': True,
        'desktop_input_available': False, 'recipient': 'fixture-parent' if entry == 'challenge' else None,
        'surface_id': 'a' * 64, 'provider': ui._shell_provider_metadata.return_value}
    field.get_child_count.assert_not_called()
    field.getText.assert_not_called()
    field.action.do_action.assert_not_called()
    field.component.grab_focus.assert_not_called()


@pytest.mark.parametrize('fault', ['unlocked', 'wrong-session', 'wrong-seat', 'multiple-sessions',
    'multiple-windows', 'wrong-owner', 'foreign-password', 'foreign-focus', 'foreign-dialog',
    'duplicate-field', 'wrong-recipient', 'disabled-field', 'unfocused-field', 'defunct', 'incomplete'])
def test_lock_challenge_refuses_unsafe_surfaces_without_input(monkeypatch, fault):
    import accessible_ui as a
    ui, root, shell, window, recipient, field = lock_tree(monkeypatch, 'challenge')
    current = {'7': props(locked='yes')}
    if fault == 'unlocked': current['7']['LockedHint'] = 'no'
    elif fault == 'wrong-session': current['7']['User'] = '1001'
    elif fault == 'wrong-seat': current['7']['Seat'] = 'seat1'
    elif fault == 'multiple-sessions': current['8'] = props('1001', locked='yes')
    elif fault == 'multiple-windows': shell.children.append(Node(role='window'))
    elif fault == 'wrong-owner': shell.get_process_id = lambda: 200
    elif fault.startswith('foreign-'):
        node = Node(role={'foreign-password': 'password text', 'foreign-focus': 'text',
                          'foreign-dialog': 'dialog'}[fault])
        if fault == 'foreign-focus': node.states.add('focused')
        root.children.append(Node('other', 'application', children=[node]))
    elif fault == 'duplicate-field': window.children.append(Node(role='password text'))
    elif fault == 'wrong-recipient': recipient.name = a.OTHER_PARENT
    elif fault == 'disabled-field': field.states.discard('sensitive')
    elif fault == 'unfocused-field': field.states.discard('focused')
    elif fault == 'defunct': field.states.add('defunct')
    elif fault == 'incomplete': window.children.append(None)
    monkeypatch.setattr(control, 'sessions', lambda: current)
    with pytest.raises(a.UiError): ui.run('parent-lock-challenge', '')
    field.action.do_action.assert_not_called()
    field.component.grab_focus.assert_not_called()
    ui.mate_challenge_identity.assert_not_called()


def test_curtain_proof_cannot_authorize_input_to_an_open_challenge(monkeypatch):
    import accessible_ui as a
    ui, _, _, _, _, _ = lock_tree(monkeypatch, 'challenge')
    with pytest.raises(a.UiError, match='lock-not-curtain'):
        ui.run('parent-lock-reveal-ready', '')


def test_live_tree_refusal_projections_use_the_same_read_only_adapter(monkeypatch):
    ui, _, _, _, _, field = lock_tree(monkeypatch, 'challenge')
    assert ui.run('parent-lock-refusals', '')['lock'] == {
        'refused': ['session', 'surface-ambiguous', 'field-ambiguous', 'recipient']}
    field.action.do_action.assert_not_called()
    field.getText.assert_not_called()


@pytest.mark.parametrize('entry', ['curtain', 'challenge'])
def test_lock_surface_binds_semantic_window_beneath_empty_shell_wrapper(monkeypatch, entry):
    ui, _, shell, window, _, field = lock_tree(monkeypatch, entry)
    wrapper = Node(role='window', children=[window])
    shell.children = [wrapper]
    wrapper.parent = shell
    result = ui.run('parent-lock-' + entry, '')['lock']
    assert result['entry'] == entry
    ui.mate_challenge_identity.assert_called_once_with(shell.get_process_id(), (shell, window))
    field.get_child_count.assert_not_called()
    field.getText.assert_not_called()


@pytest.mark.parametrize('entry', ['curtain', 'challenge'])
@pytest.mark.parametrize('fault', ['hint', 'recipient', 'password', 'focus', 'modal', 'dialog',
    'descendant-window', 'sibling-window', 'shared-window', 'shared-control', 'cycle',
    'owner-cycle', 'foreign-wrapper', 'duplicate-edge'])
def test_lock_wrapper_never_hides_competing_or_ambiguous_ownership(monkeypatch, entry, fault):
    import accessible_ui as a
    ui, _, shell, window, _, field = lock_tree(monkeypatch, entry)
    wrapper = Node(role='window', children=[window])
    shell.children = [wrapper]
    wrapper.parent = shell
    if fault in ('hint', 'recipient', 'password', 'focus', 'modal', 'dialog'):
        extra = Node(role='label')
        if fault == 'hint': extra.name = 'Click or press a key to unlock'
        elif fault == 'recipient': extra.name = a.OTHER_PARENT
        elif fault == 'password': extra.role = 'password text'
        elif fault == 'focus': extra.states.add('focused')
        elif fault == 'modal': extra.states.add('modal')
        elif fault == 'dialog': extra.role = 'dialog'
        wrapper.children.append(extra)
    elif fault == 'descendant-window': window.children.append(Node(role='window'))
    elif fault == 'sibling-window': wrapper.children.append(Node(role='window'))
    elif fault == 'shared-window': shell.children.append(window)
    elif fault == 'shared-control': wrapper.children.append(window.children[0])
    elif fault == 'cycle': window.children.append(wrapper)
    elif fault == 'owner-cycle': wrapper.children.append(shell)
    elif fault == 'foreign-wrapper': wrapper.get_process_id = lambda: 200
    elif fault == 'duplicate-edge': wrapper.children.append(window)
    with pytest.raises(UiError): ui.run('parent-lock-' + entry, '')
    ui.mate_challenge_identity.assert_not_called()
    field.getText.assert_not_called()
    field.action.do_action.assert_not_called()
    window.component.grab_focus.assert_not_called()


def test_lock_replacement_under_unchanged_wrapper_cannot_release_reveal(monkeypatch):
    from ui_observations import UiObservations
    from private_artifacts import EvidenceError
    ui, _, shell, window, _, _ = lock_tree(monkeypatch)
    wrapper = Node(role='window', children=[window])
    shell.children = [wrapper]
    wrapper.parent = shell
    ui.mate_challenge_identity = lambda pid, targets: ('a' if targets[1] is window else 'b') * 64
    reader = UiObservations(SimpleNamespace())
    reader.call = lambda argv, *args, **kwargs: (json.dumps(ui.run(argv[3], '')).encode(), [])
    assert reader.observe('parent-lock-curtain')['lock']['surface_id'] == 'a' * 64
    replacement = Node(role='window', children=[Node('Click or press a key to unlock', 'label')],
                       states=('showing', 'visible', 'sensitive', 'focused'))
    wrapper.children = [replacement]
    replacement.parent = wrapper
    with pytest.raises(EvidenceError, match='lock-surface-changed'):
        reader.observe('parent-lock-reveal-ready')


@pytest.mark.parametrize('entry', ['curtain', 'challenge'])
@pytest.mark.parametrize('topology', ['ancestor', 'sibling', 'cycle', 'shared'])
def test_lock_ambiguity_diagnostic_preserves_refusal_and_private_text(
        monkeypatch, capsys, entry, topology):
    ui, _, shell, window, _, field = lock_tree(monkeypatch, entry)
    extra = Node('private-window-canary', 'window', children=[
        Node('private-label-canary', 'label')])
    if topology == 'ancestor':
        # An ancestor is ambiguous only when it has independent lock semantics.
        extra.children.append(Node('Click or press a key to unlock', 'label'))
    if topology in ('ancestor', 'cycle', 'shared'):
        extra.children.append(window)
        shell.children = [extra]
        window.parent = extra
        if topology == 'cycle': window.children.append(extra)
        if topology == 'shared': shell.children.append(window)
    else:
        shell.children.append(extra)
    extra.parent = shell
    ui.read_snapshot = Mock(wraps=ui.read_snapshot)
    with pytest.raises(UiError, match='lock-surface-ambiguous'):
        ui.run('parent-lock-' + entry, '')
    stderr = capsys.readouterr().err
    diagnostic = next(json.loads(line) for line in stderr.splitlines()
                      if line.startswith('{') and json.loads(line).get('event')
                      == 'ui-lock-window-ambiguity')
    assert diagnostic['window_count'] == 2 and not diagnostic['truncated']
    rows = diagnostic['windows']
    assert sorted(len(row['contains_windows']) for row in rows) == (
        [1, 1] if topology == 'cycle' else [0, 1] if topology != 'sibling' else [0, 0])
    if topology == 'shared': assert max(row['incoming_edges'] for row in rows) == 2
    if topology != 'cycle':
        assert sum(row['own_hints'] for row in rows) == int(entry == 'curtain') + int(topology == 'ancestor')
        assert sum(row['own_password_fields'] for row in rows) == int(entry == 'challenge')
        assert sum(row['own_parent_labels'] for row in rows) == int(entry == 'challenge')
    assert 'private-window-canary' not in stderr and 'private-label-canary' not in stderr
    ui.read_snapshot.assert_called_once_with(protect_text=True)
    ui.mate_challenge_identity.assert_not_called()
    field.getText.assert_not_called()
    field.get_child_count.assert_not_called()
    field.action.do_action.assert_not_called()
    window.component.grab_focus.assert_not_called()


@pytest.mark.parametrize('unavailable', [False, True])
def test_lock_ambiguity_diagnostic_bounds_output_and_cannot_replace_failure(
        monkeypatch, capsys, unavailable):
    ui, _, shell, _, _, _ = lock_tree(monkeypatch)
    shell.children.extend(Node('private-canary', 'window') for _ in range(24))
    if unavailable:
        ui.lock_window_diagnostic = Mock(side_effect=RuntimeError('private-error-canary'))
    with pytest.raises(UiError, match='lock-surface-ambiguous'):
        ui.run('parent-lock-curtain', '')
    stderr = capsys.readouterr().err
    if unavailable:
        assert 'ui:lock-window-diagnostic-unavailable' in stderr
    else:
        diagnostic = next(json.loads(line) for line in stderr.splitlines()
                          if line.startswith('{') and json.loads(line).get('event')
                          == 'ui-lock-window-ambiguity')
        assert diagnostic['window_count'] == 25 and diagnostic['truncated']
        assert len(diagnostic['windows']) == 16 and len(stderr) < 8192
    assert 'private-canary' not in stderr and 'private-error-canary' not in stderr
    ui.mate_challenge_identity.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'entry', 'owner', 'locked', 'desktop', 'recipient',
                                  'identity', 'provider', 'extra', 'replacement'])
def test_lock_decoder_validates_public_result_and_pins_surface(monkeypatch, fault):
    from ui_observations import UiObservations
    from private_artifacts import EvidenceError
    ui, _, _, _, _, _ = lock_tree(monkeypatch, 'curtain')
    curtain = ui.run('parent-lock-curtain', '')
    reader = UiObservations(SimpleNamespace())
    reader.call = Mock(return_value=(json.dumps(curtain).encode(), []))
    assert reader.observe('parent-lock-curtain')['lock']['surface_id'] == 'a' * 64
    result = {**curtain, 'operation': 'parent-lock-challenge', 'lock': {
        **curtain['lock'], 'entry': 'challenge', 'recipient': 'fixture-parent'}}
    changes = {'entry': ('entry', 'curtain'), 'owner': ('owner', 'other'),
        'locked': ('locked', False), 'desktop': ('desktop_input_available', True),
        'recipient': ('recipient', 'other'), 'identity': ('surface_id', 'bad'),
        'provider': ('provider', {}), 'extra': ('private', 'canary'),
        'replacement': ('surface_id', 'b' * 64)}
    if fault:
        key, value = changes[fault]
        result['lock'][key] = value
    reader.call.return_value = (json.dumps(result).encode(), [])
    if fault:
        with pytest.raises((EvidenceError, UiError)): reader.observe('parent-lock-challenge')
    else:
        assert reader.observe('parent-lock-challenge')['lock']['recipient'] == 'fixture-parent'


@pytest.mark.parametrize('supplied', [False, True])
def test_lock_worker_complete_sequence_and_refusal_stops(supplied):
    from desktop_session import LOCK_PLAN, SUPPLIED_LOCK_PLAN
    plan = SUPPLIED_LOCK_PLAN if supplied else LOCK_PLAN
    program = RUN_PROBE.replace("onpc_desktop_session::run(sub {",
        "onpc_desktop_session::qualify_lock(sub {").replace('}, $action);', '}, $action);')
    result = json.loads(run_perl(program, '1' if supplied else '0').stdout)
    assert result['ok'], result
    events = result['events']
    assert [event[1] for event in events if event[0] == 'stage'] == list(plan.screen_tags)
    assert events.count(['secret']) == 1  # Fresh login only; lock input is never secret.
    assert events.count(['key', 'spc']) == 1
    assert events.count(['key', 'super-l']) == int(supplied)
    assert events[-1] == ['power', 'off']
    for stage in ('unlocked-refused', 'lock-ready', 'curtain', 'reveal-ready', 'challenge', 'lock-refusals'):
        failed = program.replace("push @events, ['stage', $_[0]];",
            "push @events, ['stage', $_[0]]; die 'guard' if $_[0] eq '" + stage + "';")
        result = json.loads(run_perl(failed, '1' if supplied else '0').stdout)
        assert not result['ok']
        expected = events[:events.index(['stage', stage]) + 1]
        assert result['events'] == expected


def test_lock_qualification_separate_attempts_and_registered_transport(monkeypatch):
    import check_e2e_lock_surface as check
    import check_graphical_smoke as smoke
    from desktop_session import LOCK_PLAN, SUPPLIED_LOCK_PLAN
    from parent_setup_qualification import LockSurfaceQualification, SuppliedLockSurfaceQualification
    from tools import test_commands
    calls = []
    monkeypatch.setattr(check, 'smoke', lambda **kwargs: calls.append(kwargs) or 0)
    assert check.main() == 0
    assert [value['lock_surface'] for value in calls] == ['command', 'supplied']
    monkeypatch.setattr(check, 'smoke', lambda **kwargs: calls.append(kwargs) or 1)
    calls.clear()
    assert check.main() == 1 and len(calls) == 1
    for cls, plan in ((LockSurfaceQualification, LOCK_PLAN),
                      (SuppliedLockSurfaceQualification, SUPPLIED_LOCK_PLAN)):
        context = SimpleNamespace()
        journey = cls.journey(context, Mock())
        assert journey.plan is plan
        assert context.installed_snapshot.startswith('onpc-v')
        assert set(plan.phases) == set(plan.stages)
        assert all(tag[7:] in control.BINDINGS for tag in plan.screen_tags.values()
                   if tag.startswith('system:'))
        assert all(tag[3:] in OPERATIONS for tag in plan.screen_tags.values() if tag.startswith('ui:'))
    # Invalid mixed modes fail before credentials, storage, VM or other preparation.
    with pytest.raises(RuntimeError, match='lock-surface-prerequisites'):
        smoke.main(assets=check.ASSETS, provision_credentials=True,
                   lock_surface='command', desktop_session_switch=True)
    prepare = Mock(return_value='prepared')
    monkeypatch.setattr(test_commands, 'allocate_artifact_output', prepare)
    monkeypatch.setattr(test_commands.os.path, 'lexists', lambda _: False)
    assert test_commands.qualification_artifact_command(ROOT, 'integration', ['check_e2e_lock_surface'])
    prepare.assert_called_once()


def test_lock_read_reacquires_delayed_and_incomplete_transitions(monkeypatch):
    import accessible_ui as a
    ui, _, _, window, _, field = lock_tree(monkeypatch, 'challenge')
    original = ui.shell_lock_snapshot
    reads = []

    def observe(*args, **kwargs):
        reads.append(1)
        if len(reads) == 1: return None
        if len(reads) == 2: raise a.UiError('ui:incomplete-tree')
        return original(*args, **kwargs)

    ui.shell_lock_snapshot = observe
    ui.timeout = 2
    assert ui.run('parent-lock-challenge', '')['lock']['entry'] == 'challenge'
    assert len(reads) == 3
    field.action.do_action.assert_not_called()
    window.component.grab_focus.assert_not_called()


def test_already_open_lock_observation_has_no_reveal_input(monkeypatch):
    from journey_blocks import lock_challenge
    from ui_observations import UiObservations
    ui, _, _, _, _, _ = lock_tree(monkeypatch, 'challenge')
    reader = UiObservations(SimpleNamespace())
    reader.call = Mock(return_value=(json.dumps(ui.run('parent-lock-challenge', '')).encode(), []))
    assert reader.observe('parent-lock-challenge')['lock']['entry'] == 'challenge'
    assert lock_challenge('again-', entry='challenge') == {'again-challenge': 'ui:parent-lock-challenge'}
    program = RUN_PROBE[:RUN_PROBE.index('my $ok = eval')] + r'''
my $journey = onpc_journey->new(exchange => sub { push @events, ['stage', $_[0]]; return {}; },
    prefix => 'independent', review => 0);
onpc_desktop_session::observe_lock($journey, 'challenge');
print encode_json({events => \@events});
'''
    assert json.loads(run_perl(program, '0').stdout)['events'] == [['stage', 'challenge']]
