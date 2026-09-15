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
    die 'missing unavailable screen' if $main::fault eq 'screen'
        && $_[0] eq 'onpc-parent-standard-unavailable';
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
sub mouse_set { }
sub mouse_click {
    $main::selected = $main::matched;
    push @main::events, ['click', $main::matched];
}
sub mouse_hide { }
sub get_var { $_[0] eq 'NOVIDEO' ? '1' : $_[1] }
sub get_required_var {
    die 'wrong role' unless $_[0] eq '_SECRET_ONPC_OTHER_CHILD_PASSWORD';
    'unit-fixture-value';
}
sub type_password { push @main::events, ['secret']; }
sub type_string { push @main::events, ['text', $_[0]]; }
sub send_key { push @main::events, ['key', $_[0]]; }
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
my $ok = eval { onpc_parent_access::run(
    sub { push @events, ['stage', $_[0]]; }, $review,
); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''


def test_customer_path_uses_fixed_recipient_and_normal_app_search():
    result = json.loads(run_perl(PROBE, "0", "").stdout)
    assert result["ok"], result
    stages = [event[1] for event in result["events"] if event[0] == "stage"]
    assert stages[-5:] == [
        "installed-greeter", "recipient-qualified", "desktop", "app-grid",
        "unavailable",
    ]
    query = result["events"].index(["text", "Oh No! Parent Control"])
    assert ["key", "ret"] not in result["events"][query:]
    assert result["events"][-1] == ["power", "off"]


@pytest.mark.parametrize("fault", ["recipient", "wrong-recipient", "focused-row"])
@pytest.mark.parametrize("review", ["0", "1"])
def test_unqualified_standard_recipient_refuses_secret_and_launcher_input(fault, review):
    result = json.loads(run_perl(PROBE, review, fault).stdout)
    assert not result["ok"]
    assert ["secret"] not in result["events"]
    assert not any(event[0] == "text" for event in result["events"])
    if fault == "focused-row":
        assert ["key", "ret"] not in result["events"]


@pytest.mark.parametrize("review", ["0", "1"])
def test_missing_unavailability_stops_strict_customer_but_review_only_acquires(review):
    result = json.loads(run_perl(PROBE, review, "screen").stdout)
    assert bool(result["ok"]) is (review == "1")
    if review == "0":
        assert ["stage", "unavailable"] not in result["events"]
        assert ["power", "off"] not in result["events"]
    else:
        assert ["check", "onpc-parent-standard-unavailable"] in result["events"]
        assert result["events"][-1] == ["power", "off"]
