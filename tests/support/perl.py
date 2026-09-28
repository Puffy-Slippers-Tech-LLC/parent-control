"""Run actual graphical Perl helpers with scenario-supplied public API doubles."""

import subprocess

from tests.support.paths import ROOT

LIB = ROOT / "tests/integration/graphical_smoke/lib"


# Isolated, bounded Perl children with captured pipes; no VM or shared resources.
ALLOWANCE_WORKER = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; $INC{'onpc_gdm.pm'} = 1; $INC{'onpc_password.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @main::events, ['key', @_]; }
sub console { bless {}, 'Console' }
sub power { push @main::events, ['power', @_]; }
sub check_shutdown { 1 }
package Console;
sub disable { }
package onpc_gdm;
sub reattach_functional { }
sub choose_account { $_[0]->seen('parent-focused'); }
package onpc_password;
sub enter_parent_gdm_password {
    $_[0]->seen('recipient-qualified'); $_[0]->seen('recipient-rechecked');
}
package main;
require onpc_set_allowance;
my $exchange = sub {
    push @events, ['stage', $_[0]];
    die 'fixture:refused' if $_[0] eq $ENV{ONPC_TEST_REFUSE};
    return {observed => $_[0], ui_focused => JSON::PP::true};
};
my $ok = eval { onpc_set_allowance::run($exchange); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events, error => "$@"});
'''


def run_perl(program, *arguments, timeout=10):
    """Return both output streams and preserve interpreter failures and deadlines."""
    return subprocess.run(
        ["/usr/bin/perl", "-I", str(LIB), "-", *arguments],
        input=program, text=True, capture_output=True, timeout=timeout, check=True,
    )
