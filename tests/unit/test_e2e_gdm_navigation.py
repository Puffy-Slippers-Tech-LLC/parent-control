"""Ordinary GDM account-navigation qualification contracts."""

import json
from pathlib import Path

from tests.support.paths import ROOT
from tests.support.perl import run_perl


RUN = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
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
    onpc_gdm::navigation_qualification(sub {
        my ($stage) = @_;
        push @events, ['exchange', $stage];
        return {ui_focused => 1} if $stage =~ /-list\z/;
        return {observed => $stage};
    });
    1;
};
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
'''


def test_worker_repeats_selection_from_an_independent_list_and_escapes_once():
    result = json.loads(run_perl(RUN).stdout)
    assert result['ok'], result['error']
    assert [event[1] for event in result['events'] if event[0] == 'exchange'] == [
        'initial-list', 'initial-focused', 'initial-prompt', 'initial-returned',
        'repeated-list', 'repeated-focused', 'repeated-prompt', 'repeated-returned',
    ]
    assert [event[1] for event in result['events'] if event[0] == 'key'] == [
        'ret', 'esc', 'ret', 'esc']
    assert result['events'][-3:] == [
        ['disable'], ['power', 'off'], ['stage', 'shutdown']]


def test_gdm_navigation_qualification_reuses_the_prepared_app_snapshot():
    import check_e2e_gdm_navigation as check
    from parent_setup_qualification import GdmNavigationQualification

    assert check.ASSETS == Path('/tmp/onpc-parent-setup-input')
    context = type('Context', (), {})()
    journey = GdmNavigationQualification.journey(context, lambda *_: None)
    assert context.installed_snapshot == 'onpc-v1.1'
    assert list(journey.plan.screen_tags) == [
        'initial-list', 'initial-focused', 'initial-prompt', 'initial-returned',
        'repeated-list', 'repeated-focused', 'repeated-prompt', 'repeated-returned',
    ]


def test_gdm_navigation_is_the_fixed_argument_free_integration_selector():
    source = (ROOT / 'tests/integration/check_e2e_gdm_navigation.py').read_text()
    assert "ASSETS = Path('/tmp/onpc-parent-setup-input')" in source
    assert 'gdm_navigation=True' in source
    assert 'sys.argv' not in source
