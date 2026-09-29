"""Link-only qualification safety; no external document is opened."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import check_e2e_license_viewer as check
import check_graphical_smoke as smoke
from license_viewer_provider import PLAN, LicenseViewerProviderJourney
from owned_commands import CommandError
from parent_setup_qualification import KioskEntryQualification, LicenseViewerProviderQualification
from tests.support.perl import run_perl


def test_selector_uses_owned_snapshot_and_refuses_conflicting_routes(monkeypatch):
    context = SimpleNamespace()
    assert issubclass(LicenseViewerProviderQualification, KioskEntryQualification)
    assert isinstance(LicenseViewerProviderQualification.journey(context, Mock()),
                      LicenseViewerProviderJourney)
    assert context.installed_snapshot.startswith('onpc-v')
    assert set(PLAN.phases) == set(PLAN.stages)
    assert list(PLAN.screen_tags).index('license') < list(
        PLAN.screen_tags).index('license-provider-refusals') < list(
        PLAN.screen_tags).index('license-closed')
    assert not any('launched' in stage for stage in PLAN.screen_tags)
    calls = []
    monkeypatch.setattr(check, 'smoke', lambda **kwargs: calls.append(kwargs) or 0)
    assert check.main() == 0
    assert calls == [{'assets': check.ASSETS, 'provision_credentials': True,
                      'license_viewer_provider': True}]
    with pytest.raises(CommandError, match='smoke:license-viewer-provider-prerequisites'):
        smoke.main(license_viewer_provider=True)
    with pytest.raises(CommandError, match='smoke:license-viewer-provider-prerequisites'):
        smoke.main(assets=check.ASSETS, provision_credentials=True,
                   license_viewer_provider=True, parent_terminal_provider=True)


@pytest.mark.parametrize('fault', ['', 'license', 'refusals',
                                   'close-input', 'return'])
def test_worker_checks_link_and_closes_only_owned_about(fault):
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
require onpc_license_viewer_provider;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { $_[0]->seen('parent-selected') };
*onpc_journey::finish = sub { push @events, ['finish'] };
my $ok = eval {
    onpc_license_viewer_provider::run(sub {
        my ($stage) = @_;
        push @events, ['seen', $stage];
        die 'missing license' if $fault eq 'license' && $stage eq 'license';
        die 'missing refusals' if $fault eq 'refusals' && $stage eq 'license-provider-refusals';
        die 'missing return' if $fault eq 'return' && $stage eq 'license-closed';
        return {};
    });
    1;
};
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
''', fault).stdout)
    events = result['events']
    assert bool(result['ok']) == (not fault), result['error']
    assert events.count(['seen', 'license']) == 1
    assert events.count(['seen', 'license-provider-refusals']) == (
        0 if fault == 'license' else 1)
    assert events.count(['key', 'alt-f4']) == {
        '': 1, 'license': 0, 'refusals': 0, 'close-input': 1, 'return': 0,
    }[fault]
    if fault:
        assert ['finish'] not in events
    else:
        assert events[-1] == ['finish']
