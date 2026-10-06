"""Link-only qualification safety; no external document is opened."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import check_e2e_license_viewer as check
import check_e2e_parent_website as website_check
import check_e2e_parent_privacy as privacy_check
import check_e2e_parent_support as support_check
import check_e2e_read_parent_information_links as information_check
import check_graphical_smoke as smoke
from license_viewer_provider import (
    PLAN, WEBSITE_PLAN, PRIVACY_PLAN, SUPPORT_PLAN, LicenseViewerProviderJourney,
    ParentWebsiteJourney, ParentPrivacyJourney, ParentSupportJourney,
    INFORMATION_PLAN, ParentInformationJourney)
from owned_commands import CommandError
from parent_setup_qualification import (
    KioskEntryQualification, LicenseViewerProviderQualification, ParentWebsiteQualification,
    ParentPrivacyQualification, ParentSupportQualification, ParentInformationQualification)
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


@pytest.mark.parametrize('link,qualification,journey_class,plan,check_module', [
    ('website', ParentWebsiteQualification, ParentWebsiteJourney, WEBSITE_PLAN, website_check),
    ('privacy', ParentPrivacyQualification, ParentPrivacyJourney, PRIVACY_PLAN, privacy_check),
    ('support', ParentSupportQualification, ParentSupportJourney, SUPPORT_PLAN, support_check),
    ('information', ParentInformationQualification, ParentInformationJourney,
     INFORMATION_PLAN, information_check),
])
def test_link_binding_reaches_shared_plan_and_owned_snapshot(
        monkeypatch, link, qualification, journey_class, plan, check_module):
    context = SimpleNamespace()
    journey = qualification.journey(context, Mock())
    assert isinstance(journey, journey_class)
    assert journey.plan is plan
    assert context.installed_snapshot.startswith('onpc-v')
    assert plan.worker_mode == 'parent_' + link
    operation = 'parent-information-clickable' if link == 'information' else f'{link}-clickable'
    assert plan.screen_tags['license'] == 'ui:' + operation
    assert plan.screen_tags['license-provider-refusals'] == 'ui:' + operation
    assert plan.settings_checks == PLAN.settings_checks
    if link == 'information':
        assert list(plan.screen_tags).index('parent-selected') < list(
            plan.screen_tags).index('help') < list(plan.screen_tags).index('about')
    calls = []
    monkeypatch.setattr(check_module, 'smoke', lambda **kwargs: calls.append(kwargs) or 0)
    assert check_module.main() == 0
    assert calls == [{'assets': check_module.ASSETS, 'provision_credentials': True,
                      'license_viewer_provider': True, 'information_link': link}]
    with pytest.raises(CommandError, match='smoke:information-link-binding'):
        smoke.main(information_link=link)
    with pytest.raises(CommandError, match='smoke:information-link-binding'):
        smoke.main(information_link='legal')


@pytest.mark.parametrize('link,fault', [
    (link, fault)
    for link in ('license', 'website', 'privacy', 'support', 'information')
    for fault in ('', 'help', 'about', 'license', 'refusals', 'close-input', 'return')
    if fault != 'help' or link == 'information'
])
def test_worker_checks_link_and_closes_only_owned_about(fault, link):
    result = json.loads(run_perl(r'''
use strict;
use warnings;
use JSON::PP;
our @events;
our @labels;
our $fault = shift @ARGV;
our $link = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { push @main::labels, $_[0] }
sub send_key {
    push @main::events, ['key', $_[0]];
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
        die 'missing help' if $fault eq 'help' && $stage eq 'help';
        die 'missing about' if $fault eq 'about' && $stage eq 'about';
        die 'missing license' if $fault eq 'license' && $stage eq 'license';
        die 'missing refusals' if $fault eq 'refusals' && $stage eq 'license-provider-refusals';
        die 'uncertain close' if $fault eq 'close-input' && $stage eq 'parent-returned';
        die 'missing return' if $fault eq 'return' && $stage eq 'license-closed';
        return {};
    }, $link);
    1;
};
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events,
                   labels => \@labels});
''', fault, link).stdout)
    events = result['events']
    prefix = 'license-provider' if link == 'license' else 'parent-' + link
    assert result['labels'] and all(label.startswith(prefix + '-')
                                   for label in result['labels'])
    assert bool(result['ok']) == (not fault), result['error']
    assert events.count(['seen', 'license']) == (0 if fault in ('help', 'about') else 1)
    assert events.count(['seen', 'license-provider-refusals']) == (
        0 if fault in ('help', 'about', 'license') else 1)
    assert not any(event[0] == 'key' for event in events)
    assert events.count(['seen', 'parent-returned']) == (1 if fault in ('', 'close-input') else 0)
    if fault:
        assert ['finish'] not in events
        assert events[-1] == ['seen', {
            'help': 'help', 'about': 'about', 'license': 'license',
            'refusals': 'license-provider-refusals', 'close-input': 'parent-returned',
            'return': 'license-closed',
        }[fault]]
        assert ('uncertain close' if fault == 'close-input'
                else 'missing ' + fault) in result['error']
    else:
        assert [event[1] for event in events if event[0] == 'seen'] == [
            'parent-selected', *(['help'] if link == 'information' else []),
            'about', 'license', 'license-provider-refusals', 'license-closed',
            'about-returned', 'parent-returned']
        assert events[-1] == ['finish']
