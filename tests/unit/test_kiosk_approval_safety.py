"""Direct credential guards: human decision time never authorizes stale input."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import ui_observations
from private_artifacts import EvidenceError
from tests.support.perl import run_password_guard


def test_privileged_fixture_password_uses_authenticated_callers_private_file(tmp_path, monkeypatch):
    import test_account_password as password
    uid = tmp_path.stat().st_uid
    config = tmp_path / '.onpc-config'
    config.mkdir()
    source = config / '.envrc'
    source.write_text("TEST_ACCOUNT_PASSWORD='fixture-only-canary'\n")
    source.chmod(0o600)
    monkeypatch.setattr(password.os, 'getuid', lambda: 0)
    monkeypatch.setenv('PKEXEC_UID', str(uid))
    lookup = Mock(return_value=SimpleNamespace(pw_dir=str(tmp_path)))
    monkeypatch.setattr(password.pwd, 'getpwuid', lookup)
    assert password.read_password() == 'fixture-only-canary'
    lookup.assert_called_once_with(uid)
    monkeypatch.setenv('PKEXEC_UID', str(uid + 1))
    with pytest.raises(ValueError, match='caller-owned regular file'):
        password.read_password()


@pytest.mark.parametrize('caller', ['', '0', '-1', 'invalid'])
def test_privileged_fixture_password_refuses_missing_caller_before_open(monkeypatch, caller):
    import test_account_password as password
    monkeypatch.setattr(password.os, 'getuid', lambda: 0)
    monkeypatch.setenv('PKEXEC_UID', caller)
    opened = Mock(side_effect=AssertionError('credential opened without authenticated caller'))
    monkeypatch.setattr(password.os, 'open', opened)
    with pytest.raises(ValueError, match='caller-owned regular file'):
        password.read_password()
    opened.assert_not_called()


@pytest.mark.parametrize('operation,previous,last_child,error', [
    ('gdm-child-time-denied', 'gdm-child-recipient-rechecked', 'child', 'denial-order'),
    ('gdm-child-denied-return-ready', 'gdm-child-time-denied', 'child', 'denial-child-changed'),
])
def test_named_gdm_denial_cannot_authorize_return_for_another_child(
        operation, previous, last_child, error):
    ui = ui_observations.UiObservations(None)
    ui.last_operation = previous
    ui.last_child = last_child
    ui.call = Mock(side_effect=AssertionError('guest observation after conclusive refusal'))
    with pytest.raises(EvidenceError, match=error):
        ui._observe(operation, child='existing')
    ui.call.assert_not_called()


def test_bound_prompt_wait_and_repeat_still_require_fresh_recipient_proofs(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(ui_observations.time, 'monotonic', lambda: clock[0])
    ui = ui_observations.UiObservations(None)
    ui.kiosk_request = ('child', 'parent', 30, False)
    ui._observe = Mock(return_value={})
    order = ui_observations.accessible_ui.BOUND_MATE_ORDER
    ui.observe(order[0])
    clock[0] += 45
    ui.observe(order[1])
    clock[0] += 1
    ui.observe(order[2])
    ui.observe(order[3])
    ui.observe('kiosk-request-estimate')
    ui.observe(order[0])
    ui.observe(order[1])
    clock[0] += 31
    calls = ui._observe.call_count
    with pytest.raises(EvidenceError, match='mate-stale-proof'):
        ui.observe(order[2])
    assert ui._observe.call_count == calls
    with pytest.raises(EvidenceError, match='challenge-previous-failure'):
        ui.observe(order[2])
    assert ui._observe.call_count == calls


def test_bound_prompt_refuses_changed_request_before_another_recipient_read():
    ui = ui_observations.UiObservations(None)
    ui.kiosk_request = ('other-child', 'parent', 30, False)
    ui._observe = Mock(return_value={})
    order = ui_observations.accessible_ui.BOUND_MATE_ORDER
    ui.observe(order[0])
    ui.kiosk_request = ('other-child', 'other-parent', 30, True)
    with pytest.raises(EvidenceError, match='mate-request-replaced'):
        ui.observe(order[1])
    assert ui._observe.call_count == 1


@pytest.mark.parametrize('mode', ['sequence', 'wrong-scope', 'crossed-request', 'replay'])
@pytest.mark.parametrize('surface', ['kiosk', 'overlay'])
def test_temporary_access_secret_binds_each_parent_and_requires_fresh_proofs(mode, surface):
    # Exercise the password guard with finite request inputs. Importing the
    # complete customer case makes this safety test depend on unrelated plans.
    requests = {'first': ('other-child', 'parent', 300, False),
                'included': ('other-child', 'other-parent', 300, True),
                'replacement': ('other-child', 'parent', 300, False)}
    prefix = 'flatpak-temporary-access' if surface == 'kiosk' else 'flatpak-grid-temporary-access'
    result = run_password_guard(r'''
my ($mode, $prefix, $encoded, $surface) = @ARGV;
my $requests = decode_json($encoded);
my $binding_key = $surface eq 'kiosk' ? 'kiosk_request' : 'overlay_request';
my $enter = sub {
    $surface eq 'kiosk' ? onpc_password::enter_kiosk_mate_password($_[0], 'bound-request')
                       : onpc_password::enter_overlay_shell_password($_[0]);
};
my $ok = eval {
    for my $name ('first', 'included', 'replacement') {
        my $request = bless {prefix => "$prefix-$name", stage_prefix => "$name-",
            $binding_key => [@{$requests->{$name}}], review => 0}, 'onpc_journey';
        $request->{stage_prefix} = 'included-' if $mode eq 'wrong-scope';
        $request->{$binding_key} = $requests->{included} if $mode eq 'crossed-request';
        $enter->($request);
        $enter->($request) if $mode eq 'replay';
    }
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
''', mode, prefix, json.dumps({name: [*binding[:3], int(binding[3])]
                             for name, binding in requests.items()}), surface)
    value = json.loads(result.stdout)
    names = list(requests) if mode == 'sequence' else ['first'] if mode == 'replay' else []
    assert value['ok'] == (mode == 'sequence')
    assert value['events'] == [event for name in names for event in (
        ['proof', name + '-approval-qualified'], ['proof', name + '-approval-rechecked'],
        ['delivery', requests[name][1], name + ('-kiosk-mate-approval' if surface == 'kiosk'
                                               else '-overlay-shell-approval')])]


def test_shell_cancel_proof_requires_the_bound_request_and_a_new_challenge():
    operation = 'overlay-shell-cancel-ready'
    proof = {'child': 'fixture-child', 'approver': 'fixture-parent',
             'duration_seconds': 30, 'allow_soft': False, 'cancel_ready': True,
             'same_challenge_rechecked': True,
             'rejected_proofs': list(ui_observations.accessible_ui.SHELL_PROMPT_REFUSALS),
             'provider': {'version': '50.0', 'locale': 'en_US.UTF-8',
                          'keyboard': [['xkb', 'us']]}, 'challenge_id': 'a' * 64}

    def observer(value):
        ui = ui_observations.UiObservations(None)
        ui.overlay_request = ('child', 'parent', 30, False)
        response = {'operation': operation, 'outcome': 'passed',
                    'interface': 'ApplicationUI+external-provider',
                    'boot_sha256': 'b' * 64, 'shell_prompt': value}
        ui.call = Mock(return_value=(json.dumps(response).encode(), []))
        return ui

    ui = observer(proof)
    assert ui.observe(operation)['shell_prompt'] == proof
    argv = ui.call.call_args.args[0]
    assert json.loads(argv[argv.index('--overlay-request') + 1]) == list(ui.overlay_request)
    with pytest.raises(EvidenceError, match='challenge-replay'):
        ui.observe(operation)

    wrong = observer({**proof, 'duration_seconds': 75, 'allow_soft': True})
    with pytest.raises(EvidenceError, match='shell-response'):
        wrong.observe(operation)
    calls = wrong.call.call_count
    with pytest.raises(EvidenceError, match='challenge-previous-failure'):
        wrong.observe(operation)
    assert wrong.call.call_count == calls


@pytest.mark.parametrize('mode,role', [
    ('excluded', 'parent'), ('included', 'other-parent'),
    ('wrong-choice', None), ('wrong-scope', None),
])
def test_panel_approval_secret_requires_fresh_proofs_and_cannot_be_replayed(mode, role):
    binding = ['child', 'parent', 30, False] if mode == 'excluded' else [
        'child', 'other-parent', 30, True]
    if mode == 'wrong-choice':
        binding[3] = False
    result = run_password_guard(r'''
my $journey = bless {prefix => shift @ARGV, stage_prefix => '',
    overlay_request => decode_json(shift @ARGV), review => 0}, 'onpc_journey';
$journey->{stage_prefix} = 'later-' if shift(@ARGV) eq 'wrong-scope';
my $first = eval { onpc_password::enter_overlay_shell_password($journey); 1; };
my $replay = eval { onpc_password::enter_overlay_shell_password($journey); 1; };
print encode_json({first => $first ? 1 : 0, replay => $replay ? 1 : 0, events => \@events});
''', 'panel-request-case', json.dumps(binding), mode)
    if role is None:
        assert json.loads(result.stdout) == {'first': 0, 'replay': 0, 'events': []}
        return
    assert json.loads(result.stdout) == {'first': 1, 'replay': 0, 'events': [
        ['proof', 'approval-qualified'], ['proof', 'approval-rechecked'],
        ['delivery', role, 'overlay-shell-approval']]}


@pytest.mark.parametrize('mode', ['two-requests', 'replay', 'wrong-scope', 'wrong-child',
                                 'profile-setup', 'profile-wrong-scope',
                                 'grant-request', 'grant-wrong-scope', 'grant-wrong-child',
                                 'transition-request', 'transition-wrong-duration', 'revocation-request',
                                 'work-recovery', 'expired-recovery', 'kiosk-recovery', 'kiosk-recovery-wrong-scope',
                                 'app-restart-request', 'sign-out-request', 'reboot-request',
                                 'process-update-request', 'process-update-wrong-soft', 'session-update-request',
                                 'reboot-update-request',
                                 'sign-out-expired-recovery', 'reboot-expired-recovery',
                                 'daily-expired-recovery', 'daily-expired-wrong-scope',
                                 'daily-expired-included', 'daily-expired-included-wrong-scope',
                                 'expired-recovery-wrong-scope', 'idle-requests', 'idle-crossed-duration'])
def test_composed_kiosk_secret_scope_and_single_use(mode):
    # Execute the real password guard; replace only the secret delivery sink.
    # No password is supplied, and each isolated Perl process owns its latch.
    # These are independent guard inputs, not runnable customer plans. Loading
    # every journey here couples a focused refusal check to unrelated setup.
    transition = ['app-rule-changes-soft-opening', 'soft-opening-', ['other-child', 'parent', 75, True]]
    revocation = ['revocation-case-request', 'request-', ['other-child', 'parent', 1200, True]]
    recovery = ['grant-work-recovery', ['child', 'parent', 1200, True]]
    if mode in ('expired-recovery', 'sign-out-expired-recovery', 'reboot-expired-recovery',
                'expired-recovery-wrong-scope'):
        expired = ('app-restart-expired' if mode == 'expired-recovery' else
                   'reboot-expired' if mode == 'reboot-expired-recovery' else 'sign-out-in-expired')
        recovery = [expired, ['child', 'parent', 1200, False]]
    if mode.startswith('daily-expired-'):
        recovery = ['expired-daily-replacement', ['child', 'parent', 1200, 'included' in mode]]
    restart = ('reboot-active' if mode == 'reboot-request' else
               'sign-out-in-active' if mode == 'sign-out-request' else 'app-restart-active')
    result = run_password_guard(r'''
my $mode = shift @ARGV;
my $transition = decode_json(shift @ARGV);
my $revocation = decode_json(shift @ARGV);
my $recovery = decode_json(shift @ARGV);
my $panel_prefix = shift @ARGV;
my $kiosk_prefix = shift @ARGV;
my $restart = decode_json(shift @ARGV);
my $process_update = decode_json(shift @ARGV);
my $idle_bindings = decode_json(shift @ARGV);
my $first = bless {prefix => 'kiosk-delayed-approval-first', stage_prefix => 'first-',
    kiosk_request => ['child', 'parent', 30, 0], review => 0}, 'onpc_journey';
my $second = bless {%$first, prefix => 'kiosk-delayed-approval-second', stage_prefix => 'second-'}, 'onpc_journey';
$first->{stage_prefix} = 'second-' if $mode eq 'wrong-scope';
$first->{kiosk_request} = ['other-child', 'parent', 30, 0] if $mode eq 'wrong-child';
if ($mode =~ /^profile-/) {
    $first = bless {prefix => $panel_prefix . '-profile-request',
        stage_prefix => $mode eq 'profile-setup' ? 'profile-request-' : 'first-',
        review => 0}, 'onpc_journey';
}
if ($mode =~ /^grant-/) {
    $first = bless {prefix => 'grant-access-case-request',
        stage_prefix => $mode eq 'grant-wrong-scope' ? 'first-' : 'request-',
        kiosk_request => [$mode eq 'grant-wrong-child' ? 'child' : 'other-child', 'parent', 1200, 1],
        review => 0}, 'onpc_journey';
}
if ($mode =~ /^transition-/) {
    $transition->[2][2] = 1200 if $mode eq 'transition-wrong-duration';
    $first = bless {prefix => $transition->[0], stage_prefix => $transition->[1],
        kiosk_request => $transition->[2],
        review => 0}, 'onpc_journey';
}
if ($mode eq 'revocation-request') {
    $first = bless {prefix => $revocation->[0], stage_prefix => $revocation->[1],
        kiosk_request => $revocation->[2], review => 0}, 'onpc_journey';
}
if ($mode eq 'app-restart-request' || $mode eq 'sign-out-request' || $mode eq 'reboot-request') {
    $first = bless {prefix => $restart->[0] . '-request', stage_prefix => 'request-',
        kiosk_request => $restart->[1], review => 0}, 'onpc_journey';
}
if ($mode =~ /^(?:process|session|reboot)-update-/) {
    $process_update->[1][3] = 1 if $mode eq 'process-update-wrong-soft';
    $first = bless {prefix => $process_update->[0] . '-request', stage_prefix => 'request-',
        kiosk_request => $process_update->[1], review => 0}, 'onpc_journey';
}
if ($mode =~ /^kiosk-recovery/) {
    $first = bless {prefix => $kiosk_prefix . '-kiosk-final',
        stage_prefix => $mode eq 'kiosk-recovery' ? 'kiosk-final-' : 'kiosk-first-',
        review => 0}, 'onpc_journey';
}
my $ok = eval {
    if ($mode =~ /^idle-/) {
        for my $scope ('request', 'recovery') {
            my $idle = bless {prefix => 'idle-active-expired-' . $scope,
                stage_prefix => $scope . '-', review => 0,
                kiosk_request => $idle_bindings->{$scope}}, 'onpc_journey';
            $idle->{kiosk_request} = $idle_bindings->{recovery} if $mode eq 'idle-crossed-duration';
            onpc_password::enter_kiosk_mate_password($idle, 'bound-request');
        }
    } elsif ($mode =~ /^kiosk-recovery/) {
        onpc_password::enter_kiosk_mate_password($first, 'request-1200');
        onpc_password::enter_kiosk_mate_password($first, 'request-1200');
    } elsif ($mode eq 'work-recovery' || $mode eq 'expired-recovery'
            || $mode eq 'sign-out-expired-recovery' || $mode eq 'reboot-expired-recovery'
            || $mode eq 'daily-expired-recovery' || $mode eq 'daily-expired-wrong-scope'
            || $mode eq 'daily-expired-included' || $mode eq 'daily-expired-included-wrong-scope'
            || $mode eq 'expired-recovery-wrong-scope') {
        my $setup = bless {prefix => $recovery->[0] . '-profile-request',
            stage_prefix => 'profile-request-', review => 0}, 'onpc_journey';
        onpc_password::enter_kiosk_mate_password($setup, 'long-request');
        my $return = bless {prefix => $recovery->[0],
            stage_prefix => ($mode eq 'expired-recovery-wrong-scope'
                || $mode eq 'daily-expired-wrong-scope'
                || $mode eq 'daily-expired-included-wrong-scope') ? 'profile-request-' : '',
            kiosk_request => $recovery->[1], review => 0}, 'onpc_journey';
        onpc_password::enter_kiosk_mate_password($return, 'bound-request');
    } elsif ($mode =~ /^profile-/) {
        onpc_password::enter_kiosk_mate_password($first, 'request-1200');
    } elsif ($mode =~ /^(?:grant|transition|revocation|app-restart|sign-out|reboot|process-update|session-update)-/) {
        onpc_password::enter_kiosk_mate_password($first, 'bound-request');
    } else {
        onpc_password::enter_kiosk_mate_password($first, 'bound-request');
        onpc_password::enter_kiosk_mate_password($mode eq 'replay' ? $first : $second, 'bound-request');
    }
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
''', mode, json.dumps(transition), json.dumps(revocation), json.dumps(recovery),
        'panel-request-case', 'baseline-journey',
        json.dumps([restart, ['other-child', 'parent', 1200, True]]),
        json.dumps(['update-reboot-case' if mode == 'reboot-update-request' else
                    'update-session-case' if mode == 'session-update-request' else 'update-process-case',
                    ['other-child', 'parent', 1200, False]]),
        json.dumps({'request': ['other-child', 'parent', 600, True],
                    'recovery': ['other-child', 'parent', 1200, True]}))
    value = json.loads(result.stdout)
    deliveries = [event for event in value['events'] if event[0] == 'delivery']
    if mode.startswith('idle-'):
        assert value['ok'] == (mode == 'idle-requests')
        scopes = ('request', 'recovery') if mode == 'idle-requests' else ()
        assert deliveries == [['delivery', 'parent', scope + '-kiosk-mate-approval'] for scope in scopes]
        assert [event for event in value['events'] if event[0] == 'proof'] == [
            ['proof', scope + '-approval-' + proof]
            for scope in scopes for proof in ('qualified', 'rechecked')]
    elif mode == 'kiosk-recovery':
        assert value['ok'] == 0  # The second delivery is refused.
        assert deliveries == [['delivery', 'parent', 'kiosk-final-kiosk-mate-request-1200']]
        assert [event for event in value['events'] if event[0] == 'proof'] == [
            ['proof', 'kiosk-final-approval-' + proof] for proof in ('qualified', 'rechecked')]
    elif mode in ('work-recovery', 'expired-recovery', 'sign-out-expired-recovery',
                  'reboot-expired-recovery', 'daily-expired-recovery', 'daily-expired-included'):
        assert value['ok'] == 1
        assert deliveries == [
            ['delivery', 'parent', 'profile-request-kiosk-mate-long-request'],
            ['delivery', 'parent', 'kiosk-mate-approval']]
        assert [event for event in value['events'] if event[0] == 'proof'] == [
            ['proof', prefix + 'approval-' + proof]
            for prefix in ('profile-request-', '') for proof in ('qualified', 'rechecked')]
    elif mode in ('expired-recovery-wrong-scope', 'daily-expired-wrong-scope',
                  'daily-expired-included-wrong-scope'):
        assert value['ok'] == 0
        assert deliveries == [['delivery', 'parent', 'profile-request-kiosk-mate-long-request']]
        assert [event for event in value['events'] if event[0] == 'proof'] == [
            ['proof', 'profile-request-approval-' + proof] for proof in ('qualified', 'rechecked')]
    elif mode == 'two-requests':
        assert value['ok'] == 1
        assert deliveries == [['delivery', 'parent', request + '-kiosk-mate-approval']
                               for request in ('first', 'second')]
        assert [event for event in value['events'] if event[0] == 'proof'] == [
            ['proof', request + '-approval-' + proof]
            for request in ('first', 'second') for proof in ('qualified', 'rechecked')]
    elif mode in ('grant-request', 'transition-request', 'revocation-request', 'app-restart-request',
                  'sign-out-request', 'reboot-request', 'process-update-request', 'session-update-request',
                  'reboot-update-request'):
        assert value['ok'] == 1
        scope = 'soft-opening' if mode == 'transition-request' else 'request'
        assert deliveries == [['delivery', 'parent', scope + '-kiosk-mate-approval']]
        assert [event for event in value['events'] if event[0] == 'proof'] == [
            ['proof', scope + '-approval-' + proof] for proof in ('qualified', 'rechecked')]
    elif mode == 'profile-setup':
        assert value['ok'] == 1
        assert deliveries == [['delivery', 'parent', 'profile-request-kiosk-mate-request-1200']]
        assert [event for event in value['events'] if event[0] == 'proof'] == [
            ['proof', 'profile-request-approval-' + proof]
            for proof in ('qualified', 'rechecked')]
    else:
        assert value['ok'] == 0
        assert len(deliveries) == (1 if mode == 'replay' else 0)
