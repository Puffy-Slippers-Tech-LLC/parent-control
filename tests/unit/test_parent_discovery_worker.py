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
sub type_string { }
sub send_key { }
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
    my $exchange = sub { push @events, ['stage', $_[0]]; };
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
    assert stages[-5:] == [
        "parent-selected", "fixture-requested", "new-child-visible",
        "new-child-selected", "existing-returned",
    ]
    assert ["click", "onpc-parent-new-child-choice"] in result["events"]
    assert result["events"][-1] == ["power", "off"]


def test_missing_new_child_stops_before_new_child_input_or_shutdown():
    result = json.loads(run_perl(PROBE, "existing", "new-choice").stdout)
    assert not result["ok"]
    assert ["click", "onpc-parent-new-child-choice"] not in result["events"]
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
