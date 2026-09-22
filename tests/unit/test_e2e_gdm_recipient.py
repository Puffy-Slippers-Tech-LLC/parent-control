"""GDM recipient qualification contracts."""

import json
from pathlib import Path

import pytest

from tests.support.paths import ROOT
from tests.support.perl import run_perl


RUN = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
our $fault = $ARGV[0] // '';
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub reset_consoles { push @main::events, ['reset'] }
sub select_console { push @main::events, ['console', $_[0]] }
sub send_key { push @main::events, ['key', $_[0]] }
sub record_info { push @main::events, ['stage', $_[0]] }
sub console { bless {}, 'Console' }
sub power { push @main::events, ['power', $_[0]] }
sub check_shutdown { 1 }
package Console;
sub disable { push @main::events, ['disable'] }
package main;
require onpc_gdm;
my $ok = eval {
    onpc_gdm::recipient_qualification(sub {
        my ($stage) = @_;
        push @events, ['exchange', $stage];
        return {ui_focused => 1} if $stage eq 'wrong-list' || $stage eq 'intended-list';
        return {observed => 'replayed'} if $fault eq $stage;
        return {observed => $stage};
    });
    1;
};
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
'''


def run(fault=''):
    return json.loads(run_perl(RUN, fault).stdout)


def test_worker_uses_wrong_refusal_two_fresh_proofs_and_one_escape_per_prompt():
    result = run()
    assert result['ok'], result['error']
    assert [event[1] for event in result['events'] if event[0] == 'exchange'] == [
        'wrong-list', 'wrong-focused', 'wrong-recipient-refused', 'wrong-returned',
        'intended-list', 'intended-focused', 'recipient-qualified', 'recipient-rechecked',
        'intended-prompt', 'intended-returned',
    ]
    assert [event[1] for event in result['events'] if event[0] == 'key'] == [
        'ret', 'esc', 'ret', 'esc']
    assert result['events'][-3:] == [
        ['disable'], ['power', 'off'], ['stage', 'shutdown']]


@pytest.mark.parametrize('fault', [
    'wrong-recipient-refused', 'recipient-qualified', 'recipient-rechecked',
    'intended-prompt',
])
def test_worker_rejects_replayed_or_wrong_prompt_proofs_before_later_input(fault):
    result = run(fault)
    assert not result['ok']
    keys = [event[1] for event in result['events'] if event[0] == 'key']
    if fault == 'wrong-recipient-refused':
        assert keys == ['ret']
    elif fault in ('recipient-qualified', 'recipient-rechecked'):
        assert keys == ['ret', 'esc', 'ret']
    else:
        assert keys == ['ret', 'esc', 'ret']


def test_gdm_recipient_qualification_reuses_the_prepared_app_snapshot():
    import check_e2e_gdm_recipient as check
    from parent_setup_qualification import GdmRecipientQualification

    assert check.ASSETS == Path('/tmp/onpc-parent-setup-input')
    context = type('Context', (), {})()
    journey = GdmRecipientQualification.journey(context, lambda *_: None)
    assert context.installed_snapshot == 'onpc-v1.1'
    assert list(journey.plan.screen_tags) == [
        'wrong-list', 'wrong-focused', 'wrong-recipient-refused', 'wrong-returned',
        'intended-list', 'intended-focused', 'recipient-qualified', 'recipient-rechecked',
        'intended-prompt', 'intended-returned',
    ]


def test_gdm_recipient_is_the_fixed_argument_free_integration_selector():
    source = (ROOT / 'tests/integration/check_e2e_gdm_recipient.py').read_text()
    assert "ASSETS = Path('/tmp/onpc-parent-setup-input')" in source
    assert 'gdm_recipient=True' in source
    assert 'sys.argv' not in source
