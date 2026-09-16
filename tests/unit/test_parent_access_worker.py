"""Execute E2E-004's real Perl worker with fixed graphical fakes."""

import json

import pytest

from tests.support.perl import run_perl


PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our $review = shift;
our $fault = shift;
our $legacy = shift // '';
our @events;
our $matched = '';
our $selected = '';
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub reset_consoles { }
sub select_console { }
sub assert_screen {
    push @main::events, ['assert', $_[0]];
    die 'missing standard recipient' if $main::fault eq 'recipient'
        && $_[0] eq 'onpc-gdm-other-child-masked-password';
    die 'wrong focused account' if $main::fault eq 'focused-row'
        && $_[0] eq 'onpc-gdm-standard-selected-account';
    die 'application pixels are forbidden' if !$main::legacy && $_[0] =~ /^onpc-parent-/;
    $main::matched = $_[0];
    return {area => [{x => 100, y => 100, w => 30, h => 30, similarity => 1,
        click_point => {xpos => 15, ypos => 15}}]};
}
sub assert_and_click { push @main::events, ['click', $_[0]]; }
sub check_screen {
    push @main::events, ['check', $_[0]];
    return $main::fault eq 'wrong-recipient'
        && $main::selected eq 'onpc-gdm-parent-installed-input-account'
        && $_[0] eq 'onpc-gdm-other-child-masked-password';
}
sub mouse_set { push @main::events, ['pointer', @_]; }
sub mouse_click {
    $main::selected = $main::matched;
    push @main::events, ['click', $main::legacy ? $main::matched : $_[0]];
}
sub mouse_hide { }
sub get_var { $_[0] eq 'NOVIDEO' ? '1' : $_[1] }
sub get_required_var {
    die 'wrong role' unless $_[0] eq '_SECRET_ONPC_OTHER_CHILD_PASSWORD';
    'unit-fixture-value';
}
sub type_password { push @main::events, ['secret']; }
sub type_string {
    die 'unpaced query' unless @_ == 3 && $_[1] eq 'max_interval' && $_[2] == 20;
    push @main::events, ['text', $_[0]];
}
sub send_key {
    push @main::events, ['key', $_[0]];
}
sub wait_still_screen { }
sub record_info { }
sub console { bless {}, 'Console' }
sub power { push @main::events, ['power', $_[0]]; }
sub check_shutdown { 1 }
package Console;
sub disable { }
sub mouse_width { 1024 }
sub mouse_height { 768 }
package main;
require onpc_parent_access;
my $ok = eval {
    my $exchange = sub {
        push @events, ['stage', $_[0]];
        die 'functional observation failed' if $fault eq $_[0];
        return {ui_pointer => {x => 700, y => 80}} if $_[0] eq 'app-grid';
        return {observed => $_[0]} if $_[0] eq 'system-prompt';
        return {observed => $_[0]} if $_[0] =~ /\Astandard-recipient-(?:qualified|rechecked)\z/;
        return {ui_keys => ['home', 'down']};
    };
    if ($legacy) {
        onpc_parent::login_standard(onpc_journey->new(
            exchange => $exchange, prefix => 'parent-access', review => $review));
    } else {
        onpc_parent_access::run($exchange, $review);
    }
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''


def test_customer_path_uses_fixed_recipient_and_normal_app_search():
    result = json.loads(run_perl(PROBE, "0", "").stdout)
    assert result["ok"], result
    stages = [event[1] for event in result["events"] if event[0] == "stage"]
    from parent_access import PLAN
    assert stages == list(PLAN.screen_tags)
    assert all(tag.startswith('ui:') for tag in PLAN.screen_tags.values())
    assert not any(event[0] in ('assert', 'check') for event in result['events'])
    assert result['events'].count(['click', 'left']) == 1
    point = result['events'].index(['pointer', 700, 80])
    assert result['events'][point:point + 3] == [
        ['pointer', 700, 80], ['click', 'left'], ['stage', 'search-focused']]
    assert result['events'].count(['secret']) == 1
    query = result["events"].index(["text", "O"])
    assert ''.join(event[1] for event in result['events'] if event[0] == 'text') == 'Oh No! Parent Control'
    assert result['events'][query:query + 3] == [
        ['text', 'O'], ['stage', 'search-started'], ['text', 'h No! Parent Control']]
    assert ["key", "ret"] not in result["events"][query:]
    assert result["events"][-1] == ["power", "off"]


@pytest.mark.parametrize("fault", ["recipient", "wrong-recipient", "focused-row"])
@pytest.mark.parametrize("review", ["0", "1"])
def test_unqualified_standard_recipient_refuses_secret_and_launcher_input(fault, review):
    result = json.loads(run_perl(PROBE, review, fault, 'legacy').stdout)
    assert not result["ok"]
    assert ["secret"] not in result["events"]
    assert not any(event[0] == "text" for event in result["events"])
    if fault == "focused-row":
        assert ["key", "ret"] not in result["events"]


@pytest.mark.parametrize("review", ["0", "1"])
@pytest.mark.parametrize("stage", ["desktop", "system-prompt", "app-grid", "search-focused", "search-started", "unavailable"])
def test_failed_functional_checkpoint_stops_without_replay_or_review_bypass(review, stage):
    result = json.loads(run_perl(PROBE, review, stage).stdout)
    assert not result["ok"]
    if review == '1':
        assert ['secret'] not in result['events']
        assert not any(event[0] == 'text' for event in result['events'])
        return
    assert result["events"][-1] == ["stage", stage]
    assert ["power", "off"] not in result["events"]
    if stage == 'search-started':
        assert [event for event in result['events'] if event[0] == 'text'] == [['text', 'O']]
    elif stage != "unavailable":
        assert not any(event[0] == "text" for event in result["events"])


def test_keyring_handling_belongs_to_shared_checkpoint_without_worker_escape():
    result = json.loads(run_perl(PROBE, '0', '').stdout)
    events = result['events'][result['events'].index(['stage', 'system-prompt']) + 1:]
    assert result['ok']
    assert events[0] == ['stage', 'app-grid']
    assert ['key', 'esc'] not in events


@pytest.mark.parametrize('stage', ['installed-greeter', 'other-parent-focused',
    'wrong-recipient-refused', 'standard-list', 'standard-focused',
    'standard-recipient-qualified', 'standard-recipient-rechecked'])
def test_standard_functional_credential_gate_refuses_before_secret(stage):
    result = json.loads(run_perl(PROBE, '0', stage).stdout)
    assert not result['ok']
    assert result['events'][-1] == ['stage', stage]
    assert ['secret'] not in result['events']
    assert not any(event[0] == 'text' for event in result['events'])
