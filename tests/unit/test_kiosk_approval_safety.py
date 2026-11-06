"""Direct credential guards: human decision time never authorizes stale input."""
import json
from unittest.mock import Mock

import pytest

import ui_observations
from private_artifacts import EvidenceError
from tests.support.perl import run_perl


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
    from panel_request_case import PLAN, INCLUDED_PLAN
    plan = PLAN if mode == 'excluded' else INCLUDED_PLAN
    binding = list(plan.overlay_request)
    if mode == 'wrong-choice':
        binding[3] = False
    result = run_perl(r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub current_console { 'sut' }
sub get_var { '1' }
package onpc_journey;
sub seen {
    my ($self, $stage) = @_;
    push @main::events, ['proof', $stage];
    return {observed => $stage};
}
package main;
require onpc_password;
{
    no warnings 'redefine';
    *onpc_password::type_fixture_secret = sub { push @events, ['delivery', $_[0], $_[3]]; };
}
my $journey = bless {prefix => shift @ARGV, stage_prefix => '',
    overlay_request => decode_json(shift @ARGV), review => 0}, 'onpc_journey';
$journey->{stage_prefix} = 'later-' if shift(@ARGV) eq 'wrong-scope';
my $first = eval { onpc_password::enter_overlay_shell_password($journey); 1; };
my $replay = eval { onpc_password::enter_overlay_shell_password($journey); 1; };
print encode_json({first => $first ? 1 : 0, replay => $replay ? 1 : 0, events => \@events});
''', plan.prefix, json.dumps(binding), mode)
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
                                 'app-restart-request', 'sign-out-request',
                                 'process-update-request', 'process-update-wrong-soft',
                                 'sign-out-expired-recovery', 'expired-recovery-wrong-scope'])
def test_composed_kiosk_secret_scope_and_single_use(mode):
    # Execute the real password guard; replace only the secret delivery sink.
    # No password is supplied, and each isolated Perl process owns its latch.
    from app_rule_changes_case import PLAN
    from revocation_case import PLAN as REVOCATION_PLAN
    from grant_work_recovery import INCLUDED_PLAN as RECOVERY_PLAN
    from panel_request_case import PLAN as PANEL_PLAN
    from kiosk_recovery import PLAN as KIOSK_PLAN
    from app_restart_active import PLAN as RESTART_PLAN, SIGN_OUT_PLAN
    from app_restart_expired import PLAN as EXPIRED_PLAN, SIGN_OUT_PLAN as EXPIRED_SIGN_OUT_PLAN
    from update_process_case import PLAN as UPDATE_PLAN
    transition = [PLAN.prefix + '-soft-opening', 'soft-opening-', list(PLAN.kiosk_request)]
    revocation = [REVOCATION_PLAN.prefix + '-request', 'request-', list(REVOCATION_PLAN.kiosk_request)]
    recovery = [RECOVERY_PLAN.prefix, list(RECOVERY_PLAN.kiosk_request)]
    if mode in ('expired-recovery', 'sign-out-expired-recovery', 'expired-recovery-wrong-scope'):
        expired = EXPIRED_PLAN if mode == 'expired-recovery' else EXPIRED_SIGN_OUT_PLAN
        recovery = [expired.prefix, list(expired.kiosk_request)]
    restart = SIGN_OUT_PLAN if mode == 'sign-out-request' else RESTART_PLAN
    result = run_perl(r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub current_console { 'sut' }
sub get_var { '1' }
package onpc_journey;
sub seen {
    my ($self, $stage) = @_;
    push @main::events, ['proof', $self->{stage_prefix} . $stage];
    return {observed => $self->{stage_prefix} . $stage};
}
package main;
require onpc_password;
{
    no warnings 'redefine';
    *onpc_password::type_fixture_secret = sub { push @events, ['delivery', $_[0], $_[3]]; };
}
my $mode = shift @ARGV;
my $transition = decode_json(shift @ARGV);
my $revocation = decode_json(shift @ARGV);
my $recovery = decode_json(shift @ARGV);
my $panel_prefix = shift @ARGV;
my $kiosk_prefix = shift @ARGV;
my $restart = decode_json(shift @ARGV);
my $process_update = decode_json(shift @ARGV);
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
if ($mode eq 'app-restart-request' || $mode eq 'sign-out-request') {
    $first = bless {prefix => $restart->[0] . '-request', stage_prefix => 'request-',
        kiosk_request => $restart->[1], review => 0}, 'onpc_journey';
}
if ($mode =~ /^process-update-/) {
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
    if ($mode =~ /^kiosk-recovery/) {
        onpc_password::enter_kiosk_mate_password($first, 'request-1200');
        onpc_password::enter_kiosk_mate_password($first, 'request-1200');
    } elsif ($mode eq 'work-recovery' || $mode eq 'expired-recovery'
            || $mode eq 'sign-out-expired-recovery' || $mode eq 'expired-recovery-wrong-scope') {
        my $setup = bless {prefix => $recovery->[0] . '-profile-request',
            stage_prefix => 'profile-request-', review => 0}, 'onpc_journey';
        onpc_password::enter_kiosk_mate_password($setup, 'long-request');
        my $return = bless {prefix => $recovery->[0],
            stage_prefix => $mode eq 'expired-recovery-wrong-scope' ? 'profile-request-' : '',
            kiosk_request => $recovery->[1], review => 0}, 'onpc_journey';
        onpc_password::enter_kiosk_mate_password($return, 'bound-request');
    } elsif ($mode =~ /^profile-/) {
        onpc_password::enter_kiosk_mate_password($first, 'request-1200');
    } elsif ($mode =~ /^(?:grant|transition|revocation|app-restart|sign-out|process-update)-/) {
        onpc_password::enter_kiosk_mate_password($first, 'bound-request');
    } else {
        onpc_password::enter_kiosk_mate_password($first, 'bound-request');
        onpc_password::enter_kiosk_mate_password($mode eq 'replay' ? $first : $second, 'bound-request');
    }
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
''', mode, json.dumps(transition), json.dumps(revocation), json.dumps(recovery),
        PANEL_PLAN.prefix, KIOSK_PLAN.prefix,
        json.dumps([restart.prefix, list(restart.kiosk_request)]),
        json.dumps([UPDATE_PLAN.prefix, list(UPDATE_PLAN.kiosk_request)]))
    value = json.loads(result.stdout)
    deliveries = [event for event in value['events'] if event[0] == 'delivery']
    if mode == 'kiosk-recovery':
        assert value['ok'] == 0  # The second delivery is refused.
        assert deliveries == [['delivery', 'parent', 'kiosk-final-kiosk-mate-request-1200']]
        assert [event for event in value['events'] if event[0] == 'proof'] == [
            ['proof', 'kiosk-final-approval-' + proof] for proof in ('qualified', 'rechecked')]
    elif mode in ('work-recovery', 'expired-recovery', 'sign-out-expired-recovery'):
        assert value['ok'] == 1
        assert deliveries == [
            ['delivery', 'parent', 'profile-request-kiosk-mate-long-request'],
            ['delivery', 'parent', 'kiosk-mate-approval']]
        assert [event for event in value['events'] if event[0] == 'proof'] == [
            ['proof', prefix + 'approval-' + proof]
            for prefix in ('profile-request-', '') for proof in ('qualified', 'rechecked')]
    elif mode == 'expired-recovery-wrong-scope':
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
                  'sign-out-request', 'process-update-request'):
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
