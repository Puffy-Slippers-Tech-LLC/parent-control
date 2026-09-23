"""Standard search's guarded entry, sanitized evidence and terminal failures."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import check_e2e_shell_search as check
import check_graphical_smoke as smoke
from accessible_ui import STANDARD_OPERATIONS, UiError
from owned_commands import CommandError
from parent_setup_qualification import KioskEntryQualification, ShellSearchQualification
from shell_search import PLAN, ShellSearchJourney
from tests.support.perl import run_perl
from ui_observations import UiObservations


@pytest.mark.parametrize('failure', [None, 0, 1])
def test_fixed_selector_runs_separate_owned_attempts_and_stops_on_failure(monkeypatch, failure):
    calls = []
    def run(**kwargs):
        calls.append(kwargs)
        return 1 if len(calls) - 1 == failure else 0
    monkeypatch.setattr(check, 'smoke', run)
    assert check.main() == (failure is not None)
    assert calls == [
        {'assets': check.ASSETS, 'provision_credentials': True, mode: True}
        for mode in ('parent_search_launch', 'shell_search')[:1 if failure == 0 else 2]]


def test_standard_selector_binds_snapshot_and_refuses_conflicting_or_missing_prerequisites():
    context = SimpleNamespace()
    assert issubclass(ShellSearchQualification, KioskEntryQualification)
    assert isinstance(ShellSearchQualification.journey(context, Mock()), ShellSearchJourney)
    assert context.installed_snapshot.startswith('onpc-v')
    assert set(PLAN.phases) == set(PLAN.stages)
    assert PLAN.screen_tags['entry-unavailable'] == 'ui:standard-search-qualified'
    assert 'standard-search-qualified' in STANDARD_OPERATIONS
    for other in ({'fresh_desktop': 'standard'}, {'shell_search_results': True},
                  {'parent_search_launch': True}, {'parent_access': True}):
        with pytest.raises(CommandError, match='smoke:standard-search-prerequisites'):
            smoke.main(assets=check.ASSETS, provision_credentials=True,
                       shell_search=True, **other)
    with pytest.raises(CommandError, match='smoke:standard-search-prerequisites'):
        smoke.main(shell_search=True)


@pytest.mark.parametrize('fault', ['', 'uncertain', 'focus', 'query', 'absence'])
def test_worker_refuses_wrong_entry_then_reads_split_query_without_activation(fault):
    result = json.loads(run_perl(r'''
use strict;
use warnings;
use JSON::PP;
our @events;
our @titles;
our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; $INC{'onpc_gdm.pm'} = 1; }
package testapi;
sub record_info { push @main::titles, $_[0] }
sub type_string {
    push @main::events, ['query', $_[0]];
    die 'uncertain' if $main::fault eq 'uncertain';
}
sub send_key { push @main::events, ['key', $_[0]] }
package main;
require onpc_shell_search_standard;
no warnings 'redefine';
*onpc_parent::login_standard_functional = sub { $_[0]->seen('desktop') };
*onpc_journey::finish = sub { push @events, ['finish'] };
my $ok = eval {
    onpc_shell_search_standard::run(sub {
        my ($stage) = @_;
        push @events, ['seen', $stage];
        die 'lost focus' if $fault eq 'focus' && $stage eq 'entry-search-focused';
        die 'wrong query' if $fault eq 'query' && $stage eq 'entry-search-started';
        die 'incomplete absence' if $fault eq 'absence' && $stage eq 'entry-unavailable';
        return {};
    });
    1;
};
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events, titles => \@titles});
''', fault).stdout)
    events = result['events']
    assert result['titles'] == ['shell-search-' + event[1] for event in events
                                if event[0] == 'seen']
    assert bool(result['ok']) == (not fault), result['error']
    assert events[:2] == [['seen', 'desktop'], ['seen', 'entry-desktop']]
    assert [event for event in events if event[0] == 'key'] == [['key', 'super-a']]
    queries = [event[1] for event in events if event[0] == 'query']
    assert queries == ([] if fault == 'focus' else ['O'] if fault in ('uncertain', 'query')
                       else ['O', 'h No! Parent Control'])
    if fault:
        assert ['finish'] not in events
    else:
        assert events[-2:] == [['seen', 'entry-unavailable'], ['finish']]


@pytest.mark.parametrize('fault', ['', 'private', 'tuple'])
def test_standard_qualification_accepts_only_sanitized_provider_metadata(fault):
    provider = {'version': '50.1-0ubuntu1.2', 'locale': 'en_US.UTF-8',
                'keyboard': [['xkb', 'us']]}
    response = {'operation': 'standard-search-qualified', 'outcome': 'passed',
                'interface': 'AT-SPI', 'provider': provider}
    if fault == 'private': response['private'] = 'private-canary'
    if fault == 'tuple': provider['locale'] = 'private\ntext'
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(response).encode()))
    if fault:
        with pytest.raises((ValueError, UiError)):
            UiObservations(transport).observe('standard-search-qualified')
    else:
        assert UiObservations(transport).observe('standard-search-qualified') == response
