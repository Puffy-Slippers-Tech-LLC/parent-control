"""VT6 prompt inspection refuses without a public identity contract."""

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
sub send_key { push @main::events, ['key', @_]; }
sub type_string { push @main::events, ['text', @_]; }
sub wait_still_screen { push @main::events, ['settle']; }
sub save_screenshot { push @main::events, ['image']; return {screenshot => 'private'}; }
package main;
require onpc_vt6;
my $exchanges = 0;
my $ok = eval { onpc_vt6::inspect_prompt(sub { $exchanges++; return {}; }); 1; };
my $error = "$@";
my $capture = eval { onpc_password::capture_before_authentication(); 1; };
my $capture_error = "$@";
print encode_json({ok => $ok ? 1 : 0, exchanges => $exchanges,
                   capture => $capture ? 1 : 0, capture_error => $capture_error,
                   events => \@events, error => $error});
'''


def test_vt6_prompt_inspection_refuses_before_console_image_or_exchange():
    result = json.loads(run_perl(PROBE).stdout)
    assert not result['ok']
    assert not result['capture']
    assert result['exchanges'] == 0
    assert result['events'] == []
    assert 'public-recipient-id-required' in result['error']
    assert 'capture-refused' in result['capture_error']
