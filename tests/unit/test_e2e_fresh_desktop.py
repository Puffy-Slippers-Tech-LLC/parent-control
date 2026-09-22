"""Fresh-login slice bindings and pre-lease safety."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import check_graphical_smoke as smoke
from owned_commands import CommandError
from fresh_desktop import FreshDesktopJourney
from parent_setup_qualification import (
    FreshParentDesktopQualification, FreshStandardDesktopQualification,
    KioskEntryQualification,
)
from private_artifacts import EvidenceError
from tests.support.perl import run_perl


@pytest.mark.parametrize('role,qualification,desktop', [
    ('parent', FreshParentDesktopQualification, 'ui:fresh-parent-desktop'),
    ('standard', FreshStandardDesktopQualification, 'ui:fresh-standard-desktop'),
])
def test_each_role_has_a_distinct_installed_login_and_desktop(role, qualification, desktop):
    assert issubclass(qualification, KioskEntryQualification)
    context = SimpleNamespace()
    journey = qualification.journey(qualification.__new__(qualification),
                                    context, lambda *_: None)
    assert context.installed_snapshot == 'onpc-v1.1'
    assert journey.plan.worker_mode == 'fresh_' + role + '_desktop'
    assert journey.plan.screen_tags['desktop'] == desktop
    assert list(journey.plan.screen_tags)[-3:] == [
        ('standard-' if role == 'standard' else '') + 'recipient-qualified',
        ('standard-' if role == 'standard' else '') + 'recipient-rechecked',
        'desktop',
    ]
    assert journey.plan.screen_tags['wrong-recipient-refused'] == 'ui:' + (
        'gdm-standard-wrong-recipient-refused' if role == 'standard'
        else 'gdm-wrong-recipient-refused')


def test_undeclared_role_refuses_before_any_guest_work():
    with pytest.raises(EvidenceError, match='fresh-desktop:role'):
        FreshDesktopJourney(SimpleNamespace(), Mock(), role='other')
    with pytest.raises(CommandError, match='smoke:fresh-desktop-prerequisites'):
        smoke.main(fresh_desktop='other')


def test_fixed_selector_uses_separate_fresh_attempts_and_owned_cleanup_route():
    import check_e2e_fresh_desktop as check

    calls = []
    def attempt(**kwargs):
        calls.append(kwargs)
        return 0
    original = check.smoke
    try:
        check.smoke = attempt
        assert check.main() == 0
        assert calls == [
            {'assets': check.ASSETS, 'provision_credentials': True,
             'fresh_desktop': role}
            for role in ('parent', 'standard')]
        calls.clear()
        check.smoke = lambda **kwargs: calls.append(kwargs) or 1
        assert check.main() == 1
        assert len(calls) == 1
    finally:
        check.smoke = original
    assert check.ASSETS == Path('/tmp/onpc-parent-setup-input')


@pytest.mark.parametrize('role,expected', [
    ('parent', 'parent'), ('standard', 'standard')])
def test_worker_uses_one_bound_login_then_owned_shutdown(role, expected):
    source = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; $INC{'onpc_parent.pm'} = 1; }
package testapi;
sub record_info { push @main::events, ['stage', $_[0]] }
sub console { bless {}, 'Console' }
sub power { push @main::events, ['power', $_[0]] }
sub check_shutdown { 1 }
package Console;
sub disable { push @main::events, ['disable'] }
package onpc_parent;
sub login_functional { push @main::events, ['login', 'parent'] }
sub login_standard_functional { push @main::events, ['login', 'standard'] }
package main;
require onpc_fresh_desktop;
my $ok = eval { onpc_fresh_desktop::run(sub { die 'unexpected exchange' }, $ARGV[0]); 1 };
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
'''
    import json
    result = json.loads(run_perl(source, role).stdout)
    assert result['ok'], result['error']
    assert result['events'] == [
        ['login', expected], ['disable'], ['power', 'off'], ['stage', 'shutdown']]
