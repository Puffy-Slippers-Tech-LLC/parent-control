"""Execute fixed Perl installation input with public testapi test doubles."""

import json

import pytest
from tests.support.perl import run_perl

PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our $mode = shift;
our $prompt_sample = shift;
our @events;
our $waits = 0;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub get_var { return $main::mode eq 'video' ? 0 : 1; }
sub current_console { return $main::mode eq 'console' ? 'sut' : 'onpc-serial'; }
sub get_required_var {
    return $main::mode eq 'control' ? "unsafe\n" : 'private-canary';
}
sub type_string {
    my ($input) = @_;
    die 'fixed input only' unless $input eq "\n" || $input eq "\x03" || $input eq
        "/usr/bin/sudo -k -p \$'\\nONPC-INSTALL-PASSWORD: ' -- /usr/bin/apt-get install -y /var/lib/onpc-e2e-assets/package.deb && printf 'ONPC-INSTALL-%s\\n' 'OK'\n";
    push @main::events, $input eq "\n" ? 'enter' : $input eq "\x03" ? 'cancel' : 'command';
}
sub wait_serial {
    my ($regex, %options) = @_;
    die 'output policy' unless $options{quiet} && !$options{record_output};
    if ($options{expect_not_found}) {
        return '';
    }
    $main::waits++;
    my $sample = $main::waits == 1 ? "\nONPC-INSTALL-PASSWORD: ] Password: "
        : $main::waits == 2 && $main::mode eq 'refusal'
            ? "\nONPC-INSTALL-PASSWORD: ] Password: "
        : $main::waits == 2 ? "\e[1;31m*** REBOOT REQUIRED: reboot before using the kiosk session. ***\e[0m\nONPC-INSTALL-OK\n" : 'fixture$ ';
    $sample = $main::prompt_sample if defined($main::prompt_sample) && $main::waits == 1;
    return undef if $main::mode eq 'prompt' && $main::waits == 1;
    return $sample =~ $regex ? $sample : undef;
}
sub type_password {
    die 'secret options' unless @_ == 1 && $_[0] eq
        ($main::mode eq 'refusal' ? 'onpc-deliberate-refusal' : 'private-canary');
    push @main::events, $main::mode eq 'refusal' ? 'refusal-password' : 'password';
    die 'private-canary' if $main::mode eq 'typing';
}
sub record_info {
    push @main::events, 'record' if $_[0] eq 'install-complete';
}
sub save_screenshot { die 'capture must stay sealed'; }
package main;
require onpc_install;
my $exchange = sub {
    my ($stage, $capture) = @_;
    die 'capture' if defined($capture);
    push @events, $stage;
    die 'private-canary' if $mode eq 'phase' && $stage eq 'install-ready';
    return {installation_authorized => $mode ne 'unauthorized',
        product_package_absent => $mode ne 'present', verified_assets => $mode ne 'assets',
        active_local_serial_session => $mode ne 'session',
        sudo_install_process_verified => $mode ne 'process',
        terminal_echo_disabled => $mode ne 'echo-enabled',
        installation_refused => $mode eq 'refusal',
        installed_identity_verified => 1, verified_package_digest => 1,
        product_reboot_required => $mode ne 'refusal',
        core_payload_absent => $mode eq 'refusal', install_process_absent => $mode eq 'refusal'};
};
my $ok = eval {
    $mode eq 'refusal' ? onpc_install::run_refusal($exchange)
        : onpc_install::run($exchange, ($mode eq 'arguments' ? ('extra') : ()));
    1;
};
my $error = $@;
my $retry = eval { onpc_install::run($exchange); 1; };
my $capture = eval { onpc_password::capture_before_authentication(); 1; };
print encode_json({ok => $ok ? 1 : 0, error => $error, retry => $retry ? 1 : 0,
                   capture => $capture ? 1 : 0, events => \@events});
'''


@pytest.mark.parametrize('mode', ['ok', 'arguments', 'video', 'console', 'phase',
    'unauthorized', 'present', 'assets', 'session', 'prompt', 'process', 'echo-enabled',
    'control', 'typing', 'refusal'])
def test_fixed_install_input_requires_phase_and_independent_password_proof(mode):
    result = run_perl(PROBE, mode)
    data = json.loads(result.stdout)
    assert 'private-canary' not in result.stdout + result.stderr
    assert data['ok'] == (mode in ('ok', 'refusal'))
    assert not data['retry'] and not data['capture']
    events = data['events']
    if mode in ('arguments', 'video', 'console', 'phase', 'unauthorized', 'present', 'assets', 'session'):
        assert 'command' not in events
    if mode in ('ok', 'typing'):
        assert events.index('install-ready') < events.index('command') < events.index('install-password') < events.index('password')
    else:
        assert 'password' not in events
    if mode == 'typing':
        assert 'install-complete' not in events
    if mode == 'ok':
        assert events[-2:] == ['install-complete', 'record']
    if mode == 'refusal':
        assert events.index('install-password') < events.index('refusal-password') < events.index('cancel')
        assert events.index('cancel') < events.index('install-refused')
        assert events.count('refusal-password') == 1 and 'password' not in events
        assert 'install-complete' not in events


def test_refusal_token_cannot_accidentally_authenticate_a_user_selected_password():
    probe = PROBE.replace("return $main::mode eq 'control' ? \"unsafe\\n\" : 'private-canary';",
                          "return 'onpc-deliberate-refusal';")
    probe = probe.replace("($main::mode eq 'refusal' ? 'onpc-deliberate-refusal' : 'private-canary')",
                          "($main::mode eq 'refusal' ? 'onpc-deliberate-refusal-alternate' : 'private-canary')")
    data = json.loads(run_perl(probe, 'refusal').stdout)
    assert data['ok']
    assert data['events'].count('refusal-password') == 1
    assert 'password' not in data['events']


@pytest.mark.parametrize('prompt', [
    "private-canary '[sudo: ONPC-INSTALL-PASSWORD: ] Password: ",
    '[sudo: ONPC-INSTALL-PASSWORD: ] private-canary: ',
    '[sudo: ONPC-INSTALL-PASSWORD: ] Password:',
    '[sudo: ONPC-INSTALL-PASSWORD: ] Password: \x1b[0m',
    '[sudo: ONPC-INSTALL-PASSWORD: ] Password: \n',
])
def test_unrelated_private_incomplete_or_control_modified_prompts_refuse_input(prompt):
    result = run_perl(PROBE, 'ok', prompt)
    data = json.loads(result.stdout)
    assert not data['ok'] and not data['retry'] and not data['capture']
    assert 'password' not in data['events']
    assert 'private-canary' not in result.stdout + result.stderr
