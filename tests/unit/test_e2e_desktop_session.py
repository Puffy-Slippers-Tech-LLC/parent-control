"""Account-disrupting session commands and lock-password input boundaries.

Parallelism review: process-local session/UI doubles, private pytest files and
bounded waited Perl children. No live VM, display, bus, shared cache or new owner;
the existing compatible unit classification continues to apply.
"""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import session_control as control


from accessible_ui import UiError
from tests.support.accessible_ui import Node, ui_for
from tests.support.desktop_session import RUN_PROBE, props
from tests.support.perl import run_perl


@pytest.mark.parametrize('fault,locked', [
    ('wrong-owner', False), ('remote', False), ('wrong-seat', False), ('greeter', False),
    ('wrong-lock-state', False), ('wrong-lock-state', True),
    ('multiple-active', False), ('multiple-owned', False), ('opening', False), ('missing', False),
])
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
    elif fault == 'opening':
        source['State'] = 'opening'
    else:
        current.clear()
    with pytest.raises(control.SessionError):
        control.source_session(current, 1000, locked=locked)


@pytest.mark.parametrize('state,active', [('closing', 'no'), ('closing', 'yes'), ('unknown', 'no')])
def test_session_reader_distinguishes_logged_out_records_before_fresh_input(monkeypatch, state, active):
    records = {'7': {**props(active=active), 'State': state},
               '8': {**props('120', kind='greeter'), 'State': 'active'}}
    monkeypatch.setattr(control, 'session_ids', lambda: list(records))
    monkeypatch.setattr(control, 'call', lambda argv: '\n'.join(
        key + '=' + value for key, value in records[argv[2]].items()))
    if state != 'closing':
        with pytest.raises(control.SessionError, match='session-state'):
            control.sessions()
        return
    current = control.sessions()
    assert control.destination(current, '7', 1000, 'logout')
    assert control.entry_identity(current, 1000, 'fresh') is None
    records['7'] = {**props(active='no', locked='yes'), 'State': 'online'}
    with pytest.raises(control.SessionError, match='entry-not-fresh'):
        control.entry_identity(control.sessions(), 1000, 'fresh')


def test_opening_greeter_cannot_authorize_a_destination_or_fresh_password(monkeypatch):
    records = {'7': {**props(active='no', locked='yes'), 'State': 'online'},
               '8': {**props('120', active='no', kind='greeter'), 'State': 'opening'}}
    monkeypatch.setattr(control, 'session_ids', lambda: list(records))
    monkeypatch.setattr(control, 'call', lambda argv: '\n'.join(
        key + '=' + value for key, value in records[argv[2]].items()))
    for active in ('no', 'yes'):
        records['8']['Active'] = active
        current = control.sessions()
        assert not control.destination(current, '7', 1000, 'switch-user')
        with pytest.raises(control.SessionError, match='entry-(greeter|opening)'):
            control.entry_identity(current, 1001, 'fresh')
    records['8']['State'] = 'active'
    current = control.sessions()
    assert control.destination(current, '7', 1000, 'switch-user')
    assert control.entry_identity(current, 1001, 'fresh') is None


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


@pytest.mark.parametrize('fault', ['changed-source', 'changed-lock'])
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
        {'7': props(locked=locked)},
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


@pytest.mark.parametrize('fault', ['', 'nonempty', 'missing-text', 'unfocused', 'wrong-user', 'stale'])
def test_lock_recipient_reads_only_empty_count_after_identity_guards(monkeypatch, fault):
    import accessible_ui as a
    ui, _, _, _, recipient, field = lock_tree(monkeypatch, 'challenge')
    interface = SimpleNamespace()
    field.get_text_iface = Mock(return_value=None if fault == 'missing-text' else interface)
    ui.api.Text = SimpleNamespace(get_character_count=Mock(return_value=1 if fault == 'nonempty' else 0))
    if fault == 'unfocused': field.states.discard('focused')
    elif fault == 'wrong-user': recipient.name = a.OTHER_PARENT
    elif fault == 'stale': field.states.add('defunct')
    if fault:
        with pytest.raises(UiError): ui.run('parent-lock-recipient-qualified', '')
    else:
        result = ui.run('parent-lock-recipient-qualified', '')['lock']
        assert result['empty'] is result['masked'] is result['focused'] is True
        assert result['challenge_id'] == 'a' * 64
        ui.api.Text.get_character_count.assert_called_once_with(interface)
    if fault in ('unfocused', 'wrong-user', 'stale'):
        field.get_text_iface.assert_not_called()
    field.getText.assert_not_called()
    field.get_child_count.assert_not_called()
    field.action.do_action.assert_not_called()
    field.component.grab_focus.assert_not_called()


def recipient_reader(monkeypatch):
    from ui_observations import UiObservations
    ui, _, _, _, _, field = lock_tree(monkeypatch, 'challenge')
    field.get_text_iface = Mock(return_value=SimpleNamespace())
    ui.api.Text = SimpleNamespace(get_character_count=Mock(return_value=0))
    reader = UiObservations(SimpleNamespace())
    reader.call = Mock(side_effect=lambda argv, *args, **kwargs:
        (json.dumps(ui.run(argv[3], '')).encode(), []))
    return ui, reader


@pytest.mark.parametrize('fault', ['', 'gdm', 'reordered', 'intervening', 'stale', 'slow',
                                  'replacement', 'replay', 'nonempty-response'])
def test_lock_recipient_decoder_orders_two_fresh_same_challenge_proofs(monkeypatch, fault):
    from private_artifacts import EvidenceError
    import ui_observations as observations
    ui, reader = recipient_reader(monkeypatch)
    clock = [10.0]
    monkeypatch.setattr(observations.time, 'monotonic', lambda: clock[0])
    reader.observe('parent-lock-challenge')
    if fault in ('gdm', 'reordered'):
        reader.last_operation = 'gdm-parent-recipient' if fault == 'gdm' else None
        with pytest.raises(EvidenceError, match='lock-recipient-order'):
            reader.observe('parent-lock-recipient-qualified')
        assert reader.call.call_count == 1
        return
    first = reader.observe('parent-lock-recipient-qualified')
    assert first['lock']['empty'] is True
    if fault == 'intervening': reader.observe('parent-lock-challenge')
    elif fault == 'stale': clock[0] = 40.0
    elif fault == 'replacement':
        ui.mate_challenge_identity = lambda pid, nodes: ('b' if len(nodes) == 3 else 'a') * 64
    elif fault in ('slow', 'nonempty-response'):
        original = reader.call.side_effect
        def response(*args, **kwargs):
            raw, prompts = original(*args, **kwargs)
            if fault == 'slow': clock[0] += 30.0
            if fault == 'nonempty-response':
                result = json.loads(raw)
                result['lock']['empty'] = False
                raw = json.dumps(result).encode()
            return raw, prompts
        reader.call.side_effect = response
    if fault and fault != 'replay':
        with pytest.raises(EvidenceError): reader.observe('parent-lock-recipient-rechecked')
        calls = reader.call.call_count
        with pytest.raises(EvidenceError, match='previous-failure'):
            reader.observe('parent-lock-recipient-qualified')
        assert reader.call.call_count == calls
    else:
        assert reader.observe('parent-lock-recipient-rechecked')['lock']['challenge_id'] == 'a' * 64
        if fault == 'replay':
            with pytest.raises(EvidenceError, match='lock-recipient-order'):
                reader.observe('parent-lock-recipient-rechecked')


@pytest.mark.parametrize('fault', ['', 'gdm', 'wrong-role', 'replacement', 'ack', 'review', 'typing'])
def test_sealed_lock_input_refuses_foreign_proofs_and_never_replays(fault):
    program = RUN_PROBE[:RUN_PROBE.index('my $ok = eval')] + r'''
my $journey = onpc_journey->new(prefix => 'independent', review => $action eq 'review' ? 1 : 0,
    exchange => sub {
        my ($stage) = @_;
        push @events, ['stage', $stage];
        die 'ack-failed' if $action eq 'ack' && $stage =~ /rechecked/;
        return {observed => $stage, challenge => {surface => 'gdm'}} if $action eq 'gdm';
        return {observed => $stage, lock_recipient => {surface => 'lock',
            role => ($action eq 'wrong-role' ? 'parent' : 'child'),
            challenge_id => scalar(($action eq 'replacement' && $stage =~ /rechecked/ ? 'b' : 'a') x 64)}};
    });
my $ok = eval { onpc_password::enter_lock_password($journey, 'child'); 1; };
my $count = scalar @events;
my $retry = eval { onpc_password::enter_lock_password($journey, 'child'); 1; };
print encode_json({ok => $ok ? 1 : 0, retry => $retry ? 1 : 0,
    count => $count, events => \@events});
'''
    if fault == 'typing':
        program = program.replace("push @main::events, ['secret'];", "push @main::events, ['secret']; die 'uncertain';")
    result = json.loads(run_perl(program, fault).stdout)
    assert bool(result['ok']) == (not fault), result
    assert not result['retry'] and result['count'] == len(result['events'])
    assert result['events'].count(['secret']) == (1 if fault in ('', 'typing') else 0)
    assert not any(row[0] == 'key' for row in result['events'])


@pytest.mark.parametrize('fault', ['', 'not-greeter', 'unlocked', 'active', 'missing', 'duplicate',
                                  'changed', 'unlocked-result', 'lost-other', 'uncertain'])
def test_enter_locked_activates_only_the_preserved_locked_child_once(monkeypatch, fault):
    before = {'7': props('1002', active='no', locked='yes'),
              '8': props('120', kind='greeter'), '9': props('1000', active='no', locked='yes')}
    after = {**before, '7': props('1002', locked='yes'), '8': props('120', active='no', kind='greeter')}
    if fault == 'not-greeter': before['8'] = props('1000')
    if fault == 'unlocked': before['7']['LockedHint'] = 'no'
    if fault == 'active': before['7']['Active'] = 'yes'
    if fault == 'missing': del before['7']
    if fault == 'duplicate': before['10'] = props('1002', active='no', locked='yes')
    rechecked = {key: dict(value) for key, value in before.items()}
    if fault == 'changed': rechecked['7']['Type'] = 'x11'
    if fault == 'unlocked-result': after['7']['LockedHint'] = 'no'
    if fault == 'lost-other': del after['9']
    monkeypatch.setattr(control, 'sessions', Mock(side_effect=[before, rechecked, after]))
    command = Mock(side_effect=RuntimeError('uncertain') if fault == 'uncertain' else None)
    monkeypatch.setattr(control, 'call', command)
    if fault:
        with pytest.raises((control.SessionError, RuntimeError)):
            control.enter_locked(SimpleNamespace(pw_uid=1002))
    else:
        assert control.enter_locked(SimpleNamespace(pw_uid=1002)) == {
            'source_retained': True, 'destination': 'locked'}
    assert command.call_count == int(fault in ('', 'unlocked-result', 'lost-other', 'uncertain'))
    if command.called: command.assert_called_once_with(['/usr/bin/loginctl', 'activate', '7'])
