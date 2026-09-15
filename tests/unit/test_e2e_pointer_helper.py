"""Execute the reusable pointer with fresh matches from any reviewed surface."""

import json

import pytest

from tests.support.perl import run_perl


PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our $match = decode_json(shift);
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub assert_screen { push @main::events, ['assert', @_]; return $main::match; }
sub get_var { $_[1] }
sub console { bless {}, 'Console' }
sub mouse_set { push @main::events, ['pointer', @_]; }
sub mouse_click { push @main::events, ['click', @_]; }
sub mouse_hide { }
sub wait_still_screen { }
package Console;
sub mouse_width { 1280 }
sub mouse_height { 800 }
package main;
require onpc_pointer;
my $ok = eval { onpc_pointer::click('onpc-child-fixture-button', 30); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''


@pytest.mark.parametrize('fault', [None, 'no-point', 'point-on-edge', 'outside-image', 'weak-context'])
def test_fresh_match_geometry_is_required_before_pointer_input(fault):
    match = {'area': [
        dict(x=10, y=10, w=40, h=20, similarity=1),
        dict(x=700, y=500, w=40, h=30, similarity=1, click_point=dict(xpos=20, ypos=15)),
    ]}
    target = match['area'][-1]
    if fault == 'no-point':
        del target['click_point']
    elif fault == 'point-on-edge':
        target['click_point']['xpos'] = 40
    elif fault == 'outside-image':
        target['x'] = 1010
    elif fault == 'weak-context':
        match['area'][0]['similarity'] = .99
    result = json.loads(run_perl(PROBE, json.dumps(match)).stdout)
    assert result['ok'] == (fault is None)
    assert result['events'][0] == ['assert', 'onpc-child-fixture-button', 30]
    if fault:
        assert len(result['events']) == 1
    else:
        assert result['events'][1:] == [['pointer', 900, 536], ['click', 'left']]
