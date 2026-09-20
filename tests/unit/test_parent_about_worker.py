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
our $entry = shift // '';
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
my $exchange = sub {
    die 'checkpoint failed' if $fault eq 'checkpoint' && $_[0] eq 'license-closed';
    die 'recipient refused' if $fault eq $_[0] && $_[0] =~ /recipient/;
    die 'picker failed' if $fault eq 'click' && $_[0] eq 'child-picker-opened';
    die 'selection failed' if $fault eq 'screen' && $_[0] eq 'parent-selected';
    push @events, ['stage', $_[0]];
    return {ui_focused => 1} if $_[0] =~ /(?:greeter|list|picker-opened)$/;
    return {observed => $_[0]};
};
my $ok = eval {
    if ($entry eq 'legacy') {
        my $journey = onpc_journey->new(exchange => $exchange, prefix => 'unit', review => $review);
        onpc_parent::login($journey, 1);
    } elsif ($entry) {
        my $journey = onpc_journey->new(exchange => $exchange, prefix => 'unit', review => $review);
        my $proof = $fault eq 'missing' ? {} : $journey->seen('license');
        $journey->seen('about') if $fault eq 'stale';
        onpc_parent_about::return_to_parent($journey, $proof, 'semantic-reveal');
        onpc_parent_about::return_to_parent($journey, $proof, 'semantic-reveal') if $fault eq 'replay';
    } else {
        onpc_parent_about::run($exchange, $review);
    }
    1;
};
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
my $ok = eval { onpc_gdm::inspect_installed_standard(); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events, error => "$@"});
'''


@pytest.mark.parametrize('review', ['0', '1'])
@pytest.mark.parametrize('fault', ['recipient', 'click'])
def test_qualification_cannot_bypass_password_recipient_or_click_matches(review, fault):
    result = json.loads(run_perl(PROBE, review, fault, 'legacy' if fault == 'recipient' else '').stdout)
    assert not result['ok']
    if fault == 'recipient':
        assert ['secret'] not in result['events']
    else:
        assert ['stage', 'parent-selected'] not in result['events']


def test_customer_failed_selection_stops_before_about():
    result = json.loads(run_perl(PROBE, '0', 'screen').stdout)
    assert not result['ok']
    assert ['stage', 'about'] not in result['events']


def test_legacy_standard_recipient_route_refuses_before_backend_or_input():
    result = json.loads(run_perl(STANDARD_RECIPIENT_PROBE).stdout)
    assert not result['ok']
    assert result['events'] == []
    assert 'provider-id-required' in result['error']


def test_functional_journey_uses_semantic_results_without_explicit_capture():
    result = json.loads(run_perl(PROBE, '0', '').stdout)
    assert result['ok']
    assert ['stage', 'child-picker-opened'] in result['events']
    assert ['stage', 'parent-selected'] in result['events']
    assert ['stage', 'parent-returned'] in result['events']
    assert not any(event[0] == 'assert' and event[1].startswith('onpc-parent-')
                   for event in result['events'])
    assert result['events'][-1] == ['power', 'off']


@pytest.mark.parametrize('fault', ['', 'missing', 'stale', 'replay', 'checkpoint'])
def test_return_block_accepts_independent_entry_and_never_replays_uncertain_input(fault):
    result = json.loads(run_perl(PROBE, '0', fault, 'return').stdout)
    assert result['ok'] == (not fault)
    keys = [event[1] for event in result['events'] if event[0] == 'key']
    if fault in ('missing', 'stale'):
        assert not keys
    elif fault == 'checkpoint':
        assert keys == ['alt-f4']
    else:
        assert keys == ['alt-f4', 'alt-f4']
    assert not any(event[0] in ('secret', 'click', 'text') for event in result['events'])


def test_close_observation_precedes_semantic_footer_reveal_and_return_close():
    result = json.loads(run_perl(PROBE, '0', '', 'return').stdout)
    assert result['events'] == [
        ['stage', 'license'], ['key', 'alt-f4'], ['stage', 'license-closed'],
        ['stage', 'about-returned'],
        ['key', 'alt-f4'], ['stage', 'parent-returned'],
    ]


@pytest.mark.parametrize('fault', ['', 'native'])
def test_legacy_parent_login_refuses_before_pointer_or_secret(fault):
    result = json.loads(run_perl(PROBE, '0', fault, 'legacy').stdout)
    assert not result['ok']
    assert not any(event[0] in ('pointer', 'click', 'secret') for event in result['events'])


@pytest.mark.parametrize('fault', ['dimensions', 'weak'])
def test_unsupported_display_or_weak_match_cannot_authorize_a_click(fault):
    result = json.loads(run_perl(PROBE, '0', fault, 'legacy').stdout)
    assert not result['ok']
    assert not any(event[0] in ('pointer', 'click', 'secret') for event in result['events'])


@pytest.mark.parametrize('stage', ['wrong-recipient-refused', 'recipient-qualified', 'recipient-rechecked'])
def test_about_sign_in_requires_wrong_recipient_refusal_and_two_fresh_checks(stage):
    result = json.loads(run_perl(PROBE, '0', stage).stdout)
    assert not result['ok']
    assert ['secret'] not in result['events']


def test_about_sign_in_uses_functional_proofs_immediately_before_one_secret():
    result = json.loads(run_perl(PROBE, '0', '').stdout)
    assert result['ok']
    events = result['events']
    assert events.count(['secret']) == 1
    index = events.index(['secret'])
    assert events[index - 2:index] == [
        ['stage', 'recipient-qualified'], ['stage', 'recipient-rechecked']]
    assert events.index(['stage', 'wrong-recipient-refused']) < index - 2
    assert not any(event[0] in ('assert', 'check', 'pointer', 'click') for event in events)
