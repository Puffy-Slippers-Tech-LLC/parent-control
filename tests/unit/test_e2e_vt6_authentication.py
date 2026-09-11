"""Execute the one-shot VT6 worker with public API/controller fault doubles.

These tests do not qualify the missing live controller or authenticated session.
"""

import json

import pytest

from tests.support.perl import run_perl


PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our ($fault, $target) = @ARGV;
our @events;
our $returns = 0;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub event {
    my ($name) = @_;
    push @main::events, $name;
    die 'private-canary' if $main::fault eq 'api' && $main::target eq $name;
}
sub get_var {
    event('video');
    return 0 if $main::fault eq 'video'
        && ($main::target eq 'initial' || grep { $_ eq $main::target } @main::events);
    return 1;
}
sub select_console { die 'wrong console' unless $_[0] eq 'sut'; event('select'); }
sub current_console {
    event('console');
    return 'onpc-serial' if $main::fault eq 'console'
        && ($main::target eq 'initial' || grep { $_ eq $main::target } @main::events);
    return 'sut';
}
sub send_key {
    my $name = $_[0] eq 'ret' ? 'return-' . ++$main::returns : $_[0];
    event($name);
}
sub wait_still_screen { event('still'); return 1; }
sub type_string {
    die 'wrong fixture input' unless @_ == 3 && $_[0] eq 'onpc-parent-jamie'
        && $_[1] eq 'secret' && $_[2] == 1;
    event('fixture');
}
sub assert_screen {
    die 'wrong needle' unless @_ == 2 && $_[0] eq 'onpc-vt6-parent-password' && $_[1] == 30;
    event('needle');
    return $main::fault eq 'no-match' ? 0 : 1;
}
sub save_screenshot {
    event('capture');
    return $main::fault eq 'bad-capture' ? {} : {screenshot => 'smoke-9.png'};
}
sub get_required_var {
    die 'wrong secret' unless @_ == 1 && $_[0] eq '_SECRET_ONPC_PARENT_PASSWORD';
    # Executable assertion: sealing precedes even secret retrieval.
    die 'capture open' if eval { onpc_password::capture_before_authentication(); 1; };
    event('secret-read');
    return $main::fault eq 'value' ? JSON::PP::decode_json($main::target) : 'private-canary';
}
sub type_password {
    die 'wrong password API' unless @_ == 1 && $_[0] eq 'private-canary';
    event('password');
}
package main;
require onpc_vt6;
my %proofs = (
    'vt6-login-ready' => [qw(vt6_getty_verified active_vt6_verified)],
    'vt6-password-ready' => [qw(vt6_login_process_verified terminal_echo_disabled
        active_vt6_verified vt6_recipient_continuity_verified)],
    'vt6-password-screen' => [qw(vt6_login_process_verified terminal_echo_disabled
        active_vt6_verified vt6_recipient_continuity_verified vt6_prompt_pixels_verified
        vt6_password_input_authorized)],
    'vt6-authenticated' => [qw(active_local_vt6_session active_vt6_verified
        vt6_shell_ready_verified vt6_login_continuity_verified)],
);
my $exchange = sub {
    my ($stage, $shot) = @_;
    testapi::event($stage);
    die 'capture shape' unless defined($shot) == ($stage eq 'vt6-password-screen' ? 1 : 0);
    if ($stage eq 'vt6-password-screen') {
        die 'wrong capture' unless $shot eq 'smoke-9.png';
        die 'capture open' if eval { onpc_password::capture_before_authentication(); 1; };
    }
    my $reply = {stage => $stage, boot_sha256 => 'a' x 64,
        map { $_ => JSON::PP::true } @{$proofs{$stage}}};
    if ($fault eq 'proof' && exists($reply->{$target})) {
        $reply->{$target} = JSON::PP::false;
    }
    if ($stage eq $target) {
        $reply->{stage} = 'vt6-password-ready' if $fault eq 'stale';
        $reply->{boot_sha256} = 'b' x 64 if $fault eq 'boot';
        $reply->{boot_sha256} = 'invalid' if $fault eq 'invalid-boot';
        $reply->{extra} = 'private-canary' if $fault eq 'extra';
        delete($reply->{stage}) if $fault eq 'missing';
        $reply->{$proofs{$stage}[0]} = 'true' if $fault eq 'string-bool';
        $reply->{$proofs{$stage}[0]} = 1 if $fault eq 'numeric-bool';
        $reply = [] if $fault eq 'shape';
    }
    return $reply;
};
if ($fault eq 'prior-inspection') {
    eval { onpc_vt6::inspect_prompt(sub { die 'refuse'; }); };
    @events = ();
}
my $ok = eval {
    $fault eq 'arguments' ? onpc_vt6::authenticate() : onpc_vt6::authenticate($exchange);
    1;
};
my $error = $@;
my $events_before_retry = scalar @events;
my $retry = eval { onpc_vt6::authenticate($exchange); 1; };
my $inspect = eval { onpc_vt6::inspect_prompt($exchange); 1; };
my $capture = eval { onpc_password::capture_before_authentication(); 1; };
print encode_json({ok => $ok ? 1 : 0, error => $error, retry => $retry ? 1 : 0,
    inspect => $inspect ? 1 : 0, capture => $capture ? 1 : 0,
    events_before_retry => $events_before_retry, events => \@events});
'''


def invoke(fault='ok', target=''):
    result = run_perl(PROBE, fault, target)
    assert 'private-canary' not in result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert not data['retry'] and not data['inspect'] and not data['capture']
    assert len(data['events']) == data['events_before_retry']
    if not data['ok']:
        assert data['error'] in ('vt6:authentication-failed\n', 'vt6:already-attempted\n')
    return data


def test_one_shot_worker_seals_capture_before_receipt_and_secret_access():
    data = invoke()
    assert data['ok']
    assert data['events'] == [
        'video', 'select', 'video', 'console', 'ctrl-alt-f6', 'still', 'vt6-login-ready',
        'video', 'console', 'fixture', 'return-1', 'still', 'vt6-password-ready',
        'needle', 'capture', 'vt6-password-screen', 'video', 'console', 'secret-read',
        'video', 'console', 'password', 'video', 'console', 'return-2', 'vt6-authenticated']


STAGES = ['vt6-login-ready', 'vt6-password-ready', 'vt6-password-screen', 'vt6-authenticated']


@pytest.mark.parametrize('stage', STAGES)
@pytest.mark.parametrize('fault', ['api', 'extra', 'missing', 'string-bool', 'numeric-bool',
                                  'shape', 'invalid-boot'])
def test_receipt_failure_refuses_input_or_completion_without_retry(stage, fault):
    data = invoke(fault, stage)
    assert not data['ok']
    if stage != 'vt6-authenticated':
        assert 'secret-read' not in data['events']
    assert data['events'].count('password') <= 1


@pytest.mark.parametrize('fault,stage', [
    ('stale', 'vt6-login-ready'), ('stale', 'vt6-password-screen'),
    ('stale', 'vt6-authenticated'), *[('boot', stage) for stage in STAGES[1:]]])
def test_reordered_receipt_or_changed_boot_never_advances(fault, stage):
    data = invoke(fault, stage)
    assert not data['ok']
    if stage != 'vt6-authenticated':
        assert 'secret-read' not in data['events']


@pytest.mark.parametrize('proof', [
    'vt6_getty_verified', 'active_vt6_verified', 'vt6_login_process_verified',
    'terminal_echo_disabled', 'vt6_recipient_continuity_verified', 'vt6_prompt_pixels_verified',
    'vt6_password_input_authorized', 'active_local_vt6_session', 'vt6_shell_ready_verified',
    'vt6_login_continuity_verified'])
def test_every_controller_proof_is_mandatory(proof):
    data = invoke('proof', proof)
    assert not data['ok']
    if proof not in ('active_local_vt6_session', 'vt6_shell_ready_verified', 'vt6_login_continuity_verified'):
        assert 'secret-read' not in data['events']


@pytest.mark.parametrize('fault,target', [
    ('arguments', ''), ('prior-inspection', ''), ('no-match', ''), ('bad-capture', ''),
    *[(fault, stage) for fault in ('console', 'video')
      for stage in ('initial', 'vt6-login-ready', 'vt6-password-screen')],
    *[('api', api) for api in ('select', 'ctrl-alt-f6', 'still', 'fixture', 'return-1',
                              'needle', 'capture', 'secret-read', 'password', 'return-2')],
    *[('value', json.dumps(value)) for value in (None, [], '', 'x\n', 'é', 'x' * 257)]])
def test_api_and_credential_failures_latch_and_prevent_later_operations(fault, target):
    data = invoke(fault, target)
    assert not data['ok']
    if target in ('password', 'secret-read') or fault == 'value':
        assert 'return-2' not in data['events']
    if fault in ('no-match', 'bad-capture', 'arguments', 'prior-inspection', 'console', 'video'):
        assert 'secret-read' not in data['events']


@pytest.mark.parametrize('fault', ['video', 'console'])
@pytest.mark.parametrize('after', ['secret-read', 'password'])
def test_late_console_or_capture_policy_change_prevents_submission(fault, after):
    data = invoke(fault, after)
    assert not data['ok'] and 'return-2' not in data['events']
    if after == 'secret-read':
        assert 'password' not in data['events']
