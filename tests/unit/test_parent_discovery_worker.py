"""Execute the real E2E-003 Perl worker with fixed graphical fakes."""

import json

import pytest

from tests.support.perl import run_perl


PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our $variant = shift;
our $fault = shift;
our @events;
our $matched = '';
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub reset_consoles { }
sub select_console { }
sub assert_screen {
    push @main::events, ['assert', $_[0]];
    die 'missing dynamic choice' if $main::fault eq 'new-choice'
        && $_[0] eq 'onpc-parent-new-child-choice';
    $main::matched = $_[0];
    return {area => [{x => 100, y => 100, w => 30, h => 30, similarity => 1,
        click_point => {xpos => 15, ypos => 15}}]};
}
sub check_screen { 0 }
sub mouse_set { }
sub mouse_click { push @main::events, ['click', $main::matched]; }
sub mouse_hide { }
sub get_var { $_[0] eq 'NOVIDEO' ? '1' : $_[1] }
sub get_required_var { 'unit-fixture-value' }
sub type_password { push @main::events, ['secret']; }
sub type_string { push @main::events, ['text', $_[0]]; }
sub send_key { push @main::events, ['key', $_[0]]; }
sub save_screenshot { die 'explicit capture forbidden'; }
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
require onpc_parent_discovery;
my $ok = eval {
    my $exchange = sub {
        push @events, ['stage', $_[0]];
        die 'failed functional observation' if $fault eq $_[0];
        return {observed => $_[0]} if $_[0] =~ /\Arecipient-(?:qualified|rechecked)\z/;
        return {ui_keys => ['home', 'down']};
    };
    $variant eq 'none' ? onpc_parent_discovery::run_none($exchange)
        : onpc_parent_discovery::run($exchange);
    1;
};
my $error = $@;
$error =~ s/\s+at .*//s;
print encode_json({ok => $ok ? 1 : 0, error => $error, events => \@events});
'''


def test_customer_worker_selects_existing_and_new_children_in_order():
    result = json.loads(run_perl(PROBE, "existing", "").stdout)
    assert result["ok"], result
    stages = [event[1] for event in result["events"] if event[0] == "stage"]
    from parent_discovery import PLAN
    assert stages == list(PLAN.screen_tags)
    assert not any(event[0] in ('assert', 'click') and event[1].startswith('onpc-parent-')
                   for event in result['events'])
    for stage in ('child-choice-highlighted', 'new-child-choice-highlighted',
                  'existing-child-choice-highlighted'):
        index = result['events'].index(['stage', stage])
        assert result['events'][index + 1] == ['key', 'ret']
    assert result["events"][-1] == ["power", "off"]


@pytest.mark.parametrize('stage', ['child-picker-opened', 'child-choice-highlighted',
    'installed-greeter', 'other-parent-focused', 'wrong-recipient-refused',
    'parent-list', 'parent-focused', 'recipient-qualified', 'recipient-rechecked',
    'parent-selected', 'fixture-requested', 'new-child-visible',
    'new-child-choice-highlighted', 'new-child-selected', 'new-child-apps',
    'existing-child-choice-highlighted', 'existing-returned'])
def test_failed_observation_stops_before_any_further_input_or_shutdown(stage):
    result = json.loads(run_perl(PROBE, "existing", stage).stdout)
    assert not result["ok"]
    assert result['events'][-1] == ['stage', stage]
    assert ["power", "off"] not in result["events"]


def test_empty_worker_observes_explanation_without_child_input():
    result = json.loads(run_perl(PROBE, "none", "").stdout)
    assert result["ok"], result
    stages = [event[1] for event in result["events"] if event[0] == "stage"]
    assert stages[-5:] == [
        "recipient-qualified", "desktop", "app-grid", "fixture-requested", "empty",
    ]
    assert not any(event == ["click", "onpc-parent-child-picker"]
                   for event in result["events"])
    assert result["events"][-1] == ["power", "off"]
