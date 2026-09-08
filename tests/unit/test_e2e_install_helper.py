"""Execute fixed Perl installation input with public testapi test doubles."""

import json
from pathlib import Path
import subprocess

import pytest

LIB = Path(__file__).resolve().parents[1] / 'integration/graphical_smoke/lib'
PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our $mode = shift;
our @events;
our $waits = 0;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub get_var { return $main::mode eq 'video' ? 0 : 1; }
sub current_console { return $main::mode eq 'console' ? 'sut' : 'onpc-serial'; }
sub get_required_var { return $main::mode eq 'control' ? "unsafe\n" : 'private-canary'; }
sub type_string {
    my ($input) = @_;
    die 'fixed input only' unless $input eq "\n" || $input eq
        "/usr/bin/sudo -k -p 'ONPC-INSTALL-PASSWORD: ' -- /usr/bin/apt-get install -y /var/lib/onpc-e2e-assets/package.deb && printf 'ONPC-INSTALL-%s\\n' 'OK'\n";
    push @main::events, $input eq "\n" ? 'enter' : 'command';
}
sub wait_serial {
    my ($regex, %options) = @_;
    die 'output policy' unless $options{quiet} && !$options{record_output};
    $main::waits++;
    my $sample = $main::waits == 1 ? 'ONPC-INSTALL-PASSWORD: '
        : $main::waits == 2 ? "ONPC-INSTALL-OK\r\n" : 'fixture$ ';
    return undef if $main::mode eq 'prompt' && $main::waits == 1;
    return undef if $main::mode eq 'shell' && $main::waits == 3;
    if ($main::waits == 2) {
        $sample = q{printf 'ONPC-INSTALL-%s\n' 'OK'} if $main::mode eq 'echo';
        $sample = 'Sorry, try again.' if $main::mode eq 'denial';
    }
    return $sample =~ $regex ? $sample : undef;
}
sub type_password {
    die 'secret options' unless @_ == 1 && $_[0] eq 'private-canary';
    push @main::events, 'password';
    die 'private-canary' if $main::mode eq 'typing';
}
sub record_info { push @main::events, 'record'; }
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
        sudo_install_process_verified => $mode ne 'process', terminal_echo_disabled => $mode ne 'echo-enabled',
        installed_identity_verified => $mode ne 'package', verified_package_digest => $mode ne 'digest',
        product_reboot_required => $mode ne 'marker'};
};
my $ok = eval { onpc_install::run($exchange, ($mode eq 'arguments' ? ('extra') : ())); 1; };
my $error = $@;
my $retry = eval { onpc_install::run($exchange); 1; };
my $capture = eval { onpc_password::capture_before_authentication(); 1; };
print encode_json({ok => $ok ? 1 : 0, error => $error, retry => $retry ? 1 : 0,
                   capture => $capture ? 1 : 0, events => \@events});
'''


@pytest.mark.parametrize('mode', ['ok', 'arguments', 'video', 'console', 'phase',
    'unauthorized', 'present', 'assets', 'session', 'prompt', 'process', 'echo-enabled',
    'control', 'typing', 'echo', 'denial', 'package', 'digest', 'marker', 'shell'])
def test_fixed_install_input_requires_phase_and_independent_password_proof(mode):
    result = subprocess.run(['/usr/bin/perl', '-I', str(LIB), '-e', PROBE, mode],
                            capture_output=True, text=True, timeout=10, check=True)
    data = json.loads(result.stdout)
    assert 'private-canary' not in result.stdout + result.stderr
    assert data['ok'] == (mode == 'ok')
    assert not data['retry'] and not data['capture']
    events = data['events']
    if mode in ('arguments', 'video', 'console', 'phase', 'unauthorized', 'present', 'assets', 'session'):
        assert 'command' not in events
    if mode in ('ok', 'typing', 'echo', 'denial', 'package', 'digest', 'marker', 'shell'):
        assert events.index('install-ready') < events.index('command') < events.index('install-password') < events.index('password')
    else:
        assert 'password' not in events
    if mode in ('echo', 'denial', 'typing'):
        assert 'install-complete' not in events
    if mode == 'ok':
        assert events[-2:] == ['install-complete', 'record']
