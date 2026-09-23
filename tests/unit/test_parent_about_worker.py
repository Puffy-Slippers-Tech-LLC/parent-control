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
    die 'picker failed' if $fault eq 'click' && $_[0] eq 'child-picker-opened';
    die 'selection failed' if $fault eq 'screen' && $_[0] eq 'parent-selected';
    push @events, ['stage', $_[0]];
    die 'observation refused' if $fault eq $_[0];
    return {ui_focused => 1} if $_[0] =~ /(?:greeter|list|picker-opened)$/;
    return {observed => $_[0]};
};
my $ok = eval {
    if ($entry eq 'legacy') {
        my $journey = onpc_journey->new(exchange => $exchange, prefix => 'unit', review => $review);
        onpc_parent::login($journey, 1);
    } elsif ($entry eq 'denial') {
        require onpc_parent_terminal;
        onpc_parent_terminal::run($exchange);
    } elsif ($entry) {
        my $journey = onpc_journey->new(exchange => $exchange, prefix => 'unit', review => $review);
        my $proof = $fault eq 'missing' ? {} : $journey->seen('license');
        $journey->seen('about') if $fault eq 'stale';
        onpc_about::return_to_parent($journey, $proof, 'semantic-reveal');
        onpc_about::return_to_parent($journey, $proof, 'semantic-reveal') if $fault eq 'replay';
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


@pytest.mark.parametrize('entry', ['', 'denial'])
def test_parent_cases_share_direct_command_and_independent_expected_result(entry):
    from parent_about import PLAN as ABOUT_PLAN
    from parent_terminal import PLAN as DENIAL_PLAN
    result = json.loads(run_perl(PROBE, '0', '', entry).stdout)
    assert result['ok'], result
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    assert stages == list((DENIAL_PLAN if entry else ABOUT_PLAN).screen_tags)
    index = stages.index('parent-command')
    assert stages[index - 1] == 'desktop'
    assert stages[index + 1] == ('management-denied' if entry else 'parent-window')
    assert not any(event[0] == 'text' or event == ['key', 'ctrl-alt-t']
                   or event == ['key', 'super-a'] for event in result['events'])


@pytest.mark.parametrize('entry', ['', 'denial'])
@pytest.mark.parametrize('fault', ['parent-command', 'result'])
def test_direct_launch_uncertainty_or_missing_result_stops_case(entry, fault):
    stage = ('management-denied' if entry else 'parent-window') if fault == 'result' else fault
    result = json.loads(run_perl(PROBE, '0', stage, entry).stdout)
    assert not result['ok']
    assert ['power', 'off'] not in result['events']
    assert result['events'].count(['stage', 'parent-command']) == 1
    assert not any(event[0] == 'text' or event == ['key', 'ctrl-alt-t']
                   or event == ['key', 'super-a'] for event in result['events'])


@pytest.mark.parametrize('expected', ['management', 'denied'])
@pytest.mark.parametrize('fault', ['', 'stale', 'binding', 'uncertain'])
def test_shared_launch_consumes_independent_desktop_once(expected, fault):
    result = json.loads(run_perl(r'''
use strict;
use warnings;
use JSON::PP;
our @events;
my ($expected, $fault) = @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
package main;
require onpc_parent;
require onpc_journey;
my $journey = onpc_journey->new(prefix => 'unit', review => 0, exchange => sub {
    push @events, $_[0];
    die 'uncertain submission' if $fault eq 'uncertain' && $_[0] eq 'parent-command';
    return {};
});
my $desktop = $journey->seen('desktop');
$journey->seen('unrelated') if $fault eq 'stale';
@events = ();
my $ok = eval { onpc_parent::launch($journey, $desktop,
    $fault eq 'binding' ? 'whole-query' : $expected); 1; };
my $replay = eval { onpc_parent::launch($journey, $desktop, $expected); 1; };
print encode_json({ok => $ok ? 1 : 0, replay => $replay ? 1 : 0, events => \@events});
''', expected, fault).stdout)
    assert result['ok'] == (not fault)
    # A rejected binding has consumed no input/proof; a corrected first call
    # remains possible. Submitted, uncertain and stale calls cannot replay.
    assert bool(result['replay']) == (fault == 'binding')
    target = 'parent-window' if expected == 'management' else 'management-denied'
    assert result['events'] == ([] if fault == 'stale' else ['parent-command']
                                if fault == 'uncertain' else ['parent-command', target])


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


@pytest.mark.parametrize('window,before,after', [
    ('license', 'license', 'license-closed'),
    ('about', 'about-returned', 'parent-returned'),
    ('management-denied', 'management-denied', 'denial-closed'),
])
@pytest.mark.parametrize('fault', ['', 'stale', 'missing', 'uncertain', 'result', 'binding'])
def test_shared_window_close_requires_fresh_proof_and_cannot_replay(window, before, after, fault):
    result = json.loads(run_perl(r'''
use strict;
use warnings;
use JSON::PP;
our @events;
our ($window, $before, $after, $fault) = @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key {
    push @main::events, $_[0];
    die 'uncertain' if $main::fault eq 'uncertain';
}
package main;
require onpc_window;
require onpc_journey;
my $journey = onpc_journey->new(prefix => 'independent', review => 0, exchange => sub {
    push @events, $_[0];
    die 'missing result' if $fault eq 'result' && $_[0] eq $after;
    return {};
});
my $proof = $fault eq 'missing' ? {} : $journey->seen($before);
$journey->seen('unrelated') if $fault eq 'stale';
@events = ();
my $ok = eval { onpc_window::close($journey, $fault eq 'binding' ? 'unknown' : $window, $proof); 1; };
my $replay = eval { onpc_window::close($journey, $fault eq 'binding' ? 'unknown' : $window, $proof); 1; };
print encode_json({ok => $ok ? 1 : 0, replay => $replay ? 1 : 0, events => \@events});
''', window, before, after, fault).stdout)
    assert bool(result['ok']) == (not fault)
    assert not result['replay']
    assert result['events'] == ([] if fault in ('stale', 'missing', 'binding')
                                else ['alt-f4'] if fault == 'uncertain'
                                else ['alt-f4', after])


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


@pytest.mark.parametrize('stage', ['recipient-qualified', 'recipient-rechecked'])
def test_about_sign_in_requires_two_fresh_recipient_checks(stage):
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
    assert ['stage', 'wrong-recipient-refused'] not in events
    assert ['key', 'esc'] not in events[:index]
    assert not any(event[0] in ('assert', 'check', 'pointer', 'click') for event in events)
