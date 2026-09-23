"""Fixed Shell search qualification, refusal, and owned attempt routing."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import check_e2e_shell_search_results as check
import check_graphical_smoke as smoke
from owned_commands import CommandError
from parent_setup_qualification import KioskEntryQualification, ShellSearchResultsQualification
from shell_search_results import PLAN, ShellSearchResultsJourney
from tests.support.perl import run_perl


def test_plan_binds_fresh_parent_entry_and_all_search_observations():
    context = SimpleNamespace()
    assert issubclass(ShellSearchResultsQualification, KioskEntryQualification)
    journey = ShellSearchResultsQualification.journey(context, Mock())
    assert isinstance(journey, ShellSearchResultsJourney)
    assert context.installed_snapshot == 'onpc-v1.1'
    assert PLAN.worker_mode == 'shell_search_results'
    assert list(PLAN.screen_tags)[-9:] == [
        'system-prompt', 'app-grid', 'search-focused', 'search-started',
        'search-entered', 'wrong-result-refused', 'result', 'search-cleared',
        'dismissed']
    assert PLAN.screen_tags['system-prompt'] == 'ui:fresh-parent-desktop'
    assert PLAN.screen_tags['dismissed'] == 'ui:shell-search-dismissed'


def test_fixed_selector_uses_owned_snapshot_attempt_and_refuses_other_modes(monkeypatch):
    calls = []
    monkeypatch.setattr(check, 'smoke', lambda **kwargs: calls.append(kwargs) or 0)
    assert check.main() == 0
    assert calls == [{'assets': check.ASSETS, 'provision_credentials': True,
                      'shell_search_results': True}]
    with pytest.raises(CommandError, match='smoke:fresh-desktop-prerequisites'):
        smoke.main(shell_search_results=True, fresh_desktop='parent')


def test_worker_consumes_fresh_entry_once_then_dismisses_and_finishes():
    source = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN {
    $INC{'onpc_progress.pm'} = 1;
    $INC{'onpc_journey.pm'} = 1;
    $INC{'onpc_parent.pm'} = 1;
    $INC{'onpc_gdm.pm'} = 1;
    $INC{'testapi.pm'} = 1;
}
package onpc_progress;
sub operation { }
package onpc_gdm;
sub reattach_functional { push @main::events, ['reattach'] }
package onpc_journey;
sub new { bless {}, shift }
sub seen { push @main::events, ['seen', $_[1]]; return {} }
sub consume_observation { push @main::events, ['consume', $_[1]] }
sub finish { push @main::events, ['finish'] }
package onpc_parent;
sub sign_in { push @main::events, ['sign-in', $_[1], $_[2]]; return {} }
sub open_search { push @main::events, ['open-search', $_[2]]; return {} }
sub focus_search { push @main::events, ['focus-search', $_[2]]; return {} }
package testapi;
sub type_string { push @main::events, ['type', $_[0]] }
sub send_key { push @main::events, ['key', $_[0]] }
package main;
require onpc_shell_search;
my $ok = eval { onpc_shell_search::run(sub {}); 1 };
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
'''
    result = json.loads(run_perl(source).stdout)
    assert result['ok'], result['error']
    assert result['events'] == [
        ['reattach'], ['sign-in', 'parent', 'success'],
        ['open-search', 'overview'], ['focus-search', 'overview'],
        ['consume', 'search-focused'], ['type', 'O'], ['seen', 'search-started'],
        ['type', 'h No! Parent Control'], ['seen', 'search-entered'],
        ['seen', 'wrong-result-refused'], ['seen', 'result'],
        ['key', 'esc'], ['seen', 'search-cleared'],
        ['key', 'super'], ['seen', 'dismissed'], ['finish'],
    ]
