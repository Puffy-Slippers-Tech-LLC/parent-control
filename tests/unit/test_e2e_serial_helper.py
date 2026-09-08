"""Execute the actual Perl serial flow against stubbed public testapi calls."""

import json
from pathlib import Path
import subprocess
import os
import termios

import pytest

LIB = Path(__file__).resolve().parents[1] / 'integration/graphical_smoke/lib'
PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our $mode = shift;
our @events;
our $waits = 0;
our $selected = '';
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub get_var { return $main::mode eq 'video' ? 0 : 1; }
sub get_required_var { return $main::mode eq 'control' ? "unsafe\n" : 'private-canary'; }
sub select_console { $main::selected = $_[0]; push @main::events, 'console:' . $_[0]; }
sub current_console { return $main::mode eq 'console' ? 'sut' : $main::selected; }
sub wait_serial {
    my ($regex, %opts) = @_;
    die 'unsafe output' unless $opts{quiet} && !$opts{record_output};
    $main::waits++;
    push @main::events, 'wait:' . $main::waits;
    return 0 if $main::mode eq 'prompt' && $main::waits == 2;
    if ($main::waits == 2) {
        my $sample = $main::mode eq 'wrong-echo' ? "other-parent\r\nPassword: "
            : $main::mode eq 'double-cr' ? "onpc-parent-jamie\r\r\nPassword: "
            : "onpc-parent-jamie\r\nPassword: ";
        return undef unless $sample =~ $regex;
        $sample =~ s/\r\n/\n/g; # Public testapi's documented return normalization.
        return $sample;
    }
    if ($main::waits == 3) {
        return undef if $main::mode eq 'shell-not-ready';
        push @main::events, 'shell-ready';
        my $sample = 'fixture-shell$ ';
        return $sample =~ $regex ? $sample : undef;
    }
    if ($main::waits == 4) {
        my $sample = $main::mode eq 'echo' ? q{printf 'ONPC-SERIAL-%s\n' 'OK'}
            : $main::mode eq 'ansi-output' ? "\e[?2004l\rONPC-SERIAL-OK\r\r\n"
            : "\r\nONPC-SERIAL-OK\r\n";
        return $sample =~ $regex;
    }
    return 1;
}
sub type_string { push @main::events, $_[0] eq "exit\n" ? 'logout' : $_[0] =~ /^printf/ ? 'command' : 'input'; }
sub type_password {
    die 'options' unless @_ == 1 && $_[0] eq 'private-canary';
    push @main::events, 'password';
    die 'private-canary' if $main::mode eq 'typing';
}
sub record_info { push @main::events, 'record'; }
sub save_screenshot { die 'capture must remain sealed'; }
package main;
require onpc_serial;
my $exchange = sub {
    my ($stage, $shot) = @_;
    die 'unexpected capture' if defined($shot);
    push @events, $stage;
    die 'private-canary' if $mode eq 'probe-error' && $stage eq 'serial-password';
    return {serial_login_process_verified => ($mode ne 'process'),
            terminal_echo_disabled => ($mode ne 'echo-enabled')};
};
my $ok = eval { onpc_serial::run($exchange); 1; };
my $error = $@;
my $retry = eval { onpc_serial::run($exchange); 1; };
my $capture = eval { onpc_password::capture_before_authentication(); 1; };
print encode_json({ok => $ok ? 1 : 0, error => $error, retry => $retry ? 1 : 0,
                   capture => $capture ? 1 : 0, events => \@events});
'''


@pytest.mark.parametrize('mode', ['ok', 'double-cr', 'ansi-output', 'shell-not-ready', 'video', 'console', 'prompt', 'wrong-echo', 'process',
                                 'echo-enabled', 'probe-error', 'control', 'typing', 'echo'])
def test_serial_secret_boundary_and_command_output(mode):
    result = subprocess.run(['/usr/bin/perl', '-I', str(LIB), '-e', PROBE, mode],
                            capture_output=True, text=True, timeout=10, check=True)
    data = json.loads(result.stdout)
    assert 'private-canary' not in result.stdout + result.stderr
    assert data['ok'] == (mode in ('ok', 'double-cr', 'ansi-output'))
    assert not data['retry'] and not data['capture']
    events = data['events']
    if mode in ('ok', 'double-cr', 'ansi-output'):
        assert events.index('serial-password') < events.index('password')
        assert events.index('serial-authenticated') < events.index('serial-command')
        assert events.index('serial-authenticated') < events.index('shell-ready') < events.index('command')
        assert events.index('serial-command') < events.index('logout') < events.index('serial-logout')
        assert events[-2:] == ['console:sut', 'record']
    elif mode in ('typing', 'echo', 'shell-not-ready'):
        assert 'password' in events and 'serial-command' not in events
        if mode == 'shell-not-ready':
            assert 'command' not in events
    else:
        assert 'password' not in events


def test_real_terminal_onlcr_produces_getty_double_carriage_return():
    master, slave = os.openpty()
    try:
        attrs = termios.tcgetattr(slave)
        attrs[1] |= termios.OPOST | termios.ONLCR
        termios.tcsetattr(slave, termios.TCSANOW, attrs)
        os.write(slave, b'onpc-parent-jamie\r\nPassword: ')
        import select
        assert select.select([master], [], [], 1)[0]
        assert os.read(master, 128) == b'onpc-parent-jamie\r\r\nPassword: '
    finally:
        os.close(slave)
        os.close(master)
