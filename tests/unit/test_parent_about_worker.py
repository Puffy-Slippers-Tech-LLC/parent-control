"""Execute the actual customer worker's strict and image-acquisition paths."""

import json

import pytest

from tests.support.perl import run_perl

PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our $review = shift;
our $fault = shift;
our @events;
our $clicked = '';
our $matched = '';
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub reset_consoles { }
sub select_console { }
sub assert_screen {
    push @main::events, ['assert', $_[0]];
    die 'missing selected child' if $main::fault eq 'screen' && $_[0] eq 'onpc-parent-child-selected';
    die 'missing click target' if $main::fault eq 'click' && $_[0] eq 'onpc-parent-child-choice';
    $main::matched = $_[0];
    return {area => [{x => 858, y => 50, w => 24, h => 31,
        similarity => $main::fault eq 'weak' ? .99 : 1,
        click_point => {xpos => 12, ypos => 15}}]};
}
sub mouse_set { push @main::events, ['pointer', @_]; }
sub mouse_click {
    $main::clicked = $main::matched;
    push @main::events, ['click', $main::clicked];
}
sub mouse_hide { }
sub check_screen {
    push @main::events, ['check', $_[0]];
    return 1 if $main::fault eq 'recipient' && $_[0] eq 'onpc-gdm-parent-masked-password'
        && $main::clicked eq 'onpc-gdm-other-parent-installed-input-account';
    return 0;
}
sub get_var { $_[0] eq 'XRES' || $_[0] eq 'YRES' ? $_[1] : '1' }
sub get_required_var { 'unit-fixture-value' }
sub type_password { push @main::events, ['secret']; }
sub type_string { push @main::events, ['text', $_[0]]; }
sub send_key { push @main::events, ['key', $_[0]]; }
sub wait_still_screen { }
sub record_info { }
sub save_screenshot { die 'explicit capture forbidden'; }
sub console { bless {}, 'Console' }
sub power { push @main::events, ['power', $_[0]]; }
sub check_shutdown { 1 }
package Console;
sub disable { }
sub mouse_width { $main::fault eq 'dimensions' ? 1920 : $main::fault eq 'native' ? 1024 : 1280 }
sub mouse_height { $main::fault eq 'native' ? 768 : 800 }
package main;
require onpc_parent_about;
my $ok = eval { onpc_parent_about::run(sub { push @events, ['stage', $_[0]]; }, $review); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''

STANDARD_RECIPIENT_PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
our $tag;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub assert_screen {
    $main::tag = $_[0];
    return {area => [{x => 443, y => 444, w => 121, h => 29, similarity => 1,
        click_point => {xpos => 60, ypos => 14}}]};
}
sub mouse_set { push @main::events, ['pointer', @_]; }
sub mouse_click { push @main::events, ['click', $main::tag]; }
sub mouse_hide { }
sub get_var { $_[1] }
sub console { bless {}, 'Console' }
sub send_key { push @main::events, ['key', $_[0]]; }
sub wait_still_screen { push @main::events, ['still']; }
sub check_screen { push @main::events, ['check', $_[0]]; 0 }
package Console;
sub mouse_width { 1280 }
sub mouse_height { 800 }
package main;
require onpc_gdm;
onpc_gdm::inspect_installed_standard();
print encode_json(\@events);
'''


@pytest.mark.parametrize('review', ['0', '1'])
@pytest.mark.parametrize('fault', ['recipient', 'click'])
def test_qualification_cannot_bypass_password_recipient_or_click_matches(review, fault):
    result = json.loads(run_perl(PROBE, review, fault).stdout)
    assert not result['ok']
    if fault == 'recipient':
        assert ['secret'] not in result['events']
    else:
        assert ['stage', 'parent-selected'] not in result['events']


def test_customer_missing_screen_stops_before_menu_input():
    result = json.loads(run_perl(PROBE, '0', 'screen').stdout)
    assert not result['ok']
    assert ['click', 'onpc-parent-menu'] not in result['events']


def test_fixed_standard_recipient_is_selected_before_opening_its_prompt():
    events = json.loads(run_perl(STANDARD_RECIPIENT_PROBE).stdout)
    assert events == [
        ['pointer', 628, 477],
        ['click', 'onpc-gdm-parent-installed-input-account'],
        ['still'], ['key', 'esc'], ['key', 'home'],
        *[['key', 'down']] * 4, ['key', 'ret'], ['still'],
        ['check', 'onpc-gdm-parent-installed-account'],
    ]


def test_qualification_can_acquire_nonsecret_screens_without_explicit_capture():
    result = json.loads(run_perl(PROBE, '1', 'screen').stdout)
    assert result['ok']
    assert ['check', 'onpc-parent-child-selected'] in result['events']
    assert ['assert', 'onpc-parent-desktop'] in result['events']
    assert ['assert', 'onpc-parent-app-grid'] in result['events']
    assert result['events'][-1] == ['power', 'off']


@pytest.mark.parametrize('fault,coordinates', [('', [1087, 67]), ('native', [870, 65])])
def test_pointer_uses_public_framebuffer_dimensions_and_matched_interior(fault, coordinates):
    result = json.loads(run_perl(PROBE, '0', fault).stdout)
    assert result['ok']
    assert ['pointer', *coordinates] in result['events']


@pytest.mark.parametrize('fault', ['dimensions', 'weak'])
def test_unsupported_display_or_weak_match_cannot_authorize_a_click(fault):
    result = json.loads(run_perl(PROBE, '0', fault).stdout)
    assert not result['ok']
    assert not any(event[0] in ('pointer', 'click', 'secret') for event in result['events'])
