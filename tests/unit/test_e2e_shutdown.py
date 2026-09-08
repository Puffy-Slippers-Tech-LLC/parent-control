"""Execute the maintained smoke against public API doubles; no guest/process cleanup."""

import json
from pathlib import Path
import subprocess

import pytest

DISTRIBUTION = Path(__file__).resolve().parents[1] / 'integration/graphical_smoke'
PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our $mode = shift;
our @events;
our $selected = '';
BEGIN { $INC{'testapi.pm'} = 1; $INC{'basetest.pm'} = 1; }
package basetest;
sub new { bless {}, shift; }
package testapi;
use Exporter 'import';
our @EXPORT = qw(wait_still_screen assert_and_click send_key select_console
                 check_screen record_info console power check_shutdown);
sub wait_still_screen { }
sub current_console { return $main::selected; }
sub select_console {
    die 'wrong initial console' unless @_ == 1 && $_[0] eq 'sut';
    push @main::events, 'select-graphics';
    $main::selected = $_[0];
}
sub assert_screen {
    push @main::events, 'match';
    return 1;
}
sub assert_and_click { }
sub send_key { }
sub check_screen { return 0; }
sub console {
    die 'wrong console' unless @_ == 1 && $_[0] eq 'sut';
    return bless {}, 'test_console';
}
sub record_info { push @main::events, 'record:' . $_[0]; }
sub power {
    die 'wrong action' unless @_ == 1 && $_[0] eq 'off';
    push @main::events, 'poweroff';
    die 'private-canary' if $main::mode eq 'power-error';
}
sub check_shutdown {
    die 'wrong timeout' unless @_ == 1 && $_[0] == 0;
    push @main::events, 'verify-off';
    return $main::mode ne 'status-error';
}
package test_console;
sub disable {
    push @main::events, 'disable-vnc';
    die 'private-canary' if $main::mode eq 'disable-error';
}
package main;
require shift;
{
    no warnings 'redefine';
    *capture = sub {
        push @events, $_[0];
        die 'private-canary' if $mode eq 'step-error';
        return {};
    };
    *exchange = sub {
        push @events, $_[0];
        return {serial => $mode eq 'serial', authenticate => $mode eq 'authenticated'};
    };
    *onpc_serial::run = sub { push @events, 'serial-complete'; };
    *onpc_password::enter_password = sub { push @events, 'authentication-input'; };
}
my $ok = eval { run(); 1; };
# Never propagate raw error text or fixture values into reviewed test evidence.
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''


@pytest.mark.parametrize('mode', ['plain', 'serial', 'authenticated', 'power-error',
                                 'status-error', 'step-error', 'disable-error'])
def test_complete_attempt_powers_off_and_verifies_before_success(mode):
    completed = subprocess.run(
        ['/usr/bin/perl', '-I', str(DISTRIBUTION / 'lib'), '-e', PROBE,
         mode, str(DISTRIBUTION / 'tests/smoke.pm')],
        capture_output=True, text=True, timeout=10, check=False)
    assert completed.returncode == 0, completed.stderr
    data = json.loads(completed.stdout)
    assert 'private-canary' not in completed.stdout + completed.stderr
    events = data['events']
    assert bool(data['ok']) == (mode in ('plain', 'serial', 'authenticated'))
    if data['ok']:
        assert events.index('select-graphics') < events.index('match') < events.index('gdm')
        assert events[-4:] == ['disable-vnc', 'poweroff', 'verify-off', 'record:shutdown']
        completed_stage = {'plain': 'dismissed', 'serial': 'serial-complete',
                           'authenticated': 'authenticated'}[mode]
        assert events.index(completed_stage) < events.index('disable-vnc')
    elif mode == 'power-error':
        assert events[-1] == 'poweroff' and 'verify-off' not in events
    elif mode == 'status-error':
        assert events[-1] == 'verify-off' and 'record:shutdown' not in events
    else:
        assert 'poweroff' not in events  # The outer lease handles failed attempts.
