"""SEARCH05 qualification routing, independent entry and no uncertain replay."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import check_e2e_parent_search_launch as check
import check_graphical_smoke as smoke
from owned_commands import CommandError
from parent_setup_qualification import KioskEntryQualification, ParentSearchLaunchQualification
from parent_search_launch import PLAN, ParentSearchLaunchJourney
from tests.support.perl import run_perl
from accessible_ui import UiError, validate_shell_metadata


@pytest.mark.parametrize('changes', [None, {'extra': 'field'}, {'locale': 'private\ntext'},
                                    {'keyboard': []}, {'keyboard': [['xkb', 'us', 'extra']]},
                                    {'version': 'v' * 129}])
def test_provider_tuple_is_bounded_and_sanitized(changes):
    value = {'version': '50.1-0ubuntu1.2', 'locale': 'en_US.UTF-8',
             'keyboard': [['xkb', 'us']]}
    value.update(changes or {})
    if changes:
        with pytest.raises(UiError, match='ui:shell-metadata'):
            validate_shell_metadata(value)
    else:
        assert validate_shell_metadata(value) == value


def test_selector_and_snapshot_journey(monkeypatch):
    context = SimpleNamespace()
    assert issubclass(ParentSearchLaunchQualification, KioskEntryQualification)
    assert isinstance(ParentSearchLaunchQualification.journey(context, Mock()),
                      ParentSearchLaunchJourney)
    assert context.installed_snapshot.startswith('onpc-v')
    assert set(PLAN.phases) == set(PLAN.stages)
    calls = []
    monkeypatch.setattr(check, 'smoke', lambda **kwargs: calls.append(kwargs) or 0)
    assert check.main() == 0
    assert calls == [{'assets': check.ASSETS, 'provision_credentials': True,
                      'parent_search_launch': True}]
    for other in ({'fresh_desktop': 'parent'}, {'shell_search_results': True},
                  {'parent_toggle': True}):
        with pytest.raises(CommandError, match='smoke:parent-search-prerequisites'):
            smoke.main(assets=check.ASSETS, provision_credentials=True,
                       parent_search_launch=True, **other)
    with pytest.raises(CommandError, match='smoke:parent-search-prerequisites'):
        smoke.main(parent_search_launch=True)


@pytest.mark.parametrize('fault', ['', 'uncertain', 'result', 'close-ready'])
def test_worker_two_independent_launches_and_terminal_failures(fault):
    result = json.loads(run_perl(r'''
use strict;
use warnings;
use JSON::PP;
our @events;
our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; $INC{'onpc_gdm.pm'} = 1; }
package onpc_gdm;
sub reattach_functional { }
package testapi;
sub record_info { }
sub type_string { push @main::events, ['query', $_[0]] }
sub send_key {
    push @main::events, ['key', $_[0]];
    die 'uncertain' if $main::fault eq 'uncertain' && $_[0] eq 'ret';
}
package main;
require onpc_parent_search_launch;
no warnings 'redefine';
*onpc_parent::sign_in = sub { $_[0]->seen('desktop') };
*onpc_journey::finish = sub { push @events, ['finish'] };
my $ok = eval {
    onpc_parent_search_launch::run(sub {
        my ($stage) = @_;
        push @events, ['seen', $stage];
        die 'wrong result' if $fault eq 'result' && $stage eq 'parent-window';
        die 'wrong owner' if $fault eq 'close-ready' && $stage eq 'close-ready';
        return {};
    });
    1;
};
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
''', fault).stdout)
    events = result['events']
    assert bool(result['ok']) == (not fault), result['error']
    assert events.count(['key', 'ret']) == (1 if fault else 2)
    assert events.count(['key', 'alt-f4']) == (0 if fault else 2)
    if not fault:
        assert events.count(['query', 'Oh No! Parent Control']) == 2
        wrong = events.index(['seen', 'repeat-wrong-entry'])
        assert events[wrong + 1] == ['seen', 'repeat-desktop']
        assert events[-2:] == [['seen', 'repeat-closed'], ['finish']]
    else:
        assert ['finish'] not in events
        assert not any('repeat-' in e[-1] for e in events)
