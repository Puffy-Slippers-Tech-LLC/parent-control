"""Direct credential guards: human decision time never authorizes stale input."""
import json
from unittest.mock import Mock

import pytest

import ui_observations
from private_artifacts import EvidenceError
from tests.support.perl import run_perl


@pytest.mark.parametrize('operation,previous,last_child,error', [
    ('gdm-child-time-denied', 'gdm-child-recipient-rechecked', 'child', 'denial-order'),
    ('gdm-child-denied-return-ready', 'gdm-child-time-denied', 'child', 'denial-child-changed'),
])
def test_named_gdm_denial_cannot_authorize_return_for_another_child(
        operation, previous, last_child, error):
    ui = ui_observations.UiObservations(None)
    ui.last_operation = previous
    ui.last_child = last_child
    ui.call = Mock(side_effect=AssertionError('guest observation after conclusive refusal'))
    with pytest.raises(EvidenceError, match=error):
        ui._observe(operation, child='existing')
    ui.call.assert_not_called()


def test_bound_prompt_wait_and_repeat_still_require_fresh_recipient_proofs(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(ui_observations.time, 'monotonic', lambda: clock[0])
    ui = ui_observations.UiObservations(None)
    ui.kiosk_request = ('child', 'parent', 30, False)
    ui._observe = Mock(return_value={})
    order = ui_observations.accessible_ui.BOUND_MATE_ORDER
    ui.observe(order[0])
    clock[0] += 45
    ui.observe(order[1])
    clock[0] += 1
    ui.observe(order[2])
    ui.observe(order[3])
    ui.observe('kiosk-request-estimate')
    ui.observe(order[0])
    ui.observe(order[1])
    clock[0] += 31
    calls = ui._observe.call_count
    with pytest.raises(EvidenceError, match='mate-stale-proof'):
        ui.observe(order[2])
    assert ui._observe.call_count == calls
    with pytest.raises(EvidenceError, match='challenge-previous-failure'):
        ui.observe(order[2])
    assert ui._observe.call_count == calls


@pytest.mark.parametrize('mode', ['two-requests', 'replay', 'wrong-scope', 'wrong-child',
                                 'profile-setup', 'profile-wrong-scope',
                                 'grant-request', 'grant-wrong-scope', 'grant-wrong-child'])
def test_composed_kiosk_secret_scope_and_single_use(mode):
    # Execute the real password guard; replace only the secret delivery sink.
    # No password is supplied, and each isolated Perl process owns its latch.
    result = run_perl(r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub current_console { 'sut' }
sub get_var { '1' }
package onpc_journey;
sub seen {
    my ($self, $stage) = @_;
    push @main::events, ['proof', $self->{stage_prefix} . $stage];
    return {observed => $self->{stage_prefix} . $stage};
}
package main;
require onpc_password;
{
    no warnings 'redefine';
    *onpc_password::type_fixture_secret = sub { push @events, ['delivery', $_[0], $_[3]]; };
}
my $mode = shift @ARGV;
my $first = bless {prefix => 'kiosk-delayed-approval-first', stage_prefix => 'first-',
    kiosk_request => ['child', 'parent', 30, 0], review => 0}, 'onpc_journey';
my $second = bless {%$first, prefix => 'kiosk-delayed-approval-second', stage_prefix => 'second-'}, 'onpc_journey';
$first->{stage_prefix} = 'second-' if $mode eq 'wrong-scope';
$first->{kiosk_request} = ['other-child', 'parent', 30, 0] if $mode eq 'wrong-child';
if ($mode =~ /^profile-/) {
    $first = bless {prefix => 'kiosk-delayed-approval-profile-request',
        stage_prefix => $mode eq 'profile-setup' ? 'profile-request-' : 'first-',
        review => 0}, 'onpc_journey';
}
if ($mode =~ /^grant-/) {
    $first = bless {prefix => 'grant-access-case-request',
        stage_prefix => $mode eq 'grant-wrong-scope' ? 'first-' : 'request-',
        kiosk_request => [$mode eq 'grant-wrong-child' ? 'child' : 'other-child', 'parent', 1200, 1],
        review => 0}, 'onpc_journey';
}
my $ok = eval {
    if ($mode =~ /^profile-/) {
        onpc_password::enter_kiosk_mate_password($first, 'request-1200');
    } elsif ($mode =~ /^grant-/) {
        onpc_password::enter_kiosk_mate_password($first, 'bound-request');
    } else {
        onpc_password::enter_kiosk_mate_password($first, 'bound-request');
        onpc_password::enter_kiosk_mate_password($mode eq 'replay' ? $first : $second, 'bound-request');
    }
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
''', mode)
    value = json.loads(result.stdout)
    deliveries = [event for event in value['events'] if event[0] == 'delivery']
    if mode == 'two-requests':
        assert value['ok'] == 1
        assert deliveries == [['delivery', 'parent', request + '-kiosk-mate-approval']
                               for request in ('first', 'second')]
        assert [event for event in value['events'] if event[0] == 'proof'] == [
            ['proof', request + '-approval-' + proof]
            for request in ('first', 'second') for proof in ('qualified', 'rechecked')]
    elif mode == 'grant-request':
        assert value['ok'] == 1
        assert deliveries == [['delivery', 'parent', 'request-kiosk-mate-approval']]
        assert [event for event in value['events'] if event[0] == 'proof'] == [
            ['proof', 'request-approval-' + proof] for proof in ('qualified', 'rechecked')]
    elif mode == 'profile-setup':
        assert value['ok'] == 1
        assert deliveries == [['delivery', 'parent', 'profile-request-kiosk-mate-request-1200']]
        assert [event for event in value['events'] if event[0] == 'proof'] == [
            ['proof', 'profile-request-approval-' + proof]
            for proof in ('qualified', 'rechecked')]
    else:
        assert value['ok'] == 0
        assert len(deliveries) == (1 if mode == 'replay' else 0)
