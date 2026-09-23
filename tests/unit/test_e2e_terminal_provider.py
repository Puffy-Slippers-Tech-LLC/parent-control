"""PARENT01 standard denial qualification and guarded route."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import check_e2e_terminal_provider as check
import check_graphical_smoke as smoke
from owned_commands import CommandError
from parent_setup_qualification import KioskEntryQualification, ParentTerminalProviderQualification
from parent_terminal_provider import PLAN, ParentTerminalProviderJourney
from tests.support.perl import run_perl


def test_selector_uses_owned_installed_snapshot_and_refuses_conflicts(monkeypatch):
    context = SimpleNamespace()
    assert issubclass(ParentTerminalProviderQualification, KioskEntryQualification)
    assert isinstance(ParentTerminalProviderQualification.journey(context, Mock()),
                      ParentTerminalProviderJourney)
    assert context.installed_snapshot.startswith('onpc-v')
    assert set(PLAN.phases) == set(PLAN.stages)
    calls = []
    monkeypatch.setattr(check, 'smoke', lambda **kwargs: calls.append(kwargs) or 0)
    assert check.main() == 0
    assert calls == [{'assets': check.ASSETS, 'provision_credentials': True,
                      'parent_terminal_provider': True}]
    for other in ({'shell_search': True}, {'parent_search_launch': True},
                  {'fresh_desktop': 'standard'}, {'parent_access': True}):
        with pytest.raises(CommandError, match='smoke:parent-terminal-provider-prerequisites'):
            smoke.main(assets=check.ASSETS, provision_credentials=True,
                       parent_terminal_provider=True, **other)
    with pytest.raises(CommandError, match='smoke:parent-terminal-provider-prerequisites'):
        smoke.main(parent_terminal_provider=True)


@pytest.mark.parametrize('fault', ['', 'command', 'denial', 'close-input', 'return'])
def test_worker_refuses_wrong_entry_and_requires_denial_and_return(fault):
    result = json.loads(run_perl(r'''
use strict;
use warnings;
use JSON::PP;
our @events;
our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key {
    push @main::events, ['key', $_[0]];
    die 'uncertain close' if $main::fault eq 'close-input';
}
package main;
require onpc_parent_terminal_provider;
no warnings 'redefine';
*onpc_parent::login_standard_functional = sub { $_[0]->seen('desktop') };
*onpc_journey::finish = sub { push @events, ['finish'] };
my $ok = eval {
    onpc_parent_terminal_provider::run(sub {
        my ($stage) = @_;
        push @events, ['seen', $stage];
        die 'uncertain command' if $fault eq 'command' && $stage eq 'entry-parent-command';
        die 'missing denial' if $fault eq 'denial' && $stage eq 'entry-management-denied';
        die 'missing return' if $fault eq 'return' && $stage eq 'entry-denial-closed';
        return {};
    });
    1;
};
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
''', fault).stdout)
    events = result['events']
    assert bool(result['ok']) == (not fault), result['error']
    assert events[:3] == [['seen', 'desktop'], ['seen', 'wrong-entry'],
                          ['seen', 'entry-desktop']]
    assert events.count(['seen', 'entry-parent-command']) == 1
    assert events.count(['key', 'alt-f4']) == (0 if fault in ('command', 'denial') else 1)
    if fault:
        assert ['finish'] not in events
    else:
        assert events[-3:] == [['key', 'alt-f4'], ['seen', 'entry-denial-closed'],
                               ['finish']]
