"""Real keyring qualification stays bound to one guarded, owned attempt."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import check_e2e_desktop_keyring as check
import check_graphical_smoke as smoke
import keyring_prompt_fixture as fixture
from fresh_desktop import KeyringDesktopJourney, prepare_keyring
from owned_commands import CommandError
from parent_setup_qualification import KeyringStandardDesktopQualification
from private_artifacts import EvidenceError
from tests.support.perl import run_perl


def test_keyring_plan_keeps_gdm_safety_and_distinct_prompt_observation():
    context = SimpleNamespace()
    journey = KeyringStandardDesktopQualification.journey(
        KeyringStandardDesktopQualification.__new__(KeyringStandardDesktopQualification),
        context, Mock())
    assert isinstance(journey, KeyringDesktopJourney)
    assert context.installed_snapshot == 'onpc-v1.1'
    assert journey.plan.screen_tags['wrong-recipient-refused'] == (
        'ui:gdm-standard-wrong-recipient-refused')
    assert list(journey.plan.screen_tags)[-4:] == [
        'standard-recipient-qualified', 'standard-recipient-rechecked',
        'desktop', 'keyring-cancelled-desktop']
    assert journey.plan.stage_actions == {'desktop': 'prepare-keyring'}
    assert journey.plan.screen_tags['keyring-cancelled-desktop'] == 'ui:keyring-cancel-standard'


def test_fixed_selector_uses_separate_attempts_and_stops_after_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(check, 'smoke', lambda **kwargs: calls.append(kwargs) or 0)
    assert check.main() == 0
    assert calls == [
        {'assets': check.ASSETS, 'provision_credentials': True,
         'fresh_desktop': role}
        for role in ('parent', 'standard-keyring')]
    assert check.ASSETS == Path('/tmp/onpc-parent-setup-input')
    calls.clear()
    monkeypatch.setattr(check, 'smoke', lambda **kwargs: calls.append(kwargs) or 1)
    assert check.main() == 1
    assert len(calls) == 1
    with pytest.raises(CommandError, match='smoke:fresh-desktop-prerequisites'):
        smoke.main(fresh_desktop='standard-keyring')


def test_keyring_preparation_uses_guarded_fixed_guest_command():
    transport = SimpleNamespace(call=Mock(return_value=b'keyring-fixture:challenge-requested\n'))
    journey = SimpleNamespace(transport=transport)
    guard = Mock()
    assert prepare_keyring(journey, guard) == {'profile': 'locked-login-keyring'}
    assert guard.call_count == 2
    argv = transport.call.call_args.args[0]
    assert argv == ['/usr/bin/python3', '-I', '-', 'standard']
    assert transport.call.call_args.kwargs['timeout'] == 60
    assert b'keyring-fixture:challenge-requested' in transport.call.call_args.kwargs['input']
    transport.call.return_value = b'wrong-profile\n'
    with pytest.raises(EvidenceError, match='keyring-fixture:preparation'):
        prepare_keyring(journey, guard)


def test_guest_fixture_locks_only_its_login_collection_without_password(monkeypatch):
    account = SimpleNamespace(pw_name='onpc-child-jordan', pw_uid=1002)
    monkeypatch.setattr(fixture.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(fixture.sys, 'argv', ['keyring_prompt_fixture.py', 'standard'])
    monkeypatch.setattr(fixture.pwd, 'getpwnam', lambda _: account)
    monkeypatch.setattr(fixture.os, 'stat', lambda path, follow_symlinks: SimpleNamespace(
        st_uid=1002, st_mode=0o040700 if path == '/run/user/1002' else 0o140700))
    run = Mock()
    launch = Mock()
    monkeypatch.setattr(fixture.subprocess, 'run', run)
    monkeypatch.setattr(fixture.subprocess, 'Popen', launch)
    fixture.main()
    assert run.call_count == 2
    store, lock = [call.args[0] for call in run.call_args_list]
    lookup = launch.call_args.args[0]
    assert store[-5:] == ['store', '--collection=default',
                          '--label=ONPC disposable test item',
                          'onpc-e2e-fixture', 'keyring-cancel']
    assert lock[-2:] == ['lock', '--collection=default']
    assert lookup[-4:] == ['search', '--unlock', 'onpc-e2e-fixture', 'keyring-cancel']
    assert run.call_args_list[0].kwargs['input'] == b'fixture-only-value\n'
    assert launch.call_args.kwargs['start_new_session'] is True


def test_guest_fixture_rejects_unbound_role_before_process_launch(monkeypatch):
    run = Mock()
    monkeypatch.setattr(fixture.subprocess, 'run', run)
    monkeypatch.setattr(fixture.subprocess, 'Popen', run)
    monkeypatch.setattr(fixture.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(fixture.sys, 'argv', ['keyring_prompt_fixture.py', 'other'])
    with pytest.raises(SystemExit, match='keyring-fixture:arguments'):
        fixture.main()
    run.assert_not_called()


def test_keyring_worker_waits_for_prompt_cancel_after_one_login():
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
sub login_functional { die 'wrong role' }
sub login_standard_functional { push @main::events, ['login', 'standard'] }
package main;
require onpc_fresh_desktop;
{ no warnings 'redefine'; *onpc_journey::seen = sub {
    push @main::events, ['checkpoint', $_[1]]; return {};
}; }
my $ok = eval { onpc_fresh_desktop::run(sub { die 'unexpected exchange' }, 'standard', 1); 1 };
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
'''
    import json
    result = json.loads(run_perl(source).stdout)
    assert result['ok'], result['error']
    assert result['events'] == [
        ['login', 'standard'], ['checkpoint', 'keyring-cancelled-desktop'],
        ['disable'], ['power', 'off'], ['stage', 'shutdown']]
