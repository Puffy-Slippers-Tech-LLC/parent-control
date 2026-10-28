"""Private natural-expiry plan refusal before guest actions."""
import json

import pytest

from natural_expiry import PLAN
from tests.support.perl import run_perl


WORKER = r'''
use strict; use warnings; use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; $INC{'onpc_gdm.pm'} = 1; $INC{'onpc_password.pm'} = 1; }
package testapi;
sub record_info { push @main::events, ['title', $_[0]]; }
sub send_key { push @main::events, ['input', $_[0]]; }
sub power { }
sub check_shutdown { 1 }
sub console { bless {}, 'Console' }
package Console;
sub disable { }
package onpc_gdm;
sub reattach_functional { }
sub sign_in_challenge {
 my ($j, $id, $greeter, $focused, $desktop) = @_;
 my $child = $id eq 'child-login';
 $j->invoke($greeter); $j->invoke($focused);
 $j->invoke($child ? 'fresh-child-recipient-qualified' : 'recipient-qualified');
 $j->invoke($child ? 'fresh-child-recipient-rechecked' : 'recipient-rechecked');
 return $j->invoke($desktop);
}
package main;
require onpc_challenges;
my $plan = decode_json($ARGV[0]);
my $exchange = sub {
 push @events, ['stage', $_[0]];
 die 'fixture:refused' if $_[0] eq ($ENV{ONPC_TEST_REFUSE} // '');
 return {observed => $_[0], ui_focused => JSON::PP::true};
};
my $ok = eval { onpc_challenges::natural_expiry($exchange, $plan->{invocations}, $plan->{challenges}); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events, error => "$@"});
'''


@pytest.mark.parametrize('fault', ['missing-final-stage', 'wrong-child', 'missing-challenge'])
def test_worker_refuses_invalid_plan_before_any_guest_stage(fault):
    invocations = list(PLAN.invocations)
    challenges = {key: list(value) for key, value in PLAN.challenges.items()}
    if fault == 'missing-final-stage':
        invocations.pop()
    elif fault == 'wrong-child':
        challenges['child-login'][0] = 'other-child'
    else:
        challenges.pop('child-login')
    result = json.loads(run_perl(WORKER, json.dumps({
        'invocations': invocations, 'challenges': challenges})).stdout)
    assert not result['ok'] and 'natural-expiry:plan' in result['error']
    assert result['events'] == []
