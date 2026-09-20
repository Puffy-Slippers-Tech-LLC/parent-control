"""VT6 graphical authentication is contained until it has a public recipient ID."""

import json

from tests.support.perl import run_perl


PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub select_console { push @main::events, ['select', @_]; }
sub current_console { push @main::events, ['console']; return 'sut'; }
sub get_var { push @main::events, ['variable', @_]; return $_[1]; }
sub send_key { push @main::events, ['key', @_]; }
sub type_string { push @main::events, ['text', @_]; }
sub type_password { push @main::events, ['secret']; }
sub assert_screen { push @main::events, ['image', @_]; }
sub check_screen { push @main::events, ['image', @_]; }
sub wait_still_screen { push @main::events, ['settle']; }
sub get_required_var { push @main::events, ['secret-read']; return 'private'; }
package main;
require onpc_vt6;
my $exchanges = 0;
my $ok = eval { onpc_vt6::authenticate(sub { $exchanges++; return {}; }); 1; };
my $first_error = "$@";
my $capture = eval { onpc_password::capture_before_authentication(); 1; };
my $capture_error = "$@";
my $retry = eval { onpc_vt6::authenticate(sub { $exchanges++; return {}; }); 1; };
my $retry_error = "$@";
print encode_json({ok => $ok ? 1 : 0, retry => $retry ? 1 : 0,
                   capture => $capture ? 1 : 0, capture_error => $capture_error,
                   exchanges => $exchanges, events => \@events,
                   first_error => $first_error, retry_error => $retry_error});
'''


def test_vt6_authentication_refuses_before_console_image_secret_or_exchange():
    result = json.loads(run_perl(PROBE).stdout)
    assert not result['ok']
    assert not result['retry']
    assert not result['capture']
    assert result['exchanges'] == 0
    assert result['events'] == []
    assert 'public-recipient-id-required' in result['first_error']
    assert 'capture-refused' in result['capture_error']
    assert 'already-attempted' in result['retry_error']
