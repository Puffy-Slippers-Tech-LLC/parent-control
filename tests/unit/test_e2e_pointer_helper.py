"""Execute the reusable pointer with fresh matches from any reviewed surface."""

import json

import pytest

from tests.support.perl import run_perl


PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our $match = decode_json(shift);
our $mode = shift // '';
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub assert_screen { push @main::events, ['assert', @_]; return $main::match; }
sub get_var { $_[1] }
sub console { bless {}, 'Console' }
sub mouse_set { push @main::events, ['pointer', @_]; }
sub mouse_click {
    push @main::events, ['click', @_];
    die 'uncertain pointer' if $main::match->{uncertain};
}
sub mouse_hide { }
sub wait_still_screen { }
package Console;
sub mouse_width { $main::mode ? $main::match->{width} : 1280 }
sub mouse_height { $main::mode ? $main::match->{height} : 800 }
package main;
require onpc_pointer;
require onpc_journey;
my $ok = eval {
    if ($mode) {
        onpc_journey->new(prefix => 'unit', review => 0, exchange => sub {})->click_target(
            {ui_pointer => $match->{point}});
    } else {
        onpc_pointer::click('onpc-child-fixture-button', 30);
    }
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''


@pytest.mark.parametrize('fault', [None, 'no-point', 'point-on-edge', 'outside-image', 'weak-context'])
def test_image_pointer_route_refuses_before_matching_or_input(fault):
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
    assert not result['ok']
    assert result['events'] == []


@pytest.mark.parametrize('size,point', [((1024, 768), (400, 90)), ((1280, 800), (700, 80)),
                                      ((2560, 1600), (1850, 150))])
@pytest.mark.parametrize('fault', [None, 'outside', 'negative', 'missing', 'uncertain'])
def test_coordinate_reply_route_refuses_before_pointer_input(size, point, fault):
    value = {'width': size[0], 'height': size[1], 'point': {'x': point[0], 'y': point[1]}}
    if fault == 'outside': value['point']['x'] = size[0]
    if fault == 'negative': value['point']['x'] = -1
    if fault == 'missing': del value['point']['y']
    if fault == 'uncertain': value['uncertain'] = True
    result = json.loads(run_perl(PROBE, json.dumps(value), 'functional').stdout)
    assert not result['ok']
    assert result['events'] == []


PROMPT_PROBE = r'''
use strict;
use warnings;
use JSON::PP;
chdir(shift) or die 'test-directory';
our $uncertain = shift;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub console { bless {}, 'Console' }
sub mouse_set { push @main::events, ['pointer', @_]; }
sub mouse_click {
    push @main::events, ['click', @_];
    die 'uncertain pointer' if $main::uncertain;
}
package Console;
sub mouse_width { 1024 }
sub mouse_height { 768 }
package main;
require onpc_journey;
my $ok = eval { onpc_journey::service_system_prompt('opened', 1); 1; };
my $replay = eval { onpc_journey::service_system_prompt('opened', 1); 1; };
print encode_json({ok => $ok ? 1 : 0, replay => $replay ? 1 : 0, events => \@events});
'''


@pytest.mark.parametrize('fault', [None, 'wrong-stage', 'wrong-sequence', 'unknown-dialog',
                                 'outside', 'uncertain', 'extra-field', 'stale-reply'])
def test_shared_prompt_coordinate_route_refuses_before_files_or_input(tmp_path, fault):
    request = {'stage': 'opened', 'sequence': 1, 'kind': 'login-keyring',
               'ui_pointer': {'x': 200, 'y': 330}}
    if fault == 'wrong-stage': request['stage'] = 'different'
    if fault == 'wrong-sequence': request['sequence'] = 2
    if fault == 'unknown-dialog': request['kind'] = 'polkit'
    if fault == 'outside': request['ui_pointer']['x'] = 1024
    if fault == 'extra-field': request['secret'] = 'canary'
    reply = tmp_path / 'opened.prompt-1.reply.json'
    if fault == 'stale-reply': reply.write_text('{}')
    (tmp_path / 'opened.prompt-1.request.json').write_text(json.dumps(request))
    result = json.loads(run_perl(PROMPT_PROBE, str(tmp_path), '1' if fault == 'uncertain' else '0').stdout)
    assert not result['ok']
    assert not result['replay']
    assert result['events'] == []
    if fault == 'stale-reply':
        assert reply.read_text() == '{}'
    else:
        assert not reply.exists()
    assert not (tmp_path / 'opened.prompt-1.input-started').exists()
